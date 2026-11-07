"""Screening service: turns fetched issues into cases and serves them for expert review."""
import csv
import io
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from .. import events
from ..db import session_scope
from ..llm import Draft, configured_model, draft, generate
from ..llm.template import CaseView
from ..models import Artifact, Case
from ..schemas import CaseOut, CaseReview, CaseSummary
from ..service import consume, create_app, require_api_key
from .coverage import coverage
from .case_stations import CSV_COLUMNS, NoStationList, counts, csv_row, matching, station_list
from .engine import handle_issue_fetched
from .rules_api import router as rules_router, visible_cases

router = APIRouter()
router.include_router(rules_router)


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(
    severity: str | None = None,
    rule_id: str | None = None,
    review_status: str | None = None,
    adm: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    query = select(Case).order_by(Case.comment_deadline.asc(), Case.id.desc()).limit(limit)
    for column, value in ((Case.severity, severity), (Case.rule_id, rule_id), (Case.review_status, review_status), (Case.adm, adm)):
        if value:
            query = query.where(column == value)
    with session_scope() as s:
        return list(s.scalars(query.where(visible_cases(s))))


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: int):
    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No case {case_id}.")
        return case


def _station_list(case_id: int):
    try:
        return station_list(case_id)
    except NoStationList as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.get("/cases/{case_id}/stations")
def case_stations(
    case_id: int,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    licence: str | None = None,
) -> dict:
    """Every station a case overlaps, worst first, recomputed from the issue file. The case itself keeps a sample.

    The first request for a case can take minutes on a large register; later pages come from memory.
    """
    result = _station_list(case_id)
    rows = list(matching(result.records, status_filter, licence))
    return {
        "total": len(result.records), "matching": len(rows), "offset": offset, "rows": rows[offset:offset + limit],
        "counts": counts(result.records), "not_visible": result.not_visible, "issue_no": result.issue_no,
        "dataset": result.dataset, "dataset_changed": result.dataset_changed,
    }


@router.get("/cases/{case_id}/stations.csv")
def case_stations_csv(
    case_id: int, status_filter: Annotated[str | None, Query(alias="status")] = None, licence: str | None = None,
) -> StreamingResponse:
    result = _station_list(case_id)

    def lines() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for n, r in enumerate(matching(result.records, status_filter, licence), 1):
            writer.writerow(csv_row(r))
            if n % 10_000 == 0:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    name = f"case-{case_id}-stations-ific{result.issue_no}.csv"
    return StreamingResponse(lines(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/cases/{case_id}/coverage")
def case_coverage(case_id: int) -> dict:
    """Where over Finland the case's satellite can reach, its worst-case pfd, and the listed stations in its bands.

    Computed from the issue file on request; nothing is stored on the case.
    """
    try:
        return coverage(case_id)
    except NoStationList as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.get("/cases/{case_id}/draft", response_model=Draft)
def get_case_draft(case_id: int, use_llm: bool = False, x_api_key: Annotated[str | None, Header()] = None):
    """An explanation and draft letter for expert review. Stores and sends nothing.

    Returns the deterministic template by default. `use_llm=true` can cost money, so it needs the API key.
    """
    if use_llm:
        require_api_key(x_api_key)
    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No case {case_id}.")
        view = CaseView.of(case)
    return generate(view, configured_model()) if use_llm else draft(view)


@router.patch("/cases/{case_id}", response_model=CaseOut, dependencies=[Depends(require_api_key)])
def review_case(case_id: int, review: CaseReview):
    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No case {case_id}.")
        case.review_status, case.review_note = review.review_status, review.review_note
        return case


@router.post(
    "/issues/{artifact_id}/screen", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)]
)
def rescreen(artifact_id: int) -> dict[str, str]:
    """Queues an issue again, for example after a rule changes."""
    with session_scope() as s:
        artifact = s.get(Artifact, artifact_id)
        if artifact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No artifact {artifact_id}.")
        artifact.screen_status = "pending"
        events.publish(s, events.ISSUE_FETCHED, {"artifact_id": artifact_id})
    return {"status": "queued"}


async def _worker() -> None:
    await consume(events.ISSUE_FETCHED, handle_issue_fetched)


app = create_app("ific-screening", router, [_worker])
