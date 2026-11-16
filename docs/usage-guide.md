# Usage Guide

How Semantic Workbench is meant to be used, from an empty folder to an AI tool asking questions.

> **Nothing here runs yet.** This guide describes the first release as designed, so that the commands can be reviewed before they are built. Every command here is listed in the [capability map](./capability-map.md). Sample output is illustrative.

Related pages: [product vision](./product-vision.md), [configuration guide](./configuration-guide.md), [example workspace](./example-workspace.md), [domain model](./domain-model.md), [storage model](./storage-model.md), [modes, contexts and skills](./mcp-modes.md), [roadmap](./roadmap.md).

## The idea in one minute

1. You describe your workspace once, in `.workbench/config.yml`.
2. `workbench index` reads the configuration, your compose files and your source code, and builds a graph.
3. You, or an AI tool through MCP, ask the graph questions.
4. When your code changes, you run `workbench index` again. Nothing else changes the graph.

## Install

With Cargo, from a checkout of the repository:

```bash
cargo install --path .
```

Or with Homebrew:

```bash
brew install workbench
```

Either puts one binary, `workbench`, on your path. macOS and Linux are supported. Windows is not. The Homebrew formula does not exist yet, so its exact name may differ.

## Quick start

The layout is the one from the [example workspace](./example-workspace.md): four repositories cloned side by side, and one folder for the workspace.

```bash
cd ~/acme/workspace
workbench init          # writes .workbench/config.yml and .workbench/.gitignore
$EDITOR .workbench/config.yml   # list your projects; see the configuration guide
workbench check         # is the configuration valid?
workbench index         # build the graph
workbench status        # what is in it, and is it current?
workbench explore "how does an invoice get from billing to the ledger?"
workbench impact shared-api:shared_api.models.Invoice
```

## How a command finds the workspace

Every command needs to know which workspace it works on. It looks in this order:

1. The `--workspace <dir>` flag.
2. The `WORKBENCH_WORKSPACE` environment variable.
3. A `.workbench/` folder in the current folder.
4. A `.workbench/` folder in each parent folder, nearest first.

If none of these gives a workspace, the command stops with an error that names the flag and the variable.

Projects may sit outside the workspace folder. A command started inside such a project finds nothing by looking upwards, so it needs the flag or the variable. This matters most for the MCP server; see below.

## Commands

| Command | What it does | Changes the graph |
|---|---|---|
| `workbench init` | Sets up a workspace in the current folder | no |
| `workbench check` | Checks the configuration | no |
| `workbench index` | Builds or updates the graph | **yes** |
| `workbench status` | Reports what is in the graph and whether it is current | no |
| `workbench explore <question>` | Answers a question with source code, call flow and blast radius | no |
| `workbench node <node>` | Shows one node, or one file | no |
| `workbench query <text>` | Finds nodes by name | no |
| `workbench callers <node>` | Lists what calls a node | no |
| `workbench callees <node>` | Lists what a node calls | no |
| `workbench impact <node>` | Lists what is affected if a node changes | no |
| `workbench neighbors <node>` | Lists what is directly related to a node | no |
| `workbench files` | Lists the indexed files | no |
| `workbench deps` | Lists dependencies between projects | no |
| `workbench mcp` | Serves AI tools, in one mode | no |

Flags every command takes: `--workspace <dir>`, and `-v` for more detail in messages. Commands that print results also take `--json`.

### `workbench init`

Creates `.workbench/` in the current folder with:

- a starter `config.yml`;
- a `.gitignore` that keeps the graph file out of version control;
- `skills/`, the written guides every mode of the MCP server shares;
- `mcp/`, the files that describe each deployed context for the operational mode.

Commit all of it but the graph file. `init` refuses to run where a configuration already exists, and it never overwrites a skill or a context file. The [modes page](./mcp-modes.md) describes the two folders.

### `workbench check`

Reads the configuration and reports every problem it can find without indexing: unknown fields, bad ids, project ids that do not exist, paths that are nested inside one another. Use it after every edit of the configuration.

