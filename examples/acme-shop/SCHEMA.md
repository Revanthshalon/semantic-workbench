# Acme Shop graph: shared contract

Every agent builds against this file. Root: this folder (`acme-graph/`).

- `src/` the complete example source: one folder per project (`shared-api`, `billing-api`, `ledger-api`, `web-app`). Do not edit it.
- `lib/ids.py` BLAKE3 and the id encoding. Import it; never reimplement ids. `node_id(scope_type, scope_name, path, kind, qualified_name, ordinal)`, `reference_id(...)`, `content_hash(bytes)`.
- `out/` where each agent writes its JSON. One file per agent, never another agent's.
- Spec, in the repository at `../../docs/`: `domain-model.md` (types, rules), `python-parsing.md` (what Python gives, stage 1 and stage 2), `example-workspace.md` (Acme Shop, its compose files, Dockerfiles, configuration), `graph-model.md`, `implementation-plan/step-1-domain-types.md` (Rust shapes, id bytes). Read-only.

## JSON conventions

- Every enum value is the snake-case storage name: kinds (`external_service`, `type_alias`), provenances (`tree_sitter`), resolutions (`self_member`), methods (`get`).
- Ids are 16 lowercase hex characters from `lib/ids.py`.
- Lines count from 1, columns from 0 (Python `ast` `lineno` and `col_offset` already do).
- Paths use `/`. A code node's path is relative to its project root (`src/billing/api.py`, `tests/test_api.py`). A compose node's path is relative to the workspace root (`docker-compose.yml`, `../billing-api/docker-compose.yml`).
- The workspace root is `src/workspace/` (holds `docker-compose.yml` and `.workbench/config.yml`); projects sit beside it as `../<project>`.

### Node

```json
{
  "id": "9f2c41d07ab35e18",
  "kind": "function",
  "name": "get_invoice",
  "qualified_name": "billing.routes.invoices.get_invoice",
  "scope": {"type": "project", "name": "billing-api"},      // workspace: {"type": "workspace", "name": null}
  "origin": {"type": "parsed", "path": "src/billing/routes/invoices.py",
             "span": {"start_line": 14, "start_column": 0, "end_line": 15, "end_column": 70}},
                                                              // or {"type": "declared"}
  "ordinal": 0,                                               // the 5th id input
  "data": { ... },                                            // the kind's data, or null for a kind with none
  "layer": "code"                                             // "code" or "workspace"
}
```

`data` by kind, field names as in `domain-model.md`:

- `file`: `{"doc": null}`
- `class` and other type kinds: `{"doc","signature","visibility","is_abstract","is_exported","decorators","type_parameters","role"}`
- `function`, `method`, `property`: `{"doc","signature","visibility","is_async","is_static","is_abstract","is_exported","decorators","type_parameters","return_type","role"}`
- `field`, `variable`, `constant`: `{"visibility","is_static","is_exported","declared_type","default","role"}`
- `parameter`: `{"member": {same as field}, "source": null | "path" | ...}`
- `route`: `{"method": "get", "path": <Template>, "status_code": 201 | null, "tags": []}`
- `command`: `{"program": "ledger-consumer", "path": ["run"], "help": null, "options": []}`
- `project`: `{"language": "python"}`
- `binary`: `{"framework": {"type": "fastapi", "app": "billing.api.app"} | {"type": "plain"} | {"type": "angular"}, "framework_source": "dockerfile"}`
- `import`, `enum_member`, and the workspace kinds other than `project` and `binary`: `null`
- `role`: `null`, `{"type": "app"}`, `{"type": "router", "prefix": <Template> | null, "tags": []}`, `{"type": "fixture"}`, `{"type": "model"}`, ...
- `visibility`: `"public"` or `"private"`. `signature`: the `def`/`class` line up to the colon, joined to one line.

`Template`: `{"parts": [{"text": "/v1/invoices/"}, {"hole": "invoice_id"}, {"unknown": true}]}`. Adjacent text merged, empty text dropped.

### Edge

```json
{
  "source": "…", "target": "…",
  "kind": "imports",
  "data": {"specifier": "shared_api.models.Invoice", "alias": null, "type_only": false},   // null for a kind with none
  "site": {"path": "src/billing/worker.py", "line": 9, "column": 0},                       // null when it has no place
  "provenance": "tree_sitter",            // declared edges: "declared", and "note": "…" or null
  "note": null,
  "resolved_by": "cross_project",         // null when not made by resolution
  "stage": "1"                            // who made it: "workspace", "1", "2a", "2b", "2d", "2f"
}
```

