"""Narrow primary-filing supplement for reviewed untagged annual disclosures.

Reviewed ExxonMobil and HPE tables explicitly report annual gross profit.
These are issuer-defined reported values, not operating-profit substitutes.
Other issuers do not trigger bulk full-report reads. The source definition
remains attached to every recovery.
"""

import re
from decimal import Decimal
from urllib.parse import parse_qs, urljoin, urlsplit

from lxml import html

from .domain import ResearchError

ISSUERS = {"0000034088", "0001645590"}
DEFINITION = "Issuer-reported gross profit: sales and other operating revenue less estimated costs associated with products sold; annual amount from quarterly information. Sales-based taxes are included in the disclosed revenue. This is an issuer-defined reported numerator, not a reconstructed standardized cost allocation."


def primary_url(api, folder, accession):
    root = html.fromstring(
        api.document(folder + accession + "-index.htm"),
        parser=html.HTMLParser(no_network=True),
    )
    links = set()
    for row in root.xpath("//tr"):
        cells = row.xpath("./td")
        if len(cells) < 4 or cells[3].text_content().strip() not in {"10-K", "10-K/A"}:
            continue
        for href in cells[2].xpath(".//a/@href"):
            parsed = urlsplit(href)
            if parsed.path == "/ix" and not parsed.netloc and not parsed.fragment:
                query = parse_qs(parsed.query)
                if set(query) != {"doc"} or len(query["doc"]) != 1:
                    continue
                href = query["doc"][0]
            url = urljoin(folder, href)
            if url.startswith(folder) and re.fullmatch(
                r"[A-Za-z0-9_.-]+\.html?", url[len(folder) :]
            ):
                links.add(url)
    return next(iter(links)) if len(links) == 1 else None


def extract(raw, cik="0000034088"):
    if cik == "0001645590":
        return hpe_annual(raw)
    if cik != "0000034088":
        return {}
    """Require declared years, quarter/year columns, units and definition."""
    root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    body = " ".join(root.text_content().split()).lower()
    if not re.search(
        r"gross profit equals sales and other operating revenue less estimated costs associated with products sold",
        body,
    ):
        return {}
    output = {}
    for row in root.xpath("//tr"):
        cells = row.xpath("./td")
        if not cells or not re.fullmatch(
            r"Gross profit(?:\s*\(\d+\))?",
            " ".join(cells[0].text_content().split()),
            re.IGNORECASE,
        ):
            continue
        table = row.getparent()
        while table is not None and table.tag != "table":
            table = table.getparent()
        if (
            table is None
            or "millions of dollars"
            not in " ".join(table.text_content().split()).lower()
        ):
            continue
        headings = table.xpath("./tr|./tbody/tr")[:3]
        if len(headings) != 3:
            continue
        years = [
            c.text_content().strip()
            for c in headings[0].xpath("./td|./th")
            if re.fullmatch(r"20\d{2}", c.text_content().strip())
        ]
        labels = [
            c.text_content().strip()
            for c in headings[2].xpath("./td|./th")
            if c.text_content().strip()
        ]
        if not years or len(set(years)) != len(years):
            continue
        if labels != (["Quarter"] * 4 + ["Year"]) * len(years):
            continue
        values = []
        for cell in cells[1:]:
            value = (
                cell.text_content().strip().replace(",", "").replace("$", "").strip()
            )
            if not value:
                continue
            if not re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", value):
                break
            values.append(
                Decimal(value.strip("()")) * (-1 if value.startswith("(") else 1)
            )
        if len(values) != 5 * len(years):
            continue
        for index, year in enumerate(years):
            part = values[index * 5 : index * 5 + 5]
            # The annual total is explicitly reported; this reconciliation is
            # an independent layout/rounding guard, never a manufactured TTM.
            if abs(sum(part[:4]) - part[4]) > Decimal(2):
                continue
            end = year + "-12-31"
            value = str(part[4] * 1000000)
            if end in output and output[end]["value"] != value:
                raise ResearchError(
                    "Conflicting ExxonMobil annual gross-profit disclosures."
                )
            output[end] = {
                "value": value,
                "method": "reported_untagged_annual_gross_profit",
                "definition": DEFINITION,
            }
    return output


