---
status: accepted
date: 2026-11-23
---

# Skills reach AI tools through links in the workspace root

`init` writes the shared skills into `.workbench/skills/<name>/SKILL.md`. An AI tool still has to find them. ADR 0022 proposed listing each skill in the UTCP manual with its path, and leaving the AI tool to read the file. Whether a manual can carry anything but tools was never confirmed. AI platforms already load skills from folders of their own. So we link each skill into those folders instead, and the manual lists tools only.

The links are made in the workspace root, one per skill and platform. Each is relative, so it works on any machine the workspace is cloned to:

| Platform | Link | Points to |
|---|---|---|
| `claude` (Claude Code) | `<workspace>/.claude/skills/<name>` | `../../.workbench/skills/<name>` |
| `copilot` (GitHub Copilot) | `<workspace>/.github/skills/<name>` | `../../.workbench/skills/<name>` |

Linking is opt-in: `workbench init --enable-shared-skills` makes the links on first setup, and `workbench skills link` makes them at any later time. `init` refuses to run once a configuration exists, so it alone could never serve a teammate or a new skill. Both take `--platform claude|copilot`, repeatable. Without it, both platforms are linked.

## Considered options

- **List skills in the UTCP manual.** Rejected: it depends on clients accepting a field the UTCP pages do not define, and AI platforms already have a place for skills.
- **Links in each project's folder.** Rejected: an AI tool opened inside a project would find them, but every project repository would hold links into a folder outside it.
- **Links in the user's home folder** (`~/.claude/skills/`). Rejected: one set of links for every repository the user opens, and two workspaces would clash.
- **A setting in `config.yml`, linked by `index`.** Rejected: `index` would write outside `.workbench/` on every run, and the graph command would change files that are not the graph.
- **A flag on `init` only.** Rejected: `init` refuses an existing configuration, so a teammate who clones the workspace could never use it.

## Consequences

- An AI tool sees the shared skills when it is opened at the workspace root. Opened inside a project, it does not. The usage guide says so.
- Linking never overwrites. A link that already points to the skill is kept. A file, a folder or another link at that path is left alone and reported. This follows K3: a team's own skills are never touched.
- `skills link` is safe to run again. It links skills added since, and removes nothing.
- The links are relative, so a team may commit them. A teammate then gets them with the clone, and `skills link` only adds new ones.
- The manual no longer lists skills, so step 8 has no skills task, and `build_manual` takes no skills.
- The paths of each platform are a default. A platform that moves its skills folder needs a new release of `workbench`. `TO_REFINE`: confirm Copilot's folder, `.github/skills/`, against its documentation when this is built.

Details: [modes.md](../modes.md#skills), [step 2](../implementation-plan/step-2-configuration.md#task-6-link-the-shared-skills).
