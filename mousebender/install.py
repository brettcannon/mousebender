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


def _tags_score(entry: dict[str, Any]) -> int:
    """Score a list of tag sets."""
    tag_sets = entry["tags"]
    sys_tags = list(packaging.tags.sys_tags())
    total = 0
    for tag_set in tag_sets:
        tag_triples = packaging.tags.parse_tag(tag_set)
        triple_scores = [0]
        for triple in tag_triples:
            try:
                triple_scores.append(sys_tags.index(triple))
            except ValueError:
                pass
        total += max(triple_scores)
    return total // len(tag_sets)


def best_match(matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Find the best match from a list of lock file entries."""
    return max(matches, key=_tags_score)
