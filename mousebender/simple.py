"""Simple index parsing module"""

import dataclasses
import html.parser
import re

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
        elif not self._name or not self._url:
            return
        else:
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
