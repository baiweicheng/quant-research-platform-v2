# Updating and storing research snapshots

In **Data → Update a saved dataset**, select the downloaded price or price + SEC snapshot, then **Update dataset**. Follow Activity and choose the new snapshot in Research when it finishes. No paper configuration or strategy approval is needed. CSV and practice data use their existing import/generation workflows.

An update refreshes S&P membership from its sources, obtains recent prices/actions through the latest completed session, and backfills newly required symbols from the original history start. Existing symbols request only the last ten calendar days of the old snapshot plus subsequent sessions. The entire overlap is replaced, so corrected prices, removed bars, and changed/removed actions cannot leave stale values in the new vintage. Rows before that window remain frozen; **a full download is required to revalidate older prices/actions**. An incremental update is not a promise that a vendor made no older corrections.

For a selected SEC-enriched dataset, update refreshes the issuer directory, submissions and company facts, retaining filing accessions, original filings, amendments and the availability model. SEC publishes whole company-facts documents, so those requests are not a per-filing delta API. Unchanged received payloads and unchanged normalized statements share local storage. The new enriched snapshot references the newly updated prices; it never silently attaches updated filings to the old price parent.

Every research dataset is immutable. Source digests, parent IDs, overlap dates and acquisition evidence travel with each update. Results and frozen validation protocols continue referencing their original dataset. If SEC fails after prices were saved, Activity identifies the new price snapshot; retry **Add SEC fundamentals** on it. Transport or identity failures before publication preserve prior datasets. Provider observations from failed attempts remain for audit. Interrupted jobs can be retried after restart.

Existing identity/action issues outside the refreshed interval remain unresolved. Departed names remain in the captured data, dated membership filters eligibility, and required-member prices/actions still gate backtests. A different provider security ID stops incremental splicing. Public historical membership is retrospective, not certified as-known or survivorship-safe.

## Shared storage

Snapshots use SHA-256-addressed, compressed **symbol/month price blocks**, per-symbol filing blocks and shared raw provider-response blocks within the workspace SQLite database. A snapshot stores references to unchanged blocks; new sessions, corrections or amendments create new blocks. A changed month stores a replacement month, rather than just one changed row. Small per-snapshot metadata and provenance also consume space. Growth follows the new/revised data and audit history; it is neither exponential nor constant, and these are not full independent copies of the price history.

Legacy datasets remain readable. Updating them can convert their physical representation to shared blocks without changing logical data, fingerprints or results. The maintenance CLI `python -m aperture.storage_maintenance --db var/aperture.sqlite3` converts all saved datasets and deduplicates legacy provider observations, verifies every dataset's logical content and observation hash, then performs SQLite compaction/integrity checks. Close Aperture and finish background work first; the command refuses to run while its worker holds the database's process lock. It does not delete snapshots or trading records. SQLite may retain freed pages until compaction; transient WAL/temporary files can increase disk usage during writes.

Back up the **whole database** after shutting the app down, or use SQLite's backup API for a consistent online copy. Include the WAL in an ordinary file copy if it exists; a lone live database-file copy is unsafe. Shared blocks are not independently disposable. This format requires the updated application; keep a pre-migration backup if downgrade compatibility is required.

## Paper trading

Paper preparation saves a decision snapshot each time a review is prepared, normally weekly. It freezes the dataset ID alongside the strategy/policy/targets. The existing paper acquisition path refreshes its configured working window; the same shared storage deduplicates unchanged blocks in those snapshots. This update does not change paper scheduling or approval scope, and does not make paper acquisition use the research incremental-update command.

Daily account values, positions, cash and fills are separate account records. No new daily full research-snapshot schedule is created. Weekly automatic preparation needs matching approval and the running app; with the Mac off, no local capture runs. Broker-held accepted orders remain at the broker, and reopening reconciles fills. Membership changes still require roster adoption and new matching approval.
