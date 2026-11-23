# Step 8: UTCP Manual Implementation Plan

**Goal:** Print a UTCP manual that describes the queries to an AI tool, in the `developer-support` mode, so the tool calls `workbench` directly.

**Architecture:** The manual is the second door to the same use cases the command line calls, and it is only data. A tool is a name, a description, a schema for its arguments and a call template: the `workbench` command to run, with `--json` and the workspace path. `workbench manual` builds the document from one table of tools and prints it. No process stays running, and the manual runs no query itself, so it cannot answer differently from the command line. A mode is a list of the tools the manual shows.

**Tech stack:** `serde_json`. No new crate: the manual is a JSON value. A crate named `rs-utcp` exists and has not been looked at (`TO_REFINE`). Decided by [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md). The manual's shape and the argument rules are drafted in [utcp-manual.md](../utcp-manual.md), and every part of that page tagged `TO_REFINE` is still open.

**Spec:** [utcp-manual.md](../utcp-manual.md), [usage-guide.md](../usage-guide.md#connecting-an-ai-tool), [modes.md](../modes.md). Capabilities M1 to M3, M5, M6, M8. Skills are not in the manual: [ADR 0023](../adrs/0023-skills-reach-ai-tools-through-links-in-the-workspace-root.md).

**Read first:** [00-overview.md](./00-overview.md), and [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md) for what is still open.

## Global constraints

- Standard output carries the manual and nothing else. Every message for a person goes to standard error.
- Every tool's call template runs a command that only reads. `index`, `init` and `check` never appear in a manual.
- A tool's call template ends in `--json`, so it returns the same JSON as its command prints.
- A call template is a line of shell, and the client inserts the AI tool's arguments into it as plain text. So every placeholder is inside double quotes, and every argument has a schema that cannot hold `"`, `$`, a backtick, `\`, a newline or a NUL. `workbench manual` refuses to print a template that breaks this. The client is assumed to keep arguments out of the shell (M8, decided), so this is a second guard. See [why arguments need care](../utcp-manual.md#why-arguments-need-care).
- With `--json`, a command that succeeds writes nothing to standard error, because the client mixes standard error into the result. Decided; the real client is checked in Task 1. See [utcp-manual.md](../utcp-manual.md#standard-error).
- Only `developer-support` is available in Release 1. `operational-support` and `testing-support` are names `manual` knows and refuses, each with a message that says the mode is not available yet.
- The same inputs give the same bytes: tools in the order of the table.
- No network calls.

## Review focus

- The manual and the command line drifting apart: a tool whose command no longer parses, or whose required argument is not in its schema. Task 4.
- A value that breaks out of its quotes and runs shell. The test that runs a real shell, with the worst values each pattern allows. Task 4.
- A workspace path with spaces or non-ASCII letters is written into every call template whole. Task 3.
- A workspace that was never indexed still gets a manual. The tools it lists answer with the "run `workbench index`" error when they are called, not when the manual is printed. Task 6.
- A query command opens the store read-only, so a tool call cannot write even by mistake. Task 6.

## The tools

A call template is a fixed line, so it cannot leave an argument out or add a flag only when one is given ([utcp-manual.md](../utcp-manual.md#arguments-all-required-with-defaults)). So **every argument of a tool is required in its schema, with a default** the AI tool is told to send. `*` means no filter, for `project` and `kind`. A flag that is only present or absent (`--no-source`, `--failed`, `--unreached`) and a repeatable option (`--edge`) are left out of the manual and stay on the command line. The defaults marked `TO_REFINE` are not in the usage guide and need choosing.

| Tool | Arguments (all required) | Command |
|---|---|---|
| `explore` | `question`, `project` (default `*`), `max_files` (default 8, `TO_REFINE`) | `workbench explore "<question>" --project "<project>" --max-files "<n>" --json` |
| `node` | `node` | `workbench node "<node>" --json` |
| `file` | `file` (`project:path`), `offset` (default 0), `limit` (default 200, `TO_REFINE`) | `workbench node --file "<file>" --offset "<n>" --limit "<n>" --json` |
| `search` | `text`, `kind` (default `*`), `project` (default `*`), `limit` (default 10) | `workbench query "<text>" --kind "<kind>" --project "<project>" --limit "<n>" --json` |
| `callers` | `node`, `depth` (default 1), `limit` (default 20) | `workbench callers "<node>" --depth "<n>" --limit "<n>" --json` |
| `callees` | `node`, `depth` (default 1), `limit` (default 20) | `workbench callees "<node>" --depth "<n>" --limit "<n>" --json` |
| `impact` | `node`, `depth` (default 2) | `workbench impact "<node>" --depth "<n>" --json` |
| `tests` | `node` | `workbench impact "<node>" --tests --json` |
| `neighbors` | `node`, `depth` (default 1, `TO_REFINE`), `direction` (`in`, `out` or `both`; default `both`, `TO_REFINE`) | `workbench neighbors "<node>" --depth "<n>" --direction "<direction>" --json` |
| `files` | `project` (default `*`) | `workbench files --project "<project>" --json` |
| `dependencies` | none | `workbench deps --json` |
| `status` | none | `workbench status --json` |

`impact --tests` answers a different question from `impact`, so it is a tool of its own, `tests`, the way `node` and `file` are two tools ([ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md#decided)). `files --unreached` stays on the command line.

Each command also gets `--workspace "<absolute path>"`. In the table, `"<n>"` stands for the placeholder `"UTCP_ARG_<name>_UTCP_END"`. A tool's description is one or two sentences written for an AI tool: what the tool answers, and when to choose it over another. `explore`'s says to start with it.

## File structure

| File | Holds |
|---|---|
| `src/adapters/driving/utcp/mod.rs` | `print_manual` |
| `src/adapters/driving/utcp/mode.rs` | `Mode` and the tools each mode lists |
| `src/adapters/driving/utcp/manual.rs` | `build_manual`, the document's shape and the format version |
| `src/adapters/driving/utcp/tools.rs` | The twelve tools: names, descriptions, schemas, call templates |
| `tests/utcp.rs` | Tests that run the binary |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 8A | 1, 2, 3 | C0 | `utcp/mod.rs`, `utcp/mode.rs`, `utcp/manual.rs` |
| 8B | 4 | 8A, 7A | `utcp/tools.rs` |
| 8D | 6 | 8B, 7D | `tests/utcp.rs`, the `manual` arm of `cli/run.rs` |

8A can start the day C0 is merged, beside the queries and the command line. 8B follows it. 8B needs the command tree of slice 7A, because its tests check that every call template parses as a command. It does not wait for SQLite or for the indexer.

8B can be split further when there are hands for it: the twelve tools are independent, and each is one entry in `tools.rs`. To split it, one developer first lands the file with `status` alone, and the other ten tools follow as small pull requests.

## Task 1: Refine the UTCP draft

**Files:** none. The result goes into [utcp-manual.md](../utcp-manual.md), where each `TO_REFINE` tag is removed or replaced as its point is settled.

The draft was written from the public UTCP pages, without the formal specification. Before any code:

- Read the UTCP specification, and fix the version and the manual's fields: [the manual shape](../utcp-manual.md#the-manual-shape-draft).
- Pick the client the team will use, and run it on a hand-written manual with one tool. Confirm: how a missing optional argument is handled, whether standard error reaches the result, how long a call may take, and whether the client ignores a field it does not know.
- **Try the argument attack.** Call the tool with `x"; echo INJECTED; echo "` and with `$(echo INJECTED)`, with and without a `pattern` on the argument. Write down what the client inserts and whether it checks the schema first. Release 1 does not wait for this: the client is assumed safe (M8). If it inserts the value unchecked, take the fallback options in [the solution](../utcp-manual.md#the-solution-draft) to the project owner.
- Decide whether `rs-utcp` is worth a crate. The manual is a small JSON value.

**Done when:** the first four open points of ADR 0022 are closed, and `manual.rs` can name the format version it targets.

## Task 2: Modes

**Files:** create `src/adapters/driving/utcp/mode.rs`.

**Produces:**

```rust
pub enum Mode { DeveloperSupport, OperationalSupport, TestingSupport }
impl FromStr for Mode { /* "developer-support", "operational-support", "testing-support" */ }
impl Mode {
    pub fn is_available(&self) -> bool;                 // only DeveloperSupport in Release 1
    pub fn tools(&self) -> &'static [&'static str];     // the twelve graph tools for DeveloperSupport
}
```

**Tests:**

| Test | Asserts |
|---|---|
| `three_names_parse` | Each name gives its mode |
| `unknown_name_lists_the_three` | The error's text holds all three names |
| `only_developer_support_is_available` | `true`, `false`, `false` |
| `developer_support_lists_the_twelve_graph_tools` | The names of the table above, in that order |

**Commit:** `feat(utcp): modes`

## Task 3: The manual

**Files:** create `src/adapters/driving/utcp/manual.rs`, `src/adapters/driving/utcp/mod.rs`.

**Produces:**

```rust
pub const FORMAT_VERSION: &str = /* from Task 1 */;
pub fn build_manual(mode: &Mode, workspace: &Path) -> serde_json::Value;
pub fn print_manual<W: Write>(mode: &Mode, workspace: &Path, out: W) -> Result<(), ManualError>;
```

`build_manual` is a pure function: it reads no file and runs no command. It names the manual `workbench` with the version of `Cargo.toml`, and lists the tools of `tool_specs(mode)` with their call templates. `print_manual` writes the value as one pretty-printed JSON document and a final newline. `workspace` must be absolute; `build_manual` refuses a relative one.

**Tests:**

| Test | Asserts |
|---|---|
| `manual_names_workbench_and_its_version` | Name and version |
| `manual_states_the_format_version` | `FORMAT_VERSION` appears |
| `manual_lists_only_the_modes_tools` | The names of `Mode::tools` and no others |
| `same_inputs_give_the_same_bytes` | Two calls print equal output |
| `output_is_one_json_document` | The whole output parses, and nothing follows it but a newline |
| `workspace_path_with_spaces_and_non_ascii_is_kept_whole` | `/home/you/acme shop/é` is one value in every call template, not split or escaped by hand |
| `every_call_template_carries_json_and_the_workspace` | `--json` and `--workspace` in each |
| `every_placeholder_is_in_double_quotes` | No `UTCP_ARG_..._UTCP_END` outside quotes |
| `manual_refuses_a_template_that_can_break_out` | An unquoted placeholder, a string argument with no `pattern`, or a `pattern` that accepts `"`, `$`, a backtick or `\` gives `ManualError` |
| `relative_workspace_is_refused` | `ManualError` naming the path |
| `workspace_path_with_shell_characters_is_refused` | A path holding `"`, `$`, a backtick or `\` gives `ManualError`, because the path is written inside quotes in every template |

**Commit:** `feat(utcp): build and print the manual`

## Task 4: The twelve tools

**Files:** create `src/adapters/driving/utcp/tools.rs`.

**Produces:**

```rust
pub struct ToolSpec { pub name: &'static str, pub description: &'static str, pub input_schema: serde_json::Value, pub call: CallTemplate }
pub fn tool_specs(mode: &Mode) -> Vec<ToolSpec>;
```

`CallTemplate` has the shape Task 1 found. It names the command and the place each argument goes. Every argument is required, with a default, so nothing in a template is optional ([ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md#decided)).

**Tests:**

| Test | Asserts |
|---|---|
| `twelve_tools_each_with_a_schema` | Twelve entries, each schema an object with its required fields |
| `every_argument_is_required_and_has_a_default` | In each schema, `required` lists every property, and each property has a `default` |
| `star_is_the_no_filter_value` | `project` and `kind` accept `*`, and no other tool argument does |
| `no_flag_is_left_for_the_model_to_toggle` | No template holds `--no-source`, `--failed`, `--unreached` or `--edge` |
| `every_description_is_one_or_two_sentences` | None is empty, and none is longer than 300 characters |
| `explore_description_says_to_start_with_it` | The text holds "start" |
| `every_call_template_parses_as_a_command` | For each tool, sample arguments made from its schema, put into its template, parse with `Cli::try_parse_from` into the matching `Command` |
| `required_arguments_match_the_command` | A schema's required fields are exactly the required arguments of its command |
| `no_tool_runs_a_command_that_writes` | `index`, `init`, `check` and `manual` are not the command of any tool |
| `node_and_file_are_two_tools` | `node` takes only `node`; `file` takes `file`, `offset` and `limit`. Each template, filled with sample arguments, parses into `Command::Node`: `node`'s without `--file`, `file`'s with it (ADR 0022) |
| `neighbors_has_no_edge_argument` | The `neighbors` schema has no `edges` property and its template holds no `--edge`: a repeatable option stays on the command line (ADR 0022) |
| `worst_allowed_values_reach_the_command_whole` | For each string argument: the template filled with the longest and the oddest values its pattern allows (spaces, braces, `;`, `'`, `(`, `)`), run by `sh` with a stub for `workbench`, gives the stub one argument equal to the value |
| `patterns_reject_shell_text` | For each pattern: `x"; echo hi; echo "`, `$(id)`, a backtick command, `\` and a newline are all refused |

**Commit:** `feat(utcp): the twelve graph tools`

## Task 5: Skills are not in the manual

Skills reach the AI tool through links in the workspace root, made by `workbench init --enable-shared-skills` and `workbench skills link` ([step 2, task 6](./step-2-configuration.md#task-6-link-the-shared-skills), [ADR 0023](../adrs/0023-skills-reach-ai-tools-through-links-in-the-workspace-root.md)). The manual lists tools only, so this step has no skills task and no slice 8C.

## Task 6: Wiring, and tests that run the binary

**Files:** create `tests/utcp.rs`; modify the `Manual` arm of `src/adapters/driving/cli/run.rs`.

The `manual` command parses the mode. A name that is not a mode exits `2`. A mode that is not available exits `1` with its message. Otherwise it finds the workspace, makes its path absolute, and calls `print_manual` on standard output. It does not open the store.

The query commands open the store read-only. That is a rule of the use cases, and this slice adds its test.

**Tests**, running `workbench manual` and the commands it lists, on a copy of the Acme Shop fixture:

| Test | Asserts |
|---|---|
| `manual_prints_one_json_document` | Standard output parses, and standard error is empty |
| `manual_lists_twelve_tools` | The twelve names |
| `every_listed_command_runs_on_the_indexed_fixture` | Each tool's template, with sample arguments, run as a process: exit `0`, and standard output has `result` and `freshness` |
| `impact_through_the_manual_equals_impact_json` | The output of the `impact` template equals `workbench impact ... --json`, but for the time in `freshness` |
| `explore_returns_source_flow_and_blast_radius` | The three parts, for a question about `Invoice` |
| `queries_cannot_write` | After running the twelve templates, the store file's content hash is unchanged |
| `manual_works_before_the_first_index` | Exit `0` on a workspace that was never indexed. `status` then answers, and `impact` exits `1` saying to run `workbench index` |
| `operational_support_is_refused` | Exit code `1`, and "not available yet" on standard error |
| `testing_support_is_refused` | The same |
| `unknown_mode_is_a_usage_error` | Exit code `2` |
| `no_workspace_names_the_flag` | Exit code `1`, and `--workspace` in the message |

**Commit:** `feat(utcp): wire the manual command and test it end to end`

## Done when

- A UTCP client given the manual of the [usage guide](../usage-guide.md#connecting-an-ai-tool) lists twelve tools. This is checked by hand with a real client, once, because no test here can stand in for one.
- The impact question of the roadmap, called through the manual, returns all six steps of the walk.
- A session of tool calls leaves the store file unchanged.

## Left open

- **Everything Task 1 finds.** If the client does not keep arguments out of the shell, this step changes shape: see the fallback options in [utcp-manual.md](../utcp-manual.md#the-solution-draft).
- **The defaults marked `TO_REFINE`**, and what the client does with an argument it is given but whose value is the default. Task 1 checks both with a real client.
- **The descriptions of the tools.** They decide how well an AI tool chooses between them, and are best tuned by trying them with a real AI tool.
- **Keeping the manual current.** The manual does not change until `workbench manual` is run again. Whether `status` should say that the manual was written by an older version is not decided.
