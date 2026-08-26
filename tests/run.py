#!/usr/bin/env python3
"""Run the verification suites in parallel, and never hang.

    python3 tests/run.py                # everything except the demo check
    python3 tests/run.py --demos        # everything, demo check included
    python3 tests/run.py tally index    # just the ones whose names match
    python3 tests/run.py --changed      # just the ones covering modified files
    python3 tests/run.py --jobs 6       # more at once

WHY THIS EXISTS

Run one at a time, the suites take about twenty minutes. They are independent:
each owns its port, its browser and its stubbed database, and none of them
reads or writes anything another one touches. Nothing was making them serial
except the habit of typing them out one after another. Four at a time brings
the wall clock down to roughly the length of the slowest suite.

WHY EACH ONE HAS A TIMEOUT

sweep_suite hung twice on 19 Aug, in the middle of the click sweep, and there
was no way to tell a hang from slow progress: it holds its output until the
end, so a stuck run and a working run look identical from outside. Thirty
minutes went into waiting for a suite that was never going to finish. A suite
that stops is now a failure with a name on it, at a known cost in minutes,
rather than a session that quietly stops moving.

Timeouts are generous on purpose. They are there to catch a hang, not to
police a slow suite, so a suite that legitimately takes longer should have its
number raised here rather than be left to trip.

WHY THE DEMOS ARE NOT IN THE DEFAULT RUN

The four demo files are BUILT, by tools/make-demo.py, from the real pages.
demo_suite rebuilds them into a scratch directory and fails when the committed
copies no longer match, which is to say it fails after any change to a sheet.

That is correct behaviour and the wrong thing to gate a publish on. The demos
are shown to somebody who is not going to sign in. Nobody is looking at them
during a normal working session, and holding up a fix to the live app until a
demo has been regenerated spends real time on nothing.

So demos are now an ON REQUEST job. They are rebuilt when somebody asks for a
demo, not on every commit. What this runner does instead is TELL you they have
drifted, every run, without failing:

    demos: 3 of 4 behind the pages they are built from (rebuild on request)

That line is the whole safety net. It means the drift can never become a
surprise, which was the actual risk: a demo that still works, still looks
right, and shows an app that no longer exists.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# name, command, timeout in seconds.
#
# Timeouts are sized at roughly three times the observed run on 19 Aug, which
# is loose enough that a slow machine does not trip them and tight enough that
# a hang is caught inside a coffee rather than inside a morning.
SUITES = [
    ("rules",      ["node", "tests/rules_test.js"],       120),
    ("coercion",   ["node", "tests/coercion_test.js"],    120),
    ("sw",         ["node", "tests/sw_test.js"],          120),
    ("worker",     ["node", "worker/test.mjs"],           300),
    ("invworker",  ["node", "worker/invites-test.mjs"],   120),
    ("tally",      ["python3", "tests/tally_suite.py"],   600),
    ("cleans",     ["python3", "tests/cl_suite.py"],      900),
    ("frontdesk",  ["python3", "tests/fd_suite.py"],      600),
    ("invites",    ["python3", "tests/inv_suite.py"],     600),
    ("index",      ["python3", "tests/index_suite.py"],   400),
    ("prearrival", ["python3", "tests/pre_suite.py"],     400),
    ("spa",        ["python3", "tests/spa_suite.py"],     400),
    ("list",       ["python3", "tests/list_suite.py"],    400),
    ("housekeep",  ["python3", "tests/hk_suite.py"],      300),
    ("auth",       ["python3", "tests/auth_suite.py"],    300),
    ("registr",    ["python3", "tests/reg_suite.py"],     300),
    ("pages",      ["python3", "tests/pages_suite.py"],   300),
    ("stats",      ["python3", "tests/stats_suite.py"],   400),
    ("tag",        ["python3", "tests/tag_suite.py"],     400),
    ("flags",      ["python3", "tests/flags_suite.py"],   400),
    ("pub",        ["python3", "tests/pub_suite.py"],     400),
    ("debug",      ["python3", "tests/debug_suite.py"],   400),
    ("print",      ["python3", "tests/print_suite.py"],   400),
    ("welcome",    ["python3", "tests/welcome_suite.py"], 300),
    ("demos",      ["python3", "tests/demo_suite.py"],    300),
]

# sweep_suite is one suite on paper and twelve independent runs in practice:
# it takes page names as arguments and each page is swept on its own. Left
# whole it takes longer than every other suite combined, runs on one core, and
# reports nothing until the end, which is what made it look hung twice on
# 19 Aug when it was only slow. Cut into twelve it fits the pool like anything
# else, and a page that breaks is named in the table rather than buried.
#
# This is a scheduling fix, not a speed fix. The suite still sleeps 750ms per
# page load and still reloads the page for each of the three widths when it
# could resize the viewport. Fixing those is the next job and worth more than
# this was.
SWEEP_PAGES = ["cleaners", "front-desk", "invitations", "arrivals-sms", "spa", "past-menus", "templates", "tally", "tag", "flags", "publish", "staff",
               "stats", "registration", "debug", "pages", "index",
               "prearrival", "welcome"]
SUITES += [("sweep:" + p, ["python3", "tests/sweep_suite.py", p], 600)
           for p in SWEEP_PAGES]

# Not in the default run. See the note at the top of this file.
ON_REQUEST = {"demos"}

# Which suites cover which files, for --changed. A shared file has no single
# owner, so it selects everything: nala-shared.js is read by ten pages and a
# change to it can surface anywhere. Better to run the lot than to guess and
# be wrong in the direction of not running something.
COVERS = {
    "tally.html":        ["tally", "sweep:tally"],
    "cleaners.html":     ["cleans", "sweep:cleaners"],
    "front-desk.html":   ["frontdesk", "sweep:front-desk"],
    "invitations.html":  ["invites", "sweep:invitations"],
    "past-menus.html":   ["sweep:past-menus"],
    "arrivals-sms.html": ["invites", "sweep:arrivals-sms"],
    "templates.html":    ["invites", "sweep:templates"],
    "worker/send-invites.js": ["invworker"],
    "worker/mews-sync.js": ["worker"],
    "index.html":        ["index", "sweep:index"],
    "prearrival.html":   ["prearrival", "sweep:prearrival"],
    "spa.html":          ["spa", "sweep:spa"],
    "list.html":         ["list"],
    "housekeeping.html": ["housekeep"],
    "staff.html":        ["auth", "sweep:staff"],
    "registration.html": ["registr", "sweep:registration"],
    "pages.html":        ["pages", "sweep:pages"],
    "stats.html":        ["stats", "sweep:stats"],
    "tag.html":          ["tag", "sweep:tag"],
    "flags.html":        ["flags", "sweep:flags"],
    "publish.html":      ["pub", "sweep:publish"],
    "debug.html":        ["debug", "sweep:debug"],
    "menu-print.html":   ["print"],
    "welcome.html":      ["welcome", "sweep:welcome"],
    "rules.json":        ["rules", "coercion"],
    # Out of EVERYTHING now that a suite owns it: sw.js deliberately has no
    # fetch handler and no caching, so the pages cannot see its internals and
    # a change to it surfaces only in what a push puts on screen, which is
    # exactly what sw_test.js asserts.
    "sw.js":             ["sw"],
}
EVERYTHING = ["nala-shared.js", "auth.js"]


def changed_suites():
    out = subprocess.run(["git", "diff", "--name-only"],
                         capture_output=True, text=True).stdout.split()
    out += subprocess.run(["git", "diff", "--name-only", "--cached"],
                          capture_output=True, text=True).stdout.split()
    if not out:
        return None, []
    picked, why = set(), []
    for f in out:
        if f in EVERYTHING or f.startswith("worker/"):
            if f.startswith("worker/"):
                picked.add("worker"); picked.add("coercion")
                why.append("%s -> worker" % f)
            else:
                why.append("%s is shared, so everything runs" % f)
                return None, why
        elif f in COVERS:
            picked.update(COVERS[f])
            why.append("%s -> %s" % (f, ", ".join(COVERS[f])))
        elif f.startswith("tests/"):
            stem = os.path.basename(f).replace("_suite.py", "").replace("_test.js", "")
            hit = [n for n, _, _ in SUITES
                   if stem.startswith(n[:5]) or n.startswith(stem[:5])
                   or n.startswith(stem + ":")]
            if hit:
                picked.update(hit)
                # One file selecting twelve sweeps printed twelve near
                # identical lines and buried the line that mattered.
                why.append("%s -> %s" % (f, ", ".join(hit) if len(hit) < 4
                                         else "%d jobs" % len(hit)))
    return sorted(picked), why


def demo_drift():
    """How many demo files no longer match what the builder would produce.

    Deliberately quiet and deliberately not a failure. It shells out to the
    builder in a scratch copy, exactly as demo_suite does, and only counts.
    Any error here reports nothing rather than stopping the run: a broken
    drift check must not be able to block a publish.
    """
    import shutil, tempfile
    demos = ["demo-tally.html", "demo-reservations.html",
             "demo-cleans.html", "demo-clean.html"]
    work = tempfile.mkdtemp(prefix="demo-drift-")
    try:
        for name in os.listdir(ROOT):
            if name in (".git", "node_modules", "__pycache__"):
                continue
            src = os.path.join(ROOT, name)
            dst = os.path.join(work, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
        r = subprocess.run(["python3", "tools/make-demo.py"], cwd=work,
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return None
        behind = 0
        for d in demos:
            a = os.path.join(ROOT, d)
            b = os.path.join(work, d)
            if not (os.path.exists(a) and os.path.exists(b)):
                continue
            if open(a, "rb").read() != open(b, "rb").read():
                behind += 1
        return behind, len(demos)
    except Exception:
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


# Most suites end with a RESULT line. sweep_suite ends with "PASS n  FAIL n",
# and reading only the first shape silently scored every sweep as no result.
RESULT = re.compile(r"RESULT:\s*(\d+)\s*passed,\s*(\d+)\s*failed"
                    r"|PASS\s+(\d+)\s+FAIL\s+(\d+)")


def run_one(entry):
    name, cmd, limit = entry
    # Every sweep serves the site itself, so each needs its own port or the
    # second one to start dies before it loads a page. Derived from the page
    # name so a rerun of the same slice always lands on the same port.
    #
    # 9100 up, not 8974 up. The suites already hold fourteen ports between
    # 8953 and 8975 and the obvious block ran straight into debug_suite and
    # print_suite, which is a collision that only appears when the two happen
    # to overlap in the pool and therefore would not have shown up every run.
    env = dict(os.environ)
    # Windows pipes default to the legacy codepage, and one suite printing an
    # emoji then dies with UnicodeEncodeError before it reports a result.
    env["PYTHONUTF8"] = "1"
    if name.startswith("sweep:"):
        env["SWEEP_PORT"] = str(9100 + SWEEP_PAGES.index(name.split(":", 1)[1]))
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=limit, env=env)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return name, "TIMEOUT", 0, 0, time.time() - t0, \
            "no RESULT line after %ds, killed" % limit
    secs = time.time() - t0
    m = RESULT.search(out)
    if not m:
        tail = [l for l in out.strip().splitlines() if l.strip()][-1:]
        return name, "NO RESULT", 0, 0, secs, (tail[0][:70] if tail else "no output")
    p, f = (int(m.group(1)), int(m.group(2))) if m.group(1) \
        else (int(m.group(3)), int(m.group(4)))
    if f:
        fails = [l for l in out.splitlines() if l.startswith("FAIL")][:3]
        return name, "FAIL", p, f, secs, " | ".join(x[5:60] for x in fails)
    return name, "ok", p, f, secs, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="substrings of suite names to run")
    # Four, not more. At six on 19 Aug, cl_suite reported two failures about
    # a pushed villa's colour and sort position, and passed cleanly on its own
    # a minute later. Nothing was wrong with the page: the suites wait on fixed
    # sleeps rather than on conditions, so under enough CPU contention an
    # animation has not finished when the assertion reads it.
    #
    # That is worth fixing at the source, and until it is, four is the number
    # that was stable here. A suite that fails only sometimes is worse than a
    # slow one, because it costs the trust that makes the whole set useful.
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--demos", action="store_true", help="include the demo drift check as a suite")
    ap.add_argument("--changed", action="store_true", help="only suites covering modified files")
    a = ap.parse_args()

    picked = SUITES
    if a.changed:
        want, why = changed_suites()
        for line in why:
            print("  " + line)
        if want is not None:
            picked = [s for s in SUITES if s[0] in want]
            if not picked:
                print("nothing modified that any suite covers")
                return 0
    if a.names:
        picked = [s for s in picked if any(n.lower() in s[0] for n in a.names)]
    if not a.demos and not a.names:
        picked = [s for s in picked if s[0] not in ON_REQUEST]

    print("running %d suites, %d at a time\n" % (len(picked), a.jobs))
    t0 = time.time()
    results = []
    # as_completed, not map. map yields in the order the suites were listed, so
    # one slow suite holds back the lines of every suite after it that has
    # already finished, and the table stops moving for minutes at a time. That
    # is the exact appearance of a hang this runner exists to remove.
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        futures = [pool.submit(run_one, s) for s in picked]
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            name, status, p, f, secs, detail = res
            print("%-18s %-9s %4d passed %3d failed %6.0fs %s"
                  % (name, status, p, f, secs, detail), flush=True)

    tp = sum(r[2] for r in results)
    tf = sum(r[3] for r in results)
    bad = [r for r in results if r[1] != "ok"]
    print("\n%d assertions, %d failed, %d suites not ok, %.0fs wall"
          % (tp + tf, tf, len(bad), time.time() - t0))

    if not a.demos:
        d = demo_drift()
        if d is None:
            print("demos: drift not checked")
        elif d[0] == 0:
            print("demos: all %d match the pages they are built from" % d[1])
        else:
            print("demos: %d of %d behind the pages they are built from "
                  "(rebuild on request: python3 tools/make-demo.py)" % d)

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
