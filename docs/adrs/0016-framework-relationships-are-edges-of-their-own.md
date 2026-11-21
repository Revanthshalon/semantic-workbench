---
status: accepted
date: 2026-11-21
---

# What a web framework does with code is held by three edge kinds of their own, and a route's full path by a record of its own

A FastAPI app mounts routers, a router mounts routes, a route runs a handler, and a route or a provider has the framework call other providers. These are three code edge kinds: `Mounts` (with its prefix, which may be unknown), `Handles` and `Injects`. Each may join only certain kinds of node (rule E11). A route's full path joins prefixes from other files, so stage 2d computes it and stores it as a route path, with the binary that serves it. No route node changes.

## Considered options

- **Reuse `References`, with a role on the node.** Rejected: "which routes use this provider" would be a filter over every reference into the provider, and nothing would link a route to its app.
- **A route node with a `References` edge to its handler, and the prefixes composed into the route's name** (as codegraph does). Rejected: with no edge from a route to its router or app, "which binary serves this route" and "which routes move if this prefix changes" cannot be walked. Writing the composed path into route nodes also means rewriting nodes of unchanged files whenever a prefix changes.
- **Compute the full path at query time.** Rejected: `search` could not find a route by its full path.

## Consequences

- Edge kinds go from 22 to 25. `Mounts`, `Handles` and `Injects` always record `resolved_by: framework`.
- Route paths are rebuilt at every index with the other results of stage 2. A part the code computes is written `{?}`, and the path is marked incomplete.
- Reach follows `Mounts` downwards, then `Handles` and `Injects`, so a provider used only through `Depends` is still reached.

Details: [domain-model.md](../domain-model.md#framework-edges), [python-parsing.md](../python-parsing.md#stage-2d-route-paths).
