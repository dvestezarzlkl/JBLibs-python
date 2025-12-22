# cspell:ignore dateutil,infu,timeru

from .lng.default import * 
from .helper import loadLng,haveSystemd
loadLng()

import subprocess,os
from typing import List, Union, Dict
from datetime import datetime
from dateutil.parser import parse as parser_parse
from .format import strTime,strTimeUSec,bytesVal,bytesTx
from .term import en_color,text_color
from .jbjh import JBJH

class c_unitsRetRow:
    """ slouží pro zobrazení výsledků z show"""
    unit: str = ""
    load: str = ""
    active: str = ""
    sub: str = ""
    description: str = ""
    
    def __init__(self,row:str=None):
        # legacy like init
        self.unit = self.unit
        self.load = self.load
        self.active = self.active
        self.sub = self.sub
        self.description = self.description
        
        if not row:
            return
        r=row.split(None,5)
        if len(r)==5:
            self.unit, self.load, self.active, self.sub, self.description = r
    
class c_unitsFilesRetRow:
    """ slouží pro zobrazení výsledků z show"""
    unit_file: str = ""
    enabled_str: str = ""
    enabled:bool = False
    vendor_preset_str: str = ""
    vendor_preset: bool = False
    
    def __init__(self,row:str=None)->None:
        # legacy like init
        self.unit_file = self.unit_file
        self.enabled_str = self.enabled_str
        self.enabled = self.enabled
        self.vendor_preset_str = self.vendor_preset_str
        self.vendor_preset = self.vendor_preset
        
        if not row:
            return        
        r=row.split(None,3)
        if len(r)==3:
            self.unit_file, self.enabled_str, self.vendor_preset_str = r
            self.vendor_preset = self.vendor_preset_str == "enabled"
            self.enabled = self.enabled_str == "enabled"        



class io_bytes(bytesVal):
    def __init__(self, value: Union[str,int]):
        if isinstance(value, str):
            if value.isdigit():
                value = int(value)        
        if value == 18446744073709551615:
            value = 0
            
        super().__init__(value)

class c_unit_status:
    """ slouží pro zobrazení výsledků z show - není zaměřeno na službu
    jen pomocná pro c_unit, jinak je přepsáno přímo v c_service_status nebo c_timer_status
    """
    
    Names:str = "unknown"
    
    LoadState: str = "unknown"
    ActiveState: str = "unknown"
    SubState: str = "unknown"
        
    CanStart:bool = False
    CanStop:bool = False
    CanReload:bool = False
    CanIsolate:bool=False
    CanFreeze:bool = False
        
    UnitFileState:bool = False
    """Označuje skutečný stav jednotky, tedy zda je aktuálně enabled, disabled, static, nebo masked."""
    
    UnitFilePreset:bool = False
    """Určuje výchozí doporučené nastavení pro povolení nebo zakázání jednotky, jak je definováno ve preset souboru."""
    
    Uptime:strTime=strTime(0)
    
    def __init__(self) -> None:
        self.Names = self.Names
        self.LoadState = self.LoadState
        self.ActiveState = self.ActiveState
        self.SubState = self.SubState
        self.CanStart = self.CanStart
        self.CanStop = self.CanStop
        self.CanReload = self.CanReload
        self.CanIsolate = self.CanIsolate
        self.CanFreeze = self.CanFreeze
        self.UnitFileState = self.UnitFileState
        self.UnitFilePreset = self.UnitFilePreset
        self.Uptime = self.Uptime

   
