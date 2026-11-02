"""UI internationalization for the operator console.

The console UI (QML labels + a few controller strings) can be shown in several
languages, switchable at runtime. Translations are Qt ``.qm`` catalogs compiled
from the ``.ts`` sources in this directory (``pyside6-lrelease``). The ``.qm``
files are gitignored build artifacts, so :func:`ensure_catalogs` compiles any
that are missing (self-healing a fresh checkout or a wheel built without them);
this module also locates and loads them. The
:class:`~safecor_emulator.console.ConsoleController` owns the
:class:`QTranslator` lifecycle (install / swap / remove) so the QML re-translates
live when the operator changes the interface language.

English is the source language: its catalog carries empty translations and simply
falls back to the source strings, so the mechanism is uniform across languages.

This module requires PySide6 (the optional ``gui`` extra).
"""

import shutil
import subprocess
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


def _find_lrelease() -> Optional[Path]:
    """Locate the ``lrelease`` compiler (on PATH or bundled with PySide6)."""
    on_path = shutil.which("lrelease")
    if on_path:
        return Path(on_path)
    try:
        import PySide6
    except ImportError:
        return None
    candidate = Path(PySide6.__file__).parent / "lrelease"
    return candidate if candidate.exists() else None


def ensure_catalogs() -> None:
    """Compile any missing ``.qm`` catalog from its ``.ts`` source.

    The ``.qm`` files are gitignored build artifacts, so a fresh checkout (or a
    wheel built without them) ships with no catalogs and language switching
    silently does nothing. This compiles whatever is missing so the console is
    self-sufficient. It is a fast no-op when all catalogs already exist, and a
    no-op when ``lrelease`` is unavailable.
    """
    if all(translation_file(code).is_file() for code in SUPPORTED_UI_LANGUAGES):
        return
    exe = _find_lrelease()
    if exe is None:
        return
    for language in SUPPORTED_UI_LANGUAGES:
        qm = translation_file(language)
        if qm.is_file():
            continue
        ts = I18N_DIR / f"{language}.ts"
        if not ts.is_file():
            continue
        try:
            subprocess.run(
                [str(exe), str(ts), "-qm", str(qm)],
                check=False,
                capture_output=True,
            )
        except OSError:
            continue


def has_translation(language: str) -> bool:
    """Return ``True`` if a compiled catalog exists for ``language``."""
    ensure_catalogs()
    return translation_file(language).is_file()


def load_translator(language: str) -> Optional[QTranslator]:
    """Create a :class:`QTranslator` loaded with the ``language`` catalog.

    :param language: a code from :data:`SUPPORTED_UI_LANGUAGES`.
    :return: the loaded translator, or ``None`` if no catalog exists for it.
    """
    ensure_catalogs()
    qm = translation_file(language)
    translator = QTranslator()
    if not qm.is_file() or not translator.load(str(qm)):
        return None
    return translator
