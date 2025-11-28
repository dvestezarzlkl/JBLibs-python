import pwd
import grp
import subprocess
from libs.JBLibs.helper import userExists, getUserHome

def getUserGroups(username:str)->list[str]:
    """Získá seznam skupin, do kterých uživatel patří.
    Args:
        username (str): jméno uživatele
    Returns:
        list[str]: seznam jmen skupin
    Raises:
        RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při získávání skupin
    """
    if not userExists(username):
        raise RuntimeError(f"User {username} does not exist.")

    groups: list[str] = []
    try:
        grps= grp.getgrall()
        for g in grps:
            if username in g.gr_mem:
                groups.append(g.gr_name)
            else:
                # může být i primární skupina
                pw = pwd.getpwnam(username)
                if pw.pw_gid == g.gr_gid:
                    groups.append(g.gr_name)
        return groups
    except Exception as e:
        raise RuntimeError(f"Failed to get groups for user {username}: {e}")

def checkUserInGroup(username:str, group_name:str)->bool:
    """Zkontroluje, zda je uživatel členem zadané skupiny.
    Args:
        username (str): jméno uživatele
        group_name (str): jméno skupiny
    Returns:
        bool: True pokud je uživatel členem skupiny
    Raises:
        RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při kontrole skupin
    """
    homeDir = getUserHome(username)
    if not homeDir:
        raise RuntimeError(f"User {username} does not exist or has no home directory.")
    
    try:
        groups = getUserGroups(username)
        return group_name in groups
    except Exception as e:
        raise RuntimeError(f"Failed to check group membership for user {username}: {e}")
                

def addUSerToGroup(username:str, group_name:str)->bool:
    """Přidá uživatele do zadané skupiny.
    Args:
        username (str): jméno uživatele
        group_name (str): jméno skupiny
    Returns:
        bool: True pokud vše ok
    Raises:
        RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při přidávání do skupiny
    """
    homeDir = getUserHome(username)
    if not homeDir:
        raise RuntimeError(f"User {username} does not exist or has no home directory.")
    
    if checkUserInGroup(username, group_name):
        return True  # už tam je

    try:
        subprocess.run([
            "usermod",
            "-aG",
            group_name,
            username
        ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to add user {username} to group {group_name}: {e}")
    
def deleteUserFromGroup(username:str, group_name:str|None)->bool:
    """Odebere uživatele ze zadané skupiny.
    Args:
        username (str): jméno uživatele
        group_name (str|None): jméno skupiny, pokud je None, odebere uživatele ze všech skupin kromě své primární
    Returns:
        bool: True pokud vše ok
    Raises:
        RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při odebírání ze skupiny
    """
    homeDir = getUserHome(username)
    if not homeDir:
        raise RuntimeError(f"User {username} does not exist or has no home directory.")
    
    try:
        if group_name is None:
            groups = getUserGroups(username)
            pw = pwd.getpwnam(username)
            primary_gid = pw.pw_gid
            primary_group = grp.getgrgid(primary_gid).gr_name
            for g in groups:
                if g != primary_group:
                    subprocess.run([
                        "gpasswd",
                        "-d",
                        username,
                        g
                    ], check=True)
        else:
            if not checkUserInGroup(group_name):
                return True  # už tam není
            subprocess.run([
                "gpasswd",
                "-d",
                username,
                group_name
            ], check=True)
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to remove user {username} from group {group_name}: {e}")