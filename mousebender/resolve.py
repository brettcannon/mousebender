"""An API for wheel-based requirement resolution."""
from __future__ import annotations

import abc
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

_Identifier = tuple[
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


# Subclass for sdists.
class Candidate(typing.Protocol):
    """A candidate to satisfy a requirement."""

    identifier: _Identifier
    version: packaging.version.Version
    metadata: Optional[packaging.metadata.Metadata]

    def is_env_compatible(
        self, *, environment: dict[str, str], tags: Sequence[packaging.tags.Tag]
    ) -> bool:
        """Check if the candidate is compatible with the environment.

        When compatibility is unknown due lack of details
        (e.g., missing metadata), assume compatibility.
        """
        if self.metadata is None:
            return True
        elif self.metadata.requires_python is None:
            return True
        else:
            python_version = packaging.version.Version(environment["python_version"])
            return python_version in self.metadata.requires_python


class WheelCandidate(Candidate):
    """A candidate to satisfy a requirement."""

    identifier: _Identifier
    details: simple.ProjectFileDetails
    wheel: Wheel
    version: packaging.version.Version
    metadata: Optional[packaging.metadata.Metadata]

    def __init__(
        self,
        details: simple.ProjectFileDetails,
        extras: Iterable[packaging.utils.NormalizedName] = frozenset(),
    ) -> None:
        self.details = details
        self.wheel = Wheel(self.details)
        self.version = self.wheel.version
        self.metadata = None
        self.identifier = self.wheel.name, frozenset(extras)

    def __eq__(self, other: object) -> bool:
        """Check if two candidates are equal."""
        if not isinstance(other, WheelCandidate):
            return NotImplemented
        return self.details == other.details

    @typing.override
    def is_env_compatible(
        self, *, environment: dict[str, str], tags: Sequence[packaging.tags.Tag]
    ) -> bool:
        """Check if the wheel is compatible with the platform."""
        if "requires-python" in self.details:
            requires_python = packaging.specifiers.SpecifierSet(
                self.details["requires-python"]
            )
            # TODO need to care that "python_version" doesn't have release level?
            python_version = packaging.version.parse(environment["python_version"])
            if python_version not in requires_python:
                return False
        elif not super().is_env_compatible(environment=environment, tags=tags):
            return False
        return any(tag in tags for tag in self.wheel.tags)


class Requirement:
    """A requirement for a distribution."""

    identifier: _Identifier
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


_RT = TypeVar("_RT")  # Requirement.
_CT = TypeVar("_CT")  # Candidate.


class _RequirementInformation(tuple, Generic[_RT, _CT]):
    requirement: _RT
    parent: Optional[_CT]


class WheelProvider(resolvelib.AbstractProvider, abc.ABC):
    """A provider for resolving requirements based on wheels."""

    environment: dict[str, str]  # packaging.markers has not TypedDict for this.
    tags: list[packaging.tags.Tag]
    # Assumed to have already been filtered down to only wheels that have any
    # chance to work with the specified environment details.
    _candidate_cache: dict[packaging.utils.NormalizedName, Collection[Candidate]]

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
        self._candidate_cache = {}

    # Override for sdists.
    @abc.abstractmethod
    def available_candidates(
        self, name: packaging.utils.NormalizedName
    ) -> Iterable[Candidate]:
        """Get the available wheels for a distribution."""
        raise NotImplementedError

    # Override for sdists.
    @abc.abstractmethod
    def fetch_candidate_metadata(self, candidates: Iterable[Candidate]) -> None:
        """Fetch the metadata of e.g. a wheel and add it in-place."""
        # A method so that subclasses can do paralle/async fetching of the metadata.
        raise NotImplementedError

    def _wheel_sort_key(
        self,
        wheel: Wheel,
    ) -> tuple[packaging.version.Version, int, packaging.utils.BuildTag]:
        """Create a sort key for a wheel.

        The key should lead to a sort of least to most preferred wheel.
        Preference is determined by the newest version, tag priority/specificity
        (as defined by self.tags), and then build tag.
        """
        # A separate method so subclasses can e.g. prefer older versions.
        for tag_priority, tag in enumerate(self.tags):  # noqa: B007
            if tag in wheel.tags:
                break
        else:
            raise ValueError("No compatible tags found for any wheels.")

        return wheel.version, len(self.tags) - tag_priority, wheel.build_tag or ()

    # This exists as method so that subclasses can e.g. prefer older versions.
    # Override for sdists.
    def sort_candidates(self, candidates: Iterable[Candidate]) -> Sequence[Candidate]:
        """Sort candidates from most to least preferred."""
        sorted_candidates = sorted(
            typing.cast(Iterable[WheelCandidate], candidates),
            key=lambda c: self._wheel_sort_key(c.wheel),
            reverse=True,
        )

        return sorted_candidates

    @typing.override
    def identify(
        self, requirement_or_candidate: Union[Requirement, Candidate]
    ) -> _Identifier:
        """Get the key for a requirement or candidate."""
        return requirement_or_candidate.identifier

    @typing.override
    def get_preference(
        self,
        identifier: _Identifier,
        resolutions: Mapping[_Identifier, Candidate],
        candidates: Mapping[_Identifier, Iterator[Candidate]],
        information: Mapping[  # type: ignore[override]
            _Identifier, Iterator[_RequirementInformation[Requirement, Candidate]]
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
        return (
            requirement.identifier == candidate.identifier
            and candidate.version in requirement.req.specifier
        )

    def _filter_candidates(
        self, candidates: Iterable[Candidate]
    ) -> Iterable[Candidate]:
        """Filter candidates based on environment details."""
        return filter(
            lambda c: c.is_env_compatible(environment=self.environment, tags=self.tags),
            candidates,
        )

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
