from datetime import datetime, timezone

from app.playtime import _cron_matches


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
