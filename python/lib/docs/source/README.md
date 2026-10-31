# Sphinx Documentation - Safecor Library

## 📖 Overview

**Safecor** documentation uses **Sphinx** to generate automated technical documentation from source code and docstrings. It provides:

- ✅ Native dark theme (dark mode)
- ✅ Global search bar
- ✅ Sidebar navigation with collapsible accordion menus
- ✅ Automatic documentation generation from Python code
- ✅ Markdown + RST support

---

## 🎨 Themes and Customization

### Theme in Use

```python
html_theme = 'readthedocs_docs_dark_mode'
```

The `readthedocs_docs_dark_mode` theme natively provides:
- Dark design by default
- Sidebar navigation with hierarchical levels
- Built-in search powered by the Sphinx API
- Support for nested menus (`navigation_depth: 3`)

### Custom Configuration (`conf.py`)

| Option | Recommended Value |
|--------|-------------------|
| `html_theme` | `'readthedocs_docs_dark_mode'` |
| `html_theme_options.navigation_depth` | `3` (navigation depth) |
| `html_search_options.type` | `"auto"` (autocomplete search) |
| `autosummary_generate` | `True` (automatic documentation generation) |

### Custom Template (`_templates/sidebar.html`)

HTML file that directly injects the following elements into the sidebar:
- Search forms
- Secondary/tertiary sidebars

---

## 🔧 CSS Customization

File: `_static/custom.css`

This file adds specific styles for:

1. **Search bar** - Integrated into the sidebar
2. **Accordion-style menu** - Downward-pointing arrows and dark colors
3. **Highlights** - Colored borders around code blocks
4. **Active navigation** - Visual indicators
5. **Accessibility** - Visible focus states

---

## 🚀 Build & Deployment

### Locally (Development)

Documentation is built from the `python/lib/docs/source` directory:

```bash
# Installation (python/lib directory)
poetry install
poetry run pip install sphinx-autobuild

# Live build
cd docs/source
poetry run sphinx-autobuild -b html .
```

### CI/CD (`.github/workflows/documentation.yml`)

The GitHub Pages workflow generates the documentation in three steps:

1️⃣ **Setup**

   ```yaml
   python-version: "3.11"
   pip install requirements-doc.txt requirements.txt
   poetry install
   ```

2️⃣ **Build Documentation**

   ```bash
   # Automatically generates API pages
   poetry run sphinx-autogen -o docs/source/api/generated api/safecor.rst
   
   # Generates the final HTML output
   poetry run sphinx-build -b html docs/source docs/build/html
   ```

3️⃣ **Deploy**

   The `python/lib/docs/build/html` artifact is deployed to GitHub Pages.

---

## 🛠️ Active Sphinx Extensions

- `sphinx.ext.autodoc` — Generates documentation from docstrings
- `sphinx.ext.napoleon` — Google/Numpy docstring formatting
- `sphinx.ext.viewcode` — Links to the online source code
- `myst_parser` — Markdown support alongside RST

---

## 📦 Generated Documentation

The final documentation structure includes:

```
Safecor Documentation (Dark Mode)
├── Home / Index
│   ├── API Reference (auto-generated from safecor.rst)
│   │   ├── Core classes & functions
│   │   ├── DomainController interfaces
│   │   └── Hardware APIs
│   ├── Emulator documentation
│   └── Quick start guide (if added)
```

---

## ✍️ Updating the Documentation

To update the documentation:

1. **Add or modify a docstring** in the source code.
2. Make sure it follows the Google or NumPy style.
3. Rebuild the documentation (`sphinx-autogen` → `sphinx-build`).
4. Commit and push → Documentation is automatically updated via GitHub Actions.

---

## 📝 Documentation Standards

- Language: **English** (as specified in `AGENTS.md`)
- Docstring format: Google or NumPy style
- Doxygen comments in Python implementations
- Keep `README.md` and `docs/index.rst` synchronized

---

*Last updated: 2026-10-30*