""" \author Tristan Israël """

import glob
import threading
import serial
import time
import struct
import msgpack
try:
    from evdev import InputDevice, ecodes, InputEvent
except ImportError as e:
    print("The package evdev is not available. Functionalities will be missing.")
    class InputDevice:
        """ This is a fake InputDevice due to missing dependancy"""
from . import SysLogger, Mouse, SingletonMeta, InputType
from . import MqttClient, Constants

INPUT_EVENT_FORMAT = "HHI"  # HH = type, code, I = value (unsigned int)
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)

class InputsDaemon(metaclass=SingletonMeta):
    """ This class monitors mouse, touch device and keyboard inputs and serialize filtered information through the XenBus.
    
    The communication channel (pvchan) *inputs* is used between sys-usb and the Dom0.

    **This class is not intended to be used in a project, it is directly managed by the core**.
    
    Mouse
    =====

    Information on mouse position and buttons are all transmitted each time an event occurs. It means that the 
    information are sent as a data structure containing x and y position and the buttons state.
    
    """    

    #__mouse = Mouse()
    __xenbus_socket_path = None
    #__xenbus_iface_ready = False
    __xenbus_socket = None
    __monitored_inputs = []
    #__mouse_max_x = 1
    #__mouse_max_y = 1
    #__last_x = 0
    #__last_y = 0
    __can_run = True
    #__mqtt_client = None

    def start(self, mqtt_client: MqttClient):
        """ Starts the inputs daemon 
        
            As soon as it starts, the daemon looks for mouses, touchscreens and keyboards.
            When it finds a device it starts monitoring it in a thread and serializes all
            input events on the pv channel ``inputs``.
        """

        #self.__mqtt_client = mqtt_client
        SysLogger("Input Daemon").info("Starting input daemon")
        self.__can_run = True

        # Start XenBus messaging
        self.__xenbus_socket_path = Constants.DOMU_INPUT_SOCKET_FILEPATH
        if not self.__connect_xenbus():
            return

        # Start inputs listeners
        threading.Thread(target=self.__find_mouse).start()
        threading.Thread(target=self.__find_touchscreen).start()
        threading.Thread(target=self.__find_keyboard).start()

    def stop(self):
        """ Stops the inputs daemon """

        self.__can_run = False
        self.__disconnect_xenbus()

    def __find_mouse(self):
        # This function is ran in a specific thread
        SysLogger("Input Daemon").info("Looking for a mouse...")

        while True:
            inputs = glob.glob("/dev/input/event*")
            for input_ in inputs:
                #Logger().debug("Fichier {}".format(input))
                try:
                    dev = InputDevice(input_)
                    type_input = self.__input_type(dev)
                    if type_input == InputType.MOUSE and input_ not in self.__monitored_inputs:
                        threading.Thread(target= self.__monitor_mouse, args=(dev,)).start()
                        self.__monitored_inputs.append(input_)
                except Exception:
                    pass # Ignore all errors silently
            
            # Wait a little and start over
            time.sleep(0.5)

    def __find_touchscreen(self):
        SysLogger("Input Daemon").info("Looking for a touchscreen...")

        while self.__can_run:
            inputs = glob.glob("/dev/input/event*")

            for input_ in inputs:
                try:
                    dev = InputDevice(input_)
                    type_input = self.__input_type(dev)

                    if type_input == InputType.TOUCH and input_ not in self.__monitored_inputs:
                        # We get min and max horizontal values to determine the resolution
                        caps = dev.capabilities()

                        # We filter in cas the device does not have the required capabilities
                        if not any(t[0] == ecodes.ABS_MT_POSITION_X for t in caps[ecodes.EV_ABS]):
                            continue

                        #self.__mouse_max_x = caps[ecodes.EV_ABS][ecodes.ABS_X][1].max
                        #self.__mouse_max_y = caps[ecodes.EV_ABS][ecodes.ABS_Y][1].max

                        #print("max_x={}, max_y={}".format(self.mouse.max_x, self.mouse.max_y))

                        threading.Thread(target= self.__monitor_touchscreen, args=(dev,)).start()
                        self.__monitored_inputs.append(input_)
                except Exception as e:
                    SysLogger("Input Daemon").warn(f"Error during touchscreen search. {e}")
                    pass # Ignore all errors silently

            # Wait a little and start over
            time.sleep(0.5)

    def __serialize_event(self, type_input, event):
        """ Serializes an event as packed bytes in order to transmit. """        
        # event.type : unsigned 16bit
        # event.code : unsigned 16bit
        # event.value : signed 32bit
        payload = msgpack.packb([type_input, event.type, event.code, event.value])
        return payload +b'\n'

    def __monitor_mouse(self, mouse):
        SysLogger("Input Daemon").info(f"Monitor the mouse {mouse.name}")

        try:
            for event in mouse.read_loop():
                if event.type in [ecodes.EV_KEY, ecodes.EV_REL, ecodes.EV_ABS, ecodes.EV_SYN]:
                    serialized = self.__serialize_event(InputType.MOUSE, event)
                    self.__xenbus_socket.write(serialized)
                    #print(f"Sent: {serialized.strip()}")

                if not self.__can_run:
                    return
        except Exception:
            SysLogger("Input Daemon").warn(f"The mouse {mouse.name} is not available anymore")
            self.__monitored_inputs.remove(mouse.path)

    def __monitor_touchscreen(self, touch):
        SysLogger("Input Daemon").info(f"Monitor the touchscreen {touch.name}")

        """ filtered_events = [
            ecodes.EV_KEY,
            ecodes.EV_MSC,
            ecodes.EV_ABS,
            ecodes.EV_SYN,
            ecodes.ABS_MT_SLOT,
            ecodes.ABS_MT_POSITION_X,
            ecodes.ABS_MT_POSITION_Y,
            ecodes.ABS_MT_TRACKING_ID
        ] """

        try:
            for event in touch.read_loop():
                serialized = self.__serialize_event(InputType.TOUCH, event)
                self.__xenbus_socket.write(serialized)
                #print(f"Sent: {serialized.strip()}")

                if not self.__can_run:
                    return
        except Exception:
            SysLogger("Input Daemon").warn(f"The touchscreen {touch.name} is not available anymore")
            self.__monitored_inputs.remove(touch.path)

    def __find_keyboard(self):
        # This function is ran in a specific thread
        SysLogger("Input Daemon").info("Looking for a keyboard...")

        while True:
            inputs = glob.glob("/dev/input/event*")
            for input_ in inputs:
                #Logger().debug("Fichier {}".format(input))
                try:
                    dev = InputDevice(input_)
                    type_input = self.__input_type(dev)
                    if type_input == InputType.KEYBOARD and input_ not in self.__monitored_inputs:
                        threading.Thread(target= self.__monitor_keyboard, args=(dev,)).start()
                        self.__monitored_inputs.append(input_)
                except Exception:
                    pass # Ignore all errors silently
            
            # Wait a little and start over
            time.sleep(0.5)
    
    def __monitor_keyboard(self, keyboard):
        SysLogger("Input Daemon").info(f"Monitor the keyboard {keyboard.name}")

        for event in keyboard.read_loop():
            if (event.type == ecodes.EV_KEY and event.code in [ ecodes.KEY_ESC, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4, ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9, ecodes.KEY_0, ecodes.KEY_MINUS, ecodes.KEY_EQUAL, ecodes.KEY_BACKSPACE, ecodes.KEY_TAB, ecodes.KEY_Q, ecodes.KEY_W, ecodes.KEY_E, ecodes.KEY_R, ecodes.KEY_T, ecodes.KEY_Y, ecodes.KEY_U, ecodes.KEY_I, ecodes.KEY_O, ecodes.KEY_P, ecodes.KEY_LEFTBRACE, ecodes.KEY_RIGHTBRACE, ecodes.KEY_ENTER, ecodes.KEY_LEFTCTRL, ecodes.KEY_A, ecodes.KEY_S, ecodes.KEY_D, ecodes.KEY_F, ecodes.KEY_G, ecodes.KEY_H, ecodes.KEY_J, ecodes.KEY_K, ecodes.KEY_L, ecodes.KEY_SEMICOLON, ecodes.KEY_APOSTROPHE, ecodes.KEY_GRAVE, ecodes.KEY_LEFTSHIFT, ecodes.KEY_BACKSLASH, ecodes.KEY_Z, ecodes.KEY_X, ecodes.KEY_C, ecodes.KEY_V, ecodes.KEY_B, ecodes.KEY_N, ecodes.KEY_M, ecodes.KEY_COMMA, ecodes.KEY_DOT, ecodes.KEY_SLASH, ecodes.KEY_RIGHTSHIFT, ecodes.KEY_KPASTERISK, ecodes.KEY_LEFTALT, ecodes.KEY_SPACE, ecodes.KEY_CAPSLOCK, ecodes.KEY_F1, ecodes.KEY_F2, ecodes.KEY_F3, ecodes.KEY_F4, ecodes.KEY_F5, ecodes.KEY_F6, ecodes.KEY_F7, ecodes.KEY_F8, ecodes.KEY_F9, ecodes.KEY_F10, ecodes.KEY_NUMLOCK, ecodes.KEY_SCROLLLOCK, ecodes.KEY_KP7, ecodes.KEY_KP8, ecodes.KEY_KP9, ecodes.KEY_KPMINUS, ecodes.KEY_KP4, ecodes.KEY_KP5, ecodes.KEY_KP6, ecodes.KEY_KPPLUS, ecodes.KEY_KP1, ecodes.KEY_KP2, ecodes.KEY_KP3, ecodes.KEY_KP0, ecodes.KEY_KPDOT, ecodes.KEY_ZENKAKUHANKAKU, ecodes.KEY_102ND, ecodes.KEY_F11, ecodes.KEY_F12, ecodes.KEY_RO, ecodes.KEY_KATAKANA, ecodes.KEY_HIRAGANA, ecodes.KEY_HENKAN, ecodes.KEY_KATAKANAHIRAGANA, ecodes.KEY_MUHENKAN, ecodes.KEY_KPJPCOMMA, ecodes.KEY_KPENTER, ecodes.KEY_RIGHTCTRL, ecodes.KEY_KPSLASH, ecodes.KEY_SYSRQ, ecodes.KEY_RIGHTALT, ecodes.KEY_HOME, ecodes.KEY_UP, ecodes.KEY_PAGEUP, ecodes.KEY_LEFT, ecodes.KEY_RIGHT, ecodes.KEY_END, ecodes.KEY_DOWN, ecodes.KEY_PAGEDOWN, ecodes.KEY_INSERT, ecodes.KEY_DELETE, ecodes.KEY_MUTE, ecodes.KEY_VOLUMEDOWN, ecodes.KEY_VOLUMEUP, ecodes.KEY_POWER, ecodes.KEY_KPEQUAL, ecodes.KEY_PAUSE, ecodes.KEY_KPCOMMA, ecodes.KEY_HANGUEL, ecodes.KEY_HANJA, ecodes.KEY_YEN, ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA, ecodes.KEY_COMPOSE, ecodes.KEY_STOP, ecodes.KEY_AGAIN, ecodes.KEY_PROPS, ecodes.KEY_UNDO, ecodes.KEY_FRONT, ecodes.KEY_COPY, ecodes.KEY_OPEN, ecodes.KEY_PASTE, ecodes.KEY_FIND, ecodes.KEY_CUT, ecodes.KEY_HELP, ecodes.KEY_CALC, ecodes.KEY_SLEEP, ecodes.KEY_WWW, ecodes.KEY_SCREENLOCK, ecodes.KEY_BACK, ecodes.KEY_FORWARD, ecodes.KEY_EJECTCD, ecodes.KEY_NEXTSONG, ecodes.KEY_PLAYPAUSE, ecodes.KEY_PREVIOUSSONG, ecodes.KEY_STOPCD, ecodes.KEY_REFRESH, ecodes.KEY_EDIT, ecodes.KEY_SCROLLUP, ecodes.KEY_SCROLLDOWN, ecodes.KEY_KPLEFTPAREN, ecodes.KEY_KPRIGHTPAREN, ecodes.KEY_F13, ecodes.KEY_F14, ecodes.KEY_F15, ecodes.KEY_F16, ecodes.KEY_F17, ecodes.KEY_F18, ecodes.KEY_F19, ecodes.KEY_F20, ecodes.KEY_F21, ecodes.KEY_F22, ecodes.KEY_F23, ecodes.KEY_F24 ]
                or (event.type == ecodes.EV_MSC and event.code == ecodes.MSC_SCAN)
            ):
                serialized = self.__serialize_event(InputType.KEYBOARD, event)
                self.__xenbus_socket.write(serialized)
                #print(f"Sent: {serialized.strip()}")

            if not self.__can_run:
                return

    def __input_type(self, input_:InputDevice):
        caps = input_.capabilities()
        keys = caps.get(ecodes.EV_KEY)

        if keys is None:
            return InputType.UNKNOWN
        
        if ecodes.KEY_ESC in keys:
            return InputType.KEYBOARD
        elif ecodes.BTN_LEFT in keys:
            return InputType.MOUSE
        elif ecodes.BTN_TOUCH in keys:
            return InputType.TOUCH
    
    def __connect_xenbus(self) -> bool:
        #Ouvre le flux avec la socket
        SysLogger("Input Daemon").debug(f"Open Xenbus I/O channel {self.__xenbus_socket_path}")

        try:
            self.__xenbus_socket = serial.Serial(port= self.__xenbus_socket_path)
            #self.__xenbus_iface_ready = True
            SysLogger("Input Daemon").info("I/O channel is open")
            return True
        except serial.SerialException as e:
            self.__xenbus_socket = None
            SysLogger("Input Daemon").error(f"Impossible to open the serial port {self.__xenbus_socket_path}")
            SysLogger("Input Daemon").error(str(e))
            return False
        
    def __disconnect_xenbus(self):
        if self.__xenbus_socket is not None:
            SysLogger("Input Daemon").info("Close Xenbus I/O socket")
            self.__xenbus_socket.close()
        