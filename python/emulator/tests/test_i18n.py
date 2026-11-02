"""Unit tests for the console UI internationalization (Phase 3).

Covers the :mod:`safecor_emulator.i18n` catalog helpers and the
:class:`~safecor_emulator.console.ConsoleController` UI-language state
(default, switching, and fallback for unknown codes). The QML re-translation
itself is exercised in :mod:`test_gui` (it needs a loaded window).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication

from safecor_emulator import i18n
from safecor_emulator.console import ConsoleController


@pytest.fixture()
def app():
    return QGuiApplication.instance() or QGuiApplication([])


def test_supported_and_default_languages():
    assert i18n.DEFAULT_UI_LANGUAGE == "en"
    assert i18n.SUPPORTED_UI_LANGUAGES == ("en", "fr")


def test_translation_catalogs_exist():
    for lang in i18n.SUPPORTED_UI_LANGUAGES:
        assert i18n.has_translation(lang), f"missing catalog for {lang}"


def test_load_translator_translates_known_string():
    translator = i18n.load_translator("fr")
    assert translator is not None
    # A known console label must be translated by the FR catalog.
    assert translator.translate("SetupPanel", "Setup") == "Configuration"
    assert translator.translate("StatePanel", "State") == "État"


def test_load_translator_unknown_language_returns_none():
    assert i18n.load_translator("xx") is None


def test_console_ui_language_default(app):
    controller = ConsoleController(parent=app)
    assert controller.uiLanguage == "en"
    assert controller.supportedUiLanguages == ["en", "fr"]


def test_console_set_ui_language_switches_state(app):
    controller = ConsoleController(parent=app)
    controller.set_ui_language("fr")
    assert controller.uiLanguage == "fr"
    controller.set_ui_language("en")
    assert controller.uiLanguage == "en"


def test_console_set_ui_language_unknown_falls_back(app):
    controller = ConsoleController(parent=app)
    controller.set_ui_language("xx")
    assert controller.uiLanguage == "en"
