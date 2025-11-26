# lib/sftp/jail.py
import os
import pwd
import grp
import shutil

def create_jail(username):
    pw = pwd.getpwnam(username)
    home = pw.pw_dir
    jail_root = os.path.join(home, "__sftp__")
    mounts_dir = os.path.join(jail_root, "mounts")

    os.makedirs(mounts_dir, exist_ok=True)

    # jail root musí být root:root 755
    os.chown(jail_root, 0, 0)
    os.chmod(jail_root, 0o755)

    # mounts patří userovi
    os.chown(mounts_dir, pw.pw_uid, pw.pw_gid)
    os.chmod(mounts_dir, 0o755)

    return jail_root, mounts_dir


def remove_jail(jail_root: str):
    if os.path.isdir(jail_root):
        shutil.rmtree(jail_root)


def validate_jail(jail_root: str, username: str, mounts: dict):
    """
    Jednoduchá validace jailu:
    - jail_root: root:root 755
    - mounts dir: user:user
    - každý dst mount: user:group, 755
    """
    pw = pwd.getpwnam(username)

    st = os.stat(jail_root)
    if st.st_uid != 0 or st.st_gid != 0 or (st.st_mode & 0o777) != 0o755:
        raise RuntimeError(f"Jail root {jail_root} must be root:root 755")

    mounts_dir = os.path.join(jail_root, "mounts")
    st_m = os.stat(mounts_dir)
    if st_m.st_uid != pw.pw_uid:
        raise RuntimeError(f"Mounts dir {mounts_dir} must be owned by {username}")

    for name, info in mounts.items():
        dst = info["dst"]
        st_d = os.stat(dst)
        if st_d.st_uid != pw.pw_uid:
            raise RuntimeError(f"Mount target {dst} must be owned by {username} (uid={pw.pw_uid})")
        # chmod 755 kontrolujeme jen orientačně
        if (st_d.st_mode & 0o777) != 0o755:
            raise RuntimeError(f"Mount target {dst} should have mode 755")
