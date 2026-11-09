"""Dated share-class evidence from a filing's own Inline XBRL cover.

Today's issuer ticker list is never historical per-share-unit evidence. Missing
or ambiguous filed evidence leaves EPS unavailable; entity profitability survives.
"""

import hashlib
import json
import re
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

from urllib.parse import urljoin
from xml.etree import ElementTree as ET

from lxml import etree

from .providers import ResourceMissing, EvidenceLimit
from .domain import ResearchError

FILING_READERS = 4
VERSION = "filed-common-class-v1"
CACHE_VERSION = "parsed-filed-evidence-v3-fast-xhtml"
CLASS_AXES = {"statementclassofstockaxis", "classesofsharecapitalaxis"}


def expand_metadata(store, metadata):
    """Resolve shared audit blocks only for complete/native exports."""
    fundamentals = metadata.get("fundamentals")
    if not isinstance(fundamentals, dict):
        return metadata
    coverage = []
    with store.connect() as db:
        for row in fundamentals.get("coverage", []):
            digest = row.get("filed_share_classes_digest")
            coverage.append(
                {**row, "filed_share_classes": json.loads(store._read_blob(db, digest))}
                if digest
                else row
            )
    return {**metadata, "fundamentals": {**fundamentals, "coverage": coverage}}


def ticker(value):
    return value.strip().upper().replace(".", "-")


def html_tree(raw):
    # libxml performs tokenization in C. SEC reports can contain tens of MB of
    # tables, while evidence needs only contexts and a handful of tagged facts.
    parser = etree.HTMLParser(
        encoding="utf-8", no_network=True, remove_comments=True, huge_tree=False
    )
    tree = etree.fromstring(raw, parser)
    if tree is None or any(
        "excessive depth" in entry.message.lower()
        or "resource limit" in entry.message.lower()
        for entry in parser.error_log
    ):
        raise ValueError("Filing HTML exceeds safe parser limits.")
    return tree


