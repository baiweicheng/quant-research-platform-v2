"""Explicit as-traded CSV contract; no ambiguous adjusted-price heuristics."""

import csv
import hashlib
import io
import json
import math
import random
import re
from datetime import date, datetime
from decimal import Decimal

from . import calendar
from .domain import Bar, Dataset, ResearchError, decimal

MAX_BYTES = 16 * 1024 * 1024
MAX_ROWS = 80000
REQUIRED = {"symbol", "date", "open", "high", "low", "close", "volume"}
WARNING = "Fixed-list exploratory research only. Historical universe membership, delisted coverage and sector history are not verified."


def records(reader):
    try:
        yield from reader
    except csv.Error:
        raise ResearchError(
            "The CSV could not be parsed. Check quoting and unusually large fields, then try again."
        ) from None


def parse_csv(text: str, name: str, source: str) -> tuple[Dataset, bytes, list[str]]:
    raw = text.encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ResearchError(
            "Import is limited to 16 MB. Use a smaller stock list or date range."
        )
    name, source = name.strip(), source.strip()
    if not name or not source:
        raise ResearchError("Give the dataset a name and describe its source.")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        fields = reader.fieldnames or []
    except csv.Error:
        raise ResearchError(
            "The CSV header could not be parsed. Check its quoting."
        ) from None
    if not REQUIRED.issubset(fields):
        raise ResearchError(
            "CSV needs symbol,date,open,high,low,close,volume columns. Download the template for the full format."
        )
    if len(fields) != len(set(fields)):
        raise ResearchError(
            "CSV column names must be unique; remove duplicate headers."
        )
    rows, sectors, seen = {}, {}, set()
    latest = calendar.latest_complete()
    allowed = set(calendar.sessions(date(1990, 1, 2), latest))
    for line, item in enumerate(records(reader), start=2):
        if line > MAX_ROWS + 1:
            raise ResearchError(
                "Import is limited to 80,000 rows. Choose a smaller dataset."
            )
        try:
            if None in item or any(item.get(key) is None for key in REQUIRED):
                raise ResearchError(
                    "The number of values does not match the CSV header. Check commas and quoting."
                )
            symbol = item["symbol"].strip().upper()
            if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", symbol):
                raise ResearchError(
                    "Use a stock symbol of at most 12 letters, digits, dots or hyphens."
                )
            day = date.fromisoformat(item["date"].strip())
            if day not in allowed:
                raise ResearchError(
                    "Date must be a completed US equity session between 1990 and today."
                )
            if (symbol, day) in seen:
                raise ResearchError(
                    f"Duplicate {symbol} session {day}; remove duplicates before importing."
                )
            seen.add((symbol, day))
            volume = int(item["volume"])
            sector = (item.get("sector") or "Unknown").strip() or "Unknown"
            if symbol in sectors and sectors[symbol] != sector:
                raise ResearchError(
                    "This milestone supports one static sector per symbol. Historical sector changes require a later data model."
                )
            sectors[symbol] = sector
            supplied = (item.get("available_at") or "").strip()
            availability = (
                datetime.fromisoformat(supplied.replace("Z", "+00:00"))
                if supplied
                else calendar.available_time(day)
            )
            if availability.tzinfo is None or availability < calendar.available_time(
                day
            ):
                raise ResearchError(
                    "available_at must include a time zone and cannot precede close + 15 minutes."
                )
            bar = Bar(
                symbol,
                day,
                *(decimal(item[key], key) for key in ("open", "high", "low", "close")),
                volume,
                decimal(item.get("split") or "1", "Split ratio"),
                decimal(item.get("dividend") or "0", "Dividend"),
                date.fromisoformat(item["pay_date"]) if item.get("pay_date") else None,
                availability,
            )
            rows.setdefault(symbol, []).append(bar)
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            raise ResearchError(f"Row {line}: {error}") from None
    if not rows:
        raise ResearchError("The CSV has no data rows.")
    if len(rows) > 1500:
        raise ResearchError(
            "This local release supports at most 1,500 symbols per dataset, including SPY."
        )
    digest = hashlib.sha256(raw + b"\0as-traded-v1\0" + source.encode()).hexdigest()
    dataset = Dataset(
        digest[:24],
        name[:100],
        "imported",
        1,
        {
            symbol: tuple(sorted(bars, key=lambda b: b.session))
            for symbol, bars in rows.items()
        },
        sectors,
        source[:500],
        digest,
    )
    warnings = [
        WARNING,
        "Prices were declared as-traded by the importer; vendor adjustment conventions have not been independently audited.",
        "Blank availability is conservatively modeled as close + 15 minutes, not proof of historical vendor publication time.",
    ]
    if "SPY" not in rows:
        warnings.append("No SPY data. Benchmark comparisons will be unavailable.")
    if "Unknown" in sectors.values():
        warnings.append(
            "Missing sectors share an Unknown bucket, capped at 25% under the default policy."
        )
    return dataset, raw, warnings


def practice_dataset() -> tuple[Dataset, bytes, list[str]]:
    """Deterministic fictional prices for learning the app, never market evidence."""
    end = calendar.latest_complete()
    days = calendar.sessions(date(2022, 1, 3), end)
    rows, sectors = {}, {}
    for index, symbol in enumerate([f"P{i:02}" for i in range(1, 33)] + ["SPY"]):
        rng = random.Random(7100 + index)
        price = 45.0 + index * 3
        bars = []
        sectors[symbol] = [
            "Technology",
            "Healthcare",
            "Industrials",
            "Consumer",
            "Financials",
            "Energy",
            "Utilities",
            "Materials",
        ][index % 8]
        for day_index, day in enumerate(days):
            split = Decimal(2) if index == 0 and day_index == 400 else Decimal(1)
            opening = price * math.exp(rng.gauss(0, 0.003)) / float(split)
            closing = opening * math.exp(
                0.00025
                + 0.00015 * math.sin(day_index / 90 + index)
                + rng.gauss(0, 0.006 + index % 6 * 0.0015)
            )
            prices = [
                Decimal(f"{value:.4f}")
                for value in (
                    opening,
                    max(opening, closing) * 1.004,
                    min(opening, closing) * 0.996,
                    closing,
                )
            ]
            bars.append(
                Bar(
                    symbol,
                    day,
                    *prices,
                    1_000_000 + index * 10000,
                    split,
                    available_at=calendar.available_time(day),
                )
            )
            price = closing
        rows[symbol] = tuple(bars)
    raw = json.dumps(
        {"generator": "practice-v1", "end": str(end), "seed": 7100}, sort_keys=True
    ).encode()
    digest = hashlib.sha256(raw).hexdigest()
    return (
        Dataset(
            digest[:24],
            "Practice universe",
            "synthetic",
            1,
            rows,
            sectors,
            "Fictional deterministic generator v1",
            digest,
        ),
        raw,
        [
            "Synthetic practice data. Symbols P01–P32 and the SPY series are fictional; returns have no investment meaning.",
            WARNING,
        ],
    )


TEMPLATE = "symbol,date,open,high,low,close,volume,split,dividend,pay_date,sector,available_at\n"
