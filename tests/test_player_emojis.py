from app.player_emojis import PlayerEmojiStore


def test_player_emoji_store_is_case_insensitive(tmp_path) -> None:
    path = tmp_path / 'player_emojis.json'
    store = PlayerEmojiStore(str(path))
    store.set('Player One', '<:member:123>')

    reopened = PlayerEmojiStore(str(path))
    assert reopened.get('player one') == '<:member:123>'
    assert reopened.all()[0].player == 'Player One'

    removed = reopened.remove('PLAYER ONE')
    assert removed is not None
    assert reopened.get('Player One') is None
