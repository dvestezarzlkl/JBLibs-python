from ..helper import getLogger
log = getLogger("sftp.parser")
"""Pro SFTP manager parsing a uživatelskou správu.

instaluje uživatele ze zadaného JSON souboru, odinstaluje uživatele,
vytváří seznam uživatelů do JSON souboru a vypisuje seznam aktivních uživatelů.

"""

import os
import re
import json5
import base64
import pwd
from typing import Union
from .user import sftpUserMng
from . import ssh
from .glob import SAFE_NAME_RGX, BASE_DIR
from . import sambaPoint as smb
from typing import Dict

class mountpointPerms:
    def __init__(self,row:dict)->None:
        self.my:bool = bool(row.get("my", True))
        """Pokud True, jedná se o mountpoint vlastněný uživatelem"""
        
        self.rw:bool = bool(row.get("rw", True))
        """Pokud True, jedná se o read-write mountpoint, jinak readonly"""
        
class mountpointsPerms(Dict[str, mountpointPerms]):
    """A dictionary where keys are strings and values are instances of mountpointPerms."""
    def __init__(self, data:Dict[str, dict])->None:
        super().__init__()
        for key, value in data.items():
            if isinstance(value, dict):
                self[key] = mountpointPerms(value)
            else:
                log.warning(f"Invalid mountpoint permissions entry for '{key}': expected a dictionary.")        

def safeName(name:str,throw:bool=True)->bool:
    """Otestuje, zda je zadané jméno bezpečné pro uživatelské jméno nebo mountpoint.
    Args:
        name (str): jméno k otestování
    Returns:
        bool: True pokud je jméno bezpečné, jinak False
    """
    err=RuntimeError(f"Invalid name '{name}': only alphanumeric characters, dots, underscores, and hyphens are allowed.")
    if not isinstance(name, str):
        if throw:
            raise err
        return False
    
    b=bool(SAFE_NAME_RGX.match(name))
    if throw and not b:
        raise err
    return b

