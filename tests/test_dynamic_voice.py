from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from app.dynamic_voice import DynamicVoiceManager, VoiceChannelSet


class FakeGuild:
    pass


def test_state_round_trip(tmp_path):
    path = tmp_path / 'voice.json'
    manager = DynamicVoiceManager(FakeGuild(), 123, 10, 5, str(path), str(tmp_path / 'reactions.json'))
    manager.sets = [VoiceChannelSet(voice_id=1, listen_id=2, empty_since='2026-01-01T00:00:00+00:00')]

    manager._save()

    restored = DynamicVoiceManager(FakeGuild(), 123, 10, 5, str(path), str(tmp_path / 'reactions.json'))
    restored._load()
    assert restored.sets == manager.sets
    assert json.loads(path.read_text(encoding='utf-8'))[0]['listen_id'] == 2


def test_configuration_values_are_normalized(tmp_path):
    manager = DynamicVoiceManager(
        FakeGuild(), 123, 10, 5, str(tmp_path / 'voice.json'), str(tmp_path / 'reactions.json')
    )

    assert manager.category_id == 123
    assert manager.default_limit == 5
    assert manager.empty_for == timedelta(minutes=10)


def test_reaction_mapping_round_trip(tmp_path):
    reactions = tmp_path / 'reactions.json'
    manager = DynamicVoiceManager(
        FakeGuild(), 123, 10, 5, str(tmp_path / 'voice.json'), str(reactions)
    )
    manager.register_reaction('<:minecraft:123456789012345678>', 'Minecraft')

    restored = DynamicVoiceManager(
        FakeGuild(), 123, 10, 5, str(tmp_path / 'voice.json'), str(reactions)
    )
    restored._load_reactions()

    assert restored.reactions['id:123456789012345678'].channel_name == 'Minecraft'

