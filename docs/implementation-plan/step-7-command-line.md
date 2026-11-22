# Step 7: Command Line Implementation Plan

**Goal:** Give every use case a `workbench` command, with text output for people and `--json` for programs, and make the binary installable.

**Architecture:** Three thin layers. The command tree turns arguments into a typed command and nothing else. A renderer turns a result into text, as a pure function from a value to a string. The wiring in `main.rs` builds the adapters, runs the use case and maps its outcome to an exit code. No decision about the graph is made here: if a rule is in this layer, it is in the wrong place.

**Tech stack:** `clap` with `derive`, `serde_json`, `tokio`, and for tests `assert_cmd` and `tempfile`.

**Spec:** [usage-guide.md](../usage-guide.md). Capabilities U1 to U8, U11, X2, X3, X6, X8.

**Read first:** [00-overview.md](./00-overview.md).

## Global constraints

- Exit code `0` when the command did what was asked, `1` when it could not, `2` when the command line itself was wrong.
- `index` with warnings, or with files that failed to parse, exits `0`.
- Results go to standard output and nothing else does. Messages, warnings and progress go to standard error.
- `--json` prints the `Answer` of the use case as one JSON document, with the same field names the UTCP manual relies on.
- Every command takes `--workspace <dir>` and `-v`. Every command that prints a result takes `--json`.
- Text output has no colour when standard output is not a terminal.

## Review focus

- Output piped into a program that stops reading, such as `head`, ends quietly with exit code `0`, not with a panic message. Task 4.
- `--workspace` pointing at a folder with no `.workbench/` exits `1` and names the folder. Task 4.
- A query on a workspace that was never indexed exits `1` and says to run `workbench index`. Task 4.
- A path with spaces or non-ASCII letters is printed as it is. Task 2.
- `workbench` with no command prints the help and exits `2`. Task 1.

## The commands

| Command | Arguments and options | Use case |
|---|---|---|
| `init` | | `config::init` |
| `check` | | `config::load` |
| `index` | `--force`, `--project <id>` | `IndexWorkspace::run` |
| `status` | | `status` |
| `explore <question>` | `--max-files <n>`, `--project <id>` | `explore` |
| `node <node>` | `--no-source`; or `--file <project>:<path>` with `--offset <n>`, `--limit <n>` | `node`, `file` |
| `query <text>` | `--kind <kind>`, `--project <id>`, `--limit <n>` | `search` |
| `callers <node>` | `--depth <n>`, `--limit <n>` | `callers` |
| `callees <node>` | `--depth <n>`, `--limit <n>` | `callees` |
| `impact <node>` | `--depth <n>` | `impact` |
| `neighbors <node>` | `--depth <n>`, `--direction in\|out\|both`, `--edge <kind>` (repeatable) | `neighbors` |
| `files` | `--project <id>`, `--failed` | `files` |
| `deps` | | `deps` |
| `manual` | `--mode <name>` | step 8 |

## File structure

| File | Holds |
|---|---|
| `src/adapters/driving/cli/mod.rs` | `Cli`, `Command`, the global flags |
| `src/adapters/driving/cli/exit.rs` | `Outcome` and its exit code |
| `src/adapters/driving/cli/render/read.rs` | Text for `explore`, `node`, `query`, `callers`, `callees`, `impact`, `neighbors`, `files`, `deps` |
| `src/adapters/driving/cli/render/manage.rs` | Text for `init`, `check`, `index`, `status` |
| `src/adapters/driving/cli/run.rs` | From a `Command` to an `Outcome` |
| `src/main.rs` | Building the adapters and the runtime |
| `tests/cli.rs` | Tests that run the binary |
| `Formula/workbench.rb`, `.github/workflows/release.yml` | Installation |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 7A | 1 | C0 | `cli/mod.rs`, `cli/exit.rs` |
| 7B | 2 | C0 | `cli/render/read.rs` |
| 7C | 3 | C0, 2C | `cli/render/manage.rs` |
| 7D | 4 | 7A, 7B, 7C, 3B, 3C, 4G, 6F | `cli/run.rs`, `main.rs`, `tests/cli.rs` |
| 7E | 5 | 7D | `Formula/`, `release.yml` |

7A, 7B and 7C start together, by three developers, the day C0 is merged. The renderers need only the result types of C0: each is tested by building a result by hand and comparing the text. They do not wait for the queries. Only 7D waits for the rest, and it is wiring and tests.

## Task 1: The command tree and exit codes

