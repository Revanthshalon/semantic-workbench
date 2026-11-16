---
status: accepted
date: 2026-11-17
---

# The graph stores where source code is, not the code

`explore` and `node` return source code exactly as written. We could copy each node's source into the store, or keep only its file and span and read the file when asked. We keep only the file and span. The files are the truth and the store is derived data; a copy would double the store's size and could disagree with the files.

## Consequences

- A file that changed since the last index may no longer match its spans. A query compares the file's hash with the indexed one and marks such a file as changed in its answer.
- A query needs the workspace's files on disk. The store alone cannot answer `explore`.
