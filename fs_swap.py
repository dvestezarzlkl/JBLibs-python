from pathlib import Path
from dataclasses import dataclass
from .format import bytesTx
from .helper import runGetObj, runRet
from .input import select,select_item,confirm,inputCliSize,cliSize
from .jbjh import JBJH
from .c_menu import onSelReturn
from .term import text_color, en_color
import re


@dataclass
class swap_info:
    file: Path
    type: str
    size: bytesTx
    used: bytesTx
    priority: int
    
def getListOfActiveSwaps(onlyFileType:bool=True) -> list[swap_info]:
    """
    Získá seznam aktivních swap souborů a jejich informace.
    
    Returns:
        list[swap_info]: Seznam informací o aktivních swap souborech.
    """
    swaps = []
    output = runGetObj(["swapon", "--show=NAME,TYPE,SIZE,USED,PRIO", "--raw", "--bytes", "--noheading"])
    if output.returncode != 0:
        return swaps  # Nebyly nalezeny žádné aktivní swapy nebo došlo k chybě
    lines = output.stdout.strip().splitlines()
    for line in lines:
        parts = line.split()
        if len(parts) != 5:
            continue  # Neočekávaný formát řádku
        filename, type_, size, used, priority = parts
        if onlyFileType and type_ != "file":
            continue
        swaps.append(swap_info(
            file=Path(filename),
            type=type_,
            size=bytesTx(int(size)),
            used=bytesTx(int(used)),
            priority=int(priority)
        ))
    return swaps

def swapIsActive(filename: str) -> bool:
    """
    Zjistí, zda je daný swap soubor aktivní.
    
    Args:
        filename: cesta k swap souboru (např. "/swapfile")
    Returns:
        True pokud je swap aktivní, False jinak
    """
    filename = Path(filename).resolve()
    if not filename.exists():
        return False
    activeSwaps = getListOfActiveSwaps()
    flnmTx=str(filename)+""

    for item in activeSwaps:
        if str(item.file) == flnmTx:
            return True
    return False

def modifyFstabSwapEntry(filename: str, add: bool = True) -> None:
    """
    Přidá nebo odstraní záznam o swap souboru v /etc/fstab.
    
    Args:
        filename: cesta k swap souboru (např. "/swapfile")
        add: pokud True, přidá záznam, pokud False, odstraní záznam
    """
    fstab_path = Path("/etc/fstab")
    fstab_lines = fstab_path.read_text(encoding="utf-8").splitlines()
    entry = f"{filename} none swap sw 0 0"

    if add:
        if any(filename in line for line in fstab_lines):
            print(f"[FSTAB] Swap soubor {filename} již existuje v /etc/fstab.")
            return
        print(f"[FSTAB] Přidávám swap soubor {filename} do /etc/fstab.")
        with open(fstab_path, "a", encoding="utf-8") as f:
            f.write("\n" + entry + "\n")
    else:
        new_lines = [line for line in fstab_lines if filename not in line]
        if len(new_lines) == len(fstab_lines):
            print(f"[FSTAB] Swap soubor {filename} nebyl nalezen v /etc/fstab.")
            return
        print(f"[FSTAB] Odstraňuji swap soubor {filename} z /etc/fstab.")
        fstab_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

@dataclass
class curMemInfo:
    mem_total: bytesTx
    mem_available: bytesTx
    swap_total: bytesTx
    swap_free: bytesTx

def getCurMemInfo() -> curMemInfo:
    """
    Získá aktuální informace o paměti a swapu systému.
    
    Returns:
        curMemInfo: Objekt obsahující informace o paměti a swapu.
    """
    o,r,e = runRet("grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo",False)
    mem = dict()
    for line in o.splitlines():
        k , v = line.split(":")
        if not (v:=JBJH.is_str(v)) or not (k:=JBJH.is_str(k)):
            continue
        mem[k.strip()] = bytesTx(v.strip().replace(" ",""))

    return curMemInfo(
        mem_total=mem.get("MemTotal", 0),
        mem_available=mem.get("MemAvailable", 0),
        swap_total=mem.get("SwapTotal", 0),
        swap_free=mem.get("SwapFree", 0)
    )

