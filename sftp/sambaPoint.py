from libs.JBLibs.helper import getLogger
log = getLogger("sambaPoint")

import os,re,pwd,time,grp,subprocess,socket
from ..systemdService import c_service
from .mountPoint import sftpUserMountpoint
import threading

SMB_CFG_DIR:str = "/etc/samba"

SMB_SFT_USER:str = "sftp_samba_user"
"""Uživatelské jméno pro přístup k Samba SFTP mount pointům."""
SMB_SFT_PWD:str = "fd8jS93jdj3kD93j"
"""Heslo pro uživatele pro přístup k Samba SFTP mount pointům."""

SMB_CRED_FILE:str = "/etc/samba/.smb_sftp_creds"

__INIT_DONE__=False
"""Indikátor, zda byla inicializace provedena."""

__INIT_LOCK__=threading.Lock()
"""Zámek pro inicializaci."""

class smbHelp:

    @staticmethod
    def ensureSambaCredFile():
        """Vytvoří credentials soubor pro CIFS mounty."""
        cred_dir = os.path.dirname(SMB_CRED_FILE)
        if not os.path.isdir(cred_dir):
            os.makedirs(cred_dir, exist_ok=True)
            os.chown(cred_dir, 0, 0)
            os.chmod(cred_dir, 0o700)

        content = f"username={SMB_SFT_USER}\npassword={SMB_SFT_PWD}\n"
        try:
            with open(SMB_CRED_FILE, "w") as f:
                f.write(content)
            os.chown(SMB_CRED_FILE, 0, 0)
            os.chmod(SMB_CRED_FILE, 0o600)
        except Exception as e:
            raise RuntimeError(f"Failed to write Samba credential file {SMB_CRED_FILE}: {e}")

    @staticmethod
    def checkSambaInstalled() -> bool:
        """Zkontroluje, zda je Samba nainstalována v systému.
        
        Returns:
            bool: True pokud je Samba nainstalována, jinak False.
        """
        from shutil import which
        return which("smbd") is not None
        
    @staticmethod        
    def ensureSambaUserPwd()->None:
        """Zajistí, že uživatel pro přístup k Samba SFTP mount pointům má nastavené
        správné heslo.
        Raises:
            RuntimeError: pokud dojde k chybě při nastavování hesla
        """
        try:
            import subprocess
            log.info(f"Setting password for Samba SFTP user {SMB_SFT_USER}.")
            subprocess.run([
                "smbpasswd",
                "-a",
                SMB_SFT_USER
            ], input=f"{SMB_SFT_PWD}\n{SMB_SFT_PWD}\n".encode(), check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to set password for Samba SFTP user {SMB_SFT_USER}: {e}")

    @staticmethod
    def ensureSambaUserExists()->None:
        """Zajistí, že uživatel pro přístup k Samba SFTP mount pointům existuje.
        Pokud neexistuje, vytvoří ho.
        Raises:
            RuntimeError: pokud dojde k chybě při kontrole nebo vytváření uživatele
        """
        try:
            pwd.getpwnam(SMB_SFT_USER)
            log.info(f"Samba SFTP user {SMB_SFT_USER} already exists.")
            smbHelp.ensureSambaUserPwd()
            return  # uživatel existuje
        except KeyError:
            log.info(f"Samba SFTP user {SMB_SFT_USER} does not exist. Creating it.")
        
        try:
            import subprocess
            subprocess.run([
                "useradd",
                "-M",  # bez home dir
                "-s", "/sbin/nologin",  # bez shellu
                SMB_SFT_USER
            ], check=True)

            smbHelp.ensureSambaUserPwd()        
            
            log.info(f"Samba SFTP user {SMB_SFT_USER} created successfully.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create Samba SFTP user {SMB_SFT_USER}: {e}")

    def write_or_replace_samba_section(section: str, content: str):
        """
        Přidá nebo přepíše celou share sekci v smb.conf.
        Args:
            section: název sekce bez []
            content: kompletní obsah sekce (může být více řádků)
        """

        section_header = f"[{section}]"
        new_section_block = section_header + "\n" + content.rstrip() + "\n"

        conf_file = os.path.join(SMB_CFG_DIR, "smb.conf")
        if not os.path.isfile(conf_file):
            raise RuntimeError(f"Samba configuration file does not exist: {conf_file}")
        
        with open(conf_file, "r") as f:
            lines = f.readlines()

        out = []
        inside = False
        replaced = False

        for line in lines:
            stripped = line.strip()

            if stripped.lower().startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1]

                if inside:
                    # ukončení staré sekce – vložíme novou
                    out.append(new_section_block)
                    inside = False
                    replaced = True

                if current_section.lower() == section.lower():
                    inside = True
                    continue  # přeskočit starou sekci

            if not inside:
                out.append(line)

        # pokud sekce nebyla nalezena – přidáme na konec
        if not replaced:
            if not out[-1].endswith("\n"):
                out.append("\n")
            out.append(new_section_block)

        with open(conf_file, "w") as f:
            f.writelines(out)


    @staticmethod    
    def ensureSambaSharePoint(target:str, share_base_name:str, forceUser:str, forceGrp:str)->None:
        """Přidá nový mount point do Samba konfigurace.
        Args:
            target (str): cesta k adresáři, který se má namountovat
            share_base_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forceUser (str): uživatel, pod kterým bude mount point přístupný
            forceGrp (str): skupina, pod kterou bude mount point přístupný
        Raises:
            RuntimeError: pokud dojde k chybě při přidávání mount pointu
        """
        initEnsureSamba()
        
        # test fyz cesty, musí existovat
        if not os.path.isdir(target):
            raise RuntimeError(f"Samba mount target path does not exist or is not a directory: {target}")
        
        # test práv uživatele a skupiny
        try:
            pw = pwd.getpwnam(forceUser)
        except Exception as e:
            raise RuntimeError(f"Samba mount point force user does not exist: {forceUser}")
        try:
            import grp
            gr = grp.getgrnam(forceGrp)
        except Exception as e:
            raise RuntimeError(f"Samba mount point force group does not exist: {forceGrp}")
        
        # má adresář právo pro uživatele a skupinu?
        st=os.stat(target)
        if st.st_uid != pw.pw_uid:
            raise RuntimeError(f"Samba mount target path {target} is not owned by user {forceUser}.")
        if st.st_gid != gr.gr_gid:
            raise RuntimeError(f"Samba mount target path {target} is not owned by group {forceGrp}.")
            
        share_name=makeShareNameSafe(share_base_name,forceUser, True)
                
        log.info(f"Adding Samba mount point config to section [{share_name}]:")
        log.info(f" - target: {target}")
        log.info(f" - force user: {forceUser}")
        log.info(f" - force group: {forceGrp}")
        
        share_cfg=f"""
    path = {target}
    valid users = {SMB_SFT_USER}
    force user = {forceUser}
    force group = {forceGrp}
    browsable = yes
    writable = yes
    read only = no
    create mask = 0700
    directory mask = 0700
    """
        smbHelp.write_or_replace_samba_section(share_name, share_cfg)
        
    @staticmethod
    def removeSambaSharePoint(share_base_name:str, forUser:str)->None:
        """Odebere mount point ze Samba konfigurace.
        Args:
            share_base_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
        Raises:
            RuntimeError: pokud dojde k chybě při odebírání mount pointu
        """        
        share_name=makeShareNameSafe(share_base_name,forUser, True)     
        log.info(f"Removing Samba mount point config for section [{share_name}].")
        smbHelp.write_or_replace_samba_section(share_name, "")  # přepíšeme prázdným obsahem – smaže se
        
    @staticmethod
    def getFstabFileName(base_share_name:str, forUser:str)->str:
        """Získá jméno fstab souboru pro zadaný mount point.
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
        Returns:
            str: jméno fstab souboru pro daný mount point
        """
        return os.path.join("/etc/fstab.d", makeShareNameSafe(base_share_name, forUser, True)+".fstab")
    
    @staticmethod    
    def ensureFstabCIFScfg(base_share_name:str, forUser:str, forGroup:str, target:str)->bool:
        """Zajistí, že je v /etc/fstab.d konfigurace pro připojení Samba share.
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
            forGroup (str): skupina, pro kterou je share určen
            target (str): cesta, kam se má share namountovat (sftp mountpoint)
        Returns:
            bool: True pokud vše ok
        Raises:
            RuntimeError: pokud dojde k chybě při úpravě /etc/fstab
        """
        fstab_file=smbHelp.getFstabFileName(base_share_name, forUser)
        cifs_line=smbHelp.getCIFSLine(base_share_name, target, forUser, forGroup)

        try:
            # pokud exituje tak bude přepsán
            log.info(f"Ensuring CIFS mount line in {fstab_file}.")
            with open(fstab_file, "w") as f:
                f.write(cifs_line + "\n")
            os.chown(fstab_file, 0, 0)
            os.chmod(fstab_file, 0o644)
            return True
        except Exception as e:
            log.error(f"Failed to ensure CIFS mount line in {fstab_file}: {e}")
            log.exception(e)
            return False
    
    @staticmethod    
    def removeFstabCIFScfg(base_share_name:str, forUser:str)->bool:
        """Odebere konfiguraci pro připojení Samba share z /etc/fstab.d
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
        Returns:
            bool: True pokud byl řádek odstraněn nebo neexistoval
        Raises:
            RuntimeError: pokud dojde k chybě při úpravě /etc/fstab
        """
        fstab_file=smbHelp.getFstabFileName(base_share_name, forUser)
        if not os.path.isfile(fstab_file):
            log.info(f"CIFS mount line file {fstab_file} does not exist. Nothing to remove.")
            return True
        try:
            log.info(f"Removing CIFS mount line file {fstab_file}.")
            os.remove(fstab_file)
            return True
        except Exception as e:
            log.error(f"Failed to remove CIFS mount line file {fstab_file}: {e}")
            log.exception(e)
            return False    

    @staticmethod
    def getCIFSpath(base_share_name:str, forUser:str, host:str="127.0.0.1")->str:
        """Získá cestu k Samba share config souboru pro zadaný mount point.        
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
            host (str): hostname nebo IP adresa serveru Samba, defaultně je localhost
        Returns:
            str: cesta pro cifs share config soubor např
                `//127.0.0.1/sftp_mount_user_sharename`
        """
        share_name=makeShareNameSafe(base_share_name, forUser, True)        
        return f"//{host}/{share_name}"
        
    @staticmethod
    def getCIFSLine(base_share_name:str, target:str, forUser:str, forGroup:str, host:str="127.0.0.1")->str:
        """Získá řádek pro připojení Samba share do fstab.
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            target (str): cesta, kam se má share namountovat (sftp mountpoint)
            forUser (str): uživatel, pro kterého je share určen
            forGroup (str): skupina, pro kterou je share určen
            host (str): hostname nebo IP adresa serveru Samba, defaultně je localhost
        Returns:
            str: řádek pro fstab
        """
        cifs_path=smbHelp.getCIFSpath(base_share_name, forUser, host)
        # získáme uid a gid pro forUser
        try:
            pw = pwd.getpwnam(forUser)
        except Exception as e:
            raise RuntimeError(f"Samba mount point force user does not exist: {forUser}")
        try:
            gr = grp.getgrnam(forGroup)
        except Exception as e:
            raise RuntimeError(f"Samba mount point force group does not exist: {forGroup}")
        try:
            uid=str(pw.pw_uid)
            gid=str(gr.gr_gid)
        except Exception as e:
            raise RuntimeError(f"Failed to get uid/gid for user/group {forUser}: {e}")
        
        options=f"credentials={SMB_CRED_FILE},uid={uid},gid={gid},rw,iocharset=utf8,file_mode=0700,dir_mode=0700"
        fstab_line=f"{cifs_path} {target} cifs {options} 0 0"
        return fstab_line

    @staticmethod
    def isMounted(base_share_name:str, forUser:str)->bool:
        """Zkontroluje, zda je mount point namountován.
        Args:
            base_share_name (str): základní jméno share (bude doplněno o prefix "sftp_mount_" )
            forUser (str): uživatel, pro kterého je share určen
        Returns:
            bool: True pokud je mount point namountován
        Raises:
            RuntimeError: pokud dojde k chybě při kontrole mount pointu
        """
        cifs_path=smbHelp.getCIFSpath(base_share_name, forUser)
        try:
            with open("/proc/mounts","r") as f:
                for line in f:
                    if cifs_path in line:
                        return True  # je namountováno
            return False
        except Exception as e:
            msg=f"Failed to check if Samba SFTP mount point {cifs_path} is mounted: {e}"
            log.error(msg)
            log.exception(e)
            raise RuntimeError(msg)
        
    @staticmethod
    def waitSambaAlive(timeout: float = 5.0, interval: float = 0.1) -> bool:
        """
        Počká, až bude Samba (smbd) skutečně připravena.
        Testuje:
        - systemctl is-active smbd
        - TCP handshake na port 445
        Args:
            timeout (float): maximální čekací doba v sekundách
            interval (float): interval dotazování v sekundách
        Returns:
            bool: True pokud je Samba živá a připravená, False při timeoutu
        """
        end = time.time() + timeout

        while time.time() < end:
            # 1) Systemd stav
            try:
                proc = subprocess.run(
                    ["systemctl", "is-active", "--quiet", "smbd"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if proc.returncode == 0:
                    log.debug("Samba smbd reported active by systemd.")
                    return True
            except Exception:
                pass  # ignorujeme, systém může běžet bez systemd

            # 2) TCP handshake test
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(interval)
            try:
                sock.connect(("127.0.0.1", 445))
                sock.close()
                log.debug("Samba port 445 accepted TCP connect().")
                return True
            except Exception:
                sock.close()

            time.sleep(interval)

        log.warning(f"Samba did not become ready within {timeout}s.")
        return False
    

def initEnsureSamba():
    """Inicializuje potřebné nastavení pro Samba SFTP mount pointy.
    Zajistí existenci uživatele, credentials souboru a konfigurace Samba pro načítání uživatelských conf souborů.
    Raises:
        RuntimeError: pokud dojde k chybě při inicializaci
    """
    global __INIT_DONE__
    with __INIT_LOCK__:
        if __INIT_DONE__ :
            return  # už inicializováno
        __INIT_DONE__ = True
    
    if not smbHelp.checkSambaInstalled():
        raise RuntimeError("Samba is not installed on this system.")
    
    smbHelp.ensureSambaUserExists()
    smbHelp.ensureSambaCredFile()
    
def restartSambaService()->bool:
    """Restartuje samba službu
    Returns:
        bool: True pokud byl restart úspěšný, False pokud došlo k chybě
    """
    SRVNM="Samba"
    SRV="smbd"
    
    log.info(f"Restarting {SRVNM} service")
    
    s=c_service(SRV)
    if s.exists() is False:
        log.error(f" < {SRVNM} - {SRV} service does not exist on this system.")
        return False
    if s.running():
        log.info(f" - Stopping {SRVNM} - {SRV} service before restart.")
        if not s.restart():
            log.error(f" < Failed to stop {SRVNM} - {SRV} service before restart.")
            return False
    else:
        log.info(f" - {SRVNM} - {SRV} service is not running. Starting it.")
        if not s.start():
            log.error(f" < Failed to start {SRVNM} - {SRV} service.")
            return False
    # počkat než samba naběhne
    if not smbHelp.waitSambaAlive(5.0, 0.2):
        log.error(f" < {SRVNM} - {SRV} service did not become ready after restart.")
        return False
    log.info(f"< {SRVNM} service restarted successfully.")
    return True

def makeShareNameSafe(name:str,username:str,prefixAdd:bool=True)->str:
    """Převede jméno na bezpečné pro použití jako Samba share name.
    Args:
        name (str): původní jméno použité jako základ pro sftp
        username (str): jméno uživatele
        prefixAdd (bool): pokud je True, přidá na začátek "sftp_mount_"
    Returns:
        str: bezpečné jméno pro Samba share
    """
    rgx = re.compile(r'[^a-zA-Z0-9_.-]')
    safe_name=rgx.sub('_', name)
    safe_user=rgx.sub('_', username)
    safe_name=f"{safe_user}_{safe_name}"
    if prefixAdd:
        safe_name=f"sftp_mount_{safe_name}"
    return safe_name

def removeSharePoint(mp:sftpUserMountpoint)->None:
    """Odebere mount point ze Samba konfigurace.
    Args:
        mp (sftpUserMountpoint): instance mount pointu
    Raises:
        RuntimeError: pokud dojde k chybě při odebírání mount pointu
    """
    share_base_name=mp.mountName
    forUser, uid = mp.forUser()
    
    log.info(f"Removing Samba SFTP mount point for share {share_base_name}.")
    cifs_path=smbHelp.getCIFSpath(share_base_name, forUser)
    if smbHelp.isMounted(share_base_name, forUser):
        # umount it
        log.info(f"Unmounting Samba SFTP mount point {cifs_path} before removal.")
        try:
            import subprocess
            subprocess.run([
                "umount",
                cifs_path
            ], check=True)
        except subprocess.CalledProcessError as e:
            msg=f"Failed to unmount Samba SFTP mount point {cifs_path} before removal: {e}"
            log.error(msg)
            log.exception(e)
            raise RuntimeError(msg)
    
    # odstranění konfigu z fstab
    log.info(f" - Removing fstab CIFS config for Samba SFTP mount point {share_base_name}.")
    if not smbHelp.removeFstabCIFScfg(share_base_name, forUser):
        msg=f"Failed to remove fstab CIFS line for Samba SFTP mount point {share_base_name}."
        log.error(msg)
        raise RuntimeError(msg)
    
    # odstranění konfigu ze samba
    log.info(f" - Removing Samba SFTP mount point configuration for share {share_base_name}.")
    smbHelp.removeSambaSharePoint(share_base_name, forUser)
        
    # odstranění mountpointu
    if os.path.isdir(mp.mountPath):
        log.info(f" - Removing Samba SFTP mount point directory {mp.mountPath}.")
        try:
            os.rmdir(mp.mountPath)
        except Exception as e:
            msg=f"Failed to remove Samba SFTP mount point directory {mp.mountPath}: {e}"
            log.error(msg)
            log.exception(e)
            raise RuntimeError(msg)
        
        
    log.info(f"< Samba SFTP mount point for share {share_base_name} removed successfully.")
    
  
# base_share_name:str, source:str, target:str, forceUser:str, forceGrp:str)->str:
def ensureMountpoint(mp:sftpUserMountpoint)->str:
    """Zajistí existenci konfigu, uživatele a mountpointu pro Samba SFTP share. A samozřejmě že je i připojen
    Args:
        mp (sftpUserMountpoint): instance mount pointu
    Returns:
        str: cesta k mount pointu
    Raises:
        RuntimeError: pokud dojde k chybě při zajišťování mount pointu
    """
    
    try:
        if not isinstance(mp, sftpUserMountpoint):
            raise RuntimeError("Invalid mount point instance provided.")
        
        base_share_name=mp.mountName
        source=mp.realPath
        target=mp.mountPath        
        log.info(f"Ensuring Samba SFTP mount point configuration for share {base_share_name}.")
        initEnsureSamba()        
        # získáme informace username a groupname z realpath
        forceUser, uid = mp.forUser()
        forceGrp, gid = mp.forGroup()        
        
        if mp.pathExists() is False:
            raise RuntimeError(f"Mount point path does not exist: {mp.mountPath}")
        if not mp.mountExists():
            log.info(f"Creating mount point directory: {mp.mountPath}")
            try:
                os.makedirs(mp.mountPath, exist_ok=True)
                os.chown(mp.mountPath, uid, gid)
                os.chmod(mp.mountPath, 0o700)
            except Exception as e:
                msg=f"Failed to create mount point directory {mp.mountPath}: {e}"
                log.error(msg)
                log.exception(e)
                raise RuntimeError(msg)
        
        if mp.isMountpointPathsOK() is False:
            raise RuntimeError("Mount point paths are not OK.")
                
        log.info(f" - Ensuring Samba SFTP mount point for share {base_share_name} at target {source}.")
        # vytvoří sourcePath  > //localhost/sftp_mount_user_sharename
        smbHelp.ensureSambaSharePoint(source, base_share_name, forceUser, forceGrp)
        if not restartSambaService():
            msg=f"Failed to restart Samba service after adding mount point for share {base_share_name}."
            log.error(msg)
            raise RuntimeError(msg)
        
        log.info(f" - Ensuring fstab CIFS config for Samba SFTP mount point {base_share_name}.")
        if not smbHelp.ensureFstabCIFScfg(base_share_name, forceUser,forceGrp, target):
            msg=f"Failed to ensure fstab CIFS line for Samba SFTP mount point {base_share_name}."
            log.error(msg)
            raise RuntimeError(msg)
        
        # check mounted
        log.info(f" - Ensuring Samba SFTP mount point {base_share_name} is mounted.")
        cifs_path=smbHelp.getCIFSpath(base_share_name, forceUser)
        if smbHelp.isMounted(base_share_name, forceUser):
            log.info(f"< Samba SFTP mount point {cifs_path} is already mounted.")
            # už je namountováno
            return cifs_path
        
        # mount it
        log.info(f" - Mounting Samba SFTP mount point {cifs_path}.")
        try:
            import subprocess
            subprocess.run([
                "mount",
                cifs_path
            ], check=True)
        except subprocess.CalledProcessError as e:
            msg=f"Failed to mount Samba SFTP mount point {cifs_path}: {e}"
            log.error(msg)
            log.exception(e)
            raise RuntimeError(msg)        
    except Exception as e:
        msg=f"Failed to ensure Samba SFTP mount point: {e}"
        log.error(msg)
        log.exception(e)
        log.info(f" - Cleaning up Samba SFTP")
        try:
            removeSharePoint(mp)
        except Exception as e2:
            log.error(f"   - Failed to clean up Samba SFTP")
            log.exception(e2)
        raise RuntimeError(msg)
    
    log.info(f"< Samba SFTP mount point {cifs_path} mounted successfully.")
    return cifs_path
    
    