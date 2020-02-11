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


class TestPackageIndexParsing:

    dummy_data = """<!DOCTYPE html>
        <html>
        <head>
            <title>Links for test_package</title>
        </head>
        <body>
            <h1>Links for test_package</h1>
            <a href="/packages/1/test_package-1.0.0-cp37-cp37m-win_amd64.whl#sha256=windows100" data-requires-python="&gt;=3.7">test_package-1.0.0-cp37-cp37m-win_amd64.whl</a><br/>
            <a href="/packages/1/test_package-1.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=linux100" data-requires-python="&gt;=3.7">test_package-1.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
            <a href="/packages/1/test_package-1.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=mac100" data-requires-python="&gt;=3.7">test_package-1.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>

            <a href="/packages/1/test_package-2.0.0-cp37-cp37m-win_amd64.whl#sha256=windows200" data-requires-python="&gt;=3.8" data-gpg-sig="false">test_package-2.0.0-cp37-cp37m-win_amd64.whl</a><br/>
            <a href="/packages/1/test_package-2.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=linux200" data-requires-python="&gt;=3.8" data-gpg-sig="false">test_package-2.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
            <a href="/packages/1/test_package-2.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=mac200" data-requires-python="&gt;=3.8" data-gpg-sig="false">test_package-2.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>

            <a href="/packages/1/test_package-3.0.0-cp37-cp37m-win_amd64.whl#sha256=windows300" data-requires-python="&gt;=3.8.1" data-gpg-sig="true">test_package-3.0.0-cp37-cp37m-win_amd64.whl</a><br/>
            <a href="/packages/1/test_package-3.0.0-cp37-cp37m-manylinux1_x86_64.whl#sha256=linux300" data-requires-python="&gt;=3.8.1" data-gpg-sig="true">test_package-3.0.0-cp37-cp37m-manylinux1_x86_64.whl</a><br/>
            <a href="/packages/1/test_package-3.0.0-cp37-cp37m-macosx_10_9_x86_64.whl#sha256=mac300" data-requires-python="&gt;=3.8.1" data-gpg-sig="true">test_package-3.0.0-cp37-cp37m-macosx_10_9_x86_64.whl</a><br/>
        </body>
        </html>
        <!--SERIAL 6405382-->"""

    def test_get_num_versions_extracted(self):
        """3 versions in dummy data, so the index for this package should have 3 entries, one for each version."""
        index_html = self.dummy_data
        index = simple.parse_file_index(index_html)
        assert len(index) == 3

    def test_get_num_files_per_version_extracted(self):
        """Each version contains 3 files."""

        index = simple.parse_file_index(self.dummy_data)
        assert len(index["1.0.0"]) == 3
        assert len(index["2.0.0"]) == 3
        assert len(index["3.0.0"]) == 3

    def test_signature_values_extracted(self):
        """Each package has a hash that coincides with the OS and version of the file."""
        index = simple.parse_file_index(self.dummy_data)

        for version in index:
            if version == "1.0.0":
                hash_list = ["windows100", "linux100", "mac100"]
            elif version == "2.0.0":
                hash_list = ["windows200", "linux200", "mac200"]
            elif version == "3.0.0":
                hash_list = ["windows300", "linux300", "mac300"]
            else:
                assert False  # need a new version?

            for pkg_file in index[version]:
                assert pkg_file.hash[1] in hash_list

    def test_python_version_required(self):
        """All package files require python >=3.7, >=3.8, or >=3.8.1."""
        index = simple.parse_file_index(self.dummy_data)

        for version in index:
            for pkg_file in index[version]:
                assert pkg_file.requires_python in [">=3.7", ">=3.8", ">=3.8.1"]

    def test_gpg_sig_extracted(self):
        """Determine if a gpg-sig is available for the file."""
        index = simple.parse_file_index(self.dummy_data)

        for version in index:
            if version == "1.0.0":
                # Version 1.0.0 files don't have it specified, should be None
                expected_gpg = None
            elif version == "2.0.0":
                # Version 2.0.0 files have data-gpg-sig set to False
                expected_gpg = False
            elif version == "3.0.0":
                # Version 3.0.0 files have data-gpg-sig set to True
                expected_gpg = True
            else:
                assert False  # Did we add another version to the dummy data?

            for pkg_file in index[version]:
                assert pkg_file.gpg_sig is expected_gpg

    def test_get_package_index_real_data(self):
        index_html = importlib.resources.read_text(data, "simple.numpy.html")
        index = simple.parse_file_index(index_html)
        assert len(index) == 75
        assert len(index["1.18.0"]) == len(index["1.18.1"]) == 20
