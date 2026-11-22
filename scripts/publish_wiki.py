#!/usr/bin/env python3
"""Render README.md and docs/**/*.md as flat GitHub wiki pages.

Usage: publish_wiki.py <repo-root> <output-dir>

Page names: README -> Home, docs/X.md -> X, docs/adrs/N-x.md -> ADR-N-x,
docs/implementation-plan/y.md -> Plan-y. Relative links between pages are
rewritten to wiki links; links to anything else go to the repo on `develop`.
"""
import os
import posixpath
import re
import sys

repo, out = sys.argv[1], sys.argv[2]
SLUG = os.environ.get("GITHUB_REPOSITORY", "Revanthshalon/semantic-workbench")
BASE = f"https://github.com/{SLUG}"
BRANCH = "develop"
TITLE_OVERRIDES = {"docs/GLOSSARY.md": "Glossary"}

files = ["README.md"] + sorted(
    os.path.relpath(os.path.join(d, f), repo)
    for d, _, fs in os.walk(os.path.join(repo, "docs"))
    for f in fs
    if f.endswith(".md")
)


def page(p):
    if p == "README.md":
        return "Home"
    n = p[len("docs/"):-3]
    if n.startswith("adrs/"):
        return "ADR-" + n[5:]
    if n.startswith("implementation-plan/"):
        return "Plan-" + n[len("implementation-plan/"):]
    return n


pages = {p: page(p) for p in files}
link = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")


def rewrite(src, text):
    def r(m):
        label, url = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#)", url):
            return m.group(0)
        path, _, anchor = url.partition("#")
        target = posixpath.normpath(posixpath.join(posixpath.dirname(src), path))
        a = "#" + anchor if anchor else ""
        if target in pages:
            return f"[{label}]({pages[target]}{a})"
        is_dir = path.endswith("/") or not os.path.splitext(target)[1]
        kind = "tree" if is_dir else "blob"
        return f"[{label}]({BASE}/{kind}/{BRANCH}/{target}{a})"

    return link.sub(r, text)


titles = {}
for p in files:
    text = open(os.path.join(repo, p), encoding="utf-8").read()
    titles[p] = TITLE_OVERRIDES.get(p) or next(
        (l[2:].strip() for l in text.splitlines() if l.startswith("# ")), pages[p]
    )
    with open(os.path.join(out, pages[p] + ".md"), "w", encoding="utf-8") as f:
        f.write(rewrite(p, text))


def section(name, ps):
    items = "\n".join(f"- [{titles[p]}]({pages[p]})" for p in ps)
    return f"**{name}**\n\n{items}\n\n"


adrs = [p for p in files if "/adrs/" in p]
plan = [p for p in files if "implementation-plan" in p]
rest = [p for p in files if p not in adrs + plan and p != "README.md"]
sidebar = (
    "[Home](Home)\n\n"
    + section("Design and reference", rest)
    + section("Decisions (ADRs)", adrs)
    + section("Implementation plan", plan)
)
with open(os.path.join(out, "_Sidebar.md"), "w", encoding="utf-8") as f:
    f.write(sidebar)
print(f"{len(files)} pages")
