import packaging.tags
import packaging.version
import pytest

from mousebender import resolve, simple


class TestWheel:
    def test_init(self):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        wheel = resolve.Wheel(details)

        assert wheel.name == "distro"
        assert wheel.version == packaging.version.Version("1.2.3")
        assert wheel.build_tag == (456, "")
        assert wheel.tags == {packaging.tags.Tag("py3", "none", "any")}
        assert wheel.details == details
        assert wheel.metadata is None

    def test_equality(self):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }

        assert resolve.Wheel(details) == resolve.Wheel(details)


class TestCandidate:
    pass


class TestRequirement:
    pass


class TestIdentifier:
    pass


class TestGetPreference:
    pass


class TestSortWheels:
    pass


class TestFindMatches:
    pass


class TestIsSatisfiedBy:
    pass


class TestGetDependencies:
    pass
