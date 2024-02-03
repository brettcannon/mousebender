import random
import typing
from typing import Iterable, Sequence

import packaging.metadata
import packaging.requirements
import packaging.tags
import packaging.utils
import packaging.version
import pytest
import resolvelib

from mousebender import resolve, simple
from mousebender.resolve import Candidate


def identifier(name: str, extras: Iterable[str] = ()) -> resolve.Identifier:
    return (
        packaging.utils.canonicalize_name(name),
        frozenset(map(packaging.utils.canonicalize_name, extras)),
    )


def candidate_from_details(details: simple.ProjectFileDetails_1_0) -> resolve.Candidate:
    file_details = resolve.WheelFile(details)

    return resolve.Candidate((file_details.name, frozenset()), file_details)


def requirement_(requirement: str) -> resolve.Requirement:
    return resolve.Requirement(packaging.requirements.Requirement(requirement))


class NothingWheelProvider(resolve.WheelProvider):
    @typing.override
    def available_files(self, name):
        raise NotImplementedError

    @typing.override
    def fetch_metadata(self, wheel):
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

    def test_equality(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        assert resolve.Wheel(details) == resolve.Wheel(details)

    def test_hash(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        assert hash(resolve.Wheel(details)) == hash(
            packaging.utils.parse_wheel_filename(details["filename"])
        )


class TestWheelFileDetails:
    def test_init(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        file_details = resolve.WheelFile(details)

        assert file_details.details == details
        assert file_details.name == "spam"
        assert file_details.version == packaging.version.Version("1.2.3")
        assert file_details.wheel == resolve.Wheel(details)

    def test_wheel_tag_compatible(self):
        tag = packaging.tags.Tag("py3", "none", "any")
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        file_details = resolve.WheelFile(details)

        assert file_details.is_compatible(
            packaging.version.Version("3.12.0"), {}, [tag]
        )

    def test_is_python_compatible(self):
        tag = packaging.tags.Tag("py3", "none", "any")
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
            "requires-python": ">=3.6",
        }
        file_details = resolve.WheelFile(details)

        assert file_details.is_compatible(
            packaging.version.Version("3.12.0"), {}, [tag]
        )

    def test_is_not_python_compatible(self):
        tag = packaging.tags.Tag("py3", "none", "any")
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
            "requires-python": ">=3.12",
        }
        file_details = resolve.WheelFile(details)

        assert not file_details.is_compatible(
            packaging.version.Version("3.6.0"), {}, [tag]
        )


class TestRequirement:
    def test_init_no_extras(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)

        assert requirement.req == req
        assert requirement.identifier == ("spam", frozenset())

    def test_init_with_extras(self):
        req = packaging.requirements.Requirement("Spam[Foo,Bar]==1.2.3")
        requirement = resolve.Requirement(req)

        assert requirement.req == req
        assert requirement.identifier == ("spam", frozenset(["foo", "bar"]))

    def test_equality(self):
        requirement_spec = "Spam[Foo,Bar]==1.2.3"
        req1 = packaging.requirements.Requirement(requirement_spec)
        req2 = packaging.requirements.Requirement(requirement_spec)

        assert resolve.Requirement(req1) == resolve.Requirement(req2)

    def test_repr(self):
        req = packaging.requirements.Requirement("Spam[Foo,Bar]==1.2.3")
        requirement = resolve.Requirement(req)

        assert str(req) in repr(requirement)


class TestWheelProviderInit:
    def test_defaults(self):
        default_tags = list(packaging.tags.sys_tags())
        default_env = packaging.markers.default_environment()
        provider = NothingWheelProvider()

        assert provider.tags == default_tags
        assert provider.environment == default_env

    def test_environment(self):
        env = {"python_version": "3.12"}
        provider = NothingWheelProvider(environment=env)

        assert provider.environment == env

    def test_tags(self):
        tags = [packaging.tags.Tag("py3", "none", "any")]
        provider = NothingWheelProvider(tags=tags)

        assert provider.tags == tags

    def test_python_version(self):
        env = {"python_version": "3.12"}
        provider = NothingWheelProvider(environment=env)

        assert provider._python_version == packaging.version.Version(
            env["python_version"]
        )


class TestIdentify:
    def test_requirement(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)

        assert requirement.req == req
        assert NothingWheelProvider().identify(requirement) == requirement.identifier

    def test_candidate(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = candidate_from_details(details)

        assert NothingWheelProvider().identify(candidate) == candidate.identifier


class TestGetPreference:
    def test_iterator(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = candidate_from_details(details)

        count = 5

        candidates = {
            candidate.identifier: iter([candidate] * count),
            identifier("foo"): iter([]),
        }

        assert (
            NothingWheelProvider().get_preference(
                candidate.identifier, {}, candidates, {}, []
            )
            == count
        )


class TestIsSatisfiedBy:
    @pytest.mark.parametrize(
        ["requirement", "matches"],
        [
            ("Distro", True),
            ("Spam", False),
            ("Distro>=1.2.0", True),
            ("Distro<1.2.3", False),
        ],
    )
    def test_no_extras(self, requirement, matches):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        candidate = candidate_from_details(details)
        requirement = requirement_(requirement)
        assert NothingWheelProvider().is_satisfied_by(requirement, candidate) == matches

    @pytest.mark.parametrize(
        ["req_extra", "candidate_extra", "matches"],
        [
            (frozenset(), frozenset(), True),
            (frozenset(["extras"]), frozenset(), False),
            (frozenset(), frozenset(["extras"]), False),
            (frozenset(["extras"]), frozenset(["extras"]), True),
            (frozenset(["extra1"]), frozenset(["extra2"]), False),
        ],
    )
    def test_extras(self, req_extra, candidate_extra, matches):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        candidate = resolve.Candidate(
            identifier("distro", candidate_extra), resolve.WheelFile(details)
        )

        req = f"Distro[{','.join(req_extra)}]" if req_extra else "Distro"
        requirement = requirement_(req)

        assert NothingWheelProvider().is_satisfied_by(requirement, candidate) == matches


class TestCandidateSortKey:
    def test_version_preference(self):
        details_2_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-2.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_2_0_0 = candidate_from_details(details_2_0_0)

        details_1_2_3: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_1_2_3 = candidate_from_details(details_1_2_3)

        details_1_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_1_0_0 = candidate_from_details(details_1_0_0)

        candidates = [candidate_2_0_0, candidate_1_2_3, candidate_1_0_0]
        randomized_candidates = candidates[:]
        random.shuffle(randomized_candidates)

        randomized_candidates.sort(
            key=NothingWheelProvider().candidate_sort_key, reverse=True
        )

        assert randomized_candidates == candidates

    def test_tag_preference(self):
        details_platform: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_platform = candidate_from_details(details_platform)

        details_abi: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-abi4-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_abi = candidate_from_details(details_abi)

        details_interpreter: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_interpreter = candidate_from_details(details_interpreter)

        tags = [
            packaging.tags.Tag("cp313", "cp313", "wasi"),
            packaging.tags.Tag("cp313", "abi4", "wasi"),
            packaging.tags.Tag("py3", "none", "any"),
        ]
        provider = NothingWheelProvider(tags=tags)
        candidates = [wheel_platform, wheel_abi, wheel_interpreter]
        random.shuffle(candidates)
        candidates.sort(key=provider.candidate_sort_key, reverse=True)

        assert candidates == [wheel_platform, wheel_abi, wheel_interpreter]

    def test_build_tag_preference(self):
        details_no_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_no_tag = candidate_from_details(details_no_tag)

        details_smaller_tag_int: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-1-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_int = candidate_from_details(details_smaller_tag_int)

        details_smaller_tag_alpha: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2a-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_alpha = candidate_from_details(details_smaller_tag_alpha)

        details_biggest: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2b-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_biggest = candidate_from_details(details_biggest)

        candidates = [
            wheel_biggest,
            wheel_smaller_tag_alpha,
            wheel_smaller_tag_int,
            wheel_no_tag,
        ]
        random.shuffle(candidates)

        candidates.sort(key=NothingWheelProvider().candidate_sort_key, reverse=True)

        assert candidates == [
            wheel_biggest,
            wheel_smaller_tag_alpha,
            wheel_smaller_tag_int,
            wheel_no_tag,
        ]

    def test_precedence_of_key_parts(self):
        "Version over wheel tag over build tag."
        details_2_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-2.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_version = candidate_from_details(details_2_0_0)

        details_wheel_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_wheel_tag = candidate_from_details(details_wheel_tag)

        details_build_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_build_tag = candidate_from_details(details_build_tag)

        provider = NothingWheelProvider(
            tags=[
                packaging.tags.Tag("cp313", "cp313", "wasi"),
                packaging.tags.Tag("py3", "none", "any"),
            ],
        )

        candidates = [wheel_version, wheel_wheel_tag, wheel_build_tag]
        random.shuffle(candidates)
        candidates.sort(key=provider.candidate_sort_key, reverse=True)

        assert candidates == [wheel_version, wheel_wheel_tag, wheel_build_tag]


class TestIsSatisfiedByFile:
    is_satisfied: Callable[
        [resolve.ProjectFile, resolve.Requirement], bool
    ] = NothingWheelProvider()._is_satisfied_by_file

    def test_all_satisfied(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = requirement_("spam==1.2.3")

        assert self.is_satisfied(wheel_file, requirement)

    def test_no_version(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = requirement_("spam")

        assert self.is_satisfied(wheel_file, requirement)

    def test_different_names(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = requirement_("eggs==1.2.3")

        assert not self.is_satisfied(wheel_file, requirement)

    def test_unwanted_version(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = requirement_("spam==3.2.1")

        assert not self.is_satisfied(wheel_file, requirement)


class TestMetadataIsCompatible:
    is_compatible: Callable[[resolve.ProjectFile], bool] = NothingWheelProvider(
        environment={"python_version": "3.12"}
    )._metadata_is_compatible

    def test_no_requires_python(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        wheel_file.metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                },
            )
        )

        assert self.is_compatible(wheel_file)

    def test_requires_python_ok(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        wheel_file.metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_python": ">=3.6",
                },
            )
        )

        assert self.is_compatible(wheel_file)

    def test_requires_python_not_satisfied(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        wheel_file.metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_python": "==3.6",
                },
            )
        )


        # Make sure the candidate is not filtered w/o metadata.
        assert provider.find_matches(
            identifier("spam"), {candidate.identifier: iter([requirement])}, {}
        )

        provider = LocalWheelProvider(
            environment={"python_version": "3.9"},  # Too old
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[candidate],
            metadata=metadata,
        )

        assert not provider.find_matches(
            identifier("spam"), {candidate.identifier: iter([requirement])}, {}
        )

    def test_candidates_sorted(self):
        old_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        old_candidate = resolve.WheelCandidate(old_details)
        new_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        new_candidate = resolve.WheelCandidate(new_details)
        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[new_candidate, old_candidate],
        )
        req = packaging.requirements.Requirement("Spam")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"), {old_candidate.identifier: iter([requirement])}, {}
        )

        # Candidates purposefully in least to most preferred order as that's
        # reverse of what's expected.
        assert found == provider.sort_candidates([old_candidate, new_candidate])


