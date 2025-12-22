from __future__ import annotations

import bcrypt,os
from .lng.default import * 
from .helper import loadLng
from .term import restoreAndClearDown,savePos,getKey,cls,reset,text_color,en_color
loadLng()

import re, getpass
from .c_menu import printBlock,onSelReturn
from typing import Union,Callable,Optional
from .format import cliSize
from pathlib import Path
from .fs_helper import fs_menu,e_fs_menu_select,c_fs_itm

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .c_menu import c_menu_block_items
    
confirm_choices: list[tuple[str, str]] = [
    ['y', TXT_INPUT_YES],
    ['n', TXT_INPUT_NO],
]

_minMessageWidth:int=0

def validate_port(port: Union[int,str], full:bool=False) -> bool:
    """
    Kontroluje zda je port v rozsahu 10000 až 65000 nebo 1 až 65535 podle parametru full
    
    Pokud na Linuxu není user root tak je povolený rozsah 1024 až 65535, jinak 1 až 65535
    
    Parameters:
        port (Union[int,str]): číslo portu
        full (bool): pokud je True, tak je rozsah 1 až 65535, jinak 1024 až 65535
        
    Returns:
        bool: True pokud je port v rozsahu, jinak False
    """
    try:
        if isinstance(port, str):
            port=port.strip()
            if port == '':
                return False
        port = int(port)
    except ValueError:
        return False    
    if full:
        return 1 <= port <= 65535
    else:
        return 1024 <= port <= 65535

def get_username(messagePrefix:None, make_cls: bool=False, maxLength:int=50, minMessageWidth:int=0) -> str:
    """
    Čeká na zadání uživatelského jména, validuje ho a vrací
    povolené znaky jsou alfanumerické znaky a-Z , podtržítko a pomlčka
    
    Parameters:
        assMessagestr (None): text který se zobrazí uživateli jako další řádek pod výzvou, pokud je zadáno
        make_cls (bool): pokud je True, tak se před zadáním smaže obrazovka
        maxLength (int): maximální délka jména
        minMessageWidth (int): minimální šířka zprávy
        
    Returns:
        str: uživatelské jméno
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    if not isinstance(maxLength, int):
        maxLength=50
    return get_input(
        TXT_INPUT_USERNAME+(f"\n  {messagePrefix}" if messagePrefix else ""),
        False,
        re.compile(r'^[\w_-]+$'),
        maxLength,
        make_cls,
        TXT_SSMD_ERR17,
        minMessageWidth=minMessageWidth
    )

def get_input(
        action: str,
        accept_empty: bool = False,
        rgx:Union[re.Pattern,Callable]=None, # např re.compile(r'\d+')
        maxLen=0,
        clearScreen:bool=False,
        errTx:str=TXT_SSMD_ERR18,
        titleNote:str="",
        minMessageWidth:int=0
    ) -> str|None:
    """
    Obecná funkce pro získání vstupu od uživatele, validuje vstup
    
    Parameters:
        action (str): text který se zobrazí uživateli
        accept_empty (bool) (False): pokud je True, tak je povolen prázdný vstup
        rgx (Union[re.Pattern,Callable]) (None): regulární výraz nebo funkce pro validaci vstupu,
            funkce má syntaxi: `def funkce(vstup:str)->bool`        
        maxLen (int) (0): maximální délka vstupu
        clearScreen (bool) (False): pokud je True, tak se před zadáním smaže obrazovka
        errTx (str) ("default text"): text chybové hlášky
        titleNote (str) (""): text poznámky
        minMessageWidth (int) (0): minimální šířka zprávy
    
    Returns:
        Union(str,None): vstup od uživatele
            - str: pokud je zadán vstup a je validní
            - None: pokud je zadáno 'q'
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    err:str=""
    i=[action]
    s=[f"q = {TXT_END}"]
    if titleNote != "":
        s.append(titleNote)
    if clearScreen:
        cls()
        
    print("\033[s", end="") # uložení pozice kurzoru
    try:
        while True:
            print("\033[u", end="")  # ANSI sekvence pro obnovení pozice kurzoru
            print("\033[J", end="")  # Vymaže od kurzoru dolů
            
            printBlock(i, s, eof=True,min_width=minMessageWidth)
            if err:
                print(err)
                print("")
                err=""

            inputText = input(f">>> {TXT_INPUT_A}: ")
            inputText = inputText.strip()
            err=""
            if inputText.lower() == 'q':
                return None
            if accept_empty and inputText == "":
                return ""
            if len(inputText) > 0 and (
                rgx is None or 
                (isinstance(rgx, re.Pattern) and re.match(rgx, inputText)) or 
                (callable(rgx) and rgx(inputText) is True)
            ) and (
                maxLen == 0 or len(inputText) <= maxLen
            ):
                return inputText
            else:
                if isinstance(rgx,re.Pattern) and not re.match(rgx, inputText):
                    err = errTx
                elif callable(rgx) and rgx(inputText) is False:
                    err = errTx
                elif maxLen > 0 and len(inputText) > maxLen:
                    err = TXT_LEN_ERR.format(maxLen=maxLen)
                else:
                    err = TXT_INPUT_ERR
                print(err)
    finally:
        restoreAndClearDown()

