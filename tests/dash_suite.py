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
  "3":  {"id": "b3",  "first": "Ada",   "last": "Lovelace", "phone": "+61400000011", "arrive": today,
         "depart": plus(3), "adults": 2},
  "7":  {"id": "b7",  "first": "Mark",  "last": "Whitfield", "phone": "+61400000012", "arrive": today,
         "depart": plus(2), "adults": 2},
  "11": {"id": "b11", "first": "Priya", "last": "Raghunathan", "phone": "+61400000013", "arrive": today,
         "depart": plus(4), "adults": 3},
  # a full ISO stamp is still arriving today, same as a bare date
  "14": {"id": "b14", "first": "Ann",   "last": "Brown", "phone": "+61400000014",
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
  "b11": {"wellness": False},
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

# Externals arrive two ways. This is the digital one: a reply with no room on
# it, keyed by phone, living under /responses - a node this page did not read
# at all until 8 Sep, so every table booked through a link was invisible here
# while Reservations counted it.
RESPONSES = {"+61400000001": {"status": "in", "pax": 3},
             "+61400000002": {"status": "out", "pax": 2},
             "+61400000003": {"status": "in", "room": "3", "pax": 2}}

# The stamp a real publish writes: UTC, which in Australia falls on the
# PREVIOUS calendar day for anything before 10am. Slicing its first ten
# characters compares the wrong date, which is how a published menu read as
# not published on the second real day.
def utc_at(h, m=0):
    import datetime as _dt
    local = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return local.astimezone(_dt.timezone.utc).isoformat().replace("+00:00", "Z")

MENU = {"published": at(10, 6), "bread": {"name": "Sourdough"},
        "entree": {"name": "Kingfish"}, "main": {"name": "Snapper"},
        "dessert": {"name": "Pavlova"}}
# The live /menu node holds whatever was published last, whatever night it
# was for. Reading it without a date check is how a card announced a publish
# time for a night nothing had been published for.
STALE_MENU = {"published": plus(-1) + "T08:14:00+10:00",
              "bread": {"name": "Old"}, "entree": {"name": "Old"},
              "main": {"name": "Old"}, "dessert": {"name": "Old"}}
HALF_MENU = {"published": at(8, 14), "bread": {"name": "Sourdough"},
             "entree": {"name": ""}, "main": {"name": ""},
             "dessert": {"name": ""}}
MENU_NOW = {"m": MENU}
# /invites/<date> is keyed by VILLA, not booking id. Villa 3 has been asked;
# villa 7 answered on its pre-arrival form so was never owed one; villas 11
# and 14 are still to ask.
INVITES = {"3": {"status": "sent", "sentAt": at(10, 11)}}

# The built-in roles always hold resBoard and resSheet together, so a suite
# using only those cannot tell the two keys apart - and telling them apart is
# the whole point of naming them. The override matrix separates them:
# housekeeping may read the day, and may still not print the sheets.
PERMS = {}

# Booked treatments only. A request or a suggestion is not something anybody
# is expecting a guest to turn up for, so it is not a reminder.
SPA = {"b3": {"t1": {"status": "booked", "day": today, "time": "11:00",
                     "dur": 60, "qty": 1, "name": "Ada Lovelace"}},
       "b7": {"t2": {"status": "requested", "reqDay": today, "reqTime": "any"},
              "t3": {"status": "booked", "day": today, "time": "14:30",
                     "dur": 90, "dur2": 60, "qty": 2, "name": "Mark Whitfield"}},
       "b11": {"t4": {"status": "booked", "day": plus(1), "time": "09:00",
                      "dur": 60, "qty": 1}}}
# The spa reminder log (/spareminders, 28 Sep): villa 3's 11:00 was texted
# this morning quoting 11:00; villa 7's pair has had nothing yet. And Mews'
# own record for each, which is where the Worker reads the number from.
SPAREM = {"b3": {"t1": {"status": "sent", "sentAt": at(8, 5), "providerId": "mid-3",
                        "day": today, "time": "11:00", "qty": 1, "dur": 60}}}
PMS = {"b3": {"first": "Ada", "last": "Lovelace", "phone": "+61 411 000 003", "villa": "3"},
       "b7": {"first": "Mark", "last": "Whitfield", "phone": "+61 411 000 007", "villa": "7"}}

# The pre-arrival SMS window: the next 14 days of ARRIVALS, read through
# preSmsState exactly as arrivals-sms.html reads it, so the two screens cannot
# disagree about who is still to send. Two villas are still to send (6 and 15),
# one was already sent (2), one has completed its form (4), and villa 8 arrived
# yesterday - in house, not an arrival - so it must be filtered even though it
# sits on a window night. Villa 6 spans two nights to exercise the dedup: it is
# counted once, on the night it arrives, never twice.
def wstay(bid, phone, a, d):
    return {"id": bid, "first": "W", "last": bid, "phone": phone,
            "arrive": plus(a), "depart": plus(d)}
WINDOW = {
  plus(2): {"2":  wstay("pa-sent2",    "+61411000032", 2, 4)},
  plus(4): {"4":  wstay("pa-done4",    "+61411000034", 4, 5)},
  plus(5): {"6":  wstay("pa-ready6",   "+61411000036", 5, 7)},
  plus(6): {"6":  wstay("pa-ready6",   "+61411000036", 5, 7),
            "8":  wstay("pa-inhouse8", "+61411000038", -1, 6)},
  plus(8): {"15": wstay("pa-ready15",  "+61411000315", 8, 10)},
}
# pa-done4 finished a one-night form; pa-sent2 was messaged and delivered;
# pa-ready6's send FAILED on the country code, so it is still to send AND a
# failure - the red-ring pill. pa-ready15 has no form and no send, so it is a
# plain grey to-send.
WPRE = {"pa-done4": {"at": at(9), "dining": True, "noDiets": True}}
WPREINV = {"pa-sent2":  {"status": "sent", "sentAt": at(9), "delivery": "delivered"},
           "pa-ready6": {"status": "failed", "sentAt": at(9),
                         "error": "COUNTRY_NOT_ENABLED"}}

STATE = {"fail": False, "contactfail": False}

# Chat (29 Sep): two guests with a message nobody has sorted, and
# the teams' tasks - one open for Maintenance, one done for Bar, and one
# still open for Pool bar, a team since retired, which must still count.
CONTACT_NEW = {"61400000011": {"in-SM1": True, "in-SM2": True},
               "61499000001": {"in-SM3": True}}
CONTACT_SETTINGS = {"teams": {"poolbar": {"label": "Pool bar", "off": True,
                                          "added": "2026-09-01T00:00:00.000Z"}}}
CONTACT_TASKS = {"maintenance": {"t1": {"state": "open"}},
                 "bar":         {"t2": {"state": "done"}},
                 "poolbar":     {"t3": {"state": "open"}}}
DAYBOARD = {}
CARDS = {}    # the card table: serial -> row
CUTRUN = {}   # the cut run, when one is on
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
    path = u.split("firebasedatabase.app")[1].split("?")[0]
    if path.startswith(("/contact", "/tasks/")):
        if STATE["contactfail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        if path == "/contactnew.json":
            body = json.dumps({k: True for k in CONTACT_NEW} if "shallow=true" in u else CONTACT_NEW)
        elif path == "/contactsettings.json": body = json.dumps(CONTACT_SETTINGS)
        elif path.startswith("/tasks/"):
            team = CONTACT_TASKS.get(path[7:-5], {})
            want = "open" if "equalTo" in u else None
            body = json.dumps({k: v for k, v in team.items()
                               if want is None or v.get("state") == want} or None)
        route.fulfill(status=200, content_type="application/json", body=body); return
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/spareminders" in u: body = json.dumps(SPAREM) if SPAREM else "null"
    elif "/spa.json" in u or u.rstrip("/").endswith("/spa"): body = json.dumps(SPA)
    elif "/permissions" in u: body = json.dumps(PERMS)
    elif "/dayboard/" + today in u: body = json.dumps(DAYBOARD)
    elif "/dayboard/" in u: body = "null"
    elif "/cards.json" in u: body = json.dumps(CARDS) if CARDS else "null"
    elif "/cutrun" in u: body = json.dumps(CUTRUN) if CUTRUN else "null"
    elif u.split("?")[0].endswith("/stays.json"):
        # loadPreSms' one ranged read over the window, orderBy="$key". The
        # window is today's arrivals plus the WINDOW days; return the nights
        # whose keys fall inside [startAt, endAt].
        from urllib.parse import urlparse, parse_qs, unquote
        q = parse_qs(urlparse(u).query)
        lo = unquote(q.get("startAt", ['""'])[0]).strip('"')
        hi = unquote(q.get("endAt", ['"￿"'])[0]).strip('"')
        allstays = dict(WINDOW); allstays[today] = STAYS
        win = {k: v for k, v in allstays.items() if lo <= k <= hi}
        body = json.dumps(win) if win else "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u:
        d = u.split("/stays/")[1].split(".json")[0]
        body = json.dumps(WINDOW[d]) if d in WINDOW else "null"
    elif u.split("?")[0].endswith("/bookings.json"):
        # loadPreSms reads prearrival from the whole node now, not per booking.
        # Same records the per-id /prearrival branch below serves (PRE + WPRE).
        node = {}
        for bid, p in list(PRE.items()) + list(WPRE.items()):
            node[bid] = {"prearrival": p}
        for bid, pm in PMS.items():
            node.setdefault(bid, {})["pms"] = pm
        body = json.dumps(node)
    elif u.split("?")[0].endswith("/previnvites.json"):
        body = json.dumps(WPREINV)
    elif u.split("?")[0].endswith("/phonefix.json"):
        body = "null"
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/dinner/" in u: body = "null"
    elif "/manual/" + today in u: body = json.dumps(MANUAL)
    elif "/responses/" + today in u: body = json.dumps(RESPONSES)
    elif "/responses/" in u: body = "null"
    elif "/manual/" in u: body = "null"
    elif "/invites/" + today in u: body = json.dumps(INVITES)
    elif "/invites/" in u: body = "null"
    elif "/previnvites/" in u:
        bid = u.split("/previnvites/")[1].split(".json")[0]
        body = json.dumps(WPREINV[bid]) if bid in WPREINV else "null"
    elif "/phonefix/" in u: body = "null"
    elif "/menu" in u: body = json.dumps(MENU_NOW["m"])
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = (json.dumps(PRE[k]) if k in PRE
                else json.dumps(WPRE[k]) if k in WPRE else "null")
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)) if not cond and detail else ""))
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── rule 7: the page gathers, it does not work things out ──────────
# CLAUDE.md rule 7. Every value on this page belongs to something else, and
# dashboard_sources.json names the owner. Prose did not stop four bugs of
# this shape in two days, so it gets a runner: the page must call each
# reader, and must not contain the patterns that caused them.
SRC = json.load(open("/home/claude/nala/tests/dashboard_sources.json"))
PAGE = open("/home/claude/nala/dashboard.html").read()

