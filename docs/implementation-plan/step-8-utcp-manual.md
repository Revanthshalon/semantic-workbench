# Step 8: UTCP Manual Implementation Plan

**Goal:** Print a UTCP manual that describes the queries and the skills to an AI tool, in the `developer-support` mode, so the tool calls `workbench` directly.

**Architecture:** The manual is the second door to the same use cases the command line calls, and it is only data. A tool is a name, a description, a schema for its arguments and a call template: the `workbench` command to run, with `--json` and the workspace path. `workbench manual` builds the document from one table of tools and prints it. No process stays running, and the manual runs no query itself, so it cannot answer differently from the command line. A mode is a list of the tools the manual shows.

**Tech stack:** `serde_json`. No new crate: the manual is a JSON value. Decided by [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md).

**Spec:** [usage-guide.md](../usage-guide.md#connecting-an-ai-tool), [modes.md](../modes.md). Capabilities M1 to M3, M5, M6, K2.

**Read first:** [00-overview.md](./00-overview.md), and [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md) for what is still open.

## Global constraints

- Standard output carries the manual and nothing else. Every message for a person goes to standard error.
- Every tool's call template runs a command that only reads. `index`, `init` and `check` never appear in a manual.
- A tool's call template ends in `--json`, so it returns the same JSON as its command prints.
- A call template never joins arguments into one shell string. How arguments are passed depends on the format found in Task 1.
- Only `developer-support` is available in Release 1. `operational-support` and `testing-support` are names `manual` knows and refuses, each with a message that says the mode is not available yet.
- Skills are the same in every mode.
- The same inputs give the same bytes: tools in the order of the table, skills sorted by name.
- No network calls.

## Review focus

- The manual and the command line drifting apart: a tool whose command no longer parses, or whose required argument is not in its schema. Task 4.
- A workspace path with spaces or non-ASCII letters is written into every call template whole. Task 3.
- A workspace that was never indexed still gets a manual. The tools it lists answer with the "run `workbench index`" error when they are called, not when the manual is printed. Task 6.
- A skill file with a missing or broken heading is left out, with a message on standard error. The others are still listed. Task 5.
- A query command opens the store read-only, so a tool call cannot write even by mistake. Task 6.

## The tools

| Tool | Arguments | Command |
|---|---|---|
| `explore` | `question` (required), `project`, `max_files` | `workbench explore <question> [--project <id>] [--max-files <n>] --json` |
| `node` | `node` or `file`, `with_source` (default `true`), `offset`, `limit` | `workbench node <node> [--no-source] --json`, or `workbench node --file <project>:<path> [--offset <n>] [--limit <n>] --json` |
| `search` | `text` (required), `kind`, `project`, `limit` | `workbench query <text> [--kind <kind>] [--project <id>] [--limit <n>] --json` |
| `callers` | `node` (required), `depth`, `limit` | `workbench callers <node> [--depth <n>] [--limit <n>] --json` |
| `callees` | `node` (required), `depth`, `limit` | `workbench callees <node> [--depth <n>] [--limit <n>] --json` |
| `impact` | `node` (required), `depth` | `workbench impact <node> [--depth <n>] --json` |
| `neighbors` | `node` (required), `depth`, `direction`, `edges` | `workbench neighbors <node> [--depth <n>] [--direction in\|out\|both] [--edge <kind>]... --json` |
| `files` | `project`, `failed` | `workbench files [--project <id>] [--failed] --json` |
| `dependencies` | | `workbench deps --json` |
| `status` | | `workbench status --json` |

Each command also gets `--workspace <absolute path>`. A tool's description is one or two sentences written for an AI tool: what the tool answers, and when to choose it over another. `explore`'s says to start with it.

## File structure

| File | Holds |
|---|---|
| `src/adapters/driving/utcp/mod.rs` | `print_manual` |
| `src/adapters/driving/utcp/mode.rs` | `Mode` and the tools each mode lists |
| `src/adapters/driving/utcp/manual.rs` | `build_manual`, the document's shape and the format version |
| `src/adapters/driving/utcp/tools.rs` | The ten tools: names, descriptions, schemas, call templates |
| `src/adapters/driving/utcp/skills.rs` | Reading skills and listing them |
| `tests/utcp.rs` | Tests that run the binary |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 8A | 1, 2, 3 | C0 | `utcp/mod.rs`, `utcp/mode.rs`, `utcp/manual.rs` |
| 8B | 4 | 8A, 7A | `utcp/tools.rs` |
| 8C | 5 | 8A | `utcp/skills.rs` |
| 8D | 6 | 8B, 8C, 7D | `tests/utcp.rs`, the `manual` arm of `cli/run.rs` |

8A can start the day C0 is merged, beside the queries and the command line. 8B and 8C then run side by side, by two developers. 8B needs the command tree of slice 7A, because its tests check that every call template parses as a command. It does not wait for SQLite or for the indexer.

8B can be split further when there are hands for it: the ten tools are independent, and each is one entry in `tools.rs`. To split it, one developer first lands the file with `status` alone, and the other nine tools follow as small pull requests.

## Task 1: Confirm the UTCP format

**Files:** none. The result goes into [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md), under its open points.

This plan was written without checking the UTCP specification. Before any code, read the current specification and its CLI call template, and write down in the ADR:

- The version of UTCP to target, and the shape of a manual: its top-level fields, a tool's fields, and how a tool's input schema is written.
- The fields of the CLI call template, and **how a client passes arguments to the command**: as a list of values, or substituted into a string that a shell reads. If it is a string, every argument needs quoting, and a tool call could inject shell text. In that case stop and take the question back to the project owner before Task 3.
- Whether a client can pass the workspace path, working directory or environment, and whether it reads the command's standard output as the tool's result.
- Whether a manual can carry anything for skills. This decides Task 5.
- Whether a Rust library for UTCP exists. If one does, decide whether it is worth a crate: the manual is a small JSON value.

**Done when:** the ADR's first, third and fourth open points are replaced by what was found, and `manual.rs` can name the format version it targets.

## Task 2: Modes

**Files:** create `src/adapters/driving/utcp/mode.rs`.

**Produces:**

```rust
pub enum Mode { DeveloperSupport, OperationalSupport, TestingSupport }
impl FromStr for Mode { /* "developer-support", "operational-support", "testing-support" */ }
impl Mode {
    pub fn is_available(&self) -> bool;                 // only DeveloperSupport in Release 1
    pub fn tools(&self) -> &'static [&'static str];     // the ten graph tools for DeveloperSupport
}
```

**Tests:**

| Test | Asserts |
|---|---|
| `three_names_parse` | Each name gives its mode |
| `unknown_name_lists_the_three` | The error's text holds all three names |
| `only_developer_support_is_available` | `true`, `false`, `false` |
| `developer_support_lists_the_ten_graph_tools` | The names of the table above, in that order |

**Commit:** `feat(utcp): modes`

## Task 3: The manual

**Files:** create `src/adapters/driving/utcp/manual.rs`, `src/adapters/driving/utcp/mod.rs`.

**Produces:**

```rust
pub const FORMAT_VERSION: &str = /* from Task 1 */;
pub fn build_manual(mode: &Mode, workspace: &Path, skills: &[Skill]) -> serde_json::Value;
pub fn print_manual<W: Write>(mode: &Mode, workspace: &Path, skills: &[Skill], out: W) -> Result<(), ManualError>;
```

`build_manual` is a pure function: it reads no file and runs no command. It names the manual `workbench` with the version of `Cargo.toml`, lists the tools of `tool_specs(mode)` with their call templates, and lists the skills. `print_manual` writes the value as one pretty-printed JSON document and a final newline. `workspace` must be absolute; `build_manual` refuses a relative one.

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
| `relative_workspace_is_refused` | `ManualError` naming the path |

**Commit:** `feat(utcp): build and print the manual`

## Task 4: The ten tools

**Files:** create `src/adapters/driving/utcp/tools.rs`.

**Produces:**

```rust
pub struct ToolSpec { pub name: &'static str, pub description: &'static str, pub input_schema: serde_json::Value, pub call: CallTemplate }
pub fn tool_specs(mode: &Mode) -> Vec<ToolSpec>;
```

`CallTemplate` has the shape Task 1 found. It names the command and the place each argument goes, and it marks an argument that is left out when the AI tool does not give it.

**Tests:**

| Test | Asserts |
|---|---|
| `ten_tools_each_with_a_schema` | Ten entries, each schema an object with its required fields |
| `every_description_is_one_or_two_sentences` | None is empty, and none is longer than 300 characters |
| `explore_description_says_to_start_with_it` | The text holds "start" |
| `every_call_template_parses_as_a_command` | For each tool, sample arguments made from its schema, put into its template, parse with `Cli::try_parse_from` into the matching `Command` |
| `required_arguments_match_the_command` | A schema's required fields are exactly the required arguments of its command |
| `no_tool_runs_a_command_that_writes` | `index`, `init`, `check` and `manual` are not the command of any tool |
| `node_takes_a_node_or_a_file` | The `node` schema accepts one of the two, and its two templates parse |
| `neighbors_edges_repeat` | Two `edges` give two `--edge` pairs |

**Commit:** `feat(utcp): the ten graph tools`

## Task 5: Skills

**Files:** create `src/adapters/driving/utcp/skills.rs`.

**Produces:**

```rust
pub struct Skill { pub name: String, pub description: String, pub path: PathBuf }
pub fn load_skills<F: Files>(files: &F, skills_dir: &Path) -> (Vec<Skill>, Vec<String>);   // skills, and messages about the ones left out
```

A skill is a folder holding a `SKILL.md` that starts with a block between two `---` lines giving `name` and `description`. `path` is the absolute path of that file. Skills are returned sorted by name. The manual lists each with its name, description and path.

How a skill reaches the AI tool is an open decision, K2 in the [capability map](../capability-map.md#open-decisions). This task builds the proposal: the manual names the file, and the AI tool reads it. Whether the manual can carry skills at all depends on Task 1. Keep that behind `load_skills` and the one place `build_manual` lists them, so a different decision changes only those.

**Tests:**

| Test | Asserts |
|---|---|
| `skill_is_read_from_its_folder` | Name, description and path |
| `skills_are_sorted_by_name` | `python` before `workbench` |
| `folder_without_skill_md_is_ignored` | No skill, and no message |
| `missing_name_leaves_the_skill_out_with_a_message` | The other skill is still returned |
| `missing_skills_folder_gives_no_skills_and_no_error` | Two empty lists |
| `manual_lists_each_skill_with_its_path` | Through `build_manual` |
| `skills_are_the_same_in_every_mode` | The list does not depend on the mode |

**Commit:** `feat(utcp): list the shared skills in the manual`

## Task 6: Wiring, and tests that run the binary

**Files:** create `tests/utcp.rs`; modify the `Manual` arm of `src/adapters/driving/cli/run.rs`.

The `manual` command parses the mode. A name that is not a mode exits `2`. A mode that is not available exits `1` with its message. Otherwise it finds the workspace, makes its path absolute, loads the skills from `.workbench/skills/`, and calls `print_manual` on standard output. It does not open the store.

The query commands open the store read-only. That is a rule of the use cases, and this slice adds its test.

**Tests**, running `workbench manual` and the commands it lists, on a copy of the Acme Shop fixture:

| Test | Asserts |
|---|---|
| `manual_prints_one_json_document` | Standard output parses, and standard error is empty |
| `manual_lists_ten_tools` | The ten names |
| `every_listed_command_runs_on_the_indexed_fixture` | Each tool's template, with sample arguments, run as a process: exit `0`, and standard output has `result` and `freshness` |
| `impact_through_the_manual_equals_impact_json` | The output of the `impact` template equals `workbench impact ... --json`, but for the time in `freshness` |
| `explore_returns_source_flow_and_blast_radius` | The three parts, for a question about `Invoice` |
| `queries_cannot_write` | After running the ten templates, the store file's content hash is unchanged |
| `manual_works_before_the_first_index` | Exit `0` on a workspace that was never indexed. `status` then answers, and `impact` exits `1` saying to run `workbench index` |
| `skills_written_by_init_are_listed` | `python` and `workbench`, with their paths |
| `operational_support_is_refused` | Exit code `1`, and "not available yet" on standard error |
| `testing_support_is_refused` | The same |
| `unknown_mode_is_a_usage_error` | Exit code `2` |
| `no_workspace_names_the_flag` | Exit code `1`, and `--workspace` in the message |

**Commit:** `feat(utcp): wire the manual command and test it end to end`

## Done when

- A UTCP client given the manual of the [usage guide](../usage-guide.md#connecting-an-ai-tool) lists ten tools and two skills. This is checked by hand with a real client, once, because no test here can stand in for one.
- The impact question of the roadmap, called through the manual, returns all six steps of the walk.
- A session of tool calls leaves the store file unchanged.

## Left open

- **How a skill reaches the AI tool.** Built here as a path and a description in the manual; see Task 5.
- **Everything Task 1 finds.** If the call template cannot pass arguments safely, this step changes shape.
- **The descriptions of the tools.** They decide how well an AI tool chooses between them, and are best tuned by trying them with a real AI tool.
- **Keeping the manual current.** The manual does not change until `workbench manual` is run again. Whether `status` should say that the manual was written by an older version is not decided.
