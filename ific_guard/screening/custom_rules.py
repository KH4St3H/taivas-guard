"""Screening rules that experts write as data, run beside the built-in rules.

A rule is a set of conditions that must all hold. Filing conditions pick satellites; assignment
conditions pick the frequencies that count. A family is raised when at least one assignment
of a matching notice passes. Nothing here runs user-supplied code: the definition is validated
data, and the title is a template with a fixed set of fields.
"""
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from string import Formatter
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..config import Settings
from .m4 import M4Row, load_m4_rows
from .rules import Hit, _deadline, _families, visible_from_finland
from .space import SATELLITE_NOTICE_TYPES, SpaceIssue

RULE_PREFIX = "custom-"
TITLE_FIELDS = {"network": "network name", "adm": "notifying administration", "bands": "number of M4 bands matched", "rule": "rule name"}
MAX_ASSIGNMENTS_LISTED = 100

Tri = Literal["any", "yes", "no"]


class FrequencyRange(BaseModel):
    low_mhz: float = Field(ge=0)
    high_mhz: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> "FrequencyRange":
        if self.high_mhz <= self.low_mhz:
            raise ValueError(f"The range {self.low_mhz}-{self.high_mhz} MHz must end above where it starts.")
        return self


class M4Condition(BaseModel):
    """Which rows of the Finnish table (Regulation M4) the frequency must fall in."""

    space_to_earth: Tri = "any"  # "no": M4 gives no space-to-Earth allocation there
    earth_to_space: Tri = "any"
    terrestrial_primary: Tri = "any"
    passive: Tri = "any"
    primary_services_any: list[str] = []  # empty: any service

    def is_open(self) -> bool:
        return self == M4Condition()

    def accepts(self, row: M4Row) -> bool:
        flags = ((self.space_to_earth, row.space_down_allocated), (self.earth_to_space, row.space_up_allocated),
                 (self.terrestrial_primary, row.terrestrial_primary), (self.passive, row.passive))
        if any(want != "any" and (want == "yes") != have for want, have in flags):
            return False
        if self.primary_services_any:
            services = {s.strip() for s in row.primary_services.split(";")}
            return any(s in services for s in self.primary_services_any)
        return True


class RuleDefinition(BaseModel):
    orbit: Literal["any", "gso", "ngso"] = "any"
    visible_from_finland: bool = True
    adm_in: list[str] = []
    adm_not_in: list[str] = []
    provision_in: list[str] = []
    direction: Literal["transmit", "receive", "either"] = "transmit"
    frequency_ranges: list[FrequencyRange] = []
    m4: M4Condition = M4Condition()

    @field_validator("adm_in", "adm_not_in")
    @classmethod
    def _adm_codes(cls, values: list[str]) -> list[str]:
        codes = sorted({v.strip().upper() for v in values if v.strip()})
        if bad := [c for c in codes if not (c.isalnum() and len(c) <= 3)]:
            raise ValueError(f"Administration codes are up to three letters, such as USA: {', '.join(bad)}.")
        return codes

    @field_validator("provision_in")
    @classmethod
    def _provisions(cls, values: list[str]) -> list[str]:
        return sorted({v.strip() for v in values if v.strip()})


class RuleSpec(BaseModel):
    """What an expert edits. The service adds the id, version and history."""

    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    severity: Literal["high", "medium", "low"]
    title_template: str = Field(default="{network} ({adm}) matches {rule}", min_length=1, max_length=300)
    definition: RuleDefinition = RuleDefinition()

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Give the rule a name.")
        return value.strip()

    @field_validator("title_template")
    @classmethod
    def _template(cls, value: str) -> str:
        try:
            parts = [(f, spec, conv) for _, f, spec, conv in Formatter().parse(value) if f is not None]
        except ValueError as exc:
            raise ValueError(f"The title can't be read: {exc}. Write braces as {{{{ and }}}}.") from None
        if any(spec or conv for _, spec, conv in parts):
            raise ValueError("Title fields take no formatting, so write {bands}, not {bands:3}.")
        fields = [f for f, _, _ in parts]
        if unknown := sorted({str(f) for f in fields if f not in TITLE_FIELDS}):
            allowed = ", ".join("{" + f + "}" for f in TITLE_FIELDS)
            raise ValueError(f"Unknown title field(s): {', '.join(unknown)}. Use {allowed}.")
        return value


