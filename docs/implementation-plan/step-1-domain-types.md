# Step 1: Domain Types Implementation Plan

**Goal:** Write the types of the knowledge graph in `src/domain`, with every Build rule checked when a value is built, every Graph rule checked by `Graph::validate`, and the Acme Shop graph as a fixture.

**Architecture:** Pure types with no input or output. `src/domain` depends on nothing else in the crate. The only crates it uses are `thiserror`, `blake3` and `serde`. Values are built through constructors that keep their rules. A finished graph is checked as a whole by one pass that reports every broken rule.

**Tech stack:** `thiserror`, `blake3`, `serde` with `derive`.

**Spec:** [domain-model.md](../domain-model.md), above all [How the types are written in Rust](../domain-model.md#how-the-types-are-written-in-rust). The reasons behind the model are in [graph-model.md](../graph-model.md).

**Read first:** [00-overview.md](./00-overview.md) for the constraints, the module map and how a task is done.

## Global constraints

- `src/domain` imports nothing from `config`, `ports`, `use_cases` or `adapters`.
- A type that keeps a rule has private fields and a constructor that returns `Result<Self, DomainError>`. A type that keeps no rule has public fields and no constructor. Getters are added only where fields are private.
- Every public type derives `Debug`, `Clone`, `PartialEq` and `Eq`. A type is `Copy` only when it is a fixed size and holds no `String` or `Vec`.
- No `match` on a domain enum has a `_` arm. No domain enum is `#[non_exhaustive]`.
- No enum has a `None` variant.
- No `unwrap`, `expect` or `panic!`, in tests too. A test returns `Result<(), Box<dyn std::error::Error>>`.
- A test for a rule is named after it: `rule_n3_...`, `rule_e1_...`.

## Review focus

Places where a quick implementation would quietly break a rule.

- **Id stability.** The id hashes `NodeKindName::as_str()`, never the enum's discriminant. Reordering the variants must not change any id. Task 2 tests this with a fixed expected id.
- **Length prefixes.** Two different sets of inputs must never hash the same bytes, such as the qualified name `a` with path `bc` and the qualified name `ab` with path `c`. Task 2.
- **`Edge::restore` is not a back door.** It skips only E1. It still checks E2, E3 and E13. Task 6.
- **`validate` reports everything.** A graph that breaks three rules gives three violations, never only the first. Task 9.
- **The fixture is built through the constructors,** never by filling in structs. A fixture that skips the rules proves nothing. Task 10.

## File structure

| File | Holds | Slice |
|---|---|---|
| `src/domain/mod.rs` | `mod` lines and re-exports | each slice adds its own lines |
| `src/domain/error.rs` | `DomainError`, `ValueKind` | 1A |
| `src/domain/rule.rs` | `RuleId` | 1A |
| `src/domain/id.rs` | `NodeId`, `ReferenceId`, `ContentHash`, `IdWriter` | 1A |
| `src/domain/name.rs` | `ProjectId`, `ComposeName`, `Name`, `QualifiedName`, `CommitId` | 1A |
| `src/domain/path.rs` | `RelPath` | 1A |
| `src/domain/position.rs` | `Line`, `Column`, `Span`, `Site` | 1A |
| `src/domain/template.rs` | `Template`, `TemplatePart` | 1A |
| `src/domain/common.rs` | `HttpMethod`, `Language`, `DependencyManager` | 1A |
| `src/domain/node/mod.rs` | `Node`, `ParsedNode`, `DeclaredNode`, `BinaryNode`, `ParsedFrom`, `Scope`, `Origin` | 1B |
| `src/domain/node/kind.rs` | `NodeKind`, `NodeKindName` | 1B |
| `src/domain/node/data.rs` | `ProjectData`, `BinaryData`, `Callable`, `TypeDecl`, `Member`, `RouteData`, `CommandData`, `Doc`, `Visibility`, `ParamSource` | 1B |
| `src/domain/node/framework.rs` | `Framework`, `FrameworkName`, `FrameworkSource`, `FrameworkRole` | 1B |
| `src/domain/node/rules.rs` | The checks for N3, N4, N9 and N10 | 1B |
| `src/domain/edge/mod.rs` | `Edge`, `EdgeInput` | 1C |
| `src/domain/edge/kind.rs` | `EdgeKind`, `EdgeKindName`, `DependencyScope`, `Protocol` | 1C |
| `src/domain/edge/provenance.rs` | `Provenance`, `Resolution` | 1C |
| `src/domain/edge/rules.rs` | The checks for E1, E2, E3 and E13 | 1C |
| `src/domain/edge/reference.rs` | `UnresolvedReference` | 1C |
| `src/domain/record/file.rs` | `FileRecord`, `ParseStatus` | 1D |
| `src/domain/record/flow.rs` | `CallSite`, `Argument`, `Slot`, `Shape`, `Accessor`, `CollectionKind`, `LiteralKind`, `Binding`, `Return` | 1D |
| `src/domain/record/analysis.rs` | `InferredType`, `Reach`, `Root`, `RoutePath`, `Candidates`, `UnmatchedHttpCall`, `UnmatchedMessage`, `MessageDirection`, `MessagePayload` | 1D |
| `src/domain/record/warning.rs` | `Warning`, `WarningCode` | 1D |
| `src/domain/record/checkout.rs` | `ProjectCheckout`, `Head` | 1D |
| `src/domain/graph/mod.rs` | `Graph`, `RuleViolation` | 1E |
| `src/domain/graph/index.rs` | `GraphIndex`: lookups built once per `validate` | 1E |
| `src/domain/graph/{nodes,edges,tree,records}.rs` | One function per group of Graph rules | 1E |
| `src/domain/fixtures/mod.rs` | `acme_workspace_layer()`, `acme()`, test-only | 1E |

## Slices

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 1A | 1, 2, 3 | | `error.rs`, `rule.rs`, `id.rs`, `name.rs`, `path.rs`, `position.rs`, `template.rs`, `common.rs` |
| 1B | 4, 5 | 1A | `node/` |
| 1C | 6, 7 | 1A, 1B's types | `edge/` |
| 1D | 8 | 1A | `record/` |
| 1E | 9, 10 | 1B, 1C, 1D | `graph/`, `fixtures/` |

1C needs 1B's types only. `Edge::new` reads a `Node`'s kind and id, and nothing of 1B's rule checks. 1C can start once 1B has committed `node/kind.rs` and the `Node` struct.

`DomainError` and `RuleId` are written once, in 1A, and list every rule. No later slice edits `error.rs` or `rule.rs`.

## Task 1: Errors and rule ids

**Files:** create `src/domain/rule.rs`. Fill in `src/domain/error.rs`.

**Produces:**

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

**Tests:**

| Test | Asserts |
|---|---|
| `rule_ids_print_as_written_in_the_model` | `RuleId::N10.to_string()` is `"N10"`, `RuleId::E13` is `"E13"` |
| `rule_error_names_its_rule` | The text of `DomainError::Rule { rule: N3, .. }` starts with `rule N3:` |

**Commit:** `feat(domain): add rule ids and the domain error`

## Task 2: Ids and hashes

**Files:** create `src/domain/id.rs`.

**Produces:**

```rust
/// 64 bits of a BLAKE3 hash. Shown as 16 lowercase hex characters.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct NodeId([u8; 8]);
impl NodeId {
    pub fn parse(hex: &str) -> Result<Self, DomainError>;   // for ids typed by a user or read from a store
    pub fn as_bytes(&self) -> &[u8; 8];
}
impl fmt::Display for NodeId { /* 16 lowercase hex */ }

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct ReferenceId([u8; 8]);       // same API as NodeId

/// All 256 bits of a BLAKE3 hash of a file's bytes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct ContentHash([u8; 32]);
impl ContentHash {
    pub fn of(bytes: &[u8]) -> Self;
    pub fn parse(hex: &str) -> Result<Self, DomainError>;   // 64 lowercase hex
}

/// Writes length-prefixed fields into a BLAKE3 hasher.
/// `pub(crate)`: only `Node` and `UnresolvedReference` compute ids.
pub(crate) struct IdWriter(blake3::Hasher);
impl IdWriter {
    pub(crate) fn new() -> Self;
    pub(crate) fn field(&mut self, bytes: &[u8]) -> &mut Self;  // u32 LE length, then the bytes
    pub(crate) fn node_id(&self) -> NodeId;                     // first 8 bytes of the hash
    pub(crate) fn reference_id(&self) -> ReferenceId;
}
```

The bytes of a node id, in order, each written with `field`:

1. The scope's type: `workspace`, `project` or `stack`.
2. The scope's name, the `ProjectId` or `ComposeName`. Empty for `workspace`.
3. The origin's path. Empty for a declared node. A `RelPath` is never empty, so this cannot be confused with a real path.
4. `NodeKindName::as_str()`, the snake-case name used in storage, such as `function`.
5. The qualified name.
6. The ordinal, as 4 bytes, little-endian.

**Tests:**

| Test | Asserts |
|---|---|
| `node_id_round_trips_through_hex` | `parse(id.to_string())` gives the same id |
| `node_id_refuses_upper_case_and_wrong_length` | `9F2C41D07AB35E18` and a 15-character id are `Malformed` |
| `content_hash_of_empty_input_is_blake3s` | Equals BLAKE3's published hash of no bytes |
| `length_prefix_separates_shifted_fields` | `field("a").field("bc")` and `field("ab").field("c")` give different ids |
| `known_inputs_give_a_known_id` | A fixed set of six fields gives a fixed id, written in the test. It guards against an accidental change of the encoding. Take the expected ids from [`examples/acme-shop/lib/ids.py`](../../examples/acme-shop/lib/ids.py): the workspace node, `node_id("workspace", "", "", "workspace", "workspace", 0)`, is `cf04ba99fe901113`, and `site/graph.json` holds the id of every other Acme node |

**Commit:** `feat(domain): add node ids and content hashes`

## Task 3: Names, paths, positions, templates and shared enums

**Files:** create `src/domain/{name,path,position,template,common}.rs`.

**Produces:**

```rust
// name.rs. Each: parse(&str) -> Result<Self, DomainError>, as_str(&self) -> &str, Display,
// and #[serde(try_from = "String", into = "String")]. No Deref, no From<String>.
pub struct ProjectId(String);       // kebab-case: [a-z0-9]+(-[a-z0-9]+)*
pub struct ComposeName(String);     // [a-z0-9][a-z0-9_-]*
pub struct Name(String);            // not empty (N1, L2)
pub struct QualifiedName(String);   // not empty (N1)
pub struct CommitId(String);        // 40 lowercase hex

// path.rs
pub struct RelPath(String);         // relative, '/', not empty, no '.' segments, '..' only at the start
impl RelPath {
    pub fn parse(s: &str) -> Result<Self, DomainError>;
    pub fn as_str(&self) -> &str;
    pub fn leaves_root(&self) -> bool;   // starts with '..'; refused under a Project scope (task 5)
}

// position.rs
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Line(NonZeroU32);        // from 1
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Column(u32);             // from 0
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

Each fieldless enum has `as_str(self) -> &'static str`, giving its snake-case storage name, and the matching `FromStr`.

**Tests:**

| Test | Asserts |
|---|---|
| `project_id_accepts_kebab_case` | `billing-api`, `a1`, `web-app-2` are accepted |
| `project_id_refuses_bad_hyphens_and_case` | `-a`, `a-`, `a--b`, `Billing` are `Malformed { value: ProjectId, .. }` |
| `compose_name_accepts_underscore` | `billing_api` and `0infra` are accepted. `_x` and `Infra` are refused |
| `name_refuses_empty` | `Name::parse("")` is `Malformed { value: Name, .. }` |
| `commit_id_needs_40_lower_hex` | 39 characters and upper case are refused |
| `rel_path_refuses_absolute_dot_backslash_empty` | `/a`, `a/./b`, `a\b`, `` are refused |
| `rel_path_allows_leading_parent_only` | `../shared/x.py` is accepted. `a/../b` is refused |
| `line_zero_cannot_be_built` | `Line::new(0)` is `Malformed { value: Line, .. }` |
| `span_refuses_start_after_end` | `(3,0)..(2,9)` is refused. `(3,4)..(3,4)` is accepted |
| `template_merges_text_and_renders_unknown` | `[Text("/v1"), Text("/x"), Unknown]` has two parts and renders `/v1/x{?}` |
| `enum_names_round_trip` | Every `HttpMethod`, `Language` and `DependencyManager` value parses back from `as_str` |

**Commit:** `feat(domain): add the value types`

## Task 4: Node kinds and their data

**Files:** create `src/domain/node/{kind,data,framework}.rs`.

**Produces:**

```rust
// kind.rs
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

// data.rs. Public fields: these keep no rule alone. Rules that tie them to a kind
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

// framework.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Framework { Plain, Fastapi { app: Option<QualifiedName> }, Angular }   // app by type (N10)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum FrameworkName { Plain, Fastapi, Angular }   // what the configuration names
impl Framework { pub fn name(&self) -> FrameworkName; }
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FrameworkSource { Declared, Compose, Dockerfile, Entry }
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameworkRole {
    App, Router { prefix: Option<Template>, tags: Vec<String> },
    Middleware, ExceptionHandler, LifecycleHook, Fixture, Model,
}
```

`Parameter` holds `source` beside its `Member`, so a field or a variable can never have one. clippy's `large_enum_variant` decides which variants hold a `Box`. A variant that is boxed is boxed in `NodeKind` only. The data types stay unboxed.

**Tests:**

| Test | Asserts |
|---|---|
| `every_kind_has_one_name` | Mapping `NodeKindName::ALL` back through `as_str` gives 33 distinct names |
| `kind_names_are_frozen` | `as_str` of `Function`, `ExternalService` and `TypeAlias` is `function`, `external_service`, `type_alias`. A change breaks every stored id |
| `code_and_workspace_split_24_9` | `is_code` is true for 24 names and `is_workspace` for 9, and never both |
| `framework_name_drops_app` | `Fastapi { app: Some(..) }.name()` is `FrameworkName::Fastapi` |

**Commit:** `feat(domain): add node kinds and their data`

## Task 5: Building a node

**Files:** create `src/domain/node/{mod,rules}.rs`.

**Produces:**

```rust
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

`rules.rs` holds one private function per rule, each returning `Result<(), DomainError>`:

| Function | Rule | Refuses |
|---|---|---|
| `scope_suits_kind` | N3 | The scope table of the domain model. A `..` path under a `Project` scope too |
| `origin_suits_kind` | N4 | A declared code node. A parsed `Workspace`, `Project`, `Binary`, `Topic` or `Queue`. A code kind from `Compose`, a workspace kind from `Source` |
| `data_suits_language` | N9 | Python with `Protected` or `Internal`, or with `Angular`. TypeScript with `Fastapi` |
| `role_suits_kind` | N10 | `App` or `Router` off a `Variable`. `Middleware`, `ExceptionHandler`, `LifecycleHook` or `Fixture` off a `Function` or `Method`. `Model` off a `Class` |

N2 and N5 need no function: the id is computed in the constructor and there is no other way to set it.

**Tests:**

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
| `rule_n4_refuses_declared_code_node` | A declared `Function` is refused with N4 |
| `rule_n4_refuses_parsed_topic` | A parsed `Topic` is refused with N4 |
| `rule_n4_refuses_code_kind_from_compose` | A `Class` with `ParsedFrom::Compose` is refused with N4 |
| `rule_n9_python_refuses_protected` | A Python `Method` with `Protected` is refused with N9 |
| `rule_n9_binary_framework_suits_project_language` | `Node::binary` with `Angular` and `Python` is refused with N9. `Fastapi` and `Python` is accepted |
| `rule_n10_router_role_only_on_variable` | A `Function` with role `Router` is refused with N10 |
| `declared_refuses_binary` | `Node::declared` with `NodeKind::Binary` is refused, naming `Node::binary` in the message |

**Commit:** `feat(domain): build nodes and compute their ids`

## Task 6: Edge kinds and building an edge

**Files:** create `src/domain/edge/{mod,kind,provenance,rules}.rs`.

**Produces:**

```rust
// kind.rs
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

// provenance.rs
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Provenance { TreeSitter, Scip, Manifest, Compose, Dockerfile, Declared { note: Option<String> }, Heuristic }  // E4 by type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Resolution {
    Import, SelfMember, SameFile, Project, CrossProject, ReExport, Annotation,
    LocalInference, Inherited, Flow, Framework, RouteMatch, MessageMatch, CommandMatch,
}

