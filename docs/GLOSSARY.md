# Semantic Workbench

Turns the source code and infrastructure files of a workspace into a graph that AI tools can query.

## Language

**Workspace**:
A set of projects described by one configuration file and indexed into one graph.
_Avoid_: Repository, monorepo

**Workspace root**:
The folder that holds `.workbench/`. A project's path in the configuration is written relative to it.
_Avoid_: Base directory, config folder

**Project**:
One unit of source code listed in the workspace configuration, with its own root folder and dependency manager.
_Avoid_: Package, module, app

**Import name**:
A name other projects' code imports a project by, which can differ from the name the project is installed by.
_Avoid_: Package name, module name

**Node**:
One thing the graph knows about, such as a file, a function, a project or a service.
_Avoid_: Symbol, entity, vertex

**Code node**:
A node read from source code, such as a file, a class or a function. It always belongs to one project.
_Avoid_: Symbol

**Workspace node**:
A node that comes from the configuration or a compose file rather than source code, such as a project, a binary, a service or a topic.
_Avoid_: Infrastructure node

**Edge**:
A directed relationship of one kind from one node to another.
_Avoid_: Link, relation, reference

**Scope**:
What a node belongs to: the workspace, one project or one stack. The scope is part of the node's id.
_Avoid_: Namespace, owner

**Origin**:
Where a node came from: parsed from a file, or declared with no file.
_Avoid_: Source, location

**Service**:
One running unit declared in a compose file, belonging either to one project or to none.
_Avoid_: Container, image

**Stack**:
All the services that run together under one Compose name, from one compose file or several.
_Avoid_: Compose project, deployment

**Compose name**:
The name Docker Compose runs a stack under. It identifies the stack, and no two stacks share one.
_Avoid_: Compose project name, stack id

**Network**:
A named container network that services join; services on the same network can reach each other.

**External service**:
A service that runs a stock image and belongs to no project, such as a database or a message broker.
_Avoid_: Stock image, external container, infrastructure

**Project compose file**:
A compose file inside one project that describes only that project's services.

**Shared compose file**:
A compose file outside any single project whose services come from more than one project.
_Avoid_: Root compose, global compose

**Binary**:
One runnable entry point inside a project.
_Avoid_: Executable, app, target

**Framework**:
The library a binary is built on, such as FastAPI, which decides what more the indexer reads from the code. A binary built on none is a **plain binary**.
_Avoid_: Stack (that is a set of services), platform

**Route**:
One HTTP or WebSocket endpoint that a binary serves: a method and a path, handled by one function.
_Avoid_: Endpoint, URL, API

**Provider**:
A function or class that a framework calls to supply a value to a route or to another provider, such as one named in FastAPI's `Depends`.
_Avoid_: Dependency (that is a local dependency), injectable

**Command**:
One thing a command-line binary can be told to do, such as `ledger-consumer replay`, with its options and the code that runs it.
_Avoid_: Subcommand, verb, task

**Root**:
A place from which code starts to run: a binary's entry file, a module named in a command, or a test file.
_Avoid_: Entry (that is a binary's file), starting point

**Reach**:
The code a root may run: everything its calls, imports and references lead to.
_Avoid_: Coverage, call graph, reachability

**Local dependency**:
One project using another project's code, either read from the dependency manager's files or declared by hand.
_Avoid_: Internal dependency, workspace dependency

**Topic**:
A named stream inside an external service, where every subscriber receives each published message.
_Avoid_: Channel, event, stream

**Queue**:
A named line of messages inside an external service, where each message goes to one consumer.
_Avoid_: Channel, job list

**Link**:
A runtime connection declared by hand in the configuration: an HTTP or gRPC call, a database connection, or publishing or subscribing to a topic or queue. Each link becomes an edge.
_Avoid_: Connection, dependency

**Mode**:
What the MCP server is started for: developer support, operational support or testing support. The mode decides which tools an AI tool is offered.
_Avoid_: Profile, role

**Context**:
One deployment of the workspace that the operational mode can look into, such as staging or production.
_Avoid_: Environment (that is a project's own environment, for language servers), cluster, stage

**Release branch**:
The branch of a project that is deployed to a context.
_Avoid_: Deploy branch, version

**Checkout**:
The branch and commit a project was on when it was last indexed.
_Avoid_: Revision, snapshot

**Skill**:
A short written guide an AI tool loads when it needs it, shared by every mode.
_Avoid_: Prompt, rule, instruction file

**Caller**:
A function or method that calls a given node. The node it calls is its **callee**.
_Avoid_: Parent, user

**Call flow**:
The chain of calls, imports and links that connects a set of nodes, inside one project or across several.
_Avoid_: Call graph, trace

**Blast radius**:
Everything that may be affected when a node changes: the code that uses it, and the projects, binaries and services that code reaches.
_Avoid_: Impact set, ripple

**Provenance**:
How an edge came to exist: read from source code, read from a dependency manager's files, read from a compose file, declared by hand, or inferred.
_Avoid_: Source, origin
