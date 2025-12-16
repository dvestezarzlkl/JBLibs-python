from .lng.default import * 
from .helper import loadLng,haveSystemd
loadLng()

import re
from typing import Union
from .jbjh import JBJH
from datetime import datetime

class strTime:
    """ typ str time"""
    
    _val:int
    """ v uSec """
        
    def __init__(self, value: Union[str,int]):
        """ reprezentuje textový čas

        Args:
            value (Union[str,int]): textový čas ve formátu '1m 30sec' nebo číslo v mikrosekundách
        """
        self._val=0
        if isinstance(value, int):
            self._val = value
        elif isinstance(value, str) and value.isdigit():
            self._val = int(value)
        else:        
            self._val = self.decode(value)
        
    @staticmethod
    def decode(fromTx: str) -> Union[int,None]:
        """ převede str time na int uSec """

        if not fromTx:
            return None
        fromTx = str(fromTx).strip()
        if not fromTx:
            return None
        # text rozdělíme, vstup může být '100ms', '1m 30sec'
        s = str(fromTx).split()
        o = 0

        # Pokud seznam není prázdný, pokračujeme
        if len(s) == 0:
            raise ValueError(TXT_SSMD_ERR01)

        # Slovník pro konverzi jednotek na mikrosekundy
        unit_factors = {
            'us': 1,                # mikrosekundy
            'ms': 1000,             # milisekundy
            's': 1000000,           # sekundy
            'sec': 1000000,         # sekundy (alternativní název)
            'm': 60000000,          # minuty
            'min': 60000000,        # minuty (alternativní název)
            'h': 3600000000,        # hodiny
            'd': 86400000000,       # dny
            'day': 86400000000      # dny
        }
        
        # Iterace přes rozdělené části vstupního textu
        for part in s:
            # Extrakce čísla a jednotky
            value = ''.join(filter(str.isdigit, part))  # extrahuje číslice
            unit = ''.join(filter(str.isalpha, part))   # extrahuje písmena

            # Ověření, že se našlo číslo a jednotka
            if not value or not unit:
                raise ValueError(TXT_SSMD_ERR02.format(tx=part))

            # Převedení na celé číslo
            value = int(value)

            # Ověření, že jednotka existuje ve slovníku
            if unit not in unit_factors:
                raise ValueError(TXT_SSMD_ERR03.format(tx=unit))

            # Přičtení převedené hodnoty do celkového času v mikrosekundách
            o += value * unit_factors[unit]

        return o
    
    def getUSec(self) -> int:
        return self._val

    def getMSec(self) -> float:
        return self._val / 1000
    
    def getSec(self) -> float:
        return self._val / 1000000
    
    def setUSec(self, value: int) -> None:
        self._val = value
        
    def setMSec(self, value: float) -> None:
        self._val = int(value * 1000)
    
    def setSec(self, value: float) -> None:
        self._val = int(value * 1000000)
    
    def __str__(self):
        return self.encode(self._val)
    
    @staticmethod
    def encode(uSec: int) -> str:
        """ Převede int uSec na str time ve formátu '1m 30sec' """

        if uSec < 0:
            raise ValueError(TXT_SSMD_ERR04)

        # Definujeme faktory pro převod mikrosekund na jiné jednotky
        units = [
            ('d', 86400000000),      # 1 den = 86 400 000 000 mikrosekund
            ('h', 3600000000),       # 1 hodina = 3 600 000 000 mikrosekund
            ('m', 60000000),         # 1 minuta = 60 000 000 mikrosekund
            ('sec', 1000000),        # 1 sekunda = 1 000 000 mikrosekund
            ('ms', 1000),            # 1 milisekunda = 1 000 mikrosekund
            ('us', 1)                # 1 mikrosekunda = 1 mikrosekunda
        ]

        # Výstupní seznam pro části času
        result = []

        # Pro každou jednotku spočítáme počet příslušných jednotek a zbytků
        for unit_name, factor in units:
            if uSec >= factor:
                count = uSec // factor
                uSec -= count * factor
                result.append(f"{count}{unit_name}")

        # Spojení jednotlivých částí výsledného řetězce a návrat
        return ' '.join(result) if result else '0us'
    
    def __repr__(self):
        return self.__str__()
    
