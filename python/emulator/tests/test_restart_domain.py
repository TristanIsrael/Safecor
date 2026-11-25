"""Emulator round-trip tests for restart_domain (issue #275).

These exercise the full MQTT path: Emulator API → mock Dom0
→ response published back over the broker → Emulator API return value.

They cover all four contract branches:
1. CORE + forced=False → accepted (self-restart), domain recorded
2. CORE + forced=True → accepted (Dom0 reboot), domain recorded
3. BUSINESS + forced=False → refused + reason
4. BUSINESS + forced=True → accepted (Dom0 reboot), domain recorded
"""

import json

import pytest
from safecor import System
from safecor_emulator import Emulator

_MINIMAL_TOPOLOGY = {
    "product": {
        "name": "TestProduct",
        "default_language": "en",
        "languages": ["en", "fr"],
    },
    "screen": {"enabled": 1},
    "usb": {"use": 1},
    "business": {
        "domains": [
            {
                "name": "myapp",
                "memory": 1024,
                "direct_mount": {"mode": "rw"},
            },
        ]
    },
}


@pytest.fixture(scope="module")
def em(tmp_path_factory):
    """Module-scoped emulator with a topology that defines CORE and BUSINESS domains."""
    tmp_path = tmp_path_factory.mktemp("restart_domain")
    topo_path = str(tmp_path / "topology.json")
    with open(topo_path, "w") as f:
        json.dump(_MINIMAL_TOPOLOGY, f)

    disk = tmp_path / "d0"
    disk.mkdir()
    emulator = Emulator(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        topology_path=topo_path,
    )
    emulator.start()
    # Trigger topology loading so mock_dom0 can look up domains.
    # reset_topology + get_topology triggers the module-level topology
    # assignment that mock_dom0's stale import eventually resolves to
    # when re-imported.
    System.reset_topology()
    System().get_topology()
    yield emulator
    emulator.stop()


def test_restart_core_not_forced_accepted(em):
    """CORE + forced=False → accepted, domain in restarted_domains."""
    resp = em.restart_domain("sys-usb", forced=False)
    assert resp is not None
    assert resp.get("state") == "accepted"
    assert resp.get("reason") == ""
    assert "sys-usb" in em.restarted_domains


def test_restart_core_forced_accepted(em):
    """CORE + forced=True → accepted (Dom0 reboot path), domain in restarted_domains."""
    resp = em.restart_domain("sys-usb", forced=True)
    assert resp is not None
    assert resp.get("state") == "accepted"
    assert resp.get("reason") == ""
    assert "sys-usb" in em.restarted_domains


def test_restart_business_not_forced_refused(em):
    """BUSINESS + forced=False → refused with reason."""
    resp = em.restart_domain("myapp", forced=False)
    assert resp is not None
    assert resp.get("state") == "refused"
    assert "not self-restartable" in resp.get("reason", "")
    assert "myapp" not in em.restarted_domains


def test_restart_business_forced_accepted(em):
    """BUSINESS + forced=True → accepted (Dom0 reboot path).

    Domain appears in restarted_domains.
    """
    resp = em.restart_domain("myapp", forced=True)
    assert resp is not None
    assert resp.get("state") == "accepted"
    assert resp.get("reason") == ""
    assert "myapp" in em.restarted_domains
