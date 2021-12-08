"""Parsing for PEP 503 -- Simple Repository API."""
import html
import html.parser
import re
import urllib.parse
import warnings

from typing import List, Optional, Tuple

import attr
import packaging.specifiers

_NORMALIZE_RE = re.compile(r"[-_.]+")

PYPI_INDEX = "https://pypi.org/simple/"

_SUPPORTED_VERSION = (1, 0)


class UnsupportedVersion(Exception):

    """A major version of the Simple API is used which is not supported."""


class UnsupportedVersionWarning(Warning, UnsupportedVersion):

    """A minor version of the Simple API is used which is not supported.

    This is a subclass of UnsupportedVersion so that catching and handling
    major version discrepancies will also include less critical minor version
    concerns as well.
    """


def create_project_url(base_url, project_name):
    """Construct the project URL for a repository following PEP 503."""
    if base_url and not base_url.endswith("/"):
        base_url += "/"
    # https://www.python.org/dev/peps/pep-0503/#normalized-names
    normalized_project_name = _NORMALIZE_RE.sub("-", project_name).lower()
    # PEP 503:
    # The format of this URL is /<project>/ where the <project> is replaced by
    # the normalized name for that project, so a project named "HolyGrail" would
    # have a URL like /holygrail/.
    #
    # All URLs which respond with an HTML5 page MUST end with a / and the
    # repository SHOULD redirect the URLs without a / to add a / to the end.
    return "".join([base_url, normalized_project_name, "/"])


def _normalize_project_url(url):
    """Normalizes a project URL found in a repository index.

    If a repository is fully-compliant with PEP 503 this will be a no-op.
    If a repository is reasonably compliant with PEP 503 then the resulting URL
    will be usable.

    """
    url_no_trailing_slash = url.rstrip("/")  # Explicitly added back later.
    base_url, _, project_name = url_no_trailing_slash.rpartition("/")
    return create_project_url(base_url, project_name)


def _check_version(tag, attrs):
    """Check if the tag is a PEP 629 tag and is a version that is supported."""
    if tag != "meta" or attrs.get("name") != "pypi:repository-version":
        return

    major, minor = map(int, attrs["content"].split("."))
    if major != _SUPPORTED_VERSION[0]:
        msg = f"v{_SUPPORTED_VERSION[0]} supported, but v{major} used"
        raise UnsupportedVersion(msg)
    elif major == _SUPPORTED_VERSION[0] and minor > _SUPPORTED_VERSION[1]:
        msg = (
            f"v{_SUPPORTED_VERSION[0]}.{_SUPPORTED_VERSION[1]} supported, "
            "but v{_SUPPORTED_VERSION[0]}.{minor_version} used"
        )
        warnings.warn(msg, UnsupportedVersionWarning)


class _SimpleIndexHTMLParser(html.parser.HTMLParser):

    """Parse the HTML of a repository index page."""

    # PEP 503:
    # Within a repository, the root URL (/) MUST be a valid HTML5 page with a
    # single anchor element per project in the repository.

    def __init__(self):
        super().__init__()
        self._parsing_anchor = False
        self._url = None
        self._name = None
        self.mapping = {}

    def handle_starttag(self, tag, attrs_list):
        # PEP 503:
        # There may be any other HTML elements on the API pages as long as the
        # required anchor elements exist.
        attrs = dict(attrs_list)
        _check_version(tag, attrs)
        if tag != "a":
            return
        self._parsing_anchor = True
        self._url = attrs.get("href")

    def handle_endtag(self, tag):
        if tag != "a":
            return
        elif self._name and self._url:
            self.mapping[self._name] = _normalize_project_url(self._url)

        self._name = self._url = None
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self._name = data


def parse_repo_index(html):
    """Parse the HTML of a repository index page."""
    parser = _SimpleIndexHTMLParser()
    parser.feed(html)
    return parser.mapping


@attr.frozen
class ArchiveLink:

    """Data related to a link to an archive file."""

    filename: str
    url: str
    requires_python: packaging.specifiers.SpecifierSet
    hash_: Optional[Tuple[str, str]] = None
    gpg_sig: Optional[bool] = None
    yanked: Tuple[bool, str] = (False, "")
    metadata: Optional[Tuple[str, str]] = None  # No hash leads to a `("", "")` tuple.


class _ArchiveLinkHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        self.archive_links = []
        super().__init__()

    def handle_starttag(self, tag, attrs_list):
        attrs = dict(attrs_list)
        _check_version(tag, attrs)
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
        hash_ = None
        # PEP 503:
        # The URL SHOULD include a hash in the form of a URL fragment with the
        # following syntax: #<hashname>=<hashvalue> ...
        if parsed_url.fragment:
            hash_algo, hash_value = parsed_url.fragment.split("=", 1)
            hash_ = hash_algo.lower(), hash_value
        # PEP 503:
        # A repository MAY include a data-requires-python attribute on a file
        # link. This exposes the Requires-Python metadata field ...
        # In the attribute value, < and > have to be HTML encoded as &lt; and
        # &gt;, respectively.
        requires_python_data = html.unescape(attrs.get("data-requires-python", ""))
        requires_python = packaging.specifiers.SpecifierSet(requires_python_data)
        # PEP 503:
        # A repository MAY include a data-gpg-sig attribute on a file link with
        # a value of either true or false ...
        gpg_sig = attrs.get("data-gpg-sig")
        if gpg_sig:
            gpg_sig = gpg_sig == "true"
        # PEP 592:
        # Links in the simple repository MAY have a data-yanked attribute which
        # may have no value, or may have an arbitrary string as a value.
        yanked = "data-yanked" in attrs, attrs.get("data-yanked") or ""
        # PEP 658:
        # ... each anchor tag pointing to a distribution MAY have a
        # data-dist-info-metadata attribute.
        metadata = None
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

        self.archive_links.append(
            ArchiveLink(
                filename, url, requires_python, hash_, gpg_sig, yanked, metadata
            )
        )


def parse_archive_links(html: str) -> List[ArchiveLink]:
    """Parse the HTML of an archive links page."""
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    return parser.archive_links
