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
  # a stay a month out whose form is already answered: the ask must show
  # TODAY, not when the date navigation reaches the stay - found live,
  # 27 Aug, when the board's 21-day read hid exactly this guest
  ("11", "b30", "Nadia",  "Faraj",   30, 33),
  # a later arrival with no request at all: the desk's search must reach
  # her when she emails about a massage, weeks before she could stand at
  # the desk
  ("16", "b45", "Priya",  "Nair",    20, 23),
]

STAYS_BY_DATE = {}
for v, bid, first, last, a, dep in BOOKINGS:
    for n in range(a, dep):
        STAYS_BY_DATE.setdefault(plus(n), {})[v] = {
            "id": bid, "first": first, "last": last,
            "arrive": plus(a), "depart": plus(dep), "adults": 2}
# Robyn Carter's second guest, as Mews sent it on every night of the stay.
for _d in STAYS_BY_DATE.values():
    if "3" in _d: _d["3"]["companion"] = "Dan Carter"

PRE = {
  # Kai Werner named his companion on the form; nothing from Mews for b4, so
  # the board is showing the pre-arrival copy.
  "b9":  {"wellness": True,  "wellDay": today,   "wellTime": "afternoon"},
  "b12": {"wellness": True,  "wellDay": plus(-1),"wellTime": "morning"},
  "b4":  {"wellness": True,  "wellDay": plus(3), "wellTime": "2:00 pm", "wellDur": 90,
          "companion": "Lena Werner"},
  "b15": {"wellness": True,  "wellDay": "",      "wellTime": "", "wellQty": 2, "wellDur": 90, "wellDur2": 60},
  "b2":  {"wellness": False},
  "b30": {"wellness": True,  "wellDay": plus(31), "wellTime": "morning"},
}

