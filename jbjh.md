# Knihovna JBJH

Obsahuje pomocné funkce pro různé účely.

## Použití funkcí `is_*`

```python
x = "123"
if (x := JBJH.is_int(x)) is not None:
    print(f"Hodnota je int: {x}")
else:
    print("Hodnota není int.")
```

Funkce `JBJH.is_*` slouží jako **kombinace validace a normalizace hodnoty**.
Nejde pouze o test typu, ale o pokus o **bezpečný převod** na požadovaný typ.

Jedná se o vědomou náhradu dřívějších PHP helper funkcí, např.:

```php
JBJH::is_int(&$var): bool
```

s tím rozdílem, že v Python verzi:

* pokud je hodnota **validní nebo převoditelná**, funkce ji **vrátí v cílovém typu**

  * `1` → `1`
  * `"1"` → `1`
* pokud převod **není možný**, vrátí `None`
* volitelně (`throw=True`) může **vyhodit výjimku**

Tím se eliminuje častý problém, kdy se hodnota sice otestuje jako „numeric“,
ale v dalším kódu se stále pracuje se stringem.

### Režimy použití

#### 1) Normalizační režim (doporučený)

Používá se při práci s dynamickými vstupy (DB, CLI, JSON, ENV):

```python
if (val := JBJH.is_int(x)) is not None:
    # val je skutečný int
    ...
else:
    # neplatná hodnota
```

#### 2) Striktní validační režim

Používá se, pokud má být chyba považována za výjimku:

```python
val = JBJH.is_int(x, throw=True)
```

### Výhody oproti tradičním metodám

* **Kombinace validace a převodu**: Umožňuje zkontrolovat a zároveň převést hodnotu na požadovaný typ v jednom kroku.
* **Jasný návratový typ**: Vrací hodnotu v požadovaném typu nebo `None`, což usnadňuje další zpracování.
* **Volitelná výjimka**: Umožňuje zvolit mezi tichým selháním (vrácení `None`) a explicitní chybou (vyhození výjimky).
* **Konzistence napříč typy**: Stejný přístup pro různé datové typy zjednodušuje kód a zvyšuje jeho čitelnost.

### Práce s databázemi a HTML vstupy

Pro běžné situace, kdy vstupy přicházejí jako řetězce oddělené čárkami
(např. hodnoty z DB, `multiple select`, checkboxy), jsou k dispozici tyto funkce:

* `is_strArray(s, returnAsString=True, throw=False)`
* `is_intArray(s, returnAsString=True, throw=False)`

Slouží k:

* ověření konzistence dat
* převodu mezi stringovou a listovou reprezentací

#### Příklady použití

```python
# Striktní režim

# data z DB / HTML formuláře → list
my_list = JBJH.is_strArray("val1,val2,val3", returnAsString=False, throw=True)
# ['val1', 'val2', 'val3']

# list → string pro uložení do DB
my_str = JBJH.is_strArray(["val1", "val2", "val3"], returnAsString=True, throw=True)
# "val1,val2,val3"
```

## Krátké shrnutí

JBJH není typový systém ani náhrada statického typování.
Je to **normalizační vrstva pro dynamická data**, která:

* sjednocuje práci se vstupy
* eliminuje opakující se `try/except`
* zvyšuje čitelnost a předvídatelnost kódu
