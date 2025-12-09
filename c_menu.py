# cspell:ignore updatovat,otrimovaná,otrimujeme,CHCS

from .helper import loadLng
from .lng.default import * 
import json,sys
loadLng()

from typing import Callable, Any, Union, List, Tuple
import traceback
from .term import getKey,text_inverse,text_remove_terminal_ASCII_ESC,cls
from .helper import constrain
from time import sleep

from .helper import getLogger
log = getLogger(__name__)

_lineCharList = "*-._+=~"
_bracket_pairs = {"(": ")", "[": "]", "{": "}", "<": ">","/":"/","\\":"\\","|":"|"}

"""
Základní menu pro konzolové aplikace, založené na psané volbě klávesou od jednoho znaku
"""

class onSelReturn:
    err: str = ""
    """ Pokud nastavíme tak chybová hláška, která se zobrazí po skončení funkce onSelect """

    ok: str = ""
    """ Pokud nastavíme, zobrazí se pod menu jako informativní hláška """

    data: Any = None
    """ Data, která se předají do funkce onAfterSelect """

    endMenu: bool = False
    """ Pokud je True, tak se menu ukončí """
    
    def __init__(self, err: str = "", ok: str = "", data: Any = None, endMenu: bool = False):
        self.err = err
        self.ok = ok
        self.data = data
        self.endMenu = endMenu
        
    def __repr__(self):
        r= "onSelReturn(err="+('ERR' if self.err else '')
        r+= ", ok="+('OK' if self.ok else '')
        r+= ", data="+str(self.data)
        r+= ", endMenu="+str(self.endMenu)
        r+= ")"
        return r

class c_menu_item:
    """ Třída reprezentující jednu položku menu """

    choice: str = ""
    """ Klávesová zkratka pro tuto položku menu, například "s" """

    data: Any = None
    """ Data, která se předají do funkce onSelect """

    onSelect: Callable[["c_menu_item"],onSelReturn] = None
    """ Funkce, která se zavolá po stisknutí klávesy pro tuto položku menu,
    návratová hodnota z funkce je předána do funkce onAfterSelect
    
    Parameters:
        item (c_menu_item): vybraný item z menu
        
    Returns:
        onSelReturn: výstupní hodnota
    """

    onAfterSelect: Callable[[onSelReturn,"c_menu_item"], None] = None
    """ Funkce, která se zavolá po skončení funkce onSelect,
    návratová hodnota z funkce onSelect je předána do této funkce
    
    Parameters:
        ret (onSelReturn): návratová hodnota z funkce onSelect
        item (c_menu_item): vybraný item z menu
        
    Returns:
        None
    """

    enabled:bool=True
    """ Pokud je False, tak položka nereaguje """
    
    hidden:bool=False
    """ Pokud je True, tak položka není zobrazena """

    atRight:str=""
    """ Pokud je nastaveno, tak se zobrazí na pravé straně menu"""
    
    justifyLabel:str="l"
    """ Default je 'l' i v případě chybné hodnoty, jinak:
    - l = left
    - r = right
    - c = center
    """
    
    isTitleInverse:bool=False
    """Pokud je True, tak nastavíme isTitle=True se label zobrazený jako titulek zobrazí inverzně"""
    
    clearScreenOnSelect:bool=True
    """Pokud je True, tak se po vybrání a spuštění Callable smaže obrazovka"""
    
    _isTitle:bool=False
    _label:str=""
    _minW:int=0
    
    @property
    def minW(self):
        """Minimální šířka položky, bude doplněno mezerami na tuto šířku"""
        return self._minW
    
    @minW.setter    
    def minW(self, value):        
        if not value:
            value=0
        if not isinstance(value,int):
            value=int(value)
            
        if value<0:
            value=0
        if value>100:
            value=100
        self._minW = value
    
    @property
    def isTitle(self):
        """Vrací True pokud je položka titulek
        Nastavením property na true se položka změní na titulek tzn. bude inverzní s mezerami okolo
        a vynuluje se choice

        Returns:
            _type_: _description_
        """
        return self._isTitle
    
    @isTitle.setter
    def isTitle(self, value):
        if self._isTitle == value:
            return
        if not isinstance(value,bool):
            value=bool(value)
        self._isTitle = value
        if value:
            self.choice=""

    @property
    def label(self):
        """ Zobrazený název položky menu - jednořádkový, například "Start service  
        - pokud necháme prázdné tak z memu bude oddělovací prázdný řádek
        - pokud nastavíme na '-','=','+','_' 
        tak bude oddělovací čára z tohoto znaku v délce title obálky
        """        
        v= self._label
        if not v:
            return ""
        if self._isTitle:
            v = f".: {v} :."

        w=len(v)
        w=max(w+2,self._minW)
        
        w-=len(v)
        if w<0:
            w=0
        if w:
            l=w//2
            r=w-l
        else:
            l=0
            r=0
        
        ch= " " if not self._isTitle else "."
        
        j=str(self.justifyLabel).lower()
        if j=="r":
            v = f"{ch*r}{v}"
        elif j=="c":
            v = f"{ch*l}{v}{ch*r}"
        else:
            v = f"{v}{ch*r}"
        if self._isTitle and self.isTitleInverse:
            v = text_inverse(v)
        return v
    
    @label.setter
    def label(self, value):
        """Nastaví label a upraví podle isTitle"""
        if not isinstance(value,str):
            value=str(value)
        # remove cr lf tab vpodstatě
        value = ''.join([i for i in value if not i in ["\n\r\t"] ])
        self._label = value

    def __init__(
        self,
        label: str = "",
        choice: str = "",
        onSelect: Callable[[], None] = None,
        onAfterSelect: Callable[[], None] = None,
        data: Any = None,
        enabled:bool=True,
        hidden:bool=False,
        atRight:str="",
        isTitle:bool=False,
        labelJustify:str="l",
        minW:int=0,
        clearScreenOnSelect:bool=True        
    ):
        self.label = label
        self.choice = choice
        self.onSelect = onSelect
        self.onAfterSelect = onAfterSelect
        self.data = data
        self.enabled=enabled
        self.hidden=hidden
        self.atRight=atRight
        self.isTitle=isTitle
        self.justifyLabel=labelJustify
        self.minW=minW
        self.clearScreenOnSelect=clearScreenOnSelect
        
    def __repr__(self):
        r= f"c_menu_item( '{self.label}'"
        r+= f", '{self.choice}'"
        r+= "" if not self.atRight else ", atRight='"+self.atRight+"'"
        r+= "" if not self.enabled else ", enabled"
        r+= "" if not self.hidden else ", hidden"
        r+= ")"
        return r

    def _get_callable_name(self, func):
        """Returns the name of the callable (function) if it exists, else None"""
        if func is None:
            return "None"
        return func.__name__ if hasattr(func, "__name__") else str(func)
    
    def __eq__(self, value):
        if isinstance(value, c_menu_item):
            x= self._getExStr()
            y= value._getExStr()
            return x == y
        return False
    
    def _getExStr(self):
        """Returns the string representation of the object"""
        return (
            f"{self.label} {self.choice} "
            f" {self._get_callable_name(self.onSelect)}"
            f" {self._get_callable_name(self.onAfterSelect)}"
            f" {self.enabled} {self.hidden} {self.atRight}"                        
        )
    
    def _xToString(self,data):
        """Returns JSON string representation of data for consistent comparison"""
        if data is None:
            return "None"
        if not data:
            return ""
        try:
            return json.dumps(self.data, sort_keys=True)
        except (TypeError, ValueError):
            return str(self.data)    

