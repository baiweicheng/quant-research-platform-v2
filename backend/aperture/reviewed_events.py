"""Reviewed terminal conversions, distributions and listing lifetimes.

Every record names a primary SEC document (fingerprinted at acquisition), the
exact captured quote vintage and closing prices it was reviewed against, and
any vendor instruction it supersedes. Changed quotes, a changed vendor record
or a different issuer vintage fail closed: the security keeps an input issue
and stays excluded instead of inheriting the correction. Original provider
records remain in provenance as rejected or displaced evidence.

These records do not create general rules for unreviewed securities.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from .action_evidence import primary_matches
from .domain import ZERO, ResearchError, decimal

VERSION = "reviewed-security-events-v1"
SPLIT_CONFLICT = "Split terms conflict with the independent adjusted-price series."
DISTRIBUTION_NOTE = "Reviewed spin-off share delivery uses closing-price total-return research; strict payment-date delivery is unsupported."


def _t(symbol, ratio):
    return {"symbol": symbol, "ratio": ratio}


# Departed securities whose completed consideration the vendor omits, dates
# incorrectly, or prices only through unlisted rights. ``targets`` are shares
# received per source share; ``cash`` is per source share. Non-transferable
# contingent rights are recorded in ``rights`` and are not valued unless paid.
TERMINALS = {
    "AET": {
        "quote_asof": "2018-11-28",
        "last_trading": "2018-11-28",
        "last_close": "212.7",
        "effective": "2018-11-29",
        "legal_effective": "2018-11-28",
        "targets": [_t("CVS", "0.8378")],
        "cash": "145.00",
        "url": "https://www.sec.gov/Archives/edgar/data/1122304/000112230418000178/form8-k.htm",
        "sha256": "4c66a85189531e10d787be5f7866ef0d0ad0c863bf9dc13896724a3e712219df",
        "content_sha256": "f59d6431b2e438421c585f754634bc7e4b70c47b0df7288001bc44e78b990fba",
        "basis": "Completed CVS Health merger: 0.8378 CVS shares and $145.00 cash per Aetna share; NYSE trading suspended before the November 29, 2018 open.",
    },
    "BCR": {
        "quote_asof": "2017-12-28",
        "last_trading": "2017-12-28",
        "last_close": "331.24",
        "effective": "2017-12-29",
        "legal_effective": "2017-12-29",
        "targets": [_t("BDX", "0.5077")],
        "cash": "222.93",
        "url": "https://www.sec.gov/Archives/edgar/data/9892/000119312517383532/d489045d8k.htm",
        "sha256": "1efcf9495801983256fa85f129d67bad9fdf5fd0c2abb4892150b030f1709436",
        "content_sha256": "28f4eb62a90e16a4aa7312a040d14e8539abf7d87a0bdc1293070ee7de10e7ad",
        "basis": "Completed BD merger on December 29, 2017: $222.93 cash and 0.5077 BD shares per Bard share; NYSE trading halted on the closing date.",
    },
    "CA": {
        "quote_asof": "2018-11-05",
        "last_trading": "2018-11-02",
        "last_close": "44.44",
        "effective": "2018-11-05",
        "legal_effective": "2018-11-05",
        "targets": [],
        "cash": "44.50",
        "truncate": True,
        "url": "https://www.sec.gov/Archives/edgar/data/356028/000119312518317918/d631849d8k.htm",
        "sha256": "3c1de8b0981e624db5ea655bed5036f8b71b8c96d027933d58b29c18643d07d8",
        "content_sha256": "155cbed6fa7727ed66d48198519bbe81aeb37df17af7f2625084c871a605228f",
        "basis": "Completed Broadcom acquisition on November 5, 2018: $44.50 cash per CA share. The captured November 5 quote is a flat zero-volume mark, not a trade, and is not retained as an executable price.",
    },
    "COL": {
        "quote_asof": "2018-11-26",
        "last_trading": "2018-11-26",
        "last_close": "141.04",
        "effective": "2018-11-27",
        "legal_effective": "2018-11-26",
        "targets": [_t("RTX", "0.37525")],
        "cash": "93.33",
        "url": "https://www.sec.gov/Archives/edgar/data/1137411/000119312518334170/d598640d8k.htm",
        "sha256": "59db5397224113fc20d77c321558d3b257741d630138d5da70ef331499a40927",
        "content_sha256": "f3af79583ff041e7b3fa40d5c158462b608f7e0887639e9b8e92bfa6f1bea0b3",
        "basis": "Completed United Technologies merger on November 26, 2018: $93.33 cash and 0.37525 UTC shares per Rockwell Collins share; NYSE trading halted after the closing session. UTC later became RTX under the same listing.",
    },
    "CSRA": {
        "quote_asof": "2018-04-03",
        "last_trading": "2018-04-03",
        "last_close": "41.23",
        "effective": "2018-04-04",
        "legal_effective": "2018-04-03",
        "targets": [],
        "cash": "41.25",
        "url": "https://www.sec.gov/Archives/edgar/data/1646383/000119312518106369/d562306d8k.htm",
        "sha256": "b932e411a7e78c725490322d8b082760b7096c0a77dffc4cea94c2867f5fac38",
        "content_sha256": "b0cfb4a3ba1fb33ab923aca9305fef38585a5fc601e66efdcaafeaede10c7d52",
        "basis": "General Dynamics completed its tender offer and merger on April 3, 2018 at $41.25 cash per CSRA share; the shares then ceased trading on the NYSE.",
    },
    "HAR": {
        "quote_asof": "2017-03-10",
        "last_trading": "2017-03-10",
        "last_close": "111.5",
        "effective": "2017-03-13",
        "legal_effective": "2017-03-10",
        "targets": [],
        "cash": "112.00",
        "url": "https://www.sec.gov/Archives/edgar/data/800459/000119312517078968/d184457d8k.htm",
        "sha256": "3813d9669b28760710f0a0e2bd3bd593ca3f2a1b8b30fb17171f2944a23d3148",
        "content_sha256": "7f1dfb7684d6f84fc73ee237566cfe578c658b5a6aec593aa8964074292d9f8f",
        "basis": "Completed Samsung acquisition: $112.00 cash per Harman share; NYSE trading suspended before the March 13, 2017 open.",
    },
    "LLL": {
        "quote_asof": "2019-06-28",
        "last_trading": "2019-06-28",
        "last_close": "245.17",
        "effective": "2019-07-01",
        "legal_effective": "2019-06-29",
        "targets": [_t("LHX", "1.30")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1039101/000114036119012103/form8k.htm",
        "sha256": "b421229d063ebf2ee9117769830b92bb2aff2ce116af470a7ada50dbc7f98a2a",
        "content_sha256": "6dc009590f10d7f61c01d9b98cf6a1e89a7410ad022b4e00f0db96ee474a4d09",
        "basis": "Completed Harris merger on June 29, 2019: 1.30 L3Harris shares per L3 share; NYSE trading suspended before the July 1, 2019 open.",
    },
    "LLTC": {
        "quote_asof": "2017-03-10",
        "last_trading": "2017-03-10",
        "last_close": "65.08",
        "effective": "2017-03-13",
        "legal_effective": "2017-03-10",
        "targets": [_t("ADI", "0.2321")],
        "cash": "46.00",
        "url": "https://www.sec.gov/Archives/edgar/data/791907/000119312517078946/d340243d8k.htm",
        "sha256": "7b67f8a402d296638f6af2dc7f3e8c683539ae62c9bec667f48b67735e39072d",
        "content_sha256": "e1385ae908fc7d8cbea366f47654eaaffd2ba9d4d8e6e2b5e63a76560fa0e472",
        "basis": "Completed Analog Devices merger: $46.00 cash and 0.2321 ADI shares per Linear share; Nasdaq trading suspended after the March 10, 2017 close.",
    },
    "MJN": {
        "quote_asof": "2017-06-14",
        "last_trading": "2017-06-14",
        "last_close": "89.98",
        "effective": "2017-06-15",
        "legal_effective": "2017-06-15",
        "targets": [],
        "cash": "90.00",
        "url": "https://www.sec.gov/Archives/edgar/data/1452575/000110465917039502/a17-15238_18k.htm",
        "sha256": "9011ee9f7c9b8f6c2d873dd909ed5346e37a22fdd1a1083f3d6e27dcba5eb233",
        "content_sha256": "d3639e9dcf9470c0349f9d265563ee0bbd75fe88b3f76349ca0b04c09240a234",
        "basis": "Completed Reckitt Benckiser merger: $90.00 cash per Mead Johnson share; NYSE trading suspended before the June 15, 2017 open.",
    },
    "MON": {
        "quote_asof": "2018-06-06",
        "last_trading": "2018-06-06",
        "last_close": "127.95",
        "effective": "2018-06-07",
        "legal_effective": "2018-06-07",
        "targets": [],
        "cash": "128.00",
        "url": "https://www.sec.gov/Archives/edgar/data/1110783/000119312518188226/d587681d8k.htm",
        "sha256": "2f73d523b902d45e87ba50339130bc7a9f3865e147f07f0c2ebcba7c6e6c231a",
        "content_sha256": "38fb66e3feb24e9ef0c8db1eab3982f2e8c83962be9d2a7bffe9e01e70a4d249",
        "basis": "Completed Bayer merger: $128.00 cash per Monsanto share; withdrawn from NYSE listing before the June 7, 2018 open.",
    },
    "PX": {
        "quote_asof": "2018-10-30",
        "last_trading": "2018-10-30",
        "last_close": "164.5",
        "effective": "2018-10-31",
        "legal_effective": "2018-10-31",
        "targets": [_t("LIN", "1")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/884905/000119312518313154/d646523d8k.htm",
        "sha256": "afda75b2157c34bdf51757085cc3d03c5a56deb671e08f6e59f56785b9a58ee1",
        "content_sha256": "04a205d3c510f74e4317b690b98b662ab7f609dfcc332480a9d57c565d3271ca",
        "basis": "Completed Linde plc business combination: one Linde plc share per Praxair share; Praxair suspended as of the October 30, 2018 close.",
    },
    "RAI": {
        "quote_asof": "2017-07-24",
        "last_trading": "2017-07-24",
        "last_close": "65.4",
        "effective": "2017-07-25",
        "legal_effective": "2017-07-25",
        "targets": [_t("BTI", "0.5260")],
        "cash": "29.44",
        "url": "https://www.sec.gov/Archives/edgar/data/1275283/000119312517235158/d397089d8k.htm",
        "sha256": "7f7a46c262b61cfdd1ebde40b26e1cf1e488bd0ddb3cdcc951e44b0581332818",
        "content_sha256": "9a3fcf84ebad1bad89d140ba5458ed46d4eeea562217df1a8a8e77d887c9c94c",
        "basis": "Completed BAT merger: BAT ADSs representing 0.5260 ordinary share plus $29.44 cash per Reynolds share; NYSE trading suspended before the July 25, 2017 open.",
    },
    "RHT": {
        "quote_asof": "2019-07-12",
        "last_trading": "2019-07-08",
        "last_close": "187.71",
        "effective": "2019-07-09",
        "legal_effective": "2019-07-09",
        "targets": [],
        "cash": "190.00",
        "url": "https://www.sec.gov/Archives/edgar/data/1087423/000095014219001516/eh1900894_8k-rh.htm",
        "sha256": "b269a28bea54daa3d7990e96cb82e7c5a257ae7480b29ebfc31f2464142775ec",
        "content_sha256": "c72faf2591ab4c67266ae969510c5a0108f8eaded2baa2b244fbae951d11bf48",
        "basis": "Completed IBM acquisition: $190.00 cash per Red Hat share; NYSE trading suspended before the July 9, 2019 open.",
    },
    "RTN": {
        "quote_asof": "2020-04-03",
        "last_trading": "2020-04-02",
        "last_close": "116.96",
        "effective": "2020-04-03",
        "legal_effective": "2020-04-03",
        "targets": [_t("RTX", "2.3348")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1047122/000119312520097237/d827106d8k.htm",
        "sha256": "077b9f0350043ea08acd77e7207d3095f3f97fcd875e3d7b22f24397684d4537",
        "content_sha256": "74735d2c7c9d3f34b54bda7dde420982b85955e1f4cad12c98f981cc74c24c2d",
        "basis": "Completed United Technologies merger: 2.3348 UTC (renamed RTX) shares per Raytheon share; NYSE trading suspended before the April 3, 2020 open. These shares are issued after UTC's Carrier and Otis distributions and do not receive them.",
    },
    "SE": {
        "quote_asof": "2017-02-24",
        "last_trading": "2017-02-24",
        "last_close": "40.68",
        "effective": "2017-02-27",
        "legal_effective": "2017-02-27",
        "targets": [_t("ENB", "0.984")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1373835/000119312517057856/d338638d8k.htm",
        "sha256": "618f8d15d1ca93fee9f18737ef5b47cf43e1aad64acb6a5d6821fc1c7f6c5a9b",
        "content_sha256": "f28d8ae207c3d7ee80c1e3412a6d38ab2c8455b79717742d49667fadad62d797",
        "basis": "Completed Enbridge merger: 0.984 Enbridge common shares per Spectra Energy share; NYSE trading suspended before the February 27, 2017 open.",
    },
    "SNI": {
        "quote_asof": "2018-03-06",
        "last_trading": "2018-03-06",
        "last_close": "90.04",
        "effective": "2018-03-07",
        "legal_effective": "2018-03-06",
        "targets": [_t("DISCK", "1.0584")],
        "cash": "65.82",
        "url": "https://www.sec.gov/Archives/edgar/data/1430602/000119312518072063/d545990d8k.htm",
        "sha256": "2d3a2f8f7f055a1111c91bf745bd567e2c559b2cf956ca8a0344dc29b934c6d4",
        "content_sha256": "7fcb5a6093dc9940f27c36f36480384ec748154bb687f8f47f13cf0b08eeefd7",
        "basis": "Completed Discovery merger: $65.82 cash and 1.0584 Discovery Series C shares per Scripps share; delisted from Nasdaq effective March 7, 2018.",
    },
    "SPLS": {
        "quote_asof": "2017-09-12",
        "last_trading": "2017-09-12",
        "last_close": "10.25",
        "effective": "2017-09-13",
        "legal_effective": "2017-09-12",
        "targets": [],
        "cash": "10.25",
        "url": "https://www.sec.gov/Archives/edgar/data/791519/000110465917056725/a17-21547_18k.htm",
        "sha256": "fed8ebc540d540b55afbecb527d09a376ab4b1a0f50f9b4b2e25370ea41ef74b",
        "content_sha256": "317a4785836662126605543fa3e5b5fb3fd1421cacba0c26e90c8ab01aa822ce",
        "basis": "Completed Sycamore acquisition: $10.25 cash per Staples share; Nasdaq trading suspended before the September 13, 2017 open.",
    },
    "STI": {
        "quote_asof": "2019-12-06",
        "last_trading": "2019-12-06",
        "last_close": "70.13",
        "effective": "2019-12-09",
        "legal_effective": "2019-12-06",
        "targets": [_t("TFC", "1.295")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/750556/000119312519308629/d808889d8k.htm",
        "sha256": "4073356f1122f564efafe37ab3b69ab2fc7f9ffbace55026448f7ca5860090c3",
        "content_sha256": "1eca07d870a93575aa5b3a2e46f9751e7f57e329b7c4c5a2bcc1a18ce2ad93d2",
        "basis": "Completed BB&T merger on December 6, 2019: 1.295 BB&T (renamed Truist, TFC) shares per SunTrust share; NYSE trading of SunTrust suspended after the closing.",
    },
    "STJ": {
        "quote_asof": "2017-01-04",
        "last_trading": "2017-01-04",
        "last_close": "80.82",
        "effective": "2017-01-05",
        "legal_effective": "2017-01-04",
        "targets": [_t("ABT", "0.8708")],
        "cash": "46.75",
        "url": "https://www.sec.gov/Archives/edgar/data/203077/000110465917000936/a16-23886_18k.htm",
        "sha256": "a88b28471db8f4856c006fefe2b39cbe3689ecdf927f2757d73791f6bcab45b6",
        "content_sha256": "9cf7ec1e9dbae06a27fa2b9345c9cbee55e58039aacebed3a6667ac523356d57",
        "basis": "Completed Abbott merger: 0.8708 Abbott shares and $46.75 cash per St. Jude share; NYSE trading suspended after the January 4, 2017 close.",
    },
    "TSS": {
        "quote_asof": "2019-09-20",
        "last_trading": "2019-09-17",
        "last_close": "133.27",
        "effective": "2019-09-18",
        "legal_effective": "2019-09-17",
        "targets": [_t("GPN", "0.8101")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/721683/000119312519250774/d803104d8k.htm",
        "sha256": "14d288bbae061bc114877a9fa5d859c3147d9c30eba31b6aff97f6a6c3b2ccc7",
        "content_sha256": "e5eba9e78d12d71c34a6efc9934e651bb99a261deb7a07ce7c982c5d993932ce",
        "basis": "Completed Global Payments merger on September 17, 2019: 0.8101 GPN shares per TSYS share; NYSE trading halted before the September 18, 2019 open.",
    },
    "TWX": {
        "quote_asof": "2018-06-14",
        "last_trading": "2018-06-14",
        "last_close": "98.77",
        "effective": "2018-06-15",
        "legal_effective": "2018-06-14",
        "targets": [_t("T", "1.437")],
        "cash": "53.75",
        "url": "https://www.sec.gov/Archives/edgar/data/1105705/000095015718000694/form8-k.htm",
        "sha256": "4a3e0738f3f9876b56b8720b46b39f32e3bf4e1c495e25d4562b92160d25f060",
        "content_sha256": "0a1e0210253d111e84c744449a5fdcb5bc58de7ecef4456fd36b5bcaa58ca28c",
        "basis": "Completed AT&T merger on June 14, 2018: 1.437 AT&T shares plus $53.75 cash per Time Warner share; NYSE trading suspended before the next day's open.",
    },
    "VIAB": {
        "quote_asof": "2019-12-04",
        "last_trading": "2019-12-04",
        "last_close": "24.22",
        "effective": "2019-12-05",
        "legal_effective": "2019-12-04",
        "targets": [_t("PARA", "0.59625")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1339947/000119312519306335/d833313d8k.htm",
        "sha256": "fe544fb759dd9bc1b45b318b9366556a69519141134f144b42ab118a6c6616bc",
        "content_sha256": "3491055ffaa08c057806168689c3ecfd6c88ce4eb030cb126fbd87afe7443a89",
        "basis": "Completed CBS merger: each Viacom Class B share converted into 0.59625 ViacomCBS Class B shares (later PARA); Nasdaq trading suspended at the December 4, 2019 close.",
    },
    "WCG": {
        "quote_asof": "2020-01-27",
        "last_trading": "2020-01-23",
        "last_close": "349.92",
        "effective": "2020-01-24",
        "legal_effective": "2020-01-23",
        "targets": [_t("CNC", "3.38")],
        "cash": "120.00",
        "url": "https://www.sec.gov/Archives/edgar/data/1279363/000114036120001340/form8k.htm",
        "sha256": "e4dddbcc22f777cb7003df110c09df7e4b3267db8bdb580736975fbaaafa9f2d",
        "content_sha256": "fd6c78bbbdd89982d60b4b299f7b57a3f48048635a2ca903dfa88bb6cd5c3f17",
        "basis": "Completed Centene merger: 3.38 Centene shares and $120.00 cash per WellCare share; NYSE trading suspended after the January 23, 2020 close.",
    },
    "WFM": {
        "quote_asof": "2017-08-25",
        "last_trading": "2017-08-25",
        "last_close": "41.99",
        "effective": "2017-08-28",
        "legal_effective": "2017-08-28",
        "targets": [],
        "cash": "42.00",
        "url": "https://www.sec.gov/Archives/edgar/data/865436/000114420417045261/v474128_8k.htm",
        "sha256": "875c1647b436f8ad817bd9e21e436a2c82d5e9ee8c8f9a55a10cb95180ca8a91",
        "content_sha256": "46ddea312d3295c980f397ecce09de79709618ce6cfa380755725fdbd3ab42f5",
        "basis": "Completed Amazon acquisition: $42.00 cash per Whole Foods share; Nasdaq trading suspended before the August 28, 2017 open.",
    },
    "ANDV": {
        "quote_asof": "2018-09-28",
        "last_trading": "2018-09-28",
        "last_close": "153.5",
        "effective": "2018-10-01",
        "legal_effective": "2018-10-01",
        "targets": [_t("MPC", "1.6269")],
        "cash": "19.7951",
        "url": "https://www.sec.gov/Archives/edgar/data/50104/000005010418000239/andv8-kelectionoct2018.htm",
        "sha256": "39d2b28b059e7baa6ac703485af0512c181fbb36d2ca0e1467ff6b351326b63f",
        "content_sha256": "c66f37317a637cb067a9bd32d40dca9df129274bd1df1d454f89c14b6ef35be5",
        "basis": "Final MPC election results: the stock election was oversubscribed, so non-electing Andeavor holders received 1.87 MPC shares for approximately 87% of their shares and $152.27 cash for the rest (0.87 x 1.87 = 1.6269 MPC shares plus 0.13 x $152.27 = $19.7951 per share). Research models the non-electing holder; no favourable election is chosen in hindsight. Trading ceased before the October 1, 2018 open.",
        "terms_source": {
            "url": "https://www.sec.gov/Archives/edgar/data/50104/000119312518289750/d632974d8k.htm",
            "sha256": "274feee5ed1f947be7b30bb973509f160943f76f35b45d65290faa06c5afd4dc",
            "content_sha256": "6d815f5b775f060a1ae254d2d403bb5910a3478977b4eceeb8d2990cdfd4cc9d",
        },
    },
    "MYL": {
        "quote_asof": "2020-11-16",
        "last_trading": "2020-11-16",
        "last_close": "15.855",
        "effective": "2020-11-17",
        "legal_effective": "2020-11-16",
        "targets": [_t("VTRS", "1")],
        "cash": "0",
        "replaces": {
            "319a05b7-8c4e-4e9f-98b6-ed57b5576479": {
                "kind": "stock_mergers",
                "effective": "2020-11-16",
                "cash": "0",
                "targets": [["VTRS", "1"]],
            }
        },
        "url": "https://www.sec.gov/Archives/edgar/data/1623613/000119312520298224/d91045d8k.htm",
        "sha256": "58ccd6f75f50d8b631d37df814e7f9246a19835d3418f8c28b3665429695f7ee",
        "content_sha256": "25a13f3f103ceaa357017075f12ad3aacf32f3101a66e56c163c5cf2db138acb",
        "basis": "Completed Upjohn combination on November 16, 2020: one Viatris share per Mylan share. Mylan traded through November 16; Viatris began regular-way trading on November 17. The vendor's same-day conversion conflicts with the captured final Mylan session.",
    },
    "NFX": {
        "quote_asof": "2019-02-14",
        "last_trading": "2019-02-13",
        "last_close": "17.07",
        "effective": "2019-02-14",
        "legal_effective": "2019-02-13",
        "targets": [_t("ECA", "2.6719")],
        "cash": "0",
        "truncate": True,
        "url": "https://www.sec.gov/Archives/edgar/data/912750/000119312519044446/d710595d8k.htm",
        "sha256": "f5e1989dd8781dfd93193e062cce1f07d208e9eb1f3f8134756c36744ca5019d",
        "content_sha256": "dfa532579c981e1b68d6d29d757d11fdf5ec6e1883dd963d4d4711378ad1845b",
        "basis": "Completed Encana merger on February 13, 2019: 2.6719 Encana shares per Newfield share; withdrawn from NYSE after that close. Later captured NFX quotes belong to a different listing and are not used.",
    },
    "DD.OLD": {
        "quote_asof": "2017-08-31",
        "last_trading": "2017-08-31",
        "last_close": "83.93",
        "effective": "2017-09-01",
        "legal_effective": "2017-08-31",
        "targets": [_t("DWDP", "1.2820")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312517274834/d426905d8k12b.htm",
        "sha256": "cba0b689235d5e6c3d703b56c9309ddb5c87bd3bd0a1757bbf54e6506922efc8",
        "content_sha256": "8015f450730ee143b67f495d5fdac8a459dfe49e4ae0c32e4ffcbbe96faff804",
        "basis": "Completed DowDuPont mergers: 1.2820 DowDuPont shares per original DuPont share; DuPont common stock suspended before the September 1, 2017 open.",
    },
    "DOW.OLD": {
        "quote_asof": "2017-08-31",
        "last_trading": "2017-08-31",
        "last_close": "66.65",
        "effective": "2017-09-01",
        "legal_effective": "2017-08-31",
        "targets": [_t("DWDP", "1")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312517274834/d426905d8k12b.htm",
        "sha256": "cba0b689235d5e6c3d703b56c9309ddb5c87bd3bd0a1757bbf54e6506922efc8",
        "content_sha256": "8015f450730ee143b67f495d5fdac8a459dfe49e4ae0c32e4ffcbbe96faff804",
        "basis": "Completed DowDuPont mergers: one DowDuPont share per original Dow Chemical share; Dow common stock suspended before the September 1, 2017 open.",
    },
    "DISCA": {
        "quote_asof": "2022-04-08",
        "last_trading": "2022-04-08",
        "last_close": "24.43",
        "effective": "2022-04-11",
        "legal_effective": "2022-04-08",
        "targets": [_t("WBD", "1")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1437107/000119312522103051/d328161d8k.htm",
        "sha256": "a9846069d83fda87cdacde8066fd0f1494fa16b4f8dacea1533515bdaa77be42",
        "content_sha256": "00606b52e6a128d58b79bc1ae8fb09ad8e1423c915bb2eab6f53c818ecd50c0d",
        "basis": "Completed reclassification: one WBD Series A common share for each Discovery Series A share; first regular-way WBD session April 11, 2022.",
    },
    "CELG": {
        "quote_asof": "2019-11-20",
        "last_trading": "2019-11-20",
        "last_close": "108.24",
        "effective": "2019-11-21",
        "legal_effective": "2019-11-20",
        "targets": [_t("BMY", "1")],
        "cash": "52.25",
        "url": "https://www.sec.gov/Archives/edgar/data/816284/000110465919065939/tm1923405d1_8k.htm",
        "sha256": "9ba2ef9e90f791494166176f668016ebbde569745fa5f502df6d620b2c20183a",
        "content_sha256": "9ba2ef9e90f791494166176f668016ebbde569745fa5f502df6d620b2c20183a",
        "basis": "Completed Bristol-Myers Squibb merger: $50.00 cash, one BMY share and one tradeable CVR per Celgene share; Nasdaq trading suspended before the November 21, 2019 open.",
        "rights": "The tradeable CVR (BMY.RT) is valued at its first regular-way NYSE close of $2.25 on November 21, 2019 and added to the $50.00 cash. Its later expiry without payment is not modeled for holders who would have kept it.",
    },
    "ABMD": {
        "quote_asof": "2022-12-21",
        "last_trading": "2022-12-21",
        "last_close": "381.02",
        "effective": "2022-12-22",
        "legal_effective": "2022-12-22",
        "targets": [],
        "cash": "380.00",
        "url": "https://www.sec.gov/Archives/edgar/data/815094/000119312522311074/d353287d8k.htm",
        "sha256": "2dd2dadd6e5f43b8f44c3ff17dc3fd79362c53293156c0e4951129ae9bbc5834",
        "content_sha256": "4cceb151cbeb2f3c0368e996a23dcc1cb658b2bc730dd33466ca862bc2845ab4",
        "basis": "Johnson & Johnson completed its tender offer and merger: $380.00 cash plus one non-tradeable CVR per Abiomed share; Nasdaq trading suspended as of the December 21, 2022 close.",
        "rights": "The non-tradeable CVR (up to $35.00 on milestones) has no market value and is not credited unless a payment is verified.",
    },
    "HOLX": {
        "quote_asof": "2026-04-08",
        "last_trading": "2026-04-06",
        "last_close": "76.01",
        "effective": "2026-04-07",
        "legal_effective": "2026-04-07",
        "targets": [],
        "cash": "76.00",
        "replaces": {
            "3857592d-548a-4140-b254-61831ebd32b0": {
                "kind": "stock_and_cash_mergers",
                "effective": "2026-04-07",
                "cash": "76",
                "targets": [],
            }
        },
        "url": "https://www.sec.gov/Archives/edgar/data/859737/000119312526144632/d135035d8k.htm",
        "sha256": "2ef6a9c080d0db18e42c59136d881195d75ee85a3325572959994c3b1b77b74f",
        "content_sha256": "7c93646c7a4c2542c47b7f055de66a5519722165317db30680e1b140adf9c615",
        "basis": "Completed merger: $76.00 cash plus one contractual CVR per Hologic share; Nasdaq trading suspended before the April 7, 2026 open.",
        "rights": "The CVR (up to $3.00 on revenue milestones) has no captured market price and is not credited unless a payment is verified.",
    },
    "WBA": {
        "quote_asof": "2025-08-27",
        "last_trading": "2025-08-27",
        "last_close": "11.98",
        "effective": "2025-08-28",
        "legal_effective": "2025-08-28",
        "targets": [],
        "cash": "11.45",
        "replaces": {
            "33038fc0-3cf1-46a4-b0aa-5cf6b5c9eae2": {
                "kind": "stock_and_cash_mergers",
                "effective": "2025-08-29",
                "cash": "11.45",
                "targets": [],
            }
        },
        "url": "https://www.sec.gov/Archives/edgar/data/1618921/000119312525190603/d87240d8k.htm",
        "sha256": "5167a8981ea0f558b7759e773fecc0efcd5c2ff4fa877e52e51a3162a40b433a",
        "content_sha256": "2f831bf3a7deebf7f2f22a793dd31bb4942221f2832ca1c33a105ba2b5547354",
        "basis": "Completed merger on August 28, 2025: $11.45 cash plus one divested asset proceed right per Walgreens share. Walgreens did not trade on August 28; the vendor's August 29 date is retained in provenance.",
        "rights": "The divested asset proceed right (up to $3.00 from VillageMD monetization) has no captured market price and is not credited unless a payment is verified.",
    },
    "EA": {
        "quote_asof": "2026-08-04",
        "last_trading": "2026-08-04",
        "last_close": "209.7",
        "effective": "2026-08-05",
        "legal_effective": "2026-08-04",
        "targets": [],
        "cash": "210",
        "replaces": {
            "e1eddaf1-f3b8-4f9d-9f0d-7bc70b3b8a52": {
                "kind": "cash_mergers",
                "effective": "2026-08-04",
                "cash": "210",
                "targets": [],
            }
        },
        "url": "https://www.sec.gov/Archives/edgar/data/712515/000114036126031157/ef20079099_8k.htm",
        "sha256": "9ed4a70a84766656e40aaee5c8b3846519e90d29c445af8c41172c9a0728188e",
        "content_sha256": "ff4f92362438f24b705e4c094b79eff8884c0f925c8977c5c9d2d933f7e3d531",
        "basis": "Completed merger on August 4, 2026: $210 cash per Electronic Arts share. Trading halted after the August 4 close and was suspended before the August 5 open, so the captured August 4 session remains a valid trading day.",
    },
    "GGP": {
        "quote_asof": "2018-08-27",
        "last_trading": "2018-08-27",
        "last_close": "22.06",
        "effective": "2018-08-28",
        "legal_effective": "2018-08-28",
        "targets": [_t("BPY", "0.376")],
        "cash": "14.642",
        "url": "https://www.sec.gov/Archives/edgar/data/1496048/000119312518256393/d605844d425.htm",
        "sha256": "5c650b01f2d409cf83f265e58da8a6c3cdcc73228853edab8a42f184cb91eefd",
        "content_sha256": "57e43870492bbeecb564cc68efe3bba3b921f161ed794881ecbccc925ccac846",
        "basis": "Brookfield's filed election results: each non-electing GGP share receives $14.642 cash and 0.376 BPY units, inclusive of the pre-closing dividend payable August 27 and the $0.312 cash merger consideration. GGP was suspended at the August 28, 2018 open. Research models the non-electing holder.",
        "terms_source": {
            "url": "https://www.sec.gov/Archives/edgar/data/1496048/000119312518260735/d614210d8k.htm",
            "sha256": "f15eb93ed12de1c608257055059a2e2f84d6bc6956299d81930a808db3ca0a06",
            "content_sha256": "04e962b9198fa7f214c4845f6e66016203f2885674b115a485dd030295c7f77e",
        },
    },
    "APC": {
        "quote_asof": "2019-08-08",
        "last_trading": "2019-08-08",
        "last_close": "72.77",
        "effective": "2019-08-09",
        "legal_effective": "2019-08-08",
        "targets": [_t("OXY", "0.2934")],
        "cash": "59.00",
        "url": "https://www.sec.gov/Archives/edgar/data/773910/000095015719000863/form8k.htm",
        "sha256": "d0114241c9bbe7f35a40437b9244152ad268d41287d616da321a01b8e4064ca8",
        "content_sha256": "48a7960efd5394a6a99b6223ae255c69c1c6159dc5f5931e1d7b00a66515ca59",
        "basis": "Completed Occidental merger: $59.00 cash and 0.2934 Occidental shares per Anadarko share; NYSE trading suspended before the August 9, 2019 open.",
    },
    "FOXA.OLD": {
        "quote_asof": "2019-03-18",
        "last_trading": "2019-03-18",
        "last_close": "51.36",
        "effective": "2019-03-19",
        "legal_effective": "2019-03-20",
        "targets": [_t("FOXA", "0.3333333333"), _t("DIS", "0.3328202389")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1308161/000119312519079034/d721340d8k.htm",
        "sha256": "730f754897cbef001a2aa880f6c4d9f89eb8e9fad21a3a6c124d0ce9a86610a9",
        "content_sha256": "1d4f1c52c717d0845982fcb2f7afc8f86692bdd47044f50d9ba7d4d6bdcb60ae",
        "basis": "On March 19, 2019, 0.263183 of each 21CF Class A share was exchanged for 1/3 of a new Fox Class A share; the remaining 0.736817 share traded one day as TFCFA and on March 20 non-electing holders received 0.4517 Disney shares for it (0.736817 x 0.4517 = 0.3328202389 DIS). The one-day TFCFA listing is not modeled; Disney shares are received with the Fox shares at the March 19 session.",
        "terms_source": {
            "url": "https://www.sec.gov/Archives/edgar/data/1308161/000095015719000308/form8k.htm",
            "sha256": "d5101f9c05523a83f9791d9a13b94e173b1b3fd8ef350bdfc967b9747d0d6b5d",
            "content_sha256": "496a420758597e952180b38cafc85d52be443144dbefa9e66345ce877f141d4a",
        },
    },
    "FOX.OLD": {
        "quote_asof": "2019-03-18",
        "last_trading": "2019-03-18",
        "last_close": "51.04",
        "effective": "2019-03-19",
        "legal_effective": "2019-03-20",
        "targets": [_t("FOX", "0.3333333333"), _t("DIS", "0.3328202389")],
        "cash": "0",
        "url": "https://www.sec.gov/Archives/edgar/data/1308161/000119312519079034/d721340d8k.htm",
        "sha256": "730f754897cbef001a2aa880f6c4d9f89eb8e9fad21a3a6c124d0ce9a86610a9",
        "content_sha256": "1d4f1c52c717d0845982fcb2f7afc8f86692bdd47044f50d9ba7d4d6bdcb60ae",
        "basis": "On March 19, 2019, 0.263183 of each 21CF Class B share was exchanged for 1/3 of a new Fox Class B share; the remaining 0.736817 share traded one day as TFCF and on March 20 non-electing holders received 0.4517 Disney shares for it (0.3328202389 DIS per original share). The one-day TFCF listing is not modeled.",
        "terms_source": {
            "url": "https://www.sec.gov/Archives/edgar/data/1308161/000095015719000308/form8k.htm",
            "sha256": "d5101f9c05523a83f9791d9a13b94e173b1b3fd8ef350bdfc967b9747d0d6b5d",
            "content_sha256": "496a420758597e952180b38cafc85d52be443144dbefa9e66345ce877f141d4a",
        },
    },
    "LVLT": {
        "quote_asof": "2017-10-12",
        "last_trading": "2017-10-31",
        "last_close": "53.63",
        "effective": "2017-11-01",
        "legal_effective": "2017-11-01",
        "targets": [_t("LUMN", "1.4286")],
        "cash": "26.50",
        "url": "https://www.sec.gov/Archives/edgar/data/794323/000119312517329395/d459582d8k.htm",
        "sha256": "c76f65545950fcc2965e9a8c81ac6da75d3d4220b1684f9acf72745d718538fe",
        "content_sha256": "a3ed0c24e0465c23e697271723f53b7eea0e8b3f7abcd15f344ec35859e20222",
        "basis": "Completed CenturyLink merger: $26.50 cash and 1.4286 CenturyLink (later LUMN) shares per Level 3 share; NYSE trading ceased at 9:00 a.m. on November 1, 2017.",
    },
    "SIVB": {
        "quote_asof": "2023-03-14",
        "last_trading": "2023-03-09",
        "last_close": "106.04",
        "effective": "2023-03-10",
        "legal_effective": "2023-03-10",
        "targets": [],
        "cash": "0",
        "zero_recovery": True,
        "url": "https://www.sec.gov/Archives/edgar/data/719739/000119312523073665/d485308d8k.htm",
        "sha256": "10e9adcdf01d537d92933bee043dca96c75e1ac361621caa3b152b2d2e2495e0",
        "content_sha256": "69f3b20dfab4c9c43641a3c38a99f288129665af40e5ae3e6993ec36ccf4fcef",
        "basis": "Silicon Valley Bank was placed in FDIC receivership on March 10, 2023; Nasdaq halted SVB Financial common stock that day and suspended it on March 28, and the parent filed for Chapter 11 on March 17. No exchange trade followed, so the position ends at zero value.",
        "rights": "Later over-the-counter quotes for the bankrupt parent's equity are not captured and are not credited; this is a conservative valuation.",
    },
    "FRC": {
        "quote_asof": "2023-05-03",
        "last_trading": "2023-04-28",
        "last_close": "3.51",
        "effective": "2023-05-01",
        "legal_effective": "2023-05-01",
        "targets": [],
        "cash": "0",
        "zero_recovery": True,
        "url": "https://www.sec.gov/Archives/edgar/data/19617/000001961723000304/jpm-20230501.htm",
        "sha256": "796d126d6a8eb863556ec426c55329fa67ed68876c0569ccac15097fd32dd034",
        "content_sha256": "d357f6b71e61ac4f831ea7a59e71b2811616afb049a91fdf92c8a45b543459a4",
        "basis": "First Republic Bank was closed and placed in FDIC receivership before the May 1, 2023 open; JPMorgan Chase acquired its assets from the FDIC. The bank's common stock had no further exchange trade and ends at zero value.",
        "rights": "First Republic's securities were registered with the FDIC, not the SEC. Later over-the-counter quotes are not captured and are not credited; this is a conservative valuation.",
    },
    "SBNY": {
        "quote_asof": "2023-03-14",
        "last_trading": "2023-03-10",
        "last_close": "70",
        "effective": "2023-03-13",
        "legal_effective": "2023-03-12",
        "targets": [],
        "cash": "0",
        "zero_recovery": True,
        "truncate": True,
        "url": "https://www.sec.gov/Archives/edgar/data/910073/000119312523074432/d481717d8k.htm",
        "sha256": "e3a5c2360990ec5eedcc8ab9c50e72cd3aee0fb7e86843f6d24192f60f15c25c",
        "content_sha256": "4043d4e772b287d368c74cfad1d21db4c71a2b0572d51c759f3adf952ccd6a6d",
        "basis": "Signature Bank was closed on Sunday, March 12, 2023 with the FDIC as receiver; Flagstar later assumed its deposits from the receiver. No exchange trade followed the March 10 close, so the position ends at zero value. Later flat zero-volume provider marks are not trades and are removed.",
        "rights": "Signature Bank's securities were registered with the FDIC, not the SEC. Later over-the-counter quotes are not captured and are not credited; this is a conservative valuation.",
    },
}

# Spin-offs and special distributions the vendor omits, records as a parent
# split, or values in the wrong share units. ``children`` are child shares per
# parent share held before the ex-date; ``parent_split`` is the legal change in
# parent shares that day. ``displaces`` names vendor records superseded by the
# reviewed terms. ``price_date`` values a child at its first regular-way close
# when no ex-date market price exists (an explicit approximation).
DISTRIBUTIONS = [
    {
        "parent": "TGNA",
        "ex_date": "2017-06-01",
        "prev_close": "23.74",
        "close": "15.35",
        "children": [{"symbol": "CARS", "ratio": "0.3333333333"}],
        "displaces": {"9df6f288-9d48-4fcf-8374-d22c8c37f7ea": "reverse_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/39899/000119312517196074/d514170d8k.htm",
        "sha256": "253908deba0a16c5d78a037b06719c279cbb62a9dfe1aba4ac7e42db381f552b",
        "content_sha256": "9ef5fc2fb29944aae6a36073e19cf93d0ea3de3e0efaf58a988c5ca757ee6053",
        "basis": "TEGNA distributed one Cars.com share per three TEGNA shares (record May 18, 2017). The vendor's 1-for-3 reverse split would remove two-thirds of a holder's TEGNA shares; TEGNA's share count did not change.",
    },
    {
        "parent": "CNX",
        "ex_date": "2017-11-29",
        "prev_close": "16.16",
        "close": "13.5",
        "children": [{"symbol": "CEIX", "ratio": "0.125", "asof": "2017-11-29"}],
        "displaces": {"9bf7abc0-ff2c-4a88-948b-44a30ab1c3c3": "reverse_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/1070412/000119312517359483/d500008d8k.htm",
        "sha256": "9c024fea467852bdb992157d2815d2076bf424f017c942883f6275f59c90424c",
        "content_sha256": "817265021c891c1a26e9a9c331afa37f98c0fbc19abc1943ccae4bb6c0735369",
        "basis": "CNX Resources (formerly CONSOL Energy) distributed one CONSOL Energy (CEIX) share per eight shares on November 28, 2017. The vendor's 1-for-8 reverse split is not a change in parent shares.",
    },
    {
        "parent": "EQT",
        "ex_date": "2018-11-13",
        "prev_close": "34.64",
        "close": "18.56",
        "children": [{"symbol": "ETRN", "ratio": "0.8", "asof": "2018-11-13"}],
        "displaces": {"e45388d6-863d-4ab3-93b3-3d40fc813f23": "reverse_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/33213/000104746918007182/a2237122z8-k.htm",
        "sha256": "6ffa0f865b2fef1cd3a2b885a685d14d82d59dfe57aef8deb912d1ce55df3fba",
        "content_sha256": "1d5f0c026cbac806cab5b639a276e8507ff47b04dadf4eacd8b927abfcbcae07",
        "basis": "EQT distributed 0.80 Equitrans Midstream shares per EQT share (record November 1, 2018). The vendor's 0.8 reverse split is not a change in parent shares.",
    },
    {
        "parent": "RTX",
        "ex_date": "2020-04-03",
        "prev_close": "86.01",
        "close": "49.93",
        "children": [
            {"symbol": "CARR", "ratio": "1"},
            {"symbol": "OTIS", "ratio": "0.5"},
        ],
        "displaces": {"6b79df0e-7762-4253-b1c8-14b4a6a9dccc": "reverse_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/101829/000114036120008397/nc10010681x2_8k.htm",
        "sha256": "1472fbb49f180aed0d9eace7d929fbb4f85965da9460db8f9bff28b7a6a0a157",
        "content_sha256": "c58d3bc45508ff339983c83d8f6e5004269284a39cd1478f739cbecc47a1ae83",
        "basis": "United Technologies (renamed RTX) distributed one Carrier share and one-half Otis share per share (record March 19, 2020). The vendor's 1-for-2 reverse split is not a change in parent shares.",
    },
    {
        "parent": "AIV",
        "ex_date": "2020-12-15",
        "prev_close": "40.34",
        "close": "5.04",
        "children": [{"symbol": "AIRC", "ratio": "1"}],
        "displaces": {"3915f4ad-7977-4e8a-a6e7-9fef37c8ffc8": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/922864/000119312520317477/d772672d8k.htm",
        "sha256": "f0055f77ca5b91ee529c58efbcf3fa79c40d2c92b6b694372930ae06a3789dac",
        "content_sha256": "b5ac141ac4b82c4c578dd10e91c0f3b0be0851cebc2994e6601f807e8ad4088d",
        "basis": "Aimco holders received one AIR (AIRC) share per Aimco share on December 15, 2020. The vendor also recorded a 9.295-for-1 forward split, which would count the separation twice.",
    },
    {
        "parent": "HON",
        "ex_date": "2026-06-29",
        "prev_close": "232.21",
        "close": "227.8",
        "parent_split": "0.5",
        "children": [{"symbol": "HONA", "ratio": "0.5"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/773840/000077384026000084/hon-20260625.htm",
        "sha256": "82ee68d23776cabc3d891b2e428e04b07cdbe1e29ef302162f2b5ebf9603a2f3",
        "content_sha256": "b5a195314fa5a0be04873c05755d2ede1aef87d04d41bff20377fddb281c1aa0",
        "basis": "Honeywell distributed one Honeywell Aerospace share per two pre-split shares (record June 15, 2026) and combined every two shares into one effective June 29. Each post-split share therefore carries one HONA share; the vendor's per-pre-split ratio would halve the distribution.",
    },
    {
        "parent": "YUM",
        "ex_date": "2016-11-01",
        "prev_close": "86.28",
        "close": "60.69",
        "children": [{"symbol": "YUMC", "ratio": "1"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/1041061/000104106116000097/form8k11316.htm",
        "sha256": "db48b4494e051b8f6ac5b506c813f42f5a066f16621776469c933a6b0eb6a98f",
        "content_sha256": "4ec11ffe7fc20bb1d5d344b9dd5af347a5136589b65b86f0538aef12c941898d",
        "basis": "Yum! Brands distributed one Yum China share per YUM share on October 31, 2016; the vendor records no action, which would show a 30% loss.",
    },
    {
        "parent": "PNR",
        "ex_date": "2018-05-01",
        "prev_close": "67.28",
        "close": "44.82",
        "children": [{"symbol": "NVT", "ratio": "1"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/77360/000007736018000018/pentairproformafinancials-.htm",
        "sha256": "eed455fdadac59cb6efe962a0039b3b0e24645999c3da6e8a0321fe1b7454f08",
        "content_sha256": "c528b51af4c57465d90d19a7b0b8ea88bfd491e567a13c1fb90b866bff106e77",
        "basis": "Pentair distributed one nVent share per Pentair share (record April 17, 2018); nVent began regular-way trading May 1, 2018. The vendor records no action.",
    },
    {
        "parent": "JCI",
        "ex_date": "2016-10-31",
        "prev_close": "43.76",
        "close": "40.32",
        "children": [{"symbol": "ADNT", "ratio": "0.1"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/833444/000110465916153134/a16-20376_18k.htm",
        "sha256": "c82c9678602c274f0be06586d0114a999b172342c673a3723d4829ef8f70c251",
        "content_sha256": "3c6c65b478c27319ab4b17ccf8fef5bcdc51b5d6e8b011eddbdbbf970cd4b0ee",
        "basis": "Johnson Controls distributed one Adient share per ten shares on October 31, 2016; the vendor records no action.",
    },
    {
        "parent": "BIIB",
        "ex_date": "2017-02-02",
        "prev_close": "281.69",
        "close": "264.23",
        "children": [{"symbol": "BIVV", "ratio": "0.5", "asof": "2017-02-02"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/875045/000087504517000007/a8-kbioverativspinxoff.htm",
        "sha256": "a4d8ec0407e8037271c17a926379ac83543657d3fcd5362fd89b0e198990d80f",
        "content_sha256": "838f094a9d5c90a51a1fb2fc5b6f27139b0ef9bdd74a539aa48e3a2494cabd8f",
        "basis": "Biogen distributed one Bioverativ share per two Biogen shares on February 1, 2017; Biogen traded ex-distribution from February 2. The vendor records no action.",
    },
    {
        "parent": "MRK",
        "ex_date": "2021-06-03",
        "prev_close": "75.87",
        "close": "73.91",
        "children": [{"symbol": "OGN", "ratio": "0.1"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/310158/000119312521180657/d190548d8k.htm",
        "sha256": "787e0430c63b828b4be37b04d4c7a0222d9c86e9d9c7b6522d6b71fce284652f",
        "content_sha256": "a7d066f40d61b23acff0fc68c446f802e307d3d9f74a39d9fc85e0bf81f820be",
        "basis": "Merck distributed one-tenth Organon share per Merck share on June 2, 2021; the vendor records no action.",
    },
    {
        "parent": "IBM",
        "ex_date": "2021-11-04",
        "prev_close": "127.13",
        "close": "120.85",
        "children": [{"symbol": "KD", "ratio": "0.2"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/51143/000155837021014643/ibm-20211103x8k.htm",
        "sha256": "c94a9d0fe09c4e35a65b30bf40be0ca03b2ca6217721c1093bfbd989a08843aa",
        "content_sha256": "532335a6d5ba68f3c1ab02e62941c33257f5d6af9759ce06ed3a5bd9fb9deee6",
        "basis": "IBM distributed one Kyndryl share per five IBM shares on November 3, 2021; the vendor records no action.",
    },
    {
        "parent": "BBWI",
        "ex_date": "2021-08-03",
        "prev_close": "79.92",
        "close": "66",
        "children": [{"symbol": "VSCO", "ratio": "0.3333333333"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/701985/000114036121026658/nt10026698x7_8k.htm",
        "sha256": "a3403b4e9dbe2e5aa66e8e8815a54d36fe737676759c187b82b70e4a641dca64",
        "content_sha256": "5e4961e0651bb95e9045e74a8f093c53ccde12defd7229037030d6daa3072c05",
        "basis": "L Brands, renamed Bath & Body Works after the August 2, 2021 close, distributed one Victoria's Secret share per three shares (record July 22). The renamed issuer continued as BBWI.",
    },
    {
        "parent": "WYND",
        "ex_date": "2018-06-01",
        "prev_close": "108.44",
        "close": "48.71",
        "children": [{"symbol": "WH", "ratio": "1"}],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/1361658/000110465918037818/a18-14563_28k.htm",
        "sha256": "350d779a763b94c2f05cc8c24cd0e505e7ffdc957950d73d50b1c66337df1654",
        "content_sha256": "3abbe937ced9beda61235278d045470460db0f42f97c6bb79e60a31c4e694dd9",
        "basis": "Wyndham Worldwide, renamed Wyndham Destinations, distributed one Wyndham Hotels share per share (record May 18, 2018); the vendor records no action across the WYN/WYND rename.",
    },
    {
        "parent": "BHGE",
        "ex_date": "2017-07-05",
        "prev_close": "57.68",
        "close": "37.25",
        "cash": "17.50",
        "children": [],
        "displaces": {},
        "url": "https://www.sec.gov/Archives/edgar/data/1701605/000119312517220852/d343521d8k12b.htm",
        "sha256": "c43174ab0d354da56540719c0f9951841c0a2fcfc67fc6c7ae4202e5de215f90",
        "content_sha256": "4086eb52e0703c72d3b7cf05fa291ed01bf4eceffddba8724209c8a9a9e615d0",
        "basis": "Each Baker Hughes share became one BHGE Class A share, and BHGE declared a $17.50 special dividend to those holders of record immediately after the merger. Baker Hughes traded through July 3; BHGE began trading July 5, 2017.",
    },
    {
        "parent": "APTV",
        "ex_date": "2017-12-05",
        "prev_close": "104.3",
        "close": "88.77",
        "children": [{"symbol": "DLPH", "ratio": "0.3333333333", "asof": "2017-12-05"}],
        "displaces": {},
        "clears_adjusted_conflict": True,
        "url": "https://www.sec.gov/Archives/edgar/data/1521332/000119312517363912/d453817d8k.htm",
        "sha256": "994aeb51b323d27fa752d1df0f7d372ebec216f869aeec6602fdf4ace273d154",
        "content_sha256": "4f76d024ce989664a87d93f6eedc34cb0889f35a4864b31c2235a429929218dd",
        "basis": "Delphi Automotive, renamed Aptiv, distributed one Delphi Technologies (new DLPH) share per three shares (record November 22, 2017). The vendor's split-adjusted series treats this as a split; Aptiv's share count did not change.",
    },
    {
        "parent": "TT",
        "ex_date": "2020-03-02",
        "prev_close": "129.04",
        "close": "100.55",
        "children": [{"symbol": "IR", "ratio": "0.8824"}],
        "displaces": {
            "6815b560-3059-4c19-a269-fd131bd6d460": "forward_splits",
            "843a4a07-11ae-4d9f-915d-2d08b817573d": "reverse_splits",
        },
        "clears_adjusted_conflict": True,
        "url": "https://www.sec.gov/Archives/edgar/data/1466258/000146625820000089/a8-kdiscontinuedoperat.htm",
        "sha256": "10cdfcedd57722dbcd20c2d046c1d1b5939337c0ce3cd815aafcdb8bcf611aef",
        "content_sha256": "4e5c4aa3e88e8aafc418ff07ce08ff17b0fe6d0d392a5d647028b521373d43a5",
        "basis": "Old Ingersoll-Rand, renamed Trane Technologies, distributed its industrial business, which merged into Gardner Denver (renamed Ingersoll Rand Inc.); holders received approximately 0.8824 new IR shares per share. The vendor's 1.289 forward split and 0.8824 reverse split are not parent share changes.",
    },
    {
        "parent": "SW",
        "ex_date": "2016-05-16",
        "prev_close": "42.56",
        "close": "39.63",
        "children": [{"symbol": "NGVT", "ratio": "0.1666666667"}],
        "displaces": {"78f521c7-d5ad-42fe-a534-5c5ac1497d33": "reverse_splits"},
        "clears_adjusted_conflict": True,
        "url": "https://www.sec.gov/Archives/edgar/data/1636023/000157104916015408/t1601375_8k.htm",
        "sha256": "4488786839c9626188f0ce1cfb804e9dea17dd5a1e175c81b888f2dc3f38f302",
        "content_sha256": "2d5c1adabf99ec177c6796e5441d91bb891534f427315010d05e6f55a04c3b29",
        "basis": "WestRock distributed one Ingevity share per six WestRock shares at 11:59 p.m. on May 15, 2016 (record May 4). The vendor's 1-for-6 reverse split is not a change in parent shares.",
    },
    {
        "parent": "SW",
        "ex_date": "2024-07-08",
        "prev_close": "51.51",
        "close": "46.22",
        "cash": "5.00",
        "children": [],
        "displaces": {},
        "rejects_merger": {
            "65899ddb-364f-4bd7-a01c-60c915c746d1": {
                "kind": "stock_and_cash_mergers",
                "effective": "2024-07-08",
                "cash": "5",
            }
        },
        "url": "https://www.sec.gov/Archives/edgar/data/2005951/000110465924078355/tm2418700d1_8k.htm",
        "sha256": "d7158d2e7c255ffe81d1de2dbfa778001fc83a797ee7c10e3e87b2425b61fcf2",
        "content_sha256": "0e88df155b57c1629e2681fe874cd21b52a8f54945eb72dfb6b71849e5306b24",
        "basis": "Each WestRock share converted into one Smurfit WestRock share and $5.00 cash. The captured SW series continues the WestRock holding one-for-one; the $5.00 is credited to overnight holders, replacing the vendor's same-symbol merger instruction.",
    },
    {
        "parent": "DOC",
        "ex_date": "2016-11-01",
        "prev_close": "34.25",
        "close": "30.47",
        "children": [{"symbol": "QCP", "ratio": "0.2", "asof": "2016-11-01"}],
        "displaces": {"3fa6fc16-b76e-4158-83d9-e534db36334b": "forward_splits"},
        "clears_adjusted_conflict": True,
        "url": "https://www.sec.gov/Archives/edgar/data/765880/000110465916153366/a16-12302_158k.htm",
        "sha256": "ee01c2ec252db502c433ff9d7ff4efe87ec2747b16dc107bf4bf3f2afd2b1384",
        "content_sha256": "f943b52faae44511dc08b901531f7b1ce57f3c8450c16f4b274ee55c41d5c855",
        "basis": "HCP (now Healthpeak, DOC) distributed one Quality Care Properties share per five HCP shares on October 31, 2016 (record October 24). The vendor's 1.098 split is not a change in parent shares.",
    },
    # Vendor "forward split" proxies estimate a spin-off's value from earlier
    # when-issued prices. The research convention values the child at its
    # ex-date close; these replacements differ from the proxy by 0.7-9%.
    {
        "parent": "APD",
        "ex_date": "2016-10-03",
        "prev_close": "150.34",
        "close": "140.57",
        "children": [{"symbol": "VSM", "ratio": "0.5", "asof": "2016-10-03"}],
        "displaces": {"649427cf-90cc-49ef-856f-38f3c0c01a67": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/2969/000119312516731580/d184846d8k.htm",
        "sha256": "ff72094f12d536e78d136df96e8a42476fe7bdd2a49893841c5fd277eb8c16fc",
        "content_sha256": "b82cecc31427cdb0fd47791fe22c17c32b7c2863253b6631faae943ea582933e",
        "basis": "Air Products distributed one Versum Materials share per two shares on October 1, 2016. The vendor's 1.081 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "CAG",
        "ex_date": "2016-11-10",
        "prev_close": "47.84",
        "close": "34.3",
        "children": [{"symbol": "LW", "ratio": "0.3333333333"}],
        "displaces": {"cbfcf359-8e12-4196-9fcb-5917ade6656f": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/23217/000119312516769038/d291722d8k.htm",
        "sha256": "3efd249079cf1decaad5ce289eaf185900323f17ba96643458eafbbbd3b6f8cf",
        "content_sha256": "4c95f465f54942371fade840368b6b727bfd720e8782c83571244abcd80f5a9c",
        "basis": "Conagra distributed one Lamb Weston share per three shares (November 2016). The vendor's 1.285 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "DHR",
        "ex_date": "2016-07-05",
        "prev_close": "102.32",
        "close": "80.4",
        "children": [{"symbol": "FTV", "ratio": "0.5"}],
        "displaces": {"75161f73-6156-4142-80e7-b27dbc1cfbc8": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/313616/000119312516643649/d205135d8k.htm",
        "sha256": "05821e6de826b1d724f5a713f681e940f3e5b085d7328fe95cdedfff37f33eab",
        "content_sha256": "fc83a9a18e526124eb69c13a9f02cbf7891f1e54887519e3d63d5a1d2a9ab306",
        "basis": "Danaher distributed one Fortive share per two shares (record June 15, 2016). The vendor's 1.319 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "DOV",
        "ex_date": "2018-05-09",
        "prev_close": "93.74",
        "close": "76.89",
        "children": [{"symbol": "APY", "ratio": "0.5", "asof": "2018-05-09"}],
        "displaces": {"45fe505c-c439-4bb8-99a6-6a59ded4de16": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/29905/000119312518161162/d585845d8k.htm",
        "sha256": "60607deb352136fd13dae2c151fa5d7b6b5c693cc8457401b0c3cb0d72bf278e",
        "content_sha256": "239f147b8355ccd9927e3fee90f062a4974f6f74f988cd957ed5d03bb830c5a3",
        "basis": "Dover distributed one Apergy share per two shares on May 9, 2018 (record April 30). The vendor's 1.238 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "FTV",
        "ex_date": "2020-10-09",
        "prev_close": "81.79",
        "close": "69.82",
        "children": [{"symbol": "VNT", "ratio": "0.4"}],
        "displaces": {"da2bec50-0c9e-45d7-81f4-6b93feff0a1a": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/1659166/000119312520268470/d35176d8k.htm",
        "sha256": "7710d1d5565a599711ea51d9a1ad695a78ab33d1203d25d6e165baa0b0cf6290",
        "content_sha256": "e5fa49ca93db039ba8a5ecd4a2c5645d4ab992d305fedc50043875087d5318af",
        "basis": "Fortive distributed two Vontier shares per five shares (record September 25, 2020). The vendor's 1.195 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "XRX",
        "ex_date": "2017-01-03",
        "prev_close": "8.73",
        "close": "6.89",
        "children": [{"symbol": "CNDT", "ratio": "0.2", "asof": "2017-01-03"}],
        "displaces": {"b47994a0-28c2-4b39-9bdd-51c374548a00": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/108772/000010877217000008/xrx-123116x10xk.htm",
        "sha256": "f4a617354e3567cea82ce7b46fa813971f75bd0d6b2a0ec76699173015d0b2c4",
        "content_sha256": "fa852055d618de4e82b2f2132367bf1eba84d02c750b0f0a30dbaad134b2d643",
        "basis": "Xerox distributed one Conduent share per five Xerox shares (December 31, 2016). The vendor's 1.518 split proxy, derived from when-issued prices, overstates the ex-date value; it is replaced by Conduent's ex-date close.",
    },
    {
        "parent": "DXC",
        "ex_date": "2018-06-01",
        "prev_close": "92.11",
        "close": "83.4",
        "children": [{"symbol": "PRSP", "ratio": "0.5", "asof": "2018-06-01"}],
        "displaces": {"8a8574af-1ed5-4463-80fc-966688ac46ba": "forward_splits"},
        "url": "https://www.sec.gov/Archives/edgar/data/1688568/000168856818000054/dxcuspsseparation8-k.htm",
        "sha256": "ad5a4800e410ee2fc7040419745f3e603c669fd25121f7aed1d62506d747080c",
        "content_sha256": "85af70995aa69c6263419044d467dc3a7c0eaaa438eb4167ec3faf2766b54dd9",
        "basis": "DXC distributed one Perspecta share per two DXC shares (May 31, 2018). The vendor's 1.156 split proxy is replaced by the child's ex-date close.",
    },
    {
        "parent": "FTI",
        "ex_date": "2021-02-16",
        "prev_close": "10.31",
        "close": "8.09",
        "cash": "3.09",
        "children": [],
        "displaces": {"632aac30-1b59-44b0-8464-ba2f53eba767": "spin_offs"},
        "url": "https://www.sec.gov/Archives/edgar/data/1681459/000114036121004982/nt10016372x18_8k.htm",
        "sha256": "5e2bc43ec37253eebf932270d67cb663ac0207adbaf1fa4bcc8623d2713ff7f5",
        "content_sha256": "7436b4ef949dbb54cc67470cd8418a37b0d35fc86f38d40c5608309560856df2",
        "basis": "TechnipFMC distributed one Technip Energies share per five FTI shares on February 16, 2021. Technip Energies traded only on Euronext Paris and has no captured US quote, so the entitlement is valued at $3.09 per FTI share: the provider's own spin-off adjustment (raw February 12 close $10.31 versus $7.22 adjusted). This provider-derived value is an approximation, not an exchange price.",
    },
    {
        "parent": "LEN",
        "ex_date": "2025-01-21",
        "prev_close": "141.54",
        "close": "133.14",
        "children": [{"symbol": "MRP", "ratio": "0.5", "price_date": "2025-02-07"}],
        "displaces": {"58374997-f6cd-4485-a6db-0c208087ead4": "spin_offs"},
        "url": "https://www.sec.gov/Archives/edgar/data/920760/000119312525022309/d933374d8k.htm",
        "sha256": "11b62420418b37bdd90ce07707fd7fd22305aff5a5082aee0e48994a4698401b",
        "content_sha256": "000c040daa62de478b90524ba328ff09aba2cfdb4153faf436f896ff3c47184b",
        "basis": "Lennar distributed one Millrose (MRP) share per two Lennar shares to holders of record January 21, 2025, the vendor ex-date; shares were delivered February 7. No Millrose market price existed on the ex-date, so the entitlement is valued at Millrose's first regular-way close (February 7, 2025). This is an approximation.",
    },
]

# Captured quotes outside a security's own listing lifetime. ``keep_from``
# removes earlier prices belonging to a predecessor; ``keep_until`` removes
# later marks or a reused ticker's quotes.
LIFETIMES = {
    "DOW": {
        "keep_from": "2019-04-02",
        "first_close": "56.25",
        "url": "https://www.sec.gov/Archives/edgar/data/1751788/000119312519095067/d716962d8k.htm",
        "sha256": "ab1564be0be7823566d629688d4699d483cc680294981c8ac30acdeff5bb4f50",
        "content_sha256": "84fb55591440bea573d6dd5c00fc97cb150db363f26d822bec9f679ea24bf145",
        "basis": "Dow Inc. was separated from DowDuPont on April 1, 2019 and began regular-way trading April 2. Earlier captured DOW quotes belong to the old Dow Chemical listing or repeat its last close with zero volume.",
    },
    "FOXA": {
        "keep_from": "2019-03-19",
        "first_close": "40.34",
        "url": "https://www.sec.gov/Archives/edgar/data/1754301/000119312519079678/d721949d8k.htm",
        "sha256": "e85cb6d7b5aebf302c69e0562196106a52a2e2b7af421a076d563c2f71d2b801",
        "content_sha256": "0f1859c1c9b696c631042401661161afaa141eac4e8960168aa829cac677d61c",
        "basis": "Fox Corporation Class A began regular-way trading as FOXA on March 19, 2019. Earlier FOXA quotes belong to Twenty-First Century Fox, held separately as FOXA.OLD.",
    },
    "FOX": {
        "keep_from": "2019-03-19",
        "first_close": "39.55",
        "url": "https://www.sec.gov/Archives/edgar/data/1754301/000119312519079678/d721949d8k.htm",
        "sha256": "e85cb6d7b5aebf302c69e0562196106a52a2e2b7af421a076d563c2f71d2b801",
        "content_sha256": "0f1859c1c9b696c631042401661161afaa141eac4e8960168aa829cac677d61c",
        "basis": "Fox Corporation Class B began regular-way trading as FOX on March 19, 2019. Earlier FOX quotes belong to Twenty-First Century Fox, held separately as FOX.OLD.",
    },
    "UA": {
        "keep_from": "2016-04-08",
        "first_close": "43.54",
        "url": "https://www.sec.gov/Archives/edgar/data/1336917/000133691716000068/march162016form8-k.htm",
        "sha256": "af884a247e07889f79a5af837edb234a366de69882d55bc9acc42be66d7c6046",
        "content_sha256": "805c37d81c17513d98cef0308fdae30fe21a9ed91a53e44aed307d3b940d732c",
        "basis": "Under Armour's Class C shares were created by a stock dividend and began trading as UA on April 8, 2016. Earlier UA quotes are the Class A shares (later UAA) and are not Class C history.",
    },
    "INFO": {
        "keep_until": "2022-02-25",
        "last_close": "108.61",
        "url": "https://www.sec.gov/Archives/edgar/data/1598014/000119312522056012/d315930d8k.htm",
        "sha256": "604a42cb46a7c858fe27cd548b0e40510cb9454e39e641be01e0c3c25905aa77",
        "content_sha256": "3bc6bead9c71443eed470b248e0a8d706855edf815a385445eee7ddd59aa9453",
        "basis": "IHS Markit was suspended before the February 28, 2022 open when each share converted into 0.2838 S&P Global shares. Later captured INFO quotes are flat zero-volume marks or a different listing.",
    },
}

# Vendor records reviewed as belonging to another security or as erroneous.
# They stay in provenance and are never applied to the indexed security.
REJECTED_NATIVE = {
    "fa113393-e8dd-4aec-b909-c789caac7839": {
        "symbol": "CA",
        "cusip": "23306X852",
        "basis": "A 2026 fund liquidation under the reused CA ticker (CUSIP 23306X852), not CA, Inc., which Broadcom acquired in 2018.",
    },
    "8bd03f1f-6aff-4d0c-802f-2915714dfa10": {
        "symbol": "CZR",
        "cusip": "127686103",
        "basis": "Eldorado Resorts' 2020 acquisition of the former Caesars Entertainment Corporation (CUSIP 127686103). The indexed CZR series is the acquiring Eldorado issuer, renamed Caesars Entertainment, Inc., which was not converted.",
    },
    "3b688d04-65d5-4acb-85c8-81886962c729": {
        "symbol": "CZR",
        "cusip": "127686103",
        "basis": "Stock leg of the same 2020 acquisition of the former Caesars Entertainment Corporation; it does not convert the acquiring issuer's shares.",
    },
    "93d0cf80-ee34-4a91-a451-0c699386fc27": {
        "symbol": "DOC",
        "cusip": "71943U104",
        "basis": "Healthpeak's 2024 acquisition of Physicians Realty Trust (CUSIP 71943U104), the former holder of the DOC ticker. The indexed DOC series is Healthpeak (CUSIP 42250P103), which was not converted.",
    },
    "f8bed1b7-cc4a-4a79-82bf-c5c84be0fc65": {
        "symbol": "PARA",
        "cusip": "92556H206",
        "basis": "The $15.00 Class B cash election was oversubscribed and prorated; non-electing Class B holders received one Paramount Skydance Class B share. Research models the non-electing holder's stock consideration. https://www.sec.gov/Archives/edgar/data/2041610/000119312525175046/d841914d8k12b.htm",
    },
    "0c3b2854-cfc1-46b1-91c2-cf22aef1a594": {
        "symbol": "RJF",
        "cusip": "754730109",
        "basis": "The alleged 1.3 stock dividend conflicts with Raymond James's split history and with the captured raw and split-adjusted prices, which show no share-count change on April 13, 2023. https://www.raymondjames.com/investor-relations/shareholder-information/stock-split-history",
    },
    "f9d7d660-bfba-4668-a5d4-9086fa9aefe9": {
        "symbol": "TDG",
        "cusip": "893641100",
        "basis": "A second copy of TransDigm's single $90.00 special dividend paid September 12, 2025, as stated in its fiscal 2025 annual report; counting both would double it. https://www.sec.gov/Archives/edgar/data/1260221/000126022125000081/tdg-20250930.htm",
    },
    "a789bd9f-2a40-4c63-b8d1-233900c325eb": {
        "symbol": "XEL",
        "cusip": "98389B100",
        "basis": "A second copy of Xcel Energy's single $0.5475 second-quarter 2024 dividend with a different payment date; the quarterly report states one $0.5475 dividend. https://www.sec.gov/Archives/edgar/data/72903/000007290324000172/xel-20240630.htm",
    },
}

# Raw provider symbols that referred to a different security before the
# indexed company adopted them. Vendor records under the raw symbol before
# ``before`` are not attributed to the indexed company.
SYMBOL_EPOCHS = {
    "BNY": {
        "before": "2026-05-21",
        "other_cusip": "09248L106",
        "basis": "Until The Bank of New York Mellon adopted the BNY ticker (vendor rename record of May 21, 2026), BNY identified the BlackRock New York Municipal Income Trust (CUSIP 09248L106). Its monthly income and 2026 fund merger are not bank actions; the bank's dividends arrive under BK.",
    },
}

# Foreign-issuer dividends whose amount the issuer's periodic report states,
# although the vendor's USD dividend-adjusted series implies another value.
VERIFIED_DIVIDENDS = {
    ("BG", "2023-02-15"): {
        "rate": "0.625",
        "url": "https://www.sec.gov/Archives/edgar/data/1144519/000114451923000096/bg-20230331.htm",
        "basis": "Bunge's first-quarter 2023 report states dividends on common shares of $0.625 per share. The vendor lists that dividend under two CUSIPs; it is counted once.",
    },
    ("BG", "2023-08-17"): {
        "rate": "0.6625",
        "url": "https://www.sec.gov/Archives/edgar/data/1144519/000114451923000170/bg-20230630.htm",
        "basis": "Bunge's second-quarter 2023 report states the $0.6625 dividend declared May 11, 2023, payable September 1 to holders of record on August 18. The vendor lists it under the Bermuda and Swiss CUSIPs; it is counted once.",
    },
    ("LIN", "2023-03-13"): {
        "rate": "1.275",
        "url": "https://www.sec.gov/Archives/edgar/data/1707925/000162828023013457/lin-20230331.htm",
        "basis": "Linde's first-quarter 2023 report states dividends of $1.275 per ordinary share. The vendor lists the March 2023 dividend under two CUSIPs around the new holding company; it is counted once.",
    },
    ("MRVL", "2021-04-08"): {
        "rate": "0.06",
        "url": "https://www.sec.gov/Archives/edgar/data/1835632/000183563221000010/mrvl-20210501.htm",
        "basis": "Marvell's quarterly report for the period ended May 1, 2021 states cash dividends declared and paid of $0.06 per share. The vendor lists the April 2021 dividend under the Bermuda and Delaware CUSIPs; it is counted once.",
    },
    ("STX", "2021-05-11"): {
        "rate": "0.67",
        "url": "https://www.sec.gov/Archives/edgar/data/1137789/000113778921000028/stx-20210402.htm",
        "basis": "Seagate's quarterly report for the period ended April 2, 2021 states the $0.67 dividend declared April 22, 2021, payable July 7 to holders of record on May 12. The vendor lists it under two CUSIPs around the redomiciliation; it is counted once.",
    },
    ("EG", "2023-03-15"): {
        "rate": "1.65",
        "url": "https://www.sec.gov/Archives/edgar/data/1095073/000109507323000024/everestre-20230331.htm",
        "basis": "Everest's first-quarter 2023 report states dividends declared of $1.65 per share.",
    },
    ("FERG", "2026-03-06"): {
        "rate": "0.89",
        "url": "https://www.sec.gov/Archives/edgar/data/2011641/000201164126000030/ferg-20260331.htm",
        "basis": "Ferguson's quarterly report for the period ended March 31, 2026 states cash dividends declared of $0.89 per share.",
    },
    ("WTW", "2021-12-30"): {
        "rate": "0.80",
        "url": "https://www.sec.gov/Archives/edgar/data/1140536/000156459021052630/wltw-10q_20210930.htm",
        "basis": "WTW's third-quarter 2021 report states the quarterly dividend rate of $0.80 per share approved in July 2021; the next increase, to $0.82, was approved in February 2022.",
    },
}

# A provider can omit a dated vintage's final sessions. These supplements add
# later quotes from the undated mapping only when every overlapping session
# matches the captured vintage exactly.
QUOTE_SUPPLEMENTS = {
    "LVLT": {
        "quote_asof": "2017-10-12",
        "captured_last": "2017-10-12",
        "overlap_from": "2017-10-02",
        "until": "2017-10-31",
        "basis": "The October 12, 2017 quote vintage ends before Level 3's final NYSE session. The undated mapping matches every overlapping OHLCV row exactly and supplies October 13 through October 31, 2017; trading ceased at 9:00 a.m. on November 1.",
    },
}


def verified_dividend(symbol, day, amount):
    """The issuer's report states this amount; a vendor adjustment is not evidence."""
    proof = VERIFIED_DIVIDENDS.get((symbol, str(day)))
    return bool(proof and decimal(amount) == decimal(proof["rate"]))


