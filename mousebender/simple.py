from __future__ import annotations

import html
import html.parser
import urllib.parse
from typing import Dict, List, Union

import packaging.specifiers
import packaging.utils

# Python 3.8+ only.
from typing_extensions import Literal, TypedDict


def create_project_url(base_url: str, project_name: str) -> str:
    """Construct the project URL for a repository following PEP 503."""
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


_Meta = TypedDict("_Meta", {"api-version": Literal["1.0"]})


class ProjectIndex(TypedDict):
    meta: _Meta
    projects: List[Dict[Literal["name"], str]]


_HashesDict = Dict[str, str]
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


class ProjectFileDetails(_OptionalProjectFileDetails):
    filename: str
    url: str
    hashes: _HashesDict


class ProjectDetails(TypedDict):
    meta: _Meta
    name: packaging.utils.NormalizedName
    files: list[ProjectFileDetails]


class _SimpleIndexHTMLParser(html.parser.HTMLParser):

    """Parse the HTML of a repository index page."""

    # PEP 503:
    # Within a repository, the root URL (/) MUST be a valid HTML5 page with a
    # single anchor element per project in the repository.

    def __init__(self):
        super().__init__()
        self._parsing_anchor = False
        self.names = []

    def handle_starttag(self, tag, _attrs_list):
        if tag != "a":
            return
        self._parsing_anchor = True

    def handle_endtag(self, tag):
        if tag != "a":
            return
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self.names.append(data)


def from_project_index_html(html: str) -> ProjectIndex:
    """Parse the HTML of a repository index page."""
    parser = _SimpleIndexHTMLParser()
    parser.feed(html)
    project_index: ProjectIndex = {
        "meta": {"api-version": "1.0"},
        "projects": [{"name": name} for name in parser.names],
    }
    return project_index


class _ArchiveLinkHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        self.archive_links = []
        super().__init__()

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        if tag != "a":
            return
        # PEP 503:
        # The href attribute MUST be a URL that links to the location of the
        # file for download ...
        full_url = attrs["href"]
        parsed_url = urllib.parse.urlparse(full_url)
        # PEP 503:
        # ... the text of the anchor tag MUST match the final path component
        # (the filename) of the URL.
        _, _, raw_filename = parsed_url.path.rpartition("/")
        filename = urllib.parse.unquote(raw_filename)
        url = urllib.parse.urlunparse((*parsed_url[:5], ""))
        args = {"filename": filename, "url": url}
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
        if "data-requires-python" in attrs:
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
            metadata = attrs.get("data-dist-info-metadata")
            if metadata and metadata != "true":
                # The repository SHOULD provide the hash of the Core Metadata
                # file as the data-dist-info-metadata attribute's value using
                # the syntax <hashname>=<hashvalue>, where <hashname> is the
                # lower cased name of the hash function used, and <hashvalue> is
                # the hex encoded digest.
                algorithm, _, hash = metadata.partition("=")
                metadata = (algorithm.lower(), hash)
            else:
                # The repository MAY use true as the attribute's value if a hash
                # is unavailable.
                metadata = "", ""
            args["metadata"] = metadata

        self.archive_links.append(args)


def from_project_details_html(name: str, html: str) -> ProjectDetails:
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    files: List[ProjectFileDetails] = []
    for archive_link in parser.archive_links:
        details: ProjectFileDetails = {
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
