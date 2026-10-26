"""End-to-end tests for the ``safecor_emulator`` package.

These tests prove that Safecor can run, and that a Safecor-based product can be
driven, on a plain machine without Xen or real hardware.

Note on ordering: ``System`` caches its values on first read, so the
``test_fakes_drive_system`` test is intentionally the first test to touch
``System`` (with the fakes installed). All tests use the default profile values
so that any cached value is consistent across tests.
"""

import time
import threading

from safecor import System, Api, MqttFactory, Topics
from safecor_emulator import (
    Emulator,
    default_profile,
    install_fakes,
    uninstall_fakes,
)


def test_profile_default_shape():
    """The default profile exposes the expected flat dictionary."""
    profile = default_profile()
    data = profile.as_dict()
    assert data["uuid"] == "11111111-2222-3333-4444-555555555555"
    assert data["cpu_count"] == 4
    assert data["screen_width"] == 1280
    assert data["screen_height"] == 720
    assert data["screen_rotation"] == 0

    # The profile round-trips through from_dict.
    rebuilt = type(profile).from_dict(data)
    assert rebuilt.uuid == profile.uuid
    assert rebuilt.cpu_count == profile.cpu_count


def test_fakes_drive_system():
    """Installing the fakes makes System report the profile values."""
    profile = default_profile()
    install_fakes(profile.as_dict())
    try:
        assert System().get_system_uuid() == profile.uuid
        assert System().get_screen_width() == profile.screen_width
        assert System().get_screen_height() == profile.screen_height
        assert System().get_screen_rotation() == profile.screen_rotation

        info = System.get_system_information()
        assert info["system"]["uuid"] == profile.uuid
        assert info["system"]["machine"]["cpu"]["count"] == profile.cpu_count
    finally:
        uninstall_fakes()


def _wait_for(responses, key, timeout=10.0):
    t0 = time.time()
    while key not in responses and time.time() - t0 < timeout:
        time.sleep(0.1)
    return key in responses


def test_emulator_roundtrip(tmp_path):
    """Full core (broker + mock Dom0 + mock sys-usb) answers a DomU client."""
    disk_a = tmp_path / "diskA"
    disk_a.mkdir()
    (disk_a / "hello.txt").write_text("hello safecor\n")
    repository = tmp_path / "repository"
    repository.mkdir()
    target = tmp_path / "target"
    target.mkdir()

    profile = default_profile()
    responses = {}
    ready = threading.Event()

    def on_ready():
        ready.set()
        Api().subscribe(f"{Topics.LIST_DISKS}/response")
        Api().subscribe(f"{Topics.SYSTEM_INFO}/response")

    def on_message(topic, payload):
        if topic == f"{Topics.LIST_DISKS}/response":
            responses["disks"] = payload.get("disks")
        elif topic == f"{Topics.SYSTEM_INFO}/response":
            responses["sysinfo"] = payload

    with Emulator(
        profile=profile,
        source_disks={"diskA": str(disk_a)},
        storage_path=str(repository),
        destination_disk_path=str(target),
    ) as em:
        assert em.is_running

        Api().add_ready_callback(on_ready)
        Api().add_message_callback(on_message)
        client = MqttFactory.create_mqtt_network_dev("Diag")
        Api().start(mqtt_client=client)
        assert ready.wait(15), "DomU Api did not become ready"
        time.sleep(0.5)  # let the subscriptions settle

        # LIST_DISKS: DomU -> MockSysUsb -> DomU
        Api().get_disks_list()
        assert _wait_for(responses, "disks"), "no disks list received"
        assert "diskA" in responses["disks"], responses["disks"]

        # SYSTEM_INFO: DomU -> MockDom0 (uses the fakes) -> DomU
        Api().request_system_info()
        assert _wait_for(responses, "sysinfo"), "no system info received"
        si = responses["sysinfo"]
        assert si["system"]["uuid"] == profile.uuid
        assert si["system"]["machine"]["cpu"]["count"] == profile.cpu_count

        # Stop the DomU client before the core (broker/fakes) is torn down.
        Api().stop()
