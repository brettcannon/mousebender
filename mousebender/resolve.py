"""An API for wheel-based requirement resolution."""
from __future__ import annotations

import abc
import functools
import typing
from typing import (
    Collection,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

import packaging.markers
import packaging.metadata
import packaging.requirements
import packaging.specifiers
import packaging.tags
import packaging.utils
import packaging.version
import resolvelib

from . import simple

Identifier = tuple[
    packaging.utils.NormalizedName, frozenset[packaging.utils.NormalizedName]
]


class Wheel:
    """A wheel for a distribution."""

    name: packaging.utils.NormalizedName
    version: packaging.version.Version
    build_tag: Optional[packaging.utils.BuildTag]
    tags: frozenset[packaging.tags.Tag]

    def __init__(self, details: simple.ProjectFileDetails) -> None:
        self._filename_tuple = packaging.utils.parse_wheel_filename(details["filename"])
        (
            self.name,
            self.version,
            self.build_tag,
            self.tags,
        ) = self._filename_tuple

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Wheel):
            return NotImplemented
        return self._filename_tuple == other._filename_tuple

    def __hash__(self) -> int:
        return hash(self._filename_tuple)


# Subclass for sdists.
class ProjectFile(typing.Protocol):
    """Protocol for storing file details to potentially be candidates."""

    details: simple.ProjectFileDetails
    name: packaging.utils.NormalizedName
    version: packaging.version.Version
    metadata: Optional[packaging.metadata.Metadata]

    @abc.abstractmethod
    def is_compatible(
        self,
        python_version: packaging.version.Version,
        environment: dict[str, str],
        tags: Collection[packaging.tags.Tag],
    ) -> bool:
        """Check if the file is compatible with the environment."""
        return True


class WheelFile(ProjectFile):
    """Details of wheel files to potentially be candidates."""

    details: simple.ProjectFileDetails
    name: packaging.utils.NormalizedName
    version: packaging.version.Version
    metadata: Optional[packaging.metadata.Metadata]
    wheel: Wheel

    def __init__(self, details: simple.ProjectFileDetails) -> None:
        self.details = details
        self.wheel = Wheel(self.details)
        self.name = self.wheel.name
        self.version = self.wheel.version
        self.metadata = None

    @typing.override
    def is_compatible(
        self,
        python_version: packaging.version.Version,
        environment: dict[str, str],
        tags: Collection[packaging.tags.Tag],
    ) -> bool:
        """Check if the wheel file is compatible with the environment and tags."""
        if not any(tag in tags for tag in self.wheel.tags):
            return False
        elif "requires-python" in self.details:
            requires_python = packaging.specifiers.SpecifierSet(
                self.details["requires-python"]
            )
            if python_version not in requires_python:
                return False

        return super().is_compatible(python_version, environment, tags)


class Candidate:
    """A Candidate to satisfy a requirement."""

    identifier: Identifier
    file: ProjectFile

    def __init__(self, identifier: Identifier, file: ProjectFile) -> None:
        self.identifier = identifier
        self.file = file


class Requirement:
    """A requirement for a distribution."""

    identifier: Identifier
    req: packaging.requirements.Requirement

    def __init__(self, req: packaging.requirements.Requirement, /) -> None:
        """Initialize from the provided requirement."""
        self.req = req
        name = packaging.utils.canonicalize_name(req.name)
        extras = frozenset(map(packaging.utils.canonicalize_name, req.extras))
        self.identifier = name, extras

    def __eq__(self, other: object) -> bool:
        """Check if two requirements are equal."""
        if not isinstance(other, Requirement):
            return NotImplemented
        return self.identifier == other.identifier and self.req == other.req

    def __repr__(self) -> str:
        """Return a string representation of the requirement."""
        return f'{type(self).__qualname__}("{self.req!s}")'


_RT = TypeVar("_RT")  # Requirement.
_CT = TypeVar("_CT")  # Candidate.


class _RequirementInformation(tuple, Generic[_RT, _CT]):
    requirement: _RT
    parent: Optional[_CT]


