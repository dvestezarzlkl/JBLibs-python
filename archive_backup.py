from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


_SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class DirectoryBackupResult:
    """Result of a successful directory archive operation."""

    path: str
    size_bytes: int


@dataclass(frozen=True)
class BackupStats:
    """Aggregate count and size of backup archives."""

    count: int = 0
    size_bytes: int = 0


def _safe_archive_label(value: str) -> str:
    label = _SAFE_LABEL_RE.sub("_", str(value or "").strip()).strip("._-")
    return label or "backup"


def _prepare_directory(
    path: Path,
    *,
    mode: int,
    owner_uid: int | None,
    owner_gid: int | None,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(mode)
    if owner_uid is not None or owner_gid is not None:
        os.chown(
            path,
            -1 if owner_uid is None else owner_uid,
            -1 if owner_gid is None else owner_gid,
        )


def _unique_archive_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        candidate = directory / f"{stem}_{index:02d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def create_directory_backup(
    source_dir: str | os.PathLike[str],
    destination_dir: str | os.PathLike[str],
    *,
    archive_label: str | None = None,
    timestamp: datetime | None = None,
    directory_mode: int = 0o700,
    archive_mode: int = 0o600,
    owner_uid: int | None = None,
    owner_gid: int | None = None,
) -> DirectoryBackupResult:
    """Create a timestamped 7z archive containing the complete source directory.

    The source directory itself is stored as the top-level archive entry.  The
    archive is first written under a hidden temporary name and is atomically
    renamed only after 7z succeeds, so callers never mistake a partial file for
    a valid backup.

    Args:
        source_dir: Directory to archive.
        destination_dir: Directory where the archive is written.
        archive_label: Optional safe label used in the filename.  Defaults to
            the source directory name.
        timestamp: Optional timestamp, mainly useful for deterministic tests.
        directory_mode: Permissions enforced on the destination directory.
        archive_mode: Permissions enforced on the completed archive.
        owner_uid: Optional UID applied to destination/archive.
        owner_gid: Optional GID applied to destination/archive.

    Returns:
        DirectoryBackupResult with the final archive path and size.

    Raises:
        RuntimeError: if 7z is unavailable or archive creation fails.
        ValueError: if source/destination paths are unsafe for this operation.
    """
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"Backup source is not a directory: {source}")

    destination = Path(destination_dir).expanduser().resolve()
    if destination == source or destination.is_relative_to(source):
        raise ValueError(
            f"Backup destination must not be inside the source directory: {destination}"
        )

    seven_zip = shutil.which("7z")
    if not seven_zip:
        raise RuntimeError("The '7z' command is required to create directory backups.")

    _prepare_directory(
        destination,
        mode=directory_mode,
        owner_uid=owner_uid,
        owner_gid=owner_gid,
    )

    ts = timestamp or datetime.now()
    label = _safe_archive_label(archive_label or source.name)
    filename = ts.strftime(f"%Y-%m-%d_%H%M%S_{label}_backup.7z")
    final_path = _unique_archive_path(destination, filename)
    temp_path = destination / f".{final_path.stem}.{os.getpid()}.partial.7z"

    try:
        proc = subprocess.run(
            [seven_zip, "a", "-t7z", str(temp_path), source.name],
            cwd=str(source.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(
                f"7z backup failed with return code {proc.returncode}"
                + (f": {detail}" if detail else "")
            )
        if not temp_path.is_file():
            raise RuntimeError("7z reported success but did not create the archive file.")

        temp_path.chmod(archive_mode)
        if owner_uid is not None or owner_gid is not None:
            os.chown(
                temp_path,
                -1 if owner_uid is None else owner_uid,
                -1 if owner_gid is None else owner_gid,
            )
        os.replace(temp_path, final_path)
        final_path.chmod(archive_mode)
        if owner_uid is not None or owner_gid is not None:
            os.chown(
                final_path,
                -1 if owner_uid is None else owner_uid,
                -1 if owner_gid is None else owner_gid,
            )
        return DirectoryBackupResult(
            path=str(final_path),
            size_bytes=final_path.stat().st_size,
        )
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def get_backup_stats(
    backup_dir: str | os.PathLike[str],
    *,
    recursive: bool = True,
    suffix: str = ".7z",
) -> BackupStats:
    """Return archive count and total size below ``backup_dir``.

    Missing or unreadable backup roots are treated as an empty set. Individual
    files that disappear during the scan are skipped.
    """
    root = Path(backup_dir).expanduser()
    if not root.is_dir():
        return BackupStats()

    pattern = f"*{suffix}"
    files = root.rglob(pattern) if recursive else root.glob(pattern)
    count = 0
    size_bytes = 0
    try:
        for path in files:
            try:
                if not path.is_file():
                    continue
                size_bytes += path.stat().st_size
                count += 1
            except OSError:
                continue
    except OSError:
        return BackupStats(count=count, size_bytes=size_bytes)
    return BackupStats(count=count, size_bytes=size_bytes)
