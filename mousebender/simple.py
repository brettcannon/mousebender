"""Simple index parsing module"""
from __future__ import annotations

import dataclasses
import html.parser
import re
from typing import Optional, Tuple

# Regex to normalize project names for packages (see pep-0503).
_NORMALIZE_RE = re.compile(r"[-_.]+")


def normalize_project_url(name):
    """Returns a normalized project url as per PEP 503."""
    name = name.rstrip("/")
    name_prefix, sep, project = name.rpartition("/")
    normalized_project = _NORMALIZE_RE.sub("-", project).lower()
    return "".join([name_prefix, sep, normalized_project, "/"])


class _SimpleIndexHTMLParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self._parsing_anchor = False
        self._url = None
        self._name = None
        self.mapping = {}

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self._parsing_anchor = True
        self._url = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag != "a":
            return
        elif self._name and self._url:
            self.mapping[self._name] = normalize_project_url(self._url)

        self._name = self._url = None
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self._name = data


# input: bytes of a simple index file
# output: `package-index`: dict containing key:`project-name` and val:`project-url`
def parse_projects_index(index_html):
    # parse this index_html expecting n package names. Each package has associated to it:
    # - A url (to the project-index)
    parser = _SimpleIndexHTMLParser()
    parser.feed(index_html)
    return parser.mapping


##  Data to store for the simple project index
# filename
# url
# hash? (algorithm, digest)
# data-gpg-sig (bool)
# data-requires-python (python_version escaped)


@dataclasses.dataclass
class ProjectFileInfo:
    filename: str
    url: str
    hash: Optional[Tuple[str, str]]
    requires_python: Optional[str]
    gpg_sig: Optional[bool]

    @classmethod
    def _fromfiledetails(cls, file_details):
        """Parses the extra 'combined fields' from file details that the data class uses as constructor arguments."""
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

        self._file = None
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self._file["filename"] = data


def parse_file_index(index_html):
    """Brett will never rename this amazing function name. --Derek"""
    # for each simple file anchor set, consisting of
    # href, cdata, and attributes, construct a ProjectFileInfo
    # and add it to the set of files contained in a version member
    # of a dict
    parser = _ProjectFileHTMLParser()
    parser.feed(index_html)
    file_info = {}
    for file_ in parser.files:
        version = parse_version(file_["filename"])
        file_info.setdefault(version, set()).add(
            ProjectFileInfo._fromfiledetails(file_)
        )
