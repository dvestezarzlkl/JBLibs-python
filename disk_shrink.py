import re
from pathlib import Path
from typing import Optional, Tuple, Union

from .c_menu import onSelReturn
from .input import select,select_item,confirm,reset,inputCliSize,cliSize
from .fs_utils import normalizeDiskPath,getDiskByPartition,getDiskPathInfo,partitionInfo
from .helper import runRet,run
from .format import bytesTx

# class ShrinkError(Exception): pass

SECTOR_SIZE = 512
TMP_MOUNT = Path("/mnt/__jb_imgtool_shrink__")


class ShrinkError(Exception):
    """Custom exception for shrink operations."""
    pass

def _parse_sfdisk_dump(dump: str, disk: str, part: int) -> Tuple[str, int, int, int, int]:
    """
    Z dumpu sfdisk -d vytáhne:
      - upravený dump s novou velikostí (zatím vyplníme až ve volajícím)
      - původní start sektoru dané partition
      - původní size (počet sektorů)
      - max_end_sector všech partitions (pro kontrolu „poslední partition“)
      - sektor size

    Vrací: (raw_dump, start_sector, size_sectors, max_end_sector)
    """
    lines = dump.splitlines()
    part_name_no_p = f"{disk}{part}"
    part_name_with_p = f"{disk}p{part}"

    _sector_size= SECTOR_SIZE
    start_sector = None
    size_sectors = None
    max_end = 0

    for line in lines:
        line_stripped = line.strip()
        if line_stripped.startswith("sector-size: "):
            # velikost sektoru
            m = re.match(r"sector-size:\s+(\d+)", line_stripped)
            if m:
                try:                    
                    _sector_size = int(m.group(1))
                except ValueError:
                    _sector_size = SECTOR_SIZE
            continue
        
        if not line_stripped or line_stripped.startswith("#"):
            continue

        # hledáme řádky typu:
        # /dev/loop0p2 : start=..., size=..., type=...
        if line_stripped.startswith(part_name_with_p) or line_stripped.startswith(part_name_no_p):
            # rozsekáme za dvojtečkou
            try:
                _, rest = line_stripped.split(":", 1)
            except ValueError:
                continue

            parts = [p.strip() for p in rest.split(",")]

            for p in parts:
                if p.startswith("start="):
                    start_sector = int(p.split("=")[1])
                if p.startswith("size="):
                    size_sectors = int(p.split("=")[1])

        # zároveň si sbíráme všechny part řádky pro max_end
        if (line_stripped.startswith(disk) and
            (" start=" in line_stripped) and
            (" size=" in line_stripped)):
            # obecné parsování
            try:
                _, rest = line_stripped.split(":", 1)
            except ValueError:
                continue
            parts = [p.strip() for p in rest.split(",")]
            s = None
            sz = None
            for p in parts:
                if p.startswith("start="):
                    s = int(p.split("=")[1])
                if p.startswith("size="):
                    sz = int(p.split("=")[1])
            if s is not None and sz is not None:
                end = s + sz
                if end > max_end:
                    max_end = end

    if start_sector is None or size_sectors is None:
        raise ShrinkError(
            f"Nenašla jsem partition {disk}p{part} v sfdisk dumpu."
        )

    return dump, start_sector, size_sectors, max_end, _sector_size


def _apply_new_size_to_sfdisk_dump(raw_dump: str, disk: str, partition: str, new_sectors: int) -> str:
    """
    Úprava size= u konkrétní partition v sfdisk -d dumpu.
    """
    
    lines = raw_dump.splitlines()
    out = []
    changed = False

    # regex, který ignoruje mezery:
    # size=\s*\d+
    size_re = re.compile(r"(size=\s*)(\d+)")
    partition = normalizeDiskPath(partition)

    for line in lines:
        stripped = line.strip()

        if stripped.startswith(partition):
            # nahradíme pouze size=
            def repl(m):
                return f"{m.group(1)}{new_sectors}"
            new_line, count = size_re.subn(repl, line)
            if count == 0:
                raise ShrinkError(f"Partition řádek nalezen, ale size= nebyl nalezen: {line}")
            line = new_line
            changed = True

        out.append(line)

    if not changed:
        raise ShrinkError("Nepodařilo se upravit size= v řádku partition.")

    return "\n".join(out) + "\n"



