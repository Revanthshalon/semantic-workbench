# Spec: Ground rules: R1

Status: draft
Module id: `ground-rules`
Capabilities: `X1` to `X8`, `X10`
Depends on: none
Consolidates: [capability-map.md](../capability-map.md) §X, [implementation plan overview](../implementation-plan/00-overview.md) ("Global constraints", "Before every commit", "Where code goes", "Crates to add", "Rules for a slice", "How a task is written", "The test workspace"), `Cargo.toml`, `rust-toolchain.toml`, `deny.toml`, `Makefile`, `.github/workflows/ci.yml`, [ADR 0003](../adrs/0003-the-graph-changes-only-on-index.md), [ADR 0022](../adrs/0022-ai-tools-reach-the-graph-through-utcp.md) (standard error), [ADR 0011](../adrs/0011-mcp-modes-and-read-only-operations-over-ssh.md) (network)

## Objective

This module holds the rules that every `workbench` command and every module of the code keeps. It has no code of its own. Its users are the people and agents who write the other modules, and the reviewers who check them. It sets how a command uses standard output, standard error and exit codes, what `index` skips, how indexes and queries share the store, and what the tool never does, such as reach the network. It also sets the rules of the Rust code: the lints, the toolchain, where code goes, which crates may be added, and how a change is tested and committed. When it is done, every other spec can say "the ground rules apply" and repeat none of them, and CI refuses a change that breaks a rule a tool can check.

## Interface

This module has no Rust types and no functions. It hands every other module this contract.

**Exit codes**, for every command:

| Code | Meaning |
|---|---|
| `0` | The command did what was asked. `index` with warnings, or with files that were skipped because they failed to parse, still exits `0` |
| `1` | The command could not do it: no workspace found, an invalid configuration, a store that cannot be read, an index already running, a mode that is not available yet |
| `2` | The command line itself was wrong: an unknown flag, a missing argument, no command, a mode name that is not a mode |

**Streams**, for every command:

| Stream | Holds |
|---|---|
| Standard output | Results, and nothing else. `workbench manual` writes only the manual |
| Standard error | Messages, warnings and progress. Empty when a command given `--json` succeeds, unless `-v` is given |

**Files and folders:**

| Path | Rule |
|---|---|
| `.workbench/.gitignore` | Written by `init`. One line: `graph.db*` |
| `.workbench/config.yml` | Meant to be committed |
| `.workbench/graph.db` | The graph file, the default of `storage.path`. Not committed |
| `.git`, `node_modules`, `.venv`, `.workbench` | Never read by `index`, with or without a `.gitignore` |

