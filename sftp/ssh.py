import logging
log = logging.getLogger("sshd")

from ...JBLibs import helper as jhlp
import os,pwd
from ..systemdService import c_service

SSHD_DIR = "/etc/ssh/sshd_config.d"

TPL = """
# Auto-generated SFTP jail config for user: {user}

Match User {user}
    ChrootDirectory {jail}
    ForceCommand internal-sftp
    PasswordAuthentication no
    AuthorizedKeysFile {authKey}
    X11Forwarding no
    AllowTcpForwarding no
    PermitTunnel no
"""

def ensureSSHDir(user:str, create:bool=True)->str|None:
    """Zajistí, že uživatel má ve svém domovském adresáři vytvořený adresář .ssh.
    Returns:
        str: cesta k adresáři .ssh   
        None: pokud uživatel neexistuje        
    """    
    log.info(f"Ensuring .ssh directory exists for user {user}")
    home=jhlp.getUserHome(user)
    if home is None:
        log.error(f" < Cannot determine home directory for user {user}.")
        return None
                
    ssh_dir = os.path.join(home, ".ssh")
    if not os.path.exists(ssh_dir) and not create:
        log.error(f" < .ssh directory does not exist for user {user} and create is False.")
        return None
    
    if os.path.isdir(ssh_dir):
        log.info(f" < .ssh directory already exists for user {user} at {ssh_dir}.")
        return ssh_dir
    elif os.path.exists(ssh_dir) and not os.path.isdir(ssh_dir):
        log.error(f" < .ssh path exists but is not a directory for user {user} at {ssh_dir}.")
        return None
    
    try:
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, exist_ok=True)
    except Exception as e:
        log.error(f" < Failed to create .ssh directory for user {user}: {e}")
        log.exception(e)
        return
    try:
        pw = pwd.getpwnam(user)
        os.chown(ssh_dir, pw.pw_uid, pw.pw_gid)
        os.chmod(ssh_dir, 0o700)
        log.info(f" < Successfully ensured .ssh directory for user {user} at {ssh_dir}.")
        return ssh_dir
    except Exception as e:
        log.error(f" < User {user} does not exist. Cannot set ownership for .ssh directory.")
        log.exception(e)
        return None

def __write_sshd_config(user, jail)-> str|None:
    """Vytvoří nebo aktualizuje sshd konfiguraci pro daného uživatele s jeho jail adresářem.
    Vrací cestu k vytvořenému konfiguračnímu souboru.
    Args:
        user (str): Uživatelské jméno SFTP uživatele.
        jail (str): Cesta k jail adresáři pro uživatele.
    Returns:
        str: Cesta k vytvořenému sshd konfiguračnímu souboru
        None: pokud došlo k chybě
    """
    log.info(f"Writing sshd config for user {user} with jail {jail}")
    
    if not jhlp.userExists(user):  # ověří, že uživatel existuje
        log.error(f" < User {user} does not exist. Cannot write sshd config.")
        return None
    
    if not os.path.isdir(SSHD_DIR):
        log.info(f" - SSHD config directory {SSHD_DIR} does not exist. Creating it.")
        try:
            os.makedirs(SSHD_DIR, exist_ok=True)
            os.chown(SSHD_DIR, 0, 0)
            os.chmod(SSHD_DIR, 0o755)
        except Exception as e:
            log.error(f" < Failed to create SSHD config directory {SSHD_DIR}: {e}")
            log.exception(e)
            return None
    else:
        log.info(f" - SSHD config directory {SSHD_DIR} already exists.")
    path = os.path.join(SSHD_DIR, f"sftp-{user}.conf")

    try:
        authKey = os.path.join( ensureSSHDir(user, create=False) or "/home/"+user+"/.ssh", "authorized_keys")
        content = TPL.format(user=user, jail=jail, authKey=authKey)
        log.info(f" - Writing sshd config for user {user} to {path}.")
        with open(path, "w") as f:
            f.write(content)
        log.info(f" < Successfully wrote sshd config for user {user} to {path}")
    except Exception as e:
        log.error(f" < Failed to write sshd config for user {user} to {path}: {e}")
        log.exception(e)
        return None

    return path

def remove_sshd_config(user:str)-> bool:
    """Odstraní sshd konfiguraci pro daného uživatele.
    Args:
        user (str): Uživatelské jméno SFTP uživatele.
    Returns:
        bool: True pokud byl soubor odstraněn nebo neexistoval, False pokud došlo k chybě
    """
    log.info(f"Removing sshd config for user {user}")
    path = os.path.join(SSHD_DIR, f"sftp-{user}.conf")
    if os.path.exists(path):
        log.info(f" - Found sshd config for user {user} at {path}. Deleting it.")
        try:
            os.remove(path)
            log.info(f" < Successfully removed sshd config for user {user} and restarted sshd.")
        except Exception as e:
            log.error(f" < Failed to remove sshd config for user {user} at {path}: {e}")
            log.exception(e)
            return False
    else:
        log.info(f"No sshd config found for user {user} at {path}. Nothing to remove.")
    return True

