from __future__ import annotations

import logging

import discord

from .config import Settings
from .pelican import PelicanClient

log = logging.getLogger(__name__)


class ControlView(discord.ui.View):
    def __init__(self, client: PelicanClient, settings: Settings) -> None:
        super().__init__(timeout=None)
        self.client = client
        self.settings = settings

    def allowed(self, interaction: discord.Interaction) -> bool:
        if not self.settings.enable_control_buttons:
            return False
        if not self.settings.control_role_ids:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        return any(
            role.id in self.settings.control_role_ids
            for role in interaction.user.roles
        )

    async def power(
        self,
        interaction: discord.Interaction,
        signal: str,
    ) -> None:
        if not self.allowed(interaction):
            await interaction.response.send_message(
                "この操作を実行する権限がありません。",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await self.client.power(signal)
            await interaction.followup.send(
                f"`{signal}` をPelicanへ送信しました。",
                ephemeral=True,
            )
        except Exception as exc:
            log.exception("Power command failed")
            await interaction.followup.send(
                f"操作に失敗しました: `{exc}`",
                ephemeral=True,
            )

    @discord.ui.button(
        label="起動",
        emoji="▶️",
        style=discord.ButtonStyle.success,
        custom_id="pelican_widget:start",
    )
    async def start_button(self, interaction, button):
        await self.power(interaction, "start")

    @discord.ui.button(
        label="再起動",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="pelican_widget:restart",
    )
    async def restart_button(self, interaction, button):
        await self.power(interaction, "restart")

    @discord.ui.button(
        label="停止",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="pelican_widget:stop",
    )
    async def stop_button(self, interaction, button):
        await self.power(interaction, "stop")
