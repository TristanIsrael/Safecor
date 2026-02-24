import threading
import socket
import msgpack
from evdev import InputDevice, ecodes, UInput
from safecor import SysLogger, InputType

class InputsProxy:
    """ The inputs proxy monitors the inputs socket of sys-usb and serializes the events on the 
        virtual devices created before.
    """

    virtual_mouse = None
    virtual_keyboard = None
    virtual_touch = None
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
                            device = self.virtual_mouse
                        elif device_type == InputType.KEYBOARD:
                            device = self.virtual_keyboard
                        elif device_type == InputType.TOUCH and self.virtual_touch is not None:
                            device = self.virtual_touch
                        else:
                            device = None

                        if device is not None:
                            device.write(event_type, event_code, event_value)

                            if device_type == InputType.KEYBOARD:
                                device.syn()

                    except Exception as e:
                        SysLogger("Input proxy").error(f"Erreur in the frame: {e}")
                        
            self.__is_running = False