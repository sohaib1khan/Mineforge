"""Extra unit coverage for archive, properties, allowlist, network, sessions."""

from __future__ import annotations

import tarfile
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
import zstandard as zstd
from app.core.config import Settings, clear_settings_cache, get_settings
from app.core.errors import AppError, ForbiddenError, UnauthorizedError
from app.models.user import User
from app.services import allowlist as allowlist_service
from app.services import network as network_service
from app.services import server_props
from app.services import sessions as session_service
from app.services.archive_safety import (
    atomic_replace_dir,
    copy_tree,
    create_tar_zst,
    dir_size,
    extract_tar_zst,
    extract_zip_safe,
    free_disk_bytes,
    read_zip_names,
    verify_tar_zst,
)
from sqlmodel import Session


def test_archive_helpers_and_error_paths(tmp_path: Path) -> None:
    with pytest.raises(AppError, match="Source directory"):
        create_tar_zst(tmp_path / "missing", tmp_path / "x.tar.zst")

    with pytest.raises(AppError, match="Archive not found"):
        verify_tar_zst(tmp_path / "nope.tar.zst")

    empty = tmp_path / "empty.tar.zst"
    cctx = zstd.ZstdCompressor()
    with empty.open("wb") as out, cctx.stream_writer(out) as compressor:
        with tarfile.open(fileobj=compressor, mode="w|"):
            pass
    with pytest.raises(AppError, match="empty"):
        verify_tar_zst(empty)

    world = tmp_path / "W"
    world.mkdir()
    (world / "level.dat").write_bytes(b"ok")
    good = tmp_path / "good.tar.zst"
    create_tar_zst(world, good, arcname="W")
    assert verify_tar_zst(good)

    corrupt = tmp_path / "corrupt.tar.zst"
    corrupt.write_bytes(b"not-zstd")
    with pytest.raises(AppError, match="verification failed"):
        verify_tar_zst(corrupt)

    src = tmp_path / "src"
    dest = tmp_path / "dest"
    backup = tmp_path / "backup"
    src.mkdir()
    (src / "a.txt").write_text("a", encoding="utf-8")
    dest.mkdir()
    (dest / "old.txt").write_text("old", encoding="utf-8")
    atomic_replace_dir(src, dest, backup=backup)
    assert (dest / "a.txt").is_file()
    assert (backup / "old.txt").is_file()

    with pytest.raises(AppError, match="Swap source"):
        atomic_replace_dir(tmp_path / "no-dir", tmp_path / "x")

    src2 = tmp_path / "src2"
    dest2 = tmp_path / "dest2"
    src2.mkdir()
    (src2 / "b.txt").write_text("b", encoding="utf-8")
    dest2.mkdir()
    (dest2 / "c.txt").write_text("c", encoding="utf-8")
    atomic_replace_dir(src2, dest2)
    assert (dest2 / "b.txt").is_file()
    assert not (dest2 / "c.txt").exists()

    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "f.txt").write_text("hello", encoding="utf-8")
    copied = tmp_path / "copied"
    copy_tree(tree, copied)
    assert (copied / "f.txt").read_text(encoding="utf-8") == "hello"
    with pytest.raises(AppError, match="already exists"):
        copy_tree(tree, copied)

    assert dir_size(tree) == 5
    assert dir_size(tmp_path / "missing-size") == 0
    assert free_disk_bytes(tmp_path / "disk") > 0

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pack/manifest.json", "{}")
    assert "pack/manifest.json" in read_zip_names(buf.getvalue())
    with pytest.raises(AppError, match="Unsafe"):
        read_zip_names(_zip_bytes({"../bad.txt": b"x"}))

    with pytest.raises(AppError, match="not empty"):
        extract_zip_safe(tmp_path / "missing.zip", tree)
    with pytest.raises(AppError, match="Zip archive not found"):
        extract_zip_safe(tmp_path / "missing.zip", tmp_path / "zip-out")

    bad_zip = tmp_path / "link.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        zf.writestr(info, b"target")
    with pytest.raises(AppError, match="Symlinks"):
        extract_zip_safe(bad_zip, tmp_path / "link-out")


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_extract_tar_rejects_symlink(tmp_path: Path) -> None:
    archive = tmp_path / "sym.tar.zst"
    cctx = zstd.ZstdCompressor()
    with archive.open("wb") as out, cctx.stream_writer(out) as compressor:
        with tarfile.open(fileobj=compressor, mode="w|") as tar:
            info = tarfile.TarInfo(name="evil")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
    with pytest.raises(AppError, match="Symlinks"):
        verify_tar_zst(archive)
    with pytest.raises(AppError, match="Symlinks"):
        extract_tar_zst(archive, tmp_path / "out-sym")


