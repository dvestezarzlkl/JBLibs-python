from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_jblibs_testpkg"
if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    package.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = package
fs_utils = importlib.import_module(f"{PACKAGE_NAME}.fs_utils")


def lsblk_json(mount_key="mountpoints", with_ptuuid=True):
    disk = {"name": "sda", "label": None, "size": 1024, "type": "disk",
            "fstype": None, "uuid": None, "partuuid": None,
            mount_key: None, "children": []}
    if with_ptuuid:
        disk["ptuuid"] = "original-id"
    return json.dumps({"blockdevices": [disk]})


class LegacyLsblkTests(unittest.TestCase):
    def test_modern_lsblk_no_fallback(self):
        with patch.object(fs_utils, "runRet", return_value=(lsblk_json(), 0, "")) as cmd:
            disk = fs_utils.lsblk_list_disks(False)["sda"]
        self.assertEqual(disk.ptuuid, "original-id")
        cmd.assert_called_once()

    def test_mountpoints_fallback(self):
        responses = [
            ("", 1, "lsblk: unknown column: MOUNTPOINTS"),
            (lsblk_json("mountpoint"), 0, ""),
        ]
        with patch.object(fs_utils, "runRet", side_effect=responses) as cmd:
            disk = fs_utils.lsblk_list_disks(False)["sda"]
        self.assertEqual(disk.mountpoints, [])
        self.assertIn("MOUNTPOINT,PTUUID", cmd.call_args_list[1].args[0][-1])

    def test_ptuuid_fallback_uses_blkid(self):
        responses = [
            ("", 1, "lsblk: unknown column: PTUUID"),
            (lsblk_json(with_ptuuid=False), 0, ""),
            ("1234abcd\\n", 0, ""),
        ]
        with patch.object(fs_utils, "runRet", side_effect=responses) as cmd:
            disk = fs_utils.lsblk_list_disks(False)["sda"]
        self.assertEqual(disk.ptuuid, "1234abcd\\n".replace("\\n", "").strip())
        self.assertEqual(cmd.call_args_list[2].args[0][0], "blkid")

    def test_both_legacy_columns(self):
        responses = [
            ("", 1, "lsblk: unknown column: MOUNTPOINTS"),
            ("", 1, "lsblk: unknown column: PTUUID"),
            (lsblk_json("mountpoint", with_ptuuid=False), 0, ""),
            ("legacy-uuid", 0, ""),
        ]
        with patch.object(fs_utils, "runRet", side_effect=responses):
            disk = fs_utils.lsblk_list_disks(False)["sda"]
        self.assertEqual(disk.ptuuid, "legacy-uuid")
        self.assertEqual(disk.mountpoints, [])

    def test_blkid_unavailable_keeps_empty_identifier(self):
        responses = [
            ("", 1, "lsblk: unknown column: PTUUID"),
            (lsblk_json(with_ptuuid=False), 0, ""),
            ("", 2, "no PTUUID"),
        ]
        with patch.object(fs_utils, "runRet", side_effect=responses):
            disk = fs_utils.lsblk_list_disks(False)["sda"]
        self.assertFalse(disk.ptuuid)

    def test_unrelated_failure_is_not_swallowed(self):
        with patch.object(fs_utils, "runRet", return_value=("", 1, "permission denied")):
            with self.assertRaises(fs_utils.lsblkError):
                fs_utils.lsblk_list_disks(False)


if __name__ == "__main__":
    unittest.main()
