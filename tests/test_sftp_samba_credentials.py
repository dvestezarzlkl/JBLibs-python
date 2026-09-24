from __future__ import annotations

import importlib
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

samba = importlib.import_module("libs.JBLibs.sftp.sambaPoint")


class SambaCredentialTests(unittest.TestCase):
    def test_existing_credential_is_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cred = Path(tmp) / ".smb_sftp_creds"
            cred.write_text(
                f"username={samba.SMB_SFT_USER}\npassword=existing-secret\n",
                encoding="utf-8",
            )
            with (
                patch.object(samba, "SMB_CRED_FILE", str(cred)),
                patch.object(samba.os, "chown"),
                patch.object(samba.os, "chmod"),
                patch.object(samba.secrets, "token_urlsafe") as generate,
            ):
                password, created = samba.smbHelp.ensureSambaCredFile()

            self.assertEqual(password, "existing-secret")
            self.assertFalse(created)
            generate.assert_not_called()

    def test_clean_install_generates_credential_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            cred = Path(tmp) / ".smb_sftp_creds"
            with (
                patch.object(samba, "SMB_CRED_FILE", str(cred)),
                patch.object(samba.os, "chown"),
                patch.object(samba.os, "chmod"),
                patch.object(samba.secrets, "token_urlsafe", return_value="generated-secret") as generate,
            ):
                password, created = samba.smbHelp.ensureSambaCredFile()

            self.assertEqual(password, "generated-secret")
            self.assertTrue(created)
            self.assertIn("password=generated-secret", cred.read_text(encoding="utf-8"))
            generate.assert_called_once_with(32)

    def test_existing_passdb_user_keeps_password(self):
        fake_pwd = types.SimpleNamespace(pw_uid=1000, pw_gid=1000)
        with (
            patch.object(samba.pwd, "getpwnam", return_value=fake_pwd),
            patch.object(samba.smbHelp, "sambaPassdbUserExists", return_value=True),
            patch.object(samba.smbHelp, "ensureSambaUserPwd") as set_password,
        ):
            samba.smbHelp.ensureSambaUserExists("stored-secret")

        set_password.assert_not_called()

    def test_missing_passdb_user_is_initialized_from_stored_credential(self):
        fake_pwd = types.SimpleNamespace(pw_uid=1000, pw_gid=1000)
        with (
            patch.object(samba.pwd, "getpwnam", return_value=fake_pwd),
            patch.object(samba.smbHelp, "sambaPassdbUserExists", return_value=False),
            patch.object(samba.smbHelp, "ensureSambaUserPwd") as set_password,
        ):
            samba.smbHelp.ensureSambaUserExists("stored-secret")

        set_password.assert_called_once_with("stored-secret")


if __name__ == "__main__":
    unittest.main()
