from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


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

ssh = importlib.import_module("libs.JBLibs.sftp.ssh")


class RestartSshdValidationTests(unittest.TestCase):
    def test_invalid_config_prevents_service_restart(self):
        with (
            patch.object(ssh, "validate_sshd_config", return_value=False),
            patch.object(ssh, "c_service") as service_factory,
        ):
            self.assertFalse(ssh.restart_sshd())

        service_factory.assert_not_called()

    def test_validation_runs_sshd_t(self):
        proc = types.SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        with (
            patch.object(ssh, "which", return_value="/usr/sbin/sshd"),
            patch.object(ssh.subprocess, "run", return_value=proc) as run,
        ):
            self.assertTrue(ssh.validate_sshd_config())

        run.assert_called_once_with(
            ["/usr/sbin/sshd", "-t"],
            stdout=ssh.subprocess.PIPE,
            stderr=ssh.subprocess.PIPE,
        )

    def test_valid_config_allows_existing_running_service_restart(self):
        service = MagicMock()
        service.exists.return_value = True
        service.running.return_value = True
        service.restart.return_value = True
        service.fullName = "ssh.service"

        with (
            patch.object(ssh, "validate_sshd_config", return_value=True),
            patch.object(ssh, "c_service", return_value=service),
        ):
            self.assertTrue(ssh.restart_sshd())

        service.restart.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
