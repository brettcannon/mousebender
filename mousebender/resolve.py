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


class _Candidate:
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


class _Requirement:
    """A requirement for a distribution."""

    identifier: _Identifier
    req: packaging.requirements.Requirement

    def __init__(self, req: packaging.requirements.Requirement, /) -> None:
        """Initialize from the provided requirement."""
        self.req = req
        name = packaging.utils.NormalizedName(req.name)
        extras = frozenset(map(packaging.utils.canonicalize_name, req.extras))
        self.identifier = name, extras

    def is_satisfied_by(self, wheel: Wheel) -> bool:
        """Check if a wheel satisfies the requirement."""
        name, extras = self.identifier
        # Markers should be unnecessary at this point as any incompatible
        # requirements have already been filtered out.
        return name == wheel.name and wheel.version in self.req.specifier


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
    def wheel_metadata(self, wheel: Wheel) -> packaging.metadata.RawMetadata:
        """Get the requirements of a wheel."""
        raise NotImplementedError

    def sort_wheels(self, wheels: Iterable[Wheel]) -> list[Wheel]:
        """Sort wheels from most to least preferred."""
        # XXX
        return list(wheels)

    @typing.override
    def identify(
        self, requirement_or_candidate: Union[_Requirement, _Candidate]
    ) -> _Identifier:
        """Get the key for a requirement or candidate."""
        return requirement_or_candidate.identifier

    @typing.override
    def get_preference(
        self,
        identifier: _Identifier,
        resolutions: Mapping[_Identifier, _Candidate],
        candidates: Mapping[_Identifier, Iterator[_Candidate]],
        information: Mapping[
            _Identifier, Iterator[_RequirementInformation[_Requirement, _Candidate]]
        ],
        backtrack_causes: Sequence[_RequirementInformation[_Requirement, _Candidate]],
    ) -> int:
        """Calculate the preference to solve for a requirement.

        Provide a sort key based on the number of candidates for the
        requirement.
        """
        # Since `candidates` contains iterators, we need to consume them to get
        # a count of items.
        return sum(1 for _ in candidates[identifier])

    # Requirement -> Candidate
    @typing.override
    def find_matches(
        self,
        identifier: _Identifier,
        requirements: Mapping[_Identifier, Iterator[_Requirement]],
        incompatibilities: Mapping[_Identifier, Iterator[_Candidate]],
    ) -> list[_Candidate]:
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

        filtered_wheels_by_req = filter(
            lambda w: all(r.is_satisfied_by(w) for r in requirements[identifier]),
            wheels,
        )
        incompat_candidates = frozenset(incompatibilities[identifier])
        filtered_wheels = filter(
            lambda w: w not in incompat_candidates, filtered_wheels_by_req
        )
        return [
            _Candidate(wheel, extras) for wheel in self.sort_wheels(filtered_wheels)
        ]

    def is_satisfied_by(self, requirement: _Requirement, candidate: _Candidate) -> bool:
        """Check if a candidate satisfies a requirement."""
        return (
            requirement.identifier == candidate.identifier
            and requirement.is_satisfied_by(candidate.wheel)
        )

    # Candidate -> Requirement
    @typing.override
    def get_dependencies(self, candidate: _Candidate) -> list[_Requirement]:
        """Get the requirements of a candidate."""
        requirements = []
        name, extras = candidate.identifier
        if extras:
            req = packaging.requirements.Requirement(
                f"{name}=={candidate.wheel.version}"
            )
            requirements.append(_Requirement(req))

        if not (metadata := candidate.wheel.metadata):
            raw_metadata = self.wheel_metadata(candidate.wheel)
            metadata = packaging.metadata.Metadata.from_raw(raw_metadata)

        for req in metadata.requires_dist:
            if req.marker is None:
                requirements.append(_Requirement(req))
            elif req.marker.evaluate(self.environment):
                requirements.append(_Requirement(req))
            elif extras and any(
                req.marker.evaluate(self.environment | {"extra": extra})
                for extra in extras
            ):
                requirements.append(_Requirement(req))

        return requirements
