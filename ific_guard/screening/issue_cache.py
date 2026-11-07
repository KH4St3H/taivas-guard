"""Stored issue files read for requests: rule previews and full station lists. Screening itself doesn't use it."""
from dataclasses import dataclass, field
from functools import lru_cache
from collections.abc import Callable
from typing import Any

from .space import MdbReader, SpaceIssue


@lru_cache(maxsize=1)
def stored_issue(artifact_id: int, mdb_path: str) -> SpaceIssue:
    """Keeps the last issue read in memory, so asking again about it is quick."""
    issue = SpaceIssue(MdbReader(mdb_path))
    issue.notices  # noqa: B018 (reads the tables now, inside the cache)
    return issue


class Unavailable(Exception):
    """What a request needs is missing. The message is for the reviewer; `status` is the HTTP status."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class CaseSource:
    case_id: int
    rule_id: str
    material_hash: str
    details: dict[str, Any] = field(compare=False)  # material_hash stands for it in cache keys
    artifact_id: int = 0
    mdb_path: str = ""
    issue_no: int = 0
    family_id: int = 0


def case_source(case_id: int, accepts: Callable[[CaseSource], bool] | None = None, refusal: str = "") -> CaseSource:
    """The stored issue that last changed a space case, and the notice family the case is about.

    `accepts` sees the case before its issue is looked up, so a case of the wrong kind gets `refusal` (404).
    """
    from sqlalchemy import select

    from ..db import session_scope
    from ..models import Artifact, Case, CaseOccurrence

    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise Unavailable(f"No case {case_id}.", 404)
        if accepts and not accepts(CaseSource(case.id, case.rule_id, case.material_hash, dict(case.details or {}))):
            raise Unavailable(refusal, 404)
        occurrences = list(s.scalars(select(CaseOccurrence).where(CaseOccurrence.case_id == case_id)))
        occurrence = next((o for o in occurrences if o.artifact_id == case.changed_artifact_id), None)
        if occurrence is None and occurrences:
            occurrence = max(occurrences, key=lambda o: o.artifact_id)
        if occurrence is None:
            raise Unavailable("No screened issue holds this case any more.", 409)
        artifact = s.get(Artifact, occurrence.artifact_id)
        if artifact is None or artifact.domain != "space":
            raise Unavailable("The issue this case came from is no longer stored.", 409)
        return CaseSource(case.id, case.rule_id, case.material_hash, dict(case.details or {}), artifact.id,
                          artifact.mdb_path, artifact.issue_no, int(occurrence.hit["family_id"]))


def load_issue(source: CaseSource) -> SpaceIssue:
    try:
        return stored_issue(source.artifact_id, source.mdb_path)
    except FileNotFoundError:
        raise Unavailable(f"The file for IFIC {source.issue_no} is no longer stored.", 409) from None
