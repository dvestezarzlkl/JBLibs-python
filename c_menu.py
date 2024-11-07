# cspell:ignore updatovat,otrimovaná,otrimujeme,CHCS

from .helper import cls,loadLng
from .lng.default import * 
import json
loadLng()

from typing import Callable, Any, Union, List, Tuple
import traceback
from .term import getKey,text_inverse
from .helper import constrain, is_numeric
from time import sleep

from helper import getLogger
log = getLogger(__name__)

_lineCharList = "*-._+=~"

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

    label: str = ""
    """ Zobrazený název položky menu - jednořádkový, například "Start service  
    - pokud necháme prázdné tak z memu bude oddělovací prázdný řádek
    - pokud nastavíme na '-','=','+','_' 
      tak bude oddělovací čára z tohoto znaku v délce title obálky
    """

    choice: str = ""
    """ Klávesová zkratka pro tuto položku menu, například "s" """

    data: Any = None
    """ Data, která se předají do funkce onSelect """

    onSelect: Callable[["c_menu_item"],onSelReturn] = None
    """ Funkce, která se zavolá po stisknutí klávesy pro tuto položku menu, návratová hodnota z funkce je předána do funkce onAfterSelect"""

    onAfterSelect: Callable[[onSelReturn,"c_menu_item"], None] = None
    """ Funkce, která se zavolá po skončení funkce onSelect, návratová hodnota z funkce onSelect je předána do této funkce """

    enabled:bool=True
    """ Pokud je False, tak položka nereaguje """
    
    hidden:bool=False
    """ Pokud je True, tak položka není zobrazena """

    atRight:str=""
    """ Pokud je nastaveno, tak se zobrazí na pravé straně menu"""

    def __init__(
        self,
        label: str = "",
        choice: str = "",
        onSelect: Callable[[], None] = None,
        onAfterSelect: Callable[[], None] = None,
        data: Any = None,
        enabled:bool=True,
        hidden:bool=False,
        atRight:str=""
    ):
        self.label = label
        self.choice = choice
        self.onSelect = onSelect
        self.onAfterSelect = onAfterSelect
        self.data = data
        self.enabled=enabled
        self.hidden=hidden
        self.atRight=atRight
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