// mod.rs
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
```

`rules.rs` holds the tables as `match` expressions over `EdgeKindName` and `NodeKindName`, with no `_` arm:

| Function | Rule | Table |
|---|---|---|
| `ends_suit_kind(kind, from, to)` | E1 | The workspace edge table of [graph-model.md](../graph-model.md#edge-kinds). Code kinds pass |
| `not_a_loop` | E2 | A workspace kind with `source == target` |
| `provenance_suits_kind` | E3 | The provenance table of the domain model. `Contains` takes `TreeSitter`, `Compose` or `Declared`. `Scip` and `Heuristic` are refused everywhere in Release 1 |
| `resolution_suits_edge` | E13 | Every clause of E13, in both directions: `Mounts` without `Framework` is refused, and so is `Framework` on `Calls` |

**Tests:**

| Test | Asserts |
|---|---|
| `rule_e1_refuses_joins_from_function` | `Joins` from a `Function` to a `Network` is `Rule { rule: E1, .. }` |
| `rule_e1_accepts_runs_service_to_binary` | Accepted |
| `rule_e2_refuses_workspace_loop` | `DependsOn` from a project to itself is refused with E2. A `Calls` loop (recursion) is accepted |
| `rule_e3_refuses_manifest_on_runs` | `Runs` with `Manifest` is refused with E3 |
| `rule_e13_framework_kinds_need_framework` | `Handles` with `resolved_by: None` is refused with E13 |
| `rule_e13_flow_only_on_calls_and_instantiates` | `References` with `Flow` is refused with E13 |
| `rule_e13_invokes_with_compose_takes_command_match` | `Invokes`, `Compose`, `CommandMatch` is accepted |
| `restore_still_checks_e3` | `Edge::restore` with `Runs` and `Manifest` is refused with E3 |
| `key_ignores_data` | Two `Imports` edges that differ only in `alias` have equal keys |
| `edge_kind_names_split_19_10` | `is_code` for 19, `is_workspace` for 10 |

**Commit:** `feat(domain): build edges and check their kinds`

## Task 7: Unresolved references

**Files:** create `src/domain/edge/reference.rs`.

**Produces:**

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UnresolvedReference { id: ReferenceId, from: NodeId, name: Name, kind: EdgeKind, site: Site }
impl UnresolvedReference {
    /// R2: `kind` is a code kind. The id hashes `from`, `name`, `kind.name().as_str()`
    /// and the site's path, line and column, with `IdWriter`.
    pub fn new(from: NodeId, name: Name, kind: EdgeKind, site: Site) -> Result<Self, DomainError>;
    pub fn id(&self) -> ReferenceId;
    pub fn from(&self) -> NodeId;
    pub fn name(&self) -> &Name;
    pub fn kind(&self) -> &EdgeKind;
    pub fn site(&self) -> &Site;
}
```

