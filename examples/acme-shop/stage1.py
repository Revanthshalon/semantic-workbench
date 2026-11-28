"""Stage 1 of the Acme Shop indexer: read every .py file alone with `ast`.

Run: python3 -I stage1.py   (writes out/stage1.json)
"""
import ast
import builtins
import json
import os
import re
import string
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT + "/lib")
from ids import node_id, reference_id, content_hash  # noqa: E402

PROJECTS = ["shared-api", "billing-api", "ledger-api"]
MTIME_NS = 1795478400000000000
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace", "websocket"}
BUILTIN_NAMES = set(dir(builtins)) | {"None"}

OUT = {k: [] for k in ("nodes", "edges", "references", "call_sites", "bindings", "returns", "files")}


def project_node_id(pid):
    return node_id("workspace", "", "", "project", pid, 0)


def module_name(path):
    p = path[4:] if path.startswith("src/") else path
    p = p[:-3].replace("/", ".")
    if p.endswith(".__init__"):
        p = p[: -len(".__init__")]
    elif p == "__init__":
        p = ""
    return p


def visibility(name):
    if name.startswith("__") and name.endswith("__") and len(name) > 4:
        return "public"
    return "private" if name.startswith("_") else "public"


def dotted(expr):
    """Dotted name of a Name/Attribute chain, else None."""
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if isinstance(expr, ast.Name):
        parts.append(expr.id)
        return ".".join(reversed(parts))
    return None


def template(parts):
    """Merge adjacent text, drop empty text."""
    out = []
    for p in parts:
        if "text" in p:
            if p["text"] == "":
                continue
            if out and "text" in out[-1]:
                out[-1] = {"text": out[-1]["text"] + p["text"]}
                continue
        out.append(p)
    return {"parts": out}


def tmpl_from_expr(expr):
    """A Template for a route path or prefix."""
    if expr is None:
        return None
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return template([{"text": expr.value}])
    s = shape(expr)
    if s["type"] == "template":
        return {"parts": s["parts"]}
    if s["type"] == "name":
        return {"parts": [{"hole": s["name"]}]}
    return {"parts": [{"unknown": True}]}


