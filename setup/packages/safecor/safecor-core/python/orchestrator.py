import os
import glob
import subprocess
import time
import socket
import threading
import json
import msgpack
import evdev
from evdev import InputDevice, ecodes, UInput
from safecor import MqttFactory, Logger, InputType, SysLogger, ConfigurationReader

mqtt_lock = threading.Event()
mqtt = MqttFactory.create_mqtt_client_dom0("Orchestrator")
MOUSE_NAME="Safecor virtual mouse"
TOUCH_NAME="Safecor virtual touchscreen"
KEYBOARD_NAME="Safecor virtual keyboard"
INPUTS_SOCKET="/var/run/sys-usb-input.sock"
VIRTUAL_MOUSE_PATH="/dev/input/virtual_mouse"
VIRTUAL_TOUCH_PATH="/dev/input/virtual_touch"
VIRTUAL_KEYBOARD_PATH="/dev/input/virtual_keyboard"
CREATE_DOMAINS=True


def find_touchscreen() -> InputDevice:
    """ Finds the input special file for a touchscreen """

    inputs = glob.glob("/dev/input/event*")
    for inputdev in inputs:        
        
        try:
            dev = InputDevice(inputdev)
            caps = dev.capabilities()
            
            if ecodes.EV_ABS in caps:
                # On filtre au cas où le périphérique n'aurait pas les capacités nécessaires
                if not any(t[0] == ecodes.ABS_MT_POSITION_X for t in caps[ecodes.EV_ABS]):
                    continue
                
                # We get all the capabilities
                SysLogger("Orchestrator").info(f"Found a touchscreen: {dev.name}")
                return dev
        except Exception as e:
            print(e)
            continue

    return None


def get_device_path(devname:str) -> str:
    """ Returns a device path from Input """

    for device_path in evdev.list_devices():
        device = evdev.InputDevice(device_path)

        if device.name == devname:
            return device.path
        
    return ""


def create_virtual_mouse():
    """ Creates a new virtual mouse device """

    capabilities = {
        ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_WHEEL_HI_RES],
    }

    input = UInput(capabilities, name=MOUSE_NAME)
    SysLogger("Orchestrator").info(f"Created virtual mouse {input.name}")

    return input


