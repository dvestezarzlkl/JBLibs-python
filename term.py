import os
import sys
import termios
import time
from typing import Union

_old_settings = None

def savePos() -> None:
    """Uloží aktuální pozici kurzoru na obrazovce
    
    Returns:
        None
    """
    sys.stdout.write("\033[s") # ANSI sekvence pro uložení pozice kurzoru
    sys.stdout.flush()

def restorePos() -> None:
    """Obnoví pozici kurzoru na obrazovce
    
    Returns:
        None
    """
    sys.stdout.write("\033[u") # ANSI sekvence pro obnovení pozice kurzoru
    sys.stdout.flush()

def clearScreen() -> None:
    """Vymaže obsah obrazovky ale nechá kurzor kde byl
    
    Returns:
        None
    """
    sys.stdout.write("\033[2J") # ANSI sekvence pro vymazání obrazovky
    sys.stdout.flush()

def restoreAndClearDown(returnRestoredPos:bool=False) -> None:
    """Obnoví pozici kurzoru a vymaže obsah obrazovky od pozice kurzoru dolů
    
    Parameters:
        returnRestoredPos (bool, optional): (False) pokud True obnoví pozici kurzoru
    
    Returns:
        None
    """
    sys.stdout.write("\033[u")
    sys.stdout.write("\033[J") # ANSI sekvence pro vymazání od kurzoru dolů
    if returnRestoredPos:
        sys.stdout.write("\033[u") # ANSI sekvence pro obnovení pozice kurzoru
    sys.stdout.flush()

def clearRow(row:int=0, restore:bool=True) -> None:
    """Vymaže řádek na obrazovce

    Parameters:
        row (int, optional): (0) číslo řádku
        restore (bool, optional): (True) obnoví pozici kurzoru
    
    Returns:
        None
    """
    if restore:
        restorePos()
    for _ in range(row):
        sys.stdout.write("\033[2K")  # Vymaže celý řádek
        sys.stdout.write("\033[B")   # Posune kurzor o jeden řádek dolů
    restorePos()

def set_nonBlocking_terminal_input(override:bool=False, exception:bool=False)->None:
    """ Inicializuje neblokující vstup z klávesnice a uloží si původní nastavení terminálu,
    které je možné obnovit pomocí metody reset_terminal()
    
    Parameters:
        override (bool, optional): (False) pokud True, přepíše původní nastavení terminálu
        exception (bool, optional): (False) pokud True, vyvolá výjimku pokud je terminál již inicializován
    """
    global _old_settings
    if not override:
        if _old_settings:
            if exception:
                raise Exception("Terminal is already initialized")
            return
    _old_settings = termios.tcgetattr(sys.stdin)
    new_settings = termios.tcgetattr(sys.stdin)
    new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
    new_settings[6][termios.VMIN] = 0
    new_settings[6][termios.VTIME] = 0
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)

def reset_and_restore_terminal()->None:
    """Obnoví původní nastavení terminálu
    
    Returns:
        None
    """
    global _old_settings
    try:
        if _old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_settings)
    except Exception as e:
        pass
    finally:
        _old_settings = None

def getK(timeout: float = None) -> Union[str, None]:
    """Čte znak z klávesnice, pokud je k dispozici, jinak vrací None

    Parameters:
        timeout (float, optional): (None) timeout pro čtení klávesnice, pokud je None, čte se nekonečně

    Returns:
        Union[str, False, None]:
            - str: přečtený znak
            - False: pokud timeout
            - None: pokud chyba
    """
    r = None
    start_time = time.time()
    while not r:
        if timeout and (time.time() - start_time) > timeout:
            r = False
            break
        if not r is False:
            r = os.read(sys.stdin.fileno(), 1)
    
    if isinstance(r, bytes):
        return r.decode('utf-8')
    return r

def getKey(
    forKeys: str = '',
    q_isExit: bool = False,
    ENTER_isExit: bool = False,
    ESC_isExit: bool = False
) -> str | bool:
    """
    Čeká na stisk klávesy a tu vrací do volající funkce, podporuje esc sekvence šipek
    
    ESC sekvence šipek    
        - `\\x1b[A` - Šipka nahoru
        - `\\x1b[B` - Šipka dolů
        - `\\x1b[C` - Šipka doprava
        - `\\x1b[D` - Šipka doleva
    
    Parameters:    
        forKeys (str, optional): ('') jeden znak nebo více znaků,  pokud:
            - je zadáno, tak návrat jen když je stisknutý znak obsažený ve forKeys
            - je prázdný řetězec, tak návrat na jakýkoliv stisk klávesy a tento je vrácen
        q_isExit (bool,optional): (False) pokud je True, tak stisk klávesy 'q' ukončí tuto funkci a vrátí False
        ENTER_isExit (bool,optional): (False) pokud je True, tak stisk klávesy ENTER ukončí tuto funkci a vrátí True
        ESC_isExit (bool): (False) pokud je True, tak stisk klávesy ESC ukončí tuto funkci a vrátí False

    Returns:
        Union[str,bool,None]
            1. když str  
                - znak klávesy  
                - Escape sekvence šipek
            2. když bool
                - True když zaplý ENTER a je stisklý
                - False když je zaplý ESC a je stisklý
            3. None při chybě - např break

    """
    forKeys = str(forKeys).lower()
    w = 0.1
    
    set_nonBlocking_terminal_input()
    ch = None
    try:
        while True:
            ch = getK()
            if ch is None:
                continue
            # Detect escape sequences for arrow keys
            if ch == '\x1b':  # ESC character
                ch_x = getK(w)
                if ch_x:
                    ch += ch_x
                    ch_x = getK(w)
                    if ch_x:
                        ch += ch_x
                        break
                else:
                    if ESC_isExit:
                        ch = False
                        break
                    else:
                        continue

            k = ch
            ch = ch.strip().lower()

            # Kontrola pro ukončovací klávesy pomocí match-case
            match ch:
                case 'q' if q_isExit:
                    ch = False
                    break
                case '\n' | '\r' if ENTER_isExit:
                    ch = True
                    break

            # Kontrola pro ostatní klávesy
            if forKeys:
                if ch in forKeys:
                    break
            else:
                ch = k
                break
    finally:
        reset_and_restore_terminal()
    if isinstance(ch, bytes):
        return ch.decode('utf-8')
    return ch

def reset()->None:
    """ Provede reset terminálu, pokud je to možné
    
    Returns:
        None
    """
    try:
        fd = sys.stdin.fileno()
        if fd is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, termios.tcgetattr(fd))
            except termios.error:
                pass  # Může nastat, pokud terminál není v nestandardním režimu
    except Exception as e:
        pass
    try:
        os.system('stty sane')  # Tento příkaz funguje pouze na systémech UNIX
    except Exception as e:
        pass

def text_inverse(text:str)->str:
    """ Vrátí text s inverzním zobrazením
    
    Parameters:
        text (str): text pro inverzní zobrazení
        
    Returns:
        str: text s inverzním zobrazením
    """
    return f"\033[7m{text}\033[0m"

def cls()->None:
    """ Vymaže obsah obrazovky resetuje kurzor na začátek obrazovky
    
    Returns:
        None
    """
    print("\033[2J\033[H", end="")
    sys.stdout.flush()
    # \033[2J - Vymaže obrazovku
    # \033[H - Posune kurzor na začátek obrazovky
