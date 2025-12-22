import os
import datetime
import hashlib
import json
from .jbjh import JBJH
import subprocess
from pathlib import Path
from typing import Any, Dict
from .format import bytesTx
from .helper import runGetObj,runRet
from .c_menu import onSelReturn
from .fs_utils import normalizeDiskPath, getDiskyByName, partitionInfo
from .input import confirm
from .term import text_color,en_color

def raw_backup(
    disk: str,
    outdir: Path,
    autoprefix: bool,
    compression: bool = True,
    cLevel: int = 7,
) -> onSelReturn:
    """
    RAW BACKUP:
      - zálohuje celý disk do jednoho image souboru
      - vytvoří manifest.json
    """
    ret = onSelReturn()
    
    if isinstance(outdir, str):
        outdir = Path(outdir)
           
    # out dir buď nesmí existovat ale musí existovat parent
    # nebo musí být prázdný
    if outdir.exists():
        if not outdir.is_dir():
            return ret.errRet(f"Výstupní cesta {outdir} není adresář.")
    else:
        outdir.mkdir(parents=True, exist_ok=True)
        if not outdir.exists() or not outdir.is_dir():
            return ret.errRet(f"Adresář {outdir.parent} neexistuje.")
            
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    prefix = f"{ts}_" if autoprefix else None
        
    disk = normalizeDiskPath(disk)
    nfo = getDiskyByName(disk)
    if not nfo:
        return ret.errRet(f"Disk {disk} se nepodařilo najít.")
    
    print(f"=== RAW BACKUP {disk} → {outdir} ===")

    size_bytes = int(nfo.size)
    human = str(bytesTx(size_bytes))

    base = f"{nfo.name}.img"
    if prefix:
        base = f"{prefix}_{base}"

    out = outdir / base

    print(f"\n[RAW] Backup disk {disk} ({human})")

    # ------------------------------------------------------------------------------------
    # test volného místa
    # ------------------------------------------------------------------------------------
    stat = os.statvfs(outdir)
    free_space = (stat.f_bavail * stat.f_frsize) * 0.95
    if free_space < size_bytes:
        return ret.errRet(f"Nedostatek místa v {outdir} pro RAW zálohu ({human}).")

    try:
        # ------------------------------------------------------------------------------------
        # Komprese / Nekompresní režim
        # ------------------------------------------------------------------------------------
        if compression and cLevel > 0:
            # === STREAMING DO 7Z ===
            out7z = Path(str(out) + ".7z")
            cmd_dd = ["dd", f"if={disk}", "bs=4M", "status=progress"]
            c_bkp_hlp._stream_to_7z(cmd_dd, out7z, level=cLevel)
            out = out7z

        else:
            # === KLASICKÉ .img ===
            print(f"[INFO] Ukládám RAW IMG → {out}")
            o,r,e = runRet(["dd", f"if={disk}", f"of={out}", "bs=4M", "status=progress"], stdOutOnly=False, noOut=True)
            if r != 0:
                return ret.errRet(f"Chyba při zálohování disku {disk}: {e}")

        # ------------------------------------------------------------------------------------
        # SHA256
        # ------------------------------------------------------------------------------------
        c_bkp_hlp.write_sha256_sidecar(out)
    except Exception as e:
        return ret.errRet(f"Chyba při zálohování disku {disk}: {e}")    

def smart_backup(
    disk: str,
    outdir: Path,
    autoprefix: bool,
    compression: bool = True,
    cLevel: int = 7,
    ddOnly: bool = False,
) -> onSelReturn:
    """
    SMART BACKUP:
      - uloží diskový layout
      - zálohuje každou partition do zvláštního image
      - vytvoří manifest.json
    """
    ret = onSelReturn()
    
    if isinstance(outdir, str):
        outdir = Path(outdir)
           
    # out dir buď nesmí existovat ale musí existovat parent
    # nebo musí být prázdný
    if outdir.exists():
        if not outdir.is_dir():
            return ret.errRet(f"Výstupní cesta {outdir} není adresář.")
    else:
        if not outdir.parent.exists() or not outdir.parent.is_dir():
            return ret.errRet(f"Rodičovský adresář {outdir.parent} neexistuje.")
        outdir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    prefix = f"{ts}_{disk}" if autoprefix else None
    if prefix:
        outdir = outdir / prefix
    outdir.mkdir(parents=True, exist_ok=True) 
    if any(outdir.iterdir()):
        return ret.errRet(f"Výstupní adresář {outdir} musí být prázdný.")        
    
    disk = normalizeDiskPath(disk)
    nfo = getDiskyByName(disk)
    if not nfo:
        return ret.errRet(f"Disk {disk} se nepodařilo najít.")
    
    print(f"=== SMART BACKUP {disk} → {outdir} ===")

    layout_path = c_bkp.backup_layout(disk, outdir)
        
    manifest: Dict[str, Any] = {
        "type": "jb" if ddOnly else "partclone",
        "disk": disk,
        "created": ts,
        "size_bytes": int(nfo.size),
        "size_human": str(bytesTx(int(nfo.size))),
        "layout_file": layout_path.name,
        "partitions": [],
    }
    if not nfo.children:
        return ret.errRet(f"Na disku /dev/{disk} nejsou žádné partitiony.")

    for p in nfo.children:
        if p.type != "part":
            continue
        try:
            entry = c_bkp.backup_partition_image(p.name, outdir, None, compression, cLevel, ddOnly=ddOnly)
        except Exception as e:
            return ret.errRet(f"Chyba při zálohování partition /dev/{p.name}: {e}")
        manifest["partitions"].append(entry)

    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")    
    return ret.okRet(f"SMART BACKUP dokončen. Manifest: {outdir / 'manifest.json'}")


