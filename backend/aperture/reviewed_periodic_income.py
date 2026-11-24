"""Comparable income recovered from the issuer's own original SEC filing."""

from dataclasses import replace
from datetime import date
from typing import NamedTuple

VERSION = "reviewed-original-periodic-income-v1"


class Statement(NamedTuple):
    document: str
    end: str
    start: str
    prior_end: str
    prior_start: str
    current: int
    prior: int
    unit: int
    form: str = "10-Q"
    concept: str = "NetIncomeLoss"


# Each entry is keyed by SEC registrant, original accession and filing date.
# Values come from the parent issuer's GAAP statement, on the same basis for
# both periods. The SEC submission date remains the signal's availability date.
_STATEMENTS = {
    # The saved Henry Schein submission metadata used the filing date as the
    # fiscal end. The original filings confirm the corrected dates and amounts.
    ("0001000228", "0001000228-16-000102", "2016-11-02"): Statement(
        "the10q_3q16.htm",
        "2016-09-24",
        "2015-12-27",
        "2015-09-26",
        "2014-12-28",
        367_562,
        349_110,
        1_000,
    ),
    ("0001000228", "0001000228-17-000025", "2017-05-09"): Statement(
        "the10q_1q17.htm",
        "2017-04-01",
        "2017-01-01",
        "2016-03-26",
        "2015-12-27",
        140_748,
        113_752,
        1_000,
    ),
    ("0001000228", "0001000228-17-000049", "2017-08-08"): Statement(
        "the10q_2q17.htm",
        "2017-07-01",
        "2017-01-01",
        "2016-06-25",
        "2015-12-27",
        276_803,
        233_849,
        1_000,
    ),
    ("0001000228", "0001000228-17-000058", "2017-11-06"): Statement(
        "the10q_3q17.htm",
        "2017-09-30",
        "2017-01-01",
        "2016-09-24",
        "2015-12-27",
        414_834,
        367_562,
        1_000,
    ),
    ("0001000228", "0001000228-18-000012", "2018-02-21"): Statement(
        "the10k_2017.htm",
        "2017-12-30",
        "2017-01-01",
        "2016-12-31",
        "2015-12-27",
        406_299,
        506_778,
        1_000,
        form="10-K",
    ),
    ("0001000228", "0001000228-18-000022", "2018-05-08"): Statement(
        "the10q_1q18.htm",
        "2018-03-31",
        "2017-12-31",
        "2017-04-01",
        "2017-01-01",
        140_218,
        140_748,
        1_000,
    ),
    ("0001000228", "0001000228-18-000039", "2018-08-06"): Statement(
        "the10q_2q18.htm",
        "2018-06-30",
        "2017-12-31",
        "2017-07-01",
        "2017-01-01",
        281_430,
        276_803,
        1_000,
    ),
    # Mid-America's joint filing contains separate parent and partnership statements.
    ("0000912595", "0000912595-17-000021", "2017-10-26"): Statement(
        "maa930201710q.htm",
        "2017-09-30",
        "2017-01-01",
        "2016-09-30",
        "2016-01-01",
        204_929,
        172_836,
        1_000,
    ),
    ("0000912595", "0001193125-26-326153", "2026-07-30"): Statement(
        "maa-20260630.htm",
        "2026-06-30",
        "2026-01-01",
        "2025-06-30",
        "2025-01-01",
        246_109,
        289_800,
        1_000,
    ),
    # Duplicated prior-year contexts in companyfacts obscured the longer pair.
    ("0001137789", "0001137789-21-000028", "2021-04-29"): Statement(
        "stx-20210402.htm",
        "2021-04-02",
        "2020-07-04",
        "2020-04-03",
        "2019-06-29",
        832,
        838,
        1_000_000,
    ),
    ("0001002047", "0001193125-25-297237", "2025-11-25"): Statement(
        "ntap-20251024.htm",
        "2025-10-24",
        "2025-04-26",
        "2024-10-25",
        "2024-04-27",
        538,
        547,
        1_000_000,
    ),
    # The snapshot captures the filing metadata but lacks the original pair.
    ("0000721371", "0000721371-26-000018", "2026-04-30"): Statement(
        "cah-20260331.htm",
        "2026-03-31",
        "2025-07-01",
        "2025-03-31",
        "2024-07-01",
        1_316,
        1_322,
        1_000_000,
    ),
    ("0000092122", "0000092122-26-000054", "2026-07-30"): Statement(
        "so-20260630.htm",
        "2026-06-30",
        "2026-01-01",
        "2025-06-30",
        "2025-01-01",
        2_531,
        2_214,
        1_000_000,
    ),
    ("0001109357", "0001109357-26-000080", "2026-07-30"): Statement(
        "exc-20260630.htm",
        "2026-06-30",
        "2026-01-01",
        "2025-06-30",
        "2025-01-01",
        1_315,
        1_300,
        1_000_000,
        concept="NetIncomeLossAvailableToCommonStockholdersBasic",
    ),
    ("0001751788", "0001751788-26-000147", "2026-07-24"): Statement(
        "dow-20260630.htm",
        "2026-06-30",
        "2026-01-01",
        "2025-06-30",
        "2025-01-01",
        188,
        -1_142,
        1_000_000,
        concept="NetIncomeLossAvailableToCommonStockholdersBasic",
    ),
}


def recover(cik, report):
    filed = str(report.filed)
    statement = _STATEMENTS.get((cik, report.accession, filed))
    if statement is None or report.form != statement.form:
        return report
    allowed_ends = {statement.end}
    if cik == "0001000228":
        allowed_ends.add(filed)
    if str(report.end) not in allowed_ends:
        return report
    accession = report.accession.replace("-", "")
    return replace(
        report,
        end=date.fromisoformat(statement.end),
        start=date.fromisoformat(statement.start),
        prior_end=date.fromisoformat(statement.prior_end),
        prior_start=date.fromisoformat(statement.prior_start),
        concept=statement.concept,
        income=statement.current * statement.unit,
        previous=statement.prior * statement.unit,
        source_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{statement.document}",
    )