class strTimeUSec(strTime):
    """ jako str time ale pokud inicializujeme s int tak to bere jako uSec
    """
    def __init__(self, value: Union[str,int]):        
        if isinstance(value, int):
            value = value / 1000            
        elif isinstance(value, str) and value.isdigit():
            value = int(value) / 1000
        super().__init__(value)
            
class bytesTx:
    """ reprezentuje velikost v bytech v textové podobě, obsahuje i převod z textu na int a naopak
    např. 1K, 1M, 1G, 1T, 1P
    akceptuje i float hodnoty např. 1.5K, 1.5M, 1.5G, 1.5T, 1.5P
        - ve float akceptuje i ',' jako oddělovač desetinných míst
        
    inicializace se provádí pomocí int nebo str (číslo může být s jednotkou B, K, M, G, T)
    
    Pro reprezentaci jako int se používá class bytesVal, která pracuje jako int: x=int(bytesVal("1K")) => x=1024
    tzn podporuje str() a int()
    
    Tato class je určena pro převod a formátování velikostí v textové formě tzn podporuje jen str()
    
    Examples:
        >>> b = bytesTx(1024)
        >>> print(b) # vytiskne '1kB'
        >>> b2 = bytesTx("1K")
    """
    val: int
    precision: int
    
    def __init__(self, value: Union[str,int], precision: int = 2):
        self.precision = precision
        self.val = 0
        if isinstance(value, int):
            self.val = value
        else:        
            self.val = self.decode(value)        
        
    @staticmethod
    def decode(fromTx: str) -> int:
        """Převede str na int."""
        if not fromTx:
            return 0

        fromTx = fromTx.strip()
        if fromTx.isdigit():
            # Pokud je to číslo, vrátíme ho
            return int(fromTx)
        
        # Převede na malá písmena pro zaručení správného převodu
        fromTx = fromTx.lower()
        
        # odstraníme 'B' na konci pokud není samotnou jednotkou
        if fromTx[-1] == 'b' and len(fromTx) > 1 and fromTx[-2] in 'kmgtpe':
            fromTx = fromTx[:-1]

        # Slovník pro jednotky a jejich hodnoty v bytech
        units = {'k': 1024, 'm': 1024**2, 'g': 1024**3, 't': 1024**4, 'p': 1024**5, 'e': 1024**6}
        
        # Pokud je jednotka v textu, převedeme
        unit = fromTx[-1]
        fromTx = fromTx[:-1]
        # replace ',' with '.'
        fromTx = fromTx.replace(',', '.')
        if unit in units:
            try:
                return int(float(fromTx) * units[unit])
            except ValueError:
                return 0  # Pokud není platná číslice před jednotkou

        return 0
    
    @property
    def bytes(self) -> int:
        """Vrátí velikost v bytech jako int

        Returns:
            int: Velikost v bytech
        """
        return self.val
    
    @staticmethod
    def _v_t_str(v: int, p: int, t:int):
        v=round(v / t, p)
        return v if v % 1 else int(v)        

    @staticmethod
    def encode(value: int, precision: int = 2) -> str:
        """Převede int na str."""
        units = ['B', 'k', 'M', 'G', 'T', 'P', 'E']
        for i in range(len(units)):
            unit_value = 1024 ** i
            if value < unit_value * 1024:
                return f"{bytesTx._v_t_str(value,precision,unit_value)}{units[i]}" + ( "" if i == 0 else "B")
        return f"{bytesTx._v_t_str(value, precision, (1024 ** len(units) ) ) }EB"  # V případě větší jednotky než PB
    
    def get(self) -> int:
        return self.val
    
    def set(self, value: int) -> None:
        self.val = value
        
    def __str__(self):
        return self.encode(self.val, self.precision)
        
    def __repr__(self):
        return self.__str__()
        
