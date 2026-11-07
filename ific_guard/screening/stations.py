"""Loads Traficom's special-interest station spreadsheet (synthetic data, ticket 05).

Bad rows are kept and flagged, not dropped: what a flag means for a result is the caller's decision.
The one row removed is an exact duplicate, and the row it duplicates records that in its flags.
"""
import csv
import hashlib
import re
from bisect import bisect_left
from collections import Counter, OrderedDict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any

STATIONS_PATH = (
    Path(__file__).resolve().parents[2] / "docs/challenge/Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx"
)
HEADER_ROW = 11
FIRST_DATA_ROW = 13  # row 12 repeats the header in Finnish
COLUMNS = (
    "Station number", "Class of licence", "Longitude", "Latitude", "Ground height (m)", "Mast height (m)",
    "Mast type", "Channel bandwidth", "TX frequency", "RX frequency", "Ant height AGL (m)", "Ant height ASL (m)",
    "Ant gain (dB)", "Class of transmission", "Transmission bandwidth", "Radiation direction (°)", "Polarisation",
    "Radioation power", "Radioation power (ITU)", "Radiation power unit", "Transmission line (dB)", "Directivity",
)  # spelling as in the sheet

DUPLICATE_REMOVED = "exact_duplicate_row_removed"
STATION_NUMBER_REUSED = "station_number_not_unique"
NO_RX = "no_rx_frequency"
NO_TX = "no_tx_frequency"
BAD_FREQUENCY = "unparsed_frequency"
NO_CHANNEL_BW = "no_channel_bandwidth_used_transmission_bandwidth"
NO_BANDWIDTH = "no_usable_bandwidth"
BW_MISMATCH = "channel_and_transmission_bandwidth_differ"
MVV_GAIN = "mvv_gain_not_real"
POWER_IMPLAUSIBLE = "power_implausible"
NEGATIVE_HEIGHT = "negative_antenna_height"
OUTSIDE_FINLAND = "coordinates_outside_finland_bounding_box"
NO_COORDINATES = "coordinates_not_known"
EARTH_STATIONS_PATH = Path(__file__).resolve().parents[2] / "data/national/fin_earth_stations.csv"

# Separates the 67 no-class rows in ticket 02 question 8 (133 MW and up) from every other row.
IMPLAUSIBLE_POWER_W = 100e6
# A rough box, for the sheet's warning that coordinates may be outside Finland. Not a border test.
FINLAND_LAT = (59.0, 70.5)
FINLAND_LON = (19.0, 32.0)

_UNIT_MHZ = {"k": 1e-3, "M": 1.0, "G": 1e3}
_POWER_W = {"mW": 1e-3, "W": 1.0, "kW": 1e3}
_FREQUENCY = re.compile(r"(\d+(?:[.,]\d+)?)\s*([kMG])Hz")
# 300.000 kHz, 5000k, 7,6k, or the ITU form 8M00 / 10k0, where the unit letter is the decimal point
_BANDWIDTH = re.compile(r"(\d+(?:[.,]\d+)?)\s*([kMG])(?:Hz)?(\d*)")


SIDE_RX = "rx"
SIDE_TX = "tx"
SIDE_BOTH = "both"  # RX and TX are the same band, as on broadcast rows
SITE_NOT_RECEIVER = "station site, not the receiver: this band is received elsewhere"


@dataclass(frozen=True)
class ProtectedBand:
    side: str
    low_mhz: float
    high_mhz: float

    def overlaps(self, low_mhz: float, high_mhz: float) -> bool:
        return low_mhz < self.high_mhz and high_mhz > self.low_mhz


