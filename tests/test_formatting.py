from datetime import datetime, timezone

from app.formatting import cpu_text, disk_text, memory_text, progress_bar, update_text


def test_progress_bar():
    assert progress_bar(50) == "[█████░░░░░]"
    assert progress_bar(150) == "[██████████]"


def test_memory_text():
    assert memory_text(1024 * 1024 * 1024, 4096) == (
        "[██░░░░░░░░] 25.00%\n1,024 MB / 4,096 MB"
    )


def test_disk_text():
    assert disk_text(2 * 1024 * 1024, None) == "[░░░░░░░░░░] N/A\n2 MB / N/A"
    assert disk_text(2 * 1024 * 1024, 4) == "[█████░░░░░] 50.00%\n2 MB / 4 MB"


def test_cpu_text():
    assert cpu_text(35.0, 100.0) == "[████░░░░░░] 35.00%\n35.0% / 100.0%"
    assert cpu_text(35.0, None) == "[████░░░░░░] 35.00%\n35.0% / N/A"


def test_update_text_is_always_jst():
    timestamp = datetime(2026, 8, 29, 0, 0, 0, tzinfo=timezone.utc)
    assert update_text(timestamp) == "2026-08-29 09:00:00"
