"""Tests for mousebender.simple."""
import importlib.resources

from mousebender import simple

from . import data


def test_simple_index_basic():
    index_html = importlib.resources.read_text(data, "simple.index.html")
    index = simple.parse_projects_index(index_html)
    assert "numpy" in index
    assert index["numpy"] == "/simple/numpy/"
    assert len(index) == 212_862


def test_simple_index_no_cdata():
    index_html = (
        "<html><head></head><body><a href='https://no.url/here'></a></body></html>"
    )
    index = simple.parse_projects_index(index_html)
    assert not index


def test_simple_index_no_href():
    index_html = "<html><head></head><body><a>my-cdata-package</a></body></html>"
    index = simple.parse_projects_index(index_html)
    assert not index


def test_normalize_package_project_url_lowercase():
    project_url = "/THEPROJECTNAME/"
    normal_url = simple.normalize_project_url(project_url)
    assert normal_url == project_url.lower()


def test_normalize_package_project_url_trailing_slash():
    project_url = "/the-project-name"
    normal_url = simple.normalize_project_url(project_url)
    assert normal_url == f"{project_url}/"


def test_normalize_package_project_url_substitutions():
    project_url = "/the_project.name.-_.-_here/"
    expected_url = "/the-project-name-here/"
    normal_url = simple.normalize_project_url(project_url)
    assert normal_url == expected_url


def test_normalize_package_project_url_only():
    project_url = "https://terribly_awesome.com/So/Simple/THE_project.name.-_.-_here"
    expected_url = "https://terribly_awesome.com/So/Simple/the-project-name-here/"
    normal_url = simple.normalize_project_url(project_url)
    assert normal_url == expected_url


def test_ensure_normalization_called():
    index_html = """
        <html>
            <body>
                <a href="/project/PACKAGE-NAME">package-name</a>
            </body>
        </html>
    """
    index = simple.parse_projects_index(index_html)
    assert index["package-name"] == "/project/package-name/"