def str_parts(expr):
    """Template parts of a string-ish expression, or None when it is not one."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return [{"text": expr.value}]
    if isinstance(expr, ast.JoinedStr):
        parts = []
        for v in expr.values:
            if isinstance(v, ast.Constant):
                parts.append({"text": v.value})
            elif isinstance(v, ast.FormattedValue):
                d = dotted(v.value)
                parts.append({"hole": d} if d else {"unknown": True})
            else:
                parts.append({"unknown": True})
        return parts
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left, right = str_parts(expr.left), str_parts(expr.right)
        if left is None and right is None:
            return None
        def side(p, e):
            if p is not None:
                return p
            d = dotted(e)
            return [{"hole": d} if d else {"unknown": True}]
        return side(left, expr.left) + side(right, expr.right)
    if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format"
            and isinstance(expr.func.value, ast.Constant) and isinstance(expr.func.value.value, str)):
        args = [dotted(a) for a in expr.args]
        kws = {k.arg: dotted(k.value) for k in expr.keywords if k.arg}
        parts, auto = [], 0
        try:
            for lit, field, _spec, _conv in string.Formatter().parse(expr.func.value.value):
                parts.append({"text": lit})
                if field is None:
                    continue
                if field == "":
                    field = str(auto)
                    auto += 1
                if field.isdigit():
                    i = int(field)
                    n = args[i] if i < len(args) else None
                else:
                    n = kws.get(field)
                parts.append({"hole": n} if n else {"unknown": True})
        except (ValueError, IndexError):
            return [{"unknown": True}]
        return parts
    return None


def shape(expr):
    if expr is None:
        return {"type": "literal", "kind": "null"}
    sp = str_parts(expr)
    if sp is not None:
        if isinstance(expr, ast.Constant):
            return {"type": "text", "value": expr.value}
        return {"type": "template", "parts": template(sp)["parts"]}
    if isinstance(expr, ast.Constant):
        v = expr.value
        if v is None:
            return {"type": "literal", "kind": "null"}
        if isinstance(v, bool):
            return {"type": "literal", "kind": "bool"}
        if isinstance(v, (int, float, complex)):
            return {"type": "literal", "kind": "number"}
        if isinstance(v, bytes):
            return {"type": "literal", "kind": "bytes"}
        return {"type": "other"}  # Ellipsis
    d = dotted(expr)
    if d:
        return {"type": "name", "name": d}
    if isinstance(expr, ast.Call):
        n = dotted(expr.func)
        return {"type": "call", "name": n} if n else {"type": "other"}
    if isinstance(expr, ast.Subscript):
        n = dotted(expr.value)
        return {"type": "item", "name": n, "accessor": "index"} if n else {"type": "other"}
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        kind = {ast.List: "list", ast.Tuple: "tuple", ast.Set: "set"}[type(expr)]
        return {"type": "collection", "kind": kind, "elements": [shape(e) for e in expr.elts]}
    if isinstance(expr, ast.Dict):
        return {"type": "collection", "kind": "dict", "elements": [shape(e) for e in expr.values]}
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        kind = {ast.ListComp: "list", ast.SetComp: "set", ast.GeneratorExp: "list"}[type(expr)]
        return {"type": "collection", "kind": kind, "elements": [shape(expr.elt)]}
    if isinstance(expr, ast.DictComp):
        return {"type": "collection", "kind": "dict", "elements": [shape(expr.value)]}
    if isinstance(expr, ast.Starred):
        n = dotted(expr.value)
        return {"type": "spread", "name": n} if n else {"type": "other"}
    return {"type": "other"}


def iter_shape(it):
    """Shape of one element of iterating `it` (a for target)."""
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr in ("keys", "values", "items") \
            and not it.args:
        n = dotted(it.func.value)
        if n:
            return {"type": "item", "name": n, "accessor": it.func.attr}
    n = dotted(it)
    if n:
        return {"type": "item", "name": n, "accessor": "iter"}
    if isinstance(it, ast.Call):
        n = dotted(it.func)
        if n:
            return {"type": "item", "name": n, "accessor": "iter"}
    return {"type": "other"}


def ends_without_return(stmts):
    """True when the end of this block can be reached."""
    if not stmts:
        return True
    last = stmts[-1]
    if isinstance(last, (ast.Return, ast.Raise)):
        return False
    if isinstance(last, ast.If):
        return ends_without_return(last.body) or ends_without_return(last.orelse)
    if isinstance(last, (ast.With, ast.AsyncWith)):
        return ends_without_return(last.body)
    if isinstance(last, ast.While) and isinstance(last.test, ast.Constant) and last.test.value is True:
        return any(isinstance(n, ast.Break) for n in ast.walk(last))
    if isinstance(last, ast.Try):
        return (ends_without_return(last.body + last.orelse) if not last.finalbody else True) or any(
            ends_without_return(h.body) for h in last.handlers)
    return True


class FileReader:
    def __init__(self, pid, path, text):
        self.pid, self.path, self.text = pid, path, text
        self.module = module_name(path)
        self.lines = text.split("\n")
        self.nodes = []
        self.node_by_key = {}  # (kind, qname) -> first node
        self.parent = {}       # child id -> parent id
        self.file_id = None
        self.imports_from = {}  # bound name -> absolute dotted target
        self.ast_owner = {}    # id(ast def node) -> node record
        self.module_vars = {}  # module-level name -> node record
        self.route_handlers = {}  # id(funcdef) -> [route records]
        self.is_test_file = (os.path.basename(path).startswith("test_") or path.endswith("_test.py")
                             or "tests" in path.split("/")[:-1] or os.path.basename(path) == "conftest.py")
        self.imports_fastapi = False
        self.imports_argparse = False

    # ---------- helpers ----------
    def src(self, n):
        s = ast.get_source_segment(self.text, n)
        return re.sub(r"\s*\n\s*", " ", s) if s is not None else ast.unparse(n)

    def span(self, n):
        return {"start_line": n.lineno, "start_column": n.col_offset,
                "end_line": n.end_lineno, "end_column": n.end_col_offset}

    def site(self, line, col):
        return {"path": self.path, "line": line, "column": col}

    def add_node(self, kind, name, qname, span, data, parent_id):
        ordinal = sum(1 for n in self.nodes if n["kind"] == kind and n["qualified_name"] == qname)
        nid = node_id("project", self.pid, self.path, kind, qname, ordinal)
        rec = {"id": nid, "kind": kind, "name": name, "qualified_name": qname,
               "scope": {"type": "project", "name": self.pid},
               "origin": {"type": "parsed", "path": self.path, "span": span},
               "ordinal": ordinal, "data": data, "layer": "code"}
        self.nodes.append(rec)
        self.node_by_key.setdefault((kind, qname), rec)
        if parent_id is not None:
            self.parent[nid] = parent_id
            OUT["edges"].append({"source": parent_id, "target": nid, "kind": "contains", "data": None, "site": None,
                                 "provenance": "tree_sitter", "note": None, "resolved_by": None, "stage": "1"})
        return rec

    def ref(self, frm, name, kind, line, col, data=None):
        OUT["references"].append({
            "id": reference_id(frm, name, kind, self.path, line, col), "from": frm, "name": name, "kind": kind,
            "data": data, "site": self.site(line, col), "flow_resolved": False})

    def call_site_pos(self, call):
        """A call's site: its start, or the attribute name when the receiver is itself a call (chains)."""
        f = call.func
        if isinstance(f, ast.Attribute) and not dotted(f):
            return f.end_lineno, f.end_col_offset - len(f.attr)
        return call.lineno, call.col_offset

    def expr_site(self, e):
        return self.call_site_pos(e) if isinstance(e, ast.Call) else (e.lineno, e.col_offset)

    def signature(self, n):
        first = n.body[0]
        lines = self.lines[n.lineno - 1: first.lineno]
        lines[-1] = lines[-1][: first.col_offset]  # cut at the body's own start
        if first.lineno == n.lineno:
            lines = [self.lines[n.lineno - 1][n.col_offset: first.col_offset]]
        else:
            lines[0] = lines[0][n.col_offset:]
            if lines[-1].strip() == "":
                lines = lines[:-1]
        seg = " ".join(l.strip() for l in lines if l.strip())
        seg = re.sub(r"\s*#[^\n]*$", "", seg).rstrip()
        if seg.endswith(":"):
            seg = seg[:-1].rstrip()
        seg = re.sub(r"\(\s+", "(", seg)
        seg = re.sub(r",?\s+\)", ")", seg) if re.search(r",\s+\)", seg) else seg
        return seg

    @staticmethod
    def doc(n):
        if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            return n.body[0].value.value
        return None

    def deco_name(self, d):
        f = d.func if isinstance(d, ast.Call) else d
        return dotted(f) or self.src(f)

    def resolved_import(self, name):
        return self.imports_from.get(name)

    def type_names(self, ann):
        """Each dotted name in an annotation (string annotations parsed), builtins skipped."""
        if ann is None:
            return []
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            try:
                ann2 = ast.parse(ann.value, mode="eval").body
            except SyntaxError:
                return []
            return [(n, ann.lineno, ann.col_offset) for n, _, _ in self.type_names(ann2)]
        out = []
        d = dotted(ann)
        if d:
            if d not in BUILTIN_NAMES:
                out.append((d, ann.lineno, ann.col_offset))
            return out
        for child in ast.iter_child_nodes(ann):
            if isinstance(child, ast.expr):
                out.extend(self.type_names(child))
        return out

    # ---------- pass 1: definitions ----------
    def read(self):
        tree = ast.parse(self.text, filename=self.path)
        self.tree = tree
        lines = self.lines[:-1] if self.lines and self.lines[-1] == "" else self.lines
        if not lines:
            span = {"start_line": 1, "start_column": 0, "end_line": 1, "end_column": 0}
        else:
            span = {"start_line": 1, "start_column": 0, "end_line": len(lines), "end_column": len(lines[-1])}
        frec = self.add_node("file", os.path.basename(self.path), self.path, span, {"doc": self.doc(tree)},
                             project_node_id(self.pid))
        self.file_id = frec["id"]
        self.file_rec = frec
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                if n.module.split(".")[0] == "fastapi":
                    self.imports_fastapi = True
                if n.module == "argparse":
                    self.imports_argparse = True
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.split(".")[0] == "fastapi":
                        self.imports_fastapi = True
                    if a.name == "argparse":
                        self.imports_argparse = True
        self.module_level(tree.body, frec)
        self.find_commands(tree)
        # pass 2: references, call sites, bindings, returns
        self.walk_block(tree.body, owner=frec, fn_locals=None, cls=None)

    def abs_module(self, n):
        if n.level == 0:
            return n.module or ""
        pkg = self.module if self.path.endswith("__init__.py") else self.module.rpartition(".")[0]
        parts = pkg.split(".") if pkg else []
        if n.level > 1:
            parts = parts[: len(parts) - (n.level - 1)]
        base = ".".join(parts)
        return ".".join(p for p in (base, n.module) if p)

    def module_level(self, body, frec):
        for st in body:
            if isinstance(st, ast.Import):
                for a in st.names:
                    bound = a.asname or a.name.split(".")[0]
                    self.add_node("import", bound, f"{self.module}.{bound}", self.span(a), None, frec["id"])
                    self.imports_from[bound] = a.name if a.asname else bound
                    self.ref(frec["id"], a.name, "imports", st.lineno, st.col_offset,
                             {"specifier": a.name, "alias": a.asname, "type_only": False})
            elif isinstance(st, ast.ImportFrom):
                target_mod = self.abs_module(st)
                written = "." * st.level + (st.module or "")
                for a in st.names:
                    if a.name == "*":
                        self.ref(frec["id"], target_mod, "imports", st.lineno, st.col_offset,
                                 {"specifier": written, "alias": None, "type_only": False})
                        continue
                    bound = a.asname or a.name
                    self.add_node("import", bound, f"{self.module}.{bound}", self.span(a), None, frec["id"])
                    full = f"{target_mod}.{a.name}" if target_mod else a.name
                    self.imports_from[bound] = full
                    spec = f"{written}.{a.name}" if st.module else f"{written}{a.name}"
                    self.ref(frec["id"], full, "imports", st.lineno, st.col_offset,
                             {"specifier": spec, "alias": a.asname, "type_only": False})
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.define_function(st, frec, self.module, in_class=None, module_level=True)
            elif isinstance(st, ast.ClassDef):
                self.define_class(st, frec, self.module, module_level=True)
            elif hasattr(ast, "TypeAlias") and isinstance(st, ast.TypeAlias):
                self.define_type_alias(st.name, [self.src(t) for t in st.type_params], frec)
            elif (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)
                  and (dotted(st.annotation) or "").split(".")[-1] == "TypeAlias"):
                self.define_type_alias(st.target, [], frec)
            elif isinstance(st, (ast.Assign, ast.AnnAssign)):
                targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                for t in targets:
                    for nm in self.target_names(t):
                        self.define_module_var(nm, st, frec)
            elif isinstance(st, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for blk in ("body", "orelse", "finalbody"):
                    self.module_level(getattr(st, blk, []) or [], frec)
                for h in getattr(st, "handlers", []) or []:
                    self.module_level(h.body, frec)

    @staticmethod
    def target_names(t):
        if isinstance(t, ast.Name):
            return [t]
        if isinstance(t, (ast.Tuple, ast.List)):
            return [n for e in t.elts for n in FileReader.target_names(e)]
        if isinstance(t, ast.Starred):
            return FileReader.target_names(t.value)
        return []

    def role_for_value(self, value):
        if not isinstance(value, ast.Call):
            return None
        d = dotted(value.func)
        target = self.resolved_import(d.split(".")[0]) if d else None
        full = None
        if d:
            head, _, rest = d.partition(".")
            full = (self.imports_from.get(head, head) + ("." + rest if rest else ""))
        if full in ("fastapi.FastAPI",):
            return {"type": "app"}
        if full in ("fastapi.APIRouter", "fastapi.routing.APIRouter"):
            kw = {k.arg: k.value for k in value.keywords if k.arg}
            tags = []
            if isinstance(kw.get("tags"), (ast.List, ast.Tuple)):
                tags = [e.value for e in kw["tags"].elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            return {"type": "router", "prefix": tmpl_from_expr(kw.get("prefix")), "tags": tags}
        return None

    def define_module_var(self, name_node, st, frec):
        nm = name_node.id
        kind = "constant" if re.fullmatch(r"[A-Z][A-Z0-9_]*", nm) else "variable"
        ann = st.annotation if isinstance(st, ast.AnnAssign) else None
        if ann is not None and (dotted(ann) or "").split(".")[-1] == "Final":
            kind = "constant"
        if nm in self.module_vars:
            return
        value = st.value
        data = {"visibility": visibility(nm), "is_static": False, "is_exported": not nm.startswith("_"),
                "declared_type": self.src(ann) if ann is not None else None,
                "default": None, "role": self.role_for_value(value) if kind == "variable" else None}
        rec = self.add_node(kind, nm, f"{self.module}.{nm}", self.span(name_node), data, frec["id"])
        self.module_vars[nm] = rec
        for tn, l, c in self.type_names(ann):
            self.ref(rec["id"], tn, "type_of", l, c)

    def define_type_alias(self, name_node, type_parameters, frec):
        """`type X[T] = ...` (3.12), or `X: TypeAlias = ...`, which has no type parameters of its own."""
        nm = name_node.id
        data = {"doc": None, "signature": None, "visibility": visibility(nm), "is_abstract": False,
                "is_exported": not nm.startswith("_"), "decorators": [],
                "type_parameters": type_parameters, "role": None}
        self.add_node("type_alias", nm, f"{self.module}.{nm}", self.span(name_node), data, frec["id"])

    def callable_data(self, fn, is_method, module_level, cls_abstract=False):
        decos = [self.deco_name(d) for d in fn.decorator_list]
        last = [d.split(".")[-1] for d in decos]
        role = None
        for d in decos:
            head, _, rest = d.partition(".")
            full = self.imports_from.get(head, head) + ("." + rest if rest else "")
            if full == "pytest.fixture":
                role = {"type": "fixture"}
        return {"doc": self.doc(fn), "signature": self.signature(fn), "visibility": visibility(fn.name),
                "is_async": isinstance(fn, ast.AsyncFunctionDef),
                "is_static": is_method and "staticmethod" in last,
                "is_abstract": "abstractmethod" in last,
                "is_exported": module_level and not fn.name.startswith("_"),
                "decorators": decos, "type_parameters": [self.src(t) for t in getattr(fn, "type_params", [])],
                "return_type": self.src(fn.returns) if fn.returns is not None else None, "role": role}

    def define_function(self, fn, parent, prefix, in_class, module_level):
        kind = "method" if in_class is not None else "function"
        qn = f"{prefix}.{fn.name}"
        rec = self.add_node(kind, fn.name, qn, self.span(fn), self.callable_data(fn, kind == "method", module_level),
                            parent["id"])
        self.ast_owner[id(fn)] = rec
        rec["_ast"] = fn
        rec["_class"] = in_class
        for tn, l, c in self.type_names(fn.returns):
            self.ref(rec["id"], tn, "returns", l, c)
        for d in fn.decorator_list:
            self.ref(rec["id"], self.deco_name(d), "decorates", d.lineno, d.col_offset)
        routes = self.define_routes(fn, qn) if module_level and kind == "function" else []
        path_holes = {p["hole"] for r in routes for p in r["data"]["path"]["parts"] if "hole" in p}
        path_holes |= {m for r in routes for p in r["data"]["path"]["parts"] if "text" in p
                       for m in re.findall(r"\{(\w+)(?::[^}]*)?\}", p["text"])}
        # parameters
        a = fn.args
        pos = a.posonlyargs + a.args
        defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
        params = list(zip(pos, defaults))
        if a.vararg:
            params.append((a.vararg, None))
        params += list(zip(a.kwonlyargs, a.kw_defaults))
        if a.kwarg:
            params.append((a.kwarg, None))
        for i, (arg, default) in enumerate(params):
            if in_class is not None and i == 0 and arg.arg in ("self", "cls") and arg in pos:
                continue
            member = {"visibility": None, "is_static": False, "is_exported": False,
                      "declared_type": self.src(arg.annotation) if arg.annotation is not None else None,
                      "default": self.src(default)[:80] if default is not None else None, "role": None}
            prec = self.add_node("parameter", arg.arg, f"{qn}.{arg.arg}", self.span(arg),
                                 {"member": member, "source": "path" if arg.arg in path_holes else None}, rec["id"])
            for tn, l, c in self.type_names(arg.annotation):
                self.ref(prec["id"], tn, "type_of", l, c)
            # injects: Depends(x) / Security(x)
            if isinstance(default, ast.Call) and (dotted(default.func) or "").split(".")[-1] in ("Depends", "Security") \
                    and default.args and dotted(default.args[0]):
                self.ref(rec["id"], dotted(default.args[0]), "injects", default.args[0].lineno,
                         default.args[0].col_offset)
            # pytest: a test function or fixture parameter named like a fixture
            if self.is_test_file and kind == "function" and (fn.name.startswith("test_") or
                                                              (rec["data"]["role"] or {}).get("type") == "fixture"):
                if arg.arg not in ("self", "cls", "request"):
                    self.ref(rec["id"], arg.arg, "injects", arg.lineno, arg.col_offset)
        # nested defs
        for st in ast.walk(fn):
            pass
        self.nested_defs(fn.body, rec, qn)
        # self.x fields: first appearance
        if in_class is not None:
            first = pos[0].arg if pos and not ("staticmethod" in [d.split(".")[-1] for d in rec["data"]["decorators"]]) else None
            if first:
                for n in ast.walk(fn):
                    tgts = []
                    if isinstance(n, ast.Assign):
                        tgts = n.targets
                    elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                        tgts = [n.target]
                    for t in tgts:
                        if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == first:
                            key = ("field", f"{in_class['qualified_name']}.{t.attr}")
                            if key not in self.node_by_key:
                                ann = n.annotation if isinstance(n, ast.AnnAssign) else None
                                frec = self.add_node("field", t.attr, key[1], self.span(t), {
                                    "visibility": visibility(t.attr), "is_static": False, "is_exported": False,
                                    "declared_type": self.src(ann) if ann is not None else None,
                                    "default": None, "role": None}, in_class["id"])
                                for tn, l, c in self.type_names(ann):
                                    self.ref(frec["id"], tn, "type_of", l, c)
        return rec

    def nested_defs(self, body, parent, prefix):
        for st in body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.define_function(st, parent, prefix, in_class=None, module_level=False)
            elif isinstance(st, ast.ClassDef):
                self.define_class(st, parent, prefix, module_level=False)
            else:
                for blk in ("body", "orelse", "finalbody"):
                    sub = getattr(st, blk, None)
                    if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                        self.nested_defs(sub, parent, prefix)
                for h in getattr(st, "handlers", []) or []:
                    self.nested_defs(h.body, parent, prefix)

    def define_routes(self, fn, handler_qn):
        routes = []
        for d in fn.decorator_list:
            if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and isinstance(d.func.value, ast.Name) and d.func.attr in HTTP_METHODS | {"api_route"}):
                continue
            recv = d.func.value.id
            var = self.module_vars.get(recv)
            is_web = var is not None and (var["data"] or {}).get("role") and var["data"]["role"]["type"] in ("app", "router")
            if not (is_web or self.imports_fastapi):
                continue
            kw = {k.arg: k.value for k in d.keywords if k.arg}
            path_expr = d.args[0] if d.args else kw.get("path")
            path = tmpl_from_expr(path_expr) or {"parts": []}
            local = "".join(p.get("text") or ("{%s}" % p["hole"] if "hole" in p else "{?}") for p in path["parts"])
            if d.func.attr == "api_route":
                ms = kw.get("methods")
                methods = [e.value.lower() for e in getattr(ms, "elts", []) if isinstance(e, ast.Constant)] or ["get"]
            else:
                methods = [d.func.attr]
            status = kw.get("status_code")
            status = status.value if isinstance(status, ast.Constant) and isinstance(status.value, int) else None
            tags = [e.value for e in getattr(kw.get("tags"), "elts", []) if isinstance(e, ast.Constant)]
            for m in methods:
                qn = f"{handler_qn}@{m.upper()} {local}"
                r = self.add_node("route", f"{m.upper()} {local}", qn, self.span(d),
                                  {"method": m, "path": path, "status_code": status, "tags": tags}, self.file_id)
                routes.append(r)
                src_id = var["id"] if var is not None else self.file_id
                self.ref(src_id, qn, "mounts", d.lineno, d.col_offset, {"prefix": None, "tags": []})
                self.ref(r["id"], handler_qn, "handles", fn.lineno, fn.col_offset)
                rm = kw.get("response_model")
                if rm is not None:
                    for tn, l, c in self.type_names(rm):
                        self.ref(r["id"], tn, "returns", l, c)
                for dep in getattr(kw.get("dependencies"), "elts", []):
                    if isinstance(dep, ast.Call) and dep.args and dotted(dep.args[0]):
                        self.ref(r["id"], dotted(dep.args[0]), "injects", dep.args[0].lineno, dep.args[0].col_offset)
        return routes

    def generic_base_params(self, cls):
        """The pre-3.12 form: the parameters of a base `Generic[T, ...]`, else none."""
        for b in cls.bases:
            if isinstance(b, ast.Subscript) and (dotted(b.value) or "").split(".")[-1] == "Generic":
                elts = b.slice.elts if isinstance(b.slice, ast.Tuple) else [b.slice]
                return [self.src(e) for e in elts]
        return []

    def define_class(self, cls, parent, prefix, module_level):
        qn = f"{prefix}.{cls.name}"
        bases = [dotted(b) or self.src(b) for b in cls.bases]
        full_bases = []
        for b in bases:
            head, _, rest = b.partition(".")
            full_bases.append(self.imports_from.get(head, head) + ("." + rest if rest else ""))
        role = {"type": "model"} if "pydantic.BaseModel" in full_bases else None
        decos = [self.deco_name(d) for d in cls.decorator_list]
        type_parameters = [self.src(t) for t in getattr(cls, "type_params", [])] or self.generic_base_params(cls)
        data = {"doc": self.doc(cls), "signature": self.signature(cls), "visibility": visibility(cls.name),
                "is_abstract": any(b.split(".")[-1] == "ABC" for b in full_bases),
                "is_exported": module_level and not cls.name.startswith("_"),
                "decorators": decos, "type_parameters": type_parameters,
                "role": role}
        rec = self.add_node("class", cls.name, qn, self.span(cls), data, parent["id"])
        self.ast_owner[id(cls)] = rec
        for b in cls.bases:
            self.ref(rec["id"], dotted(b) or self.src(b), "extends", b.lineno, b.col_offset)
        for d in cls.decorator_list:
            self.ref(rec["id"], self.deco_name(d), "decorates", d.lineno, d.col_offset)
        self.class_body(cls.body, rec, qn)
        if any(m["data"]["is_abstract"] for m in self.nodes if self.parent.get(m["id"]) == rec["id"] and m["kind"] == "method"):
            pass  # the spec marks abstract by base ABC; methods carry their own flag
        return rec

    def class_body(self, body, rec, qn):
        for st in body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.define_function(st, rec, qn, in_class=rec, module_level=False)
            elif isinstance(st, ast.ClassDef):
                self.define_class(st, rec, qn, module_level=False)
            elif isinstance(st, (ast.Assign, ast.AnnAssign)):
                targets = st.targets if isinstance(st, ast.Assign) else [st.target]
                ann = st.annotation if isinstance(st, ast.AnnAssign) else None
                for t in targets:
                    for nm in self.target_names(t):
                        key = ("field", f"{qn}.{nm.id}")
                        if key in self.node_by_key:
                            continue
                        f = self.add_node("field", nm.id, key[1], self.span(nm), {
                            "visibility": visibility(nm.id), "is_static": False, "is_exported": False,
                            "declared_type": self.src(ann) if ann is not None else None,
                            "default": self.src(st.value)[:80] if st.value is not None else None,
                            "role": None}, rec["id"])
                        for tn, l, c in self.type_names(ann):
                            self.ref(f["id"], tn, "type_of", l, c)
            elif isinstance(st, (ast.If, ast.Try)):
                for blk in ("body", "orelse", "finalbody"):
                    self.class_body(getattr(st, blk, []) or [], rec, qn)

    # ---------- argparse ----------
    def find_commands(self, tree):
        if not self.imports_argparse:
            return
        scopes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for scope in scopes:
            own = []  # nodes of this scope, not of nested defs

            def collect(n):
                for c in ast.iter_child_nodes(n):
                    if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                        continue
                    own.append(c)
                    collect(c)
            collect(scope)
            parsers, subs, made = {}, {}, {}

            def cmd_of(e):
                if isinstance(e, ast.Name):
                    return parsers.get(e.id)
                if isinstance(e, ast.Call) and isinstance(e.func, ast.Attribute):
                    if id(e) in made:
                        return made[id(e)]
                    d = dotted(e.func) or ""
                    if d.split(".")[-1] == "ArgumentParser" and (d == "ArgumentParser" and
                                                                 self.imports_from.get("ArgumentParser") == "argparse.ArgumentParser"
                                                                 or d == "argparse.ArgumentParser"):
                        return make_program(e)
                    if e.func.attr == "add_parser" and isinstance(e.func.value, ast.Name) and e.func.value.id in subs \
                            and e.args and isinstance(e.args[0], ast.Constant):
                        parent = subs[e.func.value.id]
                        kw = {k.arg: k.value for k in e.keywords if k.arg}
                        h = kw.get("help")
                        word = e.args[0].value
                        path = parent["data"]["path"] + [word]
                        prog = parent["data"]["program"]
                        c = self.add_node("command", f"{prog} {' '.join(path)}",
                                          f"{self.module}@{prog} {' '.join(path)}", self.span(e),
                                          {"program": prog, "path": path,
                                           "help": h.value if isinstance(h, ast.Constant) else None, "options": []},
                                          parent["id"])
                        made[id(e)] = c
                        return c
                elif isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "ArgumentParser" \
                        and self.imports_from.get("ArgumentParser") == "argparse.ArgumentParser":
                    return made.get(id(e)) or make_program(e)
                return None

            def make_program(e):
                kw = {k.arg: k.value for k in e.keywords if k.arg}
                p = kw.get("prog")
                prog = p.value if isinstance(p, ast.Constant) and isinstance(p.value, str) else self.module.split(".")[-1]
                h = kw.get("description")
                c = self.add_node("command", prog, f"{self.module}@{prog}", self.span(e),
                                  {"program": prog, "path": [], "help": h.value if isinstance(h, ast.Constant) else None,
                                   "options": []}, self.file_id)
                made[id(e)] = c
                return c

            ordered = sorted(own, key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
            for n in ordered:
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                    v, name = n.value, n.targets[0].id
                    if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute) and v.func.attr == "add_subparsers":
                        parent = cmd_of(v.func.value)
                        if parent:
                            subs[name] = parent
                            continue
                    c = cmd_of(v)
                    if c:
                        parsers[name] = c
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                    if n.func.attr in ("add_argument", "set_defaults"):
                        c = cmd_of(n.func.value)
                        if not c:
                            continue
                        if n.func.attr == "add_argument":
                            c["data"]["options"] += [a.value for a in n.args
                                                     if isinstance(a, ast.Constant) and isinstance(a.value, str)]
                        else:
                            for k in n.keywords:
                                if k.arg == "func" and dotted(k.value):
                                    self.ref(c["id"], dotted(k.value), "handles", k.value.lineno, k.value.col_offset)
                    elif n.func.attr == "add_parser":
                        cmd_of(n)

    # ---------- pass 2: calls, references, bindings, returns ----------
    def fn_locals(self, fn):
        names = set()
        a = fn.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
            names.add(arg.arg)
        stack = list(fn.body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(n.name)
                continue
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                names.add(n.id)
            if isinstance(n, ast.arg):
                names.add(n.arg)
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for al in n.names:
                    names.add((al.asname or al.name).split(".")[0])
            stack.extend(ast.iter_child_nodes(n))
        return names

    def value_refs(self, e, owner, locs, skip=()):
        """`references` for names used as values inside e (calls handle their own arguments)."""
        if e is None or id(e) in skip:
            return
        d = dotted(e)
        if d:
            root = d.split(".")[0]
            if (locs and root in locs) or root in BUILTIN_NAMES:
                return
            self.ref(owner["id"], d, "references", e.lineno, e.col_offset)
            return
        if isinstance(e, (ast.List, ast.Tuple, ast.Set)):
            for x in e.elts:
                self.value_refs(x, owner, locs, skip)
        elif isinstance(e, ast.Dict):
            for x in e.values:
                self.value_refs(x, owner, locs, skip)
        elif isinstance(e, ast.JoinedStr):
            for v in e.values:
                if isinstance(v, ast.FormattedValue):
                    self.value_refs(v.value, owner, locs, skip)
        elif isinstance(e, ast.BinOp):
            self.value_refs(e.left, owner, locs, skip)
            self.value_refs(e.right, owner, locs, skip)
        elif isinstance(e, (ast.Starred, ast.Await)):
            self.value_refs(e.value, owner, locs, skip)
        elif isinstance(e, ast.Subscript):
            self.value_refs(e.value, owner, locs, skip)
        elif isinstance(e, ast.IfExp):
            self.value_refs(e.body, owner, locs, skip)
            self.value_refs(e.orelse, owner, locs, skip)

    def profile_consumed(self, call):
        """Argument nodes a profile reference already covers (no extra `references`)."""
        out = set()
        f = call.func
        last = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if last in HTTP_METHODS | {"api_route"}:  # a route decorator: response_model is the Route's `returns`
            out |= {id(k.value) for k in call.keywords if k.arg == "response_model"}
        if last in ("Depends", "Security") and call.args:
            out.add(id(call.args[0]))
        if last == "include_router" and call.args:
            out.add(id(call.args[0]))
        # set_defaults(func=f) also gives References to f (python-parsing: plain binary callbacks)
        return out

    def do_call(self, call, owner, locs):
        line, col = self.call_site_pos(call)
        callee = self.src(call.func)
        self.ref(owner["id"], callee, "calls", line, col)
        args, pos = [], 0
        for a in call.args:
            args.append({"slot": {"position": pos}, "shape": shape(a)})
            pos += 1
        for k in call.keywords:
            args.append({"slot": {"keyword": k.arg if k.arg else "**"},
                         "shape": shape(k.value) if k.arg else (
                             {"type": "spread", "name": dotted(k.value)} if dotted(k.value) else {"type": "other"})})
        OUT["call_sites"].append({"from": owner["id"], "site": self.site(line, col), "callee": callee, "arguments": args})
        skip = self.profile_consumed(call)
        for a in call.args:
            self.value_refs(a, owner, locs, skip)
        for k in call.keywords:
            self.value_refs(k.value, owner, locs, skip)
        # FastAPI: app.include_router(x, prefix=...)
        if isinstance(call.func, ast.Attribute) and call.func.attr == "include_router" and call.args \
                and isinstance(call.func.value, ast.Name) and dotted(call.args[0]):
            var = self.module_vars.get(call.func.value.id)
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            tags = [e.value for e in getattr(kw.get("tags"), "elts", []) if isinstance(e, ast.Constant)]
            src = var["id"] if var else owner["id"]
            a0 = call.args[0]
            self.ref(src, dotted(a0), "mounts", a0.lineno, a0.col_offset,
                     {"prefix": tmpl_from_expr(kw.get("prefix")), "tags": tags})

    def walk_expr(self, e, owner, locs):
        """Every call inside an expression (lambdas and comprehensions included)."""
        if e is None:
            return
        for n in ast.walk(e):
            if isinstance(n, ast.Call):
                self.do_call(n, owner, locs)

    def bind(self, within, name, e_site, shp):
        OUT["bindings"].append({"within": within["id"], "name": name, "site": self.site(*e_site), "shape": shp})

    def bind_target(self, t, value_shape, site, owner, cls, self_name, value=None):
        if isinstance(t, ast.Name):
            self.bind(owner, t.id, site, value_shape)
        elif isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and self_name and t.value.id == self_name \
                and cls is not None:
            self.bind(cls, t.attr, site, value_shape)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for i, el in enumerate(t.elts):
                if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(t.elts):
                    s = shape(value.elts[i])
                    sub_value = value.elts[i]
                elif value_shape.get("type") == "name":
                    s = {"type": "item", "name": value_shape["name"], "accessor": "index"}
                    sub_value = None
                elif value_shape.get("type") == "item":
                    s = {"type": "item", "name": value_shape["name"], "accessor": value_shape["accessor"]}
                    sub_value = None
                else:
                    s, sub_value = {"type": "other"}, None
                self.bind_target(el, s, site, owner, cls, self_name, sub_value)
        elif isinstance(t, ast.Starred):
            self.bind_target(t.value, {"type": "other"}, site, owner, cls, self_name)

    def walk_block(self, body, owner, fn_locals, cls, self_name=None):
        for st in body:
            self.walk_stmt(st, owner, fn_locals, cls, self_name)

    def walk_stmt(self, st, owner, locs, cls, self_name):
        W = lambda e: self.walk_expr(e, owner, locs)
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rec = self.ast_owner[id(st)]
            for d in st.decorator_list:
                W(d)  # decorator calls run in the enclosing scope
            a = st.args
            for dflt in list(a.defaults) + [x for x in a.kw_defaults if x is not None]:
                self.walk_expr(dflt, rec, locs)
                self.value_refs(dflt, rec, locs, skip=self.profile_consumed(dflt) if isinstance(dflt, ast.Call) else ())
            new_locs = self.fn_locals(st) | (locs or set())
            pos = a.posonlyargs + a.args
            sname = pos[0].arg if rec["kind"] == "method" and pos and not rec["data"]["is_static"] else None
            self.walk_block(st.body, rec, new_locs, rec.get("_class"), sname)
            # returns
            for n in self.own_nodes(st):
                if isinstance(n, ast.Return):
                    OUT["returns"].append({"within": rec["id"], "site": self.site(n.lineno, n.col_offset),
                                           "shape": shape(n.value)})
            if ends_without_return(st.body):
                last = st.body[-1]
                OUT["returns"].append({"within": rec["id"], "site": self.site(last.end_lineno, last.col_offset),
                                       "shape": {"type": "literal", "kind": "null"}})
            return
        if isinstance(st, ast.ClassDef):
            rec = self.ast_owner[id(st)]
            for d in st.decorator_list:
                W(d)
            for b in st.bases:
                W(b)
            self.walk_block(st.body, rec, None, rec, None)
            return
        if isinstance(st, ast.Assign):
            W(st.value)
            self.value_refs(st.value, owner, locs)
            site = self.expr_site(st.value)
            for t in st.targets:
                self.bind_target(t, shape(st.value), site, owner, cls, self_name, st.value)
                self.walk_target(t, owner, locs)
            return
        if isinstance(st, ast.AnnAssign):
            W(st.value)
            if st.value is not None:
                self.value_refs(st.value, owner, locs)
                self.bind_target(st.target, shape(st.value), self.expr_site(st.value), owner, cls, self_name, st.value)
            self.walk_target(st.target, owner, locs)
            return
        if isinstance(st, ast.AugAssign):
            W(st.value)
            self.value_refs(st.value, owner, locs)
            self.bind_target(st.target, {"type": "other"}, self.expr_site(st.value), owner, cls, self_name)
            return
        if isinstance(st, (ast.For, ast.AsyncFor)):
            W(st.iter)
            self.value_refs(st.iter, owner, locs)
            self.bind_target(st.target, iter_shape(st.iter), (st.target.lineno, st.target.col_offset), owner, cls,
                             self_name)
            self.walk_block(st.body, owner, locs, cls, self_name)
            self.walk_block(st.orelse, owner, locs, cls, self_name)
            return
        if isinstance(st, (ast.With, ast.AsyncWith)):
            for item in st.items:
                W(item.context_expr)
                if item.optional_vars is not None:
                    self.value_refs(item.context_expr, owner, locs)
                    self.bind_target(item.optional_vars, shape(item.context_expr), self.expr_site(item.context_expr),
                                     owner, cls, self_name, item.context_expr)
            self.walk_block(st.body, owner, locs, cls, self_name)
            return
        if isinstance(st, ast.Return):
            W(st.value)
            self.value_refs(st.value, owner, locs)
            return
        if isinstance(st, ast.Expr) and isinstance(st.value, (ast.Yield, ast.YieldFrom)):
            W(st.value)
            self.value_refs(st.value.value, owner, locs)
            return
        # any other statement: calls in its expressions, recurse into blocks
        for field, val in ast.iter_fields(st):
            vals = val if isinstance(val, list) else [val]
            for v in vals:
                if isinstance(v, ast.stmt):
                    self.walk_stmt(v, owner, locs, cls, self_name)
                elif isinstance(v, ast.expr):
                    W(v)
                elif isinstance(v, ast.excepthandler):
                    W(v.type)
                    self.walk_block(v.body, owner, locs, cls, self_name)
                elif isinstance(v, ast.match_case):
                    self.walk_block(v.body, owner, locs, cls, self_name)
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.NamedExpr):
            ne = st.value
            self.bind_target(ne.target, shape(ne.value), self.expr_site(ne.value), owner, cls, self_name, ne.value)

    def walk_target(self, t, owner, locs):
        """Calls inside a target, e.g. `x[f()] = ...`."""
        for n in ast.walk(t):
            if isinstance(n, ast.Call):
                self.do_call(n, owner, locs)

    @staticmethod
    def own_nodes(fn):
        out, stack = [], list(fn.body)
        while stack:
            n = stack.pop()
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            out.append(n)
            stack.extend(ast.iter_child_nodes(n))
        return out


def main():
    for pid in PROJECTS:
        proot = os.path.join(ROOT, "src", pid)
        files = []
        for dp, dns, fns in os.walk(proot):
            dns[:] = sorted(d for d in dns if d not in ("__pycache__", ".venv", "venv", ".git"))
            for fn in fns:
                if fn.endswith(".py"):
                    files.append(os.path.relpath(os.path.join(dp, fn), proot).replace(os.sep, "/"))
        for path in sorted(files):
            raw = open(os.path.join(proot, path), "rb").read()
            text = raw.decode("utf-8")
            r = FileReader(pid, path, text)
            r.read()
            for n in r.nodes:
                n.pop("_ast", None)
                n.pop("_class", None)
            OUT["nodes"].extend(r.nodes)
            OUT["files"].append({"project": pid, "path": path, "content_hash": content_hash(raw), "size": len(raw),
                                 "mtime": MTIME_NS, "language": "python", "status": {"type": "parsed"}})

    # ---- self-check ----
    ids = [n["id"] for n in OUT["nodes"]]
    assert len(ids) == len(set(ids)), "duplicate node ids"
    parents = {}
    for e in OUT["edges"]:
        if e["kind"] == "contains":
            assert e["target"] not in parents, f"two parents for {e['target']}"
            parents[e["target"]] = e["source"]
    by_id = {n["id"]: n for n in OUT["nodes"]}
    for n in OUT["nodes"]:
        if n["kind"] == "file":
            assert parents[n["id"]] == project_node_id(n["scope"]["name"])
            continue
        cur, seen = n["id"], set()
        while by_id[cur]["kind"] != "file":
            assert cur not in seen and cur in parents, f"not below a file: {n['qualified_name']}"
            seen.add(cur)
            cur = parents[cur]
    rids = [r["id"] for r in OUT["references"]]
    assert len(rids) == len(set(rids)), "duplicate reference ids"
    for r in OUT["references"]:
        assert r["from"] in by_id
    cs = [(c["from"], c["site"]["line"], c["site"]["column"]) for c in OUT["call_sites"]]
    assert len(cs) == len(set(cs)), "C3 violated"
    bs = [(b["within"], b["name"], b["site"]["line"], b["site"]["column"]) for b in OUT["bindings"]]
    assert len(bs) == len(set(bs)), "L3 violated"
    rs = [(b["within"], b["site"]["line"], b["site"]["column"]) for b in OUT["returns"]]
    assert len(rs) == len(set(rs)), "B2 violated"

    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out", "stage1.json"), "w") as f:
        json.dump(OUT, f, indent=1)
        f.write("\n")
    print("nodes:", dict(Counter(n["kind"] for n in OUT["nodes"])))
    print("edges:", dict(Counter(e["kind"] for e in OUT["edges"])))
    print("references:", dict(Counter(r["kind"] for r in OUT["references"])))
    print("records:", {k: len(v) for k, v in OUT.items()})


if __name__ == "__main__":
    main()
