---
status: accepted
date: 2026-11-17
---

# SQLite holds one table of nodes and one of edges, with typed columns

The graph has two layers, code and workspace, and three edge kinds carry data. We store both layers in one `nodes` table and one `edges` table, with one column per field. The data of an edge kind has its own typed columns (`import_specifier`, `import_alias`, `dependency_scope`, `protocol`), and the table checks that each is filled in for its own kind and for no other.

## Considered options

- **Separate tables for the code layer and the workspace layer.** Rejected: a walk that crosses layers, which is the point of the tool, would need a union on every step.
- **Generic tables: an id, a kind and a JSON blob.** Rejected: filters and the name search get slow, and SQLite can enforce nothing.
- **One JSON column for edge data.** Rejected: typed columns can be checked by the table and filtered with an index, and only three kinds carry data.

## Consequences

- Workspace nodes leave the code-only columns empty.
- A kind that gains data later needs a new column, and so a new format version.

Details: [storage-model.md](../storage-model.md).
