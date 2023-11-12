import random

import packaging.metadata
import packaging.requirements
import packaging.tags
import packaging.utils
import packaging.version
import pytest

from mousebender import resolve, simple


class NoopWheelProvider(resolve.WheelProvider):
    def available_wheels(self, name):
        raise NotImplementedError

    def wheel_metadata(self, wheel):
        raise NotImplementedError


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
    def test_requirement(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve._Requirement(req)

        assert requirement.req == req
        assert NoopWheelProvider().identify(requirement) == requirement.identifier

    def test_candidate(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        wheel = resolve.Wheel(details)
        candidate = resolve._Candidate(wheel)

        assert NoopWheelProvider().identify(candidate) == candidate.identifier


class TestGetPreference:
    def test_iterator(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        wheel = resolve.Wheel(details)
        candidate = resolve._Candidate(wheel)

        count = 5

        candidates = {
            candidate.identifier: iter([candidate] * count),
            (packaging.utils.canonicalize_name("foo"), frozenset()): iter([]),
        }

        assert (
            NoopWheelProvider().get_preference(
                candidate.identifier, {}, candidates, {}, []
            )
            == count
        )


class TestSortWheels:
    def test_version_preference(self):
        details_2_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-2.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_2_0_0 = resolve.Wheel(details_2_0_0)

        details_1_2_3: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_1_2_3 = resolve.Wheel(details_1_2_3)

        details_1_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_1_0_0 = resolve.Wheel(details_1_0_0)

        wheels = [wheel_2_0_0, wheel_1_2_3, wheel_1_0_0]
        random.shuffle(wheels)

        provider = NoopWheelProvider(
            {}, tags=[packaging.tags.Tag("py3", "none", "any")]
        )

        assert provider.sort_wheels(wheels) == [wheel_2_0_0, wheel_1_2_3, wheel_1_0_0]

    def test_tag_preference(self):
        details_platform: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_platform = resolve.Wheel(details_platform)

        details_abi: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-abi4-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_abi = resolve.Wheel(details_abi)

        details_interpreter: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_interpreter = resolve.Wheel(details_interpreter)

        wheels = [wheel_platform, wheel_abi, wheel_interpreter]
        random.shuffle(wheels)

        tags = [
            packaging.tags.Tag("cp313", "cp313", "wasi"),
            packaging.tags.Tag("cp313", "abi4", "wasi"),
            packaging.tags.Tag("py3", "none", "any"),
        ]

        provider = NoopWheelProvider({}, tags=tags)

        sorted_wheels = provider.sort_wheels(wheels)

        assert sorted_wheels == [
            wheel_platform,
            wheel_abi,
            wheel_interpreter,
        ]

    def test_build_tag_preference(self):
        details_no_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_no_tag = resolve.Wheel(details_no_tag)

        details_smaller_tag_int: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-1-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_int = resolve.Wheel(details_smaller_tag_int)

        details_smaller_tag_alpha: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2a-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_alpha = resolve.Wheel(details_smaller_tag_alpha)

        details_biggest: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2b-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_biggest = resolve.Wheel(details_biggest)

        wheels = [
            wheel_biggest,
            wheel_smaller_tag_alpha,
            wheel_smaller_tag_int,
            wheel_no_tag,
        ]
        random.shuffle(wheels)

        provider = NoopWheelProvider(
            {}, tags=[packaging.tags.Tag("py3", "none", "any")]
        )

        assert provider.sort_wheels(wheels) == [
            wheel_biggest,
            wheel_smaller_tag_alpha,
            wheel_smaller_tag_int,
            wheel_no_tag,
        ]

    def test_precedence(self):
        "Version over wheel tag over build tag."
        details_2_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-2.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_version = resolve.Wheel(details_2_0_0)

        details_wheel_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_wheel_tag = resolve.Wheel(details_wheel_tag)

        details_build_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_build_tag = resolve.Wheel(details_build_tag)

        wheels = [wheel_version, wheel_wheel_tag, wheel_build_tag]
        random.shuffle(wheels)

        provider = NoopWheelProvider(
            {},
            tags=[
                packaging.tags.Tag("cp313", "cp313", "wasi"),
                packaging.tags.Tag("py3", "none", "any"),
            ],
        )

        assert provider.sort_wheels(wheels) == [
            wheel_version,
            wheel_wheel_tag,
            wheel_build_tag,
        ]


class TestFindMatches:
    pass


class TestIsSatisfiedBy:
    pass


class TestGetDependencies:
    pass
