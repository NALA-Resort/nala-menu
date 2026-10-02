"""Each page opens on its own data and the shell's, and nothing else.

Rule 8 in CLAUDE.md, from the owner's worry of 2 Oct: "I don't want this
air-conditioning automation to slow up the reservations portion. In the same
way, I don't want the Guest chat to slow up their reservation portion." A
module is its own page, its own nodes, its own script and its own Worker, and
another page meets it only through the menu's one small count.

tests/page_reads.json says what every page in the menu may read as it opens,
and how many requests that takes. This opens each page as the admin on one
small seeded house with the menu's counts switched off - nala-shared.js is
served with NAV_ACTIONS emptied, so what is left is the page and the login -
and fails:
  - a node a page reads that is neither its own nor the shell's, by name
  - a page whose own requests grew past its number
It then opens Reservations with the counts on, and fails a count that reads a
node not in "counts", or counts that cost more requests than their number. A
line that allows more than its page now reads is reported, not failed: trim it.

Every page in the menu (tests/nav_canon.json) must have a line here, so a new
module's page cannot arrive without saying what it reads.

    python3 tests/reads_suite.py            the check
    python3 tests/reads_suite.py --record   what every page reads now, for the table
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, os, sys, time, datetime, collections, urllib.parse
os.chdir('/home/claude/nala')
PORT = 8949
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)
RECORD = "--record" in sys.argv

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("No Firebase App '[DEFAULT]' has been created"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},signOut:function(){}};"""
now = datetime.datetime.now().astimezone(); today = now.strftime("%Y-%m-%d")
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")

# One small house, so the pages take their data-led paths as well as their
# fixed ones: an arrival today, a stay-over who dined, and a departure.
STAFF = {"staff@x": {"name": "Admin", "role": "admin"}}
GUESTS = [("1", "b1", "Ada", today, plus(2)),
          ("2", "b2", "Bo", plus(-1), plus(1)),
          ("3", "b3", "Cy", plus(-2), today)]
STAYS, BOOKINGS = {}, {}
for v, bid, first, a, d in GUESTS:
    n = datetime.date.fromisoformat(a)
    while n.isoformat() < d:
        STAYS.setdefault(n.isoformat(), {})[v] = {"id": bid, "first": first, "last": "Lee",
                                                   "arrive": a, "depart": d, "adults": 2}
        n += datetime.timedelta(days=1)
    BOOKINGS[bid] = {"pms": {"first": first, "last": "Lee", "arrive": a, "depart": d,
                             "villa": v, "state": "confirmed"}}
BOOKINGS["b1"]["prearrival"] = {"dining": True, "pax": 2, "diets": ["Nut allergy"]}
DINNER = {today: {"2": {"status": "in", "pax": 2, "room": "2", "bookingId": "b2",
                        "by": "guest", "at": now.isoformat()}}}
HK = {plus(-1): {"3": {"done": now.isoformat()}}}

def node_of(path):
    return path.lstrip("/").split("/")[0].split(".json")[0]

def fb(route, request):
    u = request.url
    if request.method != "GET":
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    path = u.split("firebasedatabase.app", 1)[1].split("?")[0]
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
    parts = path.lstrip("/").replace(".json", "").split("/")
    body = None
    if parts[0] == "staff":
        body = STAFF
    elif parts[0] == "stays" and len(parts) == 1:
        lo = json.loads(qs.get("startAt", ['""'])[0]); hi = json.loads(qs.get("endAt", ['"9"'])[0])
        body = {d: s for d, s in STAYS.items() if lo <= d <= hi}
    elif parts[0] == "stays":
        body = STAYS.get(parts[1])
    elif parts[0] == "dinner" and len(parts) > 1:
        body = DINNER.get(parts[1])
    elif parts[0] == "hk" and len(parts) > 1:
        body = HK.get(parts[1])
    elif parts[0] == "bookings" and len(parts) == 1:
        start = json.loads(qs["startAt"][0]) if "startAt" in qs else ""
        body = {k: b for k, b in BOOKINGS.items() if b["pms"]["depart"] >= start}
    elif parts[0] == "bookings":
        body = BOOKINGS.get(parts[1])
        for p in parts[2:]:
            body = body.get(p) if isinstance(body, dict) else None
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

