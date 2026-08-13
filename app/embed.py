from __future__ import annotations

import discord

from .config import Settings
from .formatting import cpu_text, disk_text, memory_text, update_text
from .models import WidgetData


def make_embed(data: WidgetData, settings: Settings) -> discord.Embed:
    if data.bedrock.online:
        state, colour = "🟢 ONLINE", discord.Colour.green()
    elif data.resources.current_state.lower() in {"starting", "running"}:
        state, colour = "🟡 STARTING", discord.Colour.yellow()
    else:
        state, colour = "🔴 OFFLINE", discord.Colour.red()

    motd = (data.bedrock.motd or "").strip()
    title = f"🖥️ {settings.server_display_name}"
    if motd:
        title += f"｜{motd}"

    embed = discord.Embed(
        title=title[:256],
        description=f"**現在の状態**\n`{state}`",
        colour=colour,
    )

    embed.add_field(
        name="CPU使用率",
        value=f"`{cpu_text(data.resources.cpu_absolute, data.server.cpu_limit)}`",
        inline=True,
    )
    embed.add_field(
        name="メモリ使用率",
        value=f"`{memory_text(data.resources.memory_bytes, data.server.memory_limit_mb)}`",
        inline=True,
    )
    embed.add_field(
        name="ディスク使用量",
        value=f"`{disk_text(data.resources.disk_bytes, data.server.disk_limit_mb)}`",
        inline=True,
    )

    address = settings.public_address or f"{settings.bedrock_host}:{settings.bedrock_port}"
    embed.add_field(name="アドレス", value=f"`{address}`", inline=True)

    connection_state = "🟢 接続" if data.bedrock.online else "🔴 未接続"
    mc_info = (
        f"**接続状態**\n`{connection_state}`\n"
        f"**Version**\n`{data.bedrock.version or 'N/A'}`"
    )
    embed.add_field(name="マイクラについて", value=mc_info, inline=False)

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
        embed.add_field(
            name="☕ サポート",
            value=f"[Ko-fiで支援する]({settings.ko_fi_url})",
            inline=False,
        )

    if data.donations:
        donation_lines = [
            f"**#{item.id} {item.donor}**\n{item.message}"
            for item in data.donations[-5:]
        ]
        donation_text = "\n\n".join(donation_lines)
        if len(donation_text) > 1024:
            donation_text = "…" + donation_text[-1023:]
        embed.add_field(name="📌 寄付者メッセージ", value=donation_text, inline=False)

    embed.set_footer(
        text=f"{settings.update_interval_seconds}秒更新 / 更新: {update_text(data.last_updated)}"
    )
    return embed
