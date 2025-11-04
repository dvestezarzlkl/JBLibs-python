# cspell:ignore levelname,HLPR,STPENA,STPDIS,geteuid
from .lng.default import *
import os, platform,sys,logging,subprocess,inspect,hashlib
from importlib import util
from typing import Union,Callable,Union,Tuple
import configparser,re,psutil
from select import select as t_sel
from typing import List

__LoggerInit:bool=False
__myLog:logging.Logger|None=None
"""logger pro tento helper"""

class c_prcLstn:
    processName:str=""
    processID:int=0
    userName:str=""
    ip:str=""
    port:int=0

    def __init__(self, processName:str="", processID:int=0, userName:str="", ip:str="", port:int=0):
        self.processName=processName
        self.processID=processID
        self.userName=userName
        self.ip=ip
        self.port=port
    
    def __repr__(self):
        return f"proc: {self.processName}, pid: {self.processID},  u: {self.userName}, tcp ip:port: {self.ip}:{self.port}"

class c_interface:
    name:str=""
    ipv4:str=""
    ipv6:str=""
    mac:str=""

    def __repr__(self):
        return f"interface: {self.name}, ipv4: {self.ip}, ipv6: {self.ipv6}, mac: {self.mac}"

def getMainScriptDir()->str:
    """
    Vrátí cestu ke složce, kde je hlavní spouštěcí skript
    
    Returns:
        str: cesta ke složce s hlavním skriptem
    """
    if getattr(sys, 'frozen', False):
        # Pokud je aplikace zabalena pomocí PyInstaller
        return os.path.dirname(sys.executable)
    else:
        # Pokud je aplikace spuštěna jako běžný Python skript
        return os.path.dirname(os.path.abspath(sys.argv[0]))

def initLogging(i_file_name:str="app.log",max_bytes: int = 1_000_000, backup_count: int = 3, toConsole: bool = False)->None:
    """
    Inicializuje logging pro skript se jménem souboru v parametru
    
    Parameters:
        file_name (str): nepovinný parametr, jméno souboru pro logování
        
    Returns:
        None
    """
    global __LoggerInit
    
    # pokud exituje LOG_DIR z configu tak použijeme tento adresář
    # pokud je None tak se použije adresář aplikace
    import libs.config as cfg
    
    file_name=os.path.join(getMainScriptDir(),'logs',i_file_name) # defaultní cesta
    
    # pokud neexistuje logdir pokusíme se jeje vytvořit
    if cfg.LOG_DIR and not os.path.exists(cfg.LOG_DIR):
        try:
            os.makedirs(cfg.LOG_DIR, exist_ok=True)
            # nastavíme pro všechny
            os.chmod(cfg.LOG_DIR, 0o755)
            print(f"Created log dir '{cfg.LOG_DIR}'.", file=sys.stderr)
        except Exception as e:
            print(f"Could not create log dir '{cfg.LOG_DIR}': {e}", file=sys.stderr)
    
    # pokud existuje a je writable tak použijeme tento adresář
    if cfg.LOG_DIR and os.path.exists(cfg.LOG_DIR) and os.path.isdir(cfg.LOG_DIR):
        if not os.access(cfg.LOG_DIR, os.W_OK):
            print(f"Log dir '{cfg.LOG_DIR}' is not writable, using script dir instead.", file=sys.stderr)
        else:
            file_name=os.path.join(cfg.LOG_DIR,i_file_name)
    
    from logging.handlers import RotatingFileHandler
    
    # --- Handlery ---
    file_handler = RotatingFileHandler(file_name, maxBytes=max_bytes, backupCount=backup_count)    

    # Formát pro oba
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(formatter)

    handlers=[
        file_handler
    ]
    if toConsole:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    # --- Logging config ---
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=handlers
    )
    
    log=logging.getLogger('LOG-INIT')
    log.info(f"Logging initialized to file '{file_name}', max size: {max_bytes}, backup count: {backup_count}.")
    
    __LoggerInit=True

