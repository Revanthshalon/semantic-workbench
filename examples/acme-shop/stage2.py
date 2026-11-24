"""Stage 2 of the Acme Shop graph: 2a resolve, 2b flow, 2c route paths,
2d HTTP matches, 2e reach, 2f messages and commands.

Reads out/workspace.json and out/stage1.json, writes out/stage2.json.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
SRC = os.path.join(ROOT, "src")

ws = json.load(open(os.path.join(OUT, "workspace.json")))
s1 = json.load(open(os.path.join(OUT, "stage1.json")))

NODES = {}
for n in ws["nodes"] + s1["nodes"]:
    NODES.setdefault(n["id"], n)
IN_EDGES = ws["edges"] + s1["edges"]

IMPORT_NAMES = {"shared_api": "shared-api", "billing": "billing-api", "ledger": "ledger-api"}
CLASS_KINDS = {"class", "protocol", "enum", "struct", "interface", "type_alias"}
CALLABLE_KINDS = {"function", "method"}


def kind(i):
    return NODES[i]["kind"]


def qn(i):
    return NODES[i]["qualified_name"]


def project_of(i):
    sc = NODES[i]["scope"]
    return sc["name"] if sc["type"] == "project" else None


def path_of(i):
    o = NODES[i]["origin"]
    return o.get("path")


def module_name(path):
    p = path[4:] if path.startswith("src/") else path
    if p.endswith(".py"):
        p = p[:-3]
    p = p.replace("/", ".")
    if p.endswith(".__init__"):
        p = p[: -len(".__init__")]
    elif p == "__init__":
        p = ""
    return p


def role(i):
    d = NODES[i]["data"]
    if not isinstance(d, dict):
        return None
    if "role" in d:
        return d["role"]
    if "member" in d:
        return d["member"].get("role")
    return None


# ---------------------------------------------------------------- indexes
FILES = {}          # (project, path) -> file id
FILE_MODULE = {}    # file id -> module name
MODULE_FILE = {}    # module name -> file id (python files)
QN_INDEX = {}       # qualified name -> node id (code nodes, not imports)
for i, n in NODES.items():
    if n["layer"] != "code" and n["kind"] != "file":
        continue
    if n["kind"] == "file":
        FILES[(project_of(i), path_of(i))] = i
        if path_of(i).endswith(".py"):
            m = module_name(path_of(i))
            FILE_MODULE[i] = m
            MODULE_FILE[m] = i
        continue
    if n["kind"] == "import":
        continue
    QN_INDEX.setdefault(n["qualified_name"], i)

CHILDREN = defaultdict(list)
PARENT = {}
for e in IN_EDGES:
    if e["kind"] == "contains":
        CHILDREN[e["source"]].append(e["target"])
        PARENT[e["target"]] = e["source"]


def file_of(i):
    """The File node a code node lives in."""
    if kind(i) == "file":
        return i
    return FILES.get((project_of(i), path_of(i)))


def enclosing_callable(i):
    k = kind(i)
    if k in CALLABLE_KINDS:
        return i
    if k == "parameter":
        return PARENT.get(i)
    return None


def enclosing_class(i):
    cur = i
    while cur is not None:
        if kind(cur) in CLASS_KINDS:
            return cur
        cur = PARENT.get(cur)
    return None


# import map per file: local name -> dotted target
IMPORTS = defaultdict(dict)
for r in s1["references"]:
    if r["kind"] == "imports":
        spec = r["data"]["specifier"]
        local = r["data"]["alias"] or spec.split(".")[-1]
        IMPORTS[r["from"]][local] = spec

BINDINGS = defaultdict(list)   # (within, name) -> [binding]
for b in s1["bindings"]:
    BINDINGS[(b["within"], b["name"])].append(b)
RETURNS = defaultdict(list)
for b in s1["returns"]:
    RETURNS[b["within"]].append(b)
CALL_SITES = {}
for c in s1["call_sites"]:
    CALL_SITES[(c["from"], c["site"]["path"], c["site"]["line"], c["site"]["column"])] = c


def params_of(fn):
    return {qn(c).rsplit(".", 1)[1]: c for c in CHILDREN[fn] if kind(c) == "parameter"}


# ---------------------------------------------------------------- 2a resolve
EDGES = []
EDGE_KEYS = set()
RESOLVED_IDS = []
FLOW_IDS = []
TYPE_OF = defaultdict(list)    # node -> [class] from resolved type_of edges
RETURNS_OF = defaultdict(list)  # callable -> [class] from resolved returns edges
EXTENDS = defaultdict(list)    # class -> [base class]
INFERRED = {}                  # node -> class (2b)


def site_key(site):
    return None if site is None else (site["path"], site["line"], site["column"])


def add_edge(source, target, k, data, site, provenance, resolved_by, stage, note=None):
    key = (source, target, k, site_key(site))
    assert key not in EDGE_KEYS, ("duplicate edge", key)
    assert source in NODES and target in NODES, (source, target)
    EDGE_KEYS.add(key)
    e = {"source": source, "target": target, "kind": k, "data": data, "site": site,
         "provenance": provenance, "note": note, "resolved_by": resolved_by, "stage": stage}
    EDGES.append(e)
    return e


def class_of_binding_shape(shape, ctx):
    """Class of a value bound once: Call(C) of a workspace class, or Call(f) with a Returns edge."""
    if shape["type"] != "call":
        return None
    t = resolve_name(shape["name"], ctx)
    if not t:
        return None
    tgt = t[0]
    if kind(tgt) in CLASS_KINDS:
        return tgt
    if kind(tgt) in CALLABLE_KINDS:
        rets = RETURNS_OF.get(tgt, [])
        if len(rets) == 1:
            return rets[0]
    return None


def type_of_value_node(i, flow=False):
    """(class, rule) of a parameter / variable / field / constant node."""
    tys = TYPE_OF.get(i, [])
    if len(tys) == 1:
        return tys[0], "annotation"
    k = kind(i)
    if k in ("variable", "constant", "field"):
        within = PARENT.get(i)
        name = qn(i).rsplit(".", 1)[1]
        bs = BINDINGS.get((within, name), [])
        if len(bs) == 1:
            c = class_of_binding_shape(bs[0]["shape"], within)
            if c:
                return c, "local_inference"
    if flow and i in INFERRED:
        return INFERRED[i], "flow"
    return None, None


def member_of(node, m, flow=False):
    """(target, rule or None) for attribute m of node."""
    k = kind(node)
    if k == "file":
        t = QN_INDEX.get(FILE_MODULE[node] + "." + m) or MODULE_FILE.get(FILE_MODULE[node] + "." + m)
        return (t, None) if t else (None, None)
    if k in CLASS_KINDS:
        t = QN_INDEX.get(qn(node) + "." + m)
        if t:
            return t, None
        seen, queue = set(), list(EXTENDS.get(node, []))
        while queue:  # breadth first stands in for the MRO here (single bases)
            b = queue.pop(0)
            if b in seen:
                continue
            seen.add(b)
            t = QN_INDEX.get(qn(b) + "." + m)
            if t:
                return t, "inherited"
            queue.extend(EXTENDS.get(b, []))
        return None, None
    if k in ("variable", "constant", "field", "parameter"):
        c, rule = type_of_value_node(node, flow)
        if c:
            t, r2 = member_of(c, m, flow)
            if t:
                return t, (r2 or rule)
    return None, None


def resolve_qualified(q, flow=False):
    """Resolve a dotted qualified name in the workspace. Returns (target, rule-or-None)."""
    if q in QN_INDEX:
        return QN_INDEX[q], None
    if q in MODULE_FILE:
        return MODULE_FILE[q], None
    parts = q.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        head = ".".join(parts[:cut])
        base = QN_INDEX.get(head) or MODULE_FILE.get(head)
        if base:
            cur, rule = base, None
            for m in parts[cut:]:
                cur, r = member_of(cur, m, flow)
                if not cur:
                    return None, None
                rule = r or rule
            return cur, rule
    return None, None


def walk_members(base, rest, flow=False):
    cur, rule = base, None
    for m in rest:
        cur, r = member_of(cur, m, flow)
        if not cur:
            return None, None
        rule = r or rule
    return cur, rule


def resolve_name(name, ctx, flow=False):
    """Resolve a name as written, seen from node ctx. Returns (target, rule) or None.

    Locals first (Python scoping), then: import, self_member, same_file, project, cross_project.
    """
    if name in QN_INDEX and ("@" in name or " " in name):  # a route or command qualified name
        t = QN_INDEX[name]
        return t, ("project" if project_of(t) == project_of(ctx) else "cross_project")
    parts = name.split(".")
    head, rest = parts[0], parts[1:]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", head) or any(
            not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p) for p in rest):
        return None  # a call on a call result, e.g. db.query(...).filter
    fn = enclosing_callable(ctx)
    if fn is not None:
        ps = params_of(fn)
        if head in ps:
            if not rest:
                return None
            p = ps[head]
            c, rule = type_of_value_node(p, flow)
            if c:
                t, r2 = walk_members(c, rest, flow)
                if t:
                    return t, (r2 if r2 == "inherited" else rule)
            return None
        bs = BINDINGS.get((fn, head), [])
        if bs:
            if len(bs) == 1 and rest:
                c = class_of_binding_shape(bs[0]["shape"], fn)
                if c:
                    t, r2 = walk_members(c, rest, flow)
                    if t:
                        return t, (r2 if r2 == "inherited" else "local_inference")
            return None
    f = file_of(ctx)
    imports = IMPORTS.get(f, {})
    if head in imports:
        t, rule = resolve_qualified(".".join([imports[head]] + rest), flow)
        if t:
            return t, (rule or "import")
        return None  # imported from outside the workspace, or no such member
    if head == "self":
        cls = enclosing_class(ctx)
        if cls and rest:
            t, rule = walk_members(cls, rest, flow)
            if t:
                return t, (rule or "self_member")
        return None
    mod = FILE_MODULE.get(f)
    if mod is not None:
        base = QN_INDEX.get(mod + "." + head)
        if base:
            t, rule = walk_members(base, rest, flow)
            if t:
                return t, (rule or "same_file")
            return None
    t, rule = resolve_qualified(name, flow)
    if t:
        same = project_of(t) == project_of(ctx)
        if same:
            return t, (rule or "project")
        if head in IMPORT_NAMES and IMPORT_NAMES[head] == project_of(t):
            return t, (rule or "cross_project")
    return None


def fixture_lookup(name, ctx):
    """pytest: nearest fixture of that name: same file, then conftest.py up the folders."""
    f = file_of(ctx)
    proj, path = project_of(f), path_of(f)
    cands = [f]
    folder = os.path.dirname(path)
    while True:
        cf = FILES.get((proj, (folder + "/" if folder else "") + "conftest.py"))
        if cf and cf not in cands:
            cands.append(cf)
        if not folder:
            break
        folder = os.path.dirname(folder)
    for cf in cands:
        for c in CHILDREN[cf]:
            if kind(c) in CALLABLE_KINDS and NODES[c]["name"] == name and (role(c) or {}).get("type") == "fixture":
                return c
    return None


def is_test_file(f):
    p = path_of(f)
    base = os.path.basename(p)
    return (p.endswith(".py") and (base.startswith("test_") or base.endswith("_test.py")
            or base == "conftest.py" or "/tests/" in "/" + p))


def is_test_callable(i):
    if kind(i) == "function":
        return NODES[i]["name"].startswith("test_")
    if kind(i) == "method":
        p = PARENT.get(i)
        return NODES[i]["name"].startswith("test_") and p and NODES[p]["name"].startswith("Test")
    return False


REFS = s1["references"]
UNRESOLVED = {r["id"]: r for r in REFS}


def resolve_ref(r, flow=False):
    k, name, ctx = r["kind"], r["name"], r["from"]
    if k == "imports":
        t, _ = resolve_qualified(name)
        if not t:
            return None
        return t, ("project" if project_of(t) == project_of(ctx) else "cross_project"), k
    if k == "injects" and is_test_file(file_of(ctx)) and (
            is_test_callable(ctx) or (role(ctx) or {}).get("type") == "fixture"):
        t = fixture_lookup(name, ctx)
        return (t, "framework", k) if t else None
    res = resolve_name(name, ctx, flow)
    if not res:
        return None
    t, rule = res
    tk = kind(t)
    if k in ("mounts", "handles", "injects"):
        ok = {"mounts": tk == "route" or (tk == "variable" and (role(t) or {}).get("type") in ("app", "router")),
              "handles": tk in CALLABLE_KINDS,
              "injects": tk in CALLABLE_KINDS or tk in CLASS_KINDS}[k]
        return (t, "framework", k) if ok else None
    if k in ("type_of", "returns", "extends", "implements"):
        return (t, rule, k) if tk in CLASS_KINDS else None
    if k == "calls":
        if tk in CLASS_KINDS:
            return t, rule, "instantiates"
        if tk in CALLABLE_KINDS or tk in ("variable", "constant", "field"):
            return t, rule, "calls"
        return None
    if k == "decorates":
        return None if tk == "file" else (t, rule, k)
    if k == "references":
        return None if tk == "file" else (t, rule, k)
    return (t, rule, k)


def run_pass(kinds, flow=False):
    for r in REFS:
        if r["id"] not in UNRESOLVED or r["kind"] not in kinds:
            continue
        res = resolve_ref(r, flow)
        if not res:
            continue
        t, rule, ek = res
        src, tgt = r["from"], t
        if ek == "decorates":  # the decorator's node, to the decorated node
            src, tgt = t, r["from"]
        add_edge(src, tgt, ek, r["data"], r["site"], "tree_sitter", rule, "2a")
        del UNRESOLVED[r["id"]]
        RESOLVED_IDS.append(r["id"])
        if ek == "type_of":
            TYPE_OF[r["from"]].append(t)
        elif ek == "returns" and kind(r["from"]) in CALLABLE_KINDS:
            RETURNS_OF[r["from"]].append(t)
        elif ek == "extends":
            EXTENDS[r["from"]].append(t)


# Types first (annotations, returns, bases), then everything that may lean on them.
run_pass({"imports"})
run_pass({"extends", "implements"})
run_pass({"type_of", "returns"})
run_pass({"calls", "references", "decorates", "mounts", "handles", "injects", "overrides", "exports"})

# ---------------------------------------------------------------- 2b flow
def value_class(shape, ctx, flow=True):
    t = shape["type"]
    if t == "call":
        res = resolve_name(shape["name"], ctx, flow)
        if not res:
            return None
        tgt = res[0]
        if kind(tgt) in CLASS_KINDS:
            return tgt
        if kind(tgt) in CALLABLE_KINDS:
            rets = RETURNS_OF.get(tgt, [])
            if len(rets) == 1:
                return rets[0]
            return INFERRED.get(tgt)
        return None
    if t == "name":
        name = shape["name"]
        fn = enclosing_callable(ctx)
        if fn is not None and "." not in name:
            ps = params_of(fn)
            if name in ps:
                c, _ = type_of_value_node(ps[name], flow)
                return c
            bs = BINDINGS.get((fn, name), [])
            if bs:
                cs = {value_class(b["shape"], fn, flow) for b in bs}
                return cs.pop() if len(cs) == 1 and None not in cs else None
        res = resolve_name(name, ctx, flow)
        if res and kind(res[0]) in ("variable", "constant", "field", "parameter"):
            c, _ = type_of_value_node(res[0], flow)
            return c
        return None
    return None  # literals, templates, items, collections, spreads, other


def callee_edges():
    """call site -> resolved callee, from the calls/instantiates edges."""
    m = {}
    for e in EDGES:
        if e["kind"] in ("calls", "instantiates") and e["site"]:
            m[(e["source"],) + site_key(e["site"])] = e["target"]
    return m


used_as_value = set()
for e in EDGES:
    if e["kind"] in ("references", "injects", "handles", "decorates"):
        used_as_value.add(e["target"] if e["kind"] != "decorates" else e["target"])
# a decorated callable: decorates edge goes decorator -> decorated
decorated = {e["target"] for e in EDGES if e["kind"] == "decorates"}

INFERRED_EVIDENCE = {}
CONFLICTED = set()
rounds = 0
for rounds in range(1, 11):
    changed = False
    cmap = callee_edges()
    sites_by_callee = defaultdict(list)
    for key, tgt in cmap.items():
        cs = CALL_SITES.get(key)
        if cs:
            sites_by_callee[tgt].append(cs)
    # parameters without annotation
    for fn in [i for i in NODES if kind(i) in CALLABLE_KINDS]:
        ps = [c for c in CHILDREN[fn] if kind(c) == "parameter"]
        for pos, p in enumerate(ps):
            if TYPE_OF.get(p) or p in CONFLICTED:
                continue
            name = qn(p).rsplit(".", 1)[1]
            if fn in used_as_value or fn in decorated:
                continue
            sites = sites_by_callee.get(fn, [])
            if not sites:
                continue
            classes = []
            for cs in sites:
                arg = None
                for a in cs["arguments"]:
                    sl = a["slot"]
                    if sl.get("position") == pos or sl.get("keyword") == name:
                        arg = a
                if arg is None:
                    classes.append(None)
                else:
                    classes.append(value_class(arg["shape"], cs["from"]))
            uniq = set(classes)
            if len(uniq) == 1 and None not in uniq:
                c = uniq.pop()
                if INFERRED.get(p) != c:
                    INFERRED[p] = c
                    INFERRED_EVIDENCE[p] = len(classes)
                    changed = True
            elif p in INFERRED:
                del INFERRED[p]
                CONFLICTED.add(p)
                changed = True
    # returns of callables without a return annotation
    for fn in [i for i in NODES if kind(i) in CALLABLE_KINDS]:
        if RETURNS_OF.get(fn) or fn in CONFLICTED:
            continue
        d = NODES[fn]["data"]
        if d.get("return_type"):
            continue
        rets = RETURNS.get(fn, [])
        if not rets:
            continue
        classes = [value_class(b["shape"], fn) for b in rets]
        uniq = set(classes)
        if len(uniq) == 1 and None not in uniq:
            c = uniq.pop()
            if INFERRED.get(fn) != c:
                INFERRED[fn] = c
                INFERRED_EVIDENCE[fn] = len(classes)
                changed = True
    # names bound more than once, and fields: every binding agrees
    for (within, name), bs in BINDINGS.items():
        target = QN_INDEX.get(qn(within) + "." + name) if kind(within) != "file" else QN_INDEX.get(FILE_MODULE[within] + "." + name)
        if not target or kind(target) not in ("variable", "constant", "field") or TYPE_OF.get(target):
            continue
        if len(bs) < 2 and kind(target) != "field":
            continue
        if target in CONFLICTED:
            continue
        classes = [value_class(b["shape"], within) for b in bs]
        uniq = set(classes)
        if len(uniq) == 1 and None not in uniq:
            c = uniq.pop()
            if INFERRED.get(target) != c:
                INFERRED[target] = c
                INFERRED_EVIDENCE[target] = len(classes)
                changed = True
    # resolve again the references whose receiver now has a class
    for r in REFS:
        if r["id"] not in UNRESOLVED or r["kind"] != "calls" or r["id"] in FLOW_IDS:
            continue
        res = resolve_name(r["name"], r["from"], flow=True)
        if not res:
            continue
        t, rule = res
        if rule != "flow" or not (kind(t) in CALLABLE_KINDS or kind(t) in CLASS_KINDS):
            continue
        ek = "instantiates" if kind(t) in CLASS_KINDS else "calls"
        add_edge(r["from"], t, ek, r["data"], r["site"], "tree_sitter", "flow", "2b")
        FLOW_IDS.append(r["id"])
        changed = True
    if not changed:
        break

for fid in FLOW_IDS:
    UNRESOLVED.pop(fid, None)
FLOW_LIMIT_HIT = rounds == 10

# ---------------------------------------------------------------- 2c route paths
def tmpl_text(t):
    if t is None:
        return ""
    out = []
    for p in t["parts"]:
        if "text" in p:
            out.append(p["text"])
        elif "hole" in p:
            out.append("{" + p["hole"] + "}")
        else:
            out.append("{?}")
    return "".join(out)


EDGES_FROM = defaultdict(list)
EDGES_TO = defaultdict(list)


def reindex():
    EDGES_FROM.clear()
    EDGES_TO.clear()
    for e in IN_EDGES + EDGES:
        EDGES_FROM[e["source"]].append(e)
        EDGES_TO[e["target"]].append(e)


reindex()

BINARIES = [i for i in NODES if kind(i) == "binary"]
APP_BINARIES = defaultdict(list)
for b in BINARIES:
    fw = NODES[b]["data"]["framework"]
    if fw["type"] == "fastapi":
        a = QN_INDEX.get(fw["app"])
        if a:
            APP_BINARIES[a].append(b)


def injects_from(i, site=None):
    return [e["target"] for e in EDGES_FROM[i] if e["kind"] == "injects"
            and (site is None or site_key(e["site"]) == site)]


def mount_site_injects(i):
    """Injects of node i given at one of its mounts share that mount's site."""
    mount_sites = {site_key(e["site"]) for e in EDGES_FROM[i] if e["kind"] == "mounts"}
    return {e["target"] for e in EDGES_FROM[i] if e["kind"] == "injects" and site_key(e["site"]) in mount_sites}


