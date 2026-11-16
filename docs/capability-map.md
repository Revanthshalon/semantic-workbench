# Capability Map

Everything Semantic Workbench is meant to do, one row per capability. It follows the [product vision](./product-vision.md). The [roadmap](./roadmap.md) says when each row ships, the [usage guide](./usage-guide.md) shows the commands, and the [configuration guide](./configuration-guide.md) explains the fields. Terms are defined in [GLOSSARY.md](./GLOSSARY.md).

Nothing is built yet beyond the module scaffold and first drafts of the domain types.

## How to read a row

- **Id:** a stable name for the capability. The roadmap and future plans refer to it.
- **Release:** `R1` is the first release, `R2` the second, `Later` is wanted and not designed.
- **Decision:**
  - **Decided**: confirmed by the project owner. Every row is decided at present.
  - **Open**: needs a decision before it can be built. Open rows are collected at the end.
- **Where you meet it:** the command, MCP tool or configuration field through which a user touches the capability.

## At a glance

| Area | What it covers | R1 | R2 | Later |
|---|---|---|---|---|
| C. Configuration | Finding, reading and checking the workspace configuration | 10 | | 2 |
| W. Workspace indexing | Projects, dependencies, compose files, networks, links | 9 | 1 | 2 |
| I. Code indexing | Parsing source code and resolving references | 7 | 3 | 3 |
| G. Graph model | What a node and an edge are | 8 | | 1 |
| S. Storage | Where the graph is kept | 3 | | 1 |
| Q. Queries | The questions the graph can answer | 7 | | 2 |
| U. Command line | The `workbench` commands | 9 | | 2 |
| M. MCP server | How AI tools reach the graph | 3 | | 1 |
| X. Ground rules | Behaviour every command shares | 9 | | 1 |

## C. Configuration

A person describes the workspace once, in `.workbench/config.yml`.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| C1 | Find the workspace: look for `.workbench/` in the current folder, then in each parent. Otherwise use `--workspace` or `WORKBENCH_WORKSPACE`, and stop with an error if neither is given | R1 | Decided | every command |
| C2 | Read the configuration and refuse unknown fields | R1 | Decided | `index`, `check` |
| C3 | Write a starter configuration from the built-in template | R1 | Decided | `init` |
| C4 | List projects: id, path, language, dependency manager, import names. A relative path starts at the workspace root | R1 | Decided | `projects` |
| C5 | Declare a project's binaries by hand | R1 | Decided | `projects[].binaries` |
| C6 | Declare extra local dependencies by hand | R1 | Decided | `projects[].dependencies.local` |
| C7 | Declare runtime links by hand: HTTP, gRPC, topic, queue, database | R1 | Decided | `projects[].links` |
| C8 | Describe each stack: its compose files in order, the projects that use it and the service mapping. A stack is shared or belongs to one project | R1 | Decided | `compose`, `projects[].compose` |
| C9 | Set a stack's Compose name, and give a network its real name when the files cannot | R1 | Decided | `compose[].name`, `compose[].networks` |
| C10 | Check every cross-reference: project ids, binaries, services, stacks, networks | R1 | Decided | `check`, `index` |
| C11 | Runtime scope for local dependencies | Later | Decided | `dependencies.local[].scope` |
| C12 | Declare external services that no compose file describes | Later | Decided | not designed |

## W. Workspace indexing

The indexer turns the configuration, the dependency manager files and the compose files into nodes and edges. This layer needs no source code parser.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| W1 | Create a node for the workspace, each project and each binary | R1 | Decided | `index` |
| W2 | Discover local dependencies from uv and poetry files | R1 | Decided | `index`, `deps` |
| W3 | Merge discovered and declared local dependencies; the declared one wins | R1 | Decided | `index`, `deps` |
| W4 | Read services, build contexts and networks from compose files | R1 | Decided | `index` |
| W5 | Merge the compose files of a stack in order, a later file overriding an earlier one | R1 | Decided | `index` |
| W6 | Match each service to its project and binary. A service with no build context and no mapping is an external service | R1 | Decided | `index` |
| W7 | Record which services share a network | R1 | Decided | `index`, `query` |
| W8 | Create topic and queue nodes, and link edges, from declared links | R1 | Decided | `index`, `query` |
| W9 | Warn about: a link between services that share no network, a network name that cannot be resolved, a dependency path that is not a listed project | R1 | Decided | `index`, `status` |
| W10 | Discover local dependencies from npm, pnpm, yarn and bun files | R2 | Decided | `index`, `deps` |
| W11 | Find topics, queues and HTTP calls in source code | Later | Decided | not designed |
| W12 | Suggest runtime links with an LLM, stored as inferred edges until confirmed | Later | Decided | its own command, not designed |

## I. Code indexing

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| I1 | Parse Python into nodes and edges | R1 | Decided | `index` |
| I2 | Skip a file whose content has not changed since the last index | R1 | Decided | `index` |
| I3 | Parse a file again when its grammar was unavailable last time, even if its content is unchanged | R1 | Decided | `index` |
| I4 | Rebuild the whole graph on demand | R1 | Decided | `index --force` |
| I5 | Resolve references between files of one project | R1 | Decided | `index` |
| I6 | Resolve imports across projects through import names | R1 | Decided | `index` |
| I7 | Parse TypeScript | R2 | Decided | `index` |
| I8 | Add Angular nodes: components, routes, navigation | R2 | Decided | `index` |
| I9 | Index HTML, CSS and SCSS files inside a project | R2 | Decided | `index` |
| I10 | Skip files by pattern, on top of what `.gitignore` excludes | R1 | Decided | `projects[].exclude` |
| I11 | Resolve references with a language server, started inside the project's own environment | Later | Decided | `lsp` and `projects[].environment` fields, reserved |
| I12 | Parse Go | Later | Decided | `projects[].language` |
| I13 | Write node summaries with an LLM | Later | Decided | its own command, not designed |

