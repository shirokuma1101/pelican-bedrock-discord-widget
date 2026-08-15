from __future__ import annotations

import discord

from .config import Settings
from .formatting import cpu_text, disk_text, memory_text, update_text
from .models import WidgetData
from .playtime import format_duration


def make_embed(data: WidgetData, settings: Settings) -> discord.Embed:
    if data.bedrock.online:
        state, colour = "🟢 ONLINE", discord.Colour.green()
    elif data.resources.current_state.lower() in {"starting", "running"}:
        state, colour = "🟡 STARTING", discord.Colour.yellow()
    else:
        state, colour = "🔴 OFFLINE", discord.Colour.red()

    motd = (data.bedrock.motd or "").strip()
    title = f"🖥️ {data.server.name}"
    if motd:
        title += f"｜{motd}"

    embed = discord.Embed(
        title=title[:256],
        colour=colour,
    )
    embed.set_author(
        name="GitHub",
        url="https://github.com/shirokuma1101/pelican-bedrock-discord-widget",
    )

    address = settings.public_address or f"{settings.bedrock_host}:{settings.bedrock_port}"

    connection_state = "🟢 接続" if data.bedrock.online else "🔴 未接続"
    embed.add_field(
        name="接続状態",
        value=f"`{connection_state}`",
        inline=True,
    )
    embed.add_field(
        name="アドレス",
        value=f"`{address}`",
        inline=True,
    )
    embed.add_field(
        name="Version",
        value=f"`{data.bedrock.version or 'N/A'}`",
        inline=True,
    )

    if data.bedrock.online:
        console_count = (
            f"{data.console.online_players}/{data.console.max_players}"
            if data.console.online_players is not None
            and data.console.max_players is not None
            else None
        )
        status_count = (
            f"{data.bedrock.online_players}/{data.bedrock.max_players}"
            if data.bedrock.online_players is not None
            and data.bedrock.max_players is not None
            else "N/A"
        )
        count = console_count or status_count

        if data.console.players:
            visible = data.console.players[: settings.max_players_displayed]
            player_text = f"`{count}`\n" + "\n".join(
                f"`{name}`" for name in visible
            )
            extra = len(data.console.players) - len(visible)
            if extra > 0:
                player_text += f"\n`… 他 {extra} 人`"
        else:
            player_text = f"`{count}`\n`プレイヤー名取得待機中`"
    else:
        player_text = "`サーバーOFFLINE`"

    embed.add_field(
        name="プレイヤー",
        value=player_text,
        inline=True,
    )

    if data.playtime_ranking:
        ranking_text = "\n".join(
            f"**{index}位** {player} — `{format_duration(seconds)}`"
            for index, (player, seconds) in enumerate(data.playtime_ranking[:5], 1)
        )
    else:
        ranking_text = "なし"
    embed.add_field(
        name="🏆 プレイ時間ランキング",
        value=(
            f"統計開始: `{data.playtime_started_at.astimezone().strftime('%Y-%m-%d')}`\n{ranking_text}"
            if data.playtime_started_at is not None
            else ranking_text
        ),
        inline=True,
    )
    # Fill the third inline column so resource fields start on the next row.
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    embed.add_field(
        name="CPU使用量",
        value=f"`{cpu_text(data.resources.cpu_absolute, data.server.cpu_limit)}`",
        inline=True,
    )
    embed.add_field(
        name="メモリ使用量",
        value=f"`{memory_text(data.resources.memory_bytes, data.server.memory_limit_mb)}`",
        inline=True,
    )
    embed.add_field(
        name="ディスク使用量",
        value=f"`{disk_text(data.resources.disk_bytes, data.server.disk_limit_mb)}`",
        inline=True,
    )

    if data.console.logs:
        lines = data.console.logs[-settings.console_log_lines:]
        logs = "\n".join(
            f"`{i + 1:02}` {line}" for i, line in enumerate(lines)
        )
        if len(logs) > 1024:
            logs = "…" + logs[-1023:]
        embed.add_field(name="サーバーログ", value=logs, inline=False)

    if data.errors:
        embed.add_field(
            name="⚠️ 取得エラー",
            value="\n".join(f"• {x}" for x in data.errors[:5])[:1024],
            inline=False,
        )

    if settings.ko_fi_url:
        support_text = f"[Ko-fiで支援する]({settings.ko_fi_url})"
    else:
        support_text = "未設定"
    embed.add_field(name="☕ サポート", value=support_text, inline=False)

    donation_lines = [
        f"**#{item.id} {item.donor}**\n{item.message}"
        for item in data.donations[-5:]
    ]
    donation_text = "\n\n".join(donation_lines) or "なし"
    if len(donation_text) > 1024:
        donation_text = "…" + donation_text[-1023:]
    embed.add_field(name="📌 寄付者からのひとこと", value=donation_text, inline=False)

    embed.set_footer(
        text=f"{settings.update_interval_seconds}秒更新 / 更新: {update_text(data.last_updated)}"
    )
    return embed
