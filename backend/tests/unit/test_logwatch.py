"""Log line parsing unit tests (fake gamertags only)."""

from app.services.logwatch import parse_log_line


def test_parse_join_and_leave() -> None:
    join = parse_log_line("Player connected: player_one, xuid: 2535400000000001")
    assert join is not None
    assert join[0] == "join"
    assert join[1]["gamertag"] == "player_one"
    assert join[1]["xuid"] == "2535400000000001"

    leave = parse_log_line(
        "[INFO] Player disconnected: player_one, xuid: 2535400000000001"
    )
    assert leave is not None
    assert leave[0] == "leave"


def test_parse_server_started() -> None:
    assert parse_log_line("Server started.") == ("started", {})
