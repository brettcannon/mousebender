# mousebender

Produce/consume dependency lock files for Python

## Important Links

- [PyPI](https://pypi.org/project/mousebender/)
- [Documentation](https://mousebender.readthedocs.io/)

## Goals for this project

This project hopes to (eventually) provide a way to create reproducible installations for a virtual environment from a lock file -- or a version-pinned dependency list if "lock file" means `flock` to you -- derived from a `pyproject.toml` file. That will require defining a lock file format for wheel files as well as being able to perform installations based on that lock file. The ultimate goal is for that lock file format to become a standard (see [PEP 665](https://peps.python.org/pep-0665/) which was an initial attempt at this).

Or put another way, this project wants to work towards a standard for what [pip-tools](https://pypi.org/project/pip-tools/) and [pip requirements files](https://pip.pypa.io/en/stable/reference/requirements-file-format/) do.

To achieve this goal, this project will need to be able to:

- [x] Know what wheel files are available on an index server ([`mousebender.simple`](https://mousebender.readthedocs.io/en/latest/simple.html))
- [x] Read the metadata from a wheel file (in [`packaging.metadata`](https://packaging.pypa.io/en/stable/metadata.html))
- [ ] Resolve what wheel files are required to meet the requirements specified in `pyproject.toml`
- [ ] Produce a lock file of wheel files for a platform
- [ ] Consume a lock file for the platform to install the specified wheel files


Where does the name come from?
==============================
The customer from [Monty Python's cheese shop sketch](https://en.wikipedia.org/wiki/Cheese_Shop_sketch) is named "Mr. Mousebender". And in case you didn't know, the original name of [PyPI](https://pypi.org) was the Cheeseshop after the Monty Python sketch (see [PyPI's 404 page](https://pypi.org/404.html) for a link to the sketch).
