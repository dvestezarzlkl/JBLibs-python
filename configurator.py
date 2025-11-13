import os, logging, re, shutil, subprocess, base64, sys
from pathlib import Path
import json,configparser
from typing import Dict, List, Tuple, Optional

__VERSION__:str="2.0.0"

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

class c_row_parser:
    """parser pro řádek:
    - mezera se bere jako oddělovač argumentů
    - uvozovky " " umožňují mít mezery v argumentu
    - escape sekvence \n \r \" \\ umožňují vložit speciální znaky
    - escape sekvence mimo uvozovky nejsou povoleny (lze je zakázat)
    """
    def __init__(self, line: str, splitter:str=" ", escapeOutsideError: bool = True):
        self.cmd: str | None = None
        """Parser pro řádek příkazu
        Args:
            line (str): řádek k parsování
            splitter (str, optional): (def=' ') musí obsahovat jeden znak oddělovače
            escapeOutsideError (bool, optional): (ddef=True) pokud je True, tak escape sekvence mimo uvozovky vyhodí chybu. Defaults to True.
        """
        
        self.args: list[str] = []
        """seznam argumentů za příkazem, pokud jsou"""
        
        self.ok:bool = False
        """Pokud false tak v .err je popis chyby"""
        
        self.error: str | None = None
        """Popis chyby v případě že ok=false"""
        
        self.emptyLine:bool=False
        """true pokud je to prázdný řádek a výsledek je ok=true"""
        
        self.commentLine:bool=False
        """true pokud je to koment řádek a výsledek je ok=true"""

        try:
            parts, self.emptyLine, self.commentLine = self._smart_split(line, splitter, escapeOutsideError)
            if parts:
                self.cmd = parts[0]
                self.args = parts[1:]
                self.ok = True
        except ValueError as e:
            self.error = str(e)
            self.ok = False
        except Exception as e:
            self.error = f"Unexpected error: {e}"
            self.ok = False

    @staticmethod
    def _smart_split(line: str, splitter:str, escapeOutsideError: bool) -> tuple[list[str],bool,bool]:
        """Rozdělí řetězec na části, podporuje uvozovky a escapování.
        Args:
            line (str): řetězec k rozdělení
            splitter (str): musí obsahovat jeden znak oddělovače
            escapeOutsideError (bool): pokud je True, tak escape sekvence mimo uvozovky vyhodí chybu.
        Returns:
            tuple
            - list[str]: seznam částí řetězce
            - true pokud je to prázdný řádek
            - true poku je to koment řádek
            
        Raises: 
        
        """
        result = []
        current = []
        in_quote = False
        escape = False
        
        if not isinstance(splitter, str) or len(splitter) != 1:
            raise ValueError("Splitter must be a single character string")
        
        if not line or line.strip() == "":
            return [], True, False  # prázdný řádek
        
        if line.strip().startswith("#"):
            return [], False, True  # komentářový řádek

        for ch in line:
            if escape:
                if not in_quote and escapeOutsideError:
                    raise ValueError("Escape sekvence mimo uvozovky není povolena")

                if ch == 'n':
                    current.append('\n')
                elif ch == 'r':
                    current.append('\r')
                elif ch in ['"', '\\']:
                    current.append(ch)
                else:
                    if in_quote:
                        current.append('\\' + ch)
                    else:
                        current.append('\\' + ch)  # pokud je escape povolen i mimo quote
                escape = False

            elif ch == '#' and not in_quote:
                # komentář, ignorujeme zbytek řádku
                break

            elif ch == '\\':
                escape = True

            elif ch == '"':
                in_quote = not in_quote

            elif not in_quote and ((splitter == " " and ch.isspace()) or ch == splitter):
                if current:
                    result.append(''.join(current))
                    current = []

            else:
                current.append(ch)

        if in_quote:
            raise ValueError("Řetězec obsahuje neukončené uvozovky")

        if escape:
            raise ValueError("Řetězec končí neukončeným escape '\\'")

        if current:
            result.append(''.join(current))

        result = [x for x in result if x] # odstranění prázdných částí
        if not result:
            return [], True, False  # prázdný řádek

        return result, False, False

    def __repr__(self):
        if self.ok:
            if self.emptyLine:
                return "<c_row_parser EMPTY LINE>"
            if self.commentLine:
                return "<c_row_parser COMMENT LINE>"
            return f"<c_row_parser cmd={self.cmd!r} args={self.args}>"
        return f"<c_row_parser ERROR={self.error!r}>"