def supplement_quotes(bars, identities, first, last, issue, quotes):
    """Append omitted final sessions from the undated provider mapping."""
    receipts = {}
    for symbol, spec in sorted(QUOTE_SUPPLEMENTS.items()):
        rows = bars.get(symbol)
        until = date.fromisoformat(spec["until"])
        if not rows or not first <= until <= last:
            continue
        captured = date.fromisoformat(spec["captured_last"])
        if identities.get(symbol, {}).get("asof") != spec["quote_asof"]:
            continue
        if max(rows) > captured:
            if max(rows) == until:
                continue  # Already supplemented in the saved history.
            issue(
                symbol,
                captured,
                "Reviewed quote supplement conflicts with the captured sessions.",
            )
            continue
        begin = date.fromisoformat(spec["overlap_from"])
        observed = quotes([symbol], begin, until, None).get(symbol, {})
        adjusted = quotes([symbol], begin, until, None, "split").get(symbol, {})
        overlap = [d for d in rows if begin <= d <= captured]
        fields = ("open", "high", "low", "close", "volume")
        if not overlap or any(
            d not in observed
            or any(getattr(rows[d], f) != getattr(observed[d], f) for f in fields)
            for d in overlap
        ):
            issue(
                symbol,
                captured,
                "Reviewed quote supplement no longer matches the captured vintage.",
            )
            continue
        added = {d: b for d, b in observed.items() if captured < d <= until}
        if (
            not added
            or max(added) != until
            or any(
                adjusted.get(d) is None or adjusted[d].close != b.close
                for d, b in added.items()
            )
        ):
            issue(
                symbol,
                captured,
                "Reviewed quote supplement sessions are incomplete or not in raw share units.",
            )
            continue
        rows.update({d: replace(b, symbol=symbol) for d, b in added.items()})
        receipts[symbol] = {
            "version": VERSION,
            **spec,
            "matched_overlap_sessions": len(overlap),
            "added_sessions": [str(d) for d in sorted(added)],
        }
    return receipts


