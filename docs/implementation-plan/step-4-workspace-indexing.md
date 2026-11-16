# Step 4: Workspace Indexing Implementation Plan

**Goal:** Turn the configuration, the dependency manager files and the compose files into the workspace layer of the graph, and store it.

**Architecture:** Three readers each turn one kind of file into plain data: a manifest, a compose stack, a git checkout. One pure function then builds the nodes, edges and warnings from the configuration and that data, with no disk access, so it can be tested with values alone. A use case wires the readers, the builder, `validate` and the store together.

**Tech stack:** `toml`, the YAML crate of step 2.

**Spec:** [example-workspace.md](../example-workspace.md), [graph-model.md](../graph-model.md), [configuration-guide.md](../configuration-guide.md) rules 14 to 19, [domain-model.md](../domain-model.md). Capabilities W1 to W9, W13, G10.

**Read first:** [00-overview.md](./00-overview.md).

**Needs:** steps 1, 2 and 3.

## Global constraints

- This step parses no source code. A binary's entry file gets a `File` node and a file record with `GrammarUnavailable`; step 5 replaces it when the language is parsed.
- Nothing is run. Docker is never called, and compose files are only read.
- A broken rule from 14 to 19 stops the index before anything is written. A warning never stops it.
- The layer built here must pass `Graph::validate` with no violation.
- Reading `.git` fetches nothing and runs no `git` program.

## Review focus

- A compose file that uses `include`, `extends` or profiles: these are not followed. The file is read as written, and one log line says which key was skipped. Task 2.
- A build context given with a variable, such as `${SRC}/api`, cannot be matched to a project. The service must then be mapped under `services`; without a mapping it is a problem that says so. Task 4.
- A service with `network_mode: host` or `none` joins no network. It gets no `Joins` edge and its links are not checked against networks. Task 4.
- A project that is not a git repository, or is on no branch, still indexes. Its checkout has an empty branch, or is empty. Task 3.
- A `pyproject.toml` that does not parse is a warning-free error naming the file, not a crash. Task 1.

## File structure

| File | Holds |
|---|---|
| `src/adapters/driven/fs/files.rs` | The `Files` port of C0, on the real disk |
| `src/adapters/driven/fs/git.rs` | The `Git` port of C0, on the real disk |
| `src/adapters/driven/parse/manifest/pyproject.rs` | Reading `pyproject.toml` for uv and poetry |
| `src/adapters/driven/parse/compose.rs` | Reading and merging compose files |
| `src/use_cases/index/stacks.rs` | Compose names, network names, matching services |
| `src/use_cases/index/workspace_layer.rs` | Building nodes, edges and warnings |
| `src/use_cases/index/mod.rs` | The `IndexWorkspace` use case |
| `tests/fixtures/acme/` | The Acme Shop workspace as files |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 4A | 1 | 1A | `parse/manifest/pyproject.rs` |
| 4B | 2 | 1A | `parse/compose.rs` |
| 4C | 3 | C0 | `fs/files.rs`, `fs/git.rs` |
| 4D | 4 | 2C, 4B | `index/stacks.rs` |
| 4E | 5 | 1E, 2C, 4A, 4D | `index/workspace_layer.rs` |
| 4F | the fixture files | | `tests/fixtures/acme/` |
| 4G | 6 | C0, 4C, 4E, 4F | `index/mod.rs` |

4A, 4B and 4F need nothing from each other and can start together, by three developers. Tasks 1, 2, 4 and 5 are pure functions over text and values: they read no disk, so each is tested with strings written in the test. 4D and 4E can start as soon as the types of the slices they need are merged. 4G joins everything and is tested on `MemoryStore`; it does not wait for SQLite.

## Task 1: Read a Python manifest

**Files:** create `src/adapters/driven/parse/manifest/pyproject.rs`.

**Produces:**

```rust
pub struct Manifest { pub local_paths: Vec<(PathBuf, DependencyScope)>, pub import_names: Vec<String> }
pub fn read_pyproject(text: &str, manager: DependencyManager, packages_on_disk: &[String]) -> Result<Manifest, ManifestError>;
```