class c_service_status(c_unit_status):
    """Status systemd služby (service unit).
    autoload, anotace nutné
    """

    Id: str = ""
    MainPID: int = 0
    ExecMainPID : int = 0
    RestartUSec: strTime = 0
    TimeoutStartUSec: strTime = 0
    TimeoutStopUSec: strTime = 0
    TimeoutAbortUSec: strTime = 0
    UID: int = 0
    User: str = ""
    GID: int = 0
    Group: str = ""
    
    ActiveEnterTimestamp:Union[datetime,None]=None
    Uptime:strTime=0
    
    ExecStart: str = ""
    ExecStartEx: str = ""
    
    MemoryCurrent: bytesVal = 0
    MemoryAvailable: bytesVal = 0 # 0=infinity
    CPUUsageNSec: strTimeUSec = 0
    """ Využití CPU v mikrosekundách od spuštění služby, v infu je číslo v nanosekundách, ale toto je převedeno na mikrosekundy
    pro potřeby tohoto objektu
    """
    
    TasksCurrent: int = 0
    
    IOReadBytes: io_bytes = 0
    IOReadOperations: io_bytes = 0
    IOWriteBytes: io_bytes = 0
    IOWriteOperations: io_bytes = 0
    
    WorkingDirectory: str = ""
    RootDirectory: str = ""
    
    Nice: int = 0
    """ priority, 0=normální, -20=nejvyšší, 19=nejnižší"""
    
    FragmentPath: str = ""
    
    StartLimitIntervalUSec: int = 0
    """ v sec """

    def __init__(self):
        super().__init__()

        self.Id: str = ""

        self.MainPID: int = 0
        self.ExecMainPID: int = 0

        self.RestartUSec: strTime = 0
        self.TimeoutStartUSec: strTime = 0
        self.TimeoutStopUSec: strTime =  0
        self.TimeoutAbortUSec: strTime = 0

        self.UID: int = 0
        self.User: str = ""
        self.GID: int = 0
        self.Group: str = ""

        self.ActiveEnterTimestamp: datetime | None = None
        self.Uptime: strTime = 0

        self.ExecStart: str = ""
        self.ExecStartEx: str = ""

        self.MemoryCurrent: bytesVal = 0
        self.MemoryAvailable: bytesVal = 0  # 0 = unlimited

        self.CPUUsageNSec: strTimeUSec = 0
        """ Využití CPU v mikrosekundách od spuštění služby, v infu je číslo v nanosekundách, ale toto je převedeno na mikrosekundy
        pro potřeby tohoto objektu
        """
        
        self.TasksCurrent: int = 0

        self.IOReadBytes: io_bytes = 0
        self.IOReadOperations: io_bytes = 0
        self.IOWriteBytes: io_bytes = 0
        self.IOWriteOperations: io_bytes = 0

        self.WorkingDirectory: str = ""
        self.RootDirectory: str = ""

        self.Nice: int = 0
        """ priority, 0=normální, -20=nejvyšší, 19=nejnižší"""

        self.FragmentPath: str = ""

        self.StartLimitIntervalUSec: int = 0
        """Interval pro restart limitaci (v usec)."""
    
    
class c_timer_status(c_unit_status):    
    NextElapseUSecRealtime: datetime = 0
    LastTriggerUSec: datetime = 0
    
    AccuracyUSec: strTime = 0
    RandomizedDelayUSec: strTime = 0
    
    Triggers: str = ""
    
    def __init__(self):
        super().__init__()
        self.NextElapseUSecRealtime = self.NextElapseUSecRealtime
        self.LastTriggerUSec = self.LastTriggerUSec
        self.AccuracyUSec = self.AccuracyUSec
        self.RandomizedDelayUSec = self.RandomizedDelayUSec
        self.Triggers = self.Triggers
  

def convert_value(value: str, target_type, doNotConvertNone:bool=False):
    """ Dynamicky převede hodnotu na zadaný typ 
    
    Parameters:
        value (str): Hodnota, kterou chceme převést.
        target_type (type): Typ, na který chceme hodnotu převést.
        doNotConvertNone (bool): Pokud je True, hodnota None se nekonvertuje ale vrátí se None.
        
    Returns:
        Any: Převedená hodnota.
    """
    try:
        # Pokud je typ Union, použijeme první platný typ, který není None
        if hasattr(target_type, '__origin__') and target_type.__origin__ is Union:
            for typ in target_type.__args__:
                if typ is not type(None):
                    target_type = typ
                    break

        # Pokud je hodnota prázdná a typ je Union s None, vrátíme None
        if value == "" and target_type is Union:
            return None

        # Pokusíme se zavolat target_type jako konstruktor s hodnotou
        if target_type == bool:
            return value.lower() in ['true', '1', 'yes', 'on', 'enabled']
        if target_type == datetime and isinstance(value, str):
            return parser_parse(value)
        if doNotConvertNone and value is None:
            return None
        return target_type(value)
    except (ValueError, TypeError):
        # V případě chyby při konverzi vrátíme výchozí hodnotu podle typu
        if target_type == int:
            return 0
        elif target_type == bool:
            return False
        elif target_type == datetime:
            return None
        elif target_type == bytesVal:
            return bytesVal()
        elif target_type == str:
            return ""
        else:
            return None

