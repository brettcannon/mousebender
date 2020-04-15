"""Tests for mousebender.__main__."""

import http
import importlib.resources
import packaging.tags
import pytest
from typing import Dict, List
import urllib

from mousebender import __main__ as e2e
from mousebender import simple

from .data import simple as simple_data


@pytest.fixture()
def archive_links() -> List[simple.ArchiveLink]:
    index_html = importlib.resources.read_text(simple_data, "archive_links.numpy.html")
    return simple.parse_archive_links(index_html)


@pytest.fixture()
def wheels_links(archive_links) -> List[simple.ArchiveLink]:
    return [a for a in archive_links if a.filename.endswith(".whl")]


def test_filter_to_wheels_gets_none():
    assert list(e2e.filter_to_wheels([])) == []


def test_filter_to_wheels_gets_data(archive_links):
    assert len(list(e2e.filter_to_wheels(archive_links))) == 1266


def test_filter_wheels_to_version_gets_none():
    assert list(e2e.filter_wheels_to_version([], version="3.8")) == []


def test_filter_wheels_to_nonpresent_version_gets_none(wheels_links):
    assert len(list(e2e.filter_wheels_to_version(wheels_links, "99.99.99"))) == 0


def test_filter_wheels_to_version_gets_some(wheels_links):
    assert len(list(e2e.filter_wheels_to_version(wheels_links, "1.18.0"))) == 20


def test_filter_wheels_to_non_version_gets_none(wheels_links):
    assert len(list(e2e.filter_wheels_to_version(wheels_links, None))) == 0


def test_find_package_nonpresent_version(wheels_links):
    assert e2e.find_package(wheels_links, "123.456.789") is None


def test_find_package_no_wheels_available(archive_links):
    no_wheels_links = [
        sdist for sdist in archive_links if not sdist.filename.endswith(".whl")
    ]
    assert e2e.find_package(no_wheels_links, "1.18.0") is None


def test_find_package_no_compatible_tags(wheels_links, monkeypatch):
    def mock_sys_tags():
        return "no_tag_here"

    monkeypatch.setattr(packaging.tags, "sys_tags", mock_sys_tags)
    assert e2e.find_package(wheels_links, "1.18.0") is None


def test_find_package_happy_path_mocked(wheels_links, monkeypatch):
    """Test that the happy path to finding a package is tested cross-platform."""

    # tags are not necessarily cross-platform, remove this uncertainty from the test
    mock_expected_tag = packaging.tags.parse_tag("py30-none-any")

    def mock_sys_tags():
        return [mock_expected_tag]

    # ensure there is a 'valid-ish' package available with our mocked up tag
    mock_archive_link = simple.ArchiveLink(
        filename="numpy-1.18.0-py30-none-any.whl",
        url="https://numpy-1.18.0-py30-none-any.whl",
        requires_python=packaging.specifiers.SpecifierSet(">=3.0"),
        hash_=(
            "sha256",
            "56710a756c5009af9f35b91a22790701420406d9ac24cf6b652b0e22cfbbb7ff",
        ),
        gpg_sig=False,
    )

    # remove any uncertainty as to which package we will get back
    def mock_filter_wheels_to_version(
        relevant_links, package_ver
    ) -> Dict[packaging.tags.Tag, simple.ArchiveLink]:
        return {mock_expected_tag: mock_archive_link}

    monkeypatch.setattr(packaging.tags, "sys_tags", mock_sys_tags)
    monkeypatch.setattr(e2e, "filter_wheels_to_version", mock_filter_wheels_to_version)

    package = e2e.find_package(wheels_links, "1.18.0")

    assert package is not None
    assert package.filename == "numpy-1.18.0-py30-none-any.whl"
