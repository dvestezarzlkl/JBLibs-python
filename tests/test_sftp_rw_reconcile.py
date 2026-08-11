from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


ROOT = Path(__file__).resolve().parents[1]

if "libs" not in sys.modules:
    libs_pkg = types.ModuleType("libs")
    libs_pkg.__path__ = []
    sys.modules["libs"] = libs_pkg

if "libs.JBLibs" not in sys.modules:
    jblibs_pkg = types.ModuleType("libs.JBLibs")
    jblibs_pkg.__path__ = [str(ROOT)]
    jblibs_pkg.__package__ = "libs.JBLibs"
    sys.modules["libs.JBLibs"] = jblibs_pkg

samba_module = importlib.import_module("libs.JBLibs.sftp.sambaPoint")
mounts_module = importlib.import_module("libs.JBLibs.sftp.mounts")
parser_module = importlib.import_module("libs.JBLibs.sftp.parser")
user_module = importlib.import_module("libs.JBLibs.sftp.user")


class SambaReadOnlyStateTests(unittest.TestCase):
    def test_reads_managed_share_access_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            conf = Path(tmp) / "smb.conf"
            conf.write_text(
                "[global]\nworkgroup = TEST\n\n"
                "[sftp_mount_alice_docs]\n"
                "path = /srv/docs\n"
                "read only = yes\n\n"
                "[other]\nread only = no\n",
                encoding="utf-8",
            )
            with patch.object(samba_module, "SMB_CFG_DIR", tmp):
                self.assertTrue(
                    samba_module.smbHelp.getSambaShareReadOnly("docs", "alice")
                )

            conf.write_text(
                "[sftp_mount_alice_docs]\nread only = no\n",
                encoding="utf-8",
            )
            with patch.object(samba_module, "SMB_CFG_DIR", tmp):
                self.assertFalse(
                    samba_module.smbHelp.getSambaShareReadOnly("docs", "alice")
                )

    def test_missing_access_mode_requests_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "smb.conf").write_text(
                "[sftp_mount_alice_docs]\npath = /srv/docs\n",
                encoding="utf-8",
            )
            with patch.object(samba_module, "SMB_CFG_DIR", tmp):
                self.assertIsNone(
                    samba_module.smbHelp.getSambaShareReadOnly("docs", "alice")
                )


