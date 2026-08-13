from __future__ import annotations

from datetime import datetime


def mb(value: int | None) -> float | None:
    return None if value is None else value / 1024 / 1024


def memory_text(used: int | None, limit_mb: int | None) -> str:
    used_mb = mb(used)
    if used_mb is None:
        return "N/A"

    if limit_mb is None:
        return f"{used_mb:,.0f} MB"

    percent = used_mb / limit_mb * 100
    return f"{used_mb:,.0f} MB / {limit_mb:,.0f} MB\n({percent:.2f}%)"


def cpu_text(used: float | None, limit: float | None) -> str:
    if used is None:
        return "N/A"

    if limit is None:
        return f"{used:.1f}%"

    percent = used / limit * 100
    return f"{used:.1f}% / {limit:.1f}%\n({percent:.2f}%)"


def disk_text(used: int | None, limit_mb: int | None) -> str:
    used_mb = mb(used)
    if used_mb is None:
        return "N/A"

    if limit_mb is None:
        return f"{used_mb:,.0f} MB"

    percent = used_mb / limit_mb * 100
    return f"{used_mb:,.0f} MB / {limit_mb:,.0f} MB\n({percent:.2f}%)"


def update_text(timestamp: datetime) -> str:
    return timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
