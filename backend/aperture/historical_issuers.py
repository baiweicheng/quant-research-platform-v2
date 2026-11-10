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
        "required_price_contract": "dated-research-inputs-v8-reviewed-separations",
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
        "required_price_contract": "dated-research-inputs-v8-reviewed-separations",
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
        and (
            not expected.get("required_price_contract")
            or metadata.get("normalizer_version") == expected["required_price_contract"]
        )
    ):
        return supplied
    return None
