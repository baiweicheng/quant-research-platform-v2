"""Reviewed corrections to retrospective ticker labels and vendor records.

These are dated, source-linked exceptions, never guessed mappings. Vendor
records remain in captured provenance alongside the applied correction.
"""

# ``quote`` traded the same security under an earlier ticker through
# ``until``. ``asof`` selects the provider's dated symbol mapping for those
# quotes when the transition date itself maps to a different listing.
# Corporate actions recorded under ``quote`` through ``until`` belong to
# ``symbol`` and are requested together with the indexed labels.
ALIASES = [
    {
        "symbol": "AABA",
        "quote": "YHOO",
        "until": "2017-06-16",
        "source": "https://www.sec.gov/Archives/edgar/data/1011006/000119312517206955/d389206d8k.htm",
    },
    {
        "symbol": "WYND",
        "quote": "WYN",
        "until": "2018-05-31",
        "source": "https://www.sec.gov/Archives/edgar/data/1361658/000110465918032536/a18-13272_2ex99d1.htm",
    },
    {
        "symbol": "BHGE",
        "quote": "BHI",
        "until": "2017-07-03",
        "source": "https://www.sec.gov/Archives/edgar/data/808362/000119312517220863/d343454d8k12b.htm",
    },
    {
        # As of the December 4 transition the provider maps DLPH to Aptiv's
        # new listing, which starts on November 17, 2017. The November 1
        # vintage selects the original Delphi Automotive history.
        "symbol": "APTV",
        "quote": "DLPH",
        "until": "2017-12-04",
        "asof": "2017-11-01",
        "source": "https://www.miaxglobal.com/sites/default/files/alert-files/DLPH_Dist_Name_42232.pdf",
    },
    {
        "symbol": "DAY",
        "quote": "CDAY",
        "until": "2024-01-31",
        "source": "https://www.sec.gov/Archives/edgar/data/1725057/000095017024009619/day-20240131.htm",
    },
    {
        # L Brands was renamed Bath & Body Works after the August 2, 2021
        # close; the same issuer and shares continued as BBWI.
        "symbol": "BBWI",
        "quote": "LB",
        "until": "2021-08-02",
        "source": "https://www.sec.gov/Archives/edgar/data/701985/000114036121026658/nt10026698x7_8k.htm",
    },
    {
        # Each FMC Technologies share became one TechnipFMC share. The
        # original FTI quotes through January 13, 2017 continue that holding.
        "symbol": "FTI",
        "quote": "FTI",
        "until": "2017-01-13",
        "source": "https://www.sec.gov/Archives/edgar/data/1135152/000119312517010427/d326621d8k.htm",
    },
]

# Tickers reused by a successor issuer on a reviewed first session. Earlier
# rosters, actions and quotes for the ticker belong to ``<ticker>.OLD``,
# quoted with the predecessor's final provider vintage.
PREDECESSORS = {
    "DOW": ("2017-09-01", "2017-08-31"),
    "DD": ("2017-09-01", "2017-08-31"),
    "FOXA": ("2019-03-19", "2019-03-18"),
    "FOX": ("2019-03-19", "2019-03-18"),
}

# Reviewed same-issuer ticker transitions absent from the vendor's rename
# records. They map indexed labels and corporate actions to the continuing
# security; prices come from the matching alias above.
RENAMES = [
    {
        "old_symbol": "LB",
        "new_symbol": "BBWI",
        "process_date": "2021-08-03",
        "source": "https://www.sec.gov/Archives/edgar/data/701985/000114036121026658/nt10026698x7_8k.htm",
    },
    {
        "old_symbol": "CDAY",
        "new_symbol": "DAY",
        "process_date": "2024-02-01",
        "source": "https://www.sec.gov/Archives/edgar/data/1725057/000095017024009619/day-20240131.htm",
    },
]

# Conflicting vendor records are quarantined, not silently substituted. These
# parent distributions are not changes in the number of parent shares. The
# reviewed distributions in ``reviewed_events`` replace them when their
# primary-source, quote and child-price checks pass; otherwise this gate stays.
CONFLICTS = {
    "78f521c7-d5ad-42fe-a534-5c5ac1497d33": "WestRock distributed one Ingevity share per six parent shares; the vendor labels this as a parent reverse split. https://www.ingevity.com/news/press-releases/ingevity-corporation-formed-with-completion-of-spinoff-from-westrock-company/",
    "3fa6fc16-b76e-4158-83d9-e534db36334b": "HCP distributed one QCP share per five parent shares; a 1.098 parent split is not supported by the issuer report. https://filecache.investorroom.com/mr5ir_healthpeakproperties/251/download/HCP%202016%20Annual%20Report.pdf",
    "843a4a07-11ae-4d9f-915d-2d08b817573d": "Old IR retained parent shares as TT and distributed 0.8824 new IR shares; this is not a parent reverse split. https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm",
    "6815b560-3059-4c19-a269-fd131bd6d460": "TT/old IR distribution terms conflict with the vendor parent split classification. https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm",
}
