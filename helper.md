# Helper
<!-- cspell:ignore nakešuje -->
## Jazyk

Jazykové proměnné musí mít prefix `TXT_` nebo `TX_`

Pro nahrátí jazyka použij v daném modulu

```py
from .lng.default import * 
from .helper import loadLng
loadLng()
```

Umisťujeme na úplný začátek skriptu před ostatní importy

- `from .lng.default import *` Zajistí nahrátí default souboru, toto použijeme jen jsme mohli používat texty v IDE. Načítá jen `TX_` a `TXT_` prefixované názvy proměnných
- `from .helper import loadLng` helper funkce
- `loadLng()` zajistí nahrátí správného jazykového souboru, pokud existuje

Tento kód zajistí nahrátí lng souboru z relativní cesty:

- 'lng/default.py' je výchozí např angličtina - povinný
- 'lng/cs-CZ.py' je přeložený soubor

## Jak nahrává

Nahrává relativně od skriptu, který požádal o nahrátí přes funkci `loadLng`

1. se snaží detekovat `default` pokud je tak jej nahraje, pokud ne tak se další kroky ignorují, default musí být vždy
2. pokud je default a je zadaný `setLng` tak se pokusí nahrát tento soubor a přepsat proměnné z default, tzn **není podmínkou mít kompletně přeložený default**
3. pokud je vše OK, tak si tyto soubory nakešuje do **paměti**, aby při dalších požadavcích nemusel znovu procházet

## Nastavení jazyka

V root skriptu zavoláme

```py
from libs.JBLibs.helper import setLng # import funkce
setLng('cs-CZ') # nastavíme např 'cs-CZ'
```
