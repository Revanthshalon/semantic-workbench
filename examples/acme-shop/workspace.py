"""Workspace layer of the Acme Shop graph: 27 nodes, 54 edges.

Run: python3 -I workspace.py   ->   out/workspace.json
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT + "/lib")
from ids import node_id, content_hash  # noqa: E402

SRC = os.path.join(ROOT, "src")
WS_DIR = os.path.join(SRC, "workspace")
MTIME_NS = 1795478400000000000


# ---------- file helpers ----------

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def lines_of(text):
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def whole_span(text):
    lines = lines_of(text)
    if not lines:
        return {"start_line": 1, "start_column": 0, "end_line": 1, "end_column": 0}
    return {"start_line": 1, "start_column": 0, "end_line": len(lines), "end_column": len(lines[-1])}


def ws_file(rel):
    """A compose file, by its path relative to the workspace root."""
    return read_bytes(os.path.normpath(os.path.join(WS_DIR, rel))).decode()


def entry_span(rel, section, key):  # craftsman-ignore: NEST001 (a small line scanner)
    """Span of the line(s) of `key:` under the top-level `section:` of a compose file.
    Starts at the key's column, ends at the end of its last line."""
    lines = lines_of(ws_file(rel))
    in_section = False
    for i, line in enumerate(lines):
        if line and not line[0].isspace():
            in_section = line.rstrip() == section + ":"
            continue
        stripped = line.lstrip()
        if in_section and stripped.startswith(key + ":"):
            indent = len(line) - len(stripped)
            end = i
            while end + 1 < len(lines) and lines[end + 1].strip() and \
                    len(lines[end + 1]) - len(lines[end + 1].lstrip()) > indent:
                end += 1
            return {"start_line": i + 1, "start_column": indent,
                    "end_line": end + 1, "end_column": len(lines[end])}
    raise SystemExit(f"FAIL: {section}.{key} not found in {rel}")


# ---------- graph building ----------

nodes, edges = [], []
by_key = {}


def scope_of(stype, sname):
    return {"type": stype, "name": sname if stype != "workspace" else None}


def add_node(kind, name, qname, stype, sname, origin, data):  # craftsman-ignore: WARN-PY001 (mirrors the node fields)
    path = origin.get("path", "") if origin["type"] == "parsed" else ""
    nid = node_id(stype, sname or "", path, kind, qname, 0)
    nodes.append({
        "id": nid, "kind": kind, "name": name, "qualified_name": qname,
        "scope": scope_of(stype, sname), "origin": origin, "ordinal": 0,
        "data": data, "layer": "workspace",
    })
    return nid


def add_edge(source, target, kind, provenance, data=None):
    edges.append({
        "source": source, "target": target, "kind": kind, "data": data, "site": None,
        "provenance": provenance, "note": None, "resolved_by": None, "stage": "workspace",
    })


DECLARED = {"type": "declared"}


def parsed(path, span):
    return {"type": "parsed", "path": path, "span": span}


def contains(parent, child, child_provenance):
    add_edge(parent, child, "contains", child_provenance)


# Workspace
W = add_node("workspace", os.path.basename(WS_DIR), "workspace", "workspace", None, DECLARED, None)

# Projects (configuration)
PROJECTS = [("shared-api", "python"), ("billing-api", "python"),
            ("ledger-api", "python"), ("web-app", "typescript")]
P = {}
for pid, lang in PROJECTS:
    P[pid] = add_node("project", pid, pid, "workspace", None, DECLARED, {"language": lang})
    contains(W, P[pid], "declared")

# Binaries and their entry files
FASTAPI_DF = lambda app: {"framework": {"type": "fastapi", "app": app}, "framework_source": "dockerfile"}
PLAIN = {"framework": {"type": "plain"}, "framework_source": "entry"}
BINARIES = [
    ("billing-api", "api", "src/billing/api.py", FASTAPI_DF("billing.api.app")),
    ("billing-api", "worker", "src/billing/worker.py", PLAIN),
    ("ledger-api", "api", "src/ledger/api.py", FASTAPI_DF("ledger.api.app")),
    ("ledger-api", "consumer", "src/ledger/consumer.py", PLAIN),
    ("web-app", "admin", "projects/admin/src/main.ts",
     {"framework": {"type": "angular"}, "framework_source": "declared"}),
]
B, F, files = {}, {}, []
for pid, bname, entry, data in BINARIES:
    B[(pid, bname)] = add_node("binary", bname, bname, "project", pid, DECLARED, data)
    contains(P[pid], B[(pid, bname)], "declared")
