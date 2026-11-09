# Performance and reproducibility

Measured locally on November 8–9, 2026. Measurements below distinguish engine 0.7.0 policy changes from earlier paired computation optimizations. These are observations on one Mac, not hardware-independent guarantees. Downloads and ordinary updates still prepare prices, sectors and SEC inputs together; there is no additional required refresh step.

## Current lightweight acquisition — engine 0.7.0

| Workload | Observed duration / size | Scope |
| --- | ---: | --- |
| Truly empty combined 2016–November 2026 download | **11m33** | Normal browser Download; 762 symbols, 1,783,977 rows, 23,512 annual records |
| Validated Update / repeated final-guard Update | **3m36 / 3m06** | Normal browser Update; 604 annual histories reused, zero company-facts downloads in each |
| Cold archive before saved backtests | **468 MB** | Decimal bytes, including captured structured source responses; zero parsed full EPS report records |

The earlier uninterrupted full acquisition took 72m42. The lightweight run uses about **84% less elapsed time**, but this intentionally changes the evidence workload and EPS eligibility; it is not a claim of identical exhaustive verification done faster. The old 0.6.0 normal warm Update took 5m56. Network conditions, cached market responses and concurrent local validation vary. The two accepted update observations are not forecasts for every weekly launch; the second preserves all price and annual blocks exactly while adding the merger-conflict findings.

Ordinary acquisition retains structured SEC facts, submissions and a small reviewed corporate-action source set instead of thousands of EPS report bodies. Annual submissions changes invalidate the financial cache; otherwise matching histories can be reused for up to 30 days. Major reviewed unequal-share/identity cases are blocked, while other class differences can remain. The [policy](LIGHTWEIGHT_EPS.md) explains that accuracy and refresh-delay tradeoff. Two issuer pipelines retain the shared eight-starts-per-second SEC gate. Backtest batches remain sequential to bound memory.

The acceptance update preserves 116 expired quote cohorts and their warnings, preventing current ticker reuse from extending old histories. It additionally backfills the previously empty DOW history; its unresolved pre-2019 identity is explicitly blocked. Unchanged annual blocks remain exactly equal. New snapshots still share price and annual blocks, and Data/Research remain the ordinary user flows.

The fully tested lightweight archive, including five backtests, compacted to **439 MB**, compared with the prior **5.282 GB** working archive. This intentionally removes bulk EPS evidence and superseded research; it is not identical source retention with stronger compression. The user then explicitly requested clearing all downloaded app data and backtests. The final normal database is **147 KB** and the entire `var` directory is about **143 MB**, mostly retained audit, reports and tool caches. A new Download starts with empty market/SEC caches. The already measured acceptance runs remain reports rather than populated app data.

## Earlier paired computation and storage measurements

| Workload | Before | After | Correctness check |
| --- | ---: | ---: | --- |
| Ten-year Value + Momentum calculation | 262.27 s | 98.31 s | Entire result exactly equal: 2,474 sessions, 514 decisions and 14,891 fills, including decisions, curves, trades, holdings and metrics |
| 29 actual inline filing covers | 6.75 s | 1.07 s | Complete dated share-class proofs exactly equal; another 17 legacy instance proofs also match |
| Load 1,782,709 saved price rows | 15.70 s | 14.47 s | Complete prices and normalized annual statements exactly equal |
| Peak memory during that load | 3,386.92 MiB | 2,514.50 MiB | Same dataset and digest |
| Save that snapshot | 13.11 s | 11.73 s | All 85,736 canonical monthly price blocks identical |
| 501 exchange-calendar range queries | 0.491 s | 0.0084 s | Exact date lists, including reversed and out-of-coverage ranges; returned lists remain independent |

The complete backtest control uses frozen pre-repair data. Its unchanged +286.72% return establishes computational equivalence, not the new corrected-input strategy baseline. These calculation times exclude loading the dataset and rendering the result.

Ranking comparisons cover 25 dates for each of five recipes. All 125 complete rankings, exclusions and component audits match. Total time for the 25 decisions fell from 5.32 to 2.86 seconds for momentum, 6.48 to 4.03 for low volatility, 10.42 to 2.19 for quality, 10.42 to 2.12 for quality value, and 12.33 to 4.37 for value + momentum. The implementation avoids repeatedly scanning every stock for each percentile, rebuilding the full exchange calendar, and traversing unrelated historical issues and price rows.