class c_header:
    unitName:str # nodered@.service
    """Pokud none tak se použije text z create jako název"""
    version:str
    date:str
    """Pokud nenastavíme tak obsahuje aktuální"""
    author:str
    """Pokud nenastavíme tak se vyvolá výjimka při getStr()"""
    
    def __init__(self,unitName:str=None,version:str="1.0.0",date:str=None,author:str=None):
        self.unitName=unitName
        self.version=version
        self.date=date
        self.author=author
        
    def checkVersion(self,toVersion:str)->int:
        """ zkontroluje zda je verze větší než toVersion
        
        Parameters:
            toVersion (str): verze k porovnání
            
        Returns:
            int: toVersion je: 0=stejná, -1=menší, 1=větší, 99=chyba
        """
        #převedeme na int
        tv=toVersion.split(".")
        if len(tv)!=3:
            return 99
        v=self.version.split(".")
        if len(v)!=3:
            return 99
        for i in range(3):
            if not v[i].isdigit() or not tv[i].isdigit():
                return 99
            if v[i]<tv[i]:
                return -1
            if v[i]>tv[i]:
                return 1
        return 0
        
    def loadFromStr(self,content:str)->None:
        """ načte hlavičku ze string-u
        
        Parameters:
            content (str): obsah souboru
                    
        Returns:
            None
        """
        import re
        lines=content.split("\n")
        for line in lines:
            # použijeme regexp pro větší flexibilitu
            if re.match(r"#\s*Version\s*:",line,flags=re.IGNORECASE):
                self.version=line.split(":",1)[1].strip()
            elif re.match(r"#\s*Date\s*:",line,flags=re.IGNORECASE):
                self.date=line.split(":",1)[1].strip()
            elif re.match(r"#\s*Author\s*:",line,flags=re.IGNORECASE):
                self.author=line.split(":",1)[1].strip()
            elif re.match(r"#\s*Unit\s*:",line,flags=re.IGNORECASE):
                self.unitName=line.split(":",1)[1].strip()
        
    def toStr(self)->str:
        """ vrátí hlavičku souboru z aktuálních hodnot
        
        Returns:
            str: textový řetězec
        """
        if self.author is None:
            raise ValueError("Není nastaven autor")
        if self.date is None:
            self.date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r=""
        if self.unitName:
            r+=f"# {self.unitName}\n"
        r+=f"# Version: {self.version}\n"
        r+=f"# Date: {self.date}\n"
        r+=f"# Author: {self.author}\n"
        r+="#\n"
        return r

