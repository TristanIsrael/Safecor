"""Phase 0 tests: topology-driven environment + configuration selector.

These cover:
- :func:`build_environment` / :func:`configuration_dmi` (pure, no fakes).
- The product-side pipeline: with the fakes installed, ``System.get_topology()``
  reads the served ``topology.json`` and applies the selected configuration.

The product-side check runs in a **subprocess** because ``install_fakes`` patches
process-global attributes (the ``safecor`` modules and ``os.path``) and must not
disrupt the session-scoped ``emulator`` fixture.
"""

import json
import subprocess
import sys

from safecor_emulator import (
    NO_CONFIGURATION,
    build_environment,
    build_environment_from_data,
    configuration_dmi,
    default_profile,
    install_fakes,
    uninstall_fakes,
)

# A Saphir-like product topology, with one hardware configuration.
SAPHIR_TOPOLOGY = """
{
    "product": {
        "name": "Saphir",
        "splash_bgcolor": "#3a414d",
        "languages": ["en", "fr"],
        "default_language": "fr"
    },
    "usb": { "use": 1 },
    "screen": { "enabled": 1, "default_focus": "saphir-gui" },
    "vcpu": { "groups": { "gui": 0.2, "antivirus": 0.8 } },
    "business": {
        "domains": [
            { "name": "saphir-gui", "app-package": "saphir-gui",
              "memory": 1200, "has_gui": 1, "vcpu_group": "gui",
              "temp_disk_size": 1024 },
            { "name": "saphir-av-clamav", "app-package": "saphir-av-clamav",
              "memory": 3000, "vcpu_group": "antivirus",
              "temp_disk_size": 4096, "swap_size": 1024 }
        ]
    },
    "configurations": [
        {
            "name": "Durabook R8",
            "identifier": { "sys_vendor": "Durabook", "product_name": "R8AA" },
            "settings": { "screen": { "rotation": 90 },
                          "pci": { "blacklist": [] } }
        }
    ]
}
"""

# Subprocess script: install the fakes, read the topology as the product would,
# and print a JSON summary. Keeps the fakes fully isolated from the test process.
_SUBPROCESS_SCRIPT = r"""
import json, sys
from safecor import System
import safecor._system as S
from safecor_emulator import (default_profile, install_fakes,
                              build_environment_from_data, configuration_dmi)

topo_path, configuration = sys.argv[1], sys.argv[2]
content = open(topo_path, "r", encoding="utf-8").read()
env = build_environment_from_data(json.loads(content))
install_fakes(default_profile().as_dict(),
              topology_content=content,
              domains=env.business_domain_names(),
              dmi=configuration_dmi(env, configuration or None))
try:
    System.reset_topology()
    topo = System.get_topology()
    print(json.dumps({
        "product_name": topo.product_name,
        "rotation": topo.screen.rotation,
        "use_usb": bool(topo.use_usb),
        "default_language": topo.default_language,
        "languages": topo.languages,
        "business": [d.name for d in topo.business_domains()],
        "get_domains": sorted(S.LibvirtHelper.get_domains().keys()),
    }))
finally:
    from safecor_emulator import uninstall_fakes
    uninstall_fakes()
"""


def _topology_file(tmp_path, content=SAPHIR_TOPOLOGY):
    p = tmp_path / "topology.json"
    p.write_text(content, encoding="utf-8")
    return str(p)


def _get_topology_in_subprocess(topology_path, configuration):
    proc = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT, topology_path, configuration or ""],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


# --- pure: Environment ------------------------------------------------------
def test_build_environment_from_data():
    env = build_environment_from_data(json.loads(SAPHIR_TOPOLOGY))
    assert env.product_name == "Saphir"
    assert env.default_language == "fr"
    assert env.languages == ["en", "fr"]
    assert env.use_usb is True
    assert env.screen.enabled is True
    assert env.screen.default_focus == "saphir-gui"
    assert env.screen.rotation == 0  # base topology has no rotation
    assert env.business_domain_names() == ["saphir-gui", "saphir-av-clamav"]
    assert env.configuration_names == ["Durabook R8"]

    gui = env.business_domains[0]
    assert gui.name == "saphir-gui"
    assert gui.has_gui is True
    assert gui.memory == 1200
    assert gui.vcpu_group == "gui"
    assert gui.temp_disk_size == 1024


