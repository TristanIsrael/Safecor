"""Mouse input handling

Copyright (c) 2024-2026, Tristan Israël
Safecor Licence — see python/lib/LICENCE.md

.. author:: Tristan Israël
"""


class MouseButton:
    """This class codes the buttons of a mouse"""

    UNKNOWN = 0  # b0000
    LEFT = 1  # b0001
    MIDDLE = 2  # b0010
    RIGHT = 4  # b0100


class MouseWheel:
    """This class codes the mouse wheel movement"""

    NO_MOVE = 0
    UP = 1
    DOWN = -1


class MouseMove:
    """
    This class codes the mouse positing strategy used by the system

    In relative positioning, an negative ``x`` value means that the mouse is moving left. A negative ``y`` value
    means that the mouse is moving up.
    """

    RELATIVE = 0
    """ Used in systems with regular mouse. The coordinates are relative from the previous value. """

    ABSOLUTE = 1
    """ Used in systems with touch screens or touch pads. The coordinates are absolute to the screen and depends from the resolution. """


class Mouse:
    """
    This class encapsulates information about a mouse or a touch event.

    The properties are public in order to make the changes quicker because the events are very numerous and
    need to be sent very quickly.
    """

    buttons = MouseButton.UNKNOWN
    x: int = 0
    y: int = 0
    move = MouseMove.RELATIVE
    wheel = MouseWheel.NO_MOVE

    def __init__(
        self,
        move: MouseMove = MouseMove.RELATIVE,
        x: int = 0,
        y: int = 0,
        buttons: int = 0,
        wheel: int = 0,
    ):
        self.x = x
        self.y = y
        self.move = move
        self.buttons = buttons
        self.wheel = wheel

    def equals(self, other) -> bool:
        """
        Returns True if the position and the buttons are the same between this instance and another instance.

        :param other: Another instance of Mouse
        :type other: Mouse
        """

        return (
            other.x == self.x
            and other.y == self.y
            and other.buttons == self.buttons
            and other.wheel == self.wheel
        )

    def buttons_equal(self, other) -> bool:
        """
        Returns True if the buttons are the same between this instance and another instance.

        :param other: Another instance of Mouse
        :type other: Mouse
        """

        return other.buttons == self.buttons

    def button_equals(self, other, button) -> bool:
        """
        Return True if a button is pressed in this instance and another one.

        :param other: Another instance of Mouse
        :type other: Mouse
        :param button: The button to compare
        :type button: MouseButton
        """

        if self.buttons == MouseButton.UNKNOWN and other.buttons == MouseButton.UNKNOWN:
            return True

        return (self.buttons & button) == (
            other.buttons & button
        ) and self.buttons & button != MouseButton.UNKNOWN

    def button_pressed(self, button) -> bool:
        """
        Returns True if the button is pressed.

        :param button: The button to verify
        :type button: MouseButton
        """

        return (self.buttons & button) > 0

    def wheel_equals(self, other) -> bool:
        """
        Returns True if the wheel state is the same between this instance and another one.

        :param other: Another instance of Mouse
        :type other: Mouse
        """

        return self.wheel == other.wheel

    def wheel_moved(self) -> bool:
        """
        Returns True if the wheel is moved
        """

        return self.wheel != MouseWheel.NO_MOVE

    def serialize(self) -> bytes:
        """
        Serializes this instance's data in order to send it on a serial bus.
        """

        return f"{self.move},{self.x},{self.y},{self.buttons},{self.wheel}".encode()

    @staticmethod
    def from_data(data: bytes):
        """
        Deserializes the data received from a serial bus in this instance.
        """

        if data is None:
            return None

        if data.count(b",") < 4:
            return None

        s = data.split(b",")
        return Mouse(int(s[0]), int(s[1]), int(s[2]), int(s[3]), int(s[4]))
