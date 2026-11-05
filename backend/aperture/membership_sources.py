"""Bridge a retrospective roster archive with primary effective-date evidence.

This is still retrospective research, not a licensed/as-known index feed. A
matching endpoint alone is insufficient: dated intervening events are required.
"""

import hashlib
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from . import calendar
from .domain import ResearchError

PRESS_URL = "https://press.spglobal.com/index.php?keywords=S%26P+500&l=100&s=2429"
RENAME_URL = "https://ir.skydance.com/news-releases/news-release-details/paramount-completes-acquisition-warner-bros-discovery-creating"
# Reviewed issuer evidence. This changes membership ticker labels only; it does
# not splice price series, infer security identity, or account for the merger.
SYMBOL_CHANGES = [("2026-10-06", "PSKY", "SKYD", RENAME_URL)]
VERSION = "primary-events-v1"


class Document(HTMLParser):
    """Read ordinary announcement tables and release links, never executable HTML."""

    def __init__(self):
        super().__init__()
        self.links, self.rows, self.text = [], [], []
        self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []

    def handle_data(self, value):
        self.text.append(value)
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def document(text):
    parsed = Document()
    parsed.feed(text)
    return parsed


def effective_day(value):
    value = re.sub(r"\bSept\b", "Sep", value).replace(".", "")
    value = re.sub(r"\s+", " ", value).strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return str(datetime.strptime(value, fmt).date())
        except ValueError:
            pass
    raise ResearchError(f"S&P announcement has an unsupported effective date: {value}.")


def announcement_events(text, source):
    rows = document(text).rows
    events = []
    for row in rows:
        while row and not row[-1]:
            row = row[:-1]
        if "S&P 500" not in row:
            continue
        if (
            len(row) != 6
            or row[1] != "S&P 500"
            or row[2] not in ("Addition", "Deletion")
        ):
            raise ResearchError(
                f"S&P 500 announcement table changed at {source}; membership was not extended."
            )
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", row[4]) or row[4] == "SPY":
            raise ResearchError("S&P announcement contains an invalid stock symbol.")
        events.append(
            {
                "effective": effective_day(row[0]),
                "action": row[2],
                "symbol": row[4],
                "source": source,
            }
        )
    return events


def extend(rosters, captured, fetch):
    """Return a reconciled timeline and every raw response used as evidence."""
    from .membership import CURRENT_URL, parse_current

    anchor = rosters[-1]["effective"]
    observed = (
        datetime.fromisoformat(captured).astimezone(ZoneInfo("America/New_York")).date()
    )
    through = calendar.latest_complete(datetime.fromisoformat(captured))
    evidence = []

    def read(url):
        response = fetch(url)
        evidence.append(
            {
                "url": url,
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "text": response.text,
            }
        )
        if sum(len(e["text"]) for e in evidence) > 16 * 1024 * 1024:
            raise ResearchError("Membership evidence exceeded the 16 MB limit.")
        return response.text

    current = parse_current(read(CURRENT_URL))
    # Announcements can precede their effective dates. Include a look-back and
    # prove the listing reaches it; never assume a truncated first page is complete.
    cutoff = date.fromisoformat(anchor) - timedelta(days=45)
    links = set()
    for offset in range(0, 500, 100):
        page = document(read(PRESS_URL + f"&o={offset}"))
        releases = {
            url: date.fromisoformat(match[1])
            for url in page.links
            if (
                match := re.match(
                    r"^https://press\.spglobal\.com/(\d{4}-\d{2}-\d{2})-", url
                )
            )
        }
        if not releases:
            raise ResearchError(
                "S&P announcement listing changed; membership was not extended."
            )
        links.update(url for url, day in releases.items() if cutoff <= day <= observed)
        if min(releases.values()) <= cutoff:
            break
    else:
        raise ResearchError(
            "S&P announcements do not reach the historical anchor within 500 releases."
        )

    events = []
    for url in sorted(links):
        parsed = announcement_events(read(url), url)
        # A release explicitly about an S&P 500 change must have a supported
        # table. Do not silently ignore prose-only or newly formatted changes.
        if (
            re.search(
                r"(?:Join|Added|Changes|Replace).*S-P-500|S-P-500.*(?:Changes|Replace)",
                url,
                re.IGNORECASE,
            )
            and not parsed
        ):
            raise ResearchError(
                f"No supported effective-date table in S&P announcement: {url}"
            )
        events.extend(e for e in parsed if anchor < e["effective"] <= str(observed))
    for day, old, new, url in SYMBOL_CHANGES:
        if anchor < day <= str(observed):
            events.extend(
                {"effective": day, "action": action, "symbol": symbol, "source": url}
                for action, symbol in [("Deletion", old), ("Addition", new)]
            )

    grouped = defaultdict(dict)
    for event in events:
        key = (event["action"], event["symbol"])
        grouped[event["effective"]][key] = event
    result = list(rosters)
    names = set(result[-1]["symbols"])
    for day, group in sorted(grouped.items()):
        added = {s for a, s in group if a == "Addition"}
        removed = {s for a, s in group if a == "Deletion"}
        if added & names or removed - names or added & removed:
            raise ResearchError(
                f"S&P dated changes conflict with the archive on {day}; no history was guessed."
            )
        names = (names - removed) | added
        if not 490 <= len(names) <= 520:
            raise ResearchError(
                f"Reconstructed S&P roster has an implausible size on {day}."
            )
        result.append({"effective": day, "symbols": sorted(names)})
    current_names = {m["symbol"] for m in current}
    if names != current_names:
        raise ResearchError(
            "Dated S&P changes do not reconcile with the observed current roster. "
            f"History-only: {', '.join(sorted(names - current_names)) or 'none'}; "
            f"current-only: {', '.join(sorted(current_names - names)) or 'none'}. Membership was not extended."
        )
    result = [r for r in result if r["effective"] <= str(through)]
    return (
        result,
        {
            "history_version": VERSION,
            "coverage_end": str(through),
            "verified_through": str(through),
            "last_change": result[-1]["effective"],
            "archive_last_change": anchor,
            "verification_basis": "Primary effective-date announcements, reviewed ticker changes and exact current-roster reconciliation; retrospective, not a certified complete index feed.",
            "events": sorted(
                events, key=lambda e: (e["effective"], e["action"], e["symbol"])
            ),
            "reviewed_symbol_changes": [
                {
                    "effective": d,
                    "old_symbol": old,
                    "new_symbol": new,
                    "source": url,
                    "reviewed_on": "2026-11-04",
                }
                for d, old, new, url in SYMBOL_CHANGES
                if anchor < d <= str(observed)
            ],
            "sources": [{k: v for k, v in e.items() if k != "text"} for e in evidence],
        },
        evidence,
    )
