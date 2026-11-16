# Domain Model

The types of the knowledge graph and the rules they must keep. This is the page to implement against and to validate against.

[graph-model.md](./graph-model.md) explains why the model looks this way. This page says exactly what it is. [storage-model.md](./storage-model.md) says how it is kept in SQLite. Terms are defined in [GLOSSARY.md](./GLOSSARY.md). The running example is the [Acme Shop workspace](./example-workspace.md).

> **Nothing here is written yet.** The types belong in `src/domain`. They depend on nothing outside it: no SQLite, no parser, no configuration loader.

Every rule has an id, so a test can name the rule it proves. The last column of each rule table says where the rule is enforced:

- **Build**: building the value is refused. A broken value can never exist.
- **Graph**: the rule needs the whole graph, so it is checked by one `validate` pass over a finished graph. Tests run it, and `index` runs it before it writes.

## The shape: one tree, many cross-links

The graph has one root, the workspace node. Everything else hangs below it through `Contains` edges, so every node can be reached from the root and every node has exactly one parent.

```
Workspace
├── Project
│   ├── Binary
│   └── File
│       └── code nodes: Module, Class, Function, ...
│           └── nested code nodes: Method, Field, Parameter, ...
├── Stack
│   ├── Service
│   ├── ExternalService
│   │   ├── Topic
│   │   └── Queue
│   └── Network          (only when its real name is unknown)
└── Network              (when its real name is known)
```

The tree says what exists and where it belongs. Every other edge kind is a cross-link between two nodes of the tree: a call, an import, a dependency, a runtime link. Cross-links are what a query walks.

## Value types

Small types that check their own content. Each is refused at build time when its content breaks the rule.

| Type | Holds | Rule |
|---|---|---|
| `ProjectId` | A project's id | Kebab-case: lowercase letters and digits, in groups joined by single hyphens |
| `ComposeName` | A stack's Compose name | Lowercase letters, digits, `-` and `_`; starts with a letter or digit |
| `RelPath` | A path to a file | Relative, uses `/`, not empty, no `.` segments. `..` segments are allowed only at the start |
| `ContentHash` | The BLAKE3 hash of a file's bytes | All 256 bits, as 64 lowercase hex characters. It is never shown to a user |
| `NodeId` | A node's identity | Computed, never assigned: 64 bits, as 16 lowercase hex characters such as `9f2c41d07ab35e18`. See [Node identity](#node-identity) |
| `Span` | A region of a file | Start line, start column, end line, end column. Lines count from 1, columns from 0. The start is not after the end |
| `Site` | One place in a file | A `RelPath`, a line and a column, counted as in `Span` |

## Scope

What a node belongs to. The scope is part of the node's id.

| Scope | Carries | Nodes that have it |
|---|---|---|
| `Workspace` | nothing | The `Workspace` node, every `Project`, every `Stack`, a `Network` whose real name is known |
| `Project` | a `ProjectId` | The project's `Binary` nodes, its `File` nodes and all code nodes |
| `Stack` | a `ComposeName` | The stack's `Service` and `ExternalService` nodes, their `Topic` and `Queue` nodes, a `Network` whose real name is unknown |

A `RelPath` on a node or an edge starts from the scope's folder: the project's root for a `Project` scope, the workspace root for the other two. Only a path that starts from the workspace root may begin with `..`.

## Origin

Where a node came from. It is one of two things.

| Origin | Carries | Used for |
|---|---|---|
| `Parsed` | A `RelPath` and a `Span` | A node read from a file: code, and whatever a compose file states |
| `Declared` | nothing | A node that exists because the configuration says so |

