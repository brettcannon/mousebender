"""Tests for mousebender.simple."""
import importlib.resources

import pytest

from mousebender import simple

from . import data


class TestProjectURLConstruction:

    """Tests for mousebender.simple.create_project_url()."""

    @pytest.mark.parametrize("base_url", ["/simple/", "/simple"])
    def test_url_joining(self, base_url):
        url = simple.create_project_url(base_url, "hello")
        assert url == "/simple/hello/"

    def test_project_name_lowercased(self):
        url = simple.create_project_url("/", "THEPROJECTNAME")
        assert url == "/theprojectname/"

    def test_project_name_normalized(self):
        normal_url = simple.create_project_url("/", "the_project.name.-_.-_here")
        assert normal_url == "/the-project-name-here/"

    def test_only_project_name_in_url_normalized(self):
        url = simple.create_project_url(
            "https://terribly_awesome.com/So/Simple/", "THE_project.name.-_.-_here"
        )
        assert url == "https://terribly_awesome.com/So/Simple/the-project-name-here/"


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


def test_get_num_versions_extracted():
    index_html = """<!DOCTYPE html>
    <html>
    <head>
        <title>Links for test_package</title>
    </head>
    <body>
        <h1>Links for test_package</h1>
        <a href="/packages/1/test_package-1.0.0-cp37-cp37m-win_amd64.whl#sha256=111">test_package-1.0.0-cp37-cp37m-win_amd64.whl</a><br/>
        <a href="/packages/1/test_package-1.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=222">test_package-1.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
        <a href="/packages/1/test_package-1.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=333">test_package-1.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>

        <a href="/packages/1/test_package-2.0.0-cp37-cp37m-win_amd64.whl#sha256=444">test_package-2.0.0-cp37-cp37m-win_amd64.whl</a><br/>
        <a href="/packages/1/test_package-2.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=555">test_package-2.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
        <a href="/packages/1/test_package-2.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=666">test_package-2.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>

        <a href="/packages/1/test_package-3.0.0-cp37-cp37m-win_amd64.whl#sha256=777">test_package-3.0.0-cp37-cp37m-win_amd64.whl</a><br/>
        <a href="/packages/1/test_package-3.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=888">test_package-3.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
        <a href="/packages/1/test_package-3.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=999">test_package-3.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>
    </body>
    </html>
    <!--SERIAL 6405382-->"""
    index = simple.parse_file_index(index_html)
    assert (
        len(index) == 3
    )  # 3 versions, so the index for this package should have 3 entries, one for each version.
    assert len(index["1.0.0"]) == 3
    assert len(index["2.0.0"]) == 3
    assert len(index["3.0.0"]) == 3


def test_get_package_index():
    index_html = importlib.resources.read_text(data, "simple.numpy.html")
    index = simple.parse_file_index(index_html)
    assert len(index) == 75
    assert len(index["1.18.0"]) == len(index["1.18.1"]) == 20
