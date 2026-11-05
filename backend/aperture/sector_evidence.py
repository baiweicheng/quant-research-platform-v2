"""Reviewed supplements to the public constituent-sector archive.

Dates identify the evidence, not a complete classification history. These
records never repair price/security identity or make a dependency investible.
"""

VERSION = "reviewed-sectors-2026-11-05-v1"

# Sector, issuer, evidence date, primary source. Business classifications are
# explicitly identified below rather than claimed to be licensed GICS records.
REVIEWED = {
    "NE": (
        "Energy",
        "Noble Corporation (drilling; issuer histories remain distinct)",
        None,
        "https://www.noblecorp.com/",
    ),
    "AIRC": (
        "Real Estate",
        "Apartment Income REIT",
        None,
        "https://www.aircommunities.com/en/about-us.html",
    ),
    "AZN": (
        "Health Care",
        "AstraZeneca",
        None,
        "https://www.astrazeneca.com/our-company.html",
    ),
    "CCEP": (
        "Consumer Staples",
        "Coca-Cola Europacific Partners",
        None,
        "https://ir.cocacolaep.com/static-files/b557e44b-afed-4f79-943c-c6e66bcbc237",
    ),
    "CP": (
        "Industrials",
        "Canadian Pacific Kansas City",
        None,
        "https://www.cpkcr.com/en/about-cpkc",
    ),
    "DKS": (
        "Consumer Discretionary",
        "DICK'S Sporting Goods",
        None,
        "https://www.sec.gov/Archives/edgar/data/1089063/000108906326000007/dks-20260131.htm",
    ),
    "DTM": (
        "Energy",
        "DT Midstream",
        "2021-06-28",
        "https://press.spglobal.com/2021-06-28-DT-Midstream-Set-to-Join-S-P-MidCap-400",
    ),
    "EMBC": (
        "Health Care",
        "Embecta",
        "2026-06-05",
        "https://press.spglobal.com/2026-06-05-Marvell-Technology-and-Flex-Set-to-Join-S-P-500-Others-to-Join-S-P-MidCap-400-and-S-P-SmallCap-600",
    ),
    "FBIN": (
        "Industrials",
        "Fortune Brands Innovations",
        "2022-12-12",
        "https://press.spglobal.com/2022-12-12-First-Solar-Set-to-Join-S-P-500-Fortune-Brands-Innovations-to-Join-S-P-MidCap-400-MasterBrand-to-Join-S-P-SmallCap-600",
    ),
    "FTRE": (
        "Health Care",
        "Fortrea",
        "2023-06-28",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20230628-1464896/1464896_5-bwa-lh.pdf",
    ),
    "GIL": (
        "Consumer Discretionary",
        "Gildan Activewear",
        None,
        "https://gildancorp.com/en/company/",
    ),
    "GRAL": ("Health Care", "GRAIL", None, "https://grail.com/about-us/"),
    "IIVI": (
        "Information Technology",
        "II-VI / Coherent",
        None,
        "https://www.coherent.com/legal/privacy-statement",
    ),
    "KLG": (
        "Consumer Staples",
        "WK Kellogg",
        "2023-09-28",
        "https://press.spglobal.com/2023-09-28-Veralto-Set-to-Join-S-P-500-Vestis-to-Join-S-P-MidCap-400-Others-to-Join-S-P-SmallCap-600",
    ),
    "LYLT": (
        "Communication Services",
        "Loyalty Ventures",
        "2021-11-04",
        "https://press.spglobal.com/2021-11-04-Loyalty-Ventures-Set-to-Join-S-P-SmallCap-600",
    ),
    "MBGL": (
        "Information Technology",
        "Mobility Global",
        "2026-07-01",
        "https://www.sec.gov/Archives/edgar/data/2090312/000110465926080006/tm2619098d1_ex99-1.htm",
    ),
    "MRP": (
        "Real Estate",
        "Millrose Properties",
        "2025-02-05",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20250205-1476446/1476446_5-len-mrp-spin.pdf",
    ),
    "NXT": (
        "Industrials",
        "Nextracker / Nextpower",
        "2024-06-07",
        "https://press.spglobal.com/2024-06-07-KKR%2C-CrowdStrike-Holdings-and-GoDaddy-Set-to-Join-S-P-500-Others-to-Join-S-P-MidCap-400-and-S-P-SmallCap-600",
    ),
    "ONL": (
        "Real Estate",
        "Orion Office REIT / Orion Properties",
        "2024-02-27",
        "https://www.onlreit.com/investors/sec-filings/all-sec-filings/content/0001873923-24-000007/0001873923-24-000007.pdf",
    ),
    "PHIN": (
        "Consumer Discretionary",
        "PHINIA",
        "2023-06-28",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20230628-1464896/1464896_5-bwa-lh.pdf",
    ),
    "RAL": (
        "Information Technology",
        "Ralliant",
        "2025-06-25",
        "https://press.spglobal.com/2025-06-25-Ralliant-Set-to-Join-S-P-SmallCap-600",
    ),
    "SGI": (
        "Consumer Discretionary",
        "Somnigroup (formerly Tempur Sealy)",
        None,
        "https://investor.somnigroup.com/",
    ),
    "SLVM": (
        "Materials",
        "Sylvamo",
        "2021-09-28",
        "https://press.spglobal.com/2021-09-28-Sylvamo-Set-to-Join-S-P-SmallCap-600",
    ),
    "THNPF": ("Energy", "Technip Energies", None, "https://www.ten.com/en"),
    "VGNT": (
        "Consumer Discretionary",
        "Versigent",
        "2026-03-30",
        "https://press.spglobal.com/2026-03-30-Versigent-Set-to-Join-S-P-SmallCap-600",
    ),
    "VREX": (
        "Health Care",
        "Varex Imaging",
        "2024-09-06",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20240906-1474143/1474143_septembershuffle546.pdf",
    ),
    "VSNT": (
        "Communication Services",
        "Versant Media Group",
        "2025-12-23",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20251223-1481212/1481212_cmcsa-vsnt-snv-546.pdf",
    ),
    "VTS": ("Energy", "Vitesse Energy", None, "https://ir.vitesse-vts.com/"),
    "ZIMV": (
        "Health Care",
        "ZimVie",
        "2023-03-03",
        "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20230303-1461866/1461866_shufflemarch2023.pdf",
    ),
}

