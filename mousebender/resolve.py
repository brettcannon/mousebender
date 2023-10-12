"""An API for wheel-based requirement resolution."""
from __future__ import annotations

from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
)

import packaging.utils
import resolvelib.providers
from typing_extensions import Self

Identifier = tuple[
    packaging.utils.NormalizedName, frozenset[packaging.utils.NormalizedName]
]


class Requirement(Protocol):
    """Protocol for a distribution requirement."""

    identifier: Identifier

    def is_satisfied_by(self, candidate: Candidate, /) -> bool:
        """Check if the candidate satisfies this requirement."""


class GeneralRequirement(Requirement):
    """A general requirement."""

    _req: packaging.requirements.Requirement
    name: packaging.utils.NormalizedName
    extras: frozenset[packaging.utils.NormalizedName]
    specifier: packaging.specifiers.SpecifierSet

    def __init__(self, req: packaging.requirements.Requirement, /) -> None:
        """Initialize from the provided requirement."""
        self.name = packaging.utils.NormalizedName(req.name)
        self.extras = frozenset(map(packaging.utils.canonicalize_name, req.extras))
        self.identifier = self.name, self.extras
        self.specifier = req.specifier

    def is_satisfied_by(self, candidate: Candidate, /) -> bool:
        """Check if the candidate satisfies this requirement.

        It is assumed that all markers have already been evaluated as
        acceptable.
        """
        if self.name != candidate.name:
            return False
        elif self.extras != candidate.extras:
            return False
        return self.specifier.contains(candidate.version)


class ExactRequirement(Requirement):
    """An requirement for an exact version."""

    name: packaging.utils.NormalizedName
    version: packaging.version.Version

    def __init__(
        self, name: packaging.utils.NormalizedName, version: packaging.version.Version
    ) -> None:
        self.name = name
        self.version = version
        self.identifier = name, frozenset()

    def is_satisfied_by(self, candidate: Candidate, /) -> bool:
        """Check if the candidate satisfies this requirement."""
        if self.name != candidate.name:
            return False
        elif candidate.extras:
            return False
        return self.version == candidate.version


class Candidate(Protocol):
    """A protocol for a candidate to a distribution requirement."""

    name: packaging.utils.NormalizedName
    version: packaging.version.Version
    extras: frozenset[packaging.utils.NormalizedName]
    identifier: Identifier

    def __eq__(self, other: Self) -> bool:
        if self.identifier != other.identifier:
            return False
        return self.version == other.version

    @property
    def identifier(self) -> Identifier:  # noqa: D102
        return self.name, self.extras

    def requirements(self) -> Iterable[Requirement]:
        """Get the requirements of this candidate."""


class WheelCandidate(Candidate):
    """A candidate based on a wheel file."""

    extras = frozenset()

    def __init__(self, metadata: packaging.metadata.Metadata) -> None:
        """Initialize from the provided metadata."""
        self.name = metadata.name
        self.version = metadata.version
        self.metadata = metadata

    def requirements(self) -> Iterable[Requirement]:
        """Get the requirements of this candidate wheel."""
        # XXX


class ExtrasCandidate(Candidate):
    """A virtual candidate for a requirement which specifies extras."""

    # XXX def __init__(...) -> None:

    def requirements(self) -> Iterable[Requirement]:
        """Get the requirements for this candidate with all of its extras.

        Requirements include the exact version of the required distribution,
        but without extras. This is to help the resolver "understand" the
        relationship of requirements with extras back to the distribution
        itself.
        """
        # XXX ExactRequirement
        # XXX Requirements coming from extras


KT = TypeVar("KT")  # Identifier.
RT = TypeVar("RT")  # Requirement.
CT = TypeVar("CT")  # Candidate.

Matches = Union[Iterable[CT], Callable[[], Iterable[CT]]]


class RequirementInformation(tuple, Generic[RT, CT]):  # noqa: D101
    requirement: RT
    parent: Optional[CT]


class Preference(Protocol):  # noqa: D101
    def __lt__(self, __other: Any) -> bool:  # noqa: D105, ANN401
        ...


class WheelProvider(resolvelib.providers.AbstractProvider):
    """A provider for resolving requirements based on wheels."""

    def identify(
        self, requirement_or_candidate: Union[Requirement, Candidate]
    ) -> Identifier:
        """Get the key for a requirement or candidate."""
        return requirement_or_candidate.identifier

    def get_preference(
        self,
        identifier: Identifier,
        resolutions: Mapping[Identifier, Candidate],
        candidates: Mapping[Identifier, Iterator[Candidate]],
        information: Mapping[
            Identifier, Iterator[RequirementInformation[Requirement, Candidate]]
        ],
        backtrack_causes: Sequence[RequirementInformation[Requirement, Candidate]],
    ) -> Preference:
        """Calculate the preference to solve for a requirement.

        Provide a sort key based on the number of candidates for the
        requirement.
        """
        candidate_count = 0
        for _ in candidates[identifier]:
            candidate_count += 1
        return candidate_count

    # Requirement -> Candidate
    def find_matches(
        self,
        identifier: Identifier,
        requirements: Mapping[Identifier, Iterator[Requirement]],
        incompatibilities: Mapping[Identifier, Iterator[Candidate]],
    ) -> Matches:
        """Get the potential candidates for a requirement.

        This involves getting all potential wheels for a distribution and
        checking if they meet all requirements while not being considered
        an incompatible candidate.
        """
        # XXX get all the available wheels for the distribution
        # XXX filter by wheel tags
        # XXX filter them out based on incompatibilities
        # XXX if extras: ExtrasCandidate
        # XXX sort

    def is_satisfied_by(self, requirement: Requirement, candidate: Candidate) -> bool:
        """Check if a candidate satisfies a requirement."""
        return requirement.is_satisfied_by(candidate)

    # Candidate -> Requirement
    def get_dependencies(self, candidate: Candidate) -> Iterable[Requirement]:
        """Get the requirements of a candidate."""
        # XXX filter out by markers
        return candidate.requirements()
