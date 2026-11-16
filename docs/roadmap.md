# Roadmap

What ships when. It follows the [product vision](./product-vision.md). Each capability named here is described in the [capability map](./capability-map.md), by its id.

Nothing is released yet. No dates are set; the order is what is decided.

## Release 1: one language, the whole workspace

**Goal:** the [Acme Shop example](./example-workspace.md) works end to end. An AI tool connected through MCP can answer "what breaks if I change `Invoice` in `shared-api`?" across four projects.

**In scope**

- Python code graph.
- The workspace layer: projects, binaries, local dependencies, compose files, stacks, services, external services, networks, and hand-written links with their topics and queues.
- SQLite storage.
- The command line and the MCP server over stdio.
- Installation with Cargo and with Homebrew, on macOS and Linux.
- The graph changes only when `workbench index` is run.

**Out of scope:** everything under Release 2 and Later.

**Build order.** Each step leaves something that can be tested on its own.

| Step | Delivers | Capabilities | Plan |
|---|---|---|---|
| 1 | Domain types: identity, nodes, edges, file records, unresolved references | G1 to G8 | [`implementation-plan/`](./implementation-plan/00-overview.md), written |
| 2 | Configuration: load, validate, starter file | C1 to C10 | not written |
| 3 | SQLite store behind one port | S1 to S3 | not written |
| 4 | Workspace indexing: projects, binaries, local dependencies, compose, networks, links | W1 to W9 | not written |
| 5 | Python parsing and reference resolution, within and across projects | I1 to I6, I10 | not written |
| 6 | Queries: search, neighbours, impact, context pack, dependencies, status | Q1 to Q7 | not written |
| 7 | Command line and installation | U1 to U8, U11 | not written |
| 8 | MCP server | M1 to M3 | not written |

Step 4 comes before step 5 on purpose. The workspace layer needs no parser, so the config, the store and the first queries can be proven on real workspaces before any code is parsed.

**Done when**

- `workbench init`, `index`, `status`, `query` and `deps` work on the Acme Shop layout.
- An MCP client can run the impact question above and get all six steps of the walk in [graph-model.md](./graph-model.md).
- Indexing the same workspace twice produces the same graph.

## Release 2: the front end

**Goal:** a workspace with a TypeScript and Angular project is covered as well as a Python one.

- TypeScript code graph.
- Angular: components, routes and navigation.
- HTML, CSS and SCSS files inside a project.
- Local dependencies from npm, pnpm, yarn and bun files.

## Later

Wanted, not designed. The order within this list is not decided.

| Item | What it adds |
|---|---|
| Language servers: resolve references | During indexing, ask a language server where a call, import or type points when the parser cannot tell. The server starts inside the project's environment, as given by `projects[].environment` |
| Language servers: live lookups | The MCP server asks a language server at question time and returns the answer next to the graph |
| LLM: summaries | A command that writes a short description of each file, class and function onto its node |
| LLM: suggested links | A command that proposes runtime links from code, stored as inferred edges until a person confirms them |
| Links found in code | Topics, queues and HTTP calls read from source instead of declared by hand |
| Memgraph | A second store behind the same port |
| Go | A third language |
| Runtime scope for local dependencies | A third value next to `build` and `dev` |
| External services outside compose | A managed database or broker that no compose file describes |
| Confidence on inferred edges | A score, once something produces inferred edges |
| Automatic freshness | Re-indexing on use, or a file watcher. Release 1 is manual only |

## Reserved in the configuration

The configuration format already has fields for three Later items.

- `lsp`, at the workspace level and on a project, and `projects[].environment`: accepted, checked for shape, and otherwise ignored with a notice. `environment` holds the virtual environment and the activation command a language server needs to start inside a project.
- `semantic.llm`: accepted, checked for shape, and otherwise ignored with a notice.
- `storage.backend: memgraph` and the Memgraph fields: refused in Release 1, with a message that says only `sqlite` is supported.

Keeping the `lsp`, `environment` and `semantic` fields in the format now means a Release 1 configuration file stays valid later.