Local paths come from `[tool.uv.sources]` entries with a `path` for uv, and from dependencies with a `path` under `[tool.poetry.dependencies]` and `[tool.poetry.group.*.dependencies]` for poetry. A dependency in a dev group, or in uv's `dev-dependencies`, has scope `Dev`.

Import names are taken, in this order, from the first source that gives any: the `packages` the manifest declares; `packages_on_disk`, the folders with an `__init__.py` directly under `src/` or the project root; the project's name with `-` turned into `_`.

**Tests:**

| Test | Asserts |
|---|---|
| `uv_path_source_is_a_local_dependency` | `shared-api = { path = "../shared-api" }` gives one path, scope `Build` |
| `poetry_path_dependency_is_a_local_dependency` | Same result from the poetry form |
| `poetry_dev_group_has_dev_scope` | Scope `Dev` |
| `registry_dependency_is_ignored` | `requests = "^2"` gives no path |
| `import_name_comes_from_declared_packages` | `packages = [{ include = "shared_api" }]` gives `shared_api` |
| `import_name_falls_back_to_the_disk_then_the_name` | Each fallback in turn |
| `broken_toml_is_an_error` | `ManifestError::Syntax` |

**Commit:** `feat(index): read local dependencies from pyproject.toml`

## Task 2: Read and merge compose files

**Files:** create `src/adapters/driven/parse/compose.rs`.

**Produces:**

```rust
pub struct ComposeStack {
    pub name: Option<String>,
    pub services: BTreeMap<String, ComposeService>,
    pub networks: BTreeMap<String, ComposeNetwork>,
    pub skipped_keys: Vec<String>,
}
pub struct ComposeService { pub build_context: Option<String>, pub build_target: Option<String>, pub networks: Vec<String>, pub position: Span }
pub struct ComposeNetwork { pub name: NetworkName, pub external: bool }
pub enum NetworkName { Stated(String), Unreadable(String), Unstated }

pub fn read_compose(files: &[(RelPath, String)]) -> Result<ComposeStack, ComposeError>;
pub fn discover_compose_files(project_files: &[String]) -> Vec<String>;
```

Files are merged in the order given: a later file adds services and networks and replaces a service's build target. `build: .` and `build: { context: . }` are the same. A service that lists no network joins `default`, and a `default` network exists even when the file does not declare it. A network name containing `${` is `Unreadable`.

`discover_compose_files` returns the first of `compose.yaml`, `compose.yml`, `docker-compose.yaml`, `docker-compose.yml` that is present, followed by its override file when that is present too.

**Tests:**

| Test | Asserts |
|---|---|
| `acme_infrastructure_file` | Name `acme-infra`; `kafka` and `postgres` have no build context; network `backbone` is `Stated("acme-backbone")` |
| `acme_billing_file` | `api` and `worker` have build targets `api` and `worker`, and each joins `default` and `backbone` |
| `acme_ledger_file` | `backbone` is `Unreadable`; neither service has a build target |
| `later_file_overrides_build_target` | The second file's target wins |
| `later_file_adds_a_service` | Two services after the merge |
| `service_without_networks_joins_default` | `networks == ["default"]` |
| `include_and_extends_are_skipped_and_reported` | `skipped_keys` holds both |
| `discovery_prefers_compose_yaml_and_adds_its_override` | Given all four names and `compose.override.yaml`, returns `compose.yaml` then the override |

**Commit:** `feat(index): read and merge compose files`

## Task 3: Read files and a project's checkout from disk

**Files:** create `src/adapters/driven/fs/files.rs`, `src/adapters/driven/fs/git.rs`.

**Produces:**

```rust
pub struct DiskFiles;      // implements the `Files` port, except `walk`, which slice 5A adds
pub struct DiskGit;        // implements the `Git` port
```

`DiskGit` reads `.git/HEAD`. `ref: refs/heads/<name>` gives the branch, and the commit is read from that ref's file or from `packed-refs`. A 40-character `HEAD` is a commit with no branch. A `.git` that is a file, as in a worktree, is followed through its `gitdir:` line.

