# Performance and reproducibility

Measured locally on November 8, 2026, with engine 0.5.0. These are paired workload measurements on one Mac, not hardware-independent guarantees. Downloads and ordinary updates still prepare prices, sectors and SEC inputs together; there is no additional required refresh step.

## Measured computation and storage

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

## Filing acquisition and reuse

Two bounded accession readers share one request gate with at least 0.18 seconds between SEC request starts, including retries. This is below the SEC's [ten requests per second maximum](https://www.sec.gov/about/developer-resources). Requests use the configured identifying contact. Reports are streamed with a 96 MiB decompressed bound; an oversized report leaves the affected EPS units explicitly unverified rather than aborting unrelated issuer evidence or substituting today's class assumptions.

Completed accession checks persist individually. Reuse requires the same parser/evidence versions, XML engine versions, issuer identity, accession, filing date, primary filename and captured source fingerprints. Changed, missing or corrupt dependencies trigger verification again. Network failures still interrupt acquisition; they do not become false evidence that a class is incompatible. A stopped-worker recovery check retained both saved snapshots, all 558 completed parsed checks and all 1,498 captured observations from the interrupted acceptance download.

Initial acquisition still needs to obtain thousands of historical reports. Faster parsing and bounded concurrency do not eliminate that network cost. Warm-update and empty-cache acceptance observations are recorded in [validation](VALIDATION.md), separately from the paired computation benchmarks above. Local scripts and detailed timing/hash artifacts are retained under ignored `var/uat/`; source data and credentials are not committed.

The accepted 2016–November 2026 workspace, original source archive and five saved baselines occupy about 5.2 GB locally. Original filing captures are retained for audit and future reuse; they are a substantial part of the initial disk cost. Shared price blocks avoid copying the price history for each vintage. This is separate from the lower peak RAM measured during snapshot loading.
