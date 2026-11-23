# Step 2: Configuration Implementation Plan

**Goal:** Find a workspace, read and check `.workbench/config.yml`, and write the files `workbench init` creates.

**Architecture:** Reading is two passes. The first turns YAML into a raw model that mirrors the file and refuses unknown fields. The second checks rules 1 to 13 and returns a validated model that uses the domain's value types. Nothing here touches the disk beyond `.workbench/` itself; the rules that need other files belong to step 4.

**Tech stack:** `serde`, a maintained YAML crate for `serde`, `thiserror`.

**Spec:** [configuration-guide.md](../configuration-guide.md), [modes.md](../modes.md#what-init-creates). Capabilities C1 to C10, K1, K3.

**Read first:** [00-overview.md](./00-overview.md) for the constraints, the module map and how a task is done.

## Global constraints

- Unknown fields are errors everywhere but in a `settings` block under `lsp`.
- A problem names the field it is about by its path, such as `projects[1].links[0].stack`.
- Checking never stops at the first problem. It returns all of them.
- Paths use `/`. A path containing `\` is a problem.
- `storage.backend: memgraph`, or any Memgraph field, is refused with a message that says only `sqlite` is supported.
- The reserved sections (`lsp`, `semantic`, `projects[].environment`) are checked for shape and produce one log line each. They are otherwise ignored.

## Review focus

Inputs the specification does not mention and a user will meet. Each has a test in the task named.

- An empty file, or a file holding only comments, is a problem that says `version` is missing, not a crash. Task 2.
- A key given twice in one mapping is a problem. Task 2.
- A project `path` written as `./billing/` or `billing//api` is treated as `billing` and `billing/api` before rule 4 compares paths. Task 3.
- Two project paths that differ only in letter case are a problem on macOS, where they are the same folder. Task 3.
- `init` in a folder that has `.workbench/` and no `config.yml` writes the missing files and overwrites none. Task 5.

## File structure

| File | Holds |
|---|---|
| `src/config/mod.rs` | The public surface: `locate`, `load`, `init` |
| `src/config/locate.rs` | Finding the workspace root |
| `src/config/raw.rs` | The raw model, one struct per YAML mapping |
| `src/config/model.rs` | The validated model |
| `src/config/validate.rs` | Rules 1 to 13 |
| `src/config/init.rs` | What `init` writes |
| `src/config/skills.rs` | Linking the shared skills into the AI platforms' folders |
| `src/config/error.rs` | `ConfigError`, which wraps the errors of the other files, and `ConfigProblem` |
| `templates/starter.yml` | The configuration `init` writes. New |
| `templates/skills/workbench/SKILL.md`, `templates/skills/python/SKILL.md` | The two skills `init` writes. New |

## Slices

Each slice is one pull request. The [overview](./00-overview.md#working-in-parallel) explains the rules.

| Slice | Tasks | Needs | Owns |
|---|---|---|---|
| 2A | 1 | | `locate.rs` |
| 2B | 2 | | `raw.rs` |
| 2C | 3, 4 | 1A, 2B | `validate.rs`, `model.rs`, `error.rs`, `load` in `mod.rs` |
| 2D | 5 | 2B | `init.rs`, `templates/starter.yml` |
| 2E | the two skill files | | `templates/skills/` |
| 2F | 6 | 2D | `skills.rs` |

2A, 2B and 2E can start on the first day, by three developers. 2C and 2D follow 2B and run side by side. 2D's test `starter_parses_and_reports_no_projects` needs `validate`, so it is added once 2C is merged.

Each slice keeps its errors in its own file, so no two slices share one: `LocateError` in `locate.rs`, `SyntaxError` in `raw.rs`, `InitError` in `init.rs`. Slice 2C creates `error.rs` with `ConfigError`, which wraps the first two and adds `Missing` and `Invalid`.

## Task 1: Find the workspace

**Files:** create `src/config/locate.rs`.

**Produces:**

```rust
pub struct WorkspaceRoot(PathBuf);            // the folder that holds `.workbench/`
impl WorkspaceRoot { pub fn path(&self) -> &Path; pub fn config_file(&self) -> PathBuf; }

pub fn locate(flag: Option<&Path>, env: Option<&OsStr>, cwd: &Path) -> Result<WorkspaceRoot, LocateError>;
```

`env` is the value of `WORKBENCH_WORKSPACE`, passed in so that tests need not set it.

**Tests:**

| Test | Asserts |
|---|---|
| `flag_wins_over_env_and_cwd` | With all three pointing at different workspaces, the flag's is returned |
| `env_wins_over_cwd` | With no flag, the variable's is returned |
| `cwd_is_used_when_it_holds_dot_workbench` | The current folder is returned |
| `nearest_parent_wins` | From `a/b/c`, with `.workbench/` in `a` and in `a/b`, `a/b` is returned |
| `flag_without_dot_workbench_is_an_error` | `LocateError::NotAWorkspace` naming the folder |
| `nothing_found_names_the_flag_and_the_variable` | The error's text contains `--workspace` and `WORKBENCH_WORKSPACE` |

**Commit:** `feat(config): locate the workspace root`

## Task 2: Read the file into the raw model

**Files:** create `src/config/raw.rs`.

**Produces:**

```rust
pub struct RawConfig { /* one field per top-level key of the configuration guide */ }
pub fn parse(text: &str) -> Result<RawConfig, SyntaxError>;
```

Every struct but the one for `lsp.settings` uses `#[serde(deny_unknown_fields)]`. `SyntaxError` carries the line and column the YAML crate reports.

**Tests:**

| Test | Asserts |
|---|---|
| `smallest_configuration_parses` | The four-field example of the guide gives one project, `billing-api` |
| `complete_template_parses` | `templates/config.yml`, read with `include_str!`, parses |
| `acme_configuration_parses` | The configuration of [example-workspace.md](../example-workspace.md#the-configuration) gives four projects |
| `unknown_field_is_an_error` | `projcts:` at the top gives a `SyntaxError` whose text contains `projcts` |
| `unknown_field_under_lsp_settings_is_allowed` | `python.analysis.typeCheckingMode` survives |
| `empty_file_says_version_is_missing` | The error's text contains `version` |
| `duplicate_key_is_an_error` | Two `projects:` keys give a `SyntaxError` |

**Commit:** `feat(config): parse the configuration file`

## Task 3: Check rules 1 to 13

**Files:** create `src/config/validate.rs`, `src/config/model.rs`, `src/config/error.rs`.

**Produces:**

```rust
pub struct ConfigProblem { pub rule: u8, pub field: String, pub message: String }

pub struct Config {
    pub projects: Vec<Project>,
    pub stacks: Vec<SharedStack>,
    pub storage: Storage,
    pub analysis: Analysis,            // flow_rounds: u32, 10 by default
    pub notices: Vec<String>,          // one per reserved section that was read and not used
}
pub struct Project {
    pub id: ProjectId, pub path: RelOrAbsPath, pub language: Language,
    pub dependency_manager: DependencyManager,
    pub import_names: Option<Vec<String>>, pub exclude: Vec<String>,
    pub dependencies: Dependencies, pub binaries: Vec<Binary>,
    pub links: Vec<Link>, pub compose: Option<ProjectStack>,
}
pub struct Binary {
    pub name: String, pub entry: RelPath,
    pub framework: Option<Framework>,  // Fastapi | Angular | None; absent: read from compose, then the entry file
    pub app: Option<AppRef>,           // module:attribute; only with Fastapi
}
pub struct Link { pub target: LinkTarget, pub via: Via, pub binary: Option<String>, pub note: Option<String> }
pub enum LinkTarget { Service { name: String, stack: Option<ComposeName> }, Project(ProjectId) }
pub enum Via { Http, Grpc, Database, Topic { name: String, role: Role }, Queue { name: String, role: Role } }

pub fn validate(raw: RawConfig) -> Result<Config, Vec<ConfigProblem>>;
```

`Via` carries `name` and `role` inside `Topic` and `Queue`, so a link with a name and no topic cannot be built. Defaults are applied here: `discover` is `true`, a dependency's scope is `Build`, `storage.path` is `.workbench/graph.db`.

**Tests:** one named `rule_N_...` for each of rules 2 to 13 of the [configuration guide](../configuration-guide.md#what-is-checked-and-when), each giving exactly one problem with that rule number, plus:

| Test | Asserts |
|---|---|
| `acme_configuration_is_valid` | No problems, four projects, five binaries, four links |
| `complete_template_is_valid` | No problems, and three notices |
| `every_problem_is_reported` | A file breaking rules 3, 7 and 11 gives three problems |
| `problem_names_its_field` | A link to an unknown project has `field == "projects[0].links[0].project"` |
| `paths_are_normalised_before_rule_4` | `./billing/` and `billing` are reported as the same path |
| `paths_differing_only_in_case_are_a_problem` | `Billing` and `billing` break rule 4 |
| `memgraph_backend_is_refused` | Rule 13, and the message contains `sqlite` |

**Commit:** `feat(config): validate the configuration`

## Task 4: Load in one call

**Files:** modify `src/config/mod.rs`.

**Produces:**

```rust
pub fn load(root: &WorkspaceRoot) -> Result<Config, ConfigError>;   // read, parse, validate
```

`ConfigError::Invalid(Vec<ConfigProblem>)` carries every problem.

**Tests:**

| Test | Asserts |
|---|---|
| `load_reads_the_file_under_dot_workbench` | A temp folder holding the Acme configuration loads four projects |
| `missing_file_is_an_error` | `ConfigError::Missing` naming the path |

**Commit:** `feat(config): load a workspace configuration`

## Task 5: What `init` writes

**Files:** create `src/config/init.rs`, `templates/starter.yml`, `templates/skills/workbench/SKILL.md`, `templates/skills/python/SKILL.md`.

`templates/config.yml` is a complete sample with invented projects, so it cannot be the file `init` writes: `check` would fail on it at once. `templates/starter.yml` is the starter: `version: 1`, the `storage` block, and one project entry in comments for the user to fill in.

**Produces:**

```rust
pub struct InitReport { pub written: Vec<PathBuf>, pub kept: Vec<PathBuf> }
pub fn init(dir: &Path) -> Result<InitReport, InitError>;
```

`init` writes these files below `dir/.workbench/`, each from a template embedded with `include_str!`:

`config.yml`, `.gitignore` (one line, `graph.db*`), `skills/workbench/SKILL.md`, `skills/python/SKILL.md`, `ops/config.yml`, `ops/contexts/testing.yml`, `ops/contexts/staging.yml`, `ops/contexts/production.yml`.

The three context files come from `templates/ops/contexts/staging.yml`, with `staging` replaced by the context's name.

**Tests:**

| Test | Asserts |
|---|---|
| `init_writes_all_eight_files` | All eight exist, and `written` lists them |
| `init_refuses_an_existing_configuration` | With `config.yml` present: `InitError::AlreadyInitialised`, and nothing is written |
| `init_fills_in_a_partial_folder` | With only `skills/python/SKILL.md` present and edited: it is in `kept`, its text is unchanged, the other seven are written |
| `starter_parses_and_reports_no_projects` | The starter parses, and `validate` gives one problem: rule 3, at least one project |
| `gitignore_covers_the_store_and_its_wal_files` | The pattern matches `graph.db`, `graph.db-wal` and `graph.db-shm` |

**Commit:** `feat(config): write the workspace files on init`

## Task 6: Link the shared skills

**Files:** create `src/config/skills.rs`.

Decided by [ADR 0023](../adrs/0023-skills-reach-ai-tools-through-links-in-the-workspace-root.md).

**Produces:**

```rust
pub enum Platform { Claude, Copilot }                    // FromStr: "claude", "copilot"
impl Platform { pub fn skills_dir(&self) -> &'static str; } // ".claude/skills", ".github/skills"
pub struct LinkReport { pub linked: Vec<PathBuf>, pub kept: Vec<PathBuf>, pub conflicts: Vec<PathBuf> }
pub fn link_skills(root: &WorkspaceRoot, platforms: &[Platform]) -> Result<LinkReport, SkillsError>;
```

For each folder under `.workbench/skills/` that holds a `SKILL.md`, and each platform given (both when the list is empty), `link_skills` makes `<root>/<skills_dir>/<name>` a relative symbolic link to `../../.workbench/skills/<name>`, creating the platform's folder if needed. A link that already points there is `kept`. Anything else at that path is left alone and listed in `conflicts`. Nothing is removed.

`init --enable-shared-skills` calls `init`, then `link_skills`. The command line wires both (step 7).

**Tests**, in a temp folder:

| Test | Asserts |
|---|---|
| `links_every_skill_for_both_platforms` | `python` and `workbench`, under `.claude/skills/` and `.github/skills/`: four in `linked` |
| `link_is_relative` | The target read back is `../../.workbench/skills/python` |
| `link_works_after_the_workspace_moves` | Moving the temp folder: each link still resolves to its `SKILL.md` |
| `running_twice_keeps_the_links` | The second run: four in `kept`, none in `linked` |
| `existing_folder_is_left_alone_and_reported` | A team's own `.claude/skills/python/` folder is unchanged and in `conflicts` |
| `link_pointing_elsewhere_is_left_alone_and_reported` | Unchanged, and in `conflicts` |
| `platform_option_limits_the_links` | With `Claude` only: no `.github/skills/` |
| `new_skill_is_linked_on_the_next_run` | A folder added under `.workbench/skills/` is in `linked`, the others in `kept` |
| `folder_without_skill_md_is_not_linked` | No link for it |
| `missing_skills_folder_links_nothing` | An empty report, and no error |

**Commit:** `feat(config): link the shared skills for AI platforms`

## Done when

- `load` returns a `Config` for the Acme configuration and for `templates/config.yml`.
- Every rule from 1 to 13 has a test that breaks only that rule.
- `init` creates the folder layout of [modes.md](../modes.md#what-init-creates).
- `link_skills` links every shared skill for Claude Code and GitHub Copilot, and never writes over what is there.

## Left open

- **The text of the two skills.** Task 5 needs real content for `workbench` and `python`. A rough draft of the `workbench` skill is in `templates/skills/workbench/SKILL.md`, tagged `TO_REFINE`. It is how Claude Code and GitHub Copilot learn the query commands (ADR 0024), so its text is tested by trying it with both. A rough draft of the Python skill is in `templates/skills/python/SKILL.md`, tagged `TO_REFINE`; the project owner will refine its conventions later ([#15](https://github.com/Revanthshalon/semantic-workbench/issues/15)).
- **The files under `ops/` are written and not read.** Reading and checking them is capability C13, in Release 3.
