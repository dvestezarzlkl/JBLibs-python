# SFTP Library Notes

- `parser.py` handles config import/export and SFTP user synchronization.
- Optional config metadata:
  - top-level `adminMail`
  - per-user `mail`
- `check_config_valid()` should validate optional mail fields when present, but not require them.
- Validation messages returned by `check_config_valid()` are user-visible and must use the relative `sftp/lng/default.py` catalog with locale overrides loaded through `loadLng()`; technical parser logs may remain in English.
- `createJson()` should preserve `adminMail` and per-user `mail` metadata when rebuilding config from active users.
- `ssh.py` owns SSHD helpers.
  - `restart_sshd()` must support both `ssh` and `sshd` service names and return a real boolean result.
- Keep SSH and SFTP helper changes small and composable so the menu layer can stay thin.
- Use `smbHelp.checkCIFSInstalled()` for CIFS availability checks; missing CIFS must be reported before a Samba-backed Apply starts changing users.
- `sambaPoint.ensureMountpoint()` must re-raise its original failure and must never continue with an uninitialized `cifs_path`.
- Parser Apply is a synchronization operation: mountpoints removed from config, moved to another real path, or changed between bind and Samba must be removed before desired mountpoints are ensured.
- SSHD config must use the real user home returned by the system and must create `.ssh` there instead of falling back to `/home/<user>`.
- Samba/CIFS Apply is a transaction: configuration changes may be queued, but no physical CIFS unmount or mountpoint-directory cleanup may occur while a batch is active. At finalization, read the final managed CIFS set from `/etc/fstab`, unmount all managed loopback CIFS mounts first, remove only obsolete queued directories that are not targets in that final set, then reload Samba, run exactly one `systemctl daemon-reload`, and remount every managed CIFS entry still present in `/etc/fstab`. This preserves a target removed and recreated in the same batch (for example RO/RW or real-path changes).
- Never run `daemon-reload` while a managed loopback CIFS mount is reconnecting after an `smbd` restart; `systemd-fstab-generator` may block in the CIFS kernel client for about 90 seconds.