def create_virtual_keyboard():
    """ Creates a new virtual keyboard device """

    capabilities = {
        ecodes.EV_KEY: [ ecodes.KEY_ESC, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0, ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_BACKSPACE, ecodes.KEY_TAB, ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, ecodes.KEY_Y, ecodes.KEY_U, ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_ENTER, ecodes.KEY_LEFTCTRL, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F, ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE, ecodes.KEY_LEFTSHIFT, ecodes.KEY_BACKSLASH, ecodes.KEY_Z, ecodes.KEY_X, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N, ecodes.KEY_M, ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_SLASH, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_KPASTERISK, ecodes.KEY_LEFTALT, ecodes.KEY_SPACE, ecodes.KEY_CAPSLOCK, ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4, ecodes.KEY_F5, ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8, ecodes.KEY_F9, ecodes.KEY_F10, ecodes.KEY_NUMLOCK, ecodes.KEY_SCROLLLOCK, ecodes.KEY_KP7, ecodes.KEY_KP8, ecodes.KEY_KP9, ecodes.KEY_KPMINUS, ecodes.KEY_KP4, ecodes.KEY_KP5, ecodes.KEY_KP6, ecodes.KEY_KPPLUS, ecodes.KEY_KP1, ecodes.KEY_KP2, ecodes.KEY_KP3, ecodes.KEY_KP0, ecodes.KEY_KPDOT, ecodes.KEY_ZENKAKUHANKAKU, ecodes.KEY_102ND, ecodes.KEY_F11, ecodes.KEY_F12, ecodes.KEY_RO, ecodes.KEY_KATAKANA, ecodes.KEY_HIRAGANA, ecodes.KEY_HENKAN, ecodes.KEY_KATAKANAHIRAGANA, ecodes.KEY_MUHENKAN, ecodes.KEY_KPJPCOMMA, ecodes.KEY_KPENTER, ecodes.KEY_RIGHTCTRL, ecodes.KEY_KPSLASH, ecodes.KEY_SYSRQ, ecodes.KEY_RIGHTALT, ecodes.KEY_HOME, ecodes.KEY_UP, ecodes.KEY_PAGEUP, ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_END, ecodes.KEY_DOWN, ecodes.KEY_PAGEDOWN, ecodes.KEY_INSERT, ecodes.KEY_DELETE, ecodes.KEY_MUTE, ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP, ecodes.KEY_POWER, ecodes.KEY_KPEQUAL, ecodes.KEY_PAUSE, ecodes.KEY_KPCOMMA, ecodes.KEY_HANGUEL, ecodes.KEY_HANJA, ecodes.KEY_YEN, ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA, ecodes.KEY_COMPOSE, ecodes.KEY_STOP, ecodes.KEY_AGAIN, ecodes.KEY_PROPS, ecodes.KEY_UNDO, ecodes.KEY_FRONT, ecodes.KEY_COPY, ecodes.KEY_OPEN, ecodes.KEY_PASTE, ecodes.KEY_FIND, ecodes.KEY_CUT, ecodes.KEY_HELP, ecodes.KEY_CALC, ecodes.KEY_SLEEP, ecodes.KEY_WWW, ecodes.KEY_SCREENLOCK, ecodes.KEY_BACK, ecodes.KEY_FORWARD, ecodes.KEY_EJECTCD, ecodes.KEY_NEXTSONG, ecodes.KEY_PLAYPAUSE, ecodes.KEY_PREVIOUSSONG, ecodes.KEY_STOPCD, ecodes.KEY_REFRESH, ecodes.KEY_EDIT, ecodes.KEY_SCROLLUP, ecodes.KEY_SCROLLDOWN, ecodes.KEY_KPLEFTPAREN, ecodes.KEY_KPRIGHTPAREN, ecodes.KEY_F13, ecodes.KEY_F14, ecodes.KEY_F15, ecodes.KEY_F16, ecodes.KEY_F17, ecodes.KEY_F18, ecodes.KEY_F19, ecodes.KEY_F20, ecodes.KEY_F21, ecodes.KEY_F22, ecodes.KEY_F23, ecodes.KEY_F24 ],
        ecodes.EV_MSC: [ ecodes.MSC_SCAN ],
    }

    input = UInput(capabilities, name=KEYBOARD_NAME)
    SysLogger("Orchestrator").info(f"Created virtual keyboard {input.name}")

    return input


def create_virtual_touch(touch_device) -> InputDevice:
    """ Creates a new virtual touchscreen device """

    virtual_touch = UInput.from_device(touch_device, name=TOUCH_NAME)
    SysLogger("Orchestrator").info(f"Created virtual touchscreen {virtual_touch.name}")
    return virtual_touch


def start_events_listener(virtual_mouse, virtual_keyboard, virtual_touch):
    """ Starts an event listener 
    
    The events listener monitors the inputs socket of sys-usb and serializes the events on the 
    virtual devices created before.
    """

    SysLogger("Orchestrator").info("Start input listener")
    buffer = bytearray()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(INPUTS_SOCKET)
    while True:
        raw_data = sock.recv(128)
        if not raw_data:
            SysLogger("Orchestrator").error("Connection with inputs socket lost")
            return
        
        buffer.extend(raw_data)

        while b'\n' in buffer:
            # Trouver la première occurrence du délimiteur '\n'
            delim_pos = buffer.find(b'\n')

            # Extraire la trame complète jusqu'au délimiteur
            frame = buffer[:delim_pos]

            # Supprimer la trame du tampon
            buffer = buffer[delim_pos + 1:]

            try:
                # Désérialiser la trame avec Msgpack
                data = msgpack.unpackb(frame)

                # Supposons que 'data' soit un tableau de 4 entiers
                device_type, event_type, event_code, event_value = data

                if device_type == InputType.MOUSE:
                    device = virtual_mouse
                elif device_type == InputType.KEYBOARD:
                    device = virtual_keyboard
                elif device_type == InputType.TOUCH and virtual_touch is not None:
                    device = virtual_touch
                else:
                    device = None

                if device is not None:
                    device.write(event_type, event_code, event_value)
                    #device.syn()

            except Exception as e:
                SysLogger("Orchestrator").error(f"Erreur lors du traitement de la trame : {e}")


