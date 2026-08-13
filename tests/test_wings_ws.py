import asyncio

import aiohttp

from app.wings_ws import (
    WingsConsole,
    PLAYER_COUNT_RE,
    _parse_inline_players,
    _parse_player_list_line,
    _parse_player_line,
)


async def _console() -> WingsConsole:
    session = aiohttp.ClientSession()
    console = WingsConsole("https://panel.example.com", "server", "token", session)
    return console


def test_multiline_bedrock_list_output():
    line = "[2026-08-12 17:39:32:529 INFO] There are 1/20 players online:"
    match = PLAYER_COUNT_RE.search(line)
    assert match is not None
    assert match.group(1) == "1"
    assert match.group(2) == "20"

    assert _parse_player_line("shirokuma1101") == "shirokuma1101"


def test_xuid_player_line():
    assert (
        _parse_player_line("akm19gu, xuid: 2535466811555748")
        == "akm19gu"
    )


def test_multiple_xuid_player_lines():
    value = (
        "akm19gu, xuid: 2535466811555748,"
        "KARUMA0618, xuid: 25354884086921547"
    )
    # Inline parser is not intended for the full comma/XUID blob because
    # commas are also separators inside the XUID format. Individual lines
    # are handled by _parse_player_line.
    assert _parse_player_line("KARUMA0618, xuid: 25354884086921547") == "KARUMA0618"


def test_comma_separated_player_list_line():
    assert _parse_player_list_line("akm19gu, Lavender2414") == [
        "akm19gu",
        "Lavender2414",
    ]


def test_player_names_with_spaces_are_parsed():
    assert _parse_player_line("Lavender 2414") == "Lavender 2414"
    assert _parse_player_list_line("akm19gu, Lavender 2414") == [
        "akm19gu",
        "Lavender 2414",
    ]


def test_alt_count_format():
    from app.wings_ws import PLAYER_COUNT_ALT_RE
    line = "There are 2 of a max of 20 players online:"
    match = PLAYER_COUNT_ALT_RE.search(line)
    assert match is not None
    assert match.group(1) == "2"
    assert match.group(2) == "20"


def test_list_output_replaces_previous_snapshot_and_ignores_command_echo():
    async def scenario():
        console = await _console()
        try:
            await console._process_console(
                "[2026-08-12 17:39:32:529 INFO] There are 1/20 players online:\n"
                "shirokuma1101\n"
                "list"
            )
            first = await console.snapshot()
            assert first.online_players == 1
            assert first.max_players == 20
            assert first.players == ["shirokuma1101"]
            assert first.logs == []

            await console._process_console("There are 0/20 players online:\nlist")
            second = await console.snapshot()
            assert second.online_players == 0
            assert second.players == []
        finally:
            await console.session.close()

    asyncio.run(scenario())


def test_list_output_is_hidden_but_normal_console_logs_are_kept():
    async def scenario():
        console = await _console()
        try:
            await console._process_console(
                "[INFO] Server started\n"
                "There are 1/20 players online:\n"
                "shirokuma1101\n"
                "list\n"
                "[INFO] Saving world"
            )
            snapshot = await console.snapshot()
            assert snapshot.players == ["shirokuma1101"]
            assert snapshot.logs == ["[INFO] Server started", "[INFO] Saving world"]
        finally:
            await console.session.close()

    asyncio.run(scenario())


def test_comma_separated_list_output_updates_widget_players():
    async def scenario():
        console = await _console()
        try:
            await console._process_console(
                "list\n"
                "[2026-08-13 12:46:02:598 INFO] There are 2/20 players online:\n"
                "akm19gu, Lavender2414"
            )
            snapshot = await console.snapshot()
            assert snapshot.online_players == 2
            assert snapshot.max_players == 20
            assert snapshot.players == ["akm19gu", "Lavender2414"]
        finally:
            await console.session.close()

    asyncio.run(scenario())


def test_xuid_lines_are_parsed_only_as_list_continuations():
    async def scenario():
        console = await _console()
        try:
            await console._process_console(
                "There are 4/20 players online:\n"
                "akm19gu, xuid: 2535466811555748\n"
                "KARUMA0618, xuid: 2535434880621547\n"
                "Min7946, xuid: 2535452646650154\n"
                "yuhii140122, xuid: 2535428870141"
            )
            snapshot = await console.snapshot()
            assert snapshot.players == [
                "akm19gu",
                "KARUMA0618",
                "Min7946",
                "yuhii140122",
            ]

            await console._process_console("akm19gu, xuid: 2535466811555748")
            assert (await console.snapshot()).players == snapshot.players
        finally:
            await console.session.close()

    asyncio.run(scenario())
