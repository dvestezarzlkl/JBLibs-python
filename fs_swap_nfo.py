#!/usr/bin/env python3
import os
import pwd
import json
from .jbjh import JBJH
from .format import bytesTx
import argparse

def get_swap(pid:str)->int:
    """Získá velikost VmSwap procesu
    Parameters:
        pid (str): PID procesu
    Returns:
        int: velikost VmSwap v kB
    """
    try:
        with open(f'/proc/{pid}/status') as f:
            for line in f:
                if line.startswith('VmSwap:'):
                    return int(line.split()[1])
    except Exception:
        return 0
    return 0

def get_user(pid:str)->str:
    """Získá uživatele procesu
    Parameters:
        pid (str): PID procesu
    Returns:
        str: uživatel procesu
    """
    try:
        stat = os.stat(f'/proc/{pid}')
        return pwd.getpwuid(stat.st_uid).pw_name
    except Exception:
        return '?'

def get_cmdline(pid:str)->str:
    """Získá příkazovou řádku procesu
    Parameters:
        pid (str): PID procesu
    Returns:
        str: příkazová řádka
    """    
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            raw = f.read().replace(b'\x00', b' ').decode().strip()
            return raw if raw else '?'
    except Exception:
        return '?'

def get_comm(pid:str)->str:
    """Získá název příkazu procesu
    Parameters:
        pid (str): PID procesu
    Returns:
        str: název příkazu
    """
    try:
        with open(f'/proc/{pid}/comm') as f:
            return f.read().strip()
    except Exception:
        return '?'

def get_meminfo(pid:str)->tuple[int,int]:
    """Získá informace o paměti procesu
    Parameters:
        pid (str): PID procesu
    Returns:
        tuple[int,int]: (RSS v kB, VSZ v kB)
    """
    try:
        with open(f'/proc/{pid}/stat') as f:
            parts = f.read().split()
            rss = int(parts[23]) * os.sysconf('SC_PAGE_SIZE') // 1024
            vsz = int(parts[22]) // 1024
            return rss, vsz
    except Exception:
        return 0, 0

def collect_processes(minswap:int=0)->list[dict]:
    """Shromáždí informace o procesech využívajících SWAP
    Parameters:
        minswap (int): Minimální velikost VmSwap v kB
    Returns:
        list[dict]: Seznam procesů s informacemi o SWAP a paměti
    """
    if (minswap:=JBJH.is_int(minswap)) is None:
        minswap=0
    procs = []
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            swap = get_swap(pid)
            if swap >= minswap:
                user = get_user(pid)
                cmd = get_cmdline(pid)
                comm = get_comm(pid)
                rss, vsz = get_meminfo(pid)
                procs.append({
                    'swap': swap,
                    'pid': int(pid),
                    'user': user,
                    'rss': rss,
                    'vsz': vsz,
                    'comm': comm,
                    'cmd': cmd
                })
    return sorted(procs, key=lambda x: x['swap'], reverse=True)

def print_table(procs:list[dict]=None, limit:int=20, cmd_limit:int=80, legenda:bool=True):
    if (limit:=JBJH.is_int(limit)) is None:
        limit=20
    if (cmd_limit:=JBJH.is_int(cmd_limit)) is None:
        cmd_limit=80    
    if procs is None:
        procs = collect_processes()        
    print(f"{'SWAP':>8} {'PID':>6} {'USER':>12} {'RSS':>8} {'VSZ':>8} {'COMM':<20} CMD")
    for i, p in enumerate(procs[:limit]):
        cmd = (p['cmd'][:cmd_limit - 3] + '...') if len(p['cmd']) > cmd_limit else p['cmd']

        # Výpočet formátovaných velikostí
        swap = bytesTx(p['swap'] * 1024)
        rss  = bytesTx(p['rss'] * 1024)
        vsz  = bytesTx(p['vsz'] * 1024)

        # Barvy
        if i == 0:
            color = '\033[91m'  # červená
        elif i < 5:
            color = '\033[93m'  # žlutá
        else:
            color = '\033[0m'
        reset = '\033[0m'

        print(color + f"{str(swap):>8} {p['pid']:6} {p['user']:12} {str(rss):>8} {str(vsz):>8} {p['comm']:<20} {cmd}" + reset)

    lgHlp=[
        "\nLegenda barev:",
        "  \033[91mČervená\033[0m - Nejvíce SWAP",
        "  \033[93mŽlutá\033[0m - Mezi 2. a 5. nejvíce SWAP",
        "  \033[0mNormální - Ostatní procesy",
        # sloupce
        "\nSloupce výstupu:",
        "  SWAP   - objem dat ve swapu (automaticky k/M/G)",
        "  PID    - ID procesu",
        "  USER   - vlastník procesu",
        "  RSS    - Resident Set Size = reálně obsazená RAM (k/M/G)",
        "  VSZ    - Virtual Memory Size = virtuální velikost procesu (k/M/G) (rezervovaná paměť)",
        "  COMM   - název binárky nebo příkazového interpreta",
        "  CMD    - úplný spuštěný příkaz (zkrácený, pokud je dlouhý)",
    ]
    if legenda:
        print("\n".join(lgHlp))

def print_json(procs:list[dict]=None, limit:int=20):
    """Vytiskne informace o procesech využívajících SWAP ve formátu JSON
    Parameters:
        procs (list[dict]|None): seznam procesů, pokud None, shromáždí aktuální
        limit (int): maximální počet procesů k zobrazení
    """
    if (limit:=JBJH.is_int(limit)) is None:
        limit=20
    if procs is None:
        procs = collect_processes()
    print(json.dumps(procs[:limit], indent=2))
