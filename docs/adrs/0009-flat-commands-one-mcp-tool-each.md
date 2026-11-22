---
status: accepted
date: 2026-11-17
---

# Flat query commands, one MCP tool for each, and `explore` first

The first design grouped every question under `workbench query <sub-command>` and gave an AI tool a "context pack". We replaced it with flat commands, after the layout of colbymchenry/codegraph: `explore`, `node`, `query`, `callers`, `callees`, `impact`, `files` and `status`, plus `neighbors` and `deps` for the workspace layer, which codegraph does not have. Each command has one MCP tool that gives the same answer.

`explore` is the tool an AI is meant to start with. One call returns the complete source of the relevant nodes as written, the call flow among them and their blast radius, across every project. That replaces a search and many file reads, which is where an AI tool spends most of its context.

## Consequences

- `workbench query` is the name search. The MCP tool for it is called `search`.
- The command line and the MCP server call the same use cases, so neither can do something the other cannot.

Amended by [ADR 0022](./0022-ai-tools-reach-the-graph-through-utcp.md): the tools are described by a UTCP manual instead of an MCP server. Each tool is still one command with one answer. Where this page says MCP tool or MCP server, read UTCP tool and UTCP manual.

Details: [usage-guide.md](../usage-guide.md#commands).
