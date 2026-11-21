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
- The `developer-support` mode of the MCP server, and the shared skills. `init` also writes the `mcp/` folder that operational support will read.
- The branch and commit of each project, recorded at every index.

**Out of scope:** everything under Release 2, Release 3 and Later.

**Build order.** Each step leaves something that can be tested on its own. The steps say what is delivered in what order. The [implementation plan](./implementation-plan/00-overview.md) cuts them into slices that several developers can build at once.

| Step | Delivers | Capabilities | Plan |
|---|---|---|---|
| 1 | Domain types: identity, nodes, edges, file records, unresolved references | G1 to G8 | specified in [domain-model.md](./domain-model.md) |
| 2 | Configuration: load, validate, and what `init` writes | C1 to C10, K1, K3 | [step 2](./implementation-plan/step-2-configuration.md) |
| 3 | SQLite store behind one port | S1 to S3 | specified in [storage-model.md](./storage-model.md) |
| 4 | Workspace indexing: projects, binaries, local dependencies, compose, networks, links | W1 to W9, W13, G10 | [step 4](./implementation-plan/step-4-workspace-indexing.md) |
| 5 | Python parsing and reference resolution, within and across projects | I1 to I6, I10 | [step 5](./implementation-plan/step-5-python-parsing.md) |
| 5b | All of Python, plain binaries and FastAPI (proposed) | I14 to I18, G11, G12 | [python-parsing.md](./python-parsing.md#plan) |
| 6 | Queries: explore, node, search, callers, callees, impact, neighbours, files, dependencies, status | Q1 to Q7, Q10, Q11 | [step 6](./implementation-plan/step-6-queries.md) |
| 7 | Command line and installation | U1 to U8, U11 | [step 7](./implementation-plan/step-7-command-line.md) |
| 8 | MCP server: the graph tools, the `developer-support` mode, the skills | M1 to M3, M5, M6, K2 | [step 8](./implementation-plan/step-8-mcp-server.md) |

Step 4 comes before step 5 on purpose. The workspace layer needs no parser, so the configuration, the store and the workspace indexer can be proven on real workspaces before any code is parsed.

The ground rules, X1 to X8 and X10, belong to no single step. Each step keeps the ones that apply to it.

**Done when**

- `workbench init`, `check`, `index`, `status`, `explore`, `node`, `query`, `callers`, `callees`, `impact`, `neighbors`, `files` and `deps` work on the Acme Shop layout.
- An MCP client can run the impact question above and get all six steps of the walk in [graph-model.md](./graph-model.md).
- One `explore` call about `Invoice` returns its source as written, the flow from billing's worker to ledger's consumer, and a blast radius that names all four projects.
- The Acme Shop graph passes every rule in [domain-model.md](./domain-model.md).
- Indexing the same workspace twice produces the same graph.

## Release 2: the front end

**Goal:** a workspace with a TypeScript and Angular project is covered as well as a Python one.

| Delivers | Capabilities |
|---|---|
| TypeScript code graph | I7 |
| Angular: components, routes and navigation | I8 |
| HTML, CSS and SCSS files inside a project | I9 |
| Local dependencies from npm, pnpm, yarn and bun files | W10 |
| The best practices of TypeScript and Angular, as a skill | K4 |

## Release 3: operational support

**Goal:** an AI tool connected in the `operational-support` mode can look into a deployed context, read the code behind what it sees, and propose the cause of an incident and a resolution. It can change nothing.

Releases 2 and 3 do not depend on each other and can be built in either order.

| Delivers | Capabilities |
|---|---|
| Reading and checking `mcp/config.yml` and the context files | C13, O1, O2 |
| Reaching a context through SSH to its virtual machine, by tunnel or by the VM's own client | O3 |
| Checking each project's indexed checkout against the context's release branch | O4 |
| Read-only tools for Kubernetes, Docker Compose, Postgres, Redis and Kafka | O5 to O9 |
| The graph tools in this mode, and the rule that every tool only reads | O10 |

This release is the first to use the network. It connects only to the virtual machine a context file names. The design is in [mcp-modes.md](./mcp-modes.md); the operational tools there are a proposal and are not confirmed. No build order is set.

## Later

Wanted, not designed. The order within this list is not decided.

| Item | What it adds | Capabilities |
|---|---|---|
| Language servers: resolve references | During indexing, ask a language server where a call, import or type points when the parser cannot tell. The server starts inside the project's environment, as given by `projects[].environment` | I11 |
| Language servers: live lookups | The MCP server asks a language server at question time and returns the answer next to the graph | Q8, M7 |
| LLM: summaries | A command that writes a short description of each file, class and function onto its node | I13, U9 |
| LLM: suggested links | A command that proposes runtime links from code, stored as inferred edges until a person confirms them | W12, U9 |
| Links found in code | Topics, queues and HTTP calls read from source instead of declared by hand | W11 |
| Search by meaning | Find nodes by what they do instead of by name | Q9 |
| Memgraph | A second store behind the same port | S4 |
| Go | A third language | I12 |
| Runtime scope for local dependencies | A third value next to `build` and `dev` | C11 |
| External services outside compose | A managed database or broker that no compose file describes | C12 |
| Confidence on inferred edges | A score, once something produces inferred edges | G9 |
| Automatic freshness | Re-indexing on use, or a file watcher. Release 1 is manual only | X9 |
| MCP over HTTP | A server for shared or remote use, next to stdio | M4 |
| Shell completions | Completion scripts for the `workbench` commands | U10 |

## Reserved in the configuration

The configuration format already has fields for three Later items.

- `lsp`, at the workspace level and on a project, and `projects[].environment`: accepted, checked for shape, and otherwise ignored with a notice. `environment` holds the virtual environment and the activation command a language server needs to start inside a project.
- `semantic.llm`: accepted, checked for shape, and otherwise ignored with a notice.
- `storage.backend: memgraph` and the Memgraph fields: refused in Release 1, with a message that says only `sqlite` is supported.

Keeping the `lsp`, `environment` and `semantic` fields in the format now means a Release 1 configuration file stays valid later.
