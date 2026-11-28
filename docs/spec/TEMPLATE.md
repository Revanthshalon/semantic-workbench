# Spec template

Every module spec in this folder is written from this template. Copy everything below the line into `SPEC-<module-id>.md`, keep every heading in the same order, and replace each instruction in *italics*. A heading with nothing to say keeps the heading and the line `None.`

## How to write a spec

- **One module per spec.** The module id comes from [capability-map.md](./capability-map.md). A spec that needs a second id is two specs.
- **The spec is the source of truth.** Where it consolidates an older page in `docs/`, it copies what that page decided, rule ids and values unchanged. It never says "see domain-model.md" for a rule: the rule is written here. Links to older pages are for background only.
- **Every rule has an id and an Enforced column.** Keep existing ids (`N3`, `C10`, `X2`). A new rule takes the next free id of its group and is never renumbered. Enforced is one of:
  - **Type**: the Rust types cannot hold a broken value.
  - **Build**: building the value is refused.
  - **Graph**: checked by `Graph::validate` over a finished graph.
  - **Indexer**: kept by how the indexer runs. No value is checked.
  - **Command**: kept by how a command behaves, proven by a test that runs it.
  - **CI**: a CI job fails when the rule breaks, such as a lint in `Cargo.toml` or `cargo deny check`.
  - **Review**: only a reviewer can catch a break of the rule.
- **Exact values.** Names, paths, flags, exit codes, error codes and expected outputs are written in full, in code spans. "A suitable error" is not a value.
- **Every success criterion is a test.** Give the test's name and what it asserts. A criterion no test can check is an open question.
- **Plain language.** Short sentences, active voice, one term per thing. Terms come from [GLOSSARY.md](../GLOSSARY.md). A new term is added there in the same change.
- **No implementation detail the spec does not need.** Function bodies, private helpers and file splits belong in the implementation plan, not here. Public types and signatures belong here when another module depends on them.
- **Review before merge.** A spec is drafted, then reviewed by someone who did not draft it, against the pages it consolidates. The reviewer checks that no rule was lost, changed or invented.

---

# Spec: *Module name*: R*N*

Status: *draft | approved | implemented*
Module id: `*module-id*`
Capabilities: *ids from the capability map, such as `C1` to `C10`*
Depends on: *module ids, or `none`*
Consolidates: *the docs pages and ADRs whose decisions this spec now holds*

## Objective

*What this module does, for whom, and why, in three to six sentences. End with one sentence on what is true when it is done.*

## Interface

*What other modules use: public types, functions, commands, files or tool calls, with exact signatures, names and fields. For a command, its synopsis, flags, output on standard output and exit codes.*

## Rules

*Every rule the module keeps, one table per group.*

| Id | Rule | Enforced |
|---|---|---|
| *X1* | *One rule, in one or two sentences* | *Type, Build, Graph, Indexer, Command, CI or Review* |

## Behaviour

*How the module behaves in the cases a reader would ask about: the normal case first, then each edge case and failure, with the exact output or error. Use the Acme Shop workspace for examples.*

## Errors

| Condition | Error or code | Exit code |
|---|---|---|
| *What went wrong* | *The exact error type, code or message* | *0, 1 or 2, or `n/a` for a library* |

## Tech stack

*The crates this module uses, with the reason for each. A crate not already in `Cargo.toml` is an Ask-first boundary.*

## Commands

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
cargo deny check
```

*Add any command specific to this module.*

## Project structure

| Path | Holds |
|---|---|
| *`src/...`* | *What lives there* |

## Code style

*One short real snippet showing how this module's code is written: a constructor, an error, a test. Rules shared by every module live in [SPEC-ground-rules.md](./SPEC-ground-rules.md) and are not repeated.*

## Testing strategy

*Where the tests live, which level covers what (unit beside the code, store tests generic over the port, binary tests in `tests/`), and which fixture they use.*

## Boundaries

- **Always:** *what every change to this module does*
- **Ask first:** *what needs the owner's approval, such as a new crate, a new rule id, a change to a stored format or a changed id*
- **Never:** *what no change does*

## Success criteria

| Test | Asserts |
|---|---|
| *`rule_n3_refuses_service_in_project_scope`* | *The exact condition* |

## Out of scope (deferred)

| What | Deferred to | Why |
|---|---|---|
| *A capability or idea* | *R2, R3 or Later* | *One line* |

## Open questions

| Question | Blocks |
|---|---|
| *What needs a decision* | *Which rule or criterion waits on it* |
