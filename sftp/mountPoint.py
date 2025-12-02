from libs.JBLibs.helper import getLogger
log = getLogger("sftpUserMountpoint")

import os
import re
import pwd
import grp
from typing import Union

RGX_MOUNT_NAME = re.compile(r'^[a-zA-Z0-9._-]+$')

class sftpUserMountpoint:
    """Třída pro správu jednoho mountu v manifestu uživatele SFTP.
    Attributes:
        mountName (str): jméno adresáře v jailu
        mountPath (str): cesta k mountpointu v jailu včetně jména `mountName`
        realPath (str): Cesta k reálnému umístění        
    """
    def __init__(
        self,
        jailPath:str,
        line:str,
        val:Union[str|None]=None,
        acceptSymlink:bool=False,
        sambaVault:bool=False,
        rw:bool=True,
        my:bool=False
    )->None:
        """Inicializace mountu ze zadaného řádku manifestu.
        Args:
            line (str): buď:
                - řádek manifestu ve formátu `mountPointName=realFullPath`  
                - anebo `mountPointName` mountpointu a pak ve `val` je `realFullPath`
            val (str|None): reálná cesta k umístění pokud `line` neobsahuje '='
            jailPath (str): cesta k jailu uživatele
            acceptSymlink (bool): pokud True, povolí se symlinky v reálné cestě nebo mountpointu
        Raises:
            ValueError: pokud řádek není ve správném formátu
        """
        self.__symlinkAccepted:bool = bool(acceptSymlink)
        """Pokud True, povolí se symlinky v reálné cestě nebo mountpointu"""        
        
        self.__jailPath = jailPath
        if not self.__isDir(self.__jailPath):
            raise ValueError(f"Jail path must be an existing directory: {self.__jailPath}")
        
        self.__sambaVault:bool = bool(sambaVault)
        """Pokud True, jedná se o mountpoint pro Samba Vault (speciální režim)"""
        
        pos= line.find("=")
        point=None
        path=None
        if pos==-1:
            # žádné '=' v řádku
            if not isinstance(val, str):
                 # musí být zadáno ve val
                raise ValueError(f"Invalid manifest mount line: {line}")
            else:
                # jinak je line jen jméno mountpointu a val je cesta
                point=line.strip()
                path=val.strip()
        else:
            # je '=' v řádku
            if val is not None:
                # nesmí být zadáno ve val, pokud je tak došlo k nějakému kritickému omylu
                raise ValueError(f"Invalid manifest mount line: {line}")
            # rozdělíme na jméno a cestu
            point=line[0:pos].strip()
            path=line[pos+1:].strip()
        
        # preventivní kontroly
        if not point or not path:
            raise ValueError(f"Invalid manifest mount line: {line}")
        
        # pokud point obsahuje jako první vykřičnéník tak je to mountpoint pro samba vault
        if point.startswith("!"):
            self.__sambaVault = True
            point = point[1:]  # odstraníme vykřičník z názvu mountpointu
        
        if not RGX_MOUNT_NAME.match(point):
            raise ValueError(f"Invalid mount point name: {point}")
        
        if not os.path.isabs(path):
            raise ValueError(f"Mount real path must be absolute: {path}")
        
        self.mountName:str = point
        """Jen jméno mountpointu v jailu"""
        
        self.realPath:str = path
        """Cesta k reálnému umístění"""
        
        self.__realPath_u:Union[tuple[str,int]] = None
        """Jméno a UID uživatele, kterému realPath patří"""
        
        self.__realPath_g:Union[tuple[str,int]] = None
        """Jméno a GID skupiny, které realPath patří"""
        
        self.mountPath:str = self.getMountPath()
        """Cesta k mountpointu v jailu včetně jména `mountName` - full path"""
                
        if not self.__isDir(self.realPath):
            raise ValueError(
                f"Invalid realPath {self.realPath}: path must be an existing directory"
                + ("" if self.__symlinkAccepted else " and symlinks are not allowed")
            )
            
        self.rw:bool = bool(rw)
        """Pokud True, jedná se o read-write mountpoint, jinak readonly"""
        
        self.my:bool = bool(my)
        """Pokud True, jedná se o mountpoint vlastněný uživatelem, jinak root"""

    def isSambaVault(self)->bool:
        """Zkontroluje, zda se jedná o mountpoint pro Samba Vault.
        Returns:
            bool: True pokud je to mountpoint pro Samba Vault, jinak False
        """
        return self.__sambaVault

    def __isDir(self, path:str)->bool:
        """Zkontroluje, zda zadaná cesta je adresář.
        v závislosti na self.symlinkAccepted buď povolí nebo zakáže symlinky.
        Args:
            path (str): cesta k ověření
        Returns:
            bool: True pokud je cesta adresář, jinak False
        """
        if self.__symlinkAccepted:
            return os.path.isdir(path)
        else:
            return os.path.isdir(path) and os.path.realpath(path) == os.path.abspath(path)
        
        
    def getLine(self)->str:
        """Získá řádek manifestu ve formátu `mountPoint=realFullPath`.
        Returns:
            str: řádek manifestu
        """
        prefix = "!" if self.__sambaVault else ""
        return f"{prefix}{self.mountName}={self.realPath}"
    
    def pathExists(self)->bool:
        """Zkontroluje, zda reálná cesta mountu existuje.
        Returns:
            bool: True pokud cesta existuje, jinak False
        """
        return os.path.isdir(self.realPath)
    
    def mountExists(self)->bool:
        """Zkontroluje, zda mountpoint existuje.
        Returns:
            bool: True pokud mountpoint existuje, jinak False
        """
        return os.path.isdir(self.getMountPath())
    
    def isMountpointPathsOK(self)->bool:
        """Zkontroluje, zda mountpoint a reálná cesta mountu existují.
        Returns:
            bool: True pokud oba existují, jinak False
        """
        return self.mountExists() and self.pathExists()
    
    def getMountPath(self)->str:
        """Získá plnou cestu k mountpointu v jailu.
        Returns:
            str: cesta k mountpointu v jailu
        """
        return os.path.join(self.__jailPath, self.mountName)
    
    def __ensureMountpointPathPermissions(self, path:str, userName:str)->None:
        """Nastaví vlastnictví a práva pro zadanou cestu mountpointu.
        Args:
            path (str): cesta k mountpointu
            userName (str): jméno uživatele pro nastavení vlastníka a práv
        Raises:
            RuntimeError: pokud se nepodaří nastavit vlastnictví nebo práva
        """
        try:            
            log.info(f"Setting ownership and permissions for mountpoint path {path}.")
            pw = pwd.getpwnam(userName)
            os.chown(path, pw.pw_uid, pw.pw_gid)
            # os.chmod(path, 0o755) + force gid permissions from parent jail
            os.chmod(path, 0o755 & ~0o020)
        except Exception as e:
            raise RuntimeError(f"Failed to set ownership/permissions for mountpoint path {path}: {e}")
    
    def ensureMountpoint(self, userName:str)->str:
        """Zajistí, že mountpoint existuje, pokud ne, vytvoří ho.
        Args:
            userName (str): jméno uživatele pro nastavení vlastníka mountpointu a práv
        Returns:
            str: cesta k mountpointu
        Raises:
            RuntimeError: pokud se nepodaří vytvořit mountpoint
        """
        mp=self.getMountPath()
        
        if self.__isDir(mp):
            self.__ensureMountpointPathPermissions(mp, userName)
            self.mountPath=mp
            return mp
                    
        if not self.__isDir(self.realPath):
            raise RuntimeError(f"Mount real path does not exist or is not a directory: {self.realPath}" +(self.__symlinkAccepted and "" or " (symlinks are not accepted)"))
                
        try:
            log.info(f"Creating mountpoint {mp} for user {userName}.")
            os.makedirs(mp, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create mountpoint {mp}: {e}")
    
        self.__ensureMountpointPathPermissions(mp, userName)        
        
        self.mountPath=mp
        return mp
    
    def isMounted(self)->bool:
        """Zkontroluje, zda je mountpoint namountován.
        Returns:
            bool: True pokud je mountpoint namountován, jinak False
        """
        try:
            mp= self.getMountPath()
            mp= f" {mp} "
            with open("/proc/mounts","r") as f:
                for line in f:
                    if mp in line:
                        return True
        except Exception as e:
            return False
        return False
    
    def forUser(self)->tuple[str,int]:
        """Získá jméno a UID uživatele, realPath patří.
        Returns:
            tuple[str,int]: jméno uživatele a jeho UID
        """
        if self.__realPath_u is None:
            st = os.stat(self.realPath)
            pw = pwd.getpwuid(st.st_uid)
            self.__realPath_u = (pw.pw_name, pw.pw_uid)
        return self.__realPath_u
        
    def forGroup(self)->tuple[str,int]:
        """Získá jméno a GID skupiny, které realPath patří.
        Returns:
            tuple[str,int]: jméno skupiny a její GID
        """
        if self.__realPath_g is None:
            st = os.stat(self.realPath)
            gr = grp.getgrgid(st.st_gid)
            self.__realPath_g = (gr.gr_name, gr.gr_gid)
        return self.__realPath_g
    
    def __repr__(self):
        return f"manifestMount(mountPoint='{self.mountName}', realPath='{self.realPath}') is OK: {self.isMountpointPathsOK()}"