import packaging.metadata
import packaging.requirements
import packaging.tags
import packaging.utils
import packaging.version
import pytest

from mousebender import resolve, simple
from mousebender.resolve import Wheel


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
    def test_default_id(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        wheel = resolve.Wheel(details)
        candidate = resolve._Candidate(wheel)

        assert candidate.identifier == ("spam", frozenset())

    def test_id_with_extras(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        wheel = resolve.Wheel(details)
        extras = [packaging.utils.canonicalize_name(name) for name in ["foo", "bar"]]
        candidate = resolve._Candidate(wheel, extras)

        assert candidate.identifier == ("spam", frozenset(extras))


class TestRequirement:
    def test_init_no_extras(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve._Requirement(req)

        assert requirement.req == req
        assert requirement.identifier == ("spam", frozenset())

    def test_init_with_extras(self):
        req = packaging.requirements.Requirement("Spam[Foo,Bar]==1.2.3")
        requirement = resolve._Requirement(req)

        assert requirement.req == req
        assert requirement.identifier == ("spam", frozenset(["foo", "bar"]))

    @pytest.mark.parametrize(
        ["requirement", "matches"],
        [
            ("Distro", True),
            ("Spam", False),
            ("Distro[Foo,Bar]", True),
            ("Spam[Foo,Bar]", False),
            ("Distro>=1.2.0", True),
            ("Distro<1.2.3", False),
        ],
    )
    def test_satisfied_by(self, requirement, matches):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        wheel = resolve.Wheel(details)
        req = packaging.requirements.Requirement(requirement)

        assert resolve._Requirement(req).is_satisfied_by(wheel) == matches


class TestIdentify:
    class WheelProviderTester(resolve.WheelProvider):
        def available_wheels(self, name):
            raise NotImplementedError

        def wheel_metadata(self, wheel):
            raise NotImplementedError

    def test_requirement(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve._Requirement(req)

        assert requirement.req == req
        assert (
            self.WheelProviderTester().identify(requirement) == requirement.identifier
        )

    def test_candidate(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        wheel = resolve.Wheel(details)
        candidate = resolve._Candidate(wheel)

        assert self.WheelProviderTester().identify(candidate) == candidate.identifier


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
