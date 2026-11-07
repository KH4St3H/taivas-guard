"""Endpoints for rules that experts write: list, save as a new version, preview on a stored issue, apply."""
from collections import Counter
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, exists, func, or_, select

from .. import events
from ..config import get_settings
from ..db import session_scope
from ..models import Artifact, Case, CaseOccurrence, CustomRule, CustomRuleVersion
from ..schemas import _Orm
from ..service import require_api_key
from ..sync.sources import SPACE
from .custom_rules import TITLE_FIELDS, DeclarativeRule, RuleDefinition, RuleSpec, describe, m4_service_names, rule_id_for
from .m4 import load_m4_rows
from .issue_cache import stored_issue as _issue

router = APIRouter(prefix="/rules", tags=["rules"])
PREVIEW_ROWS = 50


class RuleVersionOut(_Orm):
    version: int
    name: str
    description: str
    enabled: bool
    severity: str
    title_template: str
    definition: dict[str, Any]
    saved_by: str
    note: str
    saved_at: datetime


class RuleOut(BaseModel):
    id: int
    rule_id: str
    name: str
    description: str
    domain: str
    enabled: bool
    version: int
    severity: str
    title_template: str
    definition: RuleDefinition
    conditions: list[str]
    case_count: int
    created_at: datetime
    updated_at: datetime
    versions: list[RuleVersionOut] = []


class RuleSave(RuleSpec):
    enabled: bool = True
    saved_by: str = ""
    note: str = ""


class PreviewIn(BaseModel):
    spec: RuleSpec
    artifact_id: int


class PreviewHit(BaseModel):
    network: str | None
    adm: str | None
    title: str
    severity: str
    notice_ids: list[int]
    bands: int
    assignments: int


class PreviewOut(BaseModel):
    artifact_id: int
    issue_no: int
    total: int
    by_adm: dict[str, int]
    hits: list[PreviewHit]


class RuleOptions(BaseModel):
    m4_primary_services: list[str]
    title_fields: dict[str, str]


def _out(rule: CustomRule, case_count: int, versions: list[CustomRuleVersion] | None = None) -> RuleOut:
    definition = RuleDefinition(**rule.definition)
    return RuleOut(
        id=rule.id, rule_id=rule_id_for(rule.id), name=rule.name, description=rule.description, domain=rule.domain,
        enabled=rule.enabled, version=rule.version, severity=rule.severity, title_template=rule.title_template,
        definition=definition, conditions=describe(definition), case_count=case_count, created_at=rule.created_at,
        updated_at=rule.updated_at, versions=[RuleVersionOut.model_validate(v) for v in versions or []],
    )


def visible_cases(s):
    """Cases from a switched-off rule, or that a rule no longer raises in any stored issue, are left out.

    Only rules written by experts are filtered: built-in cases from before occurrences were kept have none.
    """
    off = [rule_id_for(i) for i in s.scalars(select(CustomRule.id).where(~CustomRule.enabled))]
    custom = Case.rule_id.like("custom-%")
    current = exists().where(CaseOccurrence.case_id == Case.id)
    return or_(~custom, and_(current, Case.rule_id.notin_(off)) if off else current)


def _case_counts(s) -> Counter:
    """Cases each rule raises in the stored issues now, whether or not the rule is switched on."""
    current = exists().where(CaseOccurrence.case_id == Case.id)
    rows = s.execute(select(Case.rule_id, func.count()).where(Case.rule_id.like("custom-%"), current).group_by(Case.rule_id))
    return Counter(dict(rows.all()))


def _snapshot(rule: CustomRule, saved_by: str, note: str) -> CustomRuleVersion:
    return CustomRuleVersion(
        rule_id=rule.id, version=rule.version, name=rule.name, description=rule.description, enabled=rule.enabled,
        severity=rule.severity, title_template=rule.title_template, definition=rule.definition, saved_by=saved_by, note=note,
    )


@router.get("", response_model=list[RuleOut])
def list_rules():
    with session_scope() as s:
        counts = _case_counts(s)
        return [_out(r, counts[rule_id_for(r.id)]) for r in s.scalars(select(CustomRule).order_by(CustomRule.id))]