class TestGetDependencies:
    def test_requirement_without_markers(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_python": ">=3.12",
                    "requires_dist": ["bacon", "eggs"],
                },
            )
        )
        candidate = resolve.WheelCandidate(details)
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
            resolve.Requirement(packaging.requirements.Requirement("eggs")),
        ]
        assert dependencies == expected

    def test_markers_evaluated(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_python": ">=3.12",
                    "requires_dist": ["bacon", "eggs; python_version<'3.12'"],
                },
            )
        )
        candidate = resolve.WheelCandidate(details)
        candidate.metadata = metadata
        provider = LocalWheelProvider(environment={"python_version": "3.12"})

        dependencies = provider.get_dependencies(candidate)
        expected = [resolve.Requirement(packaging.requirements.Requirement("bacon"))]
        assert dependencies == expected

    def test_pinned_dep_for_extra(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details, {packaging.utils.canonicalize_name("bonus")}
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3"))
        ]
        assert dependencies == expected

    def test_extra(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_dist": ["bacon; extra=='bonus'"],
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details, {packaging.utils.canonicalize_name("bonus")}
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3")),
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
        ]
        assert dependencies == expected

    def test_extra_with_marker(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_python": ">=3.12",
                    "requires_dist": [
                        "bacon; extra=='bonus'",
                        "eggs; python_version<'3.12' and extra=='bonus'",
                    ],
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details, {packaging.utils.canonicalize_name("bonus")}
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider(environment={"python_version": "3.12"})

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3")),
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
        ]
        assert dependencies == expected

    def test_multiple_extras_simultaneously(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_dist": [
                        "bacon; extra=='bonus'",
                        "eggs; extra=='bonus-bonus'",
                    ],
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details,
            {
                packaging.utils.canonicalize_name("bonus"),
                packaging.utils.canonicalize_name("bonus-bonus"),
            },
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3")),
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
            resolve.Requirement(packaging.requirements.Requirement("eggs")),
        ]
        assert dependencies == expected

    def test_requirement_listed_under_different_extras(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_dist": [
                        "bacon; extra=='bonus'",
                        "bacon; extra=='unimportant'",
                    ],
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details, {packaging.utils.canonicalize_name("bonus")}
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3")),
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
        ]
        assert dependencies == expected

    def test_extras_and_not(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                    "requires_dist": [
                        "bacon; extra=='bonus'",
                        "eggs",
                    ],
                },
            )
        )
        candidate = resolve.WheelCandidate(
            details,
            {
                packaging.utils.canonicalize_name("bonus"),
            },
        )
        candidate.metadata = metadata
        provider = LocalWheelProvider()

        dependencies = provider.get_dependencies(candidate)
        expected = [
            resolve.Requirement(packaging.requirements.Requirement("spam==1.2.3")),
            resolve.Requirement(packaging.requirements.Requirement("bacon")),
            resolve.Requirement(packaging.requirements.Requirement("eggs")),
        ]
        assert dependencies == expected


