from dataclasses import dataclass
import subprocess
import json
import re
from typing import List, Optional, Union
from .format import bytesTx
from pathlib import Path
from .helper import runRet,run


class fsInfo_ret:
    def __init__(
        self,
        total:int,
        used:int,
        free:int,
        usePercent:float,
        fsType:str="",
    ):
        self.total=total
        self.used=used
        self.free=free
        self.usePercent=usePercent
        self.fsType=fsType

class partitionInfo():
    """Popis partition.
    Args:
        partition (str): Partition (např. /dev/sda1) nebo název (sda1).
    Raises:
        ValueError: pokud partition není validní string.
    Attributes:
        partitionName (str): Název partition bez /dev/ prefixu (např. sda1).
        partitionPath (str): Plná cesta k partition (např. /dev/sda1).
        diskInfo (lsblkDiskInfo|None): Info o disku, na kterém je partition.
        diskName (str|None): Název disku (např. sda).
        diskPath (str|None): Plná cesta k disku (např. /dev/sda).
        partitionInfo (lsblkDiskInfo|None): Info o partition.
        partitionIndex (int|None): Index partition na disku (1,2,3...).
        isLastPartition (bool): Je to poslední partition na disku?
        isPartitionExt4 (bool): Je to ext4 partition?
    """
    
    def __init__(
        self,
        partition:str,
    ):
        """Inicializace partitionInfo.
        Args:
            partition (str): Partition (např. /dev/sda1) nebo název (sda1).
        Raises:
            ValueError: pokud partition není validní string.
        """
        
        self.ok:bool = False
        
        if not isinstance(partition, str):
            raise ValueError("partition musí být string")
        partition=partition.strip()
        if not partition or len(partition)<2:
            raise ValueError("partition nesmí být prázdný string a musí mít alespoň 2 znaky")
        
        self.partitionName:str = normalizeDiskPath(partition, True)
        """Název partition neobsahuje prefix /dev/"""
        
        self.partitionPath:str = normalizeDiskPath(partition)
        """Plná cesta k partition (např. /dev/sda1)"""
        
        self.diskInfo:lsblkDiskInfo|None = getDiskByPartition(self.partitionPath)
        """Info o disku, na kterém je partition."""
        
        self.diskName:str|None = normalizeDiskPath(self.diskInfo.name,True)
        """Název disku (např. sda)"""
        
        self.diskPath:str|None = normalizeDiskPath(self.diskInfo.name)
        """Plná cesta k disku (např. /dev/sda)"""
        
        self.partitionInfo:lsblkDiskInfo|None = None
        """Info o partition."""
        
        self.partitionIndex:int|None = None
        """Index partition na disku (1,2,3...)"""
        
        self.isLastPartition:bool = False
        """Je to poslední partition na disku?"""
        
        self.isPartitionExt4:bool = False
        """Je to ext4 partition?"""
                
        if self.diskInfo and self.diskInfo.children:
            for idx, part in enumerate(self.diskInfo.children):
                if part.name == self.partitionName or normalizeDiskPath(part.name, False) == self.partitionName:
                    self.partitionInfo = part
                    self.partitionIndex = idx + 1
                    self.isLastPartition = (idx == len(self.diskInfo.children) - 1)
                    self.isPartitionExt4 = (part.fstype == 'ext4')
                    break
        
        self.ok = self.partitionInfo is not None and self.diskInfo is not None
        
        __extPartInfo: Optional[fsInfo_ret] = None
        
    def getExtendedInfo(self) -> Optional[fsInfo_ret]:
        """Získá rozšířené info o partition (velikost, použití, atd.) pokud je ext4.
        Returns:
            Optional[fsInfo_ret]: Rozšířené info o partition nebo None pokud není ext4 nebo nelze získat info.
        """
        if not self.isPartitionExt4:
            return None
        if self.partitionInfo is None:
            return None
        return getExtSize(self.partitionPath)
            
    def setLabel(self, label:str) -> bool:
        """Nastaví label partition.
        Args:
            label (str): Nový label.
        Returns:
            bool: True pokud se podařilo nastavit label, False pokud ne.
        """
        if self.partitionInfo is None:
            return False
        return setPartitionLabel(self.partitionPath, label)

