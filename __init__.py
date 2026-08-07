__version__ = "1.2.23"

# 1.2.23: Samba/CIFS batch defers physical cleanup, preserves recreated targets, and uses correct SFTP share identity
# 1.2.22: SFTP reconciliation accepts in-memory config and exposes concrete per-user apply errors
# 1.2.21: c_menu consistently honors onExitMenu=False for ESC, endMenu, and registered-key exit paths
# 1.2.20: SFTP Apply reconciles Samba RO/RW changes even when alias and real path stay unchanged
# 1.2.19: c_menu adds a persistent global title context with per-menu opt-out
# 1.2.18: system disk detection follows child partitions and filtering removes the complete live system disk
# 1.2.17: missing lsof no longer terminates applications during SFTP mount module import
# 1.2.16: c_menu exits cleanly on Ctrl+C while waiting for input without swallowing interrupts from active actions
# 1.2.15: SMTP messages include the required RFC Date header before transport
# 1.2.14: reusable SMTP transport with path/bytes/stream attachments and in-memory ZIP support
# 1.2.13: updater integration test only; no library behavior changed