BUSINESS_INFERENCES = {
    "NE",
    "AIRC",
    "AZN",
    "CCEP",
    "CP",
    "DKS",
    "GIL",
    "GRAL",
    "IIVI",
    "MBGL",
    "ONL",
    "SGI",
    "THNPF",
    "VTS",
}

# These are explicitly reviewed issuer/quote relationships, never arbitrary
# ticker-prefix stripping. DD.OLD must not inherit today's different DD issuer.
ALIASES = {
    "AABA": (
        "YHOO",
        "2017-06-16",
        "https://www.sec.gov/Archives/edgar/data/1011006/000119312517206955/d389206d8k.htm",
    ),
    "WYND": (
        "WYN",
        "2018-05-31",
        "https://www.sec.gov/Archives/edgar/data/1361658/000110465918032536/a18-13272_2ex99d1.htm",
    ),
    "DD.OLD": (
        "DD",
        "2017-08-31",
        "https://www.investors.dupont.com/news-and-media/press-release-details/2017/DowDuPont-Merger-Successfully-Completed/default.aspx",
    ),
    "DOW.OLD": (
        "DOW",
        "2017-08-31",
        "https://www.investors.dupont.com/news-and-media/press-release-details/2017/DowDuPont-Merger-Successfully-Completed/default.aspx",
    ),
}

WARRANTS = {
    "BBBY.WS": (
        "Consumer Discretionary",
        "Bed Bath & Beyond (formerly Beyond, not the bankrupt former BBBY issuer)",
        "https://www.sec.gov/Archives/edgar/data/1130713/000113071326000018/bbby-20251231.htm",
    ),
    "GME.WS": (
        "Consumer Discretionary",
        "GameStop",
        "https://www.sec.gov/Archives/edgar/data/1326380/000132638025000084/gme-form8xa.htm",
    ),
    "SKYD.WS": (
        "Communication Services",
        "Skydance / Paramount",
        "https://ir.paramount.com/node/73416/html",
    ),
    "XRXDW": (
        "Information Technology",
        "Xerox",
        "https://investors.xerox.com/static-files/c2a19261-7316-4af4-b49a-9d05df0525ff",
    ),
}

FUNDS = {
    "MYN": (
        "BlackRock MuniYield New York Quality Fund",
        "https://www.blackrock.com/us/individual/products/240271/blackrock-muniyield-new-york-insured-fund-inc-usd-fund",
    ),
}
