# Example Workspace: Acme Shop

A worked example of one workspace made of several separately cloned repositories. It shows what the indexer can read on its own, what the configuration has to add, and how networks and links fit together.

This describes the designed behaviour. The indexer is not built yet. In the first release only the Python projects have their source code read; `web-app` still appears as a project with its binary, the binary's entry file and its link. Terms are defined in [GLOSSARY.md](./GLOSSARY.md). Every configuration field is explained in the [configuration guide](./configuration-guide.md) and shown in [`templates/config.yml`](../templates/config.yml). The graph this workspace produces is drawn in [graph-model.md](./graph-model.md#what-the-graph-looks-like-for-acme-shop).

## The application

Four repositories cloned side by side, plus one folder that holds the workspace.

```
~/acme/
├── workspace/                  # workspace root: holds .workbench/
│   ├── .workbench/config.yml
│   └── docker-compose.yml      # shared infrastructure: kafka, postgres
├── shared-api/                 # Python lib: Invoice models, used by both APIs
├── billing-api/                # Python, uv. Binaries: api, worker
│   ├── Dockerfile              # one Dockerfile, two build targets
│   └── docker-compose.yml
├── ledger-api/                 # Python, poetry. Binaries: api, consumer
│   └── docker-compose.yml
└── web-app/                    # Angular. Runs on the host with `ng serve`
```

The workspace root is the folder that holds `.workbench/`. The projects sit outside it, which the configuration allows.

## How it runs

```
 web-app (host) ──HTTP──> billing api ──SQL──> postgres
                          billing worker ──publishes invoice.created──> kafka
                          ledger consumer <──subscribes invoice.created── kafka
```

## The three compose files

### Shared infrastructure: `workspace/docker-compose.yml`

It states its own Compose name and the network's real name.

```yaml
name: acme-infra
services:
  kafka:    {image: apache/kafka:3.8, networks: [backbone]}
  postgres: {image: postgres:16,      networks: [backbone]}
networks:
  backbone: {name: acme-backbone}
```

### Billing: `billing-api/docker-compose.yml`

It joins the same network as an external one, and builds two services from one Dockerfile with different build targets.

```yaml
services:
  api:    {build: {context: ., target: api},    networks: [default, backbone]}
  worker: {build: {context: ., target: worker}, networks: [default, backbone]}
networks:
  backbone: {external: true, name: acme-backbone}
```

### Ledger: `ledger-api/docker-compose.yml`

The network name comes from an environment variable, and the team starts this file with `docker compose -p ledger`.

```yaml
services:
  api:      {build: ., networks: [backbone]}
  consumer: {build: ., command: python -m ledger.consumer run, networks: [backbone]}
networks:
  backbone: {external: true, name: "${BACKBONE_NET}"}
```

### The two Dockerfiles

Billing builds one image per target. Ledger builds one image, and its `consumer` service overrides the command.

```dockerfile
# billing-api/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY . .
RUN pip install .

FROM base AS api
CMD ["uvicorn", "billing.api:app", "--host", "0.0.0.0"]

FROM base AS worker
CMD ["python", "-m", "billing.worker"]
```

```dockerfile
# ledger-api/Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install .
CMD ["uvicorn", "ledger.api:app", "--host", "0.0.0.0"]
```

## What the indexer can and cannot read

| File | Readable from the file | Missing from the file |
|---|---|---|
| Infrastructure | Stack `acme-infra`. Network `acme-backbone`. `kafka` and `postgres` have no build context, so they are external services. | Nothing. |
| Billing | Network `acme-backbone`. Each build target has the name of a binary, so each service maps to its binary. The stack is named after the folder, `billing-api`. | Nothing. |
| Ledger | Two services built from the project. Which binary each service runs: `api` runs `uvicorn ledger.api:app` from the Dockerfile's `CMD`, and `consumer` runs `python -m ledger.consumer run` from its compose `command`. | The Compose name, set by `-p`. The network's real name, set by a variable. |
| Dockerfiles | The command line each service runs, and so each binary's framework: billing's and ledger's `api` are FastAPI apps, started by uvicorn. | Nothing. |

The configuration fills exactly the gaps in the right-hand column.

## The configuration

