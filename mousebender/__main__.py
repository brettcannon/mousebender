"""end_to_end

Sample script to describe how to use the mousebender.simple library.
Run this from the root of this repo by:
> python -m mousebender

Try pulling directly from pypi like so:
> python -m mousebender -r https://pypi.org -i simple


Usage:
  mousebender --help
  mousebender --version
  mousebender [--package-name=PKG]
              [--package-version=VER]
              [--repo-index-base=URL] [--index-url=PATH]

Options:
  -h --help                         Show this screen.
  -v --version                      Show version.
  -p PKG --package-name=PKG         Name of the package to find for installation. [default: numpy]
  -V VER --package-version=VER      Version of the package to find for installation. [default: 1.17.3]
  -r URL --repo-index-base=URL      The root URL to pull the repo index and package indexes from. 
                                    [default: https://pypi.org]
  -i PATH --index-url=PATH          The repo index path. This is appended to the repo-index-base to find the
                                    repo information. [default: simple]
"""

import os
import pathlib
import urllib.request
from typing import Dict, Iterable, Iterator, List, Optional

import docopt  # type: ignore
import packaging.specifiers
import packaging.tags
import packaging.utils

from mousebender import simple


def filter_to_wheels(
    archive_links: Iterable[simple.ArchiveLink],
) -> Iterator[simple.ArchiveLink]:
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


def find_package(archive_links: Iterable[simple.ArchiveLink], package_ver: str):
    relevant_links = filter_to_wheels(
        archive_links
    )  # get all wheels only, disregard other files

    tags_to_links = filter_wheels_to_version(
        relevant_links, package_ver
    )  # get all the wheels at this version

    for tag in packaging.tags.sys_tags():
        if link := tags_to_links.get(tag):
            return link  # return the first compatible tag encountered
    else:
        return None


def get_package_links(
    repo_index: str, repo_subfolder: str, package_name: str
) -> Optional[Iterable[simple.ArchiveLink]]:  # pragma: no cover

    with urllib.request.urlopen(
        urllib.parse.urljoin(repo_index, repo_subfolder)
    ) as response:
        repo_index_data = response.read().decode("utf-8")

    pkg_index = simple.parse_repo_index(repo_index_data)

    if pkg_index and (package_name in pkg_index):
        with urllib.request.urlopen(
            urllib.parse.urljoin(repo_index, pkg_index[package_name])
        ) as response:
            archive_links_data = response.read().decode("utf-8")

        return simple.parse_archive_links(archive_links_data)

    return None


if __name__ == "__main__":  # pragma: no cover
    opts = docopt.docopt(__doc__)

    archive_links = get_package_links(
        repo_index=opts["--index-url"],
        repo_subfolder=opts["--repo-index-base"],
        package_name=opts["--package-name"],
    )

    if archive_links is not None:
        found = find_package(
            archive_links=archive_links, package_ver=opts["--package-version"].strip(),
        )
        print(found)
    else:
        print(
            f"""Could not find package 
            '{opts['--package-name']}', v{opts['--package-version']}
            in index at:
            {urllib.parse.urljoin(opts['--repo-index-base'], opts['--index-url'])}
            """
        )
