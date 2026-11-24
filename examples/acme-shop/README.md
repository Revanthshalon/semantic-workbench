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
| Inferred types, reach records, route paths, payloads | 2, 117, 3, 2 |
| Warnings | 2: `StackNamedAfterFolder`, `HttpCallWithoutLink` |

The checkout commits are made up, and every file's modification time is fixed, so that the output does not change from one run to the next.

## Where the spec was unclear

Building the graph showed these gaps in the spec. Each was settled one way in the scripts, as noted.

1. **Test functions.** Reach starts at a test file, but nothing in the code calls a `test_*` function; pytest does. Test reach starts at the file's test functions and fixtures as well.
2. **Module-level names.** `app.include_router(...)` gives a `Mounts` edge from the `app` variable, not from the file, and reach follows edges out of a `File`. A reached file also reaches its module-level variables and constants.
3. **Reach of `routes/invoices.py`.** `domain-model.md` says it is reached by `api` only. Ledger's `api` reaches it too, through `Requests` and then `Handles`, as the reach rules define.
4. **`set_defaults(func=f)`** gives both a `Handles` edge (argparse) and a `References` edge (plain-binary callbacks). Both are emitted. Without the `References` edge, `run_consume` is reached by no binary.
5. **SQLAlchemy models.** `class InvoiceRow(Base)`, with `Base = declarative_base()`, gives no `Extends` edge, because `Base` is a variable.
6. **A plain binary's `framework_source`** is not specified. It is `entry` here.
7. **The ledger stack** takes its name from the configuration, so it is `Declared`, as in `graph-model.md`.
8. **The fixture `repo`** gets an inferred return type, `InvoiceRepo` with evidence 1, which the example's tables do not list.
