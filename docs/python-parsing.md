# Python Parsing

Everything the graph captures from Python source, what it leaves out, and why. It covers the Python language itself, a binary built on no framework, and a binary built on FastAPI.

> **Proposed, not built.** This page widens what [step 5](./implementation-plan/step-5-python-parsing.md) reads. Where the two disagree, this page is the target and step 5 is the first slice of it. The changes this needs in the domain, the store and the capability map are listed under [Changes this needs elsewhere](#changes-this-needs-elsewhere).

Related pages: [domain-model.md](./domain-model.md) for the types and rules, [graph-model.md](./graph-model.md) for why the graph looks the way it does, [capability-map.md](./capability-map.md) for the rows this page fills (C14, I14 to I21, G11, G12). Terms are defined in [GLOSSARY.md](./GLOSSARY.md).

## How languages are added

**One language at a time, completely.** A language is done when every construct in its coverage table below is either read or listed as not read, with the reason. A second language starts only after that.

Each language has three layers:

| Layer | Applies to | Example |
|---|---|---|
| **Language core** | Every file of the language | Classes, functions, imports, calls, type annotations |
| **Framework profile** | Every file that imports the framework | FastAPI: apps, routers, routes, providers, models |
| **Binary framework** | One binary, decided before any code is parsed | From the configuration, the compose command or the entry file: `api` is a FastAPI binary whose app is `billing.api:app` |

## Principles

These decide every row below.

1. **A node holds only what its own file says.** The parser sees one file at a time. Anything that needs another file, such as what a base class is or which app mounts a router, is an edge made by resolution or a fact derived at query time. A file that has not changed therefore never needs to be parsed again because another file changed.
2. **A binary's framework is known before parsing.** The workspace layer decides it for each binary, together with the binary's app object. It reads the binary's entry in the configuration, then the compose command of the services that run the binary, then the binary's entry file. See [How a binary's framework is decided](#how-a-binarys-framework-is-decided).
3. **A profile's rules still run on any file that imports the framework.** A router module is never an entry, and it may sit in a library project with no binaries at all. So the configuration decides what a binary *is*, and the import decides which rules read a file. The two never disagree about a file: they answer different questions.
4. **Nothing is guessed.** A reference that the rules below cannot resolve stays unresolved. An edge from reading a file has the `TreeSitter` provenance. An edge from types carried from callers has its own provenance, `Flow`, so a reader can tell the two apart.
5. **Deterministic.** The same files give the same nodes, ids and edges, in every run and on every machine.
6. **Read every file, then analyse from each entry.** Reading never depends on where a file is reached from. Analysis runs over the finished graph and never reads a file again. See [How the graph is built](#how-the-graph-is-built).

## How the graph is built

Two stages, inside one index and one transaction (ADR 0003).

```
Stage 1  read every file         file by file, keyed by content hash
           → nodes, Contains edges, unresolved references,
             call sites, local bindings, file records

Stage 2  analyse from each entry over the graph, no file is read again
           2a  resolve                 references → edges              TreeSitter
           2b  carry types from callers parameter types → more edges    Flow
           2c  reach                   which roots may run each node
```

### Stage 1: read every file

**What is read.** Every file the walk of [step 5](./implementation-plan/step-5-python-parsing.md#task-1-choose-the-files-to-read) returns, whether or not any binary reaches it. That means every file not excluded by `.gitignore`, the fixed folders or `exclude`.

**When a file is read again.**
- Its content hash differs from its record.
- Its record says `GrammarUnavailable`.
- `--force` is given.
- `replace_file` or `remove_file` returns it because something it referred to is gone.

Files are independent of each other, so they can be read in parallel.

**What one file gives.** All of it comes from that file alone (principle 1):

| Output | Holds | Used by |
|---|---|---|
| Nodes | Every definition in [Definitions](#definitions-which-nodes-a-python-file-gives), with its [details](#details-what-each-node-carries) | Everything |
| `Contains` edges | Nesting, from the `File` down | The tree, rules T1 to T5 |
| Unresolved references | Every row of [References](#references-which-edges-a-python-file-gives), each with its name as written, kind and site | 2a |
| Call sites | For each call: the node it is in, its site, the callee as written (`process`, `self.repo.save`, `models.Invoice`), and each argument's position or keyword with its shape | 2b |
| Local bindings | For each name assigned in a function: the function, the name, the shape of the value, and whether it is assigned once | 2a rule 3, 2b |
| A file record | Project, path, content hash, language, parse status | Incremental reading, `files`, `status` |

**The shape of a value or an argument** is one of these, read from the syntax alone:

| Shape | Written as | Example |
|---|---|---|
| `New(name)` | A call of a name, which may turn out to be a class | `Invoice(...)`, `models.Invoice(...)` |
| `Call(name)` | The same syntax. Resolution decides whether it is `New` or a call of a function | `make_invoice()` |
| `Name(name)` | A bare or dotted name | `repo`, `self.repo`, `settings` |
| `Literal(kind)` | A string, number, bytes, bool, `None`, list, dict, set or tuple literal | `"x"`, `3`, `[]` |
| `Other` | Anything else | `a + b`, `f()[0]`, `await x`, a lambda |

`New` and `Call` are kept as one shape at read time, because the parser cannot know whether a name is a class. They are listed apart here only to show what resolution turns them into.

**Why every file is read, and not only what an entry reaches:**

1. **Code loaded by name is invisible to a walk.** `uvicorn "billing.api:app"`, `importlib.import_module(...)`, plugin entry points and Celery autodiscovery load modules by a string. A walk from the entry never sees them, and the graph would not say they are missing. Reading every file cannot miss them.
2. **Libraries would be read in part.** `shared-api` has no binary. Only what another project imports would be indexed, and `search` for anything else would find nothing.
3. **Tests, scripts and migrations would vanish.** "What breaks if I rename `Invoice`?" must name `tests/test_invoice.py`.
4. **Incremental reading would break.** One changed file is one read, by its content hash. With a walk, adding one import changes which files are reachable, so each binary's reachable set would have to be tracked and walked again.
5. **Nothing would be saved.** A file reached by two binaries is read once either way.

### Stage 2a: resolve

Turns unresolved references into edges, with the `TreeSitter` provenance. Step 5's lookup order and the four rules under [Resolution, beyond step 5](#resolution-beyond-step-5) apply, in that order. A local binding of shape `Call(name)` becomes `New` when the name resolves to a class. When the name resolves to a function with a `Returns` edge, the binding takes that class. The FastAPI profile's references (`Mounts`, `Handles`, `Injects`) are resolved here like any other.

### Stage 2b: carry types from callers

**The problem.** A parameter with no annotation leaves every call on it unresolved:

```python
# billing/worker.py (entry)
repo = InvoiceRepo()
process(repo)

# billing/services.py
def process(r):          # no annotation
    r.save()             # after 2a: unresolved
```

**The rule.** A parameter takes a type when **every** call site in the workspace that reaches it passes a value of the same project class. Then every reference inside the callee whose receiver is that parameter is resolved again with the type. Here `r` takes `InvoiceRepo`, and `r.save()` becomes a `Calls` edge to `InvoiceRepo.save` with the `Flow` provenance.

**The type of an argument at one call site** is:

| Argument shape | Its type |
|---|---|
| `New(C)`, with `C` resolved to a class of the workspace | `C` |
| `Call(f)`, with `f` resolved to a function that has a `Returns` edge to a class | That class |
| `Name(n)`, with `n` a parameter that has a declared type, or a type from this stage | That type |
| `Name(n)`, with `n` a local binding assigned once, whose value has a type by this table | That type |
| `Name(self.x)`, with `x` a field that has a declared type | That type |
| Anything else: a literal, `Other`, a name assigned more than once, a module, a class passed as a value | Unknown |

**When a parameter does not take a type.**
- Any call site passes an argument whose type is unknown.
- Two call sites pass different classes. A subclass and its base count as different. A test passing a `Mock` is enough to stop it.
- Any call site leaves the argument out, and the parameter's default is not of the same class.
- The callable is also used as a value: there is a `References` edge to it (a callback), an `Injects` edge (a provider), a `Handles` edge (a route handler), or it is decorated by a decorator that resolves to a node. Its real callers are then not all visible.
- The callable has no resolved call site at all.
- `*args` and `**kwargs`.

**How it runs.**
1. Rounds. In each round, every parameter's type is computed from the edges that exist at the start of the round. Then every reference inside an affected callee is resolved again.
2. A parameter goes from untyped to typed to conflicted, and never back. A parameter typed in one round that meets a disagreeing call site in a later round becomes conflicted. Every `Flow` edge that rested on it is removed.
3. The rounds stop when one changes nothing, or after 5 rounds. Because a conflicted parameter never takes a type again, the rounds always end.
4. The result depends only on the graph, not on the order in which nodes are visited.

**Every caller counts, not only those reached from an entry.** A function called from `worker.py` and from `tests/test_services.py` takes a type only if both pass the same class. A type that ignored the test would be wrong for the test.

**What is stored.** For each parameter that took a type: the parameter, the class, and how many call sites agreed. `node` on a parameter shows `inferred: InvoiceRepo (3 call sites)`. These records and every `Flow` edge are removed and computed again at every index.

### Stage 2c: reach

**Roots: where reach starts.**

| Root | From |
|---|---|
| A binary | Its entry `File` (`EntryPoint`) |
| A named module | A module named in a string that Stage 1 or the workspace layer found: a compose `command` (`uvicorn billing.api:app`, `python -m ledger.consumer`), a binary's `app`, a `uvicorn.run("billing.api:app")` call |
| A test | A file named `test_*.py` or `*_test.py`, a file under a folder named `tests`, and `conftest.py` |

**Edges followed, from a root outwards.**

| Edge | Why it means "may run" |
|---|---|
| `Imports`, to a `File` | Importing a module runs its module-level code |
| `Calls`, `Instantiates` | The callee runs. `Instantiates` also reaches the class's `__init__` |
| `References` | A function passed as a value is assumed to be called |
| `Overrides`, followed backwards | A call to a base method may run any override of it |
| `Decorates` | The decorator runs when the decorated node is defined |
| `Mounts`, downwards, then `Handles` | An app serves its routers' routes, and each route runs its handler |
| `Injects` | A route or provider runs its providers |

Module-level code of a reached `File` reaches what it calls. A reached class does not reach its methods by itself; each method is reached through its own calls.

**What is stored.** For each code node, the roots that reach it. It is computed again at every index, and replaced in the same transaction.

**Where it shows.**
- `node` on any code node: `reached by: api, worker, tests`.
- `node` on a binary: how many files and nodes it reaches.
- `files --unreached`: files that no root reaches.
- `impact` already walks towards binaries; reach lets it say which binaries run each step.

**What "unreached" means.** Not reached through *resolved* edges. An unresolved call breaks the chain, so an unreached node may still run. `files --unreached` is a hint to look, never proof that code is dead.

### Incremental indexing with two stages

| Stage | When it runs again | Cost |
|---|---|---|
| 1 | Per file, by the four triggers above | One read per changed file |
| 2a | For references in changed files, and in files whose targets went away, as step 5 does | As step 5 |
| 2b | In full, at every index | Linear in call sites, times at most 5 rounds |
| 2c | In full, at every index | Linear in edges, times the number of roots, with one bit per root |

Running 2b and 2c in full keeps them simple and deterministic. Running them only from the changed nodes outward is Later.

### What the two stages lack

| Not covered | Why |
|---|---|
| Types from return values that are not annotated | Only `Returns` edges from annotations feed 2b. Inferring a function's return type from its body is Later |
| Types carried through containers: `repos = [InvoiceRepo()]`, then `repos[0].save()` | A list's element type is not tracked |
| Types carried through attributes set outside `__init__` and not annotated | Only annotated fields and the first `self.x = ...` give a field. That field has no declared type unless annotated |
| Callers outside the workspace | A library function called by code that is not indexed. 2b counts only the callers it sees, which is why its edges carry `Flow` and not `TreeSitter` |
| Calls through `getattr`, dicts of functions, `functools.partial` | No static form. `partial(f, ...)` gives a `References` edge to `f`, which reach follows, and 2b stops at it |
| Reach through code loaded by name in ways not listed as roots | Add the module as a binary, or wait for a profile that knows the loader |

## The language core

### Definitions: which nodes a Python file gives

| Node kind | From | Qualified name | Notes |
|---|---|---|---|
| `File` | Every `.py` file | Its path | Also the module. Python gets no separate `Module` node |
| `Class` | `class` | `<module>.<Outer>.<Name>` | Nested classes too |
| `Protocol` | A class whose base is `Protocol` imported from `typing` or `typing_extensions` in the same file | as `Class` | |
| `Enum` | A class whose base is `Enum`, `IntEnum`, `StrEnum`, `Flag` or `IntFlag` imported from `enum` in the same file | as `Class` | |
| `EnumMember` | An assignment in the body of an `Enum` | `<enum>.<NAME>` | |
| `Function` | `def` at module level, or inside a function | `<module>.<outer...>.<name>` | |
| `Method` | `def` directly inside a class | `<class>.<name>` | |
| `Property` | A method decorated with `@property`, or with `@<name>.setter` or `.deleter` | `<class>.<name>` | The getter, setter and deleter are one name, so they get ordinals 0, 1, 2 |
| `Parameter` | Each parameter of a function or method, except `self` and `cls` | `<function>.<param>` | `*args` and `**kwargs` included, named without stars |
| `Field` | An annotated name in a class body (`amount: Decimal`), a plain assignment in a class body, and the first `self.<name> = ...` in a method | `<class>.<name>` | One node per name, at its first appearance |
| `Constant` | A module-level assignment to a name in capitals, or one annotated `Final` | `<module>.<NAME>` | |
| `Variable` | Any other module-level assignment, or an annotated name with no value | `<module>.<name>` | `a, b = ...` gives two |
| `TypeAlias` | `type X = ...` (3.12), or `X: TypeAlias = ...` | `<module>.<X>` | A plain `X = Union[...]` stays a `Variable` |
| `Import` | Each name an `import` statement binds | `<module>.<bound name>` | |

Not nodes:

- **Variables local to a function.** There are too many, and they are rarely what a question is about. The FastAPI profile makes one exception: a local name bound to `FastAPI(...)` or `APIRouter(...)`, as in an app factory.
- **Lambdas, comprehensions and generator expressions.** A call inside one belongs to the node that encloses it.
- **The `if __name__ == "__main__":` block.** Its code belongs to the `File`, like any other module-level code.

The kinds `Struct`, `Interface`, `Trait`, `Union`, `Namespace`, `Module`, `Export` and `Component` are not used for Python.

**Conditional definitions.** A name defined in both branches of an `if`, or in a `try` and its `except`, gets two nodes, with ordinals 0 and 1. A reference resolves to the last one, as Python's own reading order does.

### Details: what each node carries

This follows the proposal that a node kind carries its own data, as an edge kind does. Each detail is read from the node's own lines.

| Detail | On | From | Python rule |
|---|---|---|---|
| `doc` | `Class`, `Protocol`, `Enum`, `Function`, `Method`, `Property`, `File` | The first statement, when it is a string | |
| `signature` | Callables and classes | The `def` or `class` line up to the colon, joined to one line | |
| `is_async` | Callables | `async def` | |
| `is_static` | `Method` | `@staticmethod` | |
| `is_abstract` | `Method`, `Property`, classes | `@abstractmethod`, or a base `ABC` | |
| `is_exported` | Module-level definitions | The name is in a literal `__all__`. With no `__all__`, every name not starting with `_` | |
| `visibility` | Every definition except `Parameter` | The name | `__name__` (dunder): public. `__name` or `_name`: private. Otherwise public. Python has no protected or internal |
| `decorators` | Callables and classes | Each decorator's dotted name as written, without `@` and without arguments, in source order | `@app.get("/x")` is kept as `app.get`. Flags such as `is_static` are set *as well*, so the list is always complete |
| `type_parameters` | Classes, callables, `TypeAlias` | `class Box[T]:` (3.12), or a base `Generic[T]` | |
| `return_type` | Callables | The `->` annotation, as written | |
| `declared_type` | `Parameter`, `Field`, `Variable`, `Constant` | The annotation, as written | |
| `default` | `Parameter`, `Field` | The default value, as written, cut at 80 characters | |

A detail that the language cannot express is refused when the node is built. A Python node with `visibility: protected` is a build error.

### References: which edges a Python file gives

The parser records each as an unresolved reference. Resolution turns it into an edge.

| Edge kind | From | Source node | Notes |
|---|---|---|---|
| `Contains` | Nesting | The enclosing node, or the `File` | Made directly, not through resolution |
| `Imports` | `import a.b`, `from a import b`, with or without `as`, relative or absolute | The `File` | `from x import *` gives one edge, to the module's `File` |
| `Calls` | A call expression | The node the call is in, or the `File` at module level | |
| `Instantiates` | A call that resolves to a class | as `Calls` | |
| `Extends` | A base in a `class` statement | The class | |
| `Implements` | A base that resolves to a `Protocol`, or to a class with an abstract method | The class | Replaces `Extends` for that base |
| `Overrides` | A method whose name is also a method of a resolved base class, searched up the chain | The method | When the bases resolve and none has the name, the reference is dropped instead of kept |
| `Decorates` | A decorator that resolves to a node | The decorator's node, to the decorated node | Decorators from outside the workspace, such as `staticmethod`, stay unresolved |
| `TypeOf` | A class named in the annotation of a `Parameter`, `Field`, `Variable` or `Constant`, including inside `Optional[...]`, `list[...]`, `X | None` and string annotations | The annotated node | One edge per class named |
| `Returns` | A class named in a return annotation | The callable | |
| `References` | A name used as a value and not called: passed as an argument, assigned, returned, a default, a dict value | The node it appears in | This is how a callback is reached: `Thread(target=work)`, `signal.signal(SIGTERM, stop)`, `executor.submit(job)` |
| `Exports` | A name in a literal `__all__` | The `File` | |

### Resolution, beyond step 5

Step 5's lookup order stays: names the file imported, then `self.<name>`, then the same file, then the project, then other projects through import names. This page adds four rules.

1. **Re-exports.** `from shared_api import Invoice`, where `shared_api/__init__.py` holds `from .models import Invoice`, follows the chain to the class in `models.py`. The chain stops after 8 steps, or when it comes back to a module it has already visited.
2. **Following annotations.** In `def pay(invoice: Invoice): invoice.total()`, the call resolves to `Invoice.total`, because the parameter is annotated with a class of the workspace. The same applies to `self.repo.save()` when the class annotates `repo: Repo`.
3. **One step of local inference.** In `x = Invoice(...)` followed by `x.total()` in the same function, the call resolves to `Invoice.total`, but only when `x` is assigned once in that function.
4. **Inherited members.** `self.save()` that is not found in the class is looked up in the resolved bases, in Python's own method resolution order.

Anything else with a receiver whose type is unknown stays unresolved: `obj.method()` with no annotation, `getattr`, a call through a dict.

## How a binary's framework is decided

The workspace layer decides it, in [step 4](./implementation-plan/step-4-workspace-indexing.md), before any code is parsed. The first of these sources that gives an answer wins:

| Order | Source | Gives | Example |
|---|---|---|---|
| 1 | The configuration: `binaries[].framework` and `binaries[].app` | The framework, and the app | `{name: api, entry: src/billing/main.py, framework: fastapi, app: billing.app:create_app}` |
| 2 | The compose `command` of a service that runs the binary | The framework, and the app | `uvicorn billing.api:app`, `fastapi run src/billing/api.py`, `gunicorn -k uvicorn.workers.UvicornWorker billing.api:app` |
| 3 | The entry file | The framework, and the app | It imports from `fastapi`, and binds `FastAPI(...)` to a name at module level, or defines a function that returns one |
| 4 | None of the above | `none`: a plain binary | Billing's `worker` |

The framework is set on a binary only, never on a project. A project's library files need no setting: the framework's rules read every file that imports it (principle 3).

Source 3 reads only the entry file, with the same tree-sitter grammar, and only its imports and module-level statements. It is cheap, and it runs again whenever the entry file's content hash changes.

**What is stored.** The binary's node carries `framework` (`fastapi` or `none`), `app` (the app's qualified name, such as `billing.api.app`) and `framework_source` (`declared`, `compose` or `entry`). `node` on a binary shows all three.

**When the sources disagree.** A higher source wins, and the indexer raises a warning:

| Warning code | Raised when | Subject |
|---|---|---|
| `FrameworkMismatch` | The configuration or the compose command names one framework, and the entry file clearly builds another, or names none while it builds an app | The binary |
| `FrameworkAppNotFound` | A FastAPI binary's `app` names nothing that the index found, or nothing that is a `FastAPI(...)` app or a function that returns one | The binary |
| `EntryCommandMismatch` | A compose command names a module other than the binary's configured `entry`, such as `python -m ledger.consumer` for an entry of `src/ledger/worker.py` | The binary |

**What it changes for parsing.**

- The app's node is known before resolution, so a route's chain of `Mounts` has a fixed end. A route belongs to every binary whose `app` its chain reaches.
- The plain-binary rules (main guard, `-m`, callbacks) are checked against binaries known to be plain, so a FastAPI binary's entry is not reported as "does nothing".
- A project whose binaries are all `none`, and whose files never import `fastapi`, runs the core alone.

**What it does not change.** The FastAPI rules still run on every file that imports `fastapi`, because of principle 3. Take `shared-api`, which has no binaries: if it defined an `APIRouter` that billing's app mounts, that router and its routes are read, and they belong to billing's `api` binary through the mount.

## Plain binary: no framework

A binary whose framework is decided as `none`. Typical examples are a worker, a consumer, a scheduled job or a command line tool. Billing's `worker` and ledger's `consumer` are both plain binaries.

### How it starts

| Construct | What the graph gets |
|---|---|
| Module-level code in the entry file | `Calls`, `Instantiates` and `References` from the entry `File` |
| `if __name__ == "__main__": main()` | The same: a `Calls` edge from the `File` to `main` |
| `asyncio.run(main())` | `Calls` to `main`. The call to `asyncio.run` stays unresolved |
| `python -m ledger.consumer` as the compose `command` | The binary's entry is the file `ledger/consumer.py`, or `ledger/consumer/__main__.py` for a package. The configuration still names the entry; the command is only a cross-check (see [Open points](#open-points)) |
| Callbacks: `Thread(target=f)`, `signal.signal(..., f)`, `atexit.register(f)`, `executor.submit(f)`, `parser.set_defaults(func=f)` | `References` to `f`, so `f` is reached from the entry |

So for a plain binary, "what code runs" is the walk from `Binary` through `EntryPoint` to the entry `File`, and on over `Calls`, `Instantiates`, `References` and `Imports`. The query layer already walks these edges, so no new command is needed.

### What a plain binary lacks

- **What it does at run time.** A consumer loop, a schedule or a retry policy is code like any other. The graph shows the calls, not what they mean.
- **Message handling.** Which topic a consumer reads is still a hand-written link ([C7](./capability-map.md#c-configuration)). Finding it in code is W11, Later.
- **Command line structure.** `argparse` subcommands are reached through `References`, but they are not nodes. Click and Typer would be profiles of their own (I19, Later).

## FastAPI binary

### When the profile runs

On every file that imports from `fastapi`, in any project. A file that does not is read by the core alone. A binary is a FastAPI binary when its framework is decided as `fastapi` (see [How a binary's framework is decided](#how-a-binarys-framework-is-decided)). Its `app` is where the walk up a route's mounts ends.

### What the profile reads

| Construct | Nodes | Edges | Node data |
|---|---|---|---|
| `app = FastAPI(...)`, at module level or inside a factory function | A `Variable` for `app` (a local one, for a factory) | `References` to a `lifespan=` function | Role `App` |
| `router = APIRouter(prefix="/invoices", dependencies=[Depends(auth)])` | A `Variable` for `router` | `Injects` from the router to `auth` | Role `Router`, with its `prefix` when it is a string literal or a constant from the same file |
| `@router.get("/{invoice_id}", response_model=Invoice, status_code=200, dependencies=[Depends(audit)])` on `async def get_invoice(...)` | A `Route`, child of the `File` | `Mounts` from the router to the route. `Handles` from the route to `get_invoice`. `Returns` from the route to `Invoice`. `Injects` from the route to `audit` | `method: GET`, `path: "/{invoice_id}"`, `status_code: 200`, `tags` |
| `.post`, `.put`, `.patch`, `.delete`, `.head`, `.options`, `.trace` | as above | as above | The method |
| `@router.api_route("/x", methods=["GET", "POST"])` | One `Route` per method | as above | |
| `@router.websocket("/ws")` | A `Route` | as above | `method: WEBSOCKET` |
| `router.add_api_route("/x", handler, methods=[...])` | One `Route` per method | `Handles` to `handler` | |
| A handler parameter `db: Session = Depends(get_db)`, or `Annotated[Session, Depends(get_db)]`, or `Security(...)` | The `Parameter` (core) | `Injects` from the handler to `get_db`. The same inside a provider, so a chain of providers is followed | |
| A handler parameter with `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` or `File()`, or named in the route's path | The `Parameter` (core) | `TypeOf` (core) | `source`: path, query, header, cookie, body, form or file. Left empty when nothing says |
| `app.include_router(invoices.router, prefix="/v1")` | | `Mounts` from `app` to the router, with `prefix: "/v1"` | |
| `app.mount("/admin", admin_app)`, where `admin_app` is a FastAPI app | | `Mounts` with the prefix | |
| `@app.middleware("http")` | | `Decorates` (core) | Role `Middleware` on the function |
| `app.add_middleware(TimingMiddleware)` | | `References` from `app` to the class | |
| `@app.exception_handler(NotFound)` | | `References` from the handler to `NotFound` | Role `ExceptionHandler` |
| `@app.on_event("startup")` or `("shutdown")` | | | Role `LifecycleHook` |
| `class Invoice(BaseModel)`, with `BaseModel` imported from `pydantic` in the same file | The `Class`, and a `Field` per annotated name (core) | `TypeOf` from each field (core) | Role `Model` |
| `background_tasks.add_task(send_receipt, ...)` | | `References` to `send_receipt` (core) | |

**A route's qualified name** is its handler's qualified name, then `@`, the method and the local path: `billing.routes.invoices.get_invoice@GET /{invoice_id}`. Its display name is `GET /{invoice_id}`. All of this is known in the route's own file, so the id stays stable. Two decorators on one handler with the same method and path get ordinals.

**A route's full path** is derived at query time. The walk follows `Mounts` from the route up to an app and joins the prefixes: `/v1` + `/invoices` + `/{invoice_id}`. A router mounted in two places gives two full paths. The path is not stored on the node, because a change to a prefix in `api.py` would otherwise mean rewriting route nodes in other files. See [Open points](#open-points).

**Which binary serves a route** is every FastAPI binary whose stored `app` is the app that the route's mounts lead to.

**Roles** are stored only when the node's own file shows them. A function becomes a provider because some route injects it, so "provider" is derived from incoming `Injects` edges and never stored. A class that extends a project model, instead of `BaseModel` directly, is a model by its `Extends` chain, also derived.

### What the FastAPI profile lacks

| Not read | Why |
|---|---|
| Paths and prefixes that are not string literals or constants from the same file, such as `prefix=settings.API_PREFIX` | Their value exists only at run time. The route gets `path: None` and is still a node |
| Routes made in a loop, or from data | No static form to read |
| `dependencies=` and `prefix=` passed to `include_router` beyond the prefix | Providers attached at mount time apply to routes in another file. `prefix` is read; `dependencies` and `tags` there are not |
| Starlette routes built as a list (`Route("/x", endpoint)`), `APIRoute` subclasses, class-based views | Other shapes, for a later profile |
| `StaticFiles` and other non-FastAPI mounts | Not code in the workspace |
| The OpenAPI document, response classes, CORS and security scheme settings | Configuration of the running app, not structure |
| Pydantic `Field(...)` constraints, validators as rules, `model_config` | The field and its type are read. Its validation rules are not |
| Which client calls a route | A link still targets a service (C7). Making a route the target of a link, and finding HTTP calls in code (W11), are Later |

## Coverage at a glance

| Construct | Step 5 today | This page | Not read |
|---|---|---|---|
| Classes, functions, methods, properties | Yes | Yes | |
| Protocols, enums and their members | | Yes | |
| Parameters, fields, type aliases | | Yes | |
| Constants and module variables | Yes | Yes | Function-local variables |
| Doc strings, signatures, `is_async`, decorators | Yes | Yes | Decorator arguments, except where a profile reads them |
| `is_static`, `is_abstract`, `is_exported`, visibility, type parameters, annotations, defaults | | Yes | |
| Imports, relative and star | Yes | Yes | |
| Re-exports through `__init__.py` | | Yes | |
| Calls and instantiation | Yes | Yes | Calls on receivers whose type is unknown |
| Calls through annotated parameters and fields, and one step of local inference | | Yes | Deeper type inference |
| Calls through parameters typed by their callers (2b) | | Yes, as `Flow` | Callers that disagree, callables used as values, containers, unannotated returns |
| Which binaries and tests may run each node (2c) | | Yes | Code reached only through unresolved calls |
| Base classes | Yes | Yes, as `Extends` or `Implements` | |
| Overrides | | Yes | |
| Type references in annotations | | Yes | |
| Functions used as values (callbacks) | | Yes | Through attributes of unknown objects |
| `__all__` | | Yes | A computed `__all__` |
| Conditional and repeated definitions | Yes | Yes | |
| `if TYPE_CHECKING:` imports | As ordinary imports | As ordinary imports | Marking them as type-only (see [Open points](#open-points)) |
| Dynamic code: `getattr`, `importlib`, monkey patching, metaclasses, `exec` | | | All of it |
| Code outside the workspace: the standard library and installed packages | | | Not indexed. References into it stay unresolved |
| Stub files `.pyi`, notebooks, Cython | | | Later |
| Plain binary: start, main guard, `-m`, callbacks | Partly (module-level calls) | Yes | Run-time behaviour |
| FastAPI: apps, routers, routes, mounts, providers, parameter sources, models, middleware, hooks | | Yes | See the table above |
| Other frameworks: Flask, Django, Celery, Click, Typer, pytest fixtures | | | Later, each a profile (I19) |

## Acme Shop, with FastAPI

The fixture's Python source grows as follows. The workspace layer does not change.

```
billing-api/src/billing/
├── api.py              app = FastAPI(); app.include_router(invoices.router, prefix="/v1")
├── routes/invoices.py  router = APIRouter(prefix="/invoices")
│                       @router.get("/{invoice_id}", response_model=Invoice)
│                       async def get_invoice(invoice_id: int, db: Session = Depends(get_db))
├── db.py               def get_db(): ...
└── worker.py           def main(): send_invoice(...);  if __name__ == "__main__": main()

ledger-api/src/ledger/
├── api.py              app = FastAPI(); @app.post("/entries") def add_entry(entry: EntryIn)
└── consumer.py         def run(): ...;  if __name__ == "__main__": run()
```

The question from [graph-model.md](./graph-model.md#walking-the-graph), "I am renaming a field on `Invoice`. What breaks?", now gets a sharper answer:

1. `Invoice` ← `Returns` ← Route `GET /{invoice_id}` in `routes/invoices.py`.
2. The route ← `Mounts` ← `router` ← `Mounts` (`/v1`) ← `app` in `api.py`. Full path: `GET /v1/invoices/{invoice_id}`.
3. `api.py` ← `EntryPoint` ← Binary `api` ← `Runs` ← Service `api` of stack `billing-api`.
4. Service `api` ← `ConnectsTo` (HTTP) ← Binary `admin` of `web-app`.

The answer names the endpoint whose response changes, not only the file that imports the class.

Stage 2 adds two things to the fixture:

```
billing-api/src/billing/
├── services.py         def process(r): r.save()
├── repo.py             class InvoiceRepo: def save(self): ...
└── worker.py           repo = InvoiceRepo(); process(repo)
billing-api/tests/
└── test_services.py    process(InvoiceRepo())
```

- **2b:** both call sites pass `InvoiceRepo`. So `r` takes `InvoiceRepo`, and `r.save()` becomes a `Flow` edge to `InvoiceRepo.save`.
- **2c:** `routes/invoices.py` is reached by `api` only. `services.py` is reached by `worker` and by the test `test_services.py`. `db.py` is reached by `api` through `Injects`.

## Changes this needs elsewhere

Nothing below is applied yet. Each change is made in its own page when this page is accepted.

| Page | Change |
|---|---|
| [domain-model.md](./domain-model.md) | Node kinds carry typed data per kind (`Callable`, `TypeDecl`, `Member`, `RouteData`), with the language capability check at build time, as proposed for the domain design. New fields: `declared_type`, `default`, `source` on `Parameter`. New `FrameworkRole`: `App`, `Router { prefix }`, `Middleware`, `ExceptionHandler`, `LifecycleHook`, `Model`. A route's qualified name, as above, as an exception to "the language's own dotted path" |
| [domain-model.md](./domain-model.md), [graph-model.md](./graph-model.md) | Three new code edge kinds, 22 → 25: `Mounts { prefix: Option<String> }`, `Handles`, `Injects`. A new graph rule for their ends: `Mounts` from an app or router to a router, app or route; `Handles` from a route to a function or method; `Injects` from a function, method, route or router to a function, method or class |
| [configuration-guide.md](./configuration-guide.md), [`templates/config.yml`](../templates/config.yml), [step 2](./implementation-plan/step-2-configuration.md) (applied) | Two optional fields on `binaries[]`: `framework` (`fastapi` or `none` for Python, `angular` or `none` for TypeScript) and `app` (`module:attribute`, as uvicorn writes it). The project-level `framework` is removed; `framework: angular` moves onto each binary. Check rule 5 grows: a binary's framework suits its project's language, and `app` is given only with `fastapi` and has the form `module:attribute` |
| [domain-model.md](./domain-model.md) | A `Binary` carries data: `framework`, `app`, `framework_source`. Three new warning codes: `FrameworkMismatch`, `FrameworkAppNotFound`, `EntryCommandMismatch` |
| [step 4](./implementation-plan/step-4-workspace-indexing.md) | A new task: decide each binary's framework from the three sources, then `none`, and raise the warnings |
| [domain-model.md](./domain-model.md) | Rule R4 gains one exception: an `Overrides` reference whose bases all resolved, and none has the name, is dropped instead of kept |
| [domain-model.md](./domain-model.md) | Language: the `Project` node carries `language`, declared by the configuration. The file record keeps `language`, detected from the file. Code nodes have no `language`; a code node's language is its file's. The language check on node details reads the language from the file being parsed |
| [domain-model.md](./domain-model.md) | Two new records from Stage 1, part of a parsed file: `CallSite { from, site, callee, arguments: [{ position or keyword, shape }] }` and `LocalBinding { in, name, shape, assigned_once }`, with `Shape` as in [Stage 1](#stage-1-read-every-file). Two derived records from Stage 2, replaced at every index: `InferredType { parameter, class, call_sites }` and `Reach { node, root }`, with `Root` a binary, a named module or a test file |
| [domain-model.md](./domain-model.md), [graph-model.md](./graph-model.md) | A new provenance, `Flow`: resolved by carrying types from callers, correct when the workspace holds every caller. Rule E3: `Flow` is allowed on `Calls` and `Instantiates` only. Graph rules: an `InferredType` joins a `Parameter` to a `Class`, `Protocol` or `Enum`; a `Reach` joins a code node to a root that exists |
| [storage-model.md](./storage-model.md) | Tables `call_sites`, `local_bindings`, `inferred_types` and `reach`. The last two, and every edge with the `Flow` provenance, are deleted and written again in each index's transaction. `nodes.language` is filled for `Project` nodes only |
| [usage-guide.md](./usage-guide.md) | `node` shows `reached by` on code nodes, `inferred` on parameters, and reach counts on binaries. `files --unreached`. `callers` and `callees` mark `Flow` edges |
| [storage-model.md](./storage-model.md) | Columns for the new node data and the `Mounts` prefix. A new format version: the store is rebuilt, per ADR 0008 |
| [capability-map.md](./capability-map.md) | Rows I14 to I21, C14, G11, G12 (done with this page) |
| [step 5](./implementation-plan/step-5-python-parsing.md) | Its "What Release 1 reads" tables become the first slice of this page. New slices, below |
| [usage-guide.md](./usage-guide.md) | `node` on a route shows its full paths and its binary. `query --kind route` finds routes |

## Plan

Each phase ends in something tested on its own. The phases follow step 5 and use its parser, resolver and fixture.

| Phase | Delivers | Needs | Tested by |
|---|---|---|---|
| P0 | Binary framework: the two new configuration fields, the three sources in order, then `none`, the stored data, the three warnings | Step 2's 2C, step 4's 4B, 4E | One test per source. A higher source beats a lower one and raises `FrameworkMismatch`. A factory app needs the configuration. `python -m` against a different entry raises `EntryCommandMismatch` |
| P1 | Core definitions: every node kind and every detail in the tables above | Step 5's 5B, the typed node data | One test per row of the definitions and details tables, on strings of Python |
| P2 | Core references: `Implements`, `Overrides`, `TypeOf`, `Returns`, `References`, `Exports`. Call sites and local bindings, with their shapes | P1, 5C | One test per row of the references table. One test per shape. `x = A(); x = B()` gives a binding that is not assigned once |
| P3 | Resolution (2a): re-exports, following annotations, local inference, inherited members, `Call` bindings through `Returns` | P2, 5D, 5E | A re-export chain across projects. A cycle in re-exports ends. `invoice.total()` through an annotation. An unannotated receiver stays unresolved |
| P3b | Types from callers (2b): rounds, the conflict rule, the stop after 5 rounds, the `Flow` provenance, inferred-type records | P3, the `Flow` provenance | The `process(repo)` example gives a `Flow` edge. A second caller passing another class removes it. A callback stops it. A `Mock` in a test stops it. Two runs give the same edges. A chain of three calls types all three parameters |
| P4 | Plain binary: main guard, `-m` entries, callbacks; the derived "what code a binary runs" | P3 | The worker reaches `send_invoice` from its entry. `Thread(target=f)` reaches `f` |
| P5 | FastAPI profile: every row of its table | P3, the new edge kinds | One test per row. A factory app. A prefix from a constant. A prefix from `settings` gives `path: None` |
| P6 | Derived views: a route's full paths, and the binaries that serve it | P0, P5, step 6's walk | `GET /v1/invoices/{invoice_id}` from the fixture, served by billing's `api`. A router mounted twice gives two paths. A router in a library is served by the binary that mounts it |
| P6b | Reach (2c): the three kinds of root, the edges followed, reach records, `reached by`, `files --unreached` | P3b, P4, P5 | `routes/invoices.py` reached by `api` only. A test file is a root. A module named in a compose command is a root. An override is reached through its base. A file behind an unresolved call is listed as unreached |
| P7 | Acme Shop with FastAPI and Stage 2, end to end | P4, P6, P6b, 5G | The walk above, on the SQLite store. The 2b and 2c results in the fixture section. Indexing twice changes nothing. `validate` passes |

## Open points

1. **The `Flow` provenance, or `Heuristic`.** An edge from 2b is right when the workspace holds every caller. `Heuristic` already means "inferred, and may be wrong", and could be reused. Proposed: a new value, `Flow`, because 2b never guesses within what it can see, and a reader should be able to trust it more than a heuristic.
2. **A route's full path, stored or derived.** Derived keeps nodes file-local and indexing incremental. Storing it would let `search` find `GET /v1/invoices`. Proposed: derived, with `search` matching the local path and the method.
3. **FastAPI in Release 1, or right after it.** The example workspace does not need it to pass Release 1's done-when list. Proposed: Release 1, as a step 5b, because billing's `api` is the natural FastAPI binary of the example.
4. **New edge kinds, or reuse.** `Mounts`, `Handles` and `Injects` could be `References` with a role on the node. Proposed: new kinds, because a query that asks "which providers does this route use" should not have to filter `References`.
5. **Type-only imports.** An import under `if TYPE_CHECKING:` breaks type checking but not the running program. Marking it needs a flag on `Imports`. Proposed: Later.
6. **The compose command never replaces `entry`.** It can give a binary's framework and app, but the entry stays what the configuration names, and a disagreement is a warning. Proposed as written. The alternative is to let a command such as `uvicorn billing.api:app` stand in for `entry`, so a binary could be declared with less.

7. **The limit of 5 rounds in 2b.** Each round carries types one call deeper. Proposed: 5, and `status` reports when the limit stopped the rounds, so the number can be tuned on real workspaces.

**Settled:**

- **Language** lives on the `Project` node (declared) and on the file record (detected). Code nodes have none. A binary was considered, but a binary has one entry file inside its project, so it can never differ from the project. A file in another language inside a project, such as a script, is covered by its file record.
- **Read every file, then analyse from each entry.** Reading only what an entry reaches was considered. It would miss code loaded by name, half-read libraries, drop tests and break incremental reading. The accuracy it promised comes from analysis, which Stage 2 gives over the whole graph.
- **The framework is set on a binary only.** The project-level `framework` is removed, and `framework: angular` moves from `web-app` onto its binaries. A project default would save one line per binary, and would cost a precedence rule and one more way for sources to disagree.
