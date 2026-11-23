---
status: accepted
date: 2026-11-17
---

# SQLite holds one table of nodes and one of edges, with typed columns

The graph has two layers, code and workspace, and seven of its 29 edge kinds carry data. We store both layers in one `nodes` table and one `edges` table, with one column per field. The data of an edge kind has its own typed columns, and the table checks that each is filled in for its own kind and for no other.

| Edge kind | Its columns |
|---|---|
| `Imports` | `import_specifier`, `import_alias`, `import_type_only` |
| `DependsOn` | `dependency_scope` |
| `ConnectsTo` | `protocol` |
| `Mounts` | `mount_prefix`, `mount_tags` |
| `Requests` | `request_method`, `request_path` |
| `Sends` | `message_name` |
| `Invokes` | `invoke_words` |

When this was accepted, three kinds carried data. `Imports` has since gained `type_only`, and `Mounts`, `Requests`, `Sends` and `Invokes` were added by ADRs [0016](./0016-framework-relationships-are-edges-of-their-own.md), [0018](./0018-http-calls-are-matched-to-routes-links-stay-declared.md), [0019](./0019-messages-are-matched-to-declared-topics.md) and [0020](./0020-commands-are-nodes-and-services-invoke-them.md). Each followed this decision with columns of its own.

## Considered options

- **Separate tables for the code layer and the workspace layer.** Rejected: a walk that crosses layers, which is the point of the tool, would need a union on every step.
- **Generic tables: an id, a kind and a JSON blob.** Rejected: filters and the name search get slow, and SQLite can enforce nothing.
- **One JSON column for edge data.** Rejected: typed columns can be checked by the table and filtered with an index, and only seven of the 29 kinds carry data.

## Consequences

- Workspace nodes leave the code-only columns empty.
- A kind that gains data later needs a new column, and so a new format version.

Details: [storage-model.md](../storage-model.md).
