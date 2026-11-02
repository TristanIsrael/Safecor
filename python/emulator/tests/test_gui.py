"""Offscreen QML validation for the operator console (Phase 2).

Loads the real QML window with a real (not-started)
:class:`~safecor_emulator.console.ConsoleController` and verifies that:

* the window loads (``rootObjects`` non-empty, expected items present);
* the bindings resolve to the controller state (a StatePanel text matches the
  topology's product name);
* a controller-driven change propagates to the view (``load_topology`` with a
  different product updates the same bound text);
* :func:`build_controller` wraps a not-started Emulator in a controller;
* :func:`run_gui` (the process entry) boots and returns the loop exit code.

The emulator is never started (no broker / peers needed); the driven change
uses :meth:`load_topology`, which only rebuilds the environment.

Qt allows a single ``QQmlApplicationEngine`` per process, so the QML window is
loaded once (module-scoped) for the binding tests, and the entry point
:func:`run_gui` is exercised in a fresh subprocess (which also mirrors the real
``safecor-emulator --gui`` deployment); that subprocess self-measures gui.py
coverage to enforce the >= 85 % module gate.
"""

import json
import os
import subprocess
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem

from safecor_emulator.console import ConsoleController
from safecor_emulator.emulator import Emulator
from safecor_emulator.gui import _apply_theme, build_controller, create_engine


def _write_topology(directory, product: str, name: str) -> str:
    data = {
        "product": {
            "name": product,
            "languages": ["en", "fr"],
            "default_language": "en",
        },
        "usb": {"use": True},
        "screen": {"enabled": True, "rotation": 90, "default_focus": "gui"},
        "business": {"domains": [{"name": "gui", "has_gui": True}]},
        "configurations": [
            {"name": "laptop", "identifier": {"product_name": "LAPTOP"}}
        ],
    }
    path = directory / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _spin(app, iterations: int = 10):
    """Let pending Qt bindings / queued signals / deferred deletions settle."""
    for _ in range(iterations):
        QCoreApplication.processEvents()


@pytest.fixture(scope="module")
def qapp():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app


@pytest.fixture(scope="module")
def console(qapp, tmp_path_factory):
    """A single loaded QML window shared by the binding tests.

    Qt allows one ``QQmlApplicationEngine`` per process, so it is created once
    for the module and torn down at the end.
    """
    directory = tmp_path_factory.mktemp("gui")
    topology = _write_topology(directory, "Alpha", "alpha.json")
    controller = ConsoleController(
        parent=qapp, emulator=Emulator(topology_path=topology)
    )
    engine = create_engine(qapp, controller)
    assert engine.rootObjects(), "the operator console QML window did not load"
    yield SimpleNamespace(
        controller=controller, engine=engine, window=engine.rootObjects()[0]
    )
    _spin(qapp)
    engine.deleteLater()


def test_window_loads_and_structure(console, qapp):
    window = console.window
    assert window is not None
    _spin(qapp)
    assert "Operator Console" in window.property("title")
    # A bound item from a sub-component must be reachable.
    assert window.findChild(QQuickItem, "stateProduct") is not None


def test_apply_theme_is_guarded(qapp):
    """_apply_theme must not raise when the color-scheme APIs are absent."""
    _apply_theme(qapp)


def test_bindings_resolve(console, qapp):
    _spin(qapp)
    product = console.window.findChild(QQuickItem, "stateProduct")
    assert product is not None
    assert product.property("text") == "Alpha"


def test_driven_state_change_updates_view(console, qapp, tmp_path_factory):
    directory = tmp_path_factory.mktemp("gui2")
    topology = _write_topology(directory, "Beta", "beta.json")
    product = console.window.findChild(QQuickItem, "stateProduct")
    assert product is not None
    assert product.property("text") == "Alpha"

    console.controller.load_topology(topology)
    _spin(qapp)

    assert console.controller.productName == "Beta"
    assert product.property("text") == "Beta"


def test_ui_language_switch_retranslates(console, qapp):
    """Switching the UI language retranslates the loaded QML (via retranslate)."""
    window = console.window
    assert "Operator Console" in window.property("title")

    console.controller.set_ui_language("fr")
    _spin(qapp)
    assert console.controller.uiLanguage == "fr"
    assert "Console d'exploitation" in window.property("title")

    # Switching back restores the source (English) strings.
    console.controller.set_ui_language("en")
    _spin(qapp)
    assert console.controller.uiLanguage == "en"
    assert "Operator Console" in window.property("title")


def test_build_controller(qapp):
    """build_controller wraps a not-started Emulator in a ConsoleController."""
    controller = build_controller(qapp)
    assert isinstance(controller, ConsoleController)
    assert not controller.running
    assert controller.productName == ""


def test_run_gui_subprocess(tmp_path):
    """run_gui (the process entry) boots in a fresh process and covers gui.py.

    A fresh subprocess is required because Qt allows one engine per process;
    the subprocess also self-measures gui.py coverage (>= 85 % gate).
    """
    topology = _write_topology(tmp_path, "Gamma", "gamma.json")
    result_file = tmp_path / "gui_cov.txt"
    script = (
        "import os, sys; os.environ['QT_QPA_PLATFORM'] = 'offscreen'\n"
        "import coverage\n"
        "cov = coverage.Coverage(source=['safecor_emulator.gui'])\n"
        "cov.erase(); cov.start()\n"
        "import safecor_emulator.gui as gui_mod\n"
        "from PySide6.QtGui import QGuiApplication\n"
        "app = QGuiApplication([])\n"
        "app.exec = lambda: 42\n"
        f"rc = gui_mod.run_gui(topology_path={topology!r})\n"
        "cov.stop()\n"
        "total = cov.report(show_missing=False)\n"
        f"open({str(result_file)!r}, 'w').write(str(total))\n"
        "assert rc == 42\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    total = float(result_file.read_text(encoding="utf-8"))
    assert total >= 85.0, f"gui.py coverage {total}% is below the 85% gate"
