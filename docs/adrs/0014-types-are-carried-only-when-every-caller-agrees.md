---
status: accepted
date: 2026-11-21
---

# Types are inferred only when all the evidence agrees; text is carried to each caller

A parameter, return, field or name with no annotation leaves every call on it unresolved. Stage 2b gives such a node a class only when all of its evidence agrees:
- every call site in the workspace, for a parameter;
- every return, for a function;
- every assignment, for a field or a name bound more than once.

A callable used as a value (a callback, a provider, a route handler, a fixture) gets no parameter types, because its real callers are not all visible. The edges this resolves keep the `TreeSitter` provenance and record `resolved_by: flow` (ADR 0017). They are right whenever the workspace holds every caller.

Text works differently. Each caller of a helper passes its own path, so text is not agreed but copied: a hole that names a parameter is filled at each call site, and the copy belongs to the caller. That is how an HTTP call made inside a helper or a client class is matched to a route (ADR 0018).

## Considered options

- **Take the type of the most common caller, or of any caller.** Rejected: one test passing a `Mock`, or one caller passing a subclass, would give a wrong edge with nothing to show it.
- **Require callers to agree on text too.** Rejected: a helper such as `get(path)` is called with a different path each time, and each call is a different route.
- **A new provenance, `Flow`, or the existing `Heuristic`.** Rejected in favour of `resolved_by` (ADR 0017). A `Heuristic` mark would understate edges that are never wrong within what the workspace shows.

## Consequences

- A node goes from untyped to typed to conflicted, and never back, so the rounds always end. Each round carries types and text one call deeper. The rounds stop when one changes nothing, or after `analysis.flow_rounds` rounds: 10 by default, and `0` turns 2b off. Stopping at the limit raises the `FlowRoundLimit` warning.
- Every caller counts, including tests. A function that a test calls with another class gets no type.
- A reference resolved by 2b is kept, marked as resolved by flow. At every index the flow edges are deleted and 2b tries those references again, so a call resolved once is never lost.
- Stage 1 records every assignment and every return, by its shape, at module, function and class level, so 2b needs no file.
- Rule E12 ties every edge resolved by `flow` to an inferred type, and rule E13 allows `flow` on `Calls` and `Instantiates` only.

Details: [python-parsing.md](../python-parsing.md#stage-2b-carry-types-and-text-through-calls), [domain-model.md](../domain-model.md#inferred-type).
