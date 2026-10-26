"""Pytest plugin that exposes the emulator as a fixture.

A product can use the emulated Safecor core directly from its own test suite.
In the product's ``conftest.py`` add::

    pytest_plugins = ["safecor_emulator.pytest_plugin"]

or enable it via ``addopts = "-p safecor_emulator.pytest_plugin"`` in
``pyproject.toml`` / ``pytest.ini``.

Fixtures provided:

- ``emulator`` (session-scoped): a fully started :class:`Emulator` (broker +
  mock Dom0 + mock sys-usb + fakes). A source disk named ``disk0`` is pre-created
  with a sample ``hello.txt``.
- ``emulator_source_disk`` (session-scoped): the path of that ``disk0``.

Example::

    def test_my_product_lists_disks(emulator):
        client = MqttFactory.create_mqtt_network_dev("myapp")
        ...  # run your product's MQTT logic against the emulated core
"""

import pytest

from safecor_emulator import Emulator, default_profile


@pytest.fixture(scope="session")
def emulator(tmp_path_factory):
    """Yield a started Emulator for the whole test session."""
    base = tmp_path_factory.mktemp("safecor_emulator")
    disk0 = base / "disk0"
    disk0.mkdir()
    (disk0 / "hello.txt").write_text("hello safecor\n")

    em = Emulator(
        profile=default_profile(),
        source_disks={"disk0": str(disk0)},
        storage_path=str(base / "repository"),
        destination_disk_path=str(base / "target"),
    )
    em.start()
    yield em
    em.stop()


@pytest.fixture(scope="session")
def emulator_source_disk(emulator):
    """Path of the pre-created source disk ``disk0``."""
    return emulator.source_disks["disk0"]
