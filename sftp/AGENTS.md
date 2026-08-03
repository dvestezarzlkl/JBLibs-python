# SFTP Library Notes

- `parser.py` handles config import/export and SFTP user synchronization.
- Optional config metadata:
  - top-level `adminMail`
  - per-user `mail`
- `check_config_valid()` should validate optional mail fields when present, but not require them.
- `createJson()` should preserve `adminMail` and per-user `mail` metadata when rebuilding config from active users.
- `ssh.py` owns SSHD helpers.
  - `restart_sshd()` must support both `ssh` and `sshd` service names and return a real boolean result.
- Keep SSH and SFTP helper changes small and composable so the menu layer can stay thin.
- Use `smbHelp.checkCIFSInstalled()` for CIFS availability checks; missing CIFS must be reported before a Samba-backed Apply starts changing users.
- `sambaPoint.ensureMountpoint()` must re-raise its original failure and must never continue with an uninitialized `cifs_path`.
- Parser Apply is a synchronization operation: mountpoints removed from config, moved to another real path, or changed between bind and Samba must be removed before desired mountpoints are ensured.
- SSHD config must use the real user home returned by the system and must create `.ssh` there instead of falling back to `/home/<user>`.
