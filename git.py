import subprocess
import os
import getpass
from typing import Optional
import libs.config as cfg # závislost na konfiguračních props, viz kiosk projekt
from libs.helper import getLogger
import re
from pathlib import Path

log = getLogger('git_updater')

class git:
    """Třída pro správu git repozitářů, kontrolu a aktualizaci.
    - Pokud chceme jen zkontrolvat update tak voláme git.check(path,user)
    - Pokud chceme provést update tak voláme git.update(path,user)
    
    **Path** je cesta k repozitáři na disku, tzn tam kde je přítomný adresář .git,
    **User** je uživatel systému pod kterým chceme spustit git příkazy (může být root nebo jiný systémový uživatel) 
    
    soubor credential je potom hledán buď u:
    - root v `/opt/kiosk/creds/root/.g_c` tzn cesta je `{credDirRoot}/{credSubDir}/root/{credFilename}`
    - sys_user v `/opt/kiosk/creds/sys_user/.g_c` tzn cesta je `{credDirRoot}/{credSubDir}/{username}/{credFilename}`
    
    Pozor pokud použijeme overrideDirUser tak se použije tento uživatel pro hledání credentials místo uživatele systému - pokud není vstup 'root'.
    Tzn pro root bude cesta stejná jako výše ale pro jakéhokoliv jinho uživatele bude:  
    `/opt/kiosk/creds/{overrideDirUser}/.g_c` tzn cesta je `{credDirRoot}/{credSubDir}/{overrideDirUser}/{credFilename}`
    
    """    
    dbg:bool=False
    
    def __init__(        
            self,
            credDirRoot:str="/opt/kiosk/",
            credSubDir:str="creds",
            credFilename:str=".g_c",
            overrideDirUser:str=None
        ):
        """Inicializace třídy git pro správu git repozitářů.
        Arguments:
            credDirRoot (str): kořenový adresář kde jsou uložené git credentials
            credSubDir (str): podadresář uvnitř root adresáře kde jsou uložené git credentials pro různé uživatele
            credFilename (str): název souboru s git credentials uvnitř uživatelského adresáře
        Raises:
            FileNotFoundError: pokud neexistuje adresář s credentials
        """
        
        self.credDir:str=os.path.join(credDirRoot,credSubDir)
        """Adresář kde jsou uložené git credentials pro různé uživatele systému."""
        
        if not os.path.exists(self.credDir) or not os.path.isdir(self.credDir):
            raise FileNotFoundError(f"Creds dir '{self.credDir}' not found.")  
        
        self.credFilename:str=credFilename
        """Název souboru s git credentials uvnitř uživatelského adresáře."""
        
        self.overrideDirUser:str=overrideDirUser
        """Pokud je nastaveno, použije se tento uživatel pro hledání credentials místo uživatele systému - pokud není vstup 'root'. Tzn jakýkoliv
        jiný user než 'root' bude mít stejný adresář pro credentials s tímto názvem"""

    def _get_git_url_from_netrc(self,file:str) -> str:
        """
        Načte .netrc pro daného uživatele a vrátí plnou URL s přihlašovacími údaji.
        Pokud se nepodaří načíst, vrátí původní repo_url.
        """
        if not os.path.exists(file) or os.path.isdir(file):
            raise FileNotFoundError(f"Cred file '{file}' not found")

        netrc_path = Path(file)        
        content = netrc_path.read_text().strip()
        match = re.search(r"machine\s+(\S+)\s+login\s+(\S+)\s+password\s+(\S+)", content)
        if not match:
            raise ValueError(f".netrc file '{file}' is malformed.")

        machine, login, password = match.groups()        
        return f"https://{login}:{password}@{machine}"

    def _run(self, cmd: list[str], cwd: str, user: Optional[str] = None) -> tuple[int, str, str]:
        """Spustí příkaz a vrátí (retcode, stdout, stderr).
        Arguments:
            cmd (list): seznam argumentů příkazu
            cwd (str): pracovní adresář
            user (str | None): uživatel systému pod kterým spustit příkaz, pokud None tak se veme aktuální uživatel
        Returns:
            tuple: (retcode, stdout, stderr)
        """
        temp_cred_file = None
        log.info(f"  > RUN CMD     : '{' '.join(cmd)}'")
        try:
            u = getpass.getuser()
            if user is None:
                user = u
            log.info(f"    -* USER        : '{user}' (aktuální: '{u}')")

            credUser = user if user == "root" else (self.overrideDirUser if self.overrideDirUser else user)
            
            log.info(f"    -* CRED-USER: {credUser}")

            home = os.path.join(self.credDir, credUser)
            if not os.path.isdir(home):
                raise FileNotFoundError(f"Credential directory '{home}' not found for user '{credUser}'.")
            if self.dbg: log.info(f"    -* HOME        : '{home}'")

            cred_path = os.path.join(home, ".g_c")
            if not os.path.exists(cred_path):
                raise FileNotFoundError(f"Credential file '{cred_path}' not found for user '{user}'.")
            if self.dbg: log.info(f"    -* CRED FILE   : '{cred_path}'")


            if os.path.exists(cred_path) and os.path.isfile(cred_path):
                # Pozor: Git očekává jen jednu volbu po -c
                cmd = cmd[:1] + ["-c", f"credential.helper=store --file={cred_path}"] + cmd[1:]
            if self.dbg: log.info(f"    -* CWD         : '{cwd}'")

            # Použij sudo jen pokud spouštíš pod jiným uživatelem
            if user != u:
                cmd = ["sudo", "-u", user] + cmd
            if self.dbg: log.info(f"    -*** CMD         : '{' '.join(cmd)}'")

            proc = subprocess.run(
                cmd,
                cwd=cwd,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )

            return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

        except Exception as e:
            log.exception(e)
            return 1, "", str(e)

        finally:
            log.info(f"  < RETURN CODE: {proc.returncode}")
            if self.dbg:
                if proc.stdout:
                    log.info(f"  < - STDOUT     : {proc.stdout.strip()}")
                if proc.stderr:
                    log.info(f"  < - STDERR     : {proc.stderr.strip()}")
            if temp_cred_file and os.path.exists(temp_cred_file):
                try:
                    os.remove(temp_cred_file)
                except OSError:
                    pass


    def _get_upstream(self, path: str, user: Optional[str]) -> Optional[str]:
        """Vrátí plný název upstream refu (např. 'origin/main') nebo None, pokud není nastaven."""
        code, out, err = self._run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], path, user)
        if code == 0 and out and out != "@{u}":
            return out
        return None

    def _get_branch(self, path: str, user: Optional[str] = None) -> str:
        """Vrátí jméno aktuální větve, nebo 'main' pokud se nepodaří zjistit.
        Arguments:
            path (str): cesta k git repozitáři
            user (str | None): uživatel systému pod kterým spustit příkaz, pokud None tak se veme aktuální uživatel
        Returns:
            str: jméno větve nebo 'main'
        """
        code, out, err = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path, user)
        # detached HEAD vrací 'HEAD' → v tom případě raději fallback na 'main'
        if code == 0 and out and out != "HEAD":
            return out
        return "main"

    def check(self, path: str, user: Optional[str] = None) -> bool:
        """Vrátí True pokud existují nové commity k fetchnutí.
        Pokud cesta neexistuje, není git repozitář nebo nemá remote, vrací False.
        Arguments:
            path (str): cesta k git repozitáři
            user (str | None): uživatel systému pod kterým spustit příkaz, pokud None tak se veme aktuální uživatel
        Returns:
            bool: True pokud jsou nové commity, jinak False
        """
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Cesta {path} neexistuje nebo není adresář.")

        if not os.path.isdir(os.path.join(path, ".git")):
            raise FileNotFoundError(f"{path} není git repozitář.")
            
        log.info(f">>> Kontroluji {path}, existuje .git.")

        # test na remote definici
        # code, out, err = self._run(["git", "remote"], path, user)
        # if code != 0 or not out:
        #     log.error(f"  - {path}: nemá žádný remote (readonly).")
        #     return False

        # Zjisti upstream (preferuj @{u}), fallback na origin/<branch>
        upstream = self._get_upstream(path, user)
        if not upstream:
            branch = self._get_branch(path, user)
            upstream = f"origin/{branch}"

        # Fetch konkrétní upstream remote (odděl remote a větev)
        if "/" in upstream:
            remote, remote_branch = upstream.split("/", 1)
        else:
            # extrémní fallback
            remote, remote_branch = "origin", "main"

        log.info(f"  - {path}: kontrola vůči {upstream} ...")
        fcode, _, ferr = self._run(["git", "fetch", remote, remote_branch], path, user)
        if fcode != 0:
            log.error(f"  ! fetch selhal: {ferr}")
            return False

        # Porovnej HEAD s upstream
        code, out, err = self._run(["git", "rev-list", f"HEAD..{upstream}", "--count"], path, user)
        if code == 0 and out.isdigit():
            log.info(f"  = rozdíl vůči {upstream} je {out} commitů.")
            return int(out) > 0
        else:
            log.error(f"  ! {path}: selhalo zjištění rozdílu vůči {upstream}. {err}")
            return False

    def update(self, path: str, user: Optional[str] = None) -> Optional[str]:
        """Provede update (git pull), pokud jsou dostupné změny.
           Vrací None pokud je vše v pořádku, jinak chybový text.
        Arguments:
            path (str): cesta k git repozitáři
            user (str | None): uživatel systému pod kterým spustit příkaz, pokud None tak se veme aktuální uživatel
        Returns:
            str | None: None pokud je vše v pořádku, jinak chybový text
        """
        if not self.check(path, user):
            return None

        # Stejná logika upstreamu jako v check()
        upstream = self._get_upstream(path, user)
        if upstream and "/" in upstream:
            remote, remote_branch = upstream.split("/", 1)
        else:
            remote, remote_branch = "origin", self._get_branch(path, user)

        isRoot=user=="root"

        log.info(f" ******* Aktualizuji {path} ({remote}/{remote_branch}) ... *******")

        code, out, err = self._run(["git", "pull", remote, remote_branch], path, user)
        if code == 0:
            log.info(f"{path}: aktualizace úspěšná.")
            
            # přidáme update submodulů pokud nějaké jsou
            try:                
                # nejdřív synchronizovat konfiguraci submodulů (pro jistotu)
                self._run(["git", "submodule", "sync", "--recursive"], path, user)

                # pak inicializovat a zároveň fetchnout remote data
                code2, out2, err2 = self._run(["git", "submodule", "update", "--init", "--recursive", "--remote"], path, user)
                
                if code2 == 0:
                    log.info(f"{path}: submoduly aktualizovány.")
                else:
                    log.error(f"{path}: selhalo aktualizování submodulů: {err2}")
            except Exception as e:
                log.exception(e)
                log.error(f"{path}: výjimka při aktualizaci submodulů")
            
            import libs.config as cfg
            if not isRoot:
                # pokud je to root, tak aktualizujeme mtime na souboru NODE_RED_RESTART_FILE aby se provedl restart démona
                try:
                    os.utime(cfg.NODE_RED_RESTART_FILE)
                    log.info(f"{path}: updated mtime of NODE_RED_RESTART_FILE to trigger Node-RED restart.")
                except Exception as e:
                    log.error(f"{path}: failed to update mtime of NODE_RED_RESTART_FILE: {e}")
                    log.exception(e)
            else:
                # je to ruut takže vyrestartuejem démona, tzn aktualizujeme mtime na souboru request_restart_me
                try:
                    os.utime(cfg.REQUEST_RESTART_ME_FILE)
                    log.info(f"{path}: updated mtime of REQUEST_RESTART_ME_FILE to trigger script restart.")
                except Exception as e:
                    log.error(f"{path}: failed to update mtime of REQUEST_RESTART_ME_FILE: {e}")
                    log.exception(e)
                
            
            return None
        else:
            msg = f"{path}: aktualizace selhala: {err or out}"
            log.error(msg)
            return msg

    def checkAll(self) -> bool:
        """Spec funkce pro KIOSK s node-red
        Zkontroluje všechny repozitáře, vrátí True pokud nějaký obsahuje update
        Arguments:
            None
        Returns:
            bool: True pokud je nějaký update, jinak False
        """
        for path, desc, user in cfg.GIT_UPDATES:
            # log.info(f"Kontroluji {desc} ({path} pod {user})")
            if self.check(path, user):
                return True
        return False

    def updateAll(self) -> tuple[Optional[str], int]:
        """Spec funkce pro KIOSK s node-red  
        Provede update všech repozitářů, pokud jsou dostupné změny.
        Arguments:
            None
        Returns:
            tuple:
                - str | None: None pokud je vše v pořádku, jinak chybový text
                - int: počet úspěšně aktualizovaných repozitářů
        """
        o = ""
        u = 0
        for path, desc, user in cfg.GIT_UPDATES:
            # log.info(f"Kontroluji {desc} ({path} pod {user})")
            result = self.update(path, user)
            if result:
                o += result + ". "
                log.warning(result)
            else:
                u += 1
        return (o if o else None, u)