def _auto_target_gib_from_used(used_bytes: int) -> int:
    """
    Vypočte cílovou velikost v GiB:
    used + 10 % + min 1 GiB.
    """
    one_gib = 1024 ** 3
    auto = int(used_bytes * 1.10)
    if auto < one_gib:
        auto = one_gib
    # zaokrouhlit nahoru na celé GiB
    target_gib = (auto + one_gib - 1) // one_gib
    return target_gib

def _shrink_partition_common(
    disk: str,
    partition: str,
    part_index: int,
    target_gib: Optional[int],
    minMenuWidth: int = 80,
    autoConfirm: bool = False,
) -> Tuple[int|None, Optional[int]]:
    """
    Společná logika shrinku:
      - zjistí used space
      - spočítá cílovou velikost
      - e2fsck + resize2fs
      - upraví partition tabulku (sfdisk)

    Args:
        disk: /dev/sdX nebo /dev/loopX (celý disk, ne partition!)
        part_index: číslo partition (typicky 2)
        target_gib: cílová velikost v GiB nebo None (auto)

    Returns:
        (None,None) pokud uživatel zrušil operaci
        (target_bytes, new_img_size_bytes_or_None)
        target_bytes = cílová velikost filesystemu v bajtech
        new_img_size_bytes = pokud loop → na kolik by se měl truncate IMG
                             pokud fyzický disk → None
    """
    if not confirm(
        f"Opravdu chcete minimalizovat ext4 filesystem na disku {disk}, partition {part_index} ({partition})?"
    ):
        print("[INFO] Operace zrušena uživatelem.")
        return None, None
    
    disk = normalizeDiskPath(disk)
    partition = normalizeDiskPath(partition)
    
    print(f"[INFO] Shrinking partition {part_index} on {disk}")
    print(f"[INFO] Target size (GiB): {target_gib if target_gib is not None else 'auto'}")    
    
    # vytvoříme mountpoint
    tmp_mount = Path(TMP_MOUNT)
    tmp_mount.mkdir(exist_ok=True, mode=0o755)

    # 1) mount pro zjištění used space
    run(f"sudo mount {partition} {tmp_mount}")
    df_out = runRet(f"df -B1 {tmp_mount}")
    # poslední řádek df je náš FS
    used_bytes = int(df_out.splitlines()[-1].split()[2])
    run(f"sudo umount {tmp_mount}")

    if target_gib is None:
        target_gib = _auto_target_gib_from_used(used_bytes)

    if target_gib < 1:
        raise ShrinkError("Cílová velikost musí být alespoň 1 GiB.")

    target_bytes = target_gib * (1024 ** 3)

    print(f"[INFO] Used: {used_bytes/1e9:.2f} GB")
    print(f"[INFO] Target FS size: {target_bytes/1e9:.2f} GB (≈ {target_gib} GiB)")

    # e2fsck
    run(f"sudo e2fsck -f {partition}")


    # resize2fs
    print(f"[INFO] Resizing ext4 filesystem on {partition} to {target_gib} GiB...")
    o,r,e = runRet(f"sudo resize2fs {partition} {target_gib}G",False)

    # zjistíme velikost bloku
    bs = get_block_size(partition)

    # zkusíme detekovat chybu "smaller than minimum"
    m = re.search(r"New size smaller than minimum \((\d+)\)", str(o) + str(e))

    if m:
        min_blocks = int(m.group(1))
        print(f"[WARN] Cílová velikost je menší než minimální možná ({min_blocks} bloků).")

        new_target_bytes  = min_blocks * bs
        new_target_gib    = (new_target_bytes + (1024**3 - 1)) // (1024**3)
        new_target_gib    += 1  # přidat 1 GiB rezervu a taky místo pro případné úravy při mount a přípravu FS

        print(f"[INFO] Navržená nová cílová velikost: {new_target_gib} GiB")

        if autoConfirm is False:
            if not confirm(f"Chcete pokračovat s velikostí {new_target_gib} GiB?", minMessageWidth=minMenuWidth):
                print("[INFO] Operace zrušena uživatelem.")
                return None, None

        run(f"sudo resize2fs {partition} {new_target_gib}G")
        target_bytes = new_target_bytes

    post_shrink_partition_align(
        partition,
        forceMaxSize=True,
        dryRun=False,
    )
    print(f"[INFO] Shrink operation completed successfully.")
    return target_bytes, None