ROUTE_PATHS = []
for route in [i for i in NODES if kind(i) == "route"]:
    rd = NODES[route]["data"]
    handler = [e["target"] for e in EDGES_FROM[route] if e["kind"] == "handles"]
    base_prov = injects_from(route) + [p for h in handler for p in injects_from(h)]
    # walk up: each chain is a list of (mount edge)
    chains = []

    def up(node, chain, seen):
        ups = [e for e in EDGES_TO[node] if e["kind"] == "mounts"]
        r_ = (role(node) or {}).get("type")
        if r_ == "app" or not ups:
            chains.append((node, list(chain)))
        for e in ups:
            if e["source"] in seen:
                continue
            up(e["source"], chain + [e], seen | {e["source"]})

    up(route, [], {route})
    for top, chain in chains:
        if (role(top) or {}).get("type") != "app":
            continue
        parts = [tmpl_text(rd["path"])]
        providers = list(base_prov)
        tags = list(rd.get("tags") or [])
        for e in chain:  # e: source mounts target
            src = e["source"]
            parts.append(tmpl_text((e["data"] or {}).get("prefix")))
            tags += (e["data"] or {}).get("tags") or []
            providers += injects_from(src, site_key(e["site"]))
            sr = role(src) or {}
            if sr.get("type") == "router":
                parts.append(tmpl_text(sr.get("prefix")))
                tags += sr.get("tags") or []
            mounted_here = mount_site_injects(src)
            providers += [p for p in injects_from(src) if p not in mounted_here]
        full = "".join(reversed(parts))
        uniq_prov = []
        for p in providers:
            if p not in uniq_prov:
                uniq_prov.append(p)
        uniq_tags = []
        for t in tags:
            if t not in uniq_tags:
                uniq_tags.append(t)
        for b in APP_BINARIES.get(top) or [None]:
            ROUTE_PATHS.append({"route": route, "binary": b, "method": rd["method"], "full_path": full,
                                "complete": "{?}" not in full, "uses_defaults": False,
                                "providers": uniq_prov, "tags": uniq_tags, "_app": top})