class c_sekce:
    def __init__(self):
        self.all:list[c_row_parser]=[]
        """items pro sekci 'all' - pro všechny zařízení"""
        self.byID:dict[str,list[c_row_parser]]={}
        """dictionary of sekce items by ID"""
        self.byRGX:dict[str,list[c_row_parser]]={}
        """dictionary of sekce items by regex"""
        self.resources:dict[str,str]={}
        """dictionary of resource data"""
        self.onBeforeStart:c_row_parser|None=None
        """script to run before starting the main process"""
        self.onEnd:c_row_parser|None=None
        """script to run at the end of the main process"""

"""Třída pro konfiguraci jednotky (linux nebo jiné) podle konfiguračního souboru
funkce `processID` lze použít víckrát s jiným ID pokud by se nějaká taková situace vyskytla
"""
class Configurator:
    def __init__(
        self, file:str,
        devID:str,
        logger:logging.Logger,
        supportColonInFloat=False,
        supportWhiteSpaceInNumbers=False,
        dry_run: bool = True
    ):
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
        
        self.supportColonInFloat:bool = supportColonInFloat == True
        """zda podporovat desetinná čísla s čárkou místo tečky"""
        
        self.supportWhiteSpaceInNumbers:bool = supportWhiteSpaceInNumbers == True
        """zda podporovat mezery v číslech (např. 1 000 000)"""
        
        """logger pro logování"""
        self.log=logger
        
        self.mod_active: bool = False
        """jestli je mod aktivní"""
        
        self.mod_filePath: Optional[str] = None
        """cesta k modifikovanému souboru"""
        
        self.mod_file: Optional[os.FileIO] = None
        """instance otevřeného souboru"""
        
        self.mod_json_content: Optional[Dict] = None
        """obsah json souboru pokud je mod typu json"""
        
        self.mod_ini_content: Optional[Dict[str,Dict[str,str]]] = None
        """obsah ini souboru pokud je mod typu ini"""
        
        self.mod_type: Optional[str] = None
        """typ modu"""
                
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
        if self.sekce.onBeforeStart:
            self.log.info(f"Running onBeforeStart script: {self.sekce.onBeforeStart}")
            self._cmd_inline_script(self.sekce.onBeforeStart.cmd, self.sekce.onBeforeStart.args)
        
        self.processID()
        
        if self.sekce.onEnd:
            self.log.info(f"Running onEnd script: {self.sekce.onEnd}")
            self._cmd_inline_script(self.sekce.onEnd.cmd, self.sekce.onEnd.args)
    
    def _getSekce(self):
        """načteme obsahy sekcí"""
        
        detected:list=[]
        """detekované sekce""" # nesmí být zdvojené
        
        currentSekce:Optional[list[c_row_parser]]=None
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
                cmdLine=c_row_parser(line[1:].strip())
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
                item=c_row_parser(line)
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
                
    def _processSekce(self,sekce:list[c_row_parser]):
        """zpracuje sekci pro dané zařízení"""
        for item in sekce:
            self.log.info(f"Processing command: {item.cmd} {' '.join(item.args)}")
            x=self._processLine(item)
            if x!='m':
                self._closeModFile()
            
    def _processLine(self, item:c_row_parser):
        """zpracuje jeden řádek příkazu
        Returns:
            None pokud je to standart příkaz
            str 'm' pokud se jedná o modifikační příkaz
        
        """
        if not item.ok:
            self.log.error(f"Invalid command line: {item.error}")
            return
        if item.commentLine or item.emptyLine:
            return
        
        cmd=item.cmd
        args=item.args
        if cmd.startswith("°") and args:
            self._cmd_inline_script(cmd[1:], args)
            return
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
        if cmd in ("=mod", "+prop", "-prop", "=prop") and args:
            if cmd=="=mod" and len(args)>=2:
                self._cmd_mod(args[0], args[1])
                return 'm'        
            else:
                action=cmd[0]  # + - =
                self._cmd_prop(action, args[0], args[1] if len(args)>=2 else None)            
            return 'm'
        if re.match(r"^([+-=])(app|npm|pip|pip3)$", cmd):
            action = cmd[0]
            pkg_type = cmd[1:]
            if args:
                self._cmd_package(action, pkg_type, args[0])
                return
            else:
                self.log.error(f"Package command '{cmd}' requires a package name.")
                return

        self._raise(SyntaxError(f"unknown or unsupported command: {cmd}"))
    
    def _cmd_inline_script(self, filename: str, args: list[str]):
        """spustí inline script na definovaném řádku
        Args:
            filename (str): cesta k souboru
            args (list[str]): argumenty pro skript
        """
        fullpath = os.path.expandvars(os.path.expanduser(filename))
        if not os.path.isabs(fullpath):
            if self.context["workdir"]:
                fullpath = os.path.join(self.context["workdir"], fullpath)
            else:
                fullpath = os.path.abspath(fullpath)
        if not os.path.exists(fullpath):
            self._raise(FileNotFoundError(f"Inline script file '{fullpath}' not found."))

        cmd = [fullpath] + args
        if self.dry_run:
            self.log.info(f"[DRY] Running inline script: {' '.join(cmd)}")
            return
        
        self.log.info(f"Running inline script: {' '.join(cmd)}")
        retcode, stdout, stderr = __hlp.run_as_user(self.context["run_user"], cmd, cwd=self.context["workdir"])
        if retcode != 0:
            self._raise(RuntimeError(f"Inline script '{fullpath}' failed with code {retcode}: {stderr.strip()}"))
        else:
            self.log.info(f"Inline script '{fullpath}' completed successfully.")
    
    def _cmd_prop(self, action: str, prop_path: str, value: Optional[str] = None):
        """Manipuluje s hodnotami v aktivním mod souboru (json nebo ini).
        Args:
            action (str): '+', '=', nebo '-' (přidat, přidat/změnit, odstranit)
            prop_path (str): cesta ve formátu "root.section.key" (s podporou quoted částí)
            value (str|None): nová hodnota (není potřeba pro '-')
        """
        if not self.mod_active or not self.mod_file or not self.mod_type:
            self._raise(ValueError(f"{action}prop použito mimo modifikační režim."))

        # Rozparsuj property path (podpora "quoted"."path with space")
        parser = c_row_parser(prop_path, splitter='.', escapeOutsideError=False)
        path = [parser.cmd] + parser.args if parser.cmd else parser.args
        if not path:
            self._raise(ValueError(f"Neplatná property cesta: '{prop_path}'"))
            
        if action in ('+', '=') and value is None:
            self._raise(ValueError(f"{action}prop '{'.'.join(path)}' vyžaduje hodnotu."))

        # =============== JSON ===============
        if self.mod_type == "json":
            self._jsonModify(action, path, value)

        # =============== INI ===============
        elif self.mod_type == "ini":
            self._iniModify(action, path, value)

        else:
            self._raise(ValueError(f"Neznámý mod_type '{self.mod_type}'"))
    
    def _auto_cast(self, val: Optional[str]) -> bool | int | float | None | str:
        """Automaticky převede řetězec na bool, int, float nebo None pokud je to možné."""
        if val is None:
            return None
        if isinstance(val, (bool, int, float)):
            return val
        
        v = str(val).strip().lower()

        # odstraň mezery mezi čísly (např. "1 234,56") – až pak testuj
        if self.supportWhiteSpaceInNumbers:
            v = v.replace(" ", "")

        match v:
            case "true":
                return True
            case "false":
                return False
            case "null" | "none" | "nan":
                return None
            case _:
                # nejdřív pokus o běžnou konverzi
                try:
                    return float(v) if "." in v else int(v)
                except ValueError:
                    pass
                
                # podpora čárky jako desetinného oddělovače
                if self.supportColonInFloat and re.match(r"^-?\d+[.,]\d+$", v):
                    if "," in v and "." in v:
                        # pokud jsou obě tak je to cz zápis formátu 1.000.000,000
                        v=v.replace(".","")
                    try:
                        return float(v.replace(",", "."))
                    except ValueError:
                        pass

                return val
    
    def _iniModify(self,action: str, path: list[str], value: Optional[str] = None):
        """Manipuluje s hodnotami v aktivním ini mod souboru.
        Args:
            action (str): '+', '=', nebo '-' (přidat, přidat
            prop_path (str): cesta ve formátu "section.key" (s podporou quoted částí)
            value (str|None): nová hodnota (není potřeba pro '-')
        Returns:
            None
        """
        ini = self.mod_ini_content
        if len(path) < 2:
            self._raise(ValueError(f"INI property musí mít alespoň sekci a klíč"))
        section = path[0]
        key = ".".join(path[1:])
        if section not in ini:
            if action == '-':
                return  # při mazání neexistující sekce nic neděláme
            ini[section] = {}

        if action in ['+','=']:
            value=self._auto_cast(value)
            value="" if value is None else str(value)
        if action == '+':
            if key not in ini[section]:
                ini[section][key] = value
                self.log.info(f"INI +prop {section}.{key} = {value}")
        elif action == '=':
            ini[section][key] = value
            self.log.info(f"INI =prop {section}.{key} = {value}")
        elif action == '-':
            if key in ini[section]:
                del ini[section][key]
                self.log.info(f"INI -prop {section}.{key} removed")
    
    
    def _jsonModify(self,action: str, path: list[str], value: Optional[str] = None):
        """Manipuluje s hodnotami v aktivním json mod souboru.
        Args:
            action (str): '+', '=', nebo '-' (přidat, přidat/změnit, odstranit)
            prop_path (str): cesta ve formátu "root.section.key" (s podporou quoted částí)
            value (str|None): nová hodnota (není potřeba pro '-')
        Returns:
            None
        """
        data = self.mod_json_content
        d = data
        for p in path[:-1]:
            if not isinstance(d, dict):
                self._raise(ValueError(f"Nelze vstoupit do '{p}' – není to objekt."))
            if p not in d:
                if action == '-':
                    return  # při mazání ignorujeme neexistující
                d[p] = {} # vytvoříme nový objekt
            d = d[p]

        key = path[-1]
        if action in ['+','=']:
            value=self._auto_cast(value)        
        if action == '+':
            if key not in d:
                d[key] = value
                self.log.info(f"JSON +prop {'.'.join(path)} = {value}")
        elif action == '=':
            d[key] = value
            self.log.info(f"JSON =prop {'.'.join(path)} = {value}")
        elif action == '-':
            if key in d:
                del d[key]
                self.log.info(f"JSON -prop {'.'.join(path)} removed")
    
    def _closeModFile(self)->None:
        """Uzavře modifikační soubor pokud je otevřený.
        Returns:
            None
        """
        if self.mod_active and self.mod_file is not None:
            # =============== Uložení změn ===============
            try:
                self.mod_file.seek(0)
                self.mod_file.truncate()
                if self.mod_type == "json":
                    json.dump(self.mod_json_content, self.mod_file, indent=2, ensure_ascii=False)
                else:
                    parser = configparser.ConfigParser()
                    for sec, kv in self.mod_ini_content.items():
                        parser[sec] = kv
                    parser.write(self.mod_file)
                self.mod_file.flush()
            except Exception as e:
                self._raise(ValueError(f"Chyba při zápisu modifikačního souboru: {e}"))            
            
            # Uzavření souboru
            self.log.info(f"Closing modification file: {self.mod_filePath}")
            self.mod_file.close()
            self.mod_active = False
            self.mod_file = None
            self.mod_type = None
            self.mod_filePath = None
            self.mod_json_content = None
            self.mod_ini_content = None
            
    def _openModFile(self,mod_type,filePath)->None:
        """Otevře modifikační soubor pro úpravy.
        Args:
            mod_type (str): typ modifikace ("json" nebo "ini")
            filePath (str): cesta k souboru
        Returns:
            None
        """        
        self._closeModFile()
        if not os.path.exists(filePath):
            self._raise(FileNotFoundError(f"File for modification not found: {filePath}"))
        self.mod_file = open(filePath, "r+", encoding="utf-8")
        self.mod_active = True
        self.mod_filePath = filePath
        self.mod_type = mod_type
        self.log.info(f"Opened modification file: {filePath} ({mod_type})")
        if mod_type == "json":
            try:
                self.mod_json_content = json.load(self.mod_file)
            except Exception as e:
                self._raise(ValueError(f"Failed to parse JSON file '{filePath}': {e}"))
        elif mod_type == "ini":
            parser = configparser.ConfigParser()
            try:
                parser.read_file(self.mod_file)
                self.mod_ini_content = {s: dict(parser.items(s)) for s in parser.sections()}
            except Exception as e:
                self._raise(ValueError(f"Failed to parse INI file '{filePath}': {e}"))
    
    def _raise(self,msg:Exception)->None:
        """Loguje a vyhazuje výjimku.
        Raises:
            Exception: předaná výjimka - vždy
        """
        self.log.exception(msg)
        raise msg
    
    def _cmd_mod(self, filename: str, mode: str):
        filePath = self._abs_path(filename)
        self._openModFile(mode, filePath)        
        self.log.info(f"Entering modification mode for {filePath} ({mode})")

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
        
    def _cmd_package(self, action: str, pkg_type: str, package: str):
        """
        Instalace, aktualizace nebo odstranění balíčku podle typu správce.
        Args:
            action (str): '+', '=', nebo '-'
            pkg_type (str): 'app', 'pip', 'pip3', 'npm'
            package (str): název balíčku
        """
        if not package or package.strip() == "":
            self.log.error(f"{pkg_type}: prázdný název balíčku není platný")
            return

        dry = "[DRY]" if self.dry_run else ""
        self.log.info(f"{dry} {pkg_type} {action}pkg {package}")

        # určování příkazu
        if pkg_type == "app":
            # detekce správce balíčků
            if shutil.which("apt-get"):
                mgr = "apt-get"
                cmds = {
                    '+': ["install", "-y", package],
                    '=': ["install", "-y", "--only-upgrade", package],
                    '-': ["remove", "-y", package],
                }
            elif shutil.which("dnf"):
                mgr = "dnf"
                cmds = {
                    '+': ["install", "-y", package],
                    '=': ["upgrade", "-y", package],
                    '-': ["remove", "-y", package],
                }
            elif shutil.which("yum"):
                mgr = "yum"
                cmds = {
                    '+': ["install", "-y", package],
                    '=': ["update", "-y", package],
                    '-': ["remove", "-y", package],
                }
            else:
                self._raise(RuntimeError("Nebyl nalezen žádný systémový správce balíčků (apt, dnf, yum)."))
                return

        elif pkg_type in ("pip", "pip3"):
            mgr = "pip3" if pkg_type == "pip3" else "pip"
            cmds = {
                '+': ["install", package],
                '=': ["install", "--upgrade", package],
                '-': ["uninstall", "-y", package],
            }

        elif pkg_type == "npm":
            mgr = "npm"
            cmds = {
                '+': ["install", "-g", package],
                '=': ["update", "-g", package],
                '-': ["uninstall", "-g", package],
            }

        else:
            self._raise(ValueError(f"Neznámý typ balíčku '{pkg_type}'"))
            return

        cmd = [mgr] + cmds[action]
        self.log.info(f"Spouštím příkaz: {' '.join(cmd)}")

        if self.dry_run:
            return

        code, out, err = __hlp.run_as_user(self.context["run_user"], cmd)
        if code == 0:
            self.log.info(f"{pkg_type} {action}pkg '{package}' -> OK")
        else:
            self.log.error(f"{pkg_type} {action}pkg '{package}' selhalo: {err or out}")