class lsblkError(Exception):
    """Custom exception for lsblk errors."""
    pass

class lsblkDiskInfo:
    """popis disku z lsblk"""
    def __init__(
        self,
        name:str,
        label:str,
        size:int,
        fstype:str,
        type:str,
        uuid:str,
        partuuid:str,        
        mountpoints:Union[List[str]],
        parent:Optional[str]=None,
        children:List['lsblkDiskInfo']=[]
    ):
        self.name: str = name
        """Název disku/partition (např. sda, sda1)"""
        
        self.label = label
        """Label disku/partition"""
        
        self.size: int = size
        """Velikost disku/partition v bytech"""
        
        self.fstype: str = fstype
        """Typ filesystému (např. ext4, ntfs)"""
        
        self.uuid: str = uuid
        """UUID disku/partition"""
        
        self.partuuid: str = partuuid
        """PARTUUID disku/partition"""
        
        self.mountpoints : List[str] = mountpoints
        """Seznam mountpointů disku/partition"""
        
        self.parent: Optional[str] = parent
        """Název rodičovského disku (např. sda) pokud je to partition"""
        
        self.type: str = type
        """Typ zařízení (disk, part, loop)"""
        
        mp = mountpoints or []
        if isinstance(mp, str):
            mp = [mp]
        self.mountpoints = mp 
        if not isinstance(self.mountpoints, list):
            self.mountpoints = []
        # vyčistíme mountpoints, protože může obsahovat None nebo prázdné stringy
        self.mountpoints = [m for m in self.mountpoints if m and isinstance(m, str)]
                    
        self.children = children
        if not isinstance(self.children, list):
            self.children = []
            
    @property
    def haveMountPoints(self) -> bool:
        """Vrátí True pokud má daný disk/partition nějaké mountpointy."""
        return len(self.mountpoints) > 0
    
    @property
    def haveAnyMountPoints(self) -> bool:
        """Vrátí True pokud má daný disk/partition nebo některé z jeho children nějaké mountpointy."""
        if self.haveMountPoints:
            return True
        for child in self.children:
            if child.haveMountPoints:
                return True
        return False
    
    @property
    def haveChildren(self) -> bool:
        """Vrátí True pokud má disk/partition nějaké children."""
        return len(self.children) > 0
        
    def __repr__(self):
        sz=bytesTx(self.size)
        mountPoints=len(self.mountpoints)
        childs=len(self.children)
        childsLst=[child.name for child in self.children]
        return f"lsblkDiskInfo(tp:{self.type}, nm={self.name}, label={self.label}, sz={sz}, fstp={self.fstype}, uuid={self.uuid}, partuuid={self.partuuid}, mountpoints={mountPoints}, children={childs} {childsLst})"

def normalizeDiskPath(disk: str, noDevPath:bool=False) -> str:
    """Normalizuje diskovou cestu na /dev/sdX formát.
    Args:
        disk (str): Cesta k disku (např. sda, /dev/sda).
        noDevPath (bool): Pokud:
            - True, vrátí cestu 'sda' bez /dev/ prefixu.
            - False, vrátí cestu '/dev/sda' s /dev/ prefixem.
    Returns:
        str: Normalizovaná cesta k disku.        
    """
    if not disk.startswith("/dev/"):
        disk = "/dev/" + disk
        
    if noDevPath:
        disk = disk.replace("/dev/","")
        
    return disk

