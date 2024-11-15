import subprocess,re
from typing import Union

class c_machine_info:
    """Třída pro získání informací o systému pomocí hostnamectl."""

    err:Union[None,str]=None
    """Pokud null tak ok, jinak chyba při inicializaci"""

    machine_id: str = ""
    """Unikátní ID stroje"""
    
    boot_id: str = ""
    """ Unikátní ID aktuálního bootu"""
    
    icon_name: str = ""
    """Ikona reprezentující typ zařízení"""
    
    static_hostname: str = ""
    """ Statický název hostitele"""
    
    hostname_full: str = ""
    """Plný název hostitele (pokud dostupný)"""
    
    virtualization: str = ""
    """Typ virtualizace, pokud existuje"""
    
    operating_system: str = ""
    """Operační systém a jeho verze, tzn např Ubuntu 20.04.1 LTS"""
    
    os_distro: str = ""
    """Distribuce operačního systému tzn např Ubuntu"""
    
    os_version: str = ""
    """Verze operačního systému, tzn 20.04.1"""
    
    os_lts: bool = False
    """True pokud je operační systém LTS"""
    
    kernel: str = ""
    """Verze jádra systému, celý text, např Linux 5.4.0-42-generic"""
    
    kernel_name:str=""
    """Jen název jádra"""
    
    kernel_version:str=""
    """Jen verze jádra"""
    
    architecture: str = ""
    """Architektura procesoru"""
    
    hardware_vendor: str = ""
    """Výrobce hardwaru"""
    
    hardware_model: str = ""
    """Model hardwaru"""

    def __init__(self):
        self.load_info()

    def load_info(self):
        """Načte informace o systému z hostnamectl."""
        try:
            result = subprocess.run(["hostnamectl"], stdout=subprocess.PIPE, text=True)
            if result.returncode == 0:
                lines = result.stdout.splitlines()
                for line in lines:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(" ", "_")
                        value = value.strip()
                        if hasattr(self, key):
                            setattr(self, key, value)
                # dokončení
                # zpracování některých položek
                # kernel
                p = r"^\s*(\w+)\s+(\d+\.\d+\.\d+)-"
                if (m:=re.match(p,self.kernel)):
                    self.kernel_name=m.group(1)
                    self.kernel_version=m.group(2)
                    
                # OS
                p = r"^(.*)\s+(\d+\.\d+\.\d+)"
                if (m:=re.match(p,self.operating_system)):
                    self.os_distro=m.group(1)
                    self.os_version=m.group(2)
                    self.os_lts="LTS" in self.operating_system
                
                # full hostname
                result = subprocess.run(["hostname", "-f"], stdout=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    self.hostname_full=result.stdout.strip()                
            else:
                self.err="Chyba při spuštění hostnamectl"
        except Exception as e:
            self.err=f"Chyba při načítání informací: {e}"

    def __str__(self):
        """Vrátí textový výpis všech informací o stroji."""
        return (
            f"Machine ID: {self.machine_id}\n"
            f"Boot ID: {self.boot_id}\n"
            f"Icon: {self.icon_name}\n"
            f"Hostname: {self.static_hostname}\n"
            f"Hostname Full: {self.hostname_full}\n"
            f"Virtualization: {self.virtualization}\n"
            f"OS: {self.operating_system}\n"
            f"OS Distro: {self.os_distro}\n"
            f"OS Version: {self.os_version}\n"
            f"OS LTS: {self.os_lts}\n"
            f"Kernel: {self.kernel}\n"
            f"Kernel Name: {self.kernel_name}\n"
            f"Kernel Version: {self.kernel_version}\n"            
            f"Architecture: {self.architecture}\n"
            f"Hardware Vendor: {self.hardware_vendor}\n"
            f"Hardware Model: {self.hardware_model}\n"            
        )