# Helper function to get password
def get_pwd(action: str = "",make_cls:bool=False, minMessageWidth:int=0) -> str:
    """
    Ask for a password, validate it, and return the valid password.
    
    Parameters:
        action (str) (""): text which will be displayed to the user
        make_cls (bool) (False): if True, the screen will be cleared before input
        minMessageWidth (int) (0): minimum message width
        
    Returns:
        str: password
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    err=""
    savePos()
    if make_cls:
        cls()
    if not isinstance(action, str):
        action=""
    if action:
        action = f": {action}"
    i=[f"{TXT_INPUT_PWD}{action}"]
    s=[f"q = {TXT_END}"]
    
    print("\033[s", end="") # uložení pozice kurzoru
    try:
        while True:
            restoreAndClearDown()
            
            printBlock(i, s, eof=True, min_width=minMessageWidth)
            if err:
                print(err)
                print("")
                err=""

            pwd = getpass.getpass(f">>> {TXT_INPUT_A}: ")
            if pwd.lower() == 'q':
                return None
            if re.match(r'^[\w\d!@#$%^&*()-_=+]+$', pwd) and len(pwd) >= 8:
                return pwd
            else:
                err=TXT_SSMD_ERR19
    finally:
        restoreAndClearDown()

def get_pwd_confirm(make_cls:bool=False, minMessageWidth:int=0) -> str:
    """Požadavek na zadání hesla s validací hesla a jeho potvrzení

    Parameters:
        make_cls (bool, optional): _description_. Defaults to False.
        minMessageWidth (int, optional): _description_. Defaults to 0.

    Returns:
        str: _description_
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    while True:
        password = get_pwd(TXT_INPUT_NEW_PWD,make_cls, minMessageWidth)
        if password == None:
            return None
        confirm_password = get_pwd(TXT_INPUT_PWD_AGAIN,make_cls, minMessageWidth)
        if confirm_password == None:
            return None
        if password == confirm_password:
            break
        else:
            print(TXT_SSMD_ERR20)
    return password

def get_port(make_cls:bool=False, minMessageWidth:int=0) -> int:
    """Čeká na zadání portu, validuje ho a vrací
    
    Parameters:
        make_cls (bool): pokud je True, tak se před zadáním smaže obrazovka
        minMessageWidth (int): minimální šířka zprávy
        
    Returns:
        int: číslo portu        
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    return get_input(
        TXT_INPUT_PORT,
        False,
        validate_port,
        0,
        make_cls,
        TXT_SSMD_ERR21,
        TXT_SSMD_PORT_REANGE,
        minMessageWidth
    )

# využívá bcrypt
def hash_password(password: str) -> str:
    # Vygenerování salt
    salt = bcrypt.gensalt()

    # Hash-ování hesla, heslo musí být bytes
    password = password.encode('utf-8')
    hashed = bcrypt.hashpw( password , salt)
    
    return hashed.decode('utf-8')
     
def setMinMessageWidth(width:int) -> None:
    """Nastaví minimální šířku zprávy pro vstupní funkce"""
    if not isinstance(width, int):
        raise ValueError("Parameter width must be integer")
    global _minMessageWidth
    _minMessageWidth=width

def getMinMessageWidth() -> int:
    """Vrátí minimální šířku zprávy pro vstupní funkce"""
    return _minMessageWidth
        
def anyKey(RETURN_KeyOny:bool=False, cls:bool=False,minMessageWidth:int=0) -> None:
    """ Čeká na stisk klávesy nebo RETURN v závislosti na volbě, nevyužívá input
    - returnKeyOny: bool - pokud je True, tak se čeká na stisk klávesy RETURN, jinak na jakoukoliv klávesu
    - cls: bool - pokud je True, tak se před čekáním smaže obrazovka
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth
    
    if cls:
        cls()
    if RETURN_KeyOny:
        printBlock([TXT_INPUT_RETURNKEY], [], "*", 3, "", False,min_width=minMessageWidth)
    else:
        printBlock([TXT_INPUT_ANYKEY], [], "*", 3, "", False,min_width=minMessageWidth)
    
    while True:
        c=getKey(ENTER_isExit=True)
        if RETURN_KeyOny:
            if c is True:
                break
        else:
            if c is not None:
                break     
        
