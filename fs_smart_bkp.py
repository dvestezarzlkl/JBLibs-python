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

def smart_backup(
    disk: str,
    outdir: Path,
    autoprefix: bool,
    compression: bool = True,
    cLevel: int = 7,
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
    
    ts = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    prefix = f"{ts}_{disk}" if autoprefix else None
    if prefix:
        outdir = outdir / prefix
        
    # out dir buď nesmí existovat ale musí existovat parent
    # nebo musí být prázdný
    if outdir.exists():
        if not outdir.is_dir():
            return ret.errRet(f"Výstupní cesta {outdir} není adresář.")
        if any(outdir.iterdir()):
            return ret.errRet(f"Výstupní adresář {outdir} musí být prázdný.")        
    else:
        if not outdir.parent.exists() or not outdir.parent.is_dir():
            return ret.errRet(f"Rodičovský adresář {outdir.parent} neexistuje.")
        outdir.mkdir(parents=True, exist_ok=True)
    
    disk = normalizeDiskPath(disk)
    nfo = getDiskyByName(disk)
    if not nfo:
        return ret.errRet(f"Disk {disk} se nepodařilo najít.")
    
    print(f"=== SMART BACKUP {disk} → {outdir} ===")

    layout_path = c_bkp.backup_layout(disk, outdir)
        
    manifest: Dict[str, Any] = {
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
            entry = c_bkp.backup_partition_image(p.name, outdir, None, compression, cLevel)
        except Exception as e:
            return ret.errRet(f"Chyba při zálohování partition /dev/{p.name}: {e}")
        manifest["partitions"].append(entry)

    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")    
    return ret.okRet(f"SMART BACKUP dokončen. Manifest: {outdir / 'manifest.json'}")
class c_bkp:

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

        base = f"{nfo.diskName}_{nfo.partitionName}.img"
        if prefix:
            base = f"{prefix}_{base}"

        out = folder / base

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
            if o != 0:
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
        h = hashlib.sha256()
        with path.open("rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                if not block:
                    break
                h.update(block)
        return h.hexdigest()    
    
    @staticmethod
    def write_sha256_sidecar(path: Path) -> None:
        """Vytvoří <soubor>.sha256 s hash + názvem souboru."""
        digest = c_bkp_hlp.sha256_file(path)
        sidecar = path.with_suffix(path.suffix + ".sha256")
        sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        # print(f"[SHA256] {sidecar} ({digest})")
    
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
    