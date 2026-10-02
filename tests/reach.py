"""How far a change can reach, and so which suites a publish needs.

The owner, 2 Oct: "I don't mind the 25 mins, but even if it's fixing a bug on
a sticky button, it runs it. What about a check on appropriateness". The full
run was the rule before every publish (rule 4), and --changed sent a change
to any shared file to everything: nala-shared.js and the two style sheets hold
most fixes, and their ?v= bump touches all 26 pages besides. So a hover
colour cost the same 25 minutes as a new module.

This reads what a change touches and sizes the run to it:

  - a page whose only change is a ?v= bump changes nothing a suite can see;
  - a page, or any file run.py's COVERS names, takes the suites named there;
  - a style sheet is read rule by rule. A rule whose changed properties only
    paint (colour, background, shadow, outline, radius) reaches the pages
    that use its selector for their suites without the sweeps, which test
    layout and reach; one that changes anything else reaches those pages'
    suites whole. colour, paper and pages run for any sheet, because they
    read the sheets themselves. A selector naming no class, id or attribute
    - button, body, :root - styles every page: a layout change there, or
    through a token such a rule uses, runs everything. A rule moved past
    another counts as changed, since which of the two wins has;
  - nala-shared.js is read as its top-level pieces (reach_js.js). A changed
    function reaches whatever refers to it, and so on outwards. If that ever
    reaches code that runs as a page loads - buildNav(), the menu filter, an
    IIFE - it reaches every page and everything runs, as does load-time
    code changing places. Otherwise it is the suites of the pages that call
    it, and of the suites that name it;
  - auth.js, the sign in, is everything, always;
  - anything else is run.py's covered_by: COVERS, the Workers, the suites
    that open a file by name (a table, a helper, a mock), and everything for
    a page or a script the pages load that none of those places.

It cannot know what a change means, only where it can land, and it rounds
every doubt up: when it cannot tell, everything runs. The heavy tier (rule
6: the data model, permissions, a new module) still takes the full run
before it goes live; this is for everything else.
"""
import difflib
import json
import os
import re
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_JS = "nala-shared.js"
SHEETS = ("nala-ui.css", "nala-ui2.css")
SIGN_IN = ("auth.js",)
# Read with the page that loads them, as part of its source.
PAGE_SCRIPTS = ("nala-shared.js", "auth.js", "nala-cards.js", "contact-demo.js")
# The suites that read the style sheets themselves, and the shared files'
# version check: any sheet change runs them.
SHEET_SUITES = ("colour", "paper", "pages")
# Properties that change how a thing is painted and never where it sits, how
# big it is, or whether it can be reached. Anything not here counts as layout.
PAINT = {
    "color", "background", "background-color", "background-image",
    "border-color", "border-top-color", "border-right-color",
    "border-bottom-color", "border-left-color", "border-radius",
    "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
    "outline", "outline-color", "outline-offset", "box-shadow", "text-shadow",
    "fill", "stroke", "caret-color", "accent-color", "text-decoration-color",
    "-webkit-tap-highlight-color", "cursor",
}
VERSION = re.compile(r"\?v=\d+")


class Plan:
    def __init__(self):
        self.everything = False
        self.suites = set()
        self.why = []

    def all(self, reason):
        self.everything = True
        self.why.append(reason)

    def add(self, suites, reason):
        self.suites.update(suites)
        self.why.append(reason)


# ── git ──────────────────────────────────────────────────────────────
def _git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True)


def base_ref():
    """Where this branch left main: only its own changes are being published."""
    mb = _git("merge-base", "HEAD", "origin/main").stdout.strip()
    return mb or "origin/main"


def _show(ref, path):
    r = _git("show", "%s:%s" % (ref, path))
    return r.stdout if r.returncode == 0 else None