class c_unit:
    noneInstance: bool
    name: str
    """pokud se nejedná o šablonu obsahuje stejný text jako ve fullName  
    Pokud se jedná o šablonovací servis tak obsahuje jen název šablony a typ tzn 'serviceName@.service' bez názvu template
    """
    fullName: str
    """plný název služby včetně přípony a šablony tzn 'serviceName@tempalteName.service'  
    pokud se nejedná o šablonovací servis tak obsahuje stejný text jako je v name
    """
    ok: bool
    
    _isTimer:bool
    _postfix:str
    """přípona pro službu nebo timer tzn '.service' nebo '.timer'"""
    _templateName:str|None
    """kopie parametru z konstruktoru"""
    _serviceName:str|None
    """kopie parametru z konstruktoru"""

    def __init__(self, service_name: str, templateName:str=None, isTimer: bool = False):
        """
        Inicializuje novou instanci pro správu `systemd` služby.

        Parameters:
            service_name (str): Název služby, kterou chceme spravovat. Pokud název neobsahuje příponu `.service`, bude automaticky doplněna.
            templateName (str): Název šablony služby, se kterou chceme pracovat, pokud:
                - 'None'= tak se nejedná o šablonu
                - '' = šablona bez zaměření, tzn pracujeme jen s šablonou a ne s konkrétní službou
                - 'název' = pracujeme s konkrétní službou, která je odvozena od šablony
            isTimer (bool): Pokud je `True`, jedná se o timer, jinak o službu.            
        """
        self._isTimer = False
        self._postfix = ""
        self._templateName = None
        self._serviceName = None
        
        if not haveSystemd():
            raise ValueError(TXT_C_UNIT_noSystemd)
        
        self._serviceName=service_name
        self._templateName=templateName
        
        self.noneInstance = service_name is None
        if service_name:
            if not isinstance(service_name, str):
                raise ValueError(TXT_C_UNIT_servNameType)
            service_name = str(service_name).strip()
        else:
            service_name = ""
            return
            
        if isTimer:
            self._isTimer = True
            self._postfix = ".timer"
        else:
            self._postfix = ".service"
        
        x=service_name.split(".")
        if len(x) > 1:
            if x[1]!=self._postfix.replace(".",""):
                raise ValueError(TXT_C_UNIT_servUnitType)
        if len(x)<1 or len(x)>2:
            raise ValueError(TXT_C_UNIT_servDotErr)
        
        service_name = x[0]
        
        # pokud obsahuje @ tak chyba, šablona se určuje parametrem
        if "@" in service_name:
            raise ValueError(TXT_C_UNIT_servAtErr)
        
        if templateName:
            if '@' in templateName or '.' in templateName:
                raise ValueError(TXT_C_UNIT_servTmplNameErr)
        
            
        self.name = service_name
        self.fullName = service_name
        if isinstance(templateName, str):
            self.fullName += '@' + templateName
            self.name += '@'
        self.fullName = self.fullName + self._postfix
        self.name = self.name + self._postfix
            
        self.ok = self.existsFile() is not None

    def status(self, status:c_unit_status=None) -> Union[c_unit_status,None]:
        """ vrátí informace o službě pomoci systemctl show
        
        Parameters:
            status (c_unit_status): objekt pro uložení informací, pokud není zadaný vytvoří z default c_unit_status
                objekt musí být c_unit_status nebo jeho potomek
        """
        if not self.ok:
            return c_service_status()
            
        if status is None:
            status = c_unit_status()    
            
        set:bool =False
        actEnterTime:bool=False
        # zavoláme systemctl show
        result = subprocess.run(["systemctl", "show", "--plain", "--no-pager", self.fullName], capture_output=True, text=True)
        if result.returncode == 0:
            anotace={}
            for base in status.__class__.__mro__:
                if hasattr(base, '__annotations__'):
                    anotace.update(base.__annotations__)
            # anotace= c_service_status.__annotations__
            for line in result.stdout.splitlines():
                key, _, value = line.partition("=")
                if key == 'ActiveEnterTimestamp':
                    actEnterTime=True
                if value=='[not set]':
                    value=None
                if not key in ['Uptime']:
                    if hasattr(status, key):
                        attr_type = anotace[key]
                        try:
                            setattr(status,key, convert_value(value,attr_type))
                            set=True
                        except ValueError:
                            setattr(status, key, value)
                            set=True
            
            if not set:
                return None
            try:
                # dopočty
                if actEnterTime:
                    x= status.ActiveEnterTimestamp
                    if x:
                        x=int(datetime.now().timestamp() - status.ActiveEnterTimestamp.timestamp())
                        status.Uptime = strTime(str(x)+"s")
            except Exception as e:
                pass
        return status

    @property
    def unit(self) -> Union[c_unitsRetRow,None]:
        """
        Používá `systemctl list-units` pro získání informací o službě.
        
        Returns:
            List[c_unitsRetRow]: Seznam řádků jednotek služby.
        """
        x=c_unit.s_units(self.fullName)
        return x[0] if len(x)==1 else None        
        
    @staticmethod
    def s_units(serviceName:str) -> List[c_unitsRetRow]:
        """
        Používá `systemctl list-units` pro test existujících služeb.

        Parameters:
            serviceName (str): Název služby pro vyhledání.

        Returns:
            List[c_unitsRetRow]: Seznam řádků jednotek služby.
        """
                
        n=str(serviceName).strip()
        if n=="":
            return []
        result = subprocess.run(["systemctl", "list-units","--plain", "--all", n], capture_output=True, text=True)        
        x=[]
        header = False
        for line in result.stdout.splitlines():
            if line.strip()=="" or line.startswith("0 loaded"):
                break
            
            if line.startswith("UNIT") and not header:
                header = True
                continue
            else:
                if header:
                    x.append(c_unitsRetRow(line))
        return x
    
    @staticmethod
    def next_params_toString(params:Union[ Dict[ str,str ],  Dict[ str, List[str] ] ]) -> str:
        """ převede slovník na string pro další sekce
        
        Parameters:
            params (Union[ Dict[ str,str ],  Dict[ str, List[str] ]): slovník parametrů
            
        Returns:
            str: textový řetězec
            
        Raises:
            ValueError: pokud je něco špatně
        """            
        if not isinstance(params, dict):
            params = ""
        else:
            r=[]
            for k,v in params.items():
                if not isinstance(k, str):
                    k=str(k)
                    raise ValueError(TXT_SSMD_ERR05.format(tx=k))
                k = k.strip()
                if isinstance(v, list):
                    for x in v:
                        x = str(x).strip() 
                        r.append(f"{k}={x}")
                elif isinstance(v, str):
                    v = str(v).strip()
                    r.append(f"{k}={v}")
                else:
                    # vyvoláme výjimku
                    raise ValueError(TXT_SSMD_ERR06.format(tx=k))
                
            params = "\n".join(r)
        return params    
    
    @property
    def unit_file(self)->Union[c_unitsFilesRetRow,None]:
        """
        Používá `systemctl list-unit-files` pro test existujících služeb. Používá self.name protože se testuje soubor

        Returns:
            List[c_unitsFilesRetRow]: Seznam řádků jednotek souborů služby.
        """
        x=c_unit.s_units_files(self.name)
        return x[0] if len(x)==1 else None
    
    @staticmethod
    def s_units_files(serviceName:str) -> List[c_unitsFilesRetRow]:
        """
        Používá `systemctl list-unit-files` pro test existujících služeb.

        Parameters:
            serviceName (str): Název služby pro vyhledání.

        Returns:
            List[c_unitsFilesRetRow]: Seznam řádků jednotek souborů služby.
        """
                
        n=str(serviceName).strip()
        if n=="":
            return []
        result = subprocess.run(["systemctl", "list-unit-files","--plain", "--all", n], capture_output=True, text=True)        
        x=[]
        header = False
        for line in result.stdout.splitlines():
            if line.strip()=="" or line.startswith("0 loaded"):
                break            
            if line.startswith("UNIT FILE") and not header:
                header = True
                continue
            else:
                if header:
                    x.append(c_unitsFilesRetRow(line))            
        return x
          
    def getServiceFilePath(self) -> str:
        return f"/etc/systemd/system/{self.name}"
    
    def getServiceFileLinkPathSystem(self) -> str:
        return f"/lib/systemd/system/{self.name}"
            
    def serviceFileExists(self) -> int:
        """ zjistí zda soubor služby fyzicky existuje
        vrací 0 pokud neexistuje, 1 pokud existuje, 2 pokud existuje jen jako link
        """        
        path = self.getServiceFilePath()
        if not os.path.exists(path):
            return 0
        if os.path.islink(path):
            return 2
        return 1            

    def existsFile(self) -> Union[c_unitsFilesRetRow,None]:
        """ zjistí zda fyzicky existuje soubor služby  
        vychází ze self.name, tzn u šablon se hledá název 'servName@.service' tj bez názvu šablony
        """
        if not os.path.exists(self.getServiceFilePath()) and not os.path.exists(self.getServiceFileLinkPathSystem()):
            return None
        
        return self.unit_file
    
    def exists(self) -> bool:
        """ zjistí zda služba existuje přes systemctl show, tzn jak to vidí systemd
        vychází ze self.fullName !!
        """
        # určení k přepsání,
        # protože nelze testovat u šablonovacích služeb existenci služby, tak musí být přepsána
        # vlastními testy, např že existuje daný soubor nebo dir pro šablonu
        if not self._templateName: # pokud není šablona tak vrátíme výsledek fyzické existence
            return self.existsFile() is not None
        
        raise NotImplementedError("Metoda pro template není implementována")
    
    def enabled(self,status=None) -> bool:
        """ zjistí zda je služba zapnutá
        
        Parameters:
            status (c_unit_status): pokud je None, tak se zavolá status() jinak se předpokládá, že je to výsledek ze status()
            
        Returns:
            bool: True=je zapnutá, False=není zapnutá
        """
        if not self.ok:
            return False
        
        if status is None:
            status=self.status()
        if not isinstance(status, c_unit_status):
            raise ValueError(TXT_C_UNIT_badCStatus)
            
        return status.UnitFileState
    
    def fullStatus(self,asInt:bool=False,status=None,coloring:bool=False) -> Union[str,int]:
        """ vrátí stav služby 
        
        Parameters:
            asInt (bool): pokud je True, vrátí číslo, jinak textový popis
            coloring (bool): pokud je True, vrátí barevný textový popis
            
        Returns:
            Union[str,int]: popis stavu služby
                Pokud int:
                - 1/11 = RUNNING, 0/10 = STOPPED
                - >9 = ENABLED, <10 = DISABLED
                - 99 = NOT EXISTS
        """
        if (asInt:=JBJH.is_bool(asInt)) is None:
            asInt=False
        if (coloring:=JBJH.is_bool(coloring)) is None:
            coloring=False
                     
        r=0
        rtx=[]
        if status is None:
            status=self.status()
        if not isinstance(status, c_unit_status):
            raise ValueError(TXT_C_UNIT_badCStatus)            
            
        if not self.exists():
            return TXT_STATUS_NEX if not asInt else 99
        if self.running(status):
            t=TXT_STATUS_RUN
            if coloring:
                t=text_color(t,en_color.GREEN)
            rtx.append(t)
            r+=1
        else:
            t=TXT_STATUS_STP
            if coloring:
                t=text_color(t,en_color.RED)
            rtx.append(t)
        if self.enabled(status):
            t=TXT_STATUS_ENA
            if coloring:
                t=text_color(t,en_color.GREEN)
            rtx.append(t)
            r=10
        else:
            t=TXT_STATUS_DIS
            if coloring:
                t=text_color(t,en_color.RED)
            rtx.append(t)
        return ", ".join(rtx) if not asInt else r
    
    def running(self,status=None) -> bool:
        """ zjistí zda služba běží
        
        Parameters:
            status (c_unit_status): pokud je None, tak se zavolá status() jinak se předpokládá, že je to výsledek ze status()
        
        Returns:
            bool: True=je spuštěná, False=není spuštěná
        """
        if not self.ok:
            return False
        
        if status is None:
            status=self.status()
            
        if not isinstance(status, c_unit_status):
            raise ValueError(TXT_C_UNIT_badCStatus)
        
        if status is None:
            return False
        if not isinstance(status.ActiveState, str):
            return False
        s=status.ActiveState.strip().lower()
        return s == "active"

    def start(self) -> bool:
        """ spustí službu """
        if not self.ok:
            return False
        if self.running():
            return True        
        subprocess.run(["systemctl", "start", self.fullName])
        return self.running()

    def stop(self) -> bool:
        """ zastaví službu """
        if not self.ok:
            return False
        if not self.running():
            return True        
        result = subprocess.run(["systemctl", "stop", self.fullName])
        return self.running()

    def restart(self) -> bool:
        """ restartuje službu """
        if not self.ok:
            return False
        if self.running():        
            result = subprocess.run(["systemctl", "restart", self.fullName])
        else:
            return self.start()
        return self.running()

    def enable(self,andRun:bool=False) -> bool:
        """ zapne službu """
        if not self.ok:
            return False
        
        if not self.enabled():        
            subprocess.run(["systemctl", "enable", self.fullName])
            
        if self.enabled():
            if andRun:
                return self.start()
            return True
        return False

    def disable(self, withStop:bool=False) -> bool:
        """ vypne službu """
        if not self.ok:
            return False
        
        if not self.enabled():
            return True
        
        if withStop and self.running():
            if not self.stop():
                return False
        
        subprocess.run(["systemctl", "disable", self.fullName])
        return not self.enabled()
    
    def createFromFile(self, fromFilename:str,andRun:bool=False) -> Union[str,None]:
        """ vytvoří novou službu, kopií souboru 
        
        Parameters:
            fromFilename (str): zdrojový soubor služby
            andRun (bool): pokud je True, tak se služba spustí
            
        Returns:
            Union[str, None]: `None` při úspěšném vytvoření. V případě chyby vrací chybovou zprávu popisující problém.
        """
        fromFilename = str(fromFilename).strip()
        if not fromFilename:
            return TXT_SSMD_ERR07
        if self.exists():
            return TXT_SSMD_ERR08
        if not os.path.exists(fromFilename):
            return TXT_SSMD_ERR09
        if not fromFilename.endswith(self._postfix):
            return TXT_SSMD_ERR10+" "+self._postfix
        try:
            #kopie souboru do systemd
            subprocess.run(["cp", fromFilename , self.getServiceFilePath() ], check=True)
            
            # úklid temp
            subprocess.run(["rm", fromFilename ], check=True)            
            
            if andRun:
                self.enable(True)
                self.start()
            return None
        except subprocess.CalledProcessError as e:
            return TXT_SSMD_ERR11+": "+self.name+f"\n{TXT_ERR}: "+str(e)

    def remove(self) -> Union[str,None]:
        """ Odstraní službu 
        
        Returns:
            Union[str, None]: `None` při úspěšném odstranění. V případě chyby vrací chybovou zprávu popisující problém.
        """
        if not self.ok:
            return False
        
        if self.disable(True):
            # odstraníme soubor (předpokládáme, že je v /etc/systemd/system)
            if not self.serviceFileExists():
                return TXT_SSMD_ERR12
            try:
                subprocess.run(["rm", self.getServiceFilePath() ], check=True)
                return None
            except subprocess.CalledProcessError as e:
                return TXT_SSMD_ERR13+": "+self.name+"\nChyba: "+str(e)
        return TXT_SSMD_ERR14+": "+self.name
    
    def getHeader(self)->c_header:
        """ vrátí hlavičku souboru služby 
        
        Returns:
            c_header: hlavička souboru, None při chybě
        """
        if not self.ok:
            return None
        
        if not self.existsFile():
            return None
        
        with open(self.getServiceFilePath(), "r") as f:
            content = f.read()
        h=c_header()
        h.loadFromStr(content)
        return h
    
    def systemdRestart(self)->None:
        subprocess.run(["systemctl", "daemon-reload"], check=True)

