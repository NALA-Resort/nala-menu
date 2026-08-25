"""spa.html, the Spa board.

The masseuse's single screen, and the desk's window into it. The three
things most worth pinning down:

  1. The state machine IS the feature: requested, suggested, booked,
     declined, each a colour, and who may move a record between them. A tap
     that writes the wrong state re-creates the text-message loop this page
     replaces.
  2. The day control never offers a day outside the guest's stay. That is
     the one guard the owner asked for by name.
  3. A pre-arrival request with no /spa record yet must still show - the
     masseuse answers requests that exist nowhere but the guest's form.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os, re

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8980), Q)
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
def short(d):
    t = now + datetime.timedelta(days=d)
    return t.strftime("%a ") + str(t.day)

STAFF = {"staff@x":    {"name": "Admin",    "role": "admin"},
         "masseuse@x": {"name": "Masseuse", "role": "spa"},
         "chef@x":     {"name": "Chef",     "role": "chef"}}

# villa, name, first night, last night (the depart day holds no stay row)
BOOKINGS = [
  # the form's request, answered by nobody yet: must appear from thin air
  ("9",  "b9",  "Sofia",  "Marino",  0, 4),
  # the masseuse offered a different time; amber until the desk approves
  ("12", "b12", "Elena",  "Petrov",  -1, 3),
  # booked, exactly as asked
  ("3",  "b3",  "Robyn",  "Carter",  -1, 2),
  # declined: nothing free
  ("7",  "b7",  "James",  "Okafor",  -2, 2),
  # a future request, sitting on its own day rather than today's board
  ("4",  "b4",  "Kai",    "Werner",  2, 5),
  # interested on the form but never picked a day
  ("15", "b15", "Anna",   "Lindqvist", 5, 7),
  # said no thank you on the form
  ("2",  "b2",  "Marco",  "Reyes",   -1, 1),
  # never answered the form at all
  ("6",  "b6",  "Harper", "Quinn",   0, 2),
]

STAYS_BY_DATE = {}
for v, bid, first, last, a, dep in BOOKINGS:
    for n in range(a, dep):
        STAYS_BY_DATE.setdefault(plus(n), {})[v] = {
            "id": bid, "first": first, "last": last,
            "arrive": plus(a), "depart": plus(dep), "adults": 2}

PRE = {
  "b9":  {"wellness": True,  "wellDay": today,   "wellTime": "afternoon"},
  "b12": {"wellness": True,  "wellDay": plus(-1),"wellTime": "morning"},
  "b4":  {"wellness": True,  "wellDay": plus(3), "wellTime": ""},
  "b15": {"wellness": True,  "wellDay": "",      "wellTime": ""},
  "b2":  {"wellness": False},
}

def spa_seed():
    return {
      "b12": {"t1": {"status": "suggested", "day": today, "time": "16:30",
                     "reqDay": plus(-1), "reqTime": "morning",
                     "name": "Elena Petrov", "source": "prearrival",
                     "by": "masseuse@x", "at": "2026-08-20T10:00:00Z"}},
      "b3":  {"t1": {"status": "booked", "day": today, "time": "11:00",
                     "reqDay": today, "reqTime": "late morning",
                     "name": "Robyn Carter", "source": "prearrival",
                     "by": "masseuse@x", "at": "2026-08-20T10:00:00Z"}},
      "b7":  {"t1": {"status": "declined",
                     "reqDay": today, "reqTime": "morning",
                     "note": "nothing free", "name": "James Okafor",
                     "source": "prearrival",
                     "by": "masseuse@x", "at": "2026-08-20T10:00:00Z"}},
    }
SPA = spa_seed()

WRITES = []
STATE = {"fail": False}

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        # the page reloads after a save; fold the write in so it shows
        mm = re.search(r"/spa/([^/]+)/([^/.]+)\.json", u)
        if mm:
            SPA.setdefault(mm.group(1), {})[mm.group(2)] = json.loads(request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/spa.json" in u: body = json.dumps(SPA)
    elif "/stays/" in u:
        d = u.split("/stays/")[1].split(".json")[0]
        body = json.dumps(STAYS_BY_DATE.get(d)) if d in STAYS_BY_DATE else "null"
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

    def board(email="masseuse@x", w=390, qs=""):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8980/spa.html" + qs)
        pg.wait_for_timeout(1600)
        return pg

    # ── the day board, all four states at once ──────────────────
    pg = board()
    def bands(page, sel="#board"):
        return page.evaluate("""(s)=>[...document.querySelectorAll(s+' .grp')]
            .map(e=>e.textContent)""", sel)
    got = bands(pg)
    ck("today shows all four bands, one item each",
       got == ["To answer · 1", "Suggested · waiting on the guest · 1",
               "Booked · 1", "Declined · 1"])
    ck("the request from the form appears with no /spa record behind it",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b9\"]')"
                   "?.dataset.status") == "requested")
    ck("each state wears its colour",
       pg.evaluate("""()=>{
         const c=(id)=>document.querySelector('#board [data-booking=\"'+id+'\"]').className;
         return c('b12').includes('b-sugg') && c('b3').includes('b-done') &&
                c('b7').includes('b-decl');}"""))
    ck("a booked treatment made no secret of being exactly what was asked",
       "as requested" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b3\"] .st').textContent"))
    ck("a suggestion shows both sides of the conversation",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b12\"] .st').textContent")
         .startswith("Suggested") and
       "asked for" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b12\"] .st').textContent"))
    ck("a decline tells the desk what to do about it",
       "let the guest know" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b7\"] .st').textContent"))
    ck("the villa number leads every tile",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b3\"] .v').textContent") == "3")

    # The stats are the masseuse's whole queue, not today's slice: b9 today,
    # b4 in two days, b15 with no day picked - all waiting on him.
    ck("To answer counts every open ask on the horizon",
       pg.evaluate("()=>nAsk.textContent") == "3")
    ck("Suggested counts what waits on the guest",
       pg.evaluate("()=>nSugg.textContent") == "1")
    ck("Booked today counts the day being looked at",
       pg.evaluate("()=>nDay.textContent") == "1")

    # ── the open card: the stay bounds the day control ──────────
    pg.locator('#board [data-booking="b9"]').click()
    pg.wait_for_timeout(300)
    chips = pg.evaluate("()=>[...document.querySelectorAll('.card .chip')].map(e=>e.textContent)")
    ck("the day chips are the guest's stay and nothing else",
       chips == [short(0), short(1), short(2), short(3), short(4)])
    ck("the time picker runs nine to five on the half hour",
       pg.evaluate("()=>[...document.querySelectorAll('.card option')].length") == 17 and
       pg.evaluate("()=>document.querySelector('.card option').textContent") == "9:00 am" and
       pg.evaluate("()=>[...document.querySelectorAll('.card option')].pop().textContent") == "5:00 pm")
    ck("on the day the guest asked for, Confirm leads",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         .startswith("Confirm"))

    # A different day turns the primary into a suggestion. The masseuse
    # cannot book a moved treatment behind the guest's back.
    pg.locator('.card .chip').nth(1).click()
    pg.wait_for_timeout(200)
    ck("a different day can only be suggested",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         .startswith("Suggest") and
       pg.evaluate("()=>[...document.querySelectorAll('.card .cbtn')]"
                   ".every(b=>!b.textContent.startsWith('Confirm'))"))

    # ── the writes, which are the actual feature ────────────────
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("suggesting writes one whole record to /spa/<booking>",
       len(w) == 1 and w[0]["m"] == "PUT")
    ck("with the suggestion and the guest's original ask side by side",
       body.get("status") == "suggested" and body.get("day") == plus(1) and
       body.get("reqDay") == today and body.get("reqTime") == "afternoon")
    ck("born from the form, so the ask stops showing as pending",
       body.get("source") == "prearrival")
    ck("and the board reflects it without a hand refresh",
       pg.evaluate("()=>nAsk.textContent") == "2")
    SPA = spa_seed()

    # Confirming on the asked-for day books it directly.
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click()   # Confirm, day untouched
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("confirming as asked books it in one tap",
       body.get("status") == "booked" and body.get("day") == today)
    SPA = spa_seed()

    # Declining writes the red record.
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]
    pg.locator('.card .cbtn', has_text="Decline").click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("declining writes declined, keeping the ask for the record",
       body.get("status") == "declined" and body.get("reqDay") == today)
    SPA = spa_seed()

    # ── the desk's half: approving a suggestion ─────────────────
    pg = board("staff@x")
    pg.locator('#board [data-booking="b12"]').click(); pg.wait_for_timeout(300)
    ck("the desk is offered Approve on an untouched suggestion",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         .startswith("Approve"))
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b12/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("approving books the suggested day and time, nothing else",
       body.get("status") == "booked" and body.get("day") == today and
       body.get("time") == "16:30")
    ck("and the guest's original ask survives the approval",
       body.get("reqDay") == plus(-1) and body.get("reqTime") == "morning")
    SPA = spa_seed()

    # The desk changing the day does NOT book: it goes back to the masseuse.
    pg = board("staff@x")
    pg.locator('#board [data-booking="b12"]').click(); pg.wait_for_timeout(300)
    pg.locator('.card .chip').nth(2).click(); pg.wait_for_timeout(200)
    ck("a changed suggestion can only be asked again",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         .startswith("Ask again"))
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b12/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("asking again writes requested with the new ask",
       body.get("status") == "requested" and body.get("reqDay") == plus(2))
    SPA = spa_seed()

    # ── the masseuse cannot approve his own suggestion ──────────
    pg = board()
    pg.locator('#board [data-booking="b12"]').click(); pg.wait_for_timeout(300)
    ck("no Approve exists on the masseuse's own screen",
       pg.evaluate("()=>[...document.querySelectorAll('.card .cbtn')]"
                   ".every(b=>!b.textContent.startsWith('Approve'))"))
    pg.close()

    # ── browsing a day: the future request sits on its own day ──
    pg = board(qs="?date=" + plus(3))
    ck("a future ask shows on the day it is for, not on today",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b4\"]')"
                   "?.dataset.status") == "requested")
    ck("and the board says which day the count is for",
       pg.evaluate("()=>nDay.nextElementSibling.textContent") == "Booked this day")
    pg.close()

    # ── all bookings: the masseuse sees only the guests who want him ──
    # A stay with no request is none of an outside contractor's business,
    # the owner ruled, 25 Aug. His horizon ends at Declined; the grey
    # no-treatment tiles, D. Kessler's no-thank-you included, exist for the
    # desk alone, and with them goes his add path - the desk adds when a
    # guest asks in person.
    pg = board()
    pg.locator('#allBtn').click(); pg.wait_for_timeout(300)
    got = bands(pg, "#allBoard")
    ck("the masseuse's drop holds asks first and ends at Declined",
       got[0] == "Waiting for an answer · 3" and got[-1] == "Declined · 1")
    ck("no stay without a treatment shows for him at all",
       pg.evaluate("()=>document.querySelectorAll('#allBoard .b-grey').length") == 0 and
       not pg.evaluate("()=>!!document.querySelector('#allBoard [data-booking=\"b2\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#allBoard [data-booking=\"b6\"]')"))
    pg.close()

    # The desk keeps the whole horizon, no-treatment band included.
    pg = board("staff@x")
    pg.locator('#allBtn').click(); pg.wait_for_timeout(300)
    got = bands(pg, "#allBoard")
    ck("the desk's drop still ends with the no-treatment band",
       got[-1] == "No treatment · staying or arriving · 2")
    ck("a guest who said no thank you is named as such, not offered around",
       "no thank you" in pg.evaluate(
         "()=>document.querySelector('#allBoard [data-booking=\"b2\"] .st').textContent"))
    pg.close()

    # The desk's add asks the masseuse: the desk does not know his book.
    pg = board("staff@x")
    pg.locator('#allBtn').click(); pg.wait_for_timeout(300)
    pg.locator('#allBoard [data-booking="b6"]').click(); pg.wait_for_timeout(300)
    ck("the desk's add offers Ask the masseuse",
       "Ask the masseuse" in pg.evaluate(
         "()=>document.querySelector('.card .cbtn.solid').textContent"))
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b6/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("and writes requested, with the desk's pick as the ask",
       body.get("status") == "requested" and body.get("source") == "desk" and
       body.get("reqDay") and body.get("reqTime"))
    SPA = spa_seed()
    pg.close()

    # ── the numbers are filters ─────────────────────────────────
    # Tap a stat and the board is that queue alone; tap it again for the
    # whole day. To answer and Suggested filter across the horizon, like the
    # numbers they sit under; Booked keeps to the viewed day, like its label.
    pg = board()
    pg.locator('#statsRow .stat[data-f="requested"]').click(); pg.wait_for_timeout(200)
    ck("tapping To answer shows every open ask, future and day-less included",
       bands(pg) == ["Every open ask · 3"] and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b4\"]')") and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b15\"]')"))
    ck("and the pressed number wears the amber mark",
       pg.evaluate("()=>document.querySelector('.stat[data-f=\"requested\"]').className")
         == "stat on")
    pg.locator('#statsRow .stat[data-f="requested"]').click(); pg.wait_for_timeout(200)
    ck("tapping it again brings the whole day back",
       len(bands(pg)) == 4 and
       pg.evaluate("()=>document.querySelectorAll('#statsRow .stat.on').length") == 0)
    pg.locator('#statsRow .stat[data-f="suggested"]').click(); pg.wait_for_timeout(200)
    ck("Suggested filters to the amber queue",
       bands(pg) == ["Suggested · waiting on the guest · 1"])
    pg.locator('#statsRow .stat[data-f="booked"]').click(); pg.wait_for_timeout(200)
    ck("Booked filters to the day it is counting",
       bands(pg) == ["Booked · today · 1"])
    pg.close()

    # ── the action icon ─────────────────────────────────────────
    # The amber count beside Spa in every other page's menu: suggestions
    # waiting on the desk. Recomputed from /spa on each load, so it clears
    # itself the moment the queue is empty and never needs unsetting.
    def badge_on_pages():
        q = b.new_page(viewport={"width": 390, "height": 900})
        q.add_init_script(SDK)
        q.add_init_script("window.__EMAIL=%s;" % json.dumps("staff@x"))
        q.route("**firebasedatabase.app/**", fb)
        q.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        q.goto("http://localhost:8980/pages.html")
        q.wait_for_timeout(1600)
        v = q.evaluate("""()=>{
          const a=[...document.querySelectorAll('#navDrop a')]
            .find(x=>(x.getAttribute('href')||'')==='spa.html');
          const b2=a && a.querySelector('.navbadge');
          return b2 ? b2.textContent : null;}""")
        q.close()
        return v
    ck("the Spa entry carries the action icon with the waiting count",
       badge_on_pages() == "1")
    SPA = {k: v for k, v in spa_seed().items() if k != "b12"}
    ck("and no icon at all once nothing waits, rather than a zero",
       badge_on_pages() is None)
    SPA = spa_seed()

    # ── a write refused is said, not swallowed ──────────────────
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    STATE["fail"] = True
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    ck("a refused save is reported in words",
       "did not save" in pg.evaluate("()=>errBar.textContent"))
    STATE["fail"] = False
    pg.close()

    # ── who may stand here ──────────────────────────────────────
    q = board("chef@x")
    q.wait_for_timeout(600)
    ck("a chef is sent to their own board rather than shown the spa",
       not q.url.endswith("spa.html"))
    q.close()
    q = board("masseuse@x")
    ck("the masseuse lands here and stays", q.url.endswith("spa.html"))
    links = q.evaluate("""()=>[...document.querySelectorAll('#navDrop a')]
        .filter(a=>getComputedStyle(a).display!=='none')
        .map(a=>a.getAttribute('href')).filter(h=>h!=='#')""")
    ck("and the masseuse's menu offers no other page", links == [])
    q.close()

    # ── widths ──────────────────────────────────────────────────
    for w2 in (390, 360, 320):
        q = board(w=w2)
        q.locator('#board [data-booking="b9"]').click(); q.wait_for_timeout(300)
        q.locator('#allBtn').click(); q.wait_for_timeout(300)
        ck("no sideways scroll at %dpt, card and drop open" % w2, not q.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
