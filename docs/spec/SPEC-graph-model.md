# Spec: Graph model: R1

Status: draft
Module id: `graph-model`
Capabilities: `G1` to `G12` (`G9` is deferred to Later)
Depends on: `ground-rules`
Consolidates: [domain-model.md](../domain-model.md), [graph-model.md](../graph-model.md), [capability map §G](../capability-map.md#g-graph-model), [step 1 plan](../implementation-plan/step-1-domain-types.md), [`examples/acme-shop/lib/ids.py`](../../examples/acme-shop/lib/ids.py), ADRs [0002](../adrs/0002-node-ids-are-computed-with-blake3.md), [0012](../adrs/0012-node-kinds-carry-their-own-data.md), [0016](../adrs/0016-framework-relationships-are-edges-of-their-own.md), [0017](../adrs/0017-every-resolved-edge-records-its-rule.md), and the parts of ADRs [0003](../adrs/0003-the-graph-changes-only-on-index.md), [0004](../adrs/0004-runtime-links-are-declared-by-hand.md), [0006](../adrs/0006-one-nodes-table-one-edges-table-typed-columns.md), [0014](../adrs/0014-types-are-carried-only-when-every-caller-agrees.md), [0020](../adrs/0020-commands-are-nodes-and-services-invoke-them.md) and [0021](../adrs/0021-dockerfiles-are-read-for-the-command-a-service-runs.md) that touch node ids, node kinds, edges or provenance

## Objective

This module holds the types of the knowledge graph in `src/domain`, and the rules those types keep. Every other module builds, stores, walks or prints these types, so they are written first. An AI tool that works on one file at a time cannot see how a workspace fits together. The graph stores that as nodes and edges in one tree rooted at the workspace node, with cross-links a query can walk across projects. Ids are computed, so indexing twice updates nodes instead of duplicating them. Each kind holds its own data, so a kind can never carry another kind's fields. Every edge records where its facts came from, and every resolved edge records the rule that resolved it, so a reader can judge each step of a walk.

When this module is done, every Build rule refuses a broken value when it is built, every Graph rule is reported by `Graph::validate`, and the Acme Shop graph built through the constructors passes `validate` with the ids of `examples/acme-shop/site/graph.json`.

## Interface

Everything here is public from `crate::domain`, unless it is marked `pub(crate)`. The types depend on nothing outside `src/domain`: no SQLite, no parser, no configuration loader. They do no input or output.

### The shape: one tree, many cross-links

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

### Errors and rule ids

`src/domain/rule.rs` and `src/domain/error.rs` are written. They list every rule of this spec. No later change edits them except to add a rule id, which is an Ask-first boundary.

```rust
/// Every rule id of the domain model, including the Type and Indexer rules,
/// so that a test or a log line can name any of them.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum RuleId {
    N1, N2, N3, N4, N5, N6, N7, N8, N9, N10,
    E1, E2, E3, E4, E5, E6, E7, E8, E9, E10, E11, E12, E13,
    T1, T2, T3, T4, T5,
    F1, F2, F3, F4,
    R1, R2, R3, R4,
    C1, C2, C3,
    L1, L2, L3,
    B1, B2,
    Y1, Y2, Y3, Y4,
    H1, H2, H3,
    U1, U2, U3, U4, U5,
    M1, M2, M3,
    G1, G2, G3,
    D1, D2, D3,
    P1, P2, P3, P4,
    A1, A2, A3,
}
impl RuleId { pub fn as_str(self) -> &'static str; }   // "N1"
impl fmt::Display for RuleId { /* as_str */ }

/// The value type a malformed input was meant to become.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ValueKind {
    ProjectId, ComposeName, RelPath, ContentHash, NodeId, ReferenceId,
    Name, QualifiedName, CommitId, Line, Span,
}

#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum DomainError {
    /// Text that does not have the form of its value type.
    #[error("not a valid {value:?}: {input:?}: {reason}")]
    Malformed { value: ValueKind, input: String, reason: &'static str },
    /// A value that breaks a rule of the domain model.
    #[error("rule {rule}: {message}")]
    Rule { rule: RuleId, message: String },
}
```

The order of `RuleId` is the order above. `validate` sorts by it.

### Value types

Small types that check their own content. Each is refused at build time when its content breaks the rule.

| Type | Holds | Rule |
|---|---|---|
| `ProjectId` | A project's id | Kebab-case: lowercase letters and digits, in groups joined by single hyphens |
| `ComposeName` | A stack's Compose name | Lowercase letters, digits, `-` and `_`; starts with a letter or digit |
| `RelPath` | A path to a file | Relative, uses `/`, not empty, no `.` segments. `..` segments are allowed only at the start |
| `ContentHash` | The BLAKE3 hash of a file's bytes | All 256 bits, as 64 lowercase hex characters. It is never shown to a user |
| `NodeId` | A node's identity | Computed, never assigned: 64 bits, shown as 16 lowercase hex characters such as `9f2c41d07ab35e18`. See [Node identity](#node-identity) |
| `ReferenceId` | An unresolved reference's identity | Computed as a `NodeId` is, from the reference's own fields |
| `Name` | A node's short name | Not empty |
| `QualifiedName` | A node's full name within its scope, or a FastAPI app's | Not empty |
| `Line` | A line in a file | Counts from 1, so 0 cannot be held |
| `Column` | A column in a line | Counts from 0 |
| `Span` | A region of a file | Start `Line` and `Column`, end `Line` and `Column`. The start is not after the end |
| `Site` | One place in a file | A `RelPath`, a `Line` and a `Column` |
| `CommitId` | A git commit | 40 lowercase hex characters |

```rust
// id.rs
/// 64 bits of a BLAKE3 hash. Shown as 16 lowercase hex characters.
/// No PartialOrd or Ord: the order of ids means nothing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct NodeId([u8; 8]);
impl NodeId {
    pub fn parse(hex: &str) -> Result<Self, DomainError>;   // for ids typed by a user or read from a store
    pub fn as_bytes(&self) -> &[u8; 8];
}
impl fmt::Display for NodeId { /* 16 lowercase hex */ }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ReferenceId([u8; 8]);       // same API as NodeId

/// All 256 bits of a BLAKE3 hash of a file's bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ContentHash([u8; 32]);
impl ContentHash {
    pub fn of(bytes: &[u8]) -> Self;
    pub fn parse(hex: &str) -> Result<Self, DomainError>;   // 64 lowercase hex
}
// There is no public NodeId or ReferenceId constructor besides `parse`. Ids are computed
// only inside `Node`'s and `UnresolvedReference`'s constructors, by a `pub(crate)` id writer
// that writes the bytes listed under Node identity.

// name.rs. Each: parse(&str) -> Result<Self, DomainError>, as_str(&self) -> &str, Display,
// and #[serde(try_from = "String", into = "String")]. No Deref, no From<String>.
pub struct ProjectId(String);       // kebab-case: [a-z0-9]+(-[a-z0-9]+)*
pub struct ComposeName(String);     // [a-z0-9][a-z0-9_-]*
pub struct Name(String);            // not empty (N1, L2)
pub struct QualifiedName(String);   // not empty (N1)
pub struct CommitId(String);        // 40 lowercase hex

// path.rs
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct RelPath(String);         // relative, '/', not empty, no '.' segments, '..' only at the start
impl RelPath {
    pub fn parse(s: &str) -> Result<Self, DomainError>;
    pub fn as_str(&self) -> &str;
    pub fn leaves_root(&self) -> bool;   // starts with '..'; refused under a Project scope (N3)
}

// position.rs
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Line(NonZeroU32);        // from 1
impl Line {
    pub fn new(n: u32) -> Result<Self, DomainError>;   // 0 is Malformed { value: Line, .. }
    pub fn get(self) -> u32;
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Column(u32);             // from 0
impl Column {
    pub fn new(n: u32) -> Self;
    pub fn get(self) -> u32;
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Span { start: (Line, Column), end: (Line, Column) }
impl Span {
    pub fn new(start: (Line, Column), end: (Line, Column)) -> Result<Self, DomainError>;  // start <= end
    pub fn start(&self) -> (Line, Column);
    pub fn end(&self) -> (Line, Column);
}
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Site { pub path: RelPath, pub line: Line, pub column: Column }   // no rule of its own

// template.rs
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum TemplatePart { Text(String), Hole(String), Unknown }
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Template(Vec<TemplatePart>);
impl Template {
    pub fn new(parts: Vec<TemplatePart>) -> Self;   // merges adjacent Text parts, drops empty Text
    pub fn text(s: impl Into<String>) -> Self;
    pub fn parts(&self) -> &[TemplatePart];
    pub fn is_known(&self) -> bool;                 // only Text parts
    pub fn render(&self) -> String;                 // Hole as {name}, Unknown as {?}
}

// common.rs, all fieldless and Copy
pub enum HttpMethod { Get, Post, Put, Patch, Delete, Head, Options, Trace, WebSocket }
pub enum Language { Python, TypeScript }
pub enum DependencyManager { Uv, Poetry, Npm, Pnpm, Yarn, Bun }
```

Each fieldless enum has `as_str(self) -> &'static str`, giving its storage name, and the matching `FromStr`. The storage names are written out here and in the tables below, not derived: every fixed set of names is stored as snake-case text (storage-model.md, "How a value is written"; SCHEMA.md), and `WebSocket` is the one value whose name is not the plain snake case of its variant.

| Enum | Storage names, in variant order |
|---|---|
| `HttpMethod` | `get`, `post`, `put`, `patch`, `delete`, `head`, `options`, `trace`, `websocket` |
| `Language` | `python`, `typescript` |
| `Scope` type | `workspace`, `project`, `stack` |
| `Visibility` | `public`, `private`, `protected`, `internal` |
| `ParamSource` | `path`, `query`, `header`, `cookie`, `body`, `form`, `file` |
| `FrameworkRole` | `app`, `router`, `middleware`, `exception_handler`, `lifecycle_hook`, `fixture`, `model` |
| `FrameworkSource` | `declared`, `compose`, `dockerfile`, `entry` |
| `FrameworkName` | `none` (for `NoFramework`, as the configuration's `framework: none`), `fastapi`, `angular` |
| `DependencyScope` | `build`, `dev` |
| `Protocol` | `http`, `grpc`, `database` |
| `ParseStatus` | `parsed`, `failed`, `grammar_unavailable` |
| `Root` | `binary`, `module`, `test` |
| `MessageDirection` | `send`, `receive` |

`DependencyManager`'s storage names are not listed in storage-model.md. By the snake-case rule they are `uv`, `poetry`, `npm`, `pnpm`, `yarn`, `bun`.

A `Template` is the type of a route's local path and of a prefix (`Mounts`, `Router`): text, or a name whose text stage 2b works out, or unknown.

### Node identity

The id is a hash of five inputs:

1. The scope: its type, and the `ProjectId` or `ComposeName` it carries.
2. The path from the origin, or nothing for a declared node.
3. The kind.
4. The qualified name.
5. The ordinal: how many earlier nodes in the same file share the first four inputs. The first has `0`.

The hash is BLAKE3, and the id is its first 8 bytes. Each input is written with its length in front of it before hashing, so two different sets of inputs can never produce the same bytes. Two nodes sharing an id is about a 1 in 40 million chance in a graph of a million nodes, and rule N6 stops the index if it ever happens.

The bytes of a node id, in order:

1. Each field below is written by `IdWriter::field`: its length in bytes as a `u32`, little-endian, then the bytes themselves. Text is written as UTF-8.
2. Field 1: the scope's type, `workspace`, `project` or `stack`.
3. Field 2: the scope's name, the `ProjectId` or `ComposeName`. Empty (length `0`) for `workspace`.
4. Field 3: the origin's path. Empty for a declared node. A `RelPath` is never empty, so this cannot be confused with a real path.
5. Field 4: `NodeKindName::as_str()`, the snake-case name used in storage, such as `function`. Never the enum's discriminant.
6. Field 5: the qualified name.
7. Field 6: the ordinal, as 4 bytes, little-endian. Like every field it has its length in front, so it is written as `04 00 00 00` and then the 4 bytes.
8. The id is the first 8 bytes of the BLAKE3 hash of all the bytes above, shown as 16 lowercase hex characters.

The bytes of a reference id, in order, each written with `IdWriter::field` as above:

1. `from`: the 8 bytes of the `NodeId`, not its hex text.
2. `name`, as UTF-8.
3. `kind.name().as_str()`, the `EdgeKindName` storage name, such as `calls`. The kind's data is not hashed.
4. The site's path.
5. The site's line, as 4 bytes, little-endian.
6. The site's column, as 4 bytes, little-endian.
7. The id is the first 8 bytes of the BLAKE3 hash of all the bytes above.

A content hash is BLAKE3 over the file's bytes, all 32 bytes, shown as 64 lowercase hex characters. No length prefix is written.

Known values. The Rust implementation must give exactly these:

| Inputs | Result |
|---|---|
| Node id: scope type `workspace`, scope name empty, path empty, kind `workspace`, qualified name `workspace`, ordinal `0` | `cf04ba99fe901113` |
| The 55 bytes hashed for the workspace node id | `09000000776f726b7370616365000000000000000009000000776f726b737061636509000000776f726b73706163650400000000000000` |
| Node id: scope type `workspace`, scope name empty, path empty, kind `project`, qualified name `billing-api`, ordinal `0` | `4df6a64e2a4a7034` |
| Reference id: `from` `f5a0e93cff6ed70a`, name `pydantic.BaseModel`, kind `imports`, site path `src/shared_api/models.py`, line `1`, column `0` (the first reference of `graph.json`) | `e4a4bafef9607dfa` |
| Content hash of no bytes | `af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262` |

Every other Acme Shop id is in `examples/acme-shop/site/graph.json`, computed by `examples/acme-shop/lib/ids.py`.

### Scope and origin

What a node belongs to. The scope is part of the node's id.

| Scope | Carries | Nodes that have it |
|---|---|---|
| `Workspace` | nothing | The `Workspace` node, every `Project`, every `Stack`, a `Network` whose real name is known |
| `Project` | a `ProjectId` | The project's `Binary` nodes, its `File` nodes and all code nodes |
| `Stack` | a `ComposeName` | The stack's `Service` and `ExternalService` nodes, their `Topic` and `Queue` nodes, a `Network` whose real name is unknown |

A `RelPath` on a node or an edge starts from the scope's folder: the project's root for a `Project` scope, the workspace root for the other two. Only a path that starts from the workspace root may begin with `..`.

Where a node came from. It is one of two things.

| Origin | Carries | Used for |
|---|---|---|
| `Parsed` | A `RelPath` and a `Span` | A node read from a file: code, and whatever a compose file states |
| `Declared` | nothing | A node that exists because the configuration says so |

A `Stack` is `Parsed` from its first compose file when its Compose name is read from that file or from the file's folder, and `Declared` when the configuration gives the name. A network that no file entry states, such as `billing-api_default`, is `Declared`.

### Node

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `NodeId` | yes | Computed from the fields below |
| `kind` | `NodeKind` | yes | One of the 33 node kinds, holding the kind's own data, which may be nothing |
| `name` | `Name` | yes | The short name, such as `Invoice` |
| `qualified_name` | `QualifiedName` | yes | The full name within the scope, such as `shared_api.models.Invoice` |
| `scope` | `Scope` | yes | What the node belongs to |
| `origin` | `Origin` | yes | Parsed or declared |

A node holds no timestamp and no copy of the source code. Source is read from the file through the node's span when a query needs it. A code node holds no language. Its language is its file's, held by the file record. A project's main language is held by the `Project` node.

Node kinds:

| Group | Kinds |
|---|---|
| Code (24) | `File`, `Module`, `Class`, `Struct`, `Interface`, `Trait`, `Protocol`, `Function`, `Method`, `Property`, `Field`, `Variable`, `Constant`, `Enum`, `EnumMember`, `TypeAlias`, `Namespace`, `Parameter`, `Import`, `Export`, `Route`, `Component`, `Union`, `Command` |
| Workspace (9) | `Workspace`, `Project`, `Binary`, `Stack`, `Service`, `ExternalService`, `Network`, `Topic`, `Queue` |

`NodeKindName::as_str` is the storage name of the kind. It is hashed into every node id, so it never changes. Nineteen of these values appear in `graph.json`. The other fourteen (`module`, `struct`, `interface`, `trait`, `protocol`, `property`, `enum`, `enum_member`, `type_alias`, `namespace`, `export`, `component`, `union`, `queue`) follow the same snake-case rule (storage-model.md, "How a value is written"; SCHEMA.md) and are fixed here:

| Variant | `as_str` | Variant | `as_str` | Variant | `as_str` |
|---|---|---|---|---|---|
| `File` | `file` | `Property` | `property` | `Route` | `route` |
| `Module` | `module` | `Field` | `field` | `Component` | `component` |
| `Class` | `class` | `Variable` | `variable` | `Union` | `union` |
| `Struct` | `struct` | `Constant` | `constant` | `Command` | `command` |
| `Interface` | `interface` | `Enum` | `enum` | `Workspace` | `workspace` |
| `Trait` | `trait` | `EnumMember` | `enum_member` | `Project` | `project` |
| `Protocol` | `protocol` | `TypeAlias` | `type_alias` | `Binary` | `binary` |
| `Function` | `function` | `Namespace` | `namespace` | `Stack` | `stack` |
| `Method` | `method` | `Parameter` | `parameter` | `Service` | `service` |
| | | `Import` | `import` | `ExternalService` | `external_service` |
| | | `Export` | `export` | `Network` | `network` |
| | | | | `Topic` | `topic` |
| | | | | `Queue` | `queue` |

### Node data

The data is part of the kind, as an edge's is, so a kind can never carry another kind's fields. Each `NodeKind` variant holds its data, such as `NodeKind::Function(Callable)`, and a kind without data is a variant with nothing in it, such as `NodeKind::Service`.

| Kinds | Data |
|---|---|
| `Project` | `ProjectData { language }`: the project's main language, from the configuration |
| `Binary` | `BinaryData { framework, framework_source }` |
| `Workspace`, `Stack`, `Service`, `ExternalService`, `Network`, `Topic`, `Queue` | none |
| `Function`, `Method`, `Property` | `Callable { doc, signature, visibility, is_async, is_static, is_abstract, is_exported, decorators, type_parameters, return_type, role }` |
| `Class`, `Struct`, `Interface`, `Trait`, `Protocol`, `Enum`, `Union`, `TypeAlias`, `Component` | `TypeDecl { doc, signature, visibility, is_abstract, is_exported, decorators, type_parameters, role }` |
| `Field`, `Variable`, `Constant` | `Member { visibility, is_static, is_exported, declared_type, default, role }` |
| `Parameter` | A `Member`, and `source` beside it |
| `Route` | `RouteData { method, path, status_code, tags }` |
| `Command` | `CommandData { program, path, help, options }` |
| `File`, `Module`, `Namespace` | `Doc { doc }` |
| `EnumMember`, `Import`, `Export` | none |

The fields:

| Field | Type | Meaning |
|---|---|---|
| `language` | `Language` | `Python` or `TypeScript` |
| `framework` | `Framework` | `NoFramework` (a plain binary, decided to have no framework), `Fastapi { app }` or `Angular` |
| `app` | `QualifiedName`, optional | Inside `Fastapi` only: the qualified name of the binary's app, such as `billing.api.app` |
| `framework_source` | `FrameworkSource` | Where `framework` came from: `Declared` (the configuration), `Compose` (a compose command), `Dockerfile` (a Dockerfile's `CMD` or `ENTRYPOINT`) or `Entry` (the entry file). A plain binary has `Entry`, the last source read, unless the configuration writes `framework: none`, which gives `Declared` |
| `doc` | text, optional | The doc string |
| `signature` | text, optional | The declaration as written, on one line |
| `visibility` | `Visibility`, optional | `Public`, `Private`, `Protected` or `Internal` |
| `is_async`, `is_static`, `is_abstract`, `is_exported` | flag | Each defaults to false |
| `decorators` | list of text | Each decorator's dotted name as written, without arguments, in source order. Defaults to empty |
| `type_parameters` | list of text | Each generic type parameter the declaration introduces, as written with its bound or default, in source order: `T`, `T: int`, `K = str`. Defaults to empty |
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

### Node types in Rust

```rust
// node/kind.rs
/// A node's kind, holding the kind's own data (rule N8 by type).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeKind {
    // code
    File(Doc), Module(Doc), Namespace(Doc),
    Class(TypeDecl), Struct(TypeDecl), Interface(TypeDecl), Trait(TypeDecl), Protocol(TypeDecl),
    Enum(TypeDecl), Union(TypeDecl), TypeAlias(TypeDecl), Component(TypeDecl),
    Function(Callable), Method(Callable), Property(Callable),
    Field(Member), Variable(Member), Constant(Member),
    Parameter { member: Member, source: Option<ParamSource> },
    Route(RouteData), Command(CommandData),
    EnumMember, Import, Export,
    // workspace
    Workspace, Project(ProjectData), Binary(BinaryData), Stack,
    Service, ExternalService, Network, Topic, Queue,
}
impl NodeKind {
    pub fn name(&self) -> NodeKindName;   // one exhaustive match
}

/// The same 33 kinds without data: for ids, filters, storage and rule tables.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum NodeKindName { File, Module, /* ... one per NodeKind variant ... */ Queue }
impl NodeKindName {
    pub const ALL: [NodeKindName; 33];
    pub fn as_str(self) -> &'static str;  // "function", "external_service". Hashed into ids: never change one
    pub fn is_code(self) -> bool;
    pub fn is_workspace(self) -> bool;
}

// node/data.rs. Public fields: these keep no rule alone. Rules that tie them to a kind
// or a language are checked when the node is built.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Callable {
    pub doc: Option<String>, pub signature: Option<String>, pub visibility: Option<Visibility>,
    pub is_async: bool, pub is_static: bool, pub is_abstract: bool, pub is_exported: bool,
    pub decorators: Vec<String>, pub type_parameters: Vec<String>,
    pub return_type: Option<String>, pub role: Option<FrameworkRole>,
}
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct TypeDecl {
    pub doc: Option<String>, pub signature: Option<String>, pub visibility: Option<Visibility>,
    pub is_abstract: bool, pub is_exported: bool,
    pub decorators: Vec<String>, pub type_parameters: Vec<String>, pub role: Option<FrameworkRole>,
}
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Member {
    pub visibility: Option<Visibility>, pub is_static: bool, pub is_exported: bool,
    pub declared_type: Option<String>, pub default: Option<String>, pub role: Option<FrameworkRole>,
}
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Doc { pub doc: Option<String> }
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RouteData { pub method: HttpMethod, pub path: Template, pub status_code: Option<u16>, pub tags: Vec<String> }
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommandData { pub program: String, pub path: Vec<String>, pub help: Option<String>, pub options: Vec<String> }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ProjectData { pub language: Language }
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BinaryData { pub framework: Framework, pub framework_source: FrameworkSource }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Visibility { Public, Private, Protected, Internal }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParamSource { Path, Query, Header, Cookie, Body, Form, File }

// node/framework.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Framework { NoFramework, Fastapi { app: Option<QualifiedName> }, Angular }   // app by type (N10)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FrameworkName { NoFramework, Fastapi, Angular }   // what the configuration names. as_str: "none", "fastapi", "angular"
impl Framework { pub fn name(&self) -> FrameworkName; }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameworkSource { Declared, Compose, Dockerfile, Entry }
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameworkRole {
    App, Router { prefix: Option<Template>, tags: Vec<String> },
    Middleware, ExceptionHandler, LifecycleHook, Fixture, Model,
}

// node/mod.rs
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum Scope { Workspace, Project(ProjectId), Stack(ComposeName) }
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Origin { Parsed { path: RelPath, span: Span }, Declared }

/// What read a parsed node: a source file in a language, or a compose file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ParsedFrom { Source(Language), Compose }

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Node { id: NodeId, kind: NodeKind, name: Name, qualified_name: QualifiedName, scope: Scope, origin: Origin }

pub struct ParsedNode {
    pub scope: Scope, pub path: RelPath, pub span: Span, pub kind: NodeKind,
    pub name: Name, pub qualified_name: QualifiedName, pub ordinal: u32,
}
pub struct DeclaredNode { pub scope: Scope, pub kind: NodeKind, pub name: Name, pub qualified_name: QualifiedName }
pub struct BinaryNode { pub project: ProjectId, pub name: Name, pub data: BinaryData }

impl Node {
    /// N2 to N5, N9, N10. A code kind needs `ParsedFrom::Source`; only Stack, Service,
    /// ExternalService and Network may come from `Compose`.
    pub fn parsed(input: ParsedNode, from: ParsedFrom) -> Result<Self, DomainError>;
    /// N3, N4, N10. Refuses `NodeKind::Binary`: a binary is built by `Node::binary`.
    pub fn declared(input: DeclaredNode) -> Result<Self, DomainError>;
    /// A binary needs its project's language to check its framework (N9).
    /// Scope is `Project(project)` and the qualified name is the binary's name.
    pub fn binary(input: BinaryNode, project_language: Language) -> Result<Self, DomainError>;
    /// The root node: qualified name `workspace`, display name `folder`.
    pub fn workspace(folder: Name) -> Self;

    pub fn id(&self) -> NodeId;
    pub fn kind(&self) -> &NodeKind;
    pub fn kind_name(&self) -> NodeKindName;
    pub fn name(&self) -> &Name;
    pub fn qualified_name(&self) -> &QualifiedName;
    pub fn scope(&self) -> &Scope;
    pub fn origin(&self) -> &Origin;
}
```

`Parameter` holds `source` beside its `Member`, so a field or a variable can never have one. clippy's `large_enum_variant` decides which variants hold a `Box`. A variant that is boxed is boxed in `NodeKind` only. The data types stay unboxed. A declared node has ordinal `0`.

### Edge

| Field | Type | Required | Meaning |
|---|---|---|---|
| `source` | `NodeId` | yes | The node the edge starts at |
| `target` | `NodeId` | yes | The node the edge ends at |
| `kind` | `EdgeKind` | yes | One of the 29 edge kinds, with its data |
| `site` | `Site` | no | Where in a file the relationship occurs, when it has a place |
| `provenance` | `Provenance` | yes | How the edge came to exist. `Declared` holds `note`, the free text of a hand-written dependency or link, when there is one |
| `resolved_by` | `Resolution` | no | The rule that resolved the reference this edge came from. Empty for an edge not made by resolution |

An edge's identity is its source, target, kind and site. The data of a kind is not part of it, and neither is `resolved_by`. Two calls from one function to another on different lines are two edges, because the site differs.

Edge kinds:

| Group | Kinds |
|---|---|
| Code (19) | `Contains`, `Calls`, `Imports`, `Exports`, `Extends`, `Implements`, `References`, `TypeOf`, `Returns`, `Instantiates`, `Overrides`, `Decorates`, `Navigates`, `Mounts`, `Handles`, `Injects`, `Requests`, `Sends`, `Receives` |
| Workspace (10) | `DependsOn`, `Uses`, `EntryPoint`, `Runs`, `BuiltFrom`, `Joins`, `ConnectsTo`, `Publishes`, `Subscribes`, `Invokes` |

The framework kinds are `Mounts`, `Handles`, `Injects`, `Requests`, `Sends` and `Receives`.

`EdgeKindName::as_str` is the storage name of the kind. It is hashed into every reference id, so it never changes. Values not in `graph.json` (`exports`, `extends`, `implements`, `overrides`, `decorates`, `navigates`, `built_from`) follow the same snake-case rule and are fixed here:

| Variant | `as_str` | Variant | `as_str` | Variant | `as_str` |
|---|---|---|---|---|---|
| `Contains` | `contains` | `Instantiates` | `instantiates` | `DependsOn` | `depends_on` |
| `Calls` | `calls` | `Overrides` | `overrides` | `Uses` | `uses` |
| `Imports` | `imports` | `Decorates` | `decorates` | `EntryPoint` | `entry_point` |
| `Exports` | `exports` | `Navigates` | `navigates` | `Runs` | `runs` |
| `Extends` | `extends` | `Mounts` | `mounts` | `BuiltFrom` | `built_from` |
| `Implements` | `implements` | `Handles` | `handles` | `Joins` | `joins` |
| `References` | `references` | `Injects` | `injects` | `ConnectsTo` | `connects_to` |
| `TypeOf` | `type_of` | `Requests` | `requests` | `Publishes` | `publishes` |
| `Returns` | `returns` | `Sends` | `sends` | `Subscribes` | `subscribes` |
| | | `Receives` | `receives` | `Invokes` | `invokes` |

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
| `Declared { note }` | Written by hand in the configuration, with the free text given there, if any | `DependsOn`, `Uses`, `EntryPoint`, `Runs`, `BuiltFrom`, `ConnectsTo`, `Publishes`, `Subscribes` |
| `Scip` | Read from a SCIP index | none yet |
| `Heuristic` | Inferred, and may be wrong | none yet |

A `Contains` edge takes its provenance from the child: `Declared` for a declared child, and for a parsed child the reader that parsed it. So `Contains` takes `TreeSitter`, `Compose` or `Declared`. `Scip` and `Heuristic` are refused on every kind in Release 1. A fact the configuration supplies, such as a service's binary, is `Declared`.

### How an edge was resolved

Provenance storage names, in variant order: `tree_sitter`, `scip`, `manifest`, `compose`, `dockerfile`, `declared`, `heuristic`.

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

Resolution storage names, in the order above: `import`, `self_member`, `same_file`, `project`, `cross_project`, `re_export`, `annotation`, `local_inference`, `inherited`, `flow`, `framework`, `route_match`, `message_match`, `command_match`.

### Edge types in Rust

```rust
// edge/kind.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EdgeKind {
    // code
    Contains, Calls, Exports, Extends, Implements, References, TypeOf, Returns,
    Instantiates, Overrides, Decorates, Navigates, Handles, Injects, Receives,
    Imports { specifier: String, alias: Option<String>, type_only: bool },
    Mounts { prefix: Option<Template>, tags: Vec<String> },
    Requests { method: HttpMethod, path: String },
    Sends { name: String },
    // workspace
    DependsOn { scope: DependencyScope },
    ConnectsTo { protocol: Protocol },
    Invokes { words: Vec<String> },
    Uses, EntryPoint, Runs, BuiltFrom, Joins, Publishes, Subscribes,
}
impl EdgeKind { pub fn name(&self) -> EdgeKindName; }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum EdgeKindName { Contains, Calls, /* ... 29 ... */ Invokes }
impl EdgeKindName {
    pub const ALL: [EdgeKindName; 29];
    pub fn as_str(self) -> &'static str;   // "depends_on"
    pub fn is_code(self) -> bool;          // 19
    pub fn is_workspace(self) -> bool;     // 10
    pub fn is_framework(self) -> bool;     // Mounts, Handles, Injects, Requests, Sends, Receives
}
#[derive(Debug, Clone, Copy, PartialEq, Eq)] pub enum DependencyScope { Build, Dev }
#[derive(Debug, Clone, Copy, PartialEq, Eq)] pub enum Protocol { Http, Grpc, Database }

// edge/provenance.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Provenance { TreeSitter, Scip, Manifest, Compose, Dockerfile, Declared { note: Option<String> }, Heuristic }  // E4 by type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Resolution {
    Import, SelfMember, SameFile, Project, CrossProject, ReExport, Annotation,
    LocalInference, Inherited, Flow, Framework, RouteMatch, MessageMatch, CommandMatch,
}

// edge/mod.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Edge {
    source: NodeId, target: NodeId, kind: EdgeKind,
    site: Option<Site>, provenance: Provenance, resolved_by: Option<Resolution>,
}
pub struct EdgeInput { pub kind: EdgeKind, pub site: Option<Site>, pub provenance: Provenance, pub resolved_by: Option<Resolution> }

/// What makes two edges the same edge (E6). The kind's data is not part of it.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct EdgeKey { pub source: NodeId, pub target: NodeId, pub kind: EdgeKindName, pub site: Option<Site> }

impl Edge {
    /// E1, E2, E3, E13.
    pub fn new(source: &Node, target: &Node, input: EdgeInput) -> Result<Self, DomainError>;
    /// For stores only: E2, E3, E13. Skips E1, which `validate` checked before the write.
    pub fn restore(source: NodeId, target: NodeId, input: EdgeInput) -> Result<Self, DomainError>;
    pub fn source(&self) -> NodeId;
    pub fn target(&self) -> NodeId;
    pub fn kind(&self) -> &EdgeKind;
    pub fn site(&self) -> Option<&Site>;
    pub fn provenance(&self) -> &Provenance;
    pub fn resolved_by(&self) -> Option<Resolution>;
    pub fn key(&self) -> EdgeKey;
}

// edge/reference.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnresolvedReference {
    id: ReferenceId, from: NodeId, name: Name, kind: EdgeKind, site: Site,
    flow_resolved: bool,   // R4: kept after stage 2b resolved it. Not part of the id. `new` sets false
}
impl UnresolvedReference {
    /// R2: `kind` is a code kind. The id hashes `from`, `name`, `kind.name().as_str()`
    /// and the site's path, line and column, with `IdWriter`.
    pub fn new(from: NodeId, name: Name, kind: EdgeKind, site: Site) -> Result<Self, DomainError>;
    /// For stores reading rows back, as `Edge::restore` is. Computes the id from the same
    /// fields as `new`, checks R2 like `new`, and keeps the stored `flow_resolved`.
    pub fn restore(from: NodeId, name: Name, kind: EdgeKind, site: Site, flow_resolved: bool) -> Result<Self, DomainError>;
    pub fn id(&self) -> ReferenceId;
    pub fn from(&self) -> NodeId;
    pub fn name(&self) -> &Name;
    pub fn kind(&self) -> &EdgeKind;
    pub fn site(&self) -> &Site;
    pub fn flow_resolved(&self) -> bool;
}
```

### Records

Records sit beside the nodes and edges. Each is described here with its fields. Their rules are under [Rules](#rules).

**File record.** One per source file the indexer has read. It decides whether a file is read again, and it feeds `status` and `files`.

| Field | Type | Meaning |
|---|---|---|
| `project` | `ProjectId` | The project the file belongs to |
| `path` | `RelPath` | From the project's root |
| `content_hash` | `ContentHash` | The hash of the file's bytes when it was read |
| `size` | number | The file's size in bytes when it was read |
| `mtime` | number | The file's modification time when it was read, in nanoseconds since 1970 UTC |
| `language` | `Language` | Detected from the file |
| `status` | `ParseStatus` | `Parsed`, `Failed` with a message, or `GrammarUnavailable` |

The content hash decides whether a file has changed. The size and mtime let that be answered without reading the file, unless the file is racy. When a file's hash still matches, `index` writes its new size and mtime into the record.

**Unresolved reference.** A name the parser saw and could not yet connect to a node: a call, an import, a base class. Resolution turns it into an edge. One that cannot be resolved stays, for example an import into an excluded file.

| Field | Type | Meaning |
|---|---|---|
| `id` | computed | A hash of the four fields below, made the same way as a `NodeId` |
| `from` | `NodeId` | The node the reference appears in |
| `name` | text | The name as written |
| `kind` | `EdgeKind` | The kind of edge it becomes when resolved, with its data: a `Mounts` reference keeps its prefix. Never a workspace kind |
| `site` | `Site` | Where it appears |
| `flow_resolved` | flag | True for a reference that stage 2b resolved with `Flow`. It is kept so that 2b can try it again at the next index (R4), and queries do not count it as unresolved. Not part of the id. `new` sets it to false, and the value is never changed in place: stage 2 reports the ids it resolved with `Flow` in its output's `flow_resolved: Vec<ReferenceId>`, the store writes the flag, and `restore` reads it back |

**Call site.** One call expression, with its arguments as written. Stage 1 records it from the call's own file, and it is replaced with its file. Stage 2 uses it to carry types and text through calls, and to find HTTP calls.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node the call is in, or the `File` at module level |
| `site` | `Site` | Where the call is |
| `callee` | text | The callee as written: `process`, `self.repo.save`, `models.Invoice` |
| `arguments` | list of `Argument` | In source order |

An `Argument` is a slot, `Position(n)` (from 0) or `Keyword(name)`, and a `Shape`. A `Shape` is one of:

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

**Binding.** One assignment of a name, with the shape of its value. Stage 1 records one per assignment, from its own file, and they are replaced with their file. A `for` target and a `with ... as` target are bindings too. A name is bound once when it has exactly one binding in its `in`.

| Field | Type | Meaning |
|---|---|---|
| `in` | `NodeId` | Where the name lives: the `File` for a module-level name, the `Function` or `Method` for a local name, the `Class` for `self.<name> = ...` in any of its methods and for a class attribute |
| `name` | text | The name assigned, without `self.` |
| `site` | `Site` | Where the assignment is. For a value of shape `Call`, the call site of the same place holds its arguments, such as a client's `base_url` |
| `shape` | `Shape` | The shape of the value |

**Return.** One way a function or method returns, with the shape of its value. A bare `return` is a return of `None`, and so is the end of a body that can be reached without a `return` or a `raise`. Stage 1 records them from their own file, and they are replaced with their file.

| Field | Type | Meaning |
|---|---|---|
| `in` | `NodeId` | The `Function` or `Method` |
| `site` | `Site` | The `return`, or the last line of a body that can end without one |
| `shape` | `Shape` | The shape of the value returned |

`in` is a Rust keyword, so the Rust field of `Binding` and `Return` is `within`.

**Inferred type.** A node's class, worked out by stage 2b. It exists only when all of the node's evidence agrees.

| Field | Type | Meaning |
|---|---|---|
| `node` | `NodeId` | A `Parameter` (evidence: its call sites), a `Function` or `Method` (its returns), a `Field` (its bindings), or a `Variable` or `Constant` bound more than once (its bindings) |
| `class` | `NodeId` | The class all of the evidence gives |
| `evidence` | non-zero number | How many call sites, returns or bindings agreed |

**Reach.** That a root may run a code node, found by stage 2e over resolved edges. A record is per node: a file is reached when its `File` node is, and a node inside the file may be reached by more roots than the file is.

| Field | Type | Meaning |
|---|---|---|
| `node` | `NodeId` | A code node |
| `root` | `Root` | `Binary(NodeId)`: a binary. `Module(NodeId)`: the `File` of a module named in a command or a binary's `app`. `Test(NodeId)`: a test `File` |

**Route path.** One full path of a route, and the binary that serves it, found by stage 2c. A route has one for each way its mounts lead to an app.

| Field | Type | Meaning |
|---|---|---|
| `route` | `NodeId` | The `Route` |
| `binary` | `NodeId`, optional | The FastAPI binary whose `app` the mounts lead to. Empty when no binary names that app |
| `method` | `HttpMethod` | The route's method |
| `full_path` | text | The prefixes and the local path, joined, with names filled in by stage 2b. A part whose value exists only at run time is written `{?}` |
| `complete` | flag, computed | True when no part is unknown. Worked out from `full_path` when asked, not stored on the value |
| `uses_defaults` | flag | True when a part was filled from a settings default, which the environment may change |
| `providers` | list of `NodeId` | The providers that run for this path: from the route, its handler, each router and app on the chain, and each mount on the chain |
| `tags` | list of text | The tags of the route, its routers and its mounts |

**Unmatched HTTP call.** An HTTP client call that stage 2d found, and could not match to exactly one route path. It is kept so that `node` can show it with its candidates.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node the call is in |
| `site` | `Site` | Where the call is |
| `method` | `HttpMethod` | The method of the call |
| `path` | text | The path as written, with unknown parts as `{?}` |
| `candidates` | list of `NodeId` | The routes whose paths matched. Empty when none did |

**Unmatched message.** A producer or consumer call that stage 2f found, and could not match to exactly one declared topic or queue.

| Field | Type | Meaning |
|---|---|---|
| `from` | `NodeId` | The node that sends, or the function or callback that receives |
| `site` | `Site` | Where the call is |
| `direction` | `Send` or `Receive` | |
| `name` | text | The name, with unknown parts as `{?}` |
| `broker` | `NodeId`, optional | The external service the connection names, when known |
| `candidates` | list of `NodeId` | The topics and queues whose names matched. Empty when none did |

**Message payload.** A project class carried on a topic or queue, as the code that sends or receives builds or reads it.

| Field | Type | Meaning |
|---|---|---|
| `topic` | `NodeId` | The `Topic` or `Queue` |
| `node` | `NodeId` | The node at the start of the `Sends` or `Receives` edge |
| `direction` | `Send` or `Receive` | |
| `class` | `NodeId` | The class sent or read |

**Project checkout.** Which version of a project the graph was built from. Each project is its own repository, so each has its own. `status` shows it, and the `operational-support` mode compares it with the release branch a context names for the project.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `project` | `ProjectId` | yes | The project |
| `head` | `Head` | no | What was checked out. Empty when the project is not a git repository |
| `head.commit` | `CommitId` | yes, within `head` | The commit that was checked out |
| `head.branch` | text | no | The branch that was checked out. Empty when the project was on no branch |

**Warning.** Something the indexer noticed that does not stop the run. The warnings of the last index are stored, and `status` shows them. A file that fails to parse is not a warning; its file record holds that.

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
| `StackNamedAfterFolder` | A stack's Compose name comes from its first file's folder, because neither its compose files nor the configuration give a `name`, and a link names that stack with `stack` | The stack |

```rust
// record/file.rs. No rule of its own: public fields.
pub struct FileRecord {
    pub project: ProjectId, pub path: RelPath, pub content_hash: ContentHash,
    pub size: u64, pub mtime: i64, pub language: Language, pub status: ParseStatus,   // mtime in nanoseconds since 1970 UTC
}
pub enum ParseStatus { Parsed, Failed { message: String }, GrammarUnavailable }

// record/flow.rs
pub enum Slot { Position(u32), Keyword(String) }        // C2 "never both" by type
pub struct Argument { pub slot: Slot, pub shape: Shape }
pub struct CallSite { from: NodeId, site: Site, callee: String, arguments: Vec<Argument> }
impl CallSite {
    /// C2: positions run 0, 1, 2 ... with no gap and no repeat.
    pub fn new(from: NodeId, site: Site, callee: String, arguments: Vec<Argument>) -> Result<Self, DomainError>;
    // getters for the four fields
}
pub enum Shape {
    Call(String), Name(String), Text(String), Template(Template),
    Item { name: String, accessor: Accessor },
    Collection { kind: CollectionKind, elements: Vec<Shape> },
    Spread(String), Literal(LiteralKind), Other,
}
pub enum Accessor { Iter, Index, Keys, Values, Items }
pub enum CollectionKind { List, Set, Tuple, Dict }
pub enum LiteralKind { Number, Bytes, Bool, Null }      // Null is Python's `None`: no `None` variant
pub struct Binding { pub within: NodeId, pub name: Name, pub site: Site, pub shape: Shape }   // L2 by type
pub struct Return { pub within: NodeId, pub site: Site, pub shape: Shape }

// record/analysis.rs
pub struct InferredType { pub node: NodeId, pub class: NodeId, pub evidence: NonZeroU32 }   // Y3 by type
pub enum Root { Binary(NodeId), Module(NodeId), Test(NodeId) }
pub struct Reach { pub node: NodeId, pub root: Root }
pub struct RoutePath {
    pub route: NodeId, pub binary: Option<NodeId>, pub method: HttpMethod, pub full_path: String,
    pub uses_defaults: bool, pub providers: Vec<NodeId>, pub tags: Vec<String>,
}
impl RoutePath { pub fn is_complete(&self) -> bool; }   // U2 by type: no `{?}` in full_path

/// Route or topic candidates of a call that matched none or several: never exactly one (M2, G2).
pub struct Candidates(Vec<NodeId>);
impl Candidates {
    pub fn new(ids: Vec<NodeId>, rule: RuleId) -> Result<Self, DomainError>;   // any RuleId, used only in the error; M2 or G2 in practice
    pub fn none() -> Self;
    pub fn as_slice(&self) -> &[NodeId];
}
pub struct UnmatchedHttpCall { pub from: NodeId, pub site: Site, pub method: HttpMethod, pub path: String, pub candidates: Candidates }
pub enum MessageDirection { Send, Receive }   // not `Direction`: that name is the store's Out | In | Both
pub struct UnmatchedMessage {
    pub from: NodeId, pub site: Site, pub direction: MessageDirection, pub name: String,
    pub broker: Option<NodeId>, pub candidates: Candidates,
}
pub struct MessagePayload { pub topic: NodeId, pub node: NodeId, pub direction: MessageDirection, pub class: NodeId }

// record/warning.rs
pub enum WarningCode {
    NetworkNameUnknown, LinkWithoutSharedNetwork, DependencyPathNotAProject, FrameworkMismatch,
    FrameworkAppNotFound, EntryCommandMismatch, DockerfileUnreadable, FlowRoundLimit,
    HttpCallWithoutLink, MessageWithoutLink, CommandNotFound, StackNamedAfterFolder,
}
pub struct Warning { code: WarningCode, subject: Option<NodeId>, message: String }
impl Warning {
    pub fn new(code: WarningCode, subject: Option<NodeId>, message: String) -> Result<Self, DomainError>;   // A1
    // getters
}

// record/checkout.rs
pub struct Head { pub commit: CommitId, pub branch: Option<String> }
pub struct ProjectCheckout { pub project: ProjectId, pub head: Option<Head> }   // P3 by type
```

Every record type derives `Debug`, `Clone`, `PartialEq` and `Eq`. The fieldless enums also derive `Copy` and `Hash`, and have `as_str` with their snake-case storage names.

### The graph

```rust
/// Everything one index produces. Public fields: a graph keeps no rule while it is
/// being assembled. `validate` checks it once it is finished.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Graph {
    pub nodes: Vec<Node>, pub edges: Vec<Edge>, pub files: Vec<FileRecord>,
    pub references: Vec<UnresolvedReference>,
    pub call_sites: Vec<CallSite>, pub bindings: Vec<Binding>, pub returns: Vec<Return>,
    pub inferred_types: Vec<InferredType>, pub reach: Vec<Reach>, pub route_paths: Vec<RoutePath>,
    pub unmatched_http_calls: Vec<UnmatchedHttpCall>, pub unmatched_messages: Vec<UnmatchedMessage>,
    pub payloads: Vec<MessagePayload>, pub warnings: Vec<Warning>, pub checkouts: Vec<ProjectCheckout>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RuleViolation { pub rule: RuleId, pub message: String }

impl Graph {
    /// Every Graph rule. Returns every violation, sorted by rule then message. Empty when valid.
    pub fn validate(&self) -> Vec<RuleViolation>;
}

// fixtures/mod.rs, #[cfg(test)] only
pub fn acme_workspace_layer() -> Result<Graph, DomainError>;   // 27 nodes, 54 edges
pub fn acme() -> Result<Graph, DomainError>;                   // plus the code layer of python-parsing.md
```

### How the types are written

The tables above say what each type holds. This says how a Rust type holds it, so that the compiler keeps as many rules as it can and a check keeps only the rest. A rule marked Type has no check and no test: a value that breaks it cannot be written.

Newtypes. Every value with a rule of its own is a newtype: a struct with one private field.

- **One way in.** A value read from text is built by `parse(&str) -> Result<Self, DomainError>`. A computed value has a named constructor, such as `ContentHash::of`. There is no public field, no `From<String>`, and no constructor that skips the rule.
- **The narrowest inner type.** `NodeId` and `ReferenceId` hold `[u8; 8]`, and `ContentHash` holds `[u8; 32]`. The hex text exists only in `Display` and `parse`. `Line` and `evidence` hold a `NonZeroU32`, so 0 cannot be held.
- **Read access, not conversion.** A text newtype offers `as_str(&self) -> &str` and `Display`. It does not implement `Deref<Target = str>`, because that would let every `&str` method treat a `RelPath` as plain text.
- **Derives.** Every newtype derives `Debug`, `Clone`, `PartialEq`, `Eq` and `Hash`. A newtype with a fixed-size inner value also derives `Copy`: `NodeId`, `ReferenceId`, `ContentHash`, `Line`, `Column`, `Span`. `PartialOrd` and `Ord` are derived only where the order means something: `Line`, `Column`, `Span`, `RelPath`.
- **Serde through the rule.** A newtype that is read with serde uses `#[serde(try_from = "String", into = "String")]`, so reading one runs `parse`.
- **No rule, no newtype.** A doc string, a signature, a decorator, a branch name or a note is a plain `String`.

Other types:

- A type that keeps a rule has private fields and a constructor that returns `Result<Self, DomainError>`. A type that keeps no rule has public fields and no constructor. Getters are added only where fields are private.
- Every public type derives `Debug`, `Clone`, `PartialEq` and `Eq`. A type is `Copy` only when it is a fixed size and holds no `String` or `Vec`.

Enums:

- **A variant holds its data.** When a value is one of several things, and each thing has its own fields, it is one enum whose variants hold those fields. It is never a tag beside an optional struct. `NodeKind`, `EdgeKind`, `Framework`, `Provenance`, `Scope`, `Origin`, `Shape`, `Root` and `ParseStatus` all follow this.
- **Kinds that share data share a type.** `NodeKind::Function(Callable)` and `NodeKind::Method(Callable)`. A kind without data is a unit variant: `NodeKind::Service`, `EdgeKind::Calls`.
- **A fieldless twin names a kind.** Code that needs a kind without its data, to filter, to hash into an id, to store or to look up a rule table, uses a fieldless enum beside the data enum: `NodeKindName`, `EdgeKindName`, `FrameworkName`. `fn name(&self)` maps one to the other in one `match`. The id hashes the name, never the data (N2).
- **Absence is `Option`.** No enum has a `None` variant: it would shadow `Option::None`, and give two ways to say "nothing". A choice that is a real answer gets a name of its own, as `Framework::NoFramework` does for a binary decided to have no framework.
- **Matches are exhaustive.** No `match` in `src/domain` on these enums has a `_` arm, and none of them is `#[non_exhaustive]`. The crate is one binary, so a new kind should break every match that has to decide about it.
- **Flags stay `bool`** when each is an independent yes or no and every combination is valid, as `is_async`, `is_static`, `is_abstract`, `is_exported` and `type_only` are. A choice between two named things is an enum: `DependencyScope::Build` or `Dev`, never `is_dev`.
- **Large variants are boxed.** clippy's `large_enum_variant` is denied in this crate. A variant that trips it holds its data in a `Box`, such as `NodeKind::Function(Box<Callable>)`. Which variants need it is found by clippy, not decided here.

Building nodes and edges:

- **Private fields, read through methods.** `Node` and `Edge` have no public field and no setter. A changed node is a new node, since its id depends on its fields.
- **One input struct per constructor.** `Node::parsed`, `Node::declared` and `Node::binary` each take one struct of named fields, not a long list of arguments, so two fields of the same type cannot be swapped by mistake. `Node::parsed` also takes what read the node, a source file in a `Language` or a compose file, for N4 and N9. `Node::binary` takes its project's `Language`, for N9. Neither stores the language.
- **An edge is built from its ends.** `Edge::new` takes `&Node` for the source and the target, so it can check E1 and E2 against their kinds. A store that reads edges back uses `Edge::restore`, which takes the ids and skips E1: what a store holds passed `validate` before it was written. Only stores call `restore`.
- **A build error names its rule.** A value that breaks a rule gives `DomainError::Rule`, which carries the rule's `RuleId`, as `RuleViolation` does, so a test can check that the right rule refused the value. Text that does not have the form of its value type gives `DomainError::Malformed`, naming the type.

## Rules

Enforced is one of Type, Build, Graph or Indexer. A Type rule has no check. A Build rule is checked by the constructor named in [Interface](#interface). A Graph rule is checked by `Graph::validate`. An Indexer rule is kept by how the indexer runs; its id is defined here so that the indexing modules and their tests can name it.

### Node rules

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

| Id | Rule | Enforced |
|---|---|---|
| N1 | `name` and `qualified_name` are not empty | Type |
| N2 | The id equals the hash of the five inputs. A node cannot be built with any other id | Build |
| N3 | The scope suits the kind, as in the Scope table | Build |
| N4 | A code node is always `Parsed`. `Workspace`, `Project`, `Binary`, `Topic` and `Queue` are always `Declared`. The other workspace kinds may be either | Build |
| N5 | Building the same node twice from the same inputs gives the same id | Build |
| N6 | No two nodes in a graph share an id | Graph |
| N7 | There is exactly one `Workspace` node | Graph |
| N8 | The data suits the kind, as in the node data table | Type |
| N9 | A code node's data suits the language of the file it is parsed from, and a binary's framework suits its project's language, as in the language table. The language is given when the node is built and is not stored on it | Build |
| N10 | A role suits the kind, as in the role table. `app` is given only when `framework` is `Fastapi` | Build for the role, Type for `app` |

How the node constructors check them:

| Rule | Refuses |
|---|---|
| N3 | Any scope the Scope table does not give the kind. A `..` path under a `Project` scope too |
| N4 | A declared code node. A parsed `Workspace`, `Project`, `Binary`, `Topic` or `Queue`. A code kind from `ParsedFrom::Compose`, a workspace kind from `ParsedFrom::Source`. Only `Stack`, `Service`, `ExternalService` and `Network` may come from `Compose` |
| N9 | Python with `Protected` or `Internal`, or with `Angular`. TypeScript with `Fastapi` |
| N10 | `App` or `Router` off a `Variable`. `Middleware`, `ExceptionHandler`, `LifecycleHook` or `Fixture` off a `Function` or `Method`. `Model` off a `Class` |

N2 and N5 need no check: the id is computed in the constructor and there is no other way to set it.

### Edge rules

The workspace edge table. Each of the ten workspace edge kinds may only connect these node kinds (rule E1). Code edges are not restricted by E1. The six framework edges are restricted by E11.

| Workspace kind | From | To | Meaning |
|---|---|---|---|
| `DependsOn` | Project | Project | Uses the other project's code |
| `Uses` | Project | Stack | Uses that stack: the project's own stack, or a shared stack that lists the project |
| `EntryPoint` | Binary | File | Starts at this file |
| `Runs` | Service | Binary | Runs this binary |
| `BuiltFrom` | Service | Project | Is built from this project, binary unknown |
| `Joins` | Service, ExternalService | Network | Is on this network |
| `ConnectsTo` | Project, Binary | Project, Service, ExternalService | Reaches it over HTTP, gRPC or a database protocol |
| `Publishes` | Project, Binary | Topic, Queue | Sends messages to it |
| `Subscribes` | Project, Binary | Topic, Queue | Receives messages from it |
| `Invokes` | Service | Command | Runs this command of its binary. Found in stage 2, from the service's compose command |

The framework edges. Six code edge kinds hold what a web framework does with code, what calls it over HTTP, and what sends and handles messages. `Mounts`, `Handles` and `Injects` are made by resolving a reference a framework profile records, so each has `resolved_by: Framework`. `Requests` is made by matching an HTTP client call to a route path, so it has `resolved_by: RouteMatch`. `Sends` and `Receives` are made by matching a producer or consumer to a declared topic or queue, so they have `resolved_by: MessageMatch`. An `Injects` edge from an app or router that has the same site as a `Mounts` edge from that node was given at the mount, and applies only to routes reached through it.

| Kind | From | To | Data | Says | Read by |
|---|---|---|---|---|---|
| `Mounts` | A `Variable` with role `App` or `Router` | A `Variable` with role `App` or `Router`, or a `Route` | `prefix`, optional | The source serves the target, under the prefix. From `include_router`, `mount` and a route decorator on a router or app | Route paths, `node` on a route, reach (downwards), `impact` |
| `Handles` | A `Route` or a `Command` | A `Function` or `Method` | none | This function runs when the route is called, or when the command is run | Reach, `impact` from a handler to its endpoints and services, `callers` |
| `Injects` | A `Function`, `Method` or `Route`, or a `Variable` with role `Router` | A `Function`, `Method` or `Class` | none | The framework calls the target and passes the result in, as FastAPI's `Depends` does, and as pytest does with a fixture | Reach, `impact` from a provider to every route that uses it, "which providers does this route use", the tests to run |
| `Requests` | A `Function`, `Method` or `File` | A `Route` | `method`, `path` | This code calls the route over HTTP: from another project, or from a test through `TestClient` | Reach, `impact`, the tests to run, API contracts, `node` on a route |
| `Sends` | A `Function`, `Method` or `File` | A `Topic` or `Queue` | `name` | This code sends messages to the topic or queue | `impact`, event contracts, `node` on a topic |
| `Receives` | A `Function` or `Method` | A `Topic` or `Queue` | none | This code handles the messages of the topic or queue | `impact`, event contracts, `node` on a topic |

| Id | Rule | Enforced |
|---|---|---|
| E1 | A workspace edge connects only the node kinds its row allows in the workspace edge table. `Edge::new` takes the two end nodes, not their ids, so that it can check this | Build |
| E2 | A workspace edge never starts and ends at the same node | Build |
| E3 | The provenance suits the kind, as in the provenance table | Build |
| E4 | `note` appears only on a `Declared` edge | Type |
| E5 | Both ends of every edge are nodes in the graph | Graph |
| E6 | No two edges share source, target, kind and site. Two calls from one function to another on different lines are two edges | Graph |
| E7 | There is at most one `DependsOn` edge from one project to another. When the manifest and the configuration both name the pair, the declared one is kept | Graph |
| E8 | A `Service` has exactly one of `Runs` or `BuiltFrom`. An `ExternalService` has neither | Graph |
| E9 | A `Binary` has exactly one `EntryPoint`, and it leads to a `File` of the same project | Graph |
| E10 | A `Runs` edge leads to a binary of the project whose folder the service is built from | Graph |
| E11 | A framework edge joins only these: `Mounts` from a `Variable` with role `App` or `Router` to such a `Variable` or to a `Route`. `Handles` from a `Route` to a `Function` or `Method`. `Injects` from a `Function`, `Method`, `Route` or `Variable` with role `Router` to a `Function`, `Method` or `Class`. `Requests` from a `Function`, `Method` or `File` to a `Route`. `Handles` may also start at a `Command`. `Sends` from a `Function`, `Method` or `File`, and `Receives` from a `Function` or `Method`, to a `Topic` or `Queue` | Graph |
| E12 | An edge with `resolved_by: Flow` rests on at least one inferred type: of a parameter of its callable, of the return of a function its receiver came from, of a field, or of a name bound more than once | Graph |
| E13 | `resolved_by` is given only on a code edge with provenance `TreeSitter` or `Scip`, and on `Invokes` (provenance `Compose` or `Dockerfile`). `Flow` is given only on `Calls` and `Instantiates`. `Framework` is given only on `Mounts`, `Handles` and `Injects`, and those three always have it. `RouteMatch` is given only on `Requests`, `MessageMatch` only on `Sends` and `Receives`, and `CommandMatch` only on `Invokes`, and each of those kinds always has its value | Build |

How the edge constructors check them. The tables are `match` expressions over `EdgeKindName` and `NodeKindName`, with no `_` arm.

| Rule | Refuses |
|---|---|
| E1 | Ends that the workspace edge table does not allow. Code kinds pass |
| E2 | A workspace kind with `source == target`. A code loop, such as a recursive `Calls`, is allowed |
| E3 | A provenance the provenance table does not give the kind. `Contains` takes `TreeSitter`, `Compose` or `Declared`. `Scip` and `Heuristic` are refused everywhere in Release 1 |
| E13 | Every clause of E13, in both directions: `Mounts` without `Framework` is refused, and so is `Framework` on `Calls` |

`Edge::restore` skips only E1. It still checks E2, E3 and E13.

### Containment tree rules

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

### File record rules

| Id | Rule | Enforced |
|---|---|---|
| F1 | No two records share project and path | Graph |
| F2 | Every `File` node has a record with the same project and path, and every record has a `File` node | Graph |
| F3 | A file whose record is not `Parsed` has a `File` node and no nodes below it | Graph |
| F4 | A record with `GrammarUnavailable` is read again on the next index, even when the hash is unchanged | Indexer |

### Unresolved reference rules

| Id | Rule | Enforced |
|---|---|---|
| R1 | `from` is a node in the graph | Graph |
| R2 | `kind` is a code edge kind | Build |
| R3 | No two references share an id | Graph |
| R4 | A resolved reference is removed, and exactly one edge replaces it, with the same `from`, kind and site. Two exceptions: an `Overrides` reference whose bases all resolved, and none has the name, is removed with no edge. A reference resolved with `Flow` is kept, marked as resolved by flow, so that it can be tried again when the flow edges are rebuilt at the next index | Indexer |

### Call site rules

| Id | Rule | Enforced |
|---|---|---|
| C1 | `from` is a node in the graph | Graph |
| C2 | Each argument has a position or a keyword, never both. Positions run from 0 without a gap | Type for "never both", Build for the gap |
| C3 | No two call sites share `from` and `site` | Graph |

`CallSite::new` refuses positions with a gap or a repeat. Keywords after the positions are allowed.

### Binding rules

| Id | Rule | Enforced |
|---|---|---|
| L1 | `in` is a `File`, `Function`, `Method` or `Class` node in the graph | Graph |
| L2 | `name` is not empty | Type |
| L3 | No two bindings share `in`, `name` and `site` | Graph |

### Return rules

| Id | Rule | Enforced |
|---|---|---|
| B1 | `in` is a `Function` or `Method` node in the graph | Graph |
| B2 | No two returns share `in` and `site` | Graph |

### Inferred type rules

| Id | Rule | Enforced |
|---|---|---|
| Y1 | `node` is a `Parameter`, `Function`, `Method`, `Field`, `Variable` or `Constant` node, and `class` is a `Class`, `Protocol` or `Enum` node | Graph |
| Y2 | At most one inferred type per node | Graph |
| Y3 | `evidence` is at least 1 | Type |
| Y4 | Every index removes all inferred types and every edge with `resolved_by: Flow`, and writes the ones it computed | Indexer |

### Reach rules

| Id | Rule | Enforced |
|---|---|---|
| H1 | `node` is a code node in the graph. A `Binary` root is a `Binary` node; a `Module` or `Test` root is a `File` node | Graph |
| H2 | No two reach records share `node` and `root` | Graph |
| H3 | Every index removes all reach records and writes the ones it computed | Indexer |

### Route path rules

| Id | Rule | Enforced |
|---|---|---|
| U1 | `route` is a `Route` node. `binary`, when given, is a `Binary` node whose framework is `Fastapi` | Graph |
| U2 | `complete` is true exactly when `full_path` holds no `{?}` | Type |
| U3 | No two route paths share `route`, `binary` and `full_path` | Graph |
| U4 | Every index removes all route paths and writes the ones it computed | Indexer |
| U5 | Every provider is a `Function`, `Method` or `Class` node | Graph |

### Unmatched HTTP call rules

| Id | Rule | Enforced |
|---|---|---|
| M1 | `from` is a node in the graph, and every candidate is a `Route` node | Graph |
| M2 | There is never exactly one candidate: one candidate is a `Requests` edge instead | Build |
| M3 | Every index removes all unmatched HTTP calls and every `Requests` edge, and writes the ones it computed | Indexer |

### Unmatched message rules

| Id | Rule | Enforced |
|---|---|---|
| G1 | `from` is a node in the graph, `broker` is an `ExternalService`, and every candidate is a `Topic` or `Queue` | Graph |
| G2 | There is never exactly one candidate | Build |
| G3 | Every index removes all unmatched messages and every `Sends` and `Receives` edge, and writes the ones it computed | Indexer |

The rule ids `G1` to `G3` name rules. The capability ids `G1` to `G12` in this spec's header name capabilities. They are two different lists.

### Message payload rules

| Id | Rule | Enforced |
|---|---|---|
| D1 | `topic` is a `Topic` or `Queue`, `class` is a `Class`, and a `Sends` or `Receives` edge of that direction joins `node` to `topic` | Graph |
| D2 | No two payloads share `topic`, `node`, `direction` and `class` | Graph |
| D3 | Every index removes all payloads and writes the ones it computed | Indexer |

### Project checkout rules

| Id | Rule | Enforced |
|---|---|---|
| P1 | There is at most one checkout per project | Graph |
| P2 | `project` is a `Project` node in the graph | Graph |
| P3 | A `branch` is given only together with a `commit` | Type |
| P4 | Every index writes the checkout of each project it indexes, read from the project's own `.git` folder. Nothing is fetched | Indexer |

### Warning rules

| Id | Rule | Enforced |
|---|---|---|
| A1 | `message` is not empty | Build |
| A2 | A `subject`, when given, is a node in the graph | Graph |
| A3 | Every index replaces all stored warnings with the ones it raised | Indexer |

### Rules the types keep

| Rule | How the type keeps it |
|---|---|
| N1, L2 | `Name` and `QualifiedName` cannot be empty |
| N8 | The data is inside the `NodeKind` variant, so no other data can be there. `source` is held by `Parameter` beside its `Member`, so no other member kind can have one |
| N10, for `app` | `app` is a field of `Framework::Fastapi` and of no other variant |
| E4 | `note` is a field of `Provenance::Declared` and of no other variant |
| C2, for "never both" | An argument's slot is `Position(u32)` or `Keyword(String)` |
| U2 | `complete` is not stored. `RoutePath::is_complete()` works it out from `full_path` |
| Y3 | `evidence` is a `NonZeroU32` |
| P3 | `commit` and `branch` sit together in `Head { commit: CommitId, branch: Option<String> }`, and a checkout holds `head: Option<Head>` |

### Where `validate` checks each Graph rule

| Group | Rules |
|---|---|
| Nodes | N6, N7 |
| Edges | E5 to E12 |
| Tree | T1 to T5 |
| Records | F1 to F3, R1, R3, C1, C3, L1, L3, B1, B2, Y1, Y2, H1, H2, U1, U3, U5, M1, G1, D1, D2, P1, P2, A2 |

## Behaviour

### Building values

A value is built through its constructor, or it does not exist. A newtype read from text that has the wrong form gives `DomainError::Malformed`, naming its `ValueKind`. A value that breaks a Build rule gives `DomainError::Rule`, naming the rule. Examples:

- `ProjectId::parse("Billing")` gives `Malformed { value: ProjectId, .. }`.
- `Line::new(0)` gives `Malformed { value: Line, .. }`.
- `Node::declared` with a `Service` in a `Project` scope gives `Rule { rule: N3, .. }`, whose text starts with `rule N3:`.
- `Edge::new` for `Joins` from a `Function` to a `Network` gives `Rule { rule: E1, .. }`.
- `Candidates::new(vec![id], M2)` gives `Rule { rule: M2, .. }`. With `G2` it names `G2`.

### Ids

- **Stable.** Building the same node twice gives the same id (N5). Building the Acme fixture twice gives equal graphs.
- **The scope decides.** The two `api` services of Acme Shop have the same kind and the same name. One is in stack `billing-api` and one in stack `ledger`, so their ids differ. A project named `billing` and a stack named `billing` also differ, because the scope's type is hashed with its name.
- **The root is the same everywhere.** The workspace node's qualified name is always `workspace`, so its id is `cf04ba99fe901113` on every machine. The folder name is only its display name.
- **The ordinal separates duplicates.** Two `Function`s `f` in one file have ordinals `0` and `1`, and different ids. Line numbers are not hashed, so editing a line above a function keeps its id.
- **Renames change ids.** Renaming a project's id, or moving a file, gives its nodes new ids.
- **Reference ids** follow the same pattern: two builds of one reference give one id, and another line gives another id.

### Validating a graph

`Graph::validate` checks every Graph rule. It returns every violation, not only the first, sorted by `RuleId` order and then by message. A valid graph gives an empty list. An empty graph gives exactly one violation, N7. A graph that breaks N7, E5 and F1 gives all three, in that order.

A rule whose input is missing reports nothing, and leaves that to the rule about the missing part. An edge to an unknown node breaks E5 only, not E1, T2 or E11 as well. T3 walks parents with a visited set, so two nodes that contain each other give T3 once, and `validate` returns. Each violation's message names the node or edge it is about, by id and qualified name.

`index` runs `validate` before it writes. A store reads edges back with `Edge::restore`, since what it holds passed `validate` before the write.

### The Acme Shop graph

The workspace layer of Acme Shop, built by hand through the constructors, passes `validate` and has exactly these counts:

| Nodes | Count | | Edges | Count |
|---|---|---|---|---|
| `Workspace` | 1 | | `Contains` | 26 |
| `Project` | 4 | | `DependsOn` | 2 |
| `Binary` | 5 | | `Uses` | 4 |
| `File` | 5 | | `EntryPoint` | 5 |
| `Stack` | 3 | | `Runs` | 4 |
| `Service` | 4 | | `BuiltFrom` | 0 |
| `ExternalService` | 2 | | `Joins` | 8 |
| `Network` | 2 | | `ConnectsTo` | 3 |
| `Topic` | 1 | | `Publishes` | 1 |
| `Queue` | 0 | | `Subscribes` | 1 |
| **Total** | **27** | | **Total** | **54** |

The five `File` nodes are the binaries' entry files, each with a file record. `EntryPoint` needs them as targets. There are 26 `Contains` edges because every node but the root has one parent. `web-app`'s entry file `projects/admin/src/main.ts` is TypeScript, which is not parsed in Release 1: it still gets a `File` node and a record with `GrammarUnavailable`, so `EntryPoint` has a target.

The walk. "I am renaming a field on `Invoice` in `shared-api`. What breaks?"

1. Start at Class `Invoice`.
2. Follow `Imports` edges backwards. They lead to files in `billing-api` and `ledger-api`, among them billing's `worker.py` and `api.py`.
3. Both are entry files. Follow `EntryPoint` backwards from each to Binary `worker` and Binary `api`.
4. From Binary `worker`, follow `Publishes` to Topic `kafka/invoice.created`.
5. From the topic, follow `Subscribes` backwards to Binary `consumer` of `ledger-api`.
6. From Binary `api`, follow `Runs` backwards to Service `api` of stack `billing-api`, then `ConnectsTo` backwards to Binary `admin` of `web-app`.

The walk crosses all three layers and all four projects. Each edge's provenance tells the reader how far to trust that step: step 2 comes from source code, and steps 4 to 6 rest on hand-written links. A file that imports `Invoice` and is not an entry file is reached the same way, one step longer: from the file up to its project through `Contains`, then down to that project's binaries.

`acme()` adds the code layer and shows that:

- Billing's `api` binary has `framework: Fastapi { app: billing.api.app }`, and `worker` has `framework: NoFramework`.
- The route `GET /{invoice_id}` reaches billing's app through two `Mounts` edges, and has one route path: `GET /v1/invoices/{invoice_id}`, complete, served by `api`.
- `r` in `process` has the inferred type `InvoiceRepo` from 2 call sites, and `r.save()` is a `Calls` edge to `InvoiceRepo.save` with `resolved_by: Flow`, and its reference is kept.
- The file `routes/invoices.py` is reached by billing's `api` and the test `test_api.py`, and not by `worker`. Its handler `get_invoice` is also reached by ledger's `api`. `services.py` is reached by `worker` and the test `test_services.py`, and not by `api`. The package files `billing/__init__.py` and `billing/routes/__init__.py` are reached by billing's `api`.
- The fixture `repo` has the inferred return `InvoiceRepo`, from 1 return.
- Ledger's `fetch_invoice` has a `Requests` edge to `GET /{invoice_id}`, with `resolved_by: RouteMatch`, and the index raises one `HttpCallWithoutLink` warning about it.
- `test_get_invoice` has a `Requests` edge to the same route and an `Injects` edge to the fixture `repo`, and `impact` on the handler `--tests` lists it.
- `send_invoice` has a `Sends` edge, and `run_consume` a `Receives` edge, to `kafka/invoice.created`, each with `Invoice` as payload.
- Ledger's `consumer` binary has the commands `ledger-consumer`, `ledger-consumer run` and `ledger-consumer replay`, and the `consumer` service an `Invokes` edge to `ledger-consumer run`.

### What the queries rely on

Each query works only if the model keeps certain rules.

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

### Decisions this spec holds

| Point | Decision |
|---|---|
| The id is computed from scope, path, kind, qualified name and ordinal | Why: The same node gets the same id on every index, and edges can be built before storing. A database id would change on every index |
| No line number in the id | Why: Editing a line above a function would change its id |
| BLAKE3, 64 bits, 16 hex characters | Why: Short enough for an AI to read and repeat. 128 bits doubles the text for a negligible risk. One algorithm also hashes file content, faster than SHA-256 |
| The scope is part of the id | Why: Once a workspace has several projects, a file path is not unique, and services belong to no project |
| One graph for the whole workspace | Why: A link between two projects is an ordinary edge, and one walk can cross projects |
| Project, binary and service are three kinds | Why: Billing's `api` service listens for HTTP and `worker` does not, although both are built from one project and one Dockerfile |
| A node is parsed or declared | Why: A service, a network or a topic has no file |
| Data is part of the kind, for nodes and edges | Why: A flat set of optional fields allowed an async service and a protected Python method. One data type per kind and language multiplies with each language |
| Language on the `Project` node and the file record, not on code nodes | Why: A code node's language is always its file's. A copy could only disagree |
| Framework relationships are three edge kinds of their own | Why: Each question about a route is one edge kind. `References` with a role could not link a route to its app |
| A route's full path is a record, computed in stage 2 | Why: The prefixes sit in other files, so a change to one would rewrite route nodes elsewhere. Computing it at query time would stop `search` finding it |
| Provenance stays coarse, and `resolved_by` records the rule | Why: A `Flow` provenance would mix "where the facts came from" with "which rule connected them". `Heuristic` would understate edges that are never wrong within what the workspace shows |
| Workspace edges have rules about what they connect | Why: A `Joins` edge from a function to a network is a bug |
| Topics, queues and links are never created from code | Why: A name in code can be a typo or another environment's topic. What the code shows is matched against what the configuration declares |
| Source code | The graph stores where a node is, not its source. A query reads the source from the file through the node's span, and marks a file that has changed since the last index |
| The root node's name | The qualified name is always `workspace`, so the id is the same on every machine. The folder name is only the display name |
| A network whose real name is unknown | It has a `Stack` scope and sits below its stack, since the configuration treats it as private to the stack |
| `Uses` for a project's own stack | A project gets a `Uses` edge to its own stack as well as to each shared stack that lists it |
| A binary's entry file in a language that is not parsed yet | The file still gets a `File` node and a record with `GrammarUnavailable`, so `EntryPoint` has a target. `web-app` needs this in Release 1 |
| Lines and columns | Lines count from 1, columns from 0 |
| Edge identity | The data of a kind is not part of an edge's identity |
| `callers` on a class | `Instantiates` edges count as calls |
| The depth of `impact` | `--depth` limits the walk through the code only, 2 by default. The runtime links after it are always followed |
| The hash | BLAKE3 for ids and for file content. A node id is 64 bits, written as 16 hex characters |
| Warnings | A structured record: a code, an optional subject node and a message |
| The release a graph was built from | A checkout is kept for each project, not one for the workspace, so that the `operational-support` mode can check each project against its release branch |
| Node data | Part of the kind, as an edge's data is. A field a kind does not have cannot be set. In Rust, each `NodeKind` variant holds its data, so there is no separate data field |
| Rust types | Newtypes for every value with a rule, data held inside enum variants, a fieldless `...Name` enum where a kind is needed without its data, no `None` variants. Rules N1, N8, E4, L2, P3, U2 and Y3 are kept by the types, and part of N10 and C2 |
| A binary with no framework | `Framework::NoFramework`, stored as `none`, not an absent value, so that the configuration's "not given" stays distinct from "decided: none" |
| A plain binary's `framework_source` | `Entry`, the last source read, or `Declared` when the configuration writes `framework: none` |
| Language | On the `Project` node, from the configuration, and on the file record, detected. Not on code nodes |
| Types carried from callers | Only when every call site in the workspace passes the same class. Such edges have `resolved_by: Flow`, and their references are kept. Up to 10 rounds by default, set by `analysis.flow_rounds` |
| How an edge was resolved | Provenance stays coarse. Every resolved edge records `resolved_by`, the rule that connected it. No `Flow` provenance |
| Framework edges | `Mounts`, `Handles` and `Injects`, each a kind of its own |
| A route's full path | Computed by stage 2c and stored as a route path, not on the route node |
| Type-only imports | `Imports` carries `type_only`. Resolution treats them as any import; reach does not follow them |
| HTTP calls in code | Matched to route paths as `Requests` edges. They never create a `ConnectsTo` link; a cross-project match with no declared link is a warning |
| Messages in code | Matched to declared topics and queues as `Sends` and `Receives` edges, with their payloads. Topics and queues are still created only from the configuration |
| Dockerfiles | Read for the command line a service runs: its binary when nothing else names it, its framework, and the command it invokes. Facts from them have the `Dockerfile` provenance |
| Commands | `argparse` parsers and subcommands are `Command` nodes. A compose service is linked to the command it runs by `Invokes`, computed in stage 2, with the provenance of the command line (`Compose` or `Dockerfile`) and `resolved_by: CommandMatch` |
| A stack's origin | `Parsed` when its Compose name comes from its compose file or that file's folder, `Declared` when the configuration names it |
| The reference output | `examples/acme-shop` builds the Acme Shop graph with scripts, and is what the Rust implementation is checked against |
| Ordering of ids | `NodeId` and `ReferenceId` derive no `PartialOrd` or `Ord`, as domain-model.md decides: the order of ids means nothing. Only `Line`, `Column`, `Span` and `RelPath` derive them. This departs on purpose from the step 1 plan, which derived them on both ids |
| No public `NodeId::compute` | domain-model.md names `NodeId::compute` as an example of a computed value's constructor. It is replaced by the `pub(crate)` id writer used inside `Node`'s and `UnresolvedReference`'s constructors, so no code outside them can compute an id |
| An unresolved reference's `name` | A `Name`, as the step 1 plan has it, so an empty name cannot be held. domain-model.md writes it as text |
| `Mounts` data | `prefix` and `tags`, as domain-model.md and the step 1 plan have it. graph-model.md mentions only the prefix |
| The field `in` of `Binding` and `Return` | Written `within` in Rust, since `in` is a keyword. Rules L1, L3, B1 and B2 keep the name `in` |
| `resolved_by` on `Invokes` | Rule E13 holds: `resolved_by` is given on code edges with `TreeSitter` or `Scip`, and on `Invokes` with `Compose` or `Dockerfile` (ADR 0020, storage-model.md). ADR 0017's "only on parsed edges" predates `Invokes` |

## Errors

| Condition | Error or code | Exit code |
|---|---|---|
| Text that does not have the form of its value type | `DomainError::Malformed { value: ValueKind::<Type>, input, reason }`, printed as `not a valid <Type>: "<input>": <reason>` | `n/a` |
| A value that breaks a Build rule | `DomainError::Rule { rule: RuleId::<Id>, message }`, printed as `rule <Id>: <message>` | `n/a` |
| `Node::declared` given `NodeKind::Binary` | `DomainError::Rule`, whose message names `Node::binary` | `n/a` |
| A finished graph that breaks a Graph rule | Not an error: `Graph::validate` returns a `RuleViolation { rule, message }` per broken rule | `n/a` |

`ValueKind` has one value per type that can be malformed: `ProjectId`, `ComposeName`, `RelPath`, `ContentHash`, `NodeId`, `ReferenceId`, `Name`, `QualifiedName`, `CommitId`, `Line`, `Span`.

## Tech stack

| Crate | Why |
|---|---|
| `thiserror` | Derives `Display` and `Error` for `DomainError`. Already in `Cargo.toml` (`2.0.21`) |
| `blake3` | Node ids, reference ids and content hashes. Already in `Cargo.toml` (`1.8.8`) |
| `serde` with `derive` | Reads newtypes through their `parse`, with `#[serde(try_from = "String", into = "String")]`. Not yet in `Cargo.toml`. Whichever of slices 1A to 1D, 2A and 2B merges first adds it, with `thiserror`, `blake3` and the YAML crate (GR20 in SPEC-ground-rules.md) |

No other crate is used in `src/domain`.

## Commands

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
cargo deny check
```

```bash
cargo test --locked domain::                 # this module's tests only
python3 examples/acme-shop/lib/ids.py        # prints "blake3 ok; cf04ba99fe901113"
```

## Project structure

| Path | Holds |
|---|---|
| `src/domain/mod.rs` | `mod` lines and re-exports |
| `src/domain/error.rs` | `DomainError`, `ValueKind` |
| `src/domain/rule.rs` | `RuleId` |
| `src/domain/id.rs` | `NodeId`, `ReferenceId`, `ContentHash`, `IdWriter` |
| `src/domain/name.rs` | `ProjectId`, `ComposeName`, `Name`, `QualifiedName`, `CommitId` |
| `src/domain/path.rs` | `RelPath` |
| `src/domain/position.rs` | `Line`, `Column`, `Span`, `Site` |
| `src/domain/template.rs` | `Template`, `TemplatePart` |
| `src/domain/common.rs` | `HttpMethod`, `Language`, `DependencyManager` |
| `src/domain/node/mod.rs` | `Node`, `ParsedNode`, `DeclaredNode`, `BinaryNode`, `ParsedFrom`, `Scope`, `Origin` |
| `src/domain/node/kind.rs` | `NodeKind`, `NodeKindName` |
| `src/domain/node/data.rs` | `ProjectData`, `BinaryData`, `Callable`, `TypeDecl`, `Member`, `RouteData`, `CommandData`, `Doc`, `Visibility`, `ParamSource` |
| `src/domain/node/framework.rs` | `Framework`, `FrameworkName`, `FrameworkSource`, `FrameworkRole` |
| `src/domain/edge/mod.rs` | `Edge`, `EdgeInput`, `EdgeKey` |
| `src/domain/edge/kind.rs` | `EdgeKind`, `EdgeKindName`, `DependencyScope`, `Protocol` |
| `src/domain/edge/provenance.rs` | `Provenance`, `Resolution` |
| `src/domain/edge/reference.rs` | `UnresolvedReference` |
| `src/domain/record/file.rs` | `FileRecord`, `ParseStatus` |
| `src/domain/record/flow.rs` | `CallSite`, `Argument`, `Slot`, `Shape`, `Accessor`, `CollectionKind`, `LiteralKind`, `Binding`, `Return` |
| `src/domain/record/analysis.rs` | `InferredType`, `Reach`, `Root`, `RoutePath`, `Candidates`, `UnmatchedHttpCall`, `UnmatchedMessage`, `MessageDirection`, `MessagePayload` |
| `src/domain/record/warning.rs` | `Warning`, `WarningCode` |
| `src/domain/record/checkout.rs` | `ProjectCheckout`, `Head` |
| `src/domain/graph/mod.rs` | `Graph`, `RuleViolation` |
| `src/domain/fixtures/mod.rs` | `acme_workspace_layer()`, `acme()`, test-only |
| `examples/acme-shop/lib/ids.py` | The reference id encoding |
| `examples/acme-shop/site/graph.json` | The expected Acme Shop graph, with every id |

## Code style

A build error names its rule, and a test checks the rule by its id. Every item outside `#[cfg(test)]` has a doc comment. From `src/domain/error.rs`:

```rust
#[test]
fn rule_error_names_its_rule() {
    let error = DomainError::Rule {
        rule: RuleId::N3,
        message: String::from("the scope does not suit the kind"),
    };
    assert!(error.to_string().starts_with("rule N3:"));
}
```

## Testing strategy

Every test is a unit test beside the code, in a `#[cfg(test)] mod tests` block of the file it tests. A test may return `()`, and `.clippy.toml` allows `unwrap`, `expect` and `panic!` in tests. A test for a rule is named after it: `rule_n3_...`, `rule_e1_...`.

There are three levels:

1. **Each type on its own.** For every rule marked Build: one test that a valid value is accepted, and one that a broken value is refused with an error that names the rule. A rule marked Type has no test, since the broken value cannot be written.
2. **The whole graph.** For every rule marked Graph: one small graph that breaks only that rule, and a check that `validate` reports exactly it.
3. **Acme Shop.** `fixtures::acme_workspace_layer()` and `fixtures::acme()` build the Acme Shop graph through the constructors, never by filling in structs. Their expected ids come from `examples/acme-shop/site/graph.json`. `acme_workspace_layer()` gives exactly its 27 workspace nodes and 54 workspace edges, with the same ids. `acme()` holds the subset of its code layer the checks need, and every node it holds has the id that file gives it. That subset must at least support: the six steps of the walk (Class `Invoice`, its file and the `Imports` edges that reach it), billing's FastAPI `app` and its two `Mounts` to `GET /{invoice_id}` with that route's route path, `process` with `r`, its two call sites, its inferred type and the `Flow` edge to `InvoiceRepo.save`, the reach records listed under [The Acme Shop graph](#the-acme-shop-graph), the fixture `repo` and its return, `fetch_invoice` and `test_get_invoice` with their `Requests` and `Injects` edges and the `HttpCallWithoutLink` warning, `send_invoice` and `run_consume` with their payloads, and ledger's three commands with the `Invokes` edge.

An Indexer rule has no test here. The module whose indexer keeps it tests it.

## Boundaries

- **Always:** build every value through its constructor, in code and in fixtures. Name a rule's test after its id. Keep every rule id and its Enforced value as written here. Run the four commands above before a change is done. Give every item outside `#[cfg(test)]` a doc comment. Change this spec in the same change as the code it describes.
- **Ask first:** changing a value of `NodeKindName::as_str` or `EdgeKindName::as_str`. Changing the id byte encoding: the fields, their order, the length prefix, the ordinal's width or the 8 bytes kept. Adding a rule id, or changing a rule's meaning or its Enforced value. Adding a crate to `src/domain`; the allowed crates are `thiserror`, `blake3` and `serde`.
- **Never:** `src/domain` importing anything from `config`, `ports`, `use_cases` or `adapters`. A `_` arm in a `match` on a domain enum. A `None` variant in any enum. `#[non_exhaustive]` on a domain enum. Hashing an enum's discriminant into an id. A public field, a `From<String>` or a `Deref<Target = str>` on a newtype. `unwrap`, `expect` or `panic!` outside tests. Input or output in `src/domain`. Renumbering a rule id.

## Success criteria

Task 1: errors and rule ids.

| Test | Asserts |
|---|---|
| `rule_ids_print_as_written_in_the_model` | `RuleId::N10.to_string()` is `"N10"`, `RuleId::E13` is `"E13"` |
| `rule_error_names_its_rule` | The text of `DomainError::Rule { rule: N3, .. }` starts with `rule N3:` |

Task 2: ids and hashes.

| Test | Asserts |
|---|---|
| `node_id_round_trips_through_hex` | `parse(id.to_string())` gives the same id |
| `node_id_refuses_upper_case_and_wrong_length` | `9F2C41D07AB35E18` and a 15-character id are `Malformed` |
| `content_hash_of_empty_input_is_blake3s` | Equals BLAKE3's published hash of no bytes, `af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262` |
| `length_prefix_separates_shifted_fields` | `field("a").field("bc")` and `field("ab").field("c")` give different ids |
| `known_inputs_give_a_known_id` | The workspace node's six fields give `cf04ba99fe901113`, and project `billing-api`'s give `4df6a64e2a4a7034` |
| `known_inputs_give_a_known_reference_id` | The first reference of `graph.json` (`from` `f5a0e93cff6ed70a`, `pydantic.BaseModel`, `imports`, `src/shared_api/models.py`, line `1`, column `0`) gives `e4a4bafef9607dfa` |

Task 3: names, paths, positions, templates and shared enums.

| Test | Asserts |
|---|---|
| `project_id_accepts_kebab_case` | `billing-api`, `a1`, `web-app-2` are accepted |
| `project_id_refuses_bad_hyphens_and_case` | `-a`, `a-`, `a--b`, `Billing` are `Malformed { value: ProjectId, .. }` |
| `compose_name_accepts_underscore` | `billing_api` and `0infra` are accepted. `_x` and `Infra` are refused |
| `name_refuses_empty` | `Name::parse("")` is `Malformed { value: Name, .. }` |
| `commit_id_needs_40_lower_hex` | 39 characters and upper case are refused |
| `rel_path_refuses_absolute_dot_backslash_empty` | `/a`, `a/./b`, `a\b` and the empty string are refused |
| `rel_path_allows_leading_parent_only` | `../shared/x.py` is accepted. `a/../b` is refused |
| `line_zero_cannot_be_built` | `Line::new(0)` is `Malformed { value: Line, .. }` |
| `span_refuses_start_after_end` | `(3,0)..(2,9)` is refused. `(3,4)..(3,4)` is accepted |
| `template_merges_text_and_renders_unknown` | `[Text("/v1"), Text("/x"), Unknown]` has two parts and renders `/v1/x{?}` |
| `enum_names_round_trip` | Every `HttpMethod`, `Language` and `DependencyManager` value parses back from `as_str` |

Task 4: node kinds and their data.

| Test | Asserts |
|---|---|
| `every_kind_has_one_name` | Mapping `NodeKindName::ALL` back through `as_str` gives 33 distinct names |
| `kind_names_are_frozen` | `as_str` of every one of the 33 `NodeKindName` values and the 29 `EdgeKindName` values equals the tables under [Node](#node) and [Edge](#edge), among them `function`, `external_service`, `type_alias` and `depends_on`. A change breaks every stored id |
| `code_and_workspace_split_24_9` | `is_code` is true for 24 names and `is_workspace` for 9, and never both |
| `framework_name_drops_app` | `Fastapi { app: Some(..) }.name()` is `FrameworkName::Fastapi` |

Task 5: building a node.

| Test | Asserts |
|---|---|
| `rule_n2_id_is_the_hash_of_the_inputs` | A parsed node's id equals an `IdWriter` fed the six fields by hand |
| `rule_n5_same_inputs_same_id` | Two builds of billing's `worker.py` file node give equal ids |
| `scope_changes_the_id` | Service `api` in stack `billing-api` and in stack `ledger` have different ids |
| `scope_type_changes_the_id` | Project `billing` and stack `billing` have different ids |
| `ordinal_changes_the_id` | Two `Function`s `f` in one file with ordinals 0 and 1 differ |
| `workspace_id_is_the_same_everywhere` | `Node::workspace` with folder names `a` and `b` gives one id |
| `rule_n3_refuses_service_in_project_scope` | `DomainError::Rule { rule: N3, .. }` |
| `rule_n3_refuses_parent_path_in_project_scope` | A file node at `../x.py` in a project scope is refused with N3 |
| `rule_n3_accepts_service_in_stack_scope` | A `Service` in a `Stack` scope is accepted |
| `rule_n4_refuses_declared_code_node` | A declared `Function` is refused with N4 |
| `rule_n4_refuses_parsed_topic` | A parsed `Topic` is refused with N4 |
| `rule_n4_refuses_code_kind_from_compose` | A `Class` with `ParsedFrom::Compose` is refused with N4 |
| `rule_n4_accepts_parsed_service_from_compose` | A parsed `Service` with `ParsedFrom::Compose` is accepted, and so is a declared `Topic` |
| `rule_n9_python_refuses_protected` | A Python `Method` with `Protected` is refused with N9 |
| `rule_n9_binary_framework_suits_project_language` | `Node::binary` with `Angular` and `Python` is refused with N9. `Fastapi` and `Python` is accepted |
| `rule_n10_router_role_only_on_variable` | A `Function` with role `Router` is refused with N10 |
| `rule_n10_accepts_router_role_on_variable` | A `Variable` with role `Router` is accepted |
| `declared_refuses_binary` | `Node::declared` with `NodeKind::Binary` is refused, naming `Node::binary` in the message |

Task 6: edge kinds and building an edge.

| Test | Asserts |
|---|---|
| `rule_e1_refuses_joins_from_function` | `Joins` from a `Function` to a `Network` is `Rule { rule: E1, .. }` |
| `rule_e1_accepts_runs_service_to_binary` | `Runs` from a `Service` to a `Binary` is accepted |
| `rule_e2_refuses_workspace_loop` | `DependsOn` from a project to itself is refused with E2. A `Calls` loop (recursion) is accepted |
| `rule_e3_refuses_manifest_on_runs` | `Runs` with `Manifest` is refused with E3 |
| `rule_e3_accepts_dockerfile_on_runs` | `Runs` with `Dockerfile` is accepted |
| `rule_e13_framework_kinds_need_framework` | `Handles` with `resolved_by: None` is refused with E13 |
| `rule_e13_flow_only_on_calls_and_instantiates` | `References` with `Flow` is refused with E13 |
| `rule_e13_invokes_with_compose_takes_command_match` | `Invokes`, `Compose`, `CommandMatch` is accepted |
| `rule_e13_requests_needs_route_match` | `Requests` without `RouteMatch` is refused with E13, and `RouteMatch` on `Calls` is refused with E13 |
| `rule_e13_sends_and_receives_need_message_match` | `Sends` or `Receives` without `MessageMatch` is refused with E13, and `MessageMatch` on `Calls` is refused with E13 |
| `rule_e13_invokes_needs_command_match` | `Invokes` without `CommandMatch` is refused with E13, and `CommandMatch` on `Calls` is refused with E13 |
| `rule_e13_refuses_resolution_on_compose_runs` | `Runs` with `Compose` and any `resolved_by` is refused with E13 |
| `restore_still_checks_e3` | `Edge::restore` with `Runs` and `Manifest` is refused with E3 |
| `restore_still_checks_e2` | `Edge::restore` of `DependsOn` with the same source and target is refused with E2 |
| `restore_still_checks_e13` | `Edge::restore` of `Handles` with `resolved_by: None` is refused with E13 |
| `key_ignores_data` | Two `Imports` edges that differ only in `alias` have equal keys |
| `edge_kind_names_split_19_10` | `is_code` for 19, `is_workspace` for 10 |

Task 7: unresolved references.

| Test | Asserts |
|---|---|
| `rule_r2_refuses_workspace_kind` | `DependsOn` is refused with R2 |
| `rule_r2_accepts_code_kind` | `Calls` is accepted |
| `mounts_reference_keeps_its_prefix` | `kind()` returns the `Mounts` with its prefix |
| `same_fields_same_id` | Two builds give one id. Another line gives another id |
| `restore_keeps_flow_resolved` | `restore` with `flow_resolved: true` gives a reference whose `flow_resolved()` is true and whose id equals `new`'s for the same fields. `new` gives false |
| `restore_still_checks_r2` | `restore` with `DependsOn` is refused with R2 |

Task 8: records.

| Test | Asserts |
|---|---|
| `rule_c2_refuses_position_gap` | Positions 0 and 2 are refused with C2 |
| `rule_c2_refuses_repeated_position` | Positions 0 and 0 are refused with C2 |
| `rule_c2_keywords_after_positions_are_fine` | `0`, `1`, `base_url=` is accepted |
| `rule_m2_refuses_one_candidate` | `Candidates::new(vec![id], M2)` is refused with M2. Zero and two are accepted |
| `rule_g2_names_its_rule` | The same with `G2` names G2 |
| `rule_a1_refuses_empty_message` | `Warning::new(.., String::new())` is refused with A1 |
| `rule_a1_accepts_message` | `Warning::new` with a non-empty message is accepted |
| `route_path_completeness_follows_the_text` | `/v1/invoices/{invoice_id}` is complete. `{?}/invoices` is not |

Task 9: the graph and `validate`.

| Test | Asserts |
|---|---|
| `empty_graph_breaks_only_n7` | `Graph::default().validate()` is one violation, N7 |
| `three_broken_rules_give_three_violations` | A graph that breaks N7, E5 and F1 gives all three, sorted |
| `contains_cycle_is_reported_once` | Two nodes that contain each other give T3, and `validate` returns |
| `edge_to_unknown_node_is_only_e5` | No E1, T2 or E11 violation for the same edge |

One test per Graph rule. Each builds the smallest graph that breaks only that rule, and asserts that `validate` returns exactly one violation, with that rule:

| Test | Asserts |
|---|---|
| `rule_n6_refuses_shared_node_id` | Exactly one violation, N6 |
| `rule_n7_needs_one_workspace` | Exactly one violation, N7 |
| `rule_e5_edge_end_not_in_graph` | Exactly one violation, E5 |
| `rule_e6_refuses_duplicate_edge` | Exactly one violation, E6 |
| `rule_e7_refuses_second_depends_on` | Exactly one violation, E7 |
| `rule_e8_service_needs_runs_or_built_from` | Exactly one violation, E8 |
| `rule_e9_binary_needs_one_entry_point` | Exactly one violation, E9 |
| `rule_e10_runs_leads_to_own_project_binary` | Exactly one violation, E10 |
| `rule_e11_refuses_handles_from_class` | Exactly one violation, E11 |
| `rule_e12_flow_edge_needs_inferred_type` | Exactly one violation, E12 |
| `rule_t1_refuses_contains_into_workspace` | Exactly one violation, T1 |
| `rule_t2_refuses_second_parent` | Exactly one violation, T2 |
| `rule_t3_refuses_cycle_cut_off_from_root` | Exactly one violation, T3 |
| `rule_t4_refuses_file_below_other_project` | Exactly one violation, T4 |
| `rule_t5_refuses_code_node_from_other_file` | Exactly one violation, T5 |
| `rule_f1_refuses_duplicate_file_record` | Exactly one violation, F1 |
| `rule_f2_file_node_needs_record` | Exactly one violation, F2 |
| `rule_f3_refuses_nodes_below_unparsed_file` | Exactly one violation, F3 |
| `rule_r1_reference_from_unknown_node` | Exactly one violation, R1 |
| `rule_r3_refuses_duplicate_reference` | Exactly one violation, R3 |
| `rule_c1_call_site_from_unknown_node` | Exactly one violation, C1 |
| `rule_c3_refuses_duplicate_call_site` | Exactly one violation, C3 |
| `rule_l1_refuses_binding_in_route` | Exactly one violation, L1 |
| `rule_l3_refuses_duplicate_binding` | Exactly one violation, L3 |
| `rule_b1_refuses_return_in_class` | Exactly one violation, B1 |
| `rule_b2_refuses_duplicate_return` | Exactly one violation, B2 |
| `rule_y1_refuses_inferred_function_class` | Exactly one violation, Y1 |
| `rule_y2_refuses_second_inferred_type` | Exactly one violation, Y2 |
| `rule_h1_refuses_reach_of_workspace_node` | Exactly one violation, H1 |
| `rule_h2_refuses_duplicate_reach` | Exactly one violation, H2 |
| `rule_u1_refuses_route_path_of_plain_binary` | Exactly one violation, U1 |
| `rule_u3_refuses_duplicate_route_path` | Exactly one violation, U3 |
| `rule_u5_refuses_variable_provider` | Exactly one violation, U5 |
| `rule_m1_refuses_non_route_candidate` | Exactly one violation, M1 |
| `rule_g1_refuses_broker_that_is_a_service` | Exactly one violation, G1 |
| `rule_d1_payload_needs_its_edge` | Exactly one violation, D1 |
| `rule_d2_refuses_duplicate_payload` | Exactly one violation, D2 |
| `rule_p1_refuses_second_checkout` | Exactly one violation, P1 |
| `rule_p2_checkout_needs_project_node` | Exactly one violation, P2 |
| `rule_a2_warning_subject_not_in_graph` | Exactly one violation, A2 |

Task 10: the Acme Shop fixtures.

| Test | Asserts |
|---|---|
| `acme_workspace_layer_is_valid` | `validate()` is empty |
| `acme_workspace_layer_ids_match_graph_json` | Every node and edge of `acme_workspace_layer()` has the id, source and target that `examples/acme-shop/site/graph.json` gives it |
| `acme_workspace_layer_counts` | Each node and edge count of the Acme Shop table, by `NodeKindName` and `EdgeKindName` |
| `acme_api_services_have_different_ids` | The two `api` services differ |
| `acme_is_stable` | Two builds give equal graphs |
| `acme_walk_reaches_admin` | The six steps of the walk can be followed over `acme()`'s edges |
| `acme_is_valid` | `acme().validate()` is empty |
| `acme_billing_api_is_fastapi` | `api` has `Framework::Fastapi { app: Some(billing.api.app) }`, `worker` has `Framework::NoFramework` |
| `acme_flow_edge_rests_on_inferred_type` | `r.save()` is a `Calls` edge with `resolved_by: Flow`, and `r` has an inferred type with evidence 2 |
| `acme_route_has_one_route_path` | `GET /{invoice_id}` reaches billing's app through two `Mounts` edges, and has one route path, `GET /v1/invoices/{invoice_id}`, complete, served by `api` |
| `acme_reach_follows_each_root` | The reach records listed under [The Acme Shop graph](#the-acme-shop-graph) hold, and `worker` does not reach `routes/invoices.py`, and `api` does not reach `services.py` |
| `acme_fixture_repo_has_inferred_return` | The fixture `repo` has the inferred return `InvoiceRepo`, from 1 return |
| `acme_requests_edges_match_routes` | `fetch_invoice` and `test_get_invoice` each have a `Requests` edge to `GET /{invoice_id}` with `resolved_by: RouteMatch`. `test_get_invoice` has an `Injects` edge to the fixture `repo` |
| `acme_sends_and_receives_carry_invoice` | `send_invoice` has a `Sends` edge, and `run_consume` a `Receives` edge, to `kafka/invoice.created`, each with `Invoice` as payload |
| `acme_consumer_service_invokes_run` | Ledger's `consumer` binary has the commands `ledger-consumer`, `ledger-consumer run` and `ledger-consumer replay`, and the `consumer` service an `Invokes` edge to `ledger-consumer run` |

## Out of scope (deferred)

| What | Deferred to | Why |
|---|---|---|
| A confidence score on inferred edges (`G9`) | Later | Nothing produces `Heuristic` edges yet, and every resolution rule is exact within the workspace |
| `Scip` and `Heuristic` edges | Later | No reader produces them in Release 1. E3 refuses them on every kind |
| What TypeScript can express, beyond `framework` of `Fastapi` (N9) | R2 | Settled when TypeScript is parsed |
| Comparing a checkout with a release branch | R3 | The `operational-support` mode does it |
| Keeping the graph in SQLite: tables, columns, the format version | `storage` | This module holds the types, not how they are stored |
| The SQLite layout: one `nodes` table and one `edges` table for both layers, a column per field, edge data as typed columns not JSON, and the tables `files`, `unresolved_refs`, `call_sites`, `bindings`, `returns`, the stage 2 tables, `warnings`, `project_checkouts`, a full-text index and `meta` | `storage` | Decided in domain-model.md ("Storing the model") and ADR 0006. The store maps these types; it does not change them |
| Walks run step by step in the core, above the store port. The store never walks, so `impact` and `explore` behave the same on any store | `storage`, `queries` | ADR 0007. No walk lives in `src/domain` |
| How an index builds the graph: stage 1 reads every file, one at a time; stage 2 analyses the finished graph from each root and reads no file again | `workspace-indexing`, `code-indexing` | ADR 0013. The domain types are the same whichever stage fills them |
| Release 1's code scope: plain Python binaries and FastAPI binaries, HTTP calls matched to routes, the tests to run for a change, API contracts | `code-indexing` | What is produced, not what the types can hold |
| A binary's framework is decided before parsing, per binary, from the configuration, then a compose command, then the entry file. A framework's rules read every file that imports it | `workspace-indexing` | ADR 0015. The result is `BinaryData`, defined here |
| What an import reaches: the `File` of the module, for an import of a module or of a name in it, and the `__init__.py` of each package on the way. Never the imported name itself | `code-indexing` | A reach rule of stage 2e |
| Where test reach starts: at the test file, and at each test function and fixture in it | `code-indexing` | A reach rule of stage 2e |
| Module-level names: a reached file reaches its module-level variables and constants, so `app = FastAPI()` and its mounts are followed | `code-indexing` | A reach rule of stage 2e |
| `set_defaults(func=f)` gives both `Handles` from the command and `References` to `f`: one says which command runs `f`, the other makes `f` reachable from the entry | `code-indexing` | A Python parsing rule |
| A base class bound to a variable: `class M(Base)` with `Base = declarative_base()` stays unresolved, since there is no class to point at | `code-indexing` | A resolution rule |
| Producing nodes, edges and records: stage 1, stage 2, warnings, Indexer rules F4, R4, Y4, H3, U4, M3, G3, D3, P4, A3 | `workspace-indexing`, `code-indexing` | This module defines the rules. The indexer keeps them |
| Timestamps on nodes and a copy of the source | Never | A node stores where its source is. The file record says whether a file changed |
| Services that run outside any compose file | Later | The current assumption is that the compose files describe everything that runs |

## Open questions

| Question | Blocks |
|---|---|
| How is `Node::declared` stopped from building a `NodeKind::Binary`, which would skip N9's check of the framework against the project's language? Options: (1) a runtime `Err` naming N9; (2) a runtime `Err` with a new rule N11; (3) a `DeclaredKind` enum without `Binary`, so the mistake cannot compile. To be decided during Task 5 with the code in front of the owner | `declared_refuses_binary`, Task 5 |
