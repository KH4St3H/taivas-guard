"""Finds which IFIC issues ITU has published, from its public listing pages.

A listing that yields nothing raises ListingChanged: a silent empty result would look like
"no new issue" and the system would stop updating without anyone noticing.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

import httpx

from ..config import Settings

SPACE = "space"
TERRESTRIAL = "terrestrial"


class ListingChanged(Exception):
    """The page loaded but no issues could be read from it, so its format probably changed."""


@dataclass(frozen=True)
class IssueRef:
    domain: str
    issue_no: int
    url: str
    published_on: date | None = None


_SPACE_ROW = re.compile(
    r"<b>\s*(\d{2}\.\d{2}\.\d{4})\s*</b>\s*</td>\s*<td[^>]*>\s*<b>\s*<a\s+href=\"([^\"]*?ific(\d+)\.zip)\"",
    re.I,
)
_TERR_ZIP = re.compile(r"href=\"([^\"]*?MDB/brific(\d+)\.zip)\"", re.I)


def _checked_url(base: str, href: str) -> str:
    url = urljoin(base, href)
    parts = urlsplit(url)
    if parts.scheme != "https" or not (parts.hostname == "itu.int" or (parts.hostname or "").endswith(".itu.int")):
        raise ListingChanged(f"Refusing a download link outside itu.int: {url}")
    return url


def parse_space_listing(html: str, page_url: str) -> list[IssueRef]:
    refs = [
        IssueRef(SPACE, int(n), _checked_url(page_url, href), datetime.strptime(d, "%d.%m.%Y").date())
        for d, href, n in _SPACE_ROW.findall(html)
    ]
    if not refs:
        raise ListingChanged(f"No issues found in the space listing {page_url}")
    return refs


def parse_terrestrial_listing(html: str, page_url: str) -> list[IssueRef]:
    refs = []
    for href, n in _TERR_ZIP.findall(html):
        found = re.search(rf">\s*{n}\s*</td>\s*<td[^>]*>\s*(?:<nobr>)?\s*(\d{{2}}/\d{{2}}/\d{{4}})", html)
        published = datetime.strptime(found.group(1), "%d/%m/%Y").date() if found else None
        refs.append(IssueRef(TERRESTRIAL, int(n), _checked_url(page_url, href), published))
    if not refs:
        raise ListingChanged(f"No issues found in the terrestrial listing {page_url}")
    return refs


def discover_space(client: httpx.Client, settings: Settings, today: date | None = None) -> list[IssueRef]:
    """Space issues sit on one page per year. Walk back until the oldest wanted issue is covered."""
    year = (today or date.today()).year
    refs: list[IssueRef] = []
    for y in range(year, year - 3, -1):
        url = urljoin(settings.space_index_base, f"demowic{y % 100:02d}.html")
        response = client.get(url)
        if response.status_code == 404:  # early January, before the new year's page exists
            continue
        response.raise_for_status()
        page = parse_space_listing(response.text, url)
        refs.extend(page)
        if min(r.issue_no for r in page) <= settings.min_issue:
            break
    if not refs:
        raise ListingChanged("No space listing page was found for the last three years")
    return [r for r in refs if r.issue_no >= settings.min_issue]


def discover_terrestrial(client: httpx.Client, settings: Settings) -> list[IssueRef]:
    """The page lists only recent issues. Older wanted ones are reached by the known URL pattern."""
    response = client.get(settings.terrestrial_index_url)
    response.raise_for_status()
    refs = parse_terrestrial_listing(response.text, settings.terrestrial_index_url)
    oldest = min(r.issue_no for r in refs)
    older = [
        IssueRef(TERRESTRIAL, n, settings.terrestrial_zip_pattern.format(issue=n))
        for n in range(settings.min_issue, oldest)
    ]
    return older + [r for r in refs if r.issue_no >= settings.min_issue]


DISCOVERERS = {SPACE: discover_space, TERRESTRIAL: discover_terrestrial}
