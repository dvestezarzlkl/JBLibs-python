from __future__ import annotations

import importlib
import sys
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

user_groups = importlib.import_module("libs.JBLibs.sftp.userGrps")


class DeleteUserFromGroupTests(unittest.TestCase):
    def test_specific_group_membership_is_checked_for_requested_user(self):
        proc = types.SimpleNamespace(returncode=0)
        with (
            patch.object(user_groups, "getUserHome", return_value="/home_sftp_users/alice"),
            patch.object(user_groups, "checkUserInGroup", return_value=True) as check,
            patch.object(user_groups.subprocess, "run", return_value=proc) as run,
        ):
            self.assertTrue(user_groups.deleteUserFromGroup("alice", "docs"))

        check.assert_called_once_with("alice", "docs")
        run.assert_called_once_with(
            ["gpasswd", "-d", "alice", "docs"],
            check=True,
        )

    def test_specific_group_is_noop_when_user_is_not_member(self):
        with (
            patch.object(user_groups, "getUserHome", return_value="/home_sftp_users/alice"),
            patch.object(user_groups, "checkUserInGroup", return_value=False) as check,
            patch.object(user_groups.subprocess, "run") as run,
        ):
            self.assertTrue(user_groups.deleteUserFromGroup("alice", "docs"))

        check.assert_called_once_with("alice", "docs")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