def _proof(record):
    return {k: record[k] for k in ("url", "sha256", "content_sha256") if k in record}


def displaced_native():
    """Vendor records replaced by reviewed distributions, by event ID."""
    return {
        event_id: spec["parent"]
        for spec in DISTRIBUTIONS
        for event_id in spec.get("displaces", {})
    }


def rejected_native(event, symbol, day, owner=None):
    """Reason a raw vendor record belongs to another security, or ``None``.

    ``symbol`` is the provider's raw symbol; ``owner`` the indexed label.
    """
    proof = REJECTED_NATIVE.get(event.get("id"))
    if proof and proof["symbol"] in (symbol, owner):
        return proof["basis"]
    epoch = SYMBOL_EPOCHS.get(symbol)
    if epoch and (
        str(day) < epoch["before"]
        or epoch["other_cusip"]
        in (
            event.get("cusip"),
            event.get("acquiree_cusip"),
            event.get("source_cusip"),
        )
    ):
        return epoch["basis"]
    return None


def children_asof():
    """Historical quote vintages for spin-off children and merger recipients."""
    result = {
        child["symbol"]: date.fromisoformat(child["asof"])
        for spec in DISTRIBUTIONS
        for child in spec["children"]
        if child.get("asof")
    }
    result.update(
        {
            "ECA": date(2019, 2, 14),
            "BPY": date(2018, 8, 28),
        }
    )
    return result


