"""Tests for the operator console controller (:mod:`safecor_emulator.console`).

These run a real started :class:`Emulator` (injected into the controller) plus
an offscreen ``QGuiApplication``, and verify that each slot mutates the expected
state, emits the expected signal and records an ``actions`` entry.
"""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication

from safecor_emulator import Emulator
from safecor_emulator.console import ConsoleController


@pytest.fixture(scope="module")
def qapp():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    yield app


@pytest.fixture
def em(tmp_path):
    disk = tmp_path / "d0"
    disk.mkdir()
    emulator = Emulator(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    emulator.start()
    yield emulator
    emulator.stop()


@pytest.fixture
def controller(qapp, em):
    return ConsoleController(emulator=em)


def _saphir_topology(tmp_path):
    topo = {
        "product": {
            "name": "Saphir",
            "languages": ["en", "fr"],
            "default_language": "en",
        },
        "business": {
            "domains": [
                {"name": "saphir-gui", "has_gui": True},
                {"name": "saphir-av-clamav"},
            ]
        },
        "configurations": [
            {
                "name": "Durabook R8",
                "identifier": {"sys_vendor": "Durabook", "product_name": "R8AA"},
            },
        ],
    }
    path = tmp_path / "topology.json"
    path.write_text(json.dumps(topo))
    return str(path)


@pytest.fixture
def topo_controller(qapp, tmp_path):
    disk = tmp_path / "d0"
    disk.mkdir()
    emulator = Emulator(
        topology_path=_saphir_topology(tmp_path),
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    emulator.start()
    yield ConsoleController(emulator=emulator), emulator
    emulator.stop()


# --- initial state -----------------------------------------------------------
def test_initial_state_reflects_emulator(qapp, em, controller):
    assert controller.running is True
    assert controller.brokerPort == 1883
    assert controller.disks == ["d0"]
    assert "Dom0" in controller.peersConnected
    assert "sys-usb" in controller.peersConnected
    assert controller.energyLevel == 100.0
    assert controller.plugged is True


def test_started_domains_includes_core_peers(qapp, em, controller):
    """1.14: the started-domains list is non-empty (mocked core peers)."""
    domains = list(controller.startedDomains)
    assert "Dom0" in domains
    assert "sys-usb" in domains


def test_started_domains_includes_business_domains(qapp, topo_controller):
    """1.14: started domains = core peers + the topology's business domains."""
    controller, _em = topo_controller
    domains = list(controller.startedDomains)
    assert "Dom0" in domains and "sys-usb" in domains
    assert "saphir-gui" in domains
    # no duplicates
    assert len(domains) == len(set(domains))


def test_refresh_components(qapp, em, controller):
    """1.15: refresh_components exposes the peers' components to the GUI."""
    controller.refresh_components()
    components = controller.components
    assert components
    names = {c["name"] for c in components}
    assert "Mock disk controller" in names


# --- disk control ------------------------------------------------------------
def test_attach_and_detach_disk(qapp, em, controller, tmp_path):
    events = []
    controller.disksChanged.connect(lambda: events.append(1))

    new_disk = tmp_path / "d1"
    new_disk.mkdir()
    controller.attach_disk("d1", str(new_disk))
    assert "d1" in controller.disks
    assert events, "disksChanged not emitted on attach"

    controller.detach_disk("d1")
    assert "d1" not in controller.disks


def test_attach_disk_rejects_duplicate_id(qapp, em, controller, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    controller.attach_disk("d1", str(a))
    before = list(controller.disks)
    b = tmp_path / "b"
    b.mkdir()
    # same id, different path -> rejected, disks unchanged
    controller.attach_disk("d1", str(b))
    assert list(controller.disks) == before
    actions = [e.text for e in em.event_bus.entries("actions")]
    assert "attach_disk_rejected" in actions


def test_attach_disk_rejects_duplicate_path(qapp, em, controller, tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    controller.attach_disk("d1", str(a))
    before = list(controller.disks)
    # same path, different id -> rejected, disks unchanged
    controller.attach_disk("d2", str(a))
    assert list(controller.disks) == before


def test_attach_disk_without_emulator_warns(qapp, tmp_path):
    """1.13: attaching a disk without a running emulator warns in the GUI."""
    disk = tmp_path / "d0"
    disk.mkdir()
    controller = ConsoleController(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    warnings = []
    controller.warning.connect(lambda m: warnings.append(m))
    controller.attach_disk("d1", str(tmp_path))
    assert warnings and "not started" in warnings[0].lower()


def test_attach_disk_bad_path_warns(qapp, em, controller):
    """1.13: attaching a disk with a non-existent path warns in the GUI."""
    warnings = []
    controller.warning.connect(lambda m: warnings.append(m))
    controller.attach_disk("d1", "/nonexistent/path/xyz")
    assert warnings and "invalid path" in warnings[0].lower()
    assert "d1" not in controller.disks


def test_require_emulator_warns(qapp, tmp_path):
    """1.13: a control action with no emulator surfaces a warning, not silence."""
    disk = tmp_path / "d0"
    disk.mkdir()
    controller = ConsoleController(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    warnings = []
    controller.warning.connect(lambda m: warnings.append(m))
    try:
        controller.restart_domain("Dom0")
    except RuntimeError:
        pass
    assert warnings and "not started" in warnings[0].lower()


def test_control_action_not_started_warns(qapp, tmp_path):
    """An action with an existing but not-started emulator warns in the GUI.

    The raw "Emulator.start() must be called first" RuntimeError must not be the
    only feedback; the operator sees a friendly warning banner.
    """
    disk = tmp_path / "d0"
    disk.mkdir()
    emulator = Emulator(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )  # created, not started
    controller = ConsoleController(emulator=emulator)
    warnings = []
    controller.warning.connect(lambda m: warnings.append(m))
    try:
        controller.ping("Dom0", "")
    except RuntimeError:
        pass
    assert warnings and "not started" in warnings[0].lower()


def test_start_failure_warns(qapp, tmp_path, monkeypatch):
    """A failed start (unreachable broker) surfaces a warning, not silence."""
    disk = tmp_path / "d0"
    disk.mkdir()
    controller = ConsoleController(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )

    def _fail(self):
        raise RuntimeError("Mock core domains did not connect (unreachable broker)")

    monkeypatch.setattr(Emulator, "start", _fail)
    warnings = []
    controller.warning.connect(lambda m: warnings.append(m))
    controller.start_emulator()
    assert warnings and "failed to start" in warnings[0].lower()
    assert controller.running is False


# --- energy control ----------------------------------------------------------
def test_set_energy(qapp, em, controller):
    events = []
    controller.energyChanged.connect(lambda: events.append(1))
    controller.set_energy(42.0, False)
    assert controller.energyLevel == 42.0
    assert controller.plugged is False
    assert events, "energyChanged not emitted"


def test_power_off_and_on(qapp, em, controller):
    controller.power_off()
    assert controller.energyLevel == 0.0
    assert controller.plugged is False
    controller.power_on()
    assert controller.energyLevel == 100.0
    assert controller.plugged is True


# --- language / restart ------------------------------------------------------
def test_set_language(qapp, em, controller):
    events = []
    controller.stateChanged.connect(lambda: events.append(1))
    controller.set_language("fr")
    assert controller.defaultLanguage == "fr"
    assert events


def test_restart_domain(qapp, em, controller):
    controller.restart_domain("saphir-gui")
    assert "saphir-gui" in controller.restartedDomains


# --- workflow / GUI fakes ----------------------------------------------------
def test_shutdown_gui_ready_switch_gui(qapp, em, controller):
    assert controller.shutdown().get("state") == "accepted"
    assert controller.gui_ready().get("accepted") is True
    assert controller.switch_gui("saphir-gui").get("state") == "accepted"


# --- configuration switch (topology) -----------------------------------------
def test_select_configuration(qapp, topo_controller):
    controller, em = topo_controller
    assert em.configuration_names == ["Durabook R8"]
    controller.select_configuration("Durabook R8")
    assert em.configuration == "Durabook R8"
    controller.select_configuration("")
    assert em.configuration is None


# --- action journaling -------------------------------------------------------
def test_slots_record_actions(qapp, em, controller, tmp_path):
    disk = tmp_path / "dX"
    disk.mkdir()
    controller.attach_disk("dX", str(disk))
    controller.power_off()
    actions = em.event_bus.entries("actions")
    texts = [e.text for e in actions]
    assert "attach_disk" in texts
    assert "power_off" in texts


def test_action_logged_signal(qapp, em, controller):
    events = []
    controller.actionLogged.connect(lambda e: events.append(e))
    controller.power_off()
    # the signal carries a display-ready string, not the raw Event object
    assert any(isinstance(e, str) and "power_off" in e for e in events)


# --- bus-driven signals (wiring) ---------------------------------------------
def test_mqtt_event_logged_signal(qapp, em, controller):
    events = []
    controller.mqttEventLogged.connect(lambda e: events.append(e))
    em.event_bus.publish("mqtt_events", "Dom0", "test event", {"k": "v"})
    # the signal carries a display-ready string, not the raw Event object
    assert any(isinstance(e, str) and "test event" in e for e in events)


def test_log_line_signal(qapp, em, controller):
    lines = []
    controller.logLine.connect(lambda t: lines.append(t))
    em.event_bus.publish("platform_log", "Dom0", "a log line")
    # formatted as "<time> <source>: <text>"
    assert len(lines) == 1 and "Dom0: a log line" in lines[0]


# --- record toggles (file writing) -------------------------------------------
def test_record_journal_and_events(qapp, em, controller, tmp_path):
    journal = str(tmp_path / "journal.jsonl")
    events_file = str(tmp_path / "events.jsonl")

    controller.set_record_journal(journal)
    controller.set_record_events(events_file)

    controller.power_off()
    em.event_bus.publish("mqtt_events", "Dom0", "recorded event")

    controller.set_record_journal("")
    controller.set_record_events("")

    journal_lines = open(journal, encoding="utf-8").read().splitlines()
    assert any("power_off" in line for line in journal_lines)

    events_lines = open(events_file, encoding="utf-8").read().splitlines()
    assert any("recorded event" in line for line in events_lines)


# --- clear actions -----------------------------------------------------------
def test_clear_actions(qapp, em, controller):
    controller.power_off()
    assert len(em.event_bus.entries("actions")) >= 1
    controller.clear_actions()
    assert len(em.event_bus.entries("actions")) == 0


# --- misc slots + getters ----------------------------------------------------
def test_misc_slots_and_getters(qapp, em, controller):
    # getters
    assert controller.brokerOwned in (True, False)
    assert controller.environment is None  # the `em` fixture has no topology
    assert controller.languages == []

    # ping slot (real broker round-trip)
    resp = controller.ping("Dom0", "ping-data")
    assert resp is not None
    assert resp.get("source") == "Dom0"
    assert resp.get("data") == "ping-data"

    # no-effect slots just record an action
    controller.set_loglevel("debug")
    controller.save_log("d0", "log.txt")
    actions = [e.text for e in em.event_bus.entries("actions")]
    assert "ping" in actions
    assert "set_loglevel" in actions
    assert "save_log" in actions


def test_require_emulator_raises_without_emulator(qapp):
    controller = ConsoleController()
    with pytest.raises(RuntimeError):
        controller.detach_disk("d")


# --- controller-managed emulator lifecycle -----------------------------------
def test_start_and_stop_own_emulator(qapp, tmp_path):
    disk = tmp_path / "d0"
    disk.mkdir()
    controller = ConsoleController(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    assert controller.running is False
    controller.start_emulator()
    assert controller.running is True
    assert "d0" in controller.disks
    controller.stop_emulator()
    assert controller.running is False
    assert controller.peersConnected == []


def test_load_topology_hot_restart_warns(qapp, tmp_path):
    """Loading a topology while running stops, restarts, and warns (hot change)."""
    disk = tmp_path / "d0"
    disk.mkdir()
    controller = ConsoleController(
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    topo2 = tmp_path / "t2.json"
    topo2.write_text(
        json.dumps({"product": {"name": "Gamma", "languages": ["en"]}}),
        encoding="utf-8",
    )

    warnings = []
    controller.warning.connect(lambda message: warnings.append(message))

    controller.start_emulator()
    assert controller.running is True

    controller.load_topology(str(topo2))

    # restarted (still running) + warned + new product applied
    assert controller.running is True
    assert controller.productName == "Gamma"
    assert warnings and "hot change" in warnings[0]


def test_select_configuration_applies_screen_settings(qapp, tmp_path):
    """1.4: a configuration's ``settings`` override the displayed state."""
    disk = tmp_path / "d0"
    disk.mkdir()
    topo = {
        "product": {"name": "Rot", "languages": ["en"]},
        "screen": {"enabled": True, "rotation": 0, "default_focus": "gui"},
        "usb": {"use": True},
        "configurations": [
            {
                "name": "landscape",
                "identifier": {"sys_vendor": "V"},
                "settings": {"screen": {"rotation": 90}},
            },
        ],
    }
    path = tmp_path / "topo.json"
    path.write_text(json.dumps(topo), encoding="utf-8")
    em = Emulator(
        topology_path=str(path),
        source_disks={"d0": str(disk)},
        storage_path=str(tmp_path / "repo"),
        destination_disk_path=str(tmp_path / "target"),
    )
    em.start()
    try:
        controller = ConsoleController(emulator=em)
        assert controller.screenRotation == 0
        controller.select_configuration("landscape")
        assert controller.screenRotation == 90
        controller.select_configuration("")
        assert controller.screenRotation == 0
    finally:
        em.stop()
