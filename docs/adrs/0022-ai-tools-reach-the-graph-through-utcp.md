---
status: proposed
date: 2026-11-22
---

# AI tools reach the graph through UTCP, not an MCP server

The first design served AI tools with an MCP server over stdio: `workbench mcp`, one tool per query, a mode chosen at start (ADR 0009, ADR 0011). We replace it with the Universal Tool Calling Protocol (UTCP). Workbench ships a UTCP manual: a description of its query tools, each as a call template over the existing `workbench` command. An AI tool loads the manual and calls `workbench` directly. There is no server process between them.

The command line already is the one core behind every answer, so the manual adds a description of it and no second implementation. The principle "one core, two doors" holds, with the command line and the manual as the doors. Every tool in every mode still only reads, and `status` and every answer still say how fresh the graph is.

## Considered options

- **Keep the MCP server, and add UTCP next to it.** Rejected by the project owner: two protocols to specify, build and test in Release 1, for one job.
- **Keep MCP only.** Rejected by the project owner.
- **A UTCP manual that points at an MCP server.** Rejected: it keeps the server and adds a layer.

## Consequences

- `workbench mcp`, the `rmcp` crate and the MCP server of step 8 are dropped from Release 1. Step 8 becomes the manual: `workbench manual --mode <name>` prints it as JSON, with one call template per query, the `developer-support` tools, and the skills. It adds no crate: the manual is a `serde_json` value.
- The `.workbench/mcp/` folder that `init` writes is renamed `.workbench/ops/`, and `templates/mcp/` is `templates/ops/`. The pages `mcp-modes.md` and `step-8-mcp-server.md` are renamed `modes.md` and `step-8-utcp-manual.md`. The filenames of ADRs 0009 and 0011 stay as they are, and each now carries a note pointing here.
- AI tools that speak only MCP cannot use Workbench in Release 1. An MCP adapter over the same use cases is listed under Later in the roadmap.
- A mode is the list of tools a manual shows. It is not a lock: a UTCP client runs `workbench` itself, so it can run any subcommand. What keeps every mode safe is that every command only reads (capability M3), and the store is opened read-only by the query commands.
- The operational tools of Release 3 are subcommands of `workbench ops`, each listed in the `operational-support` manual as a call template. `operational-support` still reaches a deployment only through SSH, read-only, from the machine where `workbench` runs.
- Results stay on standard output, messages on standard error, with `--json` as the form an AI tool reads (rule X2, capability U8). Every call template ends in `--json`.
- The manual does not change until `workbench manual` is run again, for example after an upgrade.

## Open points

Step 8, Task 1 settles the first three before any code is written.

- The exact UTCP version and manual format, and whether a Rust library exists or the manual is written by hand. The plan assumes a manual written by hand and has not checked the specification.
- How a UTCP client passes arguments to a command: as a list of values, or as a string a shell reads. If it is a string, every argument needs quoting and the design must be reconsidered.
- Whether a manual can carry anything for skills (K2). Proposed: the manual lists each skill with its file path and description, and the AI tool reads the file.
- Whether `status` should say that the manual was written by an older version of `workbench`.
