import os,re,time,json,base64
import pwd
import subprocess
import helper as hlp
from typing import Union
import logging

BASE_DIR = "/home_sftp_users"
_SAFE_NAME_RGX = re.compile(r'^[a-zA-Z0-9._-]+$')

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
        
        # regexp na validaci jména mountpointu
        rgx = r'^[a-zA-Z0-9._-]+$'
        if not re.match(rgx, point):
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
            mp= os.path.join(self.__jailPath, self.mountName)
            with open("/proc/mounts","r") as f:
                for line in f:
                    parts=line.split()
                    if len(parts)>=2:
                        if parts[1].strip() == mp:
                            return True
        except Exception:
            return False
        return False
    
    def __repr__(self):
        return f"manifestMount(mountPoint='{self.mountName}', realPath='{self.realPath}') is OK: {self.isMountpointPathsOK()}"

class sftpUserMng:
    """Třída pro správu SFTP uživatele v systému.
    Attributes:
        ok (bool): Pokud True tak inicializace proběhla v pořádku, tzn existuje a je součástí mechanismu
        error (str|None): Chybová hláška pokud ok je False
        username (str): Uživatelské jméno
        homeDir (str|None): Domovský adresář uživatele pokud existuje a je user ok
    """
    
    def __init__(self,username:str):
        """Inicializace sftpUserMng instance pro zadaného uživatele.
        Args:
            username (str): uživatelské jméno
        Raises:
            RuntimeError: pokud BASE_DIR začíná /home/ (není povoleno)
        """        
        if BASE_DIR.startswith("/home/"):
            raise RuntimeError(f"Base directory {BASE_DIR} cannot be under /home/.")
        
        self.ok:bool = False
        """Pokud True tak inicializace proběhla v pořádku, tzn existuje a je součástí mechanismu"""
        
        self.error:str|None = None
        """Chybová hláška pokud ok je False"""
        
        self.username:str = username
        """Uživatelské jméno"""
        
        self.homeDir:str|None = None
        """Domovský adresář uživatele pokud existuje a je user ok"""
        
        try:
            x=self.user_exists(username)
            if x:
                self.homeDir=self.getUserHome(username)
                if self.homeDir is None:
                    self.error="User home directory is outside of base dir."
                    return
            else:
                self.error="User does not exist."
                return
        except Exception as e:
            self.error=str(e)
            return
            
        self.mountpointFile:str = os.path.join(self.homeDir, ".sftp_mounts") if self.homeDir else ""
        """Cesta k mountpointům uživatele do jailu"""
        
        self.mountpoints:list[sftpUserMountpoint] = []
        """Seznam mountpointů uživatele"""
        
        # načteme mountpointy
        jailDir= self.ensureJail()
        try:
            if os.path.isfile(self.mountpointFile):
                with open(self.mountpointFile, "r") as f:
                    for line in f:
                        line=line.strip()
                        if line!="":
                            mp=sftpUserMountpoint(jailPath=jailDir, line=line, val=None)
                            self.mountpoints.append(mp)
        except Exception as e:
            self.error=f"Failed to load mountpoints: {e}"
            return
        
        # načteme certifikáty, je v home v souboru .sftp_certs co řádek to jeden certifikát, jako v 'authorized_keys'
        # je to v podstatě kopie, ale může mít jiný obsah než authorized_keys
        self.certificates:list[str] = []
        """Seznam certifikátů uživatele"""
        
        try:
            certs_file=os.path.join(self.homeDir, ".sftp_certs")
            if os.path.isfile(certs_file):
                with open(certs_file, "r") as f:
                    for line in f:
                        line=line.strip()
                        if line!="":
                            self.certificates.append(line)
                            
            self.ok=True                
        except Exception as e:
            self.error=f"Failed to load certificates: {e}"
            return
        
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

    @staticmethod
    def user_exists(username:str)->bool:
        """Zkontroluje, zda uživatel existuje v systému a je součástí tohoto sftp řešení.
        Args:
            username (str): uživatelské jméno
        Returns:
            bool: True pokud uživatel existuje, jinak False
        Raises:
            RuntimeError: pokud uživatel existuje, ale jeho domovský adresář je mimo BASE_DIR        
        """
        if hlp.userExists(username, checkWhiteSpace=False):
            x=sftpUserMng.getUserHome(username)
            # musí být součástí base dir jinak throw
            if not x:
                # toto by asi nastat nemělo ;) takže throw
                raise RuntimeError(f"User {username} exists but home directory cannot be determined.")
            if x and not x.startswith(BASE_DIR):
                raise RuntimeError(f"User {username} exists but home directory {x} is outside of base dir {BASE_DIR}.")
            return True
        return False
        
    @staticmethod
    def getUserHome(username:str)->str|None:
        """Získá domovský adresář uživatele pokud existuje a je pod BASE_DIR.
        Args:
            username (str): uživatelské jméno
        Returns:
            str|None: cesta k domovskému adresáři nebo None pokud uživatel neexistuje
        Raises:
            RuntimeError: pokud uživatel existuje, ale jeho domovský adresář je mimo BASE_DIR
        """
        x= hlp.getUserHome(username, checkWhiteSpace=False)
        if x and x.startswith(BASE_DIR):
            return x
        elif x:
            raise RuntimeError(f"User {username} exists but home directory {x} is outside of base dir {BASE_DIR}.")
        return None

    @staticmethod
    def create_user(username)->Union['sftpUserMng', None]:
        """Vytvoří systémového uživatele pokud neexistuje s daným jménem, pokud ještě neexistuje.
        Args:
            username (str): uživatelské jméno
        Returns:
            sftpUserMng: instance sftpUserMng pro vytvořeného uživatele
        Raises:
            RuntimeError: pokud se vytvoření uživatele nezdaří
        """
        u=sftpUserMng.__create_user(username)
        if u and u.ok:
            u.ensureJail()
            return u
        return None
        
    @staticmethod
    def __create_user(username)->'sftpUserMng':
        # pokud je basedir začíná /home/ tak chyba, je to mechanismus pro sftp uživatele        
        try:
            u=sftpUserMng.user_exists(username)
            if u:
                return sftpUserMng(username)
        except Exception as e:
            raise RuntimeError(f"Cannot create user {username}: {e}")
        
        home_path = os.path.join(BASE_DIR, username)

        # useradd needs base directory to exist
        if not os.path.exists(BASE_DIR):
            try:
                os.makedirs(BASE_DIR, exist_ok=True)
            except Exception as e:
                raise RuntimeError(f"Failed to create base directory {BASE_DIR}: {e}")
        try:
            os.chown(BASE_DIR, 0, 0)
            os.chmod(BASE_DIR, 0o755)
        except Exception as e:
            raise RuntimeError(f"Failed to create base directory {BASE_DIR}: {e}")

        try:
            subprocess.run([
                "useradd",
                "-m",
                "-d", home_path,
                "-s", "/usr/sbin/nologin",
                username
            ], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create user {username}: {e}")

        try:
            _ = sftpUserMng.getUserHome(username)
        except KeyError:
            raise RuntimeError(f"User {username} was not created successfully.")

        # useradd vytvoří /user/someuser pod rootem, ALE někdy nechá špatné vlastníky
        # → proto to raději pojišťujeme na root:root 755
        try:
            os.chown(home_path, 0, 0)
            os.chmod(home_path, 0o755)
        except Exception as e:
            raise RuntimeError(f"Failed to set ownership/permissions for {home_path}: {e}")

        return sftpUserMng(username)
    
    def ensureJail(self)->str:
        """Zajistí, že uživatel má vytvořený jail adresář.
        Returns:
            str: cesta k jail adresáři
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při vytváření jail adresáře
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
               
        jail_dir = os.path.join(self.homeDir, "__sftp__")
        try:
            os.makedirs(jail_dir, exist_ok=True)
            try:
                pw = pwd.getpwnam(self.username)
                os.chown(jail_dir, pw.pw_uid, pw.pw_gid)
                os.chmod(jail_dir, 0o755)
                return jail_dir
            except KeyError:
                raise RuntimeError(f"Cannot set ownership for jail directory, user {self.username} does not exist.")
        except Exception as e:
            raise RuntimeError(f"Failed to create jail directory for user {self.username}: {e}")

    def _ensureSSHDir(self)->str:
        """Zajistí, že uživatel má ve svém domovském adresáři vytvořený adresář .ssh.
        Returns:
            str: cesta k adresáři .ssh        
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při vytváření adresáře
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
               
        ssh_dir = os.path.join(self.homeDir, ".ssh")
        try:
            os.makedirs(ssh_dir, exist_ok=True)
            try:
                pw = pwd.getpwnam(self.username)
                os.chown(ssh_dir, pw.pw_uid, pw.pw_gid)
                os.chmod(ssh_dir, 0o700)
                return ssh_dir
            except KeyError:
                raise RuntimeError(f"Cannot set ownership for .ssh directory, user {self.username} does not exist.")
        except Exception as e:
            raise RuntimeError(f"Failed to create .ssh directory for user {self.username}: {e}")

    def myCertExists(self, cert:str)->bool:
        """Zkontroluje, zda uživatel má zadaný certifikát ve svém seznamu certifikátů.
        Args:
            cert (str): certifikát
        Returns:
            bool: True pokud certifikát existuje, jinak False
        Raises:
            RuntimeError: pokud uživatel není správně inicializován
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        return cert in self.certificates
    
    def save_myCerts(self)->None:
        """Uloží aktuální seznam certifikátů uživatele do souboru.
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při ukládání certifikátů
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        try:
            certs_file=os.path.join(self.homeDir, ".sftp_certs")
            with open(certs_file, "w") as f:
                for c in self.certificates:
                    f.write(c + "\n")
            pw = pwd.getpwnam(self.username)
            os.chown(certs_file, pw.pw_uid, pw.pw_gid)
            os.chmod(certs_file, 0o600)
        except Exception as e:
            raise RuntimeError(f"Failed to save certificates for user {self.username}: {e}")
    
    def __addMyCert(self, cert:str)->None:
        """Přidá zadaný certifikát do seznamu certifikátů uživatele.
        Args:
            cert (str): certifikát
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při přidávání certifikátu
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        if cert not in self.certificates:
            self.certificates.append(cert)
            self.save_myCerts()
    
    def deleteMyCert(self, cert:str)->None:
        """Odstraní zadaný certifikát ze seznamu certifikátů uživatele.
        Args:
            cert (str): certifikát
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání certifikátu
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        if cert in self.certificates:
            self.certificates.remove(cert)
            self.save_myCerts()

    def ensure_ssh_key(self,public_key:str)->str:
        """Zajistí, že uživatel má ve svém domovském adresáři nainstalovaný zadaný veřejný SSH klíč.
        Args:
            public_key (str): veřejný SSH klíč
        Returns:
            str: cesta k souboru s autorizovanými klíči
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při instalaci klíče
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
               
        ssh_dir = self._ensureSSHDir()
        ak_file = os.path.join(ssh_dir, "authorized_keys")        

        # načteme existující klíče (pokud nějaké jsou) a přidáme nový, pokud tam ještě není
        existing_keys = set()
        if os.path.exists(ak_file):
            with open(ak_file, "r") as f:
                for line in f:
                    existing_keys.add(line.strip())
        # přidáme nový klíč, pokud tam ještě není
        if public_key.strip() not in existing_keys:
            existing_keys.add(public_key.strip())
            
        try:    
            with open(ak_file, "w") as f:
                for key in existing_keys:
                    f.write(key + "\n")
            pw = pwd.getpwnam(self.username)
            os.chown(ak_file, pw.pw_uid, pw.pw_gid)
            os.chmod(ak_file, 0o600)
            
            # přidáme do seznamu certifikátů pokud tam ještě není
            self.__addMyCert(public_key.strip())
            
        except Exception as e:
            raise RuntimeError(f"Failed to write authorized_keys for user {self.username}: {e}")

        return ak_file
    
    def ensure_ssh_key_file(self, key_file:str)->str:
        """Zajistí, že uživatel má ve svém domovském adresáři nainstalovaný veřejný SSH klíč ze zadaného souboru.
        Args:
            key_file (str): cesta k souboru s veřejným SSH klíčem
        Returns:
            str: cesta k souboru s autorizovanými klíči
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při instalaci klíče
        """
        if not os.path.isfile(key_file):
            raise RuntimeError(f"SSH key file {key_file} does not exist.")
        
        with open(key_file, "r") as f:
            public_key = f.read().strip()
        
        return self.ensure_ssh_key(public_key)

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
                    self.__deleteOneMountpoint(mp)
                    self.__saveMountpoints()
                    break  # pokračujeme v tvorbě nového mountpointu
        
        jail_dir = self.ensureJail()
        mp = sftpUserMountpoint(jailPath=jail_dir, line=mount_name, val=real_path)
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

    def __deleteOneMountpoint(self, mount_point:sftpUserMountpoint)->None:
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
        
        try:
            if mount_point.isMounted():
                # zkontrolujeme, zda je možné bezpečně odmountovat
                if not self.__can_umount(mount_point.mountPath):
                    raise RuntimeError(f"Mountpoint {mount_point.mountName} is busy and cannot be unmounted.")
                subprocess.run(["umount", mp_to_delete.mountPath], check=True)
            if mp_to_delete.mountExists():
                os.rmdir(mp_to_delete.mountPath)
                
            self.mountpoints.remove(mp_to_delete)
            self.__saveMountpoints() # jen pokud nic neselže jinak znovu proběhnou kroky výše
        except Exception as e:
            raise RuntimeError(f"Failed to delete mountpoint {mount_point.mountName} for user {self.username}: {e}")
            

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
                self.__deleteOneMountpoint(mp)
        else:
            mp=self.getMountpointByName(mount_name)
            if mp is None:
                raise RuntimeError(f"Mountpoint {mount_name} does not exist for user {self.username}.")
            self.__deleteOneMountpoint(mp)
            
    def deleteSSHKey(self, public_key:str|list[str])->None|str:
        """Odstraní zadaný veřejný SSH klíč ze souboru authorized_keys uživatele.
        Args:
            public_key (str): veřejný SSH klíč
        Returns:
            None|str: None pokud vše ok, jinak seznam chyba - nekritická
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání klíče
        """
        
        ak_file = os.path.join( self._ensureSSHDir(), "authorized_keys")
        if not os.path.exists(ak_file):
            return "authorized_keys file does not exist."

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
                        
            self.deleteMyCert(public_key.strip())
                        
        except Exception as e:
            raise RuntimeError(f"Failed to delete SSH key for user {self.username}: {e}")
        
        return None
    
    def delete_ssh_key_file(self, key_file:str)->None|str:
        """Odstraní ze souboru authorized_keys uživatele veřejný SSH klíč ze zadaného souboru.
        Args:
            key_file (str): cesta k souboru s veřejným SSH klíčem
        Returns:
            None|str: None pokud vše ok, jinak seznam chyba - nekritická
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání klíče
        """
        if not os.path.isfile(key_file):
            raise RuntimeError(f"SSH key file {key_file} does not exist.")
        
        with open(key_file, "r") as f:
            public_key = f.read().strip()
        
        return self.deleteSSHKey(public_key)

    def __killUserProcesses(self)->None:
        """Zabije všechny procesy patřící uživateli.
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při zabíjení procesů
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        try:
            # otestujeme existenci loginctl
            subprocess.run(["loginctl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run([
                "loginctl",
                "terminate-user",
                self.username
            ])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to terminate user {self.username} sessions: {e}")
        
        try:
            subprocess.run([
                "pkill",
                "-u",
                self.username
            ], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to kill processes for user {self.username}: {e}")
        
        time.sleep(1)  # počkáme chvíli, aby se procesy stihly ukončit
        
        # ověření
        proc = subprocess.run(["pgrep", "-u", self.username], stdout=subprocess.PIPE)
        if proc.stdout.strip():
            raise RuntimeError(f"Some processes of {self.username} are still running.")

    @staticmethod
    def __can_umount(path: str) -> bool:
        if not os.path.ismount(path):
            return True
        proc = subprocess.run(
            ["lsof", "+f", "--", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return (proc.stdout.strip() == b"") and (proc.returncode in (0,1))

    def __umount_will_be_ok(self) -> bool:
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
                if not sftpUserMng.__can_umount(mp.mountPath):
                    return False
        return True

    def delete_user(self)->None:
        """Odstraní systémového uživatele a jeho domovský adresář.
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání uživatele
        """
        if not self.ok or not self.homeDir:
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        try:
            # zabijeme všechny procesy uživatele
            self.__killUserProcesses()
            
            # zkontrolujeme zda je možné bezpečně odmountovat všechny mountpointy
            if not self.__umount_will_be_ok():
                raise RuntimeError(f"Cannot delete user {self.username} because some mountpoints are busy.")
            
            # smažeme mountpointy
            self.deleteMountpoint(None)
            
            # odstraníme certifikáty
            deepCpy = self.certificates.copy()
            for cert in deepCpy:
                self.deleteMyCert(cert)
            
            # odstraníme uživatele, je to sftp managovaný jen pro sftp takže se může smazat komplet s home
            try:
                subprocess.run([
                    "userdel",
                    "-r",
                    self.username
                ], check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to delete user {self.username}: {e}")            
        except Exception as e:
            raise RuntimeError(f"Failed to delete user {self.username}: {e}")

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

    @staticmethod
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
        
        b=bool(_SAFE_NAME_RGX.match(name))
        if throw and not b:
            raise err
        return b

    @staticmethod
    def createUserFromJson(file:str, log:logging.Logger)->Union[list['sftpUserMng']|None]:
        """Vytvoří uživatele ze zadaného json souboru
        Musí mít root property:
        - `sftpuser` (string) a v něm uživatelské jméno
        - `sftpmounts` (optional object) je objekt kde:
            - každý klíč je jméno mountpointu v jailu
            - každá hodnota je reálná cesta k umístění
        - `sftpcerts` (optional array) je string[] pole certifikátů
            POZOR hodnota může začínat "b64:..." což znamená že je certifikát base64 zakódován
        
        POZOR pokud je root parametr `users` tak se jedná o pole uživatelů
            kde se uživatel stane rootem výše uvedených property
        
        Args:
            file (str): cesta k json souboru
        Returns:
            list[sftpUserMng]: seznam vytvořených uživatelů
            None pokud se vytvoření uživatelů nezdaří
        """
        
        if not os.path.isfile(file):
            log.error(f"JSON file {file} does not exist.")
            return None
        
        try:
            with open(file, "r") as f:
                d=json.load(f)
        except Exception as e:
            log.error(f"Failed to load JSON file {file}: {e}")
            log.exception(e)
            return None
        
        users=[]
        ret=[]
        if "users" in d and isinstance(d["users"], list):
            for udata in d["users"]:
                users.append(udata)
        else:
            users.append(d)
        
        log.info(f"Creating {len(users)} SFTP users from JSON file {file}.")
        for data in users:
            try:
                log.info(f"Processing user data: {data}")
                if "sftpuser" not in data or not isinstance(data["sftpuser"], str):
                    log.error(f"Invalid JSON format: missing 'sftpuser' string property.")
                    continue
                
                username=str(data["sftpuser"])
                sftpUserMng.safeName(username,throw=True)
                
                if sftpUserMng.user_exists(username):
                    log.info(f"User {username} already exists, skipping creation.")
                    u=sftpUserMng(username)
                    ret.append(u)
                    continue
                
                # vytvoříme uživatele
                u=sftpUserMng.create_user(username)
                if u is None or not u.ok:
                    log.error(f"Failed to create user {username}.")
                    continue                    
                
                # přidáme mountpointy
                log.info(f"Adding mountpoints for user {username}.")
                if "sftpmounts" in data and isinstance(data["sftpmounts"], dict):
                    for mount_name, real_path in data["sftpmounts"].items():
                        if not isinstance(mount_name, str) or not isinstance(real_path, str):
                            log.error(f"Invalid mountpoint entry for user {username}: mount_name and real_path must be strings.")
                            continue
                        sftpUserMng.safeName(mount_name,throw=True)
                        if not os.path.isabs(real_path):
                            log.error(f"Invalid mountpoint real path for user {username}: path must be absolute.")
                            continue
                        if not os.path.exists(real_path):
                            log.error(f"Mountpoint real path does not exist for user {username}: {real_path}.")
                            continue
                        u.ensure_mountpoint(mount_name, real_path)
                else:
                    log.info(f"No mountpoints to add for user {username}.")
                
                # přidáme certifikáty
                log.info(f"Adding certificates for user {username}.")
                if "sftpcerts" in data and isinstance(data["sftpcerts"], list):                    
                    for cert in data["sftpcerts"]:
                        if not isinstance(cert, str):
                            log.error(f"Invalid certificate entry for user {username}: certificate must be a string.")
                            continue
                        cert=cert.strip()
                        if cert.startswith("b64:"):
                            b64_data=cert[4:]
                            try:
                                decoded_bytes=base64.b64decode(b64_data)
                                cert=decoded_bytes.decode("utf-8").strip()
                            except Exception as e:
                                log.error(f"Failed to decode base64 certificate for user {username}: {e}")
                                log.exception(e)
                                continue
                        if not re.match(r'^(ssh-|ecdsa-)', cert):
                            log.error(f"Invalid certificate format for user {username}: certificate must start with 'ssh-' or 'ecdsa-'.")
                            continue
                        u.ensure_ssh_key(cert)
                else:
                    log.info(f"No certificates to add for user {username}.")
                    
                ret.append(u)
            except Exception as e:
                log.error(f"Failed to create user from JSON data: {e}")
                log.exception(e)
        
        if len(ret) == 0:
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
                        u = sftpUserMng(username)
                        if u.ok:
                            users.append(u)
                except Exception:
                    continue
        except Exception as e:
            return None
        return users
    
    @staticmethod
    def createJson(file:str,overwrite:bool, log:logging.Logger)->bool:
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
            users = sftpUserMng.listActiveUsers()
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
                    user_data["sftpmounts"][mp.mountName] = mp.realPath
                data["users"].append(user_data)
            except Exception as e:
                log.error(f"Failed to process user {u.username} for JSON export: {e}")
                log.exception(e)
                continue
        
        try:
            with open(file, "w") as f:
                json.dump(data, f, indent=4, sort_keys=True)
            log.info(f"Successfully created JSON file {file} with {len(users)} users.")
        except Exception as e:
            log.error(f"Failed to create JSON file {file}: {e}")
            log.exception(e)
            return False
        
        return True
