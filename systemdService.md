# Skript pro správu `systemd` služeb a časovačů

## Úvod

Tento Python skript poskytuje nástroje pro správu `systemd` služeb a časovačů na systémech Linux. Pomocí těchto nástrojů můžete snadno vytvářet, spouštět, zastavovat, povolovat nebo zakazovat systémové jednotky (services) a časovače (timers). Celý skript je navržen tak, aby umožnil efektivní manipulaci s jednotkami `systemd` přímo z Pythonu.

generováno pomocí *ChatGPT 4o Canvas'

## Strom tříd

- `c_unitsRetRow`: Třída pro reprezentaci řádku z výsledků `systemctl list-units`.
- `c_unitsFilesRetRow`: Třída pro reprezentaci řádku z výsledků `systemctl list-unit-files`.
- `c_unit`: Hlavní třída sdílených operací nad `systemd` jednotkami.
  - `c_service`: Třída pro správu `systemd` služeb, dědí z hlavní třídy `c_unit`.
  - `c_timer`: Třída pro správu časovačů, dědí všechny vlastnosti a metody třídy `c_unit`.
- `strTime`: Třída pro reprezentaci a převod časových hodnot.
- `bytesTx` a `bytes`: Třídy pro reprezentaci a převod hodnot v bajtech.
- `c_header`: Třída pro správu metadat služeb.
- `c_service_status` a `c_timer_status`: Třídy pro reprezentaci stavu služeb a časovačů.

## Popis tříd

### `c_unitsRetRow`

Třída `c_unitsRetRow` slouží k reprezentaci řádku z výsledků příkazu `systemctl list-units`. Tento příkaz zobrazí informace o aktuálních jednotkách, které jsou na systému spuštěny nebo povoleny. Třída obsahuje atributy, jako jsou:

- `unit`: Název jednotky.
- `load`: Stav načtení jednotky.
- `active`: Aktuální stav aktivity jednotky.
- `sub`: Podrobnější stav jednotky.
- `description`: Popis jednotky.

### `c_unitsFilesRetRow`

Třída `c_unitsFilesRetRow` reprezentuje řádek z výsledků příkazu `systemctl list-unit-files`. Tento příkaz vypisuje seznam dostupných souborů jednotek, jejich stavy a zda jsou povoleny nebo zakázány. Atributy zahrnují:

- `unit_file`: Název souboru jednotky.
- `enabled_str`: Textové vyjádření povolení jednotky (např. "enabled").
- `enabled`: Boolean vyjádření, zda je jednotka povolena.
- `vendor_preset_str`: Textový přednastavený stav jednotky.
- `vendor_preset`: Boolean vyjádření přednastavení od výrobce.

### `strTime`

Třída `strTime` slouží k reprezentaci časových hodnot ve formátu textu nebo mikrosekund. Obsahuje metody pro převod mezi různými časovými jednotkami (např. sekundy, milisekundy) a umožňuje práci s časovými hodnotami jako s celými čísly v mikrosekundách.

#### Metody `strTime`

- `decode(fromTx: str) -> int`: Převádí textový čas na mikrosekundy.
- `encode(uSec: int) -> str`: Převádí mikrosekundy na textový čas ve formátu jako "1m 30sec".
- `getUSec() -> int`: Vrací čas v mikrosekundách.
- `getMSec() -> float`: Vrací čas v milisekundách.
- `getSec() -> float`: Vrací čas v sekundách.
- `setUSec(value: int)`: Nastaví čas v mikrosekundách.
- `setMSec(value: float)`: Nastaví čas v milisekundách.
- `setSec(value: float)`: Nastaví čas v sekundách.

### `bytesTx` a `bytes`

Třídy `bytesTx` a `bytes` slouží k reprezentaci hodnot v bajtech a poskytují metody pro převod mezi textovým a číselným formátem.

#### Metody

- `decode(fromTx: str) -> int`: Převádí textový řetězec s jednotkou (např. "1K", "10M") na počet bajtů.
- `encode(value: int, precision: int = 2) -> str`: Převádí počet bajtů na textový řetězec s příslušnou jednotkou.
- `get() -> int`: Vrací počet bajtů.
- `set(value: int)`: Nastaví počet bajtů.

### `c_service`

Třída `c_service` je třídou pro správu `systemd` služeb, dědí z hlavní třídy `c_unit`. Poskytuje metody pro:

- Zjištění existence služby (`exists`).
- Povolení (`enable`) a zakázání (`disable`) služby.
- Spuštění (`start`), zastavení (`stop`) a restartování (`restart`) služby.
- Vytvoření nové služby (`create`, `createFromFile`) a odstranění (`remove`).

#### Parametry metody `create` (`c_service`)