class TestResolution:
    def test_depth_1(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)
        metadata = {
            candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "Spam",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            )
        }
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[candidate],
            metadata=metadata,
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        reporter = resolvelib.BaseReporter()
        resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
        resolution = resolver.resolve([requirement])

        assert len(resolution.mapping) == 1
        assert candidate.identifier in resolution.mapping
        assert resolution.mapping[candidate.identifier] == candidate

    def test_depth_2(self):
        spam_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        spam_candidate = resolve.WheelCandidate(spam_details)
        bacon_details: simple.ProjectFileDetails_1_0 = {
            "filename": "bacon-1.2.3-456-py3-none-any.whl",
            "url": "bacon.whl",
            "hashes": {},
        }
        bacon_candidate = resolve.WheelCandidate(bacon_details)
        eggs_details: simple.ProjectFileDetails_1_0 = {
            "filename": "eggs-1.2.3-456-py3-none-any.whl",
            "url": "eggs.whl",
            "hashes": {},
        }
        eggs_candidate = resolve.WheelCandidate(eggs_details)
        metadata = {
            spam_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "Spam",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        "requires_dist": ["bacon", "eggs"],
                    },
                )
            ),
            bacon_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "bacon",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
            eggs_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "eggs",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
        }
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[spam_candidate, bacon_candidate, eggs_candidate],
            metadata=metadata,
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        reporter = resolvelib.BaseReporter()
        resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
        resolution = resolver.resolve([requirement])

        assert len(resolution.mapping) == 3
        assert spam_candidate.identifier in resolution.mapping
        assert resolution.mapping[spam_candidate.identifier] == spam_candidate
        assert bacon_candidate.identifier in resolution.mapping
        assert resolution.mapping[bacon_candidate.identifier] == bacon_candidate
        assert eggs_candidate.identifier in resolution.mapping
        assert resolution.mapping[eggs_candidate.identifier] == eggs_candidate

    def test_depth_3(self):
        spam_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        spam_candidate = resolve.WheelCandidate(spam_details)
        bacon_details: simple.ProjectFileDetails_1_0 = {
            "filename": "bacon-1.2.3-456-py3-none-any.whl",
            "url": "bacon.whl",
            "hashes": {},
        }
        bacon_candidate = resolve.WheelCandidate(bacon_details)
        eggs_details: simple.ProjectFileDetails_1_0 = {
            "filename": "eggs-1.2.3-456-py3-none-any.whl",
            "url": "eggs.whl",
            "hashes": {},
        }
        eggs_candidate = resolve.WheelCandidate(eggs_details)
        sausage_details: simple.ProjectFileDetails_1_0 = {
            "filename": "sausage-1.2.3-456-py3-none-any.whl",
            "url": "sausage.whl",
            "hashes": {},
        }
        sausage_candidate = resolve.WheelCandidate(sausage_details)
        metadata = {
            spam_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "Spam",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        "requires_dist": ["bacon", "eggs"],
                    },
                )
            ),
            bacon_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "bacon",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        "requires_dist": ["sausage"],
                    },
                )
            ),
            eggs_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "eggs",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        "requires_dist": ["sausage"],
                    },
                )
            ),
            sausage_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "sausage",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
        }
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[
                spam_candidate,
                bacon_candidate,
                eggs_candidate,
                sausage_candidate,
            ],
            metadata=metadata,
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        reporter = resolvelib.BaseReporter()
        resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
        resolution = resolver.resolve([requirement])

        assert len(resolution.mapping) == 4
        assert spam_candidate.identifier in resolution.mapping
        assert resolution.mapping[spam_candidate.identifier] == spam_candidate
        assert bacon_candidate.identifier in resolution.mapping
        assert resolution.mapping[bacon_candidate.identifier] == bacon_candidate
        assert eggs_candidate.identifier in resolution.mapping
        assert resolution.mapping[eggs_candidate.identifier] == eggs_candidate
        assert sausage_candidate.identifier in resolution.mapping
        assert resolution.mapping[sausage_candidate.identifier] == sausage_candidate

    @pytest.mark.xfail(reason="Bug to be fixed")
    def test_extras(self):
        spam_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        spam_candidate = resolve.WheelCandidate(spam_details)
        bacon_details: simple.ProjectFileDetails_1_0 = {
            "filename": "bacon-1.2.3-456-py3-none-any.whl",
            "url": "bacon.whl",
            "hashes": {},
        }
        bacon_candidate = resolve.WheelCandidate(bacon_details)
        eggs_details: simple.ProjectFileDetails_1_0 = {
            "filename": "eggs-1.2.3-456-py3-none-any.whl",
            "url": "eggs.whl",
            "hashes": {},
        }
        eggs_candidate = resolve.WheelCandidate(eggs_details)
        sausage_details: simple.ProjectFileDetails_1_0 = {
            "filename": "sausage-1.2.3-456-py3-none-any.whl",
            "url": "sausage.whl",
            "hashes": {},
        }
        sausage_candidate = resolve.WheelCandidate(sausage_details)
        toast_details: simple.ProjectFileDetails_1_0 = {
            "filename": "toast-1.2.3-456-py3-none-any.whl",
            "url": "toast.whl",
            "hashes": {},
        }
        toast_candidate = resolve.WheelCandidate(toast_details)
        metadata = {
            spam_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "Spam",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # Extras which are requested separately, but resolve to the
                        # same base dependency so that resolver has to merge
                        # them.
                        "requires_dist": ["bacon[sausage-bonus]", "bacon[eggs-bonus]"],
                    },
                )
            ),
            bacon_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "bacon",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        "requires_dist": [
                            "toast",
                            "sausage; extra=='sausage-bonus'",
                            "eggs; extra=='eggs-bonus'",
                        ],
                        "provides_extra": ["sausage-bonus", "eggs-bonus"],
                    },
                )
            ),
            eggs_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "eggs",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
            sausage_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "sausage",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
            toast_candidate.identifier: packaging.metadata.Metadata.from_raw(
                typing.cast(
                    packaging.metadata.RawMetadata,
                    {
                        "metadata_version": "2.3",
                        "name": "toast",
                        "version": "1.2.3",
                        "requires_python": ">=3.6",
                        # No dependencies.
                    },
                )
            ),
        }
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[
                spam_candidate,
                bacon_candidate,
                eggs_candidate,
                sausage_candidate,
                toast_candidate,
            ],
            metadata=metadata,
        )
        req = packaging.requirements.Requirement("Spam")
        requirement = resolve.Requirement(req)
        reporter = resolvelib.BaseReporter()
        resolver: resolvelib.Resolver = resolvelib.Resolver(provider, reporter)
        resolution = resolver.resolve([requirement])

        assert len(resolution.mapping) == 5
        assert spam_candidate.identifier in resolution.mapping
        assert resolution.mapping[spam_candidate.identifier] == spam_candidate
        assert bacon_candidate.identifier in resolution.mapping
        assert resolution.mapping[bacon_candidate.identifier] == bacon_candidate
        assert eggs_candidate.identifier in resolution.mapping
        assert resolution.mapping[eggs_candidate.identifier] == eggs_candidate
        assert sausage_candidate.identifier in resolution.mapping
        assert resolution.mapping[sausage_candidate.identifier] == sausage_candidate
        assert toast_candidate.identifier in resolution.mapping
        assert resolution.mapping[toast_candidate.identifier] == toast_candidate

    # XXX prefer newest release
    # XXX failure from no wheels
    # XXX backtrack due to upper-bound
    pass
