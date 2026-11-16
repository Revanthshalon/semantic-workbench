---
status: accepted
date: 2026-11-17
---

# A walk is done in the core, never inside the store

`impact`, `explore`, `callers` and `neighbors` all walk the graph. SQLite could do a walk in one recursive query, and a graph database such as Memgraph has its own walking language. We use neither. The store port offers only "the edges out of, or into, this set of nodes"; the core asks, decides where to go next, and asks again.

The rules of a walk are part of the product: which edge kinds `impact` follows, where it changes from code to runtime links, when a budget cuts it short. Kept in the core, they are written once and tested without a database, and they behave the same on every store.

## Consequences

- A walk costs one query per step instead of one in total. Each step uses an index, and walks are shallow.
- Adding Memgraph means implementing a small port, not rewriting the queries.
