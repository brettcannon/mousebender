import random
import typing
from typing import Iterable, Sequence

import packaging.metadata
import packaging.requirements
import packaging.tags
import packaging.utils
import packaging.version
import pytest
from packaging.tags import Tag

from mousebender import resolve, simple
from mousebender.resolve import Candidate


def identifier(name: str, extras: Iterable[str] = ()) -> resolve._Identifier:
    return (
        packaging.utils.canonicalize_name(name),
        frozenset(map(packaging.utils.canonicalize_name, extras)),
    )


class NoopCandidate(resolve.Candidate):
    def __init__(self):
        self.identifier = identifier("spam")
        self.version = packaging.version.Version("1.2.3")
        self.metadata = None


class NoopWheelProvider(resolve.WheelProvider):
    def available_candidates(self, name):
        raise NotImplementedError

    def fetch_candidate_metadata(self, wheel):
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


class TestCandidate:
    def test_is_env_compatible_no_metadata(self):
        assert NoopCandidate().is_env_compatible(environment={}, tags=[])

    def test_is_env_compatible(self):
        raw_metadata = typing.cast(
            packaging.metadata.RawMetadata,
            {
                "metadata_version": "2.3",
                "name": "Spam",
                "version": "1.2.3",
                "requires_python": ">=3.6",
            },
        )
        metadata = packaging.metadata.Metadata.from_raw(raw_metadata)
        candidate = NoopCandidate()
        candidate.metadata = metadata

        assert NoopCandidate().is_env_compatible(
            environment={"python_version": "3.6"}, tags=[]
        )

    def test_is_not_env_compatible(self):
        raw_metadata = typing.cast(
            packaging.metadata.RawMetadata,
            {
                "metadata_version": "2.3",
                "name": "Spam",
                "version": "1.2.3",
                "requires_python": ">=3.6",
            },
        )
        metadata = packaging.metadata.Metadata.from_raw(raw_metadata)
        candidate = NoopCandidate()
        candidate.metadata = metadata

        assert not candidate.is_env_compatible(
            environment={"python_version": "3.0.0"}, tags=[]
        )


class TestWheelCandidate:
    def test_default_id(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        candidate = resolve.WheelCandidate(details)

        assert candidate.identifier == ("spam", frozenset())

    def test_id_with_extras(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }

        extras = [packaging.utils.canonicalize_name(name) for name in ["foo", "bar"]]
        candidate = resolve.WheelCandidate(details, extras)

        assert candidate.identifier == ("spam", frozenset(extras))

    def test_equality(self):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)

        assert candidate == resolve.WheelCandidate(details)

    def test_is_not_env_compatible_metadata(self):
        raw_metadata = typing.cast(
            packaging.metadata.RawMetadata,
            {
                "metadata_version": "2.3",
                "name": "Spam",
                "version": "1.2.3",
                "requires_python": ">=3.6",
            },
        )
        metadata = packaging.metadata.Metadata.from_raw(raw_metadata)
        candidate = NoopCandidate()
        candidate.metadata = metadata

        assert not candidate.is_env_compatible(
            environment={"python_version": "3.0"}, tags=[]
        )

    def test_is_not_env_compatible_requires_python(self):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
            "requires-python": ">=3.6",
        }
        candidate = resolve.WheelCandidate(details)

        assert not candidate.is_env_compatible(
            environment={"python_version": "3.0"}, tags=[]
        )

    def test_is_not_env_compatbile_wheel_tags(self):
        filename = "Distro-1.2.3-456-py313-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)

        assert not candidate.is_env_compatible(
            environment={}, tags=[packaging.tags.Tag("py3", "none", "any")]
        )

    def test_is_env_compatible(self):
        filename = "Distro-1.2.3-456-py3-none-any.whl"
        details: simple.ProjectFileDetails_1_0 = {
            "filename": filename,
            "url": f"https://example.com/{filename}",
            "hashes": {},
            "requires-python": ">=3.6",
        }
        candidate = resolve.WheelCandidate(details)

        assert candidate.is_env_compatible(
            environment={"python_version": "3.6.0"},
            tags=[packaging.tags.Tag("py3", "none", "any")],
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


class TestIdentify:
    def test_requirement(self):
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)

        assert requirement.req == req
        assert NoopWheelProvider().identify(requirement) == requirement.identifier

    def test_candidate(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)

        assert NoopWheelProvider().identify(candidate) == candidate.identifier