def post_shrink_partition_align(
    partition: str,
    forceMaxSize:bool=False,
    dryRun:bool=False,
) -> Union[str|None]:
    """
    Provede zarovnání ext4 filesystemu na block size po shrinku.
    Args:
        partition: /dev/sdXn
        forceMaxSize: pokud True, povolí zvětšení partition na max velikost (i když je menší než předchozí), např pro opravu
           kdyý je fs větší než partition.
    Returns:
        None pokud OK
        string s chybou pokud chyba
    """
    nfo=partitionInfo(partition)
    if nfo.ok is False:
        return f"Nepodařilo se načíst informace o partition {partition}."
    
    disk= normalizeDiskPath(nfo.diskInfo.name)
    partition= normalizeDiskPath(partition)
    
    if not nfo.isLastPartition:
        return f"Partition {nfo.partitionInfo.name} není poslední na disku. Zarovnání není potřeba."
    
    # sfdisk -d a úprava partition tabulky
    print(f"[INFO] Updating partition table for disk {nfo.diskInfo.name}...")
            
    o,r,e = runRet(f"sudo sfdisk -d {disk}",False)
    if r != 0:
        raise ShrinkError(f"Chyba při čtení partition tabulky pomocí sfdisk: {e}")
    raw_dump, start_sector, old_size, max_end, sector_size = _parse_sfdisk_dump(
        o, disk, nfo.partitionIndex
    )
    
    extNfo=nfo.getExtendedInfo()
    if extNfo is None:
        return f"Nepodařilo se načíst rozšířené informace o partition {nfo.partitionInfo.name}."
    
    print(f"[INFO] Current ext4 size: {bytesTx(extNfo.total)}")
    new_sectors = extNfo.total // sector_size

    if new_sectors > old_size and forceMaxSize is False:
        raise ShrinkError(
            f"Nová velikost partition ({new_sectors} sektorů) je větší než původní ({old_size})."
        )

    new_dump = _apply_new_size_to_sfdisk_dump(raw_dump, disk, partition, new_sectors)
    
    # aplikace nové partition tabulky
    if dryRun:
        print(f"[INFO] (DRY RUN) Aplikace nové partition tabulky pro disk {disk} ...")
        print(new_dump)
    else:
        run(["sudo", "sfdisk", disk], input_bytes=new_dump.encode("utf-8"))

    print(f"[INFO] Partition {disk}p{nfo.partitionIndex}: start={start_sector}, old_size={old_size}, new_size={new_sectors}")
    print(f"[INFO] Zarovnání partition {nfo.partitionInfo.name} dokončeno.")
    return None

