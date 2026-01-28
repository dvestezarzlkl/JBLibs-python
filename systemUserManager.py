from .lng.default import * 
from .helper import loadLng
loadLng()

import os, pwd, grp, subprocess
import subprocess
from libs.JBLibs.input import get_username, get_pwd_confirm, confirm, anyKey, get_input
from libs.JBLibs.helper import userExists,getLogger,getUserList
from libs.JBLibs.term import cls
from typing import Union,List

log = getLogger(__name__)     

class sshMng:
    # kam ukládat per-user ssh policy
    SSHD_D_DIR = "/etc/ssh/sshd_config.d"
    SSHD_USER_PREFIX = "90-jb-user-"
    # kam ukládat per-user sudo policy
    SUDOERS_D_DIR = "/etc/sudoers.d"
    SUDO_USER_PREFIX = "90-jb-user-"    
    
    
    @staticmethod
    def getUserHome(username:str)->str|None:
        """Získá domovský adresář uživatele.
        Args:
            username (str): uživatelské jméno
        Returns:
            str|None: cesta k domovskému adresáři nebo None pokud uživatel neexistuje
        """
        try:
            pw = pwd.getpwnam(username)
        except KeyError:
            return None
        return pw.pw_dir
    
    @staticmethod
    def getFilePath_auth(username, check:bool=False) -> Union[str, None]:
        """
        Vrací cestu k souboru authorized_keys pro zadaného uživatele
        
        Parameters:
            username (str): jméno uživatele
            check (bool): pokud True, tak vrací cestu pouze pokud soubor existuje
            
        Returns:
            str: cesta k souboru authorized_keys
            None: pokud soubor neexistuje
        """
        x = os.path.join(sshMng.getUserHome(username), ".ssh", "authorized_keys")
        return x if not check or os.path.isfile(x) else None
    
    @staticmethod
    def getDirPath_ssh(username, check:bool=False) -> Union[str, None]:
        """
        Vrací cestu k adresáři .ssh pro zadaného uživatele
        
        Parameters:
            username (str): jméno uživatele
            check (bool): pokud True, tak vrací cestu pouze pokud adresář existuje
            
        Returns:
            str: cesta k adresáři .ssh
            None: pokud adresář neexistuje
        """
        x= os.path.join(sshMng.getUserHome(username), ".ssh")
        return x if not check or os.path.isdir(x) else None
    
    @staticmethod
    def getDirPath_sshManager(username, check:bool=False) -> Union[str, None]:
        """
        Vrací cestu k adresáři sshManager pro zadaného uživatele
        
        Parameters:
            username (str): jméno uživatele
            check (bool): pokud True, tak vrací cestu pouze pokud adresář existuje
            
        Returns:
            str: cesta k adresáři sshManager
            None: pokud adresář neexistuje
        """
        x= os.path.join(sshMng.getDirPath_ssh(username), "sshManager")
        return x if not check or os.path.isdir(x) else None
    
    @staticmethod
    def createSysUser():
        """
        Create a new system user.
        """
        
        username = get_username(f"{TXT_SSH_MNG_001}: ",True)
        if not username:
            return TXT_ABORTED

        username = username.strip()
        if userExists(username):
            print(TXT_SSH_MNG_002.format(name=username))
            anyKey()
            return TXT_ABORTED

        pwd = get_pwd_confirm(f"{TXT_SSH_MNG_005}: ")
        if not pwd:
            return TXT_ABORTED

        try:
            # Vytváření systémového uživatele
            log.debug(TXT_SSH_MNG_003.format(name=username))
            subprocess.run(['useradd', '-m', '-s', '/bin/bash', username], check=True)
            subprocess.run(['chpasswd'], input=f"{username}:{pwd}", text=True, check=True)

            # Nastavení SSH adresáře
            sshMng.repairSshFile(username)

            print(TXT_SSH_MNG_004.format(name=username))
        except subprocess.CalledProcessError as e:
            log.error(f"Error creating user {username}: {e}", exc_info=True)
            return f"{TXT_ERROR_OCCURRED}: {e}"
        
        print(TXT_SSH_MNG_006)
        anyKey()
    
    @staticmethod
    def repairSshFile(username) -> bool:
        """
        Funkce opraví adresář .ssh a soubor authorized_keys pro zadaného uživatele.
        1. Pokud neexistuje adresář .ssh, vytvoří ho
        2. Pokud neexistuje soubor authorized_keys, vytvoří ho
        3. Pokud neexistuje adresář sshManager, vytvoří ho
        4. Nastaví vlastníka a práva na adresář .ssh a soubor authorized_keys        
        """
        ssh_dir = sshMng.getDirPath_ssh(username)
        ssh_manager_dir = sshMng.getDirPath_sshManager(username)
        authorized_keys = sshMng.getFilePath_auth(username)

        try:
            # Vytvoření adresáře .ssh, sshManager a souboru authorized_keys pokud neexistují
            os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
            os.makedirs(ssh_manager_dir, mode=0o700, exist_ok=True)
            if not sshMng.getFilePath_auth(username,True):
                open(authorized_keys, 'a').close()
            
            # Nastavení vlastníka a práv
            subprocess.run(['chown', '-R', f"{username}:{username}", ssh_dir], check=True)
            subprocess.run(['chmod', '700', ssh_dir], check=True)
            subprocess.run(['chmod', '700', ssh_manager_dir], check=True)
            subprocess.run(['chmod', '600', authorized_keys], check=True)
        except Exception as e:
            log.error(f"{TXT_SSH_MNG_007} {username}: {e}", exc_info=True)
            raise    
    
    @staticmethod
    def certExists(username:str,certName:str) -> bool:
        """
        Kontroluje, zda certifikáty pro uživatele již existují v sshManager adresáři
        
        Parameters:
            username (str): jméno uživatele
            certName (str): název certifikátu, tj jméno souboru bez přípony
            
        Returns:
            bool: True pokud certifikáty existují
        """
        ssh_manager_dir = sshMng.getDirPath_sshManager(username,True)
        if not ssh_manager_dir:            
            return False
        private_key = os.path.join(ssh_manager_dir, certName)
        public_key = f"{private_key}.pub"
        return os.path.isfile(private_key) and os.path.isfile(public_key)
    
    @staticmethod
    def createCert(username:str)->Union[str, None]:
        """
        Vytvoří pár SSH klíčů pro uživatele a uloží je do adresáře sshManager
        
        Parameters:
            username (str): jméno uživatele
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        if not (ssh_manager_dir:=sshMng.getDirPath_sshManager(username,True)):
            log.error(f"SSH Manager directory for user {username} does not exist.")
            return TXT_SSH_MNG_008
        
        cert_name = get_input(f"{TXT_SSH_MNG_010}: ").strip()
        cert_name += "_key"
        private_key = os.path.join(ssh_manager_dir, f"{cert_name}")
        public_key = f"{private_key}.pub"
        
        if sshMng.certExists(username, cert_name):
            log.error(f"Certificate for user {username} already exists.")
            return TXT_SSH_MNG_009.format(key=cert_name)
        
        pwd=None
        if confirm(TXT_SSH_MNG_011):
            pwd = get_pwd_confirm(f"{TXT_SSH_MNG_005}: ")
            if not pwd:
                return TXT_ABORTED
        
        try:           
            # Vytvoření SSH klíče pomocí ssh-keygen
            cmd = [
                'ssh-keygen', '-t', 'rsa', '-b', '2048', '-f', private_key
            ]
            if pwd:
                cmd += ['-N', pwd]
            else:
                cmd += ['-N', '']

            subprocess.run(cmd, check=True)            
            
            # Nastavení vlastníka a práv
            subprocess.run(['chown', f"{username}:{username}", private_key, public_key], check=True)
            subprocess.run(['chmod', '600', private_key], check=True)
            subprocess.run(['chmod', '644', public_key], check=True)
            print(TXT_SSH_MNG_012.format(name=username, cert=cert_name))                  
            anyKey()
        except subprocess.CalledProcessError as e:
            log.error(f"Error creating SSH key for user {username}: {e}", exc_info=True)
            raise
        return None
    
    @staticmethod
    def deleCert(userName:str, certName:str)->Union[str, None]:
        """Smazání certifikátu z sshManager adresáře uživatele
        
        Parameters:
            userName (str): jméno uživatele
            certName (str): název certifikátu, tj jméno souboru bez přípony
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        if not (ssh_manager_dir:=sshMng.getDirPath_sshManager(userName,True)):
            log.error(f"SSH Manager directory for user {userName} does not exist.")
            return TXT_SSH_MNG_014
        
        if confirm(TXT_SSH_MNG_013.format(name=userName, cert=certName)):            
            if (e:=sshMng.delKey(userName, certName, False, True)):
                return e
                        
            private_key = os.path.join(ssh_manager_dir, f"{certName}")
            public_key = f"{private_key}.pub"
            
            if not os.path.isfile(private_key):
                print(TXT_SSH_MNG_015.format(key=private_key))
            
            if not os.path.isfile(public_key):
                print(TXT_SSH_MNG_016.format(key=public_key))
            
            try:
                if os.path.isfile(private_key):
                    os.remove(private_key)
                if os.path.isfile(public_key):
                    os.remove(public_key)
                print(TXT_SSH_MNG_017.format(name=userName, cert=certName))
                anyKey()
            except Exception as e:
                log.error(f"Error deleting certificate for user {userName}: {e}", exc_info=True)
                return TXT_SSH_MNG_018
        return None
    
    @staticmethod
    def checkKeyIncluded(username, fileName) -> bool:
        """
        Kontroluje, zda klíč s daným názvem je přítomen v authorized_keys souboru
        
        Parameters:
            username (str): jméno uživatele
            fileName (str): název klíče, tzn jméno souboru bez přípony
            
        Returns:
            bool: True pokud klíč existuje v authorized_keys
        """
        if not (authorized_keys := sshMng.getFilePath_auth(username, True)):
            return False
        
        # read public key do var for comparison
        if not (pub := sshMng.getDirPath_sshManager(username,True)):
            return False
        
        pub = os.path.join(pub, f"{fileName}.pub")
        if not os.path.isfile(pub):
            return False
        
        pub = open(pub, 'r').read().strip()
        
        with open(authorized_keys, 'r') as f:
            keys = f.readlines()
            keys = [key.strip() for key in keys]
            for key in keys:
                if pub == key:
                    return True
        return False
    
    @staticmethod
    def addKey(username, fileName) -> Union[str, None]:
        """
        Přidá klíč do authorized_keys, pokud tam ještě není
        
        Parameters:
            username (str): jméno uživatele
            fileName (str): název klíče
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        if sshMng.checkKeyIncluded(username, fileName):
            return TXT_SSH_MNG_019
        
        if not (ssh_manager_dir := sshMng.getDirPath_sshManager(username, True)):
            return TXT_SSH_MNG_020
        
        public_key_path = os.path.join(ssh_manager_dir, f"{fileName}.pub")
        if not os.path.isfile(public_key_path):
            return TXT_SSH_MNG_021.format(key_path=public_key_path)
        
        with open(public_key_path, 'r') as key_file:
            public_key = key_file.read().strip()
        
        authorized_keys = f"/home/{username}/.ssh/authorized_keys"
        with open(authorized_keys, 'a') as f:
            f.write(public_key + '\n')
        
        print(TXT_SSH_MNG_022.format(key=fileName, name=username))
        anyKey()
        return None
    
    @staticmethod
    def delKey(username:str, fileName:str, any_key:bool=True,ignoreKeyNotIncluded=False) -> Union[str, None]:
        """
        Smaže klíč z authorized_keys, pokud je přítomen
        
        Parameters:
            username (str): jméno uživatele
            fileName (str): název klíče
            any_key (bool): pokud True, zobrazí se zpráva pro stisknutí klávesy
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        
        # read public key do var for comparison
        if not (pub := sshMng.getDirPath_sshManager(username,True)):
            return TXT_SSH_MNG_023
        
        if not (authorized_keys := sshMng.getFilePath_auth(username)):
            return TXT_SSH_MNG_024.format(name=username)
        
        pub = os.path.join(pub, f"{fileName}.pub")
        if not os.path.isfile(pub):
            return TXT_SSH_MNG_025.format(pub=pub)
        
        pub = open(pub, 'r').read().strip()
        
        with open(authorized_keys, 'r') as f:
            keys = f.readlines()
        keys = [key.strip() for key in keys]
        l=len(keys)
        keys = [k for k in keys if k != pub ]
        key_found = len(keys) != l
        
        keys = "\n".join(keys)
        with open(authorized_keys, 'w') as f:
            f.write(keys)
        
        if key_found:
            print(TXT_SSH_MNG_026.format(key=fileName, name=username))
            if any_key:
                anyKey()
            return None
        else:
            if ignoreKeyNotIncluded:
                return None
            return TXT_SSH_MNG_027.format(key=fileName, name=username)
            
    @staticmethod
    def getKeyList(username) -> Union['listKeyRow', None]:
        """
        Vypíše klíče z authorized_keys
        
        Parameters:
            username (str): jméno uživatele
            
        Returns:
            str: obsah authorized_keys
            None: pokud neexistuje
        """
        
        if not (d := sshMng.getDirPath_sshManager(username,True)):
            return None

        lst = os.listdir(d)
        # Vytvoření seznamu klíčů
        keys = []
        for f in lst:
            if f.endswith('.pub'):
                keys.append(listKeyRow(f[:-4], username))        
        return keys

    @staticmethod
    def showKey(username:str, fileName:str, clear:bool=True)->Union[str, None]:
        """
        Vypíše obsah klíče, public key, tento je na serveru pro ověření
        
        Parameters:
            username (str): jméno uživatele
            fileName (str): název klíče
        """
        cls()
        if not (d := sshMng.getDirPath_sshManager(username)):
            return TXT_SSH_MNG_028.format(name=username)
        
        public_key_path = os.path.join(d, f"{fileName}.pub")
        if not os.path.isfile(public_key_path):
            return TXT_SSH_MNG_029.format(key_path=public_key_path)
        
        with open(public_key_path, 'r') as f:
            print(f.read())
            
        anyKey()
        return None
    
    @staticmethod
    def showCert(username:str, fileName:str, clear:bool=True)->Union[str, None]:
        """
        Vypíše obsah certifikátu, tento je potřebný pro klienta který se bude připojovat
        
        Parameters:
            username (str): jméno uživatele
            fileName (str): název klíče
        """
        cls()
        if not (d := sshMng.getDirPath_sshManager(username)):
            return TXT_SSH_MNG_030.format(name=username)
        
        private_key_path = os.path.join(d, f"{fileName}")
        if not os.path.isfile(private_key_path):
            return TXT_SSH_MNG_031.format(key_path=private_key_path)
        
        with open(private_key_path, 'r') as f:
            print(f.read())
            
        anyKey()
        return None
    
    @staticmethod
    def changeSystemUserPwd(username: str) -> Union[str, None]:
        """
        Změní heslo systémového uživatele
        
        Parameters:
            username (str): jméno uživatele
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        # Získání nového hesla od uživatele
        pwd = get_pwd_confirm(f"{TXT_SSH_MNG_032}: ")
        if not pwd:
            return TXT_ABORTED
        
        try:
            # Použití chpasswd pro změnu hesla uživatele
            subprocess.run(['chpasswd'], input=f"{username}:{pwd}", text=True, check=True)
            print( TXT_SSH_MNG_033.format(name=username))
        except subprocess.CalledProcessError as e:
            log.error(
                TXT_SSH_MNG_034.format(name=username, e=e),
                exc_info=True
            )
            return TXT_ERROR_OCCURRED
        anyKey()
        return None
       
    @staticmethod
    def add_sudo_privileges(username)->Union[str, None]:
        """Přidá uživateli sudo práva
        
        Parameters:
            username (str): jméno uživatele
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        x=sshMng.is_sudoer(username)
        if isinstance(x,str):
            return x
        elif x:
            return None
        try:
            subprocess.run(['usermod', '-aG', 'sudo', username], check=True)            
            return None
        except subprocess.CalledProcessError as e:
            log.error(f"Error adding user {username} to sudo group: {e}", exc_info=True)
            return TXT_ERROR_OCCURRED
    
    def remove_sudo_privileges(username:str)->Union[str, None]:
        """Odebere uživateli sudo práva
        
        Parameters:
            username (str): jméno uživatele
            
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        x=sshMng.is_sudoer(username)
        if isinstance(x,str):
            return x
        elif not x:
            return None
        try:
            subprocess.run(['sudo', 'deluser', username, 'sudo'], check=True)
            return None
        except subprocess.CalledProcessError as e:
            log.error(f"Chyba při odebírání uživatele ze skupiny sudo: {e}", exc_info=True)
            return TXT_ERROR_OCCURRED
        

    @staticmethod
    def _run(cmd:list[str]) -> tuple[int,str,str]:
        """Spustí příkaz a vrátí návratový kód, stdout a stderr.
        
        Args:
            cmd (list[str]): příkaz a jeho argumenty jako seznam
            
        Returns:
            tuple[int,str,str]: (returncode, stdout, stderr)
        """
        
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p.returncode, p.stdout or "", p.stderr or ""

    # ---------- SUDO state ----------
    @staticmethod
    def is_sudoer(username: str) -> bool:
        """True, pokud uživatel patří do sudo (sekundárně nebo primárně).
        
        Args:
            username (str): uživatelské jméno
        Returns:
            bool: True pokud je uživatel sudoer, jinak False
        """
        try:
            # primární group
            primary_gid = pwd.getpwnam(username).pw_gid
            primary_group = grp.getgrgid(primary_gid).gr_name
            if primary_group == "sudo":
                return True

            # sekundární group membership
            sudo_gr = grp.getgrnam("sudo")
            return username in sudo_gr.gr_mem
        except KeyError:
            # user nebo group neexistuje
            return False

    @staticmethod
    def _sudo_nopasswd_path(username: str) -> str:
        """Cesta k sudoers.d souboru pro NOPASSWD pravidlo uživatele.
        Args:
            username (str): uživatelské jméno
        Returns:
            str: cesta k souboru
        """        
        return os.path.join(sshMng.SUDOERS_D_DIR, f"{sshMng.SUDO_USER_PREFIX}{username}-nopasswd")

    @staticmethod
    def has_sudo_nopasswd(username: str) -> bool:
        """True, pokud má uživatel NOPASSWD pravidlo v sudoers.d.
        Args:
            username (str): uživatelské jméno
        Returns:
            bool: True pokud má NOPASSWD pravidlo, jinak False
        """
        return os.path.isfile(sshMng._sudo_nopasswd_path(username))

    @staticmethod
    def enforce_sudo_nopasswd(username: str, enable: bool) -> str|None:
        """
        Vytvoří nebo odstraní NOPASSWD pravidlo v sudoers.d pro uživatele.
        
        Args:
            username (str): uživatelské jméno
            enable (bool): True pro vytvoření NOPASSWD pravidla, False pro odstranění            
                enable=True  -> vytvoří NOPASSWD jen pokud je user sudoer, jinak odstraní
                enable=False -> vždy odstraní
        Returns:
            str|None: chyba, pokud došlo k chybě, jinak None
        """
        path = sshMng._sudo_nopasswd_path(username)

        def _remove():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    return f"{TXT_ERROR_OCCURRED}: {e}"
            return None

        if not enable:
            return _remove()

        # enable == True
        if not sshMng.is_sudoer(username):
            # uklid: nemá být NOPASSWD, když není sudoer
            return _remove()

        try:
            content = f"{username} ALL=(ALL) NOPASSWD: ALL\n"
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            subprocess.run(["chown", "root:root", path], check=True)
            subprocess.run(["chmod", "0440", path], check=True)

            # validace přes visudo
            subprocess.run(["visudo", "-cf", path], check=True)
            return None
        except subprocess.CalledProcessError as e:
            # když visudo failne, radši soubor smaž a vrať chybu
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
            return f"{TXT_ERROR_OCCURRED}: {e}"
        except Exception as e:
            return f"{TXT_ERROR_OCCURRED}: {e}"

    # ---------- SSH password login policy ----------
    @staticmethod
    def _sshd_user_path(username: str) -> str:
        """Cesta k sshd_config.d souboru pro per-user SSH policy.
        Args:
            username (str): uživatelské jméno
        Returns:
            str: cesta k souboru
        """
        return os.path.join(sshMng.SSHD_D_DIR, f"{sshMng.SSHD_USER_PREFIX}{username}.conf")

    @staticmethod
    def is_password_login_disabled(username: str) -> bool:
        """True, pokud má uživatel per-user SSH policy zakazující PasswordAuthentication.
        Args:
            username (str): uživatelské jméno
        Returns:
            bool: True pokud má per-user SSH policy, jinak False
        """
        return os.path.isfile(sshMng._sshd_user_path(username))

    @staticmethod
    def _reload_sshd() -> str|None:
        """Reload SSH server služby (ssh / sshd)."""
        try:
            subprocess.run(
                ["systemctl", "reload", "ssh"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return None
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    ["systemctl", "reload", "sshd"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return None
            except subprocess.CalledProcessError as e:
                return f"{TXT_ERROR_OCCURRED}: {e}"

    @staticmethod
    def set_password_login(username: str, enable: bool, require_totp: bool=True) -> str|None:
        """
        Per-user policy přes sshd_config.d.
        
        Args:
            username (str): uživatelské jméno
            enable (bool): True pro povolení PasswordAuthentication (odstraní per-user soubor), 
                           False pro zakázání PasswordAuthentication
            require_totp (bool): pokud True, vynutí publickey + keyboard-interactive
        Returns:
            str|None: chyba, pokud došlo k chybě, jinak None
        """
        path = sshMng._sshd_user_path(username)

        if enable:
            # smazat per-user override
            try:
                if os.path.exists(path):
                    os.remove(path)
                
                # reload sshd
                err = sshMng._reload_sshd()
                if err:
                    return err
                
                return None
            except Exception as e:
                return f"{TXT_ERROR_OCCURRED}: {e}"

        # enable == False
        # bezpečnost: bez klíčů tohle nedovol (aspoň autorizované klíče existují a nejsou prázdné)
        u = sshUser(username)
        if u.keyCount == 0:
            return TXT_SSH_MNG_024.format(name=username)  # nebo vlastní text: "authorized_keys empty"

        try:
            os.makedirs(sshMng.SSHD_D_DIR, exist_ok=True)

            if require_totp:
                methods = "publickey,keyboard-interactive"
                kbd = "yes"
            else:
                methods = "publickey"
                kbd = "no"

            conf = (
                f"Match User {username}\n"
                f"    PasswordAuthentication no\n"
                f"    PubkeyAuthentication yes\n"
                f"    KbdInteractiveAuthentication {kbd}\n"
                f"    AuthenticationMethods {methods}\n"
            )

            with open(path, "w", encoding="utf-8") as f:
                f.write(conf)

            subprocess.run(["chown", "root:root", path], check=True)
            subprocess.run(["chmod", "0644", path], check=True)

            # validace sshd konfigurace
            subprocess.run(["sshd", "-t"], check=True)

            # reload sshd
            err = sshMng._reload_sshd()
            if err:
                return err
            return None
        except subprocess.CalledProcessError as e:
            # revert soubor při failu
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
            return f"{TXT_ERROR_OCCURRED}: {e}"
        except Exception as e:
            return f"{TXT_ERROR_OCCURRED}: {e}"        

class listKeyRow:
    userName:str=""
    """Systémový uživatel"""
    fileName:str=""
    """jen jméno souboru bez přípony"""
    included:bool=False
    haveCert:bool=False
    
    def __init__(self, fileName:str, userName:str):
        self.fileName=fileName
        self.userName=userName
        self.check()
        
    def __repr__(self):
        return f"{self.fileName} {'inSSH' if self.included else ''} {'+cert' if self.haveCert else ''}"
    
    def showKey(self)->Union[str, None]:
        """zobrazí obsah klíče - public key
        
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        return sshMng.showKey(self.userName,self.fileName)
    
    def showCert(self)->Union[str, None]:
        """zobrazí obsah certifikátu - private key pro připojujícího se klienta
        """
        return sshMng.showCert(self.userName,self.fileName)
    
    def check(self):
        """aktualizuje properties podle aktuálního stavu
        """
        self.included=False
        self.haveCert=False
        if not sshMng.getFilePath_auth(self.userName):
            return
        self.included=sshMng.checkKeyIncluded(self.userName,self.fileName)
        self.haveCert=sshMng.certExists(self.userName,self.fileName)
    
    def addKey(self)->Union[str, None]:
        """přidá klíč do authorized_keys
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        return sshMng.addKey(self.userName,self.fileName)
    
    def remKey(self)->Union[str, None]:
        """smaže klíč z authorized_keys
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        return sshMng.delKey(self.userName,self.fileName)        
        
    def delMe(self)->Union[str, None]:
        """smaže klíč a certifikát
        Returns:
            str: chyba, pokud došlo k chybě
            None: pokud OK
        """
        if (e:=sshMng.deleCert(self.userName,self.fileName)):
            return e
        return None
        
