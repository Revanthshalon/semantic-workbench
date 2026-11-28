# Spec map

The module specs of Release 1, and the order they are built in. Each module groups rows of the product [capability map](../capability-map.md) by their letter, so every spec traces back to capability ids.

The specs in this folder are the source of truth. Where a spec consolidates an older page in `docs/`, that page carries a line at its top pointing here, and the spec wins where the two differ. Every spec is written from [TEMPLATE.md](./TEMPLATE.md).

## Modules

| Module id | Responsibility | Capabilities | Depends on | Consolidates | Spec |
|---|---|---|---|---|---|
| `ground-rules` | Behaviour every command and every module shares | X1 to X8, X10 | none | capability map §X, [implementation plan overview](../implementation-plan/00-overview.md) | [SPEC-ground-rules.md](./SPEC-ground-rules.md) |
| `graph-model` | Domain types, ids, Build and Graph rules | G1 to G12 | `ground-rules` | [domain-model.md](../domain-model.md), [graph-model.md](../graph-model.md), ADRs 0002, 0012, 0016, 0017 | [SPEC-graph-model.md](./SPEC-graph-model.md) |
| `configuration` | Finding, reading and checking the configuration, and what `init` writes | C1 to C10, C14, C15 | `graph-model` | [configuration-guide.md](../configuration-guide.md), [step 2](../implementation-plan/step-2-configuration.md) | not written |
| `storage` | The store port, SQLite, `MemoryStore` | S1 to S3 | `graph-model` | [storage-model.md](../storage-model.md), ADR 0006 | not written |
| `skills` | The shared skills and their links in the workspace root | K1 to K3 | `configuration` | [modes.md](../modes.md), ADRs 0023, 0024 | not written |
| `workspace-indexing` | Projects, binaries, dependencies, compose, Dockerfiles, networks, links | W1 to W16 | `configuration`, `storage` | [example-workspace.md](../example-workspace.md), [step 4](../implementation-plan/step-4-workspace-indexing.md) | not written |
| `code-indexing` | Python parsing, resolution, flow, FastAPI, pytest, reach | I1 to I6, I10, I14 to I23 | `workspace-indexing` | [python-parsing.md](../python-parsing.md), [step 5](../implementation-plan/step-5-python-parsing.md) | not written |
| `queries` | `explore`, `node`, `search`, `callers`, `callees`, `impact`, `neighbors`, `files`, `deps`, `status` | Q1 to Q7, Q10 to Q14 | `storage` | [step 6](../implementation-plan/step-6-queries.md) | not written |
| `command-line` | The `workbench` commands and installation | U1 to U8, U11 | `queries`, `configuration` | [usage-guide.md](../usage-guide.md), [step 7](../implementation-plan/step-7-command-line.md) | not written |
| `utcp-manual` | The UTCP manual over the command line | M1 to M3, M5, M6, M8 | `command-line` | [utcp-manual.md](../utcp-manual.md), [step 8](../implementation-plan/step-8-utcp-manual.md) | not written |

Operational support (O, Release 3) gets its own module when Release 3 is specified.

## Build order

`ground-rules`, then `graph-model`, then `configuration` and `storage`, then `skills` and `workspace-indexing`, then `code-indexing`, then `queries`, then `command-line`, then `utcp-manual`.

This is the [roadmap](../roadmap.md)'s order. `queries` depends only on `storage`, but its tests run on the indexed Acme Shop graph, so it follows `code-indexing`.
