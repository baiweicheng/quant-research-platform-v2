# Historical coverage improvements

Engine 0.6.0 narrows the price history required for exploratory backtests and adds reviewed missing merger terms. The normal Download and Update workflows apply the data supplements automatically. Original snapshots and saved results remain frozen.

## Reviewed security events and financial successions (input contract v9)

Input contract `dated-research-inputs-v9-reviewed-security-events` with annual
normalizer `annual-us-gaap-v5-successors-and-eps-elements` removes the remaining
price/action exclusions for January 3, 2017–November 6, 2026. All five recipes
now use the full **704-stock** dated universe with **zero exclusions**, down
from 66 (momentum, low volatility, value + momentum) and 64 (quality, quality
value). The ordinary Download and Update apply every repair; no new user step
exists. The first Update of an older snapshot revalidates the full history once,
because earlier snapshots froze vendor records that these reviews correct.

Most former exclusions had prices through the real final session, but the
vendor's terminal record was missing, misdated or incomplete. The reviewed
registry (`backend/aperture/reviewed_events.py`) holds primary-filing terms,
fingerprints and the captured final close for each case:

- **43 terminal conversions**, including cash, stock and mixed mergers, the
  21st Century Fox split into Disney plus new Fox shares, and conversions on
  the first session after trading stopped. Elections model the non-electing
  holder, never a favourable choice in hindsight (Andeavor, GGP, Paramount).
  Silicon Valley Bank, First Republic and Signature Bank end at zero value,
  following receivership with no later exchange trade.
- **29 reviewed distributions** replace spin-off proxies that the vendor recorded
  as parent reverse splits. Without the fix, TGNA, CNX, EQT and UTX/RTX showed
  one-day losses of 58–90%. Spin-offs missing from vendor data are added (YUM,
  PNR, JCI, BIIB, MRK, IBM). Children are valued at their ex-date close.
- **Five listing lifetimes** remove quotes that belong to another security under
  the same ticker (DOW before April 2, 2019; FOXA/FOX before the new Fox; Under
  Armour Class A history under the Class C label; IHS Markit marks after its
  conversion).
- The same dividend listed under a second CUSIP counts once (33 records). Two
  more duplicate payments are rejected individually: TransDigm's $90 special
  and a second Xcel dividend. Eight foreign-issuer dividend amounts are
  confirmed from the issuer's periodic report.
- Vendor records belonging to other securities are rejected: BNY's municipal
  fund before the bank adopted the ticker, a fund liquidation under the reused
  CA ticker, Caesars/Eldorado, Physicians Realty/Healthpeak, and a phantom RJF
  stock dividend. Level 3's final October 2017 sessions come from the undated
  quote mapping; every overlapping row has to match exactly.
- Old tickers (YHOO/AABA, DLPH/APTV, CDAY/DAY, LB/BBWI, BHI/BHGE, WYN/WYND,
  FMC Technologies/TechnipFMC) now include the old ticker's corporate actions.
- A new guard blocks any unreviewed split or distribution day whose total return
  differs from SPY by more than about −22%/+28%. Such a day indicates a
  mislabeled or doubled action. Reviewed days and genuine large moves on
  dividend days are not affected.
- Shares received in a merger on its effective session were not held at the
  prior close. They no longer receive that session's split or ex-date
  entitlement. Coverage ignores repeated zero-volume closing marks after
  trading stops. It also ignores up to five roster sessions before a new
  listing's first trade; backtest validation applies the same rule.

Financial inputs gained three repairs:

- **Nine reviewed Rule 12g-3 successions** (ExxonMobil 2026, APA, Broadcom,
  Bunge, BlackRock, Cigna, Disney, Xerox, and WestRock/Smurfit Westrock). The
  current SEC ticker map points at the new registrant. The predecessor's own
  annual reports, filed before the succession, are now used for the same listed
  shares. WestRock's reports stop at the July 2024 Smurfit combination, which
  paid $5.00 per share and added a merged business.
- Diluted EPS uses `EarningsPerShareDiluted`, then the combined
  `EarningsPerShareBasicAndDiluted` element, then diluted EPS from continuing
  operations. The last applies only when the filing has no whole-entity net
  element. Many single-class filers without discontinued operations tag their
  bottom-line EPS only this way (Monster, Regency, Kimco, Analog Devices,
  American Express 2014–2018, Halliburton, Exelon, ConocoPhillips). Earnings
  before discontinued operations is also the usual research earnings measure.
- Positive EPS above the decision share price is rejected as a filing scale
  error. Example: Halliburton's 2023–2025 10-Ks tag $1.73 as 1,730,000. Losses
  larger than the share price remain valid negative inputs.

