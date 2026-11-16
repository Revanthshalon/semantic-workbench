---
status: accepted
date: 2026-11-17
---

# One graph for the whole workspace, rooted at one workspace node

A workspace has several projects, and the questions that matter cross them: what breaks in `ledger-api` when `shared-api` changes. We keep one graph for the whole workspace. Its root is a single workspace node, and every other node hangs below it through `Contains`: projects, stacks and networks first, then binaries, files, services and code. A link between two projects is then an ordinary edge, and one walk can cross projects.

## Considered options

- **One database per project, plus a database of cross-project links.** Rejected: every cross-project question becomes a join across databases.
- **One graph per project, merged when queried.** Rejected: walking and ranking across projects would be slow and awkward.

## Consequences

- A file path is not unique in the graph, so every node has a scope, and the scope is part of its id.
- The root's qualified name is always `workspace`, so its id is the same on every machine.

Details: [graph-model.md](../graph-model.md), [domain-model.md](../domain-model.md#the-shape-one-tree-many-cross-links).
