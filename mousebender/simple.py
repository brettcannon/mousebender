"""Parsing for PEP 503 -- Simple Repository API."""
from __future__ import annotations

import dataclasses
import html.parser
import re
from typing import Optional, Tuple


_NORMALIZE_RE = re.compile(r"[-_.]+")


def create_project_url(base_url, project_name):
    """Construct the project URL for a repository following PEP 503."""
    if not base_url.endswith("/"):
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


def parse_repo_index(index_html):
    """Parse the HTML for a repository index page."""
    parser = _SimpleIndexHTMLParser()
    parser.feed(index_html)
    return parser.mapping


# XXX Draft code for archive links parsing =====================================

# Data to store for the simple project index:
# - filename
# - url
# - hash? (algorithm, digest)
# - data-gpg-sig (bool)
# - data-requires-python (python_version escaped)


@dataclasses.dataclass
class ArchiveLink:
    filename: str
    url: str
    hash: Optional[Tuple[str, str]]
    requires_python: Optional[str]  # XXX packaging.specifiers.SpecifierSet?
    gpg_sig: Optional[bool]

    @classmethod
    def _fromfiledetails(cls, file_details):
        """
        Parses the extra 'combined fields' from file details that the data class uses
        as constructor arguments.
        """
        url = file_details["url"]
        url, _, hash_info = url.partition("#")
        hash_algo, _, hash_val = hash_info.partition("=")
        if hash_algo and hash_val:
            file_details["hash"] = hash_algo, hash_val

        return cls(**file_details)


class _ProjectFileHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self._parsing_anchor = False
        self.files = []
        self._file = {}

    def handle_starttag(self, tag, attrs_list):
        if tag != "a":
            return
        self._parsing_anchor = True
        attrs = dict(attrs_list)
        self._file["url"] = attrs.get("href")
        if gpg_sig := attrs.get("data-gpg-sig"):
            self._file["gpg_sig"] = gpg_sig == "true"
        self._file["requires_python"] = attrs.get("data-requires-python")

    def handle_endtag(self, tag):
        if tag != "a":
            return
        elif self._file.get("url") and self._file.get("filename"):
            self.files.append(self._file)

        self._file = {}
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self._file["filename"] = data


def parse_archive_links(index_html):
    # for each simple file anchor set, consisting of
    # href, cdata, and attributes, construct a ProjectFileInfo
    # and add it to the set of files contained in a version member
    # of a dict
    parser = _ProjectFileHTMLParser()
    parser.feed(index_html)
    file_info = {}
    for file_ in parser.files:
        version = extract_version(file_["filename"])
        file_info.setdefault(version, set()).add(
            ProjectFileInfo._fromfiledetails(file_)
        )
