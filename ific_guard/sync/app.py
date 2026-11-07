"""Sync service: keeps the local copy of Space and Terrestrial IFIC databases up to date."""
import asyncio
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select

from ..db import session_scope
from ..models import Artifact, SyncRun
from ..schemas import ArtifactOut, SyncRunOut
from ..service import create_app, require_api_key
from .runner import _running, freshness, run_sync, scheduled_pass

router = APIRouter()


@router.get("/issues", response_model=list[ArtifactOut])
def list_issues(domain: str | None = None, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    query = select(Artifact).order_by(Artifact.issue_no.desc(), Artifact.id.desc()).limit(limit)
    if domain:
        query = query.where(Artifact.domain == domain)
    with session_scope() as s:
        return list(s.scalars(query))


@router.get("/runs", response_model=list[SyncRunOut])
def list_runs(limit: Annotated[int, Query(ge=1, le=200)] = 20):
    with session_scope() as s:
        return list(s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(limit)))


@router.get("/status")
def sync_status() -> dict:
    return {"running": _running.locked(), "domains": freshness()}


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def trigger_sync(background: BackgroundTasks) -> dict[str, str]:
    if _running.locked():
        raise HTTPException(status.HTTP_409_CONFLICT, "A sync is already running.")
    background.add_task(run_sync, "manual")
    return {"status": "started"}


async def _scheduler() -> None:
    while True:
        await asyncio.sleep(await asyncio.to_thread(scheduled_pass))


app = create_app("ific-sync", router, [_scheduler])