class c_menu_title_label(c_menu_item):
    """
    Nadpis pro menu sekci, pokud je použito tak je před a za vložena mezera
    """
    def __init__(self, label:str):
        super().__init__(
            label,
            isTitle=True,
            labelJustify='c',
            minW=50
        )

class c_menu_block_items:
    """ Třída reprezentující blok položek menu, který může být zobrazen pomocí 'printBlock'  
    lze použít call pro získání listu položek, tzn př.
        
        ```
        m=c_menu_block_items("a")
        print(m())
        ```
    """
    
    _l:List[Tuple[str,str]]=[]
    
    def __init__(self,items:List[Union[str,Tuple[str,str],'c_menu_block_items']]=None):
        self._l=[]
        if items:
            self.extend(items)
    
    def __repr__(self):
        return self._l.__repr__()
    
    def _sanitizeItem(self,item:Union[str,Tuple[str,str]],boolNoError:bool=False) -> Tuple[str,str]:
        """Sanitizuje položku a vrátí tuple s dvěma hodnotami
        
        Parameters:
            item (Union[str,Tuple[str,str]]): položka ke zpracování, může být:
                - `str`, tak se použije (val,'')
                - `tuple`, tak se použije (val[0],val[1] nebo '' pokud je len 1), pokud je len nula tak se ignoruje
                - `list` = stejně jako tuple
                - ostatní hodnoty vyvolají chybu nebo vrátí prázdný tuple viz boolNoError
                - POZOR pokud je None tak se v menu přeskočí - prázdný řádkek
            boolNoError (bool): default(False) pokud je True, tak nevyvolává chybu, ale vrátí prázdný tuple
            
        Returns:
            Tuple[str,str]: výstupní hodnota
            
        Raises:
            ValueError: pokud je formát položky neplatný a boolNoError je False
        """
        if isinstance(item,str):
            return (item,"")
        elif isinstance(item, (tuple,list)):
            if len(item)>1 and isinstance(item[0],str) and isinstance(item[1],str):
                return item
            elif len(item)==1 and isinstance(item[0],str):
                return (item[0],"")
        if boolNoError:
            return ("","")
        raise ValueError("Invalid format of item")
    
    def clear(self) -> 'c_menu_block_items':
        """Vyčistí seznam
        """
        self._l.clear()
        return self
    
    def append(self,item:Union[str,Tuple[str,str]]) -> 'c_menu_block_items':
        """Přidá položku do seznamu
        
        Parameters:
            item (Union[str,Tuple[str,str]]): položka k přidání, může být:
                - `str`, tak se použije (val,'')
                - `tuple`, tak se použije (val[0],val[1] nebo '' pokud je len 1), pokud je len nula tak se ignoruje  
                    - pokud je val[1]=='c' tak se val[0] vycentruje (přidají se mezery okolo)
                - `list` = stejně jako tuple
                - None = Přeskočí se, vynechá se
                - ostatní hodnoty vyvolají chybu
        Returns:
            c_menu_block_items: vrátí instanci třídy
        """
        if item is None:
            return self
        self._l.append(self._sanitizeItem(item))
        
    def extend(self,items:Union[str,'c_menu_block_items',List[Union[str,Tuple[str,str]]]]) -> 'c_menu_block_items':
        """Přidá položky do seznamu
        
        Parameters:
            items (Union[str,'c_menu_block_items',List[Union[str,Tuple[str,str]]]): položky k přidání, může být:
                - `str`, tak se použije (val,'')
                - `tuple`, tak se použije (val[0],val[1] nebo '' pokud je len 1),
                    - pokud je len nula tak se ignoruje
                    - pokud je val[1]=='c' tak se val[0] vycentruje (přidají se mezery okolo)
                - `list` = stejně jako tuple
                - `c_menu_block_items` = jiný objekt c_menu_block_items, jeho obsah se přidá k tomuto objektu
                
        Returns:
            c_menu_block_items: vrátí instanci třídy
        
        """
        if isinstance(items,(list,tuple)):
            for item in items:
                self._l.append(self._sanitizeItem(item))            
            return self
        elif isinstance(items,c_menu_block_items):
            self._l.extend(items._l)
            return self
        elif isinstance(items,str):
            self._l.append((items,""))
            return self
        raise ValueError("Invalid format of items")
    
    def __iter__(self):
        return iter(self._l)
    
    def __len__(self):
        return len(self._l)
    
    def __getitem__(self,idx:int) -> Tuple[str,str]:
        return self._l[idx]
    
    def __setitem__(self,idx:int,item:Union[str,Tuple[str,str]]):
        self._l[idx]=self._sanitizeItem(item)
        
    def __delitem__(self,idx:int):
        del self._l[idx]
        
    def __call__(self, *args, **kwds):        
        """Vrátí list položek
        
        Parameters:
            *args: nepoužito
            **kwds: nepoužito            
            
        Returns:
            List[Tuple[str,str]]: výstupní hodnota
        """
        return self._l

