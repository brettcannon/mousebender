"""Tests for mousebender.simple."""
import importlib.resources

import pytest

from mousebender import simple

from .data import simple as simple_data
from .data.simple import numpy as numpy_data


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
        index_html = importlib.resources.read_text(simple_data, "index.html")
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
        index = simple.parse_archive_links(index_html)
        assert len(index) == 9

    def test_get_num_files_per_version_extracted(self):
        """Each version contains 3 files."""

        index = simple.parse_archive_links(self.dummy_data)
        ver_1 = [al for al in index if "1.0.0" in al.filename]
        ver_2 = [al for al in index if "2.0.0" in al.filename]
        ver_3 = [al for al in index if "3.0.0" in al.filename]

        assert len(ver_1) == 3
        assert len(ver_2) == 3
        assert len(ver_3) == 3

    def test_get_expected_file(self):
        """Ensure the file name is present in the list."""
        index = simple.parse_archive_links(self.dummy_data)
        expected_file = "test_package-1.0.0-cp37-cp37m-win_amd64.whl"
        found_file = [al for al in index if al.filename == expected_file]

        assert len(found_file) == 1

    def test_signature_values_extracted(self):
        """Each package has a hash that coincides with the OS and version of the file."""
        index = simple.parse_archive_links(self.dummy_data)

        for al in index:
            assert al.hash[1] in [
                "windows100",
                "windows200",
                "windows300",
                "linux100",
                "linux200",
                "linux300",
                "mac100",
                "mac200",
                "mac300",
            ]

    def test_python_version_required(self):
        """All package files require python >=3.7, >=3.8, or >=3.8.1."""
        index = simple.parse_archive_links(self.dummy_data)

        for pkg_file in index:
            assert pkg_file.requires_python in [">=3.7", ">=3.8", ">=3.8.1"]

    def test_gpg_sig_extracted(self):
        """Determine if a gpg-sig is available for the file."""
        index = simple.parse_archive_links(self.dummy_data)

        for pkg in index:
            if "1.0.0" in pkg.filename:
                # Version 1.0.0 files don't have it specified, should be None
                expected_gpg = None
            elif "2.0.0" in pkg.filename:
                # Version 2.0.0 files have data-gpg-sig set to False
                expected_gpg = False
            elif "3.0.0" in pkg.filename:
                # Version 3.0.0 files have data-gpg-sig set to True
                expected_gpg = True
            else:
                assert False  # Did we add another version to the dummy data?

            assert pkg.gpg_sig is expected_gpg

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
        index_html = importlib.resources.read_text(numpy_data, "index.html")
        index = simple.parse_archive_links(index_html)
        assert len(index) == 1402
        assert len([al for al in index if "1.18.0" in al.filename]) == 42
        assert len([al for al in index if "1.18.1" in al.filename]) == 21