def confirm(msg: str, make_cls:bool=False,minMessageWidth:int=0) -> bool:
    """ Čeká na potvrzení pomocí klávesy Y nebo N
    
    Parameters:
        msg (str): zpráva která se zobrazí uživateli
        make_cls (bool): pokud je True, tak se před zobrazením smaže obrazovka
        minMessageWidth (int): minimální šířka zprávy
    Returns:
        bool: True pokud bylo potvrzeno, jinak False
    
    """
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    if make_cls:
        cls()
    i=[
        msg,
        ' - '+confirm_choices[0][0].upper()+' = '+confirm_choices[0][1],
        ' - '+confirm_choices[1][0].upper()+' = '+confirm_choices[1][1]
    ]
    printBlock(i, [], "-", 3, "", False,min_width=minMessageWidth)
    
    ch = getKey(forKeys=confirm_choices[0][0]+confirm_choices[1][0])
    ch=ch.strip().lower()
    if ch == confirm_choices[0][0].lower():
        return True
    return False

class select_item:
    """Položka pro výběr z více možností pro funkci select
    """
    
    label: str = ""
    """Zobrazený popisek položky"""
    
    choice: str = ""
    """sekvence k vybrání, max 8 znaků  
    pokud nezadáme, tzn necháme "", tak se k položce vygeneruje číselné choice
    """
    
    data: any = None
    """Data která jsou spojená s položkou, ať už je to str, int, dict, list, tuple
    nebo jiný objekt
    
    """
    
    def __init__(self, label:str, choice:str="", data:any=None):
        self.label=label
        self.choice=choice
        self.data=data

class selectReturn:
    """Výsledek funkce select"""
    
    item: Union[select_item,None] = None
    """Vybraná položka"""
    
    calcWidth: int = 0
    """Vypočítaná šířka menu - zprávy, pokud je přesaženo minWidth
    """
    
    def __init__(self, item: Union[select_item,None], calcWidth:int):
        self.item=item
        self.calcWidth=calcWidth

