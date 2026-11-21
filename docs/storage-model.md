# Storage Model

How the knowledge graph is kept in SQLite: every table, column and index, and how the store is written and read. It is the plan for step 3 of the [roadmap](./roadmap.md) and covers capabilities S1 to S3 of the [capability map](./capability-map.md).

The types being stored, and the rules they keep, are in [domain-model.md](./domain-model.md). This page adds nothing to them. It only says where each field goes.

> **Nothing here is built yet.** The schema below has been run against SQLite 3.54 and its constraints tested, so it is known to be valid. The store that uses it is not written.

## Where the store is

One SQLite file, `.workbench/graph.db` unless `storage.path` says otherwise. It is derived data: deleting it loses nothing, and `workbench index --force` rebuilds it.

The file is opened with:

| Setting | Value | Why |
|---|---|---|
| `journal_mode` | `WAL` | Queries and the MCP server keep reading while an index writes |
| `foreign_keys` | `ON` | The edge and reference tables rely on it. SQLite leaves it off by default |
| `synchronous` | `NORMAL` | Safe with WAL, and the store can always be rebuilt |

## How a value is written

| Value | Stored as |
|---|---|
| `NodeId`, and the id of an unresolved reference | Text, 16 lowercase hex characters |
| `ContentHash` | Text, 64 lowercase hex characters |
| A kind, a provenance, a status or any other fixed set of names | Text in snake_case: `ExternalService` is `external_service`, `TreeSitter` is `tree_sitter` |
| A scope | Two columns: `scope_type` is `workspace`, `project` or `stack`; `scope_name` is the project id or the Compose name, and empty for `workspace` |
| An origin | Five columns: `path` and the four numbers of the span. All five are empty for a declared node |
| A site | Three columns: `site_path`, `site_line`, `site_column`. All three are empty for an edge with no place |
| The data of an edge kind | Its own typed columns, empty for every other kind. See [`edges`](#edges) |
| The data of a node kind | One column per field, empty for kinds whose data has no such field. See [`nodes`](#nodes) |
| A prefix (`Mounts` data, a router's prefix) | Text. An unknown prefix is written `{?}`, which no literal path segment can be. No prefix is empty |
| A call site's arguments | Text holding a JSON array of `{"position": 0, "shape": "name", "value": "repo"}` or `{"keyword": "db", ...}`. They are only ever read whole, so they are not split into columns |
| A flag | Integer, `0` or `1` |
| A list of text | Text holding a JSON array, `[]` when empty |
| A time | Text, UTC, ISO 8601, such as `2026-11-16T09:12:00Z` |

## The schema

Format version `1`.

```sql
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE nodes (
  id              TEXT PRIMARY KEY CHECK (length(id) = 16),
  kind            TEXT NOT NULL,
  name            TEXT NOT NULL CHECK (name <> ''),
  qualified_name  TEXT NOT NULL CHECK (qualified_name <> ''),
  scope_type      TEXT NOT NULL CHECK (scope_type IN ('workspace', 'project', 'stack')),
  scope_name      TEXT,
  path            TEXT,
  start_line      INTEGER,
  start_column    INTEGER,
  end_line        INTEGER,
  end_column      INTEGER,
  -- ProjectData
  language        TEXT CHECK (language IN ('python', 'typescript')),
  -- BinaryData
  framework        TEXT CHECK (framework IN ('fastapi', 'angular', 'none')),
  framework_source TEXT CHECK (framework_source IN ('declared', 'compose', 'entry')),
  app              TEXT,
  -- Doc, Callable, TypeDecl, Member
  doc             TEXT,
  signature       TEXT,
  visibility      TEXT CHECK (visibility IN ('public', 'private', 'protected', 'internal')),
  is_exported     INTEGER NOT NULL DEFAULT 0 CHECK (is_exported IN (0, 1)),
  is_async        INTEGER NOT NULL DEFAULT 0 CHECK (is_async IN (0, 1)),
  is_static       INTEGER NOT NULL DEFAULT 0 CHECK (is_static IN (0, 1)),
  is_abstract     INTEGER NOT NULL DEFAULT 0 CHECK (is_abstract IN (0, 1)),
  decorators      TEXT NOT NULL DEFAULT '[]',
  type_parameters TEXT NOT NULL DEFAULT '[]',
  return_type     TEXT,
  declared_type   TEXT,
  default_value   TEXT,
  param_source    TEXT CHECK (param_source IN ('path', 'query', 'header', 'cookie', 'body', 'form', 'file')),
  role            TEXT CHECK (role IN ('app', 'router', 'middleware', 'exception_handler', 'lifecycle_hook', 'model')),
  router_prefix   TEXT,
  -- RouteData
  route_method    TEXT CHECK (route_method IN
                    ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace', 'websocket')),
  route_path      TEXT,
  route_status    INTEGER,
  route_tags      TEXT NOT NULL DEFAULT '[]',
  CHECK ((scope_type = 'workspace') = (scope_name IS NULL)),
  CHECK ((path IS NULL) = (start_line IS NULL)
     AND (path IS NULL) = (start_column IS NULL)
     AND (path IS NULL) = (end_line IS NULL)
     AND (path IS NULL) = (end_column IS NULL)),
  CHECK ((kind = 'project') = (language IS NOT NULL)),
  CHECK ((kind = 'binary') = (framework IS NOT NULL)),
  CHECK ((framework IS NULL) = (framework_source IS NULL)),
  CHECK (app IS NULL OR framework IS 'fastapi'),
  CHECK (param_source IS NULL OR kind = 'parameter'),
  CHECK (router_prefix IS NULL OR role IS 'router'),
  CHECK ((kind = 'route') = (route_method IS NOT NULL)),
  CHECK (kind = 'route' OR (route_path IS NULL AND route_status IS NULL AND route_tags = '[]'))
);

CREATE INDEX nodes_kind           ON nodes (kind);
CREATE INDEX nodes_name           ON nodes (name);
CREATE INDEX nodes_lower_name     ON nodes (lower(name));
CREATE INDEX nodes_qualified_name ON nodes (scope_type, scope_name, qualified_name);
CREATE INDEX nodes_file           ON nodes (scope_name, path, start_line);

CREATE TABLE edges (
  id               INTEGER PRIMARY KEY,
  source           TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  target           TEXT NOT NULL REFERENCES nodes (id) DEFERRABLE INITIALLY DEFERRED,
  kind             TEXT NOT NULL,
  site_path        TEXT,
  site_line        INTEGER,
  site_column      INTEGER,
  provenance       TEXT NOT NULL CHECK (provenance IN
                     ('tree_sitter', 'scip', 'manifest', 'compose', 'declared', 'heuristic')),
  resolved_by      TEXT CHECK (resolved_by IN
                     ('import', 'self_member', 'same_file', 'project', 'cross_project', 're_export',
                      'annotation', 'local_inference', 'inherited', 'flow', 'framework')),
  note             TEXT,
  import_specifier TEXT,
  import_alias     TEXT,
  import_type_only INTEGER CHECK (import_type_only IN (0, 1)),
  dependency_scope TEXT CHECK (dependency_scope IN ('build', 'dev')),
  protocol         TEXT CHECK (protocol IN ('http', 'grpc', 'database')),
  mount_prefix     TEXT,
  CHECK ((kind = 'imports')     = (import_specifier IS NOT NULL)),
  CHECK (import_alias IS NULL OR kind = 'imports'),
  CHECK ((kind = 'imports')     = (import_type_only IS NOT NULL)),
  CHECK ((kind = 'depends_on')  = (dependency_scope IS NOT NULL)),
  CHECK ((kind = 'connects_to') = (protocol IS NOT NULL)),
  CHECK (mount_prefix IS NULL OR kind = 'mounts'),
  CHECK ((site_path IS NULL) = (site_line IS NULL)
     AND (site_path IS NULL) = (site_column IS NULL)),
  CHECK (note IS NULL OR provenance = 'declared'),
  CHECK (resolved_by IS NULL OR provenance IN ('tree_sitter', 'scip')),
  CHECK (resolved_by IS NOT 'flow' OR kind IN ('calls', 'instantiates')),
  CHECK ((kind IN ('mounts', 'handles', 'injects')) = (resolved_by IS 'framework'))
);

CREATE UNIQUE INDEX edges_identity ON edges
  (source, target, kind, ifnull(site_path, ''), ifnull(site_line, -1), ifnull(site_column, -1));
CREATE INDEX edges_source_kind ON edges (source, kind);
CREATE INDEX edges_target_kind ON edges (target, kind);
CREATE INDEX edges_flow        ON edges (resolved_by) WHERE resolved_by = 'flow';

CREATE TABLE files (
  project      TEXT NOT NULL,
  path         TEXT NOT NULL,
  content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
  language     TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (status IN ('parsed', 'failed', 'grammar_unavailable')),
  error        TEXT,
  PRIMARY KEY (project, path),
  CHECK ((status = 'failed') = (error IS NOT NULL))
) WITHOUT ROWID;

CREATE INDEX files_status ON files (status);

CREATE TABLE unresolved_refs (
  id          TEXT PRIMARY KEY CHECK (length(id) = 16),
  from_node   TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  name        TEXT NOT NULL CHECK (name <> ''),
  kind        TEXT NOT NULL,
  site_path   TEXT NOT NULL,
  site_line   INTEGER NOT NULL,
  site_column INTEGER NOT NULL,
  flow_resolved INTEGER NOT NULL DEFAULT 0 CHECK (flow_resolved IN (0, 1))
) WITHOUT ROWID;

CREATE INDEX unresolved_refs_name ON unresolved_refs (name);
CREATE INDEX unresolved_refs_from ON unresolved_refs (from_node);

CREATE TABLE call_sites (
  id          INTEGER PRIMARY KEY,
  from_node   TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  site_path   TEXT NOT NULL,
  site_line   INTEGER NOT NULL,
  site_column INTEGER NOT NULL,
  callee      TEXT NOT NULL CHECK (callee <> ''),
  arguments   TEXT NOT NULL DEFAULT '[]',
  UNIQUE (from_node, site_path, site_line, site_column)
);

CREATE TABLE local_bindings (
  in_node       TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  name          TEXT NOT NULL CHECK (name <> ''),
  shape         TEXT NOT NULL CHECK (shape IN ('call', 'name', 'literal', 'other')),
  shape_value   TEXT,
  assigned_once INTEGER NOT NULL CHECK (assigned_once IN (0, 1)),
  PRIMARY KEY (in_node, name),
  CHECK ((shape = 'other') = (shape_value IS NULL))
) WITHOUT ROWID;

CREATE TABLE inferred_types (
  parameter  TEXT PRIMARY KEY REFERENCES nodes (id) ON DELETE CASCADE,
  class      TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  call_sites INTEGER NOT NULL CHECK (call_sites >= 1)
) WITHOUT ROWID;

CREATE TABLE reach (
  node      TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  root_kind TEXT NOT NULL CHECK (root_kind IN ('binary', 'module', 'test')),
  root      TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  PRIMARY KEY (node, root_kind, root)
) WITHOUT ROWID;

CREATE INDEX reach_root ON reach (root);

CREATE TABLE route_paths (
  id        INTEGER PRIMARY KEY,
  route     TEXT NOT NULL REFERENCES nodes (id) ON DELETE CASCADE,
  binary    TEXT REFERENCES nodes (id) ON DELETE CASCADE,
  method    TEXT NOT NULL CHECK (method IN
              ('get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace', 'websocket')),
  full_path TEXT NOT NULL CHECK (full_path <> ''),
  complete  INTEGER NOT NULL CHECK (complete IN (0, 1)),
  CHECK (complete = (instr(full_path, '{?}') = 0))
);

CREATE UNIQUE INDEX route_paths_identity ON route_paths (route, ifnull(binary, ''), full_path);
CREATE INDEX route_paths_path ON route_paths (full_path);

CREATE TABLE warnings (
  id      INTEGER PRIMARY KEY,
  code    TEXT NOT NULL CHECK (code IN
            ('network_name_unknown', 'link_without_shared_network', 'dependency_path_not_a_project',
             'framework_mismatch', 'framework_app_not_found', 'entry_command_mismatch',
             'flow_round_limit')),
  subject TEXT REFERENCES nodes (id) ON DELETE CASCADE,
  message TEXT NOT NULL CHECK (message <> '')
);

CREATE TABLE project_checkouts (
  project   TEXT PRIMARY KEY,
  branch    TEXT,
  commit_id TEXT CHECK (commit_id IS NULL OR length(commit_id) = 40),
  CHECK (branch IS NULL OR commit_id IS NOT NULL)
) WITHOUT ROWID;

CREATE VIRTUAL TABLE nodes_fts USING fts5 (
  name, qualified_name, doc, signature,
  content = 'nodes', content_rowid = 'rowid'
);

CREATE TRIGGER nodes_fts_insert AFTER INSERT ON nodes BEGIN
  INSERT INTO nodes_fts (rowid, name, qualified_name, doc, signature)
  VALUES (new.rowid, new.name, new.qualified_name, new.doc, new.signature);
END;

CREATE TRIGGER nodes_fts_delete AFTER DELETE ON nodes BEGIN
  INSERT INTO nodes_fts (nodes_fts, rowid, name, qualified_name, doc, signature)
  VALUES ('delete', old.rowid, old.name, old.qualified_name, old.doc, old.signature);
END;

CREATE TRIGGER nodes_fts_update AFTER UPDATE ON nodes BEGIN
  INSERT INTO nodes_fts (nodes_fts, rowid, name, qualified_name, doc, signature)
  VALUES ('delete', old.rowid, old.name, old.qualified_name, old.doc, old.signature);
  INSERT INTO nodes_fts (rowid, name, qualified_name, doc, signature)
  VALUES (new.rowid, new.name, new.qualified_name, new.doc, new.signature);
END;
```

## The tables

### `meta`

One row per key.

| Key | Value |
|---|---|
| `format_version` | The version of this schema, `1` |
| `workbench_version` | The version of `workbench` that last wrote the store |
| `indexed_at` | When the last index finished |

### `nodes`

One row per node, for both layers. Each column is the field of the same name in the [domain model](./domain-model.md#node).

- **The node data of a kind fills its own columns only.** The comments in the schema group the columns by data type. A column that the node's data does not have is empty, a flag is `0` and a list is `[]`.

| Columns | Filled in for |
|---|---|
| `language` | `project`, always. Code nodes have no language: it is the file's, in `files` |
| `framework`, `framework_source` | `binary`, always |
| `app` | `binary`, when `framework` is `fastapi` and the app is known |
| `doc`, `signature`, `visibility`, the flags, `decorators`, `type_parameters`, `return_type` | Callables and type declarations; `doc` also for `file`, `module` and `namespace` |
| `declared_type`, `default_value` | `field`, `variable`, `constant`, `parameter` |
| `param_source` | `parameter`, when something says where it comes from |
| `role` | `variable` (`app`, `router`), `function` and `method` (`middleware`, `exception_handler`, `lifecycle_hook`), `class` (`model`) |
| `router_prefix` | A node whose role is `router`, when the prefix is known |
| `route_method`, `route_path`, `route_status`, `route_tags` | `route`. `route_method` always |
- **The kind is not checked by the table.** There are 32 kinds and the list grows with each language. The domain types already refuse an unknown kind.
- **`nodes_qualified_name`** serves the `scope:qualified name` form of naming a node.
- **`nodes_file`** serves "every node in this file", which `node --file` and the replacing of a file both need.

### `edges`

One row per edge, for both layers.

The data of an edge kind has typed columns, and the table checks that each is filled in for its own kind and for no other.

| Column | Filled in for | Holds |
|---|---|---|
| `import_specifier` | `imports`, always | The import as written |
| `import_alias` | `imports`, when there is one | The local name it is bound to |
| `dependency_scope` | `depends_on`, always | `build` or `dev` |
| `protocol` | `connects_to`, always | `http`, `grpc` or `database` |
| `import_type_only` | `imports`, always | `1` when the import only serves type checking |
| `mount_prefix` | `mounts`, when there is one | The path prefix the mount adds, or `{?}` |

`resolved_by` holds the rule that resolved the edge, and is empty on an edge not made by resolution. The table refuses it on any provenance but `tree_sitter` and `scip`, refuses `flow` on any kind but `calls` and `instantiates`, and requires `framework` on exactly `mounts`, `handles` and `injects`. `edges_flow` serves deleting the flow edges at every index.

A kind that gains data later gets its own column in a new format version.

- **`edges_identity`** enforces rule E6: no two edges share source, target, kind and site.
- **`edges_source_kind` and `edges_target_kind`** serve every walk: the edges out of a set of nodes, and the edges into it, by kind.
- **Deleting a node deletes the edges that start at it.** An edge that ends at a deleted node is not deleted. The store refuses to commit while such an edge exists, which is what makes [replacing a file](#replacing-a-file) safe.

### `files`

One row per file record. `error` holds the parser's message, and is filled in only when `status` is `failed`.

### `unresolved_refs`

One row per unresolved reference. Deleting a node deletes the references that appear in it. `flow_resolved` is `1` for a reference that stage 2b resolved: it is kept so that 2b can try it again at the next index, and queries do not count it as unresolved. `unresolved_refs_name` serves resolution: when a new node appears, the references that wait for its name are found by name.

### `call_sites` and `local_bindings`

One row per call site, and one per local binding, read in stage 1. Deleting a node deletes the call sites and bindings it holds, so they are replaced with their file. Stage 2 reads them all at every index. `shape_value` holds the name for `call` and `name`, the literal's kind for `literal`, and nothing for `other`.

### `inferred_types`, `reach` and `route_paths`

The results of stage 2. They are deleted and written again at every index, together with every edge whose `resolved_by` is `flow`. `route_paths_path` serves `search` by full path; the search matches any part of the path. `reach_root` serves "everything this binary may run"; the primary key serves "which roots run this node".

### `warnings`

One row per warning of the last index. `subject` is empty for a warning about no node.

### `project_checkouts`

One row per project: the branch and commit it was on at the last index. `branch` is empty when the project was on no branch, and both are empty when the project is not a git repository. `status` shows it, and the `operational-support` mode compares it with a context's release branch.

### `nodes_fts`

A full-text index over `name`, `qualified_name`, `doc` and `signature`. It holds no copy of the text; it points at `nodes`, and three triggers keep it in step. It serves `search` and the first step of `explore`.

## Rules the schema enforces

The domain types are the first guard. The schema is the second, for the rules that are cheap to state in SQL.

| Rule | How |
|---|---|
| N1: names are not empty | `CHECK` on `name` and `qualified_name` |
| N3, in part: a `workspace` scope carries no name, the other two carry one | `CHECK` on `scope_type` and `scope_name` |
| N6: no two nodes share an id | Primary key |
| Origin is all or nothing | `CHECK` across `path` and the span columns |
| Edge data suits the kind | `CHECK` on each data column |
| E4: a note only on a declared edge | `CHECK` on `note` and `provenance` |
| E5: both ends of an edge exist | Foreign keys |
| E6: edge identity | `edges_identity` |
| F1: one record per project and path | Primary key |
| A `failed` file has a message, and only a failed one | `CHECK` on `status` and `error` |
| R1: a reference's `from` exists | Foreign key |
| R3: no two references share an id | Primary key |
| P1: one checkout per project | Primary key |
| P3: a branch only with a commit | `CHECK` on `branch` and `commit_id` |
| A1: a warning's message is not empty | `CHECK` |
| A2: a warning's subject exists | Foreign key |
| N8, in part: a project has a language, a binary a framework, a route a method, and no other kind has them | `CHECK` on `language`, `framework` and `route_method` with `kind` |
| N10, in part: `app` only with `fastapi`; a router prefix only on a router | `CHECK` on `app` and `router_prefix` |
| E13: `resolved_by` only on parsed edges; `flow` only on `calls` and `instantiates`; `framework` on exactly the three framework kinds | `CHECK` on `resolved_by`, `provenance` and `kind` |
| `type_only` on every import, and only on imports | `CHECK` on `import_type_only` |
| U2: `complete` exactly when the path has no `{?}` | `CHECK` |
| U3: one route path per route, binary and full path | `route_paths_identity` |
| C1, L1 in part, Y1 in part, H1 in part: the nodes named exist | Foreign keys |
| C3: one call site per node and site | `UNIQUE` |
| L3: one binding per function and name | Primary key |
| Y2: one inferred type per parameter | Primary key |
| Y3: at least one call site agreed | `CHECK` |
| H2: one reach record per node and root | Primary key |

Every other rule of the domain model needs more than one row to decide, and is checked by `validate` before anything is written.

## How the store is written

### One index is one transaction

`workbench index` opens one write transaction at its start and commits at its end.

- **A reader never sees half an index.** Until the commit, queries and the MCP server see the graph as it was.
- **A failed index changes nothing.** An error rolls the transaction back.
- **Only one index runs at a time.** A second one cannot open its transaction, and stops with exit code `1` and a message that an index is already running.

### Replacing a file

When a file has changed, the indexer replaces it in four steps.

1. Delete the file's nodes. The edges that start at them, and the references, call sites and local bindings that appear in them, go with them. The edges that end at them stay.
2. Insert the nodes, edges, references, call sites and local bindings of the new parse. Ids are computed, so a node that did not move in name keeps its id, and the edges that end at it are valid again.
3. Find the edges that still end at a node that no longer exists. Each belongs to a file that referred to something now gone.
4. Delete those edges and read their files again in the same run, so that each lost edge becomes an unresolved reference.

A change to a file therefore costs one parse, plus one for each file that referred to something the change removed or renamed.

### Removing a file

A file that is gone from disk, or newly excluded, is replaced by nothing: steps 1, 3 and 4, and its record is deleted.

### Rebuilding the workspace layer

The workspace layer is rebuilt on every index, inside the same transaction.

1. Write every workspace node the run produces, by id. A node that is already there is updated in place, so the edges that touch it stay.
2. Delete every workspace node the run did not produce.
3. Delete every edge whose provenance is `manifest`, `compose` or `declared`, and insert the ones the run produces.
4. Delete all warnings, and insert the ones the run raised.
5. Write the checkout of every project the run indexed, replacing its row.

### Writing the results of stage 2

Stage 2 runs after every file is in and every reference has been tried, inside the same transaction.

1. Delete every edge whose `resolved_by` is `flow`, and every row of `inferred_types`, `reach` and `route_paths`. Set `flow_resolved` back to `0` on every reference.
2. Insert the `flow` edges, inferred types, reach records and route paths the run computed, and set `flow_resolved` to `1` on each reference a `flow` edge resolved.

Deleting first keeps the results free of leftovers from a call site that is gone. Stage 2 always works on the whole graph, so nothing is lost.

### `index --force`

Drops every table, creates the schema again, then indexes as if the store were new. This also works on a store of another format version.

## How the store is read

The rest of the program reaches the store through one port, so a second store can be added later without touching it. The port offers these operations and no others.

| Operation | Used by |
|---|---|
| One node by id | every query |
| Nodes by scope and qualified name | naming a node |
| Nodes by full-text search, with filters for kind and project | `search`, `explore` |
| Nodes of one file | `node --file` |
| Edges out of, or into, a set of nodes, with a filter for kinds | `callers`, `callees`, `impact`, `neighbors`, `explore`, `deps` |
| File records, with filters for project and status | `files`, `status`, `index` |
| Warnings | `status` |
| Project checkouts | `status`, and `context_status` in the `operational-support` mode |
| Counts of nodes, edges and files | `status` |
| The `meta` values | `status`, every MCP answer |
| Every call site and local binding | `index`, stage 2 |
| The inferred type of a parameter | `node` |
| The roots that reach a node, and the nodes a root reaches | `node`, `impact` |
| Files that no root reaches | `files --unreached` |
| The route paths of a route, and the routes whose full path holds a text | `node`, `search` |
| Write one index, as described above, with the results of stage 2 | `index` |

**The store never walks.** A walk is done step by step above the port: ask for the edges of a set of nodes, decide where to go next, ask again. Each step is one query on `edges_source_kind` or `edges_target_kind`. `impact` and `explore` therefore behave the same on any store.

## The format version

`format_version` is `1`. Any change to the schema raises it.

- **A store with the same version** is opened.
- **A store with any other version is refused,** with a message that says to run `workbench index --force`. That command drops every table and creates the schema again.
- **There are no migrations.** The store is derived data, so rebuilding it is always correct and never loses anything.
- **A file that has no `meta` table,** or is not a SQLite file, is refused the same way.

## Validating an implementation

1. **The schema.** Create it in an empty file. For each row of [Rules the schema enforces](#rules-the-schema-enforces), insert one row that breaks the rule and check that SQLite refuses it.
2. **Round trip.** Write the Acme Shop fixture of the [domain model](./domain-model.md#validating-an-implementation), read it back through the port, and check that every node with its data, edge, file record, call site, local binding, inferred type, reach record and warning is equal to what was written.
3. **Stage 2 is replaced.** Index the fixture, remove the test's call to `process`, and index again. The inferred type of `r` stays, and `test_services.py` no longer reaches `services.py`. Add a call that passes another class: the inferred type and its `flow` edge are gone.
4. **Replacing a file.** Rename a class in one file of a small two-file graph and index again. The edge from the other file is gone, an unresolved reference has taken its place, and the other file was read again.
5. **One index at a time.** Start an index, start a second one, and check that the second stops with exit code `1` and that a query still answers from the old graph.
6. **The format version.** Set `format_version` to `2` and check that the store is refused with the `index --force` message.

## Left to the implementation

- **The SQLite library.** Which Rust crate opens the file.
- **Batch sizes.** How many rows go into one statement.
- **Memgraph.** A second store behind the same port. It is on the roadmap and not designed.