**Tests:**

| Test | Asserts |
|---|---|
| `branch_and_commit_are_read` | A temp repository on `release-2.4` gives both |
| `detached_head_has_a_commit_and_no_branch` | `branch == None` |
| `commit_is_found_in_packed_refs` | With no loose ref file |
| `folder_without_git_gives_an_empty_checkout` | Both `None` |
| `worktree_git_file_is_followed` | The branch of the worktree |

**Commit:** `feat(index): read each project's branch and commit`

## Task 4: Resolve the stacks

**Files:** create `src/use_cases/index/stacks.rs`.

**Produces:**

```rust
pub struct ResolvedStack {
    pub name: ComposeName, pub owner: StackOwner, pub users: Vec<ProjectId>,
    pub services: Vec<ResolvedService>, pub networks: Vec<ResolvedNetwork>,
}
pub enum StackOwner { Shared, Project(ProjectId) }
pub enum ServiceRole { Runs { project: ProjectId, binary: String, from: Provenance }, BuiltFrom { project: ProjectId, from: Provenance }, External }
pub struct ResolvedNetwork { pub key: String, pub real_name: Option<String>, pub from_configuration: bool }

pub fn resolve_stacks(config: &Config, stacks: Vec<(StackSource, ComposeStack)>) -> Result<(Vec<ResolvedStack>, Vec<Warning>), Vec<ConfigProblem>>;
```

- **Compose name:** the configuration's `name`, else the file's, else the first file's folder name.
- **A network's real name:** the configuration's entry, else the stated name, else `<Compose name>_<key>`. An `Unreadable` name with no entry gives `real_name: None` and a `NetworkNameUnknown` warning.
- **A service's role:** the configuration's mapping when there is one, with `Declared`. Otherwise the project whose folder is the build context, and the binary whose name is the build target, with `Compose`. A project with no matching binary gives `BuiltFrom`. No build context and no mapping gives `External`.

**Tests:**

| Test | Asserts |
|---|---|
| `acme_gives_three_stacks` | `acme-infra`, `billing-api` and `ledger` |
| `ledger_name_comes_from_the_configuration` | `ledger`, not `ledger-api` |
| `billing_services_run_their_binaries_from_compose` | Both are `Runs` with `Compose` |
| `ledger_services_run_their_binaries_as_declared` | Both are `Runs` with `Declared` |
| `kafka_and_postgres_are_external` | `External` |
| `unstated_network_gets_the_compose_name_in_front` | `billing-api_default` |
| `configuration_network_name_wins` | Ledger's `backbone` is `acme-backbone`, with `from_configuration` |
| `unreadable_network_without_an_entry_warns` | One `NetworkNameUnknown`, and `real_name == None` |
| `rule_14_unknown_service_key` to `rule_16_project_not_in_the_stack` | One problem each, with that rule number |
| `rule_11_two_stacks_with_one_compose_name` | One problem, found here because the name can come from a file |
| `build_context_with_a_variable_needs_a_mapping` | A problem that names the service and says to map it under `services` |

**Commit:** `feat(index): resolve stacks, networks and services`

## Task 5: Build the workspace layer

**Files:** create `src/use_cases/index/workspace_layer.rs`.

**Produces:**

```rust
pub struct LayerInput<'a> {
    pub workspace_name: &'a str, pub config: &'a Config,
    pub manifests: &'a BTreeMap<ProjectId, Manifest>, pub stacks: &'a [ResolvedStack],
    pub checkouts: &'a BTreeMap<ProjectId, Checkout>, pub existing_entries: &'a BTreeSet<FileRef>,
}
pub fn build_workspace_layer(input: LayerInput<'_>) -> Result<WorkspaceLayer, Vec<ConfigProblem>>;
```

It builds every node and edge of the workspace layer as [domain-model.md](../domain-model.md) defines them, and:

