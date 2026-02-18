from safecor import LibvirtHelper, Domain, DomainType
import os
import unittest

class TestLibvirtHelper(unittest.TestCase):

    def setUp(self):
        os.environ["MOCK_LIBVIRT"] = "1"

    def test_get_domains_count(self):
        self.assertEqual(LibvirtHelper.get_domains_count(), 1)

    def test_get_domains(self):
        domains = LibvirtHelper.get_domains()

        self.assertEqual(len(domains), 1)
        self.assertIsNotNone(domains["test"])

        dom = domains["test"]
        self.assertEqual(dom.id, 1)
        self.assertEqual(dom.name, "test")
        self.assertEqual(dom.domain_type, DomainType.BUSINESS)
        self.assertEqual(dom.memory, 2048)
        self.assertEqual(dom.vcpus, 2)
        self.assertEqual(dom.cpu_affinity, [0,1,2,3,4,5,6,7])

    def test_get_cpu_count(self):
        self.assertEqual(LibvirtHelper.get_cpu_count(), 16)

    def test_reboot_domain(self):
        self.skipTest("Not implemented")

if __name__ == "__main__":
    unittest.main()