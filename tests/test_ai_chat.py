import asyncio
from types import SimpleNamespace

import discord

from app.ai_chat import AIConsentView, LLMChatManager, split_discord_message, strip_bot_mention


def test_strip_bot_mention_supports_both_discord_formats() -> None:
    assert strip_bot_mention('<@123> こんにちは', 123) == 'こんにちは'
    assert strip_bot_mention('ねえ <@!123> テスト', 123) == 'ねえ  テスト'


def test_split_discord_message_preserves_all_content() -> None:
    content = 'a' * 2000 + ' ' + 'b' * 10
    chunks = split_discord_message(content)
    assert chunks == ['a' * 2000, 'b' * 10]
    assert all(len(chunk) <= 2000 for chunk in chunks)


def test_complete_sends_deepseek_authentication_and_model() -> None:
    class FakeResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def raise_for_status(self) -> None:
            pass

        async def json(self) -> dict:
            return {'choices': [{'message': {'content': ' こんにちは '}}]}

    class FakeSession:
        def __init__(self) -> None:
            self.url = ''
            self.kwargs = {}

        def post(self, url, **kwargs):
            self.url = url
            self.kwargs = kwargs
            return FakeResponse()

    settings = SimpleNamespace(
        llm_database_file=':memory:',
        llm_max_concurrent_requests=1,
        llm_base_url='https://api.deepseek.com',
        deepseek_api_key='secret-key',
        llm_system_prompt='system',
        llm_max_tokens=512,
        llm_model='deepseek-v4-flash',
        llm_timeout_seconds=120,
    )
    session = FakeSession()
    manager = LLMChatManager(settings, session)

    answer = asyncio.run(manager._complete(
        [{'role': 'user', 'content': 'hello'}], [],
    ))

    assert answer == 'こんにちは'
    assert session.url == 'https://api.deepseek.com/v1/chat/completions'
    assert session.kwargs['headers']['Authorization'] == 'Bearer secret-key'
    assert session.kwargs['json']['model'] == 'deepseek-v4-flash'


def test_continue_chat_requires_each_users_consent() -> None:
    settings = SimpleNamespace(
        llm_database_file=':memory:',
        llm_max_concurrent_requests=1,
        llm_terms_text='terms',
        llm_history_learn_messages=30,
    )
    manager = LLMChatManager(settings, SimpleNamespace())
    calls = []

    class FakeDatabase:
        def upsert_user(self, user_id, display_name):
            calls.append(('upsert', user_id, display_name))

        def consent_status(self, user_id):
            return None, None

    class FakeMessage:
        def __init__(self):
            self.content = '未同意ユーザーの発言'
            self.guild = object()
            self.channel = object()
            self.author = SimpleNamespace(id=22, display_name='guest')
            self.id = 123
            self.reply_kwargs = None

        async def reply(self, **kwargs):
            self.reply_kwargs = kwargs
            return SimpleNamespace()

    manager.database = FakeDatabase()
    message = FakeMessage()

    # Make the lightweight fake channel pass the runtime Discord type check.
    original_thread_type = discord.Thread
    try:
        discord.Thread = object
        asyncio.run(manager.continue_chat(message))
    finally:
        discord.Thread = original_thread_type

    assert calls == [('upsert', 22, 'guest')]
    assert message.reply_kwargs is not None
    assert isinstance(message.reply_kwargs['view'], AIConsentView)