@dataclass(frozen=True, slots=True)  # slots: the national register has millions of rows
class Station:
    row: int  # row in the sheet; station_no alone is not unique
    station_no: int
    licence_class: str | None
    lon_deg: float | None
    lat_deg: float | None
    ground_height_m: float | None
    mast_height_m: float | None
    ant_height_agl_m: float | None  # as given, including the negative value on row 108
    ant_height_asl_m: float | None
    ant_gain_db: float | None  # None for MVV rows, whose values are not real; see MVV_GAIN
    tx_mhz: float | None
    rx_mhz: float | None
    channel_bw_mhz: float | None
    transmission_bw_mhz: float | None
    transmission_class: str | None
    radiation_direction_deg: float | None
    polarisation: str | None
    power: float | None  # as given: ERP or EIRP, and whether it is really watts, is ticket 02 question 8
    power_unit: str | None
    power_itu: str | None
    line_loss_db: float | None
    directivity: str | None
    quality_flags: tuple[str, ...] = ()
    sheet: int = 1  # an Excel sheet holds about a million rows, so a large register spans several
    site: str | None = None  # a real earth station named in Traficom's frequency table, not a sheet row

    @property
    def key(self) -> str:
        if self.site:
            return f"ES:{self.site}"
        # The first sheet keeps the original form, so keys on existing cases stay the same.
        return f"{self.station_no}@R{self.row}" if self.sheet == 1 else f"{self.station_no}@S{self.sheet}R{self.row}"

    @property
    def bandwidth_mhz(self) -> float | None:
        return self.channel_bw_mhz if self.channel_bw_mhz is not None else self.transmission_bw_mhz

    def _band_mhz(self, centre_mhz: float | None) -> tuple[float, float] | None:
        if centre_mhz is None or self.bandwidth_mhz is None:
            return None
        return centre_mhz - self.bandwidth_mhz / 2, centre_mhz + self.bandwidth_mhz / 2

    @property
    def rx_band_mhz(self) -> tuple[float, float] | None:
        return self._band_mhz(self.rx_mhz)

    @property
    def tx_band_mhz(self) -> tuple[float, float] | None:
        return self._band_mhz(self.tx_mhz)

    @property
    def protected_bands(self) -> tuple[ProtectedBand, ...]:
        """Traficom: "every TX is received in Finland", so a TX band is protected as well as an RX band."""
        rx, tx = self.rx_band_mhz, self.tx_band_mhz
        if rx is not None and rx == tx:
            return (ProtectedBand(SIDE_BOTH, *rx),)
        return tuple(ProtectedBand(side, *band) for side, band in ((SIDE_RX, rx), (SIDE_TX, tx)) if band is not None)


# Bands wider than this are checked one by one, so one very wide band can't widen every search window.
WIDE_BAND_MHZ = 100.0
OVERLAP_CACHE = 32  # recent ranges kept; a range can match millions of stations, so the cache is bounded


class StationIndex:
    """The stations with a protected band, and which of them overlap a frequency range.

    Bands are sorted by their lower edge, so a search reads only the bands that can reach the range:
    the cost grows with the number of matches, not with the size of the register.
    """

    def __init__(self, stations: Iterable[Station]):
        self.stations = [s for s in stations if s.protected_bands]
        narrow: list[tuple[float, int, int, ProtectedBand]] = []
        self._wide: list[tuple[float, int, int, ProtectedBand]] = []
        for i, station in enumerate(self.stations):
            for k, band in enumerate(station.protected_bands):
                (self._wide if band.high_mhz - band.low_mhz > WIDE_BAND_MHZ else narrow).append((band.low_mhz, i, k, band))
        narrow.sort(key=lambda entry: entry[:3])
        self._narrow = narrow
        self._lows = [entry[0] for entry in narrow]
        self._reach = max((b.high_mhz - b.low_mhz for *_, b in narrow), default=0.0)
        self._overlaps: OrderedDict[tuple[float, float], tuple[tuple[Station, tuple[ProtectedBand, ...]], ...]] = OrderedDict()

    def overlapping(self, low_mhz: float, high_mhz: float) -> tuple[tuple[Station, tuple[ProtectedBand, ...]], ...]:
        key = (low_mhz, high_mhz)
        if key in self._overlaps:
            self._overlaps.move_to_end(key)
            return self._overlaps[key]
        start = bisect_left(self._lows, low_mhz - self._reach)
        end = bisect_left(self._lows, high_mhz)  # a band starting at or above high_mhz can't overlap
        found: dict[int, list[tuple[int, ProtectedBand]]] = {}
        for _, i, k, band in chain(self._narrow[start:end], self._wide):
            if band.overlaps(low_mhz, high_mhz):
                found.setdefault(i, []).append((k, band))
        result = tuple((self.stations[i], tuple(b for _, b in sorted(found[i], key=lambda x: x[0]))) for i in sorted(found))
        self._overlaps[key] = result
        if len(self._overlaps) > OVERLAP_CACHE:
            self._overlaps.popitem(last=False)
        return result