def sanitizeUserName(username: str) -> Union[str,None]:
    """Ošetří jméno uživatele
    
    Parameters:
        username (str): jméno uživatele
        
    Returns:
        Union[str,None]: ošetřené jméno uživatele nebo None při chybě
    """
    if not username:
        return None
    username = str(username).strip()
    if not username:
        return None
    return username

def userExists(userName:str,checkWhiteSpace=True)->Union[bool,None]:
    """
    Check if user exists
    
    Parameters:
        userName (str): user name
        checkWhiteSpace (bool): check if there are any white spaces at the beginning or end of the user name
        
    Returns:
        Union[bool,None]: True if user exists, False if not, None if error
    """
    if not isinstance(userName, str):
        return None
    u=userName.strip()
    if checkWhiteSpace and u!=userName:
        return None
    if not userName:
        return None
    result = subprocess.run(['id', '-u', userName], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0

def getLogger(name:str)->logging.Logger:
    """
    Vráti instanci loggeru, pokud ještě nebyl inicializován, inicializuje se viz initLogging()
    
    See:
        initLogging()
    
    Parameters:
        name (str): jméno loggeru
        
    Returns:
        logging.Logger: instance loggeru
    """
    global __LoggerInit
    if not __LoggerInit:
        initLogging()
        __LoggerInit=True
    return logging.getLogger(name)

def getMyLog()->logging.Logger:    
    global __myLog
    if __myLog is None:
        __myLog=getLogger('HELPER')
    return __myLog

def isSystemLinux()->bool:
    """
    Check if system is Linux
    
    Parameters:
        None
        
    Returns:
        bool: True if system is Linux, False otherwise
    """
    return platform.system() == "Linux"

def haveSystemd()->bool:
    """
    Check if system has systemd
    
    Parameters:
        None
        
    Returns:
        bool: True if system has systemd, False otherwise
    """
    if not isSystemLinux():
        return False
    return os.path.exists('/bin/systemctl')

def cls()->None:
    """
    Smaže obsah konzole pomoc cls/clear
    
    Parameters:
        None
    """
    if isSystemLinux():
        os.system('clear')
    else:
        os.system('cls')

def constrain(val:Union[int,float] , min_val, max_val) -> Union[int,float]:
    """
    Omezí hodnotu na zadaný rozsah, viz Arduino 
    
    Parameters:
        val (Union[int,float]): hodnota
        min_val (Union[int,float]): minimální hodnota
        max_val (Union[int,float]): maximální hodnota
        
    Returns:
        Union[int,float]: omezená hodnota
    """
    return max(min(val, max_val), min_val)

__lng='cs-CZ'
__lng_cache={}

def setLng(lng:str='cs-CZ')->None:
    """
    Nastaví jazyk pro skript, který se použije pro výběr jazykového modulu, jen nastavuje proměnnou
    pro načtení je třeba volat loadLng
    
    Example:
        V primárním - spouštěcím skriptu definujeme jazyk:
        ```python
        from libs.JBLibs.helper import setLng   # importujeme pouze funkci setLng pokud nepotřebujeme loadLng
        setLng('cs-CZ')                         # nastavíme jazyk, který se musí shodovat s názvem souboru v adresáři lng
        ```
        
        V dalších skriptech kde chceme použít jazykové proměnné:
        ```python
        from libs.JBLibs.helper import *        # toto použijeme kvůli IDE a autocomplet-u, jinak se může vypustit
        from libs.JBLibs.helper import loadLng  # importujeme pouze funkci loadLng
        loadLng()                               # načteme jazykový modul
        ```
    
    Parameters:
        lng (str): jazyk
        
    Returns:
        None
    """
    log=getMyLog()
    if not isinstance(lng,str):
        log.error("Language must be a string.")
        return
    global __lng
    __lng=lng
    log.info(f"Language set to '{__lng}'.")
    
    loadLng() # aby se i tu načetl jazykový modul

def loadLng()->None:
    """
    Načte jazykový modul pro skript, ze kterého je voláno  
    Načítá relativně k souboru, ze kterého je voláno do složky lng
    
    Parameters:
        None
        
    Returns:
        None        
    """
    try:
        log=getMyLog()
        # Získáme cestu souboru, ze kterého byla funkce volána
        frame_stack = inspect.stack()
        if len(frame_stack) < 2:
            log.warning("There is not enough stack depth to get the calling module.")
            return

        frame = frame_stack[1]
        if len(frame) < 1:
            log.warning("There is not enough stack depth to get the calling module.")
            return

        caller_module = inspect.getmodule(frame[0])

        if caller_module is None:
            log.warning("Cannot determine the calling module.")            
            return

        caller_file = frame.filename
        file_dir = os.path.dirname(caller_file)
        log.debug(f"Loading language file for '{file_dir}'.")

        lng_file_default = os.path.join(file_dir, 'lng', 'default.py')
        lng_file = os.path.join(file_dir, 'lng', f'{__lng}.py')
        
        # Hash souboru pro uložení do cache
        hash_key_lng = hashlib.sha256(lng_file.encode()).hexdigest()

        # Pokud je již načten v cache, použijeme jej
        if hash_key_lng in __lng_cache:
            log.debug(f"-- HitCache for {__lng}")
            __updateGlob(caller_module,__lng_cache[hash_key_lng])
            return
        
        hash_key_def = hashlib.sha256(lng_file_default.encode()).hexdigest()
        if hash_key_def in __lng_cache:
            log.debug(f"-- HitCache for default")
            __updateGlob(caller_module,__lng_cache[hash_key_def])
            
        # Načteme default-ní jazykový soubor
        __lng_dict = {}
        if os.path.exists(lng_file_default):
            log.debug(f"-- Loading default language file '{lng_file_default}'.")
            __load_file_to_dict(lng_file_default, __lng_dict)

        # Pokud existuje konkrétní jazykový soubor, přepíšeme hodnoty
        if os.path.exists(lng_file):
            log.debug(f"-- Updating language from file '{lng_file}'.")
            hash_key_def=hash_key_lng
            __load_file_to_dict(lng_file, __lng_dict)

        # Uložíme do cache a aktualizujeme globální proměnné volajícího modulu
        __lng_cache[hash_key_def] = __lng_dict
        __updateGlob(caller_module,__lng_dict)

    except ModuleNotFoundError:
        log.info(f"Jazykový modul '{__lng}' nenalezen, používá se výchozí.")
    

def __updateGlob(m,lngDict:dict):
    """ Provede update globs ze slovníku s jazykovými proměnnými
    
    Parameters:
        m (module): modul, který volal funkci
        lngDict (dict): slovník s jazykovými proměnnými
        
    Returns:
        None
    """
    glob = m.__dict__
    glob.update(lngDict)

def __load_file_to_dict(file_path: str, target_dict: dict):
    """
    Načte proměnné z daného souboru do cílového slovníku
    
    Parameters:
        file_path (str): cesta k souboru
        target_dict (dict): cílový slovník
        
    Returns:
        None
    """
    spec = util.spec_from_file_location(os.path.basename(file_path), file_path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Přepíšeme existující definice pouze těmi, které mají prefix 'TXT_'
    for key, value in vars(module).items():
        if key.startswith('TXT_') or key.startswith('TX_'):
            target_dict[key] = value


def check_root_user(exitIfNotRoot:bool=True)->bool:
    """
    Check if script is run as root
    
    Parameters:
        exitIfNotRoot (bool): exit if not root
        
    Returns:
        bool: True if root, False otherwise
    """
    from sys import exit
    if os.geteuid() != 0:
        if exitIfNotRoot:
            print(TXT_HLPR_MUST_BE_ROOT)
            exit(1)
        return False
    return True

def getAssetsPath(filename:str=None)->str:
    """
    Return path to assets directory
    
    Parameters:
        filename (str): filename to be added to path if specified
        
    Returns:
        str: path to assets directory
    """
    filename=str(filename).strip()
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    p=os.path.join(script_dir,'assets')
    if filename:
        p=os.path.join(p,filename)        
    return p

def is_numeric(value)->bool:
    """Check if value is numeric

    Args:
        value (Any): Any value

    Returns:
        bool: True if value is numeric, False otherwise
    """
    return isinstance(value, (int, float, complex))

def load_config()->None:
    """Načte konfigurační soubor config.ini z adresáře, kde je spuštěn hlavní skript
    a přepíše globální proměnné v modulu cfg.py

    Returns:
        None

    Raises:
        FileNotFoundError: detailní popis chyby
    """
    log=getMyLog()
    # Získat cestu ke složce, kde je hlavní skript spuštěn
    script_dir = os.getcwd()
    config_path = os.path.join(script_dir, "config.ini")

    # Načíst a přepsat globální proměnné, pokud soubor existuje
    config = configparser.ConfigParser()
    config.optionxform = str # zachovat původní velikost písmen klíčů
    if os.path.exists(config_path):
        config.read(config_path)                
        if 'globals' in config:            
            frame_stack = inspect.stack()
            if len(frame_stack) < 2:
                log.warning("There is not enough stack depth to get the calling module.")
                return

            frame = frame_stack[1]
            if len(frame) < 1:
                log.warning("There is not enough stack depth to get the calling module.")
                return
            # otestujeme že caller je config, protože je určen jen pro něj, tzn cfg.py
            if not frame.filename.endswith('/cfg.py'):
                raise FileNotFoundError(f"Only cfg.py can call load_config().")

            caller_module = inspect.getmodule(frame[0])

            if caller_module is None:
                log.warning("Cannot determine the calling module.")
                return
            vars = {key: parse_ini_value(config['globals'][key].strip('"')) for key in config['globals']}
            __updateGlob(caller_module,vars)
            
    else:
        raise FileNotFoundError(f"Config file '{config_path}' not found.")
    
    
def parse_ini_value(value:str)->Union[int,float,str,None]:
    """Převede hodnotu z ini souboru na int, float, str, None nebo bool
    
    Parameters:
        value (str): hodnota z ini souboru

    Returns:
        Union[int,float,str,None]: převedená hodnota
    """
    # pokud začíná " tak je to řetězec a odstraníme " na začátku a konci
    if value.startswith('"') and value.endswith('"'):
        value = re.sub(r'^"|"$', '', value)
        return value
    v=value.lower()
    if v in ['true','false']:
        return v == 'true'
    if v in ['none','null'] or not value:
        return None
    try:
        # Zkusit převést na int
        return int(value)
    except ValueError:
        try:
            # Zkusit převést na float
            return float(value)
        except ValueError:
            # Pokud je None, vrátit None
            if value.lower() == 'none':
                return None
            # Jinak vrátit jako řetězec
            return value
        
def sleep_ms(ms: int):
    """Jako time.sleep ale přesnější

    Parameters:
        ms (int): počet milisekund
    """
    seconds = ms / 1000.0
    # select.select([], [], [], timeout) uspí po dobu "timeout" v sekundách
    t_sel([], [], [], seconds)

def getListeningPorts(processName:str="node node-red")->List[c_prcLstn]:
    """Vrátí seznam portu pro zadaný proces
    
    Parameters:
        processName (str): jméno procesu, mezera odděluje více jmen
        
    Returns:
        List[c_prcLstn]: seznam portů
    """
    ret=[]
    psN=processName.lower.strip().split(' ')
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == psutil.CONN_LISTEN:
            pid = conn.pid
            if pid is not None:
                try:
                    process = psutil.Process(pid)
                    if process.name().lower() in psN:
                        item = c_prcLstn()
                        item.processName=process.name()
                        item.processID=pid
                        item.userName=process.username()
                        item.ip=conn.laddr.ip
                        item.port=conn.laddr.port
                        ret.append(item)                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    return ret

def getUserHome(username: str) -> Union[str,None]:
    """ vrátí cestu k domovskému adresáři uživatele
    
    Parameters:
        username (str): jméno uživatele
    
    Returns:
        Union[str,None]: cesta k domovskému adresáři uživatele nebo None při chybě bez lomítek na konci
    """
    user=sanitizeUserName(username)
    if user:
        return f'/home/{user}'
    return None

def getUserList(filter:Callable[[str],bool]=None,asTuple=False)->Union[ List[str] , List[Tuple[int,str]] ]:
    """
    Return list of system users with node config file in hos home directory
    vrací seznam uživatelů, popřípadě filtrované pomocí funkce `filter`
    vrací seznam uživatelů nebo indexovaný seznam tuple (index,username)
    
    Parameters:
        filter (callable): filter function syntax: filter(username:str)->bool
    
    Returns:
        List[str]: list of system users
        List[Tuple[int,str]]: list of tuples (index,username)
        
    """
    ret = [d for d in os.listdir('/home') if os.path.isdir(os.path.join('/home', d))]

    if callable(filter):
        ret=[d for d in ret if filter(d)]
    ret.sort()
    
    if asTuple:
        r=[]    
        for idx, user in enumerate(ret):
            r.append((idx,user))
        return r

    return ret

def getInterfaces(noLoop:bool=True)->List[c_interface]:
    """
    Return list of network interfaces
    
    Returns:
        List[c_interface]: list of network interfaces
    """
    import socket
    ret = []
    for iface, addrs in psutil.net_if_addrs().items():
        item = c_interface()
        item.name = iface

        for addr in addrs:
            if addr.family == socket.AF_INET:  # IPv4 address
                item.ipv4 = addr.address
            elif addr.family == socket.AF_INET6:  # IPv6 address
                item.ipv6 = addr.address
            elif addr.family == psutil.AF_LINK:  # MAC address (Linux specific)
                item.mac = addr.address

        if noLoop and item.name == 'lo':
            continue
        ret.append(item)

    return ret

def waitForSec(seconds:float, callableCheckToStopSec:callable=None, callableCheckToStopLoop:callable=None)->int:
    """
    Čeká zadaný počet sekund, ale reaguje na SIGINT a SIGTERM
    a každou sekundu zapíše do logu že čeká.
    
    Parameters:
        seconds (float): počet sekund k čekání
        callableCheckToStopSec (callable, optional): Vrací True pro stop čekání  
            - nepovinná funkce, která se volá každou sekundu,
            - pokud vrátí True, tak se čekání přeruší a funkce vrátí True - protože to není přerušení signálem,
            - je to pomocná funkce pro případ že chcete čekání přerušit jiným způsobem než signálem, třeba že byla
            splněna určitá podmínka, že už se nemusí čekat.
        callableCheckToStopLoop (callable, optional): Stejná funkce jako callableCheckToStopSec, ale volá se v každé iteraci smyčky
        
    Returns:
        bool: vrací:
                - 0 pokud bylo vše OK a proběhlo celé čekání,
                - 1 pokud bylo čekání přerušeno signálem,
                - 2 pokud bylo čekání přerušeno callableCheckToStop vracející
                - 9 pokud bylo zadáno <=0 sekund, takže se nečekalo vůbec.
        
    """    
    log = getMyLog()

    import time
    import libs.run_vars as gVars
    
    if(seconds<=0):
        return 9
    
    log.info(f"Waiting for {seconds} seconds (can be interrupted with Ctrl-C)...")
    t0=time.time()
    dif=0
    sec=0
    while not gVars.getSTOP() and dif<seconds:
        time.sleep(.1)
        if int(dif)>sec:
            sec=int(dif)
            log.info(f"  ... waited {int(dif)} seconds ...")
            if callableCheckToStopSec and callableCheckToStopSec():
                log.info(" - Wait interrupted by callableCheckSec.")
                return 2
        if callableCheckToStopLoop and callableCheckToStopLoop():
            log.info(" - Wait interrupted by callableCheckLoop.")
            return 2
        dif=time.time()-t0
    if gVars.getSTOP():
        log.info(" - Wait interrupted by signal.")
        return 1
    else:
        log.info(" - Wait completed.")
        return 0