def select(
    msg: Union[str|None],
    items: list[select_item],
    minMessageWidth:int=0,
    title:Union[str,c_menu_block_items]=TXT_SELECT_TITLE,
    subTitle:Union[str,"c_menu_block_items"]="",
) ->selectReturn:
    """Zobrazí seznam položek a čeká na výběr jedné z nich  
    POZOR, protože využívá menu, tak maže obrazovku
    
    Parameters:
        msg (str|None): zpráva která se zobrazí nad seznamem položek  
            pokud je None, tak se nezobrazí žádná zpráva
        items (list[select_item]): seznam položek, striktně se očekává že každá položka bude:  
            - class select_item
            - None - pro oddělovač
            - class c_menu_title_label - vytváří se centrovaný text bez výběru
        make_cls (bool): pokud je True, tak se před zobrazením smaže obrazovka
        minMessageWidth (int): minimální šířka zprávy
        title (Union[str,"c_menu_block_items"]): titulek menu, může být i c_menu_block_items pro víceřádkový titulek
        subTitle (Union[str,"c_menu_block_items"]): podtitulek menu, může být i c_menu_block_items pro víceřádkový podtitulek
                
    Returns:
        Union[select_item,None]: vybraná položka nebo None pokud uživatel zrušil výběr
        
    Raises:
        ValueError: pokud je některá položka v seznamu jiného typu než select_item
        
    Example:
        ```python
        x=select("Testovací select",[
            select_item("První",data="první výběr"),
            select_item("Druhý","dru",data="druhý výběr"),
        ],80)
        print(x.item.data if x.item else "ESC, nebylo nic vybráno")
        
        # nebo
        x.item.choice obsahuje vybranou klávesovou sekvenci
        x.item.data je None nebo data spojená s položkou, ale musí být zadána při vytváření položky tzn
            select_item("Druhý","dru",data="druhý výběr"),
            select_item("Druhý","dru",data=15),
            select_item("Druhý","dru",data={"klic":"hodnota"}), atd.
        ```
    """
    from .c_menu import c_menu,c_menu_item,onSelReturn,c_menu_block_items,c_menu_title_label
    reset()
    if not isinstance(items, list):
        raise ValueError("Parameter items must be list of select_item")
    if len(items) == 0:
        raise ValueError("Parameter items must contain at least one select_item")
    # for i in range(len(items)):
    #     if not items[i] is None and not isinstance(items[i], (select_item,c_menu_title_label)):
    #         raise ValueError(f"Item at index {i} is not instance of select_item")
    
    if not isinstance(title, (str, c_menu_block_items)):
        raise ValueError("Parameter title must be str or list[c_menu_block_items]")
    
    if isinstance(subTitle, str) and subTitle:
        subTitle= c_menu_block_items([subTitle])
    elif not subTitle:
        subTitle=c_menu_block_items()
    if not isinstance(subTitle, c_menu_block_items):
        raise ValueError("Parameter subTitle must be str or list[c_menu_block_items]")
    
    if not isinstance(msg, str) and msg:
        raise ValueError("Parameter msg must be str")
    subTitle.append(msg)
    
    if not minMessageWidth:
        minMessageWidth=_minMessageWidth    
    
    cnt=0
    menuItems = []
    for i in range(len(items)):
        if isinstance(items[i], select_item):
            if not isinstance(items[i].choice, str):
                items[i].choice = ""
            else:            
                items[i].choice = items[i].choice.strip()
            # max 8 znaků
            if len(items[i].choice) > 8:
                items[i].choice = items[i].choice[:8]
                
            if not items[i].choice:
                items[i].choice = str(cnt+1)
                cnt+=1
            if not isinstance(items[i].label, str):
                raise ValueError(f"Item at index {i} has not label")
            menuItems.append( c_menu_item(
                items[i].label,
                items[i].choice,
                lambda f: onSelReturn(endMenu=True),
                data=items[i].data
            ))
        elif items[i] is None:
            menuItems.append( None )
        elif isinstance(items[i], c_menu_title_label):
            menuItems.append( items[i] )
        else:
            raise ValueError(f"Item at index {i} is not instance of select_item")
        
    m=c_menu(menuItems,minMessageWidth,True,False,title,subTitle)
    m.run()
    reset()
    return selectReturn(m.getLastSelItem(),m.getCalcWidth())

