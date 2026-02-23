import os
import glob
import subprocess
import time
import threading
import json
import evdev
from evdev import InputDevice, ecodes, UInput
from safecor import MqttFactory, Logger, InputType, SysLogger, ConfigurationReader, System
from inputs_proxy import InputsProxy

mqtt_lock = threading.Event()
mqtt = MqttFactory.create_mqtt_client_dom0("Orchestrator")
MOUSE_NAME="Safecor virtual mouse"
TOUCH_NAME="Safecor virtual touchscreen"
KEYBOARD_NAME="Safecor virtual keyboard"
INPUTS_SOCKET_PATH="/var/run/safecor"
INPUTS_SOCKET_FILENAME="sys-usb-input.sock"
VIRTUAL_MOUSE_PATH="/var/run/safecor/virtual_mouse"
VIRTUAL_TOUCH_PATH="/var/run/safecor/virtual_touch"
VIRTUAL_KEYBOARD_PATH="/var/run/safecor/virtual_keyboard"
inputs_proxy = InputsProxy()

def create_virtual_devices() -> tuple[InputDevice, InputDevice, InputDevice]:
    """ Creates virtual devices for the mouse, keyboard and touch """

    # Create virtual input devices
    virtual_mouse = create_virtual_mouse()
    # Create symlinks for the virtual inputs which act as a permalinks
    mouse_path = get_device_path(MOUSE_NAME)
    if mouse_path == "":
        SysLogger("Orchestrator").warn("The mouse device path has not been found")
    else:
        if os.path.exists(VIRTUAL_MOUSE_PATH) or os.path.islink(VIRTUAL_MOUSE_PATH):
            try:
                os.remove(VIRTUAL_MOUSE_PATH)
                time.sleep(0.1)
            except Exception as e:
                SysLogger("Orchestrator").error(f"Could not remove current virtual mouse device. {e}")

        try:
            os.symlink(mouse_path, VIRTUAL_MOUSE_PATH)
        except Exception as e:
            SysLogger("Orchestrator").error(f"Could not create a symlink for the virtual mouse device. {e}")

    virtual_keyboard = create_virtual_keyboard()
    # Create symlinks for the virtual inputs which act as a permalinks
    keyboard_path = get_device_path(KEYBOARD_NAME)
    if keyboard_path == "":
        SysLogger("Orchestrator").error("The keyboard device path has not been found")
    else:
        if os.path.exists(VIRTUAL_KEYBOARD_PATH) or os.path.islink(VIRTUAL_KEYBOARD_PATH):
            try:
                os.remove(VIRTUAL_KEYBOARD_PATH)
                time.sleep(0.1)
            except Exception as e:
                SysLogger("Orchestrator").error(f"Could not remove current virtual keyboard device. {e}")

        try:
            os.symlink(keyboard_path, VIRTUAL_KEYBOARD_PATH)
        except Exception as e:
            SysLogger("Orchestrator").error(f"Could not create a symlink for the virtual keyboard device. {e}")

    # Find touch screen and keep capabilities
    touch_device = find_touchscreen()
    if touch_device is None:
        SysLogger("Orchestrator").info("No touchscreen found on the system")
        virtual_touch = None
    else:
        #print(touch_caps)
        virtual_touch = create_virtual_touch()
        touch_path = get_device_path(TOUCH_NAME)
        if touch_path == "":
            SysLogger("Orchestrator").error("The touch device path has not been found")
        else:            
            if os.path.exists(VIRTUAL_TOUCH_PATH) or os.path.islink(VIRTUAL_TOUCH_PATH):
                try:
                    os.remove(VIRTUAL_TOUCH_PATH)
                    time.sleep(0.1)
                except Exception as e:
                    SysLogger("Orchestrator").error(f"Could not remove current virtual touch device. {e}")

            try:
                os.symlink(touch_path, VIRTUAL_TOUCH_PATH)
            except Exception as e:
                SysLogger("Orchestrator").error(f"Could not create a symlink for the virtual touch device. {e}") 

    return virtual_mouse, virtual_keyboard, virtual_touch

def find_touchscreen() -> InputDevice:
    """ Finds the input device for a touchscreen """

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


def create_virtual_mouse() -> InputDevice:
    """ Creates a new virtual mouse device 
    
    The device created has the following capabilities: 
        - EV_KEY: BTN_LEFT, BTN_RIGHT
        - EV_REL: REL_X, REL_Y, REL_WHEEL, REL_WHEEL_HI_RES
    """

    capabilities = {
        ecodes.EV_KEY: [ecodes.BTN_LEFT, ecodes.BTN_RIGHT],
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL, ecodes.REL_WHEEL_HI_RES],
    }

    try:
        input = UInput(capabilities, name=MOUSE_NAME)
        SysLogger("Orchestrator").info(f"Created device {input.name}")
        return input
    except Exception as e:
        SysLogger("Orchestrator").error(f"Error while creating the virtual mouse: {e}")    
    

