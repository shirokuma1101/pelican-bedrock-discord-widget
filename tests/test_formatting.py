from app.formatting import cpu_text, memory_text, disk_text


def test_memory_text():
    assert memory_text(1024 * 1024 * 1024, 4096) == (
        "1,024 MB / 4,096 MB\n(25.00%)"
    )


def test_disk_text():
    assert disk_text(2 * 1024 * 1024, None) == "2 MB"
    assert disk_text(2 * 1024 * 1024, 4) == "2 MB / 4 MB\n(50.00%)"


def test_cpu_text():
    assert cpu_text(35.0, 100.0) == "35.0% / 100.0%\n(35.00%)"
    assert cpu_text(35.0, None) == "35.0%"
