---
status: accepted
date: 2026-11-21
---

# A node kind carries its own data, and code nodes hold no language

The first model gave every node one flat set of optional fields: doc, signature, visibility, flags, decorators, return type and language. Nothing stopped an async service or a protected Python method. We make the data part of the kind, as an edge's data already is. Kinds that look alike share one data type (`Callable`, `TypeDecl`, `Member`, `RouteData`), a project carries its language and a binary its framework, and a table per language refuses values the language cannot express.

The language is not stored on code nodes. A code node's language is always its file's, so the file record holds it, and the project's main language sits on the `Project` node.

## Considered options

- **Keep the flat optional fields, and add a rule that workspace nodes leave them empty.** Rejected: it still allows a field that makes no sense for the kind, and the language rules would need checks across fields.
- **One data type per kind and language** (`PyFunction`, `TsFunction`, ...). Rejected: the number of types multiplies with each language. Languages differ in which values they allow, not in which fields exist.
- **Language on each code node, with a rule that it matches its file.** Rejected: a copy that can only disagree.
- **Language on the binary.** Rejected: a binary has one entry file inside its project, so it can never differ from the project.

## Consequences

- Every parser, and the store's row mapping, matches on the kind to reach its data.
- In Rust the data sits inside the kind's variant, `NodeKind::Function(Callable)`, not in a field beside the kind, so rule N8 is kept by the type. A fieldless `NodeKindName` serves filters, ids and storage.
- The `nodes` table keeps one column per field, grouped by data type, with checks that a kind fills only its own (ADR 0006).
- `Node::parsed` takes the file's language to check what the node may hold, and does not store it.

Details: [domain-model.md](../domain-model.md#node-data), [graph-model.md](../graph-model.md#10-a-node-kind-carries-its-own-data).