def create_virtual_keyboard() -> InputDevice:
    """ Creates a new virtual keyboard device 
    
    The keyboard created has the following capabilities:
        - EV_KEY: KEY_ESC, KEY_1, KEY_2, KEY_3, KEY_4, KEY_5, KEY_6, KEY_7, KEY_8, KEY_9, KEY_0, KEY_MINUS, KEY_EQUAL, KEY_BACKSPACE, KEY_TAB, KEY_Q, KEY_W, KEY_E, KEY_R, KEY_T, KEY_Y, KEY_U, KEY_I, KEY_O, KEY_P, KEY_LEFTBRACE, KEY_RIGHTBRACE, KEY_ENTER, KEY_LEFTCTRL, KEY_A, KEY_S, KEY_D, KEY_F, KEY_G, KEY_H, KEY_J, KEY_K, KEY_L, KEY_SEMICOLON, KEY_APOSTROPHE, KEY_GRAVE, KEY_LEFTSHIFT, KEY_BACKSLASH, KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B, KEY_N, KEY_M, KEY_COMMA, KEY_DOT, KEY_SLASH, KEY_RIGHTSHIFT, KEY_KPASTERISK, KEY_LEFTALT, KEY_SPACE, KEY_CAPSLOCK, KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6, KEY_F7, KEY_F8, KEY_F9, KEY_F10, KEY_NUMLOCK, KEY_SCROLLLOCK, KEY_KP7, KEY_KP8, KEY_KP9, KEY_KPMINUS, KEY_KP4, KEY_KP5, KEY_KP6, KEY_KPPLUS, KEY_KP1, KEY_KP2, KEY_KP3, KEY_KP0, KEY_KPDOT, KEY_ZENKAKUHANKAKU, KEY_102ND, KEY_F11, KEY_F12, KEY_RO, KEY_KATAKANA, KEY_HIRAGANA, KEY_HENKAN, KEY_KATAKANAHIRAGANA, KEY_MUHENKAN, KEY_KPJPCOMMA, KEY_KPENTER, KEY_RIGHTCTRL, KEY_KPSLASH, KEY_SYSRQ, KEY_RIGHTALT, KEY_HOME, KEY_UP, KEY_PAGEUP, KEY_LEFT, KEY_RIGHT, KEY_END, KEY_DOWN, KEY_PAGEDOWN, KEY_INSERT, KEY_DELETE, KEY_MUTE, KEY_VOLUMEDOWN, KEY_VOLUMEUP, KEY_POWER, KEY_KPEQUAL, KEY_PAUSE, KEY_KPCOMMA, KEY_HANGUEL, KEY_HANJA, KEY_YEN, KEY_LEFTMETA, KEY_RIGHTMETA, KEY_COMPOSE, KEY_STOP, KEY_AGAIN, KEY_PROPS, KEY_UNDO, KEY_FRONT, KEY_COPY, KEY_OPEN, KEY_PASTE, KEY_FIND, KEY_CUT, KEY_HELP, KEY_CALC, KEY_SLEEP, KEY_WWW, KEY_SCREENLOCK, KEY_BACK, KEY_FORWARD, KEY_EJECTCD, KEY_NEXTSONG, KEY_PLAYPAUSE, KEY_PREVIOUSSONG, KEY_STOPCD, KEY_REFRESH, KEY_EDIT, KEY_SCROLLUP, KEY_SCROLLDOWN, KEY_KPLEFTPAREN, KEY_KPRIGHTPAREN, KEY_F13, KEY_F14, KEY_F15, KEY_F16, KEY_F17, KEY_F18, KEY_F19, KEY_F20, KEY_F21, KEY_F22, KEY_F23, KEY_F24
    """

    capabilities = {
        ecodes.EV_KEY: [ ecodes.KEY_ESC, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0, ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_BACKSPACE, ecodes.KEY_TAB, ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, ecodes.KEY_Y, ecodes.KEY_U, ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_ENTER, ecodes.KEY_LEFTCTRL, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F, ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE, ecodes.KEY_LEFTSHIFT, ecodes.KEY_BACKSLASH, ecodes.KEY_Z, ecodes.KEY_X, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N, ecodes.KEY_M, ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_SLASH, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_KPASTERISK, ecodes.KEY_LEFTALT, ecodes.KEY_SPACE, ecodes.KEY_CAPSLOCK, ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4, ecodes.KEY_F5, ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8, ecodes.KEY_F9, ecodes.KEY_F10, ecodes.KEY_NUMLOCK, ecodes.KEY_SCROLLLOCK, ecodes.KEY_KP7, ecodes.KEY_KP8, ecodes.KEY_KP9, ecodes.KEY_KPMINUS, ecodes.KEY_KP4, ecodes.KEY_KP5, ecodes.KEY_KP6, ecodes.KEY_KPPLUS, ecodes.KEY_KP1, ecodes.KEY_KP2, ecodes.KEY_KP3, ecodes.KEY_KP0, ecodes.KEY_KPDOT, ecodes.KEY_ZENKAKUHANKAKU, ecodes.KEY_102ND, ecodes.KEY_F11, ecodes.KEY_F12, ecodes.KEY_RO, ecodes.KEY_KATAKANA, ecodes.KEY_HIRAGANA, ecodes.KEY_HENKAN, ecodes.KEY_KATAKANAHIRAGANA, ecodes.KEY_MUHENKAN, ecodes.KEY_KPJPCOMMA, ecodes.KEY_KPENTER, ecodes.KEY_RIGHTCTRL, ecodes.KEY_KPSLASH, ecodes.KEY_SYSRQ, ecodes.KEY_RIGHTALT, ecodes.KEY_HOME, ecodes.KEY_UP, ecodes.KEY_PAGEUP, ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_END, ecodes.KEY_DOWN, ecodes.KEY_PAGEDOWN, ecodes.KEY_INSERT, ecodes.KEY_DELETE, ecodes.KEY_MUTE, ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP, ecodes.KEY_POWER, ecodes.KEY_KPEQUAL, ecodes.KEY_PAUSE, ecodes.KEY_KPCOMMA, ecodes.KEY_HANGUEL, ecodes.KEY_HANJA, ecodes.KEY_YEN, ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA, ecodes.KEY_COMPOSE, ecodes.KEY_STOP, ecodes.KEY_AGAIN, ecodes.KEY_PROPS, ecodes.KEY_UNDO, ecodes.KEY_FRONT, ecodes.KEY_COPY, ecodes.KEY_OPEN, ecodes.KEY_PASTE, ecodes.KEY_FIND, ecodes.KEY_CUT, ecodes.KEY_HELP, ecodes.KEY_CALC, ecodes.KEY_SLEEP, ecodes.KEY_WWW, ecodes.KEY_SCREENLOCK, ecodes.KEY_BACK, ecodes.KEY_FORWARD, ecodes.KEY_EJECTCD, ecodes.KEY_NEXTSONG, ecodes.KEY_PLAYPAUSE, ecodes.KEY_PREVIOUSSONG, ecodes.KEY_STOPCD, ecodes.KEY_REFRESH, ecodes.KEY_EDIT, ecodes.KEY_SCROLLUP, ecodes.KEY_SCROLLDOWN, ecodes.KEY_KPLEFTPAREN, ecodes.KEY_KPRIGHTPAREN, ecodes.KEY_F13, ecodes.KEY_F14, ecodes.KEY_F15, ecodes.KEY_F16, ecodes.KEY_F17, ecodes.KEY_F18, ecodes.KEY_F19, ecodes.KEY_F20, ecodes.KEY_F21, ecodes.KEY_F22, ecodes.KEY_F23, ecodes.KEY_F24 ],
        ecodes.EV_MSC: [ ecodes.MSC_SCAN ],
    }

    try:
        input = UInput(capabilities, name=KEYBOARD_NAME)
        SysLogger("Orchestrator").info(f"Created device{input.name}")
        return input
    except Exception as e:
        SysLogger("Orchestrator").error(f"Error while creating the virtual keyboard: {e}")        


