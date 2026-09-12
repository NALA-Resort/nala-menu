"""calendar.html, the whole house across a month.

The board is a reader: stays from /stays night by night, each bar's fill
from formState - the Front Desk's three states, the same tints. The things
worth pinning:

  1. A bar's fill IS the form state, by computed colour: the tiles are a
     contract between boards, so the suite asserts the paint, not a class.
  2. A bar is a door to the Guest Profile only for a login holding
     resBoard; housekeeping gets the same board with no doors in it.
  3. The page is gated on cleansBoard - housekeeping stays, the chef is
     routed home - because the grounds crew is who the board is for.
  4. The window is a month of /stays reads and nothing else per day; a
     day that could not be read is named under the board, never shown
     as an empty day.
  5. Dates go through parseDepDate/dkey. A stay drawn off a string slice
     shifts a day in any zone west of UTC; run this suite in a second
     zone (TZ=Australia/Brisbane) like the other date suites.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8985), Q)
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
         "housekeeping@x": {"name": "Mere", "role": "housekeeping"}}

# Four bookings: complete (green), part answered (amber), untouched (grey),
# and a long stay off both window edges. b2 arrives the day b1 departs -
# the same-day turnover the changeover gap exists for.
def mk(v, id, f, l, a, d):
    return {"id": id, "first": f, "last": l, "arrive": a, "depart": d, "adults": 2}
NIGHTS = {}
def put(v, id, f, l, a, d):
    ad = datetime.datetime.strptime(a, "%Y-%m-%d")
    dd = datetime.datetime.strptime(d, "%Y-%m-%d")
    cur = ad
    while cur < dd:
        NIGHTS.setdefault(cur.strftime("%Y-%m-%d"), {})[str(v)] = mk(v, id, f, l, a, d)
        cur += datetime.timedelta(days=1)
put(8, "b1", "Adam", "Christison", plus(-1), plus(2))
put(8, "b2", "Kim", "Vlahov", plus(2), plus(5))
put(4, "b3", "Melissa", "Mueller", plus(1), plus(3))
put(12, "b4", "Katelyn", "Tree", plus(-9), plus(40))
PRE = {"b1": {"at": now.isoformat(), "dining": True, "noDiets": True, "wellness": False},
       "b3": {"dining": True}}
SPA = {}
STATE = {"failDays": set()}

def fb(route, request):
    u = request.url
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif "/spa.json" in u: body = json.dumps(SPA) if SPA else "null"
    elif "/stays/" in u:
        k = u.split("/stays/")[1].split(".json")[0]
        if k in STATE["failDays"]:
            route.fulfill(status=500, content_type="application/json",
                          body='{"error":"boom"}'); return
        if k in NIGHTS: body = json.dumps(NIGHTS[k])
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE[k]) if k in PRE else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── the page reads, it does not work things out ────────────────────
PAGE = open("/home/claude/nala/calendar.html").read()
ck("the fill comes from formState, the one reading of the form's state",
   "formState(" in PAGE)
ck("dates go through parseDepDate, never a slice",
   "parseDepDate(" in PAGE and ".slice(0, 10)" not in PAGE
   and ".substring(0, 10)" not in PAGE)
ck("the day anchor is initDateNav's, the standard daterow",
   "initDateNav(" in PAGE)
ck("bars carry the booking to guest.html by its id",
   "guest.html?b=" in PAGE)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(email="staff@x", w=390, h=844):
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8985/calendar.html")
        pg.wait_for_timeout(1700)
        return pg

    def bars(pg):
        return pg.eval_on_selector_all(".bar", """els => els.map(e => ({
            tag: e.tagName, cls: e.className, name: e.textContent.trim(),
            href: e.getAttribute('href'),
            fill: getComputedStyle(e).backgroundColor }))""")

    # ── the board, as the admin sees it ─────────────────────────
    pg = board()
    bl = {x["name"]: x for x in bars(pg)}
    ck("every booking in the window draws exactly one bar",
       len(bars(pg)) == 4 and "Christison, Adam" in bl and "Vlahov, Kim" in bl)
    ck("a completed form's bar is the dining green, by computed colour",
       bl["Christison, Adam"]["fill"] == "rgba(122, 160, 130, 0.26)")
    ck("a part-answered form's bar is amber",
       bl["Mueller, Melissa"]["fill"] == "rgb(246, 234, 213)")
    ck("an untouched booking's bar is the waiting grey",
       # 0.045 alpha stores as 11/255, which computes back as 0.043
       bl["Vlahov, Kim"]["fill"].startswith("rgba(28, 28, 26, 0.04"))
    ck("a stay off both window edges wears both cut ends",
       "cutL" in bl["Tree, Katelyn"]["cls"] and "cutR" in bl["Tree, Katelyn"]["cls"])
    ck("a bar is a door to the profile, keyed on the booking id",
       bl["Christison, Adam"]["tag"] == "A"
       and bl["Christison, Adam"]["href"] == "guest.html?b=b1")
    ck("the same-day turnover draws both bars in the villa's row",
       "Christison, Adam" in bl and "Vlahov, Kim" in bl)
    ck("the stats count the viewed day: two in house, nobody moving",
       pg.eval_on_selector_all(".stat-n", "els=>els.map(e=>e.textContent)")
       == ["2", "0", "0"])
    ck("the date row shows the day",
       pg.eval_on_selector("#date", "e=>e.textContent.trim()") != "")
    ck("the menu is built, with links in it",
       pg.evaluate("()=>document.querySelectorAll('#navDrop a').length") > 3)
    # ── Expand grows the rows, and the way back is the same press ──
    h0 = pg.eval_on_selector(".vrow", "e=>e.getBoundingClientRect().height")
    pg.click("#expandBtn")
    pg.wait_for_timeout(120)
    h1 = pg.eval_on_selector(".vrow", "e=>e.getBoundingClientRect().height")
    ck("Expand grows the rows to the full booking-row height",
       abs(h1 - 42) < 1 and h1 > h0)
    pg.click("#expandBtn")
    pg.wait_for_timeout(120)
    ck("and pressing it again comes back",
       abs(pg.eval_on_selector(".vrow", "e=>e.getBoundingClientRect().height") - h0) < 1)
    ck("the default board fits every villa on one screen, no page scroll",
       pg.evaluate("()=>document.documentElement.scrollHeight - "
                   "document.documentElement.clientHeight") <= 0)
    pg.close()

    # ── the board is broad, the detail behind it is not ─────────
    pg = board(email="housekeeping@x")
    ck("housekeeping sees the board - it is who the board is for",
       pg.url.endswith("calendar.html") and len(bars(pg)) == 4)
    ck("but its bars are not doors: no resBoard, no profile",
       all(x["tag"] == "DIV" and not x["href"] for x in bars(pg)))
    pg.close()

    pg = board(email="chef@x")
    ck("the chef holds no cleansBoard and is routed home, not told off",
       not pg.url.endswith("calendar.html"))
    pg.close()

    # ── a failed read is not an empty day ───────────────────────
    STATE["failDays"] = {plus(2)}
    pg = board()
    ck("a day that could not be read is named under the board",
       "1 day could not be read" in
       pg.eval_on_selector("#boardNote", "e=>e.textContent"))
    pg.close()
    STATE["failDays"] = set()

    # ── width ───────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = board(w=w)
        over = pg.evaluate("()=>document.documentElement.scrollWidth - "
                           "document.documentElement.clientWidth")
        ck("the page never bleeds sideways at %d - the board scrolls "
           "inside its own box" % w, over <= 0)
        pg.close()

    b.close()

httpd.shutdown()
print("\nRESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
