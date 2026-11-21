# Python Parsing

Everything the graph captures from Python source, what it leaves out, and why. It covers the Python language itself, a binary built on no framework, and a binary built on FastAPI.

> **Decided, not built.** Every open point is settled by the project owner; see [Open points](#open-points). This page widens what [step 5](./implementation-plan/step-5-python-parsing.md) reads. Where the two disagree, this page is the target and step 5 is the first slice of it. The changes this needs in the domain, the store and the capability map are listed under [Changes this needs elsewhere](#changes-this-needs-elsewhere).

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

1. **A node holds only what its own file says.** The parser sees one file at a time. Anything that needs another file, such as what a base class is or which app mounts a router, is an edge made by resolution, or a record computed by stage 2. A file that has not changed therefore never needs to be parsed again because another file changed.
2. **A binary's framework is known before parsing.** The workspace layer decides it for each binary, together with the binary's app object. It reads the binary's entry in the configuration, then the compose command of the services that run the binary, then the binary's entry file. See [How a binary's framework is decided](#how-a-binarys-framework-is-decided).
3. **A profile's rules still run on any file that imports the framework.** A router module is never an entry, and it may sit in a library project with no binaries at all. So the configuration decides what a binary *is*, and the import decides which rules read a file. The two never disagree about a file: they answer different questions.
4. **Nothing is guessed.** A reference that the rules below cannot resolve stays unresolved. Every edge here has the `TreeSitter` provenance. An edge made by resolving a reference also records `resolved_by`, the rule that connected it, such as `import`, `annotation` or `flow`. So a reader can always tell an edge carried from callers from one read directly.
5. **Deterministic.** The same files give the same nodes, ids and edges, in every run and on every machine.
6. **Read every file, then analyse from each entry.** Reading never depends on where a file is reached from. Analysis runs over the finished graph and never reads a file again. See [How the graph is built](#how-the-graph-is-built).

## How the graph is built

Two stages, inside one index and one transaction (ADR 0003).

```
Stage 1  read every file         file by file, keyed by content hash
           → nodes, Contains edges, unresolved references,
             call sites, bindings, returns, file records

Stage 2  analyse from each root    over the graph, no file is read again
           2a  resolve                  references → edges        resolved_by: import, annotation, ...
           2b  carry types and text     inferred types → edges    resolved_by: flow
           2c  route paths              each route's full paths and the binaries that serve it
           2d  HTTP calls               client calls matched to routes → Requests edges
           2e  reach                    which roots may run each node
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
| Call sites | For each call: the node it is in, its site, the callee as written (`process`, `self.repo.save`, `models.Invoice`), and each argument's position or keyword with its shape | 2a, 2b, 2d |
| Bindings | One per assignment: where it is (the `File` for module level, the function or method, or the class for `self.<name> = ...` and class attributes), the name, its site and the shape of the value. A `for` target and a `with ... as` target are bindings too | 2a, 2b, 2c, 2d |
| Returns | One per `return` in a function or method, with the shape of its value. A bare `return`, and the end of a body that can be reached without a `return` or a `raise`, are returns of `None` | 2b |
| A file record | Project, path, content hash, language, parse status | Incremental reading, `files`, `status` |

**The shape of a value or an argument** is one of these, read from the syntax alone:

| Shape | Written as | Example |
|---|---|---|
| `Call(name)` | A call of a name. Resolution decides whether it creates an instance of a class or calls a function | `Invoice(...)`, `models.Invoice(...)`, `make_invoice()` |
| `Name(name)` | A bare or dotted name | `repo`, `self.repo`, `settings.API_PREFIX` |
| `Text(value)` | A string literal, with its value | `"/v1/invoices"` |
| `Template(parts)` | An f-string, `str.format` on a literal, or strings joined with `+`. Each part is text, a hole naming a bare or dotted name, or an unknown part | `f"{BASE}/v1/invoices/{invoice_id}"` gives text `/v1/invoices/` between the holes `BASE` and `invoice_id` |
| `Item(name, accessor)` | An element taken from a named value: a `for` target, a subscript, or iteration over `.values()`, `.keys()` or `.items()` | `for r in repos`, `repos[0]`, `for k, v in by_id.items()` |
| `Collection(kind, elements)` | A list, set, tuple or dict literal, or a comprehension, with the shapes of its elements (for a comprehension, of its one element expression) | `[InvoiceRepo(), InvoiceRepo()]`, `[Invoice(x) for x in rows]` |
| `Spread(name)` | `*name` or `**name` passed as an argument | `client.get(*args, **kwargs)` |
| `Literal(kind)` | Any other literal: number, bytes, bool or `None` | `3`, `None` |
| `Other` | Anything else | `a * b`, `f()[0]`, `await x`, a lambda |

The parser cannot know whether a called name is a class, so a call is one shape until resolution. A template keeps the names in its holes, so a later stage can fill them.

**Stub files.** A `.pyi` file is read like a `.py` file, for its definitions and annotations. Its nodes belong to its own `File`. References resolve to the `.py` definition when both exist, and reach never treats a stub as code that runs. A stub's annotations are used by 2a and 2b when the `.py` definition of the same qualified name has none (see [Resolution](#stage-2a-resolve)).

**Why every file is read, and not only what an entry reaches:**

1. **Code loaded by name is invisible to a walk.** `uvicorn "billing.api:app"`, `importlib.import_module(...)`, plugin entry points and Celery autodiscovery load modules by a string. A walk from the entry never sees them, and the graph would not say they are missing. Reading every file cannot miss them.
2. **Libraries would be read in part.** `shared-api` has no binary. Only what another project imports would be indexed, and `search` for anything else would find nothing.
3. **Tests, scripts and migrations would vanish.** "What breaks if I rename `Invoice`?" must name `tests/test_invoice.py`.
4. **Incremental reading would break.** One changed file is one read, by its content hash. With a walk, adding one import changes which files are reachable, so each binary's reachable set would have to be tracked and walked again.
5. **Nothing would be saved.** A file reached by two binaries is read once either way.

### Stage 2a: resolve

Turns unresolved references into edges, with the `TreeSitter` provenance. Step 5's lookup order and the four rules under [Resolution, beyond step 5](#resolution-beyond-step-5) apply, in that order. The FastAPI profile's references (`Mounts`, `Handles`, `Injects`) are resolved here like any other. Every edge made here records its `resolved_by`.

Three more rules use the bindings of stage 1:

1. **A name bound once.** A binding of shape `Call(name)` takes the class when the name resolves to a class, and the class of the function's `Returns` edge when it resolves to a function. So `x = Invoice(...)` followed by `x.total()` resolves, by `local_inference`. It works the same for a module-level name (`client = httpx.Client(...)`) and for a field set once (`self.repo = InvoiceRepo()`).
2. **`functools.partial`.** A name bound once to `partial(f, ...)` calls `f` when it is called. Its arguments follow the ones given to `partial`.
3. **Stubs.** When a parameter, field or function in a `.py` file has no annotation, and a `.pyi` file of the same module annotates the same qualified name, the stub's annotation is used, by `annotation`.

Names assigned more than once, parameters without annotation, loop targets and return values get their types in 2b.

### How an edge was resolved

`resolved_by` names the rule that connected a reference to its target. It is set on every edge made by resolution, and on no other edge. It is not part of an edge's identity.

| `resolved_by` | The rule |
|---|---|
| `import` | A name the file imported |
| `self_member` | `self.<name>`: a member of the class around the reference |
| `same_file` | A definition in the same file |
| `project` | The name as a qualified name in the project |
| `cross_project` | Another project, found through its import names |
| `re_export` | Followed through re-exports in `__init__.py` |
| `annotation` | The receiver's declared type: an annotated parameter or field |
| `local_inference` | A name bound once, in a function, at module level or as a field, to a call of a class or of a function with a `Returns` edge, or to `partial(f, ...)` |
| `inherited` | A member found in a resolved base class |
| `flow` | The receiver's class was inferred by 2b: a parameter typed by its callers, a return, a field, a name bound more than once, or an element of a collection |
| `framework` | A framework profile's reference: `Mounts`, `Handles` or `Injects`, including a pytest fixture |
| `route_match` | An HTTP client call matched to a route path (2d) |

When several rules could apply, the first in the lookup order wins and names the edge. The same idea is `resolvedBy` in codegraph, the project this design follows for its commands.

### Stage 2b: carry types and text through calls

Two things travel along the graph here: the **class** of a value, and the **text** of a value. Classes resolve calls that 2a could not. Text fills in paths: of HTTP calls made inside helpers (2d), and of route prefixes given as names (2c).

**The problem, for classes.** A parameter with no annotation leaves every call on it unresolved:

```python
# billing/worker.py (entry)
repo = InvoiceRepo()
process(repo)

# billing/services.py
def process(r):          # no annotation
    r.save()             # after 2a: unresolved
```

**Inferred types.** Four kinds of node can take a class, each only when all of its evidence agrees:

| Node | Takes a class when |
|---|---|
| A parameter | **Every** call site in the workspace passes a value of that class. Here `r` takes `InvoiceRepo`, and `r.save()` becomes a `Calls` edge to `InvoiceRepo.save` with `resolved_by: flow` |
| A function or method (its return) | Every return in its body, including the `None` of a body that can end without one, returns a value of that class |
| A field | Every binding of it, `self.x = ...` in any method or `x = ...` in the class body, is a value of that class |
| A name bound more than once, at module level or in a function | Every binding of it is a value of that class |

Once a node has a class, every reference whose receiver is that node is resolved again: calls on it, calls on its elements, and calls on its attributes.

**The class of a value** is:

| Shape | Its class |
|---|---|
| `Call(C)`, with `C` resolved to a class of the workspace | `C` |
| `Call(f)`, with `f` resolved to a function | `f`'s return type: its `Returns` edge, or its inferred type |
| `Call(g)`, with `g` bound once to `partial(f, ...)` | As `Call(f)` |
| `Name(n)` | `n`'s type: declared, or inferred here. `n` may be a parameter, a binding, a field (`self.x`), or a module-level name in any file, found through imports |
| `Item(n, accessor)` | The element type of `n`'s type (below) |
| `Collection(kind, elements)` | A collection of the elements' class, when every element has the same one |
| Anything else: a literal, `Spread`, `Other`, a module, a class passed as a value | Unknown |

**Element types.** For `Item(n, ...)`, from `n`'s declared or inferred type:
- `list[C]`, `List[C]`, `Sequence[C]`, `Iterable[C]`, `Iterator[C]`, `Collection[C]`, `set[C]`, `frozenset[C]`, `tuple[C, ...]`: iteration and a subscript give `C`;
- `dict[K, V]` or `Mapping[K, V]`: iteration and `.keys()` give `K`, `.values()` and a subscript give `V`, and `.items()` gives `K` and `V` to the two targets of `for k, v in`;
- a `Collection` value: its elements' class;
- `Optional[...]` and `X | None` are unwrapped first.

**When a parameter does not take a class.**
- Any call site passes an argument whose class is unknown.
- Two call sites pass different classes. A subclass and its base count as different. A test passing a `Mock` is enough to stop it.
- Any call site leaves the argument out, and the parameter's default is not of the same class.
- The callable is also used as a value: there is a `References` edge to it (a callback), an `Injects` edge (a provider or fixture), a `Handles` edge (a route handler), or it is decorated by a decorator that resolves to a node. Its real callers are then not all visible.
- The callable has no resolved call site at all.

`*args` and `**kwargs` that are passed straight on, as `f(*args, **kwargs)`, forward each caller's arguments by position and keyword to the inner call. A parameter reached that way is typed from the outer callers.

**Text.** The text of a value is worked out the same way, along the same edges:

| Shape | Its text |
|---|---|
| `Text(v)` | `v` |
| `Template(parts)` | The parts joined, with each hole filled by the text of the name it holds |
| `Name(n)`, with `n` bound once, at module level in any file or in the function, to a value with text | That text |
| `Name(obj.X)`, with `obj` an instance of a class whose field `X` has a text default, such as a pydantic `BaseSettings` | The default. A path built from it is marked as using defaults, because the environment may change it at run time |
| `Name(p)`, with `p` a parameter of the function the value is in | Not known here. Each caller's argument fills it (below) |
| Anything else | Unknown, written `{?}` |

**Text carried to callers.** When a value's text still has a hole that names a parameter of its function, the hole is filled at each call site of that function, with that call site's argument. This makes one copy of the value per call site, which belongs to the caller. If the caller's argument is itself a parameter, the copy is carried up again, at most `analysis.flow_rounds` call levels:

```python
# ledger/billing_client.py
BASE = "/v1"
def get(path):                                    # a helper
    return httpx.get(f"{BILLING_URL}{BASE}{path}")    # the path holds the parameter `path`

# ledger/clients.py
def fetch_invoice(invoice_id):
    return get(f"/invoices/{invoice_id}")         # fills `path`: /invoices/{?}
```

So the HTTP call in `get` gets one copy for the call in `fetch_invoice`: `GET {?}/v1/invoices/{?}`, belonging to `fetch_invoice`. 2d matches it, and the `Requests` edge starts at `fetch_invoice`, at its call to `get`.

A hole that names an attribute of `self` set in `__init__` from a parameter, such as a client class's base URL, is filled from the arguments of the call that created the receiver. The caller's receiver must be a name bound once to that call:

```python
class BillingClient:
    def __init__(self, base_url): self.http = httpx.Client(base_url=base_url)
    def invoice(self, invoice_id): return self.http.get(f"/invoices/{invoice_id}")

billing = BillingClient("http://billing:8000/v1")   # base path /v1
billing.invoice(7)                                  # GET /v1/invoices/{?}, from the caller
```

**How it runs.**
1. Rounds. In each round, every inferred type is computed from the edges and bindings that exist at the start of the round. Then every reference whose receiver changed is resolved again, and text is carried one call level further.
2. A node goes from untyped to typed to conflicted, and never back. A node typed in one round that meets disagreeing evidence in a later round becomes conflicted. Every edge with `resolved_by: flow` that rested on it is removed.
3. The rounds stop when one changes nothing, or after `analysis.flow_rounds` rounds: 10 unless the configuration says otherwise, and `0` turns 2b off. Because a conflicted node never takes a type again, the rounds always end. Stopping at the limit raises the `FlowRoundLimit` warning, which `status` shows with the number of nodes still changing.
4. The result depends only on the graph, not on the order in which nodes are visited.
5. A reference that 2b resolves stays in the store, marked as resolved by flow, instead of being removed (rule R4's second exception). At the next index its edge is deleted with every other `flow` edge, and 2b tries the reference again. Without this, a call resolved once by 2b would be lost at the next index.

**What a round is.** One pass of "give nodes a type from their evidence, then resolve the calls on them again". Each round carries types and text one call deeper:

```python
process(InvoiceRepo())          # worker.py: the caller passes a known class

def process(r):    save_all(r)  # round 1: r → InvoiceRepo (its argument is a call of a class)
def save_all(s):   persist(s)   # round 2: s → InvoiceRepo (its argument is r, typed only after round 1)
def persist(p):    p.save()     # round 3: p → InvoiceRepo, and p.save() resolves
```

A round can also resolve new calls, such as `r.helper()`, whose callees then get typed in the next round. Most code settles in 2 to 4 rounds. Hitting the limit makes nothing wrong: deeper nodes stay untyped, and their calls stay unresolved, as they would without 2b.

**Every caller counts, not only those reached from an entry.** A function called from `worker.py` and from `tests/test_services.py` takes a type only if both pass the same class. A type that ignored the test would be wrong for the test.

**What is stored.** For each node that took a class: the node, the class, and how many pieces of evidence agreed. `node` shows it, as `inferred: InvoiceRepo (3 call sites)` on a parameter or `inferred return: Invoice (2 returns)` on a function. These records and every edge with `resolved_by: flow` are removed and computed again at every index. Text is not stored: it shows in what it fills, a route path or a `Requests` edge.

### Stage 2c: route paths

A route's full path joins prefixes from other files, so it is computed here, over the graph, and stored as its own record. No route node is changed, so principle 1 holds, and `search` can find a route by its full path.

**How it is computed.** From each `Route`, follow `Mounts` upwards to every app it reaches, then join:

```
Route  GET /{invoice_id}         local path  "/{invoice_id}"
  ↑ Mounts (no prefix)
router (role Router)             router prefix "/invoices"
  ↑ Mounts (prefix "/v1")
app (role App)                   ← billing's api binary has app billing.api.app

full path: GET /v1/invoices/{invoice_id}, served by api
```

- Each step is one indexed lookup. A typical route is 2 or 3 steps.
- A router mounted in two places gives two full paths.
- A prefix or path given as a name, such as `prefix=API_PREFIX` or `prefix=settings.API_PREFIX`, takes its text from 2b. One taken from a settings default marks the record as using defaults.
- A part whose value exists only at run time, such as one read from `os.environ`, is written `{?}`, and the record is marked incomplete.
- An app that no binary names still gives full paths, with no binary.
- A cycle of mounts is cut at the first node seen twice.

**Providers and tags of a full path.** Along the same chain, 2c collects the providers that run for the path, and its tags:
- `Injects` from the route, and from its handler;
- `Injects` from each router and app on the chain, given when it was created (`APIRouter(dependencies=...)`, `FastAPI(dependencies=...)`);
- `Injects` given when a router was mounted (`include_router(..., dependencies=...)`). Such an edge has the site of the `include_router` call, the same as its `Mounts` edge, and it applies only to routes reached through that mount;
- the tags of the route, of each router, and of each mount.

**What is stored.** For each route, each binary and each full path: `RoutePath { route, binary, method, full_path, complete, uses_defaults, providers, tags }`. These records are replaced at every index, with the other results of stage 2.

**Where it shows.** `node` on a route lists its full paths and their binaries. `search "/v1/invoices"` finds the route. `impact` on a handler names the endpoints it serves.

### Stage 2d: match HTTP calls to routes

A Python client call that names a path is matched against the route paths of stage 2c. A match becomes a `Requests` edge from the node the call is in to the route. Only a workspace graph can do this: the caller and the route usually live in different repositories.

**Calls recognised.** These come from the call sites of stage 1:

| Client | Calls |
|---|---|
| `httpx` | `httpx.get`, `post`, `put`, `patch`, `delete`, `head` and `options`, `httpx.request(method, url)`, and the same methods on an `httpx.Client` or `httpx.AsyncClient` |
| `requests` | `requests.get` and the rest, `requests.request(method, url)`, and the same methods on a `requests.Session` |
| `aiohttp` | The same methods on an `aiohttp.ClientSession` |
| FastAPI's `TestClient` | The same methods on `TestClient(app)`, where `app` resolves to a node with role `App`, and `websocket_connect(path)` |
| `websockets` | `websockets.connect(url)`, matched to `WEBSOCKET` routes |
| The standard library | `urllib.request.urlopen(url)` and `urllib.request.Request(url, method=...)` |

`stream(method, url)` on `httpx` and its clients, and `ws_connect(url)` on an `aiohttp.ClientSession`, are recognised too.

A receiver is a client when its type, declared or inferred by 2a and 2b, is one of the client classes. That covers a client bound in the function, at module level, or as a field of your own client class.

**The method** is the function's name, or the first argument of `request(...)` when that is text.

**The path** comes from the URL argument:

| URL argument | Path |
|---|---|
| Text: `"/v1/invoices"` or `"http://billing:8000/v1/invoices"` | `/v1/invoices`: whatever follows the host |
| A template: `f"{BILLING_URL}/v1/invoices/{invoice_id}"` | `/v1/invoices/{?}`. A leading unknown part is taken as the scheme and host |
| Any other value | Its text, as 2b works it out: a constant from another file, a settings default, or a parameter filled at each call site of a helper |
| A value with no text at all, such as `os.environ["BILLING_URL"]` | `{?}`. The call is kept as an unmatched HTTP call, so it is still listed |

A client created with a `base_url` adds the path part of its text in front, wherever the client was created: in the function, at module level, as a field, or in `__init__` from an argument of the call that created your client object.

**Matching.** A call matches a route path when the methods are equal and the paths match segment by segment:
- equal text matches;
- a route's `{param}` matches any one segment;
- the call's `{?}` matches any one segment.

A query string and a trailing slash are ignored.

**Narrowing the candidates**, in this order:
1. `TestClient(app)`: only the routes of that app.
2. The calling binary, or else its project, declares `http` links: only routes served by binaries that the linked services run.
3. Otherwise, every route in the workspace.

A call made inside a helper is matched once for each copy 2b carried to a caller, and the edge starts at the caller, at its call to the helper. When exactly one route path is left, the call gives a `Requests` edge. Its data holds the method and the path as written in the call, and it has `resolved_by: route_match`. When more than one is left, or none, the call is stored as an unmatched HTTP call with its candidates, and `node` shows it. Nothing is guessed.

**Links stay declared** (ADR 0004, amended by ADR 0018). A match never creates a `ConnectsTo` link. Say a call matches a route served by a binary of another project, and the caller declares no `http` link to a service that runs that binary. Then the `HttpCallWithoutLink` warning names the link to add.

**What is stored.** `Requests` edges and unmatched HTTP calls, replaced at every index with the other results of stage 2.

**What is not matched:**
- A path whose every part exists only at run time. The call is listed as unmatched, with path `{?}`, so it can still be found.
- A helper chain deeper than `analysis.flow_rounds` call levels. The copies stop there, and `FlowRoundLimit` says so.
- gRPC and GraphQL. They come with the frameworks that serve them, in later releases.
- Callers in TypeScript. Those arrive with TypeScript parsing in Release 2.

### Stage 2e: reach

**Roots: where reach starts.**

| Root | From |
|---|---|
| A binary | Its entry `File` (`EntryPoint`) |
| A named module | A module named in a string that Stage 1 or the workspace layer found: a compose `command` (`uvicorn billing.api:app`, `python -m ledger.consumer`), a binary's `app`, a `uvicorn.run("billing.api:app")` call |
| A test | A file named `test_*.py` or `*_test.py`, a file under a folder named `tests`, and `conftest.py` |

**Edges followed, from a root outwards.**

| Edge | Why it means "may run" |
|---|---|
| `Imports`, to a `File`, unless the import is `type_only` | Importing a module runs its module-level code. An import under `if TYPE_CHECKING:` never runs, so reach does not follow it |
| `Calls`, `Instantiates` | The callee runs. `Instantiates` also reaches the class's `__init__` |
| `References` | A function passed as a value is assumed to be called |
| `Overrides`, followed backwards | A call to a base method may run any override of it |
| `Decorates` | The decorator runs when the decorated node is defined |
| `Mounts`, downwards, then `Handles` | An app serves its routers' routes, and each route runs its handler |
| `Injects` | A route or provider runs its providers, and a test or fixture runs its fixtures |
| `Requests`, then `Handles` | A call to a route runs its handler. This is how an API test, or a client in another project, reaches the handler |

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
| 2b | In full, at every index | Linear in call sites, bindings and returns, times at most `analysis.flow_rounds` rounds (10 by default) |
| 2c | In full, at every index | Linear in routes, times the depth of their mounts |
| 2d | In full, at every index | Linear in HTTP call sites, times the candidate routes |
| 2e | In full, at every index | Linear in edges, times the number of roots, with one bit per root |

Running 2b to 2e in full keeps them simple and deterministic. Running them only from the changed nodes outward would make an index faster, and gives the same graph. It is a speed-up for a later release, not missing behaviour.

### What the two stages lack

Only what static reading cannot know:

| Not covered | Why |
|---|---|
| Callers outside the workspace | A library function called by code that is not indexed. 2b counts only the callers it sees, which is why its edges say `resolved_by: flow` |
| Dynamic dispatch: `getattr` with a computed name, a dict of functions indexed by a run-time key, monkey patching, `exec` | No static form. A function stored in a dict is still reached, through its `References` edge |
| Values that exist only at run time: a URL or prefix read whole from the environment or a file | Written `{?}`. An HTTP call with no text at all is still listed, as unmatched |
| Chains deeper than `analysis.flow_rounds` | Raise the setting. `FlowRoundLimit` says when it was hit |
| Code loaded by name in ways not listed as roots | Add the module as a binary |

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
| `Imports` | `import a.b`, `from a import b`, with or without `as`, relative or absolute | The `File` | `from x import *` gives one edge, to the module's `File`. An import inside `if TYPE_CHECKING:` or `if typing.TYPE_CHECKING:` is marked `type_only`: it resolves like any import, and reach does not follow it |
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
| `app = FastAPI(..., dependencies=[Depends(audit)])`, at module level or inside a factory function | A `Variable` for `app` (a local one, for a factory) | `References` to a `lifespan=` function. `Injects` from `app` to `audit` | Role `App` |
| `router = APIRouter(prefix="/invoices", tags=["invoices"], dependencies=[Depends(auth)])` | A `Variable` for `router` | `Injects` from the router to `auth` | Role `Router`, with its `prefix` as a template: text, or a name whose text 2b fills in |
| `@router.get("/{invoice_id}", response_model=Invoice, status_code=200, dependencies=[Depends(audit)])` on `async def get_invoice(...)` | A `Route`, child of the `File` | `Mounts` from the router to the route. `Handles` from the route to `get_invoice`. `Returns` from the route to `Invoice`. `Injects` from the route to `audit` | `method: GET`, `path: "/{invoice_id}"`, `status_code: 200`, `tags` |
| `.post`, `.put`, `.patch`, `.delete`, `.head`, `.options`, `.trace` | as above | as above | The method |
| `@router.api_route("/x", methods=["GET", "POST"])` | One `Route` per method | as above | |
| `@router.websocket("/ws")` | A `Route` | as above | `method: WEBSOCKET` |
| `router.add_api_route("/x", handler, methods=[...])` | One `Route` per method | `Handles` to `handler` | |
| A handler parameter `db: Session = Depends(get_db)`, or `Annotated[Session, Depends(get_db)]`, or `Security(...)` | The `Parameter` (core) | `Injects` from the handler to `get_db`. The same inside a provider, so a chain of providers is followed | |
| A handler parameter with `Path()`, `Query()`, `Header()`, `Cookie()`, `Body()`, `Form()` or `File()`, or named in the route's path | The `Parameter` (core) | `TypeOf` (core) | `source`: path, query, header, cookie, body, form or file. Left empty when nothing says |
| `app.include_router(invoices.router, prefix="/v1", tags=["v1"], dependencies=[Depends(rate_limit)])` | | `Mounts` from `app` to the router, with `prefix: "/v1"` and `tags: ["v1"]`. `Injects` from `app` to `rate_limit`, with the site of this call, so it applies only through this mount | |
| `app.mount("/admin", admin_app)`, where `admin_app` is a FastAPI app | | `Mounts` with the prefix | |
| `@app.middleware("http")` | | `Decorates` (core) | Role `Middleware` on the function |
| `app.add_middleware(TimingMiddleware)` | | `References` from `app` to the class | |
| `@app.exception_handler(NotFound)` | | `References` from the handler to `NotFound` | Role `ExceptionHandler` |
| `@app.on_event("startup")` or `("shutdown")` | | | Role `LifecycleHook` |
| `class Invoice(BaseModel)`, with `BaseModel` imported from `pydantic` in the same file | The `Class`, and a `Field` per annotated name (core) | `TypeOf` from each field (core) | Role `Model` |
| `background_tasks.add_task(send_receipt, ...)` | | `References` to `send_receipt` (core) | |

**A route's qualified name** is its handler's qualified name, then `@`, the method and the local path: `billing.routes.invoices.get_invoice@GET /{invoice_id}`. Its display name is `GET /{invoice_id}`. All of this is known in the route's own file, so the id stays stable. Two decorators on one handler with the same method and path get ordinals.

**A route's full path** is computed by [stage 2c](#stage-2c-route-paths), which follows `Mounts` from the route up to an app and joins the prefixes: `/v1` + `/invoices` + `/{invoice_id}`. It is stored as a route-path record, not on the route node, because a change to a prefix in `api.py` would otherwise mean rewriting route nodes in other files.

**Which binary serves a route** is every FastAPI binary whose stored `app` is the app that the route's mounts lead to. Stage 2c records it with each full path.

**Roles** are stored only when the node's own file shows them. A function becomes a provider because some route injects it, so "provider" is derived from incoming `Injects` edges and never stored. A class that extends a project model, instead of `BaseModel` directly, is a model by its `Extends` chain, also derived.

### What the FastAPI profile lacks

| Not read | Why |
|---|---|
| Paths and prefixes whose value exists only at run time, such as one read from `os.environ` | The route is still a node, the unknown part is written `{?}` in its full path, and the path is marked incomplete. A name whose text 2b can work out, a constant in any file or a settings default, is filled in |
| Routes made in a loop, or from data | No static form to read |
| Starlette routes built as a list (`Route("/x", endpoint)`), `APIRoute` subclasses, class-based views | Other shapes, for a later profile |
| `StaticFiles` and other non-FastAPI mounts | Not code in the workspace |
| The OpenAPI document, response classes, CORS and security scheme settings | Configuration of the running app, not structure |
| Pydantic `Field(...)` constraints, validators as rules, `model_config` | The field and its type are read. Its validation rules are not |
| A route as the target of a declared link | A link targets a service (C7). The calls themselves are matched to routes by 2d |

## Tests

**Test files and test functions.** A test file is a root of reach (stage 2e): a file named `test_*.py` or `*_test.py`, a file under a folder named `tests`, or a `conftest.py`. Inside it, a test function is a `Function` named `test_*`, or a `Method` named `test_*` in a class named `Test*`.

**pytest fixtures.** A function decorated with `@pytest.fixture` has role `Fixture`. Fixtures are passed in by name, so the graph follows them like providers:
- A test function or fixture whose parameter has a fixture's name gets an `Injects` edge to that fixture, with `resolved_by: framework`.
- The nearest fixture of that name wins, as in pytest's own lookup: the same file, then `conftest.py` in the same folder, then in each parent folder.
- `@pytest.mark.usefixtures("name")` gives the same edge.
- An `autouse=True` fixture gives an edge from every test function at or below its file's folder.
- A fixture from a pytest plugin outside the workspace stays unresolved.

**API tests.** `TestClient(app).get("/v1/invoices/1")` in a test is matched by stage 2d, so the test reaches the route's handler.

### Tests to run for a change

`workbench impact <node> --tests` lists the test functions to run when the node changes:

1. Reach narrows the search to the test files whose root reaches the node.
2. Inside those files, it walks backwards from the node over the edges reach follows, and stops at each test function it meets.
3. It prints each one as a pytest node id: `tests/test_services.py::test_process`, `tests/test_api.py::TestInvoices::test_get`.

Several nodes may be given, or `--file <project>:<path>` for every node of a file. Like reach, the list can include a test that only might run the node, through a callback or an override. It can miss a test that reaches the node only through an unresolved call.

## API contracts

When `impact` is asked about a class used by a route, or a field of one, it adds an **API contract** section:

1. **The routes that use the class**:
   - in the request, when a handler parameter is typed with it;
   - in the response, through the route's `response_model` (`Returns`) or the handler's return annotation;
   - nested, when the class is the type of a field of a model a route uses, such as `InvoiceList.items: list[Invoice]`. Nesting is followed up to 5 levels.
2. **For each route**: its full paths and binaries (2c), whether the class is in the request or the response, and the chain of fields that leads to it.
3. **Its consumers:**
   - `Requests` edges into the route: Python callers in any project, and tests.
   - Declared `http` links to the services that run its binary. These are marked "declared; call site unknown", such as web-app's `admin` in Release 1.

```
API contract: shared_api.models.Invoice
  GET /v1/invoices/{invoice_id}    response    billing-api: api
    called by  ledger-api   ledger.clients.fetch_invoice        src/ledger/clients.py:14
    called by  web-app      admin                               declared link; call site unknown
    tested by  billing-api  tests/test_api.py::test_get_invoice
```

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
| Calls and instantiation | Yes | Yes | Calls on receivers whose type is unknown after 2b |
| Calls through annotated parameters and fields, names bound once, fields set once, `functools.partial`, stubs | | Yes | |
| Inferred types: parameters from callers, returns, fields, names bound more than once, elements of collections and dicts | | Yes, with `resolved_by: flow` | Evidence that disagrees |
| `*args` and `**kwargs` passed straight on | | Yes | |
| Which rule resolved each edge (`resolved_by`) | | Yes | |
| A route's full paths, searchable, with their binaries (2c) | | Yes | Parts that are not literals, written `{?}` |
| Which binaries and tests may run each node (2e) | | Yes | Code reached only through unresolved calls |
| Base classes | Yes | Yes, as `Extends` or `Implements` | |
| Overrides | | Yes | |
| Type references in annotations | | Yes | |
| Functions used as values (callbacks) | | Yes | Through dynamic dispatch |
| `__all__` | | Yes | A computed `__all__` |
| Conditional and repeated definitions | Yes | Yes | |
| `if TYPE_CHECKING:` imports | As ordinary imports | Yes, marked `type_only`: resolved, and not followed by reach | |
| Dynamic code: `getattr`, `importlib`, monkey patching, metaclasses, `exec` | | | All of it |
| Code outside the workspace: the standard library and installed packages | | | Not indexed. References into it stay unresolved |
| Stub files `.pyi` | | Yes: their annotations fill gaps in the `.py` files | |
| Notebooks, Cython | | | Not read: they are not modules a binary imports |
| Plain binary: start, main guard, `-m`, callbacks | Partly (module-level calls) | Yes | Run-time behaviour |
| FastAPI: apps, routers, routes, mounts, providers, parameter sources, models, middleware, hooks | | Yes | See the table above |
| HTTP client calls (`httpx`, `requests`, `aiohttp`, `websockets`, `urllib`, `TestClient`) matched to routes (2d), including through helpers and client classes | | Yes, as `Requests` | Paths that exist only at run time (listed as unmatched), gRPC, GraphQL |
| pytest test functions and fixtures, `usefixtures`, `autouse` | | Yes | `parametrize`, fixtures from plugins |
| The tests to run for a change | | Yes (`impact --tests`) | Tests reached only through unresolved calls |
| API contracts: the routes a model is in, and their callers | | Yes (`impact`) | Callers in TypeScript until Release 2 |
| Other frameworks: Flask, Django, Celery, Click, Typer | | | Later, each a profile (I19) |

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

- **2b:** both call sites pass `InvoiceRepo`. So `r` takes `InvoiceRepo`, and `r.save()` becomes a `Calls` edge to `InvoiceRepo.save` with `resolved_by: flow`.
- **2e:** `routes/invoices.py` is reached by `api` only. `services.py` is reached by `worker` and by the test `test_services.py`. `db.py` is reached by `api` through `Injects`.
- **2c:** `GET /v1/invoices/{invoice_id}`, complete, served by `api`. `search "/v1/invoices"` finds it.

Release 1's three cross-repository answers add:

```
ledger-api/src/ledger/
└── clients.py          def fetch_invoice(invoice_id): return httpx.get(f"{BILLING_URL}/v1/invoices/{invoice_id}")
billing-api/tests/
├── conftest.py         @pytest.fixture def repo(): return InvoiceRepo()
└── test_api.py         def test_get_invoice(repo): TestClient(app).get("/v1/invoices/1")
```

- **2d:** `fetch_invoice` gives a `Requests` edge to `GET /{invoice_id}`, the only route that matches `/v1/invoices/{?}`. Ledger declares no `http` link to billing's `api` service, so the index raises one `HttpCallWithoutLink` warning. The fixture expects it. `test_get_invoice` gives a `Requests` edge through `TestClient(app)`, and an `Injects` edge to the fixture `repo`.
- **Tests to run:** `impact billing-api:billing.routes.invoices.get_invoice --tests` lists `tests/test_api.py::test_get_invoice`.
- **API contract:** `impact shared-api:shared_api.models.Invoice` lists `GET /v1/invoices/{invoice_id}` (response), called by ledger's `fetch_invoice`, by web-app's `admin` (declared link) and by `test_get_invoice`.

## Changes this needs elsewhere

All of these are applied. The decisions that are hard to reverse are also in ADRs [0012](./adrs/0012-node-kinds-carry-their-own-data.md), [0013](./adrs/0013-read-every-file-then-analyse-from-each-root.md), [0014](./adrs/0014-types-are-carried-only-when-every-caller-agrees.md), [0015](./adrs/0015-a-binarys-framework-is-decided-before-parsing.md), [0016](./adrs/0016-framework-relationships-are-edges-of-their-own.md) [0017](./adrs/0017-every-resolved-edge-records-its-rule.md) and [0018](./adrs/0018-http-calls-are-matched-to-routes-links-stay-declared.md).

| Page | Change |
|---|---|
| [domain-model.md](./domain-model.md) | Node data per kind (`ProjectData`, `BinaryData`, `Callable`, `TypeDecl`, `Member`, `RouteData`, `Doc`), checked against the file's language and the kind's roles: rules N8 to N10. Code nodes hold no language. A route's qualified name |
| [domain-model.md](./domain-model.md), [graph-model.md](./graph-model.md) | Three framework edge kinds, 22 → 25: `Mounts { prefix }`, `Handles`, `Injects`, with rule E11 for their ends. `Imports` gains `type_only`. Every resolved edge records `resolved_by`, rules E12 and E13. No new provenance |
| [domain-model.md](./domain-model.md) | Records from stage 1: `CallSite`, `Binding` (one per assignment, at module, function or class level), `Return`, with the `Shape` of each value. Records from stage 2, replaced at every index: `InferredType` (parameters, returns, fields, names), `Reach`, `RoutePath` (with providers, tags and `uses_defaults`), `UnmatchedHttpCall`. Rule R4 gains two exceptions: a dropped `Overrides` reference, and a reference resolved by 2b, which is kept. Four warning codes: `FrameworkMismatch`, `FrameworkAppNotFound`, `EntryCommandMismatch`, `FlowRoundLimit` |
| [storage-model.md](./storage-model.md) | Node data columns. `edges` gains `resolved_by`, `import_type_only` and `mount_prefix`. `unresolved_refs` gains `flow_resolved`. Tables `call_sites`, `bindings`, `returns`, `inferred_types`, `reach`, `route_paths`, `route_path_providers`, `unmatched_http_calls`. How stage 2 is written |
| [configuration-guide.md](./configuration-guide.md), [`templates/config.yml`](../templates/config.yml), [step 2](./implementation-plan/step-2-configuration.md) | `binaries[].framework` and `binaries[].app`; `projects[].framework` removed. A new `analysis` section with `flow_rounds`, 10 by default, `0` to turn 2b off |
| [step 4](./implementation-plan/step-4-workspace-indexing.md), [00-overview.md](./implementation-plan/00-overview.md) | Task 7 and slice 4H decide each binary's framework. `ComposeService` gains `command`. `LanguageParser` gains `probe_framework`. The store port gains the reads and the write of stage 2. The names table gains the new types |
| [usage-guide.md](./usage-guide.md) | `node` shows `reached by`, `inferred`, a route's full paths and binaries, a binary's framework. `search` finds routes by full path. `callers` and `callees` show `resolved_by`. `impact` labels type-only steps. `files --unreached` |
| [capability-map.md](./capability-map.md), [roadmap.md](./roadmap.md) | Rows C14, C15, I14 to I22, W14, Q12, Q13, G11, G12, decided. W11 keeps topics and queues for Later. Step 5b in Release 1 |
| [domain-model.md](./domain-model.md), [graph-model.md](./graph-model.md), [storage-model.md](./storage-model.md) | The `Requests` edge kind, 25 → 26, with `resolved_by: route_match`. The role `Fixture`. The shapes `Text` and `Template`. The unmatched HTTP call record. The `HttpCallWithoutLink` warning. ADR 0018 amends ADR 0004 |
| [usage-guide.md](./usage-guide.md) | `impact --tests` and the API contract section. `node` shows a function's HTTP calls and a route's callers |
| [step 5](./implementation-plan/step-5-python-parsing.md) | Its "What Release 1 reads" tables become the first slice of this page |

## Plan

Each phase ends in something tested on its own. The phases follow step 5 and use its parser, resolver and fixture.

| Phase | Delivers | Needs | Tested by |
|---|---|---|---|
| P0 | Binary framework: the two configuration fields, the three sources in order, then `none`, the stored data, the warnings | Step 2's 2C, step 4's 4B, 4H | One test per source. A higher source beats a lower one and raises `FrameworkMismatch`. A factory app needs the configuration. `python -m` against a different entry raises `EntryCommandMismatch` |
| P1 | Core definitions: every node kind and every detail in the tables above | Step 5's 5B, the typed node data | One test per row of the definitions and details tables, on strings of Python |
| P2 | Core references: `Implements`, `Overrides`, `TypeOf`, `Returns`, `References`, `Exports`, `type_only` imports. Call sites, bindings (module, function, class, `for` and `with` targets) and returns, with their shapes. Stub files | P1, 5C | One test per row of the references table. An import under `if TYPE_CHECKING:` is `type_only`. One test per shape, including a template's holes, `Item` with each accessor, `Collection` from a comprehension, and `Spread`. A body that can end without `return` gives a return of `None`. A `.pyi` file's nodes belong to its own `File` |
| P3 | Resolution (2a): re-exports, following annotations, inherited members, names and fields bound once, `functools.partial`, stub annotations, and `resolved_by` on every edge | P2, 5D, 5E | A re-export chain across projects, `resolved_by: re_export`. A cycle in re-exports ends. `invoice.total()` through an annotation. `self.repo = InvoiceRepo()` then `self.repo.save()`. A call through `partial`. An annotation found only in the stub. An unannotated receiver stays unresolved. One test per `resolved_by` value |
| P3b | Types and text (2b): parameters from callers, returns, fields, names bound more than once, element types, `*args` forwarding, text of values, text carried to callers and into client classes, rounds, `analysis.flow_rounds`, kept references | P3 | The `process(repo)` example gives a `flow` edge; a second caller passing another class removes it; a callback stops it; a `Mock` in a test stops it. A function whose every return is `Invoice()` types its callers' bindings. A body that can fall through gets no return type. `for r in repos` with `repos: list[InvoiceRepo]`. `.items()` on `dict[str, InvoiceRepo]`. A helper's path filled at two call sites gives two copies. A client class's base URL is filled from its creation. A constant in another file gives text. `flow_rounds: 1` stops after one level and raises `FlowRoundLimit`. Two runs give the same edges |
| P4 | Plain binary: main guard, `-m` entries, callbacks; the derived "what code a binary runs" | P3 | The worker reaches `send_invoice` from its entry. `Thread(target=f)` reaches `f` |
| P5 | FastAPI profile: every row of its table, and the three framework edges, with `dependencies=` and `tags=` on apps, routers and mounts | P3 | One test per row. A factory app. A prefix from a constant in another file. A prefix from `settings` gives its default. `include_router(..., dependencies=...)` gives an `Injects` edge with the mount's site |
| P6 | Route paths (2c): full paths, binaries, providers, tags, `uses_defaults`, search | P0, P3b, P5 | `GET /v1/invoices/{invoice_id}`, complete, served by billing's `api`. A router mounted twice gives two paths. A router in a library is served by the binary that mounts it. A prefix from `os.environ` gives `{?}` and `complete: false`. A prefix from a settings default sets `uses_defaults`. A provider given at one mount is on that mount's paths only. `search "/v1/invoices"` finds the route |
| P6b | Reach (2e): the three kinds of root, the edges followed, reach records, `reached by`, `files --unreached` | P3b, P4, P5 | `routes/invoices.py` reached by `api` only. A test file is a root. A module named in a compose command is a root. An override is reached through its base. A `type_only` import is not followed. A file behind an unresolved call is listed as unreached |
| P8 | HTTP calls (2d): the clients, method and path, helpers and client classes through 2b, matching, narrowing, `Requests` edges, unmatched calls, `HttpCallWithoutLink` | P6 | One test per client, including `websockets` and `urllib`. A template matches a `{param}`. A query string is ignored. A helper called from two places gives two edges, each from its caller. A `BillingClient("http://billing/v1")` method call matches `/v1/...`. A declared link narrows two candidates to one. Two candidates with no link give an unmatched call. A URL from `os.environ` is listed as unmatched with path `{?}`. A cross-project match with no link warns |
| P9 | Tests: test functions, fixtures and their `Injects` edges, `usefixtures`, `autouse`, `impact --tests` | P6b, P8 | A fixture in a parent `conftest.py` is found, and a nearer one wins. An `autouse` fixture reaches every test below it. `impact --tests` lists pytest node ids, and a test class method as `file::Class::test` |
| P10 | API contracts in `impact`: request, response and nested use, route paths, consumers from `Requests` edges and declared links | P8, P9 | `Invoice` in a response, and nested in `InvoiceList`. A declared link is shown as "call site unknown". Nesting stops at 5 levels |
| P7 | Acme Shop with FastAPI and stage 2, end to end | P4, P6, P6b, P8, P9, P10, 5G | The walk above, on the SQLite store. The results of 2b, 2e and 2c in the fixture section. Indexing twice changes nothing. `validate` passes |

## Open points

None at present. Each point below was settled by the project owner.

- **Plain Python and FastAPI are both in Release 1,** as step 5b.
- **Language** is on the `Project` node (declared) and the file record (detected). Code nodes have none. A binary was considered; it can never differ from its project.
- **Read every file, then analyse from each root.** Reading only what an entry reaches would miss code loaded by name, read libraries in part, drop tests and break incremental reading.
- **The framework is set on a binary only.** A project default would save one line per binary, at the cost of a precedence rule and one more way for sources to disagree.
- **A compose command never replaces `entry`.** It can give a binary's framework and app. A disagreement is the `EntryCommandMismatch` warning.
- **A route's full path is computed by stage 2c and stored in its own record.** Computing it at query time would keep `search` from finding it. Storing it on the route node, as codegraph does, would mean rewriting route nodes in other files whenever a prefix changes.
- **Three framework edge kinds:** `Mounts`, `Handles`, `Injects`. Reusing `References` would make "which routes use this provider" a filter over every reference, and leave no edge from a route to its app.
- **Type-only imports are marked in Release 1.** Reach would otherwise follow imports that never run.
- **Provenance stays `TreeSitter`; every resolved edge records `resolved_by`.** A new `Flow` provenance would explain only flow edges. `Heuristic` would understate edges that are never wrong within the workspace.
- **Everything for Python, plain binaries and FastAPI is in Release 1.** That includes types and text carried through calls, helpers and client classes for HTTP calls, stub files, and providers given at a mount. Only what static reading cannot know is left out. More languages and more frameworks come in later releases.
- **Three cross-repository answers are in Release 1:** HTTP calls in Python matched to routes, the tests to run for a change, and API contracts. Links stay declared; a matched call with no declared link is a warning (ADR 0018).
- **Types from callers run for up to 10 rounds by default,** set by `analysis.flow_rounds`. `status` reports when the limit is hit.
