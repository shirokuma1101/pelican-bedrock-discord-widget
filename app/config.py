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


def number(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if not raw else float(raw)


def boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_with_legacy(name: str, legacy_name: str, default: str = '') -> str:
    value = os.getenv(name)
    if value is None:
        value = os.getenv(legacy_name, default)
    return value.strip()


def integer_with_legacy(name: str, legacy_name: str, default: int) -> int:
    raw = env_with_legacy(name, legacy_name)
    return default if not raw else int(raw)


def boolean_with_legacy(name: str, legacy_name: str, default: bool) -> bool:
    raw = env_with_legacy(name, legacy_name)
    return default if not raw else raw.lower() in {'1', 'true', 'yes', 'on'}


def role_ids() -> FrozenSet[int]:
    raw = os.getenv('CONTROL_ROLE_IDS', '')
    return frozenset(int(x.strip()) for x in raw.split(',') if x.strip())


@dataclass(frozen=True)
class Settings:
    discord_token: str
    discord_guild_id: int
    discord_channel_id: int
    discord_to_minecraft_channel_id: int
    discord_message_id: int | None
    pelican_base_url: str
    pelican_server_id: str
    pelican_client_api_token: str
    bedrock_host: str
    bedrock_port: int
    update_interval_seconds: int
    presence_enabled: bool
    website_url: str
    victoria_metrics_url: str
    victoria_metrics_query: str
    power_average_window: str
    electricity_yen_per_kwh: float
    domain_annual_cost_yen: float
    hdd_count: int
    hdd_watts_each: float
    ssd_count: int
    ssd_watts_each: float
    other_hardware_watts: float
    llm_enabled: bool
    llm_base_url: str
    deepseek_api_key: str
    llm_model: str
    llm_allowed_channel_id: int | None
    llm_system_prompt: str
    llm_timeout_seconds: int
    llm_max_history_messages: int
    llm_max_concurrent_requests: int
    llm_max_tokens: int
    llm_database_file: str
    llm_terms_text: str
    llm_history_learn_messages: int
    llm_history_scan_limit: int
    public_address: str
    console_enabled: bool
    console_log_lines: int
    player_list_enabled: bool
    player_list_command_interval_seconds: int
    max_players_displayed: int
    player_emoji_file: str
    ko_fi_url: str
    ko_fi_goal_title: str
    ko_fi_goal_percentage: str
    ko_fi_goal_current: str
    ko_fi_goal_target: str
    donations_file: str
    playtime_file: str
    playtime_reset_cron: str
    enable_control_buttons: bool
    control_role_ids: FrozenSet[int]
    dynamic_voice_category_id: int | None
    dynamic_voice_empty_minutes: int
    dynamic_voice_default_limit: int
    dynamic_voice_file: str
    dynamic_voice_reactions_file: str
    log_level: str
    minecraft_voice_channel_id: int | None = None

    @classmethod
    def from_env(cls) -> 'Settings':
        load_dotenv()
        message = os.getenv('DISCORD_MESSAGE_ID', '').strip()
        voice_category = os.getenv('DYNAMIC_VOICE_CATEGORY_ID', '').strip()
        minecraft_voice_channel = os.getenv(
            'MINECRAFT_NOTIFY_VOICE_CHANNEL_ID', ''
        ).strip()
        llm_channel = env_with_legacy('LLM_ALLOWED_CHANNEL_ID', 'LLAMA_ALLOWED_CHANNEL_ID')
        return cls(
            discord_token=required('DISCORD_TOKEN'),
            discord_guild_id=int(required('DISCORD_GUILD_ID')),
            discord_channel_id=int(required('DISCORD_CHANNEL_ID')),
            discord_to_minecraft_channel_id=int(
                os.getenv('DISCORD_TO_MINECRAFT_CHANNEL_ID', '').strip()
                or os.getenv('DISCORD_CHANNEL_ID', '')
            ),
            discord_message_id=int(message) if message else None,
            pelican_base_url=required('PELICAN_BASE_URL').rstrip('/'),
            pelican_server_id=required('PELICAN_SERVER_ID'),
            pelican_client_api_token=required('PELICAN_CLIENT_API_TOKEN'),
            bedrock_host=os.getenv('BEDROCK_HOST', '127.0.0.1'),
            bedrock_port=integer('BEDROCK_PORT', 19132),
            update_interval_seconds=max(5, integer('UPDATE_INTERVAL_SECONDS', 15)),
            presence_enabled=boolean('PRESENCE_ENABLED', True),
            website_url=os.getenv('WEBSITE_URL', '').strip(),
            victoria_metrics_url=os.getenv('VICTORIA_METRICS_URL', '').strip(),
            victoria_metrics_query=os.getenv(
                'VICTORIA_METRICS_QUERY',
                'ohm_cpu_watts{instance="shirokuma1103",sensor="CPU Package"}',
            ).strip(),
            power_average_window=(
                os.getenv('POWER_AVERAGE_WINDOW', '7d').strip() or '7d'
            ),
            electricity_yen_per_kwh=max(
                0.0, number('ELECTRICITY_YEN_PER_KWH', 32.6)
            ),
            domain_annual_cost_yen=max(
                0.0, number('DOMAIN_ANNUAL_COST_YEN', 0.0)
            ),
            hdd_count=max(0, integer('HDD_COUNT', 1)),
            hdd_watts_each=max(0.0, number('HDD_WATTS_EACH', 8.0)),
            ssd_count=max(0, integer('SSD_COUNT', 2)),
            ssd_watts_each=max(0.0, number('SSD_WATTS_EACH', 3.0)),
            other_hardware_watts=max(
                0.0, number('OTHER_HARDWARE_WATTS', 30.0)
            ),
            llm_enabled=boolean_with_legacy('LLM_ENABLED', 'LLAMA_ENABLED', False),
            llm_base_url=(
                env_with_legacy(
                    'LLM_BASE_URL', 'LLAMA_BASE_URL', 'https://api.deepseek.com'
                ).rstrip('/')
            ),
            deepseek_api_key=os.getenv('DEEPSEEK_API_KEY', '').strip(),
            llm_model=env_with_legacy(
                'LLM_MODEL', 'LLAMA_MODEL', 'deepseek-v4-flash'
            ),
            llm_allowed_channel_id=int(llm_channel) if llm_channel else None,
            llm_system_prompt=env_with_legacy(
                'LLM_SYSTEM_PROMPT', 'LLAMA_SYSTEM_PROMPT',
                'あなたはMinecraftサーバーの親しみやすい雑談Botです。簡潔に日本語で返答してください。',
            ),
            llm_timeout_seconds=max(10, integer_with_legacy('LLM_TIMEOUT_SECONDS', 'LLAMA_TIMEOUT_SECONDS', 120)),
            llm_max_history_messages=max(2, integer_with_legacy('LLM_MAX_HISTORY_MESSAGES', 'LLAMA_MAX_HISTORY_MESSAGES', 20)),
            llm_max_concurrent_requests=max(1, integer_with_legacy('LLM_MAX_CONCURRENT_REQUESTS', 'LLAMA_MAX_CONCURRENT_REQUESTS', 1)),
            llm_max_tokens=max(32, integer_with_legacy('LLM_MAX_TOKENS', 'LLAMA_MAX_TOKENS', 512)),
            llm_database_file=(
                os.getenv('LLM_DATABASE_FILE', '').strip() or 'data/llm_chat.sqlite3'
            ),
            llm_terms_text=(
                os.getenv('LLM_TERMS_TEXT', '').strip()
                or 'AIの回答には誤りが含まれる場合があります。個人情報・機密情報を送信しないでください。入力内容と、許可した場合は過去の発言がDeepSeek APIへ送信され、会話履歴・長期記憶・同意設定がBotのデータベースに保存されます。AIの回答は重要な判断の根拠にしないでください。'
            ),
            llm_history_learn_messages=min(
                100, max(1, integer('LLM_HISTORY_LEARN_MESSAGES', 30))
            ),
            llm_history_scan_limit=min(
                5000, max(1, integer('LLM_HISTORY_SCAN_LIMIT', 500))
            ),
            public_address=os.getenv('PUBLIC_ADDRESS', '').strip(),
            console_enabled=boolean('CONSOLE_ENABLED', True),
            console_log_lines=min(5, max(0, integer('CONSOLE_LOG_LINES', 5))),
            player_list_enabled=boolean('PLAYER_LIST_ENABLED', True),
            player_list_command_interval_seconds=max(10, integer('PLAYER_LIST_COMMAND_INTERVAL_SECONDS', 30)),
            max_players_displayed=max(1, integer('MAX_PLAYERS_DISPLAYED', 20)),
            player_emoji_file=os.getenv(
                'PLAYER_EMOJI_FILE', 'data/player_emojis.json'
            ).strip() or 'data/player_emojis.json',
            ko_fi_url=os.getenv('KO_FI_URL', '').strip(),
            ko_fi_goal_title=os.getenv('KO_FI_GOAL_TITLE', '').strip(),
            ko_fi_goal_percentage=os.getenv('KO_FI_GOAL_PERCENTAGE', '').strip(),
            ko_fi_goal_current=os.getenv('KO_FI_GOAL_CURRENT', '').strip(),
            ko_fi_goal_target=os.getenv('KO_FI_GOAL_TARGET', '').strip(),
            donations_file=os.getenv('DONATIONS_FILE', 'data/donations.json').strip(),
            playtime_file=os.getenv('PLAYTIME_FILE', 'data/playtime.json').strip(),
            playtime_reset_cron=os.getenv('PLAYTIME_RESET_CRON', '').strip(),
            enable_control_buttons=boolean('ENABLE_CONTROL_BUTTONS', False),
            control_role_ids=role_ids(),
            dynamic_voice_category_id=int(voice_category) if voice_category else None,
            dynamic_voice_empty_minutes=max(1, integer('DYNAMIC_VOICE_EMPTY_MINUTES', 10)),
            dynamic_voice_default_limit=min(99, max(0, integer('DYNAMIC_VOICE_DEFAULT_LIMIT', 0))),
            dynamic_voice_file=os.getenv('DYNAMIC_VOICE_FILE', 'data/dynamic_voice.json').strip(),
            dynamic_voice_reactions_file=os.getenv(
                'DYNAMIC_VOICE_REACTIONS_FILE', 'data/dynamic_voice_reactions.json'
            ).strip(),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            minecraft_voice_channel_id=(
                int(minecraft_voice_channel) if minecraft_voice_channel else None
            ),
        )
