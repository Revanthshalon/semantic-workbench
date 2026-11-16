---
status: accepted
date: 2026-11-17
---

# A node id is computed: BLAKE3, 64 bits, 16 hex characters

The same node must get the same id every time the workspace is indexed, so that indexing twice updates nodes instead of duplicating them and edges keep pointing at the right node. The id is therefore a hash of what makes a node unique: its scope, its file path, its kind, its qualified name and an ordinal. We hash with BLAKE3 and keep the first 64 bits, written as 16 lowercase hex characters. BLAKE3 also hashes file content, at full length.

## Considered options

- **An id assigned by the database.** Rejected: edges could not be built before storing, and ids would change on every index.
- **The line number as an input.** Rejected: editing a line above a function would change its id.
- **Base64 of the inputs, so the id can be decoded.** Rejected: long, and the node already stores those values.
- **128 bits.** Rejected: twice the text in every answer an AI reads, for a risk that is already negligible.
- **SHA-256.** Rejected: slower on file content, which is hashed on every index. One algorithm for both jobs is simpler than two.

## Consequences

- Two nodes sharing an id is about a 1 in 40 million chance in a graph of a million nodes. Rule N6 stops the index if it happens, so a collision is loud, never silent.
- Renaming a project's id, or moving a file, gives its nodes new ids.

Details: [domain-model.md](../domain-model.md#node-identity).
