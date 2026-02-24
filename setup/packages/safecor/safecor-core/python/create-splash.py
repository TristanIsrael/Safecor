from PIL import Image
import sys
import os
from safecor import SysLogger, System

LOGO_FILEPATH = "/boot/splash.png"
TOPOLOGY_FILE="/etc/safecor/topology.json"


def create_splash(rotate:bool, filepath_pattern:str) -> Image:
    screen = System.get_framebuffer_dimension()
    screen_width = screen[0] if screen is not None else 800
    screen_height = screen[1] if screen is not None else 600
    screen_rotation = System.get_screen_rotation_from_topology()
    bgcolor = System.get_splash_bgcolor_from_topology()

    SysLogger("Create splash").info(f"Create splash of size {screen_width}x{screen_height} {"rotated" if rotate else ""} width background color {bgcolor}")

    splash = Image.new("RGB", (screen_width, screen_height) if not rotate else (screen_height, screen_width), bgcolor)
    original = Image.open(LOGO_FILEPATH)
    
    if not rotate and (screen_rotation == 90 or screen_rotation == 270):
        rotated = original.rotate(screen_rotation)
        original = rotated
    
    image_width, image_height = original.size
    if not rotate:
        x = (screen_width - image_width) // 2
        y = (screen_height - image_height) // 2
    else:
        x = (screen_height - image_width) // 2
        y = (screen_width - image_height) // 2

    splash.paste(original, (x,y), original)

    save_splash(splash, filepath_pattern, rotate)

def save_splash(splash:Image, dest:str, rotate:bool):
    # dest does not contain the extension

    SysLogger("Create splash").info("Create PNG file")
    splash.save(f"{dest}{"_rotated" if rotate else ""}.png")
    
    SysLogger("Create splash").info("Create PPM file")
    splash.save(f"{dest}{"_rotated" if rotate else ""}.ppm", format="PPM")

if __name__ == "__main__":
    SysLogger("Create splash").info("Starting...")

    if len(sys.argv) < 1:
        SysLogger("Create splash").error("Error: missing arguments")
        print("Error: Missing arguments")
        print("Usage: ")
        print(f"    {os.path.basename(__file__)} destination_dir")
        sys.exit()
    
    _dest = sys.argv[1]

    create_splash(False, _dest)
    create_splash(True, _dest)

    SysLogger("Create splash").info("... done")