def _read(path):
    try:
        return open(os.path.join(ROOT, path), encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return None


def changed_files(base, head=None):
    """(path, before, after) for every file that differs. head None is the
    working tree, untracked files included."""
    if head is None:
        names = _git("diff", "--no-renames", "--name-only", base).stdout.split()
        names += _git("ls-files", "--others", "--exclude-standard").stdout.split()
    else:
        names = _git("diff", "--no-renames", "--name-only", base, head).stdout.split()
    return [(p, _show(base, p), _show(head, p) if head else _read(p))
            for p in sorted(set(names))]


def version_only(before, after):
    return (before is not None and after is not None and before != after
            and VERSION.sub("?v=", before) == VERSION.sub("?v=", after))


# ── the pages, as the head side has them ─────────────────────────────
def page_index(read, names):
    """page -> {"text": its source and the local scripts it loads, "sheets": the
    sheets it links, "own": its source alone}."""
    out = {}
    for p in names:
        own = read(p) or ""
        text = own
        for s in PAGE_SCRIPTS:
            if re.search(r'src="%s' % re.escape(s), own):
                text += "\n" + (read(s) or "")
        sheets = [s for s in SHEETS if re.search(r'href="%s' % re.escape(s), own)]
        out[p] = {"text": text, "own": own, "sheets": sheets}
    return out


def has_token(text, tok):
    """A class, id or attribute name present in a page's source. A name built
    in code from a prefix or a suffix - 'law-' + kind, st + '-form' - counts
    as present too."""
    if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(tok), text):
        return True
    for i, ch in enumerate(tok):
        if ch == "-" and i > 0 and (
                re.search(re.escape(tok[:i + 1]) + r"['\"`]", text) or
                re.search(r"['\"`]" + re.escape(tok[i:]) + r"(?![\w-])", text)):
            return True
    return False


# ── style sheets ─────────────────────────────────────────────────────
def _norm(s):
    return re.sub(r"\s+", " ", s).strip()


def _split_top(s, sep):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x for x in (y.strip() for y in out) if x]