class WheelProvider(resolvelib.AbstractProvider, abc.ABC):
    """A provider for resolving requirements based on wheels."""

    environment: dict[str, str]  # packaging.markers has no TypedDict for this.
    tags: list[packaging.tags.Tag]
    # If is assumed the files have already been filtered down to only wheels
    # that have any chance to work with the specified environment details.
    _file_details_cache: dict[packaging.utils.NormalizedName, Collection[ProjectFile]]
    _python_version: packaging.version.Version

    def __init__(
        self,
        *,
        environment: Optional[dict[str, str]] = None,
        tags: Optional[Sequence[packaging.tags.Tag]] = None,
    ) -> None:
        """Initialize the provider.

        Any unspecified argument will be set according to the running
        interpreter.

        The 'tags' argument is expected to be in priority order, from most to
        least preferred tag.
        """
        if environment is None:
            environment = packaging.markers.default_environment()
        self.environment = environment
        if tags is None:
            self.tags = list(packaging.tags.sys_tags())
        else:
            self.tags = list(tags)
        self._file_details_cache = {}
        # TODO need to care that "python_version" doesn't have release level?
        self._python_version = packaging.version.parse(environment["python_version"])

    # Override for sdists.
    @abc.abstractmethod
    def available_files(
        self, name: packaging.utils.NormalizedName
    ) -> Iterable[ProjectFile]:
        """Get the available wheels for a distribution."""
        raise NotImplementedError

    # Override for sdists.
    @abc.abstractmethod
    def fetch_metadata(self, file_details: Iterable[ProjectFile]) -> None:
        """Fetch the metadata of e.g. a wheel and add it in-place."""
        # A method so that subclasses can do paralle/async fetching of the metadata.
        raise NotImplementedError

    @typing.override
    def identify(
        self, requirement_or_candidate: Union[Requirement, Candidate]
    ) -> Identifier:
        """Get the key for a requirement or candidate."""
        return requirement_or_candidate.identifier

    @typing.override
    def get_preference(
        self,
        identifier: Identifier,
        resolutions: Mapping[Identifier, Candidate],
        candidates: Mapping[Identifier, Iterator[Candidate]],
        information: Mapping[  # type: ignore[override]
            Identifier, Iterator[_RequirementInformation[Requirement, Candidate]]
        ],
        backtrack_causes: Sequence[_RequirementInformation[Requirement, Candidate]],  # type: ignore[override]
    ) -> int:
        """Calculate the preference to solve for a requirement.

        Provide a sort key based on the number of candidates for the
        requirement.
        """
        # Since `candidates` contains iterators, we need to consume them to calculate
        # their length.
        return sum(1 for _ in candidates[identifier])

    @typing.override
    def is_satisfied_by(self, requirement: Requirement, candidate: Candidate) -> bool:
        """Check if a candidate satisfies a requirement."""
        # A method so subclasses can decide to e.g. allow for pre-releases.
        print("Is", requirement, "satisfied by", candidate, "?", end=" ")
        is_satisfied = (
            requirement.identifier == candidate.identifier
            and self._is_satisfied_by_file(candidate.file, requirement)
        )
        print(is_satisfied)
        return is_satisfied

    # This exists as method so that subclasses can e.g. prefer older versions.
    # Override for sdists.
    def candidate_sort_key(self, candidate: Candidate) -> tuple:
        """Provide a sort key for a candidate.

        The key should lead to a sort of least to most preferred wheel.
        Preference is determined by the newest version, tag priority/specificity
        (as defined by self.tags), and then build tag.
        """
        assert isinstance(candidate.file, WheelFile)

        # A separate method so subclasses can e.g. prefer older versions.
        for tag_priority, tag in enumerate(self.tags):  # noqa: B007
            if tag in candidate.file.wheel.tags:
                break
        else:
            raise ValueError("No compatible tags found for any wheels.")

        return (
            candidate.file.version,
            len(self.tags) - tag_priority,
            candidate.file.wheel.build_tag or (),
        )

    def _is_satisfied_by_file(
        self, details: ProjectFile, requirement: Requirement
    ) -> bool:
        """Check if the file satisfies the requirement."""
        is_satisfied = (
            details.name == packaging.utils.canonicalize_name(requirement.req.name)
            and details.version in requirement.req.specifier
        )

        return is_satisfied

    def _metadata_is_compatible(self, details: ProjectFile) -> bool:
        """Check if the file metadata is compatible with the environment."""
        # Should have already been fetched.
        assert details.metadata is not None

        if requires_python := details.metadata.requires_python:
            if self._python_version not in requires_python:
                return False

        return True

    # Requirement -> Candidate
    @typing.override
    def find_matches(
        self,
        identifier: _Identifier,
        requirements: Mapping[_Identifier, Iterator[Requirement]],
        incompatibilities: Mapping[_Identifier, Iterator[Candidate]],
    ) -> Sequence[Candidate]:
        """Get the potential candidates for a requirement.

        This involves getting all potential wheels for a distribution and
        checking if they meet all requirements while not being considered
        an incompatible candidate.
        """
        name, _extras = identifier
        if name in self._candidate_cache:
            candidates = self._candidate_cache[name]
        else:
            potential_candidates = self.available_candidates(name)
            # Quickly filter based on file details to avoid pointlessly fetching
            # metadata.
            filtered_on_details = self._filter_candidates(potential_candidates)

            self._candidate_cache[name] = list(filtered_on_details)
            candidates = self._candidate_cache[name]

        filtered_candidates_by_req = filter(
            lambda c: all(self.is_satisfied_by(r, c) for r in requirements[identifier]),
            candidates,
        )
        incompat_candidates = list(incompatibilities.get(identifier, []))
        filtered_candidates = list(
            filter(lambda c: c not in incompat_candidates, filtered_candidates_by_req)
        )

        # Wait as long as possible to fetch metadata; it might be expensive.
        missing_metadata = filter(lambda c: c.metadata is None, filtered_candidates)
        self.fetch_candidate_metadata(missing_metadata)

        # Filter again in case metadata clarified compatibility.
        fully_filtered = self._filter_candidates(filtered_candidates)

        sorted_candidates = self.sort_candidates(fully_filtered)

        return sorted_candidates

    # Candidate -> Requirement
    @typing.override
    def get_dependencies(self, candidate: Candidate) -> list[Requirement]:
        """Get the requirements of a candidate."""
        assert candidate.metadata is not None

        requirements = []
        name, extras = candidate.identifier
        if extras:
            # https://github.com/brettcannon/mousebender/issues/105#issuecomment-1704244739
            req = packaging.requirements.Requirement(f"{name}=={candidate.version}")
            requirements.append(Requirement(req))

        for req in candidate.metadata.requires_dist:
            if req.marker is None:
                requirements.append(Requirement(req))
            elif req.marker.evaluate(self.environment):
                requirements.append(Requirement(req))
            elif extras and any(
                req.marker.evaluate(self.environment | {"extra": extra})
                for extra in extras
            ):
                requirements.append(Requirement(req))

        # Since the markers have been evaluated, they are no longer needed.
        # Stripping them out simplifies testing.
        for requirement in requirements:
            requirement.req.marker = None

        return requirements