def deleteSSHKey(user:str,public_key:str|list[str])->bool:
    """Odstraní zadaný veřejný SSH klíč ze souboru authorized_keys uživatele.
    Args:
        public_key (str): veřejný SSH klíč
    Returns:
        None|str: None pokud vše ok, jinak seznam chyba - nekritická
    Raises:
        RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání klíče
    """
    log.info(f"Deleting SSH key for user {user}")
    sshDir=ensureSSHDir(user,create=False)
    if sshDir is None:
        # vpodstatě není chyna pokud uživatel nemá .ssh adresář
        log.warning(f" < Cannot ensure .ssh directory for user {user}.")
        return True
    ak_file = os.path.join( sshDir, "authorized_keys")
    if not os.path.exists(ak_file):
        # vpodstatě není chyna pokud uživatel nemá authorized_keys soubor
        log.warning(f" < authorized_keys file does not exist for user {user}.")
        return True

    try:
        # načteme existující klíče
        existing_keys = set()
        with open(ak_file, "r") as f:
            for line in f:
                existing_keys.add(line.strip())
        
        if public_key.strip() in existing_keys:
            existing_keys.remove(public_key.strip())
            with open(ak_file, "w") as f:
                for key in existing_keys:
                    f.write(key + "\n")
                    
        log.info(f" < Successfully removed SSH key for user {user}.") 
    except Exception as e:
        log.error(f" < Failed to delete SSH key for user {user}: {e}")
        log.exception(e)
        return False
    return True

def ensure_ssh_key(username:str,public_key:str)->str|None:
    """Zajistí, že uživatel má ve svém domovském adresáři nainstalovaný zadaný veřejný SSH klíč.
    Args:
        public_key (str): veřejný SSH klíč
    Returns:
        str: cesta k souboru s autorizovanými klíči
        None: pokud při chybě
    """
    log.info(f"Ensuring SSH key for user {username}")
    sshDir=ensureSSHDir(username,create=True)
    if sshDir is None:
        log.error(f" < Failed to ensure .ssh directory for user {username}.")
        return None
    
    ak_file = os.path.join( sshDir, "authorized_keys")
    # načteme existující klíče (pokud nějaké jsou) a přidáme nový, pokud tam ještě není
    existing_keys = set()
    if os.path.exists(ak_file):
        log.info(f" - Loading existing authorized_keys for user {username}.")
        try:
            with open(ak_file, "r") as f:
                for line in f:
                    existing_keys.add(line.strip())
        except Exception as e:
            log.error(f" < Failed to load existing authorized_keys file for user {username}: {e}")
            log.exception(e)
            return None
    else:
        log.info(f" - No existing authorized_keys file for user {username}. It will be created.")
    
    # přidáme nový klíč, pokud tam ještě není
    if public_key.strip() not in existing_keys:
        existing_keys.add(public_key.strip())
        
    try:    
        log.info(f" - Writing authorized_keys file for user {username}.")
        with open(ak_file, "w") as f:
            for key in existing_keys:
                f.write(key + "\n")
        pw = pwd.getpwnam(username)
        log.info(f" - Setting ownership and permissions for authorized_keys file of user {username}.")
        os.chown(ak_file, pw.pw_uid, pw.pw_gid)
        os.chmod(ak_file, 0o600)
        
        log.info(f" < Successfully wrote authorized_keys file for user {username} at {ak_file}.")        
    except Exception as e:
        log.error(f" < Failed to write authorized_keys file for user {username} at {ak_file}: {e}")
        log.exception(e)
        return None

    return ak_file

def ensureJail(username:str,testOnly:bool=False)->str|None:
    """Zajistí, že uživatel má vytvořený jail adresář a konfig
    Args:
        username (str): uživatelské jméno
        testOnly (bool): pokud je True, pouze otestuje existenci jail adresáře a neprovádí žádné změny
    Returns:
        str: cesta k jail adresáři
        None: pokud při chybě
    """
    if not testOnly:
        log.info(f"Ensuring jail directory for user {username}")
    homeDir=jhlp.getUserHome(username)
    if homeDir is None:
        if not testOnly:
            log.error(f" < Cannot determine home directory for user {username}.")
        return None
            
    jail_dir = os.path.join(homeDir, "__sftp__")
    try:
        if not os.path.exists(jail_dir):
            if testOnly:
                # log.info(f" - Jail directory {jail_dir} does not exist for user {username}, but testOnly is True. Not creating it.")
                return None
            log.info(f" - Jail directory {jail_dir} does not exist for user {username}. Creating it.")
            os.makedirs(jail_dir, exist_ok=True)
        else:
            log.info(f" - Jail directory {jail_dir} already exists for user {username}.")
    except Exception as e:
        log.error(f" < Failed to create jail directory for user {username} at {jail_dir}: {e}")
        log.exception(e)
        return None
    try:
        # pw = pwd.getpwnam(username)
        # os.chown(jail_dir, pw.pw_uid, pw.pw_gid)
        os.chown(jail_dir, 0, 0)
        os.chmod(jail_dir, 0o755)
    except KeyError:
        raise RuntimeError(f"Cannot set ownership for jail directory, user {username} does not exist.")
    
    try:
        # vytvoříme nebo aktualizujeme sshd config pro uživatele
        x=__write_sshd_config(username, jail_dir)
        if x is None:
            log.error(f" < Failed to write sshd config for user {username}.")
            return None
    except Exception as e:
        log.error(f" < Failed to ensure sshd config for user {username}: {e}")
        log.exception(e)
        return None
    
    log.info(f" < Successfully ensured jail directory for user {username} at {jail_dir}.")
    return jail_dir

def restart_sshd()->bool:
    """Restartuje sshd službu.
    Returns:
        bool: True pokud byl restart úspěšný, False pokud došlo k chybě
    """
    log.info("Restarting sshd service")
    
    s=c_service("ssh")
    if s.exists() is False:
        log.error(" < sshd service does not exist on this system.")
        return False
    # if not s.enabled(): # netestuejem, museli by jsme testovat 'ssh.socket' 
    #     log.info(" < sshd service is not enabled. Enabling it.")
    #     return False
    if s.running():
        log.info(" - Stopping sshd service before restart.")
        if not s.restart():
            log.error(" < Failed to stop sshd service before restart.")
            return False
    else:
        log.info(" - sshd service is not running. Starting it.")
        if not s.start():
            log.error(" < Failed to start sshd service.")
            return False
