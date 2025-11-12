# konfigurátor

- script before konfig 
  `^<filename>[ <přepínače>]`  
  fullpathfilename ke scriptu který se spustí před, musí na daném zařízení existovat

- script po instalaci
  `~<filename>[ <přepínače>]`
  fullpathfilename ke scriptu který se sputí nakonec

- změna sys usera pod kterým se pak budou dělat další operace
  `=u <name>`
  
  **toto musí být vždy za názvem sekce pak dle libosti**
- vytvoření usera- přidá uživatele a udělá home/user, nepřepne na něj
  `+u <username>`
- vytvoření usera s přepnutím  
  `!u <username>`


## soubory

**vždy před souborem musí být použito `=d <path>`**

- přepne cestu
  `=d <path>`
- vytvoří cestu - dir
  `+d <path>`
- vytvoří cestu a přepne do ní
  `!d <path>`
- odstraní dir pokud existuje
  `-d <path>`
- přidá soubor jen pokud neexistuje
  `+fl <filename> <nic nebo resource name>`
- přidá nebo přepíše soubor
  `!fl <filename> <nic nebo resource name>`
- odstraní soubor pokud existuje
  `-fl <filename>`
- nastaví práva, skládá se z písmen g,o,u za každým může následovat '+' '-' a 'r', 'w' a 'x' jako u chmod  
    mezi požadavky je povolená jedna mezera
    např: `u+rwx g+r g-wx o-rwx` ale lze zadat i `u+rwxg+rg-wxo-rwx` ale není tak přehledné
    
    | část    | význam                              | výsledek                                  |
    | ------- | ----------------------------------- | ----------------------------------------- |
    | `u+rwx` | přidá `rwx` pro vlastníka           | user dostane všechna práva                |
    | `g+r`   | přidá jen `read` skupině            | ostatní práva skupiny zůstanou beze změny |
    | `g-wx`  | odebere skupině `write` a `execute` | po tomhle kroku má group pouze `r`        |
    | `o-rwx` | odebere všem „others“ všechna práva | ostatní uživatelé = žádná práva           |

    `=acc <filename> <chmod>`




## ssh klíče

*u klíčů se zajistí existence .ssh adr a souboru, klíče se identifikují celým záznamem, takže nejde aktualizovat, je vysoká možnost stejného názvu v klíči*

- přidá klíč do .ssh/authorized_keys
  `+ssh <resource name>`
- odebere klíč
`-ssh <klíč resource name>`

## soubory s credential .g_c

- nastaví cestu pro uložení .g_c, výchozí je ˙~/.creds˙
  `=g <path>`
- url adresa přihlášení, z ní se detekuje cesta podle které se přidává pokud neexistuje
  `+g <resource name>`
- přidá nebo updatuje
  `!g <resource name>`
- odebere
  `-g <resource name>`

## sekce identifikací

- `*a` za tímto následuje konfigurace pro všechny jednotky nezávisle na ID a je vykonána jako první
- `**<id_zarizeni>` # id zařízení - machine id např z hostname
- `??<regexp pro výběr zařízení>`

## sekce resources

`__res__` = označení sekce

Sekce se načítá jako poslední, takže se doporučuje ji mít až na konce, sekce musí být jen jedna a paltí pro všechny ostatní sekce které na resorce odkazují

pak každý řádek musí začínat - a-Z nebo 0-9 `<nazev> <base64Data>` název má podporu jen a-Z 0-9 _ a mínus v textu

## příklad konfigu:
```txt
*a
=u root
+ssh ssh_key_pc1
**zlkl_sun_5433677
=u jen_testy
+g g_key_kiosk
??/_sun_/i
=u jen_testy
+g jsLibs
!d ~/.myTest
+f jmenosouboru.ext mydiledata
__res__
g_key_kiosk base64data
ssh_key_pc1 base64data
jsLibs base64data
myfiledata base64
```
## komentáře

kometační řádky začínajíznakem hashe, jinde komentáře povoleny nejsou

## prázdné řádky

jsou povoleny

