---
status: accepted
date: 2026-11-22
---

# Dockerfiles are read for the command line a service runs

A service built from a project usually takes its command line from its Dockerfile, not from compose: billing's `api` stage ends in `CMD ["uvicorn", "billing.api:app"]`. Reading compose files alone left that line unknown. So the service's binary had to be mapped by hand, its framework came from probing code, and its command could not be linked. The workspace layer now reads the Dockerfile of each built service. It works out the command line by Docker's own rules: the build target's stage, `ENTRYPOINT` and `CMD` inherited across stages, overrides from compose, `ARG` and `ENV` defaults, and wrappers such as entrypoint scripts and `tini`. Facts that come from it carry a new provenance, `Dockerfile`.

## Considered options

- **Keep reading compose files only.** Rejected: most services give no `command` in compose, so their binary, framework and command would stay unknown, or be written by hand. The configuration is for what files cannot say.
- **Read every instruction** (`RUN`, `COPY`, `EXPOSE`, `HEALTHCHECK`, ...). Rejected: the graph uses none of them. Only `FROM`, `ARG`, `ENV`, `ENTRYPOINT` and `CMD` are read.
- **Build and inspect the images.** Rejected: nothing is run (step 4's constraint), and an index must stay fast and offline.

## Consequences

- A service is matched to the binary whose entry its command line runs, when neither the configuration nor the build target names one. Acme's ledger needs no `services` mapping any more.
- The command line is source 2 for a binary's framework and app, and gives the command words for `Invokes` (ADR 0020).
- A missing or unreadable Dockerfile raises `DockerfileUnreadable`, and the service is matched as if it had none.
- A command line given by an outside base image cannot be read, because only the workspace's own files are.

Details: [python-parsing.md](../python-parsing.md#the-command-a-service-runs), [step 4](../implementation-plan/step-4-workspace-indexing.md).
