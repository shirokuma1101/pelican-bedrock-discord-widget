from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import deque
from contextlib import suppress
from typing import Any

import aiohttp
import websockets
from websockets.asyncio.client import ClientConnection

from .models import ConsoleSnapshot

log = logging.getLogger(__name__)

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# The timestamp/log prefix may be present:
# [2026-08-12 17:39:32:529 INFO] There are 1/20 players online:
PLAYER_COUNT_RE = re.compile(
    r"There are\s+(\d+)\s*/\s*(\d+)\s+players?\s+online\s*:?\s*(.*)$",
    re.I,
)

# Some versions use:
# There are 1 of a max of 20 players online:
PLAYER_COUNT_ALT_RE = re.compile(
    r"There are\s+(\d+)\s+of\s+a\s+max\s+of\s+(\d+)\s+players?\s+online\s*:?\s*(.*)$",
    re.I,
)

TIMESTAMP_LINE_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2} .*?\]")

# "akm19gu, xuid: 2535466811555748"
XUID_PLAYER_RE = re.compile(
    r"^\s*([^,]{1,32})\s*,\s*xuid\s*:\s*\d+\s*$",
    re.I,
)

JOIN_PATTERNS = (
    re.compile(r"(?:Player connected:|joined the game:?)\s*([^\s]+)", re.I),
    re.compile(r"^\[.*?\]\s*([^\s]+) joined the game", re.I),
)

LEAVE_PATTERNS = (
    re.compile(r"(?:Player disconnected:|left the game:?)\s*([^\s]+)", re.I),
    re.compile(r"^\[.*?\]\s*([^\s]+) left the game", re.I),
)


