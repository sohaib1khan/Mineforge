"""Safe archive creation and extraction (zip-bomb / path-escape protection)."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import tarfile
import zipfile
from pathlib import Path

import zstandard as zstd

from app.core.errors import AppError

MAX_ENTRIES = 50_000
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024  # 8 GiB


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return the hex SHA-256 of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def create_tar_zst(source_dir: Path, dest: Path, *, arcname: str | None = None) -> int:
    """Create a `.tar.zst` archive of source_dir. Returns archive size in bytes.

    Raises:
        AppError: if source is missing or archive write fails.
    """

    if not source_dir.is_dir():
        raise AppError(f"Source directory not found: {source_dir}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    name = arcname if arcname is not None else source_dir.name
    cctx = zstd.ZstdCompressor(level=3)
    try:
        with dest.open("wb") as out, cctx.stream_writer(out) as compressor:
            with tarfile.open(fileobj=compressor, mode="w|") as tar:
                tar.add(str(source_dir), arcname=name)
    except OSError as exc:
        if dest.exists():
            dest.unlink(missing_ok=True)
        raise AppError(f"Failed to create archive: {exc}") from exc
    return dest.stat().st_size


def verify_tar_zst(path: Path) -> list[str]:
    """List members of a `.tar.zst` archive (verification).

    Raises:
        AppError: if the archive is corrupt or exceeds safety limits.
    """

    if not path.is_file():
        raise AppError("Archive not found")
    names: list[str] = []
    total = 0
    dctx = zstd.ZstdDecompressor()
    try:
        with path.open("rb") as raw, dctx.stream_reader(raw) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                for member in tar:
                    _validate_tar_member(member)
                    names.append(member.name)
                    if member.isfile():
                        total += max(member.size, 0)
                    if len(names) > MAX_ENTRIES:
                        raise AppError("Archive has too many entries")
                    if total > MAX_UNCOMPRESSED_BYTES:
                        raise AppError("Archive uncompressed size exceeds limit")
    except (OSError, zstd.ZstdError, tarfile.TarError) as exc:
        raise AppError(f"Archive verification failed: {exc}") from exc
    if not names:
        raise AppError("Archive is empty")
    return names


def extract_tar_zst(archive: Path, dest_dir: Path) -> Path:
    """Safely extract a `.tar.zst` into dest_dir (must not exist or be empty).

    Returns the top-level extracted directory (or dest_dir if flat).

    Raises:
        AppError: on unsafe paths, limits exceeded, or I/O errors.
    """

    dest_dir.mkdir(parents=True, exist_ok=True)
    if any(dest_dir.iterdir()):
        raise AppError("Extraction destination is not empty")

    dctx = zstd.ZstdDecompressor()
    total = 0
    count = 0
    try:
        with archive.open("rb") as raw, dctx.stream_reader(raw) as reader:
            with tarfile.open(fileobj=reader, mode="r|") as tar:
                for member in tar:
                    _validate_tar_member(member)
                    count += 1
                    if count > MAX_ENTRIES:
                        raise AppError("Archive has too many entries")
                    if member.isfile():
                        total += max(member.size, 0)
                        if total > MAX_UNCOMPRESSED_BYTES:
                            raise AppError("Archive uncompressed size exceeds limit")
                    target = _safe_join(dest_dir, member.name)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source = tar.extractfile(member)
                        if source is None:
                            raise AppError(f"Could not extract {member.name}")
                        with source, target.open("wb") as out:
                            shutil.copyfileobj(source, out)
                    else:
                        raise AppError(f"Unsupported archive entry type: {member.name}")
    except AppError:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise
    except (OSError, zstd.ZstdError, tarfile.TarError) as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise AppError(f"Archive extraction failed: {exc}") from exc

    children = list(dest_dir.iterdir())
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return dest_dir


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    name = member.name.replace("\\", "/")
    if name.startswith("/") or name.startswith("..") or "/../" in f"/{name}/":
        raise AppError(f"Unsafe archive path: {member.name}")
    if member.issym() or member.islnk():
        raise AppError(f"Symlinks are not allowed: {member.name}")


def _safe_join(root: Path, relative: str) -> Path:
    cleaned = relative.replace("\\", "/").lstrip("/")
    candidate = (root / cleaned).resolve()
    root_resolved = root.resolve()
    if not candidate.is_relative_to(root_resolved):
        raise AppError(f"Unsafe archive path: {relative}")
    return candidate


def atomic_replace_dir(src: Path, dest: Path, *, backup: Path | None = None) -> None:
    """Atomically swap dest with src. Optionally move old dest to backup.

    Raises:
        AppError: on filesystem failures.
    """

    if not src.is_dir():
        raise AppError("Swap source is not a directory")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if dest.exists():
            if backup is not None:
                if backup.exists():
                    shutil.rmtree(backup)
                dest.replace(backup)
            else:
                tmp_old = dest.with_name(dest.name + ".mf-old")
                if tmp_old.exists():
                    shutil.rmtree(tmp_old)
                dest.replace(tmp_old)
                shutil.rmtree(tmp_old, ignore_errors=True)
        src.replace(dest)
    except OSError as exc:
        raise AppError(f"Failed to swap directories: {exc}") from exc


def copy_tree(src: Path, dest: Path) -> None:
    """Copy a directory tree. Dest must not exist."""

    if dest.exists():
        raise AppError("Copy destination already exists")
    try:
        shutil.copytree(src, dest, symlinks=False)
    except OSError as exc:
        raise AppError(f"Failed to copy directory: {exc}") from exc


def dir_size(path: Path) -> int:
    """Return total size of files under path."""

    total = 0
    if not path.exists():
        return 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def read_zip_names(data: bytes) -> list[str]:
    """List names inside a zip (used by pack upload later). Rejects unsafe entries."""

    names: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                raise AppError(f"Unsafe zip path: {info.filename}")
            names.append(info.filename)
    return names


def extract_zip_safe(archive: Path, dest_dir: Path) -> Path:
    """Safely extract a zip (e.g. `.mcworld`) into an empty dest_dir.

    Returns dest_dir. Rejects absolute paths, `..`, symlinks, and zip bombs.

    Raises:
        AppError: on unsafe entries, limits, or I/O errors.
    """

    dest_dir.mkdir(parents=True, exist_ok=True)
    if any(dest_dir.iterdir()):
        raise AppError("Extraction destination is not empty")
    if not archive.is_file():
        raise AppError("Zip archive not found")

    total = 0
    count = 0
    try:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if not name or name.endswith("/"):
                    # directory entry
                    if name.startswith("/") or ".." in name.split("/"):
                        raise AppError(f"Unsafe zip path: {info.filename}")
                    continue
                if name.startswith("/") or ".." in name.split("/"):
                    raise AppError(f"Unsafe zip path: {info.filename}")
                if info.is_dir():
                    continue
                # ZipInfo external_attr high bits can mark symlinks on Unix
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise AppError(f"Symlinks are not allowed: {info.filename}")
                count += 1
                if count > MAX_ENTRIES:
                    raise AppError("Archive has too many entries")
                size = info.file_size
                total += max(size, 0)
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise AppError("Archive uncompressed size exceeds limit")
                target = _safe_join(dest_dir, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
    except AppError:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise AppError(f"Zip extraction failed: {exc}") from exc
    return dest_dir


def free_disk_bytes(path: Path) -> int:
    """Return free bytes on the filesystem containing path."""

    path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(path).free
