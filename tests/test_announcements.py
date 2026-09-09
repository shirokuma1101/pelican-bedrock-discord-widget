from datetime import datetime, timedelta, timezone

from app.announcements import AnnouncementStore


def test_active_filters_expired_announcements(tmp_path):
    store = AnnouncementStore(str(tmp_path / 'announcements.json'))
    now = datetime.now(timezone.utc)
    active = store.add('掲載中', '本文', now + timedelta(hours=1))
    store.add('期限切れ', '本文', now - timedelta(hours=1))

    assert store.active(now) == [active]


def test_announcements_are_persisted(tmp_path):
    path = tmp_path / 'announcements.json'
    store = AnnouncementStore(str(path))
    item = store.add('タイトル', 'メッセージ', None)

    restored = AnnouncementStore(str(path))

    assert restored.all() == [item]


def test_remove_and_clear(tmp_path):
    store = AnnouncementStore(str(tmp_path / 'announcements.json'))
    first = store.add('1', '本文', None)
    store.add('2', '本文', None)

    assert store.remove(first.id) is True
    assert store.remove(first.id) is False
    assert store.clear() == 1
    assert store.all() == []
