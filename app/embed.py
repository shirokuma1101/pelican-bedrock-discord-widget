from __future__ import annotations

import discord

from .config import Settings
from .formatting import mb, progress_bar, update_text
from .timezones import JST
from .models import WidgetData
from .playtime import format_duration


def goal_progress_bar(value: str, width: int = 10) -> str:
    try:
        percentage = min(100.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return f"[{'░' * width}] {value}%"
    filled = round(percentage / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {percentage:.2f}%"


def resource_percentage(label: str, used: float | None, limit: float | None) -> str:
    if used is None or limit is None or limit <= 0:
        return f"`{label} {'░' * 10} N/A`"
    percentage = used / limit * 100
    return f"`{label} {progress_bar(percentage)} {percentage:.2f}%`"


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
    if settings.website_url:
        embed.set_author(
            name="PostMineClan 公式サイト",
            url=settings.website_url,
        )
    else:
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
                (
                    f"{data.player_emojis[name.casefold()]} `{name}`"
                    if name.casefold() in data.player_emojis
                    else f"`{name}`"
                )
                for name in visible
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
            f"`{index}位 {player} — {format_duration(seconds)}`"
            for index, (player, seconds) in enumerate(data.playtime_ranking[:5], 1)
        )
    else:
        ranking_text = "`なし`"
    reset_text = (
        data.playtime_next_reset_at.astimezone(JST).strftime('%Y-%m-%d %H:%M')
        if data.playtime_next_reset_at is not None
        else '自動リセットなし'
    )
    embed.add_field(
        name="🏆 プレイ時間ランキング",
        value=(
            f"統計開始: {data.playtime_started_at.astimezone(JST).strftime('%Y-%m-%d')}\n"
            f"リセット予定: {reset_text}\n{ranking_text}"
            if data.playtime_started_at is not None
            else f"リセット予定: {reset_text}\n{ranking_text}"
        ),
        inline=True,
    )
    # Fill the third inline column so resource fields start on the next row.
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    memory_used_mb = mb(data.resources.memory_bytes)
    disk_used_mb = mb(data.resources.disk_bytes)
    resources_text = "\n".join((
        resource_percentage("CPU", data.resources.cpu_absolute, data.server.cpu_limit),
        resource_percentage("MEM", memory_used_mb, data.server.memory_limit_mb),
        resource_percentage("DSK", disk_used_mb, data.server.disk_limit_mb),
    ))
    embed.add_field(name="📊 リソース使用率", value=resources_text, inline=True)

    if data.backups:
        backup_lines = []
        for backup in data.backups[:3]:
            if backup.completed_at is None:
                status = "⏳"
            elif backup.successful is True:
                status = "✅"
            else:
                status = "❌"
            created = (
                backup.created_at.astimezone(JST).strftime("%m/%d %H:%M")
                if backup.created_at is not None
                else "日時不明"
            )
            backup_lines.append(f"{status} `{created}`")
        backups_text = "\n".join(backup_lines)
    else:
        backups_text = "なし"
    embed.add_field(name="💾 バックアップ履歴", value=backups_text[:1024], inline=True)

    if data.cpu_watts is not None:
        storage_watts = (
            settings.hdd_count * settings.hdd_watts_each
            + settings.ssd_count * settings.ssd_watts_each
        )
        total_watts = (
            data.cpu_watts + storage_watts + settings.other_hardware_watts
        )
        monthly_electricity_cost = (
            total_watts / 1000
            * 24
            * 30
            * settings.electricity_yen_per_kwh
        )
        monthly_total_cost = (
            monthly_electricity_cost + settings.domain_annual_cost_yen / 12
        )
        maintenance_text = (
            f"**PC全体概算**\n"
            f"{total_watts:.1f} W\n"
            f"**電気料金（月額概算）**\n"
            f"約{monthly_electricity_cost:,.0f}円/月\n"
            f"**ドメイン維持費**\n"
            f"{settings.domain_annual_cost_yen:,.0f}円/年 "
            f"（約{settings.domain_annual_cost_yen / 12:,.0f}円/月）\n"
            f"**合計（月額概算）**\n"
            f"約{monthly_total_cost:,.0f}円/月"
        )
    else:
        maintenance_text = (
            "**PC全体概算**\nN/A\n"
            "**電気料金（月額概算）**\nN/A\n"
            f"**ドメイン維持費**\n{settings.domain_annual_cost_yen:,.0f}円/年 "
            f"（約{settings.domain_annual_cost_yen / 12:,.0f}円/月）\n"
            "**合計（月額概算）**\nN/A"
        )
    embed.add_field(name="💰 維持費", value=maintenance_text, inline=True)

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
    support_text += (
        "\n[GitHubを見る]"
        "(https://github.com/shirokuma1101/pelican-bedrock-discord-widget)"
    )
    embed.add_field(name="☕ サポート", value=support_text, inline=True)
    if data.kofi_goal:
        goal_text = (
            f"**{data.kofi_goal.title}**"
            f"\n`{goal_progress_bar(data.kofi_goal.percentage)}`"
            f"\n`{data.kofi_goal.current_text} / {data.kofi_goal.target_text}`"
        )
        embed.add_field(name="🎯 予算", value=goal_text, inline=True)

    donation_lines = [
        f"**#{item.id} {item.donor}**\n{item.message}"
        for item in data.donations[-5:]
    ]
    donation_text = "\n\n".join(donation_lines) or "なし"
    if len(donation_text) > 1024:
        donation_text = "…" + donation_text[-1023:]
    embed.add_field(name="📌 寄付者からのひとこと", value=donation_text, inline=False)

    if settings.dynamic_voice_category_id is not None:
        embed.add_field(
            name="🔊 一時VC",
            value="このメッセージの 🔊 を押すと、VCと聞き専テキストを作成します。",
            inline=False,
        )

    embed.set_footer(
        text=f"{settings.update_interval_seconds}秒更新 / 更新: {update_text(data.last_updated)}"
    )
    return embed