class sshUser:
    _userName:str=""
    _keys:List[listKeyRow]=None
    
    @property
    def userName(self)->str:
        """Jméno systémového uživatele"""
        return self._userName
        
    @property
    def keys(self)->List[listKeyRow]:
        """Seznam klíčů pro uživatele"""
        return self._keys
        
    @property
    def keyCount(self)->int:
        """Počet klíčů pro uživatele"""
        return len(self.keys) if self.keys else 0
    
    @property
    def hasSudo(self)->bool:
        """True pokud uživatel má sudo práva"""
        return sshMng.is_sudoer(self.userName)
    
    def __init__(self,userName:str):
        self._userName=userName
        self.refresh()
        
    def refresh(self):
        if not userExists(self._userName):
            raise ValueError(f"User {self._userName} does not exist.")
        self._keys=sshMng.getKeyList(self._userName)
        if not self._keys:
            self._keys=[]
            
    def __repr__(self):
        return f"{self.userName} (keys: {self.keyCount})" + (" sudo" if self.hasSudo else "")
            
    def createCerKey(self)->Union[str, None]:
        """Vytvoří certifikát pro uživatele"""
        return sshMng.createCert(self.userName)
    
    @property
    def isSudoer(self) -> bool:
        """True pokud uživatel patří do sudo skupiny"""
        return sshMng.is_sudoer(self.userName)

    @property
    def hasSudoNoPasswd(self) -> bool:
        """True pokud má uživatel NOPASSWD pravidlo v sudoers.d"""
        return sshMng.has_sudo_nopasswd(self.userName)

    @property
    def passwordLoginDisabled(self) -> bool:
        """True pokud má uživatel zakázané přihlašování heslem přes per-user sshd_config.d"""
        return sshMng.is_password_login_disabled(self.userName)
    
    def enforceSudoNoPasswd(self, enable: bool) -> str|None:
        """Nastaví nebo odstraní NOPASSWD pravidlo v sudoers.d pro uživatele.
        
        Args:
            enable (bool): True pro vytvoření NOPASSWD pravidla, False pro odstranění
            
        Returns:
            str|None: chyba, pokud došlo k chybě, jinak None
        """
        return sshMng.enforce_sudo_nopasswd(self.userName, enable)
    
    def setPasswordLogin(self, enable: bool, require_totp: bool=True) -> str|None:
        """Nastaví per-user sshd_config.d pro povolení nebo zakázání přihlašování heslem.
        
        Args:
            enable (bool): True pro povolení PasswordAuthentication, False pro zakázání
            require_totp (bool): pokud True, vynutí publickey + keyboard-interactive
        Returns:
            str|None: chyba, pokud došlo k chybě, jinak None
        """
        return sshMng.set_password_login(self.userName, enable, require_totp)
        
class sshUsers:
    _users:List[sshUser]=None
    
    @property
    def users(self)->Union[sshUser, None]:
        """Seznam uživatelů"""
        return self._users
        
    def __init__(self):
        self.refresh()
          
    def refresh(self):
        """Aktualizuje seznam uživatelů"""
        self._users=[]
        for u in getUserList(None):
            self._users.append(sshUser(u))
            
    def getUser(self,userName:str)->Union[sshUser, None]:
        """Vrátí uživatele podle jména
        
        Parameters:
            userName (str): jméno uživatele
            
        Returns:
            sshUser: uživatel
            None: pokud uživatel neexistuje
        """
        for u in self._users:
            if u.userName==userName:
                return u
        return None
    
    def createUser(self)->Union[str, None]:
        """Vytvoří nového uživatele"""
        return sshMng.createSysUser()
    
    def __iter__(self):
        return iter(self._users)

    def __len__(self):
        return len(self._users)
    
    def __repr__(self):
        return f"{len(self)} users"
    
    def __getitem__(self, key):
        return self._users[key]