def restore_disk(
    disk: str,
    bkpdir: Path,
    confirmQuery: bool = True,
) -> onSelReturn:
    """
    Obnovení disku z SMART zálohy.
    """
    print(text_color(f"=== RESTORE DISKU {disk} ZE SMART ZÁLOHY {bkpdir} ===", color=en_color.BRIGHT_CYAN))
    ret = onSelReturn()
    
    JBJH.is_str(bkpdir, throw=True)
    JBJH.is_str(disk, throw=True)
    bkpdir = Path(bkpdir)
    disk = normalizeDiskPath(disk)
    
    if not bkpdir.exists() or not bkpdir.is_dir():
        return ret.errRet(f"Zálohovací adresář {bkpdir} neexistuje.")

    manifest_file = bkpdir / "manifest.json"
    if not manifest_file.exists() or not manifest_file.is_file():
        return ret.errRet(f"Zálohovací adresář {bkpdir} neobsahuje manifest.json.")
                    
    disk = normalizeDiskPath(disk)
    nfo = getDiskyByName(disk)
    if not nfo:
        return ret.errRet(f"Disk {disk} se nepodařilo najít.")
    
    print(f"[RESTORE] Načítám manifest ze {manifest_file}")
    
    manifest_data = manifest_file.read_text(encoding="utf-8")
    manifest = json.loads(manifest_data)

    if "partitions" not in manifest:
        return ret.errRet("Manifest neobsahuje žádné partitiony.")
    
    # porovnáme velikost disku a popř zeptáme pokud nesedí velikost že to opravdu chceme
    print(f"[RESTORE] Kontroluji velikost disku...")
    bkp_size = manifest.get("size_bytes", 0)
    curr_size = int(nfo.size) if nfo.size else 0
    if bkp_size != curr_size:
        print(f"[WARNING] Velikost zálohovaného disku ({bytesTx(bkp_size)}) neodpovídá velikosti cílového disku ({bytesTx(curr_size)}).")
        print("Nejspíš se nejedná o zálohu pro tento disk.")
        
        if not confirm("Opravdu chcete pokračovat v obnově?"):
            return ret.errRet("Obnova disku zrušena uživatelem.")

    # kontrola SHA256 všech partition image souborů
    print(f"[RESTORE] Ověřuji SHA256 všech partition image souborů...")
    verify_err = c_bkp.verifyPartitionsByManifest(bkpdir, manifest)
    if verify_err is not None:
        return ret.errRet(verify_err)

    # restore layout
    print(f"[RESTORE] Načítám diskový layout...")
    layout_file:Path = bkpdir / manifest.get("layout_file", "")
    if not layout_file.exists() or not layout_file.is_file():
        return ret.errRet(f"Layout soubor {layout_file} neexistuje.")
    
    if confirmQuery:
        print()
        print(text_color(f" [RESTORE] Upozornění: Obnova disku {disk} přepíše veškerá data na tomto disku! ", color=en_color.BRIGHT_RED, inverse=True, bold=True))
        if not confirm("Opravdu chcete pokračovat v obnově disku?"):
            return ret.errRet("Obnova disku zrušena uživatelem.")
    
    print(f"\n[RESTORE] Obnovuji diskový layout ze {layout_file}")
    if layout_file.suffix == ".gpt":
        cmd_layout = ["sgdisk", f"--load-backup={str(layout_file)}", disk]
    else:
        # předpokládáme sfdisk
        cmd_layout = ["sfdisk", disk, "<", str(layout_file)]
    o,r,e = runRet(cmd_layout, stdOutOnly=False, noOut=True)
    if r != 0:
        return ret.errRet(f"Chyba při obnově diskového layoutu: {e}")
    # restore partitions
    print("\n[RESTORE] Obnovuji partitiony...")
    for p_entry in manifest["partitions"]:
        p_entry:Dict[str,Any]
        part_dev = normalizeDiskPath(p_entry["name"])
        image_file:Path = bkpdir / p_entry["image"]
        if not image_file.exists() or not image_file.is_file():
            return ret.errRet(f"Image soubor {image_file} pro partition {part_dev} neexistuje.")
        
        try:
            c_bkp.restore_partition_image(
                part_dev,
                image_file,
                bkp_type=p_entry.get("bkp_type", None),
            )
        except Exception as e:
            return ret.errRet(f"Chyba při obnově partition {part_dev}: {e}")

    return ret.okRet("Obnova disku dokončena.")

