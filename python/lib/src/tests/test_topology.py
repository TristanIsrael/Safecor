import unittest
from safecor import Topology, Domain, DomainType


class TestTopology(unittest.TestCase):

    def test_init_domain(self):
        domain = Domain("My domain", DomainType.BUSINESS)

        self.assertEqual(domain.name, "My domain")
        self.assertEqual(domain.domain_type, DomainType.BUSINESS)

    def test_init_topology(self):
        topo = Topology()

        self.assertEqual(topo.domains, [])
        self.assertEqual(topo.colors(), {})
        self.assertFalse(topo.initialized())

    def test_set_initialized(self):
        topo = Topology()

        topo.set_initialized(True)
        self.assertTrue(topo.initialized())

    def test_colors(self):
        topo = Topology()

        topo.add_color("color 1", "#fff")
        topo.add_color("color 2", "#000")
        topo.add_color("color 3", "#123456ab")
        topo.add_color("color 4", "#fafafa")
        topo.add_color("color 5", "#fff2")

        self.assertEqual(len(topo.colors()), 5)

        self.assertEqual(topo.color_as_rgba("color 1"), (255, 255, 255, 255))
        self.assertEqual(topo.color_as_rgba("color 2"), (0, 0, 0, 255))
        self.assertEqual(topo.color_as_rgba("color 3"), (0x12, 0x34, 0x56, 0xab))
        self.assertEqual(topo.color_as_rgba("color 4"), (0xfa, 0xfa, 0xfa, 0xff))
        self.assertEqual(topo.color_as_rgba("color 5"), (0xff, 0xff, 0xff, 0x22))

        self.assertEqual(topo.color_as_hex("color 1"), "#ffffffff")
        self.assertEqual(topo.color_as_hex("color 2"), "#000000ff")
        self.assertEqual(topo.color_as_hex("color 3"), "#123456ab")
        self.assertEqual(topo.color_as_hex("color 4"), "#fafafaff")
        self.assertEqual(topo.color_as_hex("color 5"), "#ffffff22")

        self.assertEqual(topo.color_as_rgba("color none"), (0, 0, 0, 0))

        hex_colors = topo.colors_as_hex()
        self.assertEqual(len(hex_colors), 5)
        self.assertEqual(hex_colors[0], "#ffffffff")
        self.assertEqual(hex_colors[1], "#000000ff")
        self.assertEqual(hex_colors[2], "#123456ab")
        self.assertEqual(hex_colors[3], "#fafafaff")
        self.assertEqual(hex_colors[4], "#ffffff22")

    def test_domains(self):
        topo = Topology()
        
        topo.add_domain(Domain("domain 1", DomainType.BUSINESS))
        topo.add_domain(Domain("domain 2", DomainType.CORE))

        self.assertEqual(len(topo.domain_names()), 2)
        self.assertEqual(topo.domain_names()[0], "domain 1")
        self.assertEqual(topo.domain_names()[1], "domain 2")
        self.assertEqual(topo.domain("domain 1").domain_type, DomainType.BUSINESS)
        self.assertEqual(topo.domain("domain 2").domain_type, DomainType.CORE)
        self.assertIsNone(topo.domain("domain 3"))

    def test_blacklist(self):
        topo = Topology()

        topo.pci.blacklist.append("00:0d.0")

        self.assertTrue(topo.is_pci_bus_blacklisted("00:0d.0"))
        self.assertFalse(topo.is_pci_bus_blacklisted("00:0d.2"))
        self.assertFalse(topo.is_pci_bus_blacklisted("00:14.0"))

    def test_deep_copy(self):
        topo = Topology()
        topo.add_domain(Domain("d1", DomainType.BUSINESS))
        topo.screen.enabled = True
        # Assign (not append) so the Pci instance owns its own list
        topo.pci.blacklist = ["00:11.0"]
        topo.use_usb = True
        topo.languages = ["en", "fr"]
        topo.default_language = "fr"

        copy = Topology(topo)

        # Mutating the copy must not affect the original
        copy.add_domain(Domain("d2", DomainType.CORE))
        copy.screen.enabled = False
        copy.pci.blacklist.append("00:12.0")
        copy.use_usb = False
        copy.languages.append("es")

        self.assertEqual(len(topo.domains), 1)
        self.assertTrue(topo.screen.enabled)
        self.assertEqual(topo.pci.blacklist, ["00:11.0"])
        self.assertEqual(copy.pci.blacklist, ["00:11.0", "00:12.0"])
        self.assertTrue(topo.use_usb)
        self.assertFalse(copy.use_usb)
        self.assertEqual(topo.languages, ["en", "fr"])
        self.assertEqual(copy.default_language, "fr")

    def test_business_domains(self):
        topo = Topology()
        topo.add_domain(Domain("biz", DomainType.BUSINESS))
        topo.add_domain(Domain("core", DomainType.CORE))
        self.assertEqual([d.name for d in topo.business_domains()], ["biz"])

    def test_graphical_domains(self):
        topo = Topology()
        d1 = Domain("gui1", DomainType.BUSINESS)
        d1.has_gui = True
        d2 = Domain("nogui", DomainType.BUSINESS)
        d2.has_gui = False
        topo.add_domain(d1)
        topo.add_domain(d2)
        self.assertEqual([d.name for d in topo.graphical_domains()], ["gui1"])

    def test_default_focus(self):
        topo = Topology()
        # No GUI domains and no explicit focus
        self.assertEqual(topo.default_focus(), "")

        d1 = Domain("gui1", DomainType.BUSINESS)
        d1.has_gui = True
        topo.add_domain(d1)
        # No explicit focus -> first graphical domain
        self.assertEqual(topo.default_focus(), "gui1")

        # Explicit focus overrides
        topo.screen.default_focus = "explicit"
        self.assertEqual(topo.default_focus(), "explicit")


if __name__ == "__main__":
    unittest.main()
