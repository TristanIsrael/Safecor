import unittest

from safecor import Mouse, MouseButton, MouseMove, MouseWheel


class TestMouse(unittest.TestCase):
    def test_init(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertEqual(mouse.move, MouseMove.RELATIVE)
        self.assertEqual(mouse.x, 10)
        self.assertEqual(mouse.y, 11)
        self.assertEqual(mouse.buttons, MouseButton.LEFT | MouseButton.MIDDLE)
        self.assertEqual(mouse.wheel, MouseWheel.UP)

    def test_equals(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )
        other = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.equals(other))

        other.x = 90
        self.assertFalse(mouse.equals(other))

        other.x = 10
        other.y = 0
        self.assertFalse(mouse.equals(other))

        other.x = 10
        other.y = 11
        other.buttons = MouseButton.LEFT
        self.assertFalse(mouse.equals(other))

        other.x = 10
        other.y = 11
        other.buttons = MouseButton.LEFT | MouseButton.MIDDLE
        other.wheel = MouseWheel.NO_MOVE
        self.assertFalse(mouse.equals(other))

    def test_buttons_equal(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )
        other = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.buttons_equal(other))

        other.buttons = MouseButton.LEFT
        self.assertFalse(mouse.buttons_equal(other))

    def test_button_equals(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )
        other = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.button_equals(other, MouseButton.LEFT))
        self.assertTrue(mouse.button_equals(other, MouseButton.MIDDLE))
        self.assertFalse(mouse.button_equals(other, MouseButton.RIGHT))

        mouse.buttons = MouseButton.UNKNOWN
        self.assertFalse(mouse.button_equals(other, MouseButton.RIGHT))

        other.buttons = MouseButton.UNKNOWN
        self.assertTrue(mouse.button_equals(other, MouseButton.UNKNOWN))

    def test_button_pressed(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.button_pressed(MouseButton.LEFT))
        self.assertTrue(mouse.button_pressed(MouseButton.MIDDLE))
        self.assertFalse(mouse.button_pressed(MouseButton.RIGHT))

    def test_wheel_equals(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )
        other = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.wheel_equals(other))

        other.wheel = MouseWheel.NO_MOVE
        self.assertFalse(mouse.wheel_equals(other))

    def test_wheel_moved(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        self.assertTrue(mouse.wheel_moved())

        mouse.wheel = MouseWheel.DOWN
        self.assertTrue(mouse.wheel_moved())

        mouse.wheel = MouseWheel.NO_MOVE
        self.assertFalse(mouse.wheel_moved())

    def test_serialize(self):
        mouse = Mouse(
            MouseMove.RELATIVE,
            10,
            11,
            MouseButton.LEFT | MouseButton.MIDDLE,
            MouseWheel.UP,
        )

        data = mouse.serialize()
        self.assertEqual(data, b"0,10,11,3,1")

    def test_deserialize(self):
        mouse = Mouse.from_data(b"0,10,11,3,1")
        self.assertEqual(mouse.move, MouseMove.RELATIVE)
        self.assertEqual(mouse.x, 10)
        self.assertEqual(mouse.y, 11)
        self.assertEqual(mouse.buttons, MouseButton.LEFT | MouseButton.MIDDLE)
        self.assertEqual(mouse.wheel, MouseWheel.UP)

        mouse = Mouse.from_data(b"0,2")
        self.assertIsNone(mouse)

        mouse = Mouse.from_data(None)
        self.assertIsNone(mouse)


if __name__ == "__main__":
    unittest.main()