for r in SRC["reads"]:
    needle = r["owner"] + "(" if r["kind"] == "function" else r["owner"]
    ck("the page reads %s through %s, rather than working it out"
       % (r["value"][:44], r["owner"]), needle in PAGE)

for b in SRC["banned"]:
    ck("the page does not use %s" % b["pattern"], b["pattern"] not in PAGE)

# The one fact it does own has to be written somewhere, or the ticks have
# nowhere to live.
ck("and the one fact it owns is written where the manifest says",
   SRC["owns"][0]["path"].replace("<date>", "") in PAGE.replace("' + nav.todayKey() + '", ""))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(email="staff@x", w=390, date=None, clock=None):
        pg = b.new_page(viewport={"width": w, "height": 900})
        #  Held only where the hour decides the answer: a spa reminder is
        #  owed until its treatment begins, and not after.
        if clock: pg.clock.set_fixed_time(clock)
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
    #  Twelve since 29 Sep: Chat's card joined Arrivals off the spine.
    #  (Eleven when Pre-arrival SMS joined the top of it, 22 Sep; ten when
    #  Key cards joined beside Arrival sheets, 8 Sep.)
    ck("the board renders its cards",
       pg.evaluate("()=>document.querySelectorAll('.node').length") == 12)
    ck("the date row shows the day, so the board says which day it is",
       pg.evaluate("()=>document.getElementById('title').textContent.trim()") != "")

    # The menu is filled by buildNav in nala-shared.js, but opened by three
    # lines every page carries its own copy of. This page shipped without
    # them, so the hamburger drew and did nothing.
    ck("the menu is built, with links in it",
       pg.evaluate("()=>document.querySelectorAll('#navDrop a').length") > 3)
    pg.locator("#tab-menu:visible, #navBtn:visible").first.click()
    pg.wait_for_timeout(150)
    ck("and the hamburger opens it",
       pg.evaluate("()=>document.getElementById('navDrop').classList.contains('open')"))
    #  On the date, which is plain type and beside the menu rather than
    #  under it: the middle of #board is wherever the cards put it, and once
    #  the Refresh row went (30 Sep) it was the FOH Sheet's print link, so
    #  the tap went there instead. Where the tab bar opens the menu from the
    #  foot (30 Sep) the page wears a shade while it is open, and the tap
    #  lands on that: it shuts the menu and presses nothing under it.
    #  Its corner, not its middle: the menu itself rises over the middle.
    shade = pg.locator("#menuShade:visible")
    if shade.count(): shade.click(position={"x": 12, "y": 12})
    else: pg.click("#title")
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
    #  The massage answer can live at /spa as an outcome since 10 Sep
    #  (massageAnswered, nala-shared.js): a stamped form holding dinner and
    #  dietary, with the massage booked on the Spa board rather than
    #  answered on the form, is complete. The desk reads it that way, so
    #  the chips here must say the same - b11 already holds a booked
    #  treatment in the SPA fixture above.
    savedPre = dict(PRE["b11"])
    PRE["b11"] = {"at": at(9, 50), "dining": True, "pax": 2, "noDiets": True}
    ng = board()
    ck("a massage booked on the Spa board completes the form chip too",
       "11:green" in card(ng, "forms")["chips"])
    ng.close()
    PRE["b11"] = savedPre

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
    # 4 staff-added + 3 digital = 7. The declined digital one does not count,
    # and the one WITH a room is a villa reply, not an external.
    ck("outside diners are added to the covers and shown as their own chip",
       "ext 7:green" in reps["chips"])
    ck("a table booked through a link counts the same as one added by staff",
       "ext 7:green" in reps["chips"])
    # The note said "needs the menu sent" on a day where nobody needed asking,
    # because it asked whether a send had happened rather than what was still
    # owed. A villa that has answered is not waiting on a menu.
    NO_ASK = {v: dict(DINNER.get(v, {}), status="in", pax=2)
              for v in ("3", "7", "11", "14", "5")}
    # And nothing was ever sent, because nobody needed asking - which is the
    # day this actually happened on.
    saved, savedInv = dict(DINNER), dict(INVITES)
    DINNER.clear(); DINNER.update(NO_ASK)
    INVITES.clear()
    na = board()
    r2 = card(na, "reps")
    ck("with every villa answered the replies card is done, not waiting",
       r2["pos"] == "past")
    ck("and it does not ask for a menu nobody is waiting on",
       "menu" not in r2["note"])
    ck("it says what was answered instead",
       "dining" in r2["note"] and "to answer" not in r2["note"])
    na.close()
    DINNER.clear(); DINNER.update(saved)
    INVITES.clear(); INVITES.update(savedInv)

    ck("covers count in-house yeses plus outside tables",
       reps["note"].startswith("13 dining so far"))
    ck("and a villa with no dinner state yet is still out, not forgotten",
       reps["note"].endswith("1 still to answer"))

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
    # A send the carrier accepted and the handset never got is not a send.
    # Invitations climbs it back into To send; the reconstruction this
    # replaced counted it as sent, so the villa read as invited and nobody
    # would have known until a guest was not asked.
    INVITES["11"] = {"status": "sent", "sentAt": at(10, 20),
                     "delivery": "failed", "deliveryText": "Unreachable"}
    fp = board()
    ck("a failed delivery is still to send, not sent",
       [c.split(":")[0] for c in card(fp, "inv")["chips"]] == ["11"])
    fp.close()
    INVITES["11"] = {"status": "sent", "sentAt": at(10, 20)}
    dp = board()
    ck("and a send with no failure on it is not asked again",
       not card(dp, "inv")["chips"])
    dp.close()
    del INVITES["11"]

    # A booking with no usable mobile cannot be sent anything, so it is not
    # waiting on a send: Invitations calls it Unsendable.
    STAYS["11"].pop("phone")
    np = board()
    ck("a villa with no mobile is not counted as one to send",
       not card(np, "inv")["chips"])
    np.close()
    STAYS["11"]["phone"] = "+61400000013"

    ck("and the header agrees with the card, not its own arithmetic",
       pg.evaluate("()=>document.getElementById('nInv').textContent") == "1")

    # ── a dinner cell whose booking has left the villa (villa 4, 19 Sep) ──
    #  The Reservations board drops a cell stamped with a booking that is no
    #  longer in the villa (dinnerElsewhere); this page read /dinner raw, so it
    #  counted the departed booking's "yes" as a cover AND left the new guest
    #  off the to-ask list - the same disagreement Invitations had, one node
    #  over. cellFor reads through cellIsForBooking now, so a stale cell falls
    #  through to the guest's own form answer exactly as Reservations does.
    STAYS_BAK, DINNER_BAK = dict(STAYS), dict(DINNER)
    STAYS["9"] = {"id": "b9-now", "first": "New", "last": "Guest",
                  "phone": "+61400000019", "arrive": today, "depart": plus(2),
                  "adults": 2}
    DINNER["9"] = {"status": "in", "pax": 2, "by": "reception",
                   "bookingId": "b9-was", "at": at(9, 43)}
    sp = board()
    ck("a stale dinner cell is not counted as a cover: the count holds at 13",
       card(sp, "reps")["note"].startswith("13 dining so far")
       and card(sp, "reps")["note"].endswith("2 still to answer"))
    ck("the departed booking's yes does not paint the new guest green",
       "9:green" not in card(sp, "reps")["chips"])
    ck("the new, unasked guest is named among those still to send to",
       "9:grey" in card(sp, "inv")["chips"])
    sp.close()
    STAYS.clear(); STAYS.update(STAYS_BAK)
    DINNER.clear(); DINNER.update(DINNER_BAK)

    # ── the menu count ──────────────────────────────────────────
    # 16 to print for. A menu is shared between two diners, two menus print
    # to a sheet, and reception keeps a menu of its own at the desk (owner,
    # 9-10 Sep): a part page rounds up and its slack is the spare, a whole
    # number takes an extra page. floor(16/4)+1 = 5.
    menus = card(pg, "menus")
    ck("an unanswered villa is still printed for, and a whole 16 takes the "
       "extra page for reception's menu",
       menus["note"].startswith("5 pages for 16 diners"))
    ck("and the note says how many of those are still unanswered",
       menus["note"].endswith("3 not answered yet"))

    # A part page already leaves slack, so it must NOT take a second spare:
    # 17 is 5 pages, the same 5 - not 6.
    MANUAL["ext-a"]["pax"] = 5
    rp = board()
    ck("a part page's round-up IS the spare: 17 diners is 5 pages, not 6",
       card(rp, "menus")["note"].startswith("5 pages for 17 diners"))
    rp.close()
    MANUAL["ext-a"]["pax"] = 4

    # An external guest invited by SMS (28 Sep) who has not answered is owed
    # a menu like an unanswered villa; one who declined is not; one who
    # accepted is already a diner. Read through extInvites and extInviteState,
    # the readers dashboard_sources.json names - never worked out here.
    MANUAL["ext-inv1"] = {"status": "awaiting", "pax": 2, "source": "invite",
                          "name": "Sarah Jones", "invitedAt": utc_at(6, 12)}
    MANUAL["ext-inv2"] = {"status": "out", "pax": 3, "source": "invite",
                          "name": "Lea Martin", "by": "guest", "at": utc_at(6, 40)}
    xp = board()
    xm = card(xp, "menus")["note"]
    ck("an invited guest still to answer joins the pile; a decline does not",
       xm.startswith("5 pages for 18 diners") and xm.endswith("5 not answered yet"))
    xp.close()
    del MANUAL["ext-inv1"]; del MANUAL["ext-inv2"]

    # ── the menu, and only tonight's ────────────────────────────
    MENU_NOW["m"] = STALE_MENU
    st = board()
    ck("last night's menu is not tonight's, however recently it was published",
       card(st, "menu")["note"] == "not published yet")
    st.close()
    MENU_NOW["m"] = dict(MENU, published=utc_at(9, 58))
    tz = board()
    ck("a menu published this morning reads as published, whatever zone the "
       "stamp is written in",
       tz.evaluate("()=>items(nowMins()).filter(d=>d.k=='menu')[0].note")
       .startswith("published"))
    tz.close()
    MENU_NOW["m"] = HALF_MENU
    hf = board()
    ck("and a menu with empty courses is not published either",
       card(hf, "menu")["note"] == "not published yet")
    hf.close()
    MENU_NOW["m"] = MENU

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
    pg.close()

    # Arrival sheets was given a tick to match the mockup and kept a state
    # that could only be ready or waiting, so it could be marked printed and
    # go on shouting.
    pg = board()
    pg.click("[data-mark='sheets']"); pg.wait_for_timeout(150)
    pg.click("[data-mark='sheets']"); pg.wait_for_timeout(500)
    pg.close()
    pg = board()
    ck("the arrival sheets card recedes when ticked, like the other two",
       card(pg, "sheets")["pos"] == "past")
    ck("and says it was printed, and by whom",
       card(pg, "sheets")["note"].startswith("printed")
       and "Ana" in card(pg, "sheets")["note"])
    pg.close()
    DAYBOARD.pop("sheets", None)
    pg = board()
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

    # ── the spa reminders, the morning text (28 Sep) ────────────
    #  The owner's rulings: a text to each guest on the morning of a booked
    #  treatment, sent by the desk from spa-reminders.html. This card listed
    #  today's treatments with a Mark done until then; it now says who is
    #  still owed a text, read through spaReminderRows - the sending page's
    #  own reader - and opens that page. The clock is held at 8:30, before
    #  any treatment begins, except where the hour is the point.
    pg = board(clock=at(8, 30))
    ck("the spa card sits just under the SMS card, above the flow",
       [c["k"] for c in cards(pg)][:2] == ["sms", "spa"])
    sp = card(pg, "spa")
    ck("today's booked treatments, in time order, each with its villa and "
       "wearing its reminder's state: 3 texted, 7 still to send",
       sp["chips"] == ["3 \u00b7 11:00 am:green", "7 \u00b7 2:30 pm:grey"])
    ck("a treatment booked for another day is not", "9:00 am" not in str(sp["chips"]))
    ck("nor is one only requested, which nobody is expecting a guest for",
       len(sp["chips"]) == 2)
    ck("the note says who is still owed a text", sp["note"] == "1 to send", sp["note"])
    ck("the card is named for its job and opens the page that sends",
       pg.evaluate("()=>HREF.spa") == "spa-reminders.html" and
       pg.evaluate("()=>NEED.spa") == "editBookings" and
       "Spa reminders" in pg.inner_text("[data-nav='spa']"))
    ck("while a text is owed it wears the amber edge of a job to chase",
       sp["pos"] == "open")
    ck("no Mark done any more: the send log says it, not a person",
       not pg.evaluate("()=>!!document.querySelector('[data-mark=\"spa\"]')") and
       not pg.evaluate("()=>!!document.querySelector('[data-print=\"spa\"]')"))
    ck("every chip's tone is spaReminderState's, not this page's",
       pg.evaluate("""()=>spaReminderRows(nav.todayKey(), DATA.spa, DATA.spareminders,
           DATA.stays, DATA.bookings, DATA.phonefix, Date.now()).map(x=>x.state).join()""")
       == "sent,ready")
    pg.close()

    def spa_card(clock=None):
        q = board(clock=clock or at(8, 30)); c = card(q, "spa"); q.close(); return c
    SAVED_REM, SAVED_PMS = json.loads(json.dumps(SPAREM)), json.loads(json.dumps(PMS))
    SPAREM["b7"] = {"t3": {"status": "failed", "sentAt": at(8, 5), "error": "INVALID_RECIPIENT",
                           "day": today, "time": "14:30", "qty": 2, "dur": 90, "dur2": 60}}
    c = spa_card()
    ck("a send that failed wears the red ring and is counted as failed",
       c["chips"][1] == "7 \u00b7 2:30 pm:fail" and c["note"] == "1 to send (1 failed)", c)
    SPAREM["b7"] = {"t3": {"status": "sent", "sentAt": at(8, 5), "providerId": "mid-7",
                           "day": today, "time": "13:00", "qty": 2, "dur": 90, "dur2": 60}}
    c = spa_card()
    ck("a booking moved since its text is amber, owed again",
       c["chips"][1] == "7 \u00b7 2:30 pm:amber" and c["note"] == "1 to send (1 changed)", c)
    SPAREM["b7"]["t3"]["time"] = "14:30"
    c = spa_card()
    ck("once everyone is texted the card sinks, done",
       c["chips"] == ["3 \u00b7 11:00 am:green", "7 \u00b7 2:30 pm:green"] and
       c["note"] == "all 2 reminded" and c["pos"] == "past", c)
    SPAREM.pop("b7"); PMS["b7"]["phone"] = "07 3358 1122"
    c = spa_card()
    ck("a guest with no mobile sinks rather than nags, and the card is done",
       c["chips"][1] == "7 \u00b7 2:30 pm:sunk" and c["pos"] == "past" and
       c["note"] == "all 1 reminded \u00b7 1 has no mobile", c)
    PMS["b7"]["phone"] = "+61 411 000 007"; SPAREM.pop("b3")
    c = spa_card(at(12, 0))
    ck("a treatment that began without a text sinks too, and says so",
       c["chips"] == ["3 \u00b7 11:00 am:sunk", "7 \u00b7 2:30 pm:grey"] and
       c["note"] == "1 to send \u00b7 1 began without one", c)
    SPAREM.clear(); SPAREM.update(SAVED_REM); PMS.clear(); PMS.update(SAVED_PMS)

    ch = board("chef@x", clock=at(8, 30))
    ck("a chef reads the card but has no door: sending answers to editBookings",
       not card(ch, "spa")["door"])
    ch.close()

    SAVED_SPA = dict(SPA)
    SPA.clear()
    ns = board()
    ck("and on a day with no treatments the card is not there at all",
       not [c for c in cards(ns) if c["k"] == "spa"])
    ns.close()
    SPA.clear(); SPA.update(SAVED_SPA)
    pg = board()

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

    # ── key cards ───────────────────────────────────────────────
    #  The card counts the table through cardsHeld and cardState (the
    #  shared readers, tests/cardstate_cases.json) and is a DOOR to
    #  Keys, which owns cutting and the register: an Encode button here
    #  would be this page originating an action it cannot watch, rule
    #  7's whole lesson. A villa is carded when it HOLDS rows - counted,
    #  never worked out (the model, 11 Sep).
    import time as _t
    live = int(_t.time()) + 2 * 86400
    pg = board()
    kc = card(pg, "cards")
    ck("key cards sit on the spine as a door to Keys",
       kc["door"] and kc["pos"] != "off"
       and pg.evaluate("()=>HREF.cards") == "keys.html")
    ck("with no rows it says so and every villa chip is grey",
       "none cut" in kc["note"]
       and sorted(kc["chips"]) == ["11:grey", "14:grey", "3:grey", "7:grey"])
    pg.close()

    #  a run on, one villa already holding, one failed in the queue
    CARDS.update({
        "903001": {"villa": "3", "guest": "G", "cut": 1, "expiry": live},
        "903002": {"villa": "3", "guest": "G", "cut": 2, "expiry": live},
    })
    CUTRUN.update({"state": "on", "queue": {
        "7":  {"guest": "G", "qty": 2, "cut": 1, "expiry": live},
        "11": {"guest": "G", "qty": 2, "cut": 0, "expiry": live,
               "note": "card write refused: not an IC card"},
    }})
    pg = board()
    kc = card(pg, "cards")
    ck("a failure outranks the count and names the villa",
       "write failed on villa 11" in kc["note"] and "Keys" in kc["note"])
    ck("held wears green, the run's villas amber, untouched stays grey",
       sorted(kc["chips"]) == ["11:amber", "14:grey", "3:green", "7:amber"])
    pg.close()
    CUTRUN.clear()

    #  every arrival holding rows: done, and the rows ARE the count
    CARDS.clear()
    for no, v in [("903001","3"),("903002","3"),("907001","7"),("907002","7"),
                  ("911001","11"),("911002","11"),("911003","11"),
                  ("914001","14"),("914002","14")]:
        CARDS[no] = {"villa": v, "guest": "G", "cut": 1, "expiry": live}
    pg = board()
    kc = card(pg, "cards")
    ck("all four villas carded reads done, with the row count",
       kc["pos"] == "past" and "9 cards cut" in kc["note"])
    pg.close()

    #  A lost card floats across dates until expiry, and the note carries
    #  it whatever the day's cutting looks like - cardState's word, the
    #  owner named in dashboard_sources.json.
    CARDS["903001"]["lost"] = True
    pg = board()
    kc = card(pg, "cards")
    ck("a floating lost card rides the note, pointing at Keys",
       "1 lost, floating - see Keys" in kc["note"])
    pg.close()
    CARDS.clear()

    # ── the pre-arrival SMS send-out, first on the board ────────
    #  The rolling 14-day queue, read through preSmsState (nala-shared.js) so
    #  this board and arrivals-sms.html cannot disagree about who is to send -
    #  rule 7, and dashboard_sources.json names preSmsState as the owner. The
    #  WINDOW fixture puts two villas in To send (6 and 15), one already sent
    #  (2), one with a completed form (4), and villa 8 who arrived yesterday
    #  and is only in house. Only the two unsent, sendable, un-engaged ones
    #  show, in villa order. Today's own arrivals (3, 7, 11, 14) are all done
    #  or opened, so none of them is to-send either.
    pg = board()
    ck("the pre-arrival SMS card is first on the board",
       [c["k"] for c in cards(pg)][0] == "sms")
    sms = card(pg, "sms")
    ck("only the villas still to send show, in villa order",
       [c.split(":")[0] for c in sms["chips"]] == ["6", "15"])
    ck("a failed send wears the red ring, a never-asked one stays grey",
       sms["chips"] == ["6:fail", "15:grey"])
    ck("a sent one, a completed one and an in-house arrival do not show",
       not any(c.split(":")[0] in ("2", "4", "8") for c in sms["chips"]))
    ck("the note counts them, flags the failure, and names the 14-day window",
       sms["note"] == "2 to send, 1 failed · arriving in the next 14 days")
    ck("it wears the amber to-do edge while anything is to send",
       sms["pos"] == "open")
    ck("and it is a door to the sending page, where recipients are chosen",
       sms["door"] and pg.evaluate("()=>HREF.sms") == "arrivals-sms.html")
    #  The OTHER pre-arrival card - Pre-arrival forms, further down - opens
    #  the Front Desk, where reception works today's arrivals. The two are
    #  distinct doors and were swapped once; this pins them apart.
    ck("the pre-arrival forms card opens the Front Desk, not the sending page",
       pg.evaluate("()=>HREF.forms") == "front-desk.html")
    ck("it carries no send control of its own - nothing is sent from here",
       not pg.evaluate("()=>!!document.querySelector("
                       "'[data-print=\"sms\"],[data-mark=\"sms\"]')"))
    pg.close()

    #  Nothing left to send: the card sinks green and says so, without
    #  implying there are no arrivals - there may be, all already sent.
    SAVED_WIN = dict(WINDOW)
    WINDOW.clear()
    pg = board()
    sms = card(pg, "sms")
    ck("with nothing to send the card recedes, green, not amber",
       sms["pos"] == "past")
    ck("and says so without claiming there are no arrivals",
       sms["note"] == "nothing to send · all within 14 days done")
    pg.close()
    WINDOW.clear(); WINDOW.update(SAVED_WIN)

    #  The shared table both screens answer to (tests/presms_cases.json): the
    #  send-state itself, proven on THIS page's copy of preSmsState so the two
    #  readers cannot drift. The same table is asserted in inv_suite.
    CASES = json.load(open("/home/claude/nala/tests/presms_cases.json"))["cases"]
    pg = board()
    bad = [c["name"] for c in CASES
           if pg.evaluate("c=>preSmsState(c.stay,c.pre,c.invite,c.fix,c.spa)", c)
              != c["state"]]
    ck("preSmsState agrees with the shared table on every case (%d)" % len(CASES),
       not bad)
    badf = [c["name"] for c in CASES
            if pg.evaluate("c=>preSmsFailed(c.invite)", c) != c["failed"]]
    ck("preSmsFailed agrees with the shared table on every case",
       not badf)
    pg.close()

    # ── Chat's card (29 Sep; Guest messages until 30 Sep) ─────────────────────────────────
    #  Two counts, each from its owner: /contactnew's keys, and
    #  contactOpenTasks over contactTeams - a retired team's open task
    #  counted, a done one not.
    pg = board()
    gm = card(pg, "contact")
    ck("Chat's card counts the guests with a message to sort, and the open tasks",
       gm["note"] == "2 guests have messages to sort · 2 tasks open", gm)
    ck("off the spine, like Arrivals, a door to Chat for the desk",
       gm["pos"] == "off" and gm["door"] and
       pg.evaluate("()=>HREF.contact") == "guest-contact.html", gm)
    pg.close()
    pg = board(date=plus(-1))
    ck("and on another day's board it is not there: the counts are now's",
       not [c for c in cards(pg) if c["k"] == "contact"])
    pg.close()
    #  Shut (PREVIEW_PAGES, 29 Sep), the card is the admin's alone, like
    #  the page it counts; opened in Settings, the desk's too.
    pg = board(email="waiter@x")
    ck("while Chat is the admin's alone, the waiter's board has no card",
       not [c for c in cards(pg) if c["k"] == "contact"])
    pg.close()
    PERMS["open"] = {"guest-contact": True, "tasks": True}
    pg = board(email="waiter@x")
    ck("opened to the staff, the waiter's has it, and its door",
       [c["door"] for c in cards(pg) if c["k"] == "contact"] == [True])
    pg.close()
    del PERMS["open"]
    STATE["contactfail"] = True
    pg = board()
    ck("a login the rules keep from the guests' messages gets no card, and no error",
       not [c for c in cards(pg) if c["k"] == "contact"] and
       pg.evaluate("()=>document.querySelectorAll('.node').length") == 11)
    pg.close()
    STATE["contactfail"] = False
    SAVED_NEW = dict(CONTACT_NEW); CONTACT_NEW.clear()
    SAVED_TASKS = json.loads(json.dumps(CONTACT_TASKS)); CONTACT_TASKS.clear()
    pg = board()
    ck("and with nothing waiting it says so",
       card(pg, "contact")["note"] == "nothing new to sort · no task open")
    pg.close()
    CONTACT_NEW.update(SAVED_NEW); CONTACT_TASKS.update(SAVED_TASKS)

    # ── width ───────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = board(w=w)
        over = pg.evaluate("()=>document.documentElement.scrollWidth - "
                           "document.documentElement.clientWidth")
        ck("nothing bleeds sideways at %d" % w, over <= 0)
        pg.close()

    b.close()

httpd.shutdown()
# RESULT:, the shape run.py greps for. Without the prefix this suite scored
# NO RESULT on every pooled run - 81 green assertions nobody could see, and
# a real break here would have been waved through the same way.
print("\nRESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
