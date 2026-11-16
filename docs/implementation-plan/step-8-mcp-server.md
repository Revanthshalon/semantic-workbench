# Step 8: MCP Server Implementation Plan

**Goal:** Serve the queries and the skills to an AI tool over stdio, in the `developer-support` mode.

**Architecture:** The server is a second door to the same use cases the command line calls. A tool is a name, a description, a schema for its arguments and a function that calls one use case and returns its `Answer` as JSON. A mode is a list of the tools it offers. The server opens the store read-only, so it cannot write even by mistake.

**Tech stack:** `rmcp`, `serde_json`, `tokio`.

**Spec:** [usage-guide.md](../usage-guide.md#connecting-an-ai-tool), [mcp-modes.md](../mcp-modes.md). Capabilities M1 to M3, M5, M6, K2.

**Read first:** [00-overview.md](./00-overview.md).

## Global constraints

- Standard output carries the protocol and nothing else. Every message for a person goes to standard error.
- The server never changes the graph and never indexes.
- A tool returns the same JSON as its command prints with `--json`.
- Every answer carries its freshness.
- Only `developer-support` runs in Release 1. `operational-support` and `testing-support` are names the server knows and refuses, each with a message that says the mode is not available yet.
- Skills are the same in every mode.
- No network calls.

## Review focus

- A call to a tool that does not exist, or with arguments that do not fit its schema, returns a tool error the AI tool can read. The server keeps running. Task 3.
- A workspace that was never indexed: every tool but `status` returns a tool error that says to run `workbench index`. `status` answers. Task 3.
- An index that runs while the server is up: tools keep answering from the graph as it was, and see the new graph on the first call after it ends. Task 5.
- A skill file with a missing or broken heading is left out, with a message on standard error. The others are still served. Task 4.
- The AI tool closing standard input ends the server with exit code `0`. Task 1.

## The tools

| Tool | Arguments | Use case |
|---|---|---|
| `explore` | `question` (required), `project`, `max_files` | `explore` |
| `node` | `node` or `file`, `with_source` (default `true`), `offset`, `limit` | `node`, `file` |
| `search` | `text` (required), `kind`, `project`, `limit` | `search` |
| `callers` | `node` (required), `depth`, `limit` | `callers` |
| `callees` | `node` (required), `depth`, `limit` | `callees` |
| `impact` | `node` (required), `depth` | `impact` |
| `neighbors` | `node` (required), `depth`, `direction`, `edges` | `neighbors` |
| `files` | `project`, `failed` | `files` |
| `dependencies` | | `deps` |
| `status` | | `status` |

A tool's description is one or two sentences written for an AI tool: what the tool answers, and when to choose it over another. `explore`'s says to start with it.

## File structure

| File | Holds |
|---|---|
| `src/adapters/driving/mcp/mod.rs` | `serve` |
| `src/adapters/driving/mcp/mode.rs` | `Mode` and the tools each mode offers |
| `src/adapters/driving/mcp/tools.rs` | The ten tools: names, descriptions, schemas |
| `src/adapters/driving/mcp/dispatch.rs` | From a tool call to a use case and back |
| `src/adapters/driving/mcp/skills.rs` | Reading and offering skills |
| `tests/mcp.rs` | Tests that run the server |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 8A | 1, 2 | C0 | `mcp/mod.rs`, `mcp/mode.rs` |
| 8B | 3 | 8A | `mcp/tools.rs`, `mcp/dispatch.rs` |
| 8C | 4 | 8A | `mcp/skills.rs` |
| 8D | 5 | 8B, 8C, 7D | `tests/mcp.rs`, the `mcp` arm of `cli/run.rs` |

8A can start the day C0 is merged, beside the queries and the command line. 8B and 8C then run side by side, by two developers. 8B is tested on `MemoryStore` with the fixture, so it does not wait for SQLite or for the indexer, only for the result types.

8B can be split further when there are hands for it: the ten tools are independent, and each is one entry in `tools.rs` and one arm in `dispatch.rs`. To split it, one developer first lands both files with `status` alone, and the other nine tools follow as small pull requests.

## Task 1: Serve over stdio

**Files:** create `src/adapters/driving/mcp/mod.rs`.

**Produces:**

```rust
pub struct Server<S, F> { /* query context, mode, skills */ }
pub async fn serve<S: GraphStore, F: Files, R: AsyncRead + Unpin, W: AsyncWrite + Unpin>(server: Server<S, F>, input: R, output: W) -> Result<(), McpError>;
```

`serve` takes its input and output as arguments, so a test drives it with in-memory pipes. It answers `initialize` with the name `workbench`, the version of `Cargo.toml`, and the capabilities for tools, prompts and resources.

**Tests:**

| Test | Asserts |
|---|---|
| `initialize_names_the_server_and_its_version` | `serverInfo.name == "workbench"` |
| `initialize_announces_tools_prompts_and_resources` | All three capabilities |
| `closing_the_input_ends_the_server` | `serve` returns `Ok(())` |
| `output_holds_only_protocol_messages` | Every line written is a JSON-RPC message |
| `broken_json_gets_a_protocol_error_and_the_server_goes_on` | An error reply, and the next request is answered |

**Commit:** `feat(mcp): serve over stdio`

## Task 2: Modes

**Files:** create `src/adapters/driving/mcp/mode.rs`.

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
| `developer_support_offers_the_ten_graph_tools` | The names of the table above, in that order |

**Commit:** `feat(mcp): modes`

## Task 3: The ten tools

**Files:** create `src/adapters/driving/mcp/tools.rs`, `src/adapters/driving/mcp/dispatch.rs`.

**Produces:**

```rust
pub struct ToolSpec { pub name: &'static str, pub description: &'static str, pub input_schema: serde_json::Value }
pub fn tool_specs(mode: &Mode) -> Vec<ToolSpec>;

pub async fn call<S: GraphStore, F: Files>(ctx: &QueryContext<S, F>, mode: &Mode, name: &str, arguments: serde_json::Value) -> Result<serde_json::Value, ToolError>;
pub enum ToolError { UnknownTool(String), BadArguments(String), Query(String) }
```

`call` refuses a tool the mode does not offer as `UnknownTool`. It turns the arguments into the use case's parameters, calls it, and returns `serde_json::to_value` of the `Answer`. A `QueryError` becomes `ToolError::Query` with the same sentence the command line prints.

**Tests**, on `MemoryStore` with `fixtures::acme()`:

| Test | Asserts |
|---|---|
| `tools_list_has_ten_tools_with_schemas` | Ten entries, each schema an object with its required fields |
| `every_description_is_one_or_two_sentences` | None is empty, and none is longer than 300 characters |
| `explore_description_says_to_start_with_it` | The text holds "start" |
| `impact_returns_the_answer_as_json` | `result.by_project` has four entries, and `freshness` is present |
| `each_tool_answers` | One call for each of the ten, each `Ok` |
| `tool_answer_equals_the_use_case_answer` | For `callers`: the JSON equals `to_value` of calling `callers` directly |
| `unknown_tool_is_a_tool_error` | `UnknownTool` |
| `missing_required_argument_is_a_tool_error` | `impact` with no `node`: `BadArguments` naming `node` |
| `wrong_type_is_a_tool_error` | `depth: "two"`: `BadArguments` |
| `ambiguous_node_lists_the_candidates` | `Query`, with both locations in the text |
| `not_indexed_says_to_index_but_status_answers` | On an empty store: `impact` is `Query` holding `workbench index`; `status` is `Ok` |

**Commit:** `feat(mcp): the ten graph tools`

## Task 4: Skills

**Files:** create `src/adapters/driving/mcp/skills.rs`.

**Produces:**

```rust
pub struct Skill { pub name: String, pub description: String, pub body: String }
pub fn load_skills<F: Files>(files: &F, skills_dir: &Path) -> (Vec<Skill>, Vec<String>);   // skills, and messages about the ones left out
```

A skill is a folder holding a `SKILL.md` that starts with a block between two `---` lines giving `name` and `description`. The rest of the file is the body. Skills are returned sorted by name. The server offers each as a prompt named after it, and as a resource with the address `workbench://skills/<name>`.

How a skill reaches the AI tool is an open decision, K2 in the [capability map](../capability-map.md#open-decisions). This task builds the proposal: a prompt and a resource. Keep both behind `load_skills`, so a different decision changes only the two places that offer them.

**Tests:**

| Test | Asserts |
|---|---|
| `skill_is_read_from_its_folder` | Name, description and body |
| `skills_are_sorted_by_name` | `python` before `workbench` |
| `folder_without_skill_md_is_ignored` | No skill, and no message |
| `missing_name_leaves_the_skill_out_with_a_message` | The other skill is still returned |
| `missing_skills_folder_gives_no_skills_and_no_error` | Two empty lists |
| `prompts_list_has_one_prompt_per_skill` | Through `serve` |
| `resource_read_returns_the_body` | For `workbench://skills/python` |
| `skills_are_the_same_in_every_mode` | The list does not depend on the mode |

**Commit:** `feat(mcp): offer the shared skills`

## Task 5: Wiring, and tests that run the server

**Files:** create `tests/mcp.rs`; modify the `Mcp` arm of `src/adapters/driving/cli/run.rs`.

The `mcp` command parses the mode. A name that is not a mode exits `2`. A mode that is not available exits `1` with its message. Otherwise it finds the workspace, opens the store read-only, loads the skills from `.workbench/skills/`, and calls `serve` on standard input and output.

**Tests**, running `workbench mcp` on an indexed copy of the Acme Shop fixture and speaking JSON-RPC to it:

| Test | Asserts |
|---|---|
| `server_starts_and_lists_ten_tools` | `tools/list` |
| `impact_over_mcp_equals_impact_json` | The tool's answer equals the output of `workbench impact ... --json`, but for the time in `freshness` |
| `explore_returns_source_flow_and_blast_radius` | The three parts for a question about `Invoice` |
| `skills_written_by_init_are_offered` | `prompts/list` has `python` and `workbench` |
| `operational_support_is_refused` | Exit code `1`, and "not available yet" on standard error |
| `testing_support_is_refused` | The same |
| `unknown_mode_is_a_usage_error` | Exit code `2` |
| `server_cannot_write` | After a session, the store file's content hash is unchanged |
| `answers_follow_an_index` | Index, ask, change a file, index again, ask again in the same session: the second answer shows the change |
| `no_workspace_names_the_flag` | Exit code `1`, and `--workspace` in the message |

**Commit:** `feat(mcp): wire the server and test it end to end`

## Done when

- An MCP client connected with the configuration of the [usage guide](../usage-guide.md#connecting-an-ai-tool) lists ten tools and two skills.
- The impact question of the roadmap returns all six steps of the walk.
- A session leaves the store file unchanged.

## Left open

- **How a skill reaches the AI tool.** Built here as a prompt and a resource; see Task 4.
- **The descriptions of the tools.** They decide how well an AI tool chooses between them, and are best tuned by trying them with a real AI tool once the server runs.