# ---------------------------------------------------------------- text of values (2b, text)
def name_text(name, ctx):
    """Text of Name(name) seen from ctx, or None when unknown."""
    fn = enclosing_callable(ctx)
    if fn is not None and "." not in name:
        if name in params_of(fn):
            return None
        bs = BINDINGS.get((fn, name), [])
        if bs:
            return shape_text(bs[0]["shape"], fn) if len(bs) == 1 else None
    res = resolve_name(name, ctx)
    if not res:
        return None
    t = res[0]
    if kind(t) in ("variable", "constant"):
        bs = BINDINGS.get((PARENT.get(t), qn(t).rsplit(".", 1)[1]), [])
        if len(bs) == 1:
            return shape_text(bs[0]["shape"], PARENT.get(t))
    return None


def shape_text(shape, ctx):
    """List of parts: str or None (unknown)."""
    t = shape["type"]
    if t == "text":
        return [shape["value"]]
    if t == "template":
        out = []
        for p in shape["parts"]:
            if "text" in p:
                out.append(p["text"])
            elif "hole" in p:
                sub = name_text(p["hole"], ctx)
                out.extend(sub if sub is not None else [None])
            else:
                out.append(None)
        return out
    if t == "name":
        return name_text(shape["name"], ctx)
    return None


def url_path(parts):
    if parts is None:
        return "{?}"
    s = "".join(p if p is not None else "\x00" for p in parts)
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/\x00]*", s)
    if m:
        s = s[m.end():]
    elif s.startswith("\x00"):
        s = s[1:]  # a leading unknown part is the scheme and host
    s = s.split("?", 1)[0]
    s = s.replace("\x00", "{?}")
    return s or "/"


