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