def inputCliSize(
    minSize:Union[int|str]=1,
    maxSize:Optional[Union[int|str]]=None,
    inMiB:bool=False,
    clearScreen:bool=False,
    minMessageWidth:int=0
)-> Union[cliSize,None]:
    """Interaktivní zadání velikosti pro CLI příkazy tzn jako '512M', '1G', atd.  
    **POZOR vždy zpracovává base 1024, tzn. i když zadáváme '1MB' tak to bere jako 1 MiB (1024*1024 bytes)**  
    JEdná se o CLI nástroj a tak je to historicky takto nastaveno že 1MB = 1MiB = 1024*1024 bytes  
    tak jak se to historicky v CLI používal a používá. Protože aktuálně se v literatuře a na webu používá  
    MiB pro base 1024 a MB pro base 1000, ale v CLI nástrojích se to takto nepoužívá.
    
    Args:
        minSize (int|str): Minimální velikost v bytech
        maxSize (Optional[int|str]): Maximální velikost v bytech, pokud je None, tak není omezená
        inMiB (bool): platí jen pokud je vstup minSize nebo maxSize int  
            - pokud je True, tak se bere int jako MiB (base 1024)
            - pokud je False, tak se bere int jako byty
        clearScreen (bool): Pokud je True, smaže obrazovku před zadáním.
        minMessageWidth (int): Minimální šířka zprávy.
    Returns:
        cliSize: Objekt cliSize reprezentující zadanou velikost.
        None pokud uživatel zruší zadání.
    """
    if not isinstance(minSize, (int, str)):
        raise ValueError(TXT_INP_CLI_ERR_01)
    if maxSize is not None and not isinstance(maxSize, (int, str)):
        raise ValueError(TXT_INP_CLI_ERR_02)
    
    minSize= cliSize(minSize, inMiB).inBytes
    maxSize=None if maxSize is None else cliSize(maxSize,inMiB).inBytes
    
    minSize = max(0, minSize)
    maxSize = maxSize if isinstance(maxSize, int) and maxSize >= minSize else None
    
    prompt =  f"{TXT_INP_CLI_SIZE_001}"
    prompt += f"\n{TXT_INP_CLI_SIZE_MIN}: {cliSize(minSize)}"
    if maxSize is not None:
        prompt += f"  |  {TXT_INP_CLI_SIZE_MAX}: {cliSize(maxSize)}"
            
    while True:        
        x=get_input(
            prompt,
            False,
            re.compile(r"^(\d+)([MKGTP]?)$"),
            0,
            clearScreen,
            TXT_INP_CLI_ERR,
            minMessageWidth=minMessageWidth
        )
        if x is None:
            return None, None
        n=cliSize(x)
        v=n.inBytes
        if v < minSize :
            print( text_color( TXT_INP_CLI_ERR_MIN.format(minSize=cliSize(minSize),size=n) , color=en_color.RED) )
            anyKey()
            continue
        if maxSize is not None and v > maxSize:
            print( text_color( TXT_INP_CLI_ERR_MAX.format(maxSize=cliSize(maxSize),size=n) , color=en_color.RED) )
            anyKey()
            continue
        
        return cliSize(x)

def selectDir(
        dir:str|None,
        message:str|list|c_menu_block_items|None=None,
        hidden:bool=False,
        lockToDir: None|str|Path = None,
        minMenuWidth:int|None=None,
        filterList:Optional[Union[str, re.Pattern,]]=None,
        onShowMenuItem:Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]]=None,
        onSelectItem:Optional[Callable[[Path],Union[onSelReturn|None|bool]]]=None,        
    )->Path|None:
    """Zobrazí dialog pro výběr adresáře.
    
    Args:
        dir (str|None): počáteční adresář, pokud None, použije se aktuální adresář.
        hidden (bool): pokud je True, zobrazí i skryté soubory a adresáře.
        lockToDir (None|str|Path): Pokud je zadáno, bude uživatel uzamčen do tohoto adresáře a tím se z něj stane root
            - cesta je ale vždy vrácena jako absolutní až do fyzickkého rootu systému.  
            - Nahrazuje chRoot.
        minMenuWidth (int|None): Minimální šířka menu.
        filterList (Optional[Union[str, re.Pattern]]): Volitelný filtr pro názvy položek.
        message (str|list|c_menu_block_items|None): Volitelná zpráva/y k zobrazení pod titulkem menu.
        onShowMenuItem (Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]]): Volitelná funkce pro úpravu zobrazení položky.
            - Funkce přijímá parametry: `fn(pth:c_fs_itm, lText:str, rText:str) -> tuple[lText:str, rText:str]`
                - pth (c_fs_itm): Položka souborového systému
                - lText (str): Levý text položky
                - rText (str): Pravý text položky
            - Funkce vrací tuple s upraveným levým a pravým textem položky.
        onSelectItem (Optional[Callable[[Path],Union[onSelReturn|None|bool]]]): Volitelná funkce pro zpracování výběru položky.
            - Funkce přijímá parametr: `fn(Path:pth) -> Union[onSelReturn|None|bool]`
                - pth (Path): Cesta vybrané položky
            - Funkce vrací:
                - onSelReturn: endMenu se ignoruje
                    - pokud je objek ve stavu `ok` tak se menu ukončí že je vybraný item ok
                    - pokud je objekt ve stavu `error` tak se zobrazí error s textem v err                    
                    - používáme pokud chceme vrátit zprávu v msg nebo nahlásit error s textem v err
                - None: Pro pokračování v menu bez změny.
                - bool: Pokud
                    - True, menu se ukončí výběrem položky
                    - False, menu pokračuje bez změny.                    
    
    Returns:
        Path|None: vybraný adresář nebo None pokud bylo zrušeno.
    """
    startDir=Path(os.getcwd()).resolve() if dir is None else Path(dir).resolve()
    m=fs_menu(
        startDir,
        e_fs_menu_select.dir,
        hidden,
        lockToDir=lockToDir,
        minMenuWidth=minMenuWidth,
        filterList=filterList,
        message=message,
        onShowMenuItem=onShowMenuItem,
        onSelectItem=onSelectItem
    )
    if er:=m.run() is None:
        s=m.getLastSelItem()
        if not s is None and not s.data is None:
            x:c_fs_itm=s.data
            return Path(x.path).resolve()
        else:
            return None
    else:
        print(f"[ERROR] Chyba při výběru adresáře: {er.err}")
        return None

