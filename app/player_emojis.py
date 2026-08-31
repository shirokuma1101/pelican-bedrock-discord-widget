from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlayerEmoji:
    player: str
    emoji: str


class PlayerEmojiStore:
    def __init__(self, filename: str) -> None:
        self.path = Path(filename)
        self._items: dict[str, PlayerEmoji] = {}
        self._load()

    @staticmethod
    def player_key(player: str) -> str:
        return player.strip().casefold()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            raw = []
        if not isinstance(raw, list):
            raw = []
        self._items = {}
        for row in raw:
            if not isinstance(row, dict) or not {'player', 'emoji'} <= row.keys():
                continue
            item = PlayerEmoji(player=str(row['player']), emoji=str(row['emoji']))
            key = self.player_key(item.player)
            if key:
                self._items[key] = item

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(
                [asdict(item) for item in self.all()],
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        temporary.replace(self.path)

    def all(self) -> list[PlayerEmoji]:
        return sorted(self._items.values(), key=lambda item: item.player.casefold())

    def get(self, player: str) -> str | None:
        item = self._items.get(self.player_key(player))
        return item.emoji if item else None

    def set(self, player: str, emoji: str) -> PlayerEmoji:
        item = PlayerEmoji(player=player.strip(), emoji=emoji.strip())
        self._items[self.player_key(item.player)] = item
        self._save()
        return item

    def remove(self, player: str) -> PlayerEmoji | None:
        removed = self._items.pop(self.player_key(player), None)
        if removed is not None:
            self._save()
        return removed
