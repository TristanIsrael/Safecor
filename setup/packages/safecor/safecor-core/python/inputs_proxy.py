import threading
import socket
import msgpack
from evdev import InputDevice, ecodes, UInput
from safecor import SysLogger, InputType, XenStore

class InputsProxy:
    """ The inputs proxy monitors the inputs socket of sys-usb and serializes the events on the 
        virtual devices created before.

        Data are read from a unique Unix Domain Socket (PV channel) from the sys-usb Domain. All 
        the inputs are serialized in this channel. They are deserialized by this proxy and copied
        in different virtual input devices (uinput) attached to a Domains's QEMU instance.

        The proxy manages different virtual inputs and copies the real physical input only to the
        virtual devices attached to the Domain that has the focus.
    """
    
    __virtual_mouses = {}
    __virtual_keyboards = {}
    __virtual_touches = {}
    __virtual_mouse = None 
    __virtual_keyboard = None
    __virtual_touch = None
    __xenstore = XenStore()
    __can_run = False
    __is_running = False
    __thread = None
    INPUTS_SOCKET="/var/run/safecor/sys-usb-input.sock"

    def start(self):
        """ Starts the inputs proxy """

        if self.__is_running:
            return
        
        self.__can_run = True

        SysLogger("Inputs proxy").info("The inputs proxy is going to start")
        self.__thread = threading.Thread(target= self.events_proxy_worker, daemon=True)
        self.__thread.start()

        # Monitor the focused domain from the XenStore
        self.__xenstore.monitor(XenStore.XsDomain.System, XenStore.XsKey.InputFocus, "inputs-focus", self.__on_focus_changed)

    def stop(self):
        """ Stops the inputs proxy """

        self.__can_run = False

    def events_proxy_worker(self):
        """ Starts the inputs proxy """

        SysLogger("Input proxy").info("Start input proxy")
        buffer = bytearray()

        self.__is_running = True

        while self.__can_run and self.__is_running:
            # If the connection is lost accidentaly we have to recreate it
            buffer.clear()

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.INPUTS_SOCKET)
            self.__is_running = True

            while self.__can_run:
                raw_data = sock.recv(128)

                if not raw_data:
                    SysLogger("Input proxy").error("Connection with inputs socket lost")
                    break # We get out of this loop to recreate the connection

                buffer.extend(raw_data)

                while b'\n' in buffer:
                    # Find the firt occurence of the delimiter '\n'
                    delim_pos = buffer.find(b'\n')

                    # Extract the complete frame until the delimiter
                    frame = buffer[:delim_pos]

                    # Remove the frame from the buffer
                    buffer = buffer[delim_pos + 1:]

                    try:
                        # Deserialize the frame
                        data = msgpack.unpackb(frame)

                        # We suppose that the frame data is a 4 bytes tuple
                        device_type, event_type, event_code, event_value = data

                        # Map the virtual input
                        if device_type == InputType.MOUSE:
                            device = self.__virtual_mouse
                        elif device_type == InputType.KEYBOARD:
                            device = self.__virtual_keyboard
                        elif device_type == InputType.TOUCH and self.__virtual_touch is not None:
                            device = self.__virtual_touch
                        else:
                            device = None

                        if device is not None:
                            device.write(event_type, event_code, event_value)

                            if device_type == InputType.KEYBOARD:
                                device.syn()

                    except Exception as e:
                        SysLogger("Input proxy").error(f"Error in the frame: {e}")
                        
            self.__is_running = False

    def set_virtual_devices_for_domain(self, domain_name:str, virtual_mouse:InputDevice, virtual_keyboard:InputDevice, virtual_touch:InputDevice):
        """ Associate a Domain name and its virtual devices """
        
        self.__virtual_mouses[domain_name] = virtual_mouse
        self.__virtual_keyboards[domain_name] = virtual_keyboard
        self.__virtual_touches[domain_name] = virtual_touch

    def __on_focus_changed(self, domain_name:str):
        """ Called by the class XenStore when the focus has changed from one Domain to another
        """

        SysLogger("Input proxy").debug(f"The focus has changed to the domain {domain_name}")

        # We get the virtual devices for this domain and update the virtual devices
        vm, vk, vt = self.__get_inputs_for_domain(domain_name)
        self.__virtual_mouse = vm
        self.__virtual_keyboard = vk
        self.__virtual_touch = vt

    def __get_inputs_for_domain(self, domain_name:str) -> tuple[InputDevice, InputDevice, InputDevice]:
        """ Returns the virtual inputs associated to a Domain (mouse, keyboard, touch) """

        virtual_mouse = self.__virtual_mouses.get(domain_name, None)
        virtual_keyboard= self.__virtual_keyboards.get(domain_name, None)
        virtual_touch = self.__virtual_touches.get(domain_name, None)

        return virtual_mouse, virtual_keyboard, virtual_touch
    