"""Parsing for PEP 503 -- Simple Repository API."""
import html
import html.parser
import urllib.parse
import warnings

from typing import Any, Dict, List, Optional, Tuple

import attr
import packaging.specifiers
import packaging.utils


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


def parse_repo_index(html: str) -> Dict[str, str]:
    """Parse the HTML of a repository index page."""
    parser = _SimpleIndexHTMLParser()
    parser.feed(html)
    return parser.mapping


@attr.frozen(kw_only=True)
class ArchiveLink:

    """Data related to a link to an archive file."""

    filename: str
    url: str
    requires_python: packaging.specifiers.SpecifierSet = (
        packaging.specifiers.SpecifierSet("")
    )
    hash_: Optional[Tuple[str, str]] = None
    gpg_sig: Optional[bool] = None
    yanked: Optional[str] = None  # Is `""` if no message provided.
    metadata: Optional[Tuple[str, str]] = None  # No hash leads to a `("", "")` tuple.

    def __str__(self) -> str:
        attrs = []
        if self.requires_python:
            requires_str = str(self.requires_python)
            escaped_requires = html.escape(requires_str)
            attrs.append(f'data-requires-python="{escaped_requires}"')
        if self.gpg_sig is not None:
            attrs.append(f"data-gpg-sig={str(self.gpg_sig).lower()}")
        if self.yanked is not None:
            if self.yanked:
                attrs.append(f'data-yanked="{self.yanked}"')
            else:
                attrs.append("data-yanked")
        if self.metadata:
            hash_algorithm, hash_value = self.metadata
            if hash_algorithm:
                attrs.append(f'data-dist-info-metadata="{hash_algorithm}={hash_value}"')
            else:
                attrs.append("data-dist-info-metadata")

        url = self.url
        if self.hash_:
            hash_algorithm, hash_value = self.hash_
            url += f"#{hash_algorithm}={hash_value}"

        return f'<a href="{url}" {" ".join(attrs)}>{self.filename}</a>'


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
        args: Dict[str, Any] = {"filename": filename, "url": url}
        # PEP 503:
        # The URL SHOULD include a hash in the form of a URL fragment with the
        # following syntax: #<hashname>=<hashvalue> ...
        if parsed_url.fragment:
            hash_algo, hash_value = parsed_url.fragment.split("=", 1)
            args["hash_"] = hash_algo.lower(), hash_value
        # PEP 503:
        # A repository MAY include a data-requires-python attribute on a file
        # link. This exposes the Requires-Python metadata field ...
        # In the attribute value, < and > have to be HTML encoded as &lt; and
        # &gt;, respectively.
        if "data-requires-python" in attrs:
            requires_python_data = html.unescape(attrs["data-requires-python"])
            args["requires_python"] = packaging.specifiers.SpecifierSet(
                requires_python_data
            )
        # PEP 503:
        # A repository MAY include a data-gpg-sig attribute on a file link with
        # a value of either true or false ...
        if "data-gpg-sig" in attrs:
            args["gpg_sig"] = attrs["data-gpg-sig"] == "true"
        # PEP 592:
        # Links in the simple repository MAY have a data-yanked attribute which
        # may have no value, or may have an arbitrary string as a value.
        if "data-yanked" in attrs:
            args["yanked"] = attrs.get("data-yanked") or ""
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

        self.archive_links.append(ArchiveLink(**args))


def parse_archive_links(html: str) -> List[ArchiveLink]:
    """Parse the HTML of an archive links page."""
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    return parser.archive_links