class c_service(c_unit):
    def __init__(self, service_name: str, templateName:str=None):
        """
        Inicializuje novou instanci pro správu `systemd` služby.

        Parameters:
            service_name (str): Název služby, kterou chceme spravovat. Pokud název neobsahuje příponu `.service`, bude automaticky doplněna.
            templateName (str): Název šablony služby, se kterou chceme pracovat, pokud:
                - 'None'= tak se nejedná o šablonu
                - '' = šablona bez zaměření, tzn pracujeme jen s šablonou a ne s konkrétní službou
                - 'název' = pracujeme s konkrétní službou, která je odvozena od šablony                
        """        
        super().__init__(service_name, templateName, False)
        
    def status(self) -> Union[c_service_status,None]:
        """ vrátí informace o službě pomoci systemctl show"""
        return super().status(c_service_status())
            
    def create(
        self,
        description:str,
        execStart:str,
        startLimitInterval:str=None,
        startLimitBurst:int=0,
        workingDirectory:str=None,
        user:str=None,
        group:str=None,
        restart:str="on-failure",
        after:str='network.target',
        WantedBy:str='multi-user.target',
        next_unit_params    :Union[ Dict[ str,str ],  Dict[ str, List[str] ] ] =None,
        next_service_params :Union[ Dict[ str,str ],  Dict[ str, List[str] ] ] =None,
        next_install_params :Union[ Dict[ str,str ],  Dict[ str, List[str] ] ]=None,
        header:c_header=None,
        andRun:bool=False
    ) -> Union[str,None]:
        """
        Vytvoří a nainstaluje novou službu `systemd` s danou konfigurací.  
        Next...params může být slovník jehož hodnota může být string nebo list string-ů. Pokud je list, tak se vytvoří více řádků.

        Parameters:
            description (str): Popis služby, zobrazí se ve výpise `systemctl`.
            execStart (str): Příkaz nebo aplikace, která se má spustit jako služba (např. '/usr/bin/node-red').
            startLimitInterval (str, optional): Časový interval pro omezení počtu opakovaných spuštění (např. '1min').
            startLimitBurst (int, optional): Počet povolených spuštění během `startLimitInterval` (0 = neomezeno).
            workingDirectory (str, optional): Pracovní adresář, ze kterého bude služba spuštěna.
            user (str, optional): Uživatel, pod kterým se služba spustí.
            group (str, optional): Skupina, pod kterou se služba spustí.
            restart (str, optional): Podmínky restartování služby (`no`, `on-failure`, `always`, atd.).
            after (str, optional): Název služby nebo target-u, který musí být spuštěn před touto službou.
            next_unit_params (Union[ Dict[ str,str ],  Dict[ str, List[str] ], optional): Parametry pro další sekci `[Unit]`.
            next_service_params (Union[ Dict[ str,str ],  Dict[ str, List[str] ], optional): Parametry pro další sekci `[Service]`.
            next_install_params (Union[ Dict[ str,str ],  Dict[ str, List[str] ], optional): Parametry pro další sekci `[Install]`.
            andRun (bool, optional): Pokud je `True`, služba bude spuštěna po vytvoření.

        Returns:
            Union[str, None]: `None` při úspěšném vytvoření. V případě chyby vrací chybovou zprávu popisující problém.
        
        Example:
            >>> service = c_service("example_service")
            >>> service.create(
            ...     description="Example Service",
            ...     execStart="/usr/bin/example_app",
            ...     user="example_user",
            ...     restart="always"
            ... )
            >>> print(service.start())  # Spustí nově vytvořenou službu.
        """
        
        # převedeme na string
        next_unit_params = self.next_params_toString(next_unit_params)
        next_service_params = self.next_params_toString(next_service_params)
        next_install_params = self.next_params_toString(next_install_params)
        
        ## vytvoříme obsah souboru a zapíšeme to /tmp
        content = [f"[Unit]"]
        content.append(f"Description={description}")
        content.append(f"After={after}")
        if next_unit_params:
            content.append(next_unit_params)

        content.append("")
        content.append("[Service]")
        content.append(f"ExecStart={execStart}")
        content.append(f"Restart={restart}")        
        if startLimitInterval:
            content.append(f"StartLimitInterval={startLimitInterval}")
        if startLimitBurst:
            content.append(f"StartLimitBurst={startLimitBurst}")
        if workingDirectory:
            content.append(f"WorkingDirectory={workingDirectory}")
        if user:
            content.append(f"User={user}")
        if group:
            content.append(f"Group={group}")
        
        if next_service_params:
            content.append(next_service_params)
        
        content.append("")
        content.append("[Install]")
        content.append(f"WantedBy={WantedBy}")
        
        if next_install_params:
            content.append(next_install_params)
        
        if header:
            if not header.unitName:
                header.unitName = self.name
                            
            content = header.toStr() +"\n" + "\n".join(content)
        else:
            content = "\n".join(content)        
        
        try:
            with open("/tmp/"+self.name, "w") as f:
                f.write(content)
        except:
            return TXT_SSMD_ERR15
        
        return self.createFromFile("/tmp/"+self.name,andRun)
    
    def getTimer(self) -> Union['c_timer',None]:
        x=c_timer(self.name, False)
        if x.ok:
            return x
        return None
    
