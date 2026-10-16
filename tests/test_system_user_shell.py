import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from libs.JBLibs.systemUserManager import sshMng, sshUsers


class TestSystemUserLoginShell(unittest.TestCase):
    @patch("libs.JBLibs.systemUserManager.pwd.getpwnam")
    def test_get_user_shell(self, getpwnam):
        getpwnam.return_value = SimpleNamespace(pw_shell="/bin/sh")
        self.assertEqual(sshMng.getUserShell("alice"), "/bin/sh")
        self.assertFalse(sshMng.userUsesBash("alice"))

        getpwnam.return_value = SimpleNamespace(pw_shell="/usr/bin/bash")
        self.assertTrue(sshMng.userUsesBash("alice"))

    @patch("libs.JBLibs.systemUserManager.subprocess.run")
    @patch("libs.JBLibs.systemUserManager.os.path.isfile", return_value=True)
    @patch("libs.JBLibs.systemUserManager.userExists", return_value=True)
    def test_set_user_shell_to_bash(self, user_exists, isfile, run):
        self.assertIsNone(sshMng.setUserShell("alice"))
        run.assert_called_once_with(["usermod", "-s", "/bin/bash", "alice"], check=True)

    @patch("libs.JBLibs.systemUserManager.subprocess.run")
    @patch("libs.JBLibs.systemUserManager.os.path.isfile", return_value=True)
    @patch("libs.JBLibs.systemUserManager.userExists", return_value=True)
    def test_set_user_shell_reports_usermod_failure(self, user_exists, isfile, run):
        run.side_effect = subprocess.CalledProcessError(1, ["usermod"])
        error = sshMng.setUserShell("alice")
        self.assertIn("Error changing login shell", error)


class TestSSHUserDiscovery(unittest.TestCase):
    def test_orphaned_home_directory_does_not_break_ssh_listing(self):
        """Only existing UNIX accounts with a /home directory belong in SSH menu."""
        def getpwnam(name):
            if name == "alice":
                return SimpleNamespace(pw_name="alice")
            raise KeyError(name)

        with (
            patch("libs.JBLibs.helper.os.listdir", return_value=["samba_all", "alice"]),
            patch("libs.JBLibs.helper.os.path.isdir", return_value=True),
            patch("libs.JBLibs.helper.pwd.getpwnam", side_effect=getpwnam),
            patch(
                "libs.JBLibs.systemUserManager.sshUser",
                side_effect=lambda name: SimpleNamespace(userName=name),
            ) as create_user,
        ):
            users = sshUsers()

        self.assertEqual([user.userName for user in users], ["alice"])
        self.assertEqual(len(users), 1)
        create_user.assert_called_once_with("alice")



    def test_only_orphaned_home_directories_yield_empty_menu(self):
        with (
            patch("libs.JBLibs.helper.os.listdir", return_value=["samba_all"]),
            patch("libs.JBLibs.helper.os.path.isdir", return_value=True),
            patch("libs.JBLibs.helper.pwd.getpwnam", side_effect=KeyError("samba_all")),
        ):
            users = sshUsers()

        self.assertEqual(len(users), 0)


if __name__ == "__main__":
    unittest.main()
