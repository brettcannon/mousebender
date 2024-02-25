"""Install packages from a lock file."""
from typing import Any

import packaging.markers
import packaging.tags
import packaging.version


def find_matches(lock_file_contents: dict[str, Any]) -> list[dict[str, Any]]:
    """Find a lock file entry that exactly matches the current environment."""
    # markers = packaging.markers.default_environment()
    tags = frozenset(packaging.tags.sys_tags())

    matches = []
    for lock_entry in lock_file_contents["lock"]:
        if not all(
            packaging.markers.Marker(marker).evaluate()
            for marker in lock_entry["markers"]
        ):
            continue

        for tag in lock_entry["tags"]:
            tag_set = packaging.tags.parse_tag(tag)
            if not any(triple in tags for triple in tag_set):
                break
        else:
            matches.append(lock_entry)

    return matches