def __lsblk_process_node(node:dict,parent:Optional[lsblkDiskInfo]=None,) -> Optional[lsblkDiskInfo]:
    """Process a single lsblk node and return lsblkDiskInfo or None.
    Args:
        node (dict): LSBLK node dictionary.
        parent (Optional[lsblkDiskInfo]): Parent disk info.
        ignoreSysDisks (bool): If True, ignore system disks used for / and /boot.
    Returns:
        Optional[lsblkDiskInfo]: Processed lsblkDiskInfo object or None.
    """    
    if node['type'] in ['disk','part','loop']:
        return lsblkDiskInfo(
            type=node.get('type',''),
            name=node.get('name', ''),
            label=node.get('label', ''),
            size=int(node.get('size', 0)),
            fstype=node.get('fstype', ''),
            uuid=node.get('uuid', ''),
            partuuid=node.get('partuuid', ''),
            mountpoints=node.get('mountpoints', []),
            parent=parent.name if parent else None,
            children=[]
        )
    return None
    
def __lsblk_chekNameMatch(
    name:str,
    filterDev:Optional[re.Pattern]=None,
    filterDevIsRegex:bool=True
) -> bool:
    """Check if the given name matches the filterDev.
    Args:
        name (str): The name to check.
        filterDev (Optional[re.Pattern]): The filter pattern.
        filterDevIsRegex (bool): If True, treat filterDev as regex pattern.
    Returns:
        bool: True if matches, False otherwise.
    """
    if filterDev is None:
        return True
    if filterDevIsRegex:
        return bool(filterDev.search(name))
    else:
        return name == filterDev
    
def __lsblk(
    nodes:List[dict],
    parent:Optional[lsblkDiskInfo]=None,
    ignoreSysDisks:bool=True,
    mounted:Optional[bool]=None,
    filterDev:Optional[re.Pattern]=None,
    filterDevIsRegex:bool=True
) -> List[lsblkDiskInfo]:
    """Recursively process lsblk nodes and return list of lsblkDiskInfo.
    Args:
        nodes (List[dict]): List of LSBLK node dictionaries.
        parent (Optional[lsblkDiskInfo]): Parent disk info.
        ignoreSysDisks (bool): If True, ignore system disks used for / and /boot.        
        mounted (Optional[bool]): If  
            True: only return if mounted
            False: only return if not mounted
            None: return regardless of mount status
        filterDev (Optional[re.Pattern]): If provided, only return 'devices' (no partitions filter) matching the regex.
            - 'loop\d+' for loop devices
            - 'sd[a-z]+' for standard disks
            - 'loop0' for specific device
        filterDevIsRegex (bool): If:
            - True, filterDev is treated as regex pattern.
            - False, filterDev is treated as exact string match.        
    Returns:
        List[lsblkDiskInfo]: List of processed lsblkDiskInfo objects.
    """
    result = []
    for node in nodes:
        info:lsblkDiskInfo = __lsblk_process_node(node, parent)
        if not info:
            continue

        children = node.get('children', [])
        if isinstance(children, list) and len(children) > 0:
            children = [__lsblk_process_node(c, info) for c in children if isinstance(c, dict)]
            children = [c for c in children if c is not None]
        else:
            children = []
        
        # filter children na základě ignoreSysDisks
        if ignoreSysDisks and info and children:
            children = [child for child in children if not ('/' in child.mountpoints or '/boot' in child.mountpoints)]
            # pokud nic nezbylo tak protože filtrujeme na sysdisk tak nepřídáme ani rodiče
            if not children:
                continue
        
        # check na mount
        if not mounted is None and info:
            children = [child for child in children if not (
                (mounted is True and not child.haveMountPoints) or
                (mounted is False and child.haveMountPoints)
            )]
            if not children:
                # nemáme children co by splňovali mount podmínku
                # tak že pokud ani parent nesplňuje podmínku mount tak nepřidáváme
                if (mounted is True and not info.haveMountPoints) or (mounted is False and info.haveMountPoints):
                    continue

        # aktuálne children jsou již filtrované podle ignoreSysDisks a mounted
        # odfiltrujeme podle názvů
        
        info.children = []
        # pokud není regexp a sedí rodič, tak jen přidáme
        if __lsblk_chekNameMatch(info.name, filterDev, filterDevIsRegex):
            # pokud je mach na disku tak přidáme children a vrátíme protože hledáme disk s detaily
            pass
        elif children:
            # disk nesouhlasí tak otestujeme partitiony, protože můžeme hledat partition
            children = [child for child in children if __lsblk_chekNameMatch(child.name, filterDev, filterDevIsRegex)]
            if not children:
                continue

        info.children = children
        result.append(info)
            
    return result

