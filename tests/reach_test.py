"""The appropriateness check's own cases: what a publish must run.

tests/reach.py sizes the run before a publish to what a change can reach
(rule 4). A check that runs too little is worse than the full run it
replaced, so these are the cases it must get right, each on three made-up
pages whose answer is known, and then the real commits of 2 Oct where the
clone holds them.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reach

P = F = 0
def ck(name, cond, detail=None):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or detail is None else "  -> %s" % (detail,)))
    if cond: P += 1
    else: F += 1

S = set(reach.SHEET_SUITES)
COVERS = {"a.html": ["sa", "sweep:a"], "b.html": ["sb", "sweep:b"], "c.html": ["sc", "sweep:c"]}
# a: its own class, the shared card, classes built in code from a prefix and
#    from a suffix, and a script it loads that sets a token in a built string.
# b: its own class, the card, and a token used in an inline style.
# c: loads only the older sheet.
A = ('<div class="only-a card"></div>'
     '<script>var cls = \'law-\' + kind, tint = st + \'-form\';</script>')
A_LOADS = "function chip(){ return '<i style=\"padding:var(--scripted)\">'; }"
B = '<div class="only-b card" style="color:var(--inline)"></div>'
C = '<div class="only-c card"></div>'
IDX = {"a.html": {"own": A, "text": A + "\n" + A_LOADS, "sheets": ["nala-ui2.css"]},
       "b.html": {"own": B, "text": B, "sheets": ["nala-ui2.css"]},
       "c.html": {"own": C, "text": C, "sheets": ["nala-ui.css"]}}

def sheet(before, after, covers=COVERS):
    pl = reach.Plan()
    reach.sheet_plan("nala-ui2.css", before, after, IDX, covers, pl)
    return pl

def runs(pl, want):
    return (not pl.everything) and pl.suites == set(want)

# ── style sheets ─────────────────────────────────────────────────────
pl = sheet(".only-a{color:red}", ".only-a{color:blue}")
ck("a colour change on one page's class runs that page's suites, without its sweep",
   runs(pl, S | {"sa"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".only-a{position:static}", ".only-a{position:sticky}")
ck("a layout change on one page's class - a sticky button - runs that page's suites whole",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet("button{padding:1px}", "button{padding:2px}")
ck("a layout change to every button runs everything", pl.everything, pl.why)
pl = sheet("button{color:red}", "button{color:blue}")
ck("a colour change to every button runs every page's suites but no sweep",
   runs(pl, S | {"sa", "sb"}), (pl.everything, sorted(pl.suites)))
pl = sheet(":root{--t:red}.only-b{color:var(--t)}", ":root{--t:blue}.only-b{color:var(--t)}")
ck("a colour token reaches the pages whose rules use it, as paint",
   runs(pl, S | {"sb"}), (pl.everything, sorted(pl.suites)))
pl = sheet(":root{--g:1px}.only-b{padding:var(--g)}", ":root{--g:2px}.only-b{padding:var(--g)}")
ck("a spacing token reaches the pages whose rules use it, as layout",
   runs(pl, S | {"sb", "sweep:b"}), (pl.everything, sorted(pl.suites)))
pl = sheet(":root{--g:1px}button{padding:var(--g)}", ":root{--g:2px}button{padding:var(--g)}")
ck("a token that sizes every button runs everything", pl.everything, pl.why)
pl = sheet(":root{--h:1px}:root{--g:var(--h)}.only-a{margin:var(--g)}",
           ":root{--h:2px}:root{--g:var(--h)}.only-a{margin:var(--g)}")
ck("a token reaches through another token", runs(pl, S | {"sa", "sweep:a"}),
   (pl.everything, sorted(pl.suites)))
pl = sheet(":root{--inline:red}", ":root{--inline:blue}")
ck("a token a page uses in its own source reaches that page",
   runs(pl, S | {"sb", "sweep:b"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".only-a:not(.only-b){padding:1px}", ".only-a:not(.only-b){padding:2px}")
ck("what sits inside :not() is not needed by the page",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".law-green{padding:1px}", ".law-green{padding:2px}")
ck("a class built in code from its prefix still finds its page",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".done-form{padding:1px}", ".done-form{padding:2px}")
ck("and one built from its suffix, as the desk's st + '-form' is",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet(":root{--scripted:1px}", ":root{--scripted:2px}")
ck("a token named in a script the page loads reaches that page",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".only-a{transition:none}", ".only-a{transition:transform .2s}")
ck("a transition counts as layout: it moves things over time",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet(".only-a{padding:1px}.only-b{color:red}.card{color:blue}",
           ".only-b{color:red}.card{color:blue}.only-a{padding:1px}")
ck("a rule moved past others, not a character of it changed, reaches its page",
   runs(pl, S | {"sa", "sweep:a"}), (pl.everything, sorted(pl.suites)))
pl = sheet("@media (max-width:400px){.only-a{padding:1px}}",
           "@media (max-width:400px){.only-a{padding:2px}}")
ck("a rule inside @media reaches its page, and says where it sat",
   runs(pl, S | {"sa", "sweep:a"}) and any("@media" in w for w in pl.why), pl.why)
pl = sheet(".only-a, .only-b{color:red}", ".only-a, .only-b{color:blue}")
ck("a grouped selector reaches each of its pages",
   runs(pl, S | {"sa", "sb"}), (pl.everything, sorted(pl.suites)))
pl = sheet("", ".only-a{margin:1px}")
ck("a new rule counts as a change", runs(pl, S | {"sa", "sweep:a"}),
   (pl.everything, sorted(pl.suites)))
pl = sheet(".only-c{padding:1px}", ".only-c{padding:2px}")
ck("a rule no page that loads the sheet uses runs only the sheets' own suites",
   runs(pl, S), (pl.everything, sorted(pl.suites)))
pl = sheet("@keyframes spin{from{opacity:0}to{opacity:1}}",
           "@keyframes spin{from{opacity:0}to{opacity:.5}}")
ck("a keyframes change runs everything", pl.everything, pl.why)
pl = sheet(".only-b{padding:1px}", ".only-b{padding:2px}",
           covers={k: v for k, v in COVERS.items() if k != "b.html"})
ck("a page with no suites in COVERS makes it everything", pl.everything, pl.why)
pl = sheet(".only-a{color:red;padding:1px}", ".only-a{color:red;padding:1px}")
ck("an unchanged sheet reaches no page", runs(pl, S), (pl.everything, sorted(pl.suites)))

# ── nala-shared.js ───────────────────────────────────────────────────
JIDX = {"a.html": {"own": "<script>helperA();</script>", "sheets": []},
        "b.html": {"own": "<button onclick=\"helperB()\">", "sheets": []},
        "c.html": {"own": "<script>draw();</script>", "sheets": []}}
JSUITES = [("named", ["python3", "tests/fake_suite.py"], 1)]
FILES = {"tests/fake_suite.py": "assert helperC() == 3"}
def shared(before, after):
    pl = reach.Plan()
    reach.shared_js_plan("nala-shared.js", before, after, JIDX, JSUITES, COVERS,
                         lambda f: FILES.get(f, ""), pl)
    return pl

LIB = ("function helperA(){ return 1; }\n"
       "function helperB(){ return helperA() + 1; }\n"
       "function helperC(){ return 3; }\n"
       "function draw(){ return '<b onclick=\"helperD()\">'; }\n"
       "function helperD(){ return 4; }\n")
pl = shared(LIB, LIB.replace("return 1;", "return 10;"))
ck("a changed helper reaches the pages that call it and those calling its callers",
   runs(pl, {"sa", "sweep:a", "sb", "sweep:b", "pages"}), (pl.everything, sorted(pl.suites)))
pl = shared(LIB, LIB.replace("return 4;", "return 40;"))
ck("a function called from a built string, an onclick, still reaches its page",
   runs(pl, {"sc", "sweep:c", "pages"}), (pl.everything, sorted(pl.suites)))
pl = shared(LIB, LIB.replace("return 3;", "return 30;"))
ck("a suite that names a changed function runs it", runs(pl, {"named", "pages"}),
   (pl.everything, sorted(pl.suites)))
pl = shared(LIB + "window.X = helperB;\n", LIB.replace("return 1;", "return 10;") + "window.X = helperB;\n")
ck("a helper that code run at page load reaches runs everything", pl.everything, pl.why)
pl = shared(LIB + "var T = (function(){ return helperB(); })();\n",
            LIB.replace("return 1;", "return 10;") + "var T = (function(){ return helperB(); })();\n")
ck("so does one a var set at page load calls", pl.everything, pl.why)
pl = shared(LIB + "buildIt();\n", LIB + "buildIt(1);\n")
ck("a changed statement that runs as every page loads runs everything", pl.everything, pl.why)
pl = shared(LIB + "var Z = 1;\nstart();\n", LIB + "start();\nvar Z = 1;\n")
ck("a var and a statement trading places runs everything", pl.everything, pl.why)
pl = shared(LIB + "tick();\ntick();\n", LIB + "tick();\n")
ck("one of two identical statements taken out runs everything", pl.everything, pl.why)
pl = shared(LIB + "function helperA(){ return 1; }\n",
            LIB.replace("return 1;", "return 10;") + "function helperA(){ return 1; }\n")
ck("a name declared twice is two pieces, and the first changing counts",
   runs(pl, {"sa", "sweep:a", "sb", "sweep:b", "pages"}), (pl.everything, sorted(pl.suites)))
pl = shared(LIB, "/* a note between pieces */\n" + LIB)
ck("a comment between pieces changes nothing but the version check",
   runs(pl, {"pages"}), (pl.everything, sorted(pl.suites)))
pl = shared(LIB, LIB + "function {")
ck("a file that cannot be read as its pieces runs everything", pl.everything, pl.why)

# ── the ?v= bump ─────────────────────────────────────────────────────
ck("a page whose only change is its ?v= bump is set aside",
   reach.version_only('<script src="nala-shared.js?v=111">', '<script src="nala-shared.js?v=112">'))
ck("but not one that changed anything else with it",
   not reach.version_only('<script src="x.js?v=1"><b>a</b>', '<script src="x.js?v=2"><b>b</b>'))
ck("and an unchanged page is not a version bump", not reach.version_only("<b>a</b>", "<b>a</b>"))

# ── the real commits of 2 Oct, where this clone holds them ───────────
import importlib.util
spec = importlib.util.spec_from_file_location("run", os.path.join(reach.ROOT, "tests", "run.py"))
run = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["run.py"]
spec.loader.exec_module(run)
sys.argv = argv
# ── files no rule above places: run.py's covered_by ──────────────────
got = run.covered_by("tests/phone_cases.json")[0]
ck("a shared table runs the suites that open it", got is not None and "invites" in got, got)
got = run.covered_by("tests/errortrap.py")[0]
ck("a helper runs the suites that import it",
   got is not None and {"tally", "frontdesk", "keys"} <= set(got), got)
got = run.covered_by("CLAUDE.md")[0]
ck("a file the suites mention only in their docstrings runs none", got == [], got)
got = run.covered_by("mock-keys-store.html")[0]
ck("a mock a suite holds its page to runs that suite", got == ["keys"], got)
got = run.covered_by("mock-paper.html")[0]
ck("a mock no suite opens runs nothing", got == [], got)
got = run.covered_by("raleway.js")[0]
ck("a script the pages load that nothing covers runs everything", got is None, got)

def real(c):
    if reach._git("cat-file", "-e", c + "~1").returncode != 0:
        print("   note: %s is not in this clone, its case skipped" % c)
        return None
    return reach.plan(run.SUITES, run.COVERS, run.covered_by, base=c + "~1", head=c)
pl = real("6e82aa9")
if pl is not None:
    ck("the menu counts' fix, in the menu filter every page runs, ran everything",
       pl.everything, pl.why)
pl = real("813bce6")
if pl is not None:
    ck("the bookings read ran the pages that read bookings and the rules, not everything",
       not pl.everything and {"tally", "cleans", "dash", "guest", "housekeep", "invites",
                               "list", "pub", "rules"} <= pl.suites
       and not ({"spa", "keys", "contact", "frontdesk"} & pl.suites), sorted(pl.suites))
pl = real("dcab9c8f")
if pl is not None:
    # It touched run.py too, whose choices this suite's cases hold.
    ck("rule 8, a rule, a suite and a line of run.py, ran those two suites alone",
       runs(pl, {"reads", "reach"}), (pl.everything, sorted(pl.suites)))

print("RESULT: %d passed, %d failed" % (P, F))
sys.exit(1 if F else 0)