def test_server_props_validation_catalog_managed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    settings = Settings(data_dir=data, bedrock_uid=0, bedrock_gid=0, _env_file=None)

    with pytest.raises(AppError, match="not found"):
        server_props.read_properties(settings)

    assert server_props.snapshot_properties_text(settings) == ""
    server_props.restore_properties_text(
        settings,
        "server-name=Test\ngamemode=survival\ndifficulty=easy\nlevel-name=Bedrock level\n",
    )
    props = server_props.read_properties(settings)
    assert props["server-name"] == "Test"

    with pytest.raises(AppError, match="true or false"):
        server_props.validate_updates({"allow-cheats": "yes"})
    with pytest.raises(AppError, match="integer"):
        server_props.validate_updates({"max-players": "many"})
    with pytest.raises(AppError, match="one of"):
        server_props.validate_updates({"gamemode": "hardcore"})

    server_props.write_managed(
        settings, {"level-name": "TestWorld", "max-players": "10"}
    )
    again = server_props.read_properties(settings)
    assert again["level-name"] == "TestWorld"
    assert again["max-players"] == "10"

    with pytest.raises(ForbiddenError):
        server_props.write_managed(settings, {"not-managed": "1"})
    with pytest.raises(AppError, match="true or false"):
        server_props.write_managed(settings, {"allow-cheats": "nope"})
    with pytest.raises(AppError, match="integer"):
        server_props.write_managed(settings, {"max-players": "x"})
    with pytest.raises(AppError, match="one of"):
        server_props.write_managed(settings, {"difficulty": "brutal"})

    catalog = server_props.property_catalog()
    keys = {item["key"] for item in catalog}
    assert "server-name" in keys
    assert "level-name" in keys
    assert any(item["editable"] is False for item in catalog)


def test_allowlist_edge_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("MINEFORGE_DATA_DIR", str(data))
    monkeypatch.setenv("MINEFORGE_SECRET_KEY", "test-secret-key-not-real")
    clear_settings_cache()
    settings = get_settings()

    with pytest.raises(AppError, match="Gamertag"):
        allowlist_service.add_allowlist_entry(settings, name="  ")

    allowlist_service.add_allowlist_entry(
        settings, name="player_one", xuid="2535400000000001"
    )
    listed = allowlist_service.list_allowlist(settings)
    assert listed[0].get("xuid") == "2535400000000001"

    bad = data / "allowlist.json"
    bad.write_text("{not-json", encoding="utf-8")
    with pytest.raises(AppError, match="Invalid JSON"):
        allowlist_service.list_allowlist(settings)
    bad.write_text('{"name": "x"}', encoding="utf-8")
    with pytest.raises(AppError, match="JSON array"):
        allowlist_service.list_allowlist(settings)
    bad.write_text("[]\n", encoding="utf-8")

    with pytest.raises(AppError, match="permission must"):
        allowlist_service.set_permission(
            settings, xuid="1", permission="god", name="player_one"
        )
    with pytest.raises(AppError, match="xuid"):
        allowlist_service.set_permission(settings, xuid="  ", permission="member")

    allowlist_service.set_permission(
        settings, xuid="2535400000000001", permission="member", name="player_one"
    )
    allowlist_service.set_permission(
        settings, xuid="2535400000000001", permission="operator"
    )
    ops = allowlist_service.list_ops(settings)
    assert ops[0]["permission"] == "operator"
    clear_settings_cache()


def test_network_helpers_edge_cases(tmp_path: Path) -> None:
    with pytest.raises(AppError, match="loopback"):
        network_service.validate_ipv4("127.0.0.1")
    with pytest.raises(AppError, match="UDP port range"):
        network_service.build_udp_ports("203.0.113.10", udp_range="bad")

    assert network_service.parse_advertised_ip(None) is None
    assert (
        network_service.parse_advertised_ip("not-an-ip:19140-19155:19140-19155") is None
    )

    checklist = network_service.forwarding_checklist(
        server_port="19133",
        server_udp_ports="203.0.113.10:19140-19150:19140-19150",
    )
    assert checklist[0]["title"] == "TCP 19133"
    assert "19140-19150" in checklist[1]["title"]

    settings = Settings(
        data_dir=tmp_path / "nodata",
        secret_key="test-secret-key-not-real",
        public_ip_lookup_url="",
        _env_file=None,
    )
    status = network_service.network_status(settings)
    assert status["server_port"] == "19132"
    assert status["advertised_public_ip"] is None

    with pytest.raises(AppError, match="not configured"):
        network_service.lookup_public_ip(settings)


def test_session_require_and_expired(admin_user: User, db_session: Session) -> None:
    settings = get_settings()
    with pytest.raises(UnauthorizedError):
        session_service.require_session(db_session, None)
    with pytest.raises(UnauthorizedError):
        session_service.require_session(db_session, "missing-token")
    assert session_service.get_session_by_token(db_session, "") is None
    session_service.destroy_session(db_session, None)

    row, raw = session_service.create_session(db_session, settings, admin_user)
    db_session.commit()
    auth, user = session_service.require_session(db_session, raw)
    assert auth.id == row.id
    assert user.id == admin_user.id

    # Expire the session and ensure lookup deletes it.
    row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(row)
    db_session.commit()
    assert session_service.get_session_by_token(db_session, raw) is None
