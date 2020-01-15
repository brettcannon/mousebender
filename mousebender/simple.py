"""Simple index parsing module"""

import dataclasses
import html.parser


class SimpleIndexHTMLParser(html.parser.HTMLParser):

    def __init__(self):
        super().__init__()
        self._parsing_anchor = False
        self._uri = None
        self._name = None
        self.mapping = {}

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self._parsing_anchor = True
        self._uri = dict(attrs)["href"]

    def handle_endtag(self, tag):
        if tag != "a":
            return
        self.mapping[self._name] = self._uri
        self._name = self._uri = None
        self._parsing_anchor = False

    def handle_data(self, data):
        if self._parsing_anchor:
            self._name = data

# input: bytes of a simple index file
# output: `package-index`: dict containing key:`project-name` and val:`project-uri`
def parse_package_index(index_html):
    # parse this index_html expecting n package names. Each package has associated to it:
    # - A url (to the project-index)
    
    parser = SimpleIndexHTMLParser()
    parser.feed(index_html)
    return parser.mapping
