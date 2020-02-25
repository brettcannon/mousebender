"""Sample module to describe how to use this library.

1. Check if package is already installed ([spec](https://packaging.python.org/specifications/recording-installed-packages/) / [`importlib-metadata`](https://pypi.org/project/importlib-metadata/))
1. Check local wheel cache (? / ?; [how pip does it](https://pip.pypa.io/en/stable/reference/pip_install/#caching))
1. Choose appropriate file from PyPI/index
   1. Process the list of files ([Simple repository spec](https://packaging.python.org/specifications/simple-repository-api/) / ?; [PyPI JSON API](https://warehouse.pypa.io/api-reference/json/) / ?)
   1. Calculate best-fitting wheel ([spec](https://packaging.python.org/specifications/platform-compatibility-tags/) / `packaging.tags`)
1. _Download the wheel_
1. Cache the wheel locally (? / ?; see local cache check for potential details)
1. Install the wheel
   1. Install the files ([spec](https://packaging.python.org/specifications/distribution-formats/) / [`distlib.wheel`](https://distlib.readthedocs.io/en/latest/tutorial.html#installing-from-wheels))
   1. Record the installation ([spec](https://packaging.python.org/specifications/recording-installed-packages/) / ?)
"""
import os
import packaging.specifiers
import packaging.tags
import packaging.utils
import pathlib
import urllib.request

from mousebender import simple


def get_interpreter():
    return f"{packaging.tags.interpreter_name()}{packaging.tags.interpreter_version()}"


def get_abi():
    return f"{get_interpreter()}m"


def get_os_and_arch():
    uname = os.uname()
    os_name = uname.sysname
    if os_name == "Linux":
        os_name = "manylinux1"
    return f"{os_name}_{uname.machine}"


def install_package(
    package_name,
    package_version_spec,
    package_index_uri,
    package_index_name,
    allow_prereleases=False,
):
    with urllib.request.urlopen(
        f"{package_index_uri}/{package_index_name}"
    ) as response:
        html_index = response.read()
    all_packages = simple.parse_projects_index(html_index)
    url_for_packages_file_list = all_packages[package_name]
    print(
        f"Reading packages for {package_name} from package list at url '{url_for_packages_file_list}'"
    )

    with urllib.request.urlopen(
        f"{package_index_uri}/{url_for_packages_file_list}"
    ) as response:
        package_list = response.read()
    package_files = simple.parse_file_index(package_list)

    spec = packaging.specifiers.Specifier(package_version_spec)
    print(
        f"Attempting to find a package version {spec.operator} {spec.version}, prereleases:{spec.prereleases}"
    )

    # sort out the best version to use to satisfy this request.
    package_file_versions = [packaging.version.Version(pv) for pv in package_files]
    valid_versions = list(spec.filter(package_file_versions))
    valid_versions.sort()
    version_index = str(valid_versions[-1])
    print(f"We will grab the wheel from the versioned index {version_index}")
    best_package_list = package_files[version_index]

    for tag in packaging.tags.sys_tags():
        # build up the file name.
        # numpy-1.18.1-cp38-cp38-manylinux1_x86_64.whl
        constructed_pkg = [
            packaging.utils.canonicalize_name(package_name),
            packaging.utils.canonicalize_version(version_index),
            tag,
        ]
        filename = f"{'-'.join(constructed_pkg)}.whl"
        print("Looking for wheel file '{wheel_file}")
        for file_ in best_package_list:
            if file_.filename == filename:
                print(f"Found the best one! '{file_}")
                return file_
    return None


if __name__ == "__main__":
    this_file = pathlib.Path(__file__)
    simple_index_path = this_file.parent.joinpath("data/")

    install_package(
        "numpy",
        ">=1.0.0",
        f"file://{simple_index_path.absolute()}",
        "simple.index.html",
    )
