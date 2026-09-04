from __future__ import annotations

from datetime import datetime
import logging
import asyncio
import socket

import discord

from .bedrock import BedrockClient
from .config import Settings
from .donations import DonationStore
from .playtime import PlaytimeStore
from .player_emojis import PlayerEmojiStore
from .embed import make_embed
from .models import BedrockStatus, ConsoleSnapshot, KoFiGoal, PelicanServer, Resources, WidgetData
from .pelican import PelicanClient
from .timezones import JST
from .views import ControlView
from .victoria_metrics import VictoriaMetricsClient
from .wings_ws import WingsConsole

log = logging.getLogger(__name__)


def _resolve_a_records(address: str) -> list[str]:
    host = address.rsplit(':', 1)[0] if address.count(':') == 1 else address
    try:
        results = socket.getaddrinfo(host, None, socket.AF_INET)
    except OSError:
        return []
    return sorted({item[4][0] for item in results})


class WidgetManager:
    def __init__(self, settings: Settings, channel: discord.TextChannel,
                 pelican: PelicanClient, bedrock: BedrockClient,
                 console: WingsConsole | None,
                 donations: DonationStore,
                 playtime: PlaytimeStore,
                 player_emojis: PlayerEmojiStore,
                 victoria_metrics: VictoriaMetricsClient | None = None) -> None:
        self.settings = settings
        self.channel = channel
        self.pelican = pelican
        self.bedrock = bedrock
        self.console = console
        self.donations = donations
        self.playtime = playtime
        self.player_emojis = player_emojis
        self.victoria_metrics = victoria_metrics
        self.message: discord.Message | None = None

    async def initialize(self) -> None:
        if self.settings.discord_message_id:
            try:
                self.message = await self.channel.fetch_message(self.settings.discord_message_id)
                return
            except discord.NotFound:
                log.warning('Configured widget message was not found.')
        self.message = await self.channel.send('Initializing server widget...')
        log.info('Created widget message ID: %s', self.message.id)

    async def update(self) -> WidgetData:
        if self.message is None:
            await self.initialize()
        self.playtime.maybe_reset(self.settings.playtime_reset_cron)
        errors: list[str] = []
        try:
            server = await self.pelican.get_server()
        except Exception as exc:
            server = PelicanServer(identifier=self.settings.pelican_server_id,
                                   name=self.settings.pelican_server_id)
            errors.append(f'Pelican server: {exc}')
        try:
            resources = await self.pelican.get_resources()
        except Exception as exc:
            resources = Resources()
            errors.append(f'Pelican resources: {exc}')
        try:
            backups = await self.pelican.get_backups()
        except Exception as exc:
            backups = []
            errors.append(f'Pelican backups: {exc}')
        cpu_watts = None
        if self.victoria_metrics is not None:
            try:
                cpu_watts = await self.victoria_metrics.get_cpu_watts()
            except Exception as exc:
                errors.append(f'VictoriaMetrics: {exc}')
        try:
            bedrock = await self.bedrock.status()
        except Exception as exc:
            bedrock = BedrockStatus()
            errors.append(f'Bedrock: {exc}')
        console = await self.console.snapshot() if self.console else ConsoleSnapshot()
        address = self.settings.public_address or (
            f'{self.settings.bedrock_host}:{self.settings.bedrock_port}'
        )
        address_a_records = await asyncio.to_thread(_resolve_a_records, address)
        kofi_goal = None
        if (
            self.settings.ko_fi_goal_title
            and self.settings.ko_fi_goal_percentage
            and self.settings.ko_fi_goal_current
            and self.settings.ko_fi_goal_target
        ):
            kofi_goal = KoFiGoal(
                title=self.settings.ko_fi_goal_title,
                percentage=self.settings.ko_fi_goal_percentage,
                current_text=self.settings.ko_fi_goal_current,
                target_text=self.settings.ko_fi_goal_target,
            )
        if self.console and console.online_players is not None:
            # Do not treat the short-lived empty snapshot between the count
            # line and the player-name lines as a mass disconnect.
            snapshot_complete = (
                console.online_players == 0
                or len(console.players) >= console.online_players
            )
            if snapshot_complete:
                self.playtime.sync_online(console.players)
        if self.settings.console_enabled and not console.connected:
            errors.append(f'Wings console: {console.last_error}' if console.last_error else 'Wings console: connecting...')
        data = WidgetData(server=server, resources=resources, bedrock=bedrock,
                          console=console, last_updated=datetime.now(JST),
                          errors=errors,
                          donations=self.donations.all(),
                          kofi_goal=kofi_goal,
                          playtime_ranking=self.playtime.ranking(),
                          playtime_started_at=self.playtime.period_started_at,
                          playtime_next_reset_at=self.playtime.next_reset_at(
                              self.settings.playtime_reset_cron
                          ),
                          backups=backups,
                          cpu_watts=cpu_watts,
                          address_a_records=address_a_records,
                          player_emojis={
                              item.player.casefold(): item.emoji
                              for item in self.player_emojis.all()
                          })
        view = ControlView(self.pelican, self.settings) if self.settings.enable_control_buttons else None
        await self.message.edit(content=None, embed=make_embed(data, self.settings), view=view)
        return data
