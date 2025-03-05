"""Tests for mousebender.simple."""

import json
import warnings
from typing import Dict, Union

# Python < 3.9
import importlib_resources
import pytest

from mousebender import simple

from .data import simple as simple_data

INDEX_v1_EXAMPLE = """{
  "meta": {
    "api-version": "1.0"
  },
  "projects": [
    {"name": "Frob"},
    {"name": "spamspamspam"}
  ]
}"""

INDEX_HTML_EXAMPLE = """<!DOCTYPE html>
<html>
  <body>
    <a href="/frob/">Frob</a>
    <a href="/spamspamspam/">spamspamspam</a>
  </body>
</html>"""

DETAILS_V1_EXAMPLE = """{
  "meta": {
    "api-version": "1.0"
  },
  "name": "holygrail",
  "files": [
    {
      "filename": "holygrail-1.0.tar.gz",
      "url": "https://example.com/files/holygrail-1.0.tar.gz",
      "hashes": {}
    },
    {
      "filename": "holygrail-1.0-py3-none-any.whl",
      "url": "https://example.com/files/holygrail-1.0-py3-none-any.whl",
      "hashes": {}
    }
  ]
}"""


DETAILS_HTML_EXAMPLE = """<!DOCTYPE html>
<html>
  <body>
    <a href="https://example.com/files/holygrail-1.0.tar.gz">holygrail-1.0.tar.gz</a>
    <a href="https://example.com/files/holygrail-1.0-py3-none-any.whl">holygrail-1.0-py3-none-any.whl</a>
  </body>
</html>"""


class TestProjectURLConstruction:
    @pytest.mark.parametrize("base_url", ["/simple/", "/simple"])
    def test_url_joining(self, base_url: str):
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

    def test_no_base_url(self):
        url = simple.create_project_url("", "django-node")
        assert url == "django-node/"


class TestRepoIndexParsing:
    @pytest.mark.parametrize(
        "name,count,expected_item",
        [
            ("pypi", 212_862, "numpy"),
            ("piwheels", 263_872, "django-node"),
        ],
    )
    def test_full_parse(self, name: str, count: int, expected_item: str):
        index_file = importlib_resources.files(simple_data) / f"index.{name}.html"
        index_html = index_file.read_text(encoding="utf-8")
        index = simple.from_project_index_html(index_html)
        assert index["meta"] == {"api-version": "1.0"}
        assert len(index["projects"]) == count
        assert any(project["name"] == expected_item for project in index["projects"])

    def test_no_cdata(self):
        index_html = (
            "<html><head></head><body><a href='https://no.url/here'></a></body></html>"
        )
        index = simple.from_project_index_html(index_html)
        assert not index["projects"]

    def test_project_name_not_normalized(self):
        index_html = """
            <html>
                <body>
                    <a href="/project/package-name">PACKAGE-NAME</a>
                </body>
            </html>
        """
        index = simple.from_project_index_html(index_html)
        assert len(index["projects"]) == 1
        assert index["projects"][0]["name"] == "PACKAGE-NAME"