class swap_mng:
    
    @staticmethod
    def remove_swap_img(swap:Path) -> onSelReturn:
        """Smaže swap soubor

        Args:
            swap (Path): cesta k swap .img souboru, full path

        Returns:
            onSelReturn: _description_
        """
        ret = onSelReturn()
        if not isinstance(swap,Path):
            return ret.errRet("Neplatný parametr swap soubor.")
        if not swap.is_absolute():
            return ret.errRet(f"SWAP .img soubor musí být absolutní cesta: {str(swap)}")
        if not swap.is_file():
            return ret.errRet(f"SWAP .img soubor neexistuje: {str(swap)}")
        
        try:
            # vypnout
            runRet(["sudo", "swapoff", str(swap)], noOut=True)
        except Exception as e:
            return ret.errRet(f"Chyba při vypínání swap souboru: {e}")
        
        try:
            # smazat
            runRet(["sudo", "rm", "-f", str(swap)], noOut=True)
        except Exception as e:
            return ret.errRet(f"Chyba při mazání swap souboru: {e}")

        print(f"[OK] Swap soubor smazán: {swap}")
        try:
            modifyFstabSwapEntry(str(swap), add=False)
        except Exception as e:
            return ret.errRet(f"Chyba při úpravě /etc/fstab: {e}")
        
        return ret.okRet("Smazání SWAP .img souboru dokončeno.")
    
    @staticmethod
    def create_swap_img(
        swap:Path,
        targetSizeB:int|None,
        minMessageWidth:int=80
    ) -> onSelReturn:
        """Vytvoří swap soubor o min velikosti 100MiB

        Args:
            swap (Path): cesta k swap .img souboru, full path
            targetSizeB (int): cílová velikost v bytech

        Returns:
            onSelReturn: _description_
        """
        ret = onSelReturn()
        if not isinstance(swap,Path):
            return ret.errRet("Neplatný parametr swap soubor.")
        if not swap.is_absolute():
            return ret.errRet(f"SWAP .img soubor musí být absolutní cesta: {str(swap)}")
        if swap.is_file():
            return ret.errRet(f"SWAP .img soubor již existuje: {str(swap)}")

        if targetSizeB is None:
            x = inputCliSize(
                "100MB",
                minMessageWidth=minMessageWidth
            )
            if x is None:
                return ret.errRet("Nezadána cílová velikost swap souboru.")
            x:cliSize
            targetSizeB = x.inBytes
            
        if not (targetSizeB:=JBJH.is_int(targetSizeB)):
            return ret.errRet("Neplatný parametr targetSize.")
        if targetSizeB < 100*1024*1024:
            return ret.errRet("Cílová velikost swap souboru musí být minimálně 100MiB.")

        
        try:
            # vytvoření sparse file
            runRet(["sudo", "fallocate", "-l", str(targetSizeB), str(swap)], noOut=True)

            # správná práva
            runRet(["sudo", "chmod", "600", str(swap)], noOut=True)
        except Exception as e:
            return ret.errRet(f"Chyba při vytváření swap souboru: {e}")
        
        try:
            # vytvořit swap strukturu
            runRet(["sudo", "mkswap", str(swap)], noOut=True)
        except Exception as e:
            return ret.errRet(f"Chyba při inicializaci swap souboru: {e}")

        try:
            # zapnout
            runRet(["sudo", "swapon", str(swap)], noOut=True)
        except Exception as e:
            return ret.errRet(f"Chyba při zapínání swap souboru: {e}")

        print(f"[OK] Swap aktivní: {swap}")
        try:
            modifyFstabSwapEntry(str(swap), add=True)
        except Exception as e:
            return ret.errRet(f"Chyba při úpravě /etc/fstab: {e}")
        
        return ret.okRet("Vytvoření SWAP .img souboru dokončeno.")

    @staticmethod
    def modifySizeSwapFile(
        filename: str,
        targetSize: int
    ) -> onSelReturn:
        """
        Změní velikost swap souboru.
        
        - Zkontroluje využití RAM a swapu (bezpečnost).
        - Výpočet zda je soubor aktivní swap.
        - Pokud neexistuje → nabídne vytvoření.
        - Pokud existuje a je aktivní → swapoff.
        - Vytvoří nový o dané velikosti.
        - Nastaví mkswap, znovu zapne swapon.
        - Přidá/aktualizuje /etc/fstab.
        
        Pokud zadáme targetSize="0", swap soubor se smaže.
        
        Args:
            filename: cesta k swap souboru (např. "/swapfile")  
            targetSize: velikost v bytech
        Returns:
            onSelReturn: výsledek operace
        """
        ret = onSelReturn()
        
        if filename is None:
            return ret.errRet("Nebyl zadán swap soubor.")

        filename:Path = Path(filename).resolve()
        if not filename.is_absolute():
            return ret.errRet(f"[ERROR] Cesta ke swap souboru musí být absolutní: {filename}")
        
        exists = filename.exists()
        swapActive = False
        if exists:
            if filename.exists and not filename.is_file():
                return ret.errRet(f"[ERROR] Cesta k swap souboru není soubor: {filename}")
            
            swapActive = swapIsActive(str(filename))

            if not swapActive:
                return ret.errRet(f"[INFO] Swap file {filename} není aktivní.")

            meminfo = getCurMemInfo()

            print("== RAM/SWAP info ==")
            used=bytesTx(meminfo.swap_total.bytes - meminfo.swap_free.bytes)
            print(f"RAM:   {meminfo.mem_total} total  | {meminfo.mem_available} free")
            print(f"SWAP:  {meminfo.swap_total} total | {used} used")

            # Bezpečnostní kontrola:
            # Pokud by vypnutí swapu snížilo dostupnou paměť pod 1.5× memory pressure, varuj
            if meminfo.swap_total.bytes - meminfo.swap_free.bytes > meminfo.mem_available.bytes * 1.5:
                print()
                print(text_color("[WARNING] Systém má méně volné RAM než využitého swapu!", en_color.BRIGHT_RED))
                print(text_color("Vypnutí swapu může způsobit OOM (out-of-memory).", en_color.BRIGHT_RED))
                if not confirm("Přesto pokračovat?"):
                    return ret.errRet("Zrušeno uživatelem.")
        else:
            return ret.errRet("[ERROR] Swap soubor neexistuje.")
        
        if (targetSize:=JBJH.is_int(targetSize)) is None:
            return ret.errRet("[ERROR] Neplatný parametr targetSize.")
        
        if targetSize < 100*1024*1024:
            return ret.errRet("[ERROR] Cílová velikost swap souboru musí být minimálně 100MiB.")
        if swapActive:
            swap_mng.remove_swap_img(swap=filename)
        swap_mng.create_swap_img(swap=filename, targetSizeB=targetSize)
        
        return ret.okRet("Změna velikosti SWAP .img souboru dokončeno.")

