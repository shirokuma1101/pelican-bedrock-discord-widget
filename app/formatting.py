from __future__ import annotations

from datetime import datetime

from .timezones import JST


def mb(value: int | None) -> float | None:
    return None if value is None else value / 1024 / 1024


def progress_bar(percent: float, width: int = 10) -> str:
    """Return a compact CLI-style progress bar."""
    width = max(1, width)
    filled = round(max(0.0, min(100.0, percent)) / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


def memory_text(used: int | None, limit_mb: int | None) -> str:
    used_mb = mb(used)
    if used_mb is None:
        return "N/A"

    if limit_mb is None or limit_mb <= 0:
        return f"{progress_bar(0)} N/A\n{used_mb:,.0f} MB / N/A"

    percent = used_mb / limit_mb * 100
    return f"{progress_bar(percent)} {percent:.2f}%\n{used_mb:,.0f} MB / {limit_mb:,.0f} MB"


def cpu_text(used: float | None, limit: float | None) -> str:
    if used is None:
        return "N/A"

    if limit is None or limit <= 0:
        return f"{progress_bar(used)} {used:.2f}%\n{used:.1f}% / N/A"

    percent = used / limit * 100
    return f"{progress_bar(percent)} {percent:.2f}%\n{used:.1f}% / {limit:.1f}%"


def disk_text(used: int | None, limit_mb: int | None) -> str:
    used_mb = mb(used)
    if used_mb is None:
        return "N/A"

    if limit_mb is None or limit_mb <= 0:
        return f"{progress_bar(0)} N/A\n{used_mb:,.0f} MB / N/A"

    percent = used_mb / limit_mb * 100
    return f"{progress_bar(percent)} {percent:.2f}%\n{used_mb:,.0f} MB / {limit_mb:,.0f} MB"


def update_text(timestamp: datetime) -> str:
    return timestamp.astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