def spa_seed():
    return {
      "b12": {"t1": {"status": "suggested", "day": today, "time": "16:30", "dur": 60,
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
PUSHES = []   # what the page told the push Worker, one dict per event
STATE = {"fail": False}

def push_route(route, request):
    PUSHES.append(json.loads(request.post_data))
    route.fulfill(status=200, content_type="text/plain", body="ok")

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
    if "/spasettings" in u:
        body = json.dumps({"price60": 180, "price90": 250, "price120": 310})
    elif "/staff" in u: body = json.dumps(STAFF)
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
        pg.route("**nala-push**", push_route)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8980/spa.html" + qs)
        pg.wait_for_timeout(1600)
        return pg

    # ── the resting board is All: the whole horizon in bands ────
    pg = board()
    def bands(page, sel="#board"):
        return page.evaluate("""(s)=>[...document.querySelectorAll(s+' .grp')]
            .map(e=>e.textContent)""", sel)
    got = bands(pg)
    ck("All is pressed on arrival and holds every band",
       got == ["To answer · 4", "Suggested · waiting on the guest · 1",
               "Booked · 1", "Declined · 1"] and
       pg.evaluate("()=>document.querySelector('.stat[data-f=\"all\"]').className")
         == "stat on")
    ck("and its number counts every live tile it shows",
       pg.evaluate("()=>nAll.textContent") == "7")
    ck("the request from the form appears with no /spa record behind it",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b9\"]')"
                   "?.dataset.status") == "requested")
    # The regression itself: an answered form for a stay a month away is on
    # TODAY'S resting board. Before 27 Aug the board read 21 days plus the
    # viewed one, so this card existed only once the date navigation reached
    # its stay - which from the desk read as "locked to its date".
    ck("an ask for a stay a month out shows today, not on its date",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b30\"]')"
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
       "suggested instead of" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b12\"] .st').textContent") and
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b12\"] .when').textContent") != "")
    ck("a decline tells the desk what to do about it",
       "let the guest know" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b7\"] .st').textContent"))
    ck("the villa number leads every tile",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b3\"] .v').textContent") == "3")

    # ── the tile's anatomy, ruled 27 Aug ────────────────────────
    # The when sits beside the name and says the month - a bare "Wed 2"
    # past the month's edge is nobody's Wednesday. One kind of fact per
    # line, and no line wraps; the card holds the whole story.
    def nice(n):
        d = now + datetime.timedelta(days=n)
        day = d.day
        suf = "th" if 11 <= day % 100 <= 13 else {1:"st",2:"nd",3:"rd"}.get(day % 10, "th")
        return d.strftime("%a ") + str(day) + suf + d.strftime(" %b")
    ck("the when sits beside the name and names the month",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b3\"] .top .when').textContent")
       == nice(0) + " · 11:00 am")
    #  Was pinned to rgb(28, 28, 26), the old --ink. The ruling is that the
    #  line wears INK and never the band's own colour, which is a statement
    #  about tokens, so it is read from the token and survives a restyle.
    ck("and wears ink on every band, never the band's colour",
       pg.evaluate("""()=>{const probe=v=>{const e=document.createElement('span');
            e.style.color='var('+v+')';document.body.appendChild(e);
            const c=getComputedStyle(e).color;e.remove();return c;};
          const ink=probe('--ink');
          return ['b3','b12','b7','b9'].every(id=>
            getComputedStyle(document.querySelector(
              '#board [data-booking="'+id+'"] .when')).color===ink);}"""))
    ck("no tile line wraps - each is one ellipsised row",
       pg.evaluate("()=>['.st','.cmp','.when'].every(s=>{"
                   "var e=document.querySelector('#board [data-booking=\"b3\"] '+s);"
                   "return !e || getComputedStyle(e).whiteSpace==='nowrap';})"))

    # ── the second guest, in the small print under the name ────
    ck("a tile carries the companion Mews sent",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b3\"] .cmp')"
                   "?.textContent") == "With Dan Carter")
    ck("and the one the guest typed at pre-arrival",
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b4\"] .cmp')"
                   "?.textContent") == "With Lena Werner")
    ck("a booking with nobody named keeps its two-line tile",
       pg.evaluate("()=>!document.querySelector('#board [data-booking=\"b9\"] .cmp')"))

    # ── how many and how long ───────────────────────────────────
    # A pair is ONE tile wearing both lengths, the owner's ruling of 26 Aug:
    # two tiles hid the second massage's length behind the first. The card
    # shows a length row for each, and the whole pair rides one record.
    ck("two massages on the form are one tile saying so, both lengths on it",
       pg.evaluate("()=>document.querySelectorAll('#board [data-booking=\"b15\"]').length") == 1 and
       pg.evaluate("()=>document.querySelector('#board [data-booking=\"b15\"] .st').textContent")
         .startswith("Two massages") and
       "1.5 hr + 1 hr" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b15\"] .st').textContent"))
    ck("a lone massage never says Two",
       "Two massages" not in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b4\"] .st').textContent"))
    ck("a tile wears its length",
       "1.5 hr" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b4\"] .st').textContent") and
       "1 hr" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b12\"] .st').textContent"))
    pg.close()
    pg = board()
    pg.locator('#board [data-booking="b4"]').click(); pg.wait_for_timeout(300)
    ck("the card opens on the length the guest picked",
       pg.evaluate("()=>[...document.querySelectorAll('.card .chips .chip.on')]"
                   ".map(c=>c.textContent).join('|')").endswith("1.5 hours"))
    ck("one massage is one length row, and it says Length plainly",
       pg.evaluate("()=>[...document.querySelectorAll('.card .sub')]"
                   ".map(e=>e.textContent)").count("Length") == 1 and
       "2nd length" not in pg.evaluate(
         "()=>[...document.querySelectorAll('.card .sub')].map(e=>e.textContent).join('|')"))
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w2 = [x for x in WRITES if "/spa/b4/" in x["u"]]
    body2 = json.loads(w2[0]["b"]) if w2 else {}
    ck("and the length rides the booking", body2.get("dur") == 90)
    ck("a lone massage never writes a second", "dur2" not in body2 and "qty" not in body2)
    SPA = spa_seed()
    pg.close()
    pg = board()
    pg.locator('#board [data-booking="b15"]').click(); pg.wait_for_timeout(300)
    ck("the pair's card offers a length for each, labelled 1st and 2nd",
       pg.evaluate("()=>[...document.querySelectorAll('.card .sub')]"
                   ".map(e=>e.textContent).join('|')").count("1st length") == 1 and
       pg.evaluate("()=>[...document.querySelectorAll('.card .sub')]"
                   ".map(e=>e.textContent).join('|')").count("2nd length") == 1)
    ck("each row open on what the guest picked",
       pg.evaluate("()=>[...document.querySelectorAll('.card .chips .chip.on')]"
                   ".map(c=>c.textContent).join('|')").endswith("1.5 hours|1 hour"))
    del WRITES[:]
    pg.locator('.card .cbtn', has_text="Suggest").first.click(); pg.wait_for_timeout(900)
    w15 = [x for x in WRITES if "/spa/b15/" in x["u"]]
    body15 = json.loads(w15[0]["b"]) if w15 else {}
    ck("answering the pair carries both lengths on the one record",
       body15.get("qty") == 2 and body15.get("dur") == 90 and body15.get("dur2") == 60)
    SPA = spa_seed()
    pg.close()

    # Editing the details is its own act: resize a booked treatment and
    # Save changes appears, writing the edit with the status it found -
    # no cancel, no re-ask, no state change.
    pg = board()
    pg.locator('#board [data-booking="b3"]').click(); pg.wait_for_timeout(300)
    ck("an untouched card offers no Save changes",
       pg.evaluate("()=>[...document.querySelectorAll('.card .cbtn')]"
                   ".map(b=>b.textContent).join('|')").count("Save changes") == 0)
    pg.locator('.card .chip', has_text="2 hours").click(); pg.wait_for_timeout(200)
    del WRITES[:]
    pg.locator('.card .cbtn', has_text="Save changes").click(); pg.wait_for_timeout(900)
    w3 = [x for x in WRITES if "/spa/b3/" in x["u"]]
    body3 = json.loads(w3[0]["b"]) if w3 else {}
    ck("Save changes writes the new length and the booking stays booked",
       body3.get("status") == "booked" and body3.get("dur") == 120)
    SPA = spa_seed()
    pg.close()

    # ── the button law ──────────────────────────────────────────
    # Destructive wears terracotta outline, never solid ink, and always asks
    # first - the dialog's Cancel costs nothing. STYLEGUIDE.md, 26 Aug.
    pg = board()
    pg.locator('#board [data-booking="b3"]').click(); pg.wait_for_timeout(300)
    ck("Cancel booking wears the terracotta outline, not solid ink",
       pg.evaluate("()=>{var b=[...document.querySelectorAll('.card .cbtn')]"
                   ".find(x=>x.textContent==='Cancel booking');"
                   "var s=getComputedStyle(b);"
                   "return s.color==='rgb(158, 100, 85)' && "
                   "s.backgroundColor==='rgba(0, 0, 0, 0)';}"))
    del WRITES[:]
    pg.once("dialog", lambda d: d.dismiss())
    pg.locator('.card .cbtn', has_text="Cancel booking").click(); pg.wait_for_timeout(600)
    ck("cancelling asks first, and the dialog's Cancel costs nothing",
       not [x for x in WRITES if "/spa/b3/" in x["u"]])
    pg.once("dialog", lambda d: d.accept())
    del PUSHES[:]
    pg.locator('.card .cbtn', has_text="Cancel booking").click(); pg.wait_for_timeout(900)
    w3c = [x for x in WRITES if "/spa/b3/" in x["u"]]
    ck("agreeing cancels it",
       len(w3c) == 1 and json.loads(w3c[0]["b"]).get("status") == "declined")
    ck("and the cancellation buzzes as spaCancelled",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaCancelled")
    SPA = spa_seed()
    pg.close()
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    ck("Decline wears the same terracotta dress",
       pg.evaluate("()=>{var b=[...document.querySelectorAll('.card .cbtn')]"
                   ".find(x=>x.textContent==='Decline');"
                   "return getComputedStyle(b).color==='rgb(158, 100, 85)';}"))
    pg.close()
    pg = board()

    # The stats are the masseuse's whole queue, not today's slice: b9 today,
    # b4 in two days, b15 with no day picked, b30 a month out - all waiting
    # on him.
    ck("To answer counts every open ask on the horizon",
       pg.evaluate("()=>nAsk.textContent") == "4")
    ck("Suggested counts what waits on the guest",
       pg.evaluate("()=>nSugg.textContent") == "1")
    ck("Booked today counts the day being looked at",
       pg.evaluate("()=>nDay.textContent") == "1")

    # ── the open card: the stay bounds the day control ──────────
    pg.locator('#board [data-booking="b9"]').click()
    pg.wait_for_timeout(300)
    chips = pg.evaluate("()=>[...document.querySelector('.card .chips')"
                        ".querySelectorAll('.chip')].map(e=>e.textContent)")
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

    # ── the card opens on the time the guest asked for ──────────
    # Found live, 25 Aug: a 2pm ask opened - and got booked - at the 10am
    # default, because the request was free text the card never read. The
    # form and the desk write a slot label now, and the card parses it; a
    # wish from before the change ("afternoon") still falls back.
    pg.close()
    pg = board()
    pg.locator('#board [data-booking="b4"]').click(); pg.wait_for_timeout(300)
    ck("a request naming a slot opens the card on that slot",
       pg.evaluate("()=>document.querySelector('.card select').value") == "14:00" and
       "2:00 pm" in pg.evaluate(
         "()=>document.querySelector('.card .cbtn.solid').textContent"))
    ck("and on the day the guest picked",
       pg.evaluate("()=>document.querySelector('.card .chip.on').textContent")
         == short(3))
    pg.close()
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    ck("a wish that names no slot still gets the mid-morning stand-in",
       pg.evaluate("()=>document.querySelector('.card select').value") == "10:00")
    # The one slot list, pinned to the table both copies answer to.
    slots_table = json.load(open("tests/slots.json"))["slots"]
    got_opts = pg.evaluate("()=>[...document.querySelectorAll('.card option')]"
                           ".map(o=>({v:o.value,label:o.textContent}))")
    ck("the board's times are exactly the canonical table",
       got_opts == [{"v": x["v"], "label": x["label"]} for x in slots_table])
    # back onto the different day, which is what the write tests press
    pg.locator('.card .chip').nth(1).click(); pg.wait_for_timeout(200)

    # ── the writes, which are the actual feature ────────────────
    del WRITES[:]; del PUSHES[:]
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
    # The buzz, 27 Aug: the desk hears the counter-offer without watching
    # a board. Signed, so the Worker can hold the masseuse's own phone.
    ck("and the suggestion buzzes the desk as spaSuggested, villa attached",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaSuggested" and
       PUSHES[0]["villa"] == "9" and PUSHES[0].get("idToken"))
    ck("and the board reflects it without a hand refresh",
       pg.evaluate("()=>nAsk.textContent") == "3")
    SPA = spa_seed()

    # Confirming on the asked-for day books it directly.
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn.solid').click()   # Confirm, day untouched
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("confirming as asked books it in one tap",
       body.get("status") == "booked" and body.get("day") == today)
    ck("and the booking buzzes as spaBooked",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaBooked")
    SPA = spa_seed()

    # Declining asks why, once, and the reason rides on the record.
    pg = board()
    pg.on("dialog", lambda d: d.accept("away until Monday"))
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn', has_text="Decline").click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("declining writes declined, keeping the ask for the record",
       body.get("status") == "declined" and body.get("reqDay") == today)
    ck("and carries the reason the prompt collected",
       body.get("note") == "away until Monday" and not body.get("told"))
    ck("and the decline buzzes as spaCancelled",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaCancelled")
    SPA = spa_seed()
    pg.close()

    # Cancelling the prompt cancels the decline: a mis-tap costs nothing.
    pg = board()
    pg.on("dialog", lambda d: d.dismiss())
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn', has_text="Decline").click()
    pg.wait_for_timeout(600)
    ck("backing out of the prompt writes nothing",
       not [x for x in WRITES if "/spa/" in x["u"]])
    ck("and buzzes nobody", not PUSHES)
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
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn.solid').click()
    pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b12/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("asking again writes requested with the new ask",
       body.get("status") == "requested" and body.get("reqDay") == plus(2))
    ck("and the fresh ask buzzes the masseuse as spaRequest",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaRequest" and
       PUSHES[0]["villa"] == "12")
    SPA = spa_seed()

    # ── the verbal yes: the desk books what he already agreed to ──
    # The masseuse says yes in person and never opens the page; the desk's
    # Manually approve books the ask directly, stamped, and the tile says
    # the desk did it. Born from the form, so the pending ask clears.
    pg = board("staff@x")
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    ck("the desk's request card leads with Manually approve",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         .startswith("Manually approve"))
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b9/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("manually approving books the selection with the desk's stamp",
       body.get("status") == "booked" and body.get("manual") and
       body.get("day") == today and body.get("source") == "prearrival")
    ck("and buzzes as spaBooked, so the masseuse hears of the verbal yes landing",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaBooked")
    ck("and the tile says the desk did it",
       "approved at the desk" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b9\"] .st').textContent"))
    SPA = spa_seed()
    pg.close()

    # The masseuse's own card never offers it: his yes is Confirm.
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    ck("no Manually approve exists on the masseuse's screen",
       pg.evaluate("()=>[...document.querySelectorAll('.card .cbtn')]"
                   ".every(b=>!b.textContent.startsWith('Manually'))"))
    pg.close()

    # ── the decline's other half: telling the guest ─────────────
    # The terracotta tile instructs the desk until somebody actually tells
    # the guest; Guest told stamps the record, the tile stops instructing,
    # and the menu icon stops counting it.
    pg = board("staff@x")
    pg.locator('#board [data-booking="b7"]').click(); pg.wait_for_timeout(300)
    ck("the desk's declined card leads with Guest told",
       pg.evaluate("()=>document.querySelector('.card .cbtn.solid').textContent")
         == "Guest told")
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b7/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("telling the guest stamps the record and keeps the reason",
       body.get("status") == "declined" and body.get("told") and
       body.get("note") == "nothing free")
    # Bookkeeping, nobody's queue: the one save that must not buzz.
    ck("the told stamp buzzes nobody", not PUSHES)
    ck("and the tile stops instructing",
       "guest told" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b7\"] .st').textContent") and
       "let the guest know" not in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b7\"] .st').textContent"))
    SPA = spa_seed()
    pg.close()

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
    ck("the masseuse's board ends at Declined",
       bands(pg)[-1] == "Declined · 1")
    ck("no stay without a treatment shows for him at all",
       pg.evaluate("()=>document.querySelectorAll('#board .b-grey').length") == 0 and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b2\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b6\"]')"))
    ck("nor the desk's find-the-guest box",
       not pg.evaluate("()=>!!document.querySelector('#addFind')"))
    pg.close()

    # The desk keeps the add path - one plainly-named header and a search,
    # because at 45 days the old every-stay band was a wall of grey the
    # owner could not read as anything, 27 Aug. Resting, it lists only who
    # can be standing at the desk: in a villa now or arriving within the
    # week. The search reaches everyone else in the window.
    pg = board("staff@x")
    got = bands(pg)
    ck("the desk's board ends with the add path, plainly named",
       got[-1] == "Add a treatment")
    ck("resting, it lists the guests here or arriving this week",
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b2\"]')") and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b6\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b45\"]')"))
    ck("and says the search reaches the rest",
       "1 more arrive later" in pg.evaluate(
         "()=>(document.querySelector('#board .hint')||{textContent:''}).textContent"))
    ck("a guest who said no thank you is named as such, not offered around",
       "no thank you" in pg.evaluate(
         "()=>document.querySelector('#board [data-booking=\"b2\"] .st').textContent"))
    # Finding the guest, the 27 Aug ask: a name fragment or the exact villa
    # number surfaces a later arrival, and her tile is the same add path.
    pg.fill("#addFind", "pri"); pg.wait_for_timeout(200)
    ck("a name fragment finds the later arrival",
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b45\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b6\"]')"))
    pg.fill("#addFind", "6"); pg.wait_for_timeout(200)
    ck("a villa number answers only to its exact self",
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b6\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b45\"]')"))
    pg.fill("#addFind", "16"); pg.wait_for_timeout(200)
    ck("and the later villa to its own",
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b45\"]')") and
       not pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b6\"]')"))
    pg.fill("#addFind", "zz"); pg.wait_for_timeout(200)
    ck("no match says so rather than showing nothing",
       "No guest by that" in pg.evaluate(
         "()=>(document.querySelector('#board .hint')||{textContent:''}).textContent"))
    pg.fill("#addFind", "priya"); pg.wait_for_timeout(200)
    pg.locator('#board [data-booking="b45"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w45 = [x for x in WRITES if "/spa/b45/" in x["u"]]
    body45 = json.loads(w45[0]["b"]) if w45 else {}
    ck("a found guest's add asks the masseuse like any other",
       body45.get("status") == "requested" and body45.get("source") == "desk")
    SPA = spa_seed()
    pg.close()

    # The desk's add asks the masseuse: the desk does not know his book.
    pg = board("staff@x")
    pg.locator('#board [data-booking="b6"]').click(); pg.wait_for_timeout(300)
    ck("the desk's add offers Ask the masseuse",
       "Ask the masseuse" in pg.evaluate(
         "()=>document.querySelector('.card .cbtn.solid').textContent"))
    del WRITES[:]; del PUSHES[:]
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    w = [x for x in WRITES if "/spa/b6/" in x["u"]]
    body = json.loads(w[0]["b"]) if w else {}
    ck("and writes requested, with the desk's pick as the ask",
       body.get("status") == "requested" and body.get("source") == "desk" and
       body.get("reqDay") and body.get("reqTime"))
    ck("and the add buzzes the masseuse as spaRequest with the villa",
       len(PUSHES) == 1 and PUSHES[0]["event"] == "spaRequest" and
       PUSHES[0]["villa"] == "6")
    SPA = spa_seed()
    pg.close()

    # ── the numbers are filters ─────────────────────────────────
    # Tap a stat and the board is that queue alone; tap it again for the
    # whole day. To answer and Suggested filter across the horizon, like the
    # numbers they sit under; Booked keeps to the viewed day, like its label.
    pg = board()
    pg.locator('#statsRow .stat[data-f="requested"]').click(); pg.wait_for_timeout(200)
    ck("tapping To answer shows every open ask, future and day-less included",
       bands(pg) == ["Every open ask · 4"] and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b4\"]')") and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b15\"]')") and
       pg.evaluate("()=>!!document.querySelector('#board [data-booking=\"b30\"]')"))
    ck("and the pressed number wears the amber mark",
       pg.evaluate("()=>document.querySelector('.stat[data-f=\"requested\"]').className")
         == "stat on")
    pg.locator('#statsRow .stat[data-f="requested"]').click(); pg.wait_for_timeout(200)
    ck("tapping it again returns to All",
       len(bands(pg)) == 4 and
       pg.evaluate("()=>document.querySelector('#statsRow .stat.on')"
                   ".getAttribute('data-f')") == "all")
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
    # One suggestion to put to the guest, one decline the guest has not
    # heard about: two things wait on the desk.
    ck("the Spa entry counts both queues that wait on the desk",
       badge_on_pages() == "2")
    SPA = {k: v for k, v in spa_seed().items() if k != "b12"}
    ck("a told decline stops counting",
       badge_on_pages() == "1")
    SPA["b7"]["t1"]["told"] = "2026-08-25T10:00:00Z"
    ck("and no icon at all once nothing waits, rather than a zero",
       badge_on_pages() is None)
    SPA = spa_seed()

    # ── a write refused is said, not swallowed ──────────────────
    pg = board()
    pg.locator('#board [data-booking="b9"]').click(); pg.wait_for_timeout(300)
    STATE["fail"] = True
    pg.locator('.card .cbtn.solid').click(); pg.wait_for_timeout(900)
    # The words come from the shared saveFailWords now, not this page. A
    # refusal is a PERMISSION and needs the manager, which is a different
    # errand from a write that never arrived; this page threw a bare Error
    # until 28 Aug, so neither could be told apart and a rules rejection
    # read as "check the connection" - the wrong remedy.
    ck("a refused save is reported in words",
       "not allowed" in pg.evaluate("()=>errBar.textContent").lower())
    ck("and names the right errand, since a refusal is not a bad connection",
       "manager" in pg.evaluate("()=>errBar.textContent").lower()
       and "connection" not in pg.evaluate("()=>errBar.textContent").lower())
    STATE["fail"] = False
    pg.close()

    # ── the manager's spa prices, set from Settings ─────────────
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.add_init_script(SDK)
    q.add_init_script("window.__EMAIL=%s;" % json.dumps("staff@x"))
    q.route("**firebasedatabase.app/**", fb)
    q.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    q.goto("http://localhost:8980/staff.html")
    q.wait_for_timeout(1600)
    ck("Settings shows the prices it holds",
       q.evaluate("()=>sp60.value") == "180" and
       q.evaluate("()=>sp90.value") == "250")
    del WRITES[:]
    q.fill("#sp60", "195")
    q.evaluate("()=>{sp60.dispatchEvent(new Event('change'))}")
    q.wait_for_timeout(600)
    w3 = [x for x in WRITES if "/spasettings" in x["u"]]
    body3 = json.loads(w3[0]["b"]) if w3 else {}
    ck("changing a price saves that price, as a number",
       w3 and w3[0]["m"] == "PATCH" and body3.get("price60") == 195)
    q.fill("#sp60", "call us")
    q.evaluate("()=>{sp60.dispatchEvent(new Event('change'))}")
    q.wait_for_timeout(300)
    ck("words are refused before they reach the database",
       "whole number" in q.evaluate("()=>spaErr.textContent"))
    q.close()

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
        ck("no sideways scroll at %dpt, card open" % w2, not q.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    b.close()

# ── the horizon is pinned to the invite Worker's window ─────────
# The board reads HORIZON days of /stays; the Worker refuses a pre-arrival
# SMS for an arrival more than N days out. HORIZON below N is the 27 Aug
# bug by construction: a guest can answer a form whose stay the board never
# reads, and the ask hides until the date navigation lands on it. The two
# numbers live in files that cannot import each other (the normalisePhone
# situation), so whichever side moves without the other fails here by name.
horizon = int(re.search(r"var HORIZON = (\d+)", open("spa.html").read()).group(1))
invite_window = int(re.search(
    r"Date\.now\(\) \+ (\d+) \* 24 \* 60 \* 60 \* 1000",
    open("worker/send-invites.js").read()).group(1))
ck("the board reads at least as far ahead as an invite can be sent",
   horizon >= invite_window)

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
