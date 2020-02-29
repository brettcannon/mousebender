"""Tests for mousebender.simple."""
import importlib.resources

from mousebender import simple

from . import data


class TestProjectURLNormalization:

    """Tests for mousebender.simple.normalize_project_url()."""

    def test_project_url_lowercased(self):
        project_url = "/THEPROJECTNAME/"
        normal_url = simple.normalize_project_url(project_url)
        assert normal_url == project_url.lower()

    def test_project_url_gets_trailing_slash(self):
        project_url = "/the-project-name"
        normal_url = simple.normalize_project_url(project_url)
        assert normal_url == f"{project_url}/"

    def test_project_url_name_normalized_by_substitution(self):
        project_url = "/the_project.name.-_.-_here/"
        expected_url = "/the-project-name-here/"
        normal_url = simple.normalize_project_url(project_url)
        assert normal_url == expected_url

    def test_only_project_name_in_url_normalized(self):
        project_url = (
            "https://terribly_awesome.com/So/Simple/THE_project.name.-_.-_here"
        )
        expected_url = "https://terribly_awesome.com/So/Simple/the-project-name-here/"
        normal_url = simple.normalize_project_url(project_url)
        assert normal_url == expected_url


class TestRepoIndexParsing:

    """Tests for mousebender.simple.parse_repo_index()."""

    def test_baseline(self):
        index_html = importlib.resources.read_text(data, "simple.index.html")
        index = simple.parse_repo_index(index_html)
        assert "numpy" in index
        assert index["numpy"] == "/simple/numpy/"
        assert len(index) == 212_862

    def test_no_cdata(self):
        index_html = (
            "<html><head></head><body><a href='https://no.url/here'></a></body></html>"
        )
        index = simple.parse_repo_index(index_html)
        assert not index

    def test_no_href(self):
        index_html = "<html><head></head><body><a>my-cdata-package</a></body></html>"
        index = simple.parse_repo_index(index_html)
        assert not index

    def test_project_url_normalization_complete(self):
        index_html = """
            <html>
                <body>
                    <a href="/project/PACKAGE-NAME">package-name</a>
                </body>
            </html>
        """
        index = simple.parse_repo_index(index_html)
        assert index["package-name"] == "/project/package-name/"

    def test_project_name_not_normalized(self):
        index_html = """
            <html>
                <body>
                    <a href="/project/package-name">PACKAGE-NAME</a>
                </body>
            </html>
        """
        index = simple.parse_repo_index(index_html)
        assert index["PACKAGE-NAME"] == "/project/package-name/"