def shrink_disk(
    partition: str,
    spaceSize: Optional[int] = None,
    part_index: Optional[int] = None,
    spaceSizeQuestion: bool = False,
    minMenuWidth: int = 80,    
) -> onSelReturn:
    """
    Shrink ext4 filesystem na fyzickém disku.
    
    Args:
        device: /dev/sdX nebo /dev/sdXn
        spaceSize: cílová velikost v GiB (>=1). Pokud None, použije se automatická volba.
        part_index: číslo partition (pokud device je disk). Pokud None, autodetekce ext4 partition.
        spaceSizeQuestion: pokud True a spaceSize je None, zeptá se uživatele na cílovou velikost.
        
    Returns:
        onSelReturn s výsledkem operace.
        v .data je cílová velikost filesystemu v bajtech (int) nebo 0 při zrušení uživatelem.
        pokud je nastaveno .endMenu = True, tak se jedná o chybu která nevyžaduje anyKay().
    
    """
    ret = onSelReturn()
    
    partition = normalizeDiskPath(partition,True)
    device_info = getDiskByPartition(partition)
    if device_info is None:        
        return ret.errRet(f"Nepodařilo se najít disk pro partition {partition}.", True)
    
    device = normalizeDiskPath(device_info.name)
    
    # kontrola že partititon je ext4
    part_info = None
    idx=None
    for index, part in enumerate(device_info.children):
        if normalizeDiskPath(part.name,True) == partition:
            part_info = part
            idx = index
            break
        
    part_index = idx + 1  # partition index je 1-based
        
    if part_info is None or part_info.fstype != "ext4":
        return ret.errRet(f"Nepodařilo se najít ext4 partition {partition} na disku {device}.", True)
    
    # dotaz na velikost
    if spaceSizeQuestion and spaceSize is None:
        x=select(
            "Zvolte způsob zadání cílové velikosti:",
            [
                select_item("Zadat velikost ručně","m"),
                select_item("Automatická volba","a"),
            ],
        )
        if x.item is None:
            return ret.errRet("Zrušeno uživatelem.", True)
        ans= x.item.choice
        if ans == 'a':
            # automatická volba
            spaceSize = None
        else:
            sz:cliSize = inputCliSize("1G",minMessageWidth=minMenuWidth)
            if sz is None:
                return ret.errRet("Zrušeno uživatelem.", True)
            spaceSize = sz.inGiB
    
    mp=[p for p in part_info.mountpoints if p]
    
    # otestujeme že nemáme připojeno
    if mp:
        return ret.errRet(f"Partition {partition} je připojena na {', '.join(mp)}. Nejprve ji odpojte.", True)

    # Spustit hlavní logiku
    target_bytes, _ = _shrink_partition_common(
        disk=device,
        partition=partition,
        part_index=part_index,
        target_gib=spaceSize,
        minMenuWidth=minMenuWidth,
        autoConfirm=bool(spaceSize is None),
    )
    if target_bytes is None:
        return ret.errRet("Operace shrink byla zrušena uživatelem.", True)

    return ret.okRet(f"[DONE] Disk {device}, partition {part_index} → ≈ {target_bytes/1e9:.2f} GB")


def e2fsck(partition: str) -> onSelReturn:
    """
    Provede kontrolu ext4 filesystemu na zadané partition.
    
    Args:
        partition: /dev/sdXn
        
    Returns:
        onSelReturn s výsledkem operace.
        pokud je nastaveno .endMenu = True, tak se jedná o chybu která nevyžaduje anyKay().
    """
    ret = onSelReturn()
        
    reset()
    print(f"[FSCK] Kontroluji ext4: {partition} ....")
    try:
        x = run(f"sudo e2fsck -f {partition}")
    except Exception as e:
        # pokud chyba obshauje "need terminal for interactive repair", tak pokražujeme
        if "need terminal for interactive repair" in str(e):
            print(f"[INFO] Filesystem na {partition} potřebuje opravu.")
            x= "Please run 'e2fsck -f ..."
        else:
            return ret.errRet(f"Chyba při kontrole ext4 pomocí e2fsck: {e}")
    
    # pokud výstup obsahuje '"Please run 'e2fsck -f" tak je potřeba spustit s force ale jen na dotaz
    x= str(x).lower()
    if "please run 'e2fsck -f" in x:
        if confirm(
            f"Filesystem na {partition} potřebuje automatickou kontrolu.\nSpustit 'e2fsck -f' v módu automatické opravy?.\nPokud zrušíte tak lze v menu provést kontrolu s opravami ručně.",
        ) is False:
            return ret.errRet("Operace zrušena uživatelem.",True)
        try:
            reset()
            run(f"sudo e2fsck -f {partition}")
        except Exception as e:
            return ret.errRet(f"Chyba při vynucené kontrole ext4 pomocí e2fsck -f: {e}")
    
    print(f"[DONE] Kontrola ext4 na {partition} proběhla úspěšně.")
    return ret

