"""guest.html, one booking's whole story.

The profile owns nothing. Every fact on it is read from the thing that
already owns it, and tests/guest_sources.json names the owners - this suite
asserts the page calls each one and carries none of the banned patterns.
Beyond that, the readings worth pinning:

  1. The dinner row is the boards' merge: the /dinner cell wins the moment
     anyone writes one, the form's answer stands in on the arrival night.
  2. The dining history follows the BOOKING id through /stays: a night the
     villa held somebody else's booking is not this guest's history.
  3. The tab borders and the Stay tab's fill are the approved vocabulary,
     asserted by computed colour where a colour is a contract.
  4. Doors are gated by the permission the page behind them answers to,
     through NAV_NEEDS - a chef sees Reservations, never Front Desk.
  5. The page answers to resBoard: housekeeping is routed home, not told off.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8987), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

now = datetime.datetime.now().astimezone()
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
today = plus(0)

STAFF = {"staff@x":        {"name": "Ana",  "role": "staff"},
         "chef@x":         {"name": "Marco", "role": "chef"},
         "waiter@x":       {"name": "Tui",  "role": "waiter"},
         "housekeeping@x": {"name": "Mere", "role": "housekeeping"}}

# One rich booking mid-stay, one fresh Mews sync with nothing answered.
BK = {
 "b8": {"pms": {"first": "Lynette", "last": "Bunker", "phone": "+61 400 512 887",
                "arrive": plus(-2), "depart": plus(1), "adults": 2,
                "companion": "Peter Bunker", "groupId": "g1",
                "number": "RES-48213", "customerId": "c77", "villa": "8"},
        "prearrival": {"at": now.isoformat(), "dining": True, "pax": 2,
                       "diets": ["Shellfish allergy", "No pork"],
                       "dnote": "Carries an EpiPen.",
                       "purpose": "A mix of relaxing and exploring",
                       "approach": "most", "arriveSlot": "1530",
                       "note": "Anniversary on the Sunday.", "wellness": True,
                       "checkedInAt": now.isoformat(), "forCustomerId": "c77"}},
 "b17": {"pms": {"first": "Kim", "last": "Vlahov", "phone": "+61 419 774 902",
                 "arrive": plus(3), "depart": plus(7), "adults": 2,
                 "number": "RES-48412", "villa": "17"}}
}
PRE_BY_ID = {k: v.get("prearrival") for k, v in BK.items()}
NIGHT = {"8": {"id": "b8", "first": "Lynette", "last": "Bunker",
               "arrive": plus(-2), "depart": plus(1), "adults": 2, "groupId": "g1"},
         "9": {"id": "b9", "first": "Grp", "last": "Mate",
               "arrive": plus(-2), "depart": plus(1), "groupId": "g1"}}
# tonight's cell says OUT although the form said dining: the cell must win
DINNER = {"8": {"status": "out", "pax": 0, "by": "guest", "bookingId": "b8"}}
SPA = {"b8": {"t1": {"status": "booked", "day": today, "time": "14:00", "dur": 60, "qty": 2},
              "t2": {"status": "suggested", "day": plus(1), "time": "10:00"}}}
CARDS = {"101": {"villa": "8", "guest": "Lynette", "cut": 1,
                 "expiry": int((now + datetime.timedelta(days=1)).replace(hour=13, minute=0).timestamp())},
         "102": {"villa": "8", "guest": "Peter", "cut": 2,
                 "expiry": int((now + datetime.timedelta(days=1)).replace(hour=13, minute=0).timestamp())}}
GUESTS = {"c77": {"diets": ["Shellfish allergy"], "updatedAt": now.isoformat()}}
FLAGS8 = {"Anniversary": True}
MENUH = {"entree": "Kingfish crudo, lime", "main": "Lamb rump, smoked eggplant",
         "dessert": "Coconut pavlova"}
# night -2: the guest dined. night -1: the villa held ANOTHER booking whose
# guest dined - it must not count as b8's history.
HIST_STAYS = {plus(-2): {"8": {"id": "b8", "arrive": plus(-2), "depart": plus(1)}},
              plus(-1): {"8": {"id": "bOTHER", "arrive": plus(-1), "depart": today}}}
HIST_DINNER = {plus(-2): {"8": {"status": "in", "pax": 2, "bookingId": "b8"}},
               plus(-1): {"8": {"status": "in", "pax": 2, "bookingId": "bOTHER"}}}

def fb(route, request):
    u = request.url
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE_BY_ID[k]) if PRE_BY_ID.get(k) else "null"
    elif "/bookings/" in u:
        k = u.split("/bookings/")[1].split(".json")[0]
        body = json.dumps(BK[k]) if k in BK else "null"
    elif "/spa/" in u:
        k = u.split("/spa/")[1].split(".json")[0]
        body = json.dumps(SPA[k]) if k in SPA else "null"
    elif "/cards" in u: body = json.dumps(CARDS)
    elif "/bookflags/b8" in u: body = json.dumps(FLAGS8)
    elif "/guests/c77" in u: body = json.dumps(GUESTS["c77"])
    elif "/stays/" in u:
        k = u.split("/stays/")[1].split(".json")[0]
        if k == today: body = json.dumps(NIGHT)
        elif k in HIST_STAYS: body = json.dumps(HIST_STAYS[k])
    elif "/dinner/" in u:
        k = u.split("/dinner/")[1].split(".json")[0]
        if k == today: body = json.dumps(DINNER)
        elif k in HIST_DINNER: body = json.dumps(HIST_DINNER[k])
    elif "/opened/" in u: body = "null"
    elif "/menuhistory/" in u: body = json.dumps(MENUH)
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── rule 7: the page gathers, it does not work things out ──────────
SRC = json.load(open("/home/claude/nala/tests/guest_sources.json"))
PAGE = open("/home/claude/nala/guest.html").read()
for r in SRC["reads"]:
    needle = r["owner"] + "(" if r["kind"] == "function" else r["owner"]
    ck("the page reads %s through %s" % (r["value"][:44], r["owner"]),
       needle in PAGE)
for b in SRC["banned"]:
    ck("the page does not use %s" % b["pattern"], b["pattern"] not in PAGE)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def profile(bid="b8", email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8987/guest.html?b=" + bid)
        pg.wait_for_timeout(1700)
        return pg

    def text(pg, sel):
        return pg.eval_on_selector(sel, "e=>e.textContent.replace(/\\s+/g,' ').trim()")
    def tabcls(pg):
        return pg.eval_on_selector_all(".tab", "els=>els.map(e=>e.className)")

    # ── the rich booking ────────────────────────────────────────
    pg = profile()
    ck("the header names the villa and the stay in one line",
       "Villa 8" in text(pg, "#who") and "3 nights" in text(pg, "#who"))
    ck("the companion rides under the name, companionOf's reading",
       "with Peter Bunker" in text(pg, "#who"))
    ck("checked in shows, isArrived's reading, never the raw stamp",
       "Checked in" in text(pg, "#who"))
    ck("the party's other villa is named in groupMatesText's wording",
       "with villa 9" in text(pg, "#who")
       and "villa 9" in text(pg, "#pGuest"))
    cls = tabcls(pg)
    ck("the Stay tab wears the completed form's green FILL",
       "fdone" in cls[1])
    ck("the Dining tab border is red: an allergy lives inside",
       "red" in cls[2])
    ck("the Spa tab is amber: a suggestion outranks the booking, "
       "massageState's precedence", "amber" in cls[3])
    #  the green fill is a contract colour, asserted by computed value
    fill = pg.eval_on_selector("#tStay", "e=>getComputedStyle(e).backgroundColor")
    ck("the Stay fill is the boards' dining green, by computed colour",
       fill == "rgba(122, 160, 130, 0.26)")

    pg.click("#tDine")
    ck("the cell wins over the form: tonight reads Not dining",
       "Not dining" in text(pg, "#pDine"))
    ck("the dietaries carry the allergy as the solid red pill",
       pg.eval_on_selector(".dp.al", "e=>getComputedStyle(e).backgroundColor")
       == "rgb(168, 50, 30)")
    ck("another booking's night is not this guest's history",
       "Dined 1 of 2 nights" in text(pg, "#pDine"))
    ck("and the courses served show the dish before the first comma",
       "Kingfish crudo" in text(pg, "#pDine") and "lime" not in text(pg, "#pDine"))
    pg.click("#tStay")
    ck("the key cards line counts the table through cardsHeld",
       "2 held" in text(pg, "#pStay"))
    ck("the flags a booking carries paint as pills",
       "Anniversary" in text(pg, "#pStay"))
    # an admin holds every key, so every door shows
    ck("the admin sees the Front Desk door",
       "Front Desk" in text(pg, "#pStay"))
    pg.close()

    # ── doors are gated by the page behind them ─────────────────
    pg = profile(email="chef@x")
    ck("the chef sees no Front Desk door - editBookings gates it",
       "Front Desk" not in text(pg, "#pStay"))
    pg.click("#tDine")
    ck("but does see Reservations, which answers to resBoard",
       "Reservations" in text(pg, "#pDine"))
    pg.click("#tSpa")
    ck("and no Spa door - spaBoard gates it",
       "Open in" not in text(pg, "#pSpa") or "Spa" not in
       pg.eval_on_selector_all("#pSpa .door", "els=>els.map(e=>e.textContent).join()"))
    pg.close()

    # ── the fresh booking ───────────────────────────────────────
    pg = profile(bid="b17")
    ck("a fresh booking's Stay pill reads not started",
       "Form not started" in text(pg, "#pStay"))
    cls = tabcls(pg)
    ck("its Stay tab holds no fill and its Dining and Spa tabs stay pale",
       "fdone" not in cls[1] and "fpart" not in cls[1]
       and "red" not in cls[2] and "has" not in cls[2]
       and cls[3].strip() == "tab")
    ck("the door leads with sending the link",
       "send the link" in text(pg, "#pStay"))
    ck("the arrival row names the 2pm standing promise",
       "standing promise" in text(pg, "#pStay"))
    pg.close()

    # ── access ──────────────────────────────────────────────────
    pg = profile(email="housekeeping@x")
    ck("housekeeping is routed home, not told off",
       pg.url.endswith("cleaners.html"))
    pg.close()

    # ── width ───────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = profile(w=w)
        over = pg.evaluate("()=>document.documentElement.scrollWidth - "
                           "document.documentElement.clientWidth")
        ck("nothing bleeds sideways at %d" % w, over <= 0)
        pg.close()

    b.close()

httpd.shutdown()
print("\nRESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
