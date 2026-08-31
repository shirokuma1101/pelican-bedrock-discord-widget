from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PelicanServer:
    identifier: str
    name: str
    state: str = "unknown"
    memory_limit_mb: int | None = None
    cpu_limit: float | None = None
    disk_limit_mb: int | None = None


@dataclass
class Resources:
    current_state: str = "unknown"
    cpu_absolute: float | None = None
    memory_bytes: int | None = None
    disk_bytes: int | None = None


@dataclass
class BedrockStatus:
    online: bool = False
    latency_ms: float | None = None
    version: str | None = None
    motd: str | None = None
    online_players: int | None = None
    max_players: int | None = None


@dataclass
class ConsoleSnapshot:
    connected: bool = False
    online_players: int | None = None
    max_players: int | None = None
    players: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    last_error: str | None = None


@dataclass
class DonationMessage:
    id: int
    donor: str
    message: str
    created_at: str


@dataclass
class KoFiGoal:
    title: str
    percentage: str
    current_text: str
    target_text: str


@dataclass
class Backup:
    name: str
    created_at: datetime | None = None
    completed_at: datetime | None = None
    successful: bool | None = None


@dataclass
class WidgetData:
    server: PelicanServer
    resources: Resources
    bedrock: BedrockStatus
    console: ConsoleSnapshot
    last_updated: datetime
    errors: list[str]
    donations: list[DonationMessage] = field(default_factory=list)
    kofi_goal: KoFiGoal | None = None
    playtime_ranking: list[tuple[str, int]] = field(default_factory=list)
    playtime_started_at: datetime | None = None
    player_emojis: dict[str, str] = field(default_factory=dict)
    backups: list[Backup] = field(default_factory=list)
    cpu_watts: float | None = None