class WingsConsole:
    """Pelican/Pterodactyl-compatible Wings console WebSocket client."""

    def __init__(
        self,
        base_url: str,
        server_id: str,
        api_token: str,
        session: aiohttp.ClientSession,
        *,
        log_lines: int = 8,
        player_command_interval: int = 30,
        player_list_enabled: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.server_id = server_id
        self.api_token = api_token
        self.session = session
        self.log_lines = max(1, log_lines)
        self.player_command_interval = max(10, player_command_interval)
        self.player_list_enabled = player_list_enabled

        self._task: asyncio.Task | None = None
        self._ws: ClientConnection | None = None
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

        self._players: set[str] = set()
        self._console_online: int | None = None
        self._console_max: int | None = None
        self._logs: deque[str] = deque(maxlen=self.log_lines)
        self._connected = False
        self._last_error: str | None = None

        # True only while parsing the continuation lines immediately following
        # "There are N/M players online:".
        self._collecting_player_list = False

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(
                self._run(), name="wings-console"
            )

    async def stop(self) -> None:
        self._stop_event.set()

        if self._ws is not None:
            with suppress(Exception):
                await self._ws.close()

        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def snapshot(self) -> ConsoleSnapshot:
        async with self._lock:
            return ConsoleSnapshot(
                connected=self._connected,
                online_players=self._console_online,
                max_players=self._console_max,
                players=sorted(self._players, key=str.casefold),
                logs=list(self._logs),
                last_error=self._last_error,
            )

    async def _run(self) -> None:
        backoff = 2

        while not self._stop_event.is_set():
            try:
                await self._connect_and_listen()
                backoff = 2
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Wings WebSocket error: %s", exc)
                async with self._lock:
                    self._connected = False
                    self._last_error = str(exc)

            if self._stop_event.is_set():
                break

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    async def _get_credentials(self) -> tuple[str, str]:
        url = f"{self.base_url}/api/client/servers/{self.server_id}/websocket"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/vnd.pterodactyl.v1+json",
            "Content-Type": "application/json",
        }

        async with self.session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            body = await response.text()

            if response.status >= 400:
                raise RuntimeError(
                    f"WebSocket credential request failed "
                    f"{response.status}: {body[:500]}"
                )

            data: Any = json.loads(body)

            try:
                return data["data"]["socket"], data["data"]["token"]
            except (KeyError, TypeError) as exc:
                raise RuntimeError(
                    f"Unexpected WebSocket credential response: {data}"
                ) from exc

    async def _connect_and_listen(self) -> None:
        socket_url, jwt_token = await self._get_credentials()

        log.info(
            "Connecting to Wings WebSocket: %s",
            socket_url.split("?", 1)[0],
        )

        async with websockets.connect(
            socket_url,
            origin=self.base_url,
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
            max_size=2 * 1024 * 1024,
        ) as ws:
            self._ws = ws

            await ws.send(json.dumps({
                "event": "auth",
                "args": [jwt_token],
            }))

            await ws.send(json.dumps({
                "event": "send logs",
                "args": [None],
            }))

            async with self._lock:
                self._connected = True
                self._last_error = None
                self._logs.clear()

            log.info("Wings WebSocket connected")

            if self.player_list_enabled:
                await self._send_command("list")
                last_player_command = asyncio.get_running_loop().time()
            else:
                last_player_command = 0.0

            async for raw in ws:
                await self._handle_message(raw)

                if self.player_list_enabled:
                    now = asyncio.get_running_loop().time()
                    if now - last_player_command >= self.player_command_interval:
                        await self._send_command("list")
                        last_player_command = now

            async with self._lock:
                self._connected = False

            self._ws = None

    async def _send_command(self, command: str) -> None:
        if self._ws is None:
            return

        await self._ws.send(json.dumps({
            "event": "send command",
            "args": [command],
        }))

    async def _handle_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            log.debug("Ignoring non-JSON Wings message: %r", raw)
            return

        event = message.get("event")
        args = message.get("args") or []

        if event == "auth success":
            return

        if event in {"token expiring", "token expired"}:
            log.info("Wings WebSocket token event: %s", event)
            if self._ws is not None:
                await self._ws.close()
            return

        if event in {"jwt error", "daemon error"}:
            raise RuntimeError(f"{event}: {' '.join(str(x) for x in args)}")

        if event == "console output":
            text = _extract_text(args)
            if text:
                await self._process_console(text)

    async def _process_console(self, text: str) -> None:
        text = ANSI_RE.sub("", text).replace("\r", "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return

        async with self._lock:
            for raw_line in lines:
                line = raw_line.strip()

                # A new list response always supersedes the previous snapshot.
                count_match = (
                    PLAYER_COUNT_RE.search(line)
                    or PLAYER_COUNT_ALT_RE.search(line)
                )
                if count_match:
                    # `list` output is consumed by the player parser and is
                    # intentionally not shown in the Discord log field.
                    self._console_online = int(count_match.group(1))
                    self._console_max = int(count_match.group(2))

                    # Every `list` response is a synchronization point.  Do
                    # not carry names over from the previous response while
                    # the new continuation lines are still arriving.
                    self._players.clear()
                    self._collecting_player_list = self._console_online > 0

                    # Some Bedrock builds put the names on the same line.
                    inline = count_match.group(3).strip()
                    if inline and self._console_online > 0:
                        parsed = _parse_inline_players(inline)
                        self._players.update(parsed[: self._console_online])

                        if len(self._players) >= self._console_online:
                            self._collecting_player_list = False

                    continue

                # "list" is the command itself. It is not a player name.
                if line.lower() == "list":
                    self._collecting_player_list = False
                    continue

                if self._collecting_player_list:
                    # Ignore the timestamped/log lines that surround the result.
                    if TIMESTAMP_LINE_RE.match(line):
                        self._collecting_player_list = False
                    else:
                        players = _parse_player_list_line(line)
                        if players:
                            remaining = (
                                self._console_online - len(self._players)
                                if self._console_online is not None
                                else len(players)
                            )
                            self._players.update(players[:max(0, remaining)])

                            # Stop once the advertised number has been reached.
                            if (
                                self._console_online is not None
                                and len(self._players) >= self._console_online
                            ):
                                self._collecting_player_list = False

                            continue

                # XUID lines outside a `list` response are historical console
                # output, not useful status logs. Keep them out of the small
                # Discord log window as well.
                if XUID_PLAYER_RE.match(line):
                    continue

                self._logs.append(line[:500])

                # Live join/leave events keep the snapshot current between
                # explicit `list` responses.
                for pattern in JOIN_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        self._players.add(match.group(1))
                        break

                for pattern in LEAVE_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        self._players.discard(match.group(1))
                        break


def _extract_text(args: list[Any]) -> str:
    if not args:
        return ""

    value = args[0]
    return value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False
    )


def _parse_inline_players(value: str) -> list[str]:
    return [
        player
        for player in (
            _parse_player_line(item.strip()) for item in value.split(",")
        )
        if player
    ]


def _parse_player_list_line(line: str) -> list[str]:
    """Parse one player-list continuation line.

    Bedrock emits both one-name-per-line and comma-separated bare names.  An
    XUID record must be handled as one unit because its own format contains a
    comma.
    """
    line = line.strip()
    if XUID_PLAYER_RE.match(line):
        player = _parse_player_line(line)
        return [player] if player else []
    return [
        player
        for item in line.split(",")
        if (player := _parse_player_line(item.strip()))
    ]


def _parse_player_line(line: str) -> str | None:
    line = line.strip()

    # UUID/XUID form seen in Bedrock console output:
    #   PlayerName, xuid: 253546...
    match = XUID_PLAYER_RE.match(line)
    if match:
        return match.group(1).strip()

    # A bare gamertag on a continuation line:
    #   shirokuma1101
    # Avoid interpreting common console/status text as a player.
    lowered = line.casefold()
    if (
        1 <= len(line) <= 32
        and re.fullmatch(r"[A-Za-z0-9_]+", line) is not None
        and lowered not in {"list", "players", "online", "server", "started"}
    ):
        return line

    return None


__all__ = [
    "WingsConsole",
    "ANSI_RE",
    "PLAYER_COUNT_RE",
    "PLAYER_COUNT_ALT_RE",
    "_parse_player_line",
    "_parse_inline_players",
    "_parse_player_list_line",
]
