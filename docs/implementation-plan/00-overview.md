# Implementation Plan: Overview

What every step plan in this folder shares: how the work is cut into slices that several developers can build at once, the constraints of the repository, where code goes, and the names one slice hands to the next.

## The plans

| Roadmap step | Plan | Specified by |
|---|---|---|
| 1. Domain types | [step-1-domain-types.md](./step-1-domain-types.md) | [domain-model.md](../domain-model.md) |
| 2. Configuration | [step-2-configuration.md](./step-2-configuration.md) | [configuration-guide.md](../configuration-guide.md) |
| 3. SQLite store | sliced below, not written as tasks | [storage-model.md](../storage-model.md) |
| 4. Workspace indexing | [step-4-workspace-indexing.md](./step-4-workspace-indexing.md) | [example-workspace.md](../example-workspace.md), [graph-model.md](../graph-model.md) |
| 5. Python parsing | [step-5-python-parsing.md](./step-5-python-parsing.md) | [domain-model.md](../domain-model.md), [storage-model.md](../storage-model.md) |
| 6. Queries | [step-6-queries.md](./step-6-queries.md) | [usage-guide.md](../usage-guide.md) |
| 7. Command line | [step-7-command-line.md](./step-7-command-line.md) | [usage-guide.md](../usage-guide.md) |
| 8. UTCP manual | [step-8-utcp-manual.md](./step-8-utcp-manual.md) | [usage-guide.md](../usage-guide.md), [modes.md](../modes.md) |

Step 3 has a specification and no task plan. Its specification is detailed enough to build from.

Each plan covers Release 1 only. Operational support (Release 3) is not planned here.

## Working in parallel

The work is cut into **slices**. A slice is one pull request by one developer: a few tasks that touch their own files and end in something tested. The roadmap's steps say what is delivered in what order. The slices say what can be built at the same time.

Three things make that possible.

1. **Contracts first.** Slice C0 lands the traits and result types that slices share, with no behaviour. After it, a slice that calls the store does not wait for SQLite, and the command line does not wait for the queries.
2. **A store in memory.** C0 also lands `MemoryStore`, a `GraphStore` that holds a `Graph` in memory. Every use case is tested on it. SQLite must pass the same tests.
3. **One fixture.** The Acme Shop graph exists as a value in code from slice 1E, so a query can be tested before any indexer exists.

### Rules for a slice

