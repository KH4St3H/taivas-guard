"""A visible satellite transmits on a special-interest station's receive frequency (ticket 05)."""
import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..config import Settings
from .rules import Hit, _deadline, _families, visible_from_finland
from .space import SATELLITE_NOTICE_TYPES, SpaceIssue, SpaceNotice
from .stations import BW_MISMATCH, NO_CHANNEL_BW, STATIONS_PATH, Station, load_stations

NO_CLASS = "no class"  # the sheet leaves the class blank; what that means is ticket 02 question 10
BAND_FLAGS = (NO_CHANNEL_BW, BW_MISMATCH)  # the quality flags that can change a station's receive band


def _downlinks(notice: SpaceNotice) -> dict[tuple[float, float], set[int]]:
    """Distinct space-to-Earth frequency ranges of a notice, with the groups using each."""
    ranges: dict[tuple[float, float], set[int]] = defaultdict(set)
    for a in notice.assignments:
        if a.get("emi_rcp") == "E" and a.get("freq_min") is not None and a.get("freq_max") is not None:
            ranges[float(a["freq_min"]), float(a["freq_max"])].add(int(a["grp_id"]))  # E = the space station transmits
    return ranges


def _class_summary(stations: Iterable[Station]) -> dict[str, int]:
    return dict(sorted(Counter(s.licence_class or NO_CLASS for s in stations).items()))


def _bands(hits: dict[Station, set[int]]) -> list[dict[str, Any]]:
    """Joins the receive bands of the stations hit into contiguous bands, so a case stays readable."""
    merged: list[dict[str, Any]] = []
    for station in sorted(hits, key=lambda s: (s.rx_band_mhz, s.row)):
        low, high = station.rx_band_mhz
        if not merged or low > merged[-1]["high"]:
            merged.append({"low": low, "high": high, "stations": [], "groups": set()})
        band = merged[-1]
        band["high"] = max(band["high"], high)
        band["stations"].append(station)
        band["groups"] |= hits[station]
    return [
        {
            "low_mhz": round(b["low"], 6),
            "high_mhz": round(b["high"], 6),
            "classes": _class_summary(b["stations"]),
            "station_ids": sorted(s.key for s in b["stations"]),
            "group_ids": sorted(b["groups"]),
        }
        for b in merged
    ]


class StationOverlapRule:
    """A space-to-Earth assignment overlaps the receive band of a special-interest station.

    Frequency overlap only, so this over-flags by design (ARCHITECTURE.md principle 6). Power, geometry
    and antenna direction are ticket 07's.
    """

    id = "station-rx-overlap"

    def __init__(self, settings: Settings, stations: list[Station], dataset: dict[str, Any] | None = None):
        self.settings = settings
        self.protected = [s for s in stations if s.rx_band_mhz is not None]
        self.total = len(stations)
        self.dataset = dataset or {}

    def _assumptions(self) -> list[str]:
        skipped = self.total - len(self.protected)
        return [
            f"{skipped} of {self.total} stations have no RX frequency and were skipped, so they are not protected "
            "here. Whether to protect them at their TX frequency is unanswered (Traficom question 12, ticket 02).",
            "A station's receive band is its RX frequency +/- half its channel bandwidth, or half its transmission "
            "bandwidth where the channel bandwidth is blank. Where the two differ, the channel bandwidth is used.",
            "Rows whose RX and TX frequencies are equal (such as broadcast rows) are protected as listed, though "
            "such a station may not be a receiver.",
            "The station data is synthetic, per Traficom.",
            "Frequency overlap only: beam coverage, power, pfd, geometry and antenna direction are not checked, "
            "and the service allocation of the band is not considered.",
        ]

    def run(self, issue: SpaceIssue) -> Iterable[Hit]:
        satellites = (n for n in issue.notices.values() if n.ntc_type in SATELLITE_NOTICE_TYPES)
        for family_id, notices in _families(satellites).items():
            hits: dict[Station, set[int]] = defaultdict(set)
            reasons = set()
            for notice in notices:
                visible, why = visible_from_finland(notice, self.settings)
                if not visible:
                    continue
                reasons.add(why)
                for (low, high), groups in _downlinks(notice).items():
                    for station in self.protected:
                        rx_low, rx_high = station.rx_band_mhz
                        if low < rx_high and high > rx_low:
                            hits[station] |= groups
            if not hits:
                continue
            head = notices[0]
            notice_ids = sorted(n.ntc_id for n in notices)
            classes = _class_summary(hits)
            flagged = {
                flag: sorted(s.key for s in hits if flag in s.quality_flags)
                for flag in BAND_FLAGS
                if any(flag in s.quality_flags for s in hits)
            }
            yield Hit(
                rule_id=self.id,
                family_id=family_id,
                severity="medium",
                title=(
                    f"{head.name or head.ntc_id} ({head.adm}) transmits on the receive band of {len(hits)} protected "
                    f"station(s): " + ", ".join(f"{name} {count}" for name, count in classes.items())
                ),
                adm=head.adm,
                network=head.name,
                notice_ids=notice_ids,
                details={
                    "method": "screening",
                    "station_ids": sorted(s.key for s in hits),
                    "classes": classes,
                    "bands": _bands(hits),
                    "station_band_flags": flagged,
                    "visibility": sorted(reasons),
                    "sections": sorted({n.provision for n in notices if n.provision}),
                    "assumptions": self._assumptions(),
                    "station_dataset": self.dataset,
                    "source": {"domain": "space", "notice_ids": [str(n) for n in notice_ids]},
                },
                comment_deadline=_deadline(notices, self.settings.comment_window_months),
            )


def station_overlap_rule(settings: Settings, path: Path = STATIONS_PATH) -> StationOverlapRule:
    stations = load_stations(path)
    with path.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    return StationOverlapRule(settings, stations, {"file": path.name, "sha256": sha256, "records": len(stations)})
