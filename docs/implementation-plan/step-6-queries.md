# Step 6: Queries Implementation Plan

**Goal:** Answer every question the command line and the UTCP manual can ask: `search`, `node`, `callers`, `callees`, `neighbors`, `impact`, `explore`, `files`, `deps` and `status`.

**Architecture:** One use case per question. Each takes the store and the files through their ports, and returns an `Answer` holding a plain result. No use case prints anything or knows who called it, which is what makes the command line and the UTCP manual give the same answer. Walks are done here, one step at a time: the store is only ever asked for the edges of a set of nodes.

**Tech stack:** `serde` for the result types. No new crate.

**Spec:** [usage-guide.md](../usage-guide.md#asking-the-graph), [graph-model.md](../graph-model.md#walking-the-graph), [storage-model.md](../storage-model.md#how-the-store-is-read). Capabilities Q1 to Q7, Q10 to Q14, and the query side of I20 and I21.

**Read first:** [00-overview.md](./00-overview.md).

## Global constraints

- A query never writes to the store.
- Every answer carries its freshness: when the graph was indexed, and how many files have changed since.
- Every answer has a budget. An answer that was cut short says so in `truncated`, and says what was left out.
- Source is read from the file through a node's span. When the file's hash differs from its record, the source block is marked as changed.
- Results are ordered, so the same question on the same graph gives the same answer.
- Every use case is tested on `MemoryStore` seeded with `fixtures::acme()`. None needs SQLite or an indexer.

## Review focus

- A question that matches nothing gives an empty result that says so, not an error. Tasks 3 and 8.
- A node whose file is gone from disk since the index gives its details, a source block marked as missing, and no error. Task 3.
- A span that ends past the end of a changed file returns the lines that exist. Task 3.
- A function that calls itself, or two that call each other, do not make a walk loop. Each node is reached once. Task 5.
- A node with thousands of callers returns the first `limit`, in order, with `truncated` giving the total. Task 6.

## Budgets and defaults

| Query | Option | Default | Range |
|---|---|---|---|
| `search` | `limit` | 10 | 1 to 100 |
| `callers`, `callees` | `limit` | 20 | 1 to 100 |
| `callers`, `callees` | `depth` | 1 | 1 to 10 |
| `neighbors` | `depth` | 1 | 1 to 10 |
| `impact` | `depth`, the code part only | 2 | 1 to 10 |
| `node --file` | `limit`, in lines | 2,000 | 1 to 2,000 |
| `explore` | `max_files` | 8 | 1 to 20 |
| `explore` | characters of source in all | 24,000 | fixed |
| `explore` | characters of source per file | 6,500 | fixed |
| any walk | nodes visited | 2,000 | fixed |

A value outside its range is brought to the nearest end of the range, not refused. The `explore` budgets are those of the reference tool for a large project.

## File structure

| File | Holds |
|---|---|
| `src/use_cases/query/node_ref.rs` | Naming a node |
| `src/use_cases/query/freshness.rs` | Freshness |
| `src/use_cases/query/budget.rs` | Clamping options, and counting what a budget left out |
| `src/use_cases/query/source.rs` | Reading a node's source through its span |
| `src/use_cases/query/search.rs`, `node.rs` | `search`, `node` |
| `src/use_cases/query/files.rs`, `deps.rs`, `status.rs` | `files`, `deps`, `status` |
| `src/use_cases/query/walk.rs` | The walk |
| `src/use_cases/query/calls.rs`, `neighbors.rs` | `callers`, `callees`, `neighbors` |
| `src/use_cases/query/impact.rs` | `impact` |
| `src/use_cases/query/explore.rs` | `explore` |
| `src/use_cases/query/node_details.rs` | What `node` shows by kind, from the results of stage 2 |
| `src/use_cases/query/tests.rs` | The tests to run for a change |
| `src/use_cases/query/contracts.rs` | API and event contracts |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 6A | 1, 2 | C0 | `node_ref.rs`, `freshness.rs`, `budget.rs`, `source.rs` |
| 6B | 3 | 6A | `search.rs`, `node.rs` |
| 6C | 4 | 6A | `files.rs`, `deps.rs`, `status.rs` |
| 6D | 5, 6 | 6A | `walk.rs`, `calls.rs`, `neighbors.rs` |
| 6E | 7 | 6D | `impact.rs` |
| 6F | 8 | 6B, 6E | `explore.rs` |
| 6G | 9 | 6B, 6C, 6D | `node_details.rs`; one call each added to `node.rs`, `search.rs`, `calls.rs`, `files.rs` |
| 6H | 10 | 6E | `impact.rs` |
| 6I | 11 | 6H | `tests.rs` |
| 6J | 12 | 6H | `contracts.rs`; the contract sections added to `impact.rs` |

After 6A, three developers take 6B, 6C and 6D at once. Tasks 9 to 12 then bring the queries up to the results of stage 2 ([python-parsing.md](../python-parsing.md)): 6G once 6B, 6C and 6D are merged, 6H once 6E is, and 6I and 6J side by side after 6H. This whole step runs beside steps 3, 4 and 5: it needs only C0, because it is tested on the fixture in memory.

## Task 1: Name a node

**Files:** create `src/use_cases/query/node_ref.rs`.

**Produces:**

```rust
pub enum NodeRef { Id(NodeId), Named { scope: Option<String>, qualified_name: String } }
impl NodeRef { pub fn parse(text: &str) -> Result<NodeRef, QueryError>; }

pub async fn find_node<S: GraphStore>(store: &S, node: &NodeRef) -> Result<Node, QueryError>;
```

Sixteen hex characters are an id. Otherwise the text before the first `:` is a scope name, a project id or a Compose name, and the rest is the qualified name. `QueryError::Ambiguous(Vec<Location>)` lists every match; `QueryError::NotFound` names what was asked.

**Tests:**

| Test | Asserts |
|---|---|
| `sixteen_hex_characters_are_an_id` | `NodeRef::Id` |
| `scope_and_name_are_split_at_the_first_colon` | `shared-api:shared_api.models.Invoice` gives scope `shared-api` |
| `name_without_scope_is_allowed` | `scope == None` |
| `invoice_is_found_by_scope_and_name` | Class `Invoice` |
| `api_in_billing_api_is_ambiguous` | `billing-api:api` matches Binary `api` of the project and Service `api` of the stack: `Ambiguous` with two locations |
| `unknown_name_is_not_found` | `NotFound` |

**Commit:** `feat(query): name a node`

## Task 2: Freshness, budgets and source

**Files:** create `src/use_cases/query/freshness.rs`, `budget.rs`, `source.rs`.

**Produces:**

```rust
pub async fn freshness<S: GraphStore, F: Files, G: Git>(store: &S, files: &F, git: &G, roots: &ProjectRoots) -> Result<Freshness, QueryError>;
pub fn clamp(value: Option<u32>, default: u32, min: u32, max: u32) -> u32;

pub struct SourceBlock { pub file: FileRef, pub start_line: u32, pub lines: Vec<String>, pub state: SourceState }
pub enum SourceState { Current, ChangedSinceIndex, Missing }
pub async fn read_source<S: GraphStore, F: Files>(store: &S, files: &F, roots: &ProjectRoots, node: &Node) -> Result<Option<SourceBlock>, QueryError>;
```

`ProjectRoots` maps a `ProjectId` to its folder on disk, built from the configuration. `freshness` works in two steps, so that an answer on a large workspace reads almost nothing:

1. **Each project's commit.** Read through the `Git` port and compare with the stored checkout. A project on another commit is listed in `moved_projects`. This reads one or two small files per project.
2. **Each file's size and mtime.** `stat` every recorded file. A file whose size and mtime equal its record is unchanged and is not read. A file where either differs is hashed: it counts as changed only when its hash differs too. A file that is gone counts as changed. `read_source` returns `None` for a declared node.

**Tests:**

| Test | Asserts |
|---|---|
| `nothing_changed_gives_zero` | `changed_files == 0`, `moved_projects` empty, and `indexed_at` from the store |
| `unchanged_stat_is_not_hashed` | With every size and mtime equal, a counting `Files` sees no `read` |
| `touched_but_unchanged_file_is_not_counted` | A newer mtime and the same bytes: `changed_files == 0`, and the file was read once |
| `moved_commit_is_reported` | A project whose checkout moved to another commit is in `moved_projects` with both commits |
| `edited_file_is_counted` | `1` |
| `deleted_file_is_counted` | `1` |
| `clamp_brings_a_value_into_range` | `clamp(Some(500), 10, 1, 100) == 100`; `clamp(None, 10, 1, 100) == 10`; `clamp(Some(0), 10, 1, 100) == 1` |
| `source_is_the_lines_of_the_span` | Lines 3 to 5 of a file, as written |
| `changed_file_is_marked` | `ChangedSinceIndex` |
| `missing_file_is_marked` | `Missing`, and no lines |
| `span_past_the_end_returns_what_exists` | The lines up to the end of the file |
| `declared_node_has_no_source` | `None` for a `Project` |

**Commit:** `feat(query): freshness, budgets and reading source`

## Task 3: `search` and `node`

**Files:** create `src/use_cases/query/search.rs`, `node.rs`.

**Produces:**

```rust
pub async fn search<S, F>(ctx: &QueryContext<S, F>, text: &str, filter: NodeFilter, limit: Option<u32>) -> Result<Answer<SearchResult>, QueryError>;
pub async fn node<S, F>(ctx: &QueryContext<S, F>, node: &NodeRef, with_source: bool) -> Result<Answer<NodeView>, QueryError>;
pub async fn file<S, F>(ctx: &QueryContext<S, F>, file: &FileRef, offset: Option<u32>, limit: Option<u32>) -> Result<Answer<FileView>, QueryError>;

pub struct QueryContext<S, F> { pub store: S, pub files: F, pub roots: ProjectRoots }
```

`search` orders its matches: an exact name first, then a name that starts with the text, then the rest, each group by qualified name.

**Tests:**

| Test | Asserts |
|---|---|
| `search_finds_invoice` | One match, Class `Invoice` in `shared-api` |
| `search_filters_by_kind_and_project` | `api` with kind `Service` gives two matches; adding project `billing-api` gives none, since a service has a stack scope |
| `exact_name_comes_first` | For `api`, the nodes named `api` precede `api.py` |
| `search_with_no_match_is_empty_not_an_error` | `matches` is empty |
| `search_over_the_limit_is_truncated` | `truncated` gives the total |
| `node_view_has_source_and_direct_calls` | `send_invoice` has its lines and one callee, `Invoice` |
| `node_view_without_source` | `with_source == false` leaves the block out |
| `file_view_lists_its_nodes` | `worker.py` holds `send_invoice` |
| `file_view_respects_offset_and_limit` | Lines 2 and 3 of the file for `offset 2, limit 2` |

**Commit:** `feat(query): search and node`

## Task 4: `files`, `deps` and `status`

**Files:** create `src/use_cases/query/files.rs`, `deps.rs`, `status.rs`.

**Produces:**

```rust
pub async fn files<S, F>(ctx: &QueryContext<S, F>, filter: FileFilter) -> Result<Answer<FileList>, QueryError>;
pub async fn deps<S, F>(ctx: &QueryContext<S, F>) -> Result<Answer<DependencyList>, QueryError>;
pub async fn status<S, F>(ctx: &QueryContext<S, F>) -> Result<Answer<StatusReport>, QueryError>;
```

**Tests:**

| Test | Asserts |
|---|---|
| `files_are_grouped_by_project_and_sorted` | The order of projects and paths |
| `failed_filter_gives_only_failed_files` | One file, with its message |
| `deps_lists_both_dependencies_on_shared_api` | `billing-api -> shared-api` and `ledger-api -> shared-api`, each `Build` and `Manifest` |
| `deps_leaves_runtime_links_out` | No `ConnectsTo`, `Publishes` or `Subscribes` |
| `status_reports_counts_checkouts_and_warnings` | The counts of the fixture, four checkouts, and the warnings of the store |
| `status_on_an_empty_store_says_not_indexed` | `indexed_at == None`, and no error |

**Commit:** `feat(query): files, deps and status`

## Task 5: The walk

**Files:** create `src/use_cases/query/walk.rs`.

**Produces:**

```rust
pub struct Step { pub direction: Direction, pub kinds: Vec<EdgeKindName> }
pub struct Reached { pub node: NodeId, pub depth: u32, pub via: Edge }
pub struct WalkResult { pub reached: Vec<Reached>, pub truncated: bool }

pub async fn walk<S: GraphStore>(store: &S, start: &[NodeId], step: &Step, max_depth: u32, max_nodes: u32) -> Result<WalkResult, QueryError>;
```

Breadth first. One call to `store.edges` for each depth, with every node of that depth. A node is reached once, at its smallest depth. The start nodes are never in `reached`.

**Tests:**

| Test | Asserts |
|---|---|
| `one_step_out` | From `send_invoice` over `Calls` and `Instantiates`: `Invoice` at depth 1 |
| `two_steps_in` | A caller of a caller is at depth 2 |
| `node_reached_twice_is_listed_once_at_the_smaller_depth` | One entry, depth 1 |
| `recursion_does_not_loop` | A function that calls itself is not in its own `reached` |
| `mutual_recursion_ends` | The walk returns |
| `budget_cuts_the_walk_short` | With `max_nodes = 1`: one node and `truncated == true` |
| `store_is_asked_once_per_depth` | A counting store sees two calls for depth 2 |

**Commit:** `feat(query): walk the graph step by step`

## Task 6: `callers`, `callees` and `neighbors`

**Files:** create `src/use_cases/query/calls.rs`, `neighbors.rs`.

**Produces:**

```rust
pub async fn callers<S, F>(ctx: &QueryContext<S, F>, node: &NodeRef, depth: Option<u32>, limit: Option<u32>) -> Result<Answer<CallList>, QueryError>;
pub async fn callees<S, F>(ctx: &QueryContext<S, F>, node: &NodeRef, depth: Option<u32>, limit: Option<u32>) -> Result<Answer<CallList>, QueryError>;
pub async fn neighbors<S, F>(ctx: &QueryContext<S, F>, node: &NodeRef, depth: Option<u32>, direction: Direction, kinds: Vec<EdgeKindName>) -> Result<Answer<NeighborsResult>, QueryError>;
```

`callers` and `callees` walk `Calls` and `Instantiates`. `neighbors` walks the kinds it is given, or every kind but `Contains` when given none.

**Tests:**

| Test | Asserts |
|---|---|
| `callers_of_invoice_cross_projects` | `send_invoice` of `billing-api`, with the site of the call |
| `callees_of_send_invoice` | `Invoice` |
| `callers_over_the_limit_are_truncated` | The first `limit` in order, and the total |
| `neighbors_of_a_service_show_its_network` | Service `api` of stack `billing-api` reaches Network `acme-backbone` over `Joins` |
| `neighbors_filtered_by_kind` | With `Publishes` only, Binary `worker` reaches the topic and nothing else |
| `neighbors_inwards` | The topic, inwards over `Subscribes`, reaches Binary `consumer` |

**Commit:** `feat(query): callers, callees and neighbors`

## Task 7: `impact`

**Files:** create `src/use_cases/query/impact.rs`.

**Produces:**

```rust
pub async fn impact<S, F>(ctx: &QueryContext<S, F>, node: &NodeRef, depth: Option<u32>) -> Result<Answer<ImpactResult>, QueryError>;
```

It works in two parts.

**Through the code.** Walk inwards from the node over `Calls`, `Imports`, `Extends`, `Implements`, `References`, `Instantiates`, `Overrides`, `Decorates`, `TypeOf` and `Returns`, to `depth`.

**Through what runs.** For the node and every node the first part reached:

1. Go up `Contains` to its `File`.
2. Find the binaries that include the file: the one whose `EntryPoint` is the file, or, when it is no entry, every binary of the file's project.
3. For each binary: the services that `Runs` it; the topics and queues it `Publishes`, and from each the binaries and projects that `Subscribes`; the binaries and projects that `ConnectsTo` one of its services or its project.

Each entry of the result holds the chain of edges that led to it, so the provenance of every step can be shown. Entries are grouped by project, and a project holds each node once.

**Tests:**

| Test | Asserts |
|---|---|
| `invoice_reaches_all_four_projects` | The result has `shared-api`, `billing-api`, `ledger-api` and `web-app` |
| `the_six_steps_of_the_graph_model_walk_are_present` | The chain to Binary `consumer` is `Imports`, `EntryPoint`, `Publishes`, `Subscribes`; the chain to Binary `admin` ends in `Runs`, `ConnectsTo` |
| `each_step_carries_its_provenance` | `Imports` is `TreeSitter`; `Publishes` is `Declared` |
| `depth_limits_only_the_code_part` | With `depth = 1`, a caller of a caller is absent, and `consumer` is still present |
| `file_that_is_no_entry_reaches_every_binary_of_its_project` | A helper file in `billing-api` reaches both `api` and `worker` |
| `node_with_no_dependents_gives_only_its_own_project` | One project, and no error |

**Commit:** `feat(query): impact across projects`

## Task 8: `explore`

**Files:** create `src/use_cases/query/explore.rs`.

**Produces:**

```rust
pub async fn explore<S, F>(ctx: &QueryContext<S, F>, question: &str, project: Option<ProjectId>, max_files: Option<u32>) -> Result<Answer<ExploreResult>, QueryError>;
```

1. **Find the entry nodes.** Take the words of the question that look like names: anything in backticks, anything with `_`, `.` or a capital inside it, and every other word of four letters or more. Search each. A node whose name equals a word exactly is an exact match and ranks first.
2. **Connect them.** Walk one step out from the entry nodes over `Calls`, `Instantiates`, `Imports`, `Publishes`, `Subscribes` and `ConnectsTo`, and keep each edge whose two ends are both entry nodes or reached from one. That is the flow.
3. **Read the source.** Take the nodes by rank: exact matches, then other entry nodes, then nodes the flow added. Read each one's source until `max_files` files, the budget per file or the budget in all is reached.
4. **Summarise the blast radius.** Run `impact` on the five highest-ranked nodes, and keep from each the projects and binaries reached and the first four caller files, as locations.

**Tests:**

| Test | Asserts |
|---|---|
| `question_naming_invoice_returns_its_source` | A source block for Class `Invoice`, lines as written |
| `flow_runs_from_worker_to_consumer_through_the_topic` | For "how does `send_invoice` reach the ledger consumer": the flow holds `Publishes` and `Subscribes` on `kafka/invoice.created` |
| `blast_radius_names_all_four_projects` | For a question about `Invoice` |
| `exact_match_ranks_before_a_partial_one` | `Invoice` precedes `invoice_total` in `sources` |
| `project_option_limits_the_entry_nodes_only` | With `project = billing-api`, the entry nodes are billing's, and the flow still reaches `ledger-api` |
| `max_files_limits_the_source` | With `1`: one file, and `truncated` names the files left out |
| `question_that_matches_nothing_says_so` | Empty `sources`, and `truncated == None` |
| `changed_file_is_marked_in_its_block` | `ChangedSinceIndex` |

**Commit:** `feat(query): explore`

## Task 9: What stage 2 adds to `node`, `search`, `callers` and `files`

**Files:** create `src/use_cases/query/node_details.rs`; modify `node.rs`, `search.rs`, `calls.rs`, `files.rs`.

**Produces:**

```rust
pub enum NodeDetails {
    Code { reached_by: Vec<Root>, inferred: Option<InferredType> },
    Function { reached_by: Vec<Root>, inferred_return: Option<InferredType>, http_calls: Vec<HttpCall>, messages: Vec<MessageUse> },
    Route { reached_by: Vec<Root>, paths: Vec<RoutePath>, callers: Vec<Location> },
    Binary { framework: Framework, framework_source: FrameworkSource, app: Option<String>, commands: Vec<Location>, reaches: ReachCount },
    Command { options: Vec<String>, handler: Option<Location>, services: Vec<Location> },
    Topic { senders: Vec<MessageUse>, handlers: Vec<MessageUse>, payloads: Vec<Location> },
    Project { language: Language },
    None,
}
pub enum HttpCall { Matched { route: Location, path: String, site: Site }, Unmatched { path: String, site: Site, candidates: Vec<Location> } }
pub async fn node_details<S: GraphStore>(store: &S, node: &Node) -> Result<NodeDetails, QueryError>;
```

`NodeView` gains `details: NodeDetails`. Each `Call` of `CallList` gains `resolved_by: Option<Resolution>`. `search` also matches the full paths of route paths. `files` gains `unreached: bool`, served by `unreached_files`.

**Tests**, on `fixtures::acme()`:

| Test | Asserts |
|---|---|
| `route_shows_full_paths_and_binaries` | `GET /{invoice_id}`: one path, `GET /v1/invoices/{invoice_id}`, complete, served by billing's `api` |
| `route_shows_its_http_callers` | Ledger's `fetch_invoice` and `test_get_invoice` |
| `parameter_shows_its_inferred_type` | `r` of `process`: `InvoiceRepo`, evidence 2 |
| `code_node_shows_reached_by` | `services.py`: `worker` and the test file `test_services.py` |
| `function_shows_http_calls_and_messages` | `fetch_invoice` has one matched call; `send_invoice` sends to `kafka/invoice.created` |
| `unmatched_http_call_lists_its_candidates` | A call with two candidate routes, added to the fixture, shows both |
| `binary_shows_framework_commands_and_reach` | Billing's `api`: `Fastapi`, `billing.api.app`, source `Dockerfile`. Ledger's `consumer`: three commands |
| `command_shows_options_handler_and_services` | `ledger-consumer run`: handler `run_consume`, service `consumer`. `ledger-consumer replay`: option `--from`, no service |
| `topic_shows_senders_handlers_and_payloads` | `send_invoice`, `run_consume`, payload `Invoice` |
| `callers_show_how_each_call_was_resolved` | The caller of `InvoiceRepo.save` is `process`, with `resolved_by: Flow` |
| `search_finds_a_route_by_its_full_path` | `/v1/invoices` finds `GET /{invoice_id}` |
| `files_unreached_lists_a_file_no_root_reaches` | A file added to the fixture that nothing imports is listed; `services.py` is not |

**Commit:** `feat(query): show the results of stage 2`

## Task 10: `impact` over the results of stage 2

**Files:** modify `src/use_cases/query/impact.rs`.

Task 7 walks code and declared links. This task widens both parts.

**Through the code**, also inwards over `Handles` (a handler to its routes and commands), `Mounts` (a route or router to what mounts it), `Injects` (a provider to the routes, providers, tests and fixtures that use it) and `Requests` (a route to the code that calls it over HTTP, in any project). Each step keeps its edge, so its provenance and `resolved_by` can be shown. A step over an `Imports` edge with `type_only` is labelled type-only.

**Through what runs:**

1. The binaries that run a node are its reach records ([python-parsing.md](../python-parsing.md#stage-2e-reach)). A node with no reach record falls back to every binary of its project, and the entry says so.
2. A binary's services: those that `Runs` it. When the walk reached the binary through a `Command`, only the services that `Invokes` that command, and those that run the binary with no command words.
3. Across a topic or queue: a node with a `Sends` edge reaches the nodes with a `Receives` edge into the same topic or queue, in any project. The step is labelled as crossing it.
4. Then the declared links, as in task 7.

Test roots that reach an affected node are listed under `tests`, by file.

**Tests:**

| Test | Asserts |
|---|---|
| `handler_change_names_its_route_and_only_the_api_service` | `get_invoice`: the route, Binary `api`, Service `api` of stack `billing-api`; not `worker` |
| `route_reaches_http_callers_in_other_projects` | `get_invoice` reaches ledger's `fetch_invoice` through `Handles` and `Requests`, `resolved_by: RouteMatch` |
| `provider_reaches_the_routes_that_inject_it` | `get_db` reaches `GET /{invoice_id}` |
| `reach_narrows_the_binaries` | `services.py` reaches `worker` and not `api`; no fallback label |
| `unreached_node_falls_back_to_its_project_and_says_so` | A function no root reaches lists both billing binaries, labelled as a fallback |
| `command_handler_names_only_the_services_that_invoke_it` | `run_replay`: command `ledger-consumer replay`, no service. `run_consume`: Service `consumer` |
| `send_crosses_the_topic_to_its_handlers` | `send_invoice` reaches ledger's `run_consume`, the step labelled as crossing `kafka/invoice.created` |
| `type_only_step_is_labelled` | An import under `if TYPE_CHECKING:` added to the fixture gives a type-only step |
| `each_step_shows_provenance_and_resolved_by` | `Requests` shows `TreeSitter` and `RouteMatch` |

**Commit:** `feat(query): impact over the results of stage 2`

## Task 11: The tests to run for a change

**Files:** create `src/use_cases/query/tests.rs`.

**Produces:**

```rust
pub enum TestsFor { Nodes(Vec<NodeRef>), File(FileRef) }
pub struct TestCase { pub id: String, pub location: Location }    // id: tests/test_api.py::TestInvoices::test_get
pub struct TestList { pub tests: Vec<TestCase> }
pub async fn tests_to_run<S, F>(ctx: &QueryContext<S, F>, of: &TestsFor) -> Result<Answer<TestList>, QueryError>;
```

As [python-parsing.md](../python-parsing.md#tests-to-run-for-a-change) sets out: reach narrows the search to the test files whose root reaches a node. Inside them, a walk backwards over the edges reach follows stops at each test function. `--file` takes every node of the file. Tests are sorted by id.

**Tests:**

| Test | Asserts |
|---|---|
| `handler_change_lists_test_get_invoice` | `tests/test_api.py::test_get_invoice`, found through `Requests` from `TestClient` |
| `fixture_change_lists_the_tests_that_use_it` | The fixture `repo` lists `test_get_invoice`, through `Injects` |
| `services_change_lists_the_tests_of_test_services` | The tests in `tests/test_services.py` |
| `method_test_id_names_its_class` | A test method in `class TestInvoices` gives `file::TestInvoices::test_x` |
| `file_option_covers_every_node_of_the_file` | The same list as giving each node |
| `node_no_test_reaches_gives_an_empty_list` | Empty, and no error |

**Commit:** `feat(query): the tests to run for a change`

## Task 12: API and event contracts

**Files:** create `src/use_cases/query/contracts.rs`; modify `impact.rs` to add the two sections.

**Produces:**

```rust
pub struct ApiContract { pub class: Location, pub routes: Vec<ContractRoute> }
pub struct ContractRoute { pub route: Location, pub paths: Vec<RoutePath>, pub side: Side, pub via_fields: Vec<String>, pub callers: Vec<Consumer>, pub tests: Vec<TestCase> }
pub enum Side { Request, Response }
pub enum Consumer { Code(Location), DeclaredLink { from: Location } }   // a declared link has no call site
pub struct EventContract { pub class: Location, pub channels: Vec<ContractChannel> }
pub struct ContractChannel { pub topic: Location, pub broker: Location, pub senders: Vec<(Location, Location)>, pub handlers: Vec<(Location, Location)>, pub mismatch: bool }
```

`ImpactResult` gains `api_contract: Option<ApiContract>` and `event_contract: Option<EventContract>`, filled when the node is a class, or a field of one, used by a route or carried as a payload. Nesting through fields is followed up to 5 levels, as [python-parsing.md](../python-parsing.md#api-contracts) sets out.

**Tests:**

| Test | Asserts |
|---|---|
| `invoice_api_contract` | `GET /v1/invoices/{invoice_id}`, response, served by `api`. Called by ledger's `fetch_invoice`, by web-app's `admin` as a declared link, tested by `test_get_invoice` |
| `nested_model_is_followed_up_to_five_levels` | `Invoice` inside `InvoiceList.items` gives the route of `InvoiceList`, with `via_fields == ["items"]`. A sixth level is not followed |
| `invoice_event_contract` | `kafka/invoice.created` on `kafka`, sent by `send_invoice`, handled by `run_consume`, both with `Invoice` |
| `sender_and_handler_disagreeing_are_flagged` | A handler reading another class gives `mismatch == true` |
| `class_used_by_no_route_has_no_contract` | Both sections are `None` |

**Commit:** `feat(query): API and event contracts in impact`

## Done when

- Each of the ten queries has a use case that returns an `Answer`.
- `impact` on `Invoice` gives the six steps of the walk in the graph model, its API contract and its event contract.
- `impact` on billing's `get_invoice` names Service `api` and not `worker`, and its tests to run are `tests/test_api.py::test_get_invoice`.
- One `explore` about `Invoice` returns its source, the flow from billing's worker to ledger's consumer, and all four projects.

## Left open

- **What freshness costs.** Settled ([#17](https://github.com/Revanthshalon/semantic-workbench/issues/17)): task 2 compares each project's commit, then each file's size and mtime, and hashes only the files whose size or mtime changed. Measure it on a large workspace in this step all the same.
