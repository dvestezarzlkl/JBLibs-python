# Dokumentace třídy `c_menu`
<!-- cspell:ignore repr -->
Třída `c_menu` poskytuje rámec pro vytváření a správu interaktivních konzolových menu v Python aplikacích. Nepoužívá knihovnu `curses`, ale pouze escape sekvence, a jejím primárním účelem není barevné zobrazování, ale praktičnost a rychlý výběr s co nejintuitivnějším ovládáním. Podporuje různé funkce, včetně vlastních položek menu, uživatelsky definovaných akcí a struktury vícestupňových menu. Třída `c_menu` se nepoužívá přímo, ale je určena k rozšíření prostřednictvím dědiců.

generováno pomocí *ChatGPT 4o Canvas'

## Aktualizovaný přehled tříd

### 1. `c_menu_item`

Reprezentuje jednotlivou položku menu s možnostmi pro přizpůsobení.

#### Vlastnosti

- `label (str)`: Zobrazený název položky menu - jednořádkový, například "Start service".
  - Speciální hodnoty:
    - `'-', '=', '+', '_'`: Zobrazí se jako oddělovací čáry v délce titulku.
- `choice (str)`: Klávesová zkratka pro tuto položku menu. Pokud je kratší text obsažen v delším, automaticky se nevyvolá, ale čeká na potvrzení stiskem Enter. Automaticky se vyvolá pouze nejdelší volba.
- `data (Any)`: Data předávaná vybranými funkcemi jako je např. `onSelect`.
- `onSelect (Callable[["c_menu_item"], onSelReturn])`: Funkce volaná při výběru této položky.
- `onAfterSelect (Callable[[onSelReturn, "c_menu_item"], None])`: Funkce volaná po provedení `onSelect`.
- `enabled (bool)`: Určuje, zda je položka dostupná k výběru. Pokud není zapnuta, je zobrazen text jako např. `/DIS/`.
- `hidden (bool)`: Pokud je `True`, položka se skryje.
- `atRight (str)`: Text zobrazený na pravé straně položky.

#### Metody

- `__init__(label, choice, onSelect, onAfterSelect, data, enabled, hidden, atRight)`: Inicializuje položku menu s danými atributy.

### 2. `onSelReturn`

Používá se pro správu odpovědí po výběru položky menu, např. vrácené z funkce `onSelect`.

#### Vlastnosti `onSelReturn`

- `err (str)`: Chybová zpráva zobrazená po výběru, pokud je nastavena. Stejně tak `ok` zobrazuje potvrzující zprávu. Pokud nejsou nastaveny, nezobrazí se.
- `ok (str)`: Potvrzující zpráva zobrazená po výběru.
- `data (Any)`: Data předána funkci `onAfterSelect`.
- `endMenu (bool)`: Pokud je nastavena na `True`, ukončí menu.

#### Metody `onSelReturn`

- `__init__(err, ok, data, endMenu)`: Inicializuje instanci s chybovými a potvrzovacími zprávami a ovládacími příznaky.
- `__repr__()`: Vrátí řetězcovou reprezentaci objektu `onSelReturn`.

### 3. `c_menu`

Hlavní třída menu, určená k rozšíření pro konkrétní aplikace. Menu se automaticky stará o minimální šířku z položek `title` a `subTitle` a následně voleb menu, které mohou mít dva texty: text volby a popisu, a pravý informační text, který je zarovnaný od pravé strany.

#### Vlastnosti `c_menu`

- `menu (list[c_menu_item])`: Seznam položek menu. Může být definován jako pevné položky nebo dynamicky měněn při zobrazení.
- `title (str)`: Titulek zobrazený nahoře menu.
- `subTitle (str)`: Podtitulek zobrazený pod titulkem.
- `afterTitle (str)`: Další text zobrazený pod titulkem a menu.
- `afterMenu (str)`: Text zobrazený na konci menu.
- `lastReturn (onSelReturn)`: Ukládá výsledek posledního volání `onSelect`.
- `onEnterMenu (Callable[[], Union[str, None]])`: Funkce volaná před prvním zobrazením menu.
- `onShowMenu (Callable[['c_menu'], None])`: Funkce volaná před každým zobrazením menu.
- `onShownMenu (Callable[['c_menu'], None])`: Funkce volaná po každém zobrazení menu.
- `onExitMenu (Callable[['c_menu'], Union[None, bool]])`: Funkce volaná při ukončení menu. Pokud vrátí `False`, menu se neukončí.
- `choiceBack (c_menu_item)`: Položka menu pro funkci "Zpět" v podmenu. Pokud `None`, nebude aktivní.
- `ESC_is_quit (bool)`: Pokud je `True`, stisk ESC ukončí menu a zobrazí volbu 'ESC - Zpět'.
- `choiceQuit (c_menu_item)`: Položka menu pro funkci "Konec". Pokud `None`, nebude aktivní.
- `_selectedItem (c_menu_item)`: Položka, která je aktuálně vybrána.

