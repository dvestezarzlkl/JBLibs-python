# cspell:ignore levelname,HLPR,STPENA,STPDIS,geteuid
from .lng.default import *
import os, platform,sys,logging,subprocess,inspect,hashlib
from importlib import util
from typing import Union
import configparser,re

__LoggerInit:bool=False

def initLogging(file_name:str="app.log"):
    """
    Inicializuje logging pro skript se jménem souboru v parametru
    
    Parameters:
        file_name (str): nepovinný parametr, jméno souboru pro logování
        
    Returns:
        None
    """
    logging.basicConfig(
        level=logging.DEBUG,  # Určuje minimální úroveň záznamů (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler(file_name),  # Záznamy se ukládají do souboru 'app.log'
        ]
    )

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

def getLogger(name:str):
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

log = logging.getLogger(__name__)
    
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
    Smaže obsah konzole
    
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