Snapshot I/O converts one security/month at a time rather than retaining a second universe-sized list of price dictionaries. Routine screen responses omit large nested source-ID lists; native exports retain complete provenance. Source audits remain available on demand.

For the 12-snapshot acceptance workspace, this screen projection reduced the serialized dataset portion from 6.76 MB to 4.39 MB (35%). The actual browser metadata download retained all 6,467 detailed filing checks, original observation IDs and source hashes. This measures payload size, not a general page-render timing guarantee.

## Historical 0.6.0 exhaustive filing acquisition and reuse

Engine 0.6.0 overlaps two issuer pipelines, each with two accession readers. All four readers share one request gate with at least 0.125 seconds between SEC request starts, including retries. This permits at most eight starts per second across the acquisition. This is below the SEC's [ten requests per second maximum](https://www.sec.gov/about/developer-resources). Requests use the configured identifying contact. Reports are streamed with a 96 MiB decompressed bound; an oversized report leaves the affected EPS units explicitly unverified rather than aborting unrelated issuer evidence or substituting today's class assumptions.

Completed accession checks persist individually. Reuse requires the same parser/evidence versions, XML engine versions, issuer identity, accession, filing date, primary filename and captured source fingerprints. Changed, missing or corrupt dependencies trigger verification again. Network failures still interrupt acquisition; they do not become false evidence that a class is incompatible. A stopped-worker recovery check retained both saved snapshots, all 558 completed parsed checks and all 1,498 captured observations from the interrupted acceptance download.

A controlled 20-issuer workload starts with empty local provider and parsed-evidence caches in every case. Issuer metadata and the requested accession set are frozen; filing bodies are fetched from the SEC. This measures the filing phase, not a complete universe download.

| Filing configuration | Elapsed | Peak process memory | Checks |
| --- | ---: | ---: | --- |
| Previous: one issuer, two readers, 0.18-second gate | 105.969 s | 1.60 GB | 213 proofs, 197 compatible |
| One issuer, four readers, same gate | 96.671 s | 1.51 GB | Exact same complete proof hash |
| One issuer, four readers, 0.125-second gate | 80.358 s | 2.14 GB | Exact same complete proof hash |
| Release: two issuers, two readers each, 0.125-second gate | 81.649 s | 1.65 GB | Exact same complete proof hash |

The release configuration is approximately **23% faster** than the prior configuration in this sample, with similar peak memory. It made 472 SEC starts versus 471 in the control, including one additional bounded retry. Measured minimum start spacing was 0.125018 seconds. Results are merged in symbol order; a slow issuer no longer prevents another issuer's pipeline from advancing. Backtest batches remain sequential in the worker to bound memory.

A real empty-workspace full acquisition also completed, with interrupted attempts retaining 1,540 and then 3,354 parsed checks before the ordinary Update workflow finished the combined snapshot. SEC transport stalls and monitoring interruptions prevent a valid uninterrupted end-to-end timing comparison with the older 72-minute run. No general full-download duration is promised. Its 85,762 price blocks, 22,330 normalized annual statements and 6,467 filing checks match the previous accepted financial inputs. Original source-capture hashes differ where SEC response bytes changed; those hashes remain preserved, and comparison excludes only the corresponding capture-hash fields.

Filing reads allow 60 seconds between response chunks, with ten-second connection/pool limits, three attempts and a fresh owned connection on retry. Supplied external/test transports are preserved. A changed source body still requires review. For reviewed primary action documents, a narrow content fingerprint ignores only the SEC-injected empty script immediately before the closing HTML body, including uppercase HTML/SGML wrappers; original bytes and raw hashes remain available. Economic text or other markup changes fail the review check.

A real normal-workspace Update with engine 0.6.0 completed in **5 minutes 56 seconds**, retaining identical price/annual blocks and filing checks. This is one observed warm run, separate from the controlled cold-filing comparison.

The historical 0.6.0 policy still needed to obtain thousands of reports. Faster parsing and bounded concurrency do not eliminate that network cost. Warm-update and empty-cache acceptance observations are recorded in [validation](VALIDATION.md), separately from the paired computation benchmarks above. Local scripts and detailed timing/hash artifacts are retained under ignored `var/uat/`; source data and credentials are not committed.

The historical 0.6.0 2016–November 2026 workspace, source archive and saved baselines occupied about 5.2 GB locally. Full filing captures were retained in that older archive and dominated its disk cost; the later explicitly authorized reset removed it. Shared price blocks avoid copying the price history for each vintage. This is separate from the lower peak RAM measured during snapshot loading.