def create_virtual_touch() -> InputDevice:
    """ Creates a new virtual touchscreen device 
    
    The touch device created has the following capabilities:
        - EV_KEY: BTN_LEFT, BTN_RIGHT
        - EV_ABS: ABS_MT_POSITION_X, ABS_MT_POSITION_Y
    """

    #virtual_touch = UInput.from_device(touch_device, name=TOUCH_NAME)
    capabilities = {
        ecodes.EV_KEY: [ ecodes.BTN_LEFT, ecodes.BTN_RIGHT ],
        ecodes.EV_MSC: [ ecodes.ABS_MT_POSITION_X, ecodes.ABS_MT_POSITION_Y ]
    }

    try:
        input = UInput(capabilities, name=TOUCH_NAME)
        SysLogger("Orchestrator").info(f"Created device {input.name}")
        return input
    except Exception as e:
        SysLogger("Orchestrator").error(f"Error while creating the virtual touchscreen: {e}")    


#def wait_for_file(filepath):
#    """ Waits for a file to exist.
#    
#    This function is used for synchronization with the XEN Domains creation.
#    """
#
#    SysLogger("Orchestrator").info(f"Wait for the file {filepath} to be available")
#
#    while not os.path.exists(filepath):
#        time.sleep(0.5)


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
            cmd = ["/usr/bin/doas", "/usr/sbin/xl", "pci-assignable-add", dev]

            res = subprocess.run(cmd)
            if res.returncode == 0:
                SysLogger("Orchestrator").info(f"Device {dev} has been passedthrough to sys-usb")
                whitelist.append(dev)
            else:
                SysLogger("Orchestrator").warn(f"There has been an error while exposing the device {dev} to Xen")           
    
    # Append devices to sys-usb.conf
    if len(whitelist) > 0:
        patch_sys_usb_conf(whitelist)