@router.get("/options", response_model=RuleOptions)
def rule_options():
    return RuleOptions(m4_primary_services=m4_service_names(get_settings()), title_fields=TITLE_FIELDS)


@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(rule_id: int):
    with session_scope() as s:
        rule = s.get(CustomRule, rule_id)
        if rule is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {rule_id}.")
        versions = list(s.scalars(select(CustomRuleVersion).where(CustomRuleVersion.rule_id == rule_id)
                                  .order_by(CustomRuleVersion.version.desc())))
        return _out(rule, _case_counts(s)[rule_id_for(rule.id)], versions)


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_rule(body: RuleSave):
    with session_scope() as s:
        rule = CustomRule(name=body.name, description=body.description, enabled=body.enabled, version=1,
                          severity=body.severity, title_template=body.title_template, definition=body.definition.model_dump())
        s.add(rule)
        s.flush()
        version = _snapshot(rule, body.saved_by, body.note or "Created")
        s.add(version)
        s.flush()  # fills the default timestamps before they are returned
        return _out(rule, 0, [version])


@router.put("/{rule_id}", response_model=RuleOut, dependencies=[Depends(require_api_key)])
def update_rule(rule_id: int, body: RuleSave):
    """Saves a new version when anything changed. Cases change only when issues are screened again."""
    with session_scope() as s:
        rule = s.get(CustomRule, rule_id)
        if rule is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No rule {rule_id}.")
        new = dict(name=body.name, description=body.description, enabled=body.enabled, severity=body.severity,
                   title_template=body.title_template, definition=body.definition.model_dump())
        if any(getattr(rule, k) != v for k, v in new.items()):
            for k, v in new.items():
                setattr(rule, k, v)
            rule.version += 1
            s.add(_snapshot(rule, body.saved_by, body.note))
        s.flush()
        versions = list(s.scalars(select(CustomRuleVersion).where(CustomRuleVersion.rule_id == rule_id)
                                  .order_by(CustomRuleVersion.version.desc())))
        return _out(rule, _case_counts(s)[rule_id_for(rule.id)], versions)


@router.post("/preview", response_model=PreviewOut, dependencies=[Depends(require_api_key)])
def preview_rule(body: PreviewIn, limit: Annotated[int, Query(ge=1, le=500)] = PREVIEW_ROWS):
    """Runs a draft on one stored space issue. Saves nothing and opens no cases."""
    with session_scope() as s:
        artifact = s.get(Artifact, body.artifact_id)
        if artifact is None or artifact.domain != SPACE:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No space issue {body.artifact_id}.")
        mdb_path, issue_no = artifact.mdb_path, artifact.issue_no
    settings = get_settings()
    try:
        issue = _issue(body.artifact_id, mdb_path)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The file for issue {issue_no} is no longer stored.") from None
    rule = DeclarativeRule(settings, 0, 0, body.spec, load_m4_rows(settings.m4_filter_path))
    hits = list(rule.run(issue))
    order = {"high": 0, "medium": 1, "low": 2}
    hits.sort(key=lambda h: (order[h.severity], h.adm or "", h.network or ""))
    return PreviewOut(
        artifact_id=body.artifact_id, issue_no=issue_no, total=len(hits),
        by_adm=dict(Counter(h.adm or "unknown" for h in hits).most_common()),
        hits=[PreviewHit(network=h.network, adm=h.adm, title=h.title, severity=h.severity, notice_ids=h.notice_ids,
                         bands=len(h.details["bands"]), assignments=h.details["matched_assignment_count"]) for h in hits[:limit]],
    )


@router.post("/rescreen", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_api_key)])
def rescreen_space_issues() -> dict[str, Any]:
    """Queues every stored space issue, so cases follow the current rules. Built-in rules run too."""
    with session_scope() as s:
        artifacts = list(s.scalars(select(Artifact).where(Artifact.domain == SPACE).order_by(Artifact.issue_no)))
        for a in artifacts:
            a.screen_status = "pending"
            events.publish(s, events.ISSUE_FETCHED, {"artifact_id": a.id})
        return {"status": "queued", "issues": sorted({a.issue_no for a in artifacts})}