def segs(p):
    p = p.split("?", 1)[0].rstrip("/")
    return p.split("/")


def path_match(call, route):
    a, b = segs(call), segs(route)
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y or x == "{?}" or re.fullmatch(r"\{[^}?]+\}", y):
            continue
        return False
    return True


# ---------------------------------------------------------------- 2e reach (before 2d? no: 2d first, reach follows requests)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
UNMATCHED_HTTP = []
WARNINGS = []


def binaries_of_caller(i):
    """Binaries whose project holds node i."""
    return [b for b in BINARIES if project_of(b) == project_of(i)]


def http_links(i):
    """Services targeted by http links of the calling node's project or its binaries."""
    proj = project_of(i)
    srcs = [b for b in BINARIES if project_of(b) == proj] + [p for p in NODES if kind(p) == "project" and NODES[p]["name"] == proj]
    out = set()
    for sid in srcs:
        for e in EDGES_FROM[sid]:
            if e["kind"] == "connects_to" and (e["data"] or {}).get("protocol") == "http":
                out.add(e["target"])
    return out, bool(out)


SERVICES_RUNNING = defaultdict(set)  # binary -> services
for e in IN_EDGES:
    if e["kind"] == "runs":
        SERVICES_RUNNING[e["target"]].add(e["source"])

