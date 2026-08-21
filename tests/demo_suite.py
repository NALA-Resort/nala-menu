"""The demo sheets, and whether they still resemble the pages they came from.

`tools/make-demo.py` inlines four pages into standalone offline files that work
with no signal and cannot write to the database. They are what gets shown to
somebody who is not going to sign in.

Nothing rebuilds them. So every change to a real sheet leaves the demo one
commit further behind, silently, and the failure is the worst kind: the demo
still works, still looks right, and quietly shows an app that no longer exists.
Checked on 18 Aug and all four had drifted, one of them by 348 lines.

This does not compare the files, which would fail on every commit and teach
everyone to ignore it. It rebuilds them into a scratch directory and asks
whether the committed copy matches what the builder produces now. If it does
not, somebody changed a sheet and did not re-run the builder.

The fix when this fails is one command:

    python3 tools/make-demo.py

then publish the four demo files with whatever else is going out.
"""
import errortrap   # fails the run if any page throws
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = "/home/claude/nala"
os.chdir(ROOT)

DEMOS = ["demo-tally.html", "demo-reservations.html",
         "demo-cleans.html", "demo-clean.html"]

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    if cond:
        P += 1
    else:
        F += 1
        if detail:
            print("      " + detail)


# Every demo must exist before anything else is worth asking.
for d in DEMOS:
    ck("%s is in the repo" % d, os.path.exists(os.path.join(ROOT, d)))

# ── rebuild into a scratch copy and compare ─────────────────────────────
# The builder writes to the repo root, so it runs against a copy. Rebuilding
# in place would make this suite pass by silently fixing what it is meant to
# report, which is the one thing a test must never do.
work = tempfile.mkdtemp(prefix="demo-check-")
try:
    for name in os.listdir(ROOT):
        if name in (".git", "node_modules", "__pycache__"):
            continue
        src = os.path.join(ROOT, name)
        dst = os.path.join(work, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                ".git", "node_modules", "__pycache__"))
        else:
            shutil.copy2(src, dst)

    run = subprocess.run([sys.executable, "tools/make-demo.py"],
                         cwd=work, capture_output=True, text=True, timeout=300)
    ck("the demo builder runs", run.returncode == 0,
       (run.stderr or run.stdout)[-300:])

    # The builder stamps the build date, so two builds on different days differ
    # by that line alone. Dates are normalised out: a date changing is not
    # drift, a sheet changing is.
    DATESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}(T[\d:.+-]+)?")

    def normalise(text):
        return DATESTAMP.sub("<date>", text)

    for d in DEMOS:
        here = os.path.join(ROOT, d)
        rebuilt = os.path.join(work, d)
        if not (os.path.exists(here) and os.path.exists(rebuilt)):
            ck("%s could be compared" % d, False, "one side missing")
            continue
        a = normalise(open(here, encoding="utf-8").read())
        b = normalise(open(rebuilt, encoding="utf-8").read())
        same = a == b
        detail = ""
        if not same:
            detail = ("committed %d chars, rebuilt %d. Run "
                      "python3 tools/make-demo.py and publish the demo files."
                      % (len(a), len(b)))
        ck("%s matches what the builder produces now" % d, same, detail)
finally:
    shutil.rmtree(work, ignore_errors=True)

# ── the promise each demo makes ────────────────────────────────────────
# A demo that can reach the network is not a demo, it is the live app under a
# different name, and it can write to the real database.
#
# This is not a text search. The database address does appear in each file,
# and that is fine: window.fetch is replaced before anything uses it, so the
# address is never dialled. Searching the text would fail on a working demo
# and pass on a broken one where the stub was installed too late. The only
# honest question is whether the file, opened in a browser, asks the network
# for anything. So it is opened, and every request it makes is recorded.
import http.server, socketserver, threading, time, json

PORT = 9007
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
time.sleep(0.3)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for d in DEMOS:
        if not os.path.exists(os.path.join(ROOT, d)):
            continue
        pg = b.new_page(viewport={"width": 390, "height": 900})
        outside = []
        def seen(req, _o=outside):
            u = req.url
            if u.startswith("http://localhost:%d/%s" % (PORT, d)):
                return          # the file itself
            if u.startswith("data:") or u.startswith("blob:"):
                return          # inlined, which is the point of the demo
            _o.append(u.split("?")[0][:70])
        pg.on("request", seen)
        pg.goto("http://localhost:%d/%s" % (PORT, d), timeout=15000)
        pg.wait_for_timeout(2200)
        # Press a few things: a demo that only leaks once somebody uses it is
        # still a demo that leaks.
        try:
            for i in range(min(6, pg.locator("button").count())):
                try:
                    pg.locator("button").nth(i).click(timeout=1200, force=True)
                    pg.wait_for_timeout(200)
                except Exception:
                    pass
        except Exception:
            pass
        pg.wait_for_timeout(600)
        ck("%s asks the network for nothing, even once used" % d,
           not outside, ", ".join(sorted(set(outside))[:4]))
        pg.close()
    b.close()
httpd.shutdown()

print("RESULT: %d passed, %d failed" % (P, F))
