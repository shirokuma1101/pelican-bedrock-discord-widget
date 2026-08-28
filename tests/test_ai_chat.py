from app.ai_chat import split_discord_message, strip_bot_mention


def test_strip_bot_mention_supports_both_discord_formats() -> None:
    assert strip_bot_mention('<@123> こんにちは', 123) == 'こんにちは'
    assert strip_bot_mention('ねえ <@!123> テスト', 123) == 'ねえ  テスト'


def test_split_discord_message_preserves_all_content() -> None:
    content = 'a' * 2000 + ' ' + 'b' * 10
    chunks = split_discord_message(content)
    assert chunks == ['a' * 2000, 'b' * 10]
    assert all(len(chunk) <= 2000 for chunk in chunks)