Weekly S&P 500 member observations lacking a value (earnings-yield) input fell
from **37,156 of 258,682 (14.4%)** in the earlier normal snapshot to **5,844
(2.3%)**. Those lacking a quality (gross-profitability) input fell from 119,007
(46.0%) to 105,532 (40.8%). The same audit covers the 513 weekly decisions from
2017-01-03.

### Remaining gaps

- **Backtests starting in 2016** still exclude members that left the index in
  2016 and have no directory identity or merger terms, for example EMC, TWC,
  BRCM and Cameron. Counts: 21 for a February 2016 start, 9 for June, 1 (old
  Arconic) for October, 0 from 2017. The default start date is January 2017.
  The three 253-session recipes cannot rank stocks in 2016 anyway.
- **Value inputs (2.3% of member-weeks):** the main causes are multi-class issuers
  that report EPS only per class (Berkshire by design, Hershey, Constellation
  Brands, Visa, Discovery, Under Armour, Alphabet in some years, Erie, KKR,
  Ares) and banks that filed with the FDIC (First Republic, Signature). Newly
  listed companies before their first 10-K, Halliburton's three scale-error
  filings and a small remainder account for the rest.
- **Quality inputs are the next item, not a minor gap.** Gross profitability is
  missing for 40.8% of member-weeks. About 21.7 points are financials,
  utilities and REITs (about 56,000 member-weeks), where gross profit is often
  not a reported line. About 19 points are operating companies, for example
  UNP, XOM and MCD in every week, and Intuit, Oracle and Verizon until roughly
  the last two years. That pattern may be an extraction gap; the cause has not
  been diagnosed. Missing profitability leaves a stock unranked rather than
  excluded, so the exclusion counts above do not show it.
- **Payment-date simulation:** strict full-index validation passes in
  total-return (ex-date) mode from January 3, 2017 through November 10, 2026.
  The stricter cash-flow mode still lacks verified payment dates for DOC, ORCL
  and XRX.
- **Approximations:** Celgene's tradeable CVR is valued at its first close
  ($2.25). Walgreens' asset-proceeds right is not credited. Technip Energies
  (Paris-only) is valued from the vendor's adjustment. Millrose is valued at
  its first regular-way close, 13 sessions after Lennar's ex-date. Sectors
  remain static current/last-known labels. The roster is retrospective; its
  size stays between 503 and 507 share classes throughout.

## Individual listings and market timing

### Reviewed separations and expanded issuer coverage (input contract v8)

The historical issuer registry now contains **64 reviewed mappings**, adding
51 original financial histories and 1,636 annual records to the preceding
snapshot. Every added history has annual records; unavailable profitability or
nonpositive factors can still make a stock ineligible for an individual recipe.
The issuer mapping does not establish exhaustive EPS share-class verification.
Raw SEC accession, annual period, units and filing availability remain checked.
Examples requiring care include old DNB versus its later IPO, original CHK
versus post-bankruptcy equity, the XL insurer versus XL Fleet, and Envision's
post-2016 issuer versus the archived AmSurg CIK. Combined Allergan and Duke
Realty filings distinguish the common-stock parent from subsidiary co-registrants.

Issuer evidence alone was insufficient for two price cohorts. The ordinary
Download/Update workflow now reconciles their economic share counts:

