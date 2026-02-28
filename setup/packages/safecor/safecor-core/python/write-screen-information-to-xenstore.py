import subprocess
import sys
from safecor import System, SysLogger

if __name__ == "__main__":    
    SysLogger("write-screen-information-to-xenstore").info("Write screen information into Xenstore...")

    topology = System.get_topology()

    if not topology.use_gui:
        SysLogger("write-screen-information-to-xenstore").info("No GUI in topology")
        sys.exit(0)
            
    command = f"xenstore-write /local/domain/system/screen_rotation {topology.screen.rotation}"
    subprocess.run(command, shell=True, check=True)

    SysLogger("write-screen-information-to-xenstore").info("... done")