- **description**: Popis služby, zobrazí se ve výsledcích `systemctl`.
- **execStart**: Příkaz nebo cesta k aplikaci, která se má spustit jako služba.
- **startLimitInterval**: Časový interval pro omezení počtu opakovaných spuštění.
- **startLimitBurst**: Počet povolených opakovaných spuštění během intervalu.
- **workingDirectory**: Pracovní adresář pro spouštění služby.
- **user**: Uživatel, pod kterým bude služba spouštěna.
- **group**: Skupina, pod kterou bude služba spouštěna.
- **restart**: Podmínky pro restartování služby (`on-failure`, `always`, atd.).
- **after**: Služba nebo cíl, které musí být spuštěny před touto službou.
- **next_unit_params, next_service_params, next_install_params**: Slovníky pro specifikaci dalších parametrů jednotlivých sekcí konfiguračního souboru.

### `c_timer`

Třída `c_timer` dědí z `c_unit` a rozšiřuje ji o vlastnosti a metody pro práci s časovači `systemd`. Tato třída umožňuje:

- Zjištění existence časovače (`exists`).
- Povolení (`enable`) a zakázání (`disable`) časovače.
- Spuštění (`start`), zastavení (`stop`) a restartování (`restart`) časovače.
- Vytvoření nového časovače (`create`, `createFromFile`) a odstranění (`remove`).

#### Parametry metody `create` (`c_timer`)

- **description**: Popis časovače, zobrazí se ve výsledcích `systemctl`.
- **onCalendar**: Definice času nebo frekvence spouštění časovače (např. "daily", "*-*-* 00:00:00").
- **accuracy**: Definuje přesnost spuštění časovače, např. "1m" znamená, že časovač může být spuštěn s přesností na jednu minutu.
- **randomizedDelay**: Přidává náhodné zpoždění ke spuštění časovače.
- **unit**: Služba, kterou časovač spouští. Pokud není zadáno, časovač automaticky propojí se službou stejného názvu.
- **next_unit_params, next_timer_params, next_install_params**: Slovníky pro specifikaci dalších parametrů jednotlivých sekcí konfiguračního souboru.

### `c_header`

Třída `c_header` slouží pro správu metadat služeb, jako jsou verze, autor, a datum vytvoření. Tato metadata mohou být zahrnuta do konfiguračních souborů služeb.

#### Metody `c_header`

- `loadFromStr(content: str)`: Načte metadata ze zadaného textového obsahu.
- `toStr() -> str`: Vrátí textový řetězec reprezentující metadata.
- `checkVersion(toVersion: str) -> int`: Porovná verzi s jinou verzí a vrátí výsledek porovnání.

### `c_service_status` a `c_timer_status`

Tyto třídy dědí z `c_unit_status` a slouží k reprezentaci specifických stavů pro služby a časovače. Obsahují další atributy, jako jsou:

- **MainPID**: Hlavní PID procesu služby.
- **MemoryCurrent**: Aktuální využití paměti.
- **CPUUsageNSec**: Využití CPU v mikrosekundách od spuštění služby.
- **NextElapseUSecRealtime** (pouze pro `c_timer_status`): Čas, kdy bude časovač příště spuštěn.

## Třída `c_unit`

### Statické funkce

#### `c_unit.s_units(serviceName: str) -> List[c_unitsRetRow]`

Tato statická funkce slouží k získání seznamu jednotek `systemd` pomocí příkazu `systemctl list-units`. Funkce vrací seznam objektů třídy `c_unitsRetRow`, které reprezentují jednotlivé řádky výsledků příkazu. Jako parametr přijímá název služby nebo časovače, přičemž rozlišení probíhá na základě přípony (`.service` nebo `.timer`).

#### `c_unit.s_units_files(serviceName: str) -> List[c_unitsFilesRetRow]`

Tato statická funkce slouží k získání seznamu jednotkových souborů pomocí příkazu `systemctl list-unit-files`. Funkce vrací seznam objektů třídy `c_unitsFilesRetRow`, které reprezentují jednotlivé řádky výsledků příkazu. Jako parametr přijímá název služby nebo časovače, přičemž rozlišení probíhá na základě přípony (`.service` nebo `.timer`).

## Závěr

Tento manuál popisuje strukturu tříd a hlavní funkce pro správu `systemd` služeb a časovačů. Třídy `c_service` a `c_timer` umožňují efektivní práci s jednotkami a časovači přímo z Pythonu, což poskytuje flexibilitu při automatizaci správy služeb na systémech Linux. Kromě základních operací jako je spouštění, zastavování nebo povolování služeb, poskytují třídy nástroje pro detailní práci s konfigurací a sledování stavu. Díky tomu mohou vývojáři snadno vytvářet a spravovat služby, definovat jejich parametry a sledovat jejich stav. To vše je integrováno do intuitivního rozhraní, které usnadňuje práci s `systemd` přímo z vašeho kódu.
