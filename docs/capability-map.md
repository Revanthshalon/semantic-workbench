# Capability Map

Everything Semantic Workbench is meant to do, one row per capability. It follows the [product vision](./product-vision.md). The [roadmap](./roadmap.md) says when each row ships, the [usage guide](./usage-guide.md) shows the commands, and the [configuration guide](./configuration-guide.md) explains the fields. Terms are defined in [GLOSSARY.md](./GLOSSARY.md).

Nothing is built yet beyond the module scaffold.

## How to read a row

- **Id:** a stable name for the capability. The roadmap and future plans refer to it.
- **Release:** `R1` is the first release, `R2` the front end, `R3` operational support, `Later` is wanted and not designed.
- **Decision:**
  - **Decided**: confirmed by the project owner.
  - **Open**: needs a decision before it can be built. Open rows are collected at the end.
- **Where you meet it:** the command, UTCP tool or configuration field through which a user touches the capability.

## At a glance

| Area | What it covers | R1 | R2 | R3 | Later |
|---|---|---|---|---|---|
| C. Configuration | Finding, reading and checking the workspace configuration | 12 | | 1 | 2 |
| W. Workspace indexing | Projects, dependencies, compose files, Dockerfiles, networks, links | 14 | 1 | | 1 |
| I. Code indexing | Parsing source code and resolving references | 16 | 3 | | 4 |
| G. Graph model | What a node and an edge are | 11 | | | 1 |
| S. Storage | Where the graph is kept | 3 | | | 1 |
| Q. Queries | The questions the graph can answer | 12 | | | 2 |
| U. Command line | The `workbench` commands | 9 | | | 2 |
| M. UTCP manual | How AI tools reach the graph | 6 | | | 3 |
| K. Skills | The written guides every mode shares | 3 | 1 | | |
| O. Operational support | Looking into a deployment, read-only | | | 10 | |
| X. Ground rules | Behaviour every command shares | 9 | | | 1 |

## C. Configuration

A person describes the workspace once, in `.workbench/config.yml`.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| C1 | Find the workspace: use `--workspace`, else `WORKBENCH_WORKSPACE`, else look for `.workbench/` in the current folder and then in each parent. Stop with an error if none of these gives one | R1 | Decided | every command |
| C2 | Read the configuration and refuse unknown fields | R1 | Decided | `index`, `check` |
| C3 | Write a starter configuration from the built-in template, together with the `skills/` and `ops/` folders. A file that is already there is never overwritten | R1 | Decided | `init` |
| C4 | List projects: id, path, language, dependency manager, import names. A relative path starts at the workspace root | R1 | Decided | `projects` |
| C5 | Declare a project's binaries by hand | R1 | Decided | `projects[].binaries` |
| C6 | Declare extra local dependencies by hand | R1 | Decided | `projects[].dependencies.local` |
| C7 | Declare runtime links by hand: HTTP, gRPC, topic, queue, database | R1 | Decided | `projects[].links` |
| C8 | Describe each stack: its compose files in order, the projects that use it and the service mapping. A stack is shared or belongs to one project | R1 | Decided | `compose`, `projects[].compose` |
| C9 | Set a stack's Compose name, and give a network its real name when the files cannot | R1 | Decided | `compose[].name`, `compose[].networks` |
| C10 | Check every cross-reference: project ids, binaries, services, stacks, networks | R1 | Decided | `check`, `index` |
| C11 | Runtime scope for local dependencies | Later | Decided | `dependencies.local[].scope` |
| C12 | Declare external services that no compose file describes | Later | Decided | not designed |
| C14 | Declare a binary's framework and its app object by hand, when the compose command and the entry file cannot tell. A framework is set on a binary only, never on a project | R1 | Decided | `binaries[].framework`, `binaries[].app` |
| C15 | Set how many call levels types and text are carried through calls, from 0 (off) to 100. Default 10 | R1 | Decided | `analysis.flow_rounds` |
| C13 | Read and check `ops/config.yml` and the context files: every field, every default, and that each project named under `branches` exists | R3 | Decided | `check` |

## W. Workspace indexing