# The menu's counts switched off for a page's own reads: the file is served
# whole with one line after it, so nothing inside it is edited by hand.
SHARED = open("nala-shared.js", encoding="utf-8").read()
def no_counts(route, request):
    route.fulfill(status=200, content_type="application/javascript",
                  body=SHARED + "\nNAV_ACTIONS.length = 0;\n")

def menu_pages():
    """Every page the menu offers, read from the canon rather than restated."""
    canon = json.load(open("tests/nav_canon.json"))
    out = set()
    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("href"), str): out.add(x["href"])
            for k, v in x.items():
                if k not in ("_comment", "tabs"): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        elif isinstance(x, str) and x.endswith(".html"):
            out.add(x)
    walk({k: v for k, v in canon.items() if k not in ("_comment", "tabs")})
    return sorted(out)

P = F = 0
def ck(name, cond, detail=None):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or detail is None else "  -> %s" % (detail,)))
    if cond: P += 1
    else: F += 1

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    def opening(page, counts=False):
        """The reads a page makes as it opens: node -> requests."""
        seen = collections.Counter()
        pg = b.new_page(viewport={"width": 390, "height": 844})
        # The last route added is tried first, so the catch-alls go in before
        # the two SDK files they would otherwise swallow.
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**cdnjs.cloudflare.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**.workers.dev/**", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        pg.route("**/firebase-app-compat.js", lambda r, _: r.fulfill(
            status=200, content_type="application/javascript", body=SDK))
        pg.route("**/firebase-auth-compat.js", lambda r, _: r.fulfill(
            status=200, content_type="application/javascript", body="/*n*/"))
        if not counts:
            pg.route("**/nala-shared.js*", no_counts)
        pg.route("**firebasedatabase.app/**", fb)
        pg.on("request", lambda r: seen.update([node_of(
            r.url.split("firebasedatabase.app", 1)[1].split("?")[0])])
            if "firebasedatabase.app" in r.url and r.method == "GET" else None)
        pg.goto("http://localhost:%d/%s" % (PORT, page))
        pg.wait_for_timeout(2500)
        pg.close()
        return seen

    pages = menu_pages()
    if RECORD:
        got = {pg_: opening(pg_) for pg_ in pages}
        shell = set.intersection(*[set(c) for c in got.values()])
        print("shell (read by every page):", sorted(shell))
        for pg_, c in got.items():
            own = {k: v for k, v in c.items() if k not in shell}
            print('  "%s": {"reads": %s, "max": %d},' % (pg_, json.dumps(sorted(own)), sum(own.values())))
        on, off = opening("tally.html", counts=True), got["tally.html"]
        diff = on - off
        print("counts on tally.html:", dict(diff), "total", sum(diff.values()))
        b.close(); sys.exit(0)

    table = json.load(open("tests/page_reads.json"))
    shell = set(table["shell"]["nodes"])
    lines = table["pages"]
    missing = [x for x in pages if x not in lines]
    ck("every page in the menu has a line in page_reads.json", not missing, missing)
    for page in sorted(lines):
        c = opening(page)
        mine = set(lines[page]["reads"])
        stray = sorted(set(c) - shell - mine)
        ck("%s reads only its own nodes and the shell's" % page, not stray,
           "reads %s, not on its line" % stray)
        own = sum(n for k, n in c.items() if k not in shell)
        ck("%s opens with at most %d requests of its own" % (page, lines[page]["max"]),
           own <= lines[page]["max"], own)
        unused = sorted(mine - set(c))
        if unused:
            print("   note: %s no longer reads %s on opening - trim its line" % (page, unused))
        if own < lines[page]["max"]:
            print("   note: %s opens with %d of its own, under its %d - lower its number"
                  % (page, own, lines[page]["max"]))
    cp = table["counts"]["page"]
    diff = opening(cp, counts=True) - opening(cp)
    stray = sorted(set(diff) - set(table["counts"]["nodes"]))
    ck("the menu's counts read only their own nodes", not stray, stray)
    ck("the menu's counts cost at most %d requests on %s" % (table["counts"]["max"], cp),
       sum(diff.values()) <= table["counts"]["max"], sum(diff.values()))
    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
sys.exit(1 if F else 0)
