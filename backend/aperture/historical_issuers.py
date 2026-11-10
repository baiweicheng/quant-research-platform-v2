"""Dated SEC ticker evidence for specific captured historical quote vintages.

No current-ticker guess, synthetic asset UUID or cross-issuer earnings splice.
The provider's explicit quote-asof selects the historical security; these filed
cover pages establish the issuer and common listing for the reviewed vintage.
Price, action, EPS-unit and filing-availability checks remain independent.
"""

from .action_evidence import primary_matches
from .domain import ResearchError

VERSION = "reviewed-historical-issuer-v1"
ISSUERS = {
    "BBBY": {
        "cik": "0000886158",
        "quote_asof": "2017-07-25",
        "name": "Bed Bath & Beyond Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/886158/000117184317003900/R1.htm",
        "sha256": "ab8bb89bc6898fbc5ef2817ccad1bbd230ce05f28aca42e02283d822796a696e",
        "content_sha256": "cbb85c59893457a628d4e48700b8a2b4c19f6078e75cd632fe0c825ad598e324",
        "basis": "June 2017 filed cover identifies BBBY and CIK 886158. This is the original Bed Bath & Beyond issuer, not the unrelated issuer later using BBBY after the original equity's cancellation.",
    },
    "FTR": {
        "cik": "0000020520",
        "quote_asof": "2017-03-17",
        "name": "Frontier Communications Corporation",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/20520/000002052017000003/ftr-20161231x10k.htm",
        "sha256": "f640a7d4b7082c8abcf2fa7787eb8f746b5f24a39667ab4c3525efa19ca4b9e6",
        "content_sha256": "fac9020b0543186e1fcd4e85cc547c61f2867b0281b8314e87d23b16fbf3df5e",
        "basis": "March 2017 10-K, Item 5, identifies the original Frontier common stock trading as FTR on Nasdaq. It does not identify the new equity issued after the later bankruptcy.",
    },
    "ENDP": {
        "cik": "0001593034",
        "quote_asof": "2017-03-01",
        "name": "Endo International plc",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1593034/000159303417000009/R1.htm",
        "sha256": "754106288ebf8a96dfee21313ab5c4f05162b460b1ec10e040335428f51bc67d",
        "content_sha256": "275078561f11cc50bce3abdfd6f3791a7072600ebebf68f7b098c2c6d063f697",
        "basis": "March 2017 filed cover identifies ENDP and CIK 1593034. The mapped financial history belongs to the original Endo International equity, not the later restructured Endo issuer.",
    },
    "MNK": {
        "cik": "0001567892",
        "quote_asof": "2017-07-25",
        "name": "Mallinckrodt plc",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1567892/000156789217000020/R1.htm",
        "sha256": "306000161a3d487df758cdedc5aa5e7ad3bbd7494429efca43e5f6d609f10ac8",
        "content_sha256": "7b122c05c92ad99bb0e5d5e2646600b2ece9eeb75f7e7461e2306eb1525e1977",
        "basis": "May 2017 filed cover identifies MNK and CIK 1567892. This mapping is limited to the reviewed 2017 quote vintage and does not certify continuity through later restructurings.",
    },
    "KORS": {
        "cik": "0001530721",
        "quote_asof": "2018-09-18",
        "name": "Michael Kors Holdings Limited",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1530721/000153072118000035/R1.htm",
        "sha256": "15819b3e8ddefd5e8056e45db2d476d0e4b1b19d25a80a5401cc2e396eaff63f",
        "content_sha256": "f56928f065a27eebac03bae17f7d07a78f121557fafe415aeb8120f57184f9cb",
        "basis": "Fiscal 2018 annual filed cover explicitly identifies trading symbol KORS and CIK 1530721 before the later Capri rename. The quarterly cover alone omitted the ticker and was insufficient evidence.",
    },
    "TMK": {
        "cik": "0000320335",
        "quote_asof": "2019-08-07",
        "name": "Torchmark Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/320335/000032033519000024/R1.htm",
        "sha256": "eb34d877770bda55399f58db08f06040fbf08d3639bcfb9beefde82e80e2fbab",
        "content_sha256": "f4b78e59b7c89541f5cb6f3f3e3233f13bf07900eaf161a4603bdf634f01eadc",
        "basis": "July 2019 filed cover identifies TMK common stock on NYSE and CIK 320335; the reviewed quote vintage precedes the August 2019 Globe Life rename.",
    },
    "HRS": {
        "cik": "0000202058",
        "quote_asof": "2019-05-31",
        "name": "Harris Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/202058/000020205819000023/R1.htm",
        "sha256": "5e1397bd5539fc6429b98500a05956a19682ffae65a3e1ecdfff431680cd7319",
        "content_sha256": "f3c78b54a3a8b6d0ac3a977eba3df6400861463bc83095b1027c105dbcb78c9e",
        "basis": "Filed 2019 Harris cover explicitly identifies HRS and CIK 202058, before the June 2019 L3Harris combination. This does not identify the separate LLL equity.",
    },
    "ADS": {
        "cik": "0001101215",
        "quote_asof": "2020-06-19",
        "name": "Alliance Data Systems Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1101215/000110121520000152/R1.htm",
        "sha256": "0ab2ab224a3c78f450fe53486875b4e4fd658655e2b118207202198497f44ae6",
        "content_sha256": "b44463aaba00262280cb0c79656f33d69b01cc6f6424fcffd8009ef259f32ca0",
        "basis": "June 2020 filed cover identifies ADS common stock on NYSE and CIK 1101215. Financial statements retain their original accession/availability dates, including when the present ticker differs.",
    },
    "GPS": {
        "cik": "0000039911",
        "quote_asof": "2022-02-01",
        "name": "The Gap, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/39911/000003991122000012/R1.htm",
        "sha256": "2e87e9d99ed0b2068bdae9cae73a902ceff63ecd538cb1e82fc4ae7d713010ee",
        "content_sha256": "160adb53f9e617772f7647d119ebad40dacf279f8640d5fea7295fc1bcd682a1",
        "basis": "Filed fiscal 2021 cover identifies Gap common stock, GPS and NYSE. The accession path belongs to CIK 39911; the reviewed quote vintage precedes the later GAP ticker.",
    },
    "SYMC": {
        "cik": "0000849399",
        "quote_asof": "2019-11-04",
        "name": "Symantec Corporation",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/849399/000084939919000008/R1.htm",
        "sha256": "7a24329d04b3a6641a7a3c1cd37becf946f64ca3d871eb6e72b99e041af3b15c",
        "content_sha256": "ecb6547390279154077ca67a921e771537124efeca07650fe025f938ad803551",
        "basis": "Filed 2019 cover identifies SYMC common stock on Nasdaq and the Symantec issuer. The reviewed quote vintage precedes the November 5 NLOK rename; this does not map Broadcom shares to Symantec earnings.",
    },
}


def verify(symbol, quote_asof, api):
    proof = ISSUERS.get(symbol)
    if not proof or str(quote_asof) != proof["quote_asof"]:
        return None
    if not primary_matches(api.document(proof["url"]), proof):
        raise ResearchError(
            f"{symbol}: reviewed historical issuer source fingerprint changed."
        )
    return {"symbol": symbol, "version": VERSION, **proof}


def mapping_evidence(metadata, symbol):
    """Only the known proof and matching captured quote context can override a directory."""
    expected = ISSUERS.get(symbol)
    supplied = metadata.get("historical_issuer_evidence", {}).get(symbol)
    identity = metadata.get("identity_resolution", {}).get(symbol, {})
    if (
        expected
        and supplied == {"symbol": symbol, "version": VERSION, **expected}
        and identity.get("asof") == expected["quote_asof"]
    ):
        return supplied
    return None
