"""Generate a lock file."""
import functools
import json
from typing import Sequence

import resolvelib.resolvers

from . import resolve


def _dict_to_inline_table(dict_: dict) -> str:
    """Convert a dictionary to an inline TOML table."""
    items = []
    for key in sorted(dict_):
        items.append(f"{key} = {dict_[key]!r}")
    return f"{{ {', '.join(items)} }}"


@functools.singledispatch
def project_file_to_toml(file: resolve.ProjectFile) -> str:
    """Convert a project file to its TOML lock representation."""
    raise NotImplementedError(f"unrecongized project file type: {type(file)}")


# XXX `direct` is statically specified.
_WHEEL_TEMPLATE = """\
[[lock.wheel]]
filename = "{filename}"
origin = "{url}"
hashes = {hashes}
direct = false"""


@project_file_to_toml.register
def _(file: resolve.WheelFile) -> str:
    """Convert a wheel file to its TOML lock representation."""
    wheel = _WHEEL_TEMPLATE.format(
        filename=file.details["filename"],
        url=file.details["url"],
        hashes=_dict_to_inline_table(file.details["hashes"]),
    )

    requires_python = None
    if details_requires := file.details.get("requires-python"):
        requires_python = repr(details_requires)
    elif metadata_requires := getattr(file.metadata, "requires_python", None):
        requires_python = repr(str(metadata_requires))

    if requires_python:
        wheel += f"\nrequires-python = {requires_python}"

    return wheel + "\n"


_LOCK_TEMPLATE = """\
[[lock]]
markers = {markers}
tags = {tags}

{wheels}
"""


def generate_lock(
    provider: resolve.WheelProvider, resolution: resolvelib.resolvers.Result
) -> str:
    """Generate a lock file entry."""
    markers = _dict_to_inline_table(provider.markers)
    tags = f"[{', '.join(map(repr, map(str, provider.tags)))}]"

    dependencies = {}  # type: ignore
    seen = set()
    queue = list(resolution.graph.iter_children(None))
    for distro in queue:
        if distro in seen:
            continue
        seen.add(distro)
        children = dependencies.setdefault(
            distro, {"parents": set(), "children": set()}
        )["children"]
        for child in resolution.graph.iter_children(distro):
            children.add(child)
            parents = dependencies.setdefault(
                child, {"parents": set(), "children": set()}
            )["parents"]
            parents.add(distro)
            queue.append(child)

    wheels = []
    for id_ in sorted(dependencies):
        candidate = resolution.mapping[id_]
        wheel = project_file_to_toml(candidate.file)
        wheel_dependencies = sorted(dependencies[id_]["children"])
        wheel_dependency_names = []
        for name, extras in wheel_dependencies:
            # XXX what to do with extras?
            wheel_dependency_names.append(name)
        wheel += f"dependencies = {json.dumps(wheel_dependency_names)}"
        wheels.append(wheel)

    return _LOCK_TEMPLATE.format(markers=markers, tags=tags, wheels="\n\n".join(wheels))


_FILE_TEMPLATE = """\
version = "1.0"

dependencies = {dependencies}

{locks}
"""


def generate_file_contents(dependencies: Sequence[str], locks: Sequence[str]) -> str:
    """Generate the contents of a lock file."""
    return _FILE_TEMPLATE.format(
        dependencies=json.dumps(sorted(dependencies)), locks="\n\n".join(locks)
    ).strip()