It lives in 1C, not 1D, because it holds an `EdgeKind`.

**Tests:**

| Test | Asserts |
|---|---|
| `rule_r2_refuses_workspace_kind` | `DependsOn` is refused with R2 |
| `mounts_reference_keeps_its_prefix` | `kind()` returns the `Mounts` with its prefix |
| `same_fields_same_id` | Two builds give one id. Another line gives another id |

**Commit:** `feat(domain): add unresolved references`

## Task 8: Records

**Files:** create `src/domain/record/{file,flow,analysis,warning,checkout}.rs`.

**Produces:**

```rust
// file.rs. No rule of its own: public fields.
pub struct FileRecord {
    pub project: ProjectId, pub path: RelPath, pub content_hash: ContentHash,
    pub size: u64, pub mtime_ns: i64, pub language: Language, pub status: ParseStatus,
}
pub enum ParseStatus { Parsed, Failed { message: String }, GrammarUnavailable }

// flow.rs
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

// analysis.rs
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
    pub fn new(ids: Vec<NodeId>, rule: RuleId) -> Result<Self, DomainError>;   // rule is M2 or G2, for the error
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

// warning.rs
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

// checkout.rs
pub struct Head { pub commit: CommitId, pub branch: Option<String> }
pub struct ProjectCheckout { pub project: ProjectId, pub head: Option<Head> }   // P3 by type
```

