import os
import re
import pwd
from typing import Union

RGX_MOUNT_NAME = re.compile(r'^[a-zA-Z0-9._-]+$')

class sftpUserMountpoint:
    """Třída pro správu jednoho mountu v manifestu uživatele SFTP.
    Attributes:
        mountName (str): jméno adresáře v jailu
        mountPath (str): cesta k mountpointu v jailu včetně jména `mountName`
        realPath (str): Cesta k reálnému umístění
    """
    def __init__(self, jailPath:str, line:str, val:Union[str|None]=None, acceptSymlink:bool=False):
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
        
        if not RGX_MOUNT_NAME.match(point):
            raise ValueError(f"Invalid mount point name: {point}")
        
        if not os.path.isabs(path):
            raise ValueError(f"Mount real path must be absolute: {path}")
        
        self.mountName:str = point
        """Jen jméno mountpointu v jailu"""
        
        self.realPath:str = path
        """Cesta k reálnému umístění"""
        
        self.mountPath:str = os.path.join(self.__jailPath, self.mountName)
        """Cesta k mountpointu v jailu včetně jména `mountName` - full path"""
                
        if not self.__isDir(self.realPath):
            raise ValueError(
                f"Invalid realPath {self.realPath}: path must be an existing directory"
                + ("" if self.__symlinkAccepted else " and symlinks are not allowed")
            )            

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
        return f"{self.mountName}={self.realPath}"
    
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
        return os.path.isdir(os.path.join(self.__jailPath, self.mountName))
    
    def isMountpointPathsOK(self)->bool:
        """Zkontroluje, zda mountpoint a reálná cesta mountu existují.
        Returns:
            bool: True pokud oba existují, jinak False
        """
        return self.mountExists() and self.pathExists()
    
    def ensureMountpoint(self, userName:str)->str:
        """Zajistí, že mountpoint existuje, pokud ne, vytvoří ho.
        Args:
            userName (str): jméno uživatele pro nastavení vlastníka mountpointu a práv
        Returns:
            str: cesta k mountpointu
        Raises:
            RuntimeError: pokud se nepodaří vytvořit mountpoint
        """
        mp=os.path.join(self.__jailPath, self.mountName)
        
        if self.__isDir(mp):
            self.mountPath=mp
            return mp
                    
        if not self.__isDir(self.realPath):
            raise RuntimeError(f"Mount real path does not exist or is not a directory: {self.realPath}" +(self.__symlinkAccepted and "" or " (symlinks are not accepted)"))
                
        try:
            os.makedirs(mp, exist_ok=True)
            pw = pwd.getpwnam(userName)
            os.chown(mp, pw.pw_uid, pw.pw_gid)
            os.chmod(mp, 0o755)
            self.mountPath=mp
            return mp
        except Exception as e:
            raise RuntimeError(f"Failed to create mountpoint {mp}: {e}")
    
    def isMounted(self)->bool:
        """Zkontroluje, zda je mountpoint namountován.
        Returns:
            bool: True pokud je mountpoint namountován, jinak False
        """
        try:            
            mp= " " + os.path.join(self.__jailPath, self.mountName) + " "
            with open("/proc/mounts","r") as f:
                for line in f:
                    if mp in line:
                        return True
        except Exception:
            return False
        return False
    
    def __repr__(self):
        return f"manifestMount(mountPoint='{self.mountName}', realPath='{self.realPath}') is OK: {self.isMountpointPathsOK()}"