"""Utilities to help with Simple repository API responses.

This module helps with the JSON-based Simple repository API by providing
:class:`~typing.TypedDict` definitions for API responses. For HTML-based
responses, functions are provided to convert the HTML to the equivalent JSON
response.

This module implements :pep:`503`, :pep:`592`, :pep:`658`, and :pep:`691` of the
:external:ref:`Simple repository API <simple-repository-api>` (it forgoes
:pep:`629` as :pep:`691` makes it obsolete).

"""
from __future__ import annotations

import html
import html.parser
import urllib.parse
from typing import Any, Dict, List, Optional, Union

import packaging.specifiers
import packaging.utils

# Python 3.8+ only.
from typing_extensions import Literal, TypeAlias, TypedDict

_Meta_1_0 = TypedDict("_Meta_1_0", {"api-version": Literal["1.0"]})


class ProjectIndex_1_0(TypedDict):
    """A :class:`~typing.TypedDict` for a project index (JSON v1.0)."""

    meta: _Meta_1_0
    projects: List[Dict[Literal["name"], str]]


# Turn into a union when future API versions are supported.
ProjectIndex: TypeAlias = ProjectIndex_1_0
"""A :data:`~typing.TypeAlias` for any version of the JSON project
index response."""


_HashesDict: TypeAlias = Dict[str, str]

_OptionalProjectFileDetails = TypedDict(
    "_OptionalProjectFileDetails",
    {
        "requires-python": str,
        "dist-info-metadata": Union[bool, _HashesDict],
        "gpg-sig": bool,
        "yanked": Union[bool, str],
    },
    total=False,
)


class ProjectFileDetails_1_0(_OptionalProjectFileDetails):
    """A :class:`~typing.TypedDict` for the ``files`` key of :class:`ProjectDetails_1_0`."""

    filename: str
    url: str
    hashes: _HashesDict


class ProjectDetails_1_0(TypedDict):
    """A :class:`~typing.TypedDict` for a project details response (JSON v1.0)."""

    meta: _Meta_1_0
    name: packaging.utils.NormalizedName
    files: list[ProjectFileDetails_1_0]


# Turn into a union when future API versions are supported.
ProjectDetails: TypeAlias = ProjectDetails_1_0
"""A :data:`~typing.TypeAlias` for any version of the JSON project details
response."""


class _SimpleIndexHTMLParser(html.parser.HTMLParser):
    # PEP 503:
    # Within a repository, the root URL (/) MUST be a valid HTML5 page with a
    # single anchor element per project in the repository.

    def __init__(self) -> None:
        super().__init__()
        self._parsing_anchor = False
        self.names: List[str] = []

    def handle_starttag(
        self, tag: str, _attrs_list: list[tuple[str, Optional[str]]]
    ) -> None:
        if tag != "a":
            return
        self._parsing_anchor = True

    def handle_endtag(self, tag: str) -> None:
        if tag != "a":
            return
        self._parsing_anchor = False

    def handle_data(self, data: str) -> None:
        if self._parsing_anchor:
            self.names.append(data)


def from_project_index_html(html: str) -> ProjectIndex_1_0:
    """Convert the HTML response of a repository index page to a JSON v1.0 response."""
    parser = _SimpleIndexHTMLParser()
    parser.feed(html)
    project_index: ProjectIndex = {
        "meta": {"api-version": "1.0"},
        "projects": [{"name": name} for name in parser.names],
    }
    return project_index


class _ArchiveLinkHTMLParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        self.archive_links: List[Dict[str, Any]] = []
        super().__init__()

    def handle_starttag(
        self, tag: str, attrs_list: list[tuple[str, Optional[str]]]
    ) -> None:
        attrs = dict(attrs_list)
        if tag != "a":
            return
        # PEP 503:
        # The href attribute MUST be a URL that links to the location of the
        # file for download ...
        if "href" not in attrs or not attrs["href"]:
            return
        full_url: str = attrs["href"]
        parsed_url = urllib.parse.urlparse(full_url)
        # PEP 503:
        # ... the text of the anchor tag MUST match the final path component
        # (the filename) of the URL.
        _, _, raw_filename = parsed_url.path.rpartition("/")
        filename = urllib.parse.unquote(raw_filename)
        url = urllib.parse.urlunparse((*parsed_url[:5], ""))
        args: Dict[str, Any] = {"filename": filename, "url": url}
        # PEP 503:
        # The URL SHOULD include a hash in the form of a URL fragment with the
        # following syntax: #<hashname>=<hashvalue> ...
        if parsed_url.fragment:
            hash_algo, hash_value = parsed_url.fragment.split("=", 1)
            args["hashes"] = hash_algo.lower(), hash_value
        # PEP 503:
        # A repository MAY include a data-requires-python attribute on a file
        # link. This exposes the Requires-Python metadata field ...
        # In the attribute value, < and > have to be HTML encoded as &lt; and
        # &gt;, respectively.
        if "data-requires-python" in attrs and attrs["data-requires-python"]:
            requires_python_data = html.unescape(attrs["data-requires-python"])
            args["requires-python"] = requires_python_data
        # PEP 503:
        # A repository MAY include a data-gpg-sig attribute on a file link with
        # a value of either true or false ...
        if "data-gpg-sig" in attrs:
            args["gpg-sig"] = attrs["data-gpg-sig"] == "true"
        # PEP 592:
        # Links in the simple repository MAY have a data-yanked attribute which
        # may have no value, or may have an arbitrary string as a value.
        if "data-yanked" in attrs:
            args["yanked"] = attrs.get("data-yanked") or True
        # PEP 658:
        # ... each anchor tag pointing to a distribution MAY have a
        # data-dist-info-metadata attribute.
        if "data-dist-info-metadata" in attrs:
            found_metadata = attrs.get("data-dist-info-metadata")
            if found_metadata and found_metadata != "true":
                # The repository SHOULD provide the hash of the Core Metadata
                # file as the data-dist-info-metadata attribute's value using
                # the syntax <hashname>=<hashvalue>, where <hashname> is the
                # lower cased name of the hash function used, and <hashvalue> is
                # the hex encoded digest.
                algorithm, _, hash_ = found_metadata.partition("=")
                metadata = (algorithm.lower(), hash_)
            else:
                # The repository MAY use true as the attribute's value if a hash
                # is unavailable.
                metadata = "", ""
            args["metadata"] = metadata

        self.archive_links.append(args)


def create_project_url(base_url: str, project_name: str) -> str:
    """Construct the URL for a project hosted on a server at *base_url*."""
    if base_url and not base_url.endswith("/"):
        base_url += "/"  # Normalize for easier use w/ str.join() later.
    # PEP 503:
    # The format of this URL is /<project>/ where the <project> is replaced by
    # the normalized name for that project, so a project named "HolyGrail" would
    # have a URL like /holygrail/.
    #
    # All URLs which respond with an HTML5 page MUST end with a / and the
    # repository SHOULD redirect the URLs without a / to add a / to the end.
    return "".join([base_url, packaging.utils.canonicalize_name(project_name), "/"])


def from_project_details_html(html: str, name: str) -> ProjectDetails_1_0:
    """Convert the HTML response for a project details page to a JSON v1.0 response.

    Due to HTML project details pages lacking the name of the project, it must
    be specified via the *name* parameter to fill in the JSON data.
    """
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    files: List[ProjectFileDetails_1_0] = []
    for archive_link in parser.archive_links:
        details: ProjectFileDetails_1_0 = {
            "filename": archive_link["filename"],
            "url": archive_link["url"],
            "hashes": {},
        }
        if "hashes" in archive_link:
            details["hashes"] = dict([archive_link["hashes"]])
        if "metadata" in archive_link:
            algorithm, value = archive_link["metadata"]
            if algorithm:
                details["dist-info-metadata"] = {algorithm: value}
            else:
                details["dist-info-metadata"] = True
        for key in {"requires-python", "yanked", "gpg-sig"}:
            if key in archive_link:
                details[key] = archive_link[key]  # type: ignore
        files.append(details)
    return {
        "meta": {"api-version": "1.0"},
        "name": packaging.utils.canonicalize_name(name),
        "files": files,
    }
