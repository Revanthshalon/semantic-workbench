---
status: accepted
date: 2026-11-17
---

# What the tool cannot read is declared by hand, not guessed

Which service calls which, and which project publishes to which topic, cannot be read reliably from source code in the first release. We could infer these runtime links, or ask a person to write them down. We ask the person: links, binaries and the gaps in compose files are declared in `.workbench/config.yml`. A wrong edge in the graph costs more than a missing one, because an AI tool will act on it.

Amended by [ADR 0018](./0018-http-calls-are-matched-to-routes-links-stay-declared.md): Python HTTP calls whose path names a route are matched to it as code edges. Links themselves stay declared. Amended again by [ADR 0019](./0019-messages-are-matched-to-declared-topics.md): producers and consumers in Python are matched to declared topics and queues.

## Consequences

- Every edge records its provenance, so a reader can tell a fact read from source from one written by hand.
- Networks are read from compose files and used to check declared links: a link between two services that share no network gets a warning.
- Finding links in code (W11) and suggesting them with an LLM (W12) are on the roadmap. Their edges will carry the `Heuristic` provenance until a person confirms them.
