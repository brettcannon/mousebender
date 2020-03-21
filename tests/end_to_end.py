"""end_to_end

Sample script to describe how to use the mousebender.simple library.
Run this from the root of this repo by:
> PYTHONPATH=$PYTHONPATH:$PWD python end_to_end.py

Try pulling directly from pypi like so:
> PYTHONPATH=$PYTHONPATH:$PWD python end_to_end.py -r https://pypi.org -i simple


Usage:
  end_to_end.py --help
  end_to_end.py --version
  end_to_end.py [--package-name=PKG]
                  [--package-version=VER]
                  [--repo-index-base=URL] [--repo-index-name=PATH]

Options:
  -h --help                         Show this screen.
  -v --version                      Show version.
  -p [PKG] --package-name=PKG       Name of the package to find for installation. [default: numpy]
  -V [VER] --package-version=VER    Version of the package to find for installation. [default: 1.17.3]
  -r [URL] --repo-index-base=URL    The root URL to pull the repo index and package indexes from. 
                                    [default: tests/data/]
  -i [PATH] --repo-index-name=PATH  The repo index path. This is appended to the repo-index-base to find the
                                    repo information. [default: simple/index.html]
"""

# TODO: Add doc string to packaging.tags.parse_tag

import os
import packaging.specifiers
import packaging.tags
import packaging.utils
import pathlib
from typing import Dict, Generator, Iterable
import urllib.request

import docopt

from mousebender import simple


def filter_to_wheels(
    archive_links: Iterable[simple.ArchiveLink],
) -> Generator[simple.ArchiveLink, None, None]:
    return (a for a in archive_links if a.filename.endswith(".whl"))


def filter_wheels_to_version(
    wheels_links: Iterable[simple.ArchiveLink], version: str
) -> Dict[packaging.tags.Tag, simple.ArchiveLink]:
    tag_to_links = {}
    for link in wheels_links:
        _, whl_ver, compressed_tags = pathlib.Path(link.filename).stem.split("-", 2)
        if whl_ver != version:
            continue
        all_tags = packaging.tags.parse_tag(compressed_tags)
        for tag in all_tags:
            tag_to_links[tag] = link
    return tag_to_links


def find_package(
    package_name: str, package_ver: str, repo_index: str, repo_index_name: str
):

    url = f"{repo_index}/{repo_index_name}"
    url = url.replace("\\", "//")
    print(f"The URI to load the repo index from: {url}")

    with urllib.request.urlopen(url) as response:
        blob = response.read().decode("utf-8")

    pkg_index = simple.parse_repo_index(blob)
    if package_name in pkg_index:
        suffix_url = pkg_index[package_name].replace("\\", "/").replace("//", "/")
        pkg_url = f"{repo_index}{suffix_url}"
        if pkg_url.startswith("file:"):
            pkg_url += "index.html"
        with urllib.request.urlopen(pkg_url) as response:
            blob = response.read().decode("utf-8")
    else:
        return None

    archive_links = simple.parse_archive_links(blob)

    # Now we have everything available for "package_name", or nothing.

    relevant_links = filter_to_wheels(
        archive_links
    )  # get all wheels only, disregard other files
    tags_to_links = filter_wheels_to_version(
        relevant_links, package_ver
    )  # get all the wheels at this version

    for tag in packaging.tags.sys_tags():
        if link := tags_to_links.get(tag):
            return link
    else:
        return None


if __name__ == "__main__":
    opts = docopt.docopt(__doc__)

    # this_file = pathlib.Path(opts["--repo-index-base"])
    # simple_index_path = f"file:///{this_file.parent.absolute().joinpath('data')}"

    # index_name = "simple/index.html"
    # index_name = opts["--repo-index-name"]

    # found = find_package("numpy", "1.17.3", simple_index_path, index_name)
    # found = find_package("numpy", "1.17.3", "https://pypi.org", "simple")

    base = pathlib.Path(opts["--repo-index-base"])
    if base.is_dir():
        base_uri = str(base.absolute().as_uri())
    else:
        base_uri = opts["--repo-index-base"].strip()

    found = find_package(
        opts["--package-name"].strip(),
        opts["--package-version"].strip(),
        str(base_uri),
        opts["--repo-index-name"].strip(),
    )
    print(found)