Every type above derives `Debug`, `Clone`, `PartialEq` and `Eq`. The fieldless enums also derive `Copy` and `Hash`, and have `as_str` with their storage names.

**Tests:**

| Test | Asserts |
|---|---|
| `rule_c2_refuses_position_gap` | Positions 0 and 2 are refused with C2 |
| `rule_c2_refuses_repeated_position` | Positions 0 and 0 are refused with C2 |
| `rule_c2_keywords_after_positions_are_fine` | `0`, `1`, `base_url=` is accepted |
| `rule_m2_refuses_one_candidate` | `Candidates::new(vec![id], M2)` is refused with M2. Zero and two are accepted |
| `rule_g2_names_its_rule` | The same with `G2` names G2 |
| `rule_a1_refuses_empty_message` | `Warning::new(.., String::new())` is refused with A1 |
| `route_path_completeness_follows_the_text` | `/v1/invoices/{invoice_id}` is complete. `{?}/invoices` is not |

**Commit:** `feat(domain): add file records and the records of the two stages`

## Task 9: The graph and `validate`

**Files:** create `src/domain/graph/{mod,index,nodes,edges,tree,records}.rs`.

**Produces:**

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

// index.rs, pub(crate)
pub(crate) struct GraphIndex<'g> {
    pub nodes: HashMap<NodeId, &'g Node>,          // the first node per id. N6 reports the rest
    pub parent: HashMap<NodeId, Vec<&'g Edge>>,    // incoming Contains edges per child
    pub out: HashMap<NodeId, Vec<&'g Edge>>,
}
```

`validate` builds a `GraphIndex` once, then calls four functions, each `fn check(g: &Graph, ix: &GraphIndex, out: &mut Vec<RuleViolation>)`:

| File | Rules |
|---|---|
| `nodes.rs` | N6, N7 |
| `edges.rs` | E5 to E12 |
| `tree.rs` | T1 to T5. T3 walks parents with a visited set, so a cycle ends the walk and is reported, never followed forever |
| `records.rs` | F1 to F3, R1, R3, C1, C3, L1, L3, B1, B2, Y1, Y2, H1, H2, U1, U3, U5, M1, G1, D1, D2, P1, P2, A2 |

A rule whose input is missing reports nothing and leaves that to the rule about the missing part. For example, an edge to an unknown node breaks E5 only, not E1 or T2 as well. Each violation's message names the node or edge it is about, by id and qualified name.

**Tests:** one per Graph rule, named `rule_<id>_...`. Each builds the smallest graph that breaks only that rule, and asserts that `validate` returns exactly one violation with that rule. Also:

| Test | Asserts |
|---|---|
| `empty_graph_breaks_only_n7` | `Graph::default().validate()` is one violation, N7 |
| `three_broken_rules_give_three_violations` | A graph that breaks N7, E5 and F1 gives all three, sorted |
| `contains_cycle_is_reported_once` | Two nodes that contain each other give T3, and `validate` returns |
| `edge_to_unknown_node_is_only_e5` | No E1, T2 or E11 violation for the same edge |

**Commit:** `feat(domain): validate a whole graph`

## Task 10: The Acme Shop fixtures

**Files:** create `src/domain/fixtures/mod.rs`, with `#[cfg(test)]` on its `mod` line.

