"""Parse Bedrock save query file lists."""

from app.services.backups import parse_save_query_files


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
