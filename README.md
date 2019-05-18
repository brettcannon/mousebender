# mousebender
A package for installing fully-specified Python packages

The goal is to provide a package which could install all dependencies as frozen by a tool like [pip-tools](https://pypi.org/project/pip-tools/) via an API. This avoids relying on pip's CLI to do installations but instead provide a more programmatic API. It also helps discover any holes in specifications and/or packages for providing such a feature. 

## The steps to installing a package

### If you requested `mousebender` 1.0.0

1. Check if package is already installed ([spec](https://packaging.python.org/specifications/recording-installed-packages/) / [`importlib-metadata`](https://pypi.org/project/importlib-metadata/))
1. Check local wheel cache (? / ?; [how pip does it](https://pip.pypa.io/en/stable/reference/pip_install/#caching))
1. Check PyPI/index for package ([spec](https://packaging.python.org/specifications/simple-repository-api/) / ?)
1. Choose appropriate file
   1. Get the list of files ([spec](https://packaging.python.org/specifications/simple-repository-api/) / ?)
   1. Calculate best-fitting wheel ([spec](https://packaging.python.org/specifications/platform-compatibility-tags/) / `packaging.tags`)
1. Download the wheel
1. Cache the wheel locally (? / ?; see local cache check for potential details)
1. Install the wheel
   1. Install the files ([spec](https://packaging.python.org/specifications/distribution-formats/) / ?)
   1. Record the installation ([spec](https://packaging.python.org/specifications/recording-installed-packages/) / ?)

  
### Things left out that pip does

These might be added in the future, but they are not considered requirements for a 1.0 release:

* Parse a frozen `requirements.txt` file
* Translate `mousebender=1.0.0` to `mousebender` 1.0.0
* Install from an sdist
* Install dependencies (i.e. read dependencies from wheel, solve dependency graph)

## Where does the name come from?
The customer from [Monty Python's cheese shop sketch](https://en.wikipedia.org/wiki/Cheese_Shop_sketch) is named "Mr. Mousebender". And in case you don't know, the original name of [PyPI](https://pypi.org/) was the Cheeseshop after the Monty Python sketch.