class SambaBatchTransactionTests(unittest.TestCase):
    def setUp(self):
        samba_module.smbHelp._batchDepth = 0
        samba_module.smbHelp.requireSambaRestart = False
        samba_module.smbHelp.toMount.clear()
        samba_module.smbHelp.toRemove.clear()
        samba_module.smbHelp.toCloseShares.clear()

    def tearDown(self):
        samba_module.smbHelp._batchDepth = 0
        samba_module.smbHelp.requireSambaRestart = False
        samba_module.smbHelp.toMount.clear()
        samba_module.smbHelp.toRemove.clear()
        samba_module.smbHelp.toCloseShares.clear()

    def test_post_remove_does_not_cleanup_inside_active_batch(self):
        samba_module.smbHelp._batchDepth = 1
        samba_module.smbHelp.toRemove.append("/jail/alice/docs")
        with patch.object(samba_module.smbHelp, "removeQueuedMountpointDirectories") as cleanup, patch.object(samba_module.smbHelp, "finalizeMountpointChanges") as finalize:
            self.assertTrue(samba_module.postRemoveAllMountpoints())
        cleanup.assert_not_called()
        finalize.assert_not_called()
        self.assertEqual(samba_module.smbHelp.toRemove, ["/jail/alice/docs"])

    def test_finalize_unmounts_before_cleanup_and_preserves_final_targets(self):
        events = []
        configured = [("//127.0.0.1/sftp_mount_alice_docs", "/jail/alice/docs")]
        samba_module.smbHelp.requireSambaRestart = True
        samba_module.smbHelp.toRemove.extend(["/jail/alice/docs", "/jail/alice/obsolete"])
        def cleanup(preserve):
            events.append(("cleanup", set(preserve)))
            return True
        with patch.object(samba_module.smbHelp, "getConfiguredManagedCIFS", return_value=configured), patch.object(samba_module.smbHelp, "unmountAllManagedCIFS", side_effect=lambda: events.append(("unmount", None))), patch.object(samba_module.smbHelp, "removeQueuedMountpointDirectories", side_effect=cleanup), patch.object(samba_module.smbHelp, "prepareConfiguredMountpointDirectories", side_effect=lambda targets: events.append(("prepare", set(targets)))), patch.object(samba_module, "reloadSambaService", side_effect=lambda: events.append(("samba", None)) or True), patch.object(samba_module.smbHelp, "closeQueuedSambaShares", side_effect=lambda: events.append(("close", None)) or True), patch.object(samba_module.smbHelp, "reloadSystemdDaemon", side_effect=lambda: events.append(("systemd", None)) or True), patch.object(samba_module.smbHelp, "mountConfiguredManagedCIFS", side_effect=lambda mounts: events.append(("mount", mounts))):
            self.assertTrue(samba_module.smbHelp.finalizeMountpointChanges())
        self.assertEqual(events, [("unmount", None), ("cleanup", {"/jail/alice/docs"}), ("prepare", {"/jail/alice/docs"}), ("samba", None), ("close", None), ("systemd", None), ("mount", configured)])

    def test_remove_queue_keeps_target_recreated_in_same_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep = Path(tmp) / "keep"
            obsolete = Path(tmp) / "obsolete"
            keep.mkdir()
            obsolete.mkdir()
            samba_module.smbHelp.toRemove.extend([str(keep), str(obsolete)])
            self.assertTrue(samba_module.smbHelp.removeQueuedMountpointDirectories({str(keep)}))
            self.assertTrue(keep.is_dir())
            self.assertFalse(obsolete.exists())
            self.assertEqual(samba_module.smbHelp.toRemove, [])

    def test_remove_share_defers_physical_unmount_inside_batch(self):
        mp = types.SimpleNamespace(mountName="docs", mountPath="/jail/alice/docs")
        samba_module.smbHelp._batchDepth = 1
        with patch.object(samba_module.smbHelp, "isMounted", return_value=True) as is_mounted, patch.object(samba_module.smbHelp, "removeFstabCIFScfg", return_value=True), patch.object(samba_module.smbHelp, "removeSambaSharePoint"), patch.object(samba_module.subprocess, "run") as run:
            samba_module.removeSharePoint("alice", mp)
        is_mounted.assert_not_called()
        run.assert_not_called()
        self.assertIn("/jail/alice/docs", samba_module.smbHelp.toRemove)

    def test_ensure_mountpoint_checks_mounted_state_with_sftp_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            jail = Path(tmp) / "jail"
            source = Path(tmp) / "source"
            jail.mkdir()
            source.mkdir()
            mp = samba_module.sftpUserMountpoint(jailPath=str(jail), line="docs", val=str(source), sambaVault=True, rw=True)
            with patch.object(mp, "forUser", return_value=("source-owner", 1000)), patch.object(mp, "forGroup", return_value=("source-group", 1000)), patch.object(samba_module, "initEnsureSamba"), patch.object(samba_module.os, "chown"), patch.object(samba_module.os, "chmod"), patch.object(samba_module.smbHelp, "ensureSambaSharePoint"), patch.object(samba_module.smbHelp, "ensureFstabCIFScfg", return_value=True), patch.object(samba_module.smbHelp, "isMounted", return_value=True) as is_mounted:
                samba_module.ensureMountpoint("alice", mp)
            is_mounted.assert_called_once_with("docs", "alice")


    def test_changed_share_is_closed_by_name_and_not_globally(self):
        samba_module.smbHelp.toCloseShares.add("sftp_mount_alice_docs")
        proc = types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        with patch.object(samba_module.subprocess, "run", return_value=proc) as run:
            self.assertTrue(samba_module.smbHelp.closeQueuedSambaShares())
        run.assert_called_once_with(
            ["smbcontrol", "smbd", "close-share", "sftp_mount_alice_docs"],
            stdout=samba_module.subprocess.PIPE,
            stderr=samba_module.subprocess.PIPE,
        )

    def test_nonempty_unmounted_target_is_never_hidden_by_remount(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "docs"
            target.mkdir()
            (target / "stale.txt").write_text("stale", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                samba_module.smbHelp.prepareConfiguredMountpointDirectories({str(target)})

    def test_close_share_failure_falls_back_to_full_samba_restart(self):
        configured = [("//127.0.0.1/sftp_mount_alice_docs", "/jail/alice/docs")]
        samba_module.smbHelp.requireSambaRestart = True
        with patch.object(samba_module.smbHelp, "getConfiguredManagedCIFS", return_value=configured), patch.object(samba_module.smbHelp, "unmountAllManagedCIFS"), patch.object(samba_module.smbHelp, "removeQueuedMountpointDirectories", return_value=True), patch.object(samba_module.smbHelp, "prepareConfiguredMountpointDirectories"), patch.object(samba_module, "reloadSambaService", return_value=True), patch.object(samba_module.smbHelp, "closeQueuedSambaShares", return_value=False), patch.object(samba_module, "restartSambaService", return_value=True) as restart, patch.object(samba_module.smbHelp, "reloadSystemdDaemon", return_value=True), patch.object(samba_module.smbHelp, "mountConfiguredManagedCIFS"):
            self.assertTrue(samba_module.smbHelp.finalizeMountpointChanges())
        restart.assert_called_once_with()


class SftpUserCleanupTests(unittest.TestCase):
    def test_backup_target_cleanup_removes_empty_and_preserves_nonempty(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty_target = Path(tmp) / "empty"
            dirty_target = Path(tmp) / "dirty"
            empty_target.mkdir()
            dirty_target.mkdir()
            stale = dirty_target / "stale.txt"
            stale.write_text("stale", encoding="utf-8")

            mounts_module.mountpointsManager._cleanupPreservedTargetDirs([
                str(empty_target),
                str(dirty_target),
            ])

            self.assertFalse(empty_target.exists())
            self.assertTrue(dirty_target.is_dir())
            self.assertTrue(stale.is_file())

    def _fake_user(self, home: str):
        user = object.__new__(user_module.sftpUserMng)
        user.ok = True
        user.username = "alice"
        user.homeDir = home
        return user

    def test_confirmed_nonempty_jail_is_removed_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            jail = Path(tmp) / "__sftp__"
            stale_dir = jail / "docs"
            stale_dir.mkdir(parents=True)
            (stale_dir / "stale.txt").write_text("stale", encoding="utf-8")
            user = self._fake_user(tmp)
            with patch.object(user_module.ssh, "ensureJail", return_value=str(jail)), patch.object(user_module, "confirm", return_value=True), patch.object(user, "_sftpUserMng__jailHasMountedPaths", return_value=False):
                self.assertTrue(user._sftpUserMng__delete_jail(queryNoEmpty=True))
            self.assertFalse(jail.exists())

    def test_jail_mount_guard_detects_bind_mount_from_mountinfo(self):
        user = self._fake_user("/home_sftp_users/alice")
        mountinfo = (
            "36 25 0:32 / / rw,relatime - ext4 /dev/root rw\n"
            "48 36 0:32 /srv/docs /home_sftp_users/alice/__sftp__/docs rw,relatime - ext4 /dev/root rw\n"
        )
        with patch("builtins.open", mock_open(read_data=mountinfo)):
            self.assertTrue(
                user._sftpUserMng__jailHasMountedPaths("/home_sftp_users/alice/__sftp__")
            )

    def test_jail_mount_guard_fails_closed_when_mountinfo_unreadable(self):
        user = self._fake_user("/home_sftp_users/alice")
        with patch("builtins.open", side_effect=OSError("mountinfo unavailable")):
            self.assertTrue(
                user._sftpUserMng__jailHasMountedPaths("/home_sftp_users/alice/__sftp__")
            )

    def test_recursive_jail_cleanup_refuses_active_mounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            jail = Path(tmp) / "__sftp__"
            stale_dir = jail / "docs"
            stale_dir.mkdir(parents=True)
            (stale_dir / "stale.txt").write_text("stale", encoding="utf-8")
            user = self._fake_user(tmp)
            with patch.object(user_module.ssh, "ensureJail", return_value=str(jail)), patch.object(user_module, "confirm", return_value=True), patch.object(user, "_sftpUserMng__jailHasMountedPaths", return_value=True):
                self.assertFalse(user._sftpUserMng__delete_jail(queryNoEmpty=True))
            self.assertTrue(jail.exists())
            self.assertTrue((stale_dir / "stale.txt").exists())

    def test_delete_user_backups_full_home_after_mount_detach(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "alice"
            jail = home / "__sftp__"
            jail.mkdir(parents=True)
            (jail / "stale.txt").write_text("stale", encoding="utf-8")
            user = self._fake_user(str(home))
            user.mountpointManager = MagicMock()
            user.mountpointManager.umount_will_be_ok.return_value = True
            user.certificateManager = MagicMock()
            user.certificateManager.certificates = []
            events = []

            def backup_side_effect(source, destination, **kwargs):
                events.append("backup")
                self.assertEqual(source, str(home))
                self.assertEqual(destination, "/var/backups/sftpusers/alice")
                return types.SimpleNamespace(path="/var/backups/sftpusers/alice/test.7z", size_bytes=123)

            def jail_side_effect(queryNoEmpty=True):
                events.append("jail")
                self.assertFalse(queryNoEmpty)
                return True

            with patch.object(user, "_sftpUserMng__killUserProcesses"), patch.object(
                user, "_sftpUserMng__jailHasMountedPaths", return_value=False
            ) as mount_guard, patch.object(
                user_module, "create_directory_backup", side_effect=backup_side_effect
            ), patch.object(
                user, "_sftpUserMng__delete_jail", side_effect=jail_side_effect
            ), patch.object(
                user, "_sftpUserMng__cleanupSSHFiles"
            ), patch.object(
                user_module, "remove_sshd_config"
            ), patch.object(
                user_module, "deleteUserFromGroup"
            ), patch.object(
                user_module.pwd, "getpwnam", return_value=types.SimpleNamespace(pw_uid=1000, pw_gid=1000)
            ), patch.object(
                user_module.os, "chown"
            ), patch.object(
                user_module.os, "chmod"
            ), patch.object(
                user_module.os, "rmdir"
            ), patch.object(
                user_module.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)
            ):
                user.delete_user(backupRoot="/var/backups/sftpusers")

            user.mountpointManager.deleteMountpoint.assert_called_once_with(
                None, preserveTargetDirs=True
            )
            mount_guard.assert_called_once_with(str(home))
            self.assertEqual(events, ["backup", "jail"])


class ParserRwReconcileTests(unittest.TestCase):
    class ExistingMount:
        mountName = "docs"

        def __init__(self, path: str):
            self.realPath = path

        def isSambaVault(self):
            return True

    class FakeMountManager:
        def __init__(self, existing):
            self.existing = [existing]
            self.deleted = []
            self.ensured = []

        def getMountpoints(self):
            return list(self.existing)

        def deleteMountpoint(self, name):
            self.deleted.append(name)

        def ensure_samba_mountpoint(self, name, path, my=False, rw=True):
            self.ensured.append((name, path, my, rw))

        def ensure_mountpoint(self, name, path):
            raise AssertionError("bind mount path should not be used")

        def ensureMountPointUserGroups(self):
            return []

    class FakeCertificateManager:
        def ensure_ssh_key(self, cert):
            raise AssertionError("no certificates expected")

    def _run_apply(self, current_read_only: bool | None, desired_rw: bool):
        with tempfile.TemporaryDirectory() as tmp:
            real_path = Path(tmp) / "docs"
            real_path.mkdir()
            cfg_path = Path(tmp) / "config.jsonc"
            cfg_path.write_text(
                json.dumps(
                    {
                        "users": [
                            {
                                "sftpuser": "alice",
                                "sambaVault": True,
                                "sftpmounts": {"docs": str(real_path)},
                                "pointsSet": {"docs": {"rw": desired_rw}},
                                "sftpcerts": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            existing = self.ExistingMount(str(real_path))
            manager = self.FakeMountManager(existing)
            fake_user = types.SimpleNamespace(
                username="alice",
                ok=True,
                mountpointManager=manager,
                certificateManager=self.FakeCertificateManager(),
            )

            class FakeUserManager:
                @staticmethod
                def user_exists(username):
                    return True

                def __new__(cls, username):
                    return fake_user

            with (
                patch.object(parser_module, "check_config_exists", return_value=(True, str(cfg_path))),
                patch.object(parser_module, "sftpUserMng", FakeUserManager),
                patch.object(parser_module.smb.smbHelp, "beginBatch"),
                patch.object(parser_module.smb.smbHelp, "endBatch", return_value=True),
                patch.object(parser_module.smb.smbHelp, "getSambaShareReadOnly", return_value=current_read_only),
                patch.object(parser_module.smb, "postEnsureAllMountpoints", return_value=True),
                patch.object(parser_module.ssh, "ensureJail", return_value=str(Path(tmp) / "jail")),
            ):
                result = parser_module.createUserFromJson(
                    cfg=json.loads(cfg_path.read_text(encoding="utf-8"))
                )

            self.assertIsNotNone(result)
            self.assertEqual(manager.ensured, [("docs", str(real_path), True, desired_rw)])
            return manager.deleted

    def test_same_path_rw_to_ro_is_reconciled(self):
        self.assertEqual(self._run_apply(current_read_only=False, desired_rw=False), ["docs"])

    def test_same_path_ro_to_rw_is_reconciled(self):
        self.assertEqual(self._run_apply(current_read_only=True, desired_rw=True), ["docs"])

    def test_same_access_mode_does_not_recreate(self):
        self.assertEqual(self._run_apply(current_read_only=True, desired_rw=False), [])
        self.assertEqual(self._run_apply(current_read_only=False, desired_rw=True), [])

    def test_missing_managed_samba_mode_is_self_healed(self):
        self.assertEqual(self._run_apply(current_read_only=None, desired_rw=True), ["docs"])

    def test_processing_error_is_returned_to_caller(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_path = Path(tmp) / "docs"
            real_path.mkdir()
            cfg = {
                "users": [
                    {
                        "sftpuser": "alice",
                        "sambaVault": True,
                        "sftpmounts": {"docs": str(real_path)},
                        "pointsSet": {"docs": {"rw": True}},
                        "sftpcerts": [],
                    }
                ]
            }

            existing = self.ExistingMount(str(real_path))

            class FailingMountManager(self.FakeMountManager):
                def deleteMountpoint(self, name):
                    raise RuntimeError("synthetic reconcile failure")

            manager = FailingMountManager(existing)
            fake_user = types.SimpleNamespace(
                username="alice",
                ok=True,
                mountpointManager=manager,
                certificateManager=self.FakeCertificateManager(),
            )

            class FakeUserManager:
                @staticmethod
                def user_exists(username):
                    return True

                def __new__(cls, username):
                    return fake_user

            errors = []
            with (
                patch.object(parser_module, "sftpUserMng", FakeUserManager),
                patch.object(parser_module.smb.smbHelp, "beginBatch"),
                patch.object(parser_module.smb.smbHelp, "endBatch", return_value=True),
                patch.object(parser_module.smb.smbHelp, "getSambaShareReadOnly", return_value=True),
                patch.object(parser_module.smb, "postEnsureAllMountpoints", return_value=True),
            ):
                result = parser_module.createUserFromJson(cfg=cfg, errors_out=errors)

            self.assertIsNone(result)
            self.assertTrue(errors)
            self.assertIn("synthetic reconcile failure", errors[-1])


if __name__ == "__main__":
    unittest.main()