The indexer turns the configuration, the dependency manager files and the compose files into nodes and edges. This layer needs no source code parser.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| W1 | Create a node for the workspace, each project and each binary. A binary's entry file gets a file node even when its language is not parsed yet | R1 | Decided | `index` |
| W2 | Discover local dependencies from uv and poetry files | R1 | Decided | `index`, `deps` |
| W3 | Merge discovered and declared local dependencies; the declared one wins | R1 | Decided | `index`, `deps` |
| W4 | Read services, build contexts and networks from compose files | R1 | Decided | `index` |
| W5 | Merge the compose files of a stack in order, a later file overriding an earlier one | R1 | Decided | `index` |
| W6 | Match each service to its project and binary. A service with no build context and no mapping is an external service | R1 | Decided | `index` |
| W7 | Record which services share a network | R1 | Decided | `index`, `neighbors` |
| W8 | Create topic and queue nodes, and link edges, from declared links | R1 | Decided | `index`, `neighbors`, `impact` |
| W9 | Warn about: a link between services that share no network, a network name that cannot be resolved, a dependency path that is not a listed project, a stack named after its folder that a link names. Each warning is stored with a code, the node it is about and a message | R1 | Decided | `index`, `status` |
| W10 | Discover local dependencies from npm, pnpm, yarn and bun files | R2 | Decided | `index`, `deps` |
| W11 | Find message producers and consumers in Python code (`kafka-python`, `aiokafka`, `confluent-kafka`, `pika`, `aio-pika`, `redis` streams) and match each to the declared topic or queue it uses, with the class it carries. A name with no declared topic is a warning. See [python-parsing.md](./python-parsing.md#messages) | R1 | Decided | `index`, `node`, `impact`, `status` |
| W12 | Suggest runtime links with an LLM, stored as inferred edges until confirmed | Later | Decided | its own command, not designed |
| W13 | Record the branch and commit each project is on, read from its own `.git` folder | R1 | Decided | `index`, `status` |
| W14 | Find HTTP client calls in Python code (`httpx`, `requests`, `aiohttp`, `websockets`, `urllib`, FastAPI's `TestClient`), including calls made inside helpers and client classes, and match each to the route it calls, across projects. Declared links narrow the candidates; a cross-project match with no declared link is a warning. See [python-parsing.md](./python-parsing.md#stage-2d-match-http-calls-to-routes) | R1 | Decided | `index`, `node`, `impact`, `status` |
| W15 | Link a compose service to the command it runs, from its `command` and `entrypoint`, else its Dockerfile's `CMD` and `ENTRYPOINT`, a `python -m` module, a file path or a script in `pyproject.toml`. An unknown command is a warning. See [python-parsing.md](./python-parsing.md#commands) | R1 | Decided | `index`, `node`, `impact`, `status` |
| W16 | Read each built service's Dockerfile: stages, `ENTRYPOINT`, `CMD`, `ARG` and `ENV`, with compose overrides and wrappers, to work out the command line it runs. It names the service's binary when nothing else does, its framework, and the command it invokes. See [python-parsing.md](./python-parsing.md#the-command-a-service-runs) | R1 | Decided | `index`, `node`, `status` |

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
| I14 | Read every Python definition and its details: stub files (`.pyi`), protocols, enums, parameters, fields, type aliases, visibility, annotations, defaults. See [python-parsing.md](./python-parsing.md#the-language-core) | R1 | Decided | `index`, `node` |
| I15 | Read every Python reference: base classes as extends or implements, overrides, types in annotations, functions used as values, `__all__`, imports that only serve type checking. Resolve through re-exports, annotated receivers and one step of local inference | R1 | Decided | `index`, `callers`, `impact` |
| I16 | Decide each binary's framework and app before parsing: from the configuration, else the compose command, else the entry file, else none. Warn when they disagree. A framework's rules still read every file that imports it | R1 | Decided | `binaries[].framework`, `binaries[].app`, `index`, `node`, `status` |
| I17 | Plain Python binary: its start through module-level code, the main guard, `python -m` and callbacks, and the code it reaches | R1 | Decided | `index`, `neighbors`, `impact` |
| I18 | FastAPI: apps, routers, routes, mounts, providers, parameter sources, models, middleware and hooks. A route's full paths and the binaries that serve them are computed after reading and stored, so search finds them | R1 | Decided | `index`, `node`, `query --kind route`, `impact` |
| I19 | More Python framework profiles: Flask, Django, Celery, Click, Typer | Later | Decided | `index` |
| I20 | Carry types and text through calls: parameters typed by every caller, return types, field types, names bound more than once, element types of collections and dicts, `*args` forwarding, and the text of values, carried to callers of helpers and into client classes. Calls on them resolve, marked as resolved by `flow`. Up to 10 call levels by default (`analysis.flow_rounds`). See [python-parsing.md](./python-parsing.md#stage-2b-carry-types-and-text-through-calls) | R1 | Decided | `index`, `callers`, `callees`, `node` |
| I21 | Reach: which binaries, named modules and tests may run each code node, from their entries over resolved edges; and the files no root reaches. See [python-parsing.md](./python-parsing.md#stage-2e-reach) | R1 | Decided | `index`, `node`, `files --unreached`, `impact` |
| I22 | pytest: test functions, and fixtures followed by name, with `usefixtures` and `autouse`. See [python-parsing.md](./python-parsing.md#tests) | R1 | Decided | `index`, `impact --tests` |
| I23 | `argparse`: programs and subcommands as `Command` nodes, with their options and handlers. See [python-parsing.md](./python-parsing.md#command-line-binaries-argparse) | R1 | Decided | `index`, `node`, `query --kind command` |

## G. Graph model

Explained in [graph-model.md](./graph-model.md) and specified, with the rules to validate against, in [domain-model.md](./domain-model.md). The **Slice** column names the slice of the [implementation plan](./implementation-plan/00-overview.md#the-slices) that builds the row.

| Id | Capability | Release | Decision | Slice |
|---|---|---|---|---|
| G1 | A node id computed from scope, path, kind, qualified name and ordinal, the same on every run, and written as 16 hex characters. One workspace node is the root, and every other node hangs below it through `Contains` | R1 | Decided | 1A, 1B |
| G2 | Nodes for code: files, types, functions, imports, routes, components | R1 | Decided | 1B |
| G3 | Nodes for the workspace: project, binary, stack, service, external service, network, topic, queue | R1 | Decided | 1B |
| G4 | A node is either parsed from a file or declared with no file | R1 | Decided | 1B |
| G5 | Edge data that cannot disagree with the edge's kind | R1 | Decided | 1C |
| G6 | Rules for which node kinds a workspace edge may connect | R1 | Decided | 1C |
| G7 | Provenance on every edge. A fact the configuration supplies, such as a service's binary, is `Declared` | R1 | Decided | 1C, 1E |
| G8 | File records with a content hash and a parse status; unresolved references with their own identity | R1 | Decided | 1D |
| G9 | A confidence score on inferred edges | Later | Decided | none |
| G10 | A checkout for each project: the branch and commit the graph was built from | R1 | Decided | 1D |
| G11 | Node data typed per kind, and checked against what the node's language can express | R1 | Decided | 1B |
| G12 | Edge kinds for frameworks: `Mounts` with its prefix, `Handles`, `Injects`, each with rules for the node kinds it joins | R1 | Decided | 1C, 1E |

## S. Storage

Specified in [storage-model.md](./storage-model.md): the schema, how an index is written and how the store is read.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| S1 | Store and query the graph in a SQLite file inside `.workbench/`: one table of nodes and one of edges for both layers, with a full-text index on names | R1 | Decided | `storage.path` |
| S2 | Keep the store behind one port, so another store can be added without touching the rest. Walks are done step by step above the port, never inside the store | R1 | Decided | internal |
| S3 | Record the store's format version. A store written by an incompatible version is refused with a message that says to run `index --force` | R1 | Decided | `index`, `status` |
| S4 | Memgraph as a second store | Later | Decided | `storage.backend`, reserved |

## Q. Queries

The questions the graph answers. The command line and the UTCP manual both reach these.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| Q1 | Find nodes by name, with filters for kind and project | R1 | Decided | `query` |
| Q2 | Show one node with its details, origin, scope and source, or one file with its source and the nodes it holds | R1 | Decided | `node` |
| Q3 | Walk outwards from a node, limited by depth, edge kinds and a node and edge budget; say when the walk was cut short | R1 | Decided | `neighbors` |
| Q4 | Answer "what is affected if this changes": the blast radius, through the code and then through what runs, across projects. A depth limit applies to the code part only | R1 | Decided | `impact` |
| Q5 | Answer a free-text question in one call: the complete source of the relevant nodes as written, the call flow among them and their blast radius, across every project, within a size budget. Source is read from the files, and a file changed since the last index is marked | R1 | Decided | `explore` |
| Q6 | List dependencies between projects, each with its provenance | R1 | Decided | `deps` |
| Q10 | List what calls a node and what a node calls, each with the place of the call, across projects. On a class, creating an instance counts as a call | R1 | Decided | `callers`, `callees` |
| Q11 | List the indexed files by project, each with its language and parse status | R1 | Decided | `files` |
| Q12 | List the test functions to run for a change, as pytest node ids, through reach, fixtures and API tests. See [python-parsing.md](./python-parsing.md#tests-to-run-for-a-change) | R1 | Decided | `impact --tests` |
| Q13 | Show the API contract of a class: the routes whose request or response uses it, directly or nested, their full paths, and the code in every project that calls them. See [python-parsing.md](./python-parsing.md#api-contracts) | R1 | Decided | `impact` |
| Q14 | Show the event contract of a class: the topics and queues that carry it, directly or nested, and the code in every project that sends and handles it. See [python-parsing.md](./python-parsing.md#event-contracts) | R1 | Decided | `impact` |
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
| U5 | Ask the graph a question | R1 | Decided | `workbench explore`, `node`, `query`, `callers`, `callees`, `impact`, `neighbors`, `files` |
| U6 | List dependencies | R1 | Decided | `workbench deps` |
| U7 | Print the UTCP manual that describes the query commands to AI tools | R1 | Decided | `workbench manual` |
| U8 | Machine-readable output from every command that prints results | R1 | Decided | `--json` |
| U9 | Summaries and suggested links, each with its own command | Later | Decided | not designed |
| U10 | Shell completions | Later | Decided | not designed |
| U11 | Install with Cargo or with Homebrew | R1 | Decided | `cargo install`, `brew install` |

## M. UTCP manual

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| M1 | Describe the query tools in a UTCP manual, a JSON document printed to standard output. The AI tool loads it and calls `workbench` directly. There is no server process | R1 | Decided | `workbench manual` |
| M2 | One tool per query: `explore`, `node`, `file`, `search`, `callers`, `callees`, `impact`, `tests`, `neighbors`, `files`, `dependencies`, `status`. Each is a call template over its command, with `--json`, so it gives the same answer as the command. Every argument is required, with a default, and `*` means no filter ([utcp-manual.md](./utcp-manual.md#arguments-all-required-with-defaults)) | R1 | Decided | UTCP tools |
| M3 | Never change the graph. Every answer says when the graph was indexed and whether files have changed since | R1 | Decided | every UTCP tool |
| M4 | Serve the manual by URL and make the commands reachable over HTTP, for shared or remote use | Later | Decided | not designed |
| M5 | Run in one mode, chosen on the command line. `developer-support` is the default and offers the graph tools | R1 | Decided | `workbench manual --mode <name>` |
| M6 | Reserve the names `operational-support` and `testing-support`. Until a mode ships, `workbench manual` refuses it, with a message | R1 | Decided | `workbench manual --mode <name>` |
| M7 | Add a language server's help to `developer-support`: definitions, references and diagnostics | Later | Decided | `lsp` and `projects[].environment` fields, reserved |
| M8 | Make a tool call safe against shell text in its arguments. The client is assumed to check each argument against the schema or insert it as given. As a second guard, every placeholder is quoted, every argument is allow-listed in the manual's schema, and a test runs a real shell. See [utcp-manual.md](./utcp-manual.md#the-solution-draft) | R1 | Decided | `workbench manual` |
| M9 | A `testing-support` mode for automation testing with Playwright. Not designed yet | Later | Decided | `workbench manual --mode testing-support` |

## K. Skills

Written guides an AI tool loads when it needs them, the same in every mode. Described in [modes.md](./modes.md#skills).

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| K1 | Write the shared skills into `.workbench/skills/`: how to use Workbench, and the best practices of Python. The `workbench` skill is how Claude Code and GitHub Copilot learn the query commands ([ADR 0024](./adrs/0024-claude-code-and-copilot-use-the-command-line-guided-by-a-skill.md)) | R1 | Decided | `init` |
| K2 | Link every skill in the folder into the AI platform's own skills folder, in the workspace root, as a relative link: `.claude/skills/` for Claude Code and `.github/skills/` for GitHub Copilot, both by default. Opt-in, never overwriting, safe to run again. The manual lists tools only. See [ADR 0023](./adrs/0023-skills-reach-ai-tools-through-links-in-the-workspace-root.md) | R1 | Decided | `init --enable-shared-skills`, `skills link`, `--platform` |
| K3 | Leave a team's skills alone: its edits and its own skills are never overwritten | R1 | Decided | `init` |
| K4 | Write the best practices of TypeScript and Angular | R2 | Decided | `init` |

## O. Operational support

The `operational-support` mode: looking into a deployment to find the cause of an incident. Described in [modes.md](./modes.md). The tools in O5 to O9 are the approved initial set; their arguments and limits are settled when Release 3 is built.

| Id | Capability | Release | Decision | Where you meet it |
|---|---|---|---|---|
| O1 | Name the contexts of the workspace and the default one. `init` writes `testing`, `staging` and `production` | R3 | Decided | `ops/config.yml` |
| O2 | Describe one context in one file: its release branches and how it is reached. The SSH password may be written in it. A pod or a Compose service on the VM is tied to a service of the graph by name, with a `services` entry when names differ | R3 | Decided | `ops/contexts/<name>.yml` |
| O3 | Reach a context only through SSH to its virtual machine. A connection either tunnels through the VM or runs the VM's own client | R3 | Decided | `ssh`, `access` |
| O4 | Check, project by project, that the indexed checkout is the context's release branch, and list the projects that differ in every operational answer | R3 | Decided | `context_status`, every operational tool |
| O5 | Read a Kubernetes namespace: pods, one resource in full, events and logs | R3 | Decided | `kube_pods`, `kube_describe`, `kube_events`, `kube_logs` |
| O6 | Read Docker Compose on the VM: the state of its services and their logs | R3 | Decided | `compose_status`, `compose_logs` |
| O7 | Run one read-only query on a named Postgres connection, with a time limit and a row limit | R3 | Decided | `postgres_query` |
| O8 | Read keys from a named Redis connection, with reading commands only | R3 | Decided | `redis_read` |
| O9 | Read Kafka: topics, how far each consumer group is behind, and the latest messages without committing an offset | R3 | Decided | `kafka_topics`, `kafka_lag`, `kafka_peek` |
| O10 | Offer the graph tools in this mode, for code context. Every tool of the mode only reads, and no configuration can change that | R3 | Decided | `workbench manual --mode operational-support` |

## X. Ground rules

Behaviour that every command shares.

| Id | Rule | Release | Decision |
|---|---|---|---|
| X1 | The graph changes only when `workbench index` is run. No query, and no UTCP tool, re-indexes | R1 | Decided |
| X2 | Results go to standard output. Messages, warnings and progress go to standard error. `workbench manual` writes only the manual to standard output. With `--json`, a command that succeeds writes nothing to standard error | R1 | Decided |
| X3 | Exit code `0` for success, `1` for a failure such as a bad configuration or an unreadable store, `2` for a wrong command line | R1 | Decided |
| X4 | `index` skips what `.gitignore` excludes, plus `.git`, `node_modules`, `.venv` and `.workbench` | R1 | Decided |
| X5 | One `index` at a time per workspace. Queries keep working while an index runs, and see the graph as it was until the index finishes. An index that fails changes nothing | R1 | Decided |
| X6 | `init` writes `.workbench/.gitignore` so the graph file is not committed. The configuration file is meant to be committed | R1 | Decided |
| X7 | No network calls and no telemetry. From Release 3 the `operational-support` mode connects to the virtual machine a context names, and to nothing else | R1 | Decided |
| X8 | macOS and Linux are supported. Windows is not | R1 | Decided |
| X9 | Keep the graph current automatically, on use or with a file watcher | Later | Decided |
| X10 | A file that fails to parse is skipped and logged. Indexing continues and still ends in success | R1 | Decided |

## Open decisions

| Rows | What needs deciding |
|---|---|
