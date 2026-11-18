"""Unit tests for Docker runtime snapshot parsing."""

from __future__ import annotations

from app.services.docker_client import filter_safe_env, parse_runtime_attrs


def test_filter_safe_env_keeps_bedrock_keys_drops_secrets() -> None:
    env = filter_safe_env(
        [
            "VERSION=1.21.50",
            "LEVEL_NAME=Helixx_World",
            "EULA=TRUE",
            "SOME_PASSWORD=secret",
            "API_TOKEN=nope",
            "MAX_PLAYERS=10",
            "not-an-entry",
        ]
    )
    assert env["VERSION"] == "1.21.50"
    assert env["LEVEL_NAME"] == "Helixx_World"
    assert env["MAX_PLAYERS"] == "10"
    assert "SOME_PASSWORD" not in env
    assert "API_TOKEN" not in env


def test_parse_runtime_attrs_ports_mounts_health() -> None:
    attrs = {
        "Created": "2026-01-01T00:00:00.123456789Z",
        "Platform": "linux",
        "RestartCount": 2,
        "State": {
            "Running": True,
            "Status": "running",
            "Pid": 42,
            "ExitCode": 0,
            "OOMKilled": False,
            "Error": "",
            "StartedAt": "2026-01-01T01:00:00.000000000Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "Health": {"Status": "healthy"},
        },
        "HostConfig": {"RestartPolicy": {"Name": "unless-stopped"}},
        "Config": {
            "Env": [
                "VERSION=1.21.50",
                "LEVEL_NAME=TestWorld",
                "SECRET_KEY=nope",
            ]
        },
        "NetworkSettings": {
            "Ports": {
                "19132/udp": [{"HostIp": "0.0.0.0", "HostPort": "19132"}],
                "19132/tcp": None,
            }
        },
        "Mounts": [
            {
                "Type": "bind",
                "Source": "/home/example/data",
                "Destination": "/data",
                "Mode": "rw",
                "RW": True,
            }
        ],
    }
    snap = parse_runtime_attrs(
        name="bedrock", attrs=attrs, image="itzg/minecraft-bedrock-server:test"
    )
    assert snap.exists is True
    assert snap.running is True
    assert snap.health == "healthy"
    assert snap.pid == 42
    assert snap.restart_count == 2
    assert snap.restart_policy == "unless-stopped"
    assert snap.level_name_env == "TestWorld"
    assert snap.safe_env is not None
    assert "SECRET_KEY" not in snap.safe_env
    assert any(
        p.private == "19132/udp" and p.public == "0.0.0.0:19132"
        for p in snap.ports or []
    )
    assert any(m.destination == "/data" for m in snap.mounts or [])
    # Host source path must not appear on mounts (privacy).
    assert all("example" not in m.destination for m in snap.mounts or [])
