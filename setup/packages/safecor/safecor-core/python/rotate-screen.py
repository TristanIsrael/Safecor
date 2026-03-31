import subprocess
import sys
from safecor import SysLogger, System

def angle_to_rotate(angle):
    """ Translates a rotation angle to XOrg value """

    mapping = {
        0: "normal",
        90: "left",
        -90: "right",
        180: "inverted"
    }
    return mapping.get(angle, "normal")

def rotate_screen(angle:int) -> None:
    """ Asks XOrg to rotate the screen """

    get_output_command = "xrandr --display :0 | grep ' connected' | awk 'NR==1 {print $1}'"

    try:
        screen_name = subprocess.check_output(get_output_command, shell=True, text=True).strip()

        if screen_name:
            # Commande pour appliquer la rotation
            rotate_command = f"xrandr --display :0 --output {screen_name} --rotate {angle_to_rotate(angle)}"

            # Exécute la commande de rotation
            subprocess.run(rotate_command, shell=True, check=True)
            SysLogger("Screen rotation").info(f"Screen {screen_name} rotated by {angle} degrees. Value={angle}")
        else:
            SysLogger("Screen rotation").error("No screen found")
    except subprocess.CalledProcessError as e:
        SysLogger("Screen rotation").error(f"Error during execution: {e}")
    except Exception as e:
        SysLogger("Screen rotation").error(f"An error occured: {e}")

if __name__ == "__main__":
    SysLogger("Screen rotation").info("Rotate screen if needed...")

    # Rotation is defined in topology.json
    #topology_file="/etc/safecor/topology.json"
    #try:
    #    with open(topology_file, 'r') as file:
    #        json_data = json.load(file)
    #except Exception as e:
    #    print("An error occured while reading the topology file {}".format(topology_file))    
    #    print(e)    
    #    exit(1)    

    #config = ConfigurationReader.get_configuration_for_system()   
    topology = System.get_topology()
    
    if not topology.screen.enabled:
        SysLogger("Screen rotation").info("The screen is disabled in the topology")
        sys.exit(0)

    if topology.screen.rotation != 0:
        rotate_screen(topology.screen.rotation)
    else:
        SysLogger("Screen rotation").info("No rotation needed")

    SysLogger("Screen rotation").info("... done")