- **A slice owns its files.** Two slices in flight never edit the same file. The file tables of each plan say who owns what.
- **Shared files change in one line.** A slice adds its own `mod` line to a `mod.rs` and nothing else there. `Cargo.toml` is changed only by C0, which adds every crate at once, so `Cargo.lock` never conflicts.
- **Types before bodies.** A slice's first commit is the types in its **Produces** block. Slices that depend on those types can then start. `todo!()` cannot be used as a placeholder: CI refuses it.
- **A slice is merged only when green.** The three checks under [Before every commit](#before-every-commit) pass, on its own.
- **A changed name is changed everywhere.** If a slice has to change a name in [Names handed between slices](#names-handed-between-slices), it changes this page in the same pull request.

### The slices

A slice can start as soon as every slice in its **Needs** column is merged, or has at least merged its types.

| Slice | Delivers | Needs | Plan |
|---|---|---|---|
| 1A | `DomainError`, `RuleId`, and the value types: `NodeId`, `ReferenceId`, `ProjectId`, `ComposeName`, `RelPath`, `ContentHash`, `Name`, `QualifiedName`, `CommitId`, `Line`, `Column`, `Span`, `Site`, `Template`, `HttpMethod`, `Language`, `DependencyManager` | | [domain-model.md](../domain-model.md#value-types) |
| 1B | `Node`, its kinds, scope, origin, identity and data. Rules N2 to N5, N9, N10 | 1A | [domain-model.md](../domain-model.md#node) |
| 1C | `Edge`, its kinds and data, its provenance, and `resolved_by` with `Resolution`. There is no `Flow` provenance (ADR 0017). `UnresolvedReference`, which holds an `EdgeKind`. Rules E1 to E3, E13 and R2 | 1A, 1B's types | [domain-model.md](../domain-model.md#edge) |
| 1D | `FileRecord`, `CallSite`, `Binding`, `Return`, `InferredType`, `Reach`, `RoutePath`, the unmatched calls and messages, `MessagePayload`, `Warning`, `ProjectCheckout`. Rules C2, M2, G2, A1 | 1A | [domain-model.md](../domain-model.md#file-record) |
| 1E | `Graph`, `validate` with every Graph rule, and the Acme Shop fixture | 1B, 1C, 1D | [domain-model.md](../domain-model.md#validating-an-implementation) |
| C0 | Contracts: the ports, the query result types, `MemoryStore`, the shared store tests, every crate | 1E | [below](#slice-c0-contracts) |
| 2A | Find the workspace | | [step 2](./step-2-configuration.md) |
| 2B | Parse the configuration into the raw model | | [step 2](./step-2-configuration.md) |
| 2C | Check rules 1 to 13, and `load` | 1A, 2B | [step 2](./step-2-configuration.md) |
| 2D | What `init` writes | 2B | [step 2](./step-2-configuration.md) |
| 2E | The text of the `workbench` and `python` skills | | [step 2](./step-2-configuration.md) |
| 2F | Link the shared skills for AI platforms | 2D | [step 2](./step-2-configuration.md) |
| 3A | The schema, opening a store, the format version | C0 | [storage-model.md](../storage-model.md#the-schema) |
| 3B | Reading: every read operation of the port | 3A | [storage-model.md](../storage-model.md#how-the-store-is-read) |
| 3C | Writing: one index as one transaction, replacing a file, the workspace layer | 3A | [storage-model.md](../storage-model.md#how-the-store-is-written) |
| 4A | Read `pyproject.toml` | 1A | [step 4](./step-4-workspace-indexing.md) |
| 4B | Read and merge compose files | 1A | [step 4](./step-4-workspace-indexing.md) |
| 4C | Read a project's checkout | C0 | [step 4](./step-4-workspace-indexing.md) |
| 4D | Resolve stacks, networks and services | 2C, 4B, 4I | [step 4](./step-4-workspace-indexing.md) |
| 4I | Read Dockerfiles and work out each service's command line | 1A, 4B | [step 4](./step-4-workspace-indexing.md) |
| 4H | Decide each binary's framework | C0, 2C, 4B, 4I | [step 4](./step-4-workspace-indexing.md) |
| 4E | Build the workspace layer | 1E, 2C, 4A, 4D, 4H | [step 4](./step-4-workspace-indexing.md) |
| 4F | The Acme Shop workspace as files | | [step 4](./step-4-workspace-indexing.md) |
| 4G | The index use case, end to end | C0, 4C, 4E, 4F | [step 4](./step-4-workspace-indexing.md) |
| 5A | Choose the files to read | C0, 2C | [step 5](./step-5-python-parsing.md) |
| 5B | Python: definitions | C0 | [step 5](./step-5-python-parsing.md) |
| 5C | Python: references | 5B | [step 5](./step-5-python-parsing.md) |
| 5D | Resolve references inside a project | C0 | [step 5](./step-5-python-parsing.md) |
| 5E | Resolve imports across projects | 5D | [step 5](./step-5-python-parsing.md) |
| 5F | Index code incrementally | C0, 5A | [step 5](./step-5-python-parsing.md) |
| 5G | Acme Shop with source, end to end | 4G, 5C, 5E, 5F, 3C | [step 5](./step-5-python-parsing.md) |
| 6A | Naming a node, budgets, freshness | C0 | [step 6](./step-6-queries.md) |
| 6B | `search`, `node` | 6A | [step 6](./step-6-queries.md) |
| 6C | `files`, `deps`, `status` | 6A | [step 6](./step-6-queries.md) |
| 6D | The walk, `callers`, `callees`, `neighbors` | 6A | [step 6](./step-6-queries.md) |
| 6E | `impact` | 6D | [step 6](./step-6-queries.md) |
| 6F | `explore` | 6B, 6E | [step 6](./step-6-queries.md) |
| 6G | What stage 2 adds to `node`, `search`, `callers`, `files` | 6B, 6C, 6D | [step 6](./step-6-queries.md) |
| 6H | `impact` over the results of stage 2 | 6E | [step 6](./step-6-queries.md) |
| 6I | The tests to run for a change | 6H | [step 6](./step-6-queries.md) |
| 6J | API and event contracts | 6H | [step 6](./step-6-queries.md) |
| 7A | The command tree, flags and exit codes | C0 | [step 7](./step-7-command-line.md) |
| 7B | Text output of the read commands | C0 | [step 7](./step-7-command-line.md) |
| 7C | Text output of `init`, `check`, `index`, `status` | C0, 2C | [step 7](./step-7-command-line.md) |
| 7D | Wiring, and tests that run the binary | 7A, 7B, 7C, 2F, 3B, 3C, 4G, 6F, 6G, 6I, 6J | [step 7](./step-7-command-line.md) |
| 7E | Installation | 7D | [step 7](./step-7-command-line.md) |
| 8A | The manual document, and modes | C0 | [step 8](./step-8-utcp-manual.md) |
| 8B | The twelve tools, as call templates | 8A, 7A | [step 8](./step-8-utcp-manual.md) |
| 8D | Wiring `workbench manual`, and tests that run the binary | 8B, 7D | [step 8](./step-8-utcp-manual.md) |

### What can run at once

| Wave | Slices | Developers it can occupy |
|---|---|---|
| 1 | 1A, 2A, 2B, 2E, 4F | 5 |
| 2 | 1B, 1C, 1D, 2C, 2D, 4A, 4B | 7 |
| 3 | 1E, 2F, 4I | 3 |
| 4 | C0, 4D | 2 |
| 5 | 3A, 4C, 4H, 5A, 5B, 5D, 6A, 7A, 7B, 7C, 8A | 11 |
| 6 | 3B, 3C, 4E, 5C, 5E, 5F, 6B, 6C, 6D, 8B | 10 |
| 6b | 4G | 1 |
| 7 | 5G, 6E, 6G | 3 |
| 8 | 6F, 6H | 2 |
| 9 | 6I, 6J | 2 |
| 10 | 7D | 1 |
| 11 | 7E, 8D | 2 |

Waves 3 and 4 are the narrow point: most of what follows waits for 1E and then C0. Keep those two small and merge them fast. The last waves are narrow too, because they join everything; they are mostly wiring and tests.

## Slice C0: contracts

**Files:** `src/ports/outbound/{mod,store,files,git,parser}.rs`, `src/use_cases/query/results.rs`, `src/ports/outbound/memory_store.rs`, `src/ports/outbound/store_tests.rs`, `Cargo.toml`.

- [ ] Add every crate of [Crates to add](#crates-to-add) to `Cargo.toml` in one commit.
- [ ] Write the traits `GraphStore`, `IndexWriter`, `Files`, `Git` and `LanguageParser`, and the types they use, exactly as in [Names handed between slices](#names-handed-between-slices).
- [ ] Write the result types of every query in `results.rs`, each deriving `Debug`, `Clone`, `PartialEq` and `serde::Serialize`.
- [ ] Write `MemoryStore`: a `GraphStore` and `IndexWriter` over a `Graph` behind a mutex. `MemoryStore::from(graph)` seeds it.
- [ ] Write `store_tests`: a set of test functions generic over `S: GraphStore`, covering every operation of the port and the four ways of writing in [storage-model.md](../storage-model.md#how-the-store-is-written). Run them on `MemoryStore`. Slice 3 runs the same functions on SQLite.
- [ ] Commit: `feat: add the ports, the query result types and a store in memory`

## How a task is written

Each task lists its files, the interfaces it produces, and its tests by name with what each asserts. The developer writes the test code and the bodies. Every task is done the same way:

- [ ] Commit the types of the task's **Produces** block.
- [ ] Write the tests listed. Run them and see them fail.
- [ ] Implement until they pass.
- [ ] Run the three checks under [Before every commit](#before-every-commit).
- [ ] Commit with the message the task gives.

## Global constraints

Taken from `Cargo.toml`, `rust-toolchain.toml` and `.github/workflows/ci.yml`.

- Rust edition `2024`, `rust-version = "1.100.0"`, stable toolchain.
- One binary crate, `workbench`, with entry point `src/main.rs`. There is no `src/lib.rs`, so tests in `tests/` can only run the binary. Unit tests sit beside the code in `#[cfg(test)]` modules.
- `unwrap_used`, `panic` and `unsafe_code` are denied, in tests too. A test returns `Result<(), Box<dyn std::error::Error>>` and uses `?`.
- `todo` is a warning, and CI turns warnings into errors. No `todo!()` is ever merged.
- `missing_docs` and `missing_debug_implementations` are warnings as well. Every public item has a doc comment and derives or implements `Debug`.
- `redundant_clone` and `large_enum_variant` are denied.
- Results go to standard output. Messages, warnings and progress go to standard error.
- No network calls and no telemetry in any Release 1 code path.
- macOS and Linux only. Paths in the configuration and the graph use `/`.
- `cargo deny` must pass for every crate added. `deny.toml` holds the rules.

### Before every commit

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
```

## Where code goes

The scaffold is hexagonal. A module may depend only on the ones named in its last column.

| Module | Holds | Depends on |
|---|---|---|
| `src/domain` | The types and rules of [domain-model.md](../domain-model.md) | nothing |
| `src/config` | Finding, reading and checking `.workbench/config.yml`, and what `init` writes | `domain` |
| `src/ports/outbound` | The traits the core needs from the outside: store, files, parsers, git | `domain` |
| `src/use_cases` | Indexing and every query | `domain`, `config`, `ports` |
| `src/adapters/driven/store/sqlite` | The SQLite store | `domain`, `ports` |
| `src/adapters/driven/fs` | Reading files, walking folders, reading `.git` | `domain`, `ports` |
| `src/adapters/driven/parse` | Reading source code, manifests and compose files | `domain`, `ports` |
| `src/adapters/driving/cli` | The command line | `use_cases`, `config` |
| `src/adapters/driving/utcp` | The UTCP manual | `use_cases`, `config` |
| `src/main.rs` | Wiring: builds the adapters and hands them to the use cases | everything |

## Crates to add

Proposed. C0 adds them all. Pick the latest release at the time of building, and check each with `cargo deny`.

| Crate | Used for |
|---|---|
| `thiserror` | Error types |
| `blake3` | Node ids and content hashes |
| `serde` with `derive`, `serde_json` | The configuration model, the result of every query, `--json` and the UTCP manual |
| A maintained YAML crate for `serde`, such as `serde_yaml_ng` | Reading YAML. `serde_yaml` itself is no longer maintained |
| `toml` | Reading `pyproject.toml` |
| `ignore` and `globset` | Walking a project by `.gitignore` rules, and `exclude` patterns |
| `tree-sitter` and `tree-sitter-python` | Parsing Python |
| `assert_cmd` and `tempfile`, as dev-dependencies | Tests that run the binary |

`sqlx`, `tokio` and `clap` are already in `Cargo.toml`. `sqlx` is asynchronous, so the store port and every use case are `async`.

Slices 1A to 1D, 2A and 2B start before C0. They need `thiserror`, `blake3`, `serde` and the YAML crate, so whichever of them merges first adds those four, and C0 adds the rest.

## Names handed between slices

Later slices use these names. A slice that has to change one changes it here in the same pull request.

### From step 1, in `src/domain`

| Name | What it is |
|---|---|
| `NodeId`, `ReferenceId`, `ProjectId`, `ComposeName`, `RelPath`, `ContentHash`, `Name`, `QualifiedName`, `Line`, `Column`, `CommitId` | The value types, each a newtype with a private field. Each read from text has `fn parse(&str) -> Result<Self, DomainError>`; ids and hashes are computed. See [How the types are written in Rust](../domain-model.md#how-the-types-are-written-in-rust) |
| `Node`, `NodeKind`, `NodeKindName`, `Scope`, `Origin`, `Span` | A node. `NodeKind` holds the kind's data in its variant, such as `Function(Callable)`; `NodeKindName` is the same kind without data. `Node::parsed(...)`, `Node::declared(...)` and `Node::binary(...)` each take one input struct, and compute the id. `Node::parsed` takes a `ParsedFrom` (`Source(Language)` or `Compose`) and `Node::binary` its project's `Language`, to check rule N9; neither stores it |
| `ProjectData`, `BinaryData`, `Callable`, `TypeDecl`, `Member`, `RouteData`, `CommandData`, `Doc` | The data a node kind carries, held inside its `NodeKind` variant |
| `Framework`, `FrameworkName`, `FrameworkSource`, `FrameworkRole`, `Visibility`, `ParamSource`, `HttpMethod` | `Plain`, `Fastapi { app: Option<QualifiedName> }`, `Angular`; the same three without data; `Declared`, `Compose`, `Dockerfile`, `Entry`; `App`, `Router { prefix }`, `Middleware`, `ExceptionHandler`, `LifecycleHook`, `Fixture`, `Model`; the rest as in [domain-model.md](../domain-model.md#node-data) |
| `Edge`, `EdgeKind`, `EdgeKindName`, `Provenance`, `Site` | An edge. `Edge::new` takes the two end nodes, to check E1; stores rebuild edges with `Edge::restore`. `Provenance::Declared { note: Option<String> }` holds the note. `EdgeKind` carries its data: `Imports { specifier, alias, type_only }`, `DependsOn { scope }`, `ConnectsTo { protocol }`, `Mounts { prefix }`, `Requests { method, path }`, `Sends { name }`, `Invokes { words }`, and the data-less `Receives`. An edge made by resolution records `resolved_by: Option<Resolution>` |
| `Resolution`, `Template` | `Import`, `SelfMember`, `SameFile`, `Project`, `CrossProject`, `ReExport`, `Annotation`, `LocalInference`, `Inherited`, `Flow`, `Framework`, `RouteMatch`, `MessageMatch`, `CommandMatch`; parts `Text(String)`, `Hole(String)` or `Unknown`, for a route's path, a prefix and a template value |
| `DependencyScope`, `Protocol` | `Build` or `Dev`; `Http`, `Grpc` or `Database` |
| `Language`, `DependencyManager` | `Python`, `TypeScript`; `Uv`, `Poetry`, `Npm`, `Pnpm`, `Yarn`, `Bun` |
| `FileRecord`, `ParseStatus` | A file record |
| `UnresolvedReference` | A reference waiting to be resolved |
| `CallSite`, `Argument`, `Shape`, `Binding`, `Return` | What stage 1 records about calls, assignments and returns |
| `InferredType`, `Reach`, `Root`, `RoutePath`, `Candidates`, `UnmatchedHttpCall`, `UnmatchedMessage`, `MessageDirection`, `MessagePayload` | What stage 2 computes. `MessageDirection` is `Send` or `Receive`, kept apart from the store's `Direction` |
| `Warning`, `WarningCode` | A warning |
| `ProjectCheckout`, `Head` | A project's checkout: `head: Option<Head>`, with `Head { commit: CommitId, branch: Option<String> }` |
| `Graph` | Nodes, edges, file records, references, warnings and checkouts together. `fn validate(&self) -> Vec<RuleViolation>` |
| `RuleViolation` | `{ rule: RuleId, message: String }`. `RuleId` lists every rule id of the domain model, such as `RuleId::T2`, and prints as `T2` |
| `DomainError`, `RuleId` | What building a broken value returns: `Rule { rule: RuleId, message }` or `Malformed { value, input, reason }` |
| `fixtures::acme_workspace_layer() -> Graph` | The Acme Shop workspace layer: 27 nodes and 53 edges |
| `fixtures::acme() -> Graph` | The same, plus the code nodes and edges the walk of [graph-model.md](../graph-model.md#walking-the-graph) needs |

Both fixtures are compiled only for tests.

### From C0: the store, in `src/ports/outbound/store.rs`

```rust
pub trait GraphStore {
    type Writer: IndexWriter;
    async fn node(&self, id: &NodeId) -> Result<Option<Node>, StoreError>;
    async fn nodes_named(&self, scope: Option<&Scope>, qualified_name: &str) -> Result<Vec<Node>, StoreError>;
    async fn search(&self, text: &str, filter: &NodeFilter, limit: usize) -> Result<Vec<Node>, StoreError>;
    async fn nodes_of_file(&self, file: &FileRef) -> Result<Vec<Node>, StoreError>;
    async fn edges(&self, of: &[NodeId], direction: Direction, kinds: &[EdgeKindName]) -> Result<Vec<Edge>, StoreError>;
    async fn files(&self, filter: &FileFilter) -> Result<Vec<FileRecord>, StoreError>;
    async fn warnings(&self) -> Result<Vec<Warning>, StoreError>;
    async fn checkouts(&self) -> Result<Vec<ProjectCheckout>, StoreError>;
    async fn inferred_type(&self, parameter: &NodeId) -> Result<Option<InferredType>, StoreError>;
    async fn reached_by(&self, node: &NodeId) -> Result<Vec<Root>, StoreError>;
    async fn reached_from(&self, root: &Root) -> Result<Vec<NodeId>, StoreError>;
    async fn route_paths(&self, route: &NodeId) -> Result<Vec<RoutePath>, StoreError>;
    async fn unmatched_http_calls(&self, node: &NodeId) -> Result<Vec<UnmatchedHttpCall>, StoreError>;
    async fn unmatched_messages(&self, node: &NodeId) -> Result<Vec<UnmatchedMessage>, StoreError>;
    async fn payloads(&self, of: &NodeId) -> Result<Vec<MessagePayload>, StoreError>;   // of a topic, a queue or a class
    async fn unreached_files(&self, filter: &FileFilter) -> Result<Vec<FileRecord>, StoreError>;
    async fn counts(&self) -> Result<Counts, StoreError>;
    async fn meta(&self) -> Result<StoreMeta, StoreError>;
    async fn begin_index(&self, force: bool) -> Result<Self::Writer, StoreError>;
}

pub trait IndexWriter {
    async fn replace_file(&mut self, parsed: ParsedFile) -> Result<Vec<FileRef>, StoreError>;
    async fn remove_file(&mut self, file: &FileRef) -> Result<Vec<FileRef>, StoreError>;
    async fn unresolved(&mut self) -> Result<Vec<UnresolvedReference>, StoreError>;
    async fn resolve(&mut self, reference: &UnresolvedReference, edge: Edge) -> Result<(), StoreError>;
    async fn rebuild_workspace_layer(&mut self, layer: WorkspaceLayer) -> Result<(), StoreError>;
    async fn call_sites(&mut self) -> Result<(Vec<CallSite>, Vec<Binding>, Vec<Return>), StoreError>;
    async fn replace_analysis(&mut self, analysis: Analysis) -> Result<(), StoreError>;
    async fn commit(self) -> Result<(), StoreError>;
}
```

| Name | What it is |
|---|---|
| `Direction` | `Out`, `In` or `Both` |
| `NodeFilter` | `{ kinds: Vec<NodeKindName>, project: Option<ProjectId> }` |
| `FileFilter` | `{ project: Option<ProjectId>, status: Option<ParseStatus> }` |
| `FileRef` | `{ project: ProjectId, path: RelPath }` |
| `ParsedFile` | `{ record: FileRecord, nodes: Vec<Node>, edges: Vec<Edge>, unresolved: Vec<UnresolvedReference>, call_sites: Vec<CallSite>, bindings: Vec<Binding>, returns: Vec<Return> }` |
| `Analysis` | `{ flow_edges: Vec<Edge>, flow_resolved: Vec<ReferenceId>, inferred: Vec<InferredType>, reach: Vec<Reach>, route_paths: Vec<RoutePath>, requests: Vec<Edge>, unmatched_http_calls: Vec<UnmatchedHttpCall>, messages: Vec<Edge>, unmatched_messages: Vec<UnmatchedMessage>, payloads: Vec<MessagePayload>, invokes: Vec<Edge>, warnings: Vec<Warning> }`, the results of stage 2. `search` also matches route paths. `replace_analysis` deletes the previous ones first |
| `Counts` | `{ nodes: u64, edges: u64, files: u64 }` |
| `StoreMeta` | `{ format_version: u32, workbench_version: String, indexed_at: Option<String> }` |
| `WorkspaceLayer` | `{ nodes: Vec<Node>, edges: Vec<Edge>, warnings: Vec<Warning>, checkouts: Vec<ProjectCheckout> }` |
| `StoreError` | Includes `IndexRunning`, `WrongFormat { found: Option<u32> }` and `NotIndexed` |

`replace_file` and `remove_file` return the files that referred to something now gone. The indexer reads those again, as [storage-model.md](../storage-model.md#replacing-a-file) describes. Dropping the writer without `commit` rolls everything back.

### From C0: the other ports

```rust
pub trait Files {
    fn read(&self, path: &Path) -> Result<Vec<u8>, FilesError>;
    fn exists(&self, path: &Path) -> bool;
    fn stat(&self, path: &Path) -> Result<FileStat, FilesError>;     // size and mtime, reading no content
    fn list(&self, dir: &Path) -> Result<Vec<PathBuf>, FilesError>;
    fn walk(&self, root: &Path, exclude: &[String]) -> Result<Vec<RelPath>, FilesError>;
}

pub struct FileStat { pub size: u64, pub mtime: i64 }      // mtime in nanoseconds since 1970 UTC

pub trait Git { fn checkout(&self, project_root: &Path) -> Checkout; }
pub struct Checkout { pub branch: Option<String>, pub commit: Option<String> }

pub trait LanguageParser {
    fn language(&self) -> Language;
    fn extensions(&self) -> &'static [&'static str];
    fn parse(&self, file: &FileRef, module_path: &str, source: &[u8]) -> Result<ParsedSource, ParseError>;
    /// Reads only imports and module-level statements of a binary's entry file.
    fn probe_framework(&self, module_path: &str, source: &[u8]) -> Option<FrameworkProbe>;
}
pub struct ParsedSource { pub nodes: Vec<Node>, pub edges: Vec<Edge>, pub unresolved: Vec<UnresolvedReference>, pub call_sites: Vec<CallSite>, pub bindings: Vec<Binding>, pub returns: Vec<Return> }
pub struct FrameworkProbe { pub framework: Framework, pub app: Option<String> }
```

### From C0: the query results, in `src/use_cases/query/results.rs`

Every query returns `Answer<T>`. The command line prints it, and the UTCP manual makes an AI tool call the command with `--json`, so both give the same answer.

```rust
pub struct Answer<T> { pub result: T, pub freshness: Freshness, pub truncated: Option<String> }
pub struct Freshness { pub indexed_at: Option<String>, pub changed_files: u64, pub moved_projects: Vec<MovedProject> }
pub struct MovedProject { pub project: ProjectId, pub indexed_commit: Option<String>, pub current_commit: Option<String> }
pub struct Location { pub node: NodeId, pub kind: NodeKind, pub scope: Scope, pub qualified_name: String, pub path: Option<RelPath>, pub line: Option<u32> }
```

| `T` | Returned by | Holds |
|---|---|---|
| `SearchResult` | `search` | `matches: Vec<Location>` |
| `NodeView` | `node` | The node, its source, its direct callers and callees, and `details`: what stage 2 says about it, by kind |
| `FileView` | `node --file` | The file's lines, and the nodes it holds |
| `CallList` | `callers`, `callees` | `calls: Vec<Call>`, each a `Location`, the `Site` of the call, its depth and its `resolved_by` |
| `NeighborsResult` | `neighbors` | The nodes reached, and the edges that reached them |
| `ImpactResult` | `impact` | `by_project: Vec<ProjectImpact>`, each entry with the path of edges that led to it, type-only and topic-crossing steps labelled; the tests that reach it; `api_contract` and `event_contract`, each optional |
| `TestList` | `impact --tests` | `tests: Vec<TestCase>`, each a pytest node id and its location |
| `ExploreResult` | `explore` | `sources: Vec<SourceBlock>`, `flow: Vec<Edge>`, `blast_radius: Vec<ImpactSummary>` |
| `FileList` | `files` | `files: Vec<FileRecord>` |
| `DependencyList` | `deps` | `dependencies: Vec<Dependency>`, each with its scope and provenance |
| `StatusReport` | `status` | Counts, checkouts, warnings, failed files |

`truncated` is `None` for a complete answer, and otherwise says what the budget left out.

## The test workspace

Two forms of the Acme Shop workspace serve the tests.

- **As a value:** `fixtures::acme()`, from slice 1E. Queries are tested on it through `MemoryStore`.
- **As files:** `tests/fixtures/acme/`, from slice 4F: the configuration, the three compose files, the `pyproject.toml` files and the Python source. Indexing is tested on it. Its layout is the one in [example-workspace.md](../example-workspace.md#the-application).

Slice 5G checks that indexing the files gives the value.
