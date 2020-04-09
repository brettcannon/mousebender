mousebender
###########
A package for installing fully-specified Python packages.

Package contents
================

- ``mousbender.simple`` -- Parsers for the `simple repository API`_

Goals for this project
======================

The goal is to provide a package which could install all dependencies as frozen by a tool like `pip-tools`_ via an API (or put another way, what is required to install ``pip`` w/o using pip itself?). This avoids relying on pip's CLI to do installations but instead provide a programmatic API. It also helps discover any holes in specifications and/or packages for providing full support for Python package installation based on standards.

The steps to installing a package
---------------------------------

`PyPA specifications`_

1. Check if package is already installed (`spec <https://packaging.python.org/specifications/recording-installed-packages/>`__ / `importlib-metadata`_)
2. Check local wheel cache (? / ?; `how pip does it <https://pip.pypa.io/en/stable/reference/pip_install/#caching>`__)
3. Choose appropriate file from PyPI/index

   1. Process the list of files (`simple repository API`_ / `mousebender.simple`)
   2. Calculate best-fitting wheel (`spec <https://packaging.python.org/specifications/platform-compatibility-tags/>`__ / `packaging.tags`_)

4. *Download the wheel*
5. Cache the wheel locally (? / ?)
6. Install the wheel

   1. Install the files (`spec <https://packaging.python.org/specifications/distribution-formats/>`__ / `distlib.wheel`_)
   2. Record the installation (`spec <https://packaging.python.org/specifications/recording-installed-packages/>`__ / ?)


Things pip does that the above outline doesn't
----------------------------------------------

* Parse a frozen ``requirements.txt`` file
* Install from an sdist
* Install dependencies (i.e. read dependencies from wheel, solve dependency graph)
* Networking (everything is sans-I/O to allow the user to use whatever networking approach they want)

Where does the name come from?
==============================
The customer from `Monty Python's cheese shop sketch`_ is named "Mr. Mousebender". And in case you don't know, the original name of PyPI_ was the Cheeseshop after the Monty Python sketch.


---
.. image::https://img.shields.io/badge/code%20style-black-000000.svg :target: https://github.com/psf/black


.. _distlib.wheel: https://distlib.readthedocs.io/en/latest/tutorial.html#installing-from-wheels
.. _importlib-metadata: https://pypi.org/project/importlib-metadata/
.. _Monty Python's cheese shop sketch: https://en.wikipedia.org/wiki/Cheese_Shop_sketch
.. _packaging.tags: https://packaging.pypa.io/en/latest/tags/
.. _pip-tools: https://pypi.org/project/pip-tools/
.. _PyPI: https://pypi.org
.. _PyPA specifications: https://packaging.python.org/specifications/
.. _simple repository API: https://packaging.python.org/specifications/simple-repository-api/
