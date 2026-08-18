from __future__ import annotations

import asyncio
import logging

import aiohttp
import discord
from discord import app_commands

from .bedrock import BedrockClient
from .config import Settings
from .donations import DonationStore
from .pelican import PelicanClient
from .playtime import PlaytimeStore, format_duration
from .widget import WidgetManager
from .wings_ws import WingsConsole

log = logging.getLogger(__name__)


class WidgetBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True
        super().__init__(intents=intents)
        self.settings = settings
        self.session: aiohttp.ClientSession | None = None
        self.pelican: PelicanClient | None = None
        self.console: WingsConsole | None = None
        self.widget: WidgetManager | None = None
        self.donations: DonationStore | None = None
        self.playtime: PlaytimeStore | None = None
        self.tree = app_commands.CommandTree(self)
        self.loop_task: asyncio.Task | None = None

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.pelican = PelicanClient(self.settings.pelican_base_url,
                                     self.settings.pelican_server_id,
                                     self.settings.pelican_client_api_token,
                                     self.session)
        self.playtime = PlaytimeStore(self.settings.playtime_file)
        bedrock = BedrockClient(self.settings.bedrock_host, self.settings.bedrock_port)
        if self.settings.console_enabled:
            self.console = WingsConsole(
                self.settings.pelican_base_url,
                self.settings.pelican_server_id,
                self.settings.pelican_client_api_token,
                self.session,
                log_lines=self.settings.console_log_lines,
                player_command_interval=self.settings.player_list_command_interval_seconds,
                player_list_enabled=self.settings.player_list_enabled,
                playtime=self.playtime,
            )
            await self.console.start()
        guild = self.get_guild(self.settings.discord_guild_id)
        if guild is None:
            guild = await self.fetch_guild(self.settings.discord_guild_id)
        channel = guild.get_channel(self.settings.discord_channel_id)
        if channel is None:
            channel = await self.fetch_channel(self.settings.discord_channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise RuntimeError('DISCORD_CHANNEL_ID is not a text channel')
        self.donations = DonationStore(self.settings.donations_file)
        self.widget = WidgetManager(
            self.settings, channel, self.pelican, bedrock, self.console,
            self.donations, self.playtime,
        )

        guild_obj = discord.Object(id=self.settings.discord_guild_id)
        commands = (
            app_commands.Command(
                name="donation_add", description="寄付者からのひとことを掲示板に追加します",
                callback=self._donation_add_command,
            ),
            app_commands.Command(
                name="donation_remove", description="寄付者からのひとことを削除します",
                callback=self._donation_remove_command,
            ),
            app_commands.Command(
                name="donation_list", description="寄付者からのひとことを確認します",
                callback=self._donation_list_command,
            ),
            app_commands.Command(
                name="donation_clear", description="寄付者からのひとことを全削除します",
                callback=self._donation_clear_command,
            ),
        )
        for command in commands:
            # Register commands only in the configured guild. Registering the
            # same command globally as well makes Discord show two entries.
            self.tree.add_command(command, guild=guild_obj, override=True)

        playtime_commands = (
            app_commands.Command(
                name="playtime", description="プレイヤーの累計プレイ時間を表示します",
                callback=self._playtime_command,
            ),
            app_commands.Command(
                name="playtime_ranking", description="プレイ時間ランキングを表示します",
                callback=self._playtime_ranking_command,
            ),
            app_commands.Command(
                name="playtime_reset", description="プレイ時間ランキングをリセットします",
                callback=self._playtime_reset_command,
            ),
        )
        for command in playtime_commands:
            self.tree.add_command(command, guild=guild_obj, override=True)

        guild_commands = await self.tree.sync(guild=guild_obj)
        # Remove global commands left behind by older versions that synced
        # this bot's commands in both scopes.
        global_commands = await self.tree.sync()
        log.info(
            "Synced commands: guild=%s global=%s",
            [command.name for command in guild_commands],
            [command.name for command in global_commands],
        )

    def _can_manage_donations(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member):
            return False
        return (
            interaction.user.guild_permissions.administrator
            or any(role.id in self.settings.control_role_ids for role in interaction.user.roles)
        )

    async def _deny_donation_command(self, interaction: discord.Interaction) -> bool:
        if self._can_manage_donations(interaction):
            return False
        await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)
        return True

    async def _donation_add_command(self, interaction: discord.Interaction, donor: str, message: str) -> None:
        if await self._deny_donation_command(interaction):
            return
        assert self.donations is not None
        donor, message = donor.strip(), message.strip()
        if not donor or not message or len(donor) > 32 or len(message) > 500:
            await interaction.response.send_message("寄付者名は32文字以内、メッセージは500文字以内で入力してください。", ephemeral=True)
            return
        item = self.donations.add(donor, message)
        await interaction.response.send_message(f"寄付者からのひとこと #{item.id} を追加しました。", ephemeral=True)

    async def _playtime_command(self, interaction: discord.Interaction, player: str) -> None:
        assert self.playtime is not None
        player = player.strip()
        if not player or len(player) > 32:
            await interaction.response.send_message("プレイヤー名を32文字以内で入力してください。", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**{player}** の累計プレイ時間: `{format_duration(self.playtime.total_seconds(player))}`",
            ephemeral=True,
        )

    async def _playtime_ranking_command(self, interaction: discord.Interaction) -> None:
        assert self.playtime is not None
        rows = self.playtime.ranking()[:10]
        if rows:
            text = "\n".join(
                f"**{index}位** {name} — `{format_duration(seconds)}`"
                for index, (name, seconds) in enumerate(rows, 1)
            )
        else:
            text = "まだプレイ時間の記録がありません。"
        await interaction.response.send_message(
            f"🏆 プレイ時間ランキング\n{text}"
        )

    async def _playtime_reset_command(self, interaction: discord.Interaction) -> None:
        if await self._deny_donation_command(interaction):
            return
        assert self.playtime is not None
        self.playtime.reset()
        await interaction.response.send_message("プレイ時間ランキングをリセットしました。", ephemeral=True)

    async def _donation_remove_command(self, interaction: discord.Interaction, item_id: int) -> None:
        if await self._deny_donation_command(interaction):
            return
        assert self.donations is not None
        result = self.donations.remove(item_id)
        await interaction.response.send_message("削除しました。" if result else "そのIDは見つかりません。", ephemeral=True)

    async def _donation_list_command(self, interaction: discord.Interaction) -> None:
        if await self._deny_donation_command(interaction):
            return
        assert self.donations is not None
        items = self.donations.all()
        text = "\n".join(f"#{item.id} {item.donor}: {item.message}" for item in items) or "登録なし"
        await interaction.response.send_message(text[:1900], ephemeral=True)

    async def _donation_clear_command(self, interaction: discord.Interaction) -> None:
        if await self._deny_donation_command(interaction):
            return
        assert self.donations is not None
        count = self.donations.clear()
        await interaction.response.send_message(f"{count}件のメッセージを削除しました。", ephemeral=True)

    async def on_ready(self) -> None:
        log.info('Discord login: %s', self.user)
        if self.loop_task is None:
            self.loop_task = asyncio.create_task(self.update_loop())

    async def update_loop(self) -> None:
        assert self.widget is not None
        await self.widget.initialize()
        while not self.is_closed():
            try:
                await self.widget.update()
            except Exception:
                log.exception('Widget update failed')
            await asyncio.sleep(self.settings.update_interval_seconds)

    async def close(self) -> None:
        if self.loop_task:
            self.loop_task.cancel()
        if self.console:
            await self.console.stop()
        if self.session:
            await self.session.close()
        await super().close()

    async def start_bot(self) -> None:
        await self.start(self.settings.discord_token)