class c_menu:
    """ Třída reprezentující menu, doporučuje se extend s přepisem potřebných hodnot """

    menu: list[c_menu_item] = []
    """ Položky menu """

    title: str = "Menu"
    """ Název menu, může být jednořádkový nebo víceřádkový s LF bez CR """

    subTitle: str = ""
    """ Podtitulek menu - je to řádek za title odsazený mezerou, může být multiline s LF bez CR """

    afterTitle: str = ""
    """ Text, který se zobrazí po menu tzn za oddělovací čarou """

    afterMenu: str = ""
    """ Text, který se zobrazí po menu tzn za oddělovací čarou voleb - pod menu """

    lastReturn: onSelReturn = None
    """ Poslední návratová hodnota z funkce onSelect """
    
    onEnterMenu: Callable[[] , Union[str,None] ] = None
    """ Funkce, která se zavolá před zobrazením menu, jen jednou při prvním zobrazení 
    `v self._runSelItem` jsou data položky menu `c_menu_item`, která byla vybrána a vstoupila do `run`
    takže pokud v `c_menu_item` nastavíme property `data`, tak jsou dostupné v celém menu pomocí  
    `self._runSelItem` jako objekt položky `c_menu_item` a data z tohoto objektu  
    budou dostupná v `self._mData` jako i v `self._runSelItem.data`
    
    POZOR pokud vrátí neprázdný string tak se tím oznamuje aby bylo menu ukončeno s chybou, tzn vrátí se do předchozího
    kam předá tento text jako chybu
    """
        
    onShowMenu: Callable[['c_menu'], None] = None
    """ Funkce která se volá pokaždé před zobrazením menu, po zobrazení header-u,
    lze např dynamicky generovat položky menu
    nebo updatovat header podle stavu systému
    """
    
    onShownMenu: Callable[['c_menu'], None] = None
    """ Funkce, která se zavolá pokaždé po zobrazení menu, před input-em """
    
    onExitMenu: Callable[['c_menu'], Union[None|bool]] = None
    """ Funkce, která se zavolá po ukončení menu, např volba Back, ne pro Exit  
    - Pokud funkce vrátí `False` tak se menu neukončí
    - Pokud vrátí `str` tak se menu ukončí a text je předán do parent menu jako chyby k zobrazení
    - Pokud vrátí `cokoliv jiného` tak se menu ukončí
    """

    choiceBack: c_menu_item = c_menu_item(TXT_BACK, "b", lambda i: onSelReturn(endMenu=True), "")
    """ Položka menu pro návrat z menu, pokud nechceme zobrazit nastavíme na None """

    ESC_is_quit:bool=True
    """ Pokud je True, tak stisk ESC ukončí menu, pokud je False, tak se ignoruje
    Pokud je true tak se zobrazí v menu 'ESC - Exit' a b -Back ne
    """

    choiceQuit: c_menu_item = c_menu_item(TXT_QUIT, "q", lambda i: exit(0), "")
    """ Položka menu pro ukončení programu, pokud nechceme zobrazit nastavíme na None """

    _runSelItem:c_menu_item=None
    """ Položka menu, která byla vybrána a vstoupila do run, pokud bylo toto menu definováno jako sub menu v onSelect """
    
    _mData:Any=None
    """ menu Data, která byla předána z _runSelItem.data, můžeme přepsat v potomkovi správným typem pro IDE """

    _rowLength: int = 50
    
    _selectedItem: c_menu_item = None

    def __init__(self):
        self.menu = []        
        pass

    def __getList(self) -> list[c_menu_item]:
        """ Vrací seznam položek menu s, pokud není None, back a quit """
        ret: list[c_menu_item] = []
        for item in self.menu:
            ret.append(item)        
        if self.choiceBack and  not self.ESC_is_quit:
            ret.append(self.choiceBack)
        if self.ESC_is_quit:
            ret.append(c_menu_item(TXT_ESC_isExit))
        if self.choiceQuit:
            ret.append(self.choiceQuit)

        # volby převedeme na malá otrimovaná písmena, včetně int na string
        for item in ret:
            item.choice = str(item.choice).lower().strip()
            if type(item.choice) == int:
                item.choice = str(item.choice)
        return ret
    
    @staticmethod
    def processList(
        lst: Union[List[str], List[Tuple[str, str]], List[List[str]]],
        onlyOneColumn: bool = False,
        spaceBetweenTexts: int = 3,
        rightTxBrackets: str = "(", # podpora "", "(", "[", "{", ":" a "-"
        minWidth: int = 0,
        linePrefix:str='', # může být například '- '
    )-> Tuple[List[str],int]: # list položek a max délku řádku
        spaceBetweenTexts = constrain(spaceBetweenTexts, 3, 100)

        if not isinstance(lst, (list, tuple)):
            raise ValueError(TXT_CMENU_ERR04)

        if not lst:
            return [], 0

        # konverze typů numeric na string
        for i in range(len(lst)):
            if is_numeric(lst[i]):
                lst[i] = str(lst[i])
            elif isinstance(lst[i], (list, tuple)):
                for j in range(len(lst[i])):
                    if is_numeric(lst[i][j]):
                        lst[i][j] = str(lst[i][j])
                    elif lst[i][j] is None:
                        lst[i][j] = ""
            elif lst[i] is None:
                lst[i] = ""

        # Získáme závorky
        bracket_pairs = {"(": ")", "[": "]", "{": "}"}
        if not isinstance(rightTxBrackets, str):
            rightTxBrackets = ""            
        rightTxBrackets=str(rightTxBrackets).strip()
        if len(rightTxBrackets) > 1:
            rightTxBrackets = rightTxBrackets[0]
                
        brL=""
        brR=""
        if rightTxBrackets:
            x = bracket_pairs.get(rightTxBrackets)
            if x:
                brR=x
                brL=rightTxBrackets
            elif rightTxBrackets in [":","-"]:
                brL=rightTxBrackets + " "

        # Převedeme list na list řetězců
        ret = []
        for item in lst:
            i_l=[""]
            i_r=[""]
                        
            if isinstance(item, list):
                item = tuple(item)  # Převedeme list na tuple
            
            # pokud numeric tak převedeme na string
            if isinstance(item, int) or isinstance(item, float):
                i_l = [str(item)]                
            elif isinstance(item, str):                
                if item:
                    i_l=item.splitlines()
                    i_r=[""] * len(i_l)
            elif isinstance(item, tuple):
                x1 = item[0].splitlines()
                x2 = []
                if len(item) > 1:
                    x2 = item[1].splitlines()
                    
                if x1 or x2:
                    i_l=[]
                    i_r=[]
                    # zpracuj více-řádky
                    for i in range(max(len(x1), len(x2))):
                        r=""
                        l=""
                        if i < len(x1):
                            l=str(x1[i]).rstrip()
                        if i < len(x2):
                            r=str(x2[i]).lstrip()
                        i_l.append(l)
                        i_r.append(r)
            else:
                # nepovolený typ
                raise ValueError(TXT_INVALID_TYPE_IN_LIS+f": {item}")                    
            
            # zpracujeme přídavky
            
            # prefix
            i_l = [ f'{linePrefix}{i}' for i in i_l]
            # závorky                    
            i_r = [ f"{brL}{i}{brR}" if i else '' for i in i_r]
                    
            if onlyOneColumn:
                i_r = [''] * len(i_l)

            if len(i_l) != len(i_r):
                raise ValueError(TXT_CMENU_ERR01)
            
            # přidáme
            ret.extend((l, r) for l, r in zip(i_l, i_r))

        # vypočítáme maximální délku levého a pravého sloupce
        w = 0
        addBetween = False
        for i in ret:
            if not isinstance(i, tuple):
                raise ValueError(TXT_CMENU_ERR02)
            
            if len(i[0]) > 1 and len(i[1]) > 0:
                addBetween = True

            w = max(w , 
                (
                    spaceBetweenTexts if addBetween else 0
                )
                + len(i[0])
                + len(i[1])
            )
                
        width = max(minWidth, w)

        # vytvoříme list z width
        ret2 = []
        for i in ret:            
            sp_btw = width - len(i[0])
            if len(i[0]) > 0 and len(i[1]) > 0:
                sp_btw = sp_btw - len(i[1])
                        
            if sp_btw < 0:
                raise ValueError(TXT_CMENU_ERR03.format(tx=sp_btw))
            
            # generování řádku se str nebo tuple, výstup bude jen List[str] s konstantní šířkou
            if i[0] and i[1]:
                ret2.append(f"{i[0]}{' ' * sp_btw}{i[1]}")
            elif i[0] and not i[1]:
                # pokud se jedná o jednoznakový znak z `_lineCharList` tak se zopakuje v délce width
                if len(i[0])==1 and i[0][0] in _lineCharList:
                    ret2.append(i[0] * width)
                else: # jinak se dorovná mezerami
                    ret2.append(i[0].ljust(width))
            else:
                ret2.append(i[1].rjust(width))
                                
        return ret2, width

    @staticmethod
    def printBlok(
        title_items: Union[List[str], List[Tuple[str, str]], List[List[str]]],
        subTitle_items: List[str],
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
            title_items (Union[List[str], List[Tuple[str, str], List[List[str]]]): Položky k vytisknutí, pokud je:
                - `str`, tak se vytiskne zleva doprava
                - `tuple`, tak se vytiskne index 0 zleva doprava a index 1 zprava doleva
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
        out=[]
        ## Předzpracování položek
        # Převod všech položek na konzistentní formát a odstranění CR/LF
        if charObal:
            charObal = str(charObal)
            obal = True
        else:
            charObal = ""
            obal = False

        width=min_width-2 # 2 = mezera zleva a zprava
        processed_subTitle_items = c_menu.processList(
            subTitle_items,
            onlyOneColumn=True,
            linePrefix=charSubtitle+" ",
            minWidth=width,
            rightTxBrackets=rightTxBrackets
        )
        width = max(width, processed_subTitle_items[1])

        processed_title_items = c_menu.processList(
            title_items,
            onlyOneColumn=False,
            spaceBetweenTexts=space_between_texts,
            minWidth=width,
            rightTxBrackets=rightTxBrackets
        )
        width = max(width, processed_title_items[1])
        processed_title_items = processed_title_items[0]

        # ještě jendou zpracujeme subTitle_items, protože se může změnit šířka
        processed_subTitle_items = c_menu.processList(
            subTitle_items,
            onlyOneColumn=True,
            linePrefix=charSubtitle+" ",
            minWidth=width,
            rightTxBrackets=rightTxBrackets
        )
        width = max(width, processed_subTitle_items[1])
        processed_subTitle_items = processed_subTitle_items[0]


        menu = processed_title_items + processed_subTitle_items      
        
        if charObal=="|":
            spacer = "-" * (width+2) # 2 = mezera zleva a zprava
        else:
            spacer = charObal * (width+2)  # 2 = mezera zleva a zprava
        
        h_Obal = charObal * leftRightLength

        if obal:
            spacer = f"{h_Obal}{spacer}{h_Obal}"
        
        if obal:
            out.append(spacer)
        
        # Vytiskneme menu
        for item in menu:
            if obal:
                out.append(f"{h_Obal} {item} {h_Obal}")
            else:
                out.append(item)
                
        # Vytiskneme spodní ohraničení, pokud je požadováno
        if obal:            
            out.append(spacer)
        
        # Přidáme prázdný řádek, pokud je eof nastaveno na True
        if eof:
            out.append("")
        
        if isinstance(outToList,list):
            outToList.extend(out)
        else:
            print("\n".join(out))
        
        width = max(width, len(spacer))
        return width

    def __print(self, lastRet: onSelReturn = None, toOut:list=None) -> int:
        width=0
        
        afterTitle=self.afterTitle
        if not isinstance(afterTitle,str):
            afterTitle=""        
        afterTitle=afterTitle.splitlines()
        
        afterMenu=self.afterMenu
        if not isinstance(afterMenu,str):
            afterMenu=""
        afterMenu=afterMenu.splitlines()
        
        out=[]
        # dva průchody, výpočetní a zobrazení
        for step in range(2):        
            out=[]

            menu_list = self.__getList()
            x=self.checkItemChoice(menu_list)
            if x:
                raise ValueError(TXT_RPT_CHCS+": "+', '.join(x))

            if not self.title:
                tt=[]
            else:
                tt = self.title.splitlines()
            if not self.subTitle:
                st=[]
            else:
                st = self.subTitle.splitlines()
            width = max(width, self.printBlok(tt, st, "|", 3, "-", False, min_width=width, outToList=out) )

            if self.afterTitle:
                width = max(width, self.printBlok(afterTitle, [], "", 0, "", False, min_width=width, outToList=out))

            # vytvoříme volby
            # zjistí max délku choice
            max_l_LenChoices=0
            lst=self.__getList()
            for item in lst:
                if not item.hidden and item.choice:
                    if item.enabled:
                        max_l_LenChoices=max(max_l_LenChoices,len(item.choice))
                    else:
                        max_l_LenChoices=max(max_l_LenChoices,len(TXT_DISABLED))
            # vytvoříme menu
            ch=[]
            for item in lst:
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
                        lbl = lbl * (width-2) # -2 mezery uvnitř obalu
                        
                    sel="  "
                    if self._selectedItem==item:
                        sel=chr(0x25B6)+" " # černá šipka doprava
                    
                    ch.append( [f"{sel}{chcs}{lbl}",item.atRight] )
            
            width = max(width,self.printBlok(ch, [], "-", 0, "", True,min_width=width, outToList=out))
                        
            if self.afterMenu:
                width = max(width, self.printBlok(afterMenu, [], "", 0, "", False, min_width=width, outToList=out))
                
            if lastRet:
                if lastRet.err:
                    width = max(width, self.printBlok([TXT_ERR, lastRet.err], [], "!", 3, "", False,min_width=width , outToList=out))
                if lastRet.ok:
                    width = max(width, self.printBlok([TXT_NFO, lastRet.ok], [], "-", 3, "", False,min_width=width), outToList=out)
        
        # inverze přes escape pokud >
        for i in range(len(out)):
            if out[i].startswith(" "+chr(0x25B6)):
                out[i]=text_inverse(out[i])
             
        if isinstance(toOut,list):
            toOut.extend(out)
        else:
            cls()                    
            print("\n".join(out))

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
            if item.enabled and not item.hidden and item.choice:
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
            if x.enabled and not x.hidden and x.choice:
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
            if not i.hidden and i.enabled and i.choice:
                if i.choice in ch:
                    err.append(TXT_RPT_CHCS+': '+i.choice)
                ch.append(i.choice)
        return err if len(err)>0 else None
        
    def run_refresh(self,c:str,first:bool=False) -> Union[bool,str]:
        """pokud vrátí string tak se menu ukončí s chybou a vrátí tento string jako chybu"""
        err=[]
        if first:
            if self.onEnterMenu:
                try:
                    log.debug(f"onEnterMenu")
                    x=self.onEnterMenu()
                    if isinstance(x,str):
                        return x
                except Exception as e:
                    self.lastReturn = onSelReturn(err=str(e))
                    log.error(f"Exception on onEnterMenu",exc_info=True)
                    err.append(str(e))
                                    
        if self.onShowMenu:
            try:
                log.debug(f"onShowMenu")
                self.onShowMenu()
            except Exception as e:
                self.lastReturn = onSelReturn(err=str(e))
                log.error(f"Exception on onShowMenu",exc_info=True)
                err.append(str(e))
        
        if self._selectedItem is None:
            self.nextItem()
        self._rowLength = self.__print(self.lastReturn)
        if self.onShownMenu:
            try:
                log.debug(f"onShownMenu")
                self.onShownMenu()
            except Exception as e:
                self.lastReturn = onSelReturn(err=str(e))
                log.error(f" Exception on onShownMenu",exc_info=True)
                err.append(str(e))
        
        if not c:
            print(TXT_PRESS_KEY)
        if len(c) > 0:
            ci=text_inverse(f" {c} ")
            print(TXT_SEL_INFO.format(c=ci))
        else:
            print(TXT_SELECT.format(c=c))
            
        if len(err)>0:
            print("\n".join(err))
            return False
            
        return True

    def run(self,item:c_menu_item=None) -> Union[None,str]:
        """ Spustí menu 
        pokud se spouští z parent menu tak 'item' obsahuje položku menu, která byla vybrána
        
        pokud je to volání menu<>menu a vrátí string, tak se string přenese jako chyba do parent menu a zobrazí
        """
        self._runSelItem=item
        self._mData=None
        if self._runSelItem:
            if hasattr(self._runSelItem,'data'):
                self._mData=self._runSelItem.data
        
        first = True
        log.info(f" >>> RUN Menu '{self.__class__.__name__}' started ---")
        c=""
        
        self.selectedItem = None
        while True: 
            x=self.run_refresh(c,first)
            if isinstance(x,str):                
                return x
            first = False

            xc=getKey(ESC_isExit=True)
            
            # pokud je klávesa string tak vezmeme první znak do xk pro jednoznakové testy
            xk=''
            if isinstance(xc,str) and xc:
                xk=xc[0]
                            
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
                        return e
                    if not x is False:
                        # návrat bez chyby a zákazu
                        return                
                continue # Nebyla detekována akce ESC nebo byl detekován zákaz (False) - čekej na další klávesu
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
                    log.debug(f"Sub menu '{item.label}' started ---")
                    e=item.onSelect.run(item)
                    # zpracuj návratovou hodnotu ze submenu
                    if isinstance(e,str):
                        self.lastReturn = onSelReturn(err=e)
                    else:
                        self.lastReturn = onSelReturn()
                else:
                    # volej funkci onSelect
                    log.debug(f"onSelect '{item.label}'")
                    self.lastReturn = item.onSelect(item)
                    # zpracuj návratovou hodnotu z funkce onSelect
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
                # self._selectedItem = None
                pass
                
            self.selectedItem = None                    
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
            sleep(0.4)
                
    def callExitMenu(self,itm: 'c_menu')->Union[bool,str,None]:
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
        log.info(f" <<< Menu '{self.title}' ended ---")
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
    
    title_items: Union[List[str], List[Tuple[str, str]], List[List[str]]],
    subTitle_items: List[str],
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
        title_items (Union[List[str], List[Tuple[str, str], List[List[str]]]): Položky k vytisknutí, pokud je:
            - `str`, tak se vytiskne zleva doprava
            - `tuple`, tak se vytiskne index 0 zleva doprava a index 1 zprava doleva
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