class TestProjectDetailsParsing:
    @pytest.mark.parametrize(
        "module_name,count,expected_file_details",
        [
            (
                "numpy",
                1402,
                {
                    "filename": "numpy-1.13.0rc1-cp36-none-win_amd64.whl",
                    "url": "https://files.pythonhosted.org/packages/5c/2e/5c0eee0635035a7e0646734e2b9388e17a97f6f2087e15141a218b6f2b6d/numpy-1.13.0rc1-cp36-none-win_amd64.whl",
                    "requires-python": ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*",
                    "hashes": {
                        "sha256": "8e8e1ccf025c8b6a821f75086a364a68d9e1877519a35bf8facec9e5120836f4"
                    },
                },
            ),
            (
                "pulpcore-client",
                370,
                {
                    "filename": "pulpcore_client-3.1.0.dev1578940535-py3-none-any.whl",
                    "url": "https://files.pythonhosted.org/packages/ca/7e/e14e41dc4bc60208f597f346d57755636e882be7509179c4e7c11f2c60a9/pulpcore_client-3.1.0.dev1578940535-py3-none-any.whl",
                    "hashes": {
                        "sha256": "83a3759d7b6af33083b0d4893d53615fc045cbad9adde68a8df02e25b1862bc6",
                    },
                },
            ),
            (
                "pytorch",
                522,
                {
                    "filename": "torchvision-0.5.0+cu100-cp36-cp36m-linux_x86_64.whl",
                    "url": "cu100/torchvision-0.5.0%2Bcu100-cp36-cp36m-linux_x86_64.whl",
                    "hashes": {},
                },
            ),
            (
                "aicoe-tensorflow",
                15,
                {
                    "filename": "tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl",
                    "url": "tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl",
                    "hashes": {},
                },
            ),
            (
                "numpy-piwheels",
                316,
                {
                    "filename": "numpy-1.10.4-cp35-cp35m-linux_armv7l.whl",
                    "url": "numpy-1.10.4-cp35-cp35m-linux_armv7l.whl",
                    "hashes": {
                        "sha256": "5768279588a4766adb0211bbaa0f5857be38483c5aafe5d1caecbcd32749966e",
                    },
                },
            ),
        ],
    )
    def test_full_parse(
        self,
        module_name: str,
        count: int,
        expected_file_details: simple.ProjectFileDetails_1_0,
    ):
        html_file = (
            importlib_resources.files(simple_data) / f"archive_links.{module_name}.html"
        )
        html = html_file.read_text(encoding="utf-8")
        project_details = simple.from_project_details_html(html, module_name)
        assert len(project_details) == 3
        assert project_details["name"] == module_name
        assert project_details["meta"] == {"api-version": "1.0"}
        assert len(project_details["files"]) == count
        assert expected_file_details in project_details["files"]

    @pytest.mark.parametrize(
        "html,expected_filename",
        [
            (
                '<a href="https://files.pythonhosted.org/packages/92/e2/7d9c6894511337b012735c0c149a7b4e49db0b934798b3ae05a3b46f31f0/numpy-1.12.1-cp35-none-win_amd64.whl#sha256=818d5a1d5752d09929ce1ba1735366d5acc769a1839386dc91f3ac30cf9faf19">numpy-1.12.1-cp35-none-win_amd64.whl</a><br/>',
                "numpy-1.12.1-cp35-none-win_amd64.whl",
            ),
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                "torch-1.2.0+cpu-cp35-cp35m-win_amd64.whl",
            ),
        ],
    )
    def test_filename(self, html: str, expected_filename: str):
        project_details = simple.from_project_details_html(html, "honey")
        assert len(project_details["files"]) == 1
        assert project_details["files"][0]["filename"] == expected_filename

    @pytest.mark.parametrize(
        "html,expected_url",
        [
            (
                '<a href="https://files.pythonhosted.org/packages/92/e2/7d9c6894511337b012735c0c149a7b4e49db0b934798b3ae05a3b46f31f0/numpy-1.12.1-cp35-none-win_amd64.whl#sha256=818d5a1d5752d09929ce1ba1735366d5acc769a1839386dc91f3ac30cf9faf19">numpy-1.12.1-cp35-none-win_amd64.whl</a><br/>',
                "https://files.pythonhosted.org/packages/92/e2/7d9c6894511337b012735c0c149a7b4e49db0b934798b3ae05a3b46f31f0/numpy-1.12.1-cp35-none-win_amd64.whl",
            ),
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                "cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl",
            ),
        ],
    )
    def test_url(self, html: str, expected_url: str):
        project_details = simple.from_project_details_html(html, "cash")
        assert len(project_details["files"]) == 1
        assert project_details["files"][0]["url"] == expected_url

    def test_no_href(self):
        html = "<a>numpy-1.12.1-cp35-none-win_amd64.whl</a><br/>"
        project_details = simple.from_project_details_html(html, "test_no_href")
        assert not len(project_details["files"])

    @pytest.mark.parametrize(
        "html,expected",
        [
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                None,
            ),
            (
                '<a href="https://files.pythonhosted.org/packages/4e/d9/d7ec4b9508e6a89f80de3e18fe3629c3c089355bec453b55e271c53dd23f/numpy-1.13.0-cp34-none-win32.whl#sha256=560ca5248c2a8fd96ac75a05811eca0ce08dfeea2ee128c87c9c7261af366288" data-requires-python="&gt;=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*">numpy-1.13.0-cp34-none-win32.whl</a><br/>',
                ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*",
            ),
        ],
    )
    def test_requires_python(self, html: str, expected: Union[str, None]):
        project_details = simple.from_project_details_html(html, "Dave")
        assert len(project_details["files"]) == 1
        if expected is None:
            assert "requires-python" not in project_details["files"][0]
        else:
            assert expected == project_details["files"][0]["requires-python"]

    @pytest.mark.parametrize(
        "html,expected_hashes",
        [
            (
                '<a href="https://files.pythonhosted.org/packages/92/e2/7d9c6894511337b012735c0c149a7b4e49db0b934798b3ae05a3b46f31f0/numpy-1.12.1-cp35-none-win_amd64.whl#sha256=818d5a1d5752d09929ce1ba1735366d5acc769a1839386dc91f3ac30cf9faf19">numpy-1.12.1-cp35-none-win_amd64.whl</a><br/>',
                {
                    "sha256": "818d5a1d5752d09929ce1ba1735366d5acc769a1839386dc91f3ac30cf9faf19"
                },
            ),
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                {},
            ),
        ],
    )
    def test_hashes(self, html: str, expected_hashes: Dict[str, str]):
        project_details = simple.from_project_details_html(html, "Brett")
        assert len(project_details["files"]) == 1
        assert project_details["files"][0]["hashes"] == expected_hashes

    @pytest.mark.parametrize(
        "html,expected_gpg_sig",
        [
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                None,
            ),
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl" data-gpg-sig="true">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                True,
            ),
            (
                '<a href="cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl" data-gpg-sig="false">cpu/torch-1.2.0%2Bcpu-cp35-cp35m-win_amd64.whl</a><br>',
                False,
            ),
        ],
    )
    def test_gpg_sig(self, html: str, expected_gpg_sig: Union[bool, None]):
        details = simple.from_project_details_html(html, "test_gpg_sig")
        assert len(details["files"]) == 1
        assert details["files"][0].get("gpg-sig") == expected_gpg_sig

    @pytest.mark.parametrize(
        "html,expected",
        [
            pytest.param(
                '<a href="spam-1.2.3-py3.none.any.whl" data-yanked>spam-1.2.3-py3.none.any.whl</a>',
                True,
                id="sole `data-yanked`",
            ),
            pytest.param(
                '<a href="spam-1.2.3-py3.none.any.whl" data-yanked="oops!">spam-1.2.3-py3.none.any.whl</a>',
                "oops!",
                id="`data-yanked` w/ string",
            ),
            # PEP 592 suggests any string value means the release is yanked,
            # but PEP 691 says the truthiness of the value determines whether something
            # was yanked. That would suggest the empty string should be replaced with
            # True according to PEP 691.
            pytest.param(
                '<a href="spam-1.2.3-py3.none.any.whl" data-yanked="">spam-1.2.3-py3.none.any.whl</a>',
                True,
                id="`data-yanked w/ ''",
            ),
            pytest.param(
                '<a href="spam-1.2.3-py3.none.any.whl">spam-1.2.3-py3.none.any.whl</a>',
                None,
                id="no `data-yanked`",
            ),
        ],
    )
    def test_yanked(self, html: str, expected: Union[bool, None]):
        details = simple.from_project_details_html(html, "test_yanked")
        assert len(details["files"]) == 1
        assert details["files"][0].get("yanked") == expected


