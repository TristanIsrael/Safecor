import unittest
import os
import string
import tempfile
import random
import shutil
import builtins
from pathlib import Path
from unittest.mock import patch, mock_open
from safecor import Topology, Domain, DomainType, System, Constants


# Saved because we will mock it later
real_open = builtins.open
real_exists = os.path.exists

# Mocks functions
def open_side_effect(*args, **kwargs):
    path = args[0] if args else kwargs.get("file")

    contents = {
        "/sys/class/dmi/id/sys_vendor": "Durabook",
        "/sys/class/dmi/id/product_name": "R8AA"
    }

    if path in contents:
        return mock_open(read_data=contents[path])()
    return real_open(*args, **kwargs)

def path_exists_side_effect(path):
    if path.startswith("/sys/class/dmi/id/"):
        return True
    return real_exists(path)

class TestSystem(unittest.TestCase):
    files_path = Path(__file__).resolve().parent / "files"

    def setUp(self):
        os.environ["MOCK_LIBVIRT"] = "1"

    def test_get_platform_cpu_count(self):
        self.assertEqual(System().get_platform_cpu_count(), 16)

    def test_domain_name(self):
        self.assertIsNotNone(System.domain_name())

    def test_read_topology_file(self):
        topo_filepath = self.files_path / "topology_1.json"
        
        topo = System.read_topology_file(topo_filepath.as_posix())
        self.assertNotEqual(topo, "")

    def test_get_topology_data(self):
        topo_filepath = self.files_path / "topology_1.json"
        
        topo = System.get_topology_data(topo_filepath.as_posix())
        self.assertNotEqual(topo, {})
 
        self.assertEqual(topo.get("product", {}).get("name", ""), "Safecor Tests")
        self.assertEqual(topo.get("product", {}).get("languages", []), [])
        self.assertEqual(topo.get("product", {}).get("default_language", ""), "")
        self.assertEqual(topo.get("pci", {}).get("blacklist", ""), ["00:0d.0"])
        self.assertEqual(topo.get("usb", {}).get("use", 0), 1)
        self.assertEqual(topo.get("screen", {}).get("enabled", 0), 1)
        self.assertEqual(topo.get("screen", {}).get("rotation", 0), 90)
        self.assertEqual(topo.get("business", {}).get("repository", ""), "https://www.alefbet.net/wp-content/uploads/repositories/Safecor")
        self.assertEqual(len(topo.get("business", {}).get("domains", "")), 2)
        
        domain = topo.get("business", {}).get("domains", "")[0]
        self.assertEqual(domain.get("name", ""), "test-domain")
        self.assertEqual(domain.get("app-package", ""), "bash")
        self.assertEqual(domain.get("memory", 0), 100)
        self.assertEqual(domain.get("cpu", 0), 0)
        self.assertEqual(domain.get("temp_disk_size", 0), 4096)

        domain = topo.get("business", {}).get("domains", "")[1]
        self.assertEqual(domain.get("name", ""), "another-domain")
        self.assertEqual(domain.get("app-package", ""), "my-domain")
        self.assertEqual(domain.get("memory", 0), 1024)
        self.assertEqual(domain.get("cpu", 0), 0)
        self.assertEqual(domain.get("temp_disk_size", 0), 0)

    def test_get_topology_struct_no_vcpus_groups(self):
        topo_filepath = self.files_path / "topology_1.json"
        
        topo = System.get_topology_struct(topo_filepath.as_posix())
        self.assertNotEqual(topo, {})

        self.assertEqual(topo.get("product", {}).get("name", ""), "Safecor Tests")

        system = topo.get("system", {})
        self.assertEqual(system.get("use_usb", False), True)
        self.assertEqual(system.get("screen_rotation", 0), 90)
        self.assertEqual(system.get("screen_enabled", -1), 1)
        
        domains = topo.get("domains", [])
        self.assertEqual(len(domains), 3)

        dom = domains["sys-usb"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "sys-usb")
        self.assertEqual(dom["type"], DomainType.CORE)
        self.assertEqual(dom["memory"], 350)
        self.assertEqual(dom["vcpus"], 2)
        self.assertEqual(dom["cpus"], [0, 1])

        dom = domains["test-domain"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "test-domain")
        self.assertEqual(dom["type"], DomainType.BUSINESS)
        self.assertEqual(dom["memory"], 100)
        self.assertEqual(dom["vcpus"], 14)
        self.assertEqual(dom["cpus"], [2,3,4,5,6,7,8,9,10,11,12,13,14,15])
        self.assertEqual(dom["has_gui"], 1)

        dom = domains["another-domain"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "another-domain")
        self.assertEqual(dom["type"], DomainType.BUSINESS)
        self.assertEqual(dom["memory"], 1024)
        self.assertEqual(dom["vcpus"], 14)
        self.assertEqual(dom["cpus"], [2,3,4,5,6,7,8,9,10,11,12,13,14,15])

    def test_get_topology_struct_vcpus_groups(self):
        topo_filepath = self.files_path / "topology_2.json"
        
        System().reset_topology()
        topo = System.get_topology_struct(topo_filepath.as_posix())
        self.assertNotEqual(topo, {})

        self.assertEqual(topo.get("product", {}).get("name", ""), "Safecor Tests")
        self.assertEqual(topo.get("product", {}).get("languages"), [ "fr", "en", "de"])
        self.assertEqual(topo.get("product", {}).get("default_language"), "fr")

        system = topo.get("system", {})
        self.assertEqual(system.get("use_usb", False), True)
        self.assertEqual(system.get("screen_rotation", 0), 90)
        self.assertEqual(system.get("screen_enabled", 0), 1)
        
        domains = topo.get("domains", [])
        self.assertEqual(len(domains), 3)

        dom = domains["sys-usb"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "sys-usb")
        self.assertEqual(dom["type"], DomainType.CORE)
        self.assertEqual(dom["memory"], 350)
        self.assertEqual(dom["vcpus"], 2)
        self.assertEqual(dom["cpus"], [0, 1])

        dom = domains["test-domain"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "test-domain")
        self.assertEqual(dom["type"], DomainType.BUSINESS)
        self.assertEqual(dom["memory"], 100)
        self.assertEqual(dom["vcpus"], 8)
        self.assertEqual(dom["package"], "bash")
        self.assertEqual(dom["has_gui"], 1)
        self.assertEqual(dom["cpus"], [4,5,6,7,8,9,10,11])

        dom = domains["another-domain"]
        self.assertIsNotNone(dom)
        self.assertEqual(dom["name"], "another-domain")
        self.assertEqual(dom["type"], DomainType.BUSINESS)
        self.assertEqual(dom["memory"], 1024)
        self.assertEqual(dom["vcpus"], 8)
        self.assertEqual(dom["package"], "my-domain")
        self.assertEqual(dom["has_gui"], 0)
        self.assertEqual(dom["cpus"], [4,5,6,7,8,9,10,11])

    def test_languages(self):
        topo_filepath = self.files_path / "topology_1.json"
        
        System().reset_topology()
        topo = System.get_topology(topo_filepath.as_posix())
        self.assertIsNotNone(topo)

        self.assertEqual(len(topo.languages), 0)
        self.assertEqual(topo.default_language, "en")

        topo_filepath = self.files_path / "topology_2.json"
        
        System().reset_topology()
        topo = System.get_topology(topo_filepath.as_posix())
        self.assertIsNotNone(topo)

        self.assertEqual(topo.languages, ["fr", "en", "de"])
        self.assertEqual(topo.default_language, "fr")

    def test_get_topology(self):
        topo_filepath = self.files_path / "topology_1.json"
        
        System().reset_topology()
        topo = System.get_topology(topo_filepath.as_posix())
        self.assertIsNotNone(topo)

        self.assertEqual(topo.product_name, "Safecor Tests")
        self.assertEqual(len(topo.colors()), 1)
        self.assertEqual(topo.colors().get("splash_bgcolor", ""), (0,0,0,0))
        self.assertEqual(topo.use_usb, True)
        self.assertEqual(topo.screen.width, 1100)
        self.assertEqual(topo.screen.height, 750)
        self.assertEqual(topo.screen.rotation, 90)
        self.assertEqual(topo.screen.default_focus, "test-domain")
        self.assertTrue(topo.screen.enabled)
        self.assertEqual(topo.pci.blacklist, [ "00:0d.0" ])

        self.assertEqual(len(topo.domain_names()), 3)

        dom = topo.domain("sys-usb")
        self.assertIsNotNone(dom)
        self.assertEqual(dom.name, "sys-usb")
        self.assertEqual(dom.domain_type, DomainType.CORE)
        self.assertEqual(dom.memory, 350)
        self.assertEqual(dom.vcpus, 2)
        self.assertEqual(dom.cpu_affinity, [0, 1])

        dom = topo.domain("test-domain")
        self.assertIsNotNone(dom)
        self.assertEqual(dom.name, "test-domain")
        self.assertEqual(dom.domain_type, DomainType.BUSINESS)
        self.assertEqual(dom.memory, 100)
        self.assertEqual(dom.vcpus, 14)
        self.assertEqual(dom.temp_disk_size, 4096)
        self.assertTrue(dom.has_gui)
        self.assertEqual(dom.cpu_affinity, [2,3,4,5,6,7,8,9,10,11,12,13,14,15])

        dom = topo.domain("another-domain")
        self.assertIsNotNone(dom)
        self.assertEqual(dom.name, "another-domain")
        self.assertEqual(dom.domain_type, DomainType.BUSINESS)
        self.assertEqual(dom.memory, 1024)
        self.assertEqual(dom.vcpus, 14)
        self.assertFalse(dom.has_gui)
        self.assertEqual(dom.temp_disk_size, 0)
        self.assertEqual(dom.cpu_affinity, [2,3,4,5,6,7,8,9,10,11,12,13,14,15])
        

    def test_parse_range(self):
        self.assertEqual(System.parse_range("1-2"), (1,2))
        self.assertEqual(System.parse_range(""), ())
        self.assertEqual(System.parse_range("3-20"), (3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20))
        self.assertEqual(System.parse_range("3"), (3,))
        self.assertRaises(ValueError, System.parse_range, "20-2")

    def test_compute_vcpus_for_group(self):
        groups = {
            "sys-gui": 0.4,
            "group-1": 0.6
        }

        self.assertEqual(System.compute_vcpus_for_group("sys-gui", groups), 6)
        self.assertEqual(System.compute_vcpus_for_group("group-1", groups), 8)
        self.assertEqual(System.compute_vcpus_for_group("none", groups), 14)

    def test_compute_cpus_for_group(self):
        groups = {
            "sys-gui": 0.4,
            "group-1": 0.6
        }

        System().reset_topology()
        self.assertEqual(System().compute_cpus_for_group("sys-gui", groups), [2,3,4,5,6,7])
        self.assertEqual(System().compute_cpus_for_group("group-1", groups), [4,5,6,7,8,9,10,11])
        self.assertEqual(System().compute_cpus_for_group("none", groups), [2,3,4,5,6,7,8,9,10,11,12,13,14,15]) 

    def test_get_system_information(self):
        Constants.DOM0_REPOSITORY_PATH = "/tmp"
        sysinfo = System.get_system_information()

        core = sysinfo.get("core", {})
        self.assertEqual(core.get("version", ""), "1.2.1")
        self.assertEqual(core.get("debug_on", None), False)

        system = sysinfo.get("system", {})
        sysos = system.get("os", {})
        self.assertNotEqual(sysos.get("name", ""), "")
        self.assertNotEqual(sysos.get("release", ""), "")
        self.assertNotEqual(sysos.get("version", ""), "")

        machine = system.get("machine", {})
        self.assertNotEqual(machine.get("arch", ""), "")
        self.assertNotEqual(machine.get("platform", ""), "")

        cpu = machine.get("cpu", {})
        self.assertGreater(cpu.get("count", 0), 0)
        self.assertGreater(cpu.get("freq_current", 0), 0)
        self.assertGreater(cpu.get("freq_min", 0), 0)
        self.assertGreater(cpu.get("freq_max", 0), 0)
        self.assertGreater(cpu.get("percent", 0), 0)

        memory = machine.get("memory", {})
        self.assertGreater(memory.get("total", 0), 0)
        self.assertGreater(memory.get("available", 0), 0)
        self.assertGreater(memory.get("percent", 0), 0)
        self.assertGreater(memory.get("free", 0), 0)
        self.assertGreater(memory.get("used", 0), 0)

        load = machine.get("load", {})
        self.assertGreater(load.get("1", 0), 0)
        self.assertGreater(load.get("5", 0), 0)
        self.assertGreater(load.get("15", 0), 0)

        # Create random files in /tmp
        self.__create_random_files("/tmp/test_system.tmp")

        storage = system.get("storage", {})
        self.assertGreater(storage.get("total", 0), 0)
        self.assertGreater(storage.get("used", 0), 0)
        self.assertGreater(storage.get("free", 0), 0)
        self.assertGreater(storage.get("files", 0), 0)

        shutil.rmtree("/tmp/test_system.tmp")

        self.assertGreater(system.get("boot_time", 0), 0)
        #self.assertNotEqual(sysinfo.get("uuid", ""), "")

        cpu_alloc = system.get("cpu_allocation", {})
        self.assertEqual(len(cpu_alloc), 1)
        self.assertEqual(cpu_alloc.get("test", []), [0, 1, 2, 3, 4, 5, 6, 7])
        
    def __create_random_files(self, tmp_dir:str):
        file_paths = []

        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)

        for i in range(10):
            with tempfile.NamedTemporaryFile(dir=tmp_dir, prefix="tmp_", suffix=".txt", delete=False) as f:
                # Générer du contenu aléatoire
                content = ''.join(random.choices(string.ascii_letters + string.digits, k=100))
                f.write(content.encode("utf-8"))
                file_paths.append(f.name)
        
        return file_paths
    
    def test_get_screen_width(self):
        system = System()

        # First call
        self.assertEqual(system.get_screen_width(), 1100)

        # Second call
        self.assertEqual(system.get_screen_width(), 1100)
        
    def test_cpu_affinity_to_string(self):
        self.assertEqual(System.cpu_affinity_to_string([1,2,3,4,5]), "1-5")

    def test_topology_with_configuration(self):
        topo_filepath = self.files_path / "topology_conf.json"
        System.reset_topology()
        
        # Test the default configuration
        topo = System.get_topology(topo_filepath.as_posix())
        self.assertNotEqual(topo, {})

        self.assertEqual(topo.use_usb, True)
        self.assertEqual(topo.screen.enabled, True)
        self.assertEqual(topo.screen.rotation, 0)
        self.assertEqual(topo.screen.default_focus, "controller")
        self.assertEqual(topo.pci.blacklist, [])
        self.assertEqual(topo.product_name, "Saphir")
        self.assertEqual(topo.color_as_hex("splash_bgcolor"), "#3a414dff")
        self.assertEqual(len(topo.domains), 4)

        dom = topo.domain("saphir-av-clamav")
        self.assertEqual(dom.name, "saphir-av-clamav")
        self.assertEqual(dom.package, "saphir-av-clamav")
        self.assertEqual(dom.memory, 3000)
        self.assertEqual(dom.vcpus, 11)

        dom = topo.domain("saphir-av-eset")
        self.assertEqual(dom.name, "saphir-av-eset")
        self.assertEqual(dom.package, "saphir-av-eset")
        self.assertEqual(dom.memory, 1500)
        self.assertEqual(dom.vcpus, 11)

        # Test the configuration with the mocked system
        # This results in activating the configuration Durabook R8
        System.reset_topology()
        with patch("builtins.open", side_effect=open_side_effect), \
             patch("os.path.exists", side_effect=path_exists_side_effect):
                topo = System.get_topology(topo_filepath.as_posix())
                self.assertNotEqual(topo, {})

                self.assertEqual(topo.use_usb, True)
                self.assertEqual(topo.screen.enabled, True)
                self.assertEqual(topo.screen.rotation, 90)
                self.assertEqual(topo.pci.blacklist, [ "00:0d.0" ])
                self.assertEqual(topo.product_name, "Saphir")
                self.assertEqual(topo.color_as_hex("splash_bgcolor"), "#3a414dff")
                self.assertEqual(len(topo.domains), 4)

                dom = topo.domain("saphir-av-clamav")
                self.assertEqual(dom.name, "saphir-av-clamav")
                self.assertEqual(dom.package, "saphir-av-clamav")
                self.assertEqual(dom.memory, 3000)
                self.assertEqual(dom.vcpus, 11)

                dom = topo.domain("saphir-av-eset")
                self.assertEqual(dom.name, "saphir-av-eset")
                self.assertEqual(dom.package, "saphir-av-eset")
                self.assertEqual(dom.memory, 1500)
                self.assertEqual(dom.vcpus, 11)


    def test_blacklist_pci(self):
        topo_filepath = self.files_path / "topology_conf.json"
        System.reset_topology()
        
        with patch("builtins.open", side_effect=open_side_effect), \
             patch("os.path.exists", side_effect=path_exists_side_effect):
                topo = System.get_topology(topo_filepath.as_posix())
                self.assertNotEqual(topo, {})
                
                self.assertEqual(len(topo.pci.blacklist), 1)


    def test_topology_no_libvirt(self):
        # We override the default env
        os.environ["MOCK_LIBVIRT"] = "0"

        topo_filepath = self.files_path / "topology_conf.json"
        System.reset_topology()

        with patch("builtins.open", side_effect=open_side_effect), \
             patch("os.path.exists", side_effect=path_exists_side_effect):
                topo = System.get_topology(topo_filepath.as_posix())
                self.assertEqual(topo.screen.rotation, 90)                

    def test_settings(self):
        self.assertEqual(System().get_setting("none"), "")
        System().set_setting("a_setting", "a value")
        self.assertEqual(System().get_setting("a_setting"), "a value")
        self.assertEqual(System().get_settings(), { "a_setting": "a value"})
