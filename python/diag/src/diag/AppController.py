try:
    import cpuinfo
except ImportError:
    pass
import subprocess
import re
from Singleton import SingletonMeta
from PySide6.QtCore import QObject, Property, Slot

class AppController(QObject):

    def __init__(self, parent:QObject):
        super().__init__(parent)

    def __get_system_info(self) -> dict:
        cpu = cpuinfo.get_cpu_info()
        return cpu
    
    def has_vtd(self):
        ''' AKA VT-d '''
        cmd = "dmesg | grep -i -e iommu -e dmar"

        found = False

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)

            sentences = [
                "DMAR: Intel(R) Virtualization Technology for Directed I/O",
                "DMAR: IOMMU enabled"
            ]

            if result.returncode == 0 and any(sentence in result.stdout for sentence in sentences):
                found = True
        except subprocess.CalledProcessError:
            found = False
        
        if not found:
            cmd = "xl dmesg | grep iommu"

            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)

                sentences = [
                    "(XEN) Intel VT-d iommu 0 supported page sizes:",
                    "(XEN) Intel VT-d iommu 1 supported page sizes:"
                ]

                if result.returncode == 0 and any(sentence in result.stdout for sentence in sentences):
                    found = True
            except subprocess.CalledProcessError:
                found = False
                

        return found
        
    def has_ept(self):
        cmd = "xl dmesg | grep -i ept"

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)

            if result.returncode == 0 and "(XEN) Intel VT-d Shared EPT tables enabled" in result.stdout:
                return True
        except subprocess.CalledProcessError:
            return False
        
        return False
    
    def has_hvm(self):
        result = subprocess.run(['xl', 'info'], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if line.startswith('virt_caps'):
                return 'hvm_directio' in line
        return False
    
    def has_vtx(self):
        result = subprocess.run(['xl', 'dmesg'], capture_output=True, text=True)
        return "VMX enabled" in result.stdout
    
    def get_installed_memory_in_gb(self):
        try:
            result = subprocess.run(['xl', 'info'], stdout=subprocess.PIPE, text=True, check=True)
            match = re.search(r'^total_memory\s*:\s*(\d+)', result.stdout, re.MULTILINE)
            if match:
                total_mb = int(match.group(1))
                return total_mb / 1024 
            else:
                raise ValueError("total_memory not found in xl info.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Error during execution of xl info : {e}")
    
    def get_bogomips(self):
        total = 0.0
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if "bogomips" in line.lower():
                    try:
                        value = float(line.split(":")[1])
                        total += value
                    except (IndexError, ValueError):
                        pass

        return round(total)

    @Slot()
    def shutdown(self):
        subprocess.run("poweroff", check=False)

    cpuInfo = Property(type=dict, fget=__get_system_info, constant=True)
    hasVTd = Property(type=bool, fget=has_vtd, constant=True)
    hasVTx = Property(type=bool, fget=has_vtx, constant=True)
    hasHVM = Property(type=bool, fget=has_hvm, constant=True)
    installedMemory = Property(type=float, fget=get_installed_memory_in_gb, constant=True)
    bogoMips = Property(type=float, fget=get_bogomips, constant=True)
