"""Builds data/national/rr_footnotes_finland.json: the RR Article 5 footnotes whose text names Finland.

    uv run --with pypdf python tools/build_rr_footnotes.py --pdf <RR 2024 Volume 1 PDF>

The PDF is the edition `data/masks/limit_masks.json` cites (sources.RR[0]); its sha256 is checked.
Text comes from the PDF's own text layer, so spacing artefacts ("Esto nia") are kept. Each entry
records its PDF page, and the file says every entry must be checked against that page before use.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "national" / "rr_footnotes_finland.json"
EXPECTED_SHA256 = json.loads((ROOT / "data" / "masks" / "limit_masks.json").read_text(encoding="utf-8"))["sources"]["RR"][0]["sha256"]

# A footnote starts with its number and then a sentence: "5.275 Additional allocation: ...". In the
# allocation table a number is followed by another number or an upper-case service name instead.
START = re.compile(r"(?<![\d.])(5\.\d{2,3}[A-Z]{0,2})\s+(?=[A-Z][a-z])")
UNIT_MHZ = {"kHz": 1e-3, "MHz": 1.0, "GHz": 1e3}
NUMBER = r"\d[\d   ]*(?:[.,]\d+)?"
RANGE = re.compile(rf"({NUMBER})\s*[-–]\s*({NUMBER})\s*(kHz|MHz|GHz)")


def _number(text: str) -> float:
    return float(re.sub(r"[\s  ]", "", text).replace(",", "."))


def ranges_mhz(text: str) -> list[list[float]]:
    """The frequency ranges a footnote's text states, in MHz, in the order written."""
    found = []
    for low, high, unit in RANGE.findall(text):
        pair = [round(_number(low) * UNIT_MHZ[unit], 6), round(_number(high) * UNIT_MHZ[unit], 6)]
        if pair[0] < pair[1] and pair not in found:
            found.append(pair)
    return found


def footnotes(pages: list[tuple[int, str]]) -> list[dict]:
    """Splits Article 5's pages into footnotes and keeps those naming Finland."""
    text, starts = "", []
    for number, page in pages:
        starts.append((len(text), number))
        text += " " + " ".join(page.split())
    marks = list(START.finditer(text))
    out = []
    for mark, following in zip(marks, marks[1:] + [None]):
        body = text[mark.end(): following.start() if following else len(text)].strip()
        if "Finland" not in re.sub(r"\s", "", body):
            continue
        page = max(number for offset, number in starts if offset <= mark.start())
        head, colon, _ = body.partition(":")
        out.append({
            "footnote": mark[1],
            "kind": head.strip() if colon and len(head) <= 40 else "other",
            "bands_mhz": ranges_mhz(body),
            "pdf_page": page,
            "text": body,
        })
    unique: dict[str, dict] = {}
    for entry in out:  # a footnote number can repeat in running text; keep its longest body
        if entry["footnote"] not in unique or len(entry["text"]) > len(unique[entry["footnote"]]["text"]):
            unique[entry["footnote"]] = entry
    return sorted(unique.values(), key=lambda e: (int(e["footnote"].split(".")[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")), e["footnote"]))


def article_5_pages(reader) -> list[tuple[int, str]]:
    texts = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    start = next(n for n, t in texts if re.search(r"ARTICLE\s+5\b", t) and "Frequency allocations" in t)
    end = next(n for n, t in texts if n > start and re.search(r"ARTICLE\s+6\b", t))
    return [(n, t) for n, t in texts if start <= n <= end]


def main() -> None:
    from pypdf import PdfReader

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    args = parser.parse_args()
    raw = args.pdf.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    if sha256 != EXPECTED_SHA256:
        raise SystemExit(f"{args.pdf} has sha256 {sha256}, not the cited edition {EXPECTED_SHA256}")
    pages = article_5_pages(PdfReader(args.pdf))
    entries = footnotes(pages)
    OUT.write_text(json.dumps({
        "description": "ITU Radio Regulations Article 5 footnotes whose text names Finland.",
        "source": {"doc": "ITU Radio Regulations, Edition of 2024, Volume 1, Article 5", "sha256": sha256,
                   "pdf_pages_searched": [pages[0][0], pages[-1][0]]},
        "method": "Extracted from the PDF text layer by tools/build_rr_footnotes.py. Spacing artefacts are kept. "
                  "Check each entry against its PDF page before relying on it.",
        "footnotes": entries,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(entries)} footnotes naming Finland on PDF pages {pages[0][0]}-{pages[-1][0]}")


if __name__ == "__main__":
    main()
