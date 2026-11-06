# Manage saved research

Use **Manage saved research** in Research, Data, Portfolio → Research allocations, or Activity. Search by name, date, dataset or ID; filter a category; select one item or all shown items; then choose **Review deletion**. Backtests, dataset cards and frozen protocols also have a direct delete button.

The preview lists every affected item and the counts of snapshots, reports, protocols, validation trials and task records. Nothing is deleted until you check the acknowledgment and choose **Delete permanently**. **Keep items** closes the preview without making changes. Deletion cannot be undone; export anything you want to keep first.

## What can be removed

- Backtests and read-only allocation reviews, including their completed task record.
- Frozen validation protocols and their evaluations, trials and task records.
- A validation evaluation as a group, including all trials from that evaluation. Deleting its report does not restore an already consumed final test.
- Completed or failed research task history. Deleting an acquisition task record does not by itself delete the dataset it created.
- Dataset snapshots, with research that requires those inputs. A snapshot's required price parent cannot disappear beneath a retained combined snapshot; the preview includes that dependent snapshot too. Newer self-contained vintages can remain when an older provenance ancestor is removed. Shared price/filing blocks still needed by any retained snapshot are preserved.

Deleting a locked protocol retires its reservation; the preview explains this. A small record of previously attempted research dates remains even after deleting reports or protocols, so an explored period cannot be relabeled unseen. This marker retains dates and attempt identity, not deleted curves, trades or hypotheses.

## Protected records and concurrent work

Paper account history, plans, approvals, orders and account-connection records are excluded. A dataset used by a retained paper plan or pending paper input cannot be deleted here. Account replacement is separate from research cleanup.

Wait for background work before deleting its inputs. The service checks dependencies again inside the deletion transaction. If related research changed after preview, refresh the preview and review the new impact. Other research and shared inputs remain intact if a deletion is blocked or fails.

Deleted unshared data becomes reusable database space. The database file may not shrink immediately; deletion does not perform an automatic full-database rewrite.

## Apply the research corrections to new work

Research engine 0.4.0 allocates cash-constrained buy budgets across the full basket, rather than by ticker order. Existing saved results remain frozen.

New downloads and updates verify EPS share units against the source filing. To refresh an existing snapshot without downloading prices again, use **Data → Refresh SEC filings & share classes**, then select the newly completed snapshot in Research. First verification reads historical SEC documents and can take longer; captures are reused on retry. Coverage shows supported filing counts and exclusions. Earlier snapshots retain their original eligibility assumptions, with a warning when a new value-based run uses the legacy screen.