**Produces:**

```rust
pub fn acme_workspace_layer() -> Result<Graph, DomainError>;   // 27 nodes, 54 edges
pub fn acme() -> Result<Graph, DomainError>;                   // plus the code layer of python-parsing.md
```

They return `Result`, not `Graph`, because building through the constructors can fail and `unwrap` is denied. A test calls `acme()?`.

The expected graph is [`examples/acme-shop/site/graph.json`](../../examples/acme-shop/site/graph.json). `acme_workspace_layer()` must give exactly its 27 workspace nodes and 54 workspace edges, with the same ids. `acme()` holds the subset of its code layer the checks below need, and every node it holds has the id that file gives it.

Nodes are built with `Node::workspace`, `Node::declared`, `Node::binary` and `Node::parsed`, and edges with `Edge::new`. Private helpers keep the fixture short: `project(&mut Graph, id, language)`, `contains(&mut Graph, parent, child, provenance)`, and so on.

**Tests:** every check listed under [Validating an implementation](../domain-model.md#validating-an-implementation), level 3:

| Test | Asserts |
|---|---|
| `acme_workspace_layer_is_valid` | `validate()` is empty |
| `acme_workspace_layer_counts` | Each node and edge count of the domain model's table, by `NodeKindName` and `EdgeKindName` |
| `acme_api_services_have_different_ids` | The two `api` services differ |
| `acme_is_stable` | Two builds give equal graphs |
| `acme_walk_reaches_admin` | The six steps of the walk in graph-model.md can be followed over `acme()`'s edges |
| `acme_is_valid` | `acme().validate()` is empty |
| `acme_billing_api_is_fastapi` | `api` has `Framework::Fastapi { app: Some(billing.api.app) }`, `worker` has `Framework::Plain` |
| `acme_flow_edge_rests_on_inferred_type` | `r.save()` is a `Calls` edge with `resolved_by: Flow`, and `r` has an inferred type with evidence 2 |

The other checks of level 3 (route paths, reach, `Requests`, `Sends`, `Invokes`) are asserted on `acme()` too, one test each, named after what they check.

**Commit:** `test(domain): add the Acme Shop fixtures`
