"""Read current-circular land-mobile notices, retaining source rows and units."""
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
import math
from typing import Any

from ..screening.space import TableReader

LAND_MOBILE_CLASSES = {"FB": "Base station", "ML": "Land mobile station"}


def number(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _pub_key(row: dict) -> tuple:
    return tuple(row.get(k) for k in ("pub_no", "pub_prefix", "addendum", "corrigendum"))


@dataclass
class TerrestrialNotice:
    terrakey: str
    adm: str
    station_class: str
    frequency_mhz: float | None
    low_mhz: float | None
    high_mhz: float | None
    bandwidth_khz: float | None
    latitude_deg: float | None
    longitude_deg: float | None
    geometry_type: str | None
    radius_km: float | None
    intent: str | None
    targets: list[dict]
    nature_services: list[str]
    raw: dict[str, Any]
    quality_flags: list[str]


class TerrestrialIssue:
    """A circular is an update, not a complete inventory of active assignments.

    Membership comes from pub + fxm_pub_hist, including special sections whose
    publication number differs from the circular number. Older recorded target
    assignments in the same MDB are retained in all_assignments but not emitted.
    """

    def __init__(self, reader: TableReader, expected_issue: int | None = None):
        self.reader = reader
        current = reader.table("pub_current_circ")
        if len(current) != 1 or current[0].get("circ_no") is None:
            raise ValueError("Terrestrial database must identify exactly one current circular.")
        self.issue_no = int(current[0]["circ_no"])
        if expected_issue is not None and self.issue_no != expected_issue:
            raise ValueError(f"Expected terrestrial issue {expected_issue}, database contains {self.issue_no}.")
        self.published_on = str(current[0].get("d_pub") or "")[:10] or None
        refs = {r["stn_cls"]: r["description"] for r in reader.table("ref_stn_cls")}
        for code, label in LAND_MOBILE_CLASSES.items():
            if refs.get(code, "").strip().lower() != label.lower():
                raise ValueError(f"Unsupported terrestrial station-class definition: {code}: {refs.get(code)!r}")
        self.nature_service_descriptions = {r["nat_srv"]: r["description"] for r in reader.table("ref_nat_srv")}
        publications = [r for r in reader.table("pub") if r.get("circ_no") == self.issue_no]
        if not publications:
            raise ValueError(f"Missing publication index for terrestrial circular {self.issue_no}.")
        keys = {_pub_key(r) for r in publications}
        self.current_publications = publications
        self.publication_history = [r for r in reader.table("fxm_pub_hist") if _pub_key(r) in keys]
        self.published_totals = [r for r in reader.table("pub_totals") if _pub_key(r) in keys]

    @cached_property
    def all_assignments(self) -> dict[str, dict]:
        result = {}
        for row in self.reader.table("fxm_terra"):
            key = str(row["terrakey"])
            if key in result:
                raise ValueError(f"Duplicate terrestrial terrakey: {key}")
            result[key] = row
        return result

    @cached_property
    def notices(self) -> dict[str, TerrestrialNotice]:
        histories = defaultdict(list)
        for row in self.publication_history:
            histories[str(row["terrakey"])].append(row)
        missing = histories.keys() - self.all_assignments.keys()
        if missing:
            raise ValueError(f"Publication history references missing assignments: {sorted(missing)[:5]}")
        geography = {r["geo_key"]: r for r in self.reader.table("fxm_geo")}
        attached = {}
        for table in ("fxm_ant", "fxm_ant_hgt", "fxm_nat_serv", "fxm_target", "fxm_coord"):
            grouped = defaultdict(list)
            for row in self.reader.table(table):
                grouped[str(row["terrakey"])].append(row)
            attached[table] = grouped
        result = {}
        for key in sorted(histories):
            row = self.all_assignments[key]
            if row.get("stn_cls") not in LAND_MOBILE_CLASSES:
                continue
            geo = geography.get(row.get("geo_key"), {})
            lat, lon = number(geo.get("lat_dec")), number(geo.get("long_dec"))
            flags = []
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                lat = lon = None
                flags.append("Missing or invalid coordinates; retain for review.")
            low, high, center = (number(row.get(k)) for k in ("freq_min", "freq_max", "freq_assgn"))
            bandwidth = number(row.get("bdwdth"))
            if low is None or high is None or low <= 0 or high < low:
                low = high = None
                if center is not None and center > 0 and bandwidth is not None and bandwidth > 0:
                    low, high = center - bandwidth / 2000, center + bandwidth / 2000
                    flags.append("Frequency interval derived from assigned MHz and bandwidth kHz.")
                else:
                    flags.append("Missing or invalid frequency interval; retain for review.")
            nature = [r["nat_srv"] for r in attached["fxm_nat_serv"][key]]
            if any(n not in self.nature_service_descriptions for n in nature):
                flags.append("Unrecognized nature-of-service code.")
            raw = {"fxm_terra": row, "fxm_geo": geo, "fxm_pub_hist": histories[key],
                   **{table: grouped[key] for table, grouped in attached.items()}}
            result[key] = TerrestrialNotice(
                key, row.get("adm") or "", row["stn_cls"], center, low, high, bandwidth,
                lat, lon, geo.get("geo_type"), number(geo.get("radius")), row.get("intent"),
                attached["fxm_target"][key], nature, raw, flags,
            )
        return result
