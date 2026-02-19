import subprocess
from safecor import ConfigurationReader, SysLogger

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
            rotate_command = "xrandr --display :0 --output {} --rotate {}".format(screen_name, angle_to_rotate(angle))

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

    config = ConfigurationReader.get_configuration_for_system()

    # Settings structure:
    # "gui": {
    #    "use": 1,    
    #    "screen": {
    #        "rotation": 0
    json_gui = config.get("gui")
    if json_gui is None:
        SysLogger("Screen rotation").info("No GUI in topology")
        exit(0)
        
    json_use = json_gui.get("use")
    if json_use is None:
        SysLogger("Screen rotation").info("GUI is unset in topology")
        exit(0)

    json_screen = json_gui.get("screen")
    if json_screen is None:
        SysLogger("Screen rotation").info("No screen option in topology")
        exit(0)

    rotation = json_screen.get("rotation")
    if rotation is None:
        SysLogger("Screen rotation").info("No rotation in topology")
        exit(0)

    if rotation != 0:
        rotate_screen(rotation)
    else:
        SysLogger("Screen rotation").info("No rotation needed")

    SysLogger("Screen rotation").info("... done")