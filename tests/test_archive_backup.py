from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from libs.JBLibs import archive_backup


class DirectoryBackupTests(unittest.TestCase):
    def test_creates_timestamped_archive_with_source_directory_as_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "alice"
            destination = base / "backups" / "alice"
            source.mkdir()
            (source / "config.txt").write_text("data", encoding="utf-8")
            timestamp = datetime(2026, 8, 11, 10, 37, 5)

            commands = []

            def fake_run(command, **kwargs):
                commands.append((command, kwargs))
                Path(command[3]).write_bytes(b"fake-archive")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(
                archive_backup.shutil, "which", return_value="/usr/bin/7z"
            ), patch.object(
                archive_backup.subprocess, "run", side_effect=fake_run
            ):
                result = archive_backup.create_directory_backup(
                    source,
                    destination,
                    archive_label="alice",
                    timestamp=timestamp,
                )

            archive = Path(result.path)
            self.assertEqual(
                archive.name,
                "2026-08-11_103705_alice_backup.7z",
            )
            self.assertEqual(result.size_bytes, len(b"fake-archive"))
            self.assertTrue(archive.is_file())
            command, kwargs = commands[0]
            self.assertEqual(command[:3], ["/usr/bin/7z", "a", "-t7z"])
            self.assertEqual(command[4], "alice")
            self.assertEqual(kwargs["cwd"], str(source.parent.resolve()))
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o700)

    def test_existing_timestamped_name_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "alice"
            destination = base / "backups"
            source.mkdir()
            destination.mkdir()
            existing = destination / "2026-08-11_103705_alice_backup.7z"
            existing.write_bytes(b"old")

            def fake_run(command, **kwargs):
                Path(command[3]).write_bytes(b"new")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.object(
                archive_backup.shutil, "which", return_value="/usr/bin/7z"
            ), patch.object(
                archive_backup.subprocess, "run", side_effect=fake_run
            ):
                result = archive_backup.create_directory_backup(
                    source,
                    destination,
                    archive_label="alice",
                    timestamp=datetime(2026, 8, 11, 10, 37, 5),
                )

            self.assertEqual(existing.read_bytes(), b"old")
            self.assertEqual(
                Path(result.path).name,
                "2026-08-11_103705_alice_backup_01.7z",
            )

    def test_rejects_backup_destination_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "alice"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "must not be inside"):
                archive_backup.create_directory_backup(
                    source,
                    source / "backups",
                )

    def test_missing_7z_fails_before_creating_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "alice"
            source.mkdir()
            with patch.object(archive_backup.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "7z"):
                    archive_backup.create_directory_backup(
                        source,
                        Path(tmp) / "backups",
                    )

    def test_backup_stats_are_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sftpusers"
            (root / "alice").mkdir(parents=True)
            (root / "bob").mkdir()
            (root / "alice" / "a.7z").write_bytes(b"1234")
            (root / "bob" / "b.7z").write_bytes(b"123456")
            (root / "bob" / "ignore.txt").write_bytes(b"123456789")

            stats = archive_backup.get_backup_stats(root)

            self.assertEqual(stats.count, 2)
            self.assertEqual(stats.size_bytes, 10)


if __name__ == "__main__":
    unittest.main()