for cs in s1["call_sites"]:
    callee, ctx = cs["callee"], cs["from"]
    method, url_arg, app_node = None, None, None
    m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_.]*)\.(\w+)", callee)
    m2 = re.fullmatch(r"TestClient\((\w+)\)\.(\w+)", callee)
    f = file_of(ctx)
    if m2 and IMPORTS.get(f, {}).get("TestClient") == "fastapi.testclient.TestClient":
        if m2.group(2) in HTTP_METHODS:
            res = resolve_name(m2.group(1), ctx)
            if res and (role(res[0]) or {}).get("type") == "app":
                method, app_node = m2.group(2), res[0]
    elif m and m.group(2) in HTTP_METHODS | {"request"}:
        recv = m.group(1)
        if IMPORTS.get(f, {}).get(recv) in ("httpx", "requests"):
            method = m.group(2)
    if method is None:
        continue
    args = cs["arguments"]
    if method == "request":
        a0 = next((a for a in args if a["slot"].get("position") == 0), None)
        if not a0 or a0["shape"]["type"] != "text":
            continue
        method = a0["shape"]["value"].lower()
        url = next((a for a in args if a["slot"].get("position") == 1 or a["slot"].get("keyword") == "url"), None)
    else:
        url = next((a for a in args if a["slot"].get("position") == 0 or a["slot"].get("keyword") == "url"), None)
    path = url_path(shape_text(url["shape"], ctx) if url else None)
    cands = ROUTE_PATHS
    if app_node:
        cands = [rp for rp in ROUTE_PATHS if rp["_app"] == app_node]
    else:
        linked, has = http_links(ctx)
        if has:
            cands = [rp for rp in ROUTE_PATHS if rp["binary"] and SERVICES_RUNNING[rp["binary"]] & linked]
    matched = [rp for rp in cands if rp["method"] == method and path_match(path, rp["full_path"])]
    routes = sorted({rp["route"] for rp in matched})
    if len(matched) == 1:
        rp = matched[0]
        add_edge(ctx, rp["route"], "requests", {"method": method, "path": path}, cs["site"],
                 "tree_sitter", "route_match", "2d")
        b = rp["binary"]
        if b and project_of(b) != project_of(ctx):
            linked, _ = http_links(ctx)
            if not (SERVICES_RUNNING[b] & linked):
                WARNINGS.append({"code": "http_call_without_link", "subject": ctx,
                                 "message": f"{qn(ctx)} calls {method.upper()} {rp['full_path']}, served by binary "
                                            f"{NODES[b]['name']} of {project_of(b)}, and {project_of(ctx)} declares no "
                                            f"http link to a service that runs it; add "
                                            + ", ".join("{service: %s, stack: %s, via: http, binary: %s}" % (
                                                NODES[sv]["name"], NODES[sv]["scope"]["name"], NODES[b]["name"])
                                                for sv in sorted(SERVICES_RUNNING[b]))
                                            + f" to the links of {project_of(ctx)}."})
    else:
        UNMATCHED_HTTP.append({"from": ctx, "site": cs["site"], "method": method, "path": path,
                               "candidates": routes})

