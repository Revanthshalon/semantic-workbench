# Acme Shop: the complete graph

The [Acme Shop example](../../docs/example-workspace.md), worked through by hand into the full graph that Workbench is designed to build: every node, edge and record of [domain-model.md](../../docs/domain-model.md), after both stages of [python-parsing.md](../../docs/python-parsing.md). Workbench is not built yet. These scripts are a stand-in, written to show what its output will look like and to test the model against a realistic workspace.

## What is here

| Path | Holds |
|---|---|
| `src/` | The workspace: four projects, the shared compose file and `.workbench/config.yml`. The Python is the code of `example-workspace.md`, plus the definitions it only implies (`InvoiceRow`, `InvoiceIn`, `Settings`, `Base`, `EntryIn`, `BILLING_URL`) |
| `SCHEMA.md` | The JSON contract every script writes to, and how the spec is read where it leaves a choice |
| `lib/ids.py` | BLAKE3 in pure Python, checked against the official test vectors, and the id encoding of [step 1](../../docs/implementation-plan/step-1-domain-types.md#task-2-ids-and-hashes) |
| `workspace.py` | The workspace layer: 27 nodes, 54 edges, the `main.ts` file record, the workspace warning and the checkouts |
| `stage1.py` | Stage 1, with Python's `ast` instead of tree-sitter: code nodes, `Contains` edges, unresolved references, call sites, bindings, returns, file records |
| `stage2.py` | Stage 2: resolution (2a), types from callers (2b), route paths (2c), HTTP matches (2d), reach (2e), messages and commands (2f) |
| `merge.py` | Joins the three outputs, removes the duplicate entry-file nodes, checks the graph rules it can (N6, N7, E5, E6, T1 to T3, F1, F2, R1 and the record references), and writes `site/` |
| `out/` | The output of each script |
| `site/` | A viewer: `index.html`, with `graph.json` (the whole graph) and `sources.json` (every source file) |

## Regenerate

Python 3.11 or later, standard library only.

```bash
cd examples/acme-shop
python3 -I workspace.py && python3 -I stage1.py && python3 -I stage2.py && python3 -I merge.py
```

`merge.py` exits non-zero and lists the broken rules if the graph breaks one. The output is stable: running the four again gives identical files.

## View

`site/index.html` fetches its two JSON files by relative URL, so serve the folder rather than opening the file:

```bash
python3 -m http.server -d examples/acme-shop/site 8000   # then open http://localhost:8000
```

## The result

| | Count |
|---|---|
| Nodes | 178: 27 in the workspace layer, 151 code nodes |
| Edges | 287, of which 177 `Contains` |
| Unresolved references | 112, all into packages outside the workspace |
| Call sites, bindings, returns | 77, 33, 19 |
| Inferred types, reach records, route paths, payloads | 2, 197, 3, 2 |
| Warnings | 2: `StackNamedAfterFolder`, `HttpCallWithoutLink` |

The checkout commits are made up, and every file's modification time is fixed, so that the output does not change from one run to the next.

## How to use it

The scripts are an executable copy of the spec, and their output is the answer the Rust implementation must give for this workspace.

| When | Use |
|---|---|
| Writing `NodeId` (step 1, task 2) | `lib/ids.py` gives the expected id of any node, so `known_inputs_give_a_known_id` tests real values. The workspace node is `node_id("workspace", "", "", "workspace", "workspace", 0)` = `cf04ba99fe901113` |
| Writing the fixtures (step 1, task 10) | `site/graph.json` is the expected graph. `acme_workspace_layer()` must give its 27 workspace nodes and 54 workspace edges with the same ids; every node `acme()` holds must have the id given there |
| Writing the Python reader (step 5) | `out/stage1.json` is the expected stage 1 output per file: nodes, `Contains` edges, unresolved references, call sites, bindings and returns. `out/stage2.json` is the expected stage 2 output. Both use the same line and column convention as tree-sitter |
| Writing the queries (step 6) | `site/graph.json` answers the Acme questions the query tests ask: who reaches a node, which tests to run, which route a call matches |
| Changing the model | Change the docs, change the script that builds that part, and run the four scripts again. The diff of `site/graph.json` shows exactly what the change does to a real workspace, and `merge.py` says whether it breaks a rule |
| Reviewing a change | Open the viewer and follow a node through its edges and records. Every field of the model is on screen |

The scripts are a stand-in, not the product. They read Python with `ast` and know only what this workspace needs: where the spec and the scripts differ, the spec wins and the script is fixed.

## The spec gaps this graph exposed

Building the graph showed where the spec was silent or wrong. Each gap is now settled in the docs, and the scripts follow them.

| Gap | Settled as | Where |
|---|---|---|
| Nothing in the code calls a `test_*` function, so reach from a test file found nothing | Test reach starts at the file and at each test function and fixture in it | [python-parsing.md, stage 2e](../../docs/python-parsing.md#stage-2e-reach) |
| `app = FastAPI()` and its `Mounts` hang off a variable, and reach followed only edges out of a `File` | A reached file reaches its module-level variables and constants, and follows their edges | stage 2e |
| `from billing.services import process` reached the function, not the module, so `services.py` was unreached | An import reaches the `File` of the module, and the `__init__.py` of each package on the way, never the imported name | stage 2e |
| "`routes/invoices.py` is reached by `api` only" read as if ledger's `api` were excluded | Reach is per node. The file is reached by billing's `api` and `test_api.py`; its handler also by ledger's `api` | [domain-model.md, Reach](../../docs/domain-model.md#reach) and the fixture checks |
| `set_defaults(func=f)` fell under two rules | Both edges are intended: `Handles` from the command, `References` to `f` | [python-parsing.md, argparse](../../docs/python-parsing.md#command-line-binaries-argparse) |
| `class InvoiceRow(Base)` with `Base = declarative_base()` | Stays unresolved: there is no class to point at. SQLAlchemy 2's `DeclarativeBase` resolves | python-parsing.md, References, `Extends` |
| A plain binary's `framework_source` | `entry`, or `declared` when the configuration writes `framework: none` | domain-model.md, node data, and python-parsing.md, framework |
| A stack's origin when its name comes from the configuration | `Declared`. `Parsed` when the name comes from the compose file or its folder | [domain-model.md, Origin](../../docs/domain-model.md#origin) |
| The fixture `repo` takes an inferred return the examples did not list | Correct by the existing rule; now listed | example-workspace.md and the fixture checks |

Each is also a row in the [decisions of domain-model.md](../../docs/domain-model.md#decisions-made-on-this-page).
