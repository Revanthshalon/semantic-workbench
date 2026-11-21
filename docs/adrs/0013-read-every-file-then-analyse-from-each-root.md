---
status: accepted
date: 2026-11-21
---

# An index reads every file, then analyses the graph from each root

Following the code from each binary's entry file, and reading only what it reaches, looks like the way to an accurate call flow. We read every file instead, one at a time and keyed by its content hash (stage 1). Then we analyse the finished graph without reading a file again (stage 2): we resolve references, carry types from callers, and record which roots reach each node. The accuracy a walk from the entry promised comes from analysis, and analysis works as well over the whole graph.

## Considered options

- **Read only what an entry reaches.** Rejected:
  - Code loaded by a string (`uvicorn "billing.api:app"`, `importlib`, plugin entry points) is invisible to the walk, and the graph would not say so.
  - A library with no binary would be read only in part.
  - Tests, scripts and migrations would vanish from `search` and `impact`.
  - Adding one import changes which files are reachable, so each binary's reachable set would have to be tracked and walked again. One changed file would no longer cost one read.
- **Read every file, and do no analysis beyond resolution.** Rejected: a call on a parameter with no annotation stays unresolved, and nothing says which binary runs which code.

## Consequences

- Stage 1 also records each call's arguments, each assignment's value and each return's value, by their shape, so stage 2 needs no file.
- Stage 2 runs in full at every index. Its results (edges resolved by `flow`, inferred types, reach, route paths) are deleted and written again in the same transaction. Running it only from what changed is Later.
- "Not reached" means not reached through resolved edges. It is a hint, never proof that code is dead.

Details: [python-parsing.md](../python-parsing.md#how-the-graph-is-built).
