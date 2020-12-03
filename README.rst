mousebender
###########
A package for installing fully-specified Python packages.

Package contents
================

- ``mousebender.simple`` -- Parsers for the `simple repository API`_

Goals for this project
======================

The goal is to provide a package which could install all dependencies as frozen by a tool like `pip-tools`_ via an API (or put another way, what is required to install ``pip`` w/o using pip itself?). This avoids relying on pip's CLI to do installations but instead provide a programmatic API. It also helps discover any holes in specifications and/or packages for providing full support for Python package installation based on standards.

The steps to installing a package
---------------------------------

`PyPA specifications`_

#. Figure out what packages are necessary

    #. For an app, read lock file (?)
    #. For a package:

        #. Read list of dependencies (?)
        #. *Solve dependency constraints* (ResolveLib_)

#. Get the wheel to install

    #. Check if package is already installed (`spec <https://packaging.python.org/specifications/recording-installed-packages/>`__ / `importlib-metadata`_)
    #. Check local wheel cache (?; `how pip does it <https://pip.pypa.io/en/stable/reference/pip_install/#caching>`__)
    #. Choose appropriate file from PyPI/index

        #. Process the list of files (`simple repository API`_ / `mousebender.simple`)
        #. Calculate best-fitting wheel (`spec <https://packaging.python.org/specifications/platform-compatibility-tags/>`__ / `packaging.tags`_)
        #. If no wheel found ...

            #. Select and download the sdist (?)
            #. Build the wheel (`PEP 517`_, `PEP 518`_ / pep517_, build_)

    #. *Download the wheel*
    #. Cache the wheel locally (?)

#. Install the wheel

   #. Install the files (`spec <https://packaging.python.org/specifications/distribution-formats/>`__ / `distlib.wheel`_, installer_)
   #. Record the installation (`spec <https://packaging.python.org/specifications/recording-installed-packages/>`__ / ?)


Where does the name come from?
==============================
The customer from `Monty Python's cheese shop sketch`_ is named "Mr. Mousebender". And in case you don't know, the original name of PyPI_ was the Cheeseshop after the Monty Python sketch.


-----

.. image:: https://github.com/brettcannon/mousebender/workflows/CI/badge.svg
    :target: https://github.com/brettcannon/mousebender/actions?query=workflow%3ACI+branch%3Amaster+event%3Apush
    :alt: CI status

.. image:: https://img.shields.io/badge/coverage-100%25-brightgreen
    :target: https://github.com/brettcannon/mousebender/blob/master/pyproject.toml
    :alt: 100% branch coverage

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Formatted with Black

.. image:: http://www.mypy-lang.org/static/mypy_badge.svg
    :target: https://mypy.readthedocs.io/
    :alt: Checked by mypy

.. image:: https://img.shields.io/pypi/pyversions/mousebender
    :target: https://pypi.org/project/mousebender
    :alt: PyPI - Python Version

.. image:: https://img.shields.io/pypi/l/mousebender
    :target: https://github.com/brettcannon/mousebender/blob/master/LICENSE
    :alt: PyPI - License

.. image:: https://img.shields.io/pypi/wheel/mousebender
    :target: https://pypi.org/project/mousebender/#files
    :alt: PyPI - Wheel


.. _build: https://github.com/pypa/build
.. _distlib.wheel: https://distlib.readthedocs.io/en/latest/tutorial.html#installing-from-wheels
.. _importlib-metadata: https://pypi.org/project/importlib-metadata/
.. _installer: https://github.com/pradyunsg/installer
.. _Monty Python's cheese shop sketch: https://en.wikipedia.org/wiki/Cheese_Shop_sketch
.. _packaging.tags: https://packaging.pypa.io/en/latest/tags/
.. _PEP 517: https://www.python.org/dev/peps/pep-0517/
.. _PEP 518: https://www.python.org/dev/peps/pep-0518/
.. _pep517: https://pypi.org/project/pep517/
.. _pip-tools: https://pypi.org/project/pip-tools/
.. _PyPI: https://pypi.org
.. _PyPA specifications: https://packaging.python.org/specifications/
.. _ResolveLib: https://pypi.org/project/resolvelib/
.. _simple repository API: https://packaging.python.org/specifications/simple-repository-api/