for pid, bname, entry, data in BINARIES:
    raw = read_bytes(os.path.join(SRC, pid, entry))
    F[(pid, entry)] = add_node("file", entry.rsplit("/", 1)[-1], entry, "project", pid,
                               parsed(entry, whole_span(raw.decode())), {"doc": None})
    contains(P[pid], F[(pid, entry)], "tree_sitter")
    if entry.endswith(".ts"):
        files.append({"project": pid, "path": entry, "content_hash": content_hash(raw),
                      "size": len(raw), "mtime_ns": MTIME_NS, "language": "typescript",
                      "status": {"type": "grammar_unavailable"}})

# Stacks
INFRA_F = "docker-compose.yml"
BILLING_F = "../billing-api/docker-compose.yml"
LEDGER_F = "../ledger-api/docker-compose.yml"
S = {
    "acme-infra": add_node("stack", "acme-infra", "acme-infra", "workspace", None,
                           parsed(INFRA_F, whole_span(ws_file(INFRA_F))), None),
    "billing-api": add_node("stack", "billing-api", "billing-api", "workspace", None,
                            parsed(BILLING_F, whole_span(ws_file(BILLING_F))), None),
    "ledger": add_node("stack", "ledger", "ledger", "workspace", None, DECLARED, None),
}
contains(W, S["acme-infra"], "compose")
contains(W, S["billing-api"], "compose")
contains(W, S["ledger"], "declared")

# Networks
N_BACKBONE = add_node("network", "acme-backbone", "acme-backbone", "workspace", None,
                      parsed(INFRA_F, entry_span(INFRA_F, "networks", "backbone")), None)
N_BDEFAULT = add_node("network", "billing-api_default", "billing-api_default", "workspace", None,
                      DECLARED, None)
contains(W, N_BACKBONE, "compose")
contains(W, N_BDEFAULT, "declared")

# External services and services
X = {}
for name in ("kafka", "postgres"):
    X[name] = add_node("external_service", name, name, "stack", "acme-infra",
                       parsed(INFRA_F, entry_span(INFRA_F, "services", name)), None)
    contains(S["acme-infra"], X[name], "compose")
V = {}
for stack, rel, names in (("billing-api", BILLING_F, ("api", "worker")),
                          ("ledger", LEDGER_F, ("api", "consumer"))):
    for name in names:
        V[(stack, name)] = add_node("service", name, name, "stack", stack,
                                    parsed(rel, entry_span(rel, "services", name)), None)
        contains(S[stack], V[(stack, name)], "compose")

# Topic (declared by the links)
T = add_node("topic", "invoice.created", "kafka/invoice.created", "stack", "acme-infra", DECLARED, None)
contains(X["kafka"], T, "declared")

# ---------- cross-links ----------

# DependsOn, from each pyproject.toml
add_edge(P["billing-api"], P["shared-api"], "depends_on", "manifest", {"scope": "build"})
add_edge(P["ledger-api"], P["shared-api"], "depends_on", "manifest", {"scope": "build"})

# Uses: own compose stack, and the shared stack listed in the configuration
add_edge(P["billing-api"], S["billing-api"], "uses", "compose")
add_edge(P["billing-api"], S["acme-infra"], "uses", "declared")
add_edge(P["ledger-api"], S["ledger"], "uses", "compose")
add_edge(P["ledger-api"], S["acme-infra"], "uses", "declared")

# EntryPoint
for pid, bname, entry, _ in BINARIES:
    add_edge(B[(pid, bname)], F[(pid, entry)], "entry_point", "declared")

