from datetime import datetime, timezone

from app.bot import presence_text
from app.models import (
    BedrockStatus,
    ConsoleSnapshot,
    PelicanServer,
    Resources,
    WidgetData,
)


def widget_data(
    *,
    console_online: int | None = None,
    console_max: int | None = None,
    bedrock_online: int | None = None,
    bedrock_max: int | None = None,
    state: str = 'running',
) -> WidgetData:
    return WidgetData(
        server=PelicanServer(identifier='test', name='test'),
        resources=Resources(current_state=state),
        bedrock=BedrockStatus(
            online=bedrock_online is not None,
            online_players=bedrock_online,
            max_players=bedrock_max,
        ),
        console=ConsoleSnapshot(
            online_players=console_online,
            max_players=console_max,
        ),
        last_updated=datetime.now(timezone.utc),
        errors=[],
    )


def test_presence_prefers_console_count() -> None:
    data = widget_data(
        console_online=2,
        console_max=20,
        bedrock_online=1,
        bedrock_max=10,
    )
    assert presence_text(data) == 'Minecraft｜2/20人が参加中'


def test_presence_falls_back_to_bedrock_count() -> None:
    data = widget_data(bedrock_online=1, bedrock_max=20)
    assert presence_text(data) == 'Minecraft｜1/20人が参加中'


def test_presence_reports_offline() -> None:
    data = widget_data(console_online=2, console_max=20, state='offline')
    assert presence_text(data) == 'Minecraft｜サーバーOFFLINE'