def _text(value: Any) -> str | None:
    """Blank cells are a mix of None and empty text."""
    text = "" if value is None else str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    """Numbers can be text and use a decimal comma. Blank or unreadable gives None."""
    text = _text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def parse_frequency_mhz(value: Any) -> float | None:
    match = _FREQUENCY.fullmatch(_text(value) or "")
    return round(float(match[1].replace(",", ".")) * _UNIT_MHZ[match[2]], 9) if match else None


def parse_bandwidth_mhz(value: Any) -> float | None:
    match = _BANDWIDTH.fullmatch(_text(value) or "")
    if not match or (match[3] and not match[1].isdigit()):
        return None
    decimals = f".{match[3]}" if match[3] else ""
    return round(float(match[1].replace(",", ".") + decimals) * _UNIT_MHZ[match[2]], 9)


def _quality_flags(cells: dict[str, Any]) -> list[str]:
    flags = []
    for column, missing in (("RX frequency", NO_RX), ("TX frequency", NO_TX)):
        if _text(cells[column]) is None:
            flags.append(missing)
        elif parse_frequency_mhz(cells[column]) is None:
            flags.append(BAD_FREQUENCY)

    channel = parse_bandwidth_mhz(cells["Channel bandwidth"])
    transmission = parse_bandwidth_mhz(cells["Transmission bandwidth"])
    if channel is None:
        flags.append(NO_BANDWIDTH if transmission is None else NO_CHANNEL_BW)
    elif transmission is not None and abs(channel - transmission) > 1e-9:
        flags.append(BW_MISMATCH)

    if _text(cells["Class of licence"]) == "MVV" and _number(cells["Ant gain (dB)"]) is not None:
        flags.append(MVV_GAIN)
    power, to_watts = _number(cells["Radioation power"]), _POWER_W.get(_text(cells["Radiation power unit"]) or "")
    if power is not None and to_watts is not None and power * to_watts > IMPLAUSIBLE_POWER_W:
        flags.append(POWER_IMPLAUSIBLE)
    height = _number(cells["Ant height AGL (m)"])
    if height is not None and height < 0:
        flags.append(NEGATIVE_HEIGHT)
    lat, lon = _number(cells["Latitude"]), _number(cells["Longitude"])
    if lat is None or lon is None or not (FINLAND_LAT[0] <= lat <= FINLAND_LAT[1] and FINLAND_LON[0] <= lon <= FINLAND_LON[1]):
        flags.append(OUTSIDE_FINLAND)
    return flags


def _station(row: int, cells: dict[str, Any], flags: list[str], sheet: int = 1) -> Station:
    licence_class = _text(cells["Class of licence"])
    return Station(
        row=row,
        station_no=int(cells["Station number"]),
        licence_class=licence_class,
        lon_deg=_number(cells["Longitude"]),
        lat_deg=_number(cells["Latitude"]),
        ground_height_m=_number(cells["Ground height (m)"]),
        mast_height_m=_number(cells["Mast height (m)"]),
        ant_height_agl_m=_number(cells["Ant height AGL (m)"]),
        ant_height_asl_m=_number(cells["Ant height ASL (m)"]),
        ant_gain_db=None if licence_class == "MVV" else _number(cells["Ant gain (dB)"]),
        tx_mhz=parse_frequency_mhz(cells["TX frequency"]),
        rx_mhz=parse_frequency_mhz(cells["RX frequency"]),
        channel_bw_mhz=parse_bandwidth_mhz(cells["Channel bandwidth"]),
        transmission_bw_mhz=parse_bandwidth_mhz(cells["Transmission bandwidth"]),
        transmission_class=_text(cells["Class of transmission"]),
        radiation_direction_deg=_number(cells["Radiation direction (°)"]),
        polarisation=_text(cells["Polarisation"]),
        power=_number(cells["Radioation power"]),
        power_unit=_text(cells["Radiation power unit"]),
        power_itu=_text(cells["Radioation power (ITU)"]),
        line_loss_db=_number(cells["Transmission line (dB)"]),
        directivity=_text(cells["Directivity"]),
        quality_flags=tuple(flags),
        sheet=sheet,
    )


