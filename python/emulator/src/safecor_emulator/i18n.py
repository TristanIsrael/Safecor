"""UI internationalization for the operator console.

The console UI (QML labels + a few controller strings) can be shown in several
languages, switchable at runtime. Translations are Qt ``.qm`` catalogs compiled
from the ``.ts`` sources in this directory (``pyside6-lrelease``). This module
only locates and loads the catalogs; the
:class:`~safecor_emulator.console.ConsoleController` owns the
:class:`QTranslator` lifecycle (install / swap / remove) so the QML re-translates
live when the operator changes the interface language.

English is the source language: its catalog carries empty translations and simply
falls back to the source strings, so the mechanism is uniform across languages.

This module requires PySide6 (the optional ``gui`` extra).
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTranslator

#: Directory holding the translation catalogs (``en.qm`` / ``fr.qm`` + ``.ts``).
I18N_DIR = Path(__file__).parent / "i18n"

#: UI languages the console supports, in display order.
SUPPORTED_UI_LANGUAGES = ("en", "fr")

#: Language used when the console starts (also the extraction source language).
DEFAULT_UI_LANGUAGE = "en"


def translation_file(language: str) -> Path:
    """Return the path of the compiled ``.qm`` catalog for ``language``."""
    return I18N_DIR / f"{language}.qm"


def has_translation(language: str) -> bool:
    """Return ``True`` if a compiled catalog exists for ``language``."""
    return translation_file(language).is_file()


def load_translator(language: str) -> Optional[QTranslator]:
    """Create a :class:`QTranslator` loaded with the ``language`` catalog.

    :param language: a code from :data:`SUPPORTED_UI_LANGUAGES`.
    :return: the loaded translator, or ``None`` if no catalog exists for it.
    """
    qm = translation_file(language)
    translator = QTranslator()
    if not qm.is_file() or not translator.load(str(qm)):
        return None
    return translator
