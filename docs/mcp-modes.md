# MCP Modes, Contexts and Skills

What `workbench init` puts in `.workbench/` besides the workspace configuration: the skills every mode of the MCP server shares, and the files that tell the operational mode how to reach each deployment.

> **Nothing here is built yet.** The folders are written by `init` in Release 1. Operational support ships in Release 3; see the [roadmap](./roadmap.md). The operational tools on this page are **proposed**: they were drafted from the sample context file and are not confirmed.

Related pages: [usage guide](./usage-guide.md), [configuration guide](./configuration-guide.md), [capability map](./capability-map.md). Terms are defined in [GLOSSARY.md](./GLOSSARY.md).

## What `init` creates

```
.workbench/
├── config.yml                  # the workspace: projects, stacks, links
├── .gitignore                  # keeps graph.db out of version control
├── graph.db                    # the graph; written by `workbench index`
├── skills/                     # shared by every mode
│   ├── workbench/SKILL.md
│   └── python/SKILL.md
└── mcp/
    ├── config.yml              # which contexts there are, and the default
    └── contexts/               # one file per context
        ├── production.yml
        ├── staging.yml
        └── testing.yml
```

Commit everything but `graph.db`. `init` never overwrites a file that is already there, so a team's edits to a skill or a context are safe.

Samples of both kinds of file are in [`templates/mcp/`](../templates/mcp/).

## Modes

The MCP server runs in one mode at a time. The mode is chosen on the command line and has no file of its own.

```bash
workbench mcp --mode developer-support      # the default
workbench mcp --mode operational-support
```

An AI tool that needs two modes gets two entries in its MCP configuration, one per mode.

| Mode | For | Offers | Ships |
|---|---|---|---|
| `developer-support` | Writing and changing code | The graph tools, and later the help of a language server | Release 1. The language server is on the roadmap |
| `operational-support` | Finding the cause of an incident and proposing a resolution | Read-only tools that look into a deployment, plus the graph tools for code context | Release 3 |
| `testing-support` | Not decided | Nothing | The name is reserved. The server refuses to start in it |

No mode changes the graph, the code or anything that runs. Every tool in every mode only reads.

### `developer-support`