## G. Graph model

Described in full in [graph-model.md](./graph-model.md). The implementation plan for this area is written: [`implementation-plan/`](./implementation-plan/00-overview.md).

| Id | Capability | Release | Decision | Plan part |
|---|---|---|---|---|
| G1 | A node id computed from scope, path, kind, qualified name and ordinal, the same on every run | R1 | Decided | 01 |
| G2 | Nodes for code: files, types, functions, imports, routes, components | R1 | Decided | 01, 02 |
| G3 | Nodes for the workspace: project, binary, stack, service, external service, network, topic, queue | R1 | Decided | 01, 02 |
| G4 | A node is either parsed from a file or declared with no file | R1 | Decided | 02 |
| G5 | Edge data that cannot disagree with the edge's kind | R1 | Decided | 03 |
| G6 | Rules for which node kinds a workspace edge may connect | R1 | Decided | 03 |
| G7 | Provenance on every edge. A fact the configuration supplies, such as a service's binary, is `Declared` | R1 | Decided | 03 |
| G8 | File records with a content hash and a parse status; unresolved references with their own identity | R1 | Decided | 04 |
| G9 | A confidence score on inferred edges | Later | Decided | none |

## S. Storage

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| S1 | Store and query the graph in a SQLite file inside `.workbench/` | R1 | Decided | `storage.path` |
| S2 | Keep the store behind one port, so another store can be added without touching the rest | R1 | Decided | internal |
| S3 | Record the store's format version. A store written by an incompatible version is refused with a message that says to run `index --force` | R1 | Decided | `index`, `status` |
| S4 | Memgraph as a second store | Later | Decided | `storage.backend`, reserved |

## Q. Queries

The questions the graph answers. The command line and the MCP server both call these.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| Q1 | Find nodes by name, with filters for kind and project | R1 | Decided | `query search` |
| Q2 | Show one node with its details, origin and scope | R1 | Decided | `query show` |
| Q3 | Walk outwards from a node, limited by depth, edge kinds and a node and edge budget; say when the walk was cut short | R1 | Decided | `query neighbors` |
| Q4 | Answer "what is affected if this changes", across projects | R1 | Decided | `query impact` |
| Q5 | Build a context pack for an AI task: the relevant nodes and code, within a size budget | R1 | Decided | `query context` |
| Q6 | List dependencies between projects, each with its provenance | R1 | Decided | `deps` |
| Q7 | Report the state of the graph: when it was indexed, how many nodes and edges, which files changed since, warnings, files that failed to parse | R1 | Decided | `status` |
| Q8 | Go to definition and find references through a language server, at question time | Later | Decided | `lsp` and `projects[].environment` fields, reserved |
| Q9 | Search by meaning instead of by name | Later | Decided | not designed |

## U. Command line

One binary, `workbench`. The exact commands and flags are in the [usage guide](./usage-guide.md).

| Id | Capability | Release | Decision | Command |
|---|---|---|---|---|
| U1 | Set up a workspace | R1 | Decided | `workbench init` |
| U2 | Build or update the graph, for the whole workspace or for one project | R1 | Decided | `workbench index`, `workbench index --project <id>` |
| U3 | See the state of the graph | R1 | Decided | `workbench status` |
| U4 | Check the configuration without indexing | R1 | Decided | `workbench check` |
| U5 | Ask the graph a question | R1 | Decided | `workbench query search`, `show`, `neighbors`, `impact`, `context` |
| U6 | List dependencies | R1 | Decided | `workbench deps` |
| U7 | Serve AI tools | R1 | Decided | `workbench mcp` |
| U8 | Machine-readable output from every command that prints results | R1 | Decided | `--json` |
| U9 | Summaries and suggested links, each with its own command | Later | Decided | not designed |
| U10 | Shell completions | Later | Decided | not designed |
| U11 | Install with Cargo or with Homebrew | R1 | Decided | `cargo install`, `brew install` |

## M. MCP server

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| M1 | Serve over stdio. The AI tool starts the process and stops it with the session | R1 | Decided | `workbench mcp` |
| M2 | One tool per query: search, node, neighbours, impact, context, dependencies, status | R1 | Decided | MCP tools |
| M3 | Never change the graph. Every answer says when the graph was indexed and whether files have changed since | R1 | Decided | every MCP tool |
| M4 | Serve over HTTP for shared or remote use | Later | Decided | not designed |

## X. Ground rules

Behaviour that every command shares.

| Id | Rule | Release | Decision |
|---|---|---|---|
| X1 | The graph changes only when `workbench index` is run. No query, and no MCP tool, re-indexes | R1 | Decided |
| X2 | Results go to standard output. Messages, warnings and progress go to standard error. In MCP mode standard output carries only the protocol | R1 | Decided |
| X3 | Exit code `0` for success, `1` for a failure such as a bad configuration or an unreadable store, `2` for a wrong command line | R1 | Decided |
| X10 | A file that fails to parse is skipped and logged. Indexing continues and still ends in success | R1 | Decided |
| X4 | `index` skips what `.gitignore` excludes, plus `.git`, `node_modules`, `.venv` and `.workbench` | R1 | Decided |
| X5 | One `index` at a time per workspace. Queries and the MCP server keep working while it runs | R1 | Decided |
| X6 | `init` writes `.workbench/.gitignore` so the graph file is not committed. The configuration file is meant to be committed | R1 | Decided |
| X7 | No network calls and no telemetry | R1 | Decided |
| X8 | macOS and Linux are supported. Windows is not | R1 | Decided |
| X9 | Keep the graph current automatically, on use or with a file watcher | Later | Decided |

## Open decisions

None at present.
