# fs_helper – dokumentace modulu

Tento modul poskytuje funkcionalitu pro práci se souborovým systémem, zejména interaktivní výběr souborů a adresářů v terminálu.
Hlavní komponentou je třída `fs_menu`, která umožňuje zobrazit obsah adresáře, filtrovat jej, procházet jej a vybrat položku.
Nevyžaduje žádné externí závislosti jako curses, což zajišťuje širokou kompatibilitu. Používá jen standardní knihovny Pythonu a vlastní knihovny JBLibs.

## Obsah

* Přehled
* Instalace a použití
* Třída `c_fs_itm`
* Funkce `getDir`
* Výčtový typ `e_fs_menu_select`
* Třída `fs_menu`
* Ovládání menu
* Ukázka použití

## Přehled

Modul umožňuje:

* číst obsah adresářů s filtrováním souborů i adresářů,
* stránkování položek,
* filtrování pomocí regulárních výrazů,
* zobrazení velikostí souborů v lidsky čitelné podobě (`bytesTx`),
* zobrazení času modifikace,
* uzamčení uživatele do definovaného kořenového adresáře (`lockToDir`),
* rozhraní ovládané kurzorovými klávesami.

## Instalace a import

```python
from libs.JBLibs.fs_helper import (
    fs_menu,
    e_fs_menu_select,
    c_fs_itm
)
from pathlib import Path
```

## Třída `c_fs_itm`

Reprezentuje jednu položku souborového systému (soubor nebo adresář).

### Atributy

| Atribut | Typ    | Popis                                                           |
| ------- | ------ | --------------------------------------------------------------- |
| `name`  | `str`  | Název souboru/adresáře                                          |
| `ext`   | `str`  | Přípona souboru včetně tečky, malá písmena; pro adresář prázdné |
| `size`  | `int`  | Velikost v bytech                                               |
| `mtime` | `int`  | Unix timestamp poslední modifikace                              |
| `type`  | `int`  | 0 = soubor, 1 = adresář                                         |
| `path`  | `Path` | Absolutní cesta                                                 |

### Vlastnosti

* `is_file` – zda je položka soubor
* `is_dir` – zda je položka adresář
* `mtimeTx` – formátovaný čas modifikace (`YYYY-MM-DD HH:MM:SS`)
* `sizeTx` – velikost jako `bytesTx`

## Funkce `getDir(dir, ...)`

Vrací obsah adresáře jako seznam objektů `c_fs_itm`.

### Parametry

* `dir` – cesta (absolutní/relativní)
* `filterFile` – filtr souborů (regexp, bool)
* `filterDir` – filtr adresářů (regexp, bool)
* `current_dir` – aktuální pracovní adresář pro relativní cesty
* `hidden` – zda zahrnout skryté položky

### Return

```python
(Path, List[c_fs_itm])
```

## Enum `e_fs_menu_select`

Slouží k určení typu výběru v menu.

| Hodnota | Význam                             |
| ------- | ---------------------------------- |
| `file`  | uživatel může vybrat pouze soubor  |
| `dir`   | uživatel může vybrat pouze adresář |

## Třída `fs_menu`

Interaktivní výběr souborů/adresářů v terminálu.
Nese plnou logiku jako stránkování, filtry, zobrazení pomocných informací, přechod v adresářové struktuře.

### Parametry konstruktoru

| Parametr      | Typ                | Popis                        |                                                     |
| ------------- | ------------------ | ---------------------------- | --------------------------------------------------- |
| `dir`         | `str               | Path`                        | výchozí adresář                                     |
| `select`      | `e_fs_menu_select` | typ výběru (soubor/adresář)  |                                                     |
| `hidden`      | `bool`             | zobrazit skryté položky      |                                                     |
| `itemsOnPage` | `int`              | počet řádků na jednu stránku |                                                     |
| `lockToDir`   | `Path              | None`                        | pokud je nastaveno, menu nepustí mimo tento adresář |

### Důležité vlastnosti

* `current_dir` – aktuální adresář
* `chRoot` – uzamčený root (pokud je nastaven)
* `dirItems` – seznam položek k zobrazení
* `filterList` – aktivní filtr (regexp nebo None)

## Ovládání v terminálu

| Klávesa     | Význam                        |
| ----------- | ----------------------------- |
| →           | vstoupit do adresáře          |
| ←           | o úroveň výš                  |
| PgUp / PgDn | stránkování                   |
| Home / End  | na začátek / konec            |
| F2          | zobrazit/skrýt adresáře       |
| F4          | zobrazit/skrýt skryté položky |
| f           | zadání regex filtru           |
| Enter       | potvrdit výběr                |
| ESC         | zavřít menu                   |

## Ukázka použití

```python
from libs.JBLibs.fs_helper import fs_menu, e_fs_menu_select, c_fs_itm
from pathlib import Path
from libs.JBLibs.format import bytesTx

m = fs_menu(
    'python',
    select=e_fs_menu_select.file,
    itemsOnPage=15,
    lockToDir=Path('/mnt')
)

# .run() vrací None pokud uživatel vybral položku
if m.run() is None:
    x = m.getLastSelItem()
    if x is not None:
        x: c_fs_itm = x.data
        print(
            f"Vybraný soubor: {x.name}, ext: {x.ext}\n"
            f"Cesta: {x.path}\n"
            f"Velikost: {bytesTx(x.size)}\n"
            f"Modifikace: {x.mtimeTx}"
        )
    else:
        print("Nebyl vybrán žádný soubor.")
else:
    print("Výběr byl zrušen.")
```

## Verze knihovny

```python
from libs.JBLibs.fs_helper import VERSION
print(VERSION())
```

## Poznámky k vnitřní implementaci

* Interní logika zajišťuje, že nedojde k opuštění `lockToDir`.
* Stav menu se aktualizuje pouze při změně adresáře nebo filtru.
* Velikosti jsou zobrazovány pomocí `bytesTx`, která rozlišuje jednotky (kB, MB, GB) a desítkové hodnoty.

## Závěr

Tento modul poskytuje jednoduché, ale velmi silné rozhraní pro práci se souborovým systémem v terminálu.
Hodí se pro instalátory, správu instancí, výběr konfigurací, průzkum logů a další serverové nástroje.