class Cover:
    def __init__(self):
        self.contexts, self.facts = {}, []
        self.namespaces = {}

    def feed(self, raw):
        try:
            tree = etree.fromstring(
                raw, etree.XMLParser(no_network=True, resolve_entities=False)
            )
        except etree.XMLSyntaxError:
            return self.feed_html(raw)
        dtd = tree.getroottree().docinfo.internalDTD
        if dtd is not None and dtd.entities():
            raise ValueError("Custom XML entities are not supported in filed evidence.")
        instance = "{http://www.xbrl.org/2003/instance}"
        for node in tree.iter(instance + "context"):
            context = {"id": node.get("id"), "members": [], "cik": None}
            for child in node.iter():
                if not isinstance(child.tag, str):
                    raise ValueError("Unresolved XML entity in filing context.")
                local = etree.QName(child).localname.lower()
                if local == "identifier" and child.get("scheme", "").rstrip("/") in {
                    "http://www.sec.gov/CIK",
                    "https://www.sec.gov/CIK",
                }:
                    context["cik"] = (
                        "".join(child.itertext()).strip().lstrip("0") or "0"
                    )
                elif (
                    local in {"explicitmember", "typedmember"}
                    and child.get("dimension", "").split(":")[-1].lower() in CLASS_AXES
                ):
                    context["members"].append(
                        " ".join("".join(child.itertext()).split())
                    )
            self.contexts[context["id"]] = context
        tags = [
            "{" + namespace + "}" + local
            for namespace in (
                "http://www.xbrl.org/2013/inlineXBRL",
                "http://www.xbrl.org/2008/inlineXBRL",
            )
            for local in ("nonNumeric", "nonFraction")
        ]
        for node in tree.iter(*tags):
            name = node.get("name", "")
            prefix, _, concept = name.partition(":")
            concept = concept.lower()
            if concept not in {
                "security12btitle",
                "security12gtitle",
                "tradingsymbol",
                "entitycommonstocksharesoutstanding",
                "earningspersharediluted",
                "earningspersharebasic",
            }:
                continue
            uri = node.nsmap.get(prefix, "")
            group = (
                "dei"
                if uri.startswith(
                    ("http://xbrl.sec.gov/dei/", "https://xbrl.sec.gov/dei/")
                )
                else "us-gaap"
                if uri.startswith(
                    ("http://fasb.org/us-gaap/", "https://fasb.org/us-gaap/")
                )
                else None
            )
            if group:
                attrs = {k.lower(): v for k, v in node.attrib.items()}
                self.facts.append(
                    (
                        group + ":" + concept,
                        attrs,
                        " ".join("".join(node.itertext()).split()),
                    )
                )

    def feed_html(self, raw):
        tree = html_tree(raw)
        nodes = tree.xpath(
            "//*[name()='context' or substring-after(name(),':')='context' "
            "or ((name()='ix:nonnumeric' or name()='ix:nonfraction') and "
            "contains($concepts, concat('|',substring-after(translate(@name, "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),':'),'|'))) "
            "or @*[starts-with(name(),'xmlns:')]]",
            concepts="|security12btitle|security12gtitle|tradingsymbol|entitycommonstocksharesoutstanding|earningspersharediluted|earningspersharebasic|",
        )
        for node in nodes:
            self.namespaces.update(
                {k[6:]: v for k, v in node.attrib.items() if k.startswith("xmlns:")}
            )
            if node.tag.split(":")[-1] == "context":
                context = {"id": node.get("id"), "members": [], "cik": None}
                for child in node.iter():
                    local = child.tag.split(":")[-1]
                    text = " ".join("".join(child.itertext()).split())
                    attrs = child.attrib
                    if local == "identifier" and attrs.get("scheme", "").rstrip(
                        "/"
                    ) in {
                        "http://www.sec.gov/CIK",
                        "https://www.sec.gov/CIK",
                    }:
                        context["cik"] = text.lstrip("0") or "0"
                    elif local in {"explicitmember", "typedmember"}:
                        axis = attrs.get("dimension", "").split(":")[-1].lower()
                        if axis in CLASS_AXES:
                            context["members"].append(text)
                self.contexts[context["id"]] = context
            if node.tag in {"ix:nonnumeric", "ix:nonfraction"}:
                attrs = dict(node.attrib)
                text = " ".join("".join(node.itertext()).split())
                name = attrs.get("name", "").lower()
                prefix, _, concept = name.partition(":")
                uri = self.namespaces.get(prefix, "")
                if uri.startswith(
                    ("http://xbrl.sec.gov/dei/", "https://xbrl.sec.gov/dei/")
                ):
                    self.facts.append(("dei:" + concept, attrs, text))
                elif uri.startswith(
                    ("http://fasb.org/us-gaap/", "https://fasb.org/us-gaap/")
                ):
                    self.facts.append(("us-gaap:" + concept, attrs, text))