def wait_for_file(filepath):
    """ Waits for a file to exist.
    
    This function is used for synchronization with the XEN Domains creation.
    """

    SysLogger("Orchestrator").info(f"Wait for the file {filepath} to be available")

    while not os.path.exists(filepath):
        time.sleep(0.5)


def get_blacklisted_devices():
    """ Reads the blacklisted PCI devices from the topology file """

    #with open("/etc/safecor/topology.json", 'r') as file:
    #    data = json.load(file)
    #
    #    pci = data.get("pci", {})
    #    blacklist = pci.get("blacklist", "")
    #    return blacklist.split(",")
    config = ConfigurationReader.get_configuration_for_system()

    pci = config.get("pci", {})
    blacklist = pci.get("blacklist", "")
    return blacklist.split(",")


def get_pci_usb_devices():
    """ Gets the list of all PCI USB devices from the system """

    devs = []
    
    cmd = subprocess.run(["lspci"], capture_output=True)
    if cmd.returncode == 0:
        spl = cmd.stdout.split(b'\n')

        for dev in spl:
            if "USB" in dev.decode():
                dev_id = dev.split(b' ')[0]
                if dev_id not in devs:
                    devs.append(dev_id.decode())

    return devs


def is_blacklisted(dev:str, blacklist:list):
    """ Returns true if the device is in the blacklist """

    for d in blacklist:
        if dev.endswith(d):
            return True
        
    return False


def expose_pci_devices():
    """ Passthrough the PCI devices to the sys-usb Domain """

    blacklisted_devices = get_blacklisted_devices()
    pci_usb_devs = get_pci_usb_devices()

    #print(blacklisted_devices)
    #print(pci_usb_devs)

    whitelist = []
    for dev in pci_usb_devs:
        if is_blacklisted(dev, blacklisted_devices):
            SysLogger("Orchestrator").info(f"Device {dev} is ignored because it is blacklisted")
        else:            
            Logger().debug(f"Expose device {dev}")
            cmd = ["xl", "pci-assignable-add", dev]

            res = subprocess.run(cmd)
            if res.returncode == 0:
                SysLogger("Orchestrator").info(f"Device {dev} has been passedthrough to sys-usb")
                whitelist.append(dev)
            else:
                SysLogger("Orchestrator").warn(f"There has been a error while exposing the device {dev} to Xen")           
    
    # Append devices to sys-usb.conf
    if len(whitelist) > 0:
        patch_sys_usb_conf(whitelist)


def patch_sys_usb_conf(usb_devs:list):
    with open("/etc/safecor/xen/sys-usb.conf", 'r') as file:
        lines = file.readlines()
    filtered_lines = [line for line in lines if "pci =" not in line]

    filtered_lines.append("\n")
    filtered_lines.append("# USB devices attached to sys-usb\n")
    devstr = "','".join(usb_devs)
    filtered_lines.append(f"pci = ['{devstr}']\n")

    with open("/etc/safecor/xen/sys-usb.conf", "w") as file:
        file.writelines(filtered_lines)


def start_business_domains():
    #with open('/etc/safecor/topology.json', 'r') as f:
    #    data = json.loads(f.read())
    #    f.close()
    config = ConfigurationReader.get_configuration_for_system()
        
    json_business = config.get("business", {})
    json_domains = json_business.get("domains", [])
    for domain in json_domains:
        domain_name = domain.get("name", "")
        if domain_name == "":
            continue

        cmd = ["/usr/lib/safecor/bin/start-business-domain.sh", domain_name]
        res = subprocess.run(cmd)

        if res == 0:
            SysLogger("Orchestrator").info(f"Started Domain {domain_name}")
        else:
            SysLogger("Orchestrator").critical(f"Domain {domain_name} did not start")