def rule_id_for(db_id: int) -> str:
    return f"{RULE_PREFIX}{db_id}"


def is_custom(rule_id: str) -> bool:
    return rule_id.startswith(RULE_PREFIX)


def _range(r: FrequencyRange) -> str:
    return f"{r.low_mhz:g}-{r.high_mhz:g} MHz"


def describe(d: RuleDefinition) -> list[str]:
    """The conditions in words, for the case, the letter template and the rules page."""
    out = []
    orbit = {"any": "any satellite", "gso": "a GSO satellite", "ngso": "a non-GSO satellite"}[d.orbit]
    out.append(f"The filing is for {orbit}" + (" whose orbit can be seen from Finland" if d.visible_from_finland else ""))
    if d.adm_in:
        out.append(f"Notified by {', '.join(d.adm_in)}")
    if d.adm_not_in:
        out.append(f"Not notified by {', '.join(d.adm_not_in)}")
    if d.provision_in:
        out.append(f"Published under provision {', '.join(d.provision_in)}")
    verb = {"transmit": "transmits", "receive": "receives", "either": "transmits or receives"}[d.direction]
    where = f" in {', '.join(_range(r) for r in d.frequency_ranges)}" if d.frequency_ranges else ""
    out.append(f"The satellite {verb}{where}")
    m = d.m4
    words = {"yes": "", "no": "no "}
    m4 = []
    if m.space_to_earth != "any":
        m4.append(f"{words[m.space_to_earth]}space-to-Earth allocation")
    if m.earth_to_space != "any":
        m4.append(f"{words[m.earth_to_space]}Earth-to-space allocation")
    if m.terrestrial_primary != "any":
        m4.append(f"{words[m.terrestrial_primary]}primary terrestrial use")
    if m.passive != "any":
        m4.append("a passive or radio astronomy service" if m.passive == "yes" else "no passive service")
    if m.primary_services_any:
        m4.append(f"a primary service among {', '.join(m.primary_services_any)}")
    if m4:
        out.append(f"There, M4 gives {'; '.join(m4)}")
    return out


@dataclass
class _Match:
    groups: set[int]
    assignments: list[dict[str, Any]]


