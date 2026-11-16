# Usage Guide

How Semantic Workbench is meant to be used, from an empty folder to an AI tool asking questions.

> **Nothing here runs yet.** This guide describes the first release as designed, so that the commands can be reviewed before they are built. Every command here is listed in the [capability map](./capability-map.md). Sample output is illustrative.

Related pages: [product vision](./product-vision.md), [configuration guide](./configuration-guide.md), [example workspace](./example-workspace.md), [roadmap](./roadmap.md).

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
workbench query impact shared-api:shared_api.models.Invoice
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
| `workbench query ...` | Asks the graph a question | no |
| `workbench deps` | Lists dependencies between projects | no |
| `workbench mcp` | Serves AI tools | no |

Flags every command takes: `--workspace <dir>`, and `-v` for more detail in messages. Commands that print results also take `--json`.

### `workbench init`

Creates `.workbench/` in the current folder with a starter `config.yml` and a `.gitignore` that keeps the graph file out of version control. Commit `config.yml`. It refuses to overwrite an existing configuration.

### `workbench check`

Reads the configuration and reports every problem it can find without indexing: unknown fields, bad ids, project ids that do not exist, paths that are nested inside one another. Use it after every edit of the configuration.

Some rules can only be checked against the compose files, for example that a named service exists. `index` checks those.

### `workbench index`

Builds the graph, or brings it up to date.

- A file whose content is unchanged since the last run is skipped.
- A changed file has its old nodes and edges removed and is read again.
- The workspace layer (projects, dependencies, compose files, networks, links) is rebuilt on every run. It is small.

Flags:

- `--force` rebuilds everything, ignoring what is stored.
- `--project <id>` limits the run to one project.

A file that fails to parse is skipped and logged. The run continues and still ends in success.

It ends with a summary: files read, files skipped, nodes and edges written, warnings, and files that failed to parse. Warnings do not stop the run. They are listed again by `status`.

### `workbench status`

Reports when the graph was last indexed, how many nodes, edges and files it holds, how many files have changed on disk since, the warnings from the last run, and the files that failed to parse.

```
Workspace   ~/acme/workspace
Indexed     2026-11-16 09:12, 4 projects, 3 stacks
Graph       1,284 nodes, 3,907 edges, 212 files
Changed     3 files since the last index. Run `workbench index`.
Warnings    1
  ledger-api: network `backbone` has no known real name
```

### `workbench query`

Asks the graph a question.

| Sub-command | Question it answers |
|---|---|
| `query search <text>` | Which nodes have this name? Filters: `--kind`, `--project` |
| `query show <node>` | What is this node: its kind, scope, origin and details |
| `query neighbors <node>` | What is directly related to it? Options: `--depth`, `--direction in\|out\|both`, `--edge <kind>` |
| `query impact <node>` | What is affected if this changes? Walks backwards across projects |
| `query context <task>` | Which nodes and code does an AI need for this task? Option: `--max-nodes` |

**Naming a node.** A `<node>` is either a node id, or a scope and a qualified name joined by a colon: `shared-api:shared_api.models.Invoice`. If the name matches several nodes, the command lists them and asks you to be more specific.

A walk has a budget of nodes and edges. When the budget cuts a walk short, the result says so.

### `workbench deps`

Lists the local dependencies between projects, each with where it came from.

```
billing-api -> shared-api    build   manifest (pyproject.toml)
ledger-api  -> shared-api    build   manifest (pyproject.toml)
```

Runtime links, such as an HTTP call or a topic, are not dependencies. See them with `query neighbors`.

### `workbench mcp`

Starts the MCP server on standard input and output. You do not run this yourself; your AI tool starts it.

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

**What the AI tool gets:** one tool per query, namely search, node, neighbours, impact, context, dependencies and status.

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
| A service appears as an external service but is yours | Its compose entry has no build context. Map it under `services` in the configuration |
| Two projects look unconnected but share a broker | Declare the topic or queue under `links` for both |
| A warning that a link's services share no network | Either the link is wrong, or a network name could not be read. Give its real name under `networks` |
| An AI tool's answers look out of date | Run `workbench index`. The server never does this for you |

## Not in the first release

TypeScript, Angular, HTML and CSS. Language servers. Anything that uses an LLM. Memgraph. Automatic re-indexing. Windows. The [roadmap](./roadmap.md) says what comes when.
