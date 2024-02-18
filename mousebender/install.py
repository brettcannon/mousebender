"""Install packages from a lock file."""
import platform
from typing import Any

import packaging.markers
import packaging.tags
import packaging.version


def strict_match(lock_file_contents: dict[str, Any]) -> dict[str, Any] | None:
    """Find a lock file entry that exactly matches the current environment."""
    markers = packaging.markers.default_environment()
    tags = list(map(str, packaging.tags.sys_tags()))

    for lock_entry in lock_file_contents["lock"]:
        if lock_entry["markers"] == markers and lock_entry["tags"] == tags:
            return lock_entry
    else:
        return None


def compatible_match(lock_file_contents: dict[str, Any]) -> dict[str, Any] | None:
    """Fine a lock file entry that is compatible with the current environment.

    Compatibility is defined as the tags of the lock file entry intersecting
    the environment's tags and all files being compatible with the running
    interpreter's Python version.
    """
    env_tags = frozenset(packaging.tags.sys_tags())
    python_version = packaging.version.Version(platform.python_version())

    for lock_entry in lock_file_contents["lock"]:
        lock_tags = frozenset(lock_entry["tags"])
        if env_tags.issuperset(lock_tags):
            for wheel in lock_entry["wheel"]:
                requires_python = packaging.specifiers.SpecifierSet(
                    wheel.get("requires-python", "")
                )
                if python_version not in requires_python:
                    break
            else:
                return lock_entry
    else:
        return None
