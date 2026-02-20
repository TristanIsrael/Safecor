from PIL import Image
import sys
import os
from safecor import SysLogger, System

LOGO_FILEPATH = "/boot/splash.png"
TOPOLOGY_FILE="/etc/safecor/topology.json"


def create_splash() -> Image:
    screen = System.get_framebuffer_dimension()
    width = screen[0] if screen is not None else 800
    height = screen[1] if screen is not None else 600
    rotation = System.get_screen_rotation_from_topology()

    # Calculate new dimensions with the rotation
    #if rotation == 90 or rotation == 270:
    #    _width = width
    #    _height = height
    #    width = _height
    #    height = _width

    SysLogger("Create splash").info(f"Create splash of size {width}x{height}")

    #bgcolor = topology.color_as_rgba("splash_bgcolor")
    bgcolor = System.get_splash_bgcolor_from_topology()
    splash = Image.new("RGB", (width, height), bgcolor)
    image = Image.open(LOGO_FILEPATH)
    
    if rotation == 90 or rotation == 270:
        rotated = image.rotate(rotation)
        image = rotated
    
    image_width, image_height = image.size
    x = (width - image_width) // 2
    y = (height - image_height) // 2

    splash.paste(image, (x,y), image)

    return splash

def save_splash(splash:Image, dest:str):
    # dest does not contain the extension

    SysLogger("Create splash").info("Create PNG file")
    splash.save(f"{dest}.png")
    
    SysLogger("Create splash").info("Create PPM file")
    splash.save(f"{dest}.ppm", format="PPM")

if __name__ == "__main__":
    SysLogger("Create splash").info("Starting...")

    if len(sys.argv) < 1:
        SysLogger("Create splash").error("Error: missing arguments")
        print("Error: Missing arguments")
        print("Usage: ")
        print(f"    {os.path.basename(__file__)} destination_dir")
        sys.exit()
    
    #_width = int(sys.argv[1])
    #_height = int(sys.argv[2])
    _dest = sys.argv[1]

    _image = create_splash()
    save_splash(_image, _dest)

    SysLogger("Create splash").info("... done")
