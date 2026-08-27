from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord

log = logging.getLogger(__name__)


@dataclass
class VoiceChannelSet:
    voice_id: int
    listen_id: int
    empty_since: str
    base_name: str = ''
    status_message_id: int = 0


@dataclass
class VoiceReaction:
    display: str
    channel_name: str


class DynamicVoiceManager:
    def __init__(self, guild: discord.Guild, category_id: int, empty_minutes: int,
                 default_limit: int, data_file: str, reactions_file: str) -> None:
        self.guild = guild
        self.category_id = category_id
        self.empty_for = timedelta(minutes=empty_minutes)
        self.default_limit = default_limit
        self.path = Path(data_file)
        self.reactions_path = Path(reactions_file)
        self.sets: list[VoiceChannelSet] = []
        self.reactions: dict[str, VoiceReaction] = {}
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._load()
        self._load_reactions()
        self._task = asyncio.create_task(self._monitor(), name='dynamic-voice-monitor')

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _load(self) -> None:
        try:
            rows = json.loads(self.path.read_text(encoding='utf-8'))
            self.sets = [VoiceChannelSet(**row) for row in rows]
        except FileNotFoundError:
            self.sets = []
        except (OSError, ValueError, TypeError):
            log.exception('Failed to load dynamic voice channel state')
            self.sets = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(
            json.dumps([asdict(item) for item in self.sets], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        temporary.replace(self.path)

    @staticmethod
    def reaction_key(emoji: str | discord.PartialEmoji) -> str:
        if isinstance(emoji, discord.PartialEmoji):
            return f'id:{emoji.id}' if emoji.id is not None else f'unicode:{emoji.name}'
        parsed = discord.PartialEmoji.from_str(emoji.strip())
        return f'id:{parsed.id}' if parsed.id is not None else f'unicode:{parsed.name}'

    def _load_reactions(self) -> None:
        try:
            rows = json.loads(self.reactions_path.read_text(encoding='utf-8'))
            self.reactions = {key: VoiceReaction(**value) for key, value in rows.items()}
        except FileNotFoundError:
            self.reactions = {}
        except (OSError, ValueError, TypeError):
            log.exception('Failed to load dynamic voice reactions')
            self.reactions = {}

    def _save_reactions(self) -> None:
        self.reactions_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.reactions_path.with_suffix(self.reactions_path.suffix + '.tmp')
        temporary.write_text(
            json.dumps(
                {key: asdict(value) for key, value in self.reactions.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        temporary.replace(self.reactions_path)

    def register_reaction(self, emoji: str, channel_name: str) -> None:
        self.reactions[self.reaction_key(emoji)] = VoiceReaction(emoji, channel_name)
        self._save_reactions()

    def remove_reaction(self, emoji: str) -> VoiceReaction | None:
        removed = self.reactions.pop(self.reaction_key(emoji), None)
        if removed is not None:
            self._save_reactions()
        return removed

    def channel_name_for_reaction(self, emoji: discord.PartialEmoji) -> str | None:
        item = self.reactions.get(self.reaction_key(emoji))
        return item.channel_name if item else None

    async def create(self, member: discord.Member, name: str | None = None,
                     limit: int | None = None) -> tuple[discord.VoiceChannel, discord.TextChannel]:
        if member.voice and member.voice.channel:
            raise ValueError('already_connected')
        category = self.guild.get_channel(self.category_id)
        if category is None:
            category = await self.guild.fetch_channel(self.category_id)
        if not isinstance(category, discord.CategoryChannel):
            raise RuntimeError('DYNAMIC_VOICE_CATEGORY_ID is not a category')

        clean_name = ' '.join((name or '').split()).strip()
        base_name = clean_name or f'{member.display_name}のVC'
        base_name = base_name[:90]
        user_limit = self.default_limit if limit is None else limit
        user_limit = min(99, max(0, user_limit))
        reason = f'Dynamic voice set requested by {member} ({member.id})'

        async with self._lock:
            voice: discord.VoiceChannel | None = None
            try:
                voice = await self.guild.create_voice_channel(
                    base_name, category=category, user_limit=user_limit, reason=reason,
                )
                listen = await self.guild.create_text_channel(
                    f'{base_name}｜聞き専'[:100],
                    category=category,
                    topic=f'{voice.mention} の聞き専用テキストチャンネル',
                    reason=reason,
                )
            except Exception:
                if voice is not None:
                    try:
                        await voice.delete(reason='Rollback incomplete dynamic voice set')
                    except discord.HTTPException:
                        log.exception('Failed to roll back dynamic voice channel')
                raise

            item = VoiceChannelSet(
                voice_id=voice.id,
                listen_id=listen.id,
                empty_since=datetime.now(timezone.utc).isoformat(),
                base_name=base_name,
            )
            self.sets.append(item)
            await self._update_expiration_message(listen, item, datetime.now(timezone.utc))
            self._save()
            return voice, listen

    async def check_once(self) -> None:
        now = datetime.now(timezone.utc)
        changed = False
        async with self._lock:
            retained: list[VoiceChannelSet] = []
            for item in self.sets:
                voice = self.guild.get_channel(item.voice_id)
                listen = self.guild.get_channel(item.listen_id)
                channels = [channel for channel in (voice, listen) if channel is not None]
                if not channels:
                    changed = True
                    continue
                occupied = (
                    isinstance(voice, discord.VoiceChannel)
                    and any(not member.bot for member in voice.members)
                )
                if occupied:
                    if item.empty_since:
                        item.empty_since = ''
                        changed = True
                        if isinstance(listen, discord.TextChannel):
                            changed |= await self._update_expiration_message(listen, item, None)
                    retained.append(item)
                    continue
                if not item.empty_since:
                    item.empty_since = now.isoformat()
                    changed = True
                    if isinstance(listen, discord.TextChannel):
                        changed |= await self._update_expiration_message(listen, item, now)
                    retained.append(item)
                    continue
                try:
                    empty_since = datetime.fromisoformat(item.empty_since)
                except ValueError:
                    item.empty_since = now.isoformat()
                    changed = True
                    retained.append(item)
                    continue
                if now - empty_since < self.empty_for:
                    if isinstance(listen, discord.TextChannel) and not item.status_message_id:
                        changed |= await self._update_expiration_message(listen, item, empty_since)
                    retained.append(item)
                    continue
                for channel in channels:
                    try:
                        await channel.delete(reason='Dynamic voice set remained empty')
                    except discord.NotFound:
                        pass
                    except discord.HTTPException:
                        log.exception('Failed to delete dynamic voice channel %s', channel.id)
                        retained.append(item)
                        break
                else:
                    changed = True
            self.sets = retained
            if changed:
                self._save()

    async def _update_expiration_message(
        self,
        channel: discord.TextChannel,
        item: VoiceChannelSet,
        empty_since: datetime | None,
    ) -> bool:
        if empty_since is None:
            content = '🟢 VCは使用中です。自動削除タイマーは停止しています。'
        else:
            expires_at = int((empty_since + self.empty_for).timestamp())
            content = f'🕒 VCが無人のため、<t:{expires_at}:R>にこのチャンネルとVCを削除します。'
        try:
            if item.status_message_id:
                await channel.get_partial_message(item.status_message_id).edit(content=content)
                return False
            message = await channel.send(content)
            item.status_message_id = message.id
            return True
        except discord.HTTPException:
            log.exception('Failed to update dynamic voice expiration message for %s', channel.id)
            return False

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(30)
            try:
                await self.check_once()
            except Exception:
                log.exception('Dynamic voice monitor failed')