class TestGetPreference:
    def test_iterator(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)

        count = 5

        candidates = {
            candidate.identifier: iter([candidate] * count),
            identifier("foo"): iter([]),
        }

        assert (
            NoopWheelProvider().get_preference(
                candidate.identifier, {}, candidates, {}, []
            )
            == count
        )


class TestSortCandidates:
    def test_version_preference(self):
        details_2_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-2.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_2_0_0 = resolve.WheelCandidate(details_2_0_0)

        details_1_2_3: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_1_2_3 = resolve.WheelCandidate(details_1_2_3)

        details_1_0_0: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate_1_0_0 = resolve.WheelCandidate(details_1_0_0)

        candidates = [candidate_2_0_0, candidate_1_2_3, candidate_1_0_0]
        randomized_candidates = candidates[:]
        random.shuffle(randomized_candidates)

        provider = NoopWheelProvider(
            environment={}, tags=[packaging.tags.Tag("py3", "none", "any")]
        )
        sorted_candidates = provider.sort_candidates(candidates)

        assert sorted_candidates == candidates

    def test_tag_preference(self):
        details_platform: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_platform = resolve.WheelCandidate(details_platform)

        details_abi: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-cp313-abi4-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_abi = resolve.WheelCandidate(details_abi)

        details_interpreter: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_interpreter = resolve.WheelCandidate(details_interpreter)

        wheels = [wheel_platform, wheel_abi, wheel_interpreter]
        random.shuffle(wheels)

        tags = [
            packaging.tags.Tag("cp313", "cp313", "wasi"),
            packaging.tags.Tag("cp313", "abi4", "wasi"),
            packaging.tags.Tag("py3", "none", "any"),
        ]

        provider = NoopWheelProvider(environment={}, tags=tags)

        candidates = provider.sort_candidates(wheels)

        assert candidates == [wheel_platform, wheel_abi, wheel_interpreter]

    def test_build_tag_preference(self):
        details_no_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_no_tag = resolve.WheelCandidate(details_no_tag)

        details_smaller_tag_int: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-1-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_int = resolve.WheelCandidate(details_smaller_tag_int)

        details_smaller_tag_alpha: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2a-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_smaller_tag_alpha = resolve.WheelCandidate(details_smaller_tag_alpha)

        details_biggest: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.0.0-2b-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_biggest = resolve.WheelCandidate(details_biggest)

        wheels = [
            wheel_biggest,
            wheel_smaller_tag_alpha,
            wheel_smaller_tag_int,
            wheel_no_tag,
        ]
        random.shuffle(wheels)

        provider = NoopWheelProvider(
            environment={}, tags=[packaging.tags.Tag("py3", "none", "any")]
        )
        candidates = provider.sort_candidates(wheels)

        assert candidates == [
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
        wheel_version = resolve.WheelCandidate(details_2_0_0)

        details_wheel_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-cp313-cp313-wasi.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_wheel_tag = resolve.WheelCandidate(details_wheel_tag)

        details_build_tag: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_build_tag = resolve.WheelCandidate(details_build_tag)

        wheels = [wheel_version, wheel_wheel_tag, wheel_build_tag]
        random.shuffle(wheels)

        provider = NoopWheelProvider(
            environment={},
            tags=[
                packaging.tags.Tag("cp313", "cp313", "wasi"),
                packaging.tags.Tag("py3", "none", "any"),
            ],
        )

        candidates = provider.sort_candidates(wheels)

        assert candidates == [wheel_version, wheel_wheel_tag, wheel_build_tag]


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
        candidate = resolve.WheelCandidate(details)
        req = packaging.requirements.Requirement(requirement)
        requirement = resolve.Requirement(req)
        assert NoopWheelProvider().is_satisfied_by(requirement, candidate) == matches

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
        candidate = resolve.WheelCandidate(details, candidate_extra)

        req = f"Distro[{','.join(req_extra)}]" if req_extra else "Distro"
        requirement = resolve.Requirement(packaging.requirements.Requirement(req))

        assert NoopWheelProvider().is_satisfied_by(requirement, candidate) == matches


class TestFilterCandidates:
    def test_all_true(self):
        class CompatibleCandidate(NoopCandidate):
            def is_env_compatible(self, *, environment, tags):
                return True

        candidates = [
            CompatibleCandidate(),
            CompatibleCandidate(),
            CompatibleCandidate(),
        ]
        provider = NoopWheelProvider(environment={}, tags=[])

        assert list(provider._filter_candidates(candidates)) == candidates

    def test_all_false(self):
        class IncompatibleCandidate(NoopCandidate):
            def is_env_compatible(self, *, environment, tags):
                return False

        candidates = [
            IncompatibleCandidate(),
            IncompatibleCandidate(),
            IncompatibleCandidate(),
        ]
        provider = NoopWheelProvider(environment={}, tags=[])

        assert list(provider._filter_candidates(candidates)) == []

    def test_mix(self):
        class MaybeCompatibleCandidate(NoopCandidate):
            def __init__(self, compatible):
                super().__init__()
                self.compatible = compatible

            def is_env_compatible(self, *, environment, tags):
                return self.compatible

        candidates = [
            MaybeCompatibleCandidate(False),
            MaybeCompatibleCandidate(True),
            MaybeCompatibleCandidate(False),
        ]
        provider = NoopWheelProvider(environment={}, tags=[])

        assert list(provider._filter_candidates(candidates)) == [candidates[1]]


class LocalWheelProvider(resolve.WheelProvider):
    def __init__(
        self,
        *,
        environment: dict[str, str] | None = None,
        tags: Sequence[Tag] | None = None,
        candidates: Iterable[Candidate] | None = None,
        metadata: dict[resolve._Identifier, packaging.metadata.Metadata] | None = None,
    ) -> None:
        super().__init__(environment=environment, tags=tags)
        self.candidates = candidates or []
        self.metadata = metadata or {}

    def available_candidates(
        self, name: packaging.utils.NormalizedName
    ) -> Iterable[Candidate]:
        return self.candidates

    def fetch_candidate_metadata(self, candidates: Iterable[Candidate]) -> None:
        for candidate in candidates:
            candidate.metadata = self.metadata.get(candidate.identifier)


class TestFindMatches:
    def test_available_candidates_cached(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        candidate = resolve.WheelCandidate(details)
        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[candidate],
        )

        assert not provider._candidate_cache

        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        provider.find_matches(
            identifier("spam"), {candidate.identifier: iter([requirement])}, {}
        )

        assert provider._candidate_cache == {candidate.identifier[0]: [candidate]}

    def test_filter_available_candidates_by_file_details(self):
        """Candidates from a server should be initially filtered by wheel tags."""
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_candidate = resolve.WheelCandidate(good_details)
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-cp313-abi3-manylinux_2_24.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        bad_candidate = resolve.WheelCandidate(bad_details)
        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[bad_candidate, good_candidate],
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"), {good_candidate.identifier: iter([requirement])}, {}
        )

        assert found == [good_candidate]

    def test_filter_by_requirement(self):
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_candidate = resolve.WheelCandidate(good_details)
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        bad_candidate = resolve.WheelCandidate(bad_details)
        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[bad_candidate, good_candidate],
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"), {good_candidate.identifier: iter([requirement])}, {}
        )

        assert found == [good_candidate]

    def test_filter_by_incompatibility(self):
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_candidate = resolve.WheelCandidate(good_details)
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        bad_candidate = resolve.WheelCandidate(bad_details)
        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[bad_candidate, good_candidate],
        )
        req = packaging.requirements.Requirement("Spam")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"),
            {good_candidate.identifier: iter([requirement])},
            {good_candidate.identifier: iter([bad_candidate])},
        )

        assert found == [good_candidate]

    def test_fetch_candidate_metadata(self):
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
        provider.find_matches(
            identifier("spam"), {candidate.identifier: iter([requirement])}, {}
        )

        assert candidate.metadata == metadata[candidate.identifier]

    def test_candidates_filtered_on_fetched_metadata(self):
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
                        "requires_python": ">=3.12",
                    },
                )
            )
        }
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)

        provider = LocalWheelProvider(
            environment={},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            candidates=[candidate],
            # No metadata
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

    # XXX all requirements
    # XXX markers on requirements are evaluated
    # XXX add pinned dependency when there's an extra
    # XXX all requirements pulled in by the extra
    pass


class TestResolution:
    # XXX
    pass
