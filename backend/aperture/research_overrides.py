"""Reviewed corrections to retrospective ticker labels and vendor records.

These are dated, source-linked exceptions, never guessed mappings. Vendor
records remain in captured provenance alongside the applied correction.
"""

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
        "symbol": "APTV",
        "quote": "DLPH",
        "until": "2017-12-04",
        "source": "https://www.miaxglobal.com/sites/default/files/alert-files/DLPH_Dist_Name_42232.pdf",
    },
]

# Conflicting vendor records are quarantined, not silently substituted. These
# parent distributions are not changes in the number of parent shares.
CONFLICTS = {
    "78f521c7-d5ad-42fe-a534-5c5ac1497d33": "WestRock distributed one Ingevity share per six parent shares; the vendor labels this as a parent reverse split. https://www.ingevity.com/news/press-releases/ingevity-corporation-formed-with-completion-of-spinoff-from-westrock-company/",
    "3fa6fc16-b76e-4158-83d9-e534db36334b": "HCP distributed one QCP share per five parent shares; a 1.098 parent split is not supported by the issuer report. https://filecache.investorroom.com/mr5ir_healthpeakproperties/251/download/HCP%202016%20Annual%20Report.pdf",
    "843a4a07-11ae-4d9f-915d-2d08b817573d": "Old IR retained parent shares as TT and distributed 0.8824 new IR shares; this is not a parent reverse split. https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm",
    "6815b560-3059-4c19-a269-fd131bd6d460": "TT/old IR distribution terms conflict with the vendor parent split classification. https://www.sec.gov/Archives/edgar/data/1466258/000146625822000031/tt-20211231.htm",
    "0c3b2854-cfc1-46b1-91c2-cf22aef1a594": "The alleged RJF 2023 stock dividend conflicts with issuer split history and the adjusted-price evidence. https://www.raymondjames.com/investor-relations/shareholder-information/stock-split-history",
}