class c_timer(c_unit):
    service : c_service|None
    
    def __init__(self, service_name: str, templateName:str=None, checkService:bool=True):
        """
        Inicializuje novou instanci pro správu `systemd` služby.

        Parameters:
            service_name (str): Název služby, kterou chceme spravovat. Pokud název neobsahuje příponu `.service`, bude automaticky doplněna.
            templateName (str): Název šablony služby, se kterou chceme pracovat, pokud:
                - 'None'= tak se nejedná o šablonu
                - '' = šablona bez zaměření, tzn pracujeme jen s šablonou a ne s konkrétní službou
                - 'název' = pracujeme s konkrétní službou, která je odvozena od šablony
            checkService (bool): Pokud je `True`, zkontroluje existenci služby a při úspěchu ji načte.
        """                        
        self.service = None
        super().__init__(service_name, templateName, True)
        
        if checkService:
            status=self.status()
            if self.ok and status.Triggers:
                x=status.Triggers.split('.')
                if len(x)==2 and x[1]=="service":
                    x = c_service(x[0])
                    if x.ok:
                        self.service = x        
    
    def status(self) -> Union[c_timer_status,None]:
        """ vrátí informace o timeru """
        return super().status(c_timer_status())
            
    def create(
        self,
        description: str,
        onCalendar: str,
        accuracy: str = "1m",
        randomizedDelay: str = "0",
        unit: str = None,
        next_unit_params: Union[Dict[str, str], Dict[str, List[str]]] = None,
        next_timer_params: Union[Dict[str, str], Dict[str, List[str]]] = None,
        next_install_params: Union[Dict[str, str], Dict[str, List[str]]] = None,
        header: c_header = None
    ) -> Union[str,None]:
        """ Vytvoří nový `systemd` časovač s danou konfigurací.

        Parameters:
            description (str): Popis časovače, zobrazí se ve výpise `systemctl`.
            onCalendar (str): Definice času nebo frekvence spouštění časovače (např. "daily" nebo "*-*-* 00:00:00").
            accuracy (str, optional): Přesnost spuštění časovače (např. "1m" znamená, že časovač může být spuštěn s přesností na jednu minutu).
            randomizedDelay (str, optional): Náhodné zpoždění při spuštění časovače, které umožňuje rozložit zatížení.
            unit (str, optional): Název služby, kterou má časovač spustit. Pokud není uvedeno, použije se služba se stejným názvem jako časovač (ale s příponou `.service`).

        Returns:
            Union[str, None]: `None` při úspěšném vytvoření. V případě chyby vrací chybovou zprávu popisující problém.
        
        Example:
            >>> timer = c_timer("example_timer")
            >>> timer.create(
            ...     description="Example Timer",
            ...     onCalendar="*-*-* 00:00:00",
            ...     accuracy="1m",
            ...     unit="example_service"
            ... )
        """
        
        # převedeme na string
        next_unit_params = self.next_params_toString(next_unit_params)
        next_timer_params = self.next_params_toString(next_timer_params)
        next_install_params = self.next_params_toString(next_install_params)
        
        # Vytvoříme obsah souboru časovače
        content = f"""[Unit]
        Description={description}
        """ + next_unit_params + """

        [Timer]
        OnCalendar={onCalendar}
        AccuracySec={accuracy}
        RandomizedDelaySec={randomizedDelay}
        """
        
        if unit:
            content += f"Unit={unit}\n"
        else:
            content += f"Unit={self.name.replace('.timer', '.service')}\n" # Automaticky spojí se službou stejného jména
        
        content += next_timer_params + """
        [Install]
        WantedBy=timers.target
        """ + next_install_params
        
        if header:
            content = header.toStr() + content
        
        try:
            with open("/tmp/" + self.name, "w") as f:
                f.write(content)
        except Exception as e:
            print(f"{TXT_SSMD_ERR16}: {e}")
            return TXT_SSMD_ERR16

        return self.createFromFile("/tmp/" + self.name)