def createUserFromJson(file:str)->Union[list['sftpUserMng']|None]:
    """Vytvoří uživatele ze zadaného json souboru
    Musí mít root property:
    - `sftpuser` (string) a v něm uživatelské jméno
    - `sftpmounts` (optional object) je objekt kde:
        - každý klíč je jméno mountpointu v jailu
        - každá hodnota je reálná cesta k umístění
    - `sftpcerts` (optional array) je string[] pole certifikátů
        POZOR hodnota může začínat "b64:..." což znamená že je certifikát base64 zakódován
    - `sambaVault` (optional bool) zda vytvořit mountpointy přes sambu (CIFS) nebo přímo bindem
        výchozí je False (bind mount)
    
    POZOR pokud je root parametr `users` tak se jedná o pole uživatelů
        kde se uživatel stane rootem výše uvedených property
    
    Args:
        file (str): cesta k json souboru
    Returns:
        list[sftpUserMng]: seznam vytvořených uživatelů
        None pokud se vytvoření uživatelů nezdaří
    """
    
    log.info(f"Loading SFTP users from JSON file {file}.")
    if not os.path.isfile(file):
        log.error(f"JSON file {file} does not exist.")
        return None
    log.info(f"Reading JSON file {file}.")
    try:
        with open(file, "r") as f:
            d=json5.load(f)
    except Exception as e:
        log.error(f"Failed to load JSON file {file}: {e}")
        log.exception(e)
        return None
    
    log.info(f"Parsing SFTP user data from JSON file {file}.")
    users=[]
    ret=[]
    if "users" in d and isinstance(d["users"], list):
        log.info(f" - Found 'users' array in JSON file {file}.")
        for udata in d["users"]:
            users.append(udata)
    else:
        log.info(f" - No 'users' array found, treating root JSON as single user data.")
        users.append(d)
    
    log.info(f"Creating {len(users)} SFTP users from JSON file {file}.")
    for data in users:
        try:
            log.info(f"Processing user data: {data.get('sftpuser','<unknown>')}")
            if "sftpuser" not in data or not isinstance(data["sftpuser"], str):
                log.error(f"Invalid JSON format: missing 'sftpuser' string property.")
                continue
            
            username=str(data["sftpuser"])
            safeName(username,throw=True)
            
            sambaVault=False
            if "sambaVault" in data:
                if isinstance(data["sambaVault"], bool):
                    sambaVault=data["sambaVault"]
                else:
                    log.error(f"Invalid 'sambaVault' property for user {username}: must be a boolean.")
                    continue
            
            if sftpUserMng.user_exists(username):
                log.info(f"User {username} already exists, skipping creation.")
                u=sftpUserMng(username)
            else:
                # vytvoříme uživatele
                u=sftpUserMng.create_user(username)
                if u is None or not u.ok:
                    log.error(f"Failed to create user {username}.")
                    continue                    
            
            # načteme nastavení mountpointů
            mpSet=mountpointsPerms({})
            if "pointsSet" in data and isinstance(data["pointsSet"], dict):
                log.info(f" - Found mountpoint permissions for user {username}.")
                mpSet=mountpointsPerms(data["pointsSet"])
            
            
            # přidáme mountpointy
            log.info(f"Adding mountpoints for user {username}.")
            if "sftpmounts" in data and isinstance(data["sftpmounts"], dict):
                log.info(f" - Found {len(data['sftpmounts'])} mountpoints to add for user {username}.")
                for mount_name, real_path in data["sftpmounts"].items():
                    log.info(f"   - Processing mountpoint '{mount_name}': '{real_path}'")
                    if not isinstance(mount_name, str) or not isinstance(real_path, str):
                        log.error(f"Invalid mountpoint entry for user {username}: mount_name and real_path must be strings.")
                        continue
                    safeName(mount_name,throw=True)
                    if not os.path.isabs(real_path):
                        log.error(f"Invalid mountpoint real path for user {username}: path must be absolute.")
                        continue
                    if not os.path.exists(real_path):
                        log.error(f"Mountpoint real path does not exist for user {username}: {real_path}.")
                        continue
                    log.info(f"   - Ensuring mountpoint '{mount_name}' for user {username}.")
                    if sambaVault:
                        mps=mpSet.get(mount_name, mountpointPerms({}))
                        log.info(f"     - Mountpoint permissions for user {username}, mount '{mount_name}': my={mps.my}, rw={mps.rw}")                        
                        log.info(f"     - Creating Samba mountpoint for user {username}.")
                        u.mountpointManager.ensure_samba_mountpoint(mount_name, real_path, my=mps.my, rw=mps.rw)
                    else:
                        log.info(f"     - Creating bind mountpoint for user {username}.")
                        u.mountpointManager.ensure_mountpoint(mount_name, real_path)
            else:
                log.info(f"No mountpoints to add for user {username}.")
            
            # přidáme certifikáty
            log.info(f"Adding certificates for user {username}.")
            if "sftpcerts" in data and isinstance(data["sftpcerts"], list):
                log.info(f" - Found {len(data['sftpcerts'])} certificates to add for user {username}.")
                for cert in data["sftpcerts"]:
                    log.info(f"   - Processing certificate for user {username}.")
                    if not isinstance(cert, str):
                        log.error(f"Invalid certificate entry for user {username}: certificate must be a string.")
                        continue
                    cert=cert.strip()
                    if cert.startswith("b64:"):
                        log.info(f"   - Decoding base64 certificate for user {username}.")
                        b64_data=cert[4:]
                        try:
                            decoded_bytes=base64.b64decode(b64_data)
                            cert=decoded_bytes.decode("utf-8").strip()
                            log.info(f"   - Successfully decoded base64 certificate for user {username}.")
                        except Exception as e:
                            log.error(f"Failed to decode base64 certificate for user {username}: {e}")
                            log.exception(e)
                            continue
                    log.info(f"   - Ensuring SSH key for user {username}.")
                    if not re.match(r'^(ssh-|ecdsa-)', cert):
                        log.error(f"Invalid certificate format for user {username}: certificate must start with 'ssh-' or 'ecdsa-'.")
                        continue
                    log.info(f"   - Adding certificate for user {username}.")
                    u.certificateManager.ensure_ssh_key(cert)
            else:
                log.info(f"No certificates to add for user {username}.")
                
            # přidáme ssh konfig
            log.info("   - Ensuring SSH config for user {username}.")
            x=ssh.ensureJail(u.username)
            if x is None:
                log.error(f"Failed to ensure SSH config for user {username}.")
                continue                                    
                
            # zajistíme skupiny
            log.info(f"   - Ensuring mountpoint user groups for user {username}.")
            try:
                u.mountpointManager.ensureMountPointUserGroups()
            except Exception as e:
                log.error(f"Failed to ensure mountpoint user groups for user {username}: {e}")
                log.exception(e)
                continue
                
            ret.append(u)
            log.info(f" <<< Successfully created/updated user {username} from JSON data.")
        except Exception as e:
            log.error(f"Failed to create user from JSON data: {e}")
            log.exception(e)
    
    smb.postEnsureAllMountpoints()
    # restart ssh je v hlavním volání    
    log.info(f"Finished processing JSON file {file}. Created/updated {len(ret)} users.")
    if len(ret) == 0:
        log.error("No users were created or updated from JSON data.")
        return None
    return ret
    
