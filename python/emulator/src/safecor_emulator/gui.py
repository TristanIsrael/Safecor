"""QML bootstrap for the operator console (the ``--gui`` entry point).

Creates a :class:`QGuiApplication`, registers the
:class:`~safecor_emulator.console.ConsoleController` as a QML singleton and
loads the QML window. This is the graphical counterpart of the headless CLI:
without ``--gui`` the emulator runs headless and this module is never imported.

The emulator is built (so the topology-driven environment is known to the views
before start) but **not** started; the operator starts it from the *Setup*
panel. The QML never touches the :class:`~safecor_emulator.Emulator` directly —
the controller is the single bridge (Saphir / demo2 convention).

This module requires PySide6 (the optional ``gui`` extra).
"""

import os
import sys
from pathlib import Path
from typing import Any, Optional, cast

from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonInstance
from PySide6.QtQuick import QQuickWindow

from .console import ConsoleController
from .emulator import Emulator

#: URI / version under which the console controller is exposed to QML.
QML_URI = "safecor.emulator"
QML_MAJOR = 1
QML_MINOR = 0

#: Name of the singleton in QML (``ConsoleController``).
QML_SINGLETON_NAME = "ConsoleController"

#: Directory holding the QML sources (``main.qml`` + ``Components/``).
QML_DIR = Path(__file__).parent / "qml"

# Request the standard Material style for the console (Qt Quick Controls 2).
# Set before the QGuiApplication is created so it is in effect when the QML
# engine initialises; it falls back to the default style when unavailable.
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")


def build_controller(
    app: QGuiApplication, topology_path: Optional[str] = None, **emulator_params: Any
) -> ConsoleController:
    """Create the :class:`ConsoleController` backed by a not-yet-started Emulator.

    The :class:`Emulator` is constructed so that the topology-driven environment
    (product, languages, screen, business Domains, configurations) is already
    available to the views; :meth:`ConsoleController.start_emulator` starts it.

    :param app: the owning :class:`QGuiApplication`.
    :param topology_path: optional path to a product ``topology.json``.
    :param emulator_params: extra keyword arguments forwarded to the
        :class:`Emulator` constructor (``profile``, ``broker_port``, ...).
    """
    emulator = Emulator(topology_path=topology_path, **emulator_params)
    return ConsoleController(parent=app, emulator=emulator)


def create_engine(
    app: QGuiApplication, controller: ConsoleController
) -> QQmlApplicationEngine:
    """Register the controller as a QML singleton and load the window.

    Split from :func:`run_gui` so the window can be loaded and inspected
    offscreen (tests) without entering the event loop.

    :param app: the owning :class:`QGuiApplication`.
    :param controller: the :class:`ConsoleController` to expose.
    """
    # The PySide6 stub types the singleton ``name`` as ``bytes``; at runtime it
    # is a str, so the annotation is ignored here.
    qmlRegisterSingletonInstance(
        ConsoleController,
        QML_URI,
        QML_MAJOR,
        QML_MINOR,
        QML_SINGLETON_NAME,  # type: ignore[arg-type]
        controller,
    )
    engine = QQmlApplicationEngine()
    engine.addImportPath(QML_DIR)
    engine.load((QML_DIR / "main.qml").as_uri())
    # Let the controller retranslate the UI when the operator changes language.
    controller.set_engine(engine)
    return engine


def _apply_theme(app: QGuiApplication) -> None:
    """Follow the system light/dark color scheme (guarded).

    Minimal / offscreen Qt builds may lack the color-scheme APIs; in that case
    the console keeps the default palette. On a full Qt the window follows the
    system appearance, fixing illegible text when the system is in dark mode.
    """
    try:
        from PySide6.QtGui import QColorScheme, QStyleHints

        dark = QGuiApplication.colorScheme() == QColorScheme.Dark
        app.styleHints().setColorScheme(
            QStyleHints.ColorScheme.Dark if dark else QStyleHints.ColorScheme.Light
        )
    except (AttributeError, ImportError, RuntimeError):
        pass


def run_gui(topology_path: Optional[str] = None, **emulator_params: Any) -> int:
    """Build the app + controller, show the window, and run the event loop.

    :return: the exit code of the Qt event loop.
    """
    # ``QGuiApplication.instance()`` is stubbed as returning the base
    # ``QCoreApplication``; the live instance is in fact a ``QGuiApplication``.
    app = cast(QGuiApplication, QGuiApplication.instance()) or QGuiApplication(sys.argv)
    _apply_theme(app)
    controller = build_controller(app, topology_path, **emulator_params)
    engine = create_engine(app, controller)
    if not engine.rootObjects():
        raise RuntimeError("Failed to load the operator console QML window")
    # The QML root is an ``ApplicationWindow`` (a ``QQuickWindow`` at runtime).
    window = cast(QQuickWindow, engine.rootObjects()[0])
    window.show()
    return app.exec()
