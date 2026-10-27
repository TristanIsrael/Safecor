import unittest
import os
import unittest.mock as mock

from safecor import Configuration, ConfigurationHelper, Topology
import safecor._configuration_helper as _configuration_helper


class TestConfiguration(unittest.TestCase):

    def test_configuration_fields(self):
        conf = Configuration("myconf", {"sys_vendor": "ALEFBET"}, {"usb": {"use": True}})
        self.assertEqual(conf.name, "myconf")
        self.assertEqual(conf.identifier, {"sys_vendor": "ALEFBET"})
        self.assertEqual(conf.settings, {"usb": {"use": True}})

    def test_configuration_class_defaults(self):
        self.assertEqual(Configuration.name, "")
        self.assertEqual(Configuration.identifier, {})
        self.assertEqual(Configuration.settings, {})
        self.assertEqual(Configuration.languages, [])
        self.assertEqual(Configuration.default_language, "en")


class TestConfigurationHelper(unittest.TestCase):

    def _topo(self):
        topo = Topology()
        topo.use_usb = False
        topo.screen.enabled = False
        topo.screen.rotation = 0
        topo.screen.default_focus = ""
        topo.pci.blacklist = []
        return topo

    def test_apply_no_configurations(self):
        topo = self._topo()
        topo.configurations = {}
        result = ConfigurationHelper.apply_configuration(topo)
        self.assertIs(result, topo)
        self.assertFalse(topo.use_usb)

    def test_apply_matching_configuration(self):
        topo = self._topo()
        topo.configurations = {
            "myconf": {
                "identifier": {"sys_vendor": "ALEFBET"},
                "settings": {
                    "usb": {"use": True},
                    "screen": {"rotation": 90, "default_focus": "sys-gui"},
                    "pci": {"blacklist": ["00:19.0"]},
                },
            }
        }

        with mock.patch.object(_configuration_helper.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="ALEFBET\n")):
            result = ConfigurationHelper.apply_configuration(topo)

        self.assertIs(result, topo)
        self.assertTrue(topo.use_usb)
        self.assertEqual(topo.screen.rotation, 90)
        self.assertEqual(topo.screen.default_focus, "sys-gui")
        self.assertIn("00:19.0", topo.pci.blacklist)

    def test_apply_non_matching_configuration(self):
        topo = self._topo()
        topo.configurations = {
            "myconf": {
                "identifier": {"sys_vendor": "OTHERVENDOR"},
                "settings": {"usb": {"use": True}},
            }
        }

        with mock.patch.object(_configuration_helper.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="ALEFBET\n")):
            ConfigurationHelper.apply_configuration(topo)

        self.assertFalse(topo.use_usb)

    def test_apply_missing_dmi_file(self):
        topo = self._topo()
        topo.configurations = {
            "myconf": {
                "identifier": {"sys_vendor": "ALEFBET"},
                "settings": {"usb": {"use": True}},
            }
        }

        with mock.patch.object(_configuration_helper.os.path, "exists", return_value=False), \
             mock.patch.object(_configuration_helper, "SysLogger", mock.MagicMock()):
            ConfigurationHelper.apply_configuration(topo)

        # The missing key prevents a match, so nothing is merged
        self.assertFalse(topo.use_usb)

    def test_apply_multiple_keys_partial_match(self):
        topo = self._topo()
        topo.configurations = {
            "myconf": {
                # Two keys: the first matches, the second does not -> no merge
                "identifier": {"sys_vendor": "ALEFBET", "product_name": "SAFE"},
                "settings": {"usb": {"use": True}},
            }
        }

        def fake_open(file=None, *args, **kwargs):
            if file and "sys_vendor" in file:
                return mock.mock_open(read_data="ALEFBET\n")()
            return mock.mock_open(read_data="WRONG\n")()

        with mock.patch.object(_configuration_helper.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", side_effect=fake_open):
            ConfigurationHelper.apply_configuration(topo)

        self.assertFalse(topo.use_usb)

    def test_apply_first_match_wins(self):
        topo = self._topo()
        topo.configurations = {
            "confA": {
                "identifier": {"sys_vendor": "ALEFBET"},
                "settings": {"usb": {"use": True}},
            },
            "confB": {
                "identifier": {"sys_vendor": "ALEFBET"},
                "settings": {"usb": {"use": False}, "screen": {"rotation": 270}},
            },
        }

        with mock.patch.object(_configuration_helper.os.path, "exists", return_value=True), \
             mock.patch("builtins.open", mock.mock_open(read_data="ALEFBET\n")):
            ConfigurationHelper.apply_configuration(topo)

        # confA matches first and the loop breaks, so confB is not applied
        self.assertTrue(topo.use_usb)
        self.assertEqual(topo.screen.rotation, 0)


if __name__ == "__main__":
    unittest.main()
