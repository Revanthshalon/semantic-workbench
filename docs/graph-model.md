# The Graph Model

How the structure of the knowledge graph was decided, and what the graph looks like for a real workspace. The exact types, fields and rules to implement and validate against are in [domain-model.md](./domain-model.md).

This describes the designed model. None of its types are written yet. They are specified in [domain-model.md](./domain-model.md), and slices 1A to 1E of the [implementation plan](./implementation-plan/00-overview.md#the-slices) build them. The running example is the Acme Shop workspace from [example-workspace.md](./example-workspace.md). Terms are defined in [GLOSSARY.md](./GLOSSARY.md).

## What the graph is for

An AI tool that works on one file at a time cannot see how a workspace fits together: which project uses which library, which service talks to which, what a change will break. The graph stores that knowledge as **nodes** (things) and **edges** (relationships between two things), so a tool can start at one node and walk outwards to everything related to it.

## The starting point

The first draft copied the types of an existing single-project code graph: a node is a code symbol in a file, and an edge is a relationship between two symbols. That model has four limits, and each decision below removes one of them.

| Limit of the first draft | What it prevented |
|---|---|
| A node's id came from its file path and name only | Two projects with a `src/main.py` would collide |
| Every node had to have a file and a position | A service, a network or a topic has no file |
| Kinds covered code only | Projects, services and topics could not be nodes |
| An edge's extra data was a free-form map | Nothing stopped data that made no sense for the edge's kind |

## The decisions, in the order they were made

### 1. A node's id is computed, not assigned

The same node must get the same id every time the workspace is indexed. Then indexing twice updates nodes instead of duplicating them, and edges keep pointing at the right node. So the id is a hash of the values that make a node unique.

| Considered | Outcome | Reason |
|---|---|---|
| Hash of file path and qualified name | Extended | A class and a function may share a name, and a function may be defined twice |
| Add the node's kind | Adopted | Separates a class from a function with the same name |
| Add an ordinal (0 for the first duplicate, 1 for the second) | Adopted | Separates overloads, redefinitions and unnamed functions |
| Add the line number | Rejected | Editing a line above a function would change its id |
| BLAKE3, keeping the first 64 bits as 16 hex characters | Adopted | Short enough for an AI to read and repeat. A collision is very unlikely, and the index stops if one happens |
| Base64 of the inputs, so the id can be decoded | Rejected | Long, unreadable, costly for an AI to read, and the node already stores those values |
| Let the database assign ids | Rejected | Edges could not be built before storing, and ids would change on every index |
| Store the ordinal on the node to verify ids later | Rejected | It duplicates what the id already encodes; a changed file is detected by its content hash |

### 2. A node belongs to a scope

Once a workspace has several projects, a file path is not unique. Services and networks belong to no project at all. So every node has a **scope**, and the scope is part of the id.

| Scope | Used for |
|---|---|
| The workspace | Projects, stacks, networks with a known real name |
| One project | Its files, its code and its binaries |
| One stack | Its services, their topics and queues, networks whose real name is unknown |

A project named `billing` and a stack named `billing` get different ids, because the scope's type is hashed along with its name.

The workspace node itself is the root of the graph. Its qualified name is always `workspace`, so its id is the same on every machine. The workspace root's folder name is only its display name.

### 3. One graph for the whole workspace

| Considered | Outcome | Reason |
|---|---|---|
| One graph, with each project as a node | Adopted | A link between two projects is an ordinary edge, and one walk can cross projects |
| One database per project, plus a database of cross-project links | Rejected | Every cross-project question becomes a join across databases |
| One graph per project, merged when queried | Rejected | Walking and ranking across projects would be slow and awkward |

### 4. Project, binary and service are three different things

The configuration and the compose files use three overlapping ideas, and merging them loses information.

- A **project** is source code.
- A **binary** is one runnable entry point inside a project. One project can have several.
- A **service** is one running unit declared in a compose file. It runs one binary.

Keeping them apart lets the graph say that the `api` service of billing listens for HTTP and the `worker` service does not, although both are built from the same project and the same Dockerfile.

Related choices:

- **Container images are not nodes.** A service records which binary it runs, and that is the fact an AI needs.
- **A service with a stock image and no project is an external service,** such as a database or a message broker. It is a node, because two projects using the same broker is exactly the kind of link the graph should reveal.
- **Topics and queues are nodes** under their external service. Without them, every project that uses one broker would look equally connected.
- **Services are grouped into stacks** by Compose name, because a service's identity is its stack plus its name. The same service name in two stacks is two services.

### 5. Networks say who can talk; links say who does

A network is only a name. Services that join the same network can reach each other, and the indexer reads this from the compose files. That is reachability, not communication: by default every service in a stack shares one network.

What actually talks to what, and how (HTTP, a topic, a database), comes from links written by hand in the configuration. Links stay declared: what the code shows is matched against them instead, an HTTP call to the route it calls and a producer or consumer to a declared topic or queue, with a warning when no link is declared (decisions 13 and 14). Networks and links are also checked against each other: a link between two services that share no network gets a warning.

### 6. An edge's data is part of its kind

Some edges need extra data. An import has the text that was imported. A dependency has a scope. A free-form map would allow dependency data on a "calls" edge. So the kind and its data are one value: each kind has its own shape, and most kinds carry nothing.

| Kind | Data it carries |
|---|---|
| `Imports` | The import as written, the local name it is bound to, and whether it only serves type checking (`type_only`) |
| `DependsOn` | When the dependency is needed: build or dev |
| `ConnectsTo` | The protocol: HTTP, gRPC or database |
| `Mounts` | The path prefix the mount adds, when there is one: a literal, or unknown when the code computes it |
| `Requests` | The HTTP method and the path as written in the call |
| `Sends` | The topic, queue or stream name |
| `Invokes` | The command words of the compose command |
| The other twenty-two | Nothing |

The same holds for nodes: a node kind carries its own data (decision 10).

### 7. Every edge says how it came to exist

An AI should treat a relationship read from source differently from one that was guessed. So provenance is required on every edge.

| Provenance | Meaning |
|---|---|
| `TreeSitter` | Read from source code by a parser |
| `Scip` | Read from a SCIP index |
| `Manifest` | Read from a dependency manager's files |
| `Compose` | Read from a compose file |
| `Dockerfile` | Read from a Dockerfile: the command line a service runs |
| `Declared` | Written by hand in the configuration |
| `Heuristic` | Inferred, and may be wrong |

Provenance says where the facts came from. A second field on every edge made by resolving a reference, `resolved_by`, says which rule connected it: an import, `self`, the same file, a re-export, an annotation, local inference, an inherited member, types carried from callers (`flow`) or a framework. codegraph keeps the same distinction, as `provenance` and `resolvedBy`.

| Considered | Outcome | Reason |
|---|---|---|
| A new provenance, `Flow`, for edges resolved by types inferred in stage 2b | Rejected | It would explain only those edges, and mix "where the facts came from" with "which rule connected them" |
| Mark those edges `Heuristic` | Rejected | They are never wrong within what the workspace shows, so `Heuristic` understates them |
| Keep provenance coarse, and record `resolved_by` on every resolved edge | Adopted | Every edge can say why it is there |

### 8. A node is either parsed from a file or declared

A code node has a file and a region of that file. A project or a hand-declared topic has neither. So a node's **origin** is one of two things: parsed, with a file and a span, or declared, with nothing. This replaced a mandatory file path and four mandatory position numbers. Lines count from 1 and columns from 0.

A binary's entry file always gets a file node, even when its language is not parsed yet. The file then has no nodes below it, and the binary's `EntryPoint` edge still has a target.

### 9. Workspace edges have rules about what they connect

A "joins" edge from a function to a network is a bug. Each of the ten workspace edge kinds may only connect certain kinds of node, and building an edge that breaks its rule is refused (rule E1). Code edges are not restricted, except the six framework edges of decisions 11, 13 and 14: `Mounts`, `Handles`, `Injects`, `Requests`, `Sends` and `Receives` (rule E11).

### 10. A node kind carries its own data

The first model gave every node the same optional fields: doc, signature, visibility, flags, decorators, return type. A service could then be async, and a Python method could be protected. So, as with edges, the data is part of the kind.

| Considered | Outcome | Reason |
|---|---|---|
| One flat set of optional fields | Replaced | Nothing stopped a field that made no sense for the kind or the language |
| One data type per kind and language (`PyFunction`, `TsFunction`, ...) | Rejected | The number of types multiplies with each language. Languages differ in which values they allow, not in which fields exist |
| One data type per shape of kind, checked against what the language can express | Adopted | Kinds that look alike share a type: `Callable`, `TypeDecl`, `Member`, `RouteData`. A table per language refuses what it cannot express |
| The kind and its data as two fields, checked against each other | Rejected | The check can be forgotten. Each kind's variant holds its data instead, so a mismatch cannot be written (rule N8) |

The language is not on code nodes. It is the file's, held by the file record, and the project's main language is on the `Project` node. A binary also carries data: its framework and its app.

### 11. Frameworks add three edge kinds

A FastAPI app mounts routers, a router mounts routes, a route is handled by a function, and a route or a provider injects other providers. These are `Mounts` (with its prefix), `Handles` and `Injects`. Each may only join certain kinds of node.

| Considered | Outcome | Reason |
|---|---|---|
| `References`, with a role on the node | Rejected | "Which routes use this provider" would be a filter over every reference into it, and nothing would link a route to its app |
| A route node and a `References` edge to its handler only, with the prefixes composed into the route's name (codegraph) | Rejected | No edge from a route to its router or app, so "which binary serves this route" and "which routes move if this prefix changes" cannot be walked |
| Three new kinds | Adopted | Each question about a route is one edge kind |
| Storing a route's full path on the route node | Rejected | The prefixes sit in other files, so a change to one would rewrite route nodes elsewhere |
| Computing the full path at query time | Rejected | `search` could not find a route by its full path |
| Computing the full path in stage 2, and storing it as its own record | Adopted | Searchable, and no route node changes. It is rebuilt at every index with the other results of stage 2 |

### 12. An index reads every file, then analyses from each root

Reading only the files an entry reaches was considered, to follow the code as it runs. It would miss code loaded by name, read libraries only in part, drop tests, and break incremental reading. So stage 1 reads every file on its own, and stage 2 analyses the finished graph: it resolves references, carries types from callers, and finds which roots reach each node. [python-parsing.md](./python-parsing.md#how-the-graph-is-built) describes both stages.

| Considered | Outcome | Reason |
|---|---|---|
| Read only what an entry reaches | Rejected | Incomplete, and not incremental |
| Infer a parameter's type from any caller | Rejected | One wrong caller would give wrong edges with no sign of it |
| Carry a type only when every caller agrees, and record `resolved_by: flow` on such edges | Adopted | Nothing is guessed within what the workspace shows, and a reader can tell these edges from those read directly |

### 13. HTTP calls in code are matched to routes, and links stay declared

Once routes and their full paths are in the graph, a client call such as `httpx.get(f"{BILLING_URL}/v1/invoices/{id}")` in another project can be matched to the exact route it calls. The match is a code edge, `Requests`, from the calling function to the route. It is what lets `impact` and the API contract go from a model to the code in other repositories that calls it, and lets an API test reach the handler it tests.

| Considered | Outcome | Reason |
|---|---|---|
| Keep finding HTTP calls for Later (W11) | Rejected | Routes and their full paths are already in the graph, so matching is cheap, and only a workspace graph can do it |
| Turn a matched call into a `ConnectsTo` link | Rejected | A link is a runtime fact a person declares (ADR 0004). A match is evidence from code, and can be ambiguous when two apps serve the same path |
| A `Requests` edge to the route, narrowed by declared links, with a warning when a cross-project match has no declared link | Adopted | Code and configuration check each other, and nothing is guessed: an ambiguous call is stored as unmatched |

### 14. Messages and commands are matched like HTTP calls

A producer's `send("invoice.created", ...)` and a consumer's loop over the same topic are matched to the declared `Topic` node, as `Sends` and `Receives` edges from the code to the topic, with the class each side carries. A compose service that runs `python -m ledger.consumer run` is linked to the command `run` of that binary, as an `Invokes` edge to a `Command` node.

| Considered | Outcome | Reason |
|---|---|---|
| Create topics and queues from the names found in code | Rejected | A name in code can be a typo or another environment's topic. Topics stay declared (ADR 0004); a name with no declared topic is a warning |
| Let reach follow `Sends` and `Receives` | Rejected | Sending a message does not run the handler in this process. The walk across a topic belongs to `impact`, which says it crosses one |
| Link a service to its binary only | Rejected | `impact` would name every service that runs a binary, even one that runs another of its commands |
| A `Command` node per `argparse` parser and subcommand, and an `Invokes` edge computed in stage 2 | Adopted | Commands exist only after parsing, so the edge cannot be built with the workspace layer. The same node kind will serve Click and Typer |

## The model that results

### Node kinds

| Group | Kinds |
|---|---|
| Code (24) | `File`, `Module`, `Class`, `Struct`, `Interface`, `Trait`, `Protocol`, `Function`, `Method`, `Property`, `Field`, `Variable`, `Constant`, `Enum`, `EnumMember`, `TypeAlias`, `Namespace`, `Parameter`, `Import`, `Export`, `Route`, `Component`, `Union`, `Command` |
| Workspace (9) | `Workspace`, `Project`, `Binary`, `Stack`, `Service`, `ExternalService`, `Network`, `Topic`, `Queue` |

### Edge kinds

| Group | Kinds |
|---|---|
| Code (19) | `Contains`, `Calls`, `Imports`, `Exports`, `Extends`, `Implements`, `References`, `TypeOf`, `Returns`, `Instantiates`, `Overrides`, `Decorates`, `Navigates`, `Mounts`, `Handles`, `Injects`, `Requests`, `Sends`, `Receives` |
| Workspace (10) | `DependsOn`, `Uses`, `EntryPoint`, `Runs`, `BuiltFrom`, `Joins`, `ConnectsTo`, `Publishes`, `Subscribes`, `Invokes` |

| Workspace kind | From | To | Meaning |
|---|---|---|---|
| `DependsOn` | Project | Project | Uses the other project's code |
| `Uses` | Project | Stack | Uses that stack: the project's own stack, or a shared stack that lists the project |
| `EntryPoint` | Binary | File | Starts at this file |
| `Runs` | Service | Binary | Runs this binary |
| `BuiltFrom` | Service | Project | Is built from this project, binary unknown |
| `Joins` | Service, ExternalService | Network | Is on this network |
| `ConnectsTo` | Project, Binary | Project, Service, ExternalService | Reaches it over HTTP, gRPC or a database protocol |
| `Publishes` | Project, Binary | Topic, Queue | Sends messages to it |
| `Subscribes` | Project, Binary | Topic, Queue | Receives messages from it |
| `Invokes` | Service | Command | Runs this command of its binary. Found in stage 2, from the service's compose command |

`Contains` does all grouping, and makes the graph one tree with the workspace node at its root: workspace to project, stack and network, project to binary and file, file to class, stack to service and external service, external service to its topics and queues.

### What a node holds

- **Identity:** the id, the kind, the name and the qualified name.
- **Place:** the scope and the origin.
- **Data, which depends on the kind:** for a callable, its doc string, signature, visibility, flags, decorators, type parameters and return type; for a field, variable or parameter, its declared type and default; for a route, its method and local path; for a project, its language; for a binary, its framework and app. Most workspace kinds carry none.

### What an edge holds

- The source node's id and the target node's id.
- The kind, with its data.
- The site: the file, line and column where the relationship occurs, when it has a place.
- The provenance.
- A note: the free text of a hand-written dependency or link.

Two calls from one function to another on different lines are two edges, because the site differs. An edge's identity is its source, target, kind and site. The data of a kind is not part of it.

## What the graph looks like for Acme Shop

The graph has three layers. The bridges between them are what make a cross-project walk possible.

```
WORKSPACE LAYER   what exists

  Workspace ─Contains─> Project billing-api ─Contains─> Binary api
                                           └─Contains─> Binary worker
                        Project ledger-api ──Contains─> Binary api, Binary consumer
                        Project shared-api
                        Project web-app ─────Contains─> Binary admin

  billing-api ─DependsOn─> shared-api <─DependsOn─ ledger-api


RUNTIME LAYER     what runs, and what can reach what

  Stack acme-infra ──Contains─> ExternalService kafka ─Contains─> Topic invoice.created
                   └─Contains─> ExternalService postgres
  Stack billing-api ─Contains─> Service api, Service worker
  Stack ledger ──────Contains─> Service api, Service consumer

  every service and external service above ─Joins─> Network acme-backbone
  Service api, Service worker (stack billing-api) ─Joins─> Network billing-api_default

  billing-api ─Uses─> Stack billing-api, Stack acme-infra
  ledger-api ──Uses─> Stack ledger, Stack acme-infra


CODE LAYER        what the source says

  Project shared-api ─Contains─> File models.py ─Contains─> Class Invoice
  Project billing-api ─Contains─> File worker.py ─Contains─> Function send_invoice
```

```
BRIDGES

  Service worker (stack billing-api) ─Runs─> Binary worker ─EntryPoint─> File worker.py
  Binary worker (billing-api) ───Publishes──> Topic invoice.created
  Binary consumer (ledger-api) ──Subscribes─> Topic invoice.created
  Binary api (billing-api) ──────ConnectsTo─> ExternalService postgres
  Binary worker (billing-api) ───ConnectsTo─> ExternalService postgres
  Binary admin (web-app) ────────ConnectsTo─> Service api (stack billing-api)
  File worker.py (billing-api) ──Imports────> Class Invoice (shared-api)
```

### A few of the nodes

| Kind | Scope | Qualified name | Origin |
|---|---|---|---|
| `Project` | Workspace | `billing-api` | Declared |
| `Binary` | Project `billing-api` | `worker` | Declared |
| `Stack` | Workspace | `ledger` | Declared |
| `Service` | Stack `billing-api` | `api` | Parsed from `docker-compose.yml` |
| `Service` | Stack `ledger` | `api` | Parsed from `docker-compose.yml` |
| `ExternalService` | Stack `acme-infra` | `kafka` | Parsed from `docker-compose.yml` |
| `Network` | Workspace | `acme-backbone` | Parsed from `docker-compose.yml` |
| `Topic` | Stack `acme-infra` | `kafka/invoice.created` | Declared |
| `Class` | Project `shared-api` | `shared_api.models.Invoice` | Parsed from `src/shared_api/models.py` |

The two `api` services have the same kind and the same name. Their scopes differ, so their ids differ.

### A few of the edges

| From | Kind and data | To | Provenance |
|---|---|---|---|
| Project `billing-api` | `DependsOn` (build) | Project `shared-api` | Manifest |
| Service `worker` | `Runs` | Binary `worker` | Compose |
| Service `consumer` | `Runs` | Binary `consumer` | Compose |
| Service `api` (stack `billing-api`) | `Joins` | Network `acme-backbone` | Compose |
| Binary `worker` | `Publishes` | Topic `kafka/invoice.created` | Declared |
| Binary `consumer` | `Subscribes` | Topic `kafka/invoice.created` | Declared |
| Binary `api` (`billing-api`) | `ConnectsTo` (database) | ExternalService `postgres` | Declared |
| Binary `worker` | `ConnectsTo` (database) | ExternalService `postgres` | Declared |
| Binary `admin` | `ConnectsTo` (HTTP) | Service `api` (stack `billing-api`) | Declared |
| File `worker.py` | `Imports` (`shared_api.models`) | Class `Invoice` | TreeSitter |

The provenance column shows the example's story. Billing's `Runs` edge comes from its compose file, where the build target names the binary. Ledger's has no build target to go by: `consumer`'s comes from its compose `command`, and `api`'s from the `CMD` of ledger's Dockerfile, with the `Dockerfile` provenance.

## Walking the graph

The question: "I am renaming a field on `Invoice` in `shared-api`. What breaks?"

1. Start at Class `Invoice`.
2. Follow `Imports` edges backwards. They lead to files in `billing-api` and `ledger-api`, among them billing's `worker.py` and `api.py`.
3. Both are entry files. Follow `EntryPoint` backwards from each to Binary `worker` and Binary `api`.
4. From Binary `worker`, follow `Publishes` to Topic `kafka/invoice.created`.
5. From the topic, follow `Subscribes` backwards to Binary `consumer` of `ledger-api`.
6. From Binary `api`, follow `Runs` backwards to Service `api` of stack `billing-api`, then `ConnectsTo` backwards to Binary `admin` of `web-app`.

The walk crosses all three layers and all four projects. Each edge's provenance tells the reader how far to trust that step: step 2 comes from source code, and steps 4 to 6 rest on hand-written links.

A file that imports `Invoice` and is not an entry file is reached the same way, one step longer: from the file up to its project through `Contains`, then down to that project's binaries.

## What is left out, and why

- **A confidence score on inferred edges.** Nothing produces `Heuristic` edges yet. Edges resolved by `flow` need none: they exist only when every caller agrees.
- **Timestamps on nodes.** A node holds none. Its file's record says whether the file changed: the content hash decides, and the size and mtime let that be checked without reading the file.
- **A copy of the source code.** A node stores where its source is. A query reads the file through the node's span, and marks a file that has changed since the last index.
- **Topics, queues and links created from code.** Code is matched to what the configuration declares: an HTTP call to a route, as a `Requests` edge, and a send or a receive to a declared topic or queue, as a `Sends` or `Receives` edge. A name found in code never creates a topic, a queue or a link. One with nothing declared for it is a warning (decisions 13 and 14).
- **Services that run outside any compose file,** such as a managed database. The current assumption is that the compose files describe everything that runs.
- **How the graph is kept in SQLite.** That is in [storage-model.md](./storage-model.md): one table of nodes and one of edges, for both layers.