def selectFile(
        dir:str|None,
        message:str|list|c_menu_block_items|None=None,
        hidden:bool=False,
        lockToDir: None|str|Path = None,
        minMenuWidth:int|None=None,
        filterList:Optional[Union[str, re.Pattern]]=None,
        onShowMenuItem:Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]]=None,
        onSelectItem:Optional[Callable[[Path],Union[onSelReturn|None|bool]]]=None,        
    )->Path|None:
    """Zobrazí dialog pro výběr souboru.
    
    Args:
        dir (str|None): počáteční adresář, pokud None, použije se aktuální adresář.
        hidden (bool): pokud je True, zobrazí i skryté soubory a adresáře.
        lockToDir (None|str|Path): Pokud je zadáno, bude uživatel uzamčen do tohoto adresáře a tím se z něj stane root
            - cesta je ale vždy vrácena jako absolutní až do fyzickkého rootu systému.  
            - Nahrazuje chRoot.
        minMenuWidth (int|None): Minimální šířka menu.
        filterList (Optional[Union[str, re.Pattern]]): Volitelný filtr pro názvy položek.
        onShowMenuItem (Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]]): Volitelná funkce pro úpravu zobrazení položky.
            - Funkce přijímá parametry: `fn(itm:c_fs_itm, lText:str, rText:str) -> tuple[lText:str, rText:str]`
                - itm (c_fs_itm): Položka souborového systému
                - lText (str): Levý text položky
                - rText (str): Pravý text položky
            - Funkce vrací tuple s upraveným levým a pravým textem položky.
        onSelectItem (Optional[Callable[[Path],Union[onSelReturn|None|bool]]]): Volitelná funkce pro zpracování výběru položky.
            - Funkce přijímá parametr: `fn(pth:Path) -> Union[onSelReturn|None|bool]`
                - pth (Path): Cesta vybrané položky
            - Funkce vrací:
                - onSelReturn: endMenu se ignoruje
                    - pokud je objek ve stavu `ok` tak se menu ukončí že je vybraný item ok
                    - pokud je objekt ve stavu `error` tak se zobrazí error s textem v err                    
                    - používáme pokud chceme vrátit zprávu v msg nebo nahlásit error s textem v err
                - None: Pro pokračování v menu bez změny.
                - bool: Pokud
                    - True, menu se ukončí výběrem položky
                    - False, menu pokračuje bez změny.                    

    Returns:
        Path|None: vybraný soubor nebo None pokud bylo zrušeno.
    """
    startDir=Path(os.getcwd()).resolve() if dir is None else Path(dir).resolve()
    m=fs_menu(
        startDir,
        e_fs_menu_select.file,
        hidden,
        lockToDir=lockToDir,
        minMenuWidth=minMenuWidth,
        filterList=filterList,
        message=message,
        onShowMenuItem=onShowMenuItem,
        onSelectItem=onSelectItem
    )
    if er:=m.run() is None:
        s=m.getLastSelItem()
        if not s is None and not s.data is None:
            x:c_fs_itm=s.data
            return Path(x.path).resolve()
        else:
            return None
    else:
        print(f"[ERROR] Chyba při výběru souboru: {er.err}")
        return None