reindex()

# ---------------------------------------------------------------- 2e reach
def service_command_lines():
    """service id -> (words list, provenance) from compose `command` or the Dockerfile CMD."""
    out = {}
    for sid in [i for i in NODES if kind(i) == "service"]:
        o = NODES[sid]["origin"]
        cpath = os.path.normpath(os.path.join(SRC, "workspace", o["path"]))
        lines = open(cpath).read().split("\n")
        line = lines[o["span"]["start_line"] - 1]
        mc = re.search(r"command:\s*([^,}\]]+?)\s*(,\s*\w+:|\}\s*$)", line)
        if mc:
            out[sid] = (mc.group(1).strip().strip('"\'').split(), "compose")
            continue
        df = os.path.join(os.path.dirname(cpath), "Dockerfile")
        if not os.path.exists(df):
            continue
        mt = re.search(r"target:\s*(\w+)", line)
        stage, cmds = None, {}
        for l in open(df).read().split("\n"):
            mf = re.match(r"FROM\s+\S+(?:\s+AS\s+(\w+))?", l, re.I)
            if mf:
                stage = mf.group(1)
            mcmd = re.match(r"CMD\s+(\[.*\])", l)
            if mcmd:
                cmds[stage] = json.loads(mcmd.group(1))
        words = cmds.get(mt.group(1)) if mt else (cmds.get(stage) if cmds else None)
        if words:
            out[sid] = (words, "dockerfile")
    return out


CMDLINES = service_command_lines()


def named_module(words):
    """(module, app attr or None) from a command line."""
    if not words:
        return None
    if words[0] == "uvicorn" and len(words) > 1:
        mod, _, attr = words[1].partition(":")
        return mod, attr or None
    if words[0].startswith("python") and len(words) > 2 and words[1] == "-m":
        return words[2], None
    return None


ROOTS = []  # (root dict, [start nodes])
for b in BINARIES:
    entry = [e["target"] for e in EDGES_FROM[b] if e["kind"] == "entry_point"]
    ROOTS.append(({"type": "binary", "node": b}, entry))
module_files = []
for b in BINARIES:
    fw = NODES[b]["data"]["framework"]
    if fw["type"] == "fastapi":
        mod = fw["app"].rsplit(".", 1)[0]
        if mod in MODULE_FILE:
            module_files.append(MODULE_FILE[mod])
for sid, (words, _) in CMDLINES.items():
    nm = named_module(words)
    if nm and nm[0] in MODULE_FILE:
        module_files.append(MODULE_FILE[nm[0]])
seen_mod = []
for f in module_files:
    if f not in seen_mod:
        seen_mod.append(f)
        ROOTS.append(({"type": "module", "node": f}, [f]))
for f in sorted(FILE_MODULE, key=lambda x: (project_of(x), path_of(x))):
    if is_test_file(f):
        starts = [f] + [c for c in CHILDREN[f] if is_test_callable(c) or (role(c) or {}).get("type") == "fixture"]
        for c in CHILDREN[f]:
            if kind(c) in CLASS_KINDS and NODES[c]["name"].startswith("Test"):
                starts += [m for m in CHILDREN[c] if is_test_callable(m)]
        ROOTS.append(({"type": "test", "node": f}, starts))

FOLLOW = {"imports", "calls", "instantiates", "references", "decorates", "mounts", "handles", "injects", "requests"}


def reach_from(starts):
    seen, stack = set(), list(starts)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        if kind(n) == "file":  # module-level assignments run when the module runs
            stack.extend(c for c in CHILDREN[n] if kind(c) in ("variable", "constant"))
        for e in EDGES_FROM[n]:
            k = e["kind"]
            if k not in FOLLOW:
                continue
            if k == "imports" and (kind(e["target"]) != "file" or (e["data"] or {}).get("type_only")):
                continue
            stack.append(e["target"])
            if k == "instantiates":
                init = QN_INDEX.get(qn(e["target"]) + ".__init__")
                if init:
                    stack.append(init)
        for e in EDGES_TO[n]:  # overrides, followed backwards
            if e["kind"] == "overrides":
                stack.append(e["source"])
    return seen


REACH = []
for root, starts in ROOTS:
    for n in sorted(reach_from(starts)):
        if NODES[n]["layer"] == "code" or kind(n) == "file":
            REACH.append({"node": n, "root": root})

# ---------------------------------------------------------------- 2f messages
UNMATCHED_MSG = []
PAYLOADS = []
TOPICS = [i for i in NODES if kind(i) in ("topic", "queue")]


def broker_of(cs, ctx):
    """External service named by the client's bootstrap_servers host, in a stack the project uses."""
    if cs is None:
        return None
    arg = next((a for a in cs["arguments"] if a["slot"].get("keyword") == "bootstrap_servers"), None)
    if not arg:
        return None
    txt = shape_text(arg["shape"], cs["from"])
    if not txt or None in txt:
        return None
    host = "".join(txt).split(",")[0].split(":")[0]
    proj = [p for p in NODES if kind(p) == "project" and NODES[p]["name"] == project_of(ctx)]
    stacks = {e["target"] for p in proj for e in EDGES_FROM[p] if e["kind"] == "uses"}
    for st in stacks:
        for c in CHILDREN[st]:
            if kind(c) == "external_service" and NODES[c]["name"] == host:
                return c
    return None


