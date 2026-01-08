from ..helper import getLogger
log= getLogger("sftp.User")

import os,time
from ..input import confirm
import pwd
import subprocess
from ...JBLibs import helper as hlp
from typing import Union
import libs.JBLibs.sftp.ssh as ssh
import grp
from .glob import BASE_DIR
from .mounts import mountpointsManager
from .userCerts import userCertsManager
from .userGrps import deleteUserFromGroup
from .ssh import remove_sshd_config

class sftpUserMng:
    """Třída pro správu SFTP uživatele v systému.
    Attributes:
        ok (bool): Pokud True tak inicializace proběhla v pořádku, tzn existuje a je součástí mechanismu
        error (str|None): Chybová hláška pokud ok je False
        username (str): Uživatelské jméno
        homeDir (str|None): Domovský adresář uživatele pokud existuje a je user ok
    """
    
    def __init__(self,username:str, testOnly:bool=False):
        """Inicializace sftpUserMng instance pro zadaného uživatele.
        Args:
            username (str): uživatelské jméno
            testOnly (bool): pokud True, tak se neinicializují mountpointy a certifikáty
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
                    
        self.ok=True # tady jsme už vpodstatě OK
        
        self.mountpointManager=mountpointsManager(username, testonly=testOnly)
        """Správce mountpointů uživatele"""    
    
        self.moundpoinstOK:bool = self.mountpointManager.ok
        """Pokud True tak se podařilo načíst mountpointy správně"""
        
        self.certificateManager=userCertsManager(username)
        """Správce certifikátů uživatele"""
        
        self.certificatesOK:bool = self.certificateManager.ok
        """Pokud True tak se podařilo načíst certifikáty správně"""
        
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
            ssh.ensureJail(username)
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
            pass

        time.sleep(1)  # počkáme chvíli, aby se procesy stihly ukončit
        
        try:
            subprocess.run([
                "pkill",
                "-u",
                self.username
            ], check=True)
        except subprocess.CalledProcessError as e:
            pass
        
        time.sleep(1)  # počkáme chvíli, aby se procesy stihly ukončit
        
        # ověření
        proc = subprocess.run(["pgrep", "-u", self.username], stdout=subprocess.PIPE)
        if proc.stdout.strip():
            raise RuntimeError(f"Some processes of {self.username} are still running.")

    def __delete_jail(self, queryNoEmpty:bool=True)->bool:
        """Odstraní pouze domovský adresář uživatele.  
        Nepoužívat, používá se interně při mazání uživatele.
            
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání domovského adresáře
        """
        try:
            # teď by měly být mountpointy pryč a adresář prázdný, pokud ne tak tam někdo něco vytvořil mimo pointy a 
            # mohou to být důležité data, takže dotaz
            jailPath = ssh.ensureJail(self.username, testOnly=True)
            if jailPath and os.path.exists(jailPath) and os.listdir(jailPath) and queryNoEmpty:
                log.warning(f"Jail directory {jailPath} of user {self.username} is not empty after removing mountpoints.")
                if not confirm(f"Home directory {jailPath} is not empty after removing mountpoints. Do you want to continue deleting the user and its home directory?\nThis will remove all data in the home directory. (y/n): "):
                    msg=f"User deletion for {jailPath} was cancelled by user due to non-empty home directory."
                    log.warning(msg)
                    return False
            # odstraníme home
            log.info(f"Deleting jail directory {jailPath} of user {self.username}.")
            if os.path.exists(jailPath):
                os.rmdir(jailPath)
            return True
        except Exception as e:
            log.error(f"Failed to delete home directory {self.homeDir} of user {self.username}: {e}")
            log.exception(e)
            return False
        
    def __cleanupSSHFiles(self)->None:
        """Odstraní zbytky po ssh konfiguraci, tzn známé soubory a adresáře.
        """
        if not self.ok or not self.homeDir:
            log.error(f"User {self.username} cannot cleanup SSH files because it is not properly initialized.")
            return
        
        files=[
            ".ssh/authorized_keys",
            ".sftp_certs",
        ]
        
        for f in files:
            path = os.path.join(self.homeDir, f)
            try:
                if os.path.exists(path):
                    log.info(f"Removing SSH related file {path} for user {self.username}.")
                    os.remove(path)
            except Exception as e:
                log.warning(f"Failed to remove SSH related file {path} for user {self.username}: {e}")
                log.exception(e)
                
        ssh_dir = os.path.join(self.homeDir, ".ssh")
        try:
            log.info(f"Removing SSH directory {ssh_dir} for user {self.username}.")
            if os.path.exists(ssh_dir) and os.path.isdir(ssh_dir):
                os.rmdir(ssh_dir)
        except Exception as e:
            log.warning(f"Failed to remove SSH directory {ssh_dir} for user {self.username}: {e}")
            log.exception(e)

    def delete_user(self)->None:
        """Odstraní systémového uživatele a jeho domovský adresář.
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání uživatele
        """
        if not self.ok or not self.homeDir:
            log.error(f"User {self.username} cannot be deleted because it is not properly initialized.")
            raise RuntimeError(f"User {self.username} is not properly initialized.")
        
        try:
            # zabijeme všechny procesy uživatele
            log.info(f"Killing all processes for user {self.username} before deletion.")
            self.__killUserProcesses()
            
            # zkontrolujeme zda je možné bezpečně odmountovat všechny mountpointy
            log.info(f"Checking if mountpoints can be safely unmounted for user {self.username}.")
            if not self.mountpointManager.umount_will_be_ok():
                log.error(f"Cannot delete user {self.username} because some mountpoints are busy.")
                raise RuntimeError(f"Cannot delete user {self.username} because some mountpoints are busy.")
            
            # smažeme mountpointy
            log.info(f"Deleting all mountpoints for user {self.username}.")
            self.mountpointManager.deleteMountpoint(None)
            
            if not self.__delete_jail(queryNoEmpty=True):
                raise RuntimeError(f"Failed to delete jail for user {self.username}.")
            
            # teď je možné smazat mount list
            log.info(f"Finishing cleanup of mountpoints for user {self.username}.")
            try:
                fl=os.path.join(self.homeDir, ".sftp_mounts_mng")
                if os.path.exists(fl):
                    os.remove(fl)
            except Exception as e:
                log.warning(f"Failed to remove mountpoints management file for user {self.username}: {e}")
                log.exception(e)
                raise RuntimeError(f"Failed to remove mountpoints management file for user {self.username}: {e}")
            
            # odstraníme certifikáty
            log.info(f"Deleting all certificates for user {self.username}.")
            deepCpy = self.certificateManager.certificates.copy()
            log.debug(f"Certificates to delete for user {self.username}")
            for cert in deepCpy:
                self.certificateManager.deleteSSHKey(cert)
            
            # odstraníme sshd konfiguraci
            log.info(f"Removing sshd configuration for user {self.username}.")
            remove_sshd_config(self.username)
            
            # cleanup ssh souborů
            self.__cleanupSSHFiles()
                        
            # odstraníme skupiny
            log.info(f"Removing user {self.username} from all SFTP groups.")
            deleteUserFromGroup(self.username, None)            
            
            # odstraníme uživatele, je to sftp managovaný jen pro sftp takže se může smazat komplet s home
            log.info(f"Deleting user {self.username} from system.")
            
            # musíme nastavit práva home pro uživele z rootu jinak jej nepůjde smazat
            log.info(f"Setting ownership and permissions for home directory {self.homeDir} of user {self.username} before deletion.")
            try:
                nfo = pwd.getpwnam(self.username)
                uid = nfo.pw_uid
                gid = nfo.pw_gid
                os.chown(self.homeDir, uid, gid)
                os.chmod(self.homeDir, 0o755)
            except Exception as e:
                log.warning(f"Failed to set ownership/permissions for {self.homeDir} before deletion: {e}")
                log.exception(e)
            
            log.info(f"Deleting user {self.username} and its home directory {self.homeDir}.")
            try:
                subprocess.run([
                    "userdel",
                    "-r",
                    self.username
                ], check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to delete user {self.username}: {e}")
            
            # pro jistoru rmtree na home pokud by tam něco zbylo
            log.info(f"Ensuring home directory {self.homeDir} of user {self.username} is removed.")
            if os.path.exists(self.homeDir):
                log.debug(f"Home directory {self.homeDir} still exists, removing it.")
                os.rmdir(self.homeDir)
            
        except Exception as e:
            raise RuntimeError(f"Failed to delete user {self.username}: {e}")
    