def dependencies(names, first, last):
    """Recipients and children a reviewed record needs prices for."""
    result = set()
    for symbol, spec in TERMINALS.items():
        if symbol in names and first <= date.fromisoformat(spec["effective"]) <= last:
            result.update(t["symbol"] for t in spec["targets"])
    for spec in DISTRIBUTIONS:
        if (
            spec["parent"] in names
            and first <= date.fromisoformat(spec["ex_date"]) <= last
        ):
            result.update(child["symbol"] for child in spec["children"])
    return result - set(names)


FACTOR_CONFLICT = "The recorded split or distribution implies a one-day total return far from the raw price change and the market; a distribution may be recorded as a split, or counted twice. The holding is not valued until the action is reviewed."
# Genuine share changes whose day coincided with an extreme price move.
VERIFIED_FACTORS = {}


def implausible_share_factors(bars, reviewed_days, limit=Decimal("0.25")):
    """Flag split/distribution days whose total return contradicts raw prices.

    A recorded share factor or distribution must roughly reconcile with the
    raw close-to-close move. Relative to SPY, a move beyond about -22%/+28%
    on such a day signals a mislabeled or duplicated action. Reviewed days
    and verified extreme genuine events are exempt.
    """
    import math

    market = bars.get("SPY", {})
    days = sorted(market)
    spy = {b: market[b].close / market[a].close for a, b in zip(days, days[1:])}
    findings = []
    for symbol, rows in bars.items():
        ordered = sorted(rows)
        for before, day in zip(ordered, ordered[1:]):
            row = rows[day]
            if row.split == 1 and not row.research_distribution:
                continue
            if (symbol, str(day)) in reviewed_days or (
                symbol,
                str(day),
            ) in VERIFIED_FACTORS:
                continue
            total = (
                row.split
                * (row.close + row.research_dividend + row.research_distribution)
                / rows[before].close
            )
            relative = total / spy.get(day, Decimal(1))
            if relative <= 0 or abs(Decimal(math.log(relative))) > limit:
                findings.append((symbol, day, FACTOR_CONFLICT))
    return findings


