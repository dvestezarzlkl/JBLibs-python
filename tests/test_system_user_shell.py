import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from libs.JBLibs.systemUserManager import sshMng


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


if __name__ == "__main__":
    unittest.main()