Edge data: `imports {specifier, alias, type_only}`, `depends_on {scope}`, `connects_to {protocol}`, `mounts {prefix: Template|null, tags}`, `requests {method, path}`, `sends {name}`, `invokes {words}`. Every other kind: `null`.

### Records

```json
"files":      [{"project","path","content_hash","size","mtime","language","status": {"type": "parsed"} | {"type": "grammar_unavailable"} | {"type": "failed","message"}}],
"references": [{"id","from","name","kind","data","site","flow_resolved": false}],
"call_sites": [{"from","site","callee","arguments": [{"slot": {"position": 0} | {"keyword": "func"}, "shape": <Shape>}]}],
"bindings":   [{"within","name","site","shape"}],
"returns":    [{"within","site","shape"}],
"inferred_types": [{"node","class","evidence"}],
"reach":      [{"node","root": {"type": "binary"|"module"|"test", "node": "<id>"}}],
"route_paths":[{"route","binary","method","full_path","complete","uses_defaults","providers","tags"}],
"unmatched_http_calls": [{"from","site","method","path","candidates"}],
"unmatched_messages":   [{"from","site","direction","name","broker","candidates"}],
"payloads":   [{"topic","node","direction","class"}],
"warnings":   [{"code","subject","message"}],
"checkouts":  [{"project","head": {"commit","branch"} | null}]
```

`Shape`: `{"type":"call","name"}`, `{"type":"name","name"}`, `{"type":"text","value"}`, `{"type":"template","parts":[...]}`, `{"type":"item","name","accessor"}`, `{"type":"collection","kind","elements":[...]}`, `{"type":"spread","name"}`, `{"type":"literal","kind": "number"|"bytes"|"bool"|"null"}`, `{"type":"other"}`.

`mtime`: in nanoseconds since 1970 UTC. Use `1795478400000000000` (2026-11-24 00:00 UTC) for every file, so the output is stable.

## How the spec is read here

Where the spec leaves a choice, every agent uses these. Each agent reports any further choice it had to make.

1. **Module names.** Path minus a leading `src/`, minus `.py`, `/` to `.`, a trailing `__init__` dropped: `src/billing/routes/invoices.py` is `billing.routes.invoices`, `tests/test_api.py` is `tests.test_api`, `src/billing/__init__.py` is `billing`.
2. **Import names for cross-project resolution.** `shared-api` is imported as `shared_api`, `billing-api` as `billing`, `ledger-api` as `ledger`. Anything else (`fastapi`, `sqlalchemy`, `pydantic`, `pydantic_settings`, `kafka`, `httpx`, `pytest`, `datetime`, `time`, `argparse`) is outside the workspace and stays unresolved.
3. **File nodes.** Every `.py` file is a `File` node, `Parsed`, scope `project`, span from `(1, 0)` to `(n, len(last line))`, where the lines are `text.split("\n")` with a final empty string dropped. An empty file is `(1, 0)` to `(1, 0)`. Its parent is the `Project` node, by a `Contains` edge with provenance `tree_sitter` and no site. The five entry files are also emitted by the workspace layer with identical fields; the merge keeps one.
4. **`web-app/projects/admin/src/main.ts`** is a `File` node with the same span rule, a file record with status `grammar_unavailable` and language `typescript`, and no nodes below it. The workspace agent emits it.
5. **`Contains` from a parent code node** to a child has provenance `tree_sitter`, no site, `resolved_by: null`, stage `1`.
6. **Framework of a plain binary.** `{"type":"plain"}` with `framework_source: "entry"`: the entry file was the last source checked.
7. **Checkouts.** Each project is on branch `main`. The commit is `blake3(<project id>)` as the first 40 hex characters. These are illustrative, and `meta` says so.
8. **Compose-parsed nodes.** A stack read from a compose file is `Parsed`, with that file's path and the whole file as span. A service or external service is `Parsed` with the span of its line(s). `acme-backbone` is `Parsed` with the span of its `networks:` entry in `docker-compose.yml`. `billing-api_default` exists in no file, so it is `Declared`.
