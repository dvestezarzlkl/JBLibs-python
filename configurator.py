import os, logging, re, shutil, subprocess, base64, sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class __hlp:
    log:logging.Logger=None
    
    @staticmethod
    def is_base64(s: str) -> bool:
        try:
            # Allow missing padding
            b = s.encode('ascii')
            # If contains whitespace/newlines it's not a single base64 token
            if any(c in b' \t\r\n' for c in b):
                return False
            base64.b64decode(b + b'===')
            return True
        except Exception:
            return False

    @staticmethod
    def write_file(path: Path, data: bytes, mode: int = 0o600, owner: Optional[str] = None, dry_run: bool = True):
        if dry_run:
            __hlp.log.info(f"[DRY] write {path} ({len(data)} bytes) mode={oct(mode)} owner={owner}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        os.chmod(path, mode)
        if owner:
            try:
                import pwd, grp
                uid = pwd.getpwnam(owner).pw_uid
                gid = pwd.getpwnam(owner).pw_gid
                os.chown(path, uid, gid)
            except Exception as e:
                __hlp.log.warning(f"chown {path} -> {owner} failed: {e}")

    @staticmethod
    def ensure_dir(path: Path, mode: int = 0o700, owner: Optional[str] = None, dry_run: bool = True):
        if dry_run:
            __hlp.log.info(f"[DRY] ensure dir {path} mode={oct(mode)} owner={owner}")
            return
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)
        if owner:
            try:
                import pwd, grp
                uid = pwd.getpwnam(owner).pw_uid
                gid = pwd.getpwnam(owner).pw_gid
                os.chown(path, uid, gid)
            except Exception as e:
                __hlp.log.warning(f"chown {path} -> {owner} failed: {e}")

    @staticmethod
    def rm_dir(path: Path, dry_run: bool = True):
        if dry_run:
            __hlp.log.info(f"[DRY] rmtree {path}")
            return
        if path.exists():
            shutil.rmtree(path)

    @staticmethod
    def remove_file(path: Path, dry_run: bool = True):
        if dry_run:
            __hlp.log.info(f"[DRY] unlink {path}")
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def run_as_user(uid_user: str, cmd: List[str], cwd: Optional[str] = None) -> Tuple[int,str,str]:
        # Simple wrapper using sudo -u for portability
        full = ["sudo", "-n", "-u", uid_user] + cmd
        try:
            p = subprocess.run(full, cwd=cwd, capture_output=True, text=True, check=False)
            return p.returncode, p.stdout, p.stderr
        except Exception as e:
            return 255, "", str(e)    

class c_sekce_item:
    def __init__(self, line:str):
        self.cmd:str|None=None
        """příkaz"""
        
        self.args:list[str]=[]
        """seznam argumentů"""
        
        self.ok=False
        """zda byl řádek správně parsován"""
        
        parts=line.split()
        if len(parts)>0:
            self.cmd=parts[0].strip()
        if len(parts)>1:
            self.args=[arg.strip() for arg in parts[1:]]
            
        self.ok=len(parts)>0 and self.cmd is not None and self.cmd!=""

class c_sekce:
    def __init__(self):
        self.all:list[c_sekce_item]=[]
        """items pro sekci 'all' - pro všechny zařízení"""
        self.byID:dict[str,list[c_sekce_item]]={}
        """dictionary of sekce items by ID"""
        self.byRGX:dict[str,list[c_sekce_item]]={}
        """dictionary of sekce items by regex"""
        self.resources:dict[str,str]={}
        """dictionary of resource data"""
        self.onBeforeStart:str|None=None
        """script to run before starting the main process"""
        self.onEnd:str|None=None
        """script to run at the end of the main process"""

