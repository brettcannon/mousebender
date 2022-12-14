# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import pathlib

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

pyproject_path = pathlib.Path(__file__).parent.parent / "pyproject.toml"
pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

project = pyproject["project"]["name"]
author = ", ".join(author["name"] for author in pyproject["project"]["authors"])
copyright = f"2022, {author}"  # noqa: A001
version = release = pyproject["project"]["version"]

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx-prompt",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "en-ca"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
# html_static_path = ["_static"]

# -- Options for autodoc ----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration

autodoc_member_order = "bysource"
autodoc_preserve_defaults = True

# Automatically extract typehints when specified and place them in
# descriptions of the relevant function/method.
autodoc_typehints = "signature"
autodoc_typehints_format = "short"

# -- Options for extlinks -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/extlinks.html#configuration


extlinks = {
    # "pep": ("https://peps.python.org/%s", "PEP %s"),
}

# -- Options for intersphinx ----------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration


intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "pypa": ("https://packaging.python.org/en/latest/", None),
}
