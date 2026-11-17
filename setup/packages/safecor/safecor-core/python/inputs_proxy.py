"""Proxies input events (keyboard, mouse, touch) from sys-usb to virtual input devices in Dom0.

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""

import os
import socket
import threading

import msgpack
from evdev import InputDevice
from safecor import InputType, SysLogger, System, XenStore, XsDomain, XsKey


class InputsProxy:
    """The Inputs-proxy monitors the inputs socket of sys-usb and serializes the events on the
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
    __virtual_mouse = None  # The current virtual mouse
    __virtual_keyboard = None  # The current virtual keyboard
    __virtual_touch = None  # The current virtual touch
    __xenstore = XenStore()
    __can_run = False
    __is_running = False
    __thread = None
    __listener = None
    INPUTS_SOCKET = "/var/run/safecor/sys-usb-input.sock"

    def start(self):
        """Starts the Inputs-proxy"""

        if self.__is_running:
            return

        self.__can_run = True

        SysLogger("Inputs-proxy").info("The Inputs-proxy is going to start")
        self.__thread = threading.Thread(target=self.events_proxy_worker, daemon=True)
        self.__thread.start()

        # Find the default GUI
        default_focus = System().get_topology().default_focus()
        if default_focus != "":
            self.__on_focus_changed(default_focus)
        else:
            SysLogger("Inputs-proxy").warn(
                "No Domain has the default focus. There is a risk that no inputs are used"
            )

        # Monitor the focused domain from the XenStore
        self.__xenstore.monitor(
            XsDomain.System.value,
            XsKey.InputFocus.value,
            "inputs-focus",
            self.__on_focus_changed,
        )

    def __del__(self):
        "Destructor: stops the input proxy when the object is garbage collected."
        self.stop()

    def stop(self):
        """Stops the Inputs-proxy"""

        self.__can_run = False
        self.__xenstore.stop()

        if self.__listener is not None:
            try:
                self.__listener.close()
            except OSError:
                pass
            self.__listener = None

        try:
            os.unlink(self.INPUTS_SOCKET)
        except OSError:
            pass

    def events_proxy_worker(self):
        """Starts the Inputs-proxy"""

        SysLogger("Input proxy").info("Start input proxy")
        buffer = bytearray()

        self.__is_running = True

        # Remove stale socket file
        try:
            os.unlink(self.INPUTS_SOCKET)
        except OSError:
            pass

        # Create listening socket
        self.__listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.__listener.bind(self.INPUTS_SOCKET)
        # The vchan servers (group safecor) must be able to connect to this
        # socket. /var/run/safecor is a setgid safecor directory on Dom0, so
        # the socket already belongs to the safecor group: only the mode
        # needs the group write bit.
        os.chmod(self.INPUTS_SOCKET, 0o660)
        self.__listener.listen(1)
        self.__listener.settimeout(1.0)

        while self.__can_run:
            try:
                conn, _ = self.__listener.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            self.__is_running = True
            buffer.clear()

            while self.__can_run:
                try:
                    raw_data = conn.recv(128)
                except OSError:
                    break

                if not raw_data:
                    SysLogger("Input proxy").error("Connection with inputs socket lost")
                    break

                buffer.extend(raw_data)

                while b"\n" in buffer:
                    # Find the first occurrence of the delimiter '\n'
                    delim_pos = buffer.find(b"\n")

                    # Extract the complete frame until the delimiter
                    frame = buffer[:delim_pos]

                    # Remove the frame from the buffer
                    buffer = buffer[delim_pos + 1 :]

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
                        elif (
                            device_type == InputType.TOUCH
                            and self.__virtual_touch is not None
                        ):
                            device = self.__virtual_touch
                        else:
                            device = None

                        if device is not None:
                            device.write(event_type, event_code, event_value)

                            if device_type == InputType.KEYBOARD:
                                device.syn()

                    except Exception as e:
                        SysLogger("Input proxy").error(f"Error in the frame: {e}")

            conn.close()
            self.__is_running = False

        # Cleanup
        try:
            self.__listener.close()
        except OSError:
            pass
        self.__listener = None

        try:
            os.unlink(self.INPUTS_SOCKET)
        except OSError:
            pass

    def set_virtual_devices_for_domain(
        self,
        domain_name: str,
        virtual_mouse: InputDevice,
        virtual_keyboard: InputDevice,
        virtual_touch: InputDevice,
    ):
        """Associate a Domain name and its virtual devices"""

        print(f"Set virtual mouse of {domain_name} to {virtual_mouse}")

        self.__virtual_mouses[domain_name] = virtual_mouse
        self.__virtual_keyboards[domain_name] = virtual_keyboard
        self.__virtual_touches[domain_name] = virtual_touch

    def __on_focus_changed(self, domain_name: str):
        """Called by the class XenStore when the focus has changed from one Domain to another"""

        SysLogger("Input proxy").debug(
            f"The focus has changed to the domain {domain_name}"
        )

        # We get the virtual devices for this domain and update the virtual devices
        vm, vk, vt = self.__get_inputs_for_domain(domain_name)
        self.__virtual_mouse = vm
        self.__virtual_keyboard = vk
        self.__virtual_touch = vt

    def __get_inputs_for_domain(
        self, domain_name: str
    ) -> tuple[InputDevice, InputDevice, InputDevice]:
        """Returns the virtual inputs associated to a Domain (mouse, keyboard, touch)"""

        virtual_mouse = self.__virtual_mouses.get(domain_name, None)
        virtual_keyboard = self.__virtual_keyboards.get(domain_name, None)
        virtual_touch = self.__virtual_touches.get(domain_name, None)

        print(f"virtual mouse of {domain_name} is {virtual_mouse}")

        return virtual_mouse, virtual_keyboard, virtual_touch