**Files:** create `src/adapters/driving/cli/mod.rs`, `src/adapters/driving/cli/exit.rs`.

**Produces:**

```rust
#[derive(clap::Parser)]
pub struct Cli { pub workspace: Option<PathBuf>, pub verbose: bool, pub json: bool, pub command: Command }

#[derive(clap::Subcommand)]
pub enum Command { Init, Check, Index { force: bool, project: Option<String> }, Status, Explore { .. }, Node { .. }, Query { .. }, Callers { .. }, Callees { .. }, Impact { .. }, Neighbors { .. }, Files { .. }, Deps, Manual { mode: String } }

pub enum Outcome { Done, Failed(String), Usage(String) }
impl Outcome { pub fn exit_code(&self) -> u8; }      // 0, 1, 2
```

The global flags are marked `global = true`, so they may come before or after the command. `Manual`'s `mode` defaults to `developer-support`.

**Tests**, with `Cli::try_parse_from`:

| Test | Asserts |
|---|---|
| `every_command_parses` | One line of arguments for each of the fourteen commands gives the matching variant |
| `workspace_flag_may_follow_the_command` | `status --workspace x` and `--workspace x status` give the same value |
| `neighbors_direction_accepts_only_three_values` | `--direction up` is an error |
| `edge_may_be_given_more_than_once` | Two `--edge` values give a list of two |
| `node_takes_a_node_or_a_file_not_both` | Both together is an error; neither is an error |
| `unknown_flag_is_a_usage_error` | The error's exit code is `2` |
| `no_command_is_a_usage_error` | Exit code `2` |
| `mode_defaults_to_developer_support` | `manual` alone gives that mode |
| `exit_codes_are_0_1_and_2` | For `Done`, `Failed` and `Usage` |

**Commit:** `feat(cli): the command tree and exit codes`

## Task 2: Text for the read commands

**Files:** create `src/adapters/driving/cli/render/read.rs`.

**Produces:** one function for each result type, all of the same shape:

```rust
pub fn search(answer: &Answer<SearchResult>) -> String;
pub fn node(answer: &Answer<NodeView>) -> String;
pub fn file(answer: &Answer<FileView>) -> String;
pub fn calls(answer: &Answer<CallList>) -> String;
pub fn neighbors(answer: &Answer<NeighborsResult>) -> String;
pub fn impact(answer: &Answer<ImpactResult>) -> String;
pub fn explore(answer: &Answer<ExploreResult>) -> String;
pub fn files(answer: &Answer<FileList>) -> String;
pub fn deps(answer: &Answer<DependencyList>) -> String;
pub fn footer(freshness: &Freshness, truncated: Option<&str>) -> String;
```