def inspect_cover(raw, *, symbol, cik, accession, filed, url):
    result = {
        "version": VERSION,
        "accession": accession,
        "filed": filed,
        "cik": cik,
        "symbol": symbol,
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "compatible": False,
    }
    parser = Cover()
    try:
        parser.feed(raw)
    except (ValueError, RecursionError, etree.LxmlError):
        return {**result, "reason": "Filed share-class evidence could not be parsed."}
    titles, symbols, outstanding, eps_members = {}, {}, set(), set()
    for name, attrs, text in parser.facts:
        context = parser.contexts.get(attrs.get("contextref"))
        if context is None or context["cik"] != (cik.lstrip("0") or "0"):
            continue
        key = tuple(sorted(context["members"]))
        if name in {"dei:security12btitle", "dei:security12gtitle"}:
            titles.setdefault(key, set()).add(text)
        elif name == "dei:tradingsymbol":
            symbols.setdefault(key, set()).add(ticker(text))
        elif name == "dei:entitycommonstocksharesoutstanding":
            outstanding.add(key)
        elif (
            name in {"us-gaap:earningspersharediluted", "us-gaap:earningspersharebasic"}
            and key
        ):
            eps_members.add(key)
    common = {
        key
        for key, names in titles.items()
        if any(
            re.search(r"\b(common|ordinary)\b", n, re.I)
            and not re.search(
                r"\b(preferred|preference|warrant|depositary|depositary|unit)\b",
                n,
                re.I,
            )
            for n in names
        )
    }
    result["common_classes"] = [
        {
            "members": list(key),
            "titles": sorted(titles[key]),
            "tickers": sorted(symbols.get(key, set())),
        }
        for key in sorted(common)
    ]
    if len(common) != 1 or any(
        key not in common for key in outstanding | eps_members if key
    ):
        return {
            **result,
            "reason": "Filing does not establish one unambiguous common-share class; class-specific EPS units remain unmapped.",
        }
    key = next(iter(common))
    if symbols.get(key) != {ticker(symbol)}:
        return {
            **result,
            "reason": "Filing common-share ticker does not uniquely match this security; historical aliases are not inferred.",
        }
    return {
        **result,
        "compatible": True,
        "reason": "Filed Inline XBRL identifies one common-share class matching this security; preferred/debt listings do not count as common classes.",
    }


