---
status: accepted
date: 2026-11-21
---

# Provenance stays coarse, and every resolved edge records the rule that resolved it

An edge's provenance says where its facts came from: source code read by a parser, a SCIP index, a manifest, a compose file, the configuration, or a guess. It does not say which rule connected a reference to its target, and an AI reading a walk needs that to judge each step. Every edge made by resolving a reference therefore records `resolved_by`: `import`, `self_member`, `same_file`, `project`, `cross_project`, `re_export`, `annotation`, `local_inference`, `inherited`, `flow` or `framework`. codegraph keeps the same distinction, as `provenance` and `resolvedBy`.

## Considered options

- **A new provenance value, `Flow`, for edges carried from callers.** Rejected: it explains only those edges, and mixes "where the facts came from" with "which rule connected them".
- **Reuse `Heuristic` for those edges.** Rejected: they are never wrong within what the workspace shows.
- **A confidence score per edge.** Rejected for now: every rule here is exact within the workspace, so a score would carry no information. It stays on the roadmap for `Heuristic` edges (G9).

## Consequences

- `resolved_by` is not part of an edge's identity (rule E6), and it is set only on parsed edges (rule E13).
- Stage 2 deletes and rebuilds the edges whose `resolved_by` is `flow` at every index.
- `callers`, `callees` and `impact` show how each step was resolved.

Details: [domain-model.md](../domain-model.md#how-an-edge-was-resolved), [graph-model.md](../graph-model.md#7-every-edge-says-how-it-came-to-exist).