Every function ends with `footer`. A location is printed as `<scope>:<qualified name>  <path>:<line>`. Source is printed with its line numbers in front. `deps` prints the layout of the [usage guide](../usage-guide.md#workbench-deps).

**Tests**, each building a result by hand:

| Test | Asserts |
|---|---|
| `location_line_has_scope_name_path_and_line` | `shared-api:shared_api.models.Invoice  src/shared_api/models.py:3` |
| `source_lines_are_numbered_from_the_span` | The first line starts with the span's start line |
| `changed_source_block_is_marked` | The block's heading says the file changed since the last index |
| `deps_line_matches_the_usage_guide` | `billing-api -> shared-api    build   manifest (pyproject.toml)` |
| `impact_is_grouped_by_project_with_provenance` | A heading for each project, and each step shows its provenance |
| `explore_has_three_parts_in_order` | Source, then call flow, then blast radius |
| `empty_result_says_so` | "No matches", not an empty string |
| `footer_names_changed_files_and_says_to_index` | With `changed_files == 3`: the count, and `workbench index` |
| `footer_shows_what_was_left_out` | The `truncated` text |
| `path_with_spaces_and_accents_is_printed_as_is` | Unchanged |

**Commit:** `feat(cli): text output of the read commands`

## Task 3: Text for `init`, `check`, `index` and `status`

**Files:** create `src/adapters/driving/cli/render/manage.rs`.

**Produces:**

```rust
pub fn init(report: &InitReport) -> String;
pub fn problems(problems: &[ConfigProblem]) -> String;      // for `check`, and for `index` when it stops
pub fn check_ok(config: &Config) -> String;
pub fn index(summary: &IndexSummary) -> String;
pub fn status(answer: &Answer<StatusReport>) -> String;
```

`status` prints the layout of the [usage guide](../usage-guide.md#workbench-status), with one line per project giving its branch and commit. A warning is printed as its subject, then its message.

**Tests:**

| Test | Asserts |
|---|---|
| `init_lists_written_and_kept_files` | Two groups, each path once |
| `each_problem_shows_its_field_and_message` | `projects[0].links[0].project: no project named "ledger"` |
| `check_ok_counts_projects_and_stacks` | "4 projects, 1 shared stack" |
| `check_ok_lists_reserved_sections_under_verbose` | One line per notice |
| `index_summary_has_all_six_numbers` | Files read, files skipped, nodes, edges, warnings, failed files |
| `status_matches_the_usage_guide_layout` | The five labels, in order |
| `status_shows_a_branch_per_project` | `billing-api  release-2.4  9f2c41d` |
| `status_of_an_empty_store_says_to_index` | "Not indexed yet. Run `workbench index`." |

**Commit:** `feat(cli): text output of init, check, index and status`

## Task 4: Wiring, and tests that run the binary

**Files:** create `src/adapters/driving/cli/run.rs`, `tests/cli.rs`; modify `src/main.rs`.

**Produces:**

```rust
pub async fn run(cli: Cli, env: &Env) -> (Outcome, Output);
pub struct Output { pub stdout: String, pub stderr: String }
pub struct Env { pub cwd: PathBuf, pub workspace_var: Option<OsString>, pub stdout_is_terminal: bool }
```

`run` finds the workspace, loads the configuration, opens the store read-only for a query and for writing only in `index`, calls the use case, and renders. With `--json` it prints `serde_json::to_string_pretty` of the answer. `main` builds a `tokio` runtime, calls `run`, writes both streams and exits with the outcome's code. A broken pipe on standard output ends the program with code `0`.

`StoreError::NotIndexed`, `IndexRunning` and `WrongFormat` each become a `Failed` with the sentence the [usage guide](../usage-guide.md#troubleshooting) gives.

**Tests**, in `tests/cli.rs`, running the binary on a copy of `tests/fixtures/acme/` in a temp folder:

| Test | Asserts |
|---|---|
| `quick_start_runs_from_init_to_impact` | `init` in an empty folder, then with the Acme configuration: `check`, `index`, `status` and `impact shared-api:shared_api.models.Invoice` each exit `0` |
| `impact_names_all_four_projects` | Standard output holds the four project ids |
| `json_output_parses_and_has_freshness` | `impact --json` is valid JSON with `result`, `freshness` and `truncated` |
| `results_go_to_stdout_and_messages_to_stderr` | `index` writes its summary to standard error, and nothing to standard output |
| `invalid_configuration_exits_1_and_lists_every_problem` | Exit code `1`, and both problems on standard error |
| `unknown_flag_exits_2` | Exit code `2` |
| `no_workspace_exits_1_and_names_the_flag` | The message holds `--workspace` |
| `query_before_index_says_to_index` | Exit code `1`, and `workbench index` in the message |
| `init_twice_refuses_the_second_time` | Exit code `1`, and the configuration is unchanged |
| `ambiguous_node_lists_the_candidates` | `node billing-api:api` exits `1` and lists both nodes |
| `closed_pipe_exits_quietly` | `files` piped into a reader that closes at once: exit code `0`, and no panic text |

**Commit:** `feat(cli): wire the commands and test the binary`

## Task 5: Installation

**Files:** create `Formula/workbench.rb`, `.github/workflows/release.yml`.

- [ ] Check that `cargo install --path . --locked` puts `workbench` on the path and that `workbench --version` prints the version of `Cargo.toml`.
- [ ] Write a release workflow that builds the binary for macOS on Apple silicon and Intel, and for Linux on x86-64 and ARM, on a version tag, and attaches the four archives with their checksums to the release.
- [ ] Write the Homebrew formula: it downloads the archive for the platform, checks its checksum and installs the one binary.
- [ ] Add a test to the formula that runs `workbench --version`.
- [ ] Commit: `build: release archives and a Homebrew formula`

## Done when

- The quick start of the usage guide runs as written on the Acme Shop fixture.
- Every command of the table has a test that runs the binary.
- `cargo install --path .` and `brew install` each give a working `workbench`.

## Left open

- **Where the Homebrew formula lives.** A formula in this repository needs a tap, and `brew install workbench` without one needs the formula accepted into Homebrew's own collection. The usage guide already says the name may differ.
