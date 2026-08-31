from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from libs.JBLibs.sftp import parser as parser_module
from libs.JBLibs.sftp.mountpoint_templates import resolve_mountpoint_records


class MountpointTemplateResolverTests(unittest.TestCase):
    def test_legacy_local_mount_defaults_to_enabled_rw_and_owned(self):
        cfg = {
            "users": [
                {
                    "sftpuser": "alice",
                    "sftpmounts": {"docs": "/srv/docs"},
                }
            ]
        }
        records, errors = resolve_mountpoint_records(cfg, cfg["users"][0])
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.source, "local")
        self.assertTrue(record.enabled)
        self.assertTrue(record.rw)
        self.assertTrue(record.my)

    def test_template_mount_defaults_to_disabled_readonly_and_not_owned(self):
        cfg = {
            "mountpointTemplates": {
                "web": {
                    "mounts": {
                        "mp_123": {"label": "site", "path": "/var/www/site"},
                    }
                }
            },
            "users": [
                {
                    "sftpuser": "alice",
                    "mountTemplates": ["web"],
                }
            ],
        }
        records, errors = resolve_mountpoint_records(cfg, cfg["users"][0])
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.record_id, "mp_123")
        self.assertEqual(record.template, "web")
        self.assertFalse(record.enabled)
        self.assertFalse(record.rw)
        self.assertFalse(record.my)

    def test_template_override_survives_label_and_path_change_by_stable_id(self):
        user = {
            "sftpuser": "alice",
            "mountTemplates": ["web"],
            "templatePoints": {"mp_123": {"enabled": True, "rw": True}},
        }
        cfg = {
            "mountpointTemplates": {
                "web": {
                    "mounts": {
                        "mp_123": {"label": "renamed", "path": "/srv/new-path"},
                    }
                }
            },
            "users": [user],
        }
        records, errors = resolve_mountpoint_records(cfg, user)
        self.assertEqual(errors, [])
        self.assertEqual(records[0].label, "renamed")
        self.assertEqual(records[0].path, "/srv/new-path")
        self.assertTrue(records[0].enabled)
        self.assertTrue(records[0].rw)

    def test_local_and_template_label_conflict_fails_closed(self):
        user = {
            "sftpuser": "alice",
            "sftpmounts": {"site": "/srv/local"},
            "mountTemplates": ["web"],
        }
        cfg = {
            "mountpointTemplates": {
                "web": {
                    "mounts": {
                        "mp_123": {"label": "site", "path": "/srv/template"},
                    }
                }
            },
            "users": [user],
        }
        _, errors = resolve_mountpoint_records(cfg, user)
        self.assertTrue(errors)
        self.assertIn("Mountpoint label conflict 'site'", errors[-1])

    def test_missing_assigned_template_is_error(self):
        user = {"sftpuser": "alice", "mountTemplates": ["missing"]}
        records, errors = resolve_mountpoint_records({"users": [user]}, user)
        self.assertEqual(records, [])
        self.assertEqual(errors, ["Assigned mountpoint template 'missing' does not exist."])

    def test_config_validation_accepts_template_only_enabled_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "mountpointTemplates": {
                    "web": {
                        "mounts": {
                            "mp_123": {"label": "site", "path": tmp},
                            "mp_456": {"label": "disabled", "path": tmp},
                        }
                    }
                },
                "users": [
                    {
                        "sftpuser": "alice",
                        "sftpmounts": {},
                        "mountTemplates": ["web"],
                        "templatePoints": {
                            "mp_123": {"enabled": True, "rw": False}
                        },
                        "sftpcerts": ["test-key"]
                    }
                ]
            }

            ok, error = parser_module.check_config_valid(cfg)

        self.assertTrue(ok)
        self.assertIsNone(error)

    def test_config_validation_requires_enabled_effective_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "mountpointTemplates": {
                    "web": {
                        "mounts": {
                            "mp_123": {"label": "site", "path": tmp}
                        }
                    }
                },
                "users": [
                    {
                        "sftpuser": "alice",
                        "sftpmounts": {},
                        "mountTemplates": ["web"],
                        "sftpcerts": ["test-key"]
                    }
                ]
            }

            ok, error = parser_module.check_config_valid(cfg)

        self.assertFalse(ok)
        self.assertIsNotNone(error)
        self.assertIn("mountpoint", error.lower())


class ParserTemplateApplyTests(unittest.TestCase):
    class ExistingMount:
        mountName = "docs"

        def __init__(self, path: str):
            self.realPath = path

        def isSambaVault(self):
            return True

    class FakeMountManager:
        def __init__(self, existing=None):
            self.existing = list(existing or [])
            self.deleted = []
            self.ensured = []

        def getMountpoints(self):
            return list(self.existing)

        def deleteMountpoint(self, name):
            self.deleted.append(name)

        def ensure_samba_mountpoint(self, name, path, my=False, rw=True):
            self.ensured.append((name, path, my, rw))

        def ensure_mountpoint(self, name, path):
            self.ensured.append((name, path, None, None))

        def ensureMountPointUserGroups(self):
            return []

    class FakeCertificateManager:
        def ensure_ssh_key(self, cert):
            raise AssertionError("no certificates expected")

    def _run_apply(self, cfg, manager):
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
            patch.object(parser_module.ssh, "ensureJail", return_value="/tmp/jail"),
        ):
            result = parser_module.createUserFromJson(cfg=cfg, errors_out=errors)
        return result, errors

    def test_disabled_local_mount_is_removed_and_not_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_path = Path(tmp) / "docs"
            real_path.mkdir()
            cfg = {
                "users": [
                    {
                        "sftpuser": "alice",
                        "sambaVault": True,
                        "sftpmounts": {"docs": str(real_path)},
                        "pointsSet": {"docs": {"enabled": False, "rw": False}},
                        "sftpcerts": [],
                    }
                ]
            }
            manager = self.FakeMountManager([self.ExistingMount(str(real_path))])
            result, errors = self._run_apply(cfg, manager)
            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertEqual(manager.deleted, ["docs"])
            self.assertEqual(manager.ensured, [])

    def test_enabled_template_mount_is_created_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            real_path = Path(tmp) / "site"
            real_path.mkdir()
            cfg = {
                "mountpointTemplates": {
                    "web": {
                        "mounts": {
                            "mp_123": {"label": "site", "path": str(real_path)},
                        }
                    }
                },
                "users": [
                    {
                        "sftpuser": "alice",
                        "sambaVault": True,
                        "sftpmounts": {},
                        "mountTemplates": ["web"],
                        "templatePoints": {
                            "mp_123": {"enabled": True, "rw": False},
                        },
                        "sftpcerts": [],
                    }
                ],
            }
            manager = self.FakeMountManager()
            result, errors = self._run_apply(cfg, manager)
            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertEqual(manager.deleted, [])
            self.assertEqual(
                manager.ensured,
                [("site", str(real_path), False, False)],
            )


if __name__ == "__main__":
    unittest.main()
