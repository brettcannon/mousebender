"""Parsing for PEP 503 -- Simple Repository API."""
import html
import html.parser
import re
import urllib.parse
from typing import Optional, Tuple

import attr
import packaging.specifiers

_NORMALIZE_RE = re.compile(r"[-_.]+")

PYPI_INDEX = "https://pypi.org/simple/"


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

    def handle_starttag(self, tag, attrs):
        # PEP 503:
        # There may be any other HTML elements on the API pages as long as the
        # required anchor elements exist.
        if tag != "a":
            return
        self._parsing_anchor = True
        self._url = dict(attrs).get("href")

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


@attr.s(frozen=True)
class ArchiveLink:

    """Data related to a link to an archive file."""

    filename: str = attr.ib()
    url: str = attr.ib()
    requires_python: packaging.specifiers.SpecifierSet = attr.ib()
    hash_: Optional[Tuple[str, str]] = attr.ib(default=None)
    gpg_sig: Optional[bool] = attr.ib(default=None)
    yanked: Tuple[bool, str] = attr.ib(default=(False, ""))


class _ArchiveLinkHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        self.archive_links = []
        super().__init__()

    def handle_starttag(self, tag, attrs_list):
        if tag != "a":
            return
        attrs = dict(attrs_list)
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

        self.archive_links.append(
            ArchiveLink(filename, url, requires_python, hash_, gpg_sig, yanked)
        )


def parse_archive_links(html):
    """Parse the HTML of an archive links page."""
    parser = _ArchiveLinkHTMLParser()
    parser.feed(html)
    return parser.archive_links