def css_rules(text):
    """(context, selector) -> {property: value}. Context is the @media or
    @supports a rule sits in. A keyframes, font-face, page or property block
    is kept whole under the key "@..."."""
    text = re.sub(r"/\*.*?\*/", "", text or "", flags=re.S)
    rules = {}

    def parse(block, context):
        i, n = 0, len(block)
        while i < n:
            j = i
            while j < n and block[j] not in "{};":
                j += 1
            if j >= n:
                break
            prelude = _norm(block[i:j])
            if block[j] != "{":
                if block[j] == ";" and prelude:
                    rules[(context, "@stmt " + prelude)] = {"@": prelude}
                i = j + 1
                continue
            depth, k = 0, j
            while k < n:
                if block[k] == "{":
                    depth += 1
                elif block[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            body = block[j + 1:k]
            low = prelude.lower()
            if low.startswith(("@media", "@supports", "@container", "@layer")):
                parse(body, (context + " " + prelude).strip())
            elif low.startswith("@"):
                rules[(context, prelude)] = {"@": _norm(body)}
            else:
                decls = {}
                for d in _split_top(body, ";"):
                    if ":" in d:
                        prop, val = d.split(":", 1)
                        decls[prop.strip().lower()] = _norm(val)
                for sel in _split_top(prelude, ","):
                    rules.setdefault((context, _norm(sel)), {}).update(decls)
            i = k + 1

    parse(text, "")
    return rules


def selector_tokens(sel):
    """The classes, ids and attribute names a selector needs. What sits inside
    :not() is not needed, and :is()/:where() alternatives are not all needed,
    so every pseudo part is dropped with its brackets."""
    s = re.sub(r"::?[\w-]+(\((?:[^()]|\([^()]*\))*\))?", " ", sel)
    toks = re.findall(r"[.#]([\w-]+)", s) + re.findall(r"\[\s*([\w-]+)", s)
    return sorted(set(toks))


def sheet_plan(path, before, after, pages, covers, plan):
    plan.add(SHEET_SUITES, "%s: the sheets' own suites (%s)" % (path, ", ".join(SHEET_SUITES)))
    a, b = css_rules(before), css_rules(after)
    users = {p: i for p, i in pages.items() if path in i["sheets"]}
    changes = []
    for key in sorted(set(a) | set(b)):
        da, db = a.get(key, {}), b.get(key, {})
        if da != db:
            changes.append((key, {p for p in set(da) | set(db) if da.get(p) != db.get(p)}))
    # A rule moved past another changes which of the two wins where both
    # apply, with not a character of either changed: the moved rule counts
    # as changed, every property of it.
    common = [k for k in a if k in b]
    order_b = [k for k in b if k in a]
    sm = difflib.SequenceMatcher(None, common, order_b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != "equal":
            for key in common[i1:i2] + order_b[j1:j2]:
                changes.append((key, set(a[key]) | set(b[key])))

    # A token reaches every declaration that uses it, through other tokens too.
    work = [(key, p) for key, props in changes for p in props if p.startswith("--")]
    seen = set()
    while work:
        key, tok = work.pop()
        if tok in seen:
            continue
        seen.add(tok)
        for rules in (a, b):
            for k2, decls in rules.items():
                for p2, v in decls.items():
                    if "var(%s)" % tok in v.replace(" ", "") or "var(%s," % tok in v.replace(" ", ""):
                        if p2.startswith("--"):
                            work.append((k2, p2))
                        else:
                            changes.append((k2, {p2}))
        # A page's own source, or a script it loads, naming the token: an
        # inline style, a built string (nala-cards.js), a property set in code.
        inline = [p for p, i in users.items() if tok in i["text"]]
        if inline:
            plan.add(_page_suites(inline, covers, plan, layout=True),
                     "%s: token %s is used in the source of %s" % (path, tok, ", ".join(inline)))

    for (context, sel), props in changes:
        props = {p for p in props if not p.startswith("--")}
        if not props:
            continue
        where = (" in " + context) if context else ""
        if sel.startswith("@"):
            plan.all("%s: %s%s changed, and reaches every page" % (path, sel.split(" ")[0], where))
            continue
        layout = sorted(p for p in props if p not in PAINT)
        toks = selector_tokens(sel)
        if not toks:
            if layout:
                plan.all("%s: %s%s moves %s, and styles every page"
                         % (path, sel, where, ", ".join(layout)))
                continue
            hit = sorted(users)
        else:
            hit = sorted(p for p, i in users.items() if all(has_token(i["text"], t) for t in toks))
        kind = ("layout (%s)" % ", ".join(layout)) if layout else "paint only"
        plan.add(_page_suites(hit, covers, plan, layout=bool(layout)),
                 "%s: %s%s, %s -> %s" % (path, sel, where, kind,
                                         ", ".join(hit) if hit else "no page uses it"))


def _page_suites(pages, covers, plan, layout):
    out = set()
    for p in pages:
        if p not in covers:
            plan.all("%s has no suites in COVERS (tests/run.py), so everything runs" % p)
            continue
        out.update(s for s in covers[p] if layout or not s.startswith("sweep:"))
    return out


# ── nala-shared.js ───────────────────────────────────────────────────
def js_units(text):
    """None when the pieces cannot be read, no node included: everything runs."""
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "reach_js.js")],
                           input=text or "", capture_output=True, text=True, cwd=ROOT)
        d = json.loads(r.stdout)
    except (OSError, ValueError):
        return None
    return None if "error" in d else d["units"]