```yaml
# ~/acme/workspace/.workbench/config.yml
version: 1
compose:
  - files: [docker-compose.yml]       # the shared infrastructure stack
    projects: [billing-api, ledger-api]
projects:
  - id: shared-api
    path: ../shared-api
    language: python
    dependency_manager: uv
  - id: billing-api
    path: ../billing-api
    language: python
    dependency_manager: uv
    binaries:
      - {name: api,    entry: src/billing/api.py}
      - {name: worker, entry: src/billing/worker.py}
    links:
      - {service: postgres, via: database, binary: api}
      - {service: kafka, via: topic, name: invoice.created, role: publish, binary: worker}
  - id: ledger-api
    path: ../ledger-api
    language: python
    dependency_manager: poetry
    binaries:
      - {name: api,      entry: src/ledger/api.py}
      - {name: consumer, entry: src/ledger/consumer.py}
    compose:
      name: ledger                     # set by `-p ledger`, not in the file
      networks:
        backbone: acme-backbone        # the file only says ${BACKBONE_NET}
    links:
      - {service: kafka, via: topic, name: invoice.created, role: subscribe, binary: consumer}
  - id: web-app
    path: ../web-app
    language: typescript
    dependency_manager: pnpm
    binaries:
      - {name: admin, entry: projects/admin/src/main.ts, framework: angular}
    links:
      - {service: api, stack: billing-api, via: http, binary: admin}
```

Points to notice:

- **Billing has no `compose` block.** Its compose file is found by default and everything in it is readable.
- **Ledger's `compose` block lists no `files`.** Its compose file is found by default too; the block only adds what the file cannot say.
- **`stack: billing-api` on the web-app link is required,** because a service named `api` exists in two stacks.
- **That stack name comes from a folder name.** It holds only while the repository is cloned as `billing-api`. Because web-app's link names the stack, `index` warns about it (`StackNamedAfterFolder`). A `name` in billing's compose file removes the warning.
- **Local dependencies are not written.** The indexer reads them from each project's `pyproject.toml`. Both APIs depend on `shared-api`.
- **`kafka` and `postgres` take no entry anywhere.** They are read from the infrastructure file as external services.

## How networks work

A network is only a name. For each real name, the indexer collects the services that join it.

| Network | Services | Stack |
|---|---|---|
| `acme-backbone` | `kafka`, `postgres` | `acme-infra` |
| `acme-backbone` | `api`, `worker` | `billing-api` |
| `acme-backbone` | `api`, `consumer` | `ledger` |
| `billing-api_default` | `api`, `worker` | `billing-api` |

- **A network with no stated name** is called `<Compose name>_<network>`. That is where `billing-api_default` comes from, and why the Compose name matters.
- **Without the `networks` override,** ledger's network is unknown. The indexer warns, and ledger appears cut off from `kafka`.
- **With the override,** `acme-backbone` joins three stacks, so the graph knows ledger's consumer can reach `kafka`. The override always wins over the name in the file, and the indexer only logs that it was used.
- **Links are checked against networks.** The worker publishes to `kafka`, and both are on `acme-backbone`, so the link is possible. A link between two services that share no network gets a warning.
- **`web-app` runs on the host,** so it has no network and its link is not checked.

Networks say who can talk. Links say who does talk, and how.

## What ends up in the graph

| Source | Nodes and edges |
|---|---|
| Configuration | Four projects and five binaries. One topic, `kafka/invoice.created`. Four links: database, publish, subscribe, HTTP. |
| Compose files | Three stacks, and which projects use each. Four services and two external services. Two networks, and each service's membership. The binary each billing service runs, from its build target, and the command ledger's `consumer` runs. |
| Dockerfiles | The command each other service runs: so ledger's `api` runs its `api` binary, and billing's and ledger's `api` binaries are FastAPI. |
| Dependency manager files | `billing-api` depends on `shared-api`. `ledger-api` depends on `shared-api`. |
| Source code | Files, classes, functions and imports inside each project, including imports of `shared_api` that resolve to nodes in `shared-api`. |

## What this gives an AI

Suppose the question is: "I am renaming a field on `Invoice` in `shared-api`. What breaks?"

Without the workspace configuration, an AI sees four unrelated repositories. With the graph, it can follow this path:

1. `Invoice` is defined in `shared-api`.
2. `billing-api` and `ledger-api` both import it. These are local dependencies read from their manifests.
3. Billing's `worker` publishes `invoice.created` to `kafka`.
4. Ledger's `consumer` subscribes to that same topic, so the two must change together.
5. Web-app's `admin` calls billing's `api` over HTTP, so the shape of its responses may change too.
6. Ledger's `api` and billing's `api` share a network and have no link, so nothing suggests they call each other.

Steps 3 to 5 rest on the hand-written `links`. Release 1 also reads the code behind them. Billing's `send_invoice` is matched to `invoice.created` as a `Sends` edge and ledger's `run_consume` as a `Receives` edge, each carrying `Invoice`. A Python HTTP call is matched to the route it calls as a `Requests` edge. A match never creates a link, and a match with no declared link is a warning. Web-app's call in step 5 stays a declared link until TypeScript is parsed in Release 2. [python-parsing.md](./python-parsing.md#acme-shop-with-fastapi) works the same question through with the code.
