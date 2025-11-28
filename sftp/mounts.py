from ..helper import getLogger
log = getLogger("sftpMountsMng")

import os,time
import grp
import subprocess
from libs.JBLibs.sftp.mountPoint import sftpUserMountpoint
import libs.JBLibs.sftp.ssh as ssh
from libs.JBLibs.sftp.glob import SAFE_NAME_RGX
from libs.JBLibs.helper import getLogger,userExists,getUserHome
from .userGrps import getUserGroups, addUSerToGroup
from . import sambaPoint as smb

FSTAB_DIR:str = "/etc/fstab.d"   # per-user fstab soubory
MOUTPOINT_FILENAME:str = ".sftp_mounts_mng"  # název souboru s mountpointy v home adresáři uživatele

class mountpointsManager:
    def __init__(self, username:str):
        self.log = getLogger("sftpMountsMng")
        self.username = username
        self.ok:bool = False
        
        if not userExists(self.username):
            self.log.error(f"User {self.username} does not exist.")
            return        
        
        self.homeDir:str|None = getUserHome(self.username)
        """Cesta k home adresáři uživatele"""
        
        if not self.homeDir:
            self.log.error(f"Cannot determine home directory for user {self.username}.")
            return
        
        self.mountpointFile:str = os.path.join(self.homeDir, MOUTPOINT_FILENAME) if self.homeDir else ""
        """Cesta k mountpointům uživatele do jailu"""
        
        self.mountpoints:list[sftpUserMountpoint] = []
        """Seznam mountpointů uživatele"""        


        # načteme mountpointy
        jailDir= ssh.ensureJail(self.username)
        try:
            if os.path.isfile(self.mountpointFile):
                with open(self.mountpointFile, "r") as f:
                    for line in f:
                        line=line.strip()
                        if line!="":
                            mp=sftpUserMountpoint(jailPath=jailDir, line=line, val=None)
                            self.mountpoints.append(mp)
        except Exception as e:
            self.moundpoinstOK=False
            self.error=f"Failed to load mountpoints: {e}. "
            return

        self.ok=True 
    
    def deleteOneMountpoint(self, mount_point:sftpUserMountpoint)->None:
        """Odstraní mountpoint s daným jménem z uživatelova jailu.
        Args:
            mount_point (sftpUserMountpoint): mountpoint k odstranění
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání mountpointu
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        if not isinstance(mount_point, sftpUserMountpoint):
            raise RuntimeError(f"Invalid mountpoint provided for deletion.")

        # zkontrolujeme existenci mountpointu
        mp_to_delete = None
        for mp in self.mountpoints:
            if mp.mountName == mount_point.mountName and mp.realPath == mount_point.realPath:
                mp_to_delete = mp
                break
        if mp_to_delete is None:
            raise RuntimeError(f"Mountpoint {mount_point.mountName} does not exist for user {self.username}.")
        
        if mp_to_delete.isSambaVault():
            # smažeme mountpoint přes sambu
            try:
                smb.removeSharePoint(self.username, mp_to_delete)
            except Exception as e:
                raise RuntimeError(f"Failed to delete Samba mountpoint {mount_point.mountName} for user {self.username}: {e}")
        
        else:
            try:
                if mount_point.isMounted():
                    # zkontrolujeme, zda je možné bezpečně odmountovat
                    if not can_umount(mount_point.mountPath):
                        raise RuntimeError(f"Mountpoint {mount_point.mountName} is busy and cannot be unmounted.")
                    try:
                        subprocess.run(["umount", mp_to_delete.mountPath], check=True)
                    except subprocess.CalledProcessError as e:
                        log.debug(f"Initial umount failed for {mp_to_delete.mountPath}, retrying after delay")
                        time.sleep(2)  # počkáme chvíli a zkusíme to znovu
                        subprocess.run(["umount", mp_to_delete.mountPath], check=True)
                        
                
                if mp_to_delete.mountExists():
                    os.rmdir(mp_to_delete.mountPath)
                    
                self.mountpoints.remove(mp_to_delete)
                self.__saveMountpoints() # jen pokud nic neselže jinak znovu proběhnou kroky výše
            except Exception as e:
                raise RuntimeError(f"Failed to delete mountpoint {mount_point.mountName} for user {self.username}: {e}")
 
    def umount_will_be_ok(self) -> bool:
        """Zkontroluje, zda je možné bezpečně odmountovat všechny mountpointy uživatele.
        Returns:
            bool: True pokud je možné bezpečně odmountovat všechny mountpointy, jinak False
        Raises:
            RuntimeError: pokud uživatel není správně inicializován
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        for mp in self.mountpoints:
            if os.path.ismount(mp.mountPath):
                if not can_umount(mp.mountPath):
                    return False
        return True
    
    def getMountpointByName(self, mount_name:str)->sftpUserMountpoint|None:
        """Získá mountpoint podle jména.
        Args:
            mount_name (str): jméno mountpointu v jailu
        Returns:
            sftpUserMountpoint|None: instance mountpointu pokud existuje, jinak None
        Raises:
            RuntimeError: pokud uživatel není správně inicializován
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        for mp in self.mountpoints:
            if mp.mountName == mount_name:
                return mp
        return None
    
    def ensure_samba_mountpoint(self, mount_name:str, real_path:str)->sftpUserMountpoint:
        """Zajistí, že uživatel má ve svém jailu vytvořený mountpoint pro zadanou reálnou cestu přes sambu (CIFS).
        Args:
            mount_name (str): jméno mountpointu v jailu
            real_path (str): reálná cesta k umístění
        Returns:
            sftpUserMountpoint: instance sftpUserMountpoint pro vytvořený mountpoint
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při vytváření mountpointu
        """
        self.__ensure_x_mountpoint(mount_name, real_path, sambaVault=True)
        
    def ensure_mountpoint(self, mount_name:str, real_path:str)->sftpUserMountpoint:
        """Zajistí, že uživatel má ve svém jailu vytvořený mountpoint pro zadanou reálnou cestu.
        Args:
            mount_name (str): jméno mountpointu v jailu
            real_path (str): reálná cesta k umístění
        Returns:
            sftpUserMountpoint: instance sftpUserMountpoint pro vytvořený mountpoint
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při vytváření mountpointu
        """
        self.__ensure_x_mountpoint(mount_name, real_path, sambaVault=False)
        
        
    def __ensure_x_mountpoint(self, mount_name:str, real_path:str, sambaVault:bool)->sftpUserMountpoint:
        """Zajistí, že uživatel má ve svém jailu vytvořený mountpoint pro zadanou reálnou cestu.
        Args:
            mount_name (str): jméno mountpointu v jailu
            real_path (str): reálná cesta k umístění
            sambaVault (bool): zda vytvořit mountpoint přes sambu (CIFS) nebo bindem
        Returns:
            sftpUserMountpoint: instance sftpUserMountpoint pro vytvořený mountpoint
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při vytváření mountpointu
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")

        # otestujeme jestli už mountpoint neexistuje
        for mp in self.mountpoints:
            if mp.mountName == mount_name:
                if mp.realPath != real_path:
                    raise RuntimeError(f"Mountpoint {mount_name} already exists with different real path {mp.realPath}.")
                if mp.isMounted():
                    return mp
                else:
                    # mountpoint existuje ale není namountován, smažeme ho a vytvoříme znovu
                    self.deleteOneMountpoint(mp)
                    self.__saveMountpoints()
                    break  # pokračujeme v tvorbě nového mountpointu
        
        jail_dir = ssh.ensureJail(self.username)
        mp = sftpUserMountpoint(jailPath=jail_dir, line=mount_name, val=real_path,sambaVault=sambaVault)
        if sambaVault:
            # vytvoříme mountpoint přes sambu
            try:
                smb.ensureMountpoint(self.username,mp)
            except Exception as e:
                raise RuntimeError(f"Failed to create Samba mountpoint {mount_name} for user {self.username}: {e}")
        else:            
            mp.ensureMountpoint(self.username)
            
            # pokusíme se vytvořit bind mount
            try:
                subprocess.run([
                    "mount",
                    "--bind",
                    real_path,
                    mp.mountPath
                ], check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to bind mount {real_path} to {mount_name}: {e}")
        
        self.mountpoints.append(mp)
        self.__saveMountpoints()
        
        return mp
    
    def __saveMountpoints(self):
        """Uloží aktuální mountpointy uživatele do manifestu.
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při ukládání
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        try:
            with open(self.mountpointFile, "w") as f:
                for mp in self.getMountpoints():
                    f.write(mp.getLine() + "\n")
        except Exception as e:
            raise RuntimeError(f"Failed to save mountpoints for user {self.username}: {e}")    
        
    def deleteMountpoint(self, mount_name:str|None)->None:
        """Odstraní mountpoint s daným jménem z uživatelova jailu.
        Args:
            mount_name (str|None): jméno mountpointu v jailu, pokud zadáme None, smaže všechny mountpointy
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání mountpointu
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        if mount_name is None:
            for mp in self.mountpoints[:]:  # kopie seznamu pro bezpečné mazání během iterace
                self.deleteOneMountpoint(mp)
        else:
            mp=self.getMountpointByName(mount_name)
            if mp is None:
                raise RuntimeError(f"Mountpoint {mount_name} does not exist for user {self.username}.")
            self.deleteOneMountpoint(mp)        
        
    def getMountpoints(self)->list[sftpUserMountpoint]:
        """Získá seznam mountpointů uživatele.
        Returns:
            list[sftpUserMountpoint]: seznam mountpointů uživatele
        Raises:
            RuntimeError: pokud uživatel není správně inicializován
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        return list(self.mountpoints)
    
    def ensureMountPointUserGroups(self)->list[str]:
        """Zajistí, že uživatel má přístup k mountpointům pro zadané skupiny.
        Returns:
            list[str]: seznam jmen skupin, které mají přístup k mountpointům
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při nastavování přístupů
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        curGroups: list[str] = getUserGroups(self.username)
        group_names: list[str] = []
        for mp in self.getMountpoints():
            # zjistíme skupinu na fizické cestě adresáře přes os
            try:
                stat_info = os.stat(mp.realPath)
                gid = stat_info.st_gid
                group_info = grp.getgrgid(gid)
                group_name = group_info.gr_name
                group_names.append(group_name)
                if group_name not in curGroups:
                    addUSerToGroup(self.username, group_name)
            except Exception as e:
                raise RuntimeError(f"Failed to ensure mountpoint user groups for user {self.username}: {e}")

    

def write_fstab(username, mounts: dict):
    """
    mounts: { name: {src: ..., dst: ..., group: ...}, ... }
    """
    os.makedirs(FSTAB_DIR, exist_ok=True)
    fstab_file = os.path.join(FSTAB_DIR, f"sftp-{username}.fstab")

    with open(fstab_file, "w") as f:
        for name, pair in mounts.items():
            src = pair["src"]
            dst = pair["dst"]
            f.write(f"{src} {dst} none bind 0 0\n")

    return fstab_file


def remove_fstab(username):
    fstab_file = os.path.join(FSTAB_DIR, f"sftp-{username}.fstab")
    if os.path.exists(fstab_file):        
        os.remove(fstab_file)

def can_umount(path: str) -> bool:
    if not os.path.ismount(path):
        return True
    proc = subprocess.run(
        ["lsof", "+f", "--", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return (proc.stdout.strip() == b"") and (proc.returncode in (0,1))

# test lsof existence, pokud není tak system exit 1 s chybovou hláškou jak instalovat, nevymýšlej neexistující funkce
try:
    subprocess.run(["lsof", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
except FileNotFoundError:
    print("Error: 'lsof' command not found. Please install 'sudo apt install lsof' package to use mountpoint management features.")
    import sys
    sys.exit(1)
