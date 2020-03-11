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


"""
url = simple.create_project_url("https://pypi.org/simple", "interesting_pkg")

blob = await read_index(url)
pkg_index = simple.parse_repo_index:
if "interesting_pkg" in pkg_index:
    blob = await read_index(pkg_index["interesting_pkg"])
else:
    return None


achive_links = simple.parse_archive_links(blob)

# Now we have everything available for "interesting_pkg", or nothing.

relevant_links = filter_to_wheels(archive_links) # get all wheels only, disregard other files
tags_to_links = filter_wheels_to_version(relevant_links, "1.2.3") # get all the wheels at this version

for tag in packaging.tags.sys_tags():
    if link := tags_to_links.get(tag):
        return link
else:
    return None


def filter_to_wheels(archive_links: Iterable[simple.ArchiveLink]) -> Generator[simple.ArchiveLink]:
    return (a for a in archive_links if a.file_name.endswith(".whl"))

def filter_wheels_to_version(wheels_links: Iterable[simple.ArchiveLink], version: str) -> Generator[simple.ArchiveLink]:
    tag_to_links = {}
    for link in wheels_links:
        _, whl_ver, compressed_tags = pathlib.Path(link.file_name).stem.split("-", 2)
        if whl_ver != version:
            continue
        all_tags = packaging.tags.parse_tag(compressed_tags)
        for tag in all_tags:
            tag_to_links[tag] = link
    return tag_to_links

# tags_to_links |= { tag : ln for tag in all_tags }
# TODO: Add doc string to packaging.tags.parse_tag

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
