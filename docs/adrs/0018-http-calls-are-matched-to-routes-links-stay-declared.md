---
status: accepted
date: 2026-11-21
---

# HTTP calls in code are matched to routes; runtime links stay declared

ADR 0004 put every runtime link in the configuration, because a wrong edge costs more than a missing one. Once routes and their full paths are in the graph, one kind of call can be matched exactly: a Python HTTP client call whose path names a route, such as `httpx.get(f"{BILLING_URL}/v1/invoices/{id}")`. Stage 2d matches such calls to route paths and records each match as a `Requests` edge from the calling code to the route, with `resolved_by: route_match`. This amends ADR 0004 without replacing it: links stay declared, and a match never creates a `ConnectsTo` link.

## Considered options

- **Keep finding HTTP calls for Later.** Rejected: the route paths are already stored, so matching is cheap, and it is what lets `impact`, the tests to run and API contracts reach code in other repositories.
- **Turn each match into a `ConnectsTo` link.** Rejected: a link is a runtime fact a person declares. A match is evidence from code, and two apps can serve the same path.
- **Take the first route that matches.** Rejected: that would be a guess. A call with more than one candidate, or none, is stored as an unmatched HTTP call with its candidates.

## Consequences

- Declared `http` links narrow a call's candidates to the routes served by the linked services. Code and configuration check each other.
- A call that matches a route served by another project's binary, with no declared link to it, raises the `HttpCallWithoutLink` warning, which names the link to add.
- `TestClient(app)` calls are matched within that app, so API tests reach the handlers they test, and `impact --tests` finds them.
- Calls made inside your own helper functions and client classes are matched too: stage 2b carries the path text to each caller, and the edge starts at the caller. Callers in TypeScript come with TypeScript parsing in Release 2. Topics and queues in code are matched the same way (ADR 0019).

Details: [python-parsing.md](../python-parsing.md#stage-2d-match-http-calls-to-routes), [graph-model.md](../graph-model.md#13-http-calls-in-code-are-matched-to-routes-and-links-stay-declared).
