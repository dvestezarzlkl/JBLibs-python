import subprocess
import json
import re
from typing import List, Optional, Union
from .format import bytesTx

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
        mountpoints:Union[List[str],str],
        parent:Optional[str]=None,
        children:Optional[List['lsblkDiskInfo']]=None
    ):
        self.name = name
        self.label = label
        self.size = size
        self.fstype = fstype
        self.uuid = uuid
        self.partuuid = partuuid
        self.mountpoints = mountpoints
        self.parent = parent
        self.type = type
        
        mp = mountpoints or []
        if isinstance(mp, str):
            mp = [mp]
        self.mountpoints = mp        
                    
        self.children = children if children is not None else []
        
    def __repr__(self):
        sz=bytesTx(self.size)
        mountPoints=len(self.mountpoints)
        childs=len(self.children)
        childsLst=[child.name for child in self.children]
        return f"lsblkDiskInfo(tp:{self.type}, nm={self.name}, sz={sz}, fstp={self.fstype}, uuid={self.uuid}, partuuid={self.partuuid}, mountpoints={mountPoints}, children={childs} {childsLst})"

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

def __lsblk_process_node(
    node:dict,
    parent:Optional[lsblkDiskInfo]=None,
    ignoreSysDisks:bool=True,
    mounted:Optional[bool]=None,
    filterDev:Optional[re.Pattern]=None
) -> Optional[lsblkDiskInfo]:
    """Process a single lsblk node and return lsblkDiskInfo or None.
    Args:
        node (dict): LSBLK node dictionary.
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
    Returns:
        Optional[lsblkDiskInfo]: Processed lsblkDiskInfo object or None.
        
    """
    
    if node['type'] in ['disk','part','loop']:
        nfo = lsblkDiskInfo(
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
        if ignoreSysDisks and ('/' in nfo.mountpoints or '/boot' in nfo.mountpoints):
            return None
        
        nfo.mountpoints = [mp for mp in nfo.mountpoints if mp]  # remove empty mountpoints
            
        is_mounted = len(nfo.mountpoints) > 0
        # pokud je to distk tak vracíme vždy, mounted je jen pro partition
        # if node['type'] != 'disk':
        if not node['type'] in ['disk','loop']:
            if mounted is True and not is_mounted:
                return None
            if mounted is False and is_mounted:
                return None
        else:
            # pokud je to disk a je nastaven filterDev tak aplikujeme filtr
            if isinstance(filterDev, re.Pattern):
                nm=normalizeDiskPath(nfo.name,True)
                if not filterDev.fullmatch(nm):
                    return None
        return nfo
    return None
        

def __lsblk_recursive(
    nodes:List[dict],
    parent:Optional[lsblkDiskInfo]=None,
    ignoreSysDisks:bool=True,
    mounted:Optional[bool]=None,
    filterDev:Optional[re.Pattern]=None
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
    Returns:
        List[lsblkDiskInfo]: List of processed lsblkDiskInfo objects.
    """
    result = []
    for node in nodes:
        info = __lsblk_process_node(node, parent, ignoreSysDisks, mounted, filterDev)
        if info:
            children = node.get('children', [])
            info.children = __lsblk_recursive(children, info, ignoreSysDisks, mounted, filterDev)
            
            # check mount status
            is_mounted = len(info.mountpoints) > 0
            for x in info.children:
                if len(x.mountpoints) > 0:
                    is_mounted = True
                    break
            
            if not mounted is None:
                if mounted is True and not is_mounted:
                    continue
                if mounted is False and is_mounted:
                    continue
                
            # ignore system disks if needed
            is_sys='/' in info.mountpoints or '/boot' in info.mountpoints
            for x in info.children:
                if '/' in x.mountpoints or '/boot' in x.mountpoints:
                    is_sys = True
                    break
            if ignoreSysDisks and is_sys:
                continue

            # process children
            result.append(info)
    return result

def lsblk_list_disks(
        ignoreSysDisks:bool=True,
        mounted:Optional[bool]=None,
        filterDev:Optional[re.Pattern|str]=None
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
    Returns:
        dict[str,lsblkDiskInfo]: Dictionary of lsblkDiskInfo objects, key is disk name.
    """
    # lsblk -no NAME,LABEL,SIZE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS --json
    out = subprocess.run(
        ["lsblk", "-J","-b", "-o", "NAME,LABEL,SIZE,TYPE,FSTYPE,UUID,PARTUUID,MOUNTPOINTS"],
        capture_output=True, text=True
    )
    data = json.loads(out.stdout)
    if filterDev and isinstance(filterDev, str):
        filterDev = re.compile(filterDev)
    disks = __lsblk_recursive(data.get('blockdevices', []), None, ignoreSysDisks, mounted, filterDev)
    disk_dict = {disk.name: disk for disk in disks if disk.fstype != 'swap'}
    return disk_dict

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