def linked_topics(ctx):
    proj = project_of(ctx)
    srcs = [b for b in BINARIES if project_of(b) == proj] + [p for p in NODES if kind(p) == "project" and NODES[p]["name"] == proj]
    return {e["target"] for s in srcs for e in EDGES_FROM[s] if e["kind"] in ("publishes", "subscribes")}


def binding_call_site(b):
    st = b["site"]
    return CALL_SITES.get((b["within"], st["path"], st["line"], st["column"]))


def match_message(ctx, site, direction, name_parts, broker):
    name = "".join(p if p is not None else "{?}" for p in name_parts) if name_parts else "{?}"
    if broker:
        pool = [t for t in TOPICS if PARENT.get(t) == broker]
    else:
        pool = [t for t in TOPICS if t in linked_topics(ctx)]
    cands = [t for t in pool if NODES[t]["name"] == name]
    topic = None
    if len(cands) == 1:
        topic = cands[0]
        k = "sends" if direction == "send" else "receives"
        add_edge(ctx, topic, k, {"name": name} if k == "sends" else None, site, "tree_sitter", "message_match", "2f")
    else:
        UNMATCHED_MSG.append({"from": ctx, "site": site, "direction": direction, "name": name,
                              "broker": broker, "candidates": sorted(cands)})
    declared = [t for t in TOPICS if NODES[t]["name"] == name]
    if not declared or not (set(declared) & linked_topics(ctx)):
        WARNINGS.append({"code": "message_without_link", "subject": ctx,
                         "message": f"{qn(ctx)} {'sends to' if direction == 'send' else 'receives from'} {name}, "
                                    f"which {project_of(ctx)} declares no link for."})
    return topic


def receiver_class(name, ctx):
    """Class of an instance named `name` in ctx, for a payload."""
    return value_class({"type": "name", "name": name}, ctx)


for cs in s1["call_sites"]:
    ctx, f = cs["from"], file_of(cs["from"])
    # producer.send(topic, value)
    m = re.fullmatch(r"(\w+)\.(send|send_and_wait)", cs["callee"])
    if m:
        recv = m.group(1)
        res = resolve_name(recv, ctx)
        bind = None
        if res and kind(res[0]) in ("variable", "constant"):
            bs = BINDINGS.get((PARENT.get(res[0]), recv), [])
            bind = bs[0] if len(bs) == 1 else None
        if not bind or bind["shape"]["type"] != "call":
            continue
        cls = bind["shape"]["name"]
        cf = file_of(bind["within"])
        if IMPORTS.get(cf, {}).get(cls) not in ("kafka.KafkaProducer", "aiokafka.AIOKafkaProducer"):
            continue
        a0 = next((a for a in cs["arguments"] if a["slot"].get("position") == 0 or a["slot"].get("keyword") == "topic"), None)
        a1 = next((a for a in cs["arguments"] if a["slot"].get("position") == 1 or a["slot"].get("keyword") == "value"), None)
        topic = match_message(ctx, cs["site"], "send", shape_text(a0["shape"], ctx) if a0 else None,
                              broker_of(binding_call_site(bind), ctx))
        if topic and a1 and a1["shape"]["type"] == "call":
            mm = re.fullmatch(r"(\w+)\.(model_dump_json|model_dump|json|dict)", a1["shape"]["name"])
            if mm:
                c = receiver_class(mm.group(1), ctx)
                if c:
                    PAYLOADS.append({"topic": topic, "node": ctx, "direction": "send", "class": c})
        continue
    # for message in KafkaConsumer(topic, ...)
    if IMPORTS.get(f, {}).get(cs["callee"]) in ("kafka.KafkaConsumer", "aiokafka.AIOKafkaConsumer"):
        st = cs["site"]
        iters = [b for (w, n), bs in BINDINGS.items() if w == ctx for b in bs
                 if b["shape"]["type"] == "item" and b["shape"]["name"] == cs["callee"]
                 and b["shape"]["accessor"] == "iter" and b["site"]["line"] == st["line"]]
        if not iters:
            continue
        a0 = next((a for a in cs["arguments"] if a["slot"].get("position") == 0), None)
        topic = match_message(ctx, cs["site"], "receive", shape_text(a0["shape"], ctx) if a0 else None,
                              broker_of(cs, ctx))
        if topic:
            msg = iters[0]["name"]
            for other in s1["call_sites"]:
                if other["from"] != ctx:
                    continue
                mm = re.fullmatch(r"([\w.]+)\.(model_validate_json|model_validate|parse_raw)", other["callee"])
                if not mm:
                    continue
                arg = next((a for a in other["arguments"] if a["slot"].get("position") == 0), None)
                if not arg or arg["shape"]["type"] != "name" or arg["shape"]["name"] not in (msg, msg + ".value"):
                    continue
                res = resolve_name(mm.group(1), ctx)
                if res and kind(res[0]) in CLASS_KINDS:
                    PAYLOADS.append({"topic": topic, "node": ctx, "direction": "receive", "class": res[0]})