def shared_js_plan(path, before, after, pages, suites, covers, read, plan):
    ua, ub = js_units(before), js_units(after)
    if ua is None or ub is None:
        plan.all("%s: could not be read as its pieces (is esprima installed? the "
                 "session hook installs it), so everything runs" % path)
        return

    def key(u):
        return ("stmt", u["hash"]) if u["kind"] == "stmt" else (u["kind"], tuple(u["names"]))
    # Grouped, not keyed: a name declared twice, or one statement written
    # twice, is two pieces, and either can change.
    ga, gb = defaultdict(list), defaultdict(list)
    for u in ua:
        ga[key(u)].append(u)
    for u in ub:
        gb[key(u)].append(u)
    # Everything but a function runs in the order it is written: two vars or
    # statements trading places can change what a page loads with, and not a
    # character of either changed.
    ka = [key(u) for u in ua if u["kind"] != "function" and key(u) in gb]
    kb = [key(u) for u in ub if u["kind"] != "function" and key(u) in ga]
    if ka != kb:
        plan.all("%s: the order of the code that runs as every page loads changed" % path)
        return
    changed = set()
    for k in sorted(set(ga) | set(gb), key=str):
        xs, ys = ga.get(k, []), gb.get(k, [])
        if [u["hash"] for u in xs] == [u["hash"] for u in ys]:
            continue
        if k[0] == "stmt":
            plan.all("%s: code that runs as every page loads changed (%s...)"
                     % (path, (xs or ys)[0]["head"][:40]))
            return
        if any(u["atLoad"] for u in xs + ys):
            plan.all("%s: %s changed, and it runs as every page loads" % (path, ", ".join(k[1])))
            return
        changed.update(k[1])
    if not changed:
        plan.add({"pages"}, "%s: no piece changed but its text (comments, spacing)" % path)
        return

    units = ua + ub
    declared = {n for u in units for n in u["names"]}
    referers = defaultdict(list)
    for u in units:
        for r in u["refs"]:
            if r in declared:
                referers[r].append(u)
    closure, queue = set(changed), list(changed)
    while queue:
        n = queue.pop()
        for u in referers.get(n, []):
            if u["atLoad"]:
                plan.all("%s: %s reaches %s, which runs as every page loads"
                         % (path, n, u["head"][:40] if u["kind"] == "stmt"
                            else "var " + ", ".join(u["names"])))
                return
            for m in u["names"]:
                if m not in closure:
                    closure.add(m)
                    queue.append(m)

    word = re.compile(r"(?<![\w$])(%s)(?![\w$])" % "|".join(sorted(map(re.escape, closure))))
    callers = sorted(p for p, i in pages.items() if word.search(i["own"]))
    for f in PAGE_SCRIPTS:
        if f != path and word.search(read(f) or ""):
            if f in SIGN_IN:
                plan.all("%s: %s is used by %s, the sign in" % (path, ", ".join(sorted(changed)), f))
                return
            plan.add(covers.get(f, []), "%s: %s is used by %s" % (path, ", ".join(sorted(changed)), f))
    named = set()
    for name, cmd, _ in suites:
        for c in cmd:
            if c.startswith(("tests/", "worker/")) and word.search(read(c) or ""):
                named.add(name)
    plan.add(_page_suites(callers, covers, plan, layout=True) | named | {"pages"},
             "%s: %s -> %s%s" % (path, ", ".join(sorted(changed)),
                                 ", ".join(callers) if callers else "no page calls it",
                                 ("; named in " + ", ".join(sorted(named))) if named else ""))


# ── the plan ─────────────────────────────────────────────────────────
def plan(suites, covers, covered_by, base=None, head=None):
    """What a publish of base..head (head None: the working tree) needs to run."""
    base = base or base_ref()
    read = (lambda p: _show(head, p)) if head else _read
    pl = Plan()
    files = changed_files(base, head)
    if not files:
        pl.why.append("nothing differs from %s" % base[:8])
        return pl
    live = sorted({p for p in covers if p.endswith(".html")})
    pages = page_index(read, live)
    for path, before, after in files:
        if path.endswith(".html") and version_only(before, after):
            pl.why.append("%s: its ?v= bump only" % path)
        elif path in SIGN_IN:
            pl.all("%s is the sign in, so everything runs" % path)
        elif path in SHEETS:
            sheet_plan(path, before, after, pages, covers, pl)
        elif path == SHARED_JS:
            shared_js_plan(path, before, after, pages, suites, covers, read, pl)
        else:
            # run.py's answer: COVERS, the Workers, the suites that read a
            # file by name, and everything for a page or script it cannot place.
            got, reason = covered_by(path)
            if got is None:
                pl.all(reason)
            elif got:
                pl.add(got, reason)
            else:
                pl.why.append("%s: no suite reads it" % path)
    return pl
