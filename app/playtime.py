from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


class PlaytimeStore:
    """JSON-backed cumulative online-time store."""

    def __init__(self, filename: str) -> None:
        self.path = Path(filename)
        self._items: dict[str, dict] = {}
        self.period_started_at: datetime = self._now()
        self._last_reset_check: str | None = None
        self._load()

    @staticmethod
    def _key(player: str) -> str:
        return player.strip().rstrip(",").strip().casefold()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        if isinstance(raw, dict) and isinstance(raw.get("players"), dict):
            self._items = raw["players"]
            meta = raw.get("_meta", {})
            started = meta.get("period_started_at") if isinstance(meta, dict) else None
        else:
            # Migrate the original flat player dictionary format.
            self._items = raw if isinstance(raw, dict) else {}
            started = None
        normalised_changed = self._normalise_items()
        if started:
            try:
                self.period_started_at = datetime.fromisoformat(started)
            except ValueError:
                pass
        if normalised_changed:
            self._save()

    def _normalise_items(self) -> bool:
        """Remove punctuation artifacts and merge duplicate player records."""
        normalised: dict[str, dict] = {}
        changed = False
        for key, raw_item in self._items.items():
            if not isinstance(raw_item, dict):
                changed = True
                continue
            player = str(raw_item.get("player", key)).strip().rstrip(",").strip()
            normalised_key = self._key(player)
            item = dict(raw_item)
            item["player"] = player
            if normalised_key != key or item["player"] != raw_item.get("player"):
                changed = True
            if normalised_key not in normalised:
                normalised[normalised_key] = item
                continue

            changed = True
            existing = normalised[normalised_key]
            existing["total_seconds"] = int(existing.get("total_seconds", 0)) + int(
                item.get("total_seconds", 0)
            )
            if existing.get("active_since") is None:
                existing["active_since"] = item.get("active_since")
            if item.get("last_joined_at") and (
                not existing.get("last_joined_at")
                or item["last_joined_at"] > existing["last_joined_at"]
            ):
                existing["last_joined_at"] = item["last_joined_at"]
            if item.get("last_left_at") and (
                not existing.get("last_left_at")
                or item["last_left_at"] > existing["last_left_at"]
            ):
                existing["last_left_at"] = item["last_left_at"]
        self._items = normalised
        return changed

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="playtime-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump({
                    "_meta": {"period_started_at": self.period_started_at.isoformat()},
                    "players": self._items,
                }, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _ensure(self, player: str) -> dict:
        key = self._key(player)
        player = player.strip().rstrip(",").strip()
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

    def reset(self, now: datetime | None = None) -> None:
        timestamp = now or self._now()
        for item in self._items.values():
            item["total_seconds"] = 0
            item["active_since"] = timestamp.isoformat() if item.get("active_since") else None
        self.period_started_at = timestamp
        self._save()

    def maybe_reset(self, cron_expression: str) -> bool:
        """Reset after the latest missed or current cron occurrence."""
        expression = cron_expression.strip()
        if not expression:
            return False
        now = datetime.now().astimezone().replace(second=0, microsecond=0)
        check_key = now.strftime("%Y-%m-%d-%H-%M")
        if self._last_reset_check == check_key:
            return False
        self._last_reset_check = check_key
        scheduled = _previous_cron_minute(expression, now)
        if scheduled is None:
            return False
        started_local = self.period_started_at.astimezone()
        if started_local >= scheduled:
            return False
        self.reset(now.astimezone(timezone.utc))
        return True

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


def _cron_field_matches(value: int, field: str, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        part = part.strip()
        if not part:
            return False
        base, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if step <= 0:
            return False
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", 1)
            start, end = int(start_text), int(end_text)
        else:
            start = end = int(base)
        if minimum <= start <= end <= maximum and (value - start) % step == 0:
            return True
    return False


def _cron_matches(expression: str, value: datetime) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        return False
    minute, hour, day, month, weekday = fields
    if not _cron_field_matches(value.minute, minute, 0, 59):
        return False
    if not _cron_field_matches(value.hour, hour, 0, 23):
        return False
    if not _cron_field_matches(value.month, month, 1, 12):
        return False
    day_match = _cron_field_matches(value.day, day, 1, 31)
    weekday_match = _cron_field_matches((value.weekday() + 1) % 7, weekday, 0, 6)
    day_restricted = day != "*"
    weekday_restricted = weekday != "*"
    if day_restricted and weekday_restricted:
        return day_match or weekday_match
    return day_match and weekday_match


def _previous_cron_minute(expression: str, now: datetime) -> datetime | None:
    if len(expression.split()) != 5:
        return None
    cursor = now
    for _ in range(366 * 24 * 60):
        try:
            if _cron_matches(expression, cursor):
                return cursor
        except (TypeError, ValueError):
            return None
        cursor -= timedelta(minutes=1)
    return None