#### Metody `c_menu`

- `__init__()`: Inicializuje novou instanci menu.
- `__getList() -> list[c_menu_item]`: Vrátí seznam položek menu, včetně možností zpět a konec.
- `processList(lst, onlyOneColumn, spaceBetweenTexts, rightTxBrackets, minWidth, linePrefix)`: Formátuje a zpracovává seznam položek pro zobrazení.
- `printBlok(title_items, subTitle_items, charObal, leftRightLength, charSubtitle, eof, space_between_texts, min_width)`: Zobrazuje blok textu s volitelnými okraji.
- `__print(lastRet) -> int`: Tiskne menu, zobrazuje všechny položky a oddělovače.
- `searchItem(choice) -> Tuple[c_menu_item, bool]`: Hledá položku menu podle klávesové zkratky.
- `checkItemChoice(list) -> Union[None, List[str]]`: Kontroluje duplicitní klávesové zkratky v položkách menu.
- `nextItem(forward=True)`: Posun na další položku menu.
- `run(item=None) -> Union[None, str]`: Spustí menu, umožňuje interaktivní navigaci a výběr položek.
- `run_refresh(c, first) -> Union[bool, str]`: Obnovuje zobrazení menu a zpracovává vstup.
- `callExitMenu(itm) -> Union[bool, str, None]`: Volá funkci `onExitMenu` při ukončení menu.

## Ukázka použití

```python
from libs.JBLibs.c_menu import c_menu, c_menu_item, onSelReturn
from libs.JBLibs.input import confirm, anyKey

# Vytvoření hlavního menu
class MainMenu(c_menu):
    def __init__(self):
        super().__init__()
        self.title = "Hlavní menu"
        self.menu = [
            c_menu_item("Možnost 1", "1", self.delete_action),
            c_menu_item("Možnost 2", "2", SubMenu()),  # Odkaz na podmenu
            c_menu_item("-", ""),  # Oddělovač
            c_menu_item("Konec", "q", lambda i: onSelReturn(endMenu=True))
        ]
    def delete_action(self, selItem: c_menu_item) -> onSelReturn:
        anyKey() # zobrazí zprávu stiskni klávesu

# Vytvoření podmenu
class SubMenu(c_menu):
    counter: int = 0

    def __init__(self):
        super().__init__()
        self.title = "Podmenu"
        self.ESC_is_quit = True  # ESC bude ukončovat podmenu
        self.menu = [
            c_menu_item("Pod-možnost 1", "1", self.confirm_action),
            c_menu_item("Pod-možnost 2", "2", example_action)
        ]

    def confirm_action(self, selItem: c_menu_item) -> onSelReturn:
        confirm("Opravdu se přejete provést akci?")

# Spuštění hlavního menu
menu = MainMenu()
menu.run()
```

## Poznámky

- **Rozšíření `c_menu`**: Doporučuje se rozšířit `c_menu` pro přidání specifického chování a přepisů pro konkrétní aplikace.
- **Ošetření chyb**: Použijte `onSelReturn` pro správu a zobrazení chybových zpráv na základě akcí uživatele.
- **Vícestupňové menu**: Podmenu lze vytvořit nastavením `onSelect` na jinou instanci `c_menu`.

## Aktuální funkcionality

- Výběr volby pomocí šipek nebo psaní klávesou.
- Podpora dynamických menu a větvení submenu pro zjednodušené ovládání.
- Příkaz ESC slouží k ukončení menu nebo návratu zpět.
- Podpora zobrazování chybových a informačních hlášek pomocí třídy `onSelReturn`.
