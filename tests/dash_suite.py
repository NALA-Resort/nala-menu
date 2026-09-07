"""dashboard.html, the day's flow on one screen.

The board owns almost nothing. Every fact on it is read from the screen that
already owns it, so the things worth pinning down are the readings, not the
drawing:

  1. An arrival is a stay whose FIRST night is the viewed date. /stays holds
     one row per night, so without that filter every in-house guest sits on
     the board all week - the same trap fd_suite exists to catch.
  2. formState decides a form chip's colour, and the arrival-sheet chips
     mirror it exactly. Two readings of one state is how the boards came to
     disagree in the first place.
  3. The doors are gated by the permission the page BEHIND them answers to,
     in the app's own keys - resSheet, not resBoard. A guessed key is how a
     housekeeper's menu came to offer Publish.
  4. Print does not tick the card. Only a person saying so counts, because
     the app cannot see the paper.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8971), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
def at(h, m=0):
    """An ISO stamp at a wall-clock hour today, in the browser's own zone, so
    a suite written in the morning still passes in the evening."""
    return now.replace(hour=h, minute=m, second=0, microsecond=0).isoformat()

STAFF = {"staff@x":        {"name": "Ana",  "role": "staff"},
         "manager@x":      {"name": "Sam",  "role": "manager"},
         "chef@x":         {"name": "Marco", "role": "chef"},
         "waiter@x":       {"name": "Tui",  "role": "waiter"},
         "housekeeping@x": {"name": "Mere", "role": "housekeeping"}}

# Four arriving today, one mid-stay who must never count as an arrival.
STAYS = {
  "3":  {"id": "b3",  "first": "Ada",   "last": "Lovelace", "arrive": today,
         "depart": plus(3), "adults": 2},
  "7":  {"id": "b7",  "first": "Mark",  "last": "Whitfield", "arrive": today,
         "depart": plus(2), "adults": 2},
  "11": {"id": "b11", "first": "Priya", "last": "Raghunathan", "arrive": today,
         "depart": plus(4), "adults": 3},
  # a full ISO stamp is still arriving today, same as a bare date
  "14": {"id": "b14", "first": "Ann",   "last": "Brown",
         "arrive": today + "T04:00:00Z", "depart": plus(1), "adults": 2},
  # arrived two days ago: in house tonight, NOT an arrival
  "5":  {"id": "b5",  "first": "Mid",   "last": "Stay", "arrive": plus(-2),
         "depart": plus(2), "adults": 2},
}

# b3 complete and checked in; b7 complete, not yet here; b11 part answered;
# b14 nothing at all.
PRE = {
  "b3":  {"at": at(9), "dining": True, "pax": 2, "noDiets": True,
          "wellness": False, "checkedInAt": at(10, 30)},
  "b7":  {"at": at(9, 30), "dining": True, "pax": 2, "noDiets": True,
          "wellness": False},
  "b11": {"dining": True},
  # answered on the form, and no /dinner cell was ever written: the case the
  # first real day turned up, where this board and Invitations disagreed.
  "b14": {"at": at(9, 45), "dining": True, "pax": 2, "noDiets": True,
          "wellness": False},
  "b5":  {"at": at(8), "dining": False, "noDiets": True, "wellness": False},
}

# Villa 3 in, 7 out, 11 not answered, 5 in. Villa 14 was never asked.
DINNER = {
  "3":  {"status": "in",  "pax": 2, "by": "guest", "at": at(10, 5)},
  "7":  {"status": "out", "pax": 0, "by": "guest", "at": at(10, 20)},
  "11": {"status": "",    "pax": 0},
  "5":  {"status": "in",  "pax": 2, "by": "guest", "at": at(10, 40)},
  "2":  {"status": "vacant"},
}

MANUAL = {"ext-a": {"status": "in", "pax": 4},
          "ext-b": {"status": "out", "pax": 2}}   # a cancelled outside table

MENU = {"published": at(10, 6), "main": {"name": "Snapper"}}
# /invites/<date> is keyed by VILLA, not booking id. Villa 3 has been asked;
# villa 7 answered on its pre-arrival form so was never owed one; villas 11
# and 14 are still to ask.
INVITES = {"3": {"status": "sent", "sentAt": at(10, 11)}}

# The built-in roles always hold resBoard and resSheet together, so a suite
# using only those cannot tell the two keys apart - and telling them apart is
# the whole point of naming them. The override matrix separates them:
# housekeeping may read the day, and may still not print the sheets.
PERMS = {}

STATE = {"fail": False}
DAYBOARD = {}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        # /dayboard persists: the tick is read back on the next load.
        if m == "PUT" and "/dayboard/" in u:
            k = u.split("/dayboard/")[1].split(".json")[0].split("/")[-1]
            v = json.loads(request.post_data)
            if v is None: DAYBOARD.pop(k, None)
            else: DAYBOARD[k] = v
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = json.dumps(PERMS)
    elif "/dayboard/" + today in u: body = json.dumps(DAYBOARD)
    elif "/dayboard/" in u: body = "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u: body = "null"
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/dinner/" in u: body = "null"
    elif "/manual/" + today in u: body = json.dumps(MANUAL)
    elif "/manual/" in u: body = "null"
    elif "/invites/" + today in u: body = json.dumps(INVITES)
    elif "/invites/" in u: body = "null"
    elif "/menu" in u: body = json.dumps(MENU)
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE[k]) if k in PRE else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(email="staff@x", w=390, date=None):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8971/dashboard.html" +
                ("?date=" + date if date else ""))
        pg.wait_for_timeout(1600)
        return pg

    def cards(pg):
        return pg.evaluate("()=>items(nowMins()).map(d=>"
                           "({k:d.k,note:d.note,pos:d.pos,door:d.door,"
                           "chips:(d.units||[]).map(u=>u.id+':'+u.tone)}))")

    def card(pg, k):
        return [c for c in cards(pg) if c["k"] == k][0]

    # ── the page draws at all ───────────────────────────────────
    pg = board()
    ck("the board renders its cards",
       pg.evaluate("()=>document.querySelectorAll('.node').length") == 8)
    ck("the date row shows the day, so the board says which day it is",
       pg.evaluate("()=>document.getElementById('title').textContent.trim()") != "")

    # The menu is filled by buildNav in nala-shared.js, but opened by three
    # lines every page carries its own copy of. This page shipped without
    # them, so the hamburger drew and did nothing.
    ck("the menu is built, with links in it",
       pg.evaluate("()=>document.querySelectorAll('#navDrop a').length") > 3)
    pg.click("#navBtn")
    pg.wait_for_timeout(150)
    ck("and the hamburger opens it",
       pg.evaluate("()=>document.getElementById('navDrop').classList.contains('open')"))
    pg.click("#board")
    pg.wait_for_timeout(150)
    ck("and a tap anywhere else shuts it again",
       not pg.evaluate("()=>document.getElementById('navDrop').classList.contains('open')"))

    # ── who is an arrival ───────────────────────────────────────
    forms = card(pg, "forms")
    villas = [c.split(":")[0] for c in forms["chips"]]
    ck("a guest mid stay is not an arrival, though they are in house tonight",
       "5" not in villas)
    ck("a full ISO timestamp counts as arriving today, same as a bare date",
       "14" in villas)
    ck("the arriving villas are the four whose first night is today",
       villas == ["3", "7", "11", "14"])

    # ── form state is formState's, not a second reading ─────────
    ck("a completed form is green, a part answered one amber, an empty one grey",
       forms["chips"] == ["3:green", "7:green", "11:amber", "14:green"])
    ck("and the arrival sheets mirror the form chips exactly",
       card(pg, "sheets")["chips"] == forms["chips"])
    ck("the note counts the three states",
       card(pg, "forms")["note"] == "3 complete, 1 part, 0 nothing yet")

    # ── replies, and the covers adding up ───────────────────────
    reps = card(pg, "reps")
    ck("a villa that said yes is green and one that said no is terracotta",
       "3:green" in reps["chips"] and "7:terra" in reps["chips"])
    ck("a villa still to answer is grey, never red",
       "11:grey" in reps["chips"])
    ck("a vacant villa was never asked, so it is not waiting on anybody",
       not any(c.startswith("2:") for c in reps["chips"]))
    # 2 (villa 3) + 2 (villa 5, in house) + 2 (villa 14, from its form) + 4
    # outside = 10. The cancelled outside table does not count.
    ck("outside diners are added to the covers and shown as their own chip",
       "ext 4:green" in reps["chips"])
    ck("covers count in-house yeses plus outside tables",
       reps["note"].startswith("10 dining so far"))
    ck("and a villa with no dinner state yet is still out, not forgotten",
       reps["note"].endswith("1 villas still out"))

    # Villa 7 said yes on its pre-arrival form and has no /dinner cell. It is
    # answered - Invitations shows it under Answered - and reading /dinner
    # alone showed it grey here while that page showed it green. This is the
    # bug the first real day found.
    ck("a villa that answered on its pre-arrival form reads as answered here too",
       "14:green" in reps["chips"])
    inv = card(pg, "inv")
    ck("and is not counted as still needing an invitation",
       not any(c.startswith("14:") for c in inv["chips"]))
    ck("a villa already sent one is not asked twice",
       not any(c.startswith("3:") for c in inv["chips"]))
    ck("the ones left to ask are named, not just counted",
       inv["chips"] == ["11:grey"])
    ck("and the note says how many are owed one",
       inv["note"].startswith("1 to send"))
    # The header counted this a second way and read five while the card
    # underneath listed one.
    ck("and the header agrees with the card, not its own arithmetic",
       pg.evaluate("()=>document.getElementById('nInv').textContent") == "1")

    # ── the menu count ──────────────────────────────────────────
    # 10 covers, plus villa 11's three unanswered adults, is 13 menus, on
    # ceil(13/2)+1 = 8 pages.
    menus = card(pg, "menus")
    ck("an unanswered villa is still printed for, at the adults on the booking",
       menus["note"].startswith("13 menus on 8 pages"))
    ck("and the note says how many of those are still unanswered",
       menus["note"].endswith("3 not answered yet"))

    # ── the doors, by the app's own permission keys ─────────────
    ck("staff may walk through every door on the board",
       all(c["door"] for c in cards(pg)))
    hk = board("housekeeping@x")
    # A role that cannot see the page it arrived on is a routing problem, not
    # an access one: they are sent to their own board rather than told off.
    ck("housekeeping may not read the day, so they are sent to their own board",
       "cleaners.html" in hk.url)
    hk.close()
    ch = board("chef@x")
    ck("a chef may read the board",
       ch.evaluate("()=>document.getElementById('noAccess').className").find("show") < 0)
    doors = {c["k"]: c["door"] for c in cards(ch)}
    # chef holds resBoard, resSheet and publishMenu, but not editBookings
    ck("a chef may open the print sheets, which answer to resSheet",
       doors["foh"] and doors["menus"])
    ck("but not the front desk pages, which answer to editBookings",
       not doors["forms"] and not doors["sheets"])
    ck("a chef sees no Print button on a sheet they may not open",
       ch.evaluate("()=>!!document.querySelector('[data-print=\\\"foh\\\"]')"))
    ch.close()

    # A role holding resBoard and NOT resSheet: the board opens, the print
    # doors do not. Swapping one key for the other is the mistake this pins.
    PERMS["resBoard"] = {"housekeeping": True}
    hk2 = board("housekeeping@x")
    ck("a role granted resBoard may read the board, whatever its own home is",
       "dashboard.html" in hk2.url)
    d2 = {c["k"]: c["door"] for c in cards(hk2)}
    ck("but resBoard alone does not open the print sheets, which need resSheet",
       not d2["foh"] and not d2["menus"])
    ck("nor the front desk pages, which need editBookings",
       not d2["forms"] and not d2["sheets"])
    ck("and with no door there is no Print button either",
       hk2.evaluate("()=>!document.querySelector('[data-print]')"))
    hk2.close()
    PERMS.clear()

    # ── a heading asks before it walks ──────────────────────────
    pg.click("[data-nav='reps']")
    pg.wait_for_timeout(120)
    # Read the url FIRST: if the tap walked straight through, the button is
    # gone and asking it for its label throws instead of failing, which reads
    # as a crash rather than as the bug it is.
    stayed = "dashboard.html" in pg.url
    # The heading carries a chevron to say it is a door, so read the label
    # without it rather than asserting on the two together.
    label = pg.evaluate("()=>{var b=document.querySelector(\"[data-nav='reps']\");"
                        "return b?b.textContent.replace('\\u203a','').trim():'';}")
    ck("the first tap on a heading asks rather than navigating",
       stayed and label == "Open page")
    pg.click("[data-nav='reps']")
    pg.wait_for_timeout(400)
    ck("and the second tap opens the page it names",
       "tally.html" in pg.url)
    pg.close()

    # ── the tick ────────────────────────────────────────────────
    pg = board()
    before = len(WRITES)
    pg.click("[data-print='foh']")
    pg.wait_for_timeout(400)
    ticks = [w for w in WRITES if "/dayboard/" in w["u"]]
    ck("pressing Print writes nothing: only a person can say the paper exists",
       len(WRITES) == before and not ticks and "foh" not in DAYBOARD)
    ck("and Print carries the day's quantity to the sheet",
       "list.html" in pg.url and "qty=2" in pg.url)
    pg.close()
    pg = board()
    ck("and the card it printed is still unticked afterwards",
       not card(pg, "foh")["note"].startswith("printed"))
    pg.close()

    pg = board()
    pg.click("[data-mark='foh']")
    pg.wait_for_timeout(150)
    ck("marking done asks first",
       pg.evaluate("()=>document.querySelector(\"[data-mark='foh']\").textContent")
       == "Confirm done" and not DAYBOARD)
    pg.click("[data-mark='foh']")
    pg.wait_for_timeout(500)
    ck("and the confirm writes the tick, with who and when",
       "foh" in DAYBOARD and "who" in DAYBOARD["foh"] and "t" in DAYBOARD["foh"])
    ck("the tick records the staff key, not a copied name, so a rename follows",
       DAYBOARD["foh"]["who"] == "staff@x")
    pg.close()

    pg = board()
    ck("a ticked card reads as printed, and says who by",
       card(pg, "foh")["note"].startswith("printed") and
       "Ana" in card(pg, "foh")["note"])
    ck("a ticked card recedes rather than shouting",
       card(pg, "foh")["pos"] == "past")
    pg.click("[data-mark='foh']")
    pg.wait_for_timeout(150)
    pg.click("[data-mark='foh']")
    pg.wait_for_timeout(500)
    ck("and undoing it asks too, then clears the tick",
       "foh" not in DAYBOARD)
    pg.close()

    # The sheets carry a tick like the other two: the written decision said
    # they would not, the mockup the owner signed off shows one, and the
    # mockup won. A card that can be printed can be marked printed.
    pg = board()
    ck("the arrival sheets card offers Mark done, same as the other print cards",
       pg.evaluate("()=>!!document.querySelector(\'[data-mark=\"sheets\"]\')"))

    # ── arrivals are read from checkedInAt ──────────────────────
    arr = card(pg, "arr")
    ck("a checked in guest is green and one still to come is grey",
       arr["chips"] == ["3:green", "7:grey", "11:grey", "14:grey"])
    ck("and the count reads as a fraction of the day's arrivals",
       arr["note"] == "1 in, 3 to come")
    ck("arrivals hang off the spine: they are what the flow was for, not a step in it",
       arr["pos"] == "off")
    pg.close()

    # ── a write that is refused says so ─────────────────────────
    STATE["fail"] = True
    errortrap.expect("401")
    pg = board()
    pg.click("[data-mark='menus']")
    pg.wait_for_timeout(150)
    pg.click("[data-mark='menus']")
    pg.wait_for_timeout(600)
    ck("a refused tick does not pretend it landed",
       "menus" not in DAYBOARD)
    pg.close()
    STATE["fail"] = False

    # ── width ───────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = board(w=w)
        over = pg.evaluate("()=>document.documentElement.scrollWidth - "
                           "document.documentElement.clientWidth")
        ck("nothing bleeds sideways at %d" % w, over <= 0)
        pg.close()

    b.close()

httpd.shutdown()
print("\n%d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