def lsblk_list_disks(
        ignoreSysDisks:bool=True,
        mounted:Optional[bool]=None,
        filterDev:Optional[re.Pattern|str]=None,
        filterDevIsRegex:bool=True
    ) -> dict[str,lsblkDiskInfo]:
    """Return list of disks with basic info using lsblk. Returns dir of lsblkDiskInfo, key is disk name.
    Args:
        ignoreSysDisks (bool): If True, ignore disks used for / and /boot.
        mounted (Optional[bool]): If  
            True: only return mounted disks
            False: only return unmounted disks
            None: return all disks
        filterDev (Optional[re.Pattern|str]): If provided, only return 'devices' (no partitions filter) matching the regex.
            - 'loop\d+' for loop devices
            - 'sd[a-z]+' for standard disks
            - 'loop0' for specific device
        filterDevIsRegex (bool): If:  
            - True, filterDev is treated as regex pattern string.
            - False, filterDev is treated as exact string match.
    Returns:
        dict[str,lsblkDiskInfo]: Dictionary of lsblkDiskInfo objects, key is disk name.
    """
    if not isinstance(ignoreSysDisks, bool):
        raise ValueError("ignoreSysDisks must be a boolean")
    if mounted is not None and not isinstance(mounted, bool):
        raise ValueError("mounted must be a boolean or None")
    if not isinstance(filterDevIsRegex, bool):
        raise ValueError("filterDevIsRegex must be a boolean")
    
    if filterDev is not None and not (isinstance(filterDev, re.Pattern) or isinstance(filterDev, str)):
        raise ValueError("filterDev must be a regex pattern or string or None")
    if isinstance(filterDev, str) and filterDevIsRegex:
        filterDev = re.compile(filterDev)
        
    # lsblk -no NAME,LABEL,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS --json
    out = subprocess.run(
        ["lsblk", "-J","-b", "-o", "NAME,LABEL,SIZE,TYPE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS"],
        capture_output=True, text=True
    )
    data = json.loads(out.stdout)
    disks = __lsblk(data.get('blockdevices', []), None, ignoreSysDisks, mounted, filterDev, filterDevIsRegex)
    disk_dict = {disk.name: disk for disk in disks if disk.fstype != 'swap'}
    return disk_dict

def getDiskPathInfo(diskPath:str, ignoreSysDisks:bool=True) -> Optional[lsblkDiskInfo]:
    """Vrátí info o daném disku nebo partition.
    Args:
        diskPath (str): Disk (např. /dev/sda) nebo název (sda) anebo partition (např. /dev/sda1) nebo název (sda1).
        ignoreSysDisks (bool): Pokud True, ignoruje systémové disky používané pro / a /boot.
    Returns:
        Optional[lsblkDiskInfo]: Disk info nebo None pokud nenalezen.
    """
    diskPath = normalizeDiskPath(diskPath, True)
    ls_disks = lsblk_list_disks(ignoreSysDisks=ignoreSysDisks, filterDev=diskPath, filterDevIsRegex=False)
    # hledáme podle definitivní cesty, takže výsledek musí být jeden disk popř jedna partition
    # jinak je to chyba
    
    ds=[ d for d in ls_disks.values()]
    if len(ds)!=1:
        return None

    if ds[0].name == diskPath:
        return ds[0]

    if len(ds[0].children)!=1:
        return None
    
    return ds[0].children[0]

def getDiskByPartition(partition:str) -> Optional[lsblkDiskInfo]:
    """Vrátí disk, na kterém se nachází daná partition.
    Args:
        partition (str): Partition (např. /dev/sda1) nebo název (sda1).
    Returns:
        Optional[lsblkDiskInfo]: Disk info nebo None pokud nenalezen.
    """
    partition = normalizeDiskPath(partition, False)
    ls_parts = lsblk_list_disks(ignoreSysDisks=False)
    for disk in ls_parts.values():
        if disk.children:
            for child in disk.children:
                if child.name == partition or normalizeDiskPath(child.name, False) == partition:
                    return disk
    return None

