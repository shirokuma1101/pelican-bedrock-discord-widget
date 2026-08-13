from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import DonationMessage


class DonationStore:
    """Small JSON-backed store for administrator-managed donation messages."""

    def __init__(self, filename: str) -> None:
        self.path = Path(filename)
        self._items: list[DonationMessage] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = []
        if not isinstance(raw, list):
            raw = []
        self._items = [
            DonationMessage(
                id=int(item["id"]),
                donor=str(item["donor"]),
                message=str(item["message"]),
                created_at=str(item.get("created_at", "")),
            )
            for item in raw
            if isinstance(item, dict) and {"id", "donor", "message"} <= item.keys()
        ]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([item.__dict__ for item in self._items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def all(self) -> list[DonationMessage]:
        return list(self._items)

    def add(self, donor: str, message: str) -> DonationMessage:
        next_id = max((item.id for item in self._items), default=0) + 1
        item = DonationMessage(
            id=next_id,
            donor=donor,
            message=message,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._items.append(item)
        self._save()
        return item

    def remove(self, item_id: int) -> bool:
        old_count = len(self._items)
        self._items = [item for item in self._items if item.id != item_id]
        if len(self._items) == old_count:
            return False
        self._save()
        return True

    def clear(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._save()
        return count
