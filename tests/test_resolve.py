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


def identifier(name: str, extras: Iterable[str] = ()) -> resolve.Identifier:
    return (
        packaging.utils.canonicalize_name(name),
        frozenset(map(packaging.utils.canonicalize_name, extras)),
    )


def candidate_from_details(details: simple.ProjectFileDetails_1_0) -> resolve.Candidate:
    file_details = resolve.WheelFile(details)

    return resolve.Candidate((file_details.name, frozenset()), file_details)


def create_requirement(requirement: str) -> resolve.Requirement:
    return resolve.Requirement(packaging.requirements.Requirement(requirement))


class NothingWheelProvider(resolve.WheelProvider):
    @typing.override
    def available_files(self, name):
        raise NotImplementedError

    @typing.override
    def fetch_metadata(self, wheel):
        raise NotImplementedError


class LocalWheelProvider(resolve.WheelProvider):
    @typing.override
    def __init__(
        self,
        *,
        environment: dict[str, str] | None = None,
        tags: Sequence[packaging.tags.Tag] | None = None,
        files: Iterable[resolve.ProjectFile] | None = None,
        metadata: dict[str, packaging.metadata.Metadata] | None = None,
    ) -> None:
        super().__init__(environment=environment, tags=tags)
        self.files = files or []
        self.metadata = metadata or {}

    @typing.override
    def available_files(
        self, name: packaging.utils.NormalizedName
    ) -> Iterable[resolve.ProjectFile]:
        return self.files

    @typing.override
    def fetch_metadata(self, project_files: Iterable[resolve.ProjectFile]) -> None:
        for file in project_files:
            if file.metadata is None:
                file.metadata = self.metadata[file.name]


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
        provider = NothingWheelProvider(
            python_version=packaging.version.Version("3.12.0"), tags=[tag]
        )

        assert file_details.is_compatible(provider)

    def test_is_python_compatible(self):
        tag = packaging.tags.Tag("py3", "none", "any")
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
            "requires-python": ">=3.6",
        }
        file_details = resolve.WheelFile(details)
        provider = NothingWheelProvider(
            python_version=packaging.version.Version("3.12.0"), tags=[tag]
        )

        assert file_details.is_compatible(provider)

    def test_is_not_python_compatible(self):
        tag = packaging.tags.Tag("py3", "none", "any")
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
            "requires-python": ">=3.12",
        }
        file_details = resolve.WheelFile(details)
        provider = NothingWheelProvider(
            python_version=packaging.version.Version("3.6.0"), tags=[tag]
        )

        assert not file_details.is_compatible(provider)


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

    def test_python_version_provided(self):
        version = packaging.version.Version("3.12.4")
        env = {"python_version": "3.12"}
        provider = NothingWheelProvider(environment=env)

        assert provider.python_version == version

    def test_python_version_from_env(self):
        env = {"python_version": "3.12"}
        provider = NothingWheelProvider(environment=env)

        assert provider.python_version == packaging.version.Version(
            env["python_version"]
        )

    def test_python_version_default(self):
        provider = NothingWheelProvider()
        version_str = sys.version.partition(" ")[0].removesuffix("+")
        version = packaging.version.Version(version_str)

        assert provider.python_version == version


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
        requirement = create_requirement(requirement)
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
        requirement = create_requirement(req)

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
        requirement = create_requirement("spam==1.2.3")

        assert self.is_satisfied(wheel_file, requirement)

    def test_no_version(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = create_requirement("spam")

        assert self.is_satisfied(wheel_file, requirement)

    def test_different_names(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = create_requirement("eggs==1.2.3")

        assert not self.is_satisfied(wheel_file, requirement)

    def test_unwanted_version(self):
        file_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-2-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        wheel_file = resolve.WheelFile(file_details)
        requirement = create_requirement("spam==3.2.1")

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


class TestFindMatches:
    def test_project_files_cached(self):
        details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        file = resolve.WheelFile(details)
        metadata = packaging.metadata.Metadata.from_raw(
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
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            files=[file],
            metadata={"spam": metadata},
        )

        assert not provider._project_files_cache

        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        provider.find_matches(
            identifier("spam"), {identifier("spam"): iter([requirement])}, {}
        )

        assert provider._project_files_cache == {"spam": [file]}

    def test_filter_project_files_by_details(self):
        metadata = packaging.metadata.Metadata.from_raw(
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
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_file = resolve.WheelFile(good_details)
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-cp313-abi3-manylinux_2_24.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        bad_file = resolve.WheelFile(bad_details)
        provider = LocalWheelProvider(
            environment={"python_version": "3.12"},
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            files=[bad_file, good_file],
            metadata={"spam": metadata},
        )
        req = create_requirement("Spam==1.2.3")
        id_ = identifier("spam")
        found = provider.find_matches(id_, {id_: iter([req])}, {})

        assert found == [resolve.Candidate(id_, good_file)]

    def test_filter_by_requirement(self):
        good_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                },
            )
        )
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_file = resolve.WheelFile(good_details)
        good_file.metadata = good_metadata
        bad_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.4",  # Too new.
                },
            )
        )
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",  # Too new.
            "url": "spam.whl",
            "hashes": {},
        }
        bad_file = resolve.WheelFile(bad_details)
        bad_file.metadata = bad_metadata
        provider = LocalWheelProvider(
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            files=[bad_file, good_file],
        )
        req = packaging.requirements.Requirement("Spam==1.2.3")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"), {identifier("spam"): iter([requirement])}, {}
        )

        assert found == [resolve.Candidate(requirement.identifier, good_file)]

    def test_filter_by_incompatibility(self):
        good_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                },
            )
        )
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_file = resolve.WheelFile(good_details)
        good_file.metadata = good_metadata
        bad_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.4",  # Newer.
                },
            )
        )
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        bad_file = resolve.WheelFile(bad_details)
        bad_file.metadata = bad_metadata
        provider = LocalWheelProvider(
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            files=[bad_file, good_file],
        )
        bad_candidate = resolve.Candidate(identifier("spam"), bad_file)
        req = packaging.requirements.Requirement("Spam")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"),
            {identifier("spam"): iter([requirement])},
            {identifier("spam"): iter([bad_candidate])},
        )

        assert found == [resolve.Candidate(requirement.identifier, good_file)]

    def test_files_filtered_on_fetched_metadata(self):
        good_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.3",
                },
            )
        )
        good_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.3-456-py3-none-any.whl",
            "url": "spam.whl",
            "hashes": {},
        }
        good_file = resolve.WheelFile(good_details)
        good_file.metadata = good_metadata
        bad_metadata = packaging.metadata.Metadata.from_raw(
            typing.cast(
                packaging.metadata.RawMetadata,
                {
                    "metadata_version": "2.3",
                    "name": "Spam",
                    "version": "1.2.4",  # Newer.
                    "requires_python": "> 3.12",  # Too new.
                },
            )
        )
        bad_details: simple.ProjectFileDetails_1_0 = {
            "filename": "Spam-1.2.4-py3-none-any.whl",  # Newer.
            "url": "spam.whl",
            "hashes": {},
        }
        bad_file = resolve.WheelFile(bad_details)
        bad_file.metadata = bad_metadata
        provider = LocalWheelProvider(
            python_version=packaging.version.Version("3.12"),
            tags=[packaging.tags.Tag("py3", "none", "Any")],
            files=[bad_file, good_file],
        )
        req = packaging.requirements.Requirement("Spam")
        requirement = resolve.Requirement(req)
        found = provider.find_matches(
            identifier("spam"), {identifier("spam"): iter([requirement])}, {}
        )

        assert found == [resolve.Candidate(requirement.identifier, good_file)]


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
