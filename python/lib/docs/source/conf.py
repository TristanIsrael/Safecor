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
    # Core extensions
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',  # Pour les docstrings Google/Numpy
    'sphinx.ext.viewcode',  # Lien vers le code source
    
    # Myst parser pour Markdown natif support
    "myst_parser",
]

templates_path = ['_templates']
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Custom sidebar template with Furo integration
html_extra_template = ['_templates/sidebar.html']

autosummary_generate = True
autosummary_imported_members = True

napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# -- Templates ---------------------------------------------------------------


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Thème sombre avec navigation moderne + recherche intégrée
html_theme = 'furo'

html_theme_options = {
    "logo": {
        "text": "Safecor",
    },
    "home_page_in_navlinks": False,
}
html_static_path = ['_static']
html_search_options = {
    'type': 'auto',
    'completion': True,
    'tools': ['site'],
}
html_context = {'docs_path': 'python/lib/docs'}

html_css_files = [
    "custom.css",
]

# Sources : support .rst et .md nativement via myst_parser
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