def _matches_close(rows, day, expected):
    row = rows.get(date.fromisoformat(day))
    return row is not None and row.close == decimal(expected)


def apply(bars, identities, events, income, issues, first, last, api, issue):
    """Apply reviewed records after historical blocks are assembled.

    Values are set absolutely, so a repeated Update reproduces the same inputs.
    Returns events, the remaining issues and receipts for provenance.
    """
    from .lifecycles import MERGERS, recipients

    receipts = []
    resolved = set()  # (symbol, start, reason)

    def document(record):
        for source in [
            record,
            *([record["terms_source"]] if "terms_source" in record else []),
        ]:
            if not primary_matches(api.document(source["url"]), source):
                raise ResearchError(
                    f"{record.get('symbol') or record.get('parent')}: reviewed corporate-event source fingerprint changed. Recheck the primary filing."
                )

    # Listing lifetimes first: later guards compare the reviewed quotes.
    for symbol, spec in sorted(LIFETIMES.items()):
        rows = bars.get(symbol)
        if not rows:
            continue
        if "keep_from" in spec:
            cut = date.fromisoformat(spec["keep_from"])
            if not first < cut <= last:
                continue
            if not _matches_close(rows, spec["keep_from"], spec["first_close"]):
                issue(
                    symbol,
                    first,
                    "Reviewed listing start no longer matches the captured quotes.",
                    "identity",
                    spec["keep_from"],
                )
                continue
            document({"symbol": symbol, **spec})
            bars[symbol] = {d: b for d, b in rows.items() if d >= cut}
        else:
            cut = date.fromisoformat(spec["keep_until"])
            if not first <= cut < last:
                continue
            if not _matches_close(rows, spec["keep_until"], spec["last_close"]):
                issue(
                    symbol,
                    cut,
                    "Reviewed listing end no longer matches the captured quotes.",
                    "identity",
                    last,
                )
                continue
            document({"symbol": symbol, **spec})
            bars[symbol] = {d: b for d, b in rows.items() if d <= cut}
        receipts.append(
            {
                "id": f"reviewed-{symbol}-lifetime",
                "kind": "reviewed_lifetimes",
                "source": symbol,
                "effective": spec.get("keep_from") or spec["keep_until"],
                "reviewed_evidence": {"version": VERSION, "symbol": symbol, **spec},
            }
        )

    # Distributions: neutralize vendor proxies and value the child shares.
    for spec in DISTRIBUTIONS:
        parent, day = spec["parent"], date.fromisoformat(spec["ex_date"])
        rows = bars.get(parent, {})
        if not first < day <= last or day not in rows:
            continue
        before = max((d for d in rows if d < day), default=None)
        if (
            before is None
            or rows[before].close != decimal(spec["prev_close"])
            or rows[day].close != decimal(spec["close"])
        ):
            issue(
                parent,
                day,
                "Reviewed distribution no longer matches the captured parent quotes; the vendor split proxy is withheld.",
            )
            continue
        split = decimal(spec.get("parent_split", "1"))
        value = opening = decimal(spec.get("cash", "0"))
        priced = []
        missing = []
        for child in spec["children"]:
            when = date.fromisoformat(child.get("price_date", spec["ex_date"]))
            row = bars.get(child["symbol"], {}).get(when)
            if row is None:
                missing.append(child["symbol"])
                continue
            ratio = decimal(child["ratio"])
            value += ratio * row.close
            # A later first price cannot fund an earlier opening trade.
            opening += ratio * (row.open if when == day else ZERO)
            priced.append(
                {
                    **child,
                    "close": str(row.close),
                    "open": str(row.open),
                    "priced_on": str(when),
                }
            )
        if missing:
            issue(
                parent,
                day,
                f"Reviewed distribution child price is unavailable: {', '.join(missing)}.",
            )
            continue
        per_share = value / split
        row = rows[day]
        total = (
            split * (row.close + row.research_dividend + per_share) / rows[before].close
        )
        if not Decimal("0.6") < total < Decimal("1.6"):
            issue(
                parent,
                day,
                "Reviewed distribution produces an implausible one-day total return; inputs need review.",
            )
            continue
        document({"symbol": parent, **spec})
        previous = {
            "split": str(row.split),
            "research_distribution": str(row.research_distribution),
        }
        rows[day] = replace(row, split=split, research_distribution=per_share)
        income.setdefault(str(day), {})[parent] = str(opening / split)
        issue(parent, day, DISTRIBUTION_NOTE, "cash_payment")
        for event_id in spec.get("displaces", {}):
            from .research_overrides import CONFLICTS

            if event_id in CONFLICTS:
                resolved.add((parent, str(day), CONFLICTS[event_id]))
        resolved.add((parent, str(day), SPLIT_CONFLICT))
        resolved.update(
            (
                parent,
                str(day),
                f"Spin-off consideration {c['symbol']} has no verified ex-date price.",
            )
            for c in spec["children"]
        )
        rejected = []
        for event_id, signature in spec.get("rejects_merger", {}).items():
            for i, event in enumerate(events):
                if event["id"] != event_id:
                    continue
                # A frozen earlier snapshot already carries this rejection;
                # an incremental Update must reproduce it, not fail on it.
                kind = (
                    event.get("original_kind")
                    if event["kind"] == "rejected_native_merger"
                    else event["kind"]
                )
                if (
                    kind != signature["kind"]
                    or event["effective"] != signature["effective"]
                    or decimal(event.get("cash", 0)) != decimal(signature["cash"])
                ):
                    raise ResearchError(
                        f"{parent}: reviewed merger replacement no longer matches the vendor record."
                    )
                events[i] = {
                    **event,
                    "original_kind": kind,
                    "kind": "rejected_native_merger",
                    "reviewed_rejection": {
                        "version": VERSION,
                        **_proof(spec),
                        "basis": spec["basis"],
                    },
                }
                rejected.append(event_id)
                resolved.add(
                    (
                        parent,
                        event["effective"],
                        "A renamed predecessor has merger consideration requiring a separate verified price/share basis.",
                    )
                )
        receipts.append(
            {
                "id": f"reviewed-{parent}-{day}-distribution",
                "kind": "reviewed_distributions",
                "source": parent,
                "effective": str(day),
                "children": priced,
                "cash": spec.get("cash", "0"),
                "parent_split": str(split),
                "per_share_value": str(per_share),
                "previous": previous,
                "displaced_records": sorted(spec.get("displaces", {})),
                "rejected_mergers": rejected,
                "reviewed_evidence": {
                    "version": VERSION,
                    "symbol": parent,
                    **{k: v for k, v in spec.items() if k not in ("children",)},
                },
            }
        )

    # Terminal conversions.
    for symbol, spec in sorted(TERMINALS.items()):
        rows = bars.get(symbol)
        effective = date.fromisoformat(spec["effective"])
        if not rows or not first <= effective <= last:
            continue
        final = date.fromisoformat(spec["last_trading"])
        if identities.get(symbol, {}).get("asof") != spec["quote_asof"]:
            issue(
                symbol,
                final,
                "Reviewed terminal terms no longer match the captured quote vintage.",
            )
            continue
        if not _matches_close(rows, spec["last_trading"], spec["last_close"]):
            issue(
                symbol,
                final,
                "Reviewed terminal terms conflict with the captured final session.",
            )
            continue
        later = [d for d in rows if d > final]
        if later and not spec.get("truncate"):
            issue(
                symbol,
                final,
                "Reviewed terminal terms conflict with later captured quotes.",
            )
            continue
        record_id = f"reviewed-{symbol}-{spec['effective']}-terminal"
        # An incremental Update carries this record from the frozen earlier
        # snapshot; it is replaced below, not treated as a vendor instruction.
        natives = [
            i
            for i, e in enumerate(events)
            if e["source"] == symbol and e["kind"] in MERGERS and e["id"] != record_id
        ]
        replaced = spec.get("replaces", {})
        conflict = False
        for i in natives:
            event = events[i]
            signature = replaced.get(event["id"])
            if (
                not signature
                or event["kind"] != signature["kind"]
                or event["effective"] != signature["effective"]
                or decimal(event.get("cash", 0)) != decimal(signature["cash"])
                or sorted((s, str(r.normalize())) for s, r in recipients(event))
                != sorted(
                    (s, str(decimal(r).normalize())) for s, r in signature["targets"]
                )
            ):
                conflict = True
        if conflict:
            issue(
                symbol,
                final,
                "Unreviewed vendor merger instructions conflict with the reviewed terminal terms.",
            )
            continue
        document({"symbol": symbol, **spec})
        if later:
            bars[symbol] = {d: b for d, b in rows.items() if d <= final}
        for i in natives:
            event = events[i]
            resolved.update(
                (symbol, event["effective"], reason)
                for reason in (
                    f"Merger has unlisted contingent consideration: {event.get('unpriced_consideration')}.",
                    "Merger cash payment date is unavailable.",
                )
            )
            events[i] = {
                **event,
                "original_kind": event["kind"],
                "kind": "rejected_native_merger",
                "reviewed_rejection": {
                    "version": VERSION,
                    **_proof(spec),
                    "basis": spec["basis"],
                    "verified_conversion": spec["effective"],
                },
            }
        targets = spec["targets"]
        cash = decimal(spec["cash"])
        kind = (
            "cash_mergers"
            if not targets
            else "stock_and_cash_mergers"
            if cash
            else "stock_mergers"
        )
        record = {
            "id": record_id,
            "kind": kind,
            "source": symbol,
            "target": targets[0]["symbol"] if len(targets) == 1 else None,
            "ratio": targets[0]["ratio"] if len(targets) == 1 else "0",
            "cash": spec["cash"],
            "effective": spec["effective"],
            "legal_effective": spec["legal_effective"],
            "pay_date": None,
            "source_record": None,
            "reviewed_evidence": {"version": VERSION, "symbol": symbol, **spec},
        }
        if len(targets) > 1:
            record["targets"] = targets
        events[:] = [e for e in events if e["id"] != record["id"]] + [record]
        if cash:
            issue(
                symbol,
                effective,
                "Merger cash payment date is unavailable.",
                "cash_payment",
            )

    # Reviewed separations replace the vendor factor that the split-adjusted
    # series still embeds; that comparison is not a remaining conflict.
    resolved.update(
        (e["source"], e["effective"], SPLIT_CONFLICT)
        for e in events
        if e["kind"] == "reviewed_separations" and e.get("target")
    )
    # Drop gates the reviewed records resolved, keeping every other issue.
    # A repeated Update re-adds the same notes to the carried issues; keep one.
    remaining, seen = [], set()
    for i in issues:
        key = (i["symbol"], i["start"], i["end"], i["kind"], i["reason"])
        if (i["symbol"], i["start"], i["reason"]) in resolved or key in seen:
            continue
        seen.add(key)
        remaining.append(i)
    return events, remaining, receipts
