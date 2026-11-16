---
status: accepted
date: 2026-11-17
---

# The store has no migrations; a new format means a rebuild

The store records a format version. When a newer `workbench` finds a store of another version, it could migrate it or refuse it. It refuses, with a message that says to run `workbench index --force`, which drops every table and builds the graph again. The store is derived data, so a rebuild is always correct and never loses anything, and migration code would be written and tested for no gain.

## Consequences

- An upgrade that changes the format costs one full index.
- Nothing that cannot be rebuilt from the workspace may ever be kept in the store. LLM summaries, which are on the roadmap and costly to produce, will need this decision revisited.
