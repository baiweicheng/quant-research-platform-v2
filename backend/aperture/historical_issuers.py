"""Dated SEC ticker evidence for specific captured historical quote vintages.

No current-ticker guess, synthetic asset UUID or cross-issuer earnings splice.
The provider's explicit quote-asof selects the historical security; these filed
cover pages establish the issuer and common listing for the reviewed vintage.
Price, action, EPS-unit and filing-availability checks remain independent.
"""

from .action_evidence import primary_matches
from .domain import ResearchError

VERSION = "reviewed-historical-issuer-v1"
# Entries with ``cik`` None establish a listing identity for an issuer that
# filed with a bank regulator rather than the SEC; they map no financials.
ISSUERS = {
    "AGN": {
        "cik": "0001578845",
        "quote_asof": "2020-05-11",
        "name": "Allergan, plc",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1578845/000156459020022386/R1.htm",
        "sha256": "fd849a1e624d35ddecdce9623c5ebc4096440c2be91707c45673dd3b1ecf4b93",
        "content_sha256": "f2bda98c4486ed87e9d9c824fe51e85776ef63c2ff0230295b7e9ee6f2442a20",
        "basis": "The filed cover associates AGN ordinary shares with Allergan plc, CIK 1578845. The second registrant, "
        "Warner Chilcott Limited (CIK 1620602), is a separate subsidiary and is not the source of AGN common-share "
        "financials.",
    },
    "ALXN": {
        "cik": "0000899866",
        "quote_asof": "2021-07-20",
        "name": "ALEXION PHARMACEUTICALS, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/899866/000089986621000039/R1.htm",
        "sha256": "0b28c0e3dfe420616996a5ddea3b5cd436d77f7cfba0cb380b4ff19d5d5f9ac7",
        "content_sha256": "965f2153eea558c2a522a3b9f3df2e42053b0b7d71460adc5ee145ea0b57ca65",
        "basis": "The dated SEC filing identifies ALXN and original issuer CIK 899866. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "ARNC": {
        "cik": "0000004281",
        "quote_asof": "2020-04-03",
        "name": "Arconic Inc. (continuing Howmet parent)",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/4281/000110465920043824/tm2015094d1_8k.htm",
        "sha256": "d6c40d8f10e6440ceda0b5139e551b903ed5e4174415a7063b386beca651ed99",
        "content_sha256": "d6c40d8f10e6440ceda0b5139e551b903ed5e4174415a7063b386beca651ed99",
        "basis": "The completed separation filing identifies the original Arconic Inc. parent, CIK 4281, continuing as "
        "Howmet. This financial mapping requires the v8 price-cohort repair; the new Arconic Corporation child (CIK "
        "1790982) is a different issuer.",
        "required_price_contracts": [
            "dated-research-inputs-v8-reviewed-separations",
            "dated-research-inputs-v9-reviewed-security-events",
        ],
    },
    "ATVI": {
        "cik": "0000718877",
        "quote_asof": "2023-10-17",
        "name": "ACTIVISION BLIZZARD, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/718877/000162828023026269/R1.htm",
        "sha256": "5bf164c3396bafee285e11bc745c4fb5461dc3d5feb1f5b731d2d3d81300593c",
        "content_sha256": "b552dd13ea7556639045c9de66a5bb53b8f98f304622d3c27b0264ea5018d1ac",
        "basis": "The dated SEC filing identifies ATVI and original issuer CIK 718877. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "AVB": {
        "cik": "0000915912",
        "quote_asof": "2026-08-17",
        "name": "AVALONBAY COMMUNITIES, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/915912/000091591226000020/R1.htm",
        "sha256": "2cb9b0ec601c535f7b0247b480bfef522ea5bb078faf9c50079f30cec29b48b3",
        "content_sha256": "c57b22a7819e57b34f83abe9fa328150ecf5adcedc4a8950fb593933137ee668",
        "basis": "The dated SEC filing identifies AVB and original issuer CIK 915912. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "CERN": {
        "cik": "0000804753",
        "quote_asof": "2022-06-07",
        "name": "Cerner",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/804753/000080475322000009/cern-20211231.htm",
        "sha256": "dc561118d2b0c449a7cecfe636a1dceb05dd01dbeeb32596dfb5db0258a8e15f",
        "content_sha256": "f8fa3fa6c57ae45849942507bdc93419ae0ac589379850467137981571f269bf",
        "basis": "The dated SEC filing identifies CERN and original issuer CIK 804753. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "CHK": {
        "cik": "0000895126",
        "quote_asof": "2018-03-16",
        "name": "CHESAPEAKE ENERGY CORPORATION",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/895126/000089512618000060/R1.htm",
        "sha256": "2fb72b870f9155bb652a98958fd9b2115c0700ce4e59145c198d7836f3ec6bae",
        "content_sha256": "933af8cba51833586a660dcbd22bc0078d263fdd572106d87bfd8f708b34ff55",
        "basis": "The dated SEC filing identifies CHK and original issuer CIK 895126. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification. This is the original pre-bankruptcy Chesapeake issuer, not its new post-reorganization "
        "equity.",
    },
    "CMA": {
        "cik": "0000028412",
        "quote_asof": "2024-06-21",
        "name": "Comerica Incorporated",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/28412/000002841224000263/R1.htm",
        "sha256": "600eda4e71537ff40ee14b22655589457457e3bd763913d0d14a64f2e68d427d",
        "content_sha256": "19d85ed697b8f0af48d85284a9b42ddcc0a5f3bc11310e7777b2d2d8deb58ef0",
        "basis": "The dated SEC filing identifies CMA and original issuer CIK 28412. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "CTRA": {
        "cik": "0000858470",
        "quote_asof": "2026-05-06",
        "name": "COTERRA ENERGY INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/858470/000085847026000082/R1.htm",
        "sha256": "f529f57c014f34ee4daec5a56a0c1f3c7c447b0b9d37830010a9aba09830faf2",
        "content_sha256": "6e9b4bbc8ed3165eb233ffe3bb73c4706bc27ae07a62507ba3d130bb11faefd1",
        "basis": "The dated SEC filing identifies CTRA and original issuer CIK 858470. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "CTXS": {
        "cik": "0000877890",
        "quote_asof": "2022-09-30",
        "name": "CITRIX SYSTEMS, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/877890/000087789022000079/R1.htm",
        "sha256": "56017c57b779ea0e2d4ffb52705e97f346a0828c6004d326080f253686ecd71a",
        "content_sha256": "0384bf91cb52b3e7d953961e2b23c06c5707d386fa7ce31ade067bceb59667b5",
        "basis": "The dated SEC filing identifies CTXS and original issuer CIK 877890. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "CXO": {
        "cik": "0001358071",
        "quote_asof": "2021-01-20",
        "name": "Concho Resources Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1358071/000135807120000059/R1.htm",
        "sha256": "948c1428d2b71f65e0805dd211d87c5544a26ab5bcf3baa890c6f7e5efaf1433",
        "content_sha256": "c7e2d0344e6a301dd984f610aa32efa8338f16fa0bafc4361cc167c68e12a03c",
        "basis": "The dated SEC filing identifies CXO and original issuer CIK 1358071. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "DFS": {
        "cik": "0001393612",
        "quote_asof": "2025-05-16",
        "name": "Discover Financial",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1393612/000139361225000009/dfs-20241231.htm",
        "sha256": "0e28cf43929490389b773458a5e99f3c67e07dc303197b07b8c4b842119a251d",
        "content_sha256": "4be5565899d0ff69eb15904d2597b4589c73df37d9ca3b0d3a491f194a026e7c",
        "basis": "The dated SEC filing identifies DFS and original issuer CIK 1393612. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "DISCK": {
        "cik": "0001437107",
        "quote_asof": "2022-04-08",
        "name": "Discovery, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1437107/000143710722000031/R1.htm",
        "sha256": "e4caab2dca06bbe08a39b887d58d73a31a0e27e295ac7a3bad8f06c55d6a10a4",
        "content_sha256": "42338fceab4b8383c3a082b46dfdf06bd1ee265d443d84320f408c67613b58dd",
        "basis": "The dated SEC filing identifies DISCK and original issuer CIK 1437107. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "DISH": {
        "cik": "0001001082",
        "quote_asof": "2023-06-16",
        "name": "Dish Network",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1001082/000155837023001811/dish-20221231x10k.htm",
        "sha256": "70d7710690ebaba71bdaac0930117c7463cd84c80c31602db66e0d41940cce58",
        "content_sha256": "9c6fc24af183ea9a71a7d0d6e7ac8940285b06bd40d3867bd211b0ae631e6784",
        "basis": "The dated SEC filing identifies DISH and original issuer CIK 1001082. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "DNB": {
        "cik": "0001115222",
        "quote_asof": "2017-04-04",
        "name": "Dun & Bradstreet",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1115222/000111522217000007/a201610-k.htm",
        "sha256": "0934f440e25e1113e673b0905745bd62e868acaa4fdcb1a6c726f4e80f66b25c",
        "content_sha256": "945942cdbed843c3e5c45d5924d2df651b7a5bcf75c2dc3b018cbdfe6236a478",
        "basis": "The dated SEC filing identifies DNB and original issuer CIK 1115222. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification. This is the old Dun & Bradstreet Corporation, not Dun & Bradstreet Holdings from the later "
        "IPO.",
    },
    "DRE": {
        "cik": "0000783280",
        "quote_asof": "2022-09-30",
        "name": "Duke Realty",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/783280/000078328022000054/R1.htm",
        "sha256": "87d7317aa02acb2523b05ff96ebc91a3b84f4b52ea4c0f6ca1b9b8038e561d2c",
        "content_sha256": "ec3cc7e961ea6a8becd154b7236822cdc526074accc5365611ebae967a92272d",
        "basis": "The filed cover identifies DRE common stock of Duke Realty Corporation, CIK 783280. Duke Realty Limited "
        "Partnership (CIK 1003410) is a different co-registrant and does not supply DRE common-share financials.",
    },
    "DWDP": {
        "cik": "0001666700",
        "quote_asof": "2019-05-31",
        "name": "DowDuPont",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1666700/000166670019000006/a2018dwdp10-k.htm",
        "sha256": "f5d5972ff0d7e4ffaf638ce39617a5a5c136b30eedb4512ffb23a1e832a965d2",
        "content_sha256": "037795a1fdbaf63b17922363d1a8b5a241a21f28dd1e70c3e6ebc376950ffffd",
        "basis": "Item 5 identifies the new DowDuPont common stock, CIK 1666700, trading from September 1, 2017. The v8 price "
        "contract removes unsupported predecessor warm-up and reconciles the later Dow/Corteva distributions, parent "
        "reverse split and DD continuation.",
        "required_price_contracts": [
            "dated-research-inputs-v8-reviewed-separations",
            "dated-research-inputs-v9-reviewed-security-events",
        ],
    },
    "ESRX": {
        "cik": "0001532063",
        "quote_asof": "2018-12-20",
        "name": "Express Scripts Holding Co.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1532063/000153206318000014/R1.htm",
        "sha256": "6853ab2e691539b02927c440b9bde428464421f61837554c3e65e2dbb57ffc8a",
        "content_sha256": "101801aa02f0eb150db90f63001361564a50ddac3f46d46e6ffb4be5fd47619c",
        "basis": "The dated SEC filing identifies ESRX and original issuer CIK 1532063. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "ETFC": {
        "cik": "0001015780",
        "quote_asof": "2020-10-06",
        "name": "E*Trade",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1015780/000101578020000065/etfc-2019123110k.htm",
        "sha256": "4e000a78d6cb41cc7404ef81194f64bde418f156b13f51b43273bce4f774a03d",
        "content_sha256": "aa1194517823b3c4e70b983874d76b60cd04cba17a908a49e8bdfdbca5feb3ab",
        "basis": "The dated SEC filing identifies ETFC and original issuer CIK 1015780. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "EVHC": {
        "cik": "0001678531",
        "quote_asof": "2018-10-10",
        "name": "Envision Healthcare",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1678531/000167853118000033/evhc10k20171231.htm",
        "sha256": "8359ea4bd82acf3d5a248732c768aecd091419787b29aecdf068538bcb25004f",
        "content_sha256": "38a6a133384802cb3d98bbafbd5c6d34c7f9c0433a5568e7db48c131f1b9a5c3",
        "basis": "The 2017 annual report identifies Envision Healthcare Corporation, CIK 1678531, whose common stock began "
        "trading as EVHC on December 2, 2016 after the combination. The archived AmSurg CIK 895930 is not "
        "substituted for this issuer.",
    },
    "FL": {
        "cik": "0000850209",
        "quote_asof": "2019-08-08",
        "name": "FOOT LOCKER, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/850209/000155837019005654/R1.htm",
        "sha256": "ca097c7409d0c270048af92cf87ec6aca41ce920ac16bace52f2615ba1f442f0",
        "content_sha256": "2d56b4db5be32aae4e5b7d29c0fd5d8f2db1321a86925a08e9b887ac6e3eff5f",
        "basis": "The dated SEC filing identifies FL and original issuer CIK 850209. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "FLIR": {
        "cik": "0000354908",
        "quote_asof": "2021-05-13",
        "name": "FLIR Systems",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/354908/000035490821000016/flir-20201231.htm",
        "sha256": "f18d2925748fcbff311dc8b4cdb183f65c36fb19ac8fcfa7c08210f635bc8643",
        "content_sha256": "1b7061db97ed63e5ebdfedc19f94875824fab298d7770fc356155a2ec87cf5cb",
        "basis": "The dated SEC filing identifies FLIR and original issuer CIK 354908. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "FLT": {
        "cik": "0001175454",
        "quote_asof": "2024-03-22",
        "name": "FLEETCOR Technologies, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1175454/000162828024008060/R1.htm",
        "sha256": "aea367b7b29afd9fb4f8d6c99dcf4ecaffe511cc04cd5b063339988b9729657c",
        "content_sha256": "e45a6c5a87c8201cf9d5bc3a1b3c56172d9cc4ed53eff1256d97f8e5d97eccca",
        "basis": "The dated SEC filing identifies FLT and original issuer CIK 1175454. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "HBI": {
        "cik": "0001359841",
        "quote_asof": "2021-12-17",
        "name": "Hanesbrands Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1359841/000135984121000174/R1.htm",
        "sha256": "ed755ff872a9d50285a3bb7008639d994f3210d836fd8fdc9eed921652222dfa",
        "content_sha256": "dd50df260e4af74f4d2f3cdb90e1f367fe9ccc836d12099f5d793c5bbefef8c2",
        "basis": "The dated SEC filing identifies HBI and original issuer CIK 1359841. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "HFC": {
        "cik": "0000048039",
        "quote_asof": "2021-06-03",
        "name": "HOLLYFRONTIER CORP",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/48039/000004803921000032/R1.htm",
        "sha256": "639da36703d2de078145aed7b049c9f7719bf59f4fc776e8d420dc4e5db427c2",
        "content_sha256": "2e9252f0e3ebe257d77e345528c11510a84adb52fd8e21b598519765c6fc2c52",
        "basis": "The dated SEC filing identifies HFC and original issuer CIK 48039. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "IPG": {
        "cik": "0000051644",
        "quote_asof": "2025-11-26",
        "name": "INTERPUBLIC GROUP OF COMPANIES, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/51644/000005164425000061/R1.htm",
        "sha256": "f3db42214d7014fb0589fe8c47f22be0dfb65a09b0b4a1ac807a36a67b57ad7b",
        "content_sha256": "b7a1a088b75d77a00fd628712f011da58069599b0529775757e8ec6c4b9a4df2",
        "basis": "The dated SEC filing identifies IPG and original issuer CIK 51644. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "JNPR": {
        "cik": "0001043604",
        "quote_asof": "2025-07-08",
        "name": "JUNIPER NETWORKS, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1043604/000104360425000065/R1.htm",
        "sha256": "28b7178660afef30a1a4d9cfc8624747ab7cd1d88706d8c0c983d98c378bd619",
        "content_sha256": "cc233aaed6d0a14d84c2cda913c234f3a1aa8ceabf237711b8be6113827cad2f",
        "basis": "The dated SEC filing identifies JNPR and original issuer CIK 1043604. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "JWN": {
        "cik": "0000072333",
        "quote_asof": "2020-06-19",
        "name": "NORDSTROM, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/72333/000007233320000142/R1.htm",
        "sha256": "69f3d4ae1ec285fc025279e3e9734305d273457f98dc210312c2725a7b49b618",
        "content_sha256": "b899b8c58e9530452ae85c95349141b0c118defbdd1994fb6eb08bddb8c9e538",
        "basis": "The dated SEC filing identifies JWN and original issuer CIK 72333. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "K": {
        "cik": "0000055067",
        "quote_asof": "2025-12-10",
        "name": "Kellanova",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/55067/000005506725000191/R1.htm",
        "sha256": "831d1bd9783799d3fc31652c54824a1aa29a8ba52819eaec9d6bb9550f6c2a21",
        "content_sha256": "9dca99141568fcfa0a1f827358adf0e48a623d6f2a6b906b4908fb510fa19b55",
        "basis": "The dated SEC filing identifies K and original issuer CIK 55067. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "KSU": {
        "cik": "0000054480",
        "quote_asof": "2021-12-13",
        "name": "KANSAS CITY SOUTHERN",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/54480/000005448021000220/R1.htm",
        "sha256": "9f9782be873b52240b32ef464fad78b307082b2ca47cdd0292caf89011105ed5",
        "content_sha256": "64eafc97c4d04d8d5d51b752c2385c097d38825cf61f1fb1475bf2e59ed2f4a0",
        "basis": "The dated SEC filing identifies KSU and original issuer CIK 54480. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification. The cover also lists preferred stock; the price/merger common-share path remains "
        "independently checked and no preferred-share EPS is inferred.",
    },
    "LEG": {
        "cik": "0000058492",
        "quote_asof": "2021-12-17",
        "name": "LEGGETT & PLATT, INC",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/58492/000005849221000005/R1.htm",
        "sha256": "6c5f90972569c398497afbb18f146ad224f645e2705acba858f5d905f1968814",
        "content_sha256": "a863f0081528122d19fe282229793f45800dc8d2114a0084c08052ae0b254bb9",
        "basis": "The dated SEC filing identifies LEG and original issuer CIK 58492. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "MRO": {
        "cik": "0000101778",
        "quote_asof": "2024-11-25",
        "name": "Marathon Oil Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/101778/000010177824000136/R1.htm",
        "sha256": "f868004f783f4d22f67e753ccf369ee7e67492b599f5831dba319c1d6911b9ad",
        "content_sha256": "64b78857fcd993dd3271d42541b497b75f34ec2c6fd20eaa328be2bd85bb055d",
        "basis": "The dated SEC filing identifies MRO and original issuer CIK 101778. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "MXIM": {
        "cik": "0000743316",
        "quote_asof": "2021-08-27",
        "name": "MAXIM INTEGRATED PRODUCTS, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/743316/000074331621000025/R1.htm",
        "sha256": "3a63a49b6b730da8c84ec6b8170923d12667f32f3c95ea220d39c02aa489d575",
        "content_sha256": "9ee679bb5224405dd0b1ce9497415dd497a514a62bfc96b16c1ae165ccb3ca1e",
        "basis": "The dated SEC filing identifies MXIM and original issuer CIK 743316. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "NBL": {
        "cik": "0000072207",
        "quote_asof": "2020-10-09",
        "name": "NOBLE ENERGY, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/72207/000007220720000041/R1.htm",
        "sha256": "984903a67e453983746af43d248708aeca9b21fc3fde0fb41d0afe5362e60d1d",
        "content_sha256": "2dc2b7fdd709815437b2cba8473d945f1ffc6809ca3619fd1288419d4f90a0f1",
        "basis": "The dated SEC filing identifies NBL and original issuer CIK 72207. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "NLSN": {
        "cik": "0001492633",
        "quote_asof": "2022-10-11",
        "name": "Nielsen Holdings plc",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1492633/000156459022026683/R1.htm",
        "sha256": "9b3d4c45b4d94954c63b83ca3ce8cd4b35c97a9c7fe31df7e2691ba73078f844",
        "content_sha256": "27564f53251fb5f624a199de765cc2dd9c2dd3e19ef459e91b66772d66603aca",
        "basis": "The dated SEC filing identifies NLSN and original issuer CIK 1492633. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "PBCT": {
        "cik": "0001378946",
        "quote_asof": "2022-04-01",
        "name": "People's United Financial, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1378946/000162828022004389/R1.htm",
        "sha256": "d0cf401fb5f13ca0a25e9c3e893a46d50fee8864d5b04616cc9a4977150944c0",
        "content_sha256": "2454325cb9184485fc3ed3e591a747b63f7eae74c7677d213a09c7f061d5f731",
        "basis": "The dated SEC filing identifies PBCT and original issuer CIK 1378946. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "PDCO": {
        "cik": "0000891024",
        "quote_asof": "2018-03-16",
        "name": "PATTERSON COMPANIES, INC.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/891024/000089102418000003/R1.htm",
        "sha256": "bad08451c2ef7635330e6adfb5c7d286d6f6a0a029b319ac868c6b9c6d592bcd",
        "content_sha256": "da4b88daa3525ef667681f3447c132a6347b9500e7d00b7b2a5e208db16535c9",
        "basis": "The dated SEC filing identifies PDCO and original issuer CIK 891024. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "PXD": {
        "cik": "0001038357",
        "quote_asof": "2024-05-07",
        "name": "PIONEER NATURAL RESOURCES CO",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1038357/000103835724000043/R1.htm",
        "sha256": "353c9c02ad76b4f33341d5debe06613a03bdb7191444d8e14374974ceccaf1e2",
        "content_sha256": "4755d014c0a39cc5a8b2f26be5e55660611e17fb3e3213e909bfe3a790e337f9",
        "basis": "The dated SEC filing identifies PXD and original issuer CIK 1038357. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "QRVO": {
        "cik": "0001604778",
        "quote_asof": "2024-12-20",
        "name": "Qorvo, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1604778/000160477824000082/R1.htm",
        "sha256": "f3b4858544d1c5594332df5d6ccf128908fbbd047aadbd753581e3526058984e",
        "content_sha256": "e0740a50745dd6e570280a9ab82ef4d223b60e26a8bebd3e82a6a8b462690f8e",
        "basis": "The dated SEC filing identifies QRVO and original issuer CIK 1604778. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "SCG": {
        "cik": "0000754737",
        "quote_asof": "2018-12-31",
        "name": "SCANA Corp",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/754737/000075473718000115/a12312017-10k.htm",
        "sha256": "abc0be7b09be2296350a1a0bdabdcf1c600290868d69faad2ebed1c1f483d5dc",
        "content_sha256": "d4249fde1769b4de0f1f8765493ecbb712246e92949b12080c6f7b1056130ac9",
        "basis": "The dated SEC filing identifies SCG and original issuer CIK 754737. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "SEE": {
        "cik": "0001012100",
        "quote_asof": "2023-12-15",
        "name": "SEALED AIR CORP/DE",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1012100/000162828023036460/R1.htm",
        "sha256": "7009c15a10d4aaa68ad2544c4501d83f0080bc78cfb96fa09d8a1004f2887afc",
        "content_sha256": "b31bb3190c3342c78943ca72de312f935e37b5f752b8bea27ef165e74207c550",
        "basis": "The dated SEC filing identifies SEE and original issuer CIK 1012100. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "SRCL": {
        "cik": "0000861878",
        "quote_asof": "2018-11-30",
        "name": "STERICYCLE INC",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/861878/000156459018026268/R1.htm",
        "sha256": "d396881f01844763aba1ea7cbf98b20ae952f38993bc84c54a129fe146aa2bd7",
        "content_sha256": "9d7c825711c51bfe23b24754dddd87746f0e388336540b074bd67af51aa30ca5",
        "basis": "The dated SEC filing identifies SRCL and original issuer CIK 861878. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "SWN": {
        "cik": "0000007332",
        "quote_asof": "2017-04-03",
        "name": "SOUTHWESTERN ENERGY CO",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/7332/000000733217000009/R1.htm",
        "sha256": "e5126a33c868f0278697927bc3a91c002e2ec2439fd7849ec718ba3b092881a2",
        "content_sha256": "40aa3d8fdc05bd16c1bee61b82914a628602dfa475725e93b049247c3a3f85d7",
        "basis": "The dated SEC filing identifies SWN and original issuer CIK 7332. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "TGNA": {
        "cik": "0000039899",
        "quote_asof": "2017-06-01",
        "name": "TEGNA INC",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/39899/000003989917000019/R1.htm",
        "sha256": "39cb59aca85e7b272d3ced2bb5aa57d2efb15f64593904b7af317d27dddcc167",
        "content_sha256": "d17ec31c9eeaada2f71ed49b22ebd2541ccbe23e53935c4c6b38cf85e9256926",
        "basis": "The dated SEC filing identifies TGNA and original issuer CIK 39899. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "TIF": {
        "cik": "0000098246",
        "quote_asof": "2021-01-06",
        "name": "Tiffany & Co.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/98246/000009824620000042/tif-2020131x10k.htm",
        "sha256": "89daaf15d984ca0c9052e33b884531389d9a31092f34e77852755bb7e71f3442",
        "content_sha256": "5476366736ab841abf67d440bd5303aa793a1966d94aa68cecc55439892bdd29",
        "basis": "The dated SEC filing identifies TIF and original issuer CIK 98246. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "TWTR": {
        "cik": "0001418091",
        "quote_asof": "2022-10-31",
        "name": "Twitter, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1418091/000141809122000147/R1.htm",
        "sha256": "9b17587f0c2e27959c47298ceebd249e38ee5344a479f67be8ca800c965184f5",
        "content_sha256": "06f42424ec34b244d8ff304d4b88e37d0005d4315da9565c6a157baa996d1c73",
        "basis": "The dated SEC filing identifies TWTR and original issuer CIK 1418091. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "VAR": {
        "cik": "0000203527",
        "quote_asof": "2021-04-19",
        "name": "VARIAN MEDICAL SYSTEMS, INC.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/203527/000020352721000010/R1.htm",
        "sha256": "39c03ca304f69316173a976ebf58b20d3a4b26258c14e5a598957203c8b2a7e2",
        "content_sha256": "012ba760ddb5e1004ab0c8a3858e818eef9286ca68aedd9f66c234f2522d6fdd",
        "basis": "The dated SEC filing identifies VAR and original issuer CIK 203527. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "WBD": {
        "cik": "0001437107",
        "quote_asof": "2026-10-05",
        "name": "Warner Bros. Discovery, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1437107/000143710726000075/R1.htm",
        "sha256": "269b768c6cce3fb90e0893071d45afb288f32dde912cb4bef0de96c99f5fd95a",
        "content_sha256": "3f16cd5a57e0ecf21b697cebe087b69f8f2d7e888568ccbee270316bc1333f85",
        "basis": "The dated SEC filing identifies WBD and original issuer CIK 1437107. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "XEC": {
        "cik": "0001168054",
        "quote_asof": "2020-03-02",
        "name": "CIMAREX ENERGY CO",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1168054/000116805420000004/R1.htm",
        "sha256": "176800c831f640f2ccff750cd9511a8c3130170a7fc3cc5a32309fde071504b7",
        "content_sha256": "36d9f861ca6764c497ca80f69a994cba562db015d981693d2ff6483ab67c0dd3",
        "basis": "The dated SEC filing identifies XEC and original issuer CIK 1168054. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "XL": {
        "cik": "0000875159",
        "quote_asof": "2018-09-11",
        "name": "XL Group",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/875159/000087515918000015/xlgroup-10xk_2017.htm",
        "sha256": "b246dbec95c32ad474f965f4aadbe5d7da4c3babb9f8b8e21fac704d2189b575",
        "content_sha256": "7b6c3964b73e53636cb630fe82b8d3779508fa78d769343b08a39f3d2aef3511",
        "basis": "The dated SEC filing identifies XL and original issuer CIK 875159. Annual financial values retain their own "
        "accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification. Item 5 identifies the old XL insurer common shares, rather than the unrelated later XL Fleet "
        "ticker.",
    },
    "XLNX": {
        "cik": "0000743988",
        "quote_asof": "2022-02-14",
        "name": "XILINX, INC",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/743988/000074398822000008/R1.htm",
        "sha256": "927dc02bb2ef10ac1e931cf8a2bef622d3c21244bfb9060d7cd674aa36b48678",
        "content_sha256": "8eaa47976a2b231c56b26667ec6d80a932c3ea602d4806cb98b002fdbc70ee8c",
        "basis": "The dated SEC filing identifies XLNX and original issuer CIK 743988. Annual financial values retain their "
        "own accession and availability dates; this mapping is issuer evidence, not exhaustive EPS share-class "
        "certification.",
    },
    "ANSS": {
        "cik": "0001013462",
        "quote_asof": "2025-07-17",
        "name": "ANSYS, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1013462/000114036125026141/ef20052066_8k.htm",
        "sha256": "325ac76a936ba8f6dbc02d48316226f89b6ce7719eaad9bbe3453029e6b95f8c",
        "content_sha256": "426bf69a6bb880823207f8d84fc5337d2ef697122d58b87f5e2805a3997c4ee2",
        "basis": "The completed-merger filing identifies the original ANSYS common shares and their Nasdaq listing. Its CIK 1013462 financial history belongs to ANSS, independently of Synopsys's financial statements.",
    },
    "CTLT": {
        "cik": "0001596783",
        "quote_asof": "2024-12-20",
        "name": "Catalent, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1596783/000119312524280922/d902883d8k.htm",
        "sha256": "af8020f90073a07d5699ffc7c5e9109bc2394ab9f10568d72e65caecf77bc65e",
        "content_sha256": "b37d91b7e7c32f8de364489ca542efeab9c53fc3cbc1a545fc6aa67710b91425",
        "basis": "The completed-merger filing identifies CTLT common stock on NYSE and the original Catalent issuer, CIK 1596783. Historical financial statements retain their own accession and availability dates.",
    },
    "HES": {
        "cik": "0000004447",
        "quote_asof": "2025-07-22",
        "name": "Hess Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/4447/000095014225001950/eh250651090_8k.htm",
        "sha256": "be047631e330ad26fcbe0ba5f20c99eb727963dce26efb59675913774c3dd7d9",
        "content_sha256": "f0bdbe694d6db9d01d7c86d2d85de863cb9fc683c2c90434889b106b53bd79c6",
        "basis": "The completed-merger filing identifies HES common stock on NYSE and Hess's original CIK 4447. The mapped financials belong to Hess rather than the Chevron stock received at conversion.",
    },
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
    "AET": {
        "cik": "0001122304",
        "quote_asof": "2018-11-28",
        "name": "Aetna Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1122304/000112230418000178/form8-k.htm",
        "sha256": "4c66a85189531e10d787be5f7866ef0d0ad0c863bf9dc13896724a3e712219df",
        "content_sha256": "f59d6431b2e438421c585f754634bc7e4b70c47b0df7288001bc44e78b990fba",
        "basis": "The filed SEC document under CIK 1122304 identifies Aetna Inc. and its NYSE-listed common shares; it is matched to the 2018-11-28 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "BCR": {
        "cik": "0000009892",
        "quote_asof": "2017-12-28",
        "name": "C. R. Bard, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/9892/000119312517383532/d489045d8k.htm",
        "sha256": "1efcf9495801983256fa85f129d67bad9fdf5fd0c2abb4892150b030f1709436",
        "content_sha256": "28f4eb62a90e16a4aa7312a040d14e8539abf7d87a0bdc1293070ee7de10e7ad",
        "basis": "The filed SEC document under CIK 9892 identifies C. R. Bard, Inc. and its NYSE-listed common shares; it is matched to the 2017-12-28 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "CA": {
        "cik": "0000356028",
        "quote_asof": "2018-11-05",
        "name": "CA, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/356028/000119312518317918/d631849d8k.htm",
        "sha256": "3c1de8b0981e624db5ea655bed5036f8b71b8c96d027933d58b29c18643d07d8",
        "content_sha256": "155cbed6fa7727ed66d48198519bbe81aeb37df17af7f2625084c871a605228f",
        "basis": "The filed SEC document under CIK 356028 identifies CA, Inc. and its NASDAQ-listed common shares; it is matched to the 2018-11-05 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "COL": {
        "cik": "0001137411",
        "quote_asof": "2018-11-26",
        "name": "Rockwell Collins, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1137411/000119312518334170/d598640d8k.htm",
        "sha256": "59db5397224113fc20d77c321558d3b257741d630138d5da70ef331499a40927",
        "content_sha256": "f3af79583ff041e7b3fa40d5c158462b608f7e0887639e9b8e92bfa6f1bea0b3",
        "basis": "The filed SEC document under CIK 1137411 identifies Rockwell Collins, Inc. and its NYSE-listed common shares; it is matched to the 2018-11-26 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "CSRA": {
        "cik": "0001646383",
        "quote_asof": "2018-04-03",
        "name": "CSRA Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1646383/000119312518106369/d562306d8k.htm",
        "sha256": "b932e411a7e78c725490322d8b082760b7096c0a77dffc4cea94c2867f5fac38",
        "content_sha256": "b0cfb4a3ba1fb33ab923aca9305fef38585a5fc601e66efdcaafeaede10c7d52",
        "basis": "The filed SEC document under CIK 1646383 identifies CSRA Inc. and its NYSE-listed common shares; it is matched to the 2018-04-03 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "HAR": {
        "cik": "0000800459",
        "quote_asof": "2017-03-10",
        "name": "Harman International Industries, Incorporated",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/800459/000119312517078968/d184457d8k.htm",
        "sha256": "3813d9669b28760710f0a0e2bd3bd593ca3f2a1b8b30fb17171f2944a23d3148",
        "content_sha256": "7f1dfb7684d6f84fc73ee237566cfe578c658b5a6aec593aa8964074292d9f8f",
        "basis": "The filed SEC document under CIK 800459 identifies Harman International Industries, Incorporated and its NYSE-listed common shares; it is matched to the 2017-03-10 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "LLL": {
        "cik": "0001039101",
        "quote_asof": "2019-06-28",
        "name": "L3 Technologies, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1039101/000114036119012103/form8k.htm",
        "sha256": "b421229d063ebf2ee9117769830b92bb2aff2ce116af470a7ada50dbc7f98a2a",
        "content_sha256": "6dc009590f10d7f61c01d9b98cf6a1e89a7410ad022b4e00f0db96ee474a4d09",
        "basis": "The filed SEC document under CIK 1039101 identifies L3 Technologies, Inc. and its NYSE-listed common shares; it is matched to the 2019-06-28 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "LLTC": {
        "cik": "0000791907",
        "quote_asof": "2017-03-10",
        "name": "Linear Technology Corporation",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/791907/000119312517078946/d340243d8k.htm",
        "sha256": "7b67f8a402d296638f6af2dc7f3e8c683539ae62c9bec667f48b67735e39072d",
        "content_sha256": "e1385ae908fc7d8cbea366f47654eaaffd2ba9d4d8e6e2b5e63a76560fa0e472",
        "basis": "The filed SEC document under CIK 791907 identifies Linear Technology Corporation and its NASDAQ-listed common shares; it is matched to the 2017-03-10 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "MJN": {
        "cik": "0001452575",
        "quote_asof": "2017-06-14",
        "name": "Mead Johnson Nutrition Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1452575/000110465917039502/a17-15238_18k.htm",
        "sha256": "9011ee9f7c9b8f6c2d873dd909ed5346e37a22fdd1a1083f3d6e27dcba5eb233",
        "content_sha256": "d3639e9dcf9470c0349f9d265563ee0bbd75fe88b3f76349ca0b04c09240a234",
        "basis": "The filed SEC document under CIK 1452575 identifies Mead Johnson Nutrition Company and its NYSE-listed common shares; it is matched to the 2017-06-14 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "MON": {
        "cik": "0001110783",
        "quote_asof": "2018-06-06",
        "name": "Monsanto Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1110783/000119312518188226/d587681d8k.htm",
        "sha256": "2f73d523b902d45e87ba50339130bc7a9f3865e147f07f0c2ebcba7c6e6c231a",
        "content_sha256": "38fb66e3feb24e9ef0c8db1eab3982f2e8c83962be9d2a7bffe9e01e70a4d249",
        "basis": "The filed SEC document under CIK 1110783 identifies Monsanto Company and its NYSE-listed common shares; it is matched to the 2018-06-06 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "PX": {
        "cik": "0000884905",
        "quote_asof": "2018-10-30",
        "name": "Praxair, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/884905/000119312518313154/d646523d8k.htm",
        "sha256": "afda75b2157c34bdf51757085cc3d03c5a56deb671e08f6e59f56785b9a58ee1",
        "content_sha256": "04a205d3c510f74e4317b690b98b662ab7f609dfcc332480a9d57c565d3271ca",
        "basis": "The filed SEC document under CIK 884905 identifies Praxair, Inc. and its NYSE-listed common shares; it is matched to the 2018-10-30 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "RAI": {
        "cik": "0001275283",
        "quote_asof": "2017-07-24",
        "name": "Reynolds American Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1275283/000119312517235158/d397089d8k.htm",
        "sha256": "7f7a46c262b61cfdd1ebde40b26e1cf1e488bd0ddb3cdcc951e44b0581332818",
        "content_sha256": "9a3fcf84ebad1bad89d140ba5458ed46d4eeea562217df1a8a8e77d887c9c94c",
        "basis": "The filed SEC document under CIK 1275283 identifies Reynolds American Inc. and its NYSE-listed common shares; it is matched to the 2017-07-24 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "RHT": {
        "cik": "0001087423",
        "quote_asof": "2019-07-12",
        "name": "Red Hat, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1087423/000095014219001516/eh1900894_8k-rh.htm",
        "sha256": "b269a28bea54daa3d7990e96cb82e7c5a257ae7480b29ebfc31f2464142775ec",
        "content_sha256": "c72faf2591ab4c67266ae969510c5a0108f8eaded2baa2b244fbae951d11bf48",
        "basis": "The filed SEC document under CIK 1087423 identifies Red Hat, Inc. and its NYSE-listed common shares; it is matched to the 2019-07-12 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "RTN": {
        "cik": "0001047122",
        "quote_asof": "2020-04-03",
        "name": "Raytheon Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1047122/000119312520097237/d827106d8k.htm",
        "sha256": "077b9f0350043ea08acd77e7207d3095f3f97fcd875e3d7b22f24397684d4537",
        "content_sha256": "74735d2c7c9d3f34b54bda7dde420982b85955e1f4cad12c98f981cc74c24c2d",
        "basis": "The filed SEC document under CIK 1047122 identifies Raytheon Company and its NYSE-listed common shares; it is matched to the 2020-04-03 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "SE": {
        "cik": "0001373835",
        "quote_asof": "2017-02-24",
        "name": "Spectra Energy Corp",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1373835/000119312517057856/d338638d8k.htm",
        "sha256": "618f8d15d1ca93fee9f18737ef5b47cf43e1aad64acb6a5d6821fc1c7f6c5a9b",
        "content_sha256": "f28d8ae207c3d7ee80c1e3412a6d38ab2c8455b79717742d49667fadad62d797",
        "basis": "The filed SEC document under CIK 1373835 identifies Spectra Energy Corp and its NYSE-listed common shares; it is matched to the 2017-02-24 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "SNI": {
        "cik": "0001430602",
        "quote_asof": "2018-03-06",
        "name": "Scripps Networks Interactive, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1430602/000119312518072063/d545990d8k.htm",
        "sha256": "2d3a2f8f7f055a1111c91bf745bd567e2c559b2cf956ca8a0344dc29b934c6d4",
        "content_sha256": "7fcb5a6093dc9940f27c36f36480384ec748154bb687f8f47f13cf0b08eeefd7",
        "basis": "The filed SEC document under CIK 1430602 identifies Scripps Networks Interactive, Inc. and its NASDAQ-listed common shares; it is matched to the 2018-03-06 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "SPLS": {
        "cik": "0000791519",
        "quote_asof": "2017-09-12",
        "name": "Staples, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/791519/000110465917056725/a17-21547_18k.htm",
        "sha256": "fed8ebc540d540b55afbecb527d09a376ab4b1a0f50f9b4b2e25370ea41ef74b",
        "content_sha256": "317a4785836662126605543fa3e5b5fb3fd1421cacba0c26e90c8ab01aa822ce",
        "basis": "The filed SEC document under CIK 791519 identifies Staples, Inc. and its NASDAQ-listed common shares; it is matched to the 2017-09-12 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "STI": {
        "cik": "0000750556",
        "quote_asof": "2019-12-06",
        "name": "SunTrust Banks, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/750556/000119312519308629/d808889d8k.htm",
        "sha256": "4073356f1122f564efafe37ab3b69ab2fc7f9ffbace55026448f7ca5860090c3",
        "content_sha256": "1eca07d870a93575aa5b3a2e46f9751e7f57e329b7c4c5a2bcc1a18ce2ad93d2",
        "basis": "The filed SEC document under CIK 750556 identifies SunTrust Banks, Inc. and its NYSE-listed common shares; it is matched to the 2019-12-06 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "STJ": {
        "cik": "0000203077",
        "quote_asof": "2017-01-04",
        "name": "St. Jude Medical, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/203077/000110465917000936/a16-23886_18k.htm",
        "sha256": "a88b28471db8f4856c006fefe2b39cbe3689ecdf927f2757d73791f6bcab45b6",
        "content_sha256": "9cf7ec1e9dbae06a27fa2b9345c9cbee55e58039aacebed3a6667ac523356d57",
        "basis": "The filed SEC document under CIK 203077 identifies St. Jude Medical, Inc. and its NYSE-listed common shares; it is matched to the 2017-01-04 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "TSS": {
        "cik": "0000721683",
        "quote_asof": "2019-09-20",
        "name": "Total System Services, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/721683/000119312519250774/d803104d8k.htm",
        "sha256": "14d288bbae061bc114877a9fa5d859c3147d9c30eba31b6aff97f6a6c3b2ccc7",
        "content_sha256": "e5eba9e78d12d71c34a6efc9934e651bb99a261deb7a07ce7c982c5d993932ce",
        "basis": "The filed SEC document under CIK 721683 identifies Total System Services, Inc. and its NYSE-listed common shares; it is matched to the 2019-09-20 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "TWX": {
        "cik": "0001105705",
        "quote_asof": "2018-06-14",
        "name": "Time Warner Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1105705/000095015718000694/form8-k.htm",
        "sha256": "4a3e0738f3f9876b56b8720b46b39f32e3bf4e1c495e25d4562b92160d25f060",
        "content_sha256": "0a1e0210253d111e84c744449a5fdcb5bc58de7ecef4456fd36b5bcaa58ca28c",
        "basis": "The filed SEC document under CIK 1105705 identifies Time Warner Inc. and its NYSE-listed common shares; it is matched to the 2018-06-14 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "VIAB": {
        "cik": "0001339947",
        "quote_asof": "2019-12-04",
        "name": "Viacom Inc. (Class B)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1339947/000119312519306335/d833313d8k.htm",
        "sha256": "fe544fb759dd9bc1b45b318b9366556a69519141134f144b42ab118a6c6616bc",
        "content_sha256": "3491055ffaa08c057806168689c3ecfd6c88ce4eb030cb126fbd87afe7443a89",
        "basis": "The filed SEC document under CIK 1339947 identifies Viacom Inc. (Class B) and its NASDAQ-listed common shares; it is matched to the 2019-12-04 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "WCG": {
        "cik": "0001279363",
        "quote_asof": "2020-01-27",
        "name": "WellCare Health Plans, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1279363/000114036120001340/form8k.htm",
        "sha256": "e4dddbcc22f777cb7003df110c09df7e4b3267db8bdb580736975fbaaafa9f2d",
        "content_sha256": "fd6c78bbbdd89982d60b4b299f7b57a3f48048635a2ca903dfa88bb6cd5c3f17",
        "basis": "The filed SEC document under CIK 1279363 identifies WellCare Health Plans, Inc. and its NYSE-listed common shares; it is matched to the 2020-01-27 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "WFM": {
        "cik": "0000865436",
        "quote_asof": "2017-08-25",
        "name": "Whole Foods Market, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/865436/000114420417045261/v474128_8k.htm",
        "sha256": "875c1647b436f8ad817bd9e21e436a2c82d5e9ee8c8f9a55a10cb95180ca8a91",
        "content_sha256": "46ddea312d3295c980f397ecce09de79709618ce6cfa380755725fdbd3ab42f5",
        "basis": "The filed SEC document under CIK 865436 identifies Whole Foods Market, Inc. and its NASDAQ-listed common shares; it is matched to the 2017-08-25 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "ANDV": {
        "cik": "0000050104",
        "quote_asof": "2018-09-28",
        "name": "Andeavor",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/50104/000119312518289750/d632974d8k.htm",
        "sha256": "274feee5ed1f947be7b30bb973509f160943f76f35b45d65290faa06c5afd4dc",
        "content_sha256": "6d815f5b775f060a1ae254d2d403bb5910a3478977b4eceeb8d2990cdfd4cc9d",
        "basis": "The filed SEC document under CIK 50104 identifies Andeavor and its NYSE-listed common shares; it is matched to the 2018-09-28 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "MYL": {
        "cik": "0001623613",
        "quote_asof": "2020-11-16",
        "name": "Mylan N.V.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1623613/000119312520298224/d91045d8k.htm",
        "sha256": "58ccd6f75f50d8b631d37df814e7f9246a19835d3418f8c28b3665429695f7ee",
        "content_sha256": "25a13f3f103ceaa357017075f12ad3aacf32f3101a66e56c163c5cf2db138acb",
        "basis": "The filed SEC document under CIK 1623613 identifies Mylan N.V. and its NASDAQ-listed common shares; it is matched to the 2020-11-16 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "NFX": {
        "cik": "0000912750",
        "quote_asof": "2019-02-14",
        "name": "Newfield Exploration Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/912750/000119312519044446/d710595d8k.htm",
        "sha256": "f5e1989dd8781dfd93193e062cce1f07d208e9eb1f3f8134756c36744ca5019d",
        "content_sha256": "dfa532579c981e1b68d6d29d757d11fdf5ec6e1883dd963d4d4711378ad1845b",
        "basis": "The filed SEC document under CIK 912750 identifies Newfield Exploration Company and its NYSE-listed common shares; it is matched to the 2019-02-14 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "DD.OLD": {
        "cik": "0000030554",
        "quote_asof": "2017-08-31",
        "name": "E. I. du Pont de Nemours and Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312517274834/d426905d8k12b.htm",
        "sha256": "cba0b689235d5e6c3d703b56c9309ddb5c87bd3bd0a1757bbf54e6506922efc8",
        "content_sha256": "8015f450730ee143b67f495d5fdac8a459dfe49e4ae0c32e4ffcbbe96faff804",
        "basis": "The filed SEC document under CIK 30554 identifies E. I. du Pont de Nemours and Company and its NYSE-listed common shares; it is matched to the 2017-08-31 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "DOW.OLD": {
        "cik": "0000029915",
        "quote_asof": "2017-08-31",
        "name": "The Dow Chemical Company",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1666700/000119312517274834/d426905d8k12b.htm",
        "sha256": "cba0b689235d5e6c3d703b56c9309ddb5c87bd3bd0a1757bbf54e6506922efc8",
        "content_sha256": "8015f450730ee143b67f495d5fdac8a459dfe49e4ae0c32e4ffcbbe96faff804",
        "basis": "The filed SEC document under CIK 29915 identifies The Dow Chemical Company and its NYSE-listed common shares; it is matched to the 2017-08-31 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "DISCA": {
        "cik": "0001437107",
        "quote_asof": "2022-04-08",
        "name": "Discovery, Inc. (Series A)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1437107/000119312522103051/d328161d8k.htm",
        "sha256": "a9846069d83fda87cdacde8066fd0f1494fa16b4f8dacea1533515bdaa77be42",
        "content_sha256": "00606b52e6a128d58b79bc1ae8fb09ad8e1423c915bb2eab6f53c818ecd50c0d",
        "basis": "The filed SEC document under CIK 1437107 identifies Discovery, Inc. (Series A) and its NASDAQ-listed common shares; it is matched to the 2022-04-08 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "CELG": {
        "cik": "0000816284",
        "quote_asof": "2019-11-20",
        "name": "Celgene Corporation",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/816284/000110465919065939/tm1923405d1_8k.htm",
        "sha256": "9ba2ef9e90f791494166176f668016ebbde569745fa5f502df6d620b2c20183a",
        "content_sha256": "9ba2ef9e90f791494166176f668016ebbde569745fa5f502df6d620b2c20183a",
        "basis": "The filed SEC document under CIK 816284 identifies Celgene Corporation and its NASDAQ-listed common shares; it is matched to the 2019-11-20 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "ABMD": {
        "cik": "0000815094",
        "quote_asof": "2022-12-21",
        "name": "ABIOMED, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/815094/000119312522311074/d353287d8k.htm",
        "sha256": "2dd2dadd6e5f43b8f44c3ff17dc3fd79362c53293156c0e4951129ae9bbc5834",
        "content_sha256": "4cceb151cbeb2f3c0368e996a23dcc1cb658b2bc730dd33466ca862bc2845ab4",
        "basis": "The filed SEC document under CIK 815094 identifies ABIOMED, Inc. and its NASDAQ-listed common shares; it is matched to the 2022-12-21 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "HOLX": {
        "cik": "0000859737",
        "quote_asof": "2026-04-08",
        "name": "Hologic, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/859737/000119312526144632/d135035d8k.htm",
        "sha256": "2ef6a9c080d0db18e42c59136d881195d75ee85a3325572959994c3b1b77b74f",
        "content_sha256": "7c93646c7a4c2542c47b7f055de66a5519722165317db30680e1b140adf9c615",
        "basis": "The filed SEC document under CIK 859737 identifies Hologic, Inc. and its NASDAQ-listed common shares; it is matched to the 2026-04-08 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "WBA": {
        "cik": "0001618921",
        "quote_asof": "2025-08-27",
        "name": "Walgreens Boots Alliance, Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1618921/000119312525190603/d87240d8k.htm",
        "sha256": "5167a8981ea0f558b7759e773fecc0efcd5c2ff4fa877e52e51a3162a40b433a",
        "content_sha256": "2f831bf3a7deebf7f2f22a793dd31bb4942221f2832ca1c33a105ba2b5547354",
        "basis": "The filed SEC document under CIK 1618921 identifies Walgreens Boots Alliance, Inc. and its NASDAQ-listed common shares; it is matched to the 2025-08-27 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "EA": {
        "cik": "0000712515",
        "quote_asof": "2026-08-04",
        "name": "Electronic Arts Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/712515/000114036126031157/ef20079099_8k.htm",
        "sha256": "9ed4a70a84766656e40aaee5c8b3846519e90d29c445af8c41172c9a0728188e",
        "content_sha256": "ff4f92362438f24b705e4c094b79eff8884c0f925c8977c5c9d2d933f7e3d531",
        "basis": "The filed SEC document under CIK 712515 identifies Electronic Arts Inc. and its NASDAQ-listed common shares; it is matched to the 2026-08-04 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "GGP": {
        "cik": "0001496048",
        "quote_asof": "2018-08-27",
        "name": "GGP Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1496048/000119312518260735/d614210d8k.htm",
        "sha256": "f15eb93ed12de1c608257055059a2e2f84d6bc6956299d81930a808db3ca0a06",
        "content_sha256": "04e962b9198fa7f214c4845f6e66016203f2885674b115a485dd030295c7f77e",
        "basis": "The filed SEC document under CIK 1496048 identifies GGP Inc. and its NYSE-listed common shares; it is matched to the 2018-08-27 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "APC": {
        "cik": "0000773910",
        "quote_asof": "2019-08-08",
        "name": "Anadarko Petroleum Corporation",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/773910/000095015719000863/form8k.htm",
        "sha256": "d0114241c9bbe7f35a40437b9244152ad268d41287d616da321a01b8e4064ca8",
        "content_sha256": "48a7960efd5394a6a99b6223ae255c69c1c6159dc5f5931e1d7b00a66515ca59",
        "basis": "The filed SEC document under CIK 773910 identifies Anadarko Petroleum Corporation and its NYSE-listed common shares; it is matched to the 2019-08-08 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "FOXA.OLD": {
        "cik": "0001308161",
        "quote_asof": "2019-03-18",
        "name": "Twenty-First Century Fox, Inc. (Class A)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1308161/000119312519079034/d721340d8k.htm",
        "sha256": "730f754897cbef001a2aa880f6c4d9f89eb8e9fad21a3a6c124d0ce9a86610a9",
        "content_sha256": "1d4f1c52c717d0845982fcb2f7afc8f86692bdd47044f50d9ba7d4d6bdcb60ae",
        "basis": "The filed SEC document under CIK 1308161 identifies Twenty-First Century Fox, Inc. (Class A) and its NASDAQ-listed common shares; it is matched to the 2019-03-18 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "FOX.OLD": {
        "cik": "0001308161",
        "quote_asof": "2019-03-18",
        "name": "Twenty-First Century Fox, Inc. (Class B)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1308161/000119312519079034/d721340d8k.htm",
        "sha256": "730f754897cbef001a2aa880f6c4d9f89eb8e9fad21a3a6c124d0ce9a86610a9",
        "content_sha256": "1d4f1c52c717d0845982fcb2f7afc8f86692bdd47044f50d9ba7d4d6bdcb60ae",
        "basis": "The filed SEC document under CIK 1308161 identifies Twenty-First Century Fox, Inc. (Class B) and its NASDAQ-listed common shares; it is matched to the 2019-03-18 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "SIVB": {
        "cik": "0000719739",
        "quote_asof": "2023-03-14",
        "name": "SVB Financial Group",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/719739/000119312523073665/d485308d8k.htm",
        "sha256": "10e9adcdf01d537d92933bee043dca96c75e1ac361621caa3b152b2d2e2495e0",
        "content_sha256": "69f3b20dfab4c9c43641a3c38a99f288129665af40e5ae3e6993ec36ccf4fcef",
        "basis": "The filed SEC document under CIK 719739 identifies SVB Financial Group and its NASDAQ-listed common shares; it is matched to the 2023-03-14 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "LVLT": {
        "cik": "0000794323",
        "quote_asof": "2017-10-12",
        "name": "Level 3 Communications, Inc.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/794323/000119312517329395/d459582d8k.htm",
        "sha256": "c76f65545950fcc2965e9a8c81ac6da75d3d4220b1684f9acf72745d718538fe",
        "content_sha256": "a3ed0c24e0465c23e697271723f53b7eea0e8b3f7abcd15f344ec35859e20222",
        "basis": "The filed SEC document under CIK 794323 identifies Level 3 Communications, Inc. and its NYSE-listed common shares; it is matched to the 2017-10-12 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "CBS": {
        "cik": "0000813828",
        "quote_asof": "2019-12-04",
        "name": "CBS Corporation (Class B)",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/813828/000081382819000006/cbs_10k-123118.htm",
        "sha256": "46f63fa2389febcc37477958237566538d714ba1c206cb3bc405d64538ebf31d",
        "content_sha256": "00bcab9a00e907a7607711314fcb641b948bb449e0cd2f1f483ea8ae4237a21d",
        "basis": "The filed SEC document under CIK 813828 identifies CBS Corporation (Class B) and its NYSE-listed common shares; it is matched to the 2019-12-04 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "PARA": {
        "cik": "0000813828",
        "quote_asof": "2025-08-07",
        "name": "Paramount Global (Class B)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/813828/000081382825000005/para-20241231.htm",
        "sha256": "ebfeca85ab8736e6d7cfa926c19f852da2a7cf32df947bf730170354653d1f15",
        "content_sha256": "5e1a509968b99ce829546d0eabeb6e663e711788577901f83d0cbaa53cf6a44a",
        "basis": "The filed SEC document under CIK 813828 identifies Paramount Global (Class B) and its NASDAQ-listed common shares; it is matched to the 2025-08-07 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "CZR": {
        "cik": "0001590895",
        "quote_asof": "2025-09-19",
        "name": "Caesars Entertainment, Inc. (formerly Eldorado Resorts)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1590895/000159089525000068/czr-20241231.htm",
        "sha256": "75b45a202b95bf6370f8b8f31a4cf70bfff918eadec96955b1de428ce5989dd7",
        "content_sha256": "935adf140fe749d605c17be7b933100e2da5ca87852dff5e9e46a9559aea4c88",
        "basis": "The filed SEC document under CIK 1590895 identifies Caesars Entertainment, Inc. (formerly Eldorado Resorts) and its NASDAQ-listed common shares; it is matched to the 2025-09-19 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "MTCH": {
        "cik": "0000891103",
        "quote_asof": "2026-03-20",
        "name": "Match Group, Inc. (formerly IAC/InterActiveCorp)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/891103/000089110326000025/mtch-20251231.htm",
        "sha256": "e7b8c72dbbb7e91a459916c1619627183b4484254e1d0b042ccf9ce9ce103a2c",
        "content_sha256": "98eef2754883ccd6341c818fec69a39e88b3e464892861d0c26db261755a7e34",
        "basis": "The filed SEC document under CIK 891103 identifies Match Group, Inc. (formerly IAC/InterActiveCorp) and its NASDAQ-listed common shares; it is matched to the 2026-03-20 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "INFO": {
        "cik": "0001598014",
        "quote_asof": "2022-03-01",
        "name": "IHS Markit Ltd.",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1598014/000119312522056012/d315930d8k.htm",
        "sha256": "604a42cb46a7c858fe27cd548b0e40510cb9454e39e641be01e0c3c25905aa77",
        "content_sha256": "3bc6bead9c71443eed470b248e0a8d706855edf815a385445eee7ddd59aa9453",
        "basis": "The filed SEC document under CIK 1598014 identifies IHS Markit Ltd. and its NYSE-listed common shares; it is matched to the 2022-03-01 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "SOLS": {
        "cik": "0002064953",
        # Still listed: the latest quote vintage moves with each Update. The
        # proof applies from this vintage onward only while the directory
        # holds exactly these two Solstice records (when-issued and regular).
        "quote_asof": "2026-11-09",
        "through_latest": True,
        "listing_ids": [
            "8dcb1587-cdd4-472a-9424-850f362a66fb",
            "b494b9bc-b781-4437-91d9-c2c57c29b334",
        ],
        "name": "Solstice Advanced Materials Inc.",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/2064953/000206495326000008/sols-20251231.htm",
        "sha256": "c9a68eaec40df49ae11c09ae38c769e47ffd8c0ac603ae90978a555babc772b1",
        "content_sha256": "836e1d89036a235092348e33e5c54931242610efcb38713eb2636fcd57eac73d",
        "basis": "The filed SEC document under CIK 2064953 identifies Solstice Advanced Materials Inc. and its NASDAQ-listed common shares. The listing directory holds two Solstice common-stock records with the same name and exchange; the proof applies to quote vintages from 2026-11-09 while exactly those two records exist. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "BHGE": {
        "cik": "0001701605",
        "quote_asof": "2019-10-17",
        "name": "Baker Hughes, a GE company (Class A)",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1701605/000119312517220852/d343521d8k12b.htm",
        "sha256": "c43174ab0d354da56540719c0f9951841c0a2fcfc67fc6c7ae4202e5de215f90",
        "content_sha256": "4086eb52e0703c72d3b7cf05fa291ed01bf4eceffddba8724209c8a9a9e615d0",
        "basis": "The filed SEC document under CIK 1701605 identifies Baker Hughes, a GE company (Class A) and its NYSE-listed common shares; it is matched to the 2019-10-17 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "AABA": {
        "cik": "0001011006",
        "quote_asof": "2017-06-16",
        "name": "Yahoo! Inc. (renamed Altaba Inc.)",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1011006/000119312517206955/d389206d8k.htm",
        "sha256": "08fd1b91b860ce2aa748cd8c9160a8872ae9add985f45d7fc16672b2be5ed442",
        "content_sha256": "f2344ced6fbffcfd2b61559bc4af7da45c36c5ad9507117d01abc76b6347f91e",
        "basis": "The filed SEC document under CIK 1011006 identifies Yahoo! Inc. (renamed Altaba Inc.) and its NASDAQ-listed common shares; it is matched to the 2017-06-16 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "DAY": {
        "cik": "0001725057",
        "quote_asof": "2026-02-06",
        "name": "Dayforce, Inc. (formerly Ceridian HCM)",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1725057/000114036126003628/ef20064744_8k.htm",
        "sha256": "a73b232d0fa5c382b5a0ca75a141e0a9a4b066e46254783b1f67fe6cd98aaa58",
        "content_sha256": "02c20dcd93ee8f7faf8273f2aec5911f1a068808e0f0be4f6d496c689c0c04c7",
        "basis": "The filed SEC document under CIK 1725057 identifies Dayforce, Inc. (formerly Ceridian HCM) and its NYSE-listed common shares; it is matched to the 2026-02-06 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "WYND": {
        "cik": "0001361658",
        "quote_asof": "2018-05-30",
        "name": "Wyndham Worldwide Corporation (renamed Wyndham Destinations)",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/1361658/000110465918037818/a18-14563_28k.htm",
        "sha256": "350d779a763b94c2f05cc8c24cd0e505e7ffdc957950d73d50b1c66337df1654",
        "content_sha256": "3abbe937ced9beda61235278d045470460db0f42f97c6bb79e60a31c4e694dd9",
        "basis": "The filed SEC document under CIK 1361658 identifies Wyndham Worldwide Corporation (renamed Wyndham Destinations) and its NYSE-listed common shares; it is matched to the 2018-05-30 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "NAVI": {
        "cik": "0001593538",
        "quote_asof": "2018-06-04",
        "name": "Navient Corporation",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/1593538/000156459018003273/navi-10k_20171231.htm",
        "sha256": "055502e00397fca0c32e5cc5382105d67978f6a895bf919c632fc919e4a57c89",
        "content_sha256": "db5a3c5320ca5000088f4ee06e9983080d0d5d7a6a56899638c1836651dab10b",
        "basis": "The filed SEC document under CIK 1593538 identifies Navient Corporation and its NASDAQ-listed common shares; it is matched to the 2018-06-04 provider quote vintage. Annual financial values keep their own accession and filing dates; later filers reusing the ticker are not mapped.",
    },
    "FRC": {
        "cik": None,
        "quote_asof": "2023-05-03",
        "name": "First Republic Bank",
        "exchange": "NYSE",
        "url": "https://www.sec.gov/Archives/edgar/data/19617/000001961723000304/jpm-20230501.htm",
        "sha256": "796d126d6a8eb863556ec426c55329fa67ed68876c0569ccac15097fd32dd034",
        "content_sha256": "d357f6b71e61ac4f831ea7a59e71b2811616afb049a91fdf92c8a45b543459a4",
        "basis": "First Republic Bank registered its securities with the FDIC, not the SEC, so it has no SEC financial history. This SEC filing by the acquirer of its deposits from the FDIC receiver identifies the bank; it is matched to the 2023-05-03 provider quote vintage for listing identity only.",
    },
    "SBNY": {
        "cik": None,
        "quote_asof": "2023-03-14",
        "name": "Signature Bank",
        "exchange": "NASDAQ",
        "url": "https://www.sec.gov/Archives/edgar/data/910073/000119312523074432/d481717d8k.htm",
        "sha256": "e3a5c2360990ec5eedcc8ab9c50e72cd3aee0fb7e86843f6d24192f60f15c25c",
        "content_sha256": "4043d4e772b287d368c74cfad1d21db4c71a2b0572d51c759f3adf952ccd6a6d",
        "basis": "Signature Bank registered its securities with the FDIC, not the SEC, so it has no SEC financial history. This SEC filing by the acquirer of its deposits from the FDIC receiver identifies the bank; it is matched to the 2023-03-14 provider quote vintage for listing identity only.",
    },
}


