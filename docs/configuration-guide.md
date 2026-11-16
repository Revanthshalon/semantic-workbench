# Configuration Guide

How to write `.workbench/config.yml`: what each field means, what you can leave out, and what the tool checks.

> This guide describes the configuration format as designed. The loader is not built yet. A complete, commented sample is in [`templates/config.yml`](../templates/config.yml), and a realistic one is worked through in [example-workspace.md](./example-workspace.md).

Related pages: [usage guide](./usage-guide.md), [graph model](./graph-model.md), [GLOSSARY.md](./GLOSSARY.md).

## What the configuration is for

Workbench reads most of what it needs from your files: source code, dependency manager files and compose files. The configuration holds two kinds of thing:

- **What only you know:** which folders are projects, which entry points they have, and how services talk to each other at run time.
- **What your files cannot say:** a Compose name set on the command line, a network name built from an environment variable, which binary a service runs.

If a fact can be read from a file, you do not write it here.

## Where the file lives

`.workbench/config.yml`, inside the **workspace root**. The workspace root is the folder that holds `.workbench/`. Commit `config.yml`. Do not commit the graph file beside it; `workbench init` writes a `.gitignore` for that.

The [usage guide](./usage-guide.md#how-a-command-finds-the-workspace) explains how a command finds this folder.

## The smallest configuration

```yaml
version: 1
projects:
  - id: billing-api
    path: ../billing-api
    language: python
    dependency_manager: uv
```

Everything else is optional.

## Rules that apply everywhere

- **Unknown fields are errors.** A misspelled field is never silently ignored. The one exception is `lsp.settings`, which is passed through as written.
- **Paths use `/`,** on every platform.
- **Secrets are never written here.** A field ending in `_env` holds the name of an environment variable, not its value.
- **Ids are kebab-case:** lowercase letters and digits, in groups joined by single hyphens, such as `billing-api`.

### Which folder a relative path starts from

| Field | Starts from |
|---|---|
| `projects[].path` | the workspace root |
| `compose[].files` (shared stacks) | the workspace root |
| `storage.path` | the workspace root |
| `projects[].binaries[].entry` | the project |
| `projects[].compose.files` | the project |
| `projects[].exclude` | the project |
| `projects[].environment.venv` | the project |

`projects[].path`, `compose[].files` and `storage.path` may also be absolute. A project may sit outside the workspace root, for example `../billing-api`. Prefer relative paths: an absolute path only works on your machine.

## `version`

Required. Always `1`. Any other value is an error.

## `projects`

Required, with at least one entry. A project is one unit of source code with its own root folder and dependency manager.

| Field | Required | Default | Meaning |
|---|---|---|---|
| `id` | yes | | A stable, unique, kebab-case name. Changing it gives every node of the project a new id, so choose it once |
| `path` | yes | | The project's root folder. No project's path may be the same as, or inside, another's |
| `language` | yes | | The main language: `python` or `typescript`. The first release reads Python projects only |
| `dependency_manager` | yes | | For Python: `poetry` or `uv`. For TypeScript: `npm`, `pnpm`, `yarn` or `bun` |
| `framework` | no | none | `angular`, and only with `typescript` |
| `import_names` | no | read from the project's manifest | The names other projects import this one by. Unique across the workspace |
| `exclude` | no | none | Files to leave out of the graph. See below |
| `dependencies` | no | discovery on, nothing declared | See below |
| `binaries` | no | none | See below |
| `links` | no | none | See below |
| `compose` | no | the project's compose files, if any are found | See below |
| `environment` | no | none | Reserved; see "Reserved sections" |
| `lsp` | no | none | Reserved; see "Reserved sections" |

**When to set `import_names`.** In Python the name you install and the name you import often differ: the package `acme-shared-api` is imported as `shared_api`. Workbench needs the import name to connect `import shared_api` in one project to the code of another. It reads it from the manifest when it can; set it by hand when it cannot.

### `exclude`: files to leave out

The indexer already skips what `.gitignore` excludes. Use `exclude` for files that are committed and still do not belong in the graph: generated code, database migrations, vendored code, test fixtures.

```yaml
exclude:
  - "src/billing/generated/**"
  - "migrations/**"
  - "**/*_pb2.py"
```

- **Each entry is a glob pattern, relative to the project.** `**` matches any number of folders.
- **An excluded file gets no node.** An import that points into it stays unresolved: the graph shows the import and nothing behind it.
- **Adding a pattern and indexing again** removes that file's nodes.
- **A binary's `entry` must not be excluded.** That is an error.

### `dependencies`: local dependencies

A local dependency is one project using another project's code.

| Field | Default | Meaning |
|---|---|---|
| `discover` | `true` | Read local dependencies from the dependency manager's files |
| `local` | none | Extra local dependencies, written by hand |
| `local[].project` | | Required. The id of another project. Never this project |
| `local[].scope` | `build` | `build` or `dev` |
| `local[].note` | none | Free text |

- **You usually write nothing.** A path dependency in `pyproject.toml` that points at another listed project is found automatically.
- **Declare one by hand** when no manifest shows it, for example code loaded through a plugin mechanism.
- **If both sources name the same pair,** there is one dependency, and your `scope` and `note` win.
- **A discovered path that is not a listed project** produces a warning and no dependency.
- **`discover: false`** uses only what is under `local`.

### `binaries`: runnable entry points

| Field | Meaning |
|---|---|
| `name` | Required. Unique within the project |
| `entry` | Required. The file the binary starts at, relative to the project. The file must exist |

Binaries are always written by hand; they are never detected. List them when one project runs as several things, such as an API and a worker. Services and links can then refer to the exact one.

### `links`: who talks to whom at run time

A link is a runtime connection the code does not reveal to the tool: an HTTP call, a message on a topic, a database connection. In the first release every link is written by hand.

| Field | Required | Meaning |
|---|---|---|
| `service` or `project` | exactly one | The target. A service is named as in its compose file |
| `stack` | only with `service` | The Compose name of the target's stack. Needed when the service name exists in more than one stack |
| `via` | yes | `http`, `grpc`, `topic`, `queue` or `database` |
| `name` | for `topic` and `queue` | The topic or queue name |
| `role` | for `topic` and `queue` | `publish` or `subscribe` |
| `binary` | no | Which of this project's own binaries makes the link |
| `note` | no | Free text |

- **`topic`, `queue` and `database` need a `service` target.** A topic lives on a broker, and the broker is a service.
- **`name` and `role` are required for `topic` and `queue`,** and not allowed for the others.
- **Prefer a `service` target for HTTP and gRPC.** A `project` target cannot say which of the target's binaries receives the call.
- **Declare both ends of a topic.** One project's `publish` and another's `subscribe` on the same name are what connect them in the graph.
- **Two identical links in one project** are an error.

```yaml
links:
  - {service: kafka, via: topic, name: invoice.created, role: publish, binary: worker}
  - {service: postgres, via: database, binary: api}
  - {service: api, stack: ledger, via: http, binary: api}
```

### `compose`: the project's own stack

A **stack** is all the services that run together under one Compose name, from one compose file or several. A project's `compose` block describes the stack made of that project's own compose files.

Most projects need no `compose` block. Workbench looks in the project root for the first of `compose.yaml`, `compose.yml`, `docker-compose.yaml` and `docker-compose.yml`. If the matching override file is beside it (`compose.override.yaml`, `compose.override.yml`, `docker-compose.override.yaml` or `docker-compose.override.yml`), that is read too, as Docker does. Add the block only to fill a gap.

| Field | Default | Meaning |
|---|---|---|
| `files` | the files found as described above | The stack's compose files, inside the project, in the order Docker is given them |
| `name` | the `name` in the files, else the first file's folder name | The Compose name the stack runs under |
| `networks` | none | Real names for networks the files cannot name |
| `services` | none | Which binary a service runs, when the files do not say |

```yaml
compose:
  files:
    - docker-compose.yml
    - docker-compose.dev.yml
  name: billing-dev
  services:
    api: {binary: api}
```

`name`, `networks` and `services` work exactly as for shared stacks, described next. The project is implied, so a `services` entry holds only `binary`.

## `compose`: shared stacks

A shared stack belongs to no single project, for example one that starts a database and a message broker for everyone. Each entry in the top-level `compose` list is one stack.

| Field | Required | Default | Meaning |
|---|---|---|---|
| `files` | yes | | The stack's compose files, in the order Docker is given them |
| `projects` | yes | | Every project that uses this stack |
| `name` | no | the `name` in the files, else the first file's folder name | The Compose name the stack runs under |
| `networks` | no | none | Real names for networks the files cannot name |
| `services` | no | none | Which project and binary a service belongs to, when the files do not say |

### `files`: the order matters

List the files in the order you pass them to Docker with `-f`. As in Docker, a later file overrides an earlier one: it can add services and networks, and it can change a service's build target. A compose file may appear in one stack only, whether that stack is shared or a project's own.

### `name`: the Compose name

Docker runs a stack under a Compose name.

- **Set `name` only when the name is given outside the files,** with `docker compose -p` or `COMPOSE_PROJECT_NAME`.
- **No two stacks may have the same Compose name.** Files that run under one name belong in one entry.
- **The same service name in two stacks is two services.**
- **A network with no stated name** is called `<Compose name>_<network>` by Docker, which is why the Compose name must be right.

### `services`: which project and binary a service is

Workbench matches a service on its own when it can:

1. The **project** is the one whose folder is the service's build context.
2. The **binary** is the one whose name equals the service's build target.
3. A service with **no build context and no entry here** is an external service: a stock image such as a database or a broker.

Add an entry only when that fails:

```yaml
services:
  billing:        {project: billing-api, binary: api}
  billing-worker: {project: billing-api, binary: worker}
```

- Each key must be a service in that stack's files.
- A `project` named here must also be in the stack's `projects` list.
- `binary` is optional. Without it the service is tied to the project only.
- This is how one Dockerfile that builds several images is captured: several services, the same project, different binaries.

### `networks`: real network names

Services on the same network can reach each other. Workbench reads networks from the compose files and uses them to check your links. It needs each network's real name to know when two stacks share one.

```yaml
networks:
  backbone: acme-backbone   # key: the network as named in the file. Value: its real name
```

- **Add an entry only when the files cannot state the name,** for example `name: "${BACKBONE_NET}"`.
- **Without an entry,** such a network produces a warning and is treated as private to its stack.
- **An entry always wins** over a name in the files. The override is logged, with no warning.
- **The value is used exactly as written.** No Compose name is put in front of it.
- **Each key must be a network in that stack's files.**

## `storage`

Optional. `workbench init` writes it.

| Field | Default | Meaning |
|---|---|---|
| `backend` | `sqlite` | The first release accepts only `sqlite` |
| `path` | `.workbench/graph.db` | The graph file |

## Reserved sections

These are part of the format so that a configuration written today stays valid later. The first release checks their shape and does not use them. See the [roadmap](./roadmap.md).

| Section | Reserved for |
|---|---|
| `lsp`, at the top level and on a project | Language servers: resolving references during indexing, and live lookups at question time |
| `semantic.llm` | LLM summaries and suggested links |
| `projects[].environment` | Language servers. It says how to enter the project's own environment: the virtual environment folder (`venv`) and the command that runs a program inside it (`activate`). A language server must start there to see the project's installed packages |
| `storage.backend: memgraph` and the Memgraph fields | Memgraph. Unlike the others, these are refused in the first release with a message |

## What is checked, and when

**When the configuration is read** (`check`, and the start of `index`):

1. No unknown fields, except under `lsp.settings`.
2. `version` is `1`.
3. Each project `id` is kebab-case and unique.
4. No project path is the same as, or inside, another's.
5. `dependency_manager` suits `language`; `framework: angular` is used only with `typescript`.
6. Every project named in `dependencies.local`, `links`, `compose[].projects` or `compose[].services` exists. A dependency or a link never names its own project.
7. Every `binary` named exists in the project it refers to. Binary names are unique within a project.
8. `import_names` are unique across the workspace.
9. A link has exactly one of `service` or `project`. `stack` appears only with `service`. `name` and `role` appear only, and always, with `topic` and `queue`. `topic`, `queue` and `database` have a `service` target.
10. No project has two identical links.
11. A compose file appears in one stack only. No two stacks have the same Compose name.
12. A Compose name uses lowercase letters, digits, `-` and `_`, and starts with a letter or digit.
13. `storage.backend` is `sqlite`.

**When the compose files are read** (`index`):

14. Every key under `services` is a service in that stack's files.
15. Every key under `networks` is a network in that stack's files.
16. A service mapped to a project in a shared stack has that project in the stack's `projects` list.
17. No `exclude` pattern matches a binary's `entry`.
18. A link's `service` exists. If the name is in more than one stack, the link gives `stack`.
19. Every binary's `entry` file exists.

## Errors, warnings and log lines

| Kind | Effect | Examples |
|---|---|---|
| Error | The command stops and nothing is written | Any rule above is broken |
| Warning | Indexing continues; the warning is shown at the end and by `status` | A network whose real name cannot be read. A link between two services that share no network. A discovered dependency path that is not a listed project |
| Log line | Shown with `-v` | A network name from the configuration replaced the one in the file. A reserved section was read and not used |

## Recipes

**Add a project.** Add an entry under `projects` with `id`, `path`, `language` and `dependency_manager`. Run `workbench check`, then `workbench index`.

**One project that runs as an API and a worker.** List both under `binaries`. If their compose services are built with build targets named `api` and `worker`, nothing more is needed. Otherwise map each service to its binary under `services`.

**A shared database and broker.** List the shared compose file under `files` in a top-level `compose` entry, with the projects that use it. The database and the broker become external services on their own.

**Two projects coupled through a topic.** Under each project's `links`, name the broker's service with `via: topic`, the same `name`, and `publish` on one side, `subscribe` on the other.

**A stack started with `-p`.** Set `name` on that stack's entry to the name you pass.

**A stack started with several `-f` files.** List them under `files`, in the same order.

**A network name that comes from a variable.** Under `networks` on that stack's entry, write the network's key and its real name.

**Generated code that is committed.** Add a pattern for it under the project's `exclude`.

**A dependency no manifest shows.** Add it under `dependencies.local` with a `note` that says why.

## Open points

These are known gaps in the format.

- **A stack named after its folder.** With no `name` in the file or the configuration, the Compose name is the folder's name, which can differ between machines. A link that names such a stack can break elsewhere. The indexer should warn.
- **Services outside any compose file.** A managed database or broker cannot be the target of a link yet. The current assumption is that the compose files describe everything that runs.