## Node

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `NodeId` | yes | Computed from the fields below |
| `kind` | `NodeKind` | yes | One of the 32 kinds listed in [graph-model.md](./graph-model.md#node-kinds) |
| `name` | text | yes | The short name, such as `Invoice` |
| `qualified_name` | text | yes | The full name within the scope, such as `shared_api.models.Invoice` |
| `scope` | `Scope` | yes | What the node belongs to |
| `origin` | `Origin` | yes | Parsed or declared |
| `language` | `Language` | no | The language of a code node |
| `doc` | text | no | The doc string |
| `signature` | text | no | The declaration as written |
| `visibility` | `Visibility` | no | Public, private, protected or internal |
| `is_exported`, `is_async`, `is_static`, `is_abstract` | flag | no | Each defaults to false |
| `decorators`, `type_parameters` | list of text | no | Each defaults to empty |
| `return_type` | text | no | The return type as written |

The optional fields are filled in for code nodes and left empty for workspace nodes. A node holds no timestamp and no copy of the source code. Source is read from the file through the node's span when a query needs it.

### Node identity

The id is a hash of five inputs:

1. The scope: its type, and the `ProjectId` or `ComposeName` it carries.
2. The path from the origin, or nothing for a declared node.
3. The kind.
4. The qualified name.
5. The ordinal: how many earlier nodes in the same file share the first four inputs. The first has `0`.

The hash is BLAKE3, and the id is its first 8 bytes. Each input is written with its length in front of it before hashing, so two different sets of inputs can never produce the same bytes.

An id of 64 bits is short enough for an AI to read and repeat. Two nodes sharing one is about a 1 in 40 million chance in a graph of a million nodes, and rule N6 stops the index if it ever happens.

### Qualified names

| Kind | Qualified name | Example |
|---|---|---|
| `Workspace` | Always `workspace`. The `name` is the workspace root's folder name | `workspace` |
| `Project` | The project id | `billing-api` |
| `Binary` | The binary's name | `worker` |
| `Stack` | The Compose name | `ledger` |
| `Service`, `ExternalService` | The service's name in its compose file | `api` |
| `Network` | The real name when known, else the name in the compose file | `acme-backbone` |
| `Topic`, `Queue` | The external service's name, `/`, the topic or queue name | `kafka/invoice.created` |
| `File` | The file's path | `src/billing/worker.py` |
| Other code kinds | The language's own dotted path | `shared_api.models.Invoice` |

### Node rules

| Id | Rule | Enforced |
|---|---|---|
| N1 | `name` and `qualified_name` are not empty | Build |
| N2 | The id equals the hash of the five inputs. A node cannot be built with any other id | Build |
| N3 | The scope suits the kind, as in the [Scope](#scope) table | Build |
| N4 | A code node is always `Parsed`. `Workspace`, `Project`, `Binary`, `Topic` and `Queue` are always `Declared`. The other workspace kinds may be either | Build |
| N5 | Building the same node twice from the same inputs gives the same id | Build |
| N6 | No two nodes in a graph share an id | Graph |
| N7 | There is exactly one `Workspace` node | Graph |

## Edge

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source` | `NodeId` | yes | The node the edge starts at |
| `target` | `NodeId` | yes | The node the edge ends at |
| `kind` | `EdgeKind` | yes | One of the 22 kinds listed in [graph-model.md](./graph-model.md#edge-kinds), with its data |
| `site` | `Site` | no | Where in a file the relationship occurs, when it has a place |
| `provenance` | `Provenance` | yes | How the edge came to exist |
| `note` | text | no | The free text of a hand-written dependency or link |

### Edge data

The data is part of the kind, so a kind can never carry another kind's data.

| Kind | Data |
|---|---|
| `Imports` | `specifier`: the import as written. `alias`: the local name it is bound to, optional |
| `DependsOn` | `scope`: `Build` or `Dev` |
| `ConnectsTo` | `protocol`: `Http`, `Grpc` or `Database` |
| The other nineteen | none |

### Provenance

| Value | Meaning | Kinds that carry it in Release 1 |
|---|---|---|
| `TreeSitter` | Read from source code by a parser | Every code kind |
| `Manifest` | Read from a dependency manager's files | `DependsOn` |
| `Compose` | Read from a compose file | `Runs`, `BuiltFrom`, `Joins`, `Uses` |
| `Declared` | Written by hand in the configuration | `DependsOn`, `Uses`, `EntryPoint`, `Runs`, `BuiltFrom`, `ConnectsTo`, `Publishes`, `Subscribes` |
| `Scip` | Read from a SCIP index | none yet |
| `Heuristic` | Inferred, and may be wrong | none yet |

A `Contains` edge takes its provenance from the child: `Declared` for a declared child, and for a parsed child the reader that parsed it.

### Edge rules

| Id | Rule | Enforced |
|---|---|---|
| E1 | A workspace edge connects only the node kinds its row allows in the [workspace edge table](./graph-model.md#edge-kinds) | Build |
| E2 | A workspace edge never starts and ends at the same node | Build |
| E3 | The provenance suits the kind, as in the table above | Build |
| E4 | `note` appears only on a `Declared` edge | Build |
| E5 | Both ends of every edge are nodes in the graph | Graph |
| E6 | No two edges share source, target, kind and site. Two calls from one function to another on different lines are two edges | Graph |
| E7 | There is at most one `DependsOn` edge from one project to another. When the manifest and the configuration both name the pair, the declared one is kept | Graph |
| E8 | A `Service` has exactly one of `Runs` or `BuiltFrom`. An `ExternalService` has neither | Graph |
| E9 | A `Binary` has exactly one `EntryPoint`, and it leads to a `File` of the same project | Graph |
| E10 | A `Runs` edge leads to a binary of the project whose folder the service is built from | Graph |

## The containment tree

A `Contains` edge is checked whenever one of its ends is a workspace node.

| Child | Its one parent |
|---|---|
| `Workspace` | none; it is the root |
| `Project`, `Stack` | `Workspace` |
| `Network` | `Workspace` when its real name is known, else the `Stack` it was read from |
| `Binary`, `File` | The `Project` in the node's scope |
| `Service`, `ExternalService` | The `Stack` in the node's scope |
| `Topic`, `Queue` | The `ExternalService` its qualified name starts with |
| Any other code node | The `File` it was parsed from, or another code node in that file |

| Id | Rule | Enforced |
|---|---|---|
| T1 | The `Workspace` node has no incoming `Contains` edge | Graph |
| T2 | Every other node has exactly one incoming `Contains` edge, from a parent the table allows | Graph |
| T3 | Following `Contains` backwards from any node reaches the `Workspace` node. There are no cycles | Graph |
| T4 | A node's scope agrees with its ancestors: a node in a `Project` scope sits below that project, and a node in a `Stack` scope sits below that stack | Graph |
| T5 | A code node below a `File` comes from that file, and so does its `Contains` parent | Graph |

## File record

One per source file the indexer has read. It decides whether a file is read again, and it feeds `status` and `files`.

| Field | Type | Meaning |
|---|---|---|
| `project` | `ProjectId` | The project the file belongs to |
| `path` | `RelPath` | From the project's root |
| `content_hash` | `ContentHash` | The hash of the file's bytes when it was read |
| `language` | `Language` | Detected from the file |
| `status` | `ParseStatus` | `Parsed`, `Failed` with a message, or `GrammarUnavailable` |

| Id | Rule | Enforced |
|---|---|---|
| F1 | No two records share project and path | Graph |
| F2 | Every `File` node has a record with the same project and path, and every record has a `File` node | Graph |
| F3 | A file whose record is not `Parsed` has a `File` node and no nodes below it | Graph |
| F4 | A record with `GrammarUnavailable` is read again on the next index, even when the hash is unchanged | Indexer |

## Unresolved reference

A name the parser saw and could not yet connect to a node: a call, an import, a base class. Resolution turns it into an edge. One that cannot be resolved stays, for example an import into an excluded file.

| Field | Type | Meaning |
|---|---|---|
| `id` | computed | A hash of the four fields below, made the same way as a `NodeId` |
| `from` | `NodeId` | The node the reference appears in |
| `name` | text | The name as written |
| `kind` | `EdgeKind` | The kind of edge it becomes when resolved. Never a workspace kind |
| `site` | `Site` | Where it appears |

| Id | Rule | Enforced |
|---|---|---|
| R1 | `from` is a node in the graph | Graph |
| R2 | `kind` is a code edge kind | Build |
| R3 | No two references share an id | Graph |
| R4 | A resolved reference is removed, and exactly one edge replaces it, with the same `from`, kind and site | Indexer |

## Project checkout

Which version of a project the graph was built from. Each project is its own repository, so each has its own. `status` shows it, and the `operational-support` mode compares it with the release branch a [context](./mcp-modes.md#the-release-branch) names for the project.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `project` | `ProjectId` | yes | The project |
| `branch` | text | no | The branch that was checked out. Empty when the project was on no branch |
| `commit` | text | no | The commit that was checked out, as 40 hex characters. Empty when the project is not a git repository |

| Id | Rule | Enforced |
|---|---|---|
| P1 | There is at most one checkout per project | Graph |
| P2 | `project` is a `Project` node in the graph | Graph |
| P3 | A `branch` is given only together with a `commit` | Build |
| P4 | Every index writes the checkout of each project it indexes, read from the project's own `.git` folder. Nothing is fetched | Indexer |

## Warning

Something the indexer noticed that does not stop the run. The warnings of the last index are stored, and `status` shows them. A file that fails to parse is not a warning; its file record holds that.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `code` | `WarningCode` | yes | Which warning it is |
| `subject` | `NodeId` | no | The node the warning is about |
| `message` | text | yes | The warning in words, for a person |

| Code | Raised when | Subject |
|---|---|---|
| `NetworkNameUnknown` | A network's real name cannot be read and the configuration does not give it | The network |
| `LinkWithoutSharedNetwork` | A link joins two services that share no network | The project or binary that makes the link |
| `DependencyPathNotAProject` | A dependency manager's file names a local path that is not a listed project | The project whose file names it |

| Id | Rule | Enforced |
|---|---|---|
| A1 | `message` is not empty | Build |
| A2 | A `subject`, when given, is a node in the graph | Graph |
| A3 | Every index replaces all stored warnings with the ones it raised | Indexer |

## Storing the model

The model maps to SQLite as one table per type, with one column per field. This section gives the layout. Every column and index, and how the store is written and read, is in [storage-model.md](./storage-model.md).

| Table | Holds | Notes |
|---|---|---|
| `nodes` | One row per node | The scope is two columns, its type and its name. The origin is a path and four span columns, all empty for a declared node. Workspace nodes leave the code-only columns empty |
| `edges` | One row per edge | The data of a kind has its own typed columns, empty for the nineteen kinds that carry none. The table checks that each is filled in for its own kind only. Unique on source, target, kind and site |
| `files` | One row per file record | |
| `unresolved_refs` | One row per unresolved reference | |
| `warnings` | One row per warning of the last index | |
| `project_checkouts` | One row per project checkout | |
| A full-text index | Name, qualified name, doc string and signature of every node | Serves `search` and the first step of `explore` |
| `meta` | The store's format version and the time of the last index | |

Code and workspace nodes share one `nodes` table, and all edges share one `edges` table, so a walk that crosses layers is one lookup per step.

A walk is done step by step in the core, above the store port: the core asks the store for the edges of a set of nodes, then decides where to go next. The store never walks. `impact` and `explore` therefore behave the same on any store that is added later.

## What the queries rely on

Each query in the [usage guide](./usage-guide.md#commands) works only if the model keeps certain rules.

| Query | Needs | Rules |
|---|---|---|
| `explore`, `node` | A file and a span on every code node, to read its source | N4, F2 |
| `callers`, `callees` | `Calls` and `Instantiates` edges with a site each | E5, E6 |
| `impact` | An unbroken path from a code node up to its file, its project and its binaries, and on through the runtime links | T2, T3, E8, E9 |
| `files` | One record per file, with its status | F1, F2 |
| `status` | The warnings of the last index, each with its code, and each project's checkout | A2, A3, P1, P4 |
| `search` | A name and a qualified name on every node | N1 |
| Every query that crosses projects | Ids that differ when only the scope differs | N2, N6 |

## Validating an implementation

Three levels, each a set of tests.

**1. Each type on its own.** For every rule marked Build: one test that a valid value is accepted, and one that a broken value is refused with an error that names the rule.

**2. The whole graph.** `validate` takes a graph and returns every rule it breaks, not only the first. For every rule marked Graph: one small graph that breaks only that rule, and a check that `validate` reports exactly it.

**3. Acme Shop.** The workspace layer of the [example](./example-workspace.md), built by hand as a fixture, passes `validate` and has exactly these counts.

| Nodes | Count | | Edges | Count |
|---|---|---|---|---|
| `Workspace` | 1 | | `Contains` | 26 |
| `Project` | 4 | | `DependsOn` | 2 |
| `Binary` | 5 | | `Uses` | 4 |
| `File` | 5 | | `EntryPoint` | 5 |
| `Stack` | 3 | | `Runs` | 4 |
| `Service` | 4 | | `BuiltFrom` | 0 |
| `ExternalService` | 2 | | `Joins` | 8 |
| `Network` | 2 | | `ConnectsTo` | 2 |
| `Topic` | 1 | | `Publishes` | 1 |
| `Queue` | 0 | | `Subscribes` | 1 |
| **Total** | **27** | | **Total** | **53** |

The five `File` nodes are the binaries' entry files, each with a file record. `EntryPoint` needs them as targets. There are 26 `Contains` edges because every node but the root has one parent.

The fixture must also show that:

- The two `api` services have different ids, because their stacks differ.
- Building the fixture twice gives the same ids.
- The six steps of the walk in [graph-model.md](./graph-model.md#walking-the-graph) can be followed, once Class `Invoice`, its file and the `Imports` edges that reach it are added.

## Decisions made on this page

Points the other pages left open, settled here and confirmed by the project owner. The ones that are hard to reverse are also recorded, with the options that were rejected, in the [decision records](./adrs/).

| Point | Decision |
|---|---|
| Source code | The graph stores where a node is, not its source. A query reads the source from the file through the node's span, and marks a file that has changed since the last index |
| The root node's name | The qualified name is always `workspace`, so the id is the same on every machine. The folder name is only the display name |
| A network whose real name is unknown | It has a `Stack` scope and sits below its stack, since the configuration guide treats it as private to the stack |
| `Uses` for a project's own stack | A project gets a `Uses` edge to its own stack as well as to each shared stack that lists it |
| A binary's entry file in a language that is not parsed yet | The file still gets a `File` node and a record with `GrammarUnavailable`, so `EntryPoint` has a target. `web-app` needs this in Release 1 |
| Lines and columns | Lines count from 1, columns from 0 |
| Edge identity | The data of a kind is not part of an edge's identity |
| `callers` on a class | `Instantiates` edges count as calls |
| The depth of `impact` | `--depth` limits the walk through the code only, 2 by default. The runtime links after it are always followed |
| The hash | BLAKE3 for ids and for file content. A node id is 64 bits, written as 16 hex characters |
| Warnings | A structured record: a code, an optional subject node and a message |
| The release a graph was built from | A checkout is kept for each project, not one for the workspace, so that the `operational-support` mode can check each project against its release branch |
| The SQLite layout | One `nodes` table and one `edges` table for both layers, with a column per field. The data of an edge kind is typed columns, not JSON. Walks are done in the core, not in SQL |

## Open points

None at present.