def xml(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("External XML declarations are not supported.")
    return ET.fromstring(raw)


class FilingIndex(HTMLParser):
    """Read the filing's declared instance-document row, including extracted XBRL."""

    def __init__(self):
        super().__init__()
        self.row = None
        self.names = set()

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = {"text": [], "links": []}
        if self.row is not None and tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.row["links"].append(href)

    def handle_data(self, value):
        if self.row is not None:
            self.row["text"].append(value)

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            text = " ".join(self.row["text"]).upper()
            if "EX-101.INS" in text or "XBRL INSTANCE DOCUMENT" in text:
                self.names.update(self.row["links"])
            self.row = None


def instance_url(api, folder, accession):
    summary = xml(api.document(folder + "FilingSummary.xml"))
    names = {
        node.attrib["instance"]
        for node in summary.iter()
        if node.attrib.get("instance")
    }
    if not names or any(not n.endswith(".xml") for n in names):
        names = {
            node.text.strip()
            for node in summary.findall(".//InputFiles/File")
            if node.text
            and node.text.strip().endswith(".xml")
            and not node.text.strip().endswith(
                ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")
            )
        }
    if len(names) == 1 and re.fullmatch(r"[A-Za-z0-9_.-]+\.xml", next(iter(names))):
        return folder + next(iter(names))
    index = FilingIndex()
    index.feed(
        api.document(folder + accession + "-index.htm").decode(
            "utf-8", errors="replace"
        )
    )
    urls = {urljoin(folder, name) for name in index.names}
    urls = {
        url
        for url in urls
        if url.startswith(folder)
        and re.fullmatch(r"[A-Za-z0-9_.-]+\.xml", url[len(folder) :])
    }
    return next(iter(urls)) if len(urls) == 1 else None


def inspect_instance(raw, primary, *, symbol, cik, accession, filed, url):
    """Pre-Inline filings: require a single reported common-share basis.

    This verifies the filed issuer, DEI outstanding-share context and undivided
    EPS contexts. It does not claim a historical ticker/CIK security master.
    Different common classes or class-specific EPS remain excluded.
    """
    result = {
        "version": VERSION,
        "method": "filed-xbrl-common-share-context",
        "accession": accession,
        "filed": filed,
        "cik": cik,
        "symbol": symbol,
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "primary_sha256": hashlib.sha256(primary).hexdigest(),
        "compatible": False,
    }
    try:
        root = xml(raw)
    except (ET.ParseError, ValueError):
        return {**result, "reason": "Filed XBRL instance could not be verified."}
    contexts = {}
    local = lambda tag: tag.split("}")[-1].lower()
    for context in root.iter():
        if local(context.tag) != "context":
            continue
        ids, members = set(), set()
        for child in context.iter():
            if local(child.tag) == "identifier" and child.attrib.get(
                "scheme", ""
            ).rstrip("/") in {"http://www.sec.gov/CIK", "https://www.sec.gov/CIK"}:
                ids.add((child.text or "").lstrip("0") or "0")
            if (
                local(child.tag) in {"explicitmember", "typedmember"}
                and child.attrib.get("dimension", "").split(":")[-1].lower()
                in CLASS_AXES
            ):
                members.add("".join(child.itertext()).strip())
        if ids == {cik.lstrip("0") or "0"}:
            contexts[context.attrib.get("id")] = tuple(sorted(members))
    outstanding, common_members, eps = set(), set(), set()
    for node in root:
        context = contexts.get(node.attrib.get("contextRef"))
        if context is None:
            continue
        name = local(node.tag)
        namespace = node.tag.partition("}")[0].lstrip("{")
        if not namespace.startswith(
            (
                "http://xbrl.sec.gov/dei/",
                "https://xbrl.sec.gov/dei/",
                "http://fasb.org/us-gaap/",
                "https://fasb.org/us-gaap/",
            )
        ):
            continue
        if name == "entitycommonstocksharesoutstanding":
            outstanding.add(context)
        if name in {
            "entitycommonstocksharesoutstanding",
            "commonstocksharesoutstanding",
            "commonstocksharesissued",
            "earningspersharediluted",
            "earningspersharebasic",
        }:
            if context:
                common_members.add(context)
        if name == "earningspersharediluted":
            eps.add(context)

    try:
        content = " ".join(" ".join(html_tree(primary).itertext()).split())
    except (ValueError, etree.LxmlError):
        return {**result, "reason": "Filed HTML could not be verified."}
    named_classes = {
        m.upper()
        for m in re.findall(
            r"\bclass\s+([a-z0-9-]+)\s+(?:voting\s+|non[- ]voting\s+)?(?:common|ordinary)\s+(?:stock|shares)",
            content,
            re.I,
        )
    }
    if outstanding != {()} or eps != {()} or common_members or len(named_classes) > 1:
        return {
            **result,
            "reason": "Filed XBRL does not establish an undivided common-share/EPS basis; multiple or unmapped class contexts remain excluded.",
        }
    return {
        **result,
        "compatible": True,
        "reason": "Dated issuer XBRL reports one undivided common-share and diluted-EPS context; no contradictory named common classes found. Historical ticker/CIK mapping remains separately limited.",
    }


def acquire(
    api,
    symbol,
    cik,
    company,
    submissions,
    start,
    end,
    progress=lambda *a: None,
    *,
    readers=None,
):
    """Read immutable filed documents once, with persistent provider caching.

    Only source accessions capable of informing this snapshot's decisions are
    requested. An unavailable/legacy cover is an explicit per-filing exclusion.
    Transport/access failures remain failures, so a retry can reuse captures.
    """
    wanted = {}
    for row in (
        company.get("facts", {})
        .get("us-gaap", {})
        .get("EarningsPerShareDiluted", {})
        .get("units", {})
        .get("USD/shares", [])
    ):
        if (
            row.get("form") in {"10-K", "10-K/A"}
            and start <= row.get("filed", "") <= end
        ):
            if re.fullmatch(r"\d{10}-\d{2}-\d{6}", row.get("accn", "")):
                wanted[row["accn"]] = row["filed"]
    recent = submissions.get("filings", {}).get("recent", {})
    documents = {}

    def collect(block):
        for accession, doc, filed in zip(
            block.get("accessionNumber", []),
            block.get("primaryDocument", []),
            block.get("filingDate", []),
        ):
            if (
                accession in wanted
                and filed == wanted[accession]
                and re.fullmatch(r"[A-Za-z0-9_.-]+\.html?", doc or "")
            ):
                documents[accession] = doc

    collect(recent)
    for archive in submissions.get("filings", {}).get("files", []):
        if len(documents) == len(wanted):
            break
        if (
            archive.get("filingTo", "") < start
            or archive.get("filingFrom", "9999") > end
        ):
            continue
        name = archive.get("name", "")
        if not re.fullmatch(r"CIK\d+-submissions-\d+\.json", name):
            continue
        collect(
            api.get("sec", "https://data.sec.gov/submissions/" + name, ttl=315360000)
        )
    evidence = {}
    store = getattr(api, "store", None)
    stats = getattr(api, "filing_cache_stats", None)
    if stats is None:
        stats = api.filing_cache_stats = {"reused": 0, "parsed": 0}

    def verify(item):
        accession, filed = item
        reader = api.fork() if hasattr(api, "fork") else api
        record = {
            "version": VERSION,
            "accession": accession,
            "filed": filed,
            "cik": cik,
            "symbol": symbol,
            "compatible": False,
            "reason": "Dated filing cover is unavailable; current issuer tickers are not historical share-class evidence.",
        }
        doc = documents.get(accession)
        cache_key = hashlib.sha256(
            json.dumps(
                [
                    CACHE_VERSION,
                    VERSION,
                    etree.LXML_VERSION,
                    etree.LIBXML_VERSION,
                    symbol,
                    cik,
                    accession,
                    filed,
                    doc,
                ],
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        cached = store.filing_evidence(cache_key) if store and doc else None
        if cached:
            return (
                accession,
                cached["proof"],
                [source["id"] for source in cached["sources"]],
                "reused",
            )
        source_start = len(getattr(reader, "observations", []))
        cacheable = False
        if doc:
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{doc}"
            record["url"] = url
            try:
                raw = reader.document(url)
                record = inspect_cover(
                    raw,
                    symbol=symbol,
                    cik=cik,
                    accession=accession,
                    filed=filed,
                    url=url,
                )
                if not record.get("common_classes"):
                    # Official filing manifest owns the filename, never a guess.
                    folder = url.rsplit("/", 1)[0] + "/"
                    instance = instance_url(reader, folder, accession)
                    if instance:
                        record = inspect_instance(
                            reader.document(instance),
                            raw,
                            symbol=symbol,
                            cik=cik,
                            accession=accession,
                            filed=filed,
                            url=instance,
                        )
                    else:
                        record["reason"] = (
                            "The filed manifest does not identify one supported XBRL instance; EPS share units remain unverified."
                        )
                cacheable = True
            except ResourceMissing:
                record["reason"] = (
                    "Filed document returned HTTP 404; share-class units remain unverified."
                )
            except EvidenceLimit as error:
                record["compatible"] = False
                record["reason"] = str(error)
            except ResearchError:
                # Provider failures inherit ValueError too. They must interrupt
                # acquisition, rather than masquerade as an incompatible filing.
                raise
            except (ET.ParseError, ValueError):
                record["compatible"] = False
                record["reason"] = (
                    "Filed XBRL manifest could not be verified; EPS units remain unavailable."
                )
        sources = getattr(reader, "observations", [])[source_start:]
        if store and cacheable:
            store.save_filing_evidence(cache_key, record, sources)
        return (
            accession,
            record,
            sources if reader is not api else [],
            "parsed" if doc else None,
        )

    pool = (
        ThreadPoolExecutor(max_workers=readers or FILING_READERS)
        if hasattr(api, "fork") and len(wanted) > 1
        else None
    )
    try:
        results = (
            pool.map(verify, sorted(wanted.items()))
            if pool
            else map(verify, sorted(wanted.items()))
        )
        for index, (accession, record, sources, status) in enumerate(results):
            evidence[accession] = record
            if sources:
                api.observations.extend(sources)
            if status:
                stats[status] += 1
            progress(index + 1, len(wanted))
    finally:
        if pool:
            pool.shutdown(wait=True, cancel_futures=True)
    return evidence
