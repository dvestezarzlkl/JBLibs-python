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


if __name__ == "__main__":
    unittest.main()
