"""Merge out/workspace.json, out/stage1.json and out/stage2.json into site/graph.json and site/sources.json,
then check the Graph rules that need only the merged graph. Exits non-zero on any violation."""
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent
OUT, SITE, SRC = ROOT / "out", ROOT / "site", ROOT / "src"
RECORDS = ["files", "references", "call_sites", "bindings", "returns", "inferred_types", "reach", "route_paths",
           "unmatched_http_calls", "unmatched_messages", "payloads", "warnings", "checkouts"]


def load(name):
    p = OUT / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


parts = [load("workspace"), load("stage1"), load("stage2")]
problems = []

WORKSPACE_KINDS = {"workspace", "project", "binary", "stack", "service", "external_service", "network", "topic", "queue"}
nodes, edges = {}, {}
for part in parts:
    for n in part.get("nodes", []):
        n["layer"] = "workspace" if n["kind"] in WORKSPACE_KINDS else "code"
        old = nodes.get(n["id"])
        if old and old != n:
            problems.append(f"N6 node {n['id']} emitted twice with different fields: {old['qualified_name']} / {n['qualified_name']}")
        nodes[n["id"]] = n
    for e in part.get("edges", []):
        site = e.get("site") or {}
        key = (e["source"], e["target"], e["kind"], site.get("path"), site.get("line"), site.get("column"))
        if key in edges:
            old = {k: v for k, v in edges[key].items() if k != "stage"}
            if old != {k: v for k, v in e.items() if k != "stage"}:
                problems.append(f"E6 edge {key} emitted twice with different fields")
            continue
        edges[key] = e

# stage 2 removes the references it resolved; it lists their ids in "resolved_reference_ids"
resolved = set()
flow_kept = set()
for part in parts:
    resolved |= set(part.get("resolved_reference_ids", []))
    flow_kept |= set(part.get("flow_resolved_reference_ids", []))

graph = {"meta": {}, "nodes": list(nodes.values()), "edges": list(edges.values())}
for rec in RECORDS:
    rows, seen = [], set()
    for part in parts:
        for r in part.get(rec, []):
            k = json.dumps(r, sort_keys=True)
            if k not in seen:
                seen.add(k)
                rows.append(r)
    graph[rec] = rows
refs = []
for r in graph["references"]:
    if r["id"] in flow_kept:
        r = {**r, "flow_resolved": True}
    elif r["id"] in resolved:
        continue
    refs.append(r)
graph["references"] = refs

# --- Graph rules over the merged graph ---
ids = set(nodes)
ws = [n for n in nodes.values() if n["kind"] == "workspace"]
if len(ws) != 1:
    problems.append(f"N7 {len(ws)} workspace nodes")
parents = defaultdict(list)
for e in edges.values():
    for end in ("source", "target"):
        if e[end] not in ids:
            problems.append(f"E5 {e['kind']} edge {end} {e[end]} is not a node")
    if e["kind"] == "contains":
        parents[e["target"]].append(e["source"])
for n in nodes.values():
    p = parents.get(n["id"], [])
    if n["kind"] == "workspace":
        if p:
            problems.append("T1 workspace has a parent")
    elif len(p) != 1:
        problems.append(f"T2 {n['kind']} {n['qualified_name']} has {len(p)} parents")
root = ws[0]["id"] if ws else None
for n in nodes.values():
    seen, cur = set(), n["id"]
    while cur != root and cur in parents and cur not in seen:
        seen.add(cur)
        cur = parents[cur][0]
    if cur != root:
        problems.append(f"T3 {n['kind']} {n['qualified_name']} does not reach the workspace")
file_nodes = {(n["scope"]["name"], n["origin"]["path"]) for n in nodes.values() if n["kind"] == "file"}
file_recs = Counter((f["project"], f["path"]) for f in graph["files"])
for k, c in file_recs.items():
    if c > 1:
        problems.append(f"F1 {k} has {c} records")
if set(file_recs) != file_nodes:
    problems.append(f"F2 files without records {sorted(file_nodes - set(file_recs))}; records without files {sorted(set(file_recs) - file_nodes)}")
for r in graph["references"]:
    if r["from"] not in ids:
        problems.append(f"R1 reference {r['name']} from unknown node")
for rec, fields in [("call_sites", ["from"]), ("bindings", ["within"]), ("returns", ["within"]),
                    ("inferred_types", ["node", "class"]), ("reach", ["node"]), ("payloads", ["topic", "node", "class"])]:
    for r in graph[rec]:
        for f in fields:
            if r[f] not in ids:
                problems.append(f"{rec}.{f} {r[f]} is not a node")

# --- sources ---
sources = {}
for p in sorted(SRC.rglob("*")):
    if p.is_file():
        sources[str(p.relative_to(SRC))] = p.read_text()

graph["meta"] = {
    "workspace": "Acme Shop",
    "spec": "docs/domain-model.md, docs/python-parsing.md, docs/example-workspace.md",
    "ids": "BLAKE3, 8 bytes, length-prefixed inputs as in step-1-domain-types.md",
    "illustrative": "Checkout commits are made up: the first 40 hex characters of blake3(project id). mtime is fixed.",
    "counts": {
        "nodes": len(nodes), "edges": len(edges),
        "nodes_by_kind": dict(Counter(n["kind"] for n in nodes.values())),
        "edges_by_kind": dict(Counter(e["kind"] for e in edges.values())),
        "records": {rec: len(graph[rec]) for rec in RECORDS},
    },
    "violations": problems,
}
SITE.mkdir(exist_ok=True)
(SITE / "graph.json").write_text(json.dumps(graph, indent=1, sort_keys=False))
(SITE / "sources.json").write_text(json.dumps(sources, indent=1))
print(json.dumps(graph["meta"]["counts"], indent=1))
print(f"{len(problems)} violations")
for p in problems[:60]:
    print(" ", p)
sys.exit(1 if problems else 0)
