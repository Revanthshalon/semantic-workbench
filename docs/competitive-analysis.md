# Competitive Analysis

How Semantic Workbench compares with two tools that also give AI coding tools a graph of the code: [codegraph](https://github.com/colbymchenry/codegraph) and [graphify](https://github.com/safishamsi/graphify). It follows the [product vision](./product-vision.md), and capability ids such as I20 refer to the [capability map](./capability-map.md).

> **Written on 2026-11-23**, from each project's DeepWiki and README. Both tools change quickly. A detail marked *unconfirmed* could not be checked from the material available.

## In short

- **codegraph** is the closest tool to Workbench inside a single project. Its query tools have the same names as ours (`explore`, `node`, `search`, `callers`, `callees`, `impact`, `files`, `status`), and [graph-model.md](./graph-model.md) already borrows its split between provenance and the rule that resolved an edge.
- **graphify** does a different job. It builds a map of a repository, including documents, PDFs, images and video, and uses an LLM for everything that is not code. It is for getting oriented, not for following calls.
- **Neither tool models what Workbench is built around:** one graph across several projects, and the layer of what runs (services, networks, topics, queues, HTTP calls matched to routes).

## Side by side

| | **Semantic Workbench** (design) | **codegraph** | **graphify** |
|---|---|---|---|
| Written in | Rust | TypeScript on Node.js, with a Rust parsing core | Python |
| Parsing | tree-sitter. Python in R1, TypeScript in R2 | tree-sitter. About 20 languages natively, more through a fallback path | tree-sitter for code. An LLM for documents, PDFs and images. Local Whisper for audio and video |
| Scope of a graph | **One graph for the workspace.** References are resolved across projects through import names ([ADR 0001](./adrs/0001-one-graph-rooted-at-the-workspace.md), I6) | **One index per project**, in `.codegraph/codegraph.db`. A `projectPath` argument picks the index. Nothing links one index to another | One graph per repository. `merge-graphs` joins graphs, prefixing node ids with `<repo>::` |
| What runs | Compose stacks, services, networks, Dockerfiles, commands, topics and queues. HTTP calls matched to routes (W14). Message producers and consumers matched to topics (W11) | Not modelled | Not modelled. Manifests and MCP configuration files are read, but not Compose files, routes or queues |
| Frameworks | FastAPI in depth: apps, routers, mounts, providers, parameter sources (I18). pytest fixtures (I22). argparse commands (I23) | FastAPI routes, with literal `include_router` prefixes composed. Django URL patterns. A name lookup for `Depends` | None documented |
| Resolution depth (Python) | Imports, re-exports, annotations, one step of local inference (I15). Types and text carried through callers, up to 10 call levels (I20). Reach from every entry point (I21) | Imports, re-exports through `__init__.py`, annotated parameters, return annotations, locals made from a project class, inherited methods. `self.attr` and flow through callers *unconfirmed* | Calls, imports and inheritance across files. Whether calls are resolved by type or only by name is *unconfirmed* |
| How an edge was made | Provenance required on every edge, and `resolved_by` on every resolved edge ([ADR 0017](./adrs/0017-every-resolved-edge-records-its-rule.md)). A confidence score is Later (G9) | A `provenance` column that may be empty. Its values are *unconfirmed* | `EXTRACTED` (score 1.0), `INFERRED` (with a score) or `AMBIGUOUS` (flagged for review) |
| Storage | SQLite: one nodes table and one edges table, full-text index, WAL. Rebuilt, never migrated ([ADR 0006](./adrs/0006-one-nodes-table-one-edges-table-typed-columns.md), [ADR 0008](./adrs/0008-no-migrations-the-store-is-rebuilt.md)) | SQLite: `nodes`, `edges`, `files`, `unresolved_refs`, full-text index, WAL. Very close to ours | NetworkX node-link JSON in `graphify-out/graph.json`. Optional export to Neo4j or FalkorDB |
| Node ids | blake3 of scope, path, kind, qualified name and ordinal, written as 16 hex characters ([ADR 0002](./adrs/0002-node-ids-are-computed-with-blake3.md)) | SHA-256, reportedly of qualified name and file path | A stable text id |
| Keeping the graph current | **Only when `workbench index` is run** ([ADR 0003](./adrs/0003-the-graph-changes-only-on-index.md), X1). Doing it automatically is Later (X9) | A file watcher with a two-second delay, a catch-up when the server reconnects, and a warning about files waiting to be indexed | A content-hash cache, `--update`, a watcher for code, and git hooks |
| How AI tools reach it | The command line, guided by a skill, for Claude Code and Copilot. A UTCP manual for other tools. No server ([ADR 0022](./adrs/0022-ai-tools-reach-the-graph-through-utcp.md), [ADR 0024](./adrs/0024-claude-code-and-copilot-use-the-command-line-guided-by-a-skill.md)) | An MCP server. Only `codegraph_explore` is offered by default. The other tools are switched on with `CODEGRAPH_MCP_TOOLS` | `/graphify` skills. An MCP server over stdio or HTTP. A Claude Code hook that points the agent at the graph before it searches files |
| Queries | `explore`, `node`, `query`, `callers`, `callees`, `impact` (with tests, API contracts and event contracts), `neighbors`, `deps`, `files`, `status` | `explore`, `node`, `search`, `callers`, `callees`, `impact` (depth 3 by default, with budgets and a flag when cut short), `files`, `status` | `query` (breadth-first or depth-first, with a token budget), `path` (shortest path), `explain`. No impact, callers or callees query |
| LLM and network | None in R1 (X7) | None | Only for non-code files, which are sent to the assistant's model or a configured backend |
| Beyond the code graph | A read-only operational mode in R3: Kubernetes, Compose on a VM, Postgres, Redis, Kafka | None | Leiden communities, most-connected nodes, surprising connections, a `GRAPH_REPORT.md`, an HTML view |

## Where Workbench is ahead

1. **Links across projects and across what runs.** A walk from a class can reach a route, the HTTP caller in another repository, and the consumer of a topic (Q4, Q13, Q14). Neither tool can do this. It is the reason Workbench exists.
2. **Depth of Python analysis.** Types carried through callers (I20), reach (I21), the tests to run for a change (Q12), and API and event contracts go well beyond either tool.
3. **Every edge says how it was made.** Requiring both provenance and `resolved_by` is stricter than codegraph's optional field, and needs no LLM, unlike graphify's inferred edges.

## Where they are ahead

1. **Languages.** codegraph reads about 20 languages today. Workbench reads Python in R1. A team outside Python will pick codegraph. That is acceptable only if the people we build for, a Python workspace with Compose files, are named plainly in the [product vision](./product-vision.md#who-it-is-for).
2. **Freshness.** Both tools update their graph by themselves. Workbench does not, on purpose ([ADR 0003](./adrs/0003-the-graph-changes-only-on-index.md)). The cost is a stale graph during an AI session. This is the largest risk to how Workbench feels in use.
3. **Getting oriented.** graphify's report gives an agent a picture of the repository before it asks anything. Workbench has no such overview.
4. **Non-code material.** graphify reads documents, PDFs and images. Workbench does not, and is not meant to.

## What to consider

Each item is a suggestion, not a decision. A decision goes into the capability map or an ADR.

| # | Suggestion | Why | Touches |
|---|---|---|---|
| 1 | Put "N files changed since the last index; run `workbench index`" at the top of every answer, not only in `status` | Lowers the cost of a manual index without breaking X1. M3 already records the data | M3, Q7 |
| 2 | Offer fewer UTCP tools by default: `explore` and a few others, the rest on request | codegraph offers only `explore` by default, a sign that agents do better with one way in | M2 |
| 3 | Show ambiguous references in answers, with their candidates, instead of dropping them | Like graphify's `AMBIGUOUS`. The unresolved references are already stored (G8) | G8, Q2, Q10 |
| 4 | A `workbench overview`: projects, services, the links between them and the most-connected code | Orientation, as graphify's report gives, built from the workspace layer neither tool has | Q, U, M |
| 5 | Prefix tool names in the UTCP manual, such as `workbench_explore` | A user running codegraph as well sees two `explore`, `callers` and `impact` tools | M2 |
| 6 | Say in the product vision which workspaces Workbench is for, and which it is not | The gap in languages is fine only if it is chosen | product vision |

## Sources

- codegraph: [repository](https://github.com/colbymchenry/codegraph), [DeepWiki: architecture](https://deepwiki.com/search/fae629b6-781f-4b27-9ada-f0ca277b792f), [DeepWiki: Python, impact and explore](https://deepwiki.com/search/2e4ac75c-498e-42f3-9680-3cacf9c56717)
- graphify: [repository](https://github.com/safishamsi/graphify), [DeepWiki: architecture](https://deepwiki.com/search/c5daaeae-eeb0-4a9c-8121-38abd9ab58f3), [DeepWiki: report and query](https://deepwiki.com/search/549e439f-060a-4355-8ca6-1a89372a943b), [InfoQ](https://www.infoq.com/news/2026/09/graphify-codebase-exploration/)