def test_build_environment_from_file(tmp_path):
    path = _topology_file(tmp_path)
    env = build_environment(path)
    assert env.product_name == "Saphir"
    assert env.configuration_names == ["Durabook R8"]


# --- pure: configuration DMI resolution -------------------------------------
def test_configuration_dmi_selected():
    data = json.loads(SAPHIR_TOPOLOGY)
    assert configuration_dmi(data, "Durabook R8") == {
        "sys_vendor": "Durabook",
        "product_name": "R8AA",
    }


def test_configuration_dmi_none():
    data = json.loads(SAPHIR_TOPOLOGY)
    assert configuration_dmi(data, None) == {
        "sys_vendor": NO_CONFIGURATION,
        "product_name": NO_CONFIGURATION,
    }


def test_configuration_dmi_unknown_name_matches_none():
    data = json.loads(SAPHIR_TOPOLOGY)
    # An unknown name is not applied -> sentinel for every key.
    assert configuration_dmi(data, "DoesNotExist") == {
        "sys_vendor": NO_CONFIGURATION,
        "product_name": NO_CONFIGURATION,
    }


# --- Emulator wiring (construction only, no broker) -------------------------
def test_emulator_environment_and_configuration_names(tmp_path):
    from safecor_emulator import Emulator

    path = _topology_file(tmp_path)
    em = Emulator(topology_path=path)
    assert em.environment is not None
    assert em.environment.product_name == "Saphir"
    assert em.environment.business_domain_names() == ["saphir-gui", "saphir-av-clamav"]
    assert em.configuration_names == ["Durabook R8"]

    # Without a topology, there is no environment and no configurations.
    em2 = Emulator()
    assert em2.environment is None
    assert em2.configuration_names == []


# --- product-side pipeline (subprocess-isolated) ----------------------------
def test_get_topology_applies_selected_configuration(tmp_path):
    path = _topology_file(tmp_path)
    result = _get_topology_in_subprocess(path, "Durabook R8")
    assert result["product_name"] == "Saphir"
    assert result["rotation"] == 90  # from the Durabook R8 configuration
    assert result["use_usb"] is True
    assert result["default_language"] == "fr"
    assert result["business"] == ["saphir-gui", "saphir-av-clamav"]
    # get_domains reflects Dom0 + sys-usb + the business domains
    assert result["get_domains"] == sorted(
        ["Dom0", "sys-usb", "saphir-gui", "saphir-av-clamav"]
    )


def test_get_topology_standard_configuration(tmp_path):
    path = _topology_file(tmp_path)
    result = _get_topology_in_subprocess(path, "")
    assert result["product_name"] == "Saphir"
    assert result["rotation"] == 0  # standard (no configuration matches)
    assert result["use_usb"] is True
    assert result["business"] == ["saphir-gui", "saphir-av-clamav"]


# --- install_fakes / uninstall_fakes sanity (no topology) -------------------
def test_install_uninstall_fakes_reversible(tmp_path):
    import os

    import safecor._system as S

    # The fakes may already be active (the session-scoped ``emulator`` fixture
    # keeps them installed for the whole session). Remember the state so the
    # test leaves the global fakes exactly as it found them.
    had_fakes = getattr(S, "open", None) is not None
    before_exists = os.path.exists

    install_fakes(default_profile().as_dict())
    try:
        # The faked open is a module attribute; os.path.exists is patched.
        assert getattr(S, "open", None) is not None
        assert os.path.exists is not before_exists
    finally:
        uninstall_fakes()
        if had_fakes:
            # Restore the fakes (default profile, like the session fixture) so
            # the global state is left as we found it.
            install_fakes(default_profile().as_dict())

    if had_fakes:
        assert getattr(S, "open", None) is not None
    else:
        assert getattr(S, "open", None) is None
        assert os.path.exists is before_exists
