"""Explicit filed-class evidence for deterministic financial fixtures."""

from aperture.filing_classes import inspect_cover


def cover(symbol="ABC", classes=None, preferred=False, cik="0000000001"):
    classes = classes or [("CommonStockMember", symbol, "Common stock")]
    if preferred:
        classes = [*classes, ("PreferredStockMember", symbol + "-P", "Preferred stock")]
    parts = []
    for i, (member, name, title) in enumerate(classes):
        parts.append(
            f'<xbrli:context id="c{i}"><xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">{cik}</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">fixture:{member}</xbrldi:explicitMember></xbrli:segment></xbrli:entity></xbrli:context>'
        )
        parts.append(
            f'<ix:nonNumeric name="dei:Security12bTitle" contextRef="c{i}">{title}</ix:nonNumeric><ix:nonNumeric name="dei:TradingSymbol" contextRef="c{i}">{name}</ix:nonNumeric>'
        )
    return (
        '<html xmlns:dei="http://xbrl.sec.gov/dei/2023" xmlns:us-gaap="http://fasb.org/us-gaap/2023">'
        + "".join(parts)
        + "</html>"
    ).encode()


def evidence(company, symbol="ABC", multi=False):
    result = {}
    classes = (
        [
            ("ClassA", symbol, "Class A Common Stock"),
            ("ClassB", symbol + ".B", "Class B Common Stock"),
        ]
        if multi
        else None
    )
    for row in company["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"][
        "USD/shares"
    ]:
        acc = row["accn"]
        result[acc] = inspect_cover(
            cover(symbol, classes),
            symbol=symbol,
            cik="0000000001",
            accession=acc,
            filed=row["filed"],
            url=f"https://www.sec.gov/Archives/edgar/data/1/{acc.replace('-', '')}/annual.htm",
        )
    return result