SUCCESSION_VERSION = "reviewed-issuer-succession-v1"
# Rule 12g-3 successions where the listed shares carried over one-for-one to a
# new registrant with a new CIK. The current SEC directory maps the ticker to
# the successor, whose own filings start at the succession. Annual reports the
# predecessor filed before ``effective`` remain the as-filed history of the
# listed shares. ``valid_before`` stops their use at a combination that
# changed the share's economic basis (cash plus a merged business).
SUCCESSIONS = {
    "XOM": {
        "successor_cik": "0002115436",
        "predecessors": [
            {
                "cik": "0000034088",
                "name": "Exxon Mobil Corporation",
                "effective": "2026-07-01",
                "url": "https://www.sec.gov/Archives/edgar/data/2115436/000119312526291990/d71068d8k12b.htm",
                "sha256": "a67ef4cbd0cb286dfed4847dd5af6256c00d6c7215128444e1ef5fc32b26cd39",
                "content_sha256": "551683b3b73070f8278bf4fc43fb9304d15010ba82c95355b1f9c8c44194ef24",
                "basis": "Effective July 1, 2026, each ExxonMobil common share was exchanged for one ExxonMobil Holdings Corporation share, which succeeded to the registration under Rule 12g-3(a).",
            }
        ],
    },
    "APA": {
        "successor_cik": "0001841666",
        "predecessors": [
            {
                "cik": "0000006769",
                "name": "Apache Corporation",
                "effective": "2021-03-01",
                "url": "https://www.sec.gov/Archives/edgar/data/1841666/000119312521063695/d127090d8k12b.htm",
                "sha256": "66190ff94a370099584ca0ed50e37c2373ca40038ac7a7758a15211b3f1608ef",
                "content_sha256": "34f410527308a767361c29a369cef28a0b37f8d2dbf5194aa6923294e85f20cb",
                "basis": "Effective March 1, 2021, each Apache common share converted into one APA Corporation share in a holding-company reorganization; APA is the Rule 12g-3(a) successor.",
            }
        ],
    },
    "AVGO": {
        "successor_cik": "0001730168",
        "predecessors": [
            {
                "cik": "0001649338",
                "name": "Broadcom Limited (Singapore)",
                "effective": "2018-04-04",
                "url": "https://www.sec.gov/Archives/edgar/data/1730168/000119312518107559/d562806d8k12b.htm",
                "sha256": "32ff4e9435ca81d95f6ad3815535e74d713f85752181d618c328fea2e6fba409",
                "content_sha256": "1853688358bc00d1dc2009d6b79fccd4808b41644e567e41ebb80834a2d26a89",
                "basis": "Broadcom-Singapore ordinary shares were exchanged one-for-one for Broadcom-Delaware common stock on April 4, 2018; Broadcom-Delaware is the Rule 12g-3(a) successor.",
            }
        ],
    },
    "BG": {
        "successor_cik": "0001996862",
        "predecessors": [
            {
                "cik": "0001144519",
                "name": "Bunge Limited (Bermuda)",
                "effective": "2023-11-01",
                "url": "https://www.sec.gov/Archives/edgar/data/1996862/000110465923113123/tm2329005d3_8k12g3.htm",
                "sha256": "83c6435682e6fe8544119544b1cdcb365dafd022783c7489585fa67ef35d7b48",
                "content_sha256": "83c6435682e6fe8544119544b1cdcb365dafd022783c7489585fa67ef35d7b48",
                "basis": "Bunge Global issued one common share for each Bunge Bermuda common share in the redomestication and is the Rule 12g-3(a) successor.",
            }
        ],
    },
    "BLK": {
        "successor_cik": "0002012383",
        "predecessors": [
            {
                "cik": "0001364742",
                "name": "BlackRock, Inc. (now BlackRock Finance, Inc.)",
                "effective": "2024-10-01",
                "url": "https://www.sec.gov/Archives/edgar/data/2012383/000119312524229601/d856271d8k12b.htm",
                "sha256": "f50cd324487a40e182e30499de7c0f776dfba951fbb8673a2b2e22df5c7d03e2",
                "content_sha256": "9bbff43c9f612ae517bdf7b7279e73f8368bfb4b71b26470f01a9a7b6fd9a1e8",
                "basis": "On October 1, 2024 each Old BlackRock common share converted into one New BlackRock common share; New BlackRock is the Rule 12g-3(a) successor.",
            }
        ],
    },
    "CI": {
        "successor_cik": "0001739940",
        "predecessors": [
            {
                "cik": "0000701221",
                "name": "Cigna Corporation (now Cigna Holding Company)",
                "effective": "2018-12-20",
                "url": "https://www.sec.gov/Archives/edgar/data/1739940/000114036118045479/form8k12b.htm",
                "sha256": "d7b7bc2c31e035764c16c0eabc2c9c84b72784e4dd4ae7a14cb8184c1fce8982",
                "content_sha256": "60c155d22d16180880a8af35c2af7cceec4d1d23ea5baa0863241e64f90df563",
                "basis": "On December 20, 2018 each Cigna common share converted into one New Cigna common share; New Cigna is the Rule 12g-3(c) successor to Cigna and Express Scripts.",
            }
        ],
    },
    "DIS": {
        "successor_cik": "0001744489",
        "predecessors": [
            {
                "cik": "0001001039",
                "name": "The Walt Disney Company (now TWDC Enterprises 18 Corp.)",
                "effective": "2019-03-20",
                "url": "https://www.sec.gov/Archives/edgar/data/1744489/000095015719000301/form8k-12b.htm",
                "sha256": "c07df3fa9a31645d6648945326f001bfbd590f8a66ca0aea801610f2e9ac280a",
                "content_sha256": "7e0ac16e575913c6342ba722e391a1f8cd12a168e76a8a656572cd8f3848084c",
                "basis": "At the March 2019 21CF acquisition each Old Disney common share converted into one share of the new Disney holding company, the Rule 12g-3(a) successor to Old Disney.",
            }
        ],
    },
    "XRX": {
        "successor_cik": "0001770450",
        "predecessors": [
            {
                "cik": "0000108772",
                "name": "Xerox Corporation",
                "effective": "2019-07-31",
                "url": "https://www.sec.gov/Archives/edgar/data/1770450/000119312519208837/d767474d8k12b.htm",
                "sha256": "4e37459893b6d2dcbf6964ff41745c722588f76e223eb0d58a154a542275f5d4",
                "content_sha256": "4e279f90dd0ad140ab71e787b848ff546e3b361be1da32015931d087f89b7e9f",
                "basis": "On July 31, 2019 each Xerox common share automatically converted into one Xerox Holdings share; Xerox Holdings is the Rule 12g-3(a) successor.",
            }
        ],
    },
    "SW": {
        "successor_cik": "0002005951",
        "predecessors": [
            {
                "cik": "0001732845",
                "name": "WestRock Company",
                "effective": "2024-07-05",
                "valid_before": "2024-07-05",
                "url": "https://www.sec.gov/Archives/edgar/data/2005951/000110465924078355/tm2418700d1_8k.htm",
                "sha256": "d7158d2e7c255ffe81d1de2dbfa778001fc83a797ee7c10e3e87b2425b61fcf2",
                "content_sha256": "0e88df155b57c1629e2681fe874cd21b52a8f54945eb72dfb6b71849e5306b24",
                "basis": "Each WestRock share became one Smurfit Westrock share plus $5.00 cash, and the combined company includes Smurfit Kappa. WestRock's own annual reports describe the indexed WestRock shares only before July 5, 2024.",
            },
            {
                "cik": "0001636023",
                "name": "WestRock Company before November 2, 2018 (now WRKCo Inc.)",
                "effective": "2018-11-02",
                "valid_before": "2024-07-05",
                "url": "https://www.sec.gov/Archives/edgar/data/1732845/000117184318007722/f8k12b_110718.htm",
                "sha256": "83993d077a493e37b14dc8c209751307d2935d44ba577d445e8b8c35195089c0",
                "content_sha256": "90cc33bfce0c0813e4d7a2e6b9fe0b9b6283e186f9c319041536b85aa7e74eab",
                "basis": "At the November 2, 2018 KapStone acquisition each WRKCo common share converted into one share of the new WestRock holding company, the Rule 12g-3(c) successor.",
            },
        ],
    },
}