def getPartitionInfo(partition:str) -> Optional[lsblkDiskInfo]:
    """Vrátí info o dané partition.
    Args:
        partition (str): Partition (např. /dev/sda1) nebo název (sda1).
    Returns:
        Optional[lsblkDiskInfo]: Partition info nebo None pokud nenalezen.
    """
    partition = normalizeDiskPath(partition, False)
    ls_parts = lsblk_list_disks(ignoreSysDisks=False)
    for disk in ls_parts.values():
        if disk.children:
            for child in disk.children:
                if child.name == partition or normalizeDiskPath(child.name, False) == partition:
                    return child
    return None

def getDiskyByName(diskName:str) -> Optional[lsblkDiskInfo]:
    """Vrátí disk podle jména disku.
    Args:
        diskName (str): Název disku (např. sda) nebo cesta (např. /dev/sda).
    Returns:
        Optional[lsblkDiskInfo]: Disk info nebo None pokud nenalezen.
    """
    diskName = normalizeDiskPath(diskName, True)
    ls_disks = lsblk_list_disks(ignoreSysDisks=False)
    for disk in ls_disks.values():
        if disk.name == diskName or normalizeDiskPath(disk.name, True) == diskName:
            return disk
    return None

def mountImageAsLoopDevice(
    imagePath:str|Path,
    callableGetMountPoint:Optional[callable]=None
) -> str|None:
    """Připojí image soubor jako loop device. Zjistí jestli se jedná o image partition nebo disku
    a podle toho připojí.
    
    Args:
        imagePath (str|Path): Cesta k image souboru.
    Returns:
        str: Cesta k připojenému loop device (např. /dev/loop0).
        None: pokud je img partition image a není poskytnuta funkce pro získání mountpointu.
    Raises:
        lsblkError: pokud se nepodaří připojit image jako loop device.
    """
    
    imagePath = Path(imagePath).resolve()
    if not imagePath.is_file():
        raise lsblkError(f"Image soubor {str(imagePath)} neexistuje nebo není soubor.")
    
    print(f"Připojování image souboru {str(imagePath)} jako loop device...")
    
    # Zkusit zjistit, zda IMG obsahuje GPT nebo MBR
    out = subprocess.run(
        ["file", "-b", str(imagePath)],
        capture_output=True,
        text=True
    ).stdout.lower()
    
    is_disk = ("partition table" in out) or ("dos/mb" in out) or ("gpt" in out)
    
    # Připojit jako loop device
    if is_disk:
        cmd = ["losetup", "--find", "--show", "-P", str(imagePath)]
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
    else:
        if callableGetMountPoint is None or not callable(callableGetMountPoint):
            print("Detekováno jako partition image, ale není poskytnuta funkce pro získání mountpointu.")
            return None
        
        mountpoint=callableGetMountPoint()
        if not isinstance(mountpoint, (str, Path)):
            raise lsblkError("Funkce pro získání mountpointu musí vrátit string nebo Path.")
        mountpoint=Path(mountpoint).resolve()
        if not mountpoint.is_dir():
            raise lsblkError(f"Mountpoint {str(mountpoint)} neexistuje nebo není adresář.")
        # mount přímo jako partition
        print(f"Detekováno jako partition image, připojuji přímo na zadaný mountpoint {str(mountpoint)}.")
        cmd = ["sudo", "mount", "-o", "loop", str(imagePath), str(mountpoint)]
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        if out.returncode != 0:
            raise lsblkError(f"Chyba při připojování image jako loop device: {out.stderr.strip()}")
        loop_device = mountpoint
        print(f"Image soubor připojen jako {loop_device}.")
        return loop_device
        
        
    if out.returncode != 0:
        raise lsblkError(f"Chyba při připojování image jako loop device: {out.stderr.strip()}")
    loop_device = out.stdout.strip()
    print(f"Image soubor připojen jako {loop_device}.")
    return loop_device

