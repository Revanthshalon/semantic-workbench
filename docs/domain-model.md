# Domain Model

The types of the knowledge graph and the rules they must keep. This is the page to implement against and to validate against.

[graph-model.md](./graph-model.md) explains why the model looks this way. This page says exactly what it is. [storage-model.md](./storage-model.md) says how it is kept in SQLite. [python-parsing.md](./python-parsing.md) says what Python fills in, and how the two stages of an index produce the call sites, bindings, returns, inferred types, route paths, HTTP matches and reach defined here. Terms are defined in [GLOSSARY.md](./GLOSSARY.md). The running example is the [Acme Shop workspace](./example-workspace.md).

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
│       └── code nodes: Module, Class, Function, Route, ...
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
| `kind` | `NodeKind` | yes | One of the 33 kinds listed in [graph-model.md](./graph-model.md#node-kinds) |
| `name` | text | yes | The short name, such as `Invoice` |
| `qualified_name` | text | yes | The full name within the scope, such as `shared_api.models.Invoice` |
| `scope` | `Scope` | yes | What the node belongs to |
| `origin` | `Origin` | yes | Parsed or declared |
| `data` | `NodeData` | yes | The kind's own data, which may be nothing. See [Node data](#node-data) |

A node holds no timestamp and no copy of the source code. Source is read from the file through the node's span when a query needs it.

A code node holds no language. Its language is its file's, held by the [file record](#file-record). A project's main language is held by the `Project` node.

### Node data

The data is part of the kind, as an edge's is, so a kind can never carry another kind's fields.

| Kinds | Data |
|---|---|
| `Project` | `ProjectData { language }`: the project's main language, from the configuration |
| `Binary` | `BinaryData { framework, app, framework_source }` |
| `Workspace`, `Stack`, `Service`, `ExternalService`, `Network`, `Topic`, `Queue` | none |
| `Function`, `Method`, `Property` | `Callable { doc, signature, visibility, is_async, is_static, is_abstract, is_exported, decorators, type_parameters, return_type, role }` |
| `Class`, `Struct`, `Interface`, `Trait`, `Protocol`, `Enum`, `Union`, `TypeAlias`, `Component` | `TypeDecl { doc, signature, visibility, is_abstract, is_exported, decorators, type_parameters, role }` |
| `Field`, `Variable`, `Constant`, `Parameter` | `Member { visibility, is_static, is_exported, declared_type, default, source, role }` |
| `Route` | `RouteData { method, path, status_code, tags }` |
| `Command` | `CommandData { program, path, help, options }` |
| `File`, `Module`, `Namespace` | `Doc { doc }` |
| `EnumMember`, `Import`, `Export` | none |

The fields:

| Field | Type | Meaning |
|---|---|---|
| `language` | `Language` | `Python` or `TypeScript` |
| `framework` | `Framework` | `Fastapi`, `Angular` or `None` |
| `app` | text, optional | The qualified name of a FastAPI binary's app, such as `billing.api.app` |
| `framework_source` | `FrameworkSource` | Where `framework` came from: `Declared` (the configuration), `Compose` (a compose command), `Dockerfile` (a Dockerfile's `CMD` or `ENTRYPOINT`) or `Entry` (the entry file) |
| `doc` | text, optional | The doc string |
| `signature` | text, optional | The declaration as written, on one line |
| `visibility` | `Visibility`, optional | `Public`, `Private`, `Protected` or `Internal` |
| `is_async`, `is_static`, `is_abstract`, `is_exported` | flag | Each defaults to false |
| `decorators` | list of text | Each decorator's dotted name as written, without arguments, in source order. Defaults to empty |
| `type_parameters` | list of text | Defaults to empty |
| `return_type`, `declared_type` | text, optional | The annotation as written |
| `default` | text, optional | A default value as written, cut at 80 characters |
| `source` | `ParamSource`, optional | `Parameter` only: `Path`, `Query`, `Header`, `Cookie`, `Body`, `Form` or `File` |
| `role` | `FrameworkRole`, optional | What a framework makes of the node, when the node's own file shows it: `App`, `Router { prefix, tags }`, `Middleware`, `ExceptionHandler`, `LifecycleHook`, `Fixture` (pytest) or `Model` |
| `method` | `HttpMethod` | `Get`, `Post`, `Put`, `Patch`, `Delete`, `Head`, `Options`, `Trace` or `WebSocket` |
| `path` | `Template` | A route's local path: text, a name whose text stage 2b works out, or unknown |
| `status_code` | number, optional | |
| `tags` | list of text | Defaults to empty |
| `program` | text | A command's program, such as `ledger-consumer` |
| `path` (command) | list of text | The subcommand words below the program, such as `["replay"]`. Empty for the program itself |
| `help` | text, optional | The help text given to the parser |
| `options` | list of text | Each option and positional argument, as written: `--from`, `source` |

What each language can express. A value outside its row is refused when the node is built (rule N9):

| Language | Refused |
|---|---|
| `Python` | `visibility` of `Protected` or `Internal`. `framework` of `Angular` |
| `TypeScript` | `framework` of `Fastapi`. The rest is settled when TypeScript is parsed (Release 2) |

A role suits only some kinds (rule N10):

| Role | Kinds |
|---|---|
| `App`, `Router` | `Variable` |
| `Middleware`, `ExceptionHandler`, `LifecycleHook`, `Fixture` | `Function`, `Method` |
| `Model` | `Class` |

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
| `Route` | Its handler's qualified name, `@`, the method and the local path. Its `name` is the method and the local path | `billing.routes.invoices.get_invoice@GET /{invoice_id}` |
| `Command` | The module, `@`, the program and the path. Its `name` is the program and the path | `ledger.consumer@ledger-consumer replay` |
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
| N8 | The data suits the kind, as in the [node data](#node-data) table | Build |
| N9 | A code node's data suits the language of the file it is parsed from, and a binary's framework suits its project's language, as in the language table. The language is given when the node is built and is not stored on it | Build |
| N10 | A role suits the kind, as in the role table. `app` is given only when `framework` is `Fastapi` | Build |

## Edge

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source` | `NodeId` | yes | The node the edge starts at |
| `target` | `NodeId` | yes | The node the edge ends at |
| `kind` | `EdgeKind` | yes | One of the 29 kinds listed in [graph-model.md](./graph-model.md#edge-kinds), with its data |
| `site` | `Site` | no | Where in a file the relationship occurs, when it has a place |
| `provenance` | `Provenance` | yes | How the edge came to exist |
| `resolved_by` | `Resolution` | no | The rule that resolved the reference this edge came from. Empty for an edge not made by resolution. See [How an edge was resolved](#how-an-edge-was-resolved) |
| `note` | text | no | The free text of a hand-written dependency or link |

### Edge data

The data is part of the kind, so a kind can never carry another kind's data.

| Kind | Data |
|---|---|
| `Imports` | `specifier`: the import as written. `alias`: the local name it is bound to, optional. `type_only`: true when the import only serves type checking, such as Python's `if TYPE_CHECKING:` |
| `DependsOn` | `scope`: `Build` or `Dev` |
| `ConnectsTo` | `protocol`: `Http`, `Grpc` or `Database` |
| `Mounts` | `prefix`: the path prefix the mount adds, a `Template`, optional. `tags`: the tags the mount adds |
| `Requests` | `method`: the HTTP method of the call. `path`: the call's path, with what stage 2b could fill in filled, and unknown parts as `{?}` |
| `Sends` | `name`: the topic, queue or stream name, as 2b filled it in |
| `Invokes` | `words`: the command words of the compose command, as written |
| The other twenty-two | none |

### Provenance

| Value | Meaning | Kinds that carry it in Release 1 |
|---|---|---|
| `TreeSitter` | Read from source code by a parser | Every code kind |
| `Manifest` | Read from a dependency manager's files | `DependsOn` |
| `Compose` | Read from a compose file | `Runs`, `BuiltFrom`, `Joins`, `Uses`, `Invokes` |
| `Dockerfile` | Read from a Dockerfile: the command line a service runs | `Runs`, `Invokes` |
| `Declared` | Written by hand in the configuration | `DependsOn`, `Uses`, `EntryPoint`, `Runs`, `BuiltFrom`, `ConnectsTo`, `Publishes`, `Subscribes` |
| `Scip` | Read from a SCIP index | none yet |
| `Heuristic` | Inferred, and may be wrong | none yet |

A `Contains` edge takes its provenance from the child: `Declared` for a declared child, and for a parsed child the reader that parsed it.

### How an edge was resolved

Provenance says where the facts came from. `resolved_by` says which rule connected a reference to its target. It is set on every edge made by resolving a reference, on no other edge, and it is not part of an edge's identity.

| `Resolution` | The rule |
|---|---|
| `Import` | A name the file imported |
| `SelfMember` | `self.<name>`: a member of the class around the reference |
| `SameFile` | A definition in the same file |
| `Project` | The name as a qualified name in the project |
| `CrossProject` | Another project, found through its import names |
| `ReExport` | Followed through re-exports |
| `Annotation` | The receiver's declared type |
| `LocalInference` | A local name assigned once from a class, or from a function with a `Returns` edge |
| `Inherited` | A member found in a resolved base class |
| `Flow` | The receiver is a parameter typed by its callers. Right when the workspace holds every caller |
| `Framework` | A framework profile's reference, including a pytest fixture |
| `RouteMatch` | An HTTP client call matched to a route path |
| `MessageMatch` | A producer or consumer matched to a declared topic or queue |
| `CommandMatch` | A compose command matched to a `Command` of the binary its service runs |

[python-parsing.md](./python-parsing.md#how-an-edge-was-resolved) says when each applies for Python.

### Framework edges

Six code edge kinds hold what a web framework does with code, what calls it over HTTP, and what sends and handles messages. `Mounts`, `Handles` and `Injects` are made by resolving a reference a framework profile records, so each has `resolved_by: Framework`. `Requests` is made by matching an HTTP client call to a route path, so it has `resolved_by: RouteMatch`. `Sends` and `Receives` are made by matching a producer or consumer to a declared topic or queue, so they have `resolved_by: MessageMatch`. An `Injects` edge from an app or router that has the same site as a `Mounts` edge from that node was given at the mount, and applies only to routes reached through it.

| Kind | From | To | Data | Says | Read by |
|---|---|---|---|---|---|
| `Mounts` | A `Variable` with role `App` or `Router` | A `Variable` with role `App` or `Router`, or a `Route` | `prefix`, optional | The source serves the target, under the prefix. From `include_router`, `mount` and a route decorator on a router or app | Route paths, `node` on a route, reach (downwards), `impact` |
| `Handles` | A `Route` or a `Command` | A `Function` or `Method` | none | This function runs when the route is called, or when the command is run | Reach, `impact` from a handler to its endpoints and services, `callers` |
| `Injects` | A `Function`, `Method` or `Route`, or a `Variable` with role `Router` | A `Function`, `Method` or `Class` | none | The framework calls the target and passes the result in, as FastAPI's `Depends` does, and as pytest does with a fixture | Reach, `impact` from a provider to every route that uses it, "which providers does this route use", the tests to run |
| `Requests` | A `Function`, `Method` or `File` | A `Route` | `method`, `path` | This code calls the route over HTTP: from another project, or from a test through `TestClient` | Reach, `impact`, the tests to run, API contracts, `node` on a route |
| `Sends` | A `Function`, `Method` or `File` | A `Topic` or `Queue` | `name` | This code sends messages to the topic or queue | `impact`, event contracts, `node` on a topic |
| `Receives` | A `Function` or `Method` | A `Topic` or `Queue` | none | This code handles the messages of the topic or queue | `impact`, event contracts, `node` on a topic |

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
| E11 | A framework edge joins only these: `Mounts` from a `Variable` with role `App` or `Router` to such a `Variable` or to a `Route`. `Handles` from a `Route` to a `Function` or `Method`. `Injects` from a `Function`, `Method`, `Route` or `Variable` with role `Router` to a `Function`, `Method` or `Class`. `Requests` from a `Function`, `Method` or `File` to a `Route`. `Handles` may also start at a `Command`. `Sends` from a `Function`, `Method` or `File`, and `Receives` from a `Function` or `Method`, to a `Topic` or `Queue` | Graph |
| E12 | An edge with `resolved_by: Flow` rests on at least one [inferred type](#inferred-type): of a parameter of its callable, of the return of a function its receiver came from, of a field, or of a name bound more than once | Graph |
| E13 | `resolved_by` is given only on a code edge with provenance `TreeSitter` or `Scip`, and on `Invokes` (provenance `Compose` or `Dockerfile`). `Flow` is given only on `Calls` and `Instantiates`. `Framework` is given only on `Mounts`, `Handles` and `Injects`, and those three always have it. `RouteMatch` is given only on `Requests`, `MessageMatch` only on `Sends` and `Receives`, and `CommandMatch` only on `Invokes`, and each of those kinds always has its value | Build |

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
| `kind` | `EdgeKind` | The kind of edge it becomes when resolved, with its data: a `Mounts` reference keeps its prefix. Never a workspace kind |
| `site` | `Site` | Where it appears |

| Id | Rule | Enforced |
|---|---|---|
| R1 | `from` is a node in the graph | Graph |
| R2 | `kind` is a code edge kind | Build |
| R3 | No two references share an id | Graph |
| R4 | A resolved reference is removed, and exactly one edge replaces it, with the same `from`, kind and site. Two exceptions: an `Overrides` reference whose bases all resolved, and none has the name, is removed with no edge. A reference resolved with `Flow` is kept, marked as resolved by flow, so that it can be tried again when the flow edges are rebuilt at the next index | Indexer |

## Call site

One call expression, with its arguments as written. Stage 1 records it from the call's own file, and it is replaced with its file. Stage 2 uses it to carry types and text through calls, and to find HTTP calls.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node the call is in, or the `File` at module level |
| `site` | `Site` | Where the call is |
| `callee` | text | The callee as written: `process`, `self.repo.save`, `models.Invoice` |
| `arguments` | list of `Argument` | In source order |

An `Argument` is a `position` (from 0) or a `keyword`, and a `Shape`. A `Shape` is one of:

| Shape | Written as |
|---|---|
| `Call(name)` | A call of a name: `Invoice(...)`, `make_invoice()`. Resolution decides whether it creates an instance of a class or calls a function |
| `Name(name)` | A bare or dotted name: `repo`, `self.repo`, `settings.API_PREFIX` |
| `Text(value)` | A string literal, with its value |
| `Template(parts)` | An f-string, `str.format` on a literal, or strings joined with `+`. Each part is `Text(value)`, `Hole(name)` for a bare or dotted name, or `Unknown` |
| `Item(name, accessor)` | An element of a named value. `accessor` is `Iter` (a `for` target), `Index` (a subscript), `Keys`, `Values` or `Items`, for iteration over those methods of a dict |
| `Collection(kind, elements)` | A `List`, `Set`, `Tuple` or `Dict` literal or comprehension, with the shapes of its elements (the values, for a dict) |
| `Spread(name)` | `*name` or `**name` passed as an argument |
| `Literal(kind)` | Any other literal: number, bytes, bool or `None` |
| `Other` | Anything else |

A `Template` is also the type of a route's local path and of a prefix (`Mounts`, `Router`): text, or a name whose text stage 2b works out, or unknown.

| Id | Rule | Enforced |
|---|---|---|
| C1 | `from` is a node in the graph | Graph |
| C2 | Each argument has a position or a keyword, never both. Positions run from 0 without a gap | Build |
| C3 | No two call sites share `from` and `site` | Graph |

## Binding

One assignment of a name, with the shape of its value. Stage 1 records one per assignment, from its own file, and they are replaced with their file. A `for` target and a `with ... as` target are bindings too.

| Field | Type | Meaning |
|---|---|---|
| `in` | `NodeId` | Where the name lives: the `File` for a module-level name, the `Function` or `Method` for a local name, the `Class` for `self.<name> = ...` in any of its methods and for a class attribute |
| `name` | text | The name assigned, without `self.` |
| `site` | `Site` | Where the assignment is. For a value of shape `Call`, the call site of the same place holds its arguments, such as a client's `base_url` |
| `shape` | `Shape` | The shape of the value |

A name is bound once when it has exactly one binding in its `in`.

| Id | Rule | Enforced |
|---|---|---|
| L1 | `in` is a `File`, `Function`, `Method` or `Class` node in the graph | Graph |
| L2 | `name` is not empty | Build |
| L3 | No two bindings share `in`, `name` and `site` | Graph |

## Return

One way a function or method returns, with the shape of its value. A bare `return` is a return of `None`, and so is the end of a body that can be reached without a `return` or a `raise`. Stage 1 records them from their own file, and they are replaced with their file.

| Field | Type | Meaning |
|---|---|---|
| `in` | `NodeId` | The `Function` or `Method` |
| `site` | `Site` | The `return`, or the last line of a body that can end without one |
| `shape` | `Shape` | The shape of the value returned |

| Id | Rule | Enforced |
|---|---|---|
| B1 | `in` is a `Function` or `Method` node in the graph | Graph |
| B2 | No two returns share `in` and `site` | Graph |

## Inferred type

A node's class, worked out by stage 2b. It exists only when all of the node's evidence agrees.

| Field | Type | Meaning |
|---|---|---|
| `node` | `NodeId` | A `Parameter` (evidence: its call sites), a `Function` or `Method` (its returns), a `Field` (its bindings), or a `Variable` or `Constant` bound more than once (its bindings) |
| `class` | `NodeId` | The class all of the evidence gives |
| `evidence` | number | How many call sites, returns or bindings agreed |

| Id | Rule | Enforced |
|---|---|---|
| Y1 | `node` is a `Parameter`, `Function`, `Method`, `Field`, `Variable` or `Constant` node, and `class` is a `Class`, `Protocol` or `Enum` node | Graph |
| Y2 | At most one inferred type per node | Graph |
| Y3 | `evidence` is at least 1 | Build |
| Y4 | Every index removes all inferred types and every edge with `resolved_by: Flow`, and writes the ones it computed | Indexer |

## Reach

That a root may run a code node, found by stage 2e over resolved edges.

| Field | Type | Meaning |
|---|---|---|
| `node` | `NodeId` | A code node |
| `root` | `Root` | `Binary(NodeId)`: a binary. `Module(NodeId)`: the `File` of a module named in a command or a binary's `app`. `Test(NodeId)`: a test `File` |

| Id | Rule | Enforced |
|---|---|---|
| H1 | `node` is a code node in the graph. A `Binary` root is a `Binary` node; a `Module` or `Test` root is a `File` node | Graph |
| H2 | No two reach records share `node` and `root` | Graph |
| H3 | Every index removes all reach records and writes the ones it computed | Indexer |

## Route path

One full path of a route, and the binary that serves it, found by stage 2c. A route has one for each way its mounts lead to an app.

| Field | Type | Meaning |
|---|---|---|
| `route` | `NodeId` | The `Route` |
| `binary` | `NodeId`, optional | The FastAPI binary whose `app` the mounts lead to. Empty when no binary names that app |
| `method` | `HttpMethod` | The route's method |
| `full_path` | text | The prefixes and the local path, joined, with names filled in by stage 2b. A part whose value exists only at run time is written `{?}` |
| `complete` | flag | True when no part is unknown |
| `uses_defaults` | flag | True when a part was filled from a settings default, which the environment may change |
| `providers` | list of `NodeId` | The providers that run for this path: from the route, its handler, each router and app on the chain, and each mount on the chain |
| `tags` | list of text | The tags of the route, its routers and its mounts |

| Id | Rule | Enforced |
|---|---|---|
| U1 | `route` is a `Route` node. `binary`, when given, is a `Binary` node whose framework is `Fastapi` | Graph |
| U2 | `complete` is true exactly when `full_path` holds no `{?}` | Build |
| U3 | No two route paths share `route`, `binary` and `full_path` | Graph |
| U4 | Every index removes all route paths and writes the ones it computed | Indexer |
| U5 | Every provider is a `Function`, `Method` or `Class` node | Graph |

## Unmatched HTTP call

An HTTP client call that stage 2d found, and could not match to exactly one route path. It is kept so that `node` can show it with its candidates.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node the call is in |
| `site` | `Site` | Where the call is |
| `method` | `HttpMethod` | The method of the call |
| `path` | text | The path as written, with unknown parts as `{?}` |
| `candidates` | list of `NodeId` | The routes whose paths matched. Empty when none did |

| Id | Rule | Enforced |
|---|---|---|
| M1 | `from` is a node in the graph, and every candidate is a `Route` node | Graph |
| M2 | There is never exactly one candidate: one candidate is a `Requests` edge instead | Build |
| M3 | Every index removes all unmatched HTTP calls and every `Requests` edge, and writes the ones it computed | Indexer |

## Unmatched message

A producer or consumer call that stage 2f found, and could not match to exactly one declared topic or queue.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node that sends, or the function or callback that receives |
| `site` | `Site` | Where the call is |
| `direction` | `Send` or `Receive` | |
| `name` | text | The name, with unknown parts as `{?}` |
| `broker` | `NodeId`, optional | The external service the connection names, when known |
| `candidates` | list of `NodeId` | The topics and queues whose names matched. Empty when none did |

| Id | Rule | Enforced |
|---|---|---|
| G1 | `from` is a node in the graph, `broker` is an `ExternalService`, and every candidate is a `Topic` or `Queue` | Graph |
| G2 | There is never exactly one candidate | Build |
| G3 | Every index removes all unmatched messages and every `Sends` and `Receives` edge, and writes the ones it computed | Indexer |

## Message payload

A project class carried on a topic or queue, as the code that sends or receives builds or reads it.

| Field | Type | Meaning |
|---|---|---|
| `topic` | `NodeId` | The `Topic` or `Queue` |
| `node` | `NodeId` | The node at the start of the `Sends` or `Receives` edge |
| `direction` | `Send` or `Receive` | |
| `class` | `NodeId` | The class sent or read |

| Id | Rule | Enforced |
|---|---|---|
| D1 | `topic` is a `Topic` or `Queue`, `class` is a `Class`, and a `Sends` or `Receives` edge of that direction joins `node` to `topic` | Graph |
| D2 | No two payloads share `topic`, `node`, `direction` and `class` | Graph |
| D3 | Every index removes all payloads and writes the ones it computed | Indexer |

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
| `FrameworkMismatch` | The configuration or a compose command names one framework for a binary, and its entry file builds another, or names none while it builds an app | The binary |
| `FrameworkAppNotFound` | A FastAPI binary's `app` names no node, or a node that is not an app or a function that returns one | The binary |
| `EntryCommandMismatch` | A service's command line, from compose or its Dockerfile, runs a module other than the binary's configured entry | The binary |
| `DockerfileUnreadable` | A service's Dockerfile is missing, or cannot be read | The service |
| `FlowRoundLimit` | Carrying types and text through calls stopped at its round limit before it settled | none |
| `HttpCallWithoutLink` | An HTTP call matches a route served by a binary of another project, and the caller declares no `http` link to a service that runs that binary | The node the call is in |
| `MessageWithoutLink` | A producer or consumer names a topic or queue that is not declared, or one the caller's project declares no link for | The node that sends or receives |
| `CommandNotFound` | A compose service's command words name no `Command` of the binary it runs | The service |

| Id | Rule | Enforced |
|---|---|---|
| A1 | `message` is not empty | Build |
| A2 | A `subject`, when given, is a node in the graph | Graph |
| A3 | Every index replaces all stored warnings with the ones it raised | Indexer |

## Storing the model

The model maps to SQLite as one table per type, with one column per field. This section gives the layout. Every column and index, and how the store is written and read, is in [storage-model.md](./storage-model.md).

| Table | Holds | Notes |
|---|---|---|
| `nodes` | One row per node | The scope is two columns, its type and its name. The origin is a path and four span columns, all empty for a declared node. The node data is one column per field, empty for kinds whose data has no such field |
| `edges` | One row per edge | The data of a kind has its own typed columns, empty for the twenty-two kinds that carry none. The table checks that each is filled in for its own kind only. Unique on source, target, kind and site |
| `files` | One row per file record | |
| `unresolved_refs` | One row per unresolved reference | |
| `call_sites`, `bindings`, `returns` | One row per call site, binding and return | Replaced with their file |
| `inferred_types`, `reach`, `route_paths`, `unmatched_http_calls`, `unmatched_messages`, `message_payloads` | One row per record | Replaced at every index, with the edges resolved by `Flow`, `RouteMatch`, `MessageMatch` and `CommandMatch` |
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
| `callers`, `callees`, with how each call was resolved | `resolved_by` on every resolved edge; a `Flow` edge always rests on an inferred type | E12, E13, Y1, Y2 |
| `node` on a parameter | At most one inferred type, with the number of call sites | Y1, Y2, Y3 |
| `node`'s `reached by`, `files --unreached` | Reach records for the last index only | H1, H2, H3 |
| `node` on a route, and `search` by full path | Route paths for the last index, from `Mounts` chains that end at an app | E11, N10, U1 to U4 |
| `node`'s `reached by`, without imports that never run | `type_only` on `Imports` | none: data of the kind |
| `impact --tests` | Reach from test files, `Injects` to fixtures, `Requests` from `TestClient` | E11, E13, H1 to H3 |
| `impact`'s API contract | Route paths, `Requests` edges into a route, `TypeOf` from fields, declared `http` links | E11, U1 to U4, E1 |
| `node`'s HTTP calls on a function | `Requests` edges and unmatched HTTP calls | E11, M1 to M3 |
| `impact`'s event contract | `Sends` and `Receives` edges, payloads, declared links | E11, E13, D1 to D3 |
| `impact` through commands, and `node` on a command | `Handles` from commands, `Invokes` from services | E1, E11, E13 |

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

`fixtures::acme()` adds the code layer of [python-parsing.md](./python-parsing.md#acme-shop-with-fastapi) and must show that:

- Billing's `api` binary has `framework: Fastapi` and `app: billing.api.app`, and `worker` has `framework: None`.
- The route `GET /{invoice_id}` reaches billing's app through two `Mounts` edges, and has one route path: `GET /v1/invoices/{invoice_id}`, complete, served by `api`.
- `r` in `process` has the inferred type `InvoiceRepo` from 2 call sites, and `r.save()` is a `Calls` edge to `InvoiceRepo.save` with `resolved_by: Flow`, and its reference is kept.
- `routes/invoices.py` is reached by `api` only, and `services.py` by `worker` and by the test `test_services.py`.
- Ledger's `fetch_invoice` has a `Requests` edge to `GET /{invoice_id}`, with `resolved_by: RouteMatch`, and the index raises one `HttpCallWithoutLink` warning about it.
- `test_get_invoice` has a `Requests` edge to the same route and an `Injects` edge to the fixture `repo`, and `impact` on the handler `--tests` lists it.
- `send_invoice` has a `Sends` edge, and `run_consume` a `Receives` edge, to `kafka/invoice.created`, each with `Invoice` as payload.
- Ledger's `consumer` binary has the commands `ledger-consumer`, `ledger-consumer run` and `ledger-consumer replay`, and the `consumer` service an `Invokes` edge to `ledger-consumer run`.

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
| Node data | Part of the kind, as an edge's data is. A field a kind does not have cannot be set |
| Language | On the `Project` node, from the configuration, and on the file record, detected. Not on code nodes |
| How an index builds the graph | Stage 1 reads every file, one at a time. Stage 2 analyses the finished graph from each root and reads no file again |
| Types carried from callers | Only when every call site in the workspace passes the same class. Such edges have `resolved_by: Flow`, and their references are kept. Up to 10 rounds by default, set by `analysis.flow_rounds` |
| How an edge was resolved | Provenance stays coarse. Every resolved edge records `resolved_by`, the rule that connected it. No `Flow` provenance |
| Framework edges | `Mounts`, `Handles` and `Injects`, each a kind of its own |
| A route's full path | Computed by stage 2c and stored as a route path, not on the route node |
| Type-only imports | `Imports` carries `type_only`. Resolution treats them as any import; reach does not follow them |
| Release 1 | Plain Python binaries and FastAPI binaries, HTTP calls matched to routes, the tests to run for a change, API contracts |
| HTTP calls in code | Matched to route paths as `Requests` edges. They never create a `ConnectsTo` link; a cross-project match with no declared link is a warning |
| Messages in code | Matched to declared topics and queues as `Sends` and `Receives` edges, with their payloads. Topics and queues are still created only from the configuration |
| Dockerfiles | Read for the command line a service runs: its binary when nothing else names it, its framework, and the command it invokes. Facts from them have the `Dockerfile` provenance |
| Commands | `argparse` parsers and subcommands are `Command` nodes. A compose service is linked to the command it runs by `Invokes`, computed in stage 2 |
| A binary's framework | Decided before parsing, per binary, from the configuration, then a compose command, then the entry file. A framework's rules read every file that imports it |

## Open points

None at present.
