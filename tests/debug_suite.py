"""debug.html, Diagnostics.

This is the page somebody opens when the boards look wrong, which means it is
the page most able to make a bad day worse: three of its buttons delete live
records, and every answer it gives is one somebody is about to act on.

So the suite is mostly about honesty rather than features:

  a node that could not be read is never counted as an empty one
  nothing is offered for deletion that has not been listed on screen first
  the merge preview writes nothing at all
  a duplicate villa is only offered for deletion when Mews has settled it

The first of those is the 17 Aug bug, which reported 0 records for four nodes
it had no permission to list, said it had succeeded, and deleted nothing. The
fix is in the page; this pins it there.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8974), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")
def plus(n):
    return (now + datetime.timedelta(days=n)).strftime("%Y-%m-%d")

def sdk(email="staff@x"):
    return """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'%s',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'%s'});},25);},
signOut:function(){}};""" % (email, email)
SDK = sdk()

# The whole database as the page sees it, node by node. Anything set to the
# string "denied" is served as a 401, which is how the rules refuse a node.
DATA = {}
WRITES = []

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

def reset():
    del WRITES[:]
    DATA.clear()
    DATA.update({
        "staff": dict(STAFF),
        "roomguests": {today: {"1": {"name": "James Hall", "departs": plus(2),
                                     "bookingId": "b1"}}},
        "responses": {},
        "manual": {},
        "hk": {today: {"1": {"done": now.isoformat()}}},
        "stays": {today: {"1": {"id": "b1", "first": "James", "last": "Hall",
                                "villa": "1", "departs": plus(2)}}},
        "guests": {},
        "combined": {},
        "dinner": {today: {"1": {"status": "in", "pax": 2, "by": "guest"}}},
        "bookings": {"b1": {"pms": {"villa": "1", "first": "James", "last": "Hall"}}},
    })

def node_of(url):
    # /roomguests/2026-08-17/1.json -> roomguests
    path = url.split("firebasedatabase.app/")[1].split(".json")[0]
    return path.split("/")[0], [s for s in path.split("/")[1:] if s]

def lookup(node, parts):
    cur = DATA.get(node)
    for p in parts:
        if not isinstance(cur, dict): return None
        cur = cur.get(p)
    return cur

def fb(route, request):
    u, m = request.url, request.method
    node, parts = node_of(u)
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "node": node, "parts": parts})
        route.fulfill(status=200, content_type="application/json", body="null"); return
    if DATA.get(node) == "denied":
        route.fulfill(status=401, content_type="application/json",
                      body='{"error":"Permission denied"}'); return
    v = lookup(node, parts)
    route.fulfill(status=200, content_type="application/json", body=json.dumps(v))

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def deletes():
    return [w for w in WRITES if w["m"] == "DELETE"]

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_debug(accept=True, w=390, email="staff@x"):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(sdk(email))
        pg.on("dialog", lambda d: d.accept() if accept else d.dismiss())
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        # The shared script's announceMenu archives today's menu on every
        # signed-in page load, and the repo's real menu.json is published
        # for the run date whenever the chef has published before the tests
        # run. That PUT lands inside this suite's "writes nothing" windows,
        # which held every day until 20 Aug only because it was racing the
        # assertions. Diagnostics do not need a menu: serve an unpublished
        # one and announceMenu correctly does nothing.
        pg.route("**/menu.json*", lambda r: r.fulfill(
            status=200, content_type="application/json", body="{}"))
        pg.goto("http://localhost:8974/debug.html")
        pg.wait_for_timeout(900)
        return pg

    # ── the page loads and reads what it says it reads ────────
    reset()
    pg = open_debug()
    ck("today's date is shown, because every other answer is dated by it",
       pg.inner_text("#today").strip() == today)
    ck("the stays node for today is read", "James" in pg.inner_text("#stayT"))
    ck("and tomorrow's, which is the one that shows a sync arriving",
       "HTTP 200" in pg.inner_text("#stayN"))
    ck("the sync check reports villa nights it can see",
       "villa night" in pg.inner_text("#syncv"))
    pg.close()

    # A fortnight with nothing in it is the answer that matters, because it is
    # the one that means the Zap has stopped.
    reset(); DATA["stays"] = {}
    pg = open_debug()
    ck("an empty fortnight is stated plainly, and points at Zapier",
       "NOTHING IN THE NEXT FORTNIGHT" in pg.inner_text("#syncv")
       and "Zap" in pg.inner_text("#syncv"))
    pg.close()

    # The old shape is a bare booking id where a record should be. The boards
    # skip those silently, so this page has to not skip them.
    reset(); DATA["stays"] = {today: {"1": "b1", "2": "b2"}}
    pg = open_debug()
    ck("stay entries in the old shape are called out",
       "OLD SHAPE" in pg.inner_text("#syncv").upper())
    pg.close()

    # ── Clean Slate: the count ────────────────────────────────
    reset()
    pg = open_debug()
    pg.click("button:text-is('Count what would go')"); pg.wait_for_timeout(700)
    wipe = pg.inner_text("#wipe")
    ck("the scan counts the operational nodes", "roomguests: 1 record" in wipe)
    ck("dinner is counted, having once been left behind by a clean slate",
       "dinner: 1 record" in wipe)
    ck("and bookings, for the same reason", "bookings: 1 record" in wipe)
    ck("configuration is named as untouched",
       "staff" in wipe and "not touched" in wipe.lower())
    ck("the delete button only wakes up once there is a list",
       not pg.is_disabled("#wipeGo"))
    ck("counting deletes nothing by itself", not deletes())
    pg.close()

    reset()
    for n in ("roomguests", "hk", "stays", "dinner", "bookings"):
        DATA[n] = {}
    pg = open_debug()
    pg.click("button:text-is('Count what would go')"); pg.wait_for_timeout(700)
    ck("an empty database offers nothing to delete", pg.is_disabled("#wipeGo"))
    pg.close()

    # ── Clean Slate: the refused read ─────────────────────────
    # The bug, in the place it happened. A node the rules will not list must
    # not be reported as a node with nothing in it.
    reset(); DATA["manual"] = "denied"; DATA["responses"] = "denied"
    pg = open_debug()
    pg.click("button:text-is('Count what would go')"); pg.wait_for_timeout(700)
    wipe = pg.inner_text("#wipe")
    ck("a node that could not be read says so, in those words",
       "COULD NOT READ" in wipe.upper())
    ck("it is not reported as zero records", "manual: 0 record" not in wipe)
    ck("the reader is told those nodes are not empty",
       "not empty" in wipe.lower())
    ck("and pointed at the rules, which is what actually fixes it",
       "rules.json" in wipe)
    pg.close()

    # ── Clean Slate: the delete ───────────────────────────────
    reset()
    pg = open_debug()
    pg.click("button:text-is('Count what would go')"); pg.wait_for_timeout(700)
    pg.click("#wipeGo"); pg.wait_for_timeout(1200)
    nodes = set(w["node"] for w in deletes())
    ck("deleting hits every node that was counted",
       {"roomguests", "hk", "stays", "dinner", "bookings"} <= nodes)
    ck("and leaves the configuration nodes alone",
       not nodes & {"staff", "notify", "menutags", "dietaries"})
    ck("it deletes leaf by leaf, not whole nodes, because the rules grant it there",
       all(len(w["parts"]) >= 2 for w in deletes() if w["node"] == "roomguests"))
    ck("and reports what it did", "deleted" in pg.inner_text("#wipe").lower())
    pg.close()

    # Two confirms guard it. Declining the first must delete nothing at all.
    reset()
    pg = open_debug(accept=False)
    pg.click("button:text-is('Count what would go')"); pg.wait_for_timeout(700)
    pg.click("#wipeGo"); pg.wait_for_timeout(600)
    ck("saying no to the confirm deletes nothing", not deletes())
    pg.close()

    # ── merge tag junk ────────────────────────────────────────
    reset()
    DATA["roomguests"] = {today: {"1": {"name": "{{firstname}} {{lastname}}",
                                        "departs": "{{check-out_date}}"},
                                  "2": {"name": "Real Guest", "departs": plus(1)}}}
    pg = open_debug()
    pg.click("button:text-is('Find junk')"); pg.wait_for_timeout(600)
    junk = pg.inner_text("#junk")
    ck("an unsubstituted merge tag is found", "1 record" in junk)
    ck("a real record beside it is left alone", "Real Guest" not in junk)
    ck("the record is shown before anything is deleted", "{{firstname}}" in junk)
    ck("finding deletes nothing", not deletes())
    pg.click("#junkDel"); pg.wait_for_timeout(600)
    ck("only the listed record is deleted",
       [w["parts"] for w in deletes()] == [[today, "1"]])
    pg.close()

    reset()
    pg = open_debug()
    pg.click("button:text-is('Find junk')"); pg.wait_for_timeout(600)
    ck("a clean node says so and offers no delete",
       "No merge tag junk" in pg.inner_text("#junk") and pg.is_disabled("#junkDel"))
    pg.close()

    # ── orphan pre-arrival answers ────────────────────────────
    # A guest answers the form, then the booking is cancelled or the link
    # carried an id Mews never had. The answers sit against nothing forever.
    reset()
    DATA["bookings"] = {
        "b1": {"pms": {"villa": "1", "first": "James", "last": "Hall",
                       "state": "confirmed"},
               "prearrival": {"dining": True, "at": now.isoformat()}},
        "b-cancelled": {"pms": {"first": "Ruth", "last": "Bell",
                                "state": "cancelled"},
                        "prearrival": {"dining": True, "diets": ["Vegan"],
                                       "at": now.isoformat()}},
        "b-typo": {"prearrival": {"dining": False, "at": now.isoformat()}},
        "b-old": {"pms": {"first": "Gone", "last": "Long", "state": "confirmed",
                          "depart": "2026-01-04"},
                  "prearrival": {"dining": True, "at": "2026-01-01T00:00:00Z"}},
        "b-nopre": {"pms": {"villa": "9", "state": "cancelled"}},
    }
    pg = open_debug()
    pg.click("button:text-is('Find orphans')"); pg.wait_for_timeout(700)
    o = pg.inner_text("#orphans")
    ck("a cancelled booking's answers are found", "b-cancelled" in o)
    ck("and an id Mews has never heard of", "b-typo" in o)
    ck("a live booking's answers are left alone", "b1" not in o)
    ck("and so are old ones, because age is not a reason", "b-old" not in o)
    ck("a cancelled booking with no answers is not listed", "b-nopre" not in o)
    ck("the guest is named where Mews knows them", "Ruth" in o)
    ck("and what they said is shown before it is deleted", "Vegan" in o)
    ck("finding deletes nothing", not deletes())
    pg.click("#orphanDel"); pg.wait_for_timeout(700)
    gone = sorted([w["parts"][0] for w in deletes()])
    ck("only the listed answers are deleted", gone == ["b-cancelled", "b-typo"])
    ck("and only the answers, not the booking",
       all(w["parts"][1] == "prearrival" for w in deletes()))
    pg.close()

    reset()
    pg = open_debug()
    pg.click("button:text-is('Find orphans')"); pg.wait_for_timeout(700)
    ck("nothing to clear says so and offers no delete",
       "No orphan" in pg.inner_text("#orphans") and pg.is_disabled("#orphanDel"))
    pg.close()

    # A refused read must not read as a clean database. Same lesson as Clean
    # Slate, in the newest place it could happen.
    reset(); DATA["bookings"] = "denied"
    pg = open_debug()
    pg.click("button:text-is('Find orphans')"); pg.wait_for_timeout(700)
    o = pg.inner_text("#orphans")
    ck("a refused read is not reported as no orphans", "No orphan" not in o)
    ck("it says what went wrong", "could not read" in o.lower())
    ck("and offers nothing to delete", pg.is_disabled("#orphanDel"))
    pg.close()

    # ── a booking in two villas ───────────────────────────────
    reset()
    DATA["stays"] = {today: {"1": {"id": "b1", "first": "James", "last": "Hall"},
                             "4": {"id": "b1", "first": "James", "last": "Hall"}}}
    pg = open_debug()
    pg.click("button:text-is('Find duplicates')"); pg.wait_for_timeout(800)
    d = pg.inner_text("#dupes")
    ck("a booking held in two villas is found", "villa 4" in d)
    ck("and the villa Mews confirms is not offered for deletion",
       "villa 1  " not in d.replace("\n", " "))
    ck("the reader is told what the list means", "Mews says" in d)
    pg.click("#dupeDel"); pg.wait_for_timeout(600)
    ck("only the villa Mews disagrees with is deleted",
       [w["parts"] for w in deletes()] == [[today, "4"]])
    pg.close()

    # If Mews cannot settle it, guessing which villa to delete is worse than
    # leaving both, because both at least shows on the board.
    reset()
    DATA["stays"] = {today: {"1": {"id": "bx"}, "4": {"id": "bx"}}}
    DATA["bookings"] = {}
    pg = open_debug()
    pg.click("button:text-is('Find duplicates')"); pg.wait_for_timeout(800)
    d = pg.inner_text("#dupes")
    ck("a duplicate Mews cannot settle is left alone", pg.is_disabled("#dupeDel"))
    ck("and is still shown, so it is not invisible", "bx" in d)
    pg.close()

    reset()
    pg = open_debug()
    pg.click("button:text-is('Find duplicates')"); pg.wait_for_timeout(800)
    ck("no duplicates says no duplicates",
       "No booking is in more than one villa" in pg.inner_text("#dupes"))
    pg.close()

    # ── the merge preview ─────────────────────────────────────
    reset()
    DATA["dinner"] = {today: {"1": {"status": "in", "pax": 2, "by": "guest",
                                    "name": "James Hall"}}}
    pg = open_debug()
    pg.click("button:text-is('Show')"); pg.wait_for_timeout(900)
    m = pg.inner_text("#merge")
    ck("the preview runs the real merge and names the guest", "James Hall" in m)
    ck("it says where the answer came from", "PMS" in m)
    ck("and it writes nothing at all", not WRITES)
    pg.close()

    # A villa marked vacant by staff is a decision, not an unknown, and the
    # preview counts it separately. Reporting those as guests made a normal
    # board look like a broken one.
    reset()
    DATA["dinner"] = {today: {"3": {"status": "vacant", "pax": 0, "by": "staff"}}}
    pg = open_debug()
    pg.click("button:text-is('Show')"); pg.wait_for_timeout(900)
    ck("a staff vacant is counted as vacant, not as a guest",
       "1 marked vacant" in pg.inner_text("#merge"))
    pg.close()

    # ── the write test ────────────────────────────────────────
    reset()
    pg = open_debug()
    pg.click("button:text-is('Run write test')"); pg.wait_for_timeout(700)
    w = [x for x in WRITES if x["m"] == "PUT"]
    ck("the write test writes to a villa number no guest uses",
       bool(w) and w[0]["parts"] == [today, "99"])
    ck("and shows the status it got back", "HTTP 200" in pg.inner_text("#write"))
    pg.close()

    # ── who may open it at all ────────────────────────────────
    # Three of the tools on this page delete live data, and until 18 Aug the
    # page had no role gate: any login that could sign in could run Clean
    # Slate. The rules cannot catch it, because those deletes are the same
    # writes these roles legitimately make elsewhere, so the page is the gate.
    reset()
    pg = open_debug(email="staff@x")
    ck("the manager sees the tools", pg.locator("#tools").is_visible())
    pg.close()

    for who, role in (("chef@x", "the chef"), ("waiter@x", "a waiter"),
                      ("housekeeping@x", "housekeeping")):
        q = open_debug(email=who)
        q.wait_for_timeout(600)
        ck("%s cannot reach Diagnostics" % role, not q.url.endswith("debug.html"))
        q.close()

    # A login with no record at all has nowhere to be sent, so it gets the
    # message rather than a redirect.
    q = open_debug(email="nobody@x")
    q.wait_for_timeout(600)
    ck("a login with no role is told, not redirected into a loop",
       q.url.endswith("debug.html")
       and "manager" in q.inner_text("#noAccess").lower())
    ck("and the tools are not on the page for them",
       not q.locator("#tools").is_visible())
    q.close()

    # ── it is opened on a phone, in a hurry ───────────────────
    reset()
    for w in (390, 360, 320):
        q = open_debug(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
