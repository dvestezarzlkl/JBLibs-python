from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
parser_module = importlib.import_module("libs.JBLibs.sftp.parser")


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

    def tearDown(self):
        samba_module.smbHelp._batchDepth = 0
        samba_module.smbHelp.requireSambaRestart = False
        samba_module.smbHelp.toMount.clear()
        samba_module.smbHelp.toRemove.clear()

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
        with patch.object(samba_module.smbHelp, "getConfiguredManagedCIFS", return_value=configured), patch.object(samba_module.smbHelp, "unmountAllManagedCIFS", side_effect=lambda: events.append(("unmount", None))), patch.object(samba_module.smbHelp, "removeQueuedMountpointDirectories", side_effect=cleanup), patch.object(samba_module, "reloadSambaService", side_effect=lambda: events.append(("samba", None)) or True), patch.object(samba_module.smbHelp, "reloadSystemdDaemon", side_effect=lambda: events.append(("systemd", None)) or True), patch.object(samba_module.smbHelp, "mountConfiguredManagedCIFS", side_effect=lambda mounts: events.append(("mount", mounts))):
            self.assertTrue(samba_module.smbHelp.finalizeMountpointChanges())
        self.assertEqual(events, [("unmount", None), ("cleanup", {"/jail/alice/docs"}), ("samba", None), ("systemd", None), ("mount", configured)])

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
