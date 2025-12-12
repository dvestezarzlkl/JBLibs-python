from .lng.default import * 
from .helper import loadLng,haveSystemd
loadLng()

import re
from typing import Union

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
