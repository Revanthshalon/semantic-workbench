---
status: proposed
date: 2026-11-21
---

# A type is carried from callers only when every caller agrees, and such edges are marked `Flow`

A parameter with no annotation leaves every call on it unresolved. Stage 2 gives the parameter a class only when every call site in the workspace passes that same class, and only when the callable is never used as a value (a callback, a provider, a route handler). The edges this resolves carry a new provenance, `Flow`, not `TreeSitter`. They are right whenever the workspace holds every caller, and a reader can tell them from edges read directly from the source.

## Considered options

- **Take the type of the most common caller, or of any caller.** Rejected: one test passing a `Mock`, or one caller passing a subclass, would give a wrong edge with nothing to show it.
- **Mark the edges `Heuristic`.** Rejected, pending review: `Heuristic` means "may be wrong" in general. These edges are never wrong within what the workspace shows, so they deserve more trust than a guess.
- **Mark the edges `TreeSitter`.** Rejected: it hides the assumption that every caller is in the workspace.

## Consequences

- A parameter goes from untyped to typed to conflicted, and never back. This guarantees the rounds end. They also stop after 5, with a `FlowRoundLimit` warning when they do.
- Every caller counts, including tests. A function that a test calls with another class gets no type.
- Rule E3 allows `Flow` on `Calls` and `Instantiates` only. Rule E12 ties every `Flow` edge to an inferred type.

Details: [python-parsing.md](../python-parsing.md#stage-2b-carry-types-from-callers), [domain-model.md](../domain-model.md#inferred-type).
