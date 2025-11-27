import os
import pwd
import libs.JBLibs.sftp.ssh as ssh
from libs.JBLibs.helper import userExists, getUserHome

CERTS_FILE_NAME: str = ".sftp_certs"

class userCertsManager:
    def __init__(self, username:str):
        """Inicializace správce certifikátů uživatele.
        Args:
            username (str): jméno uživatele
        Raises:
            RuntimeError: pokud uživatel neexistuje nebo dojde k chybě při načítání certifikátů
        """
        self.username:str = username
        """Jméno uživatele"""
        
        self.ok:bool = False
        """Indikátor, zda je uživatel správně inicializován"""
        
        self.homeDir:str|None = None
        """Domovský adresář uživatele"""
        
        self.certificates:list[str] = []
        """Seznam certifikátů uživatele"""
        
        if not userExists(self.username):
            raise RuntimeError(f"User {self.username} does not exist.")
        
        self.homeDir = getUserHome(self.username)
        if not self.homeDir or not os.path.isdir(self.homeDir):
            raise RuntimeError(f"Cannot determine home directory for user {self.username}.")
        
        certs_file=os.path.join(self.homeDir, CERTS_FILE_NAME)
        if os.path.isfile(certs_file):
            try:
                with open(certs_file, "r") as f:
                    for line in f:
                        cert=line.strip()
                        if cert:
                            self.certificates.append(cert)
            except Exception as e:
                raise RuntimeError(f"Failed to load certificates for user {self.username}: {e}")
        
        self.ok = True
    
    
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
            certs_file=os.path.join(self.homeDir, CERTS_FILE_NAME)
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
    
    def __deleteMyCert(self, cert:str)->None:
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
        ak_file = ssh.ensure_ssh_key(self.username, public_key)
        if ak_file is None:
            raise RuntimeError(f"Failed to ensure SSH key for user {self.username}.")
        
        try:    
            self.__addMyCert(public_key.strip())            
        except Exception as e:
            raise RuntimeError(f"Failed to add certificate for user {self.username}: {e}")

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
            
    def deleteSSHKey(self, public_key:str|list[str])->None|str:
        """Odstraní zadaný veřejný SSH klíč ze souboru authorized_keys uživatele.
        Args:
            public_key (str): veřejný SSH klíč
        Returns:
            None|str: None pokud vše ok, jinak seznam chyba - nekritická
        Raises:
            RuntimeError: pokud uživatel není správně inicializován nebo dojde k chybě při mazání klíče
        """
        if not ssh.deleteSSHKey(self.username, public_key):
            return f"Failed to delete SSH key for user {self.username}."        
        try:
            self.__deleteMyCert(public_key.strip())
        except Exception as e:
            return f"SSH key deleted but failed to remove from certificates: {e}"
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