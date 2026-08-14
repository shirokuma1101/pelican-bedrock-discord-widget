from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class PlaytimeStore:
    """JSON-backed cumulative online-time store."""

    def __init__(self, filename: str) -> None:
        self.path = Path(filename)
        self._items: dict[str, dict] = {}
        self._load()

    @staticmethod
    def _key(player: str) -> str:
        return player.strip().casefold()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        self._items = raw if isinstance(raw, dict) else {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="playtime-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(self._items, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _ensure(self, player: str) -> dict:
        key = self._key(player)
        item = self._items.setdefault(key, {
            "player": player.strip(),
            "total_seconds": 0,
            "active_since": None,
            "last_joined_at": None,
            "last_left_at": None,
        })
        item["player"] = player.strip()
        return item

    def mark_online(self, player: str, now: datetime | None = None) -> None:
        item = self._ensure(player)
        if item.get("active_since") is None:
            joined = now or self._now()
            item["active_since"] = joined.isoformat()
            item["last_joined_at"] = joined.isoformat()
            self._save()

    def mark_offline(self, player: str, now: datetime | None = None) -> None:
        item = self._items.get(self._key(player))
        if item is None or item.get("active_since") is None:
            return
        left = now or self._now()
        try:
            started = datetime.fromisoformat(item["active_since"])
            elapsed = max(0, int((left - started).total_seconds()))
        except (TypeError, ValueError):
            elapsed = 0
        item["total_seconds"] = int(item.get("total_seconds", 0)) + elapsed
        item["active_since"] = None
        item["last_left_at"] = left.isoformat()
        self._save()

    def sync_online(self, players: list[str], now: datetime | None = None) -> None:
        current = {self._key(player) for player in players}
        timestamp = now or self._now()
        changed = False
        for player in players:
            item = self._ensure(player)
            if item.get("active_since") is None:
                item["active_since"] = timestamp.isoformat()
                item["last_joined_at"] = timestamp.isoformat()
                changed = True
        for key, item in self._items.items():
            if key in current or item.get("active_since") is None:
                continue
            try:
                started = datetime.fromisoformat(item["active_since"])
                elapsed = max(0, int((timestamp - started).total_seconds()))
            except (TypeError, ValueError):
                elapsed = 0
            item["total_seconds"] = int(item.get("total_seconds", 0)) + elapsed
            item["active_since"] = None
            item["last_left_at"] = timestamp.isoformat()
            changed = True
        if changed or not self.path.exists():
            self._save()

    def total_seconds(self, player: str) -> int:
        item = self._items.get(self._key(player))
        return self._total(item) if item else 0

    def ranking(self, now: datetime | None = None) -> list[tuple[str, int]]:
        timestamp = now or self._now()
        result = [(str(item.get("player", key)), self._total(item, timestamp)) for key, item in self._items.items()]
        return sorted(result, key=lambda value: (-value[1], value[0].casefold()))

    def reset(self) -> None:
        self._items.clear()
        self._save()

    @staticmethod
    def _total(item: dict, now: datetime | None = None) -> int:
        total = int(item.get("total_seconds", 0))
        if item.get("active_since"):
            try:
                total += max(0, int(((now or datetime.now(timezone.utc)) - datetime.fromisoformat(item["active_since"])).total_seconds()))
            except (TypeError, ValueError):
                pass
        return total


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    if days:
        return f"{days}日{hours}時間{minutes}分"
    if hours:
        return f"{hours}時間{minutes}分"
    return f"{minutes}分"
