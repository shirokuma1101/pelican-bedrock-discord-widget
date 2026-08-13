"""指定したDiscordスラッシュコマンドを削除する一時ツール。"""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.http import Route
from dotenv import load_dotenv


COMMANDS_TO_DELETE = {
    "topic",
    "translate",
    "askai",
    "help_",
    "map",
    "news",
    "ping",
    "search",
}


class CommandCleanupClient(discord.Client):
    def __init__(self, guild_id: int) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        self.cleaned = False

    async def delete_registered_command(
        self,
        command_id: int,
        guild_id: int | None = None,
    ) -> None:
        """Discord APIから登録済みコマンドを削除する。"""
        if guild_id is None:
            route = Route(
                "DELETE",
                "/applications/{application_id}/commands/{command_id}",
                application_id=self.application_id,
                command_id=command_id,
            )
        else:
            route = Route(
                "DELETE",
                "/applications/{application_id}/guilds/{guild_id}/commands/{command_id}",
                application_id=self.application_id,
                guild_id=guild_id,
                command_id=command_id,
            )
        await self.http.request(route)

    async def on_ready(self) -> None:
        if self.cleaned:
            return
        self.cleaned = True

        guild = discord.Object(id=self.guild_id)
        deleted: list[str] = []

        # グローバルコマンドを削除
        global_commands = await self.tree.fetch_commands()
        for command in global_commands:
            if command.name in COMMANDS_TO_DELETE:
                await self.delete_registered_command(command.id)
                deleted.append(f"global /{command.name}")

        # 指定ギルドに登録されたコマンドを削除
        guild_commands = await self.tree.fetch_commands(guild=guild)
        for command in guild_commands:
            if command.name in COMMANDS_TO_DELETE:
                await self.delete_registered_command(command.id, guild_id=self.guild_id)
                deleted.append(f"guild /{command.name}")

        if deleted:
            for name in deleted:
                logging.info("削除しました: %s", name)
        else:
            logging.info("削除対象のコマンドは見つかりませんでした。")

        await self.close()


async def main() -> None:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN", "").strip()
    guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    if not token:
        raise ValueError(".env に DISCORD_TOKEN が必要です")
    if not guild_id:
        raise ValueError(".env に DISCORD_GUILD_ID が必要です")

    client = CommandCleanupClient(int(guild_id))
    await client.start(token)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(main())