class bytesVal:
    """ reprezentuje velikost v bytech jako int ale s formátováním, tzl můžeme pracovat s převodem int(...)
    inicializace se provádí pomocí int nebo str (číslo může být s jednotkou B, K, M, G, T)
    
    Pokud použijeme:
        - x=int(bytesVal("1K")) tak x bude 1024
        - x=str(bytesVal(1024)) tak x bude '1kB'
    
    Examples:
        >>> b = bytes(1024)
        >>> print(b)
        >>> b2 = bytes("1K")
    """
    __val: int
    
    def __init__(self, value: Union[str,int]):
        self.__val = 0
        
        if isinstance(value, int):
            self.__val = value
        else:
            self.__val = bytesTx.decode(value)        
        
    # default get pro class
    def __int__(self):
        return self.__val
    
    def __str__(self):
        return bytesTx.encode(self.__val)
    
    def set(self, value: int):
        self.__val=value
        
    def __repr__(self):
        return self.__str__()

class cliSize:
    """Velikost pro CLI příkazy (např. '512M', '1G', atd.)"""
    
    __size_bytes:int
    __inMb:bool = False
    
    def __init__(self, sizeStr:str, ifIntIsMiB:bool=False) -> None:
        """Inicializace velikosti z CLI formátu (např. '512M', '1G') nebo z int (v bytech nebo MiB).
        Args:
            sizeStr (str|int): Velikost jako string (např. '512M', '1G', atd.) nebo int (v bytech nebo MiB).
            ifIntIsMiB (bool): Pokud je sizeStr int, určuje zda je to v MiB (True) nebo v bytech (False).
        """
        self.__inMb = bool(ifIntIsMiB)
        if isinstance(sizeStr, int):
            if ifIntIsMiB:
                self.__size_bytes = sizeStr * 1024 * 1024
            else:
                self.__size_bytes = sizeStr
        elif isinstance(sizeStr, str):
            self.__size_bytes = self.strToInt(sizeStr)
        
    @staticmethod
    def strToInt(sizeStr:str)-> int:
        """Převod velikosti z CLI formátu (např. '512M', '1G') na velikost v MiB.
        Args:
            sizeStr (str): Velikost jako string (např. '512M', '1G', atd.).
        Returns:
            int: Velikost v bytech
        Raises:
            ValueError: Pokud je neplatný formát velikosti.
        """
        if not isinstance(sizeStr, str):
            raise ValueError("sizeStr musí být string.")
        sizeStr = sizeStr.strip().upper()
        match = re.match(r"^(\d+)([MKGTPB]?)$", sizeStr)
        if not match:
            raise ValueError("Neplatný formát velikosti. Použijte číslo následované volitelně jednotkou (M, G, K, T, P).")
        sizeValue = int(match.group(1))
        sizeUnit = match.group(2) or "B"
        sizeInB = sizeValue
        if sizeUnit == "B":
            sizeInB = sizeValue
        elif sizeUnit == "K":
            sizeInB = sizeValue * 1024
        elif sizeUnit == "M":
            sizeInB = sizeValue * 1024 * 1024
        elif sizeUnit == "G":
            sizeInB = sizeValue * 1024 * 1024 * 1024
        elif sizeUnit == "T":
            sizeInB = sizeValue * 1024 * 1024 * 1024 * 1024
        elif sizeUnit == "P":
            sizeInB = sizeValue * 1024 * 1024 * 1024 * 1024 * 1024
        else:
            raise ValueError("Neplatná jednotka velikosti. Použijte M, G, K, T, P.")
        return sizeInB
    
    @property
    def isInMiB(self)-> bool:
        """Vrátí True pokud je velikost v MiB, jinak False (v bytech)."""
        return self.__inMb
    
    @property
    def value(self)-> int:
        """Vrátí velikost jako int (v MiB nebo bytech podle nastavení)."""
        if self.__inMb:
            return self.__size_bytes // (1024 * 1024)
        else:
            return self.__size_bytes
    
    @property
    def inBytes(self)-> int:
        """Vrátí velikost v bytech."""
        return self.__size_bytes
    
    @property
    def inMiB(self)-> int:
        """Vrátí velikost v MiB."""
        return self.__size_bytes // (1024 * 1024)
    
    @property
    def inGiB(self)-> int:
        """Vrátí velikost v GiB."""
        return self.__size_bytes // (1024 * 1024 * 1024)
    
    @property
    def inMiBFloat(self)-> float:
        """Vrátí velikost v MiB jako float."""
        return self.__size_bytes / (1024 * 1024)
    
    @property
    def inGiBFloat(self)-> float:
        """Vrátí velikost v GiB jako float."""
        return self.__size_bytes / (1024 * 1024 * 1024)
    
    @staticmethod
    def intToStr(val:int)-> str:
        """Převod velikosti na CLI formát (např. '512M', '1G').
        Args:
            val (int): Velikost v bytech
        Returns:
            str: Velikost jako string (např. '512M', '1G', atd.).
        """
        cnt=0
        while val >= 1024 and cnt < 5:
            val = val // 1024
            cnt += 1
        units = ['B', 'K', 'M', 'G', 'T', 'P']
        return f"{val}{units[cnt]}"
        
    
    def __str__(self)-> str:
        """Vrátí velikost jako string (např. '512M', '1G', atd.)."""
        return cliSize.intToStr(self.inBytes)
        
    def __int__(self)-> int:
        """Vrátí velikost jako int (v MiB nebo bytech podle nastavení)."""
        if self.__inMb:
            return self.__size_bytes // (1024 * 1024)
        else:
            return self.__size_bytes
        
    def __repr__(self)-> str:
        """Vrátí reprezentaci objektu."""
        return f"cliSize(size={self.__size_bytes} bytes, inMiB={self.__inMb})"