class TestPEP629Versioning:
    @pytest.mark.parametrize(["version"], [("",), ("1.0",), ("1.1",)])
    def test_supported_versions(self, version):
        if not version:
            meta_tag = ""
        else:
            meta_tag = f'<meta name="pypi:repository-version" content="{version}">'

        index_html = (
            f"<!DOCTYPE html><html><head>{meta_tag}</head>"
            '<body><a href="/spamspamspam/">spamspamspam</a></body></html>'
        )

        assert simple.from_project_index_html(index_html)

        details_html = (
            f"<!DOCTYPE html><html><head>{meta_tag}</head>"
            '<body><a href="mousebender-2022.1.0-py3-none-any.whl">'
            "mousebender-2022.1.0-py3-none-any.whl/a></body></html>"
        )

        assert simple.from_project_details_html(details_html, "mousebender")

    @pytest.mark.parametrize(["version"], [("0.1",), ("2.0",), ("2.1",), ("10.0",)])
    def test_unsupported_major_versions(self, version):
        meta_tag = f'<meta name="pypi:repository-version" content="{version}">'
        index_html = (
            f"<!DOCTYPE html><html><head>{meta_tag}</head>"
            '<body><a href="/spamspamspam/">spamspamspam</a></body></html>'
        )

        with pytest.raises(simple.UnsupportedAPIVersion):
            simple.from_project_index_html(index_html)

    @pytest.mark.parametrize(["minor_version"], [("2",), ("10",)])
    def test_unsupported_minor_version(self, minor_version):
        meta_tag = f'<meta name="pypi:repository-version" content="1.{minor_version}">'
        details_html = (
            f"<!DOCTYPE html><html><head>{meta_tag}</head>"
            '<body><a href="mousebender-2022.1.0-py3-none-any.whl">'
            "mousebender-2022.1.0-py3-none-any.whl/a></body></html>"
        )

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(simple.APIVersionWarning):
                simple.from_project_details_html(details_html, "mousebender")


