"""rules.json, held to what the Firebase console will actually accept.

The real rules suite (rules_suite / rules_test.js) exercises the rules
against firebase's own test module, which not every container carries -
it reports NO RESULT here. That gap shipped a rule the console refused
on 11 Sep: a .matches() pattern of the shape /^A$|^B$/, legal regex
everywhere except Firebase's rules engine, which allows ^ only at the
very start and $ only at the very end of a pattern. The owner met it as
a red banner mid-paste.

This lint needs nothing but Python, so it runs in EVERY container: the
file parses, and every .matches(/.../)  pattern obeys the console's own
regex law. It cannot prove the rules do the right thing - only the real
suite can - but it proves the console will swallow the paste, which is
the failure that actually reached a person.
"""
import json, os, re, sys

os.chdir('/home/claude/nala')

P = F = 0
def ck(name, cond, detail=None):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or detail is None
          else " :: " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── the file parses ─────────────────────────────────────────────────
try:
    RULES = json.load(open("rules.json"))
    ck("rules.json parses as JSON", True)
except Exception as e:
    ck("rules.json parses as JSON", False, e)
    print("RESULT: %d passed, %d failed" % (P, F))
    sys.exit(1)

# ── every .matches() pattern obeys the console's regex law ──────────
#  Walk every string in the tree and pull each /.../  out of .matches().
#  The console's engine allows ^ only as the first character and $ only
#  as the last (backslash-escaped ones excepted), and its patterns are
#  house-anchored: every one starts ^ and ends $, because an unanchored
#  match is a substring match nobody here ever means.
pats = []
def walk(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, path + "/" + k)
    elif isinstance(node, str):
        for m in re.finditer(r"\.matches\(/((?:[^/\\]|\\.)*)/\)", node):
            pats.append((path, m.group(1)))
walk(RULES, "")
ck("the rules hold .matches() patterns to check at all", len(pats) > 0,
   len(pats))

def unescaped(pat, ch):
    """positions of ch in pat that are not backslash-escaped"""
    out, i = [], 0
    while i < len(pat):
        if pat[i] == "\\": i += 2; continue
        if pat[i] == ch: out.append(i)
        i += 1
    return out

bad = []
for path, pat in pats:
    carets = unescaped(pat, "^")
    dollars = unescaped(pat, "$")
    #  a ^ anywhere but position 0 is the console's red banner - the
    #  /^A$|^B$/ shape included. A ^ inside [^...] is fine, but nothing
    #  in this file uses negated classes; if one ever does, teach this
    #  lint rather than loosen it blind.
    if any(i != 0 for i in carets): bad.append((path, pat, "^ not at start"))
    if any(i != len(pat) - 1 for i in dollars): bad.append((path, pat, "$ not at end"))
    if 0 not in carets: bad.append((path, pat, "unanchored start"))
    if len(pat) - 1 not in dollars: bad.append((path, pat, "unanchored end"))
    try:
        re.compile(pat)
    except re.error as e:
        bad.append((path, pat, "does not compile: %s" % e))
ck("every pattern obeys the console's regex law (^ first, $ last)",
   not bad, bad)

print("RESULT: %d passed, %d failed" % (P, F))
sys.exit(1 if F else 0)
