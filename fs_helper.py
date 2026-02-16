import os
from pathlib import Path
import re
from typing import List
from dataclasses import dataclass,field
from enum import Enum
from .c_menu import c_menu,c_menu_item,onSelReturn,c_menu_block_items
from .term import text_inverse,en_color,text_color
from .format import bytesTx
from datetime import datetime
from typing import Optional, Union, Callable
from .jbjh import JBJH

"""
Modul pro pomocné funkce související se souborovým systémem.
Hlavní třídou je fs_menu, která umožňuje procházet adresáře a vybírat soubory nebo adresáře.

Pouřití např:
```python
from libs.JBLibs.fs_helper import e_fs_menu_select,fs_menu,c_fs_itm
from pathlib import Path
from libs.JBLibs.format import bytesTx
            
m=fs_menu('python',
    select=e_fs_menu_select.file,
    itemsOnPage=15,
    lockToDir=Path('/mnt')
)

if m.run() is None:
    x=m.getLastSelItem() # vrací c_menu_item nebo None
    if not x is None:
        x:c_fs_itm=x.data # pokud je vráceno c_menu_item, získáme data která obsahují c_fs_itm
        print(
            f"Vybraný soubor: {x.name}, ext: {x.ext}\n"
            f"Cesta: {x.path}\n"
            f"Velikost souboru: {bytesTx(x.size)}\n"
            f"Poslední modifikace: {x.mtimeTx}"
        )
    else:
        print("Nebyl vybrán žádný soubor.")
else:
    print("Výběr byl zrušen.")
```
"""

def VERSION() -> str:
    return fs_menu._VERSION_

@dataclass
class c_fs_itm:
    name: str
    """Název souboru nebo adresáře. Včetně přípony pro soubory."""
    
    ext: str
    """Přípona souboru, včetně tečky, malá písmena. Prázdné pro adresáře."""
    
    size: int
    """Velikost souboru v bytech."""
    
    mtime: int
    """Čas poslední modifikace jako unix timestamp."""
    
    type: int   # 0=file, 1=dir
    """Typ položky: 0=soubor, 1=adresář, jednoduše lze testovat přes is_file a is_dir vlastnosti."""
    
    path: Path
    """Cesta k souboru nebo adresáři."""

    @property
    def is_file(self) -> bool:
        return self.type == 0

    @property
    def is_dir(self) -> bool:
        return self.type == 1
    
    __mtimeStr:Optional[str]=field(default=None, init=False, repr=False)
    @property
    def mtimeTx(self) -> str:
        """Vrátí čas poslední modifikace jako čitelný řetězec."""
        if self.__mtimeStr is None:
            self.__mtimeStr=datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M:%S")
        return self.__mtimeStr
    
    __sizeTx:Optional[bytesTx]=field(default=None, init=False, repr=False)
    @property
    def sizeTx(self) -> bytesTx:
        """Vrátí velikost jako bytesTx objekt."""
        if self.__sizeTx is None:
            self.__sizeTx=bytesTx(self.size)
        return self.__sizeTx
    
    def __repr__(self):
        return (
            f"c_fs_itm("
            f"name={self.name!r}, "
            f"ext={self.ext!r}, "
            f"size={self.size}, "
            f"mtime={self.mtimeTx}, "
            f"type={'DIR' if self.is_dir else 'FILE'}, "
            f"path={str(self.path)!r}"
            f")"
        )
    
class e_fs_menu_select(Enum):
    dir=1
    file=2

