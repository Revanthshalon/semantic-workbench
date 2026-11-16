# Product Vision

The capability map, the roadmap and the usage guide all follow from this page.

## The problem

An AI coding tool sees the files it is shown. It does not see how a workspace fits together: which project uses which shared library, which service talks to which, what a change in one repository breaks in another. In a workspace made of several projects, that missing picture is where most wrong answers come from.

## What Semantic Workbench is

A command-line tool that reads a workspace and stores what it finds as a graph: the code inside each project, the projects themselves, the services that run them, and the links between all of these. AI tools query the graph through an MCP server. People query it through the same command line.

## Who it is for

A developer, or a small team, working in a workspace of several projects with shared local libraries and Docker Compose files, who uses an AI coding tool and wants it to understand the whole workspace.

## What makes it different

- **It works across projects.** One graph covers every project in the workspace, including projects cloned as separate repositories.
- **It knows what runs.** Services, networks, topics and queues are in the graph next to the code.
- **It says how it knows.** Every relationship records whether it was read from source, read from a manifest or a compose file, written by hand, or inferred.
- **A person can fill the gaps.** What the tool cannot read is declared in one configuration file.

## Principles

1. **The source is the truth.** The graph is derived data and can always be rebuilt from the workspace.
2. **Nothing changes behind your back.** The graph changes only when you run `workbench index`.
3. **Explicit over clever.** A fact the tool cannot read is declared by hand. It is not guessed silently.
4. **Local by default.** The first release makes no network calls and sends no code anywhere.
5. **One core, two doors.** The command line and the MCP server call the same use cases and give the same answers.

## What it is not

- Not a language server. It does not offer completion or live diagnostics.
- Not a search engine for code text. It answers questions about structure and relationships.
- Not a deployment tool. It reads compose files and never starts or changes anything.
- Not an AI model. In the first release it uses no LLM.

## The first release

A thin slice of the whole idea, enough for the [Acme Shop example](./example-workspace.md) to work end to end:

- Python code graph.
- The whole workspace layer: projects, local dependencies, compose files, networks and hand-written links.
- SQLite storage.
- The command line and the MCP server.

What follows is in the [roadmap](./roadmap.md).
