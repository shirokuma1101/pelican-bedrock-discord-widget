from datetime import datetime, timezone

from app.playtime import _cron_matches, _next_cron_minute, format_duration


def test_format_duration_uses_compact_hours_and_minutes():
    assert format_duration(0) == "0h00m"
    assert format_duration(8 * 60) == "0h08m"
    assert format_duration(1 * 3600 + 5 * 60) == "1h05m"
    assert format_duration(49 * 3600 + 7 * 60) == "49h07m"


def test_monthly_cron_matches_only_first_day_at_midnight():
    expression = "0 0 1 * *"

    assert _cron_matches(
        expression,
        datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert not _cron_matches(
        expression,
        datetime(2026, 9, 1, 0, 1, tzinfo=timezone.utc),
    )
    assert not _cron_matches(
        expression,
        datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc),
    )
    assert not _cron_matches(
        expression,
        datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc),
    )


def test_cron_step_and_range_fields():
    assert _cron_matches(
        "*/15 9-17 * * 1-5",
        datetime(2026, 8, 17, 9, 30, tzinfo=timezone.utc),
    )
    assert not _cron_matches(
        "*/15 9-17 * * 1-5",
        datetime(2026, 8, 17, 9, 31, tzinfo=timezone.utc),
    )


def test_next_monthly_cron_minute():
    assert _next_cron_minute(
        "0 0 1 * *",
        datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
    ) == datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