Some rules can only be checked against the files on disk, for example that a named service exists in a compose file. `index` checks those. The [configuration guide](./configuration-guide.md#what-is-checked-and-when) lists every rule and says which command checks it.

### `workbench index`

Builds the graph, or brings it up to date.

- A file whose content is unchanged since the last run is skipped.
- A changed file has its old nodes and edges removed and is read again.
- The workspace layer (projects, dependencies, compose files, networks, links) is rebuilt on every run. It is small.
- Files that `.gitignore` excludes are never read, nor are `.git`, `node_modules`, `.venv` and `.workbench`, nor anything a project's `exclude` patterns match.
- One `index` runs at a time per workspace; a second one stops with an error. Queries and the MCP server keep working while it runs, and see the graph as it was until it finishes.
- An index that fails changes nothing.

Flags:

- `--force` rebuilds everything, ignoring what is stored.
- `--project <id>` limits the run to one project.

A file that fails to parse is skipped and logged. The run continues and still ends in success.

It ends with a summary: files read, files skipped, nodes and edges written, warnings, and files that failed to parse. Warnings do not stop the run. They are listed again by `status`.

### `workbench status`

Reports when the graph was last indexed, how many nodes, edges and files it holds, the branch and commit each project was on, how many files have changed on disk since, the warnings from the last run, and the files that failed to parse.

The sample below is the Acme Shop workspace before the `networks` entry for ledger is added to the configuration:

```
Workspace   ~/acme/workspace
Indexed     2026-11-16 09:12, 4 projects, 3 stacks
Graph       1,284 nodes, 3,907 edges, 212 files
Changed     3 files since the last index. Run `workbench index`.
Warnings    1
  ledger-api: network `backbone` has no known real name
```

Ledger's compose file takes that network's name from a variable, so the tool cannot read it. Once the configuration gives the real name, as the [example workspace](./example-workspace.md#the-configuration) does, the warning is gone.

### Asking the graph

Eight commands ask the graph a question. None of them changes it.

**Naming a node.** A `<node>` is either a node id, or a scope and a qualified name joined by a colon: `shared-api:shared_api.models.Invoice`. If the name matches several nodes, the command lists them and asks you to be more specific.

**Budgets.** Every answer has a size budget. When the budget cuts an answer short, the answer says so and says what was left out.

### `workbench explore`

Answers a question in one call. This is the command an AI tool uses most, because one answer replaces a search and many file reads.

```bash
workbench explore "how does an invoice get from billing to the ledger?"
```

The question is free text. Workbench finds the nodes it names, in every project of the workspace, and returns three things:

- **Source.** The complete source of each relevant node, exactly as it is in the file, with line numbers, grouped by project and file.
- **Call flow.** How those nodes reach each other: calls and imports inside a project and across projects, and runtime links such as a topic between a publisher and a subscriber.
- **Blast radius.** For the main nodes, what would be affected by a change: the callers, the projects and the binaries, as locations without source.

Options: `--max-files` limits how many files' source is returned. `--project <id>` limits where the search starts; the flow and the blast radius still cross projects.

The graph stores where each node is, not its source. `explore` reads the source from your files when you ask. If a file has changed since the last index, its lines may no longer match, so the answer marks that file as changed and tells you to run `workbench index`.

### `workbench node`

Shows one node: its kind, scope, origin and details, its source, and what it directly calls and is called by.

```bash
workbench node shared-api:shared_api.models.Invoice
workbench node --file billing-api:src/billing/worker.py
```

With `--file <project>:<path>` it shows a file instead: its source with line numbers, and the nodes it holds. Options: `--no-source` leaves the source out. `--offset` and `--limit` choose which lines of a file are shown.

### `workbench query`

Finds nodes by name.

```bash
workbench query Invoice --kind class
```

Each result is a location, not source. Filters: `--kind`, `--project`. Option: `--limit`, 10 by default.

### `workbench callers` and `workbench callees`

`callers` lists the functions and methods that call a node, each with the file and line of the call. `callees` lists what the node calls. Both cross projects. On a class, creating an instance counts as a call.

Options: `--depth`, 1 by default, follows the callers of the callers. `--limit`, 20 by default.

### `workbench impact`

Lists what is affected if a node changes: its blast radius. It works in two parts.

1. **Through the code.** It walks backwards from the node over calls, imports, inheritance and references, across projects. `--depth` limits this part, 2 by default.
2. **Through what runs.** From each affected file it finds the binaries that include it, the services that run them, and then follows the runtime links: who subscribes to a topic the binary publishes, who connects to a service that runs it.

The result is grouped by project. Each entry shows the edges that led to it, with their provenance, so you can tell a fact read from source from a hand-written link. The [graph model](./graph-model.md#walking-the-graph) works one case through.

### `workbench neighbors`

Lists what is directly related to a node, over any kind of edge. Use it for what the commands above do not cover, such as the networks a service joins or the links a binary declares.

Options: `--depth`, `--direction in|out|both`, `--edge <kind>`.

### `workbench files`

Lists the indexed files, by project, each with its language and whether it was parsed. Filters: `--project`, `--failed` for files that failed to parse.

### `workbench deps`

Lists the local dependencies between projects, each with where it came from.

```
billing-api -> shared-api    build   manifest (pyproject.toml)
ledger-api  -> shared-api    build   manifest (pyproject.toml)
```

Runtime links, such as an HTTP call or a topic, are not dependencies. See them with `workbench neighbors`.

### `workbench mcp`

Starts the MCP server on standard input and output. You do not run this yourself; your AI tool starts it.

`--mode <name>` chooses what the server is for. `developer-support` is the default and the only mode in the first release. `operational-support` and `testing-support` are reserved names: the server refuses to start in them and says the mode is not available yet. The [modes page](./mcp-modes.md) describes all three.

## Connecting an AI tool

Add Workbench to your AI tool's MCP configuration. The usual shape is:

```json
{
  "mcpServers": {
    "workbench": {
      "command": "workbench",
      "args": ["mcp", "--workspace", "/home/you/acme/workspace"]
    }
  }
}
```

Give `--workspace` an absolute path. AI tools usually start the server inside whichever repository you have open, and that is often a project outside the workspace folder.

**What the AI tool gets:** one tool per query. Each gives the same answer as its command.

| MCP tool | Command | Use it to |
|---|---|---|
| `explore` | `workbench explore` | Answer a question in one call: source, call flow and blast radius. Start here |
| `node` | `workbench node` | Read one node or one file |
| `search` | `workbench query` | Find nodes by name |
| `callers` | `workbench callers` | See what calls a node |
| `callees` | `workbench callees` | See what a node calls |
| `impact` | `workbench impact` | See what a change affects |
| `neighbors` | `workbench neighbors` | See what is directly related to a node |
| `files` | `workbench files` | List the indexed files |
| `dependencies` | `workbench deps` | List dependencies between projects |
| `status` | `workbench status` | See what is in the graph and whether it is current |

**Skills.** The server also offers the skills in `.workbench/skills/`: a guide to using Workbench well, and the best practices of each language. They are the same in every mode, and your team can edit them.

**What the server never does:** it never changes the graph and never re-indexes. Every answer says when the graph was indexed and whether files have changed since, so the AI tool can tell you the graph is out of date.

## Keeping the graph current

The graph changes only when you run `workbench index`. This is a deliberate choice: an answer never depends on work happening behind your back.

- Run `workbench index` after pulling, switching branches or finishing a change.
- `workbench status` and every MCP answer tell you when files have changed since the last index.
- If the graph ever looks wrong, `workbench index --force` rebuilds it from the source.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The command did what was asked. `index` with warnings, or with files that were skipped because they failed to parse, still exits `0` |
| `1` | The command could not do it: no workspace found, an invalid configuration, a store that cannot be read |
| `2` | The command line itself was wrong: an unknown flag or a missing argument |

Results go to standard output. Messages, warnings and progress go to standard error, so output can be piped safely.

## Troubleshooting

| What you see | What to do |
|---|---|
| "no workspace found" | Run the command from the workspace folder, or pass `--workspace <dir>` |
| "unknown field" in the configuration | Check the spelling against the [configuration guide](./configuration-guide.md). Unknown fields are never ignored |
| "store was written by another version" | Run `workbench index --force` |
| "an index is already running" | Wait for it to finish. Queries still answer from the graph as it was |
| A service appears as an external service but is yours | Its compose entry has no build context. Map it under `services` in the configuration |
| Two projects look unconnected but share a broker | Declare the topic or queue under `links` for both |
| A warning that a link's services share no network | Either the link is wrong, or a network name could not be read. Give its real name under `networks` |
| An AI tool's answers look out of date | Run `workbench index`. The server never does this for you |

## Not in the first release

TypeScript, Angular, HTML and CSS. The operational mode of the MCP server. Language servers. Anything that uses an LLM. Memgraph. Automatic re-indexing. Windows. The [roadmap](./roadmap.md) says what comes when.
