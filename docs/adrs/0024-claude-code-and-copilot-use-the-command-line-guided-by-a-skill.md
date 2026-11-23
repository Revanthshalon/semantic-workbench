---
status: accepted
date: 2026-11-23
---

# Claude Code and GitHub Copilot reach the graph through the command line, guided by the `workbench` skill

ADR 0022 gives AI tools a UTCP manual that describes the `workbench` commands. The AI tools the team uses, Claude Code and GitHub Copilot, do not load UTCP manuals: they speak MCP, and they can run shell commands. ADR 0023 already links the shared skills into their folders. So in Release 1 these two tools reach the graph by running `workbench` themselves, with `--json`. The `workbench` skill tells them which command answers which question, and in what order. The UTCP manual stays, as the door for AI tools that do speak UTCP.

## Considered options

- **A UTCP-to-MCP bridge.** Rejected for Release 1: a third-party program each user installs and keeps working, between the AI tool and a command line it can already run.
- **An MCP adapter in Release 1.** Rejected: a second protocol to build and test, which ADR 0022 turned down. It stays under Later in the roadmap.
- **Drop the UTCP manual.** Rejected: it costs little, it is already planned, and it serves any AI tool that speaks UTCP.

## Consequences

- The `workbench` skill is part of the product, not an extra. It names each query command, when to use it, how to name a node, and what to do when an answer says the graph is out of date. It is written by `init` (K1) and linked by `init --enable-shared-skills` or `skills link` (ADR 0023).
- The AI tool writes the command line itself, so the manual's allow-list patterns do not apply on this path. What keeps it safe is the rule that every query command only reads (M3), and that the query commands open the store read-only.
- Every query command's `--json` output is what these AI tools read. Rule X2 already keeps standard error empty when a command with `--json` succeeds.
- The command line's own defaults apply. The manual's draft defaults matter only to UTCP clients.
- The AI tool must be opened at the workspace root to see the linked skills. From there, `workbench` finds the workspace by itself, so no `--workspace` is needed.

Amends [ADR 0022](./0022-ai-tools-reach-the-graph-through-utcp.md). Details: [usage-guide.md](../usage-guide.md#connecting-an-ai-tool), [modes.md](../modes.md#developer-support).
