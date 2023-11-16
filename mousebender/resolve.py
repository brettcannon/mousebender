"""An API for wheel-based requirement resolution."""
from __future__ import annotations

import abc
import operator
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
import resolvelib.providers

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
    metadata: Optional[packaging.metadata.Metadata]
    details: simple.ProjectFileDetails_1_0 | simple.ProjectFileDetails_1_1

    def __init__(
        self, details: simple.ProjectFileDetails_1_0 | simple.ProjectFileDetails_1_1
    ) -> None:
        self.details = details
        (
            self.name,
            self.version,
            self.build_tag,
            self.tags,
        ) = packaging.utils.parse_wheel_filename(details["filename"])
        self.metadata = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Wheel):
            return NotImplemented
        return self.details == other.details


class Candidate:
    """A candidate to satisfy a requirement."""

    identifier: _Identifier
    wheel: Wheel

    def __init__(
        self,
        wheel: Wheel,
        extras: Iterable[packaging.utils.NormalizedName] = frozenset(),
    ) -> None:
        self.wheel = wheel
        self.identifier = wheel.name, frozenset(extras)


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


_RT = TypeVar("_RT")  # Requirement.
_CT = TypeVar("_CT")  # Candidate.


class _RequirementInformation(tuple, Generic[_RT, _CT]):
    requirement: _RT
    parent: Optional[_CT]


class WheelProvider(resolvelib.providers.AbstractProvider, abc.ABC):
    """A provider for resolving requirements based on wheels."""

    environment: dict[str, str]  # packaging.markers has not TypedDict for this.
    tags: list[packaging.tags.Tag]
    # Assumed to have already been filtered down to only wheels that have any
    # chance to work with the specified environment details.
    _wheel_cache: dict[packaging.utils.NormalizedName, Collection[Wheel]]

    def __init__(
        self,
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
        self._wheel_cache = {}

    @abc.abstractmethod
    def available_wheels(
        self, name: packaging.utils.NormalizedName
    ) -> simple.ProjectDetails:
        """Get the available wheels for a distribution."""
        raise NotImplementedError

    @abc.abstractmethod
    def fetch_wheel_metadata(self, wheels: Iterable[Wheel]) -> None:
        """Fetch the metadata of a wheel and add it in-place."""
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

    def sort_candidates(self, candidates: Iterable[Candidate]) -> list[Candidate]:
        """Sort candidates from most to least preferred."""
        # A method so that subclasses can e.g. prefer older versions.
        return sorted(
            candidates, key=lambda c: self._wheel_sort_key(c.wheel), reverse=True
        )

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
        information: Mapping[
            _Identifier, Iterator[_RequirementInformation[Requirement, Candidate]]
        ],
        backtrack_causes: Sequence[_RequirementInformation[Requirement, Candidate]],
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
            and candidate.wheel.version in requirement.req.specifier
        )

    # Requirement -> Candidate
    @typing.override
    def find_matches(
        self,
        identifier: _Identifier,
        requirements: Mapping[_Identifier, Iterator[Requirement]],
        incompatibilities: Mapping[_Identifier, Iterator[Candidate]],
    ) -> list[Candidate]:
        """Get the potential candidates for a requirement.

        This involves getting all potential wheels for a distribution and
        checking if they meet all requirements while not being considered
        an incompatible candidate.
        """
        name, extras = identifier
        if name in self._wheel_cache:
            wheels = self._wheel_cache[name]
        else:
            possible_wheels = self.available_wheels(name)
            python_version = packaging.version.parse(self.environment["python_version"])
            wheels = []
            for wheel_file_details in possible_wheels["files"]:
                wheel = Wheel(wheel_file_details)
                if "requires-python" in wheel_file_details:
                    requires_python = packaging.specifiers.SpecifierSet(
                        wheel_file_details["requires-python"]
                    )
                    # TODO need to care that "python_version" doesn't have release level?
                    if python_version not in requires_python:
                        continue
                if any(tag in self.tags for tag in wheel.tags):
                    wheels.append(wheel_file_details)
                    break
            self._wheel_cache[name] = wheels

        candidates = [Candidate(wheel, extras) for wheel in wheels]
        filtered_candidates_by_req = filter(
            lambda c: all(self.is_satisfied_by(r, c) for r in requirements[identifier]),
            candidates,
        )
        incompat_candidates = frozenset(incompatibilities[identifier])
        filtered_candidates = filter(
            lambda c: c not in incompat_candidates, filtered_candidates_by_req
        )

        sorted_candidates = self.sort_candidates(filtered_candidates)

        # Wait as long as possible to fetch the metadata while being able to do it in
        # bulk to support parallel/async downloading.
        missing_metadata = filter(lambda c: c.wheel.metadata is None, sorted_candidates)
        self.fetch_wheel_metadata(map(operator.attrgetter("wheel"), missing_metadata))

        return sorted_candidates

    # Candidate -> Requirement
    @typing.override
    def get_dependencies(self, candidate: Candidate) -> list[Requirement]:
        """Get the requirements of a candidate."""
        assert candidate.wheel.metadata is not None

        requirements = []
        name, extras = candidate.identifier
        if extras:
            req = packaging.requirements.Requirement(
                f"{name}=={candidate.wheel.version}"
            )
            requirements.append(Requirement(req))

        for req in candidate.wheel.metadata.requires_dist:
            if req.marker is None:
                requirements.append(Requirement(req))
            elif req.marker.evaluate(self.environment):
                requirements.append(Requirement(req))
            elif extras and any(
                req.marker.evaluate(self.environment | {"extra": extra})
                for extra in extras
            ):
                requirements.append(Requirement(req))

        return requirements