class TestPEP658Metadata:
    def test_default(self):
        html = '<a href="spam-1.2.3-py3.none.any.whl">spam-1.2.3-py3.none.any.whl</a>'
        details = simple.from_project_details_html(html, "test_default")
        assert len(details["files"]) == 1
        # Need to make sure it isn't an empty dict.
        assert "core-metadata" not in details["files"][0]
        assert "dist-info-metadata" not in details["files"][0]

    @pytest.mark.parametrize("field", ["data-core-metadata", "data-dist-info-metadata"])
    @pytest.mark.parametrize("value", ["", "=true"])
    def test_attribute_only(self, field: str, value: str):
        html = f'<a href="spam-1.2.3-py3.none.any.whl" {field}{value} >spam-1.2.3-py3.none.any.whl</a>'
        details = simple.from_project_details_html(html, "test_default")
        assert len(details["files"]) == 1
        assert details["files"][0]["core-metadata"] is True
        assert details["files"][0]["dist-info-metadata"] is True

    @pytest.mark.parametrize("field", ["data-core-metadata", "data-dist-info-metadata"])
    @pytest.mark.parametrize("value", ['"sha256=abcdef"', '"SHA256=abcdef"'])
    def test_hash(self, field: str, value: str):
        html = f'<a href="spam-1.2.3-py3.none.any.whl" {field}={value}>spam-1.2.3-py3.none.any.whl</a>'
        details = simple.from_project_details_html(html, "test_default")
        assert len(details["files"]) == 1
        assert details["files"][0]["core-metadata"] == {"sha256": "abcdef"}
        assert details["files"][0]["dist-info-metadata"] == {"sha256": "abcdef"}


class TestParseProjectIndex:
    def test_json(self):
        index = simple.parse_project_index(INDEX_v1_EXAMPLE, simple.ACCEPT_JSON_V1)
        assert index == json.loads(INDEX_v1_EXAMPLE)

    @pytest.mark.parametrize(
        ["content_type"],
        [(content_type,) for content_type in simple._ACCEPT_HTML_VALUES],
    )
    def test_html(self, content_type: str):
        index = simple.parse_project_index(INDEX_HTML_EXAMPLE, content_type)
        assert index == json.loads(INDEX_v1_EXAMPLE)

    def test_invalid_content_type(self):
        with pytest.raises(simple.UnsupportedMIMEType):
            simple.parse_project_index(INDEX_HTML_EXAMPLE, "invalid")


class TestParseProjectDetails:
    def test_json(self):
        index = simple.parse_project_details(
            DETAILS_V1_EXAMPLE, simple.ACCEPT_JSON_V1, "holygrail"
        )
        assert index == json.loads(DETAILS_V1_EXAMPLE)

    @pytest.mark.parametrize(
        ["content_type"],
        [(content_type,) for content_type in simple._ACCEPT_HTML_VALUES],
    )
    def test_html(self, content_type: str):
        index = simple.parse_project_details(
            DETAILS_HTML_EXAMPLE, content_type, "holygrail"
        )
        assert index == json.loads(DETAILS_V1_EXAMPLE)

    def test_invalid_content_type(self):
        with pytest.raises(simple.UnsupportedMIMEType):
            simple.parse_project_details(INDEX_HTML_EXAMPLE, "invalid", "holygrail")
