from .lng.default import * 
from .helper import loadLng
from .term import restoreAndClearDown,savePos,getKey,cls
loadLng()

import re, bcrypt, getpass
from .c_menu import printBlock
from typing import Union,Callable

confirm_choices: list[tuple[str, str]] = [
    ['y', TXT_INPUT_YES],
    ['n', TXT_INPUT_NO],
]

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
    ) -> str:
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
        
def anyKey(RETURN_KeyOny:bool=False, cls:bool=False,minMessageWidth:int=0) -> None:
    """ Čeká na stisk klávesy nebo RETURN v závislosti na volbě, nevyužívá input
    - returnKeyOny: bool - pokud je True, tak se čeká na stisk klávesy RETURN, jinak na jakoukoliv klávesu
    - cls: bool - pokud je True, tak se před čekáním smaže obrazovka
    """
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
    """ Čeká na potvrzení pomocí klávesy Y nebo N"""
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