The mode for day-to-day coding. It offers every graph tool of the [usage guide](./usage-guide.md#connecting-an-ai-tool): `explore`, `node`, `search`, `callers`, `callees`, `impact`, `neighbors`, `files`, `dependencies` and `status`. It makes no network calls.

When language servers arrive, this mode adds them: going to a definition, finding references and reading diagnostics at question time. The language server starts inside each project's own environment, as given by `lsp` and `projects[].environment` in the workspace configuration. No other mode uses a language server.

### `operational-support`

The mode for an incident. An AI tool looks at what a deployment is doing, reads the code that does it from the graph, and proposes a cause and a resolution. It can change nothing.

It works in one **context** at a time: one deployment of the workspace, such as staging. `init` writes three: `testing`, `staging` and `production`. Every operational tool takes the context as an argument and uses `default_context` when none is given, so one conversation can compare what staging and production are doing.

This is the one part of Workbench that uses the network. It connects only to the machine a context file names, and only when a tool is called.

### `testing-support`

A name and nothing more. `workbench mcp --mode testing-support` stops with a message that the mode is not available yet.

## `mcp/config.yml`: the contexts

```yaml
# .workbench/mcp/config.yml
default_context: staging
contexts:
  production: contexts/production.yml
  staging:    contexts/staging.yml
  testing:    contexts/testing.yml
```

| Field | Required | Meaning |
|---|---|---|
| `default_context` | yes | The context a tool uses when it is given none. It must be a key of `contexts` |
| `contexts` | yes | One entry per context: its name, and the path of its file, relative to `.workbench/mcp/` |

## A context file

A context file says which release is deployed there and how to reach it. The complete sample is [`templates/mcp/contexts/staging.yml`](../templates/mcp/contexts/staging.yml).

### How a context is reached

Everything goes through one virtual machine, over SSH. Workbench logs in to the VM and reaches the cluster, the databases and the broker from there. Nothing else in the deployment has to be open to your machine.

A connection to a database, a cache or a broker has an `access` of one of two kinds:

| `access` | How it works | Where the password is |
|---|---|---|
| `tunnel`, the default | Workbench forwards a port through the VM and connects from your machine | In an environment variable on your machine, named by `password_env` |
| `remote` | Workbench runs the VM's own client program, such as `psql`, over SSH | On the VM, for example in its `.pgpass`. The context file holds none |

### The release branch

| Field | Required | Meaning |
|---|---|---|
| `version` | yes | Always `1` |
| `branch` | yes | The release branch deployed to this context |
| `branches` | no | The release branch of one project, when it differs. The key is a project id from the workspace configuration |

The branch is tracked for each project, because each project is its own repository. `workbench index` records the branch and commit every project was on. In `operational-support` mode, Workbench compares that with the branch the context names for the project, and every operational answer lists the projects that do not match. The code an AI reads is then known to be, or known not to be, the code that is deployed.

### `ssh`: the way in

Required.

| Field | Default | Meaning |
|---|---|---|
| `host` | | Required. The VM |
| `port` | `22` | |
| `user` | | Required |
| `password_env` | | The name of the environment variable that holds the SSH password. The sample also allows `password`, written in the file |
| `host_key` | | The VM's key fingerprint. Without it, your `known_hosts` must already list the host |
| `connect_timeout` | | Seconds |

### `kubectl`: the cluster

Runs on the VM, through SSH.

| Field | Default | Meaning |
|---|---|---|
| `binary` | `kubectl` | The program on the VM |
| `kubeconfig` | | Its configuration file on the VM |
| `context` | | The name of the kubectl context. This is kubectl's own word, not a Workbench context |
| `namespace` | | Required |

### `compose`: Docker Compose on the VM

Optional.

| Field | Default | Meaning |
|---|---|---|
| `binary` | `docker` | The program on the VM |
| `project_dir` | | An absolute path on the VM |
| `files` | `compose.yaml` | Relative to `project_dir` |

### `postgres`, `redis` and `kafka`

`postgres` and `redis` each hold named connections. `kafka` holds one. Hosts and ports are written as the VM sees them.

| Section | Fields |
|---|---|
| `postgres.<name>` | `host`, `port` (default `5432`), `database`, `user`, `password_env`, `sslmode` (`disable`, `prefer`, `require`, `verify-ca` or `verify-full`; default `require`), `access`, and `binary` (default `psql`) with `access: remote` |
| `redis.<name>` | `host`, `port` (default `6379`), `db`, `tls`, `password_env`, `access`, and `binary` (`redis-cli`) with `access: remote` |
| `kafka` | `brokers`, `security` (`plaintext`, `ssl`, `sasl_plaintext` or `sasl_ssl`; default `plaintext`), `sasl_mechanism` (`plain`, `SCRAM-SHA-256` or `SCRAM-SHA-512`), `username`, `password_env`, `access`, and `bin_dir` with `access: remote` |

With `access: remote` a connection holds no password.

## The operational tools (proposed)

One group of tools for each section of a context file. Every tool takes `context`, and every tool only reads.

| Tool | Reads | How it is kept read-only |
|---|---|---|
| `context_status` | Which contexts exist, whether the VM answers, and for each project whether the indexed branch is the release branch | It only connects |
| `kube_pods` | The pods of the namespace, with their state and restarts | Runs `kubectl get` |
| `kube_describe` | One pod, deployment or service in full | Runs `kubectl describe` |
| `kube_events` | The recent events of the namespace | Runs `kubectl get events` |
| `kube_logs` | The logs of a pod or a deployment, limited by time, by line count and by a search text | Runs `kubectl logs` |
| `compose_status` | The services of the Compose project on the VM and their state | Runs `docker compose ps` |
| `compose_logs` | The logs of one of those services | Runs `docker compose logs` |
| `postgres_query` | The rows of one `SELECT` | The statement runs in a read-only transaction, with a time limit and a row limit |
| `redis_read` | A key, its type and time to live, or a scan of key names | Only commands from a fixed list of reading commands are sent |
| `kafka_topics` | The topics and their partitions | Lists only |
| `kafka_lag` | How far each consumer group is behind | Lists only |
| `kafka_peek` | The latest messages of a topic | Reads without a consumer group, so no offset is committed |

The graph tools are offered in this mode as well. They give the code context: `kube_logs` shows an error, `explore` shows the code that raised it, and `impact` shows what else that code touches.

Workbench never passes text from the AI tool to a shell. Each tool builds its own command from checked arguments.

## Skills

A skill is a short written guide an AI tool loads when it needs it. Skills are the same in every mode.

| Skill | Written by `init` | Says |
|---|---|---|
| `workbench` | always | Start with `explore`. How to name a node. What to do when an answer says the graph is out of date |
| `python` | always | The best practices for Python code |
| `typescript` | from Release 2 | The best practices for TypeScript and Angular code |

- **One folder per skill,** holding a `SKILL.md`. The file starts with a `name` and a `description`, and the guide follows as Markdown.
- **The best practices of each language are shared.** Every workspace starts from the same guide for a language, so every AI tool follows the same conventions.
- **A team owns its copy.** Edit the skills `init` wrote, and add a folder for each of your own.
- **The MCP server offers every skill in the folder,** in every mode, to the AI tool that connects.
- **A skill never changes what a tool returns.** It is guidance for the AI tool, not configuration.

## Open points

| Point | What needs deciding |
|---|---|
| The operational tools | The table above is a proposal. The names, the arguments and the limits need confirming |
| A password written in a context file | The sample allows `ssh.password`. The workspace configuration forbids secrets in files, and a context file is meant to be committed |
| From a pod to a project | A pod or a Compose service on the VM is not yet tied to a service, a binary or a project in the graph. Until it is, the AI tool makes that step by name |
| How a skill reaches the AI tool | Proposed: each skill is offered as an MCP prompt and as an MCP resource |
| What `testing-support` is for | Not decided |