def extend_disk_part_max(
    dev_partition: str,
) -> onSelReturn|None:
    """
    Rozšíří ext4 filesystem na fyzickém disku na zadanou velikost v GiB.
    'device' může být disk nebo partition.
    Args:
        dev_partition: /dev/sdX nebo /dev/sdXn
        new_size_gib: nová velikost v GiB (>=1). Pokud None, zvětší se na maximum.
    Returns:
        onSelReturn s výsledkem operace.
        v .data je nová velikost filesystemu v bajtech (int).
        pokud je nastaveno .endMenu = True, tak se jedná o chybu která nevyžaduje anyKay().
    """
    ret = onSelReturn()
    
    dev_partition = normalizeDiskPath(dev_partition,True)
    
    diskInfo=getDiskByPartition(dev_partition)
    if diskInfo is None:
        return ret.errRet(f"Nepodařilo se najít disk pro partition {dev_partition}.", True)
    
    disk= normalizeDiskPath(diskInfo.name)
        
    idx=None
    for index, part in enumerate(diskInfo.children):
        if normalizeDiskPath(part.name,True) == dev_partition and part.fstype == "ext4":
            part_info = part
            idx = index
            break
    if idx is None:
        return ret.errRet(f"Nepodařilo se najít ext4 partition {dev_partition} na disku {disk}.", True)
    
    part_index = idx + 1  # partition index je 1-based

    if idx != len(diskInfo.children)-1:
        return ret.errRet(f"Partition {dev_partition} není poslední na disku {disk}. Nelze automaticky zvětšit na maximum.", True)
   
    print(f"[INFO] Extending partition {part_index} ({dev_partition}) on disk {disk} to size: maximum")
    
    if confirm(
        f"Opravdu chcete rozšířit ext4 filesystem na disku {disk}, partition {part_index} ({dev_partition})?"
    ) is False:
        return ret.errRet("Operace zrušena uživatelem.", True)
        
    dev_partition = normalizeDiskPath(dev_partition,False)
    # grow partition na maximum
    try:
        run(["sudo", "growpart", disk, str(part_index)],terminalActive=False)
    except Exception as e:
        # 'Command failed: sudo growpart /dev/sdb 2\nNOCHANGE: partition 2 is size 1951366543. it cannot be grown\n'
        x= str(e).lower()
        if "nochange" in x and "cannot be grown" in x:
            print(f"[INFO] Partition {dev_partition} již zabírá maximum dostupného místa.")
        else:
            return ret.errRet(f"Chyba při rozšiřování partition pomocí growpart: {e}")

    x= e2fsck(dev_partition)
    if x.hasError:
        return x
    
    # maximize filesystem
    try:
        run(f"sudo resize2fs {dev_partition}")
    except Exception as e:
        return ret.errRet(f"Chyba při rozšiřování ext4 filesystemu pomocí resize2fs: {e}")
    
    
    # zjistit novou velikost
    try:
        tune = runRet(f"tune2fs -l {dev_partition}")
    except Exception as e:
        return ret.errRet(f"Chyba při čtení velikosti ext4 pomocí tune2fs: {e}")
    block_count = None
    block_size = None

    for line in tune.splitlines():
        if line.startswith("Block count:"):
            block_count = int(line.split()[-1])
        elif line.startswith("Block size:"):
            block_size = int(line.split()[-1])

    if block_count is None or block_size is None:
        return ret.errRet("Nepodařilo se přečíst velikost EXT4 z tune2fs.")
        
    ret.data = block_count * block_size
    return ret


def get_block_size(partition: str) -> int | None:
    """
    Získá velikost bloku filesystemu pro daný ext2/ext3/ext4 partition.
    
    Použije rychlý výpis hlavičky:
        dumpe2fs -h /dev/sdxY

    Returns:
        int  -> velikost bloku v bytech (obvykle 4096)
        None -> pokud nelze zjistit (např. není ext FS)
    """
    try:
        o,r,e = runRet(["dumpe2fs", "-h", partition],False)
    except FileNotFoundError:
        raise RuntimeError("dumpe2fs není nainstalováno")

    if r != 0:
        # není ext filesystem, nebo chyba
        return None

    # najdeme řádek "Block size:  4096"
    m = re.search(r"Block size:\s+(\d+)", o)
    if not m:
        return None

    return int(m.group(1))