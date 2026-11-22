---
status: accepted
date: 2026-11-17
---

# The MCP server has modes, and the operational mode reaches a deployment only through SSH, read-only

The same graph serves two different jobs: writing code, and finding the cause of an incident in a running deployment. We give the MCP server a mode for each, chosen with `--mode`: `developer-support`, `operational-support`, and the reserved name `testing-support`. A mode decides which tools an AI tool is offered. Skills are shared by every mode.

`operational-support` looks into one context at a time, such as staging. It reaches a context through a single virtual machine over SSH, and from there the cluster, the databases and the broker. Every operational tool only reads, and that is a rule of the mode, not a setting.

Each context names the release branch of each project. The graph keeps the checkout of each project, so the mode can say, project by project, whether the code an AI reads is the code that is deployed.

## Considered options

- **One mode with every tool.** Rejected: an AI tool helping with code has no business holding a connection to production.
- **A file per mode.** Rejected: the mode needs nothing but its name. Only the contexts need files.
- **Direct connections to the cluster and the databases.** Rejected: each would have to be open to every developer's machine. One VM is one door to guard.
- **One graph per context, indexed from its release branch.** Rejected for now: it multiplies the store. Reporting a mismatch is enough to make an answer trustworthy.

## Consequences

- `operational-support` is the one part of Workbench that uses the network. It ships after Release 1, which stays fully local.
- A tool that writes can never be added to `operational-support` through configuration.
- The index must record a checkout for each project, which it does from Release 1.

Amended by [ADR 0022](./0022-ai-tools-reach-the-graph-through-utcp.md): a mode is the list of tools a UTCP manual shows, chosen with `workbench manual --mode`, and not a mode of a running server. The `mcp/` folder is now `ops/`. Every command, in every mode, only reads: that rule, not the list, is what keeps a mode safe.

Details: [modes.md](../modes.md).