**The checks**, run before every commit and by CI:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
```

A commit that changes `Cargo.toml` or `Cargo.lock` also runs `cargo deny check`. CI also runs `cargo deny check` and `cargo tarpaulin --config tarpaulin.ci.toml --locked`. `make ci` runs all five locally, with the same flags.

## Rules

### Behaviour of every command (X)

| Id | Rule | Enforced |
|---|---|---|
| X1 | The graph changes only when `workbench index` is run. No query, and no UTCP tool, re-indexes. A query opens the store read-only and never writes to it. `index`, with or without `--force`, is the only command that writes the store | Command |
| X2 | Results go to standard output. Messages, warnings and progress go to standard error. `workbench manual` writes only the manual to standard output. With `--json`, a command that succeeds writes nothing to standard error, unless `-v` is given: with `-v` it may write messages to standard error, and standard output stays one clean JSON document | Command |
| X3 | Exit code `0` for success, `1` for a failure such as a bad configuration or an unreadable store, `2` for a wrong command line | Command |
| X4 | `index` skips what `.gitignore` excludes, plus `.git`, `node_modules`, `.venv` and `.workbench`, and anything a project's `exclude` patterns match. A `.gitignore` in a subfolder applies below it | Indexer |
| X5 | One `index` at a time per workspace. Queries keep working while an index runs, and see the graph as it was until the index finishes. An index that fails changes nothing. One index is one write transaction. While one index runs, a second cannot open its transaction and stops with exit code `1` and `an index is already running` | Indexer |
| X6 | `init` writes `.workbench/.gitignore` so the graph file is not committed. The file holds one line, `graph.db*`, which matches `graph.db`, `graph.db-wal` and `graph.db-shm`. The configuration file is meant to be committed | Command |
| X7 | No network calls and no telemetry in any Release 1 code path. From Release 3 the `operational-support` mode connects to the virtual machine a context names, and to nothing else. It connects only over SSH, read-only, to that machine. The cluster, the databases and the broker are reached through it. Each new crate is reviewed for network I/O before it is added | Review |
| X8 | macOS and Linux are supported. Windows is not. CI builds on Linux only, and nothing refuses a Windows build; `deny.toml` checks the four supported targets | Review |
| X10 | A file that fails to parse is skipped and logged. Indexing continues and still ends in success. The file gets a `File` node, a file record with status `Failed` and the parser's message, and no nodes below it. A file that is not UTF-8 is recorded as `Failed` the same way. Logged means the `Failed` record and one warning line on standard error. With `--json` there is no such line: the failure appears only in the JSON result | Indexer |

X9 is deferred: see [Out of scope](#out-of-scope-deferred).

### Rust code (GR)

| Id | Rule | Enforced |
|---|---|---|
| GR1 | The crate uses edition `2024` and `rust-version = "1.100.0"`. The toolchain is `channel = "stable"`, `profile = "minimal"`, with components `rustfmt`, `clippy` and `cargo` | CI |
| GR2 | There is one binary crate. The package is `semantic-workbench`, the binary is `workbench`, and its entry point is `src/main.rs`. There is no `src/lib.rs`, so tests in `tests/` can only run the binary | Review |
| GR3 | Unit tests sit beside the code they test, in a `#[cfg(test)] mod tests` in the same file | Review |
| GR4 | `clippy::unwrap_used` and `clippy::panic` are `deny` outside tests. `.clippy.toml` sets `allow-unwrap-in-tests`, `allow-expect-in-tests` and `allow-panic-in-tests` to `true`, so `unwrap`, `expect` and `panic!` are allowed in `#[test]` functions and `#[cfg(test)]` modules. `unsafe_code` is `deny` everywhere, tests included | CI |
| GR5 | A test may return `()` or `Result<(), Box<dyn std::error::Error>>` | Review |
| GR6 | `clippy::todo` is `warn`, and CI turns every warning into an error. No `todo!()` is ever merged, not even as a placeholder | CI |
| GR7 | `missing_docs` and `clippy::missing_docs_in_private_items` are `warn`. Every item outside `#[cfg(test)]` has a doc comment | CI |
| GR8 | `missing_debug_implementations` is `warn`. Every public type derives or implements `Debug` | CI |
| GR9 | `clippy::redundant_clone`, `clippy::large_enum_variant` and `clippy::missing_safety_doc` are `deny`. A variant that trips `large_enum_variant` holds its data in a `Box` | CI |
| GR10 | These clippy lints are `warn`, so they fail CI: the `perf` group (`priority = 1`), `trivially_copy_pass_by_ref`, `large_types_passed_by_value`, `clone_on_ref_ptr`, `implicit_clone`, `inefficient_to_string`, `str_to_string`, `needless_collect`, `large_futures` | CI |
| GR11 | CI sets `RUSTFLAGS=-D warnings`, `CARGO_INCREMENTAL=0` and `CARGO_TERM_COLOR=always`. `make` sets the same values unless the environment already does. Clippy runs with `-- -D warnings` | CI |
| GR12 | Code is formatted by `rustfmt`: `cargo fmt --all --check` passes | CI |
| GR13 | A module depends only on the modules its row allows in [Project structure](#project-structure). `src/domain` depends on nothing | Review |
| GR14 | Every crate passes `cargo deny check` against `deny.toml`. Licences allowed: `MIT`, `Unicode-3.0`, `Apache-2.0`, with `confidence-threshold = 0.9` and `unused-allowed-license = "warn"`. The crate's own licence is not checked: `[licenses.private] ignore = true`. Advisories: `yanked = "deny"`, `unmaintained = "all"`, `unsound = "all"`. Bans: `wildcards = "deny"`, `multiple-versions = "warn"`. Sources: only `https://github.com/rust-lang/crates.io-index`; `unknown-registry` and `unknown-git` are `deny`. Targets checked: `x86_64-unknown-linux-gnu`, `aarch64-unknown-linux-gnu`, `aarch64-apple-darwin`, `x86_64-apple-darwin`. The crate's own licence is `license = "MIT"` | CI |
| GR15 | Paths in the graph use `/`. The `graph-model` spec holds the full rule of `RelPath` | Build |
| GR23 | Paths in the configuration use `/` | Review |

### Working rules (GR)

| Id | Rule | Enforced |
|---|---|---|
| GR16 | Before every commit, the three checks under [Commands](#commands) pass. A commit that changes `Cargo.toml` or `Cargo.lock` also passes `cargo deny check` | Review |
| GR17 | A task is done in this order: commit the types of its **Produces** block, write its tests and see them fail, implement until they pass, run the three checks, commit with the message the task gives | Review |
| GR18 | A slice is one pull request and owns its files. Two slices in flight never edit the same file | Review |
| GR19 | A slice changes a shared `mod.rs` by adding its own `mod` line and nothing else | Review |
| GR20 | `Cargo.toml` gains crates only in slice C0, which adds every crate at once, so `Cargo.lock` never conflicts. The one exception: slices 1A to 1D, 2A and 2B need `thiserror`, `blake3`, `serde` and the YAML crate, and each of the four is added by the first of those slices that needs it | Review |
| GR21 | Commit messages follow Conventional Commits (`type(scope): summary` or `type: summary`, such as `feat(domain): add DomainError and RuleId`). The type is one of `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style`, `revert`. A change to the examples uses `docs(examples):`. They carry no AI attribution trailers, such as `Co-Authored-By` naming an AI tool | Review |
| GR22 | A changed name is changed everywhere. A slice that has to change a name handed between slices changes the implementation plan's list of those names in the same pull request | Review |
| GR24 | A pull request is merged only when every CI job is green, on its own | CI |
| GR25 | `src/main.rs` keeps `#![allow(dead_code)]` until slice 7D wires the adapters, and 7D removes it. No other `allow(dead_code)` is added | Review |

## Behaviour

**A query, normal case.** `workbench impact shared-api:shared_api.models.Invoice` on the indexed Acme Shop workspace opens `.workbench/graph.db` read-only, prints the answer on standard output and exits `0`. It writes nothing to the store, even when files have changed since the last index (X1). The answer's freshness says how many files changed; it does not re-index.

**`--json`.** `workbench impact ... --json` prints one JSON document on standard output. When it succeeds, standard error is empty, because a UTCP client captures the result with `2>&1` and any notice would break the JSON (X2). With `-v`, it may write messages to standard error; standard output stays the same JSON.

**`index`.** `workbench index` writes its summary to standard error and nothing to standard output (X2). It skips ignored files, the four fixed folders and what each project's `exclude` patterns match (X4). A Python file in `billing-api` that fails to parse gets a `File` node and a `Failed` record with the parser's message, and one warning line on standard error; the other files are indexed, and the command exits `0` (X10). With `--json`, no warning line is written: the failed file appears only in the JSON result.

**Two indexes at once.** A second `workbench index` started while one runs stops with exit code `1` and the message `an index is already running`. A query run meanwhile answers from the graph as it was (X5).

**An index that fails.** An error rolls the write transaction back. The store holds the graph of the last successful index (X5).

**`init`.** `workbench init` writes `.workbench/.gitignore` with the line `graph.db*`, beside `.workbench/config.yml` (X6). When `storage.path` puts the graph file elsewhere, `workbench` does nothing about it: the configuration guide tells the user to ignore that file themselves.

**A wrong command line.** `workbench` with no command prints the help and exits `2`. `workbench index --no-such-flag` exits `2`. `workbench manual --mode nonsense` exits `2` (X3).

**A mode that is not available.** In Release 1, `workbench manual --mode operational-support` and `--mode testing-support` exit `1`, with a message on standard error that the mode is not available yet (X3).

**A failure.** A query on a workspace that was never indexed exits `1` and says to run `workbench index`. An invalid configuration exits `1` and lists every problem on standard error (X3).

**A closed pipe.** `workbench files | head -1` ends quietly with exit code `0`, with no panic text on standard error.

**The network.** No Release 1 command opens a socket. Nothing is fetched, not even by `git`: a project's checkout is read from its own `.git` folder (X7).

## Errors

| Condition | Error or code | Exit code |
|---|---|---|
| Unknown flag, missing argument, no command, unknown mode | `Outcome::Usage(String)` | `2` |
| No workspace found from the flag, `WORKBENCH_WORKSPACE` or the current folder | `LocateError`, `no workspace found`; the text names `--workspace` and `WORKBENCH_WORKSPACE` | `1` |
| `--workspace` names a folder with no `.workbench/` | `LocateError::NotAWorkspace`, naming the folder | `1` |
| Invalid configuration | `ConfigError::Invalid(Vec<ConfigProblem>)`, every problem listed on standard error | `1` |
| `manual --mode operational-support` or `--mode testing-support` in Release 1 | A message that the mode is not available yet | `1` |
| Query before the first index | `StoreError::NotIndexed`, message names `workbench index` | `1` |
| A second index while one runs | `StoreError::IndexRunning`, `an index is already running` | `1` |
| Store written by another format version | `StoreError::WrongFormat { found }`, `store was written by another version`, says to run `workbench index --force` | `1` |
| A file fails to parse during `index` | Not an error: the file record has status `Failed` and the parser's message | `0` |
| Standard output closed by the reader | Not an error | `0` |

## Tech stack

This module adds no crate. It sets the policy for every crate.

In `Cargo.toml` now:

| Crate | Reason |
|---|---|
| `thiserror` (`2.0.21`) | Error types |
| `blake3` (`1.8.8`) | Node ids and content hashes |

Proposed, for slice C0 to add (GR20):

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
| `sqlx` with SQLite | The SQLite store. `sqlx` is asynchronous, so the store port and every use case are `async` |
| `tokio` | The runtime `main` builds to run the `async` use cases |
| `clap` with `derive` | The command line |

A crate not in `Cargo.toml` is an Ask-first boundary. When approved, it takes its latest release at the time of building, and it must pass `cargo deny check` (GR14).

Tools, not crates: `cargo-deny` (`cargo install cargo-deny --locked`) and `cargo-tarpaulin` (`cargo install cargo-tarpaulin --locked`).

## Commands

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
cargo deny check
```

```bash
make ci          # fmt, clippy, test, deny and coverage, with the CI flags
make fmt-fix     # cargo fmt --all
make coverage    # cargo tarpaulin --config tarpaulin.ci.toml --locked, report in target/coverage/
```

## Project structure

The scaffold is hexagonal. A module may depend only on the ones in its last column (GR13).

| Path | Holds | Depends on |
|---|---|---|
| `src/domain` | The types and rules of the graph model | nothing |
| `src/config` | Finding, reading and checking `.workbench/config.yml`, and what `init` writes | `domain` |
| `src/ports/outbound` | The traits the core needs from the outside: store, files, parsers, git | `domain` |
| `src/use_cases` | Indexing and every query | `domain`, `config`, `ports` |
| `src/adapters/driven/store/sqlite` | The SQLite store | `domain`, `ports` |
| `src/adapters/driven/store/memgraph` | A stub for a Memgraph store, behind the `memgraph` feature. Later: not built in Release 1 | `domain`, `ports` |
| `src/adapters/driven/fs` | Reading files, walking folders, reading `.git` | `domain`, `ports` |
| `src/adapters/driven/parse` | Reading source code, manifests and compose files | `domain`, `ports` |
| `src/adapters/driving/cli` | The command line | `use_cases`, `config` |
| `src/adapters/driving/utcp` | The UTCP manual | `use_cases`, `config` |
| `src/main.rs` | Wiring: builds the adapters and hands them to the use cases | everything |
| `tests/` | Tests that run the binary | the binary only |
| `tests/fixtures/acme/` | The Acme Shop workspace as files | |

## Code style

A value type has one private field and one way in: `parse` for a value read from text, returning `Result<Self, DomainError>`. Every item outside `#[cfg(test)]` has a doc comment. A test may return `()` and use `unwrap` or `expect`, or return a `Result` and use `?`.

```rust
//! The name of a node.

use std::fmt;

use crate::domain::error::{DomainError, ValueKind};

/// The short name of a node, such as `Invoice`. It is never empty.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Name(String);

impl Name {
    /// Reads a name from text, refusing empty text.
    pub fn parse(input: &str) -> Result<Self, DomainError> {
        if input.is_empty() {
            return Err(DomainError::Malformed {
                value: ValueKind::Name,
                input: input.to_owned(),
                reason: "a name is not empty",
            });
        }
        Ok(Self(input.to_owned()))
    }

    /// The name as text.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for Name {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

#[cfg(test)]
mod tests {
    use super::Name;
    use crate::domain::error::DomainError;

    #[test]
    fn empty_name_is_refused() {
        assert!(matches!(Name::parse(""), Err(DomainError::Malformed { .. })));
    }

    #[test]
    fn name_keeps_its_text() -> Result<(), Box<dyn std::error::Error>> {
        let name = Name::parse("Invoice")?;
        assert_eq!(name.as_str(), "Invoice");
        Ok(())
    }
}
```

The snippet shows the style only. The rules of `Name` belong to the `graph-model` spec.

## Testing strategy

- **Unit tests** sit beside the code in `#[cfg(test)]` modules (GR3). There is no `src/lib.rs`, so only they can reach private code.
- **Binary tests** sit in `tests/` and run `workbench` as a process with `assert_cmd`, on a copy of `tests/fixtures/acme/` in a temporary folder made with `tempfile`. Every X rule enforced by Command is proven here.
- **Store tests** are generic over `S: GraphStore` and run on `MemoryStore` and on SQLite alike. X5 and the format check are proven here, and X5 again in the binary tests.
- **Fixtures.** Two forms of the Acme Shop workspace: `fixtures::acme()`, a `Graph` value compiled only for tests, and `tests/fixtures/acme/`, the workspace as files. Slice 5G checks that indexing the files gives the value.
- **GR rules** enforced by CI are proven by the CI jobs `rust-fmt`, `rust-clippy`, `rust-test`, `rust-deny` and `rust-coverage`, not by tests.

## Boundaries

- **Always:** run the three checks before every commit, and `cargo deny check` when `Cargo.toml` or `Cargo.lock` changes; review each new crate for network I/O; give every item outside `#[cfg(test)]` a doc comment and every public type `Debug`; send results to standard output and everything else to standard error; exit `0`, `1` or `2` only; open the store read-only outside `index`; keep unit tests beside the code; write commit messages in Conventional Commits form.
- **Ask first:** a new crate in `Cargo.toml`; a licence added to `deny.toml`; a new rule id; a change to a stored format or to how ids are encoded; a change to CI, in `.github/workflows/ci.yml`.
- **Never:** `unwrap`, `expect` or `panic!` outside tests; `unsafe` or `todo!()` anywhere; a `src/lib.rs`; a network call or telemetry in Release 1; a query or UTCP tool that writes to the store; a merge with a red CI job; two slices in flight editing the same file; an AI attribution trailer in a commit message.

## Success criteria

Each test names its level: **unit** (beside the code, `#[cfg(test)]`), **store** (generic over `S: GraphStore`, run on `MemoryStore` and SQLite), **binary** (in `tests/`, runs `workbench`).

| Test | Asserts |
|---|---|
| `queries_cannot_write` | Binary. After running the twelve UTCP templates on the indexed fixture, the store file's content hash is unchanged (X1) |
| `results_go_to_stdout_and_messages_to_stderr` | Binary. `index` writes its summary to standard error, and nothing to standard output (X2) |
| `json_success_writes_nothing_to_standard_error` | Binary. Each query command with `--json`, on an indexed fixture, without `-v`: standard error is empty, also when `index --json` meets a file that fails to parse (X2, X10) |
| `manual_prints_one_json_document` | Binary. `workbench manual`: standard output parses as JSON, and standard error is empty (X2) |
| `exit_codes_are_0_1_and_2` | Unit. `Outcome::Done` maps to `0`, `Outcome::Failed` to `1`, `Outcome::Usage` to `2` (X3) |
| `no_command_is_a_usage_error` | Unit. `Cli::try_parse_from` with no command gives exit code `2` (X3) |
| `unknown_flag_exits_2` | Binary. Running the binary with an unknown flag exits `2` (X3) |
| `unknown_mode_is_a_usage_error` | Binary. `manual` with a name that is not a mode exits `2` (X3) |
| `operational_support_is_refused` | Binary. `manual --mode operational-support` exits `1`, with "not available yet" on standard error (X3) |
| `invalid_configuration_exits_1_and_lists_every_problem` | Binary. Exit code `1`, and both problems on standard error (X3) |
| `no_workspace_exits_1_and_names_the_flag` | Binary. Exit code `1`, and the message holds `--workspace` (X3) |
| `nothing_found_names_the_flag_and_the_variable` | Unit. The `LocateError` text contains `--workspace` and `WORKBENCH_WORKSPACE` (X3) |
| `flag_without_dot_workbench_is_an_error` | Unit. `--workspace` at a folder with no `.workbench/` gives `LocateError::NotAWorkspace` naming the folder (X3) |
| `query_before_index_says_to_index` | Binary. Exit code `1`, and `workbench index` in the message (X3) |
| `wrong_format_version_is_refused` | Store. With `format_version` set to `2`, opening the store is refused with `StoreError::WrongFormat`, and the message says to run `workbench index --force` (X3) |
| `closed_pipe_exits_quietly` | Binary. `files` piped into a reader that closes at once: exit code `0`, and no panic text |
| `gitignored_file_is_skipped` | Unit. With `build/` in `.gitignore`, `build/x.py` is absent (X4) |
| `fixed_folders_are_skipped` | Unit. `.git`, `node_modules`, `.venv` and `.workbench` are absent with no `.gitignore` (X4) |
| `nested_gitignore_is_honoured` | Unit. A `.gitignore` in a subfolder applies below it (X4) |
| `exclude_pattern_is_skipped` | Unit. `**/*_pb2.py` removes `a/b_pb2.py` and keeps `a/b.py` (X4) |
| `second_begin_index_is_index_running` | Store. While one writer from `begin_index` is held, a second `begin_index` gives `StoreError::IndexRunning` (X5) |
| `second_index_exits_1_while_one_runs` | Binary. With one index running, a second exits `1` with `an index is already running`, and a query still answers from the old graph (X5) |
| `failed_index_changes_nothing` | Store. A writer dropped without `commit` after `replace_file` leaves every read equal to what it was before (X5) |
| `gitignore_covers_the_store_and_its_wal_files` | Unit. The pattern in `.workbench/.gitignore` matches `graph.db`, `graph.db-wal` and `graph.db-shm` (X6) |
| `init_writes_all_eight_files` | Unit. All eight files `init` writes exist, `.gitignore` among them, and `written` lists them (X6) |
| `failed_parse_is_recorded_and_the_run_succeeds` | Unit. The file's record has status `Failed` with the message; the run returns `Ok`; the file is in `failed_files` (X10) |
| `failed_parse_writes_one_warning_line` | Binary. `index` on a fixture with one file that fails to parse: exit `0`, and exactly one warning line on standard error naming the file (X10) |
| `bytes_that_are_not_utf8_are_a_parse_error` | Unit. Bytes that are not UTF-8 give `Err(ParseError)`, so the file is recorded as `Failed` (X10) |
| CI jobs `rust-clippy` and `rust-test` | Build and pass on the `stable` toolchain with edition `2024` (GR1) |
| CI job `rust-clippy` | Passes with `-D warnings` over `--all-targets` (GR4, GR6 to GR10) |
| Every `rust-*` CI job | Runs with `RUSTFLAGS: -D warnings`, `CARGO_INCREMENTAL: 0` and `CARGO_TERM_COLOR: always` from the workflow's `env` (GR11) |
| CI job `rust-fmt` | `cargo fmt --all --check` passes (GR12) |
| CI job `rust-deny` | `cargo deny check` passes (GR14) |
| All five CI jobs | Green before a pull request is merged (GR24) |

## Out of scope (deferred)

| What | Deferred to | Why |
|---|---|---|
| X9: keep the graph current automatically, on use or with a file watcher | Later | Release 1 is manual only (ADR 0003). It would be added next to manual indexing, not in place of it |
| Network access for `operational-support` | R3 | The one part of Workbench that uses the network, over SSH to the context's virtual machine |
| Windows | Later | Not supported (X8) |
| A Memgraph store | Later | `src/adapters/driven/store/memgraph` and the `memgraph` feature stay as a stub |
| A coverage threshold | Later | `fail-under` in `tarpaulin.ci.toml` is commented out until real code and tests exist |

## Open questions

None.
