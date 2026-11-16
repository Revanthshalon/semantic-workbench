---
status: accepted
date: 2026-11-17
---

# A warning is a structured record, not a line of text

The indexer raises warnings that do not stop a run, and `status` shows those of the last index, so they are stored. A warning is a record with a code, an optional subject node and a message. The code lets tests assert on a warning without matching text, makes `--json` output useful, and lets a later query show a warning next to the node it concerns.

## Considered options

- **Plain text lines.** Rejected: they can only be filtered or tested by matching text.
- **A flag on the node or edge concerned.** Rejected: it changes the node and edge types, and a warning about no node has nowhere to live.

## Consequences

- Every index replaces all stored warnings with the ones it raised.
- A file that fails to parse is not a warning. Its file record holds the failure.

Details: [domain-model.md](../domain-model.md#warning).