@dataclass
class chkImgFlUsed_ret:
    used: bool
    """Image je použit (připojen jako loop device)"""
    device: str
    """Název loop device (např. /dev/loop0)"""

def getLoopImgInfo() -> dict[str,Path]:
    """ Vrátí dict s informacemi o připojených loop image souborech
    dict of Path kde key = loopDevice
    """
    ls=subprocess.run(
        ["losetup", "--json", "--list"],
        capture_output=True,
        text=True
    ).stdout
    import json
    lsj=json.loads(ls)
    res:dict[str,Path]={}
    for d in lsj["loopdevices"]:
        if "back-file" in d:
            res[d["name"]]=Path(d["back-file"]).resolve()
    return res

def chkImgFlUsed(imagePath:Path) -> chkImgFlUsed_ret:
    """Zkontroluje jestli již není image připojen jako loop device nebo mountnutý.    
    Args:
        imagePath (Path): cesta k image souboru.
    
    Returns:
        chkImgFlUsed_ret: Dict s informacemi o použití image souboru.
    """
    ls=getLoopImgInfo()
    imagePath=imagePath.resolve()
    for dev, fl in ls.items():
        if fl == imagePath:
            return chkImgFlUsed_ret(
                used=True,
                device=dev
            )
    return chkImgFlUsed_ret(
        used=False,
        device=""
    )
    
def chkMountpointUsed(mountPoint:Path) -> bool:
    """Zkontroluje jestli je mountpoint již použitý.
    Args:
        mountPoint (Path): cesta k mountpointu.
    Returns:
        bool: True pokud je mountpoint použitý, False pokud není.
        None pokud mountpoint neexistuje nebo není adresář.
    """
    mountPoint=Path(mountPoint).resolve()
    if not mountPoint.is_dir():
        return None
    mountPointStr=mountPoint.as_posix()
    for mp in lsblk_list_disks(ignoreSysDisks=False).values():
        if mountPointStr in mp.mountpoints:
            return True
        if mp.children:
            for p in mp.children:
                if mountPointStr in p.mountpoints:
                    return True
    return False

def checkExt4(partition:str) -> None|str:
    """Zkontroluje ext4 partition.
    Akceptuje název partition bez /dev/ (sdb2, mmcblk0p1, atd.).
    Args:
        partition (str): název partition s nebo bez /dev/
    Returns:
        None: pokud je kontrola úspěšná.
        str: chybová hláška pokud kontrola selže.
    """
    
    part = partitionInfo(partition)
    if part is None or part.partitionInfo is None:
        return f"Nepodařilo se zjistit informace o partition: {partition}"
    
    if not part.isPartitionExt4:
        return f"Partition {partition} není ext4."
    
    try:
        run(["sudo", "e2fsck", "-f", part.partitionPath])
    except Exception as e:
        return f"Chyba při kontrole ext4 partition {partition}: {e}"
    
    return None
        
def detectFsType(dev: str) -> Optional[str]:
    """Zjistí typ filesystému podle magic number."""
    dev= normalizeDiskPath(dev, True)
    nfo=getPartitionInfo(dev)
    if nfo is None:
        return None
    if nfo.fstype:
        return nfo.fstype
    return None

def getExtSize(dev: str) -> Optional[fsInfo_ret]:
    """Získá informace z ext2/3/4 přes tune2fs (bez mountu)."""
    text,r,e = runRet(["tune2fs", "-l", dev], False)

    if r != 0:
        return None

    block_count  = int(re.search(r"Block count:\s+(\d+)", text).group(1))
    block_size   = int(re.search(r"Block size:\s+(\d+)", text).group(1))

    total = block_count * block_size

    free_blocks = int(re.search(r"Free blocks:\s+(\d+)", text).group(1))
    free = free_blocks * block_size

    used = total - free
    usePercent = (used / total) * 100 if total > 0 else 0

    return fsInfo_ret(
        total=total,
        used=used,
        free=free,
        usePercent=usePercent,
        fsType="ext"
    )


