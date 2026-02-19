from PIL import Image
import sys
import os
import json
from safecor import SysLogger, System

LOGO_FILEPATH = "/boot/splash.png"
TOPOLOGY_FILE="/etc/safecor/topology.json"

def create_splash() -> Image:
    topology = System.get_topology()
    width = topology.screen.width
    height = topology.screen.height

    SysLogger("Create splash").info(f"Create splash of size {width}x{height}")

    bgcolor = topology.color_as_rgba("splash_bgcolor")
    print(bgcolor)
    splash = Image.new("RGB", (width, height), bgcolor)
    image = Image.open(LOGO_FILEPATH)
    
    image_width, image_height = image.size
    x = (width - image_width) // 2
    y = (height - image_height) // 2

    splash.paste(image, (x,y), image)

    return splash

def save_splash(splash:Image, dest:str):
    width, height = splash.size

    SysLogger("Create splash").info("Create PNG file")
    splash.save(f"{dest}/splash_{width}_{height}.png")
    
    SysLogger("Create splash").info("Create PPM file")
    splash.save(f"{dest}/splash_{width}_{height}.ppm", format="PPM")

if __name__ == "__main__":
    SysLogger("Create splash").info("Starting...")

    if len(sys.argv) < 1:
        SysLogger("Create splash").error("Error: missing arguments")
        print("Error: Missing arguments")
        print("Usage: ")
        print(f"    {os.path.basename(__file__)} destination_dir")
        sys.exit()
    
    dest = sys.argv[3]

    image = create_splash()
    save_splash(image, dest)

    SysLogger("Create splash").info("... done")
