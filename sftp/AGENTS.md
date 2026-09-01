# SFTP Library Notes

- `parser.py` handles config import/export and SFTP user synchronization.
- Optional config metadata:
  - top-level `adminMail`
  - per-user `mail`
- `check_config_valid()` should validate optional mail fields when present, but not require them. Mountpoint validation must use `resolve_mountpoint_records()` for local + template state and require at least one enabled effective mountpoint per user; do not gate template users on raw `sftpmounts`.
- Validation messages returned by `check_config_valid()` are user-visible and must use the relative `sftp/lng/default.py` catalog with locale overrides loaded through `loadLng()`; technical parser logs may remain in English.
- `createJson()` should preserve `adminMail` and per-user `mail` metadata when rebuilding config from active users.
- `ssh.py` owns SSHD helpers.
  - `restart_sshd()` must support both `ssh` and `sshd` service names and return a real boolean result.
- Keep SSH and SFTP helper changes small and composable so the menu layer can stay thin.
- Use `smbHelp.checkCIFSInstalled()` for CIFS availability checks; missing CIFS must be reported before a Samba-backed Apply starts changing users.
- `sambaPoint.ensureMountpoint()` must re-raise its original failure and must never continue with an uninitialized `cifs_path`.
- Parser Apply is a synchronization operation: mountpoints removed from config, moved to another real path, or changed between bind and Samba must be removed before desired mountpoints are ensured.
- SSHD config must use the real user home returned by the system and must create `.ssh` there instead of falling back to `/home/<user>`.
- Samba/CIFS Apply is a transaction: configuration changes may be queued, but no physical CIFS unmount or mountpoint-directory cleanup may occur while a batch is active. At finalization, derive the affected targets from queued remove/recreate targets, newly mounted shares and queued share closes, then unmount only those affected managed loopback CIFS mounts. Unchanged mounted targets must stay connected, even when Samba is reloaded, so an unrelated busy CWD cannot fail Apply. Read the final managed CIFS set from `/etc/fstab`, remove only obsolete queued directories that are not targets in that final set, verify every affected final unmounted target is empty and secure it as root-owned/non-writable, then reload Samba, close only the affected managed `sftp_mount_*` service connections with `smbcontrol smbd close-share` (fallback to full smbd restart if targeted close fails), run exactly one `systemctl daemon-reload`, and remount only affected CIFS entries still present in `/etc/fstab`. Samba reload alone does not change parameters of established service connections, so the targeted close is required for live RO/RW changes. This preserves a target removed and recreated in the same batch (for example RO/RW or real-path changes) without disconnecting unrelated Samba shares or unchanged SFTP mountpoints.
- Never mount a managed CIFS share over a non-empty underlying target: Linux would hide that data under the mount. During user deletion, recursive jail cleanup is allowed only after explicit confirmation and after proving from `/proc/self/mountinfo` that neither the jail nor any descendant is still mounted; do not rely on `os.path.ismount()` for this destructive guard because same-filesystem bind mounts are not reliably detected. If mountinfo cannot be read, fail closed and preserve the jail.
- Never run `daemon-reload` while a managed loopback CIFS mount is reconnecting after an `smbd` restart; `systemd-fstab-generator` may block in the CIFS kernel client for about 90 seconds.