def getXfsSize(dev: str) -> Optional[fsInfo_ret]:
    """Získá informace z XFS přes xfs_db (bez mountu)."""
    txt,r,e = runRet(["xfs_db", "-r", dev, "-c", "sb 0", "-c", "print"], False)

    if r != 0:
        return None

    block_size = int(re.search(r"blocksize = (\d+)", txt).group(1))
    dblocks    = int(re.search(r"dblocks = (\d+)", txt).group(1))

    total = block_size * dblocks

    # XFS *neukládá free blocks v superbloku* → bez mountu nezjistitelné
    # ⇒ Vracíme jen total a ostatní None
    return fsInfo_ret(
        total=total,
        used=None,
        free=None,
        usePercent=None,
        fsType="xfs"
    )


def getFsInfo(partition: str) -> Optional[fsInfo_ret]:
    """Získá info o ext2/3/4 pomocí dumpe2fs (rychlé a spolehlivé)."""
    partition = normalizeDiskPath(partition, False)
    try:
        txt, returncode, stderr = runRet(["dumpe2fs", "-h", partition],False)
        if returncode != 0:
            return None
    except Exception:
        return None

    # Parsování
    def find(pattern):
        m = re.search(pattern, txt)
        return m.group(1) if m else None

    block_count = find(r"Block count:\s+(\d+)")
    free_blocks = find(r"Free blocks:\s+(\d+)")
    block_size  = find(r"Block size:\s+(\d+)")
    fsFeat =  find(r"Filesystem features:\s+(.+)")
    fsFeat = fsFeat.split() if fsFeat else []
    fsType= 'ext2'

    if "extent" in fsFeat:
        fsType = "ext4"
    if "has_journal" in txt:
        fsType = "ext3"    

    if not (block_count and free_blocks and block_size):
        return None

    block_count = int(block_count)
    free_blocks = int(free_blocks)
    block_size  = int(block_size)

    total = block_count * block_size
    free  = free_blocks * block_size
    used  = total - free
    pct   = (used / total * 100) if total > 0 else 0

    return fsInfo_ret(
        total=total,
        used=used,
        free=free,
        usePercent=pct,
        fsType=fsType or "ext?"
    )
    
def getLabel(part:str) -> Optional[str]:
    """Získá label partition.
    Args:
        part (str): Partition (např. /dev/sda1) nebo název (sda1).
    Returns:
        Optional[str]: Label partition nebo None pokud není nastaven.
    """
    part = normalizeDiskPath(part, False)
    ls_parts = lsblk_list_disks(ignoreSysDisks=False)
    for disk in ls_parts.values():
        if disk.children:
            for child in disk.children:
                if child.name == part or normalizeDiskPath(child.name, False) == part:
                    return child.label if child.label else None
    return None

def setPartitionLabel(part:str, label:str) -> bool:
    """Nastaví label partition. Vstup musí partition, musí existovat a musí mít podporovaný fs type.
    Args:
        part (str): Partition (např. /dev/sda1) nebo název (sda1).
        label (str): Nový label partition.
    Returns:
        bool: True pokud se podařilo nastavit label, False pokud ne.
    """
    part = normalizeDiskPath(part, False)
    nfo=getPartitionInfo(part)
    if nfo is None:
        return False
    if not nfo.fstype:
        return False
    fs_type=nfo.fstype.lower()
    if nfo.type != 'part':
        return False
    
    try:
        if fs_type in ['ext2','ext3','ext4']:
            o,r,e = runRet(["sudo", "e2label", part, label], False)
            if r != 0:
                return False
        elif fs_type == 'xfs':
            o,r,e = runRet(["sudo", "xfs_admin", "-L", label, part], False)
            if r != 0:
                return False
        elif fs_type in ['fat','ntfs']:
            o,r,e = runRet(["sudo", "mlabel", "-i", part, "::" + label], False)
            if r != 0:
                return False
        else:
            return False
    except Exception:
        return False
    
    return True