class DeclarativeRule:
    """Runs one saved rule. `id` is the case rule_id, so cases stay with the rule across edits."""

    def __init__(self, settings: Settings, db_id: int, version: int, spec: RuleSpec, m4_rows: list[M4Row]):
        self.settings, self.db_id, self.version, self.spec = settings, db_id, version, spec
        self.id = rule_id_for(db_id)
        self.m4_rows = sorted(m4_rows, key=lambda r: r.low_mhz)

    def _segments(self, low: float, high: float) -> list[tuple[float, float]]:
        ranges = self.spec.definition.frequency_ranges
        if not ranges:
            return [(low, high)]
        # Same overlap test as the M4 rule, so a single-frequency assignment inside a range counts.
        return [(max(low, r.low_mhz), min(high, r.high_mhz)) for r in ranges if low < r.high_mhz and high > r.low_mhz]

    def _rows(self, low: float, high: float) -> list[M4Row]:
        return [r for r in self.m4_rows if low < r.high_mhz and high > r.low_mhz]

    def _filing_matches(self, notice) -> tuple[bool, str | None]:
        d = self.spec.definition
        if d.orbit == "gso" and notice.ntc_type != "G" or d.orbit == "ngso" and notice.ntc_type != "N":
            return False, None
        if d.adm_in and notice.adm not in d.adm_in or d.adm_not_in and notice.adm in d.adm_not_in:
            return False, None
        if d.provision_in and notice.provision not in d.provision_in:
            return False, None
        if d.visible_from_finland:
            visible, why = visible_from_finland(notice, self.settings)
            return visible, why if visible else None
        return True, None

    def run(self, issue: SpaceIssue) -> Iterable[Hit]:
        d = self.spec.definition
        wanted = {"transmit": {"E"}, "receive": {"R"}, "either": {"E", "R"}}[d.direction]
        satellites = (n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES)
        for family_id, notices in _families(satellites).items():
            bands: dict[M4Row, set[int]] = defaultdict(set)
            match = _Match(set(), [])
            reasons: set[str] = set()
            for notice in notices:
                ok, why = self._filing_matches(notice)
                if not ok:
                    continue
                for a in notice.assignments:
                    if a.get("emi_rcp") not in wanted or a.get("freq_min") is None or a.get("freq_max") is None:
                        continue
                    hit_here = False
                    for low, high in self._segments(float(a["freq_min"]), float(a["freq_max"])):
                        rows = self._rows(low, high)
                        if not d.m4.is_open():
                            rows = [r for r in rows if d.m4.accepts(r)]
                            if not rows:
                                continue
                        hit_here = True
                        for r in rows:
                            bands[r].add(int(a["grp_id"]))
                    if hit_here:
                        match.groups.add(int(a["grp_id"]))
                        match.assignments.append({
                            "group_id": int(a["grp_id"]), "freq_min_mhz": float(a["freq_min"]),
                            "freq_max_mhz": float(a["freq_max"]), "direction": "transmit" if a["emi_rcp"] == "E" else "receive",
                        })
                        if why:
                            reasons.add(why)
            if not match.groups:
                continue
            head = notices[0]
            values = {"network": head.name or str(head.ntc_id), "adm": head.adm or "unknown administration",
                      "bands": len(bands), "rule": self.spec.name}
            assignments = sorted(match.assignments, key=lambda x: (x["freq_min_mhz"], x["group_id"]))
            yield Hit(
                rule_id=self.id,
                family_id=family_id,
                severity=self.spec.severity,
                title=self.spec.title_template.format_map(values),
                adm=head.adm,
                network=head.name,
                notice_ids=sorted(n.ntc_id for n in notices),
                details={
                    "custom_rule": {"id": self.db_id, "name": self.spec.name, "version": self.version},
                    "conditions": describe(d),
                    "definition": d.model_dump(),
                    "bands": [
                        {
                            "low_mhz": r.low_mhz, "high_mhz": r.high_mhz, "m4_primary_services": r.primary_services,
                            "finnish_use": r.finnish_use, "passive": r.passive, "m4_table_pages": r.pages,
                            "m4_space_to_earth": "allocated" if r.space_down_allocated else "not allocated",
                            "m4_earth_to_space": "allocated" if r.space_up_allocated else "not allocated",
                            "group_ids": sorted(groups),
                        }
                        for r, groups in sorted(bands.items(), key=lambda kv: kv[0].low_mhz)
                    ],
                    "matched_assignments": assignments[:MAX_ASSIGNMENTS_LISTED],
                    "matched_assignment_count": len(assignments),
                    "visibility": sorted(reasons),
                    "sections": sorted({n.provision for n in notices if n.provision}),
                    "assumptions": [
                        f"Raised by the user-defined rule “{self.spec.name}”, version {self.version}. "
                        "Its conditions were written by an expert, not taken from a regulation.",
                        "Beam coverage over Finland is not checked.", "No power or pfd calculation was done.",
                    ],
                },
                comment_deadline=_deadline(notices, self.settings.comment_window_months),
            )


def load_enabled(settings: Settings) -> list[DeclarativeRule]:
    """The enabled space rules from the database, at their current versions."""
    from sqlalchemy import select

    from ..db import session_scope
    from ..models import CustomRule

    with session_scope() as s:
        rows = [(r.id, r.version, RuleSpec(name=r.name, description=r.description, severity=r.severity,
                                           title_template=r.title_template, definition=RuleDefinition(**r.definition)))
                for r in s.scalars(select(CustomRule).where(CustomRule.enabled, CustomRule.domain == "space"))]
    if not rows:
        return []
    m4 = load_m4_rows(settings.m4_filter_path)
    return [DeclarativeRule(settings, db_id, version, spec, m4) for db_id, version, spec in rows]


def m4_service_names(settings: Settings) -> list[str]:
    return sorted({s.strip() for r in load_m4_rows(settings.m4_filter_path) for s in r.primary_services.split(";") if s.strip()})