"""Třída pro konfiguraci jednotky (linux nebo jiné) podle konfiguračního souboru
funkce `processID` lze použít víckrát s jiným ID pokud by se nějaká taková situace vyskytla
"""
class Configurator:
    def __init__(self, file:str, devID:str, logger:logging.Logger, dry_run: bool = True):        
        self.dry_run = dry_run
        self.context = {
            "run_user": os.getenv("USER") or "root",
            "workdir": None,
            "g_path": None,
        }        
        
        # pokud není logger tak chyba
        if logger is None:
            raise ValueError("Logger must be provided")
        
        __hlp.log=logger
        
        """logger pro logování"""
        self.log=logger
                
        # načteme soubor pokud existuje a rozdělíme na řádky, příprava pro parser
        self.lines=[]
        self.log.info(f"Loading configuration file '{file}'...")
        if file and os.path.exists(file):
            try:
                with open(file,"r",encoding="utf-8") as f:
                    self.lines=f.readlines()
                    self.log.info(f"Configuration file '{file}' loaded, {len(self.lines)} lines.")
            except Exception as e:
                self.log.error(f"Error loading configuration file '{file}'")
                self.log.exception(e)
                sys.exit(1)
        else:
            self.log.warning(f"Configuration file '{file}' not found, using empty configuration.")
            sys.exit(1)
        # odstraníme řádky od prázdných řádků a komentářů
        self.lines=[line.strip() for line in self.lines if line.strip() and not line.strip().startswith("#")]
        self.log.info(f"Configuration file '{file}' processed, {len(self.lines)} valid lines.")
        
        
        self.device_id =str(devID).strip()
        if not self.device_id or self.device_id=="" or len(self.device_id)<2:
            self.log.error("Device ID is required for configuration parsing.")
            sys.exit(1)
        
        self.sekce:c_sekce=c_sekce()
        """konfigurační sekce"""
        
        self._getSekce()
        self.processID()
    
    def _getSekce(self):
        """načteme obsahy sekcí"""
        
        detected:list=[]
        """detekované sekce""" # nesmí být zdvojené
        
        currentSekce:Optional[list[c_sekce_item]]=None
        """aktuální sekce"""
        
        lineTyp:Optional[str]=None
        """typ řádku"""
        
        for line in self.lines:
            # vybíráme regexpem
            skcHead=re.compile(r"^(?:\*a|__res__|\*\*|\?\?)(.*)$", re.IGNORECASE)
            # pokud je detekována sekce, změníme aktuální sekci
            m=skcHead.match(line)
            if m:
                sekceID=m.group(1).strip()
                if line.startswith("*a"):
                    if detected.count("all")>0:
                        self.log.error("Duplicate 'all' section detected in configuration file.")
                        sys.exit(1)
                    detected.append("all")
                    currentSekce=self.sekce.all
                    lineTyp=None
                    continue
                elif line.startswith("**"):
                    # sekce podle ID
                    sekceID="byID_"+sekceID
                    if sekceID in detected:
                        self.log.error(f"Duplicate section ID '{sekceID}' detected in configuration file.")
                        sys.exit(1)
                    detected.append(sekceID)
                    if sekceID not in self.sekce.byID:
                        self.sekce.byID[sekceID]=[]
                    currentSekce=self.sekce.byID[sekceID]
                    lineTyp=None
                    continue
                elif line.startswith("??"):
                    # sekce podle regexu
                    sekceID="byRGX_"+sekceID
                    if sekceID in detected:
                        self.log.error(f"Duplicate section regex '{sekceID}' detected in configuration file.")
                        sys.exit(1)
                    detected.append(sekceID)
                    if sekceID not in self.sekce.byRGX:
                        self.sekce.byRGX[sekceID]=[]
                    currentSekce=self.sekce.byRGX[sekceID]
                    lineTyp=None
                    continue
                elif line.startswith("__res__"):
                    # resource sekce
                    sekceID="resource_"+sekceID
                    if sekceID in detected:
                        self.log.error(f"Duplicate resource '{sekceID}' detected in configuration file.")
                        sys.exit(1)
                    currentSekce=self.sekce.resources
                    lineTyp='r'
                    continue
            elif line.startswith("^") or line.startswith("~"):
                # speciální příkazy
                cmdLine=line[1:].strip()
                if line.startswith("^"):
                    self.sekce.onBeforeStart=cmdLine
                else:
                    self.sekce.onEnd=cmdLine
                continue
            
            if line=="" or line.startswith("#") or line.strip()=="":
                continue
            
            # jen zpracování řádku
            if currentSekce is None:
                # řádek před jakoukoliv sekí je problém syntaxerror
                self.log.error("Syntax error in configuration file: command found outside of any section.")
                sys.exit(1)
            if lineTyp=='r':
                # resource řádek
                resParts=line.split(None,1)
                if len(resParts)<2:
                    self.log.error("Syntax error in resource line: missing data.")
                    sys.exit(1)
                resKey=resParts[0].strip()
                resData=resParts[1].strip()
                currentSekce[resKey]=resData
            else:
                # běžný řádek
                item=c_sekce_item(line)
                if not item.ok:
                    self.log.error("Syntax error in configuration line: missing command.")
                    sys.exit(1)
                currentSekce.append(item)
                
    def processID(self,ID:str|None=None):
        """zpracuje sekci pro dané zařízení
        Args:
            ID (str|None, optional): ID zařízení. Pokud None, použije se výchozí z konstruktoru. Defaults to None.
        Returns:
            None
        """
        if ID is not None:
            self.device_id=ID
        self._processSekce(self.sekce.all)
        sekce=self.sekce.byID.get(self.device_id)
        if sekce is not None:
            self._processSekce(sekce)
        for rgx, items in self.sekce.byRGX.items():
            # musí začínat '/' a končit '/i' nebo '/'
            if len(rgx)<3 or not rgx.startswith("/") or not (rgx.endswith("/i") or rgx.endswith("/")):
                self.log.error(f"Invalid regex section '{rgx}' in configuration file.")
                continue
            pattern=rgx[1:-2] if rgx.endswith("/i") else rgx[1:-1]
            flags=re.IGNORECASE if rgx.endswith("/i") else 0
            try:
                rgxCompiled=re.compile(pattern, flags)
            except re.error as e:
                self.log.error(f"Invalid regex pattern '{pattern}' in configuration file: {e}")
                continue
            if rgxCompiled.match(self.device_id):
                self._processSekce(items)
                
    def _processSekce(self,sekce:list[c_sekce_item]):
        """zpracuje sekci pro dané zařízení"""
        for item in sekce:
            self.log.info(f"Processing command: {item.cmd} {' '.join(item.args)}")
            self._processLine(item)
            
    def _processLine(self, item:c_sekce_item):
        """zpracuje jeden řádek příkazu"""
        cmd=item.cmd
        args=item.args
        if cmd == "=u" and args:
            self._set_user(args[0])
            return
        if cmd == "=d" and args:
            self._set_dir(args[0])
            return
        if cmd == "+d" and args:
            self._cmd_mkdir(args[0], chdir=False)
            return
        if cmd == "!d" and args:
            self._cmd_mkdir(args[0], chdir=True)
            return
        if cmd == "-d" and args:
            self._cmd_rmdir(args[0])
            return
        if cmd in ("+fl","!fl") and len(args) >= 2:
            filename = args[0]
            resource = args[1]
            overwrite = (cmd == "!fl")
            self._cmd_add_file(filename, resource, overwrite=overwrite)
            return
        if cmd == "-fl" and args:
            self._cmd_remove_file(args[0])
            return
        if cmd == "=acc" and len(args) >= 2:
            self._cmd_acc(args[0], args[1])
            return
        if cmd == "+u" and args:
            self._cmd_add_user(args[0])
            return
        if cmd == "+ssh" and args:
            self._cmd_add_ssh(args[0])
            return
        if cmd == "-ssh" and args:
            self._cmd_remove_ssh(args[0])
            return
        if cmd == "=g" and args:
            self.context["g_path"] = args[0]
            self.log.info(f"set g_path -> {self.context['g_path']}")
            return
        if cmd in ("+g","!g","-g") and args:
            opmap = {"+g":"+","!g":"!","-g":"-"}
            self._cmd_g_op(opmap[cmd], args[0])
            return
        self.log.warning(f"unknown or unsupported command: {cmd}")
            

    def _set_user(self, user: str):
        self.log.info(f"set run_user -> {user}")
        self.context["run_user"] = user

    def _set_dir(self, path: str):
        # expand ~ for given user if necessary
        if path.startswith("~"):
            # map to home dir of user in context
            if self.context["run_user"] == "root":
                path = path.replace("~", "/root", 1)
            else:
                path = path.replace("~", f"/home/{self.context['run_user']}", 1)
        self.context["workdir"] = os.path.expanduser(path)
        self.log.info(f"set workdir -> {self.context['workdir']}")

    def _cmd_mkdir(self, path: str, chdir: bool=False):
        p = Path(self._abs_path(path))
        __hlp.ensure_dir(p, owner=self.context["run_user"], dry_run=self.dry_run)
        if chdir:
            self._set_dir(str(p))

    def _cmd_rmdir(self, path: str):
        p = Path(self._abs_path(path))
        __hlp.rm_dir(p, dry_run=self.dry_run)

    def _abs_path(self, path: str) -> str:
        if path.startswith("/"):
            return path
        wd = self.context.get("workdir")
        if wd:
            return os.path.join(wd, path)
        # if no workdir, interpret relative to user's home
        if self.context["run_user"] == "root":
            base = "/root"
        else:
            base = f"/home/{self.context['run_user']}"
        return os.path.join(base, path)

    def _cmd_add_file(self, filename: str, resource_name: str, overwrite: bool=False):
        if resource_name not in self.sekce.resources:
            self.log.error(f"resource {resource_name} not found")
            return
        data = self.sekce.resources[resource_name]
        
        if isinstance(data, str):
            if __hlp.is_base64(data):
                data = base64.b64decode(data)
            else:
                data = data.encode('utf-8')
                            
        dest = Path(self._abs_path(filename))
        if dest.exists() and not overwrite:
            self.log.info(f"skip add file {dest} (exists)")
            return
        __hlp.write_file(dest, data, dry_run=self.dry_run)
        # set ownership to run_user
        if not self.dry_run:
            try:
                import pwd
                pw = pwd.getpwnam(self.context["run_user"])
                os.chown(dest, pw.pw_uid, pw.pw_gid)
            except Exception:
                pass
        self.log.info(f"file {'written' if not self.dry_run else 'would write'}: {dest}")

    def _cmd_remove_file(self, filename: str):
        p = Path(self._abs_path(filename))
        __hlp.remove_file(p, dry_run=self.dry_run)

    def _cmd_acc(self, filename: str, spec: str):
        """Upraví přístupová práva podle specifikace (např. gourwx nebo g+rwx)."""
        p = Path(self._abs_path(filename))
        if not p.exists():
            self.log.warning(f"chmod target not exist: {p}")
            return

        try:
            cur_mode = p.stat().st_mode & 0o777
            u = (cur_mode >> 6) & 0b111
            g = (cur_mode >> 3) & 0b111
            o = cur_mode & 0b111

            # rozparsuj po blocích (např. g+rwx, o, u=rw)
            tokens = re.findall(r'([ugo])([+=-]?[rwx]*)', spec.replace(" ",""))
            if not tokens:
                self.log.warning(f"chmod spec invalid: {spec}")
                return

            for who, perm in tokens:
                # pokud není operátor, ber jako smazání všech práv
                op = '=' if (perm and perm[0] in '+-=') else '-'
                perms = perm[1:] if perm and perm[0] in '+-=' else perm

                def bits(val):
                    b = 0
                    if 'r' in val: b |= 4
                    if 'w' in val: b |= 2
                    if 'x' in val: b |= 1
                    return b

                val = bits(perms)
                if who == 'u':
                    if op == '+': u |= val
                    elif op == '-': u &= ~val
                    elif op == '=': u = val
                    else: u = 0
                elif who == 'g':
                    if op == '+': g |= val
                    elif op == '-': g &= ~val
                    elif op == '=': g = val
                    else: g = 0
                elif who == 'o':
                    if op == '+': o |= val
                    elif op == '-': o &= ~val
                    elif op == '=': o = val
                    else: o = 0

            new_mode = (u << 6) | (g << 3) | o
            if self.dry_run:
                self.log.info(f"[DRY] chmod {oct(new_mode)} {p}")
            else:
                os.chmod(p, new_mode)
                self.log.info(f"chmod {oct(new_mode)} {p}")

        except Exception as e:
            self.log.warning(f"chmod failed for {p}: {e}")


    def _cmd_add_user(self, username: str):
        # quick adduser using useradd; create home.
        if self.dry_run:
            self.log.info(f"[DRY] useradd {username}")
            return
        try:
            subprocess.run(["useradd", "-m", username], check=True)
            self.log.info(f"user {username} added")
        except subprocess.CalledProcessError as e:
            self.log.warning(f"useradd failed: {e}")

    def _cmd_add_ssh(self, resource_name: str):
        # ensure .ssh in user's home and append authorized_keys if key absent
        if resource_name not in self.sekce.resources:
            self.log.error(f"ssh resource {resource_name} not found")
            return
        keydata = self.sekce.resources[resource_name].strip()
        # trusted string from resource (we expect the full authorized_keys line)
        if isinstance(keydata, bytes):
            try:
                keydata_s = keydata.decode('utf-8')
            except Exception:
                keydata_s = base64.b64encode(keydata).decode('ascii')
        else:
            keydata_s = str(keydata)
        home = "/root" if self.context["run_user"] == "root" else f"/home/{self.context['run_user']}"
        sshdir = Path(home) / ".ssh"
        auth = sshdir / "authorized_keys"
        __hlp.ensure_dir(sshdir, owner=self.context["run_user"], dry_run=self.dry_run)
        if self.dry_run:
            self.log.info(f"[DRY] add ssh key to {auth} -> {resource_name}")
            return
        auth_text = auth.read_text(encoding='utf-8') if auth.exists() else ""
        if keydata_s not in auth_text:
            with auth.open("a", encoding="utf-8") as f:
                if not auth_text.endswith("\n") and auth_text != "":
                    f.write("\n")
                f.write(keydata_s + "\n")
            os.chmod(auth, 0o600)
            try:
                import pwd
                pw = pwd.getpwnam(self.context["run_user"])
                os.chown(auth, pw.pw_uid, pw.pw_gid)
            except Exception:
                pass
            self.log.info(f"ssh key added to {auth}")
        else:
            self.log.info("ssh key already present")

    def _cmd_remove_ssh(self, resource_name: str):
        home = "/root" if self.context["run_user"] == "root" else f"/home/{self.context['run_user']}"
        auth = Path(home) / ".ssh" / "authorized_keys"
        if not auth.exists():
            self.log.info("authorized_keys not present")
            return
        if self.dry_run:
            self.log.info(f"[DRY] remove ssh key {resource_name} from {auth}")
            return
        old = auth.read_text(encoding='utf-8')
        new_lines = []
        for l in old.splitlines():
            if resource_name in l:
                continue
            new_lines.append(l)
        auth.write_text("\n".join(new_lines) + ("\n" if new_lines else ""))
        self.log.info("ssh key entries removed (matching resource name)")

    def _cmd_g_op(self, op: str, resource_name: str):
        # op: '+' add if missing, '!' add or replace, '-' remove
        gpath = self.context.get("g_path")
        if not gpath:
            self.log.error("g_path not set; use =g <path>")
            return
        dest = Path(gpath)
        dest.mkdir(parents=True, exist_ok=True)
        dest_file = dest / resource_name
        if op == '-':
            __hlp.remove_file(dest_file, dry_run=self.dry_run)
            return
        if resource_name not in self.sekce.resources:
            self.log.error(f"resource {resource_name} not found")
            return
        if op == '+' and dest_file.exists():
            self.log.info(f"g: {dest_file} exists -> skip")
            return
        data = self.sekce.resources[resource_name]
        if isinstance(data, str):
            if __hlp.is_base64(data):
                data = base64.b64decode(data)
            else:
                data = data.encode('utf-8')
        __hlp.write_file(dest_file, data, dry_run=self.dry_run)        
        self.log.info(f"g: wrote {dest_file}")