def getDir(
    dir: Union[str|Path],
    filterFile: Union[str|re.Pattern|bool|Callable] = True,
    filterDir:Union[str|re.Pattern|bool|Callable]=True,
    current_dir: Union[str|Path|None] = None,
    hidden: bool = False,
    nameFilter: Optional[Union[str, re.Pattern, callable]] = None,
) -> tuple[Path, List[c_fs_itm]]:
    """
    Vrátí seznam souborů a adresářů v zadaném adresáři.
    
    Args:
        dir (str): Cesta k adresáři. 
                   - Absolutní → použije se přímo
                   - Relativní → spojí se s current_dir
                   - "." → parent dir
        filterFile (str): regexp filtr pro názvy souborů
        filterDir (str|bool): buď:
            str - regexp filtr pro názvy adresářů
            False - nezahrnovat adresáře
            True - zahrnout všechny adresáře
            callable - funkce která přijímá Path položky a vrací True/False, lze použít pro složitější filtry, např když chceme
                        ověřit že v adresáři něco existuje
        nameFilter (Optional[Union[str, re.Pattern, callable]]): Volitelný filtr pro názvy položek. Pochází z filtru 'f'
            - str - regexp pro filtrování názvů položek
            - re.Pattern - regexp pro filtrování názvů položek            
        current_dir (str|Path|None): výchozí adresář pokud je relativní cesta
        hidden (bool): zda zahrnout skryté soubory (začínající tečkou)
            True - zahrnout
            False - nezahrnovat
        
    Returns:
        tuple[Path,List[c_fs_itm]]: adresář (popř změněnný) ze kterého se čte a seznam položek, a seznam položek
        
    Raises:
        FileNotFoundError
        NotADirectoryError
        TypeError
    """
    if not isinstance(dir, (str, Path)):
        raise TypeError("dir musí být string nebo Path")
    if not isinstance(filterFile, (str, bool, re.Pattern, Callable)):
        raise TypeError("filterFile musí být string bool nebo re.Pattern")
    if not isinstance(filterDir, (str, bool, re.Pattern, Callable)):
        raise TypeError("filterDir musí být string bool nebo re.Pattern")
    if isinstance(current_dir, str):
        current_dir = Path(current_dir).resolve()
    if not isinstance(current_dir, (Path, type(None))):
        raise TypeError("current_dir musí být string nebo None")
    
    if isinstance(dir, str):
        dir = Path(dir).resolve()
    
    # určení výchozí cesty
    if current_dir is None:
        current_dir = Path(os.getcwd()).resolve()

    # Pokud ".", přejdi do parent
    if dir == ".":
        base = current_dir.parent
    else:
        p = Path(dir)
        base = p if p.is_absolute() else current_dir / p

    base = base.resolve()

    if not base.exists():
        raise FileNotFoundError(f"Cesta neexistuje: {base}")

    if not base.is_dir():
        raise NotADirectoryError(f"Není adresář: {base}")

    items: List[c_fs_itm] = []
    
    flRgx:None|re.Pattern = None
    dirRgx:bool|re.Pattern = None
    nmFilterRgx:None|re.Pattern = None
    
    if filterFile is False:
        flRgx = False
    elif isinstance(filterFile, str):
        flRgx = re.compile(filterFile,re.IGNORECASE)
    else:
        flRgx = filterFile
    
    if filterDir is False:
        dirRgx = False
    elif isinstance(filterDir, str):
        dirRgx = re.compile(filterDir,re.IGNORECASE)
    else:
        dirRgx = filterDir

    if nameFilter is not None:
        if isinstance(nameFilter, str):
            nmFilterRgx = re.compile(nameFilter,re.IGNORECASE)
        elif isinstance(nameFilter, re.Pattern):
            nmFilterRgx = nameFilter
        elif callable(nameFilter):
            nmFilterRgx = nameFilter
        else:
            raise TypeError("nameFilter musí být string nebo re.Pattern nebo callable")

    # projdi adresář
    for entry in base.iterdir():
        name = entry.name

        # filtrace podle regexu
        if entry.is_file():
            if not hidden and name.startswith("."):
                continue            
            if flRgx is False:
                continue
            if isinstance(flRgx, re.Pattern) and flRgx.search(name) is None:
                continue
            if callable(flRgx):
                if not flRgx(entry):
                    continue
                
        if entry.is_dir():
            if not hidden and name.startswith("."):
                continue            
            if dirRgx is False:
                continue
            if isinstance(dirRgx, re.Pattern) and dirRgx.search(name) is None:
                continue
            if callable(dirRgx):
                if not dirRgx(entry):
                    continue

        # filtrace podle nameFilter
        if nmFilterRgx is not None:
            if isinstance(nmFilterRgx, re.Pattern):
                if nmFilterRgx.search(name) is None:
                    continue
            elif callable(nmFilterRgx):
                if not nmFilterRgx(entry):
                    continue

        stat = entry.stat()
        ext = entry.suffix.lower() if entry.is_file() else ""

        items.append(
            c_fs_itm(
                name=name,
                ext=ext,
                size=stat.st_size,
                mtime=int(stat.st_mtime),
                type=1 if entry.is_dir() else 0,
                path=entry.resolve()
            )
        )

    # řazení: dirs first, then files, alphabetical
    items.sort(
        key=lambda x: (0 if x.type == 1 else 1, x.name.lower())
    )

    return (base, items)


