from __future__ import annotations

import asyncio
import logging
import re

import aiohttp
import discord
from discord import app_commands

from .ai_chat import LLMChatManager
from .bedrock import BedrockClient
from .config import Settings
from .donations import DonationStore
from .dynamic_voice import DynamicVoiceManager
from .models import WidgetData
from .pelican import PelicanClient
from .playtime import PlaytimeStore, format_duration
from .widget import WidgetManager
from .wings_ws import WingsConsole

log = logging.getLogger(__name__)

MINECRAFT_SELECTOR_RE = re.compile(
    r'(?<![A-Za-z0-9_])@([aeprs])(?![A-Za-z0-9_])',
    re.IGNORECASE,
)
DISCORD_MINECRAFT_EMOJI_RE = re.compile(
    r'<a?:mc_([A-Za-z0-9_]+):\d+>',
    re.IGNORECASE,
)


def replace_minecraft_emojis(content: str) -> str:
    return DISCORD_MINECRAFT_EMOJI_RE.sub(
        lambda match: f":{match.group(1).lower()}:",
        content,
    )


def presence_text(data: WidgetData) -> str:
    if data.resources.current_state.lower() in {'offline', 'stopping'}:
        return 'Minecraft｜サーバーOFFLINE'

    online = data.console.online_players
    maximum = data.console.max_players
    if online is None or maximum is None:
        online = data.bedrock.online_players
        maximum = data.bedrock.max_players

    if online is not None and maximum is not None:
        return f'Minecraft｜{online}/{maximum}人が参加中'
    return 'Minecraft｜人数を取得中'


class WidgetBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = True
        intents.guild_reactions = True
        intents.voice_states = True
        intents.message_content = True
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
        self.dynamic_voice: DynamicVoiceManager | None = None
        self.ai_chat: LLMChatManager | None = None
        self._presence_text: str | None = None

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        if self.settings.llm_enabled:
            self.ai_chat = LLMChatManager(self.settings, self.session)
            await self.ai_chat.initialize()
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
        await self.widget.initialize()
        if self.settings.dynamic_voice_category_id is not None:
            self.dynamic_voice = DynamicVoiceManager(
                guild,
                self.settings.dynamic_voice_category_id,
                self.settings.dynamic_voice_empty_minutes,
                self.settings.dynamic_voice_default_limit,
                self.settings.dynamic_voice_file,
                self.settings.dynamic_voice_reactions_file,
            )
            await self.dynamic_voice.start()
            assert self.widget.message is not None
            try:
                await self.widget.message.add_reaction('🔊')
                for reaction in self.dynamic_voice.reactions.values():
                    try:
                        await self.widget.message.add_reaction(reaction.display)
                    except discord.HTTPException:
                        log.warning('Could not restore dynamic voice reaction %s', reaction.display)
            except discord.HTTPException:
                log.exception('Failed to add the dynamic voice reaction')

        guild_obj = discord.Object(id=self.settings.discord_guild_id)
        commands = (
            app_commands.Command(
                name="help", description="このBotの機能とコマンド一覧を表示します",
                callback=self._help_command,
            ),
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

        if self.ai_chat is not None:
            ai_commands = (
                app_commands.Command(
                    name='ai_reset', description='現在のAIスレッドの会話履歴をリセットします',
                    callback=self._ai_reset_command,
                ),
                app_commands.Command(
                    name='ai_memory', description='AIの長期記憶を追加・確認・設定します',
                    callback=self._ai_memory_command,
                ),
                app_commands.Command(
                    name='ai_forget', description='AIが記憶している自分の情報を削除します',
                    callback=self._ai_forget_command,
                ),
            )
            for command in ai_commands:
                self.tree.add_command(command, guild=guild_obj, override=True)

        if self.dynamic_voice is not None:
            voice_commands = (
                app_commands.Command(
                    name='vc_create',
                    description='VCと聞き専テキストチャンネルのセットを作成します',
                    callback=self._voice_create_command,
                ),
                app_commands.Command(
                    name='vc_reaction_add',
                    description='絵文字と作成するVC名を固定Embedへ登録します',
                    callback=self._voice_reaction_add_command,
                ),
                app_commands.Command(
                    name='vc_reaction_remove',
                    description='固定EmbedからVC作成用リアクションを削除します',
                    callback=self._voice_reaction_remove_command,
                ),
                app_commands.Command(
                    name='vc_reaction_list',
                    description='登録済みのVC作成用リアクションを表示します',
                    callback=self._voice_reaction_list_command,
                ),
            )
            for command in voice_commands:
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

    async def _help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title='🖥️ Pelican Bedrock Widget Bot ヘルプ',
            description=(
                'Minecraft Bedrockサーバーの状態を固定Embedへ表示し、'
                'Discordとサーバーの連携を行うBotです。'
            ),
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name='📊 主な機能',
            value=(
                '• サーバー状態・接続人数・リソース使用量の表示\n'
                '• プレイ時間ランキングの記録\n'
                '• DiscordメッセージのMinecraftへの転送\n'
                '• 寄付者メッセージの掲示'
            ),
            inline=False,
        )
        embed.add_field(
            name='👤 一般コマンド',
            value=(
                '`/help` — このヘルプを表示\n'
                '`/playtime player:<名前>` — 累計プレイ時間を表示\n'
                '`/playtime_ranking` — プレイ時間ランキングを表示'
            ),
            inline=False,
        )
        if self.ai_chat is not None:
            embed.add_field(
                name='🤖 AI雑談',
                value=(
                    'BotへのメンションまたはReplyでAI雑談スレッドを開始\n'
                    '`/ai_reset` — 現在のスレッドの会話履歴をリセット\n'
                    '`/ai_memory` — 長期記憶の追加・確認・ON/OFF\n'
                    '`/ai_forget` — 自分の長期記憶を削除'
                ),
                inline=False,
            )
        if self.dynamic_voice is not None:
            embed.add_field(
                name='🔊 一時VC',
                value=(
                    '`/vc_create` — VCと聞き専テキストを作成\n'
                    '`/vc_create limit:5 name:雑談` — 人数・名前を指定して作成\n'
                    '固定サーバーEmbedのリアクションからも作成できます。\n'
                    '既にVCへ参加中の場合は新規作成されません。'
                ),
                inline=False,
            )
        admin_commands = (
            '`/donation_add` `/donation_remove` `/donation_list` `/donation_clear`\n'
            '`/playtime_reset`'
        )
        if self.dynamic_voice is not None:
            admin_commands += (
                '\n`/vc_reaction_add` `/vc_reaction_remove` `/vc_reaction_list`'
            )
        embed.add_field(
            name='🛠️ 管理者コマンド',
            value=(
                f'{admin_commands}\n'
                'Discord管理者または設定済みの管理ロールのみ利用できます。'
            ),
            inline=False,
        )
        embed.set_footer(text='コマンド入力時に表示される各オプションも参照してください。')
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

    async def _ai_reset_command(self, interaction: discord.Interaction) -> None:
        if self.ai_chat is None:
            await interaction.response.send_message('AIチャット機能は無効です。', ephemeral=True)
            return
        if await self.ai_chat.reset(interaction.channel):
            await interaction.response.send_message('このスレッドの会話履歴をリセットしました。')
        else:
            await interaction.response.send_message(
                'このコマンドはAI雑談スレッド内で使用してください。', ephemeral=True,
            )

    @app_commands.describe(
        content='AIに覚えさせる情報（省略すると現在の記憶を表示）',
        enabled='長期記憶を会話で使用するかどうか',
    )
    async def _ai_memory_command(
        self, interaction: discord.Interaction,
        content: str | None = None, enabled: bool | None = None,
    ) -> None:
        if self.ai_chat is None:
            await interaction.response.send_message('AIチャット機能は無効です。', ephemeral=True)
            return
        content = content.strip() if content else None
        if content and len(content) > 500:
            await interaction.response.send_message('記憶する内容は500文字以内にしてください。', ephemeral=True)
            return
        current, rows, memory_id = await self.ai_chat.memory(
            interaction.user.id, interaction.user.display_name, content, enabled,
        )
        lines = [f'長期記憶: **{"ON" if current else "OFF"}**']
        if memory_id is not None:
            lines.append(f'記憶 `#{memory_id}` を追加しました。')
        if rows:
            lines.extend(f'`#{item_id}` {text}' for item_id, text in rows)
        else:
            lines.append('保存されている記憶はありません。')
        await interaction.response.send_message('\n'.join(lines)[:1900], ephemeral=True)

    @app_commands.describe(memory_id='削除する記憶ID（省略するとすべて削除）')
    async def _ai_forget_command(
        self, interaction: discord.Interaction, memory_id: int | None = None,
    ) -> None:
        if self.ai_chat is None:
            await interaction.response.send_message('AIチャット機能は無効です。', ephemeral=True)
            return
        removed = await self.ai_chat.forget(interaction.user.id, memory_id)
        if memory_id is None:
            text = f'保存されていた長期記憶を{removed}件削除しました。'
        elif removed:
            text = f'長期記憶 `#{memory_id}` を削除しました。'
        else:
            text = f'長期記憶 `#{memory_id}` は見つかりませんでした。'
        await interaction.response.send_message(text, ephemeral=True)

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

    @app_commands.describe(limit='VCの人数上限（0は無制限）', name='チャンネル名')
    async def _voice_create_command(
        self,
        interaction: discord.Interaction,
        limit: int | None = None,
        name: str | None = None,
    ) -> None:
        if self.dynamic_voice is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('動的VC機能は利用できません。', ephemeral=True)
            return
        if interaction.user.voice and interaction.user.voice.channel:
            await interaction.response.send_message(
                '既に音声チャンネルへ参加しているため、新規作成しませんでした。', ephemeral=True,
            )
            return
        if limit is not None and not 0 <= limit <= 99:
            await interaction.response.send_message('人数は0～99で指定してください（0は無制限）。', ephemeral=True)
            return
        if name is not None and (not name.strip() or len(name.strip()) > 90):
            await interaction.response.send_message('チャンネル名は1～90文字で指定してください。', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            voice, listen = await self.dynamic_voice.create(interaction.user, name, limit)
        except ValueError:
            await interaction.followup.send('既に音声チャンネルへ参加しているため、新規作成しませんでした。', ephemeral=True)
        except Exception:
            log.exception('Dynamic voice creation failed')
            await interaction.followup.send('チャンネルの作成に失敗しました。Botの権限とカテゴリ設定を確認してください。', ephemeral=True)
        else:
            await interaction.followup.send(
                f'{voice.mention} と {listen.mention} を作成しました。', ephemeral=True,
            )

    @app_commands.describe(emoji='登録する絵文字', channel_name='作成時に使用するチャンネル名')
    async def _voice_reaction_add_command(
        self, interaction: discord.Interaction, emoji: str, channel_name: str,
    ) -> None:
        if await self._deny_donation_command(interaction):
            return
        if self.dynamic_voice is None or self.widget is None or self.widget.message is None:
            await interaction.response.send_message('動的VC機能は利用できません。', ephemeral=True)
            return
        channel_name = ' '.join(channel_name.split()).strip()
        if not channel_name or len(channel_name) > 90:
            await interaction.response.send_message('チャンネル名は1～90文字で指定してください。', ephemeral=True)
            return
        parsed = discord.PartialEmoji.from_str(emoji.strip())
        display = str(parsed)
        await interaction.response.defer(ephemeral=True)
        try:
            await self.widget.message.add_reaction(parsed)
        except discord.HTTPException:
            await interaction.followup.send(
                'その絵文字を使用できません。カスタム絵文字がBotから利用可能か確認してください。', ephemeral=True,
            )
            return
        try:
            self.dynamic_voice.register_reaction(display, channel_name)
        except OSError:
            log.exception('Failed to save dynamic voice reaction')
            try:
                await self.widget.message.remove_reaction(parsed, self.user)
            except discord.HTTPException:
                pass
            await interaction.followup.send('リアクション設定の保存に失敗しました。', ephemeral=True)
            return
        await interaction.followup.send(
            f'{display} → `{channel_name}` を登録しました。', ephemeral=True,
        )

    @app_commands.describe(emoji='削除する絵文字')
    async def _voice_reaction_remove_command(
        self, interaction: discord.Interaction, emoji: str,
    ) -> None:
        if await self._deny_donation_command(interaction):
            return
        if self.dynamic_voice is None or self.widget is None or self.widget.message is None:
            await interaction.response.send_message('動的VC機能は利用できません。', ephemeral=True)
            return
        parsed = discord.PartialEmoji.from_str(emoji.strip())
        try:
            removed = self.dynamic_voice.remove_reaction(str(parsed))
        except OSError:
            log.exception('Failed to remove dynamic voice reaction')
            await interaction.response.send_message('リアクション設定の保存に失敗しました。', ephemeral=True)
            return
        if removed is None:
            await interaction.response.send_message('その絵文字は登録されていません。', ephemeral=True)
            return
        try:
            await self.widget.message.remove_reaction(parsed, self.user)
        except discord.HTTPException:
            log.warning('Could not remove registered reaction %s from widget', parsed)
        await interaction.response.send_message(
            f'{removed.display} の登録を削除しました。', ephemeral=True,
        )

    async def _voice_reaction_list_command(self, interaction: discord.Interaction) -> None:
        if await self._deny_donation_command(interaction):
            return
        if self.dynamic_voice is None:
            await interaction.response.send_message('動的VC機能は利用できません。', ephemeral=True)
            return
        rows = [
            f'{item.display} → `{item.channel_name}`'
            for item in self.dynamic_voice.reactions.values()
        ]
        await interaction.response.send_message(
            ('\n'.join(rows)[:1900] if rows else 'カスタムリアクションは登録されていません。'),
            ephemeral=True,
        )

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if self.user is None or payload.user_id == self.user.id:
            return
        if self.dynamic_voice is None or self.widget is None or self.widget.message is None:
            return
        if payload.guild_id != self.settings.discord_guild_id or payload.message_id != self.widget.message.id:
            return
        if str(payload.emoji) == '🔊':
            channel_name = None
        else:
            channel_name = self.dynamic_voice.channel_name_for_reaction(payload.emoji)
            if channel_name is None:
                return
        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return
        member = payload.member or guild.get_member(payload.user_id)
        if member is None or member.bot:
            return
        try:
            message = self.widget.message
            await message.remove_reaction(payload.emoji, member)
        except (discord.Forbidden, discord.HTTPException):
            log.warning('Could not remove dynamic voice reaction from user %s', member.id)
        if member.voice and member.voice.channel:
            return
        try:
            await self.dynamic_voice.create(member, name=channel_name)
        except Exception:
            log.exception('Dynamic voice creation from reaction failed')

    async def on_voice_state_update(self, member, before, after) -> None:
        if self.dynamic_voice is not None and member.guild.id == self.settings.discord_guild_id:
            await self.dynamic_voice.check_once()

    async def on_ready(self) -> None:
        log.info('Discord login: %s', self.user)
        if self.dynamic_voice is not None:
            cached_guild = self.get_guild(self.settings.discord_guild_id)
            if cached_guild is not None:
                self.dynamic_voice.guild = cached_guild
        # Force a refresh after reconnecting to the Discord Gateway.
        self._presence_text = None
        if self.loop_task is None:
            self.loop_task = asyncio.create_task(self.update_loop())

    async def on_message(self, message: discord.Message) -> None:
        """Handle AI conversations and Discord-to-Bedrock forwarding."""
        if message.author.bot:
            return
        if message.guild is None:
            return
        if message.guild.id != self.settings.discord_guild_id:
            return
        if self.ai_chat is not None and self.user is not None:
            if self.ai_chat.is_ai_thread(message.channel):
                await self.ai_chat.continue_chat(message)
                return
            if await self.ai_chat.can_start(message, self.user):
                await self.ai_chat.start(message, self.user)
                return
        if message.channel.id != self.settings.discord_to_minecraft_channel_id:
            return
        if self.console is None:
            log.warning('Cannot forward Discord message: console is disabled')
            return

        content = ' '.join(message.content.split())
        if not content:
            return
        content = discord.utils.escape_mentions(content)
        content = replace_minecraft_emojis(content)
        # Prevent Bedrock target selectors such as @a and @r from being
        # interpreted if a message is later extended or reused in a command.
        content = MINECRAFT_SELECTOR_RE.sub(r'＠\1', content)
        author = discord.utils.escape_mentions(message.author.display_name)
        author = MINECRAFT_SELECTOR_RE.sub(r'＠\1', author)
        channel_name = discord.utils.escape_mentions(message.channel.name)
        text = f'(#{channel_name}) <{author}> {content}'[:240]
        try:
            await self.console.send_command(f'say {text}')
        except Exception:
            log.exception('Failed to forward Discord message to Bedrock')

    async def update_loop(self) -> None:
        assert self.widget is not None
        await self.widget.initialize()
        while not self.is_closed():
            try:
                data = await self.widget.update()
                await self._update_presence(data)
            except Exception:
                log.exception('Widget update failed')
            await asyncio.sleep(self.settings.update_interval_seconds)

    async def _update_presence(self, data: WidgetData) -> None:
        if not self.settings.presence_enabled:
            return
        text = presence_text(data)
        if text == self._presence_text:
            return
        await self.change_presence(activity=discord.Game(name=text))
        self._presence_text = text
        log.info('Discord presence updated: %s', text)

    async def close(self) -> None:
        if self.loop_task:
            self.loop_task.cancel()
        if self.console:
            await self.console.stop()
        if self.dynamic_voice:
            await self.dynamic_voice.stop()
        if self.session:
            await self.session.close()
        await super().close()

    async def start_bot(self) -> None:
        try:
            await self.start(self.settings.discord_token)
        finally:
            # setup_hook creates independent HTTP/WebSocket resources. Ensure
            # they are closed even when Discord login or Gateway DNS fails.
            if not self.is_closed():
                await self.close()