def predecessors(symbol, cik, api):
    """Reviewed predecessors of the issuer the current directory maps to ``symbol``."""
    spec = SUCCESSIONS.get(symbol)
    if not spec or spec["successor_cik"] != cik:
        return []
    proofs = []
    for proof in spec["predecessors"]:
        if not primary_matches(api.document(proof["url"]), proof):
            raise ResearchError(
                f"{symbol}: reviewed issuer succession source fingerprint changed."
            )
        proofs.append({"symbol": symbol, "version": SUCCESSION_VERSION, **proof})
    return proofs


def _vintage_matches(proof, quote_asof, candidate_ids):
    """Exact reviewed quote vintage, or a still-listed security's later vintages.

    A ``through_latest`` proof needs the exact reviewed directory records, so
    a new listing under the ticker fails closed.
    """
    if not proof.get("through_latest"):
        return str(quote_asof) == proof["quote_asof"]
    return str(quote_asof) >= proof["quote_asof"] and sorted(
        candidate_ids or ()
    ) == sorted(proof["listing_ids"])


def verify(symbol, quote_asof, api, candidate_ids=None):
    proof = ISSUERS.get(symbol)
    if not proof or not _vintage_matches(proof, quote_asof, candidate_ids):
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
        and _vintage_matches(
            expected, identity.get("asof", ""), identity.get("candidate_ids")
        )
        and (
            not expected.get("required_price_contracts")
            or metadata.get("normalizer_version")
            in expected["required_price_contracts"]
        )
    ):
        return supplied
    return None
