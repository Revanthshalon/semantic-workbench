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
One unit of source code listed in the workspace configuration, with its own root directory and dependency manager.
_Avoid_: Package, module, app

**Node**:
One thing the graph knows about, such as a file, a function or a class.
_Avoid_: Symbol, entity, vertex

**Edge**:
A directed relationship of one kind from one node to another.
_Avoid_: Link, relation, reference

**Service**:
One running unit declared in a compose file, belonging either to one project or to none.
_Avoid_: Container, image

**Stack**:
All the services that run together under one Compose name, from one compose file or several.
_Avoid_: Compose project, deployment

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

**Local dependency**:
One project using another project's code, either read from the dependency manager's files or declared by hand.
_Avoid_: Internal dependency, workspace dependency

**Topic**:
A named stream inside an external service, where every subscriber receives each published message.
_Avoid_: Channel, event, stream

**Queue**:
A named line of messages inside an external service, where each message goes to one consumer.
_Avoid_: Channel, job list

**Provenance**:
How an edge came to exist: read from source, declared by hand, or inferred.
_Avoid_: Source, origin