class c_bkp:

    # restore funkce na základě bkp_type, a přípony souboru
    @staticmethod
    def restore_partition_image(
        part_dev: str,
        image_file: Path,
        bkp_type: str | None = None,
    ) -> None:
        """
        Obnoví partition z image souboru.
        Parameters:
            part_dev (str): Cesta k partition device (např. /dev/sda1)
            image_file (Path): Cesta k image souboru
            bkp_type (str | None): Typ zálohy ("partclone" nebo "dd"). Pokud None, určí se podle přípony souboru.
        Returns:
            None
        """
        if not bkp_type in ("partclone", "dd"):
            # název je <cesta>/<timestamp>_<disk>_<partition>.<typ>.img[.7z]
            # kde typ je "pcn" pro partclone, nebo "dd" pro dd
            if bkp_type is None:
                if image_file.suffix == ".7z":
                    stem = image_file.stem  # odstraní .7z
                else:
                    stem = image_file.name
                if stem.endswith(".pcn.img"):
                    bkp_type = "partclone"
                elif stem.endswith(".dd.img"):
                    bkp_type = "dd"
                else:
                    raise ValueError(f"Nepodařilo se určit typ zálohy partition {part_dev} podle názvu souboru: {image_file}")
            else:
                raise ValueError(f"Neznámý typ zálohy partition {part_dev}: {bkp_type}")
        
        nfo=partitionInfo(part_dev)
        if nfo.ok is False:
            raise RuntimeError(f"Nepodařilo se získat informace o partition {part_dev}")
        
        part_dev= normalizeDiskPath(part_dev)
        print(f"Velikost partition {part_dev}: {bytesTx(int(nfo.partitionInfo.size))}")
        
        print(text_color(f"\n[RESTORE] Obnovuji partition {part_dev} ze {image_file}", color=en_color.YELLOW))
        # Obnova partition
        # partclone a dd vychází z bkp_type
        # jestli stramujeme ze 7z nebo ne, to se určí podle přípony souboru
        if bkp_type == "partclone":
            if image_file.suffix == ".7z":
                print(text_color(f"[RESTORE] Obnova partition {part_dev} ze {image_file} pomocí partclone a 7z", color=en_color.BRIGHT_BLACK))
                cmd_restore = [
                    "7z", "x", "-so", str(image_file), "|",
                    "partclone.restore",
                    "-s",
                    "-",
                    "-o",
                    part_dev,
                ]
            else:
                print(text_color(f"[RESTORE] Obnova partition {part_dev} ze {image_file} pomocí partclone", color=en_color.BRIGHT_BLACK))
                cmd_restore = [
                    "partclone.restore",
                    "-s",
                    str(image_file),
                    "-o",
                    part_dev,
                ]
        elif bkp_type == "dd":
            if image_file.suffix == ".7z":
                print(text_color(f"[RESTORE] Obnova partition {part_dev} ze {image_file} pomocí dd a 7z", color=en_color.BRIGHT_BLACK))
                cmd_restore = [
                    "7z", "x", "-so", str(image_file), "|",
                    "dd",
                    f"of={part_dev}",
                    "bs=4M",
                    "status=progress",
                ]
            else:
                print(text_color(f"[RESTORE] Obnova partition {part_dev} ze {image_file} pomocí dd", color=en_color.BRIGHT_BLACK))
                cmd_restore = [
                    "dd",
                    f"if={str(image_file)}",
                    f"of={part_dev}",
                    "bs=4M",
                    "status=progress",
                ]
        else:
            raise ValueError(f"Neznámý typ zálohy partition {part_dev}: {bkp_type}")
        
        o,r,e = runRet(" ".join(cmd_restore), stdOutOnly=False, noOut=True)
        if r != 0:
            raise RuntimeError(f"Chyba při obnově partition {part_dev}: {e}")
        print(text_color(f"[RESTORE] Obnova partition {part_dev} dokončena.", color=en_color.GREEN))
        
    @staticmethod
    def verifyPartitionsByManifest(
        bkpdir: Path,
        manifest: Dict[str, Any],
    ) -> None|str:
        """
        Ověří SHA256 všech partition image souborů podle manifestu.
        Vrací None pokud je vše v pořádku, nebo chybovou hlášku pokud něco neodpovídá.
        Parameters:
            bkpdir (Path): Cesta k zálohovacímuu adresáři
            manifest (Dict[str, Any]): Načtený manifest.json
        Returns:
            None|str: None pokud je vše v pořádku, nebo chybová hláška pokud něco neodpovídá.
        """
        if "partitions" not in manifest:
            return "Manifest neobsahuje žádné partitiony."
        
        print(text_color(f"[VERIFY] Ověřuji SHA256 všech partition image souborů...", color=en_color.YELLOW))
        for p_entry in manifest["partitions"]:
            image_file:Path = bkpdir / p_entry["image"]
            if not image_file.exists() or not image_file.is_file():
                return f"Image soubor {image_file} pro partition neexistuje."
            print(text_color(f"[VERIFY]  - Ověřuji {image_file}...", color=en_color.YELLOW))
            try:
                if not c_bkp_hlp.verify_sha256_sidecar(image_file):
                    return f"[ERROR] SHA256 neodpovídá pro {image_file}."
            except Exception as e:
                return f"[ERROR] Chyba při ověřování SHA256 pro {image_file}: {e}"
            print(text_color(f"[VERIFY]  - SHA256 OK pro {image_file}.", color=en_color.GREEN))
        return None

    @staticmethod
    def backup_layout(disk: str, folder: Path) -> Path:
        """
        Záloha GPT nebo MBR layoutu do souboru.
        Upřednostňuje GPT (sgdisk), jinak sfdisk.
        """
        dev = normalizeDiskPath(disk)
        gpt_file = folder / "layout.gpt"
        try:
            runGetObj(["sgdisk", f"--backup={gpt_file}", dev], raiseOnError=True)
            return gpt_file
        except subprocess.CalledProcessError:
            sfd_file = folder / "layout.sfdisk"
            data = runGetObj(["sfdisk", "-d", dev], raiseOnError=True).stdout
            sfd_file.write_bytes(data)
            return sfd_file

    @staticmethod
    def backup_partition_image(
        devName: str,
        folder: Path,
        prefix: str | None,
        compression: bool = True,
        cLevel: int = 7,
        ddOnly: bool = False,
    ) -> Dict[str, Any]:

        devPath = normalizeDiskPath(devName)
        nfo = partitionInfo(devPath)
        if nfo.ok is False:
            raise RuntimeError(
                f"Nepodařilo se získat informace o partition {devPath}: {nfo.errmsg}"
            )

        if compression:
            cLevel = JBJH.is_int(cLevel, throw=True)
            JBJH.checkMinMax(cLevel, 0, 9, True)

        fs = nfo.partitionInfo.fstype
        size_bytes = int(nfo.partitionInfo.size) if nfo.partitionInfo.size else 0
        human = str(bytesTx(size_bytes))

        print(f"\n[SMART] Backup partition {devPath} ({fs}, {human})")

        # ------------------------------------------------------------------------------------
        # Výběr zdrojového programu (partclone nebo dd)
        # ------------------------------------------------------------------------------------
        pc_prog = None if ddOnly else c_bkp_hlp.program_for_fs(fs)

        if pc_prog:
            print(f"[INFO] Používám {pc_prog} (partclone).")
            src_cmd = [pc_prog, "-c", "-s", devPath, "-o", "-"]  # stream na stdout
        else:
            print("[INFO] Používám dd.")
            src_cmd = ["dd", f"if={devPath}", "bs=4M", "status=progress"]

        # ------------------------------------------------------------------------------------
        # Vytvoření výstupního jména souboru
        # ------------------------------------------------------------------------------------
        typ="pcn" if pc_prog else "dd"
        base = f"{nfo.diskName}_{nfo.partitionName}.{typ}.img"
        if prefix:
            base = f"{prefix}_{base}"

        out = folder / base

        # ------------------------------------------------------------------------------------
        # Komprese / Nekompresní režim
        # ------------------------------------------------------------------------------------
        if compression and cLevel > 0:
            # === STREAMING DO 7Z ===
            out7z = Path(str(out) + ".7z")
            c_bkp_hlp._stream_to_7z(src_cmd, out7z, level=cLevel)
            out = out7z

        else:
            # === KLASICKÉ .img ===
            # test volného místa (jen když ukládáme nekomprimované)
            stat = os.statvfs(folder)
            free_space = (stat.f_bavail * stat.f_frsize) * 0.95
            if free_space < size_bytes:
                raise RuntimeError(
                    f"Nedostatek místa v {folder} pro nekomprimovanou zálohu ({human})."
                )

            print(f"[INFO] Ukládám RAW IMG → {out}")
            o,r,e = runRet(src_cmd + ["of=" + str(out)], stdOutOnly=False, noOut=True)
            if r != 0:
                raise RuntimeError(f"Chyba při zálohování partition {devPath}: {e}")

        # ------------------------------------------------------------------------------------
        # SHA256
        # ------------------------------------------------------------------------------------
        c_bkp_hlp.write_sha256_sidecar(out)

        return {
            "name": devName,
            "devpath": devPath,
            "fstype": fs,
            "size_bytes": size_bytes,
            "size_human": human,
            "image": out.name,
            "sha256_file": out.name + ".sha256",
            "bkp_type" : "partclone" if pc_prog else "dd",
            "compress_level": cLevel if compression and cLevel > 0 else 0,
        }
        