def patch_sys_usb_conf(usb_devs:list):
    """ Adds the PCI passthrough option to the sys-usb XL configuration file """

    with open("/etc/safecor/xen/sys-usb.conf", 'r') as file:
        lines = file.readlines()
    filtered_lines = [line for line in lines if "pci =" not in line]

    filtered_lines.append("\n")
    filtered_lines.append("# USB devices attached to sys-usb\n")
    devstr = "','".join(usb_devs)
    filtered_lines.append(f"pci = ['{devstr}']\n")

    with open("/etc/safecor/xen/sys-usb.conf", "w") as file:
        file.writelines(filtered_lines)

def can_create_domains() -> bool:
    """ Verifies whether the automatic creation of the Domains is authorized 
    
    The automatic creation of the Domains can be disabled by adding `no_autostart` to the kernel command line.
    """

    with open("/proc/cmdline", "r") as f:
        cmdline = f.read()

    if "no_autostart" in cmdline.split() or "NO_AUTOSTART" in cmdline.split():
        SysLogger("Orchesrator").info("The Domains autostart is disabled from the kernel command line")
        return False
    
    return True


def start_business_domains():
    """ Starts the business Domains"""

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

        cmd = ["/usr/bin/doas", "/usr/lib/safecor/bin/start-business-domain.sh", domain_name]
        res = subprocess.run(cmd)

        if res == 0:
            SysLogger("Orchestrator").info(f"Started Domain {domain_name}")
        else:
            SysLogger("Orchestrator").critical(f"Domain {domain_name} did not start")


def on_mqtt_message(topic:str, payload:dict):
    # Currently unused
    pass

def on_inputs_socket_file_changed(path:str, filename:str, exists:bool):
    """ This function is a callback for the file monitor that monitors the inputs socket file """

    if exists:
        SysLogger("Orchestrator").info("The inputs socket file is ready. Start the event listener")
        inputs_proxy.start()

    else:
        SysLogger("Orchestrator").info("The inputs socket file has disappeared. Stop the event listener")
        inputs_proxy.stop()

def on_mqtt_ready():
    """ Callback for MQTT broker connection """

    SysLogger("Orchestrator").info("Starting Orchestrator")

    mqtt.add_message_callback(on_mqtt_message)

    # Create virtual devices
    virtual_mouse, virtual_keyboard, virtual_touch = create_virtual_devices()
    inputs_proxy.virtual_mouse = virtual_mouse
    inputs_proxy.virtual_keyboard = virtual_keyboard
    inputs_proxy.virtual_touch = virtual_touch

    # Attach PCI devices
    expose_pci_devices()

    # Start sys-usb
    if can_create_domains():
        cmd = ["/usr/bin/doas", "/usr/lib/safecor/bin/start-sys-usb.sh"]
        res = subprocess.run(cmd, check= True)

        if res.returncode == 0:
            SysLogger("Orchestrator").info("Started Domain sys-usb")
        else:
            SysLogger("Orchestrator").critical("Domain sys-usb did not start")

        # Start sys-gui
        cmd = ["/usr/bin/doas", "/usr/lib/safecor/bin/start-sys-gui.sh"]
        res = subprocess.run(cmd, check= True)

        if res.returncode == 0:
            SysLogger("Orchestrator").info("Started Domain sys-gui")
        else:
            SysLogger("Orchestrator").critical("Domain sys-gui did not start")

        # Start all other domains
        start_business_domains()

        # The monitor will look at the inputs file fomr sys-usb
        # and when sys-usb is rebooted, the events listener will stop and start
        # back after the reboor
        System().monitor_file(INPUTS_SOCKET_PATH, INPUTS_SOCKET_FILENAME, on_inputs_socket_file_changed)

        # When the domain sys-usb is rebooted, the socket is list
        # so we need to loop
        #while True:
        #    # Wait for the inputs socket to be ready
        #    wait_for_file(INPUTS_SOCKET)
        #
        #    # Start listening for events from sys-usb
        #    start_events_listener(virtual_mouse, virtual_keyboard, virtual_touch)


if __name__ == "__main__":
    SysLogger("Orchestrator").info("Starting Safecor orchestrator...")

    mqtt.add_connected_callback(on_mqtt_ready)
    mqtt.start()

    mqtt_lock.wait()
    SysLogger("Orchestrator").info("Safecor orchestrator closed")
