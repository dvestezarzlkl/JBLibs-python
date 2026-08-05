from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "_jblibs_testpkg"

if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(ROOT)]
    package.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = package

fs_utils = importlib.import_module(f"{PACKAGE_NAME}.fs_utils")


def device(
    name: str,
    *,
    type_: str = "disk",
    mountpoints: list[str] | None = None,
    children: list | None = None,
):
    return fs_utils.lsblkDiskInfo(
        name=name,
        label="",
        size=1024,
        fstype="ext4" if type_ == "part" else "",
        type=type_,
        uuid="",
        partuuid="",
        mountpoints=mountpoints or [],
        children=children or [],
        ptuuid="disk-id",
    )


def node(
    name: str,
    *,
    type_: str,
    mountpoints: list[str] | None = None,
    children: list[dict] | None = None,
) -> dict:
    return {
        "name": name,
        "label": "",
        "size": 1024,
        "fstype": "ext4" if type_ == "part" else "",
        "type": type_,
        "uuid": "",
        "partuuid": "",
        "ptuuid": "disk-id",
        "mountpoints": mountpoints or [],
        "children": children or [],
    }


class SystemDiskDetectionTests(unittest.TestCase):
    def test_partition_with_root_mountpoint_is_system_device(self):
        self.assertTrue(
            device("sda2", type_="part", mountpoints=["/"]).isSystemDisk
        )

    def test_parent_disk_inherits_system_state_from_child_partition(self):
        root = device("sda2", type_="part", mountpoints=["/"])
        disk = device("sda", children=[root])

        self.assertTrue(disk.isSystemDisk)

    def test_efi_mountpoint_marks_parent_as_system_disk(self):
        efi = device("sda1", type_="part", mountpoints=["/boot/efi"])
        disk = device("sda", children=[efi])

        self.assertTrue(disk.isSystemDisk)

    def test_regular_disk_is_not_system_disk(self):
        data = device("sdb1", type_="part", mountpoints=["/mnt/data"])
        disk = device("sdb", children=[data])

        self.assertFalse(disk.isSystemDisk)

    def test_ignore_system_disks_removes_complete_parent(self):
        nodes = [
            node(
                "sda",
                type_="disk",
                children=[
                    node("sda1", type_="part"),
                    node("sda2", type_="part", mountpoints=["/"]),
                ],
            )
        ]
        process_lsblk = getattr(fs_utils, "__lsblk")

        self.assertEqual(process_lsblk(nodes, ignoreSysDisks=True), [])

        all_disks = process_lsblk(nodes, ignoreSysDisks=False)
        self.assertEqual(len(all_disks), 1)
        self.assertEqual(len(all_disks[0].children), 2)
        self.assertTrue(all_disks[0].isSystemDisk)


if __name__ == "__main__":
    unittest.main()