class c_menu:
    """ Třída reprezentující menu, doporučuje se extend s přepisem potřebných hodnot """

    menu: list[c_menu_item] = []
    """ Položky menu """

    title: c_menu_block_items = c_menu_block_items('Menu')
    """ Název menu, může být jednořádkový nebo víceřádkový s LF bez CR """

    subTitle: c_menu_block_items = c_menu_block_items()
    """ Podtitulek menu - je to řádek za title odsazený mezerou, může být multiline s LF bez CR """

    afterTitle: str = ""
    """ Text, který se zobrazí po menu tzn za oddělovací čarou """

    afterMenu: str = ""
    """ Text, který se zobrazí po menu tzn za oddělovací čarou voleb - pod menu """

    lastReturn: onSelReturn = None
    """ Poslední návratová hodnota z funkce onSelect """
    
    onEnterMenu: Callable[['c_menu'] , Union[onSelReturn,str,None] ] = None
    """ Funkce, která se zavolá před zobrazením menu, a dokáže menu bez zobrazení ukončit, lze použít pro tzv precheck.  
    Tzn je voláno jen jednou při před prvním zobrazení.
    - v `self._runSelItem` jsou data položky menu `c_menu_item`, která byla vybrána a vstoupila do `run`
    - v `self.mData` je reference na data c_menu_item z `_runSelItem`    
    
    POZOR pokud vrátí neprázdný string tak se tím oznamuje aby bylo menu ukončeno s chybou, tzn vrátí se do předchozího
    kam předá tento text jako chybu
    
    Parameters:
        self (c_menu):  instance třídy `c_menu`, doporučuje se funkce z vlastního menu
        
    Returns:
        ret (onSelReturn): tak se návrat z měnu řídí touto proměnnou, POZOR property
            - `err` jen nastaví chybovou zprávu pod menu, neukončí jej
            - `ok`  jen zobrazí hlášku pod menu jako info
            - `endMenu` = True menu ukončí, pokud nastavíme `err` tak se zobrazí chyba `ok` je ignorováno
        ret (str):   pokud není prázdný tak se vrátí do předchozího menu s chybou
        ret (False): jen ukončí menu
        ret (None):  nebo cokoliv jiného nic neovlivní a pokračuje se dál
    """
        
    onShowMenu: Callable[['c_menu'], None] = None
    """ Funkce která se volá pokaždé před zobrazením menu, po zobrazení header-u,
    lze např dynamicky generovat položky menu
    nebo updatovat header podle stavu systému
    
    Parameters:
        self (c_menu): instance třídy `c_menu`, doporučuje se funkce z vlastního menu
        
    Returns:
        None
    """
    
    onShownMenu: Callable[['c_menu'], None] = None
    """ Funkce, která se zavolá pokaždé po zobrazení menu, před input-em
    
    Parameters:
        self (c_menu): instance třídy `c_menu`, doporučuje se funkce z vlastního menu
        
    Returns:
        None
    """
    
    onExitMenu: Callable[['c_menu'], Union[None,str,bool]] = None
    """ Funkce, která se zavolá po ukončení menu, např volba Back, ne pro Exit  
    
    Parameters:
        self (c_menu): instance třídy `c_menu`, doporučuje se funkce z vlastního menu
        
    Returns:
        ret (False): jen se menu neukončí - Zákaz ukončení menu
        ret (str):   pokud není prázdný tak se vrátí do předchozího menu s chybou
        ret (other): nic neovlivní a pokračuje se v ukončení menu
    """

    choiceBack: c_menu_item = c_menu_item(TXT_BACK, "b", lambda i: onSelReturn(endMenu=True), "")
    """ Položka menu pro návrat z menu, pokud nechceme zobrazit nastavíme na None """

    ESC_is_quit:bool=True
    """ Pokud je True, tak stisk ESC ukončí menu, pokud je False, tak se ignoruje
    Pokud je true tak se zobrazí v menu 'ESC - Exit' a b -Back ne
    """
    
    minMenuWidth:int=0
    """Minimální šířka menu, pokud je nastaveno tak se menu nezmenší pod tuto hodnotu"""

    choiceQuit: c_menu_item = c_menu_item(TXT_QUIT, "q", lambda i: exit(0), "")
    """ Položka menu pro ukončení programu, pokud nechceme zobrazit nastavíme na None """

    setInputMessageWitthToLastCalc:bool=True
    """Pokud je True, tak v modulu input nastaví min šířku zpráv podle poslední vypočítané šířky menu
    """

    _runSelItem:c_menu_item=None
    """ Položka menu, která byla vybrána a vstoupila do run, pokud bylo toto menu definováno jako sub menu v onSelect """
    
    _mData:Any=None
    """ menu Data, která byla předána z _runSelItem.data, můžeme přepsat v potomkovi správným typem pro IDE """

    _lastCalcMenuWidth: int = 50
    """poslední spočítaná šírka menu"""
    
    _selectedItem: c_menu_item = None

    def __init__(
        self,
        menu: list[c_menu_item,None,c_menu_title_label] = [],
        minMenuWidth:int=0,
        esc_is_quit:bool=None, # pokud None tak se použije self.ESC_is_quit
        quitEnable:bool=True,
        title:Union[str,c_menu_block_items]='Menu',
        subTitle:Union[str,c_menu_block_items]='',
    ):
        """Inicializace menu
        
        Parameters:
            menu (list[c_menu_item]): default `[]`, nepovinné, položky menu
            minMenuWidth (int): default `0`, nepovinné, minimální šířka menu, pokud je nastaveno tak se menu nezmenší pod tuto hodnotu,  
                povolené hodnoty jsou 0, a pak rozsah 20-100
            
        Raises:
            ValueError: pokud není menu list nebo obsahuje jiné typy než c_menu_item            
        """
        # kontrola items
        if not isinstance(menu, (list, tuple)):
            raise ValueError(TXT_CMENU_ERR06)
        for i in range(len(menu)):
            if menu[i] is None:
                continue
            if not isinstance(menu[i], (c_menu_item,c_menu_title_label)):
                raise ValueError(TXT_CMENU_ERR07)
        self.menu = menu
        
        if not isinstance(minMenuWidth,int):
            raise ValueError(TXT_CMENU_ERR08)
        if minMenuWidth<0:
            minMenuWidth=0
        if minMenuWidth>100:
            minMenuWidth=100
        if minMenuWidth>0 and minMenuWidth<20:
            minMenuWidth=20
        self.minMenuWidth=minMenuWidth
        
        if not isinstance(esc_is_quit,bool) and esc_is_quit is not None:
            raise ValueError(TXT_CMENU_ERR09)
        if not esc_is_quit is None:
            self.ESC_is_quit=esc_is_quit
        
        if not isinstance(quitEnable,bool):
            raise ValueError(TXT_CMENU_ERR10)
        if not quitEnable:
            self.choiceQuit=None
            
        if isinstance(title,str):
            title=c_menu_block_items(title)
        if not isinstance(title,c_menu_block_items):
            raise ValueError(TXT_CMENU_ERR11.format(co="title"))
        self.title=title
        
        
        if isinstance(subTitle,str):
            subTitle=c_menu_block_items(subTitle)
        if not isinstance(subTitle,c_menu_block_items):
            raise ValueError(TXT_CMENU_ERR11.format(co="subTitle"))
        self.subTitle=subTitle

    def __getList(self) -> list[c_menu_item]:
        """ Vrací seznam položek menu s, pokud není None, back a quit """
        ret: list[c_menu_item] = []
        for item in self.menu:
            ret.append(item)
            
        e=[]
        if self.choiceBack and  not self.ESC_is_quit:
            e.append(self.choiceBack)
        if self.ESC_is_quit:
            e.append(c_menu_item(TXT_ESC_isExit))
        if self.choiceQuit:
            e.append(self.choiceQuit)
            
        if e:
            ret.append(None)
            ret.extend(e)

        # volby převedeme na malá otrimovaná písmena, včetně int na string
        for item in ret:
            if item is None:
                continue
            item.choice = str(item.choice).lower().strip()
            if type(item.choice) == int:
                item.choice = str(item.choice)
        
        return ret
    
    @staticmethod
    def sanitizeToStr(val)->str:
        """pokud je None tak vrátí prázdný řetězec, jinak vrátí string
        
        Parameters:
            val: hodnota ke zpracování
            
        Returns:
            str: výstupní hodnota
        """
        try:
            return "" if val is None else str(val)
        except:
            return ""
    
    @staticmethod
    def sanitizeListFroProcess(lst)->List[Tuple[str,str]]:
        """Převede list na list řetězců, pokud je None tak vrátí prázdný list
        
        Parameters:
            lst: list k zpracování
            
        Returns:
            List[List[str,str]]: výstupní list
        """
        if isinstance(lst,str):
            lst=[lst]
        if not isinstance(lst, (list, tuple)):
            raise ValueError(TXT_CMENU_ERR04)

        if not lst:
            return []
                
        return [
            [i, ""] if isinstance(i, str) else
            [c_menu.sanitizeToStr(i[0]), c_menu.sanitizeToStr(i[1])]    if isinstance(i, (tuple, list)) and len(i) > 1  else
            [c_menu.sanitizeToStr(i[0]), ""                        ]    if isinstance(i, (tuple, list)) and len(i) == 1 else
            [" "                       , ""                        ]    if isinstance(i, (tuple, list)) and len(i) == 0 else
            ["ERROR, row type"         , ""                        ]
            for i in lst
        ]
    
    @staticmethod
    def getBrackets(b:str)->Tuple[str,str]:
        """Sanitizuje vstup a vrátí pár závorek podle zadaného znaku
        
        Parameters:
            b (str): závorka, může být "(","[","{","<" anebo "",  
                pro nepárové znaky jsou povolené tyto znaky "/","\\","|"
        
        Returns:
            Tuple[str,str]: pár závorek L a R
        """        
        # sanitizace závorek
        b = b[0] if isinstance(b, str) and b else "" 
        
        if not b:
            return "",""
                
        if ( x:=_bracket_pairs.get(b) ):
            return b, x
        elif b in [":","-"]:
            return b + " ", ""
        
        return "",""
    
    @staticmethod
    def processList(
        lst: c_menu_block_items,
        onlyOneColumn: bool = False,
        spaceBetweenTexts: int = 3,
        rightTxBrackets: str = "(", # podpora "", "(", "[", "{", ":" a "-"
        minWidth: int = 0,
        linePrefix:str='', # může být například '- '
    )-> Tuple[List[str],int]: # list položek a max délku řádku        
        spaceBetweenTexts = constrain(spaceBetweenTexts, 3, 100)

        if not lst:
            return [], 0
        
        if not isinstance(lst, c_menu_block_items):
            raise ValueError(TXT_CMENU_ERR02)
        
        lst=lst()

        # nastavíme levou a pravou stranu závorek
        brL,brR=c_menu.getBrackets(rightTxBrackets)

        # Převedeme list na list řetězců
        ret = []
        for item in lst:                                    
            x1 = item[0].splitlines()
            x2 = item[1].splitlines() if len(item) > 1 else []
            
            i_l=[""] if not x1 else x1
            i_r=[""] if not x2 else x2
            center = (item[1] or "").strip().lower() == "c"
            
            if center:
                # pokud je požadováno centrování, tak nastavíme pravý text na prázdný a provedeme centrování
                max_len = max(len(line) for line in i_l)
                max_len = max(max_len, minWidth)
                i_l = [ line.center(max_len) for line in i_l ]
                i_r = [''] * len(i_l)
            else:
                # dorovnej délky polí
                if len(i_l) > len(i_r):
                    i_r.extend([""] * (len(i_l) - len(i_r)))
                elif len(i_r) > len(i_l):
                    i_l.extend([""] * (len(i_r) - len(i_l)))
                
            # zpracujeme přídavky            
            #   prefix
            i_l = [ f'{linePrefix}{i}' for i in i_l]
            #   závorky                    
            i_r = [ f"{brL}{i}{brR}" if i else '' for i in i_r]
                    
            # vyžadujeme jeden column tak pravý vynulujeme
            if onlyOneColumn:
                i_r = [''] * len(i_l)

            # toto by vážně nemělo nastat - pro jistotu
            if len(i_l) != len(i_r):
                raise ValueError(TXT_CMENU_ERR01)
            
            # přidáme do výsledku
            ret.extend(zip(i_l, i_r))
        lst=ret

        width=minWidth
        # vypočítáme maximální délku levého a pravého sloupce
        for i in ret:
            l=len(text_remove_terminal_ASCII_ESC(i[0]))
            r=len(text_remove_terminal_ASCII_ESC(i[1]))
            c= l+r
            if l>1 and r>0:
                c+=spaceBetweenTexts
            width = max(width, c)

        # vytvoříme list z width
        ret = []
        for i in lst:
            l=text_remove_terminal_ASCII_ESC(i[0])
            r=text_remove_terminal_ASCII_ESC(i[1])
            
            sp_btw = width - len(l)
            if len(l) > 0 and len(r) > 0:
                sp_btw = sp_btw - len(r)                
                        
            if sp_btw < 0:
                raise ValueError(TXT_CMENU_ERR03.format(tx=sp_btw))
            
            # generování řádku se str nebo tuple, výstup bude jen List[str] s konstantní šířkou
            if l and r:
                # oba sou texty tak append-neme s mezerou mezi
                ret.append(f"{i[0]}{' ' * sp_btw}{i[1]}")
            elif l and not r:
                # jen levý text
                # pokud se jedná o jednoznakový znak z `_lineCharList` tak se zopakuje v délce width
                spl=l.strip() # získáme čisté znaky
                splW=len(l)-len(spl) # zjistíme počet mezer na začátku
                if not spl and splW>0:
                    # pokud je to mezera nebo mezery tak spacer
                    ret.append( " " * width)
                else:
                    pref=spl.startswith("- ") # pokud je to prefix tak použijeme posléze
                    if pref and len(spl)==3:
                        spl=spl[2]
                        splW=0 # oddělovač se kreslí od začátku bez odrážky
                    # byly přítomné znaky, otestujeme zda je to znak z _lineCharList
                    if spl in _lineCharList and len(spl)==1:
                        # pokud je to znak z _lineCharList, tak se zopakuje width krát
                        # dosadíme mezery na začátek pokud byly
                        ret.append( " " * splW + (width-splW) * spl )
                    else: # jinak se dorovná mezerami zprava
                        ret.append(i[0]+(" " * (width-len(l))))                                        
            else:
                # jen pravý text
                # dorovnáme mezerami zleva
                ret.append( (" " * (width-len(r))) + i[1])
                                
        return ret, width

    @staticmethod
    def printBlok(
        title_items: Union[c_menu_block_items,List[str], List[Tuple[str, str]], List[List[str]]],
        subTitle_items: Union[c_menu_block_items,List[str], List[Tuple[str, str]], List[List[str]]],
        charObal: str = "*",
        leftRightLength: int = 3,
        charSubtitle: str = "-",
        eof: bool = True,
        space_between_texts: int = 3,
        min_width: int = 0,
        rightTxBrackets: str = "(",
        outToList:list=None
    ) -> int:
        """
        Vytiskne blok textu s ohraničením nebo bez, podle volby
        
        Parameters:
            title_items (Union[c_menu_block_items,List[str], List[Tuple[str, str]], List[List[str]]]): Položky k vytisknutí, může být:
                - `c_menu_block_items` identický s `List[Tuple[str, str]]`
                - `str`, tak se vytiskne zleva doprava
                - `tuple`, tak se vytiskne index 0 zleva doprava a index 1 zprava doleva
                - `list` = stejně jako tuple
            subTitle_items (Union[c_menu_block_items,List[str], List[Tuple[str, str]], List[List[str]]]): Položky podtitulku, může být:
                (platí stejné typy jako pro `title_items`),  
                které budou odsazené `charSubtitle` pokud je uveden; pokud je prázdný řetězec `""`,
                mají stejné zarovnání jako `title_items`
            charObal (str): Znak ohraničení:  
                - pokud je prázdný řetězec `""`, ohraničení se nezobrazí
                - Pokud se jako znak ohraničení použije `'|'`, vytiskne se horní a dolní řádek znakem `'-'`, pouze tam kde je text mezi ohraničeními.
            leftRightLength (int): Počet znaků charObal na levé a pravé straně, pokud nula tak je vynechán
                min 0 max 10
            charSubtitle (str): Znak odsazení pro podtitulek, může být "" jinak se použije jako prefix + mezera
            eof (bool): True pokud se má přidat prázdný řádek na konec
            space_between_texts (int): Počet mezer mezi levým a pravým textem u tuple položek, výchozí je 3
            min_width (int): Minimální šířka menu
            rightTxBrackets (str): default = "(" typ závorky nebo odsazení, pokud:  
                - "(","[","{" tak se zobrazí závorky kolem pravého textu tzn např "xxx" bude "(xxx)
                - "" tak se text neupravuje
                - ":","-" tak budou použity jako odsazení, tzn např "xxx" bude ": xxx"
            outToList (list): Pokud je uveden, tak se výstup vytiskne/přidá do tohoto listu místo na obrazovku
            
        Returns:
            int: délka nejdelšího řádku, vnější rozměr
        
        """
        title_items = c_menu_block_items(title_items)
        subTitle_items = c_menu_block_items(subTitle_items)
        
        # Sanitizace vstupů
        charObal = charObal[0] if isinstance(charObal, str) and charObal else ""
        leftRightLength = constrain(leftRightLength,0,10) if isinstance(leftRightLength, int) else 0
        
        # Zajištění, že pokud je leftRightLength 0 nebo charObal prázdný, obalování nebude použito
        if leftRightLength == 0 or not charObal:
            leftRightLength = 0
            charObal = ""        
        
        # Určení, jestli bude použito ohraničení, tady už je jedno jesli or nebo and
        obal = bool(charObal or leftRightLength)
        
        # Určení šířky ohraničení
        obalW = leftRightLength * 2 + 2 if obal else 0        
        
        # init var    
        width = max(0, min_width - obalW)
        out=[]
        
        # jen zjistíme šířku tutilků, pokud by byly náhodou delší jak title items
        width = max(width, 
            c_menu.processList(
                subTitle_items,
                onlyOneColumn=False,
                linePrefix=charSubtitle+" ",
                minWidth=width,
                rightTxBrackets=rightTxBrackets
            )[1]
        )
        pass
        # začínáme finální výpočty, tzn první title ale už s min_width titulků
        processed_title_items = c_menu.processList(
            title_items,
            onlyOneColumn=False,
            spaceBetweenTexts=space_between_texts,
            minWidth=width,
            rightTxBrackets=rightTxBrackets
        )
        width = max(width, processed_title_items[1])
        processed_title_items = processed_title_items[0]

        # finálně zpracujeme subTitle_items, protože se mohla změnit šířka o title items
        processed_subTitle_items = c_menu.processList(
            subTitle_items,
            onlyOneColumn=False,
            linePrefix=charSubtitle+" ",
            minWidth=width,
            rightTxBrackets=rightTxBrackets
        )
        width = max(width, processed_subTitle_items[1])
        processed_subTitle_items = processed_subTitle_items[0]

        # finální komplet items
        menu = processed_title_items + processed_subTitle_items      
        
        # vytvoříme spacer z charObal, pokud je "" tak bude ""
        # pokud roura tak změníme na mínus
        ow=width + ( 2 if obal else 0 )
        spacer = "-" * ow if charObal=="|" else charObal * ow
                
        h_Obal = charObal * leftRightLength

        if obal:
            # přidáme okraje na spacer, pokud je obal
            # spacer by měl být = width+obalW
            spacer = f"{h_Obal}{spacer}{h_Obal}"
        
        if obal:
            # vložíme horní ohraničení, pokud je požadováno
            out.append(spacer)
        
        # vložíme položky menu podle obalu
        out.extend(
            [
                f"{h_Obal} {item} {h_Obal}" if obal else item
                for item in menu
            ]
        )
                            
        if obal:            
            # Vytiskneme spodní ohraničení, pokud je požadováno
            out.append(spacer)
        
        if eof:
            # Přidáme prázdný řádek, pokud je eof nastaveno na True
            out.append("")

        if isinstance(outToList,list):
            # nechceme tisknout ale vrátit
            outToList.extend(out)
        else:
            # požadujeme tisk, nechceme vracet
            print("\n".join(out))
        
        return max(width, width+obalW)

    def _print_getMenuList(self,menu_list:List[c_menu_item],width:int)->list:
        """interní funkce, vrátí list pro  tisk menu položek

        Parameters:
            menu_list (list): seznam položek menu z funkce __getList
            width (int): šířka menu

        Returns:
            list: list of tuples pro tisk menu, tzn pro vstup do printBlok
        """
        # zjistíme maximální délku choice
        max_l_LenChoices=0
        for item in menu_list:
            if not item.hidden and item.choice:
                if item.enabled:
                    max_l_LenChoices=max(max_l_LenChoices,len(item.choice))
                else:
                    max_l_LenChoices=max(max_l_LenChoices,len(TXT_DISABLED))
        # vytvoříme menu
        ch=[]
        for item in menu_list:
            if not item.hidden:
                lbl=item.label
                chcs=item.choice
                if not item.enabled:
                    chcs = TXT_DISABLED
                chcs=chcs.ljust(max_l_LenChoices)
                chcs+= " - " if item.choice else "   "
                if len(str(lbl).strip())==0:
                    chcs = ""
                    lbl = ""
                elif lbl in _lineCharList:
                    chcs = ""
                    # lbl = lbl * (width-5) # -2 mezery uvnitř obalu
                    
                sel="  "
                if self._selectedItem==item:
                    sel=chr(0x25B6)+" " # černá šipka doprava
                
                ch.append( [f"{sel}{chcs}{lbl}",item.atRight] )
        return ch
        

    def __print(self, lastRet: onSelReturn = None, toOut:list=None) -> int:        
        afterTitle=self.afterTitle
        if isinstance(afterTitle,str):            
            afterTitle=afterTitle.splitlines()
        afterTitle=c_menu_block_items(afterTitle)
        
        afterMenu=self.afterMenu
        if isinstance(afterMenu,str):
            afterMenu=afterMenu.splitlines()
        afterMenu=c_menu_block_items(afterMenu)
            
        # vygenerujeme menu položky voleb
        mx = self.__getList()
        x=self.checkItemChoice(mx)
        if x:
            raise ValueError(TXT_RPT_CHCS+": "+', '.join(x))
        
        menu_list=[]
        for item in mx:
            if isinstance(item, c_menu_title_label):
                menu_list.extend([
                    c_menu_item(''),
                    item,
                    c_menu_item('')
                ])
            elif item is None:
                menu_list.append(c_menu_item(''))
            else:
                menu_list.append(item)
        
        tt=self.title
        if isinstance(tt,str):
            tt=tt.splitlines()
        tt=c_menu_block_items(tt)
        
        st=self.subTitle
        if isinstance(st,str):
            st=st.splitlines()
        st=c_menu_block_items(st)        
        
        out=[]
        width=self.minMenuWidth
        # dva průchody, výpočetní a zobrazení
        for step in range(2):        
            out=[]
                  
            # záhlaví menu  
            width = max(width, self.printBlok(tt, st, "|", 3, "-", True, min_width=width, outToList=out) )

            # pokud je tak afrerTitle
            if self.afterTitle:
                width = max(width, self.printBlok(afterTitle, [], "", 0, "", False, min_width=width, outToList=out))

            ch=self._print_getMenuList(menu_list,width)            
            width = max(width,self.printBlok(ch, [], "-", 0, "", True,min_width=width, outToList=out))
                        
            if self.afterMenu:
                width = max(width, self.printBlok(afterMenu, [], "", 0, "", False, min_width=width, outToList=out))
                
            if lastRet:
                if lastRet.err:
                    width = max(width, self.printBlok([TXT_ERR, lastRet.err], [], "!", 3, "", False,min_width=width , outToList=out))
                if lastRet.ok:
                    width = max(width, self.printBlok([TXT_NFO, lastRet.ok], [], "-", 3, "", False,min_width=width, outToList=out))
        
        # inverze přes escape pokud >
        for i in range(len(out)):
            if out[i].startswith(" "+chr(0x25B6)) or out[i].startswith(chr(0x25B6)):
                out[i]=text_inverse(out[i])
             
        if isinstance(toOut,list):
            toOut.extend(out)
        else:
            cls(False)
            print("\n".join(out),flush=True)

        return width

    def searchItem(self, choice: str) -> Tuple[c_menu_item, bool]:
        """ Vyhledá položku menu podle klávesy/zkratky vrací:
        - None = Nenalezeno
        - c_menu_item = nalezeno
        - True = volba byla nalezena částečně, např pro víceznakové položky, tzn choice
          je částí textu od počátku v item.choice
        """
        if not choice:
            return None, False
        c=str(choice).lower().strip()
        choice=None
        partOfLonger=False
        for item in self.__getList():
            if not item is None and  item.enabled and not item.hidden and item.choice:
                if item.choice == c:
                    if choice is None:
                        choice = item
                if item.choice.startswith(c) and len(c) != len(item.choice):
                    partOfLonger=True
        return  choice, partOfLonger        
    
    def nextItem(self, forward:bool=True) -> None:
        """Posun na další položku menu

        Parameters:
            forward (bool, optional): True = další, False = předchozí. Defaults to True.
            
        Returns:
            None
        """
        ls = self.__getList()
        if not ls:
            self._selectedItem = None
            return

        max_count = len(ls)
        if self._selectedItem is None:
            pos = 0
        else:
            try:
                pos = (ls.index(self._selectedItem) + (1 if forward else -1)) % len(ls)
            except ValueError:
                pos = 0

        while max_count > 0:
            x = ls[pos]
            if not x is None and x.enabled and not x.hidden and x.choice:
                self._selectedItem = x
                return
            pos = (pos + (1 if forward else -1)) % len(ls)
            max_count -= 1

        self._selectedItem = None           

    def checkItemChoice(self, list:list[c_menu_item]) -> Union[None, List[str]]:
        """ Zkontroluje zda se neopakuje klávesová zkratka v menu a vrací
        - None pokud je vše v pořádku
        - list[str] seznam položek, které mají stejnou klávesu        
        """
        ch=[]
        err=[]
        for i in list:
            if i is None:
                continue
            if not i.hidden and i.enabled and i.choice:
                if i.choice in ch:
                    err.append(TXT_RPT_CHCS+': '+i.choice)
                ch.append(i.choice)
        return err if len(err)>0 else None
        
    def run_refresh(self,c:str,first:bool=False) -> Union[bool,str]:
        """pokud vrátí string tak se menu ukončí s chybou a vrátí tento string jako chybu"""
        from .input import setMinMessageWidth
        if first:
            sys.stdout.write(
                f"\033[H{TXT_SCR_LDNG}\033[J"
            )
        
        err=[]                 
        if self.menuRecycle:
            if self.onShowMenu:
                try:
                    # log.debug(f"onShowMenu")
                    self.onShowMenu()
                except Exception as e:
                    self.lastReturn = onSelReturn(err=str(e))
                    log.error(f"Exception on onShowMenu",exc_info=True)
                    err.append(str(e))
        
        if self._selectedItem is None:
            self.nextItem()
        out=[]
        self._lastCalcMenuWidth = self.__print(self.lastReturn, out)
        if self.setInputMessageWitthToLastCalc is True:
            setMinMessageWidth(self._lastCalcMenuWidth)
        
        if self.menuRecycle:
            if self.onShownMenu:
                try:
                    # log.debug(f"onShownMenu")
                    self.onShownMenu()
                except Exception as e:
                    self.lastReturn = onSelReturn(err=str(e))
                    log.error(f" Exception on onShownMenu",exc_info=True)
                    err.append(str(e))
        
        if not c:
            out.append(TXT_PRESS_KEY)
        if len(c) > 0:            
            ci=text_inverse(f" {c} ")
            out.append(TXT_SEL_INFO.format(c=ci))
        else:
            out.append(TXT_SELECT.format(c=c))
            
        ok=True
        if len(err)>0:
            out.extend(err)            
            ok=False
        
        # \033[H - nastaví kurzor na začátek obrazovky
        # \033[J - smaže od kurzoru dolů
        # \033[K - smaže řádek od kurzoru doprava
        o="\033[K"+("\n\033[K".join(out))+"\n"
        sys.stdout.write(
            f"\033[H{o}\033[J"
        )
        
        return ok

    menuRecycle:bool=False

    def run(self,item:c_menu_item=None) -> Union[None,str]:
        """ Spustí menu 
        pokud se spouští z parent menu tak 'item' obsahuje položku menu, která byla vybrána,
        tato položka je zapsána do self._runSelItem a může být použita v rámci tohoto objektu menu, navíc data z této položky
        jsou zapsána do self._mData a stejně tak mohou být použita v rámci tohoto objektu menu
        
        pokud je to volání menu<>menu a vrátí string, tak se string přenese jako chyba do parent menu a zobrazí
        
        Po návratu z menu:
            - (bez chyby) lze poslední vybranou položku získat z metodou **getLastSelItem**
            - šířku lze získat (pokud byla přesažena) metodou **getCalcMenuWidth**
        
        Parameters:
            item (c_menu_item, optional): Položka menu, která byla vybrána. Defaults to None.
            
        Returns:
            Union[None,str]: None pokud je vše v pořádku, jinak string s chybou
        
        """
        self._runSelItem=item
        self._mData=None
        if self._runSelItem:
            if hasattr(self._runSelItem,'data'):
                self._mData=self._runSelItem.data
        
        first = True
        """První načtení menu a s tímspojené akce jako text loadnig nebo první zpoždění kvůli klávesnici"""
        
        log.info(f" >>> RUN Menu '{self.__class__.__name__}' started ---")
        c=""
        
        self.selectedItem = None
        self.menuRecycle=True
        
        if self.onEnterMenu:
            try:
                x=self.onEnterMenu()
                if x is False:
                    return None
                elif isinstance(x,str):
                    return x
                if isinstance(x, onSelReturn):
                    if x.endMenu:
                        return x.err if x.err else None
                    self.lastReturn=x
            except Exception as e:
                log.error(f"Exception on onEnterMenu",exc_info=True)
                return "Exception on onEnterMenu: "+str(e)
        
        while True: 
            x=self.run_refresh(c,first)
            self.menuRecycle=False
            if isinstance(x,str):                
                return x
            
            if first:
                sleep(0.25) # opoždění při prvním načtení aby se stihla klávesnice stabilizovat a nezopakovala se např volba
            first = False

            xc=getKey(ESC_isExit=True)
            
            # pokud je klávesa string tak vezmeme první znak do xk pro jednoznakové testy
            xk=''
            if isinstance(xc,str) and xc:
                xk=xc[0]
            
            self.lastReturn = None
            # zpracuje escape
            if xc is False:
                if c:
                    # pokud je zadána sekvence kláves tak se napřed zruší než se provede escape menu, pokud je povoleno
                    c=""
                    continue # čekej na další klávesu
                if self.ESC_is_quit:
                    # je povoleno exit
                    e=self.callExitMenu(item)
                    if isinstance(e,str):
                        # chybu předáme
                        self._selectedItem=None # zrušíme výběr je to EXIT
                        return e
                    if not x is False:
                        # návrat bez chyby a zákazu
                        self._selectedItem=None # zrušíme výběr je to EXIT
                        return                
                continue # Nebyla detekována akce ESC nebo byl detekován zákaz (False) - čekej na další klávesu
            # F5 - refresh
            elif xc == '\x1b[15~':
                self.menuRecycle=True
                continue
            elif xc == '\x7f':
                ## pokud backspace tak vymažeme poslední znak
                c=c[:-1]
                continue # čekej na další klávesu
            elif xc in ['\x1b[A','\x1b[B','\x1b[C','\x1b[D']:
                # detekovány klávesy šipek, tak zpracuj
                if xc == '\x1b[A':
                    self.nextItem(False)
                elif xc == '\x1b[B':
                    self.nextItem(True)
                continue # čekej na další klávesu
            elif xk in ['\t',' ']:
                # zakázané znaky
                continue
            
            if not xk in ['\r','\n']:
                # pokud není RETURN tak přidej znak a vymaž old položku 
                # a najde položku k aktuální volbě
                c+=xk
                self._selectedItem=None
            
                # najdeme novou položku pokud nebyl enter
                s_chr_itm=self.searchItem(c)
                if s_chr_itm[0]:
                    # nalezena položka z hodná s aktuální volbou, tj znakem nebo sadou znaků
                    # toto musí být před testem delší volby, která má continue a pak by se nezapsala do self
                    self._selectedItem = s_chr_itm[0]
                if s_chr_itm[1] is True:
                    # byla nalezená položka ale její volba je obsažena v jiné delší volbě, tak se pokračuje čekáním na další znak
                    continue                
                if self._selectedItem:
                    c=""
                    continue
                c=""
            
            # zpracuj RETURN key
            if not self._selectedItem:
                # pokud RETURN klávesa a není nic vybráno tak další key
                continue
            
            # je vybráno tak zpracujeme
            item=self._selectedItem
            try:
                if isinstance(item.onSelect,c_menu):
                    # detekováno submenu, zpracuj
                    cls()
                    log.debug(f"Sub menu '{item.label}' started ---")
                    e=item.onSelect.run(item)
                    first=True # po návratu je to vpodstatě také první načtení menu
                    # zpracuj návratovou hodnotu ze submenu
                    if isinstance(e,str):
                        self.lastReturn = onSelReturn(err=e)
                    else:
                        self.lastReturn = onSelReturn()
                else:
                    # volej funkci onSelect
                    log.debug(f"onSelect '{item.label}'")
                    if isinstance(item, c_menu_item) and item.clearScreenOnSelect is True:
                        cls()
                    self.lastReturn = item.onSelect(item)
                    # zpracuj návratovou hodnotu z funkce onSelect
                    first=True # po návratu je to vpodstatě také první načtení menu
                    if not isinstance(self.lastReturn, onSelReturn):
                        if isinstance(self.lastReturn, str):
                            ## pokud začíná 'OK' tak není chyba ale info
                            if self.lastReturn[:2].upper() == 'OK':
                                self.lastReturn = onSelReturn(ok=self.lastReturn)
                            else:
                                self.lastReturn = onSelReturn(err=self.lastReturn)
                        else:
                            self.lastReturn = onSelReturn()                            
            except Exception as e:
                self.lastReturn = onSelReturn(err=f'Exception:\n'+traceback.format_exc())
                log.error(f" Exception on processing choice",exc_info=True)
            finally:
                self.menuRecycle=True
                pass
                
            if item.onAfterSelect:
                try:
                    item.onAfterSelect(self.lastReturn,item)
                except Exception as e:
                    self.lastReturn.err = str(e)
                    log.error(f" Exception on onAfterSelect",exc_info=True)
            
            if self.lastReturn.endMenu:
                e=self.callExitMenu(item)
                if isinstance(e,str):
                    return e
                if not x  is False:
                    return
            
            self._selectedItem = None
            sleep(0.1) # malá pauza než se znovu vykreslí menu
       
    def getLastSelItem(self) -> Union[None,c_menu_item]:
        """Vrátí poslední vybranou položku menu
        
        Parameters:
            None
            
        Returns:
            Union[None,c_menu_item]: None pokud není vybrána žádná položka, jinak c_menu_item
        """
        if isinstance(self._selectedItem,c_menu_item):
            return self._selectedItem
        return None
    
    def getCalcWidth(self) -> int:
        """Vrátí šířku menu po posledním zobrazení
        
        Parameters:
            None
            
        Returns:
            int: šířka menu
        """
        return self._lastCalcMenuWidth
                
    def callExitMenu(self,itm: 'c_menu')->Union[bool,str,None]:
        """Interní funkce  
        Zavolá funkci onExitMenu a zpracuje návratovou hodnotu
        
        Parameters:
            itm (c_menu): položka menu, která byla vybrána
            
        Returns:
            Union[bool,str,None]: návrat je:
                - **False** pokud se nemá ukončit menu
                - **string** s chybou pokud se má ukončit s chybou,
                - **None** pokud se má ukončit bez chyby
        """
        cls()
        if self.onExitMenu:
            try:
                x=self.onExitMenu()
                if x is False:
                    self.lastReturn.err = onSelReturn(err=TXT_ABORTED)
                    return False
                if isinstance(x,str):
                    return x
                return None
            except Exception as e:
                self.lastReturn = onSelReturn(err=str(e))
                log.error(f" Exception on onExitMenu",exc_info=True)
        log.info(f" <<< Menu END ---")
        return None
    
    def __repr__(self):
        r= (
            f"c_menu( '{self.title}'"
                f", '{self.subTitle}'"
                f", '{self.afterTitle}'"
                f", '{self.afterMenu}'"
            ")"
        )
        return r