def on_mqtt_message(topic:str, payload:dict):
    pass


def on_mqtt_ready():
    SysLogger("Orchestrator").info("Starting Orchestrator")

    mqtt.add_message_callback(on_mqtt_message)

    # Create virtual input devices
    virtual_mouse = create_virtual_mouse()
    # Create symlinks for the virtual inputs which act as a permalinks
    mouse_path = get_device_path(MOUSE_NAME)
    if mouse_path == "":
        SysLogger("Orchestrator").warn("The mouse device path has not been found")
    else:
        if os.path.exists(VIRTUAL_MOUSE_PATH) or os.path.islink(VIRTUAL_MOUSE_PATH):
            os.remove(VIRTUAL_MOUSE_PATH)
            time.sleep(0.1)
        os.symlink(mouse_path, VIRTUAL_MOUSE_PATH)

    virtual_keyboard = create_virtual_keyboard()
    # Create symlinks for the virtual inputs which act as a permalinks
    keyboard_path = get_device_path(KEYBOARD_NAME)
    if keyboard_path == "":
        SysLogger("Orchestrator").error("The keyboard device path has not been found")
    else:
        if os.path.exists(VIRTUAL_KEYBOARD_PATH) or os.path.islink(VIRTUAL_KEYBOARD_PATH):
            os.remove(VIRTUAL_KEYBOARD_PATH)
            time.sleep(0.1)
        os.symlink(keyboard_path, VIRTUAL_KEYBOARD_PATH)

    # Find touch screen and keep capabilities
    touch_device = find_touchscreen()
    if touch_device is None:
        SysLogger("Orchestrator").info("No touchscreen found on the system")
        virtual_touch = None
    else:
        #print(touch_caps)
        virtual_touch = create_virtual_touch(touch_device)
        touch_path = get_device_path(TOUCH_NAME)
        if touch_path == "":
            SysLogger("Orchestrator").error("The touch device path has not been found")
        else:
            if os.path.exists(VIRTUAL_TOUCH_PATH) or os.path.islink(VIRTUAL_TOUCH_PATH):
                os.remove(VIRTUAL_TOUCH_PATH)
                time.sleep(0.1)
            os.symlink(touch_path, "/dev/input/virtual_touch")

    # Attach PCI devices
    expose_pci_devices()

    # Start sys-usb
    if CREATE_DOMAINS:
        cmd = ["/usr/lib/safecor/bin/start-sys-usb.sh"]
        res = subprocess.run(cmd)

        if res == 0:
            SysLogger("Orchestrator").info("Started Domain sys-usb")
        else:
            SysLogger("Orchestrator").critical("Domain sys-usb did not start")

        # Start sys-gui
        cmd = ["/usr/lib/safecor/bin/start-sys-gui.sh"]
        res = subprocess.run(cmd)

        if res == 0:
            SysLogger("Orchestrator").info("Started Domain sys-gui")
        else:
            SysLogger("Orchestrator").critical("Domain sys-gui did not start")

        # Start all other domains
        start_business_domains()

        # When the domain sys-usb is rebooted, the socket is list
        # so we need to loop
        while True:
            # Wait for the inputs socket to be ready
            wait_for_file(INPUTS_SOCKET)

            # Start listening for events from sys-usb
            start_events_listener(virtual_mouse, virtual_keyboard, virtual_touch)


if __name__ == "__main__":
    SysLogger("Orchestrator").info("Starting Safecor orchestrator...")
    
    mqtt.add_connected_callback(on_mqtt_ready)
    mqtt.start()

    mqtt_lock.wait()
    SysLogger("Orchestrator").info("Safecor orchestrator closed")