# ---------------------------------------------------------------- 2f commands
for sid, (words, prov) in CMDLINES.items():
    runs = [e["target"] for e in EDGES_FROM[sid] if e["kind"] == "runs"]
    if not runs:
        continue
    b = runs[0]
    entry = [e["target"] for e in EDGES_FROM[b] if e["kind"] == "entry_point"]
    if not entry or entry[0] not in FILE_MODULE:
        continue
    nm = named_module(words)
    rest = None
    if nm and words[0].startswith("python") and nm[0] == FILE_MODULE[entry[0]]:
        rest = words[3:]
    elif words and words[0].startswith("python") and len(words) > 1 and words[1] == path_of(entry[0]):
        rest = words[2:]
    if rest is None:
        continue
    cmd_words = []
    for w in rest:
        if w.startswith("-"):
            break
        cmd_words.append(w)
    commands = [c for c in NODES if kind(c) == "command" and file_of(c) == entry[0]]
    if not cmd_words or not commands:
        continue
    best = None
    for c in commands:
        p = NODES[c]["data"]["path"]
        if p and cmd_words[: len(p)] == p and (best is None or len(p) > len(NODES[best]["data"]["path"])):
            best = c
    if best is None:
        WARNINGS.append({"code": "command_not_found", "subject": sid,
                         "message": f"Service {NODES[sid]['name']} runs command words {' '.join(cmd_words)}, "
                                    f"which name no command of binary {NODES[b]['name']}."})
        continue
    add_edge(sid, best, "invokes", {"words": cmd_words}, None, prov, "command_match", "2f")

if FLOW_LIMIT_HIT:
    WARNINGS.append({"code": "flow_round_limit", "subject": None, "message": "2b stopped at its round limit."})

# ---------------------------------------------------------------- write
for rp in ROUTE_PATHS:
    rp.pop("_app", None)
inferred = [{"node": n, "class": c, "evidence": INFERRED_EVIDENCE[n]} for n, c in sorted(INFERRED.items())]
out = {
    "edges": EDGES,
    "resolved_reference_ids": RESOLVED_IDS,
    "flow_resolved_reference_ids": FLOW_IDS,
    "inferred_types": inferred,
    "reach": REACH,
    "route_paths": ROUTE_PATHS,
    "unmatched_http_calls": UNMATCHED_HTTP,
    "unmatched_messages": UNMATCHED_MSG,
    "payloads": PAYLOADS,
    "warnings": WARNINGS,
}
with open(os.path.join(OUT, "stage2.json"), "w") as fh:
    json.dump(out, fh, indent=1)
    fh.write("\n")

# ---------------------------------------------------------------- self-check
E13 = {"framework": {"mounts", "handles", "injects"}, "route_match": {"requests"},
       "message_match": {"sends", "receives"}, "command_match": {"invokes"}, "flow": {"calls", "instantiates"}}
MUST = {"mounts": "framework", "handles": "framework", "injects": "framework", "requests": "route_match",
        "sends": "message_match", "receives": "message_match", "invokes": "command_match"}
for e in EDGES:
    rb = e["resolved_by"]
    if rb in E13:
        assert e["kind"] in E13[rb], e
    if e["kind"] in MUST:
        assert rb == MUST[e["kind"]], e
    if rb is not None:
        assert e["provenance"] in ("tree_sitter", "scip") or e["kind"] == "invokes", e
assert len(set(RESOLVED_IDS)) == len(RESOLVED_IDS) and not set(RESOLVED_IDS) & set(FLOW_IDS)

print("rounds of 2b:", rounds)
print("edges by kind and resolved_by:")
for (k, rb), n in sorted(Counter((e["kind"], e["resolved_by"]) for e in EDGES).items()):
    print(f"  {k:13s} {rb:16s} {n}")
print("total edges:", len(EDGES), " resolved refs:", len(RESOLVED_IDS), " flow refs:", len(FLOW_IDS))
print("unresolved references by kind:", dict(sorted(Counter(r["kind"] for r in UNRESOLVED.values()).items())),
      "total", len(UNRESOLVED))

cnt = Counter(e["kind"] for e in EDGES)
checks = []


def check(label, cond):
    checks.append((label, bool(cond)))
    print(("PASS " if cond else "FAIL ") + label)


check("Requests 2", cnt["requests"] == 2)
check("Sends 1", cnt["sends"] == 1)
check("Receives 1", cnt["receives"] == 1)
check("Invokes 1", cnt["invokes"] == 1)
check("route_paths 3", len(ROUTE_PATHS) == 3)
r_param = QN_INDEX["billing.services.process.r"]
check("inferred r -> InvoiceRepo evidence 2",
      any(t["node"] == r_param and t["class"] == QN_INDEX["billing.repo.InvoiceRepo"] and t["evidence"] == 2 for t in inferred))

by_file = defaultdict(set)
for rec in REACH:
    f = file_of(rec["node"])
    by_file[f].add(rec["root"]["node"])
B = {(project_of(b), NODES[b]["name"]): b for b in BINARIES}
F = lambda proj, p: FILES[(proj, p)]
api, worker = B[("billing-api", "api")], B[("billing-api", "worker")]
inv, svc = F("billing-api", "src/billing/routes/invoices.py"), F("billing-api", "src/billing/services.py")
tsvc = F("billing-api", "tests/test_services.py")
check("invoices.py reached by binary api, not worker", api in by_file[inv] and worker not in by_file[inv])
check("services.py reached by worker and test_services.py, not api",
      worker in by_file[svc] and tsvc in by_file[svc] and api not in by_file[svc])
for p in ("src/billing/outbox.py", "src/billing/db.py"):
    check(f"{p} reached by api and worker", {api, worker} <= by_file[F("billing-api", p)])
print("reach per file (roots):")
for f in sorted(by_file, key=lambda x: (project_of(x) or "", path_of(x))):
    names = sorted(("%s:%s" % (NODES[r]["name"], project_of(r)) if kind(r) == "binary" else
                    ("mod:" if any(rt["node"] == r and rt["type"] == "module" for rt, _ in ROOTS) and not is_test_file(r) else "test:") + path_of(r))
                   for r in by_file[f])
    print(f"  {project_of(f)}:{path_of(f)} <- {', '.join(names)}")
print("warnings:", [w["code"] for w in WARNINGS])
print("inferred:", [(qn(t["node"]), qn(t["class"]), t["evidence"]) for t in inferred])
if not all(c for _, c in checks):
    sys.exit(1)