def printBlock(
    
    title_items: Union[c_menu_block_items, List[str], List[Tuple[str, str]], List[List[str]]],
    subTitle_items: Union[c_menu_block_items, List[str], List[Tuple[str, str]], List[List[str]]],
    charObal: str = "*",
    leftRightLength: int = 3,
    charSubtitle: str = "-",
    eof: bool = True,
    space_between_texts: int = 3,
    min_width: int = 0,
    rightTxBrackets: str = "(",
    outToList:list=None,
) -> int:
    """
    Vytiskne blok textu s ohraničením nebo bez, podle volby
    
    Parameters:
        title_items Union[c_menu_block_items, List[str], List[Tuple[str, str], List[List[str]]]: Položky k vytisknutí, pokud je:
            - `c_menu_block_items` identický s `List[Tuple[str, str]]`
            - `str`, tak se vytiskne zleva doprava
            - `tuple`, tak se vytiskne index 0 zleva doprava a index 1 zprava doleva, pokud index je, pokud není je nahrazen ''
            - `list` = stejně jako tuple
        subTitle_items (List[str]): Položky k vytisknutí pod `title_items` (platí stejné typy jako pro `title_items`),  
            které budou odsazené `charSubtitle` pokud je uveden; pokud je prázdný řetězec `""`,
            mají stejné zarovnání jako `title_items`
        charObal (str): Znak ohraničení:  
            - pokud je prázdný řetězec `""`, ohraničení se nezobrazí
            - Pokud se jako znak ohraničení použije `'|'`, vytiskne se horní a dolní řádek znakem `'-'`, pouze tam kde je text mezi ohraničeními.
        leftRightLength (int): Počet znaků charObal na levé a pravé straně
        charSubtitle (str): Znak odsazení pro podtitulek, může být "" jinak se použije jako prefix + mezera
        eof (bool): True pokud se má přidat prázdný řádek na konec
        space_between_texts (int): Počet mezer mezi levým a pravým textem u tuple položek, výchozí je 3
        min_width (int): Minimální šířka menu
        rightTxBrackets (str): default = "(" typ závorky nebo odsazení, pokud:  
            - "(","[","{" tak se zobrazí závorky kolem pravého textu tzn např "xxx" bude "(xxx)
            - "" tak se text neupravuje
            - ":","-" tak budou použity jako odsazení, tzn např "xxx" bude ": xxx"
        outToList (list): Pokud je uveden, tak se výstup vytiskne/přidá do tohoto listu místo na obrazovku
        
    Returns:
        int: délka nejdelšího řádku
    
    """
    return c_menu.printBlok(title_items, subTitle_items, charObal, leftRightLength, charSubtitle, eof, space_between_texts, min_width, rightTxBrackets, outToList)

