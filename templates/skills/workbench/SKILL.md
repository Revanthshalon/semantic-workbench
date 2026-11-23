---
name: workbench
description: Query the Semantic Workbench graph of this workspace with the `workbench` command. Use it before reading many files, before changing shared code, and to find what calls what across projects, services and topics.
---

# Workbench

> **TO_REFINE: rough draft.** Written from the usage guide. Tune it by trying it with Claude Code and GitHub Copilot.

`workbench` holds a graph of every project in this workspace: the code, the projects, the services that run them, and the links between them (HTTP calls, topics, queues, databases). Ask it before opening files one by one. Every command here only reads.

Always add `--json`, and read the JSON it prints.

## Start here

```bash
workbench explore "<question in plain words>" --json
```

One call returns the source of the relevant code, how it connects across projects, and what a change would affect. Start with it for any question about how something works.

## Which command for which question

| Question | Command |
|---|---|
| How does X work? Where is X? | `workbench explore "<question>" --json` |
| Find something by name | `workbench query <text> --kind <kind> --project <id> --json` |
| Show one thing, with its source | `workbench node <node> --json` |
| Show part of a file | `workbench node --file <project>:<path> --offset <n> --limit <n> --json` |
| What calls this? What does it call? | `workbench callers <node> --json`, `workbench callees <node> --json` |
| What breaks if I change this? | `workbench impact <node> --json` |
| Which tests should I run? | `workbench impact <node> --tests --json` |
| What is it connected to (networks, links, topics)? | `workbench neighbors <node> --json` |
| How do the projects depend on each other? | `workbench deps --json` |
| Which files are indexed, failed or unreached? | `workbench files --json`, with `--failed` or `--unreached` |
| Is the graph current? | `workbench status --json` |

## Naming a node

- `<scope>:<qualified name>`, such as `shared-api:shared_api.models.Invoice`. The scope is a project id, or a stack's Compose name for a service.
- Or the 16-character id from an earlier answer, such as `9f2c41d07ab35e18`.
- If the answer lists several matches, pick one and ask again with it.

## Before changing code

1. `workbench impact <node> --json`: read every project it names, the API and event contracts, and the services affected.
2. `workbench impact <node> --tests --json`: run the tests it lists.
3. A change to a model in a shared library can break other repositories. The API contract names their callers.

## Reading an answer

- Each step says how it is known: read from source, from a manifest or compose file, written by hand, and which rule resolved it. `flow` means it rests on every caller agreeing. Trust a declared link less than a call read from source.
- `freshness` says when the graph was indexed and how many files have changed since. If files have changed, or `moved_projects` is not empty, tell the user to run `workbench index`. Never run it yourself.
- `truncated` says what a budget left out. Ask a narrower question rather than repeating the same one.
- An error that says to run `workbench index` means the graph is missing. Tell the user.

## Never

- Never run `workbench index`, `init`, `check` or `skills link` on your own. They are the user's to run.
- Do not guess a link between services. If an HTTP call or a topic is not in the graph, the answer or `status` will say which `links` entry is missing. Suggest it to the user.