def hpe_annual(raw):
    """Use HPE's explicit company MD&A subtotal, before separate intangibles.

    Monetary columns are bound to declared fiscal years via their actual
    colspans. Percentages and segment tables cannot supply company amounts.
    Revenue/cost arithmetic checks the reported subtotal; it does not allocate
    the separately presented intangible amortization.
    """
    root = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    output = {}

    def text(cell):
        return " ".join(cell.text_content().split())

    def expanded(row):
        return [
            c for c in row.xpath("./td|./th") for _ in range(int(c.get("colspan", "1")))
        ]

    def number(cells):
        values = []
        for cell in dict.fromkeys(cells):
            value = text(cell).replace(",", "").replace("$", "").strip()
            if value in {"", "%"}:
                continue
            if not re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", value):
                return None
            values.append(
                Decimal(value.strip("()")) * (-1 if value.startswith("(") else 1)
            )
        return next(iter(values)) if len(values) == 1 else None

    for table in root.xpath("//table"):
        rows = table.xpath("./tr|./tbody/tr")
        contents = " ".join(text(r) for r in rows)
        if not re.search(r"For the fiscal years ended October\s+31,", contents, re.I):
            continue
        if "Dollars in millions" not in contents:
            continue
        # Segment tables use net revenue / GP too. Require the consolidated
        # operating-expense presentation as well as the monetary column layout.
        labels = {
            text(r.xpath("./td|./th")[0]).lower() for r in rows if r.xpath("./td|./th")
        }
        if (
            not {"research and development", "selling, general and administrative"}
            <= labels
        ):
            continue
        year_rows = [
            r
            for r in rows
            if len(
                [c for c in r.xpath("./td|./th") if re.fullmatch(r"20\d{2}", text(c))]
            )
            >= 2
        ]
        dollar_rows = [
            r
            for r in rows
            if len([c for c in r.xpath("./td|./th") if text(c) == "Dollars"]) >= 2
        ]
        if len(year_rows) != 1 or len(dollar_rows) != 1:
            continue
        years, columns = expanded(year_rows[0]), expanded(dollar_rows[0])
        if len(years) != len(columns):
            continue
        groups = []
        for i, cell in enumerate(columns):
            if text(cell) == "Dollars" and (i == 0 or columns[i - 1] is not cell):
                width = int(cell.get("colspan", "1"))
                year = text(years[i])
                if re.fullmatch(r"20\d{2}", year) and all(
                    text(c) == year for c in years[i : i + width]
                ):
                    groups.append((year, i, i + width))
        if len(groups) < 2 or len({g[0] for g in groups}) != len(groups):
            continue
        measures = {}
        for row in rows:
            cells = expanded(row)
            if len(cells) != len(columns):
                continue
            label = text(cells[0]).lower()
            key = (
                "revenue"
                if label == "net revenue"
                else "gross"
                if label == "gross profit"
                else "cost"
                if label.startswith("cost of sales")
                else None
            )
            if key:
                if key in measures:
                    measures[key] = None
                else:
                    measures[key] = [number(cells[a:b]) for _, a, b in groups]
        if any(not measures.get(k) for k in ("revenue", "cost", "gross")):
            continue
        for index, (year, _, _) in enumerate(groups):
            revenue, cost, gross = (
                measures[k][index] for k in ("revenue", "cost", "gross")
            )
            if (
                None in (revenue, cost, gross)
                or revenue <= 0
                or cost < 0
                or revenue - cost != gross
            ):
                continue
            end = year + "-10-31"
            result = {
                "value": str(gross * 1000000),
                "revenue": str(revenue * 1000000),
                "cost": str(cost * 1000000),
                "method": "reported_untagged_annual_gross_profit",
                "definition": "HPE issuer-reported consolidated annual gross profit from MD&A, before separately presented intangible amortization. This follows the reported definition rather than imposing a standardized production allocation.",
            }
            if end in output and output[end] != result:
                raise ResearchError("Conflicting HPE annual gross-profit disclosures.")
            output[end] = result
    return output