- **Dependencies:** a discovered path that is a listed project gives a `DependsOn` with `Manifest`. A declared one gives `Declared`. For the same pair the declared one is kept. A discovered path that is no listed project gives a `DependencyPathNotAProject` warning.
- **Links:** `http` and `grpc` give `ConnectsTo`; `database` gives `ConnectsTo` with `Database`; a topic or queue gives the `Topic` or `Queue` node below the external service, once, and a `Publishes` or `Subscribes` edge. The source is the binary when the link names one, else the project.
- **Network check:** for a link whose source binary runs in a service, and whose target is a service, the two must share a network with a known real name. If they share none, a `LinkWithoutSharedNetwork` warning. A source that runs in no service is on the host and is not checked.
- **Entry files:** a `File` node and a `GrammarUnavailable` record for each binary's `entry`.
- **Rules 17 to 19** of the configuration guide.

**Tests:**

| Test | Asserts |
|---|---|
| `acme_layer_has_the_expected_counts` | The node and edge counts of the table in [domain-model.md](../domain-model.md#validating-an-implementation): 27 nodes, 53 edges |
| `acme_layer_equals_the_fixture` | The same node ids and edges as `fixtures::acme_workspace_layer()` |
| `acme_layer_is_valid` | `Graph::validate` returns nothing |
| `acme_layer_has_no_warnings` | An empty list |
| `declared_dependency_wins_over_discovered` | One `DependsOn` edge, `Declared`, with the note |
| `discover_false_uses_only_declared` | No `Manifest` edge |
| `dependency_path_that_is_no_project_warns` | One `DependencyPathNotAProject` whose subject is the project |
| `topic_is_created_once_for_publisher_and_subscriber` | One `Topic`, one `Publishes`, one `Subscribes` |
| `link_without_shared_network_warns` | Without ledger's network entry: one `LinkWithoutSharedNetwork` on ledger's `consumer` |
| `link_from_the_host_is_not_checked` | `web-app`'s link gives no warning |
| `rule_17_excluded_entry`, `rule_18_unknown_service`, `rule_18_ambiguous_service_needs_stack`, `rule_19_missing_entry` | One problem each |

**Commit:** `feat(index): build the workspace layer of the graph`

## Task 6: The use case, end to end

**Files:** create `src/use_cases/index/mod.rs`, `tests/fixtures/acme/`.

**Produces:**

```rust
pub struct IndexOptions { pub force: bool, pub project: Option<ProjectId> }
pub struct IndexSummary { pub files_read: u64, pub files_skipped: u64, pub nodes: u64, pub edges: u64, pub warnings: Vec<Warning>, pub failed_files: Vec<FileRef> }

pub struct IndexWorkspace<S, F, G> { /* store, files, git */ }
impl<S: GraphStore, F: Files, G: Git> IndexWorkspace<S, F, G> {
    pub async fn run(&self, root: &WorkspaceRoot, options: IndexOptions) -> Result<IndexSummary, IndexError>;
}
```

`run` loads the configuration, reads every manifest, compose file and checkout, builds the layer, runs `Graph::validate`, and writes with `begin_index`, `rebuild_workspace_layer` and `commit`. A problem or a violation returns `IndexError` before `begin_index`.

**Tests**, against `MemoryStore` and the fixture on disk:

| Test | Asserts |
|---|---|
| `acme_indexes_into_the_store` | `counts()` gives 27 nodes and 53 edges |
| `indexing_twice_changes_nothing` | The node ids and the edges are the same after a second run |
| `removing_a_link_removes_its_edge` | After deleting ledger's link and indexing again: no `Subscribes` edge, and the `Topic` remains because billing still publishes |
| `checkouts_are_stored_per_project` | Four rows, each with the fixture's branch |
| `invalid_configuration_writes_nothing` | With rule 19 broken, the store still holds the previous graph |

**Commit:** `feat(index): index the workspace layer`

## Done when

- The Acme Shop fixture indexes into SQLite with exactly the counts of the domain model, and passes every rule.
- Each of the three warnings has a test that raises it, and each of rules 14 to 19 a test that breaks it.
- Indexing twice gives the same graph.