# Runs
add_edge(V[("billing-api", "api")], B[("billing-api", "api")], "runs", "compose")
add_edge(V[("billing-api", "worker")], B[("billing-api", "worker")], "runs", "compose")
add_edge(V[("ledger", "api")], B[("ledger-api", "api")], "runs", "dockerfile")
add_edge(V[("ledger", "consumer")], B[("ledger-api", "consumer")], "runs", "compose")

# Joins
for x in ("kafka", "postgres"):
    add_edge(X[x], N_BACKBONE, "joins", "compose")
for svc in ("api", "worker"):
    add_edge(V[("billing-api", svc)], N_BDEFAULT, "joins", "compose")
    add_edge(V[("billing-api", svc)], N_BACKBONE, "joins", "compose")
for svc in ("api", "consumer"):
    add_edge(V[("ledger", svc)], N_BACKBONE, "joins", "compose")

# ConnectsTo, Publishes, Subscribes (links)
add_edge(B[("billing-api", "api")], X["postgres"], "connects_to", "declared", {"protocol": "database"})
add_edge(B[("billing-api", "worker")], X["postgres"], "connects_to", "declared", {"protocol": "database"})
add_edge(B[("web-app", "admin")], V[("billing-api", "api")], "connects_to", "declared", {"protocol": "http"})
add_edge(B[("billing-api", "worker")], T, "publishes", "declared")
add_edge(B[("ledger-api", "consumer")], T, "subscribes", "declared")

warnings = [{
    "code": "stack_named_after_folder",
    "subject": S["billing-api"],
    "message": "Stack billing-api takes its Compose name from the folder of "
               "../billing-api/docker-compose.yml, and web-app's link names it; "
               "add a name to that compose file or the configuration.",
}]

checkouts = [{"project": pid, "head": {"commit": content_hash(pid.encode())[:40], "branch": "main"}}
             for pid, _ in PROJECTS]

out = {"nodes": nodes, "edges": edges, "files": files, "warnings": warnings, "checkouts": checkouts}

# ---------- self-check ----------


def check(cond, msg):
    if not cond:
        raise SystemExit("FAIL: " + msg)


check(len(nodes) == 27, f"27 nodes, got {len(nodes)}")
check(len(edges) == 54, f"54 edges, got {len(edges)}")
want_nodes = {"workspace": 1, "project": 4, "binary": 5, "file": 5, "stack": 3, "service": 4,
              "external_service": 2, "network": 2, "topic": 1}
want_edges = {"contains": 26, "depends_on": 2, "uses": 4, "entry_point": 5, "runs": 4,
              "joins": 8, "connects_to": 3, "publishes": 1, "subscribes": 1}
check(dict(Counter(n["kind"] for n in nodes)) == want_nodes, "node kind counts")
check(dict(Counter(e["kind"] for e in edges)) == want_edges, "edge kind counts")
check(not any(e["kind"] == "built_from" for e in edges), "no built_from")
ids = [n["id"] for n in nodes]
check(len(set(ids)) == len(ids), "unique node ids")
idset = set(ids)
check(all(e["source"] in idset and e["target"] in idset for e in edges), "edge ends exist")
parents = Counter(e["target"] for e in edges if e["kind"] == "contains")
check(parents[W] == 0, "workspace has no parent")
check(all(parents[i] == 1 for i in ids if i != W), "every non-root node has exactly one parent")
check(V[("billing-api", "api")] != V[("ledger", "api")], "two api services differ")
check(len({(e["source"], e["target"], e["kind"]) for e in edges}) == len(edges), "unique edges")

text = json.dumps(out, indent=2, sort_keys=False) + "\n"

if __name__ == "__main__" and os.environ.get("WS_CHILD") != "1":
    import subprocess
    env = dict(os.environ, WS_CHILD="1")
    again = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--stdout"],
                           capture_output=True, text=True, env=env)
    check(again.returncode == 0, "second run failed: " + again.stderr)
    check(again.stdout == text, "second run gives different output")
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out", "workspace.json"), "w") as f:
        f.write(text)
    print(f"ok: {len(nodes)} nodes, {len(edges)} edges; workspace {W}")
elif "--stdout" in sys.argv:
    sys.stdout.write(text)