@staticmethod
def listActiveUsers()->Union[list['sftpUserMng']|None]:
    """Vrátí seznam všech aktivních sftpUserMng uživatelů v systému.
    Returns:
        Union[list[sftpUserMng]|None]: seznam uživatelů nebo None pokud dojde k chybě
        None pokud dojde k chybě
    """
    users:list[sftpUserMng] = []
    try:
        all_users = pwd.getpwall()
        for user in all_users:
            username = user.pw_name
            if not str(user.pw_dir).startswith(BASE_DIR):
                continue
            try:
                if sftpUserMng.user_exists(username):
                    u = sftpUserMng(username, testOnly=True)
                    if u.ok:
                        users.append(u)
            except Exception:
                continue
    except Exception as e:
        return None
    return users

def createJson(file:str,overwrite:bool)->bool:
    """Vytvoří JSON soubor se seznamem všech sftpUserMng uživatelů v systému.
    Args:
        file (str): cesta k výstupnímu JSON souboru
        overwrite (bool): pokud True, přepíše existující soubor
    Returns:
        bool: True pokud se vytvoření souboru podařilo, jinak False
    """
    log.info(f"Creating JSON file {file} with SFTP users.")
    if os.path.isfile(file) and not overwrite:
        log.error(f"JSON file {file} already exists and overwrite is False.")
        return False
    
    try:
        users = listActiveUsers()
    except Exception as e:
        log.error(f"Failed to list active SFTP users: {e}")
        log.exception(e)
        return False
    if users is None:
        log.error("Failed to list active SFTP users.")
        return False
    
    data = {"users": []}
    log.info(f"Found {len(users)} active SFTP users to export.")
    for u in users:
        log.info(f"Processing user {u.username} for JSON export.")
        try:
            user_data = {
                "sftpuser": u.username,
                "sftpmounts": {},
                "sftpcerts": list(u.certificates)
            }
            for mp in u.getMountpoints():
                nm=mp.mountName
                user_data["sftpmounts"][nm] = mp.realPath
            data["users"].append(user_data)
        except Exception as e:
            log.error(f"Failed to process user {u.username} for JSON export: {e}")
            log.exception(e)
            continue
    
    try:
        with open(file, "w") as f:
            json5.dump(data, f, indent=4, sort_keys=True)
        log.info(f"Successfully created JSON file {file} with {len(users)} users.")
    except Exception as e:
        log.error(f"Failed to create JSON file {file}: {e}")
        log.exception(e)
        return False
    
    return True

def uninstallUser(username:str|sftpUserMng)->bool:
    """Odinstaluje zadaného sftpUserMng uživatele ze systému.
    Args:
        username (str): jméno uživatele k odinstalaci
    Returns:
        bool: True pokud se odinstalace podařila, jinak False
    """
    from .sambaPoint import smbHelp
    __uninstallUser(username)
    smbHelp.reloadSystemdDaemon()
    return True

def __uninstallUser(username:str|sftpUserMng)->bool:
    """Odinstaluje zadaného sftpUserMng uživatele ze systému.
    Args:
        username (str): jméno uživatele k odinstalaci
    Returns:
        bool: True pokud se odinstalace podařila, jinak False
    """
    log.info(f"Uninstalling SFTP user {username}.")
    try:
        if isinstance(username, str):
            u = sftpUserMng(username)
        else:
            u = username
        if not u.ok:
            log.error(f"User {username} is not a valid SFTP user.")
            return False
        u.delete_user()
        log.info(f"Successfully uninstalled SFTP user {username}.")
        return True
    except Exception as e:
        log.error(f"Failed to uninstall SFTP user {username}: {e}")
        log.exception(e)
        return False
    
def uninstallAllUsers()->bool:
    """Odinstaluje všechny sftpUserMng uživatele ze systému.
    Returns:
        bool: True pokud se odinstalace podařila, jinak False
    """
    from .sambaPoint import smbHelp
    
    log.info("Uninstalling all SFTP users.")
    try:
        users = listActiveUsers()
    except Exception as e:
        log.error(f"Failed to list active SFTP users: {e}")
        log.exception(e)
        return False
    if users is None:
        log.error("Failed to list active SFTP users.")
        return False
    
    success=True
    for u in users:
        if not __uninstallUser(u):
            success=False
            
    smbHelp.reloadSystemdDaemon()
    return success