class fs_menu(c_menu):
    """Menu pro výběr souborů a adresářů v daném adresáři.
    Využívá getDir pro získání seznamu položek.
    """
    
    _VERSION_:str="2.2.0"
        
    def __init__(
        self,
        dir: str|Path,
        select:e_fs_menu_select = e_fs_menu_select.file,
        hidden: bool = False,
        itemsOnPage: int = 30,
        lockToDir: None|str|Path = None,
        minMenuWidth:int|None=None,
        filterList: Optional[Union[str, re.Pattern, callable]] = None,
        message:str|c_menu_block_items|list|None=None,
        onShowMenuItem:Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]]=None,
        onSelectItem:Optional[Callable[[Path],Union[onSelReturn|None|bool]]]=None,
    ) -> None:
        """Inicializace fs_menu.
        Parametry:
            dir (str|Path): Výchozí adresář pro zobrazení., může obsahovat '' pokud máme zadané lockToDir
            select (e_fs_menu_select): Typ výběru - adresář nebo soubor.
            hidden (bool): Zda zobrazit skryté soubory (začínající tečkou).
            itemsOnPage (int): Počet položek na stránku.
            lockToDir (None|str|Path): Pokud je zadáno, bude uživatel uzamčen do tohoto adresáře a tím se z něj stane root
                - cesta je ale vždy vrácena jako absolutní až do fyzickkého rootu systému.  
                - Nahrazuje chRoot.
            minMenuWidth (int|None): Minimální šířka menu.
            filterList (Optional[Union[str, re.Pattern, callable]]): Volitelný filtr pro názvy položek.
                - str - regexp pro filtrování názvů položek
                - re.Pattern - regexp pro filtrování názvů položek
                - callable - funkce která přijímá Path položky a vrací True/False, lze použít pro složitější filtry, např když chceme
                        ověřit že v adresáři něco existuje
            message (str|c_menu_block_items|list|None): Volitelná zpráva/y k zobrazení pod  titulkem menu.
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

        Raises:
            TypeError: Pokud jsou parametry v nesprávném formátu.
        
        """
        
        super().__init__(
            minMenuWidth=minMenuWidth
        )
        
        if not isinstance(select, e_fs_menu_select):
            raise TypeError("select musí být e_fs_menu_select")        
        if select is e_fs_menu_select.dir:
            filterFile = False
        else:
            filterFile = True
        filterDir = True
        
        self.select:e_fs_menu_select = select
        """Typ výběru: adresář nebo soubor."""
        
        self.dir:Path = dir
        """Výchozí adresář pro zobrazení."""
        
        if isinstance(self.dir, str):
            self.dir = Path(self.dir)
        if not isinstance(self.dir, Path):
            raise TypeError("dir musí být string nebo Path")
        
        self.filterFile:str|re.Pattern|bool = filterFile
        """Filtry pro soubory."""
        
        self.filterDir:str|re.Pattern|bool = filterDir
        """Filtry pro soubory a adresáře."""
        
        self.filterList:None|re.Pattern|callable = None
        """Volitelný filtr pro názvy položek."""
        
        if filterList is not None:
            if isinstance(filterList, str):
                filterList = re.compile(filterList,re.IGNORECASE)
            elif isinstance(filterList, re.Pattern):
                pass
            elif callable(filterList):
                pass
            else:
                raise TypeError("filterItemsRgx musí být string nebo re.Pattern")
            if select is e_fs_menu_select.file:
                self.filterFile = filterList
            if select is e_fs_menu_select.dir:
                self.filterDir = filterList        
        
        self.chRoot:None|Path = None
        """Kořenový adresář pro uzamčení uživatele."""
        if lockToDir is not None:
            if isinstance(lockToDir, str):
                lockToDir = Path(lockToDir)
            if not isinstance(lockToDir, Path):
                raise TypeError("lockToDir musí být string nebo Path")
            if not lockToDir.is_absolute():
                raise ValueError("lockToDir musí být absolutní cesta")
            self.chRoot = lockToDir.resolve()
            
        
        if not self.dir.is_absolute():
            if isinstance(self.chRoot, Path):
                # je definován root tak připojíme k němu relativní cestu
                self.dir = (self.chRoot / self.dir).resolve()
            else:
                # připojíme k aktuálnímu adresáři
                self.dir = (Path(os.getcwd()).resolve() / self.dir).resolve()
        else:
            self.dir = self.dir.resolve()
        
        if not self.dir.is_dir():
            raise ValueError("Adresář nebyl nalezen: " + str(self.dir))


        if onShowMenuItem and JBJH.is_callable(onShowMenuItem) is None:
            raise TypeError("onShowMenuItem musí být callable nebo None")
        self.__onShowMenuItem:Optional[Callable[[c_fs_itm,str,str],tuple[str,str]]] = onShowMenuItem
        """Volitelná funkce pro úpravu zobrazení položky."""
        
        if onSelectItem and JBJH.is_callable(onSelectItem) is None:
            raise TypeError("onSelectItem musí být callable nebo None")
        self.__onSelectItem:Optional[Callable[[Path],Union[onSelReturn|None|bool]]] = onSelectItem
        """Volitelná funkce pro zpracování výběru položky."""

        self.current_dir = Path(self.dir).resolve()
        """Aktuální adresář pro zobrazení."""        

        # pokud není path v rámci chRoot, vyhodíme error
        if isinstance(self.chRoot, Path) and not self.checkLockDir(self.current_dir):
            raise ValueError("Zadaný adresář není v rámci lockToDir: " + str(self.current_dir))
                
        self.hidden: bool = hidden
        self.items: List[c_menu_item] = []
        
        self.baseTitle:c_menu_item = c_menu_block_items()
        # self.title.append( ("Výběr souboru/adresáře","c") )
        self.baseTitle.append((
            text_color(" Výběr "+ ("adresáře" if select is e_fs_menu_select.dir else "souboru") +" ",en_color.YELLOW,inverse=True),
            "c"
        ))
        self.baseTitle.append( (f"v.: {self._VERSION_}") )
        self.baseTitle.append( ("",text_color("Pohyb adresáři: → ←, PgUp/PgDn, Home/End", en_color.BRIGHT_YELLOW)) )
        if message is not None:
            self.baseTitle.extend( message )
        
        self.keyBind('\x1b[C', self.toAdr)
        self.keyBind('\x1b[D', self.outAdr)
        # zaregistrujeeme page up/down
        self.keyBind('\x1b[5~', self.pageUp)
        self.keyBind('\x1b[6~', self.pageDown)
        # home a end
        self.keyBind('\x1b[H', self.toTop)
        self.keyBind('\x1b[F', self.toBottom)
                
        # f4 toggle hidden
        self.keyBind('\x1bOS', self.toggleHidden)
        
        # f2 toggle show dir
        self.keyBind('\x1bOQ', self.toggleShowDir)
                
        self.oldDir = None
        self.dirItems=[]
        self.page=0
        self.pageItemsCount=itemsOnPage
        # pokud je míň jak 10 nebo víc jak 100, tak nastavíme očetříme na 10 nebo 100
        if self.pageItemsCount < 10:
            self.pageItemsCount = 10
        elif self.pageItemsCount > 100:
            self.pageItemsCount = 100
        
    def checkLockDir(self, path:Path)->bool:
        """Pokud je lockDir None tak vrací True, jinak ověřuje zda je cesta v rámci lockDir.
        Tzn path musí být absolutní, pokud není, tak vrací False.
        Args:
            path (Path): Cesta k ověření.
        Returns:
            bool: True pokud je cesta v rámci lockDir nebo pokud není lockDir nastaven.
        """
        if self.chRoot is None:
            return True
        try:
            path.relative_to(self.chRoot)
            return True
        except ValueError:
            return False
        
    def onShowMenu(self) -> None:
        """Při zobrazení menu načte položky z adresáře."""
        if self.oldDir != self.current_dir:
            self.oldDir = self.current_dir            
                
            self.current_dir, items = getDir(
                self.current_dir,
                filterFile=self.filterFile,
                filterDir=self.filterDir,
                hidden=self.hidden,
                nameFilter=self.filterList
            )
            self.dirItems=[]
            
            self.page=0
            choice=0
            for itm in items:
                display_name = f"[DIR] {itm.name}" if itm.is_dir else itm.name
                
                lText=display_name
                rText=str(bytesTx(itm.size)) if itm.is_file else "<DIR>"
                if self.__onShowMenuItem is not None:
                    try:
                        xTx=self.__onShowMenuItem(itm,lText,rText)
                        if isinstance(xTx, tuple) and len(xTx) == 2:
                            lText,rText=xTx
                            display_name=lText
                        else:
                            raise TypeError("onShowMenuItem musí vracet tuple[str,str]")
                    except Exception as e:
                        raise RuntimeError(f"Chyba v onShowMenuItem funkci: {str(e)}")
                
                self.dirItems.append(
                    c_menu_item(
                        lText,
                        f"{choice:02}",
                        self.vyberItem,
                        None,
                        itm,
                        atRight=rText
                    )
                )
                choice+=1
            self.dirItems.append(c_menu_item(
                "Vyber aktuální cestu",
                "p",
                self.vyberItem,
                None,
                c_fs_itm(
                    name=str(self.current_dir.name),
                    ext="",
                    size=0,
                    mtime=0,
                    type=1,
                    path=self.current_dir.resolve()
                ),
                atRight=text_color("<OK>", color=en_color.BRIGHT_GREEN)
            ))
                
        # do .menu přidáme položky z dirItems se stránkováním
        start_idx = self.page * self.pageItemsCount
        end_idx = start_idx + self.pageItemsCount
        paged_items = self.dirItems[start_idx:end_idx]
        self.menu = paged_items
        
        self.title = c_menu_block_items()
        self.title.extend(self.baseTitle)
        self.title.rightBrackets = False
        # přidáme navigační položky
        ano=text_inverse(" ANO ")
        self.title.append( (
            f"Zobrazení skrytých souborů: " + (ano if self.hidden else "NE"),
            f"Zobr. jen soubory: " +("NE" if self.filterDir is True else (self.filterDir if isinstance(self.filterDir,str) else ano))
        ))
        
        self.menu.append(None)  # oddělovač
        self.menu.append(c_menu_item("Nápověda", "h", self.showHelp))
        self.menu.append(c_menu_item("Nastav filtr názvů", "f", self.setFilter))
        
        # aktualizace subtitle
        self.subTitle = c_menu_block_items()
        if isinstance(self.chRoot, Path):
            self.subTitle.append( (f"Uzamčeno do:", str(self.chRoot)) )
        self.subTitle.append( (f"Filtr názvů souborů:", text_inverse(" "+self.filterList.pattern+" ") if self.filterList else "ŽÁDNÝ") )
        
        # aktuální cesta
        self.afterTitle =c_menu_block_items( rightBrackets=False)
        self.afterTitle.append( ( text_color(f" Akt.cesta: ",color=en_color.BRIGHT_BLUE,inverse=True),  text_color(str(self.current_dir),color=en_color.BRIGHT_CYAN)) )
        self.afterTitle.append('-')

        # přidáme info o počtu položek a stránkování        
        self.afterMenu =[]
        self.afterMenu.append('-')
        self.afterMenu.append( (f"Celkem položek: ", str(len(self.dirItems))) )
        total_pages = max(1, ((len(self.dirItems) - 1) // self.pageItemsCount) + 1)
        self.afterMenu.append(("Stránka:", f"{self.page + 1} / {total_pages}"))
        self.afterMenu.append('=')
        
        
    def vyberItem(self, item:c_menu_item) -> onSelReturn:
        """Zpracuje výběr položky."""
        if not isinstance(item, c_menu_item):
            return False
        fs:c_fs_itm = getattr(item,'data',None)
        if not isinstance(fs, c_fs_itm):
            return False
        
        if self.select is not e_fs_menu_select.dir and fs.is_dir:
            return False
        
        data:c_fs_itm = item.data
        ret=str(data.name) + (data.ext if data.ext else "")
        if self.__onSelectItem is not None:
            pth=Path(data.path)
            try:
                res=self.__onSelectItem(pth)
                if isinstance(res, onSelReturn):
                    res.endMenu=res.ok  # pokud je ok, ukončíme menu
                    return res
                elif isinstance(res, bool):
                    if res is True:
                        return onSelReturn(endMenu=True,data=ret)
                    else:
                        return False
                else:
                    return False
            except Exception as e:
                return onSelReturn(
                    err=f"Chyba v onSelectItem funkci: {str(e)}"
                )
        
        return onSelReturn(endMenu=True,data=ret)
        
    def toAdr(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy."""
        
        if isinstance(item, c_menu_item):
            fs:c_fs_itm = getattr(item,'data',None)
            if isinstance(fs, c_fs_itm) and fs.is_dir:
                self.current_dir = self.current_dir / fs.name
                self.filterList = None
                self.menuRecycle=True
                self._selectedItem = None  # zrušíme výběr protože jsme změnili adresář
        
        return None
    
    def outAdr(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy."""

        # if isinstance(item, c_menu_item):
        #    fs:c_fs_itm = getattr(item,'data',None)
        #    if isinstance(fs, c_fs_itm):
        # toto může kdykoliv, protože jdeme jen o úroveň výš a může být situace výberu dir kde v dir není žádný dir
        parent = self.current_dir.parent                
        if parent != self.current_dir:
            if isinstance(self.chRoot, Path) and not self.checkLockDir(parent):
                return None
            
            self.current_dir = parent
            self.filterList = None
            self.menuRecycle=True
            self._selectedItem = None  # zrušíme výběr protože jsme změnili adresář
        
        return None
    
    def pageUp(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy Page Up."""
        if self.page > 0:
            self.page -= 1
            self.menuRecycle = True
        return None
    
    def pageDown(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy Page Down."""
        max_page = len(self.dirItems) // self.pageItemsCount
        if self.page < max_page:
            self.page += 1
            self.menuRecycle = True
        return None
    
    def toTop(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy Home."""
        if self.page != 0:
            self.page = 0
            self.menuRecycle = True
        return None
    def toBottom(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy End."""
        max_page = len(self.dirItems) // self.pageItemsCount
        if self.page != max_page:
            self.page = max_page
            self.menuRecycle = True
        return None
    
    def setFilter(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy F3 pro zadání filtru."""
        from libs.JBLibs.input import get_input,reset
        
        reset()
        inp = get_input(
            "Zadejte filtr pro názvy souborů a adresářů (regexp), prázdné pro všechny:",
            True
        )
        inp = inp.strip()
        if inp is not None:
            if inp == "":
                self.filterList = None
            else:
                rg=re.compile(inp,re.IGNORECASE)
                self.filterList = rg
            self.menuRecycle = True
            self.oldDir = None  # vynutí načtení znovu
        return None
    
    def toggleHidden(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy F4 pro přepnutí zobrazení skrytých souborů."""
        self.hidden = not self.hidden
        self.oldDir = None  # vynutí načtení znovu
        self.menuRecycle = True
        return None
    
    def toggleShowDir(self, item:c_menu_item) -> None:
        """Zpracuje vložení klávesy F2 pro přepnutí zobrazení adresářů."""
        if self.filterDir is False:
            self.filterDir = True
        else:
            self.filterDir = False
        self.oldDir = None  # vynutí načtení znovu
        self.menuRecycle = True
        return None
    
    def showHelp(self, item:c_menu_item) -> None:
        """Zobrazí nápovědu pro ovládání FS menu."""
        from libs.JBLibs.term import cls   # pokud máš vlastní cls(), jinak použij print("\033c")
        from libs.JBLibs.input import reset, anyKey

        cls()
        print("=== Nápověda pro prohlížeč souborů ===\n")
        print("Navigace:")
        print("  →   vstoupit do adresáře")
        print("  ←   o úroveň výš")
        print("  ↑↓  pohyb v seznamu")
        print("  PgUp / PgDown  stránkování")
        print("  Home / End     skok na začátek / konec")
        print("")
        print("Filtry a zobrazení:")
        print("  F2  přepnout zobrazování adresářů")
        print("  F4  zobrazit / skrýt skryté soubory (.)")
        print("  f   zadat regexp filtr pro názvy")
        print("        ponech prázdné pro zrušení filtru")
        print("")
        print("Obecné:")
        print("  ENTER   vybrat položku")
        print("  ESC     zavřít menu")
        print("")
        print("----------------------------------------")
        print(" Stiskněte ENTER pro návrat do menu ...")
        print("----------------------------------------\n")

        reset()
        anyKey()

        self.menuRecycle = True
        return None
    