class c_bkp_hlp:
    
    
    
    @staticmethod
    def program_for_fs(fs: str) -> str | None:
        """Vrátí vhodný partclone.* binárku pro daný FS, nebo None."""
        fs = fs.lower()
        if fs in ("ext2", "ext3", "ext4"):
            return "partclone.extfs"
        if fs in ("vfat", "fat", "fat32"):
            return "partclone.vfat"
        if fs == "ntfs":
            return "partclone.ntfs"
        # další FS lze doplnit podle potřeby
        return None
    
    @staticmethod
    def sha256_file(path: Path) -> str:
        """Vypočítá SHA256 pro daný soubor."""
        print(f"[SHA256] Vypočítávám SHA256 pro {path}...")
        h = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    
    @staticmethod
    def verify_sha256_sidecar(path: Path) -> bool:
        """Ověří SHA256 soubor proti .sha256 sidecaru. Vrací True pokud souhlasí."""
        sidecar = path.with_suffix(path.suffix + ".sha256")
        if not sidecar.exists() or not sidecar.is_file():
            raise FileNotFoundError(f"Soubor {sidecar} neexistuje.")
        
        expected_line = sidecar.read_text(encoding="utf-8").strip()
        expected_hash, expected_name = expected_line.split("  ", 1)
        if expected_name != path.name:
            raise ValueError(f"Název souboru v {sidecar} neodpovídá: {expected_name} != {path.name}")
        
        actual_hash = c_bkp_hlp.sha256_file(path)
        return actual_hash == expected_hash
    
    @staticmethod
    def write_sha256_sidecar(path: Path) -> None:
        """Vytvoří <soubor>.sha256 s hash + názvem souboru."""
        digest = c_bkp_hlp.sha256_file(path)
        sidecar = path.with_suffix(path.suffix + ".sha256")
        sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        # print(f"[SHA256] {sidecar} ({digest})")
    
    @staticmethod
    def update_sha256_sidecar(path: Path, throwOnMissing: bool = True) -> None:
        """Aktualizuje existující .sha256 soubor pro daný soubor."""
        sidecar = path.with_suffix(path.suffix + ".sha256")
        if not sidecar.exists():
            if throwOnMissing:
                raise FileNotFoundError(f"Soubor {sidecar} neexistuje.")
            else:
                return            
        digest = c_bkp_hlp.sha256_file(path)
        sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    
    @staticmethod
    def _stream_to_7z(cmd_source: list[str], out_file: Path, level: int = 7):
        """
        Pustí např. dd nebo partclone a výstup přímo streamuje do 7z
        bez mezisouboru.
        """
        cmd_7z = [
            "7z", "a",
            "-t7z",
            "-m0=lzma2",
            f"-mx={level}",
            "-si",
            str(out_file)
        ]

        print(f"[INFO] Stream: {' '.join(cmd_source)} | {' '.join(cmd_7z)}")

        p1 = subprocess.Popen(cmd_source, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(cmd_7z, stdin=p1.stdout)
        p1.stdout.close()
        p2.wait()

        if p2.returncode != 0:
            raise RuntimeError("Chyba při kompresi streamu do 7z.")
    