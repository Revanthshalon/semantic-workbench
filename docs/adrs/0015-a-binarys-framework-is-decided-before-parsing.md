---
status: proposed
date: 2026-11-21
---

# A binary's framework is decided before parsing; a framework's rules read every file that imports it

Each binary's framework and app are decided in the workspace layer, before any code is parsed. They come from the binary's `framework` and `app` in the configuration, else from a compose command that runs it (`uvicorn billing.api:app`), else from a probe of its entry file, else `none`. A framework is never set on a project. Separately, the framework's rules read every file that imports the framework, in any project, because a router module is never an entry, and it may sit in a library with no binaries at all.

## Considered options

- **Derive the framework from the graph after parsing.** Rejected: the app would not be known when resolution runs, so a route's chain of mounts would have no fixed end, and the plain-binary rules could not tell a FastAPI entry from one that does nothing.
- **Run a framework's rules only on the files of binaries declared with it.** Rejected: a router in a library with no binaries would be missed, even when an app mounts it.
- **A project-level `framework` as the default for its binaries.** Rejected: it saves one line per binary, and costs a precedence rule and one more way for sources to disagree.
- **Let a compose command stand in for `entry`.** Rejected, pending review: the configuration's `entry` stays the authority, and a disagreement is the `EntryCommandMismatch` warning.

## Consequences

- Step 4 probes each binary's entry file through `LanguageParser::probe_framework`, which reads only imports and module-level statements. It is the only source code step 4 reads.
- A `Binary` node carries `framework`, `app` and `framework_source`. Disagreements raise `FrameworkMismatch`, `FrameworkAppNotFound` and `EntryCommandMismatch`.
- `projects[].framework` is removed from the configuration format. `framework: angular` moves onto each binary.

Details: [python-parsing.md](../python-parsing.md#how-a-binarys-framework-is-decided), [configuration-guide.md](../configuration-guide.md#binaries-runnable-entry-points).