class dateTimeFormat:
    """Formátování datetime pro různé použití (CLI, logy, atd.)"""
    
    FORMATS = {
        'MYSQL': ["%Y-%m-%d"," ","%H:%M:%S"],
        'FILENAME': ["%Y-%m-%d","_","%H%M%S"],
        'CZ': ["%d.%m.%Y"," ","%H:%M:%S"],
    }
    
    OUT = ['d','dt','t']
            
    @staticmethod
    def mysql(dt,out:str) -> str:
        """Formátování datetime pro logy."""
        if (dt:=JBJH.is_dateTime(dt,True) ) is not None:            
            if out == 'd':
                return dt.strftime(dateTimeFormat.FORMATS['MYSQL'][0])
            elif out == 't':
                return dt.strftime(dateTimeFormat.FORMATS['MYSQL'][2])
            elif out == 'dt':
                return dt.strftime(''.join(dateTimeFormat.FORMATS['MYSQL']))
            else:
                raise ValueError("Neplatný formát výstupu. Použijte 'd', 't' nebo 'dt'.")
    
    @staticmethod
    def filename(dt,out:str) -> str:
        """Formátování datetime pro názvy souborů."""
        if (dt:=JBJH.is_dateTime(dt,True) ) is not None:
            if out == 'd':
                return dt.strftime(dateTimeFormat.FORMATS['FILENAME'][0])
            elif out == 't':
                return dt.strftime(dateTimeFormat.FORMATS['FILENAME'][2])
            elif out == 'dt':
                return dt.strftime(''.join(dateTimeFormat.FORMATS['FILENAME']))
            else:
                raise ValueError("Neplatný formát výstupu. Použijte 'd', 't' nebo 'dt'.")

    @staticmethod
    def CZ(dt,out:str) -> str:
        """Formátování datetime pro české logy."""
        if (dt:=JBJH.is_dateTime(dt,True) ) is not None:
            if out == 'd':
                return dt.strftime(dateTimeFormat.FORMATS['CZ'][0])
            elif out == 't':
                return dt.strftime(dateTimeFormat.FORMATS['CZ'][2])
            elif out == 'dt':
                return dt.strftime(''.join(dateTimeFormat.FORMATS['CZ']))
            else:
                raise ValueError("Neplatný formát výstupu. Použijte 'd', 't' nebo 'dt'.")

