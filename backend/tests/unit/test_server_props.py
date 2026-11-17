"""server.properties whitelist and persistence tests."""

from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.services import server_props


def test_write_whitelisted_property_survives_reread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    props = data / "server.properties"
    props.write_text(
        "\n".join(
            [
                "server-name=TestWorld",
                "gamemode=survival",
                "difficulty=easy",
                "level-name=Bedrock level",
                "allow-cheats=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    settings = Settings(
        data_dir=data,
        bedrock_uid=0,
        bedrock_gid=0,
        _env_file=None,
    )

    server_props.write_properties(
        settings, {"difficulty": "hard", "allow-cheats": "true"}
    )
    # Simulate container restart: only the file on disk matters.
    again = server_props.read_properties(settings)
    assert again["difficulty"] == "hard"
    assert again["allow-cheats"] == "true"
    assert again["level-name"] == "Bedrock level"
    assert again["server-name"] == "TestWorld"


def test_readonly_and_unknown_keys_rejected(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "server.properties").write_text("server-name=Test\n", encoding="utf-8")
    settings = Settings(data_dir=data, bedrock_uid=0, bedrock_gid=0, _env_file=None)

    with pytest.raises(ForbiddenError):
        server_props.write_properties(settings, {"level-name": "hacked"})
    with pytest.raises(ForbiddenError):
        server_props.write_properties(settings, {"not-a-real-key": "1"})
