# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Safecor'
copyright = '2025-2026, Tristan Israël'
author = 'Tristan Israël'
release = '1.2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    # Google/Numpy style docstrings
    'sphinx.ext.napoleon',
    # Link to the code source
    'sphinx.ext.viewcode',
    # Native Markdown support
    "myst_parser",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autosummary_generate = True
autosummary_imported_members = True

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'pydata_sphinx_theme'
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
}

# Source suffixes: .rst and .md natively via myst_parser
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# -- Options for inheritance -----------------------------------
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

python_use_unqualified_type_names = True

# Constants
rst_epilog = f"""
.. |URL_DOC_PROTOCOL| replace:: https://github.com/TristanIsrael/Safecor/wiki/Protocol
"""
