from __future__ import annotations

import os
from dataclasses import dataclass
from typing import FrozenSet

from dotenv import load_dotenv


def required(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise ValueError(f'Missing required environment variable: {name}')
    return value


def integer(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if not raw else int(raw)


def boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def role_ids() -> FrozenSet[int]:
    raw = os.getenv('CONTROL_ROLE_IDS', '')
    return frozenset(int(x.strip()) for x in raw.split(',') if x.strip())


@dataclass(frozen=True)
class Settings:
    discord_token: str
    discord_guild_id: int
    discord_channel_id: int
    discord_message_id: int | None
    pelican_base_url: str
    pelican_server_id: str
    pelican_client_api_token: str
    bedrock_host: str
    bedrock_port: int
    update_interval_seconds: int
    server_display_name: str
    public_address: str
    console_enabled: bool
    console_log_lines: int
    player_list_enabled: bool
    player_list_command_interval_seconds: int
    max_players_displayed: int
    ko_fi_url: str
    donations_file: str
    enable_control_buttons: bool
    control_role_ids: FrozenSet[int]
    log_level: str

    @classmethod
    def from_env(cls) -> 'Settings':
        load_dotenv()
        message = os.getenv('DISCORD_MESSAGE_ID', '').strip()
        return cls(
            discord_token=required('DISCORD_TOKEN'),
            discord_guild_id=int(required('DISCORD_GUILD_ID')),
            discord_channel_id=int(required('DISCORD_CHANNEL_ID')),
            discord_message_id=int(message) if message else None,
            pelican_base_url=required('PELICAN_BASE_URL').rstrip('/'),
            pelican_server_id=required('PELICAN_SERVER_ID'),
            pelican_client_api_token=required('PELICAN_CLIENT_API_TOKEN'),
            bedrock_host=os.getenv('BEDROCK_HOST', '127.0.0.1'),
            bedrock_port=integer('BEDROCK_PORT', 19132),
            update_interval_seconds=max(5, integer('UPDATE_INTERVAL_SECONDS', 15)),
            server_display_name=os.getenv('SERVER_DISPLAY_NAME', 'Vanilla Bedrock'),
            public_address=os.getenv('PUBLIC_ADDRESS', '').strip(),
            console_enabled=boolean('CONSOLE_ENABLED', True),
            console_log_lines=min(5, max(1, integer('CONSOLE_LOG_LINES', 5))),
            player_list_enabled=boolean('PLAYER_LIST_ENABLED', True),
            player_list_command_interval_seconds=max(10, integer('PLAYER_LIST_COMMAND_INTERVAL_SECONDS', 30)),
            max_players_displayed=max(1, integer('MAX_PLAYERS_DISPLAYED', 20)),
            ko_fi_url=os.getenv('KO_FI_URL', '').strip(),
            donations_file=os.getenv('DONATIONS_FILE', 'data/donations.json').strip(),
            enable_control_buttons=boolean('ENABLE_CONTROL_BUTTONS', False),
            control_role_ids=role_ids(),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
        )
