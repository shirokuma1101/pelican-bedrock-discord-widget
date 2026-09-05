from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatDatabase:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA journal_mode = WAL')
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    discord_user_id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    memory_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    owner_user_id INTEGER NOT NULL,
                    starter_message_id INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    reset_at TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    thread_id INTEGER NOT NULL,
                    user_id INTEGER,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    message_id INTEGER,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS messages_thread_id_id ON messages(thread_id, id);
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(discord_user_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS memories_user_id_id ON memories(user_id, id);
                '''
            )
            columns = {
                str(row['name'])
                for row in connection.execute('PRAGMA table_info(users)').fetchall()
            }
            if 'terms_accepted' not in columns:
                connection.execute('ALTER TABLE users ADD COLUMN terms_accepted INTEGER')
            if 'history_consent' not in columns:
                connection.execute('ALTER TABLE users ADD COLUMN history_consent INTEGER')
            if 'consent_updated_at' not in columns:
                connection.execute('ALTER TABLE users ADD COLUMN consent_updated_at TEXT')
            if 'history_learned_at' not in columns:
                connection.execute('ALTER TABLE users ADD COLUMN history_learned_at TEXT')

    def upsert_user(self, user_id: int, display_name: str) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                '''INSERT INTO users(discord_user_id, display_name, created_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(discord_user_id) DO UPDATE SET
                       display_name = excluded.display_name, updated_at = excluded.updated_at''',
                (user_id, display_name, now, now),
            )

    def register_thread(self, thread_id: int, guild_id: int, channel_id: int,
                        owner_user_id: int, starter_message_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                '''INSERT OR REPLACE INTO threads(
                       thread_id, guild_id, channel_id, owner_user_id,
                       starter_message_id, active, created_at, reset_at
                   ) VALUES (?, ?, ?, ?, ?, 1, ?, NULL)''',
                (thread_id, guild_id, channel_id, owner_user_id, starter_message_id, utc_now()),
            )

    def active_thread_ids(self) -> set[int]:
        with self._connect() as connection:
            rows = connection.execute('SELECT thread_id FROM threads WHERE active = 1').fetchall()
        return {int(row['thread_id']) for row in rows}

    def add_message(self, guild_id: int, channel_id: int, thread_id: int,
                    user_id: int | None, role: str, message_id: int | None,
                    content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                '''INSERT INTO messages(
                       guild_id, channel_id, thread_id, user_id,
                       role, message_id, content, timestamp
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (guild_id, channel_id, thread_id, user_id, role, message_id, content, utc_now()),
            )

    def recent_messages(self, thread_id: int, limit: int) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT role, content FROM messages WHERE thread_id = ? ORDER BY id DESC LIMIT ?',
                (thread_id, limit),
            ).fetchall()
        return [{'role': str(row['role']), 'content': str(row['content'])} for row in reversed(rows)]

    def reset_thread(self, thread_id: int) -> bool:
        with self._connect() as connection:
            exists = connection.execute(
                'SELECT 1 FROM threads WHERE thread_id = ? AND active = 1', (thread_id,),
            ).fetchone()
            if exists is None:
                return False
            connection.execute('DELETE FROM messages WHERE thread_id = ?', (thread_id,))
            connection.execute('UPDATE threads SET reset_at = ? WHERE thread_id = ?', (utc_now(), thread_id))
        return True

    def memory_enabled(self, user_id: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT memory_enabled FROM users WHERE discord_user_id = ?', (user_id,),
            ).fetchone()
        return True if row is None else bool(row['memory_enabled'])

    def set_memory_enabled(self, user_id: int, enabled: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                'UPDATE users SET memory_enabled = ?, updated_at = ? WHERE discord_user_id = ?',
                (int(enabled), utc_now(), user_id),
            )

    def consent_status(self, user_id: int) -> tuple[bool | None, bool | None]:
        with self._connect() as connection:
            row = connection.execute(
                'SELECT terms_accepted, history_consent FROM users WHERE discord_user_id = ?',
                (user_id,),
            ).fetchone()
        if row is None:
            return None, None
        terms = row['terms_accepted']
        history = row['history_consent']
        return (
            None if terms is None else bool(terms),
            None if history is None else bool(history),
        )

    def set_consent(self, user_id: int, terms_accepted: bool,
                    history_consent: bool) -> None:
        with self._connect() as connection:
            connection.execute(
                '''UPDATE users SET terms_accepted = ?, history_consent = ?,
                   consent_updated_at = ?, updated_at = ?
                   WHERE discord_user_id = ?''',
                (
                    int(terms_accepted), int(history_consent), utc_now(), utc_now(),
                    user_id,
                ),
            )

    def mark_history_learned(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                'UPDATE users SET history_learned_at = ?, updated_at = ? WHERE discord_user_id = ?',
                (utc_now(), utc_now(), user_id),
            )

    def add_memory(self, user_id: int, content: str) -> int:
        now = utc_now()
        with self._connect() as connection:
            cursor = connection.execute(
                'INSERT INTO memories(user_id, content, created_at, updated_at) VALUES (?, ?, ?, ?)',
                (user_id, content, now, now),
            )
            return int(cursor.lastrowid)

    def list_memories(self, user_id: int, limit: int = 20) -> list[tuple[int, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT id, content FROM memories WHERE user_id = ? ORDER BY id DESC LIMIT ?',
                (user_id, limit),
            ).fetchall()
        return [(int(row['id']), str(row['content'])) for row in rows]

    def forget_memory(self, user_id: int, memory_id: int | None) -> int:
        with self._connect() as connection:
            if memory_id is None:
                cursor = connection.execute('DELETE FROM memories WHERE user_id = ?', (user_id,))
            else:
                cursor = connection.execute(
                    'DELETE FROM memories WHERE user_id = ? AND id = ?', (user_id, memory_id),
                )
            return cursor.rowcount
