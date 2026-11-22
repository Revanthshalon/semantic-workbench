---
status: accepted
date: 2026-11-17
---

# The graph changes only when `workbench index` is run

Tools of this kind usually keep themselves current with a file watcher or by re-indexing on use. We do neither in the first release. The graph changes only when a person runs `workbench index`. No query and no UTCP tool ever writes. An answer therefore never depends on work happening behind the user's back, and a query is always fast and always repeatable.

## Consequences

- The graph can be out of date. So `status` and every answer say when the graph was indexed and whether files have changed since.
- One index is one transaction. Readers see the graph as it was until the index finishes, and an index that fails changes nothing.
- Only one index runs at a time per workspace.
- Automatic freshness stays on the roadmap as capability X9. It would be added next to manual indexing, not in place of it.
