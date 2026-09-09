from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import Announcement


class AnnouncementStore:
    def __init__(self, filename: str) -> None:
        self.path = Path(filename)
        self._items: list[Announcement] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            raw = []
        if not isinstance(raw, list):
            raw = []
        self._items = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            try:
                self._items.append(Announcement(
                    id=int(row['id']),
                    title=str(row['title']),
                    message=str(row['message']),
                    created_at=str(row['created_at']),
                    expires_at=(str(row['expires_at']) if row.get('expires_at') else None),
                ))
            except (KeyError, TypeError, ValueError):
                continue

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix='announcements-', suffix='.tmp', dir=self.path.parent
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                json.dump(
                    [asdict(item) for item in self._items], file,
                    ensure_ascii=False, indent=2,
                )
                file.write('\n')
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def add(self, title: str, message: str, expires_at: datetime | None) -> Announcement:
        item = Announcement(
            id=max((item.id for item in self._items), default=0) + 1,
            title=title,
            message=message,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at.astimezone(timezone.utc).isoformat() if expires_at else None,
        )
        self._items.append(item)
        self._save()
        return item

    def active(self, now: datetime | None = None) -> list[Announcement]:
        timestamp = now or datetime.now(timezone.utc)
        result: list[Announcement] = []
        for item in self._items:
            if item.expires_at:
                try:
                    if datetime.fromisoformat(item.expires_at) <= timestamp:
                        continue
                except ValueError:
                    continue
            result.append(item)
        return result

    def all(self) -> list[Announcement]:
        return list(self._items)

    def remove(self, item_id: int) -> bool:
        previous = len(self._items)
        self._items = [item for item in self._items if item.id != item_id]
        if len(self._items) == previous:
            return False
        self._save()
        return True

    def clear(self) -> int:
        count = len(self._items)
        self._items.clear()
        self._save()
        return count
