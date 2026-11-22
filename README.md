# Semantic Workbench

A command-line tool that reads a workspace of several projects and stores what it finds as a graph: the code inside each project, the projects themselves, the services that run them, and the links between all of these. AI coding tools query the graph through a UTCP manual that describes the command line. People query it through the same command line.

> **Status: design.** Nothing runs yet. The repository holds the module scaffold, the full design, and a plan for building it. There is no release.

## Why

An AI coding tool sees the files it is shown. It does not see how a workspace fits together: which project uses which shared library, which service talks to which, what a change in one repository breaks in another. Semantic Workbench gives it that picture.

```bash
workbench init                  # set up a workspace
workbench index                 # build the graph
workbench explore "how does an invoice get from billing to the ledger?"
workbench impact shared-api:shared_api.models.Invoice
```

The last command answers "what breaks if I change `Invoice`?" across every project: the code that imports it, the binaries that run that code, and the services that talk to them over a topic or an HTTP call.

## What makes it different

- **It works across projects.** One graph covers every project in the workspace, including projects cloned as separate repositories.
- **It knows what runs.** Services, networks, topics and queues are in the graph next to the code.
- **It says how it knows.** Every relationship records whether it was read from source, read from a manifest or a compose file, written by hand, or inferred.
- **Nothing changes behind your back.** The graph changes only when you run `workbench index`.
- **Local by default.** The first release makes no network calls and sends no code anywhere.

## Documentation

Start with the product vision. Every other page follows from it.

| Page | What it answers |
|---|---|
| [Product vision](docs/product-vision.md) | What is this, who is it for, and what is it not? |
| [Capability map](docs/capability-map.md) | What will the tool do? One row per capability |
| [Roadmap](docs/roadmap.md) | What ships when, and in what order is it built? |
| [Usage guide](docs/usage-guide.md) | Which commands and UTCP tools are there, and how are they used? |
| [Configuration guide](docs/configuration-guide.md) | How is `.workbench/config.yml` written? |
| [Example workspace](docs/example-workspace.md) | What does a real workspace look like, end to end? |
| [Modes, contexts and skills](docs/modes.md) | What are the modes of the UTCP manual, and what else does `init` write? |
| [Graph model](docs/graph-model.md) | Why does the graph look the way it does? |
| [Domain model](docs/domain-model.md) | Which types and rules are implemented and validated against? |
| [Storage model](docs/storage-model.md) | How is the graph kept in SQLite? |
| [Implementation plan](docs/implementation-plan/00-overview.md) | Who builds what, in which order, and what can be built at once? |
| [Decision records](docs/adrs/) | Which decisions were made, and why? |
| [Glossary](docs/GLOSSARY.md) | What does each term mean? |

Samples of every file a workspace holds are in [`templates/`](templates/).

## What is planned

| Release | Delivers |
|---|---|
| 1 | Python code, the whole workspace layer, SQLite storage, the command line, and the UTCP manual in its `developer-support` mode |
| 2 | TypeScript and Angular |
| 3 | The `operational-support` mode: read-only tools that look into a deployed context to find the cause of an incident |

No dates are set. The [roadmap](docs/roadmap.md) has the detail.

## Repository layout

```
docs/                 the design, the plan and the decision records
templates/            samples of the files `workbench init` writes
src/
├── domain/           the types and rules of the graph; depends on nothing
├── config/           finding, reading and checking the workspace configuration
├── ports/            what the core needs from the outside
├── use_cases/        indexing, and every query
├── adapters/
│   ├── driven/       the SQLite store, the file system, the parsers
│   └── driving/      the command line and the UTCP manual
└── main.rs           wiring
```

The code is Rust, edition 2024, and needs Rust 1.100 or later. The binary is called `workbench`.

## Contributing

The work is cut into slices that can be built side by side, each one pull request. Pick one from the [slice table](docs/implementation-plan/00-overview.md#the-slices) whose needs are already merged.

Before every commit:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked
```

CI runs the same three checks, a dependency audit and a coverage report. A few rules are stricter than usual and are enforced by the lints in `Cargo.toml`: no `unwrap`, no `panic`, no `unsafe`, no `todo!()`, and a doc comment on every public item.

A change that settles something hard to reverse gets a record in [`docs/adrs/`](docs/adrs/).