- [Old Arconic/Howmet](https://www.sec.gov/Archives/edgar/data/4281/000110465920043824/tm2015094d1_8k.htm):
  one continuing Howmet parent share plus 0.25 new Arconic Corporation shares
  per old share on April 1, 2020. Captured HWM prices continue the parent;
  the old parent's prefix supplies HWM's verified pre-rename history. The
  later $30 acquisition of the spun-off Arconic child does not liquidate the
  old parent. Its exact native instruction remains visible as rejected evidence.
- [Dow distribution](https://www.sec.gov/Archives/edgar/data/1666700/000119312519095042/d725044d8k.htm):
  one DOW share per three parent shares before regular trading April 2, 2019.
  The vendor's 1.487 adjustment factor does not create extra parent shares.
- [Corteva and the parent reverse split](https://www.sec.gov/Archives/edgar/data/1666700/000119312519163322/d715311d8k.htm):
  three old parent shares become one DD share plus one CTVA share for the
  June 3, 2019 session. Distribution amounts are expressed per post-split
  parent share, so the child is not divided by three a second time.

Both DWDP and the continuing DD issuer discard unsupported quotes before the
new company's [September 1, 2017 first trading date, Item 5](https://www.sec.gov/Archives/edgar/data/1666700/000166670019000006/a2018dwdp10-k.htm).
The separately captured DD.OLD predecessor is unaffected. The reviewed DWDP
quote vintage supplies the continuing issuer's prices; DD at that earlier
as-of date denotes a different, ceased security and is not a valid substitute.

These repairs require exact listing/quote cohorts, primary-document
fingerprints, native instruction signatures and captured delivery-date quotes.
Changed or additional instructions require review. Research values distributions
at their actual opening/closing marks and reinvests at the closing parent price,
following the existing ex-date convention; no opening cash is invented. Strict
payment-date share delivery remains unsupported. Historical ticker boundaries
can still cause a modeled sale/rebuy rather than seamless position renaming.

The isolated first Update completed in **256.253 seconds**; a repeat completed
in **214.365 seconds**, reused 668 financial histories without company-facts
downloads, and retained exactly identical price/annual blocks, actions and
distribution marks. All 617 earlier financial blocks are unchanged. An
independent source audit verifies 64 filing fingerprints and 4,802 numerical
fields across 2,170 mapped annual records; a separate share/price audit verifies
the separation terms. Only the four reviewed historical series change, with no
unrelated price revisions in this acceptance. No new cold-download timing is
claimed. Original normal-workspace research remains unchanged.

This is partial data-gap progress. The remaining price/action exclusions are
material, and further distribution/adjustment-factor and terminal/identity
review continues. A ledger replay establishes arithmetic consistency with
inputs, not universal economic source correctness. The active goal now covers
data-gap resolution only; strategy outperformance research is deferred.

### Native merger reconciliation (input contract v7)

Primary completed-merger filings establish the first converted market sessions
for [ANSS, July 17, 2025](https://www.sec.gov/Archives/edgar/data/1013462/000114036125026141/ef20052066_8k.htm),
[CTLT, December 18, 2024](https://www.sec.gov/Archives/edgar/data/1596783/000119312524280922/d902883d8k.htm)
and [HES, July 18, 2025](https://www.sec.gov/Archives/edgar/data/4447/000095014225001950/eh250651090_8k.htm).
Corrections require exact original listing/event IDs, CUSIPs, consideration,
document fingerprints and source quote lifetimes. The vendor effective date,
verified legal date and market session remain distinct in provenance. Native
payment dates and consideration are unchanged; CTLT cash remains a receivable
until December 19 rather than becoming spendable on conversion.

HES also contains an exact stale September 30, 2024 conversion instruction.
That reviewed record remains visible as rejected source evidence and cannot
convert holdings. The actual July 2025 instruction executes once. Unknown or
changed additional merger instructions prevent this correction; the exception
does not generally suppress conflicting provider records.

The same filings establish the original three issuers' CIKs, bringing the
reviewed registry to 13. A price-only eligibility repair was insufficient:
without these financial mappings the fundamental strategies still had no annual
records for the recovered names. Final Update adds 114 annual records
(ANSS 45, CTLT 36, HES 33), reuses 614 histories and downloads three in
209.176 seconds. All prior annual blocks and actions are unchanged versus the
intermediate corrected snapshot. Every backtest-period price and all OHLC
fields are unchanged; 374 November 9 volume revisions occur after the tested
November 6 end date and are retained as ordinary provider overlap updates.

Price/action exclusions improve from 69/67 to **66/64**, recovering these three
names with no regressions, or 52 recoveries from the original 118/116. This is
not complete financial coverage: a separate audit finds **51 otherwise
price-eligible historical members without issuer financial mappings**. These
and the remaining price/action exclusions are material unresolved gaps. All
five full-period browser runs pass independent accounting checks, but none
beats SPY. No strategy tuning or paper activation is part of this repair.

### Dated historical issuers (input contract v6)

Ten reviewed filing/quote-vintage pairs identify ADS, BBBY, ENDP, FTR, GPS,
HRS, KORS, MNK, SYMC and TMK independently of the SEC's current ticker
directory. The exact primary-document fingerprints and provider quote-asof
dates must match. These mappings also load each original issuer's annual SEC
history; they never substitute an unrelated present-day holder of a reused
ticker. For example, [BBBY's 2017 cover](https://www.sec.gov/Archives/edgar/data/886158/000117184317003900/R1.htm)
identifies CIK 886158, and [Frontier's 2016 annual report, Item 5](https://www.sec.gov/Archives/edgar/data/20520/000002052017000003/ftr-20161231x10k.htm)
identifies the original FTR common stock. Neither mapping crosses the later
bankruptcy into new equity. [KORS's annual cover](https://www.sec.gov/Archives/edgar/data/1530721/000153072118000035/R1.htm)
explicitly reports its ticker; a quarterly cover that omitted it was insufficient.

Issuer certification is retrospective identity evidence, not a point-in-time
security master. Financial values remain accession/filing-date versioned, with
the existing unit, split, annual-period, share-basis and availability checks.
Price/action conflicts, missing quotes and unsupported terminal consideration
remain independent blockers. This does not implement a general share-class or
rename-conversion engine; a rename at an index ticker boundary can still
generate a modeled sale/rebuy rather than seamless continuity.

For current constituents, duplicate provider listing IDs can be reconciled
only when all names/classes/exchanges match, exactly one candidate is active,
an individual lookup confirms that active ID and status, and the first
eligible date is within the constituent's recorded admission cohort. Different
descriptors, older cohorts and former/reused tickers remain ambiguous. All
original candidate IDs survive in the audit. Six current duplicate records
qualify in the acceptance archive; IR retains its separate action blockers.

Ordinary Update revalidates only the exact missing/multiple-directory warning
supported by the new evidence. It preserves the earlier snapshot, historical
prices, and other warnings. Data exposes the ten historical mappings and their
primary links in an expandable evidence section; no new routine action is needed.

The November 9 isolated browser Update completed in 156.126 seconds, reused
610 annual histories and downloaded four, and reduced exclusions from 84/82 to
69/67: 15 more recovered, 49 versus the user's original 118/116. No previously
eligible security became excluded. All 85,867 price blocks (including the
recent overlap), existing annual records, corporate actions and original saved
results remained unchanged. The ten mapped tickers add 420 annual records; an independent audit
matches 1,009 available numerical fields to their exact captured SEC facts and
verifies all ten primary-document fingerprints and six active lookup responses.
The remaining exclusions are material; full paper readiness is not established.

Input contract v5 checks the individual asset endpoint when both bulk listing directories omit a security. It requires the exact requested symbol and valid listing metadata, retains unsupported/fund/collision checks, and captures the response through the ordinary provider archive. A missing resource remains unresolved; permission, transport and malformed-response errors fail the acquisition. This recovers provider-directory omissions, not a complete historical security master.

Ordinary Update can revalidate the specific historical missing-directory warning when a captured individual lookup supplies a supported listing. Other identity and action warnings remain. The original snapshot and its prices are preserved; the new snapshot records the prior warning and replacement listing evidence. Historical price downloads are unnecessary for this metadata repair.

Four native merger records have narrow source-verified market-date treatment. Exact listing IDs, event IDs, original CUSIPs, native consideration, source fingerprints and captured quote lifetimes must match. Legal completion dates stay in provenance; trading-session conversion follows the verified suspension:

| Security | Legal closing | First converted market session | Evidence |
| --- | --- | --- | --- |
| AGN | 2020-05-08 | 2020-05-11 | [Completed scheme and pre-open suspension](https://www.sec.gov/Archives/edgar/data/1578845/000119312520137717/d927229d8k.htm) |
| CXO | 2021-01-15 | 2021-01-19 | [NYSE filed suspension](https://www.sec.gov/Archives/edgar/data/876661/000087666121000081/ruleprovisionnotice.htm), [1.46 COP consideration](https://www.sec.gov/Archives/edgar/data/1163165/000156276221000304/R10.htm) |
| NLSN | 2022-10-11 | 2022-10-12 | [Completed $28 acquisition and suspension](https://www.sec.gov/Archives/edgar/data/1492633/000119312522260583/d407513d8k.htm) |
| ATVI | 2023-10-13 | 2023-10-13 | [Completed $95 merger and pre-open halt](https://www.sec.gov/Archives/edgar/data/718877/000110465923108985/tm2328253d1_8k.htm) |

ATVI's exact flat, zero-volume October 13 mark is retained as captured data but does not prevent contractual conversion following the verified halt. This is not a generic stale-price rule: a nonzero-volume, differently priced or later mark rejects the exception. These corrections do not manufacture cash payment dates, replace native consideration, or resolve alternative merger elections. Source links appear in the expandable corporate-action audit and full metadata export.

The isolated November 9 candidate recovers 34 names, reducing 118/116 exclusions to 84/82. All 85,736 captured price blocks remain identical. Five full-period browser-submitted results pass independent cash/NAV/SPY accounting at 12,380 valuations, including actual merger holdings. These are partial coverage improvements; the remaining omissions are material, and no candidate strategy beats SPY yet. The paper-readiness goal remains incomplete.

## What the prior implementation established

The read-only v1 review found retrospective constituent membership and explicit daily Yahoo acquisition. It also found skipped ticker/action failures, forward-filled quotes, and exits using the last available close or a price-based bankruptcy proxy. These choices can make a calculation finish without establishing the historical terminal return. V2 does not adopt those exit assumptions. No v1 code, configuration or tests were reused, and no v1 application or database was run.

## Prices needed by the actual workflow

A stock needs prices while it is an eligible member and until the opening execution after the next ordinary rebalance decision following departure. The trading schedule is unchanged. It does not need years of unrelated post-membership prices after that execution.

A supported cash or stock conversion can end the original security's price path. Missing sessions **before** conversion still block inclusion. Stock consideration requires the recipient's prices and verified inputs through the possible holding period, including subsequent supported conversions. An incomplete merger, unpriced contingent right, ambiguous identity or missing liquidation-session quote remains a blocker. A missing history is never converted into an assumed sale or zero recovery.

Cessation filtering does not treat a ticker with subsequent quotes or a later index re-entry as permanently dead. Source and recipient identity checks also apply to held or incoming positions in strict research. Non-trading legal effective dates enter the daily accounting loop on the first exchange session; reviewed after-close transactions retain their separate legal and market dates.

Coverage-limited selection still uses future availability relative to a decision. Its exclusions are frozen before simulation, disclosed and exported. This remains exploratory subset research with potential survivorship and selection bias. It is not a certified full S&P 500 history.

## Reviewed missing completed mergers

These exceptions require the exact captured old listing ID, the reviewed primary filing content fingerprint and the expected final source quote session. They fill absent vendor events without replacing native consideration. Original provider captures and primary response bytes remain available. Cash payment dates are not invented; cash-flow simulation remains stricter than the approved total-return research convention.

| Old security | First converted market session | Contractual consideration | Primary evidence |
| --- | --- | --- | --- |
| EVHC | 2018-10-11 | $46 cash | [Completed acquisition and pre-open suspension](https://www.sec.gov/Archives/edgar/data/1678531/000119312518297466/d637722dex991.htm) |
| XL | 2018-09-12 | $57.60 cash | [Completed old XL insurer acquisition, Items 2.01 and 3.01](https://www.sec.gov/Archives/edgar/data/875159/000087515918000068/axaclosing8-k.htm) |
| ESRX | 2018-12-21 | $48.75 plus 0.2434 new CI shares | [Completed exchange and first regular-way session](https://www.sec.gov/Archives/edgar/data/1739940/000114036118045479/form8k12b.htm) |
| SCG | 2019-01-02 | 0.6690 D shares | [January 1 legal closing and January 2 suspension](https://www.sec.gov/Archives/edgar/data/754737/000119312519000643/d678624d8k.htm) |
| DISCK | 2022-04-11 | One WBD Series A common share | [Completed reclassification, Items 3.01 and 3.03](https://www.sec.gov/Archives/edgar/data/1437107/000119312522103051/d328161d8k.htm) |

The DISCK terms alone do **not** resolve the WBD recipient's historical identity gap. That exclusion remains. ANDV's election/proration terms, CELG/WBA contingent rights, MYL/VTRS market timing and other unresolved events are not assigned a convenient terminal value.

## Measured coverage effect

On the captured 703-stock January 3, 2017–November 6, 2026 universe, the revised holding-window checks recover 17 names before the new missing-merger supplements. Four supplements make additional names price/action eligible, reducing 138 exclusions to 117 for momentum, low volatility and value + momentum. The shorter fundamental lookback gives 115 exclusions for quality and quality value. An annual filing must still be available for a fundamental strategy to select a stock; price/action eligibility does not create a missing financial statement.

The 21 recovered names in the 253-session case are AIV, ALXN, CERN, DNB, DWDP, ESRX, ETFC, EVHC, EXE, FLIR, KSU, MXIM, NBL, PBCT, SCG, TIF, VAR, XEC, XL, XLNX and XRX. No previously covered stock is newly excluded in that comparison.

In the updated normal snapshot, the 117 momentum exclusions include 74 paths with unavailable historical listing identity, 11 with multiple listing identities, and 53 with missing holding-period sessions. These categories overlap; they are not additive. Five paths retain split-evidence conflicts and four retain dividend-evidence conflicts. More quote downloads alone cannot establish the missing issuer identity or terminal consideration.

All five full-period updated normal-workspace runs completed together through the browser. Their complete financial outputs and coverage audits match the isolated candidate. Independent replay matches every daily cash balance, portfolio value and SPY value exactly across 12,380 valuations, including actual merger holdings. Filing-component and EPS-unit checks also pass. This establishes accounting consistency for those captured inputs, not completeness of the remaining history. See [validation](VALIDATION.md) and [remaining free-data gaps](FREE_DATA_GAPS.md).