def _sheet_rows(path: Path) -> Iterator[tuple[int, int, tuple]]:
    """Yields (sheet, row number, cells) for every data row, from every sheet of a workbook or from a CSV.

    A sheet either has the original layout (header on row 11, a Finnish header on row 12) or starts with the
    header on row 1, as a continuation sheet would. Anything else stops the load: reading part of the
    register would silently drop stations.
    """
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = tuple(next(reader, ()))[: len(COLUMNS)]
            if header != COLUMNS:
                raise ValueError(f"{path.name}: the first line is not the expected header")
            for number, row in enumerate(reader, 2):
                yield 1, number, tuple((row + [""] * len(COLUMNS))[: len(COLUMNS)])
        return

    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet_no, sheet in enumerate(workbook.worksheets, 1):
            first_data, has_content = None, False
            for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
                cells = tuple(row[: len(COLUMNS)])
                if first_data is None:
                    if cells == COLUMNS and number in (1, HEADER_ROW):
                        first_data = FIRST_DATA_ROW if number == HEADER_ROW else 2
                    has_content = has_content or any(_text(c) for c in cells)
                    if number >= HEADER_ROW and first_data is None:
                        break
                elif number >= first_data:
                    yield sheet_no, number, cells
            if first_data is None and (has_content or sheet_no == 1):
                raise ValueError(
                    f"{path.name}, sheet {sheet.title!r}: the header is not on row 1 or row {HEADER_ROW}, so the layout has changed"
                )
    finally:
        workbook.close()


def load_stations(path: Path = STATIONS_PATH) -> list[Station]:
    """Reads the register in one pass. Only a 16-byte digest of each row is kept to find exact duplicates."""
    first_of: dict[bytes, int] = {}  # row digest -> index in `stations`
    duplicated: set[int] = set()
    rows_per_number: Counter = Counter()
    stations: list[Station] = []
    for sheet, number, row in _sheet_rows(path):
        if _text(row[0]) is None:
            continue
        digest = hashlib.blake2b(repr(tuple(_text(c) for c in row)).encode(), digest_size=16).digest()
        if digest in first_of:
            duplicated.add(first_of[digest])
            continue
        cells = dict(zip(COLUMNS, row))
        try:
            station = _station(number, cells, _quality_flags(cells), sheet)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{path.name}, sheet {sheet} row {number}: station number {row[0]!r} is not a number") from exc
        first_of[digest] = len(stations)
        rows_per_number[station.station_no] += 1
        stations.append(station)
    for i, station in enumerate(stations):
        extra = (STATION_NUMBER_REUSED,) * (rows_per_number[station.station_no] > 1) + (DUPLICATE_REMOVED,) * (i in duplicated)
        if extra:
            stations[i] = replace(station, quality_flags=station.quality_flags + extra)
    return stations


def load_earth_stations(path: Path = EARTH_STATIONS_PATH) -> list[Station]:
    """Receiving earth stations from data/national/fin_earth_stations.csv, as stations to protect (ticket 21).

    Transmitting sites are listed in the file but not loaded: a satellite downlink in their band
    reaches no receiver there. A site without coordinates is flagged, so it is linked by frequency only.
    """
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["protected"].strip().lower() == "true" and r["direction"] == "rx"]
    out = []
    for number, r in enumerate(rows, 1):
        low, high = float(r["low_mhz"]), float(r["high_mhz"])
        lat, lon = _number(r["lat_deg"]), _number(r["lon_deg"])
        out.append(Station(
            row=0, station_no=number, licence_class="Earth station (RX)", lon_deg=lon, lat_deg=lat, ground_height_m=None,
            mast_height_m=None, ant_height_agl_m=None, ant_height_asl_m=None, ant_gain_db=None, tx_mhz=None,
            rx_mhz=(low + high) / 2, channel_bw_mhz=high - low, transmission_bw_mhz=None, transmission_class=None,
            radiation_direction_deg=None, polarisation=None, power=None, power_unit=None, power_itu=None, line_loss_db=None,
            directivity=None, quality_flags=() if lat is not None and lon is not None else (NO_COORDINATES,), site=r["site"],
        ))
    return out


@lru_cache(maxsize=2)
def _cached(path: Path, mtime_ns: int, size: int) -> tuple[Station, ...]:
    return tuple(load_stations(path))


def load_stations_cached(path: Path = STATIONS_PATH) -> list[Station]:
    """For on-request recomputation: reloads only when the file changes."""
    info = path.stat()
    return list(_cached(path, info.st_mtime_ns, info.st_size))


def protected_stations(path: Path = STATIONS_PATH, cached: bool = False) -> list[Station]:
    """Everything the space rules protect: Traficom's special-interest list plus the real receiving earth stations."""
    return (load_stations_cached(path) if cached else load_stations(path)) + load_earth_stations()
