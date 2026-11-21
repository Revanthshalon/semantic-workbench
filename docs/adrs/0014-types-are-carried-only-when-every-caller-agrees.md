---
status: accepted
date: 2026-11-21
---

# A type is carried from callers only when every caller agrees

A parameter with no annotation leaves every call on it unresolved. Stage 2b gives the parameter a class only when every call site in the workspace passes that same class, and only when the callable is never used as a value (a callback, a provider, a route handler). The edges this resolves keep the `TreeSitter` provenance and record `resolved_by: flow` (ADR 0017). They are right whenever the workspace holds every caller.

## Considered options

- **Take the type of the most common caller, or of any caller.** Rejected: one test passing a `Mock`, or one caller passing a subclass, would give a wrong edge with nothing to show it.
- **A new provenance, `Flow`, or the existing `Heuristic`.** Rejected in favour of `resolved_by` (ADR 0017). A `Heuristic` mark would understate edges that are never wrong within what the workspace shows.

## Consequences

- A parameter goes from untyped to typed to conflicted, and never back, so the rounds always end. Each round carries types one call deeper. The rounds stop when one changes nothing, or after `analysis.flow_rounds` rounds: 10 by default, and `0` turns 2b off. Stopping at the limit raises the `FlowRoundLimit` warning.
- Every caller counts, including tests. A function that a test calls with another class gets no type.
- A reference resolved by 2b is kept, marked as resolved by flow. At every index the flow edges are deleted and 2b tries those references again, so a call resolved once is never lost.
- Rule E12 ties every edge resolved by `flow` to an inferred type, and rule E13 allows `flow` on `Calls` and `Instantiates` only.

Details: [python-parsing.md](../python-parsing.md#stage-2b-carry-types-from-callers), [domain-model.md](../domain-model.md#inferred-type).
