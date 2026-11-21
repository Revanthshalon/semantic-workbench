---
status: accepted
date: 2026-11-22
---

# Command-line commands are nodes, and a service is linked to the command it runs

A plain binary is often a command-line program with subcommands, and a compose service usually runs one of them: `python -m ledger.consumer run`. Linking the service only to the binary makes `impact` name every service that runs the binary, even one that runs another command. So each `argparse` parser and subcommand becomes a `Command` node, with its options and a `Handles` edge to the code it runs. Stage 2f then links each compose service to the command its command line names, with an `Invokes` edge.

## Considered options

- **Leave commands as `References` from `set_defaults(func=...)`.** Rejected: the handler is reached, but nothing names the command or links it to a service.
- **Make a command a `Route` with a special method.** Rejected: a route is an HTTP endpoint, and its full path, binaries and HTTP matching would all have to skip it.
- **Build `Invokes` with the workspace layer.** Rejected: commands exist only after the code is parsed. The edge is computed in stage 2 and replaced at every index, like the other results of stage 2. It keeps the `Compose` provenance, because the fact it records comes from the compose file, and has `resolved_by: command_match`.

## Consequences

- Node kinds go from 32 to 33, and edge kinds from 26 to 29 with `Sends`, `Receives` (ADR 0019) and `Invokes`. `Handles` may also start at a `Command`.
- Manifests also yield their scripts (`[project.scripts]`, `[tool.poetry.scripts]`), so a command line that starts with a script name is understood.
- A command word that names no command raises `CommandNotFound`. A service that gives no command words runs the binary as a whole.
- A command line given only in a Dockerfile is not read, because the workspace layer reads compose files only.
- Click and Typer, as later framework profiles, give `Command` nodes too.

Details: [python-parsing.md](../python-parsing.md#command-line-binaries-argparse), [python-parsing.md](../python-parsing.md#commands).