class currencyTx:
    """Formátování měny pro různé použití (CLI, logy, atd.)
    Default je CZK s oddělovačem tisíců mezerou a desetinnou čárkou.
    """
    
    __val:float
    __mena:str
    __thousands_sep:str
    __decimal_sep:str
    __precision:int
    __menaPosAtEnd:bool
    
    def __init__(
        self,
        value: str | int | float,
        decimal_sep:str=",",
        mena:str="CZK",
        thousands_sep:str=" ",
        precision:int=2,
        menaPosAtEnd:bool=True
    ):
        """Inicializace formátování měny.
        Pokud je value str, tak se parsuje a vše se pokusí detekovat,  
        POZOR !!! jediné co se nedekuje **je desetinný oddělovač** tzn pokud vkládám při init str tak musíme
        vždy zajisti správné nastavení desetinného oddělovače, pokud není default ',', ostatní se detekuje
        ze stringu automaticky.
                
        Args:
            value (str | int | float): Hodnota měny jako string, int nebo float.
            decimal_sep (str, optional): Desetinný oddělovač. Default je ",".
            mena (str, optional): Měna. Default je "CZK".
            thousands_sep (str, optional): Oddělovač tisíců. Default je " ".
            precision (int, optional): Počet desetinných míst. Default je 2.
            menaPosAtEnd (bool, optional): Umístění měny na konec (True) nebo na začátek (False). Default je True.
        Raises:
            ValueError: Pokud jsou neplatné parametry.
        """
        
        self.__mena = str(mena)        
        self.__thousands_sep = str(thousands_sep)
        self.__decimal_sep = str(decimal_sep)
        self.__precision = int(precision)
        self.__menaPosAtEnd = bool(menaPosAtEnd)
        self.parse(value)
        
        if re.match(r"([0-9]|[-+.,])+", self.__mena):
            raise ValueError("Měna nesmí obsahovat číslice ani znaky - + . ,")
        
        if self.__thousands_sep == self.__decimal_sep:
            raise ValueError("Oddělovač tisíců a desetinný oddělovač nesmí být stejné znaky.")
        
        self.__thousands_sep = JBJH.is_str(self.__thousands_sep, True)
        if [", ","."," "].count(self.__thousands_sep) == 0 or len(self.__thousands_sep) > 1:
            raise ValueError("Oddělovač tisíců musí být jeden z těchto znaků: ' ', ',', '.' anebo prázdný znak pro žádný oddělovač.")
        
        self.__decimal_sep = JBJH.is_str(self.__decimal_sep, True)
        if [',', '.'].count(self.__decimal_sep) == 0 or len(self.__decimal_sep) != 1:
            raise ValueError("Desetinný oddělovač musí být jeden z těchto znaků: ',', '.'")
        
        # test měny může být CZK nebo Kč ale nesmí obsahovat znaky oddělování, jen písmena vč diakritických znaků
        if re.search(r"[ \d\-\+\,\.]", self.__mena):
            raise ValueError("Měna nesmí obsahovat číslice, mezery ani znaky - + , .")
        
        # může mít max 5 znaků
        if len(self.__mena) > 5:
            raise ValueError("Měna nesmí mít více než 5 znaků.")
    
    def parse(self, fromTx: str | int | float, decimal_sep:str|None=None) -> None:
        """Parses a formatted currency string and updates internal value."""
        if not decimal_sep:
            decimal_sep = self.__decimal_sep
        if not isinstance(decimal_sep, str) or len(decimal_sep) != 1 or decimal_sep not in ",.":
            raise ValueError("Desetinný oddělovač musí být jeden z těchto znaků: ',', '.'")

        # číslo → hotovo
        if isinstance(fromTx, (int, float)):
            self.__val = float(fromTx)
            return
        if not isinstance(fromTx, str):
            raise ValueError("fromTx musí být string, int nebo float.")

        s = fromTx.strip()
        if not s:
            self.__val = 0.0
            return

        # ----------------------------
        # 1) Detekce prefix měny
        # ----------------------------
        m = re.match(r"^([^\d\-]+)", s)
        mena = None
        if m:
            mena = m.group(1).strip()
            s = s[len(m.group(0)):].strip()

        # ----------------------------
        # 2) Detekce postfix měny
        # ----------------------------
        m = re.search(r"([^\d\-]+)$", s)
        if m:
            if mena is not None:
                raise ValueError("Měna nemůže být na začátku i na konci současně.")            
            mena = m.group(1).strip()
            s = s[:-len(m.group(0))].strip()
            self.__menaPosAtEnd = True
        else:
            self.__menaPosAtEnd = False
            
        des_c = None
        tis_c = None
        int_part = ""
        dec_part = ""        

        # detekce ',-' na konci
        if re.search(f"{re.escape(decimal_sep)}[-–]$", s):
            s = s[:-2].strip()
            des_c = decimal_sep
            

        # validace měny
        if mena:
            if re.search(r"[ \d\-\+\,\.]", mena):
                raise ValueError("Měna nesmí obsahovat číslice nebo oddělovače.")
            if len(mena) > 5:
                raise ValueError("Měna je příliš dlouhá.")
            self.__mena = mena

        # ----------------------------
        # 3) Detekce znaménka
        # ----------------------------
        minus = False
        if s.startswith("-"):
            minus = True
            s = s[1:].strip()

        # ----------------------------
        # 4) Číselná část
        # ----------------------------

        i = len(s) - 1

        while i >= 0:
            c = s[i]
            if c.isdigit():
                if des_c is None:
                    dec_part = c + dec_part
                else:
                    int_part = c + int_part
            else:
                # první oddělovač od konce = desetinný
                if des_c is None:
                    if c == decimal_sep:
                        des_c = c
                    else:
                        des_c = decimal_sep
                        if dec_part:
                            # pokud už máme něco v dec_part tak to přesuneme do int_part
                            int_part = dec_part + int_part
                            dec_part = ""
                        if tis_c is None:
                            tis_c = c
                else:
                    if des_c is not None and c == des_c:
                        raise ValueError("Více než jeden desetinný oddělovač.")                    
                    # další musí být tisícový a stejný
                    if tis_c is None:
                        tis_c = c
                    elif tis_c != c:
                        raise ValueError("Nesouhlasí tisícové oddělovače.")
                    if tis_c == des_c:
                        # pokud jsou stejné tak se předpokládá že nejsou desetiny
                        int_part = dec_part + int_part
                        dec_part = ""
                        des_c = ""
            i -= 1

        if not int_part and not dec_part:
            raise ValueError("Nenalezeny žádné číslice.")

        # pokud nebyla desetinná část
        if int_part == "":
            int_part = dec_part
            dec_part = ""
            des_c = None

        # ----------------------------
        # 5) Ověření oddělovačů
        # ----------------------------
        if des_c:
            if des_c not in ",.":
                raise ValueError("Neplatný znak pro desetinný oddělovač.")
            self.__decimal_sep = des_c

        if tis_c:
            if tis_c not in " .,":
                raise ValueError("Neplatný znak pro tisícový oddělovač.")
            if tis_c == des_c:
                raise ValueError("Tisícový a desetinný oddělovač nesmí být stejný.")
            self.__thousands_sep = tis_c

        # ----------------------------
        # 6) Výpočet
        # ----------------------------
        v = float(f"{int_part}.{dec_part}") if dec_part else float(int_part)
        if minus:
            v = -v

        self.__val = v
    
    def __str__(self):
        """Vrátí formátovanou měnu jako string."""
        # formátování čísla
        celek=int(abs(self.__val))
        desetinna=round( abs(self.__val) - celek, self.__precision)
        desetinnaStr=str(desetinna).replace("0.","")
        
        # přidáme tisícové oddělovače
        celekStr=""
        celekTx=str(celek)
        ln=len(celekTx)
        cnt=0
        while ln > 0:
            ln-=1
            celekStr=celekTx[ln]+celekStr
            cnt+=1
            if cnt == 3 and ln > 0:
                celekStr=self.__thousands_sep+celekStr
                cnt=0
                
        if self.__precision > 0:
            while len(desetinnaStr) < self.__precision:
                desetinnaStr+="0"
            finalNumber=f"{celekStr}{self.__decimal_sep}{desetinnaStr}"
        else:
            finalNumber=celekStr
            
        if self.__val < 0:
            finalNumber = "-"+finalNumber
            
        if self.__menaPosAtEnd:
            return f"{finalNumber} {self.__mena}"
        else:
            return f"{self.__mena} {finalNumber}"
    
    def __int__(self):
        """Vrátí hodnotu jako int."""
        return int(self.__val)
    
    def __float__(self):
        """Vrátí hodnotu jako float."""
        return float(self.__val)
    