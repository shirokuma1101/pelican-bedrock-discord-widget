from app.ai_database import ChatDatabase


def test_database_persists_threads_messages_and_memories(tmp_path) -> None:
    path = tmp_path / 'chat.sqlite3'
    database = ChatDatabase(str(path))
    database.initialize()
    database.upsert_user(10, 'Player')
    database.register_thread(30, 1, 20, 10, 100)
    database.add_message(1, 20, 30, 10, 'user', 101, 'Player: hello')
    database.add_message(1, 20, 30, None, 'assistant', 102, 'hello')
    memory_id = database.add_memory(10, '紅茶が好き')

    reopened = ChatDatabase(str(path))
    reopened.initialize()
    assert reopened.active_thread_ids() == {30}
    assert reopened.recent_messages(30, 20) == [
        {'role': 'user', 'content': 'Player: hello'},
        {'role': 'assistant', 'content': 'hello'},
    ]
    assert reopened.list_memories(10) == [(memory_id, '紅茶が好き')]

    assert reopened.reset_thread(30)
    assert reopened.recent_messages(30, 20) == []
    assert reopened.forget_memory(10, memory_id) == 1


def test_user_can_disable_memory(tmp_path) -> None:
    database = ChatDatabase(str(tmp_path / 'chat.sqlite3'))
    database.initialize()
    database.upsert_user(10, 'Player')
    assert database.memory_enabled(10)
    database.set_memory_enabled(10, False)
    assert not database.memory_enabled(10)
