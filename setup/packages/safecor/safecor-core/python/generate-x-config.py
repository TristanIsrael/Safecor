import json
from safecor import SysLogger


def angle_to_rotate(angle):
    mapping = {
        0: "normal",
        90: "left",
        -90: "right",
        180: "inverted"
    }
    return mapping.get(angle, "normal")


def write_monitor_section(angle:int) -> None:
    filepath = "/etc/X11/xorg.conf.d/10-monitor.conf"

    # Read current resolution
    with open('/sys/class/graphics/fb0/virtual_size', 'r') as fichier:
        resolution = fichier.read().strip().replace(",", "x")
        #print(resolution)

    # Calculate resolution
    if resolution is None:
        resolution = "1024x768"

    # Apply rotation
    section = f"""
Section "Monitor"
    Identifier "Monitor0"
    Option "PreferredMode" "{resolution}"
    Option "Rotate" "{angle_to_rotate(angle)}"
    Option "DPMS" "false"
EndSection
"""
            
    with open(filepath, "w") as fichier:
        fichier.write(section)

if __name__ == "__main__":
    SysLogger("Generate X config").info("Generating X server configuration files...")

    # Rotation is defined in topology.json
    TOPOLOGY_FILE="/etc/safecor/topology.json"

    try:
        with open(TOPOLOGY_FILE, 'r') as file:
            json_data = json.load(file)
    except Exception as e:
        SysLogger("Generate X config").error(f"An error occured while reading the topology file {TOPOLOGY_FILE}")
        SysLogger("Generate X config").error(e)
        print(f"An error occured while reading the topology file {TOPOLOGY_FILE}")
        print(e)
        exit(1)

    #"gui": {
    #    "use": 1,    
    #    "screen": {
    #        "rotation": 0
    json_gui = json_data.get("gui")
    if json_gui is None:
        print("No GUI in topology")
        exit(0)
        
    json_use = json_gui.get("use")
    if json_use is None:
        print("GUI is unset in topology")
        exit(0)

    json_screen = json_gui.get("screen")
    if json_screen is not None:        
        rotation = json_screen.get("rotation")
               
        write_monitor_section(rotation)
    
    SysLogger("Generate X config").info("... done")