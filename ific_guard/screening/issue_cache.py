"""Stored issue files read for requests: rule previews and full station lists. Screening itself doesn't use it."""
from functools import lru_cache

from .space import MdbReader, SpaceIssue


@lru_cache(maxsize=1)
def stored_issue(artifact_id: int, mdb_path: str) -> SpaceIssue:
    """Keeps the last issue read in memory, so asking again about it is quick."""
    issue = SpaceIssue(MdbReader(mdb_path))
    issue.notices  # noqa: B018 (reads the tables now, inside the cache)
    return issue
