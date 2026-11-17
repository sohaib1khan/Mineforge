"""Parse Bedrock save query file lists."""

from app.services.backups import _file_map_covers_db, parse_save_query_files


def test_parse_save_query_paths_and_sizes() -> None:
    lines = [
        "Saving...",
        "Data saved. Files are now ready to be copied.",
        "worlds/TestWorld/db/000001.ldb:120",
        "worlds/TestWorld/level.dat:40",
        "File,worlds/TestWorld/db/MANIFEST-000002:55",
        "noise",
    ]
    result = parse_save_query_files(lines)
    assert result["worlds/TestWorld/db/000001.ldb"] == 120
    assert result["worlds/TestWorld/level.dat"] == 40
    assert result["worlds/TestWorld/db/MANIFEST-000002"] == 55


def test_parse_save_query_comma_separated_line() -> None:
    """Bedrock emits the full file list as one comma-separated line."""

    lines = [
        "Data saved. Files are now ready to be copied.",
        (
            "worlds/TestWorld/db/000001.ldb:120, worlds/TestWorld/level.dat:40, "
            "worlds/TestWorld/db/MANIFEST-000002:55, worlds/TestWorld/db/CURRENT:16"
        ),
    ]
    result = parse_save_query_files(lines)
    assert result == {
        "worlds/TestWorld/db/000001.ldb": 120,
        "worlds/TestWorld/level.dat": 40,
        "worlds/TestWorld/db/MANIFEST-000002": 55,
        "worlds/TestWorld/db/CURRENT": 16,
    }
    assert _file_map_covers_db(result, "TestWorld")


def test_parse_save_query_world_relative_paths() -> None:
    lines = [
        "Data saved. Files are now ready to be copied.",
        "TestWorld/db/000966.ldb:37747, TestWorld/db/CURRENT:16, TestWorld/level.dat:99",
    ]
    result = parse_save_query_files(lines)
    assert result["TestWorld/db/000966.ldb"] == 37747
    assert result["TestWorld/level.dat"] == 99
    assert _file_map_covers_db(result, "TestWorld")


def test_parse_save_query_paths_with_spaces() -> None:
    lines = [
        "Data saved. Files are now ready to be copied.",
        (
            "Helixx World/db/MANIFEST-001386:10694, Helixx World/db/CURRENT:16, "
            "Helixx World/level.dat:3054"
        ),
    ]
    result = parse_save_query_files(lines)
    assert result["Helixx World/db/MANIFEST-001386"] == 10694
    assert result["Helixx World/level.dat"] == 3054
    assert _file_map_covers_db(result, "Helixx World")
