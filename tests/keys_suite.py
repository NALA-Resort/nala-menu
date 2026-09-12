"""Keys - the card register, held to the mock it was approved as.

The owner approved the rebuilt store shape by shape (mock-keys-store.html,
11 Sep) and ruled the build must BE that design. So the first block here
is a drift check: a list of the mock's load-bearing fragments, markup and
dress alike, each of which must appear verbatim in keys.html. A redesign
fails by name before a single behaviour check runs. The dress itself is
Front Desk's, copied, and one fragment pins the copy to front-desk.html.

Everything the page SHOWS is owned elsewhere: /cards, one row per card
in the world (the helper writes a row per cut and removes the row it
wipes; cardRows/cardState in nala-shared are the only readers, held to
tests/cardstate_cases.json). The page OWNS the lost flag, the by-hand
Remove and the /cancelrun switch, and those writes are asserted here
byte for byte.
"""
import errortrap
import threading, http.server, socketserver, json, time, os, datetime

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8992), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── the drift check: the built page IS the approved mock ────────────
mock = open("mock-keys-store.html", encoding="utf-8").read()
page = open("keys.html", encoding="utf-8").read()
fd   = open("front-desk.html", encoding="utf-8").read()

FRAGMENTS = [
    # the header the owner shaped by hand: no heading, the button leads
    '>Cancel keys</button>',
    '>Issue keys</button>',
    '<div class="keydrop" id="issueDrop"></div>',
    'border:1px solid var(--terra-b)',
    'All arrivals',
    'Villa by number',
    'margin-right:auto',
    # the segmented control
    '<div class="seg" id="tabs"',
    # the row: an arr tile, state words in the fork slot
    '<div class="kst">',
    '.kst { flex:0 0 auto; text-align:right; font-size:var(--t1);',
    '.kst .g { color:var(--law-green); }',
    '.kst .t { color:var(--terra); }',
    # the wording laws: till, expires, floating, Expired not Tally
    "cards never came back",
    "'Expired' }",
    "' &middot; was lost'",
    # the sheet and its buttons, acting on ONE row
    '>Mark lost</button>',
    'Remove',
    '>Found</button>',
    "'a card &middot; <span class=\"eta\">till '",
    "one of villa ",
    '<div class="sum-l">Card</div>',
    'card off the register',
    # the cancel session: the ask drawing and the one-shape words
    'Hold a card to the reader',
    '<rect x="57" y="10" width="33" height="46" rx="5" transform="rotate(16 73 33)"/>',
    'cards cancelled',
    '>Stop</button>',
    "'Unknown card",
]
missing = [f for f in FRAGMENTS if f not in page]
ck("every load-bearing fragment of the approved mock is in the page",
   not missing)
if missing: print("   missing:", missing)
inmock = [f for f in FRAGMENTS if f not in mock]
ck("and the mock itself still carries them (the list is honest)",
   not inmock)
if inmock: print("   not in mock:", inmock)
#  The dress is Front Desk's, copied: one heavy rule pins the copy. If
#  front-desk's .arr changes, this fails and both files move together.
arr_rule = fd[fd.index('.arr {'): fd.index('.arr-v {')]
ck("the row dress is front-desk's own, byte for byte", arr_rule in page)
ck("nothing mock-only leaked into the page",
   'mocktools' not in page and 'tapnote' not in page and 'mintCard' not in page)
#  The rate died with the counters (ruled 11 Sep) and must not creep back.
ck("no returned-rate on the page", '% returned' not in page
   and 'Math.round' not in page)

# ── the live page, against a stubbed database ───────────────────────
SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

now = datetime.datetime.now().astimezone()
def day(off): return (now + datetime.timedelta(days=off)).strftime("%Y-%m-%d")
def at13(off):
    t = (now + datetime.timedelta(days=off)).replace(hour=13, minute=0,
                                                     second=0, microsecond=0)
    return int(t.timestamp())
def late_today():
    t = now.replace(hour=23, minute=0, second=0, microsecond=0)
    return int(t.timestamp())

STAFF = {"staff@x": {"name": "Admin", "role": "admin"}}

#  Tonight's villa map, the same node Front Desk reads: two arrivals and
#  one villa already in house, for the Issue keys drop.
STAYS2 = {
  "2":  {"id": "s2", "first": "Michelle", "last": "Edmondson",
         "arrive": day(0), "depart": day(2), "adults": 2},
  "12": {"id": "s12", "first": "Jeroen", "last": "Hamers",
         "arrive": day(0), "depart": day(3), "adults": 3},
  "4":  {"id": "s4", "first": "Robyn", "last": "Williams",
         "arrive": day(-2), "depart": day(4), "adults": 2},
}
#  LAST night's map: Ann Brown departs today, so she is gone from
#  tonight's - but she stands at the desk till 1pm and the drop must
#  still offer her (the owner, 11 Sep).
STAYS_PREV2 = {
  "14": {"id": "s14", "first": "Ann", "last": "Brown",
         "arrive": day(-3), "depart": day(0), "adults": 1},
  "4":  {"id": "s4", "first": "Robyn", "last": "Williams",
         "arrive": day(-2), "depart": day(4), "adults": 2},
}

#  The card table: one row per card in the world, keyed by serial.
#  Villa 6's third card was wiped, so its row is simply not here.
def cards():
    return {
      "914001": {"villa": "14", "guest": "Ann Brown", "cut": 1,
                 "expiry": late_today()},
      "904001": {"villa": "4", "guest": "Robyn Williams", "cut": 2,
                 "expiry": at13(4)},
      "904002": {"villa": "4", "guest": "Robyn Williams", "cut": 3,
                 "expiry": at13(4)},
      "909001": {"villa": "9", "guest": "Konstantinos Papadopoulos",
                 "cut": 4, "expiry": at13(2)},
      "909002": {"villa": "9", "guest": "Konstantinos Papadopoulos",
                 "cut": 5, "expiry": at13(2)},
      "909003": {"villa": "9", "guest": "Konstantinos Papadopoulos",
                 "cut": 6, "expiry": at13(2), "lost": True},
      "906001": {"villa": "6", "guest": "Karen and Mike Mount", "cut": 7,
                 "expiry": at13(2)},
      "906002": {"villa": "6", "guest": "Karen and Mike Mount", "cut": 8,
                 "expiry": at13(2)},
      #  the Expired list: rows past their 1pm, still present
      "902001": {"villa": "2", "guest": "Sarah Mitchell", "cut": 9,
                 "expiry": at13(-2)},
      "911001": {"villa": "11", "guest": "Priya Raghunathan", "cut": 10,
                 "expiry": at13(-5)},
      "911002": {"villa": "11", "guest": "Priya Raghunathan", "cut": 11,
                 "expiry": at13(-5)},
    }

CARDS = cards()
CANCELRUN = {}
CUTRUN = {}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if "/cancelrun" in u:
            body = json.loads(request.post_data)
            if m == "PUT": CANCELRUN.clear(); CANCELRUN.update(body)
            else: CANCELRUN.update(body)
        if "/cutrun" in u:
            body = json.loads(request.post_data)
            if "/cutrun/queue/" in u:
                v = u.split("/cutrun/queue/")[1].split(".json")[0]
                CUTRUN.setdefault("queue", {}).setdefault(v, {}).update(body)
            elif m == "PUT": CUTRUN.clear(); CUTRUN.update(body)
            else: CUTRUN.update(body)
        if "/cards/" in u:
            no = u.split("/cards/")[1].split(".json")[0]
            if m == "DELETE": CARDS.pop(no, None)
            elif m == "PATCH" and no in CARDS:
                CARDS[no].update(json.loads(request.post_data))
            elif m == "PUT": CARDS[no] = json.loads(request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/cancelrun" in u: body = json.dumps(CANCELRUN) if CANCELRUN else "null"
    elif "/cutrun" in u: body = json.dumps(CUTRUN) if CUTRUN else "null"
    elif "/cards" in u: body = json.dumps(CARDS)
    elif "/stays/" in u:
        d = u.split("/stays/")[1].split(".json")[0]
        body = json.dumps(STAYS2) if d == day(0) \
             else json.dumps(STAYS_PREV2) if d == day(-1) else "null"
    elif "/staff" in u: body = json.dumps(STAFF)
    route.fulfill(status=200, content_type="application/json", body=body)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(w=390):
        pg = b.new_page(viewport={"width": w, "height": 844})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL='staff@x';")
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8992/keys.html")
        pg.wait_for_timeout(900)
        return pg

    pg = board()
    tabs = pg.inner_text("#tabs")
    #  Rows counted, nothing worked out: 7 in hand, 1 flagged, 3 past
    #  their 1pm. Three tabs and no All (ruled 11 Sep): In use, Lost,
    #  Expired - a lost card becomes Expired at its 1pm, so Lost is
    #  almost always empty.
    ck("three tabs and no All: In use 7, Lost 1, Expired 3",
       "In use · 7" in tabs and "Lost · 1" in tabs
       and "Expired · 3" in tabs and "All" not in tabs
       and pg.evaluate("()=>document.querySelectorAll('#tabs button').length") == 3)
    ck("a last-day card wears amber and the 12h clock",
       pg.evaluate("""()=>{var r=document.querySelector('.arr[data-villa="14"]');
         return r && r.className.indexOf('part-form')>=0
             && r.innerText.indexOf('till 11pm')>=0
             && r.innerText.indexOf('expires 11pm')>=0;}"""))
    mon = (now + datetime.timedelta(days=4)).strftime("%b")
    ck("a living card wears green, till day-only - no month, no spill",
       pg.evaluate("""(mon)=>{var r=document.querySelector('.arr[data-villa="4"]');
         return r && r.className.indexOf('done-form')>=0
             && r.innerText.indexOf('till ')>=0
             && r.innerText.indexOf(mon)<0;}""", mon))
    #  A ROW PER CARD: villa 9 holds two rows in hand here; its lost one
    #  lives on the Lost tab, anonymous on screen.
    ck("a card is a row: villa 9 shows two in use, the lost one elsewhere",
       pg.evaluate("""()=>{var r=[...document.querySelectorAll('.arr[data-villa="9"]')];
         return r.length===2
             && r.every(x=>x.innerText.indexOf('a card')>=0);}"""))
    ck("a wiped card left the register: villa 6 shows two rows, not three",
       pg.evaluate("()=>document.querySelectorAll('.arr[data-villa=\"6\"]').length") == 2)
    #  the wording law: the serial lives in the row, never on the screen
    ck("no serial numbers on screen",
       pg.evaluate("""()=>!/9(02|04|06|09|11|14)\\d{3}/.test(
           document.getElementById('list').innerText)"""))

    #  one card's sheet: tap a row, act on that row alone
    pg.evaluate("()=>document.querySelector('[data-open=\"909001\"]').click()")
    pg.wait_for_timeout(200)
    sheet = pg.inner_text("#list")
    ck("the sheet says the one card's facts, tersely",
       "villa 9 · till" in sheet and "Mark lost" in sheet and "Remove" in sheet)
    del WRITES[:]
    pg.evaluate("()=>document.querySelector('[data-lose=\"909001\"]').click()")
    pg.wait_for_timeout(300)
    lost_w = [w for w in WRITES if w["m"] == "PATCH" and "/cards/909001" in w["u"]]
    ck("Mark lost flags THAT row, byte for byte",
       lost_w and json.loads(lost_w[0]["b"]) == {"lost": True})
    #  the flagged row leaves In use for the Lost tab; Found lives there
    pg.evaluate("()=>document.querySelector('[data-tab=\"lost\"]').click()")
    pg.wait_for_timeout(200)
    ck("the lost card reads anonymous, floating",
       pg.evaluate("""()=>{var r=[...document.querySelectorAll('.arr[data-villa="9"]')];
         return r.length===2 && r.every(x=>x.innerText.indexOf('one of villa 9')>=0
             && x.innerText.indexOf('floating till')>=0);}"""))
    pg.evaluate("()=>document.querySelector('[data-open=\"909001\"]').click()")
    pg.wait_for_timeout(200)
    pg.evaluate("()=>document.querySelector('[data-found=\"909001\"]').click()")
    pg.wait_for_timeout(300)
    found_w = [w for w in WRITES if w["m"] == "PATCH" and "/cards/909001" in w["u"]]
    ck("Found walks the flag back, the row stays",
       json.loads(found_w[-1]["b"]) == {"lost": False} and "909001" in CARDS)

    #  Remove: the by-hand door for plastic the machine can never see
    #  again. It asks first, then DELETES the row - the same act a wipe
    #  performs, moved by a person. The found card is back In use.
    pg.evaluate("()=>document.querySelector('[data-tab=\"ok\"]').click()")
    pg.wait_for_timeout(200)
    pg.evaluate("()=>document.querySelector('[data-open=\"909001\"]').click()")
    pg.wait_for_timeout(200)
    del WRITES[:]
    pg.evaluate("()=>document.querySelector('[data-remove=\"909001\"]').click()")
    pg.wait_for_timeout(200)
    ck("Remove asks before it deletes",
       not [w for w in WRITES if "/cards/" in w["u"]]
       and "card off the register" in pg.inner_text("#list"))
    pg.evaluate("()=>document.querySelector('[data-remove=\"909001\"]').click()")
    pg.wait_for_timeout(300)
    ck("and the confirm DELETEs the row",
       [w for w in WRITES if w["m"] == "DELETE" and "/cards/909001" in w["u"]]
       and "909001" not in CARDS)
    ck("the register then holds one active row fewer for villa 9",
       pg.evaluate("""()=>[...document.querySelectorAll('.arr[data-villa="9"]')]
           .filter(x=>x.innerText.indexOf('a card')>=0).length""") == 1)

    #  tabs filter; Expired is rows past their 1pm still present
    pg.evaluate("()=>document.querySelector('[data-tab=\"lost\"]').click()")
    pg.wait_for_timeout(200)
    ck("the Lost tab holds only the floating cards",
       pg.evaluate("()=>document.querySelectorAll('#list .arr').length") == 1
       and "floating" in pg.inner_text("#list"))
    pg.evaluate("()=>document.querySelector('[data-tab=\"expired\"]').click()")
    pg.wait_for_timeout(200)
    ck("Expired counts the never-returned, and no rate",
       "3 cards never came back" in pg.inner_text("#tallyLine")
       and "%" not in pg.inner_text("#tallyLine"))
    ck("its rows are the cards still owing, newest first",
       pg.evaluate("""()=>{var r=[...document.querySelectorAll('#list .arr')];
         return r.length===3 && r[0].innerText.indexOf('Sarah Mitchell')>=0
             && r[1].innerText.indexOf('Priya Raghunathan')>=0;}"""))

    #  the cancel session: on, fed by the helper, stopped by the desk
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('cancelBtn').click()")
    pg.wait_for_timeout(300)
    started = [w for w in WRITES if w["m"] == "PUT" and "/cancelrun" in w["u"]]
    ck("Cancel keys switches the session on",
       started and json.loads(started[0]["b"])["state"] == "on"
       and not pg.evaluate("()=>document.getElementById('cancelOv').hidden"))
    ck("and asks with the drawing",
       pg.evaluate("()=>!!document.querySelector('#ovBody .cardask svg')"))
    #  the pretend helper answers: heartbeat, a named wipe, an unknown one
    CANCELRUN["seen"] = int(time.time() * 1000) + 60000
    CANCELRUN["done"] = {"0": {"villa": "9", "no": "909002", "at": 1},
                         "1": {"villa": "?", "no": "555", "at": 2}}
    pg.wait_for_timeout(1600)
    ov = pg.inner_text("#ovBody")
    #  ONE notification shape, ruled 11 Sep: the entry, then the action.
    ck("each wiped card lands named, one shape",
       "Villa 9 · cancelled" in ov and "Unknown card · cancelled" in ov)
    ck("never a narrative variant",
       "was lost" not in ov and "off the tally" not in ov
       and "blank" not in ov and "wiped" not in ov)
    ck("and the count grows", "2" in pg.evaluate(
           "()=>document.querySelector('#ovBody .crun-v').textContent"))
    pg.evaluate("()=>document.getElementById('ovStop').click()")
    pg.wait_for_timeout(300)
    ck("Stop switches it off",
       [w for w in WRITES if w["m"] == "PATCH" and "/cancelrun" in w["u"]
        and json.loads(w["b"]).get("state") == "off"]
       and pg.evaluate("()=>document.getElementById('cancelOv').hidden"))

    #  Issue keys: the shared nala-cards runtime, fed everyone in house
    #  with arrivals leading, held counts from the table, All arrivals
    #  at the foot behind the seam.
    pg.evaluate("()=>document.getElementById('issueBtn').click()")
    pg.wait_for_timeout(300)
    drop = pg.evaluate("""()=>[...document.querySelectorAll('#issueDrop button')]
        .map(b=>b.textContent)""")
    ck("the drop: arrivals, then departing today, then in house, then the pad",
       len(drop) == 6 and "Villa 2" in drop[0] and "Villa 12" in drop[1]
       and "Villa 14" in drop[2] and "Ann Brown" in drop[2]
       and "Villa 4" in drop[3] and "Villa by number" in drop[4])
    ck("a villa's held count reads from the table",
       "2 held" in drop[3] and "arriving" in drop[0] and "1 held" in drop[2])
    ck("All arrivals stands last, its count in a badge",
       pg.evaluate("""()=>{var b=[...document.querySelectorAll('#issueDrop button')];
         var a=b[b.length-1];
         return a.getAttribute('data-key')==='all'
             && a.querySelector('.navbadge').textContent==='2';}"""))

    #  the pad: a room with no guest, reached by number. Its expiry is
    #  not a settled fact, so the sheet asks till when - a date and a
    #  time, defaulting to the next 1pm - and Issue carries the answer.
    pg.evaluate("()=>document.querySelector('#issueDrop [data-key=\"pad\"]').click()")
    pg.wait_for_timeout(300)
    ck("the pad asks which villa, seventeen one-tap numbers",
       "Which villa" in pg.inner_text("#cardBody")
       and pg.evaluate("()=>document.querySelectorAll('[data-cardvilla]').length") == 17)
    pg.evaluate("()=>document.querySelector('[data-cardvilla=\"7\"]').click()")
    pg.wait_for_timeout(300)
    body7 = pg.inner_text("#cardBody")
    if now.hour >= 13:
        exp_def = (now + datetime.timedelta(days=1)).replace(
            hour=13, minute=0, second=0, microsecond=0)
    else:
        exp_def = now.replace(hour=13, minute=0, second=0, microsecond=0)
    ck("a no-guest villa asks till when, defaulting to the next 1pm",
       "No guest" in body7 and "Till when?" in body7
       and pg.evaluate("()=>document.getElementById('askDate').value")
           == exp_def.strftime("%Y-%m-%d")
       and pg.evaluate("()=>document.getElementById('askTime').value") == "13:00")
    del WRITES[:]
    CUTRUN.clear()
    pg.evaluate("()=>document.querySelector('[data-cardissue]').click()")
    pg.wait_for_timeout(400)
    pads = [json.loads(w["b"]) for w in WRITES
            if w["m"] == "PUT" and "/cutrun" in w["u"]]
    ck("Issue carries the chosen expiry, and No guest is the name",
       pads and pads[0]["queue"]["7"]["guest"] == "No guest"
       and pads[0]["queue"]["7"]["expiry"] == int(exp_def.timestamp()))
    pg.evaluate("()=>document.getElementById('cardX').click()")
    pg.wait_for_timeout(300)

    #  a departing-today guest: settled at today's 1pm while that is
    #  still ahead; once it has passed, the sheet asks instead - a card
    #  born dead is never cut silently (the owner, 11 Sep).
    pg.evaluate("()=>document.getElementById('issueBtn').click()")
    pg.wait_for_timeout(200)
    pg.evaluate("()=>document.querySelector('#issueDrop [data-key=\"14\"]').click()")
    pg.wait_for_timeout(300)
    asks_when = pg.evaluate("()=>!!document.getElementById('askDate')")
    ck("a leaving guest's sheet asks till-when exactly when 1pm has passed",
       asks_when == (now.hour >= 13))
    pg.evaluate("()=>document.getElementById('cardX').click()")
    pg.wait_for_timeout(200)
    del WRITES[:]
    pg.evaluate("()=>document.querySelector('#issueDrop [data-key=\"2\"]').click()")
    pg.wait_for_timeout(400)
    ck("a villa opens the run's own quantity question",
       not pg.evaluate("()=>document.getElementById('cardOv').hidden")
       and "How many cards" in pg.inner_text("#cardBody"))
    pg.evaluate("()=>document.querySelector('[data-cardissue]').click()")
    pg.wait_for_timeout(400)
    iss = [json.loads(w["b"]) for w in WRITES
           if w["m"] == "PUT" and "/cutrun" in w["u"]]
    ck("Issue switches the cut run on - a request, not a stored record",
       iss and iss[0]["state"] == "on" and iss[0]["queue"]["2"]["qty"] == 2
       and iss[0]["queue"]["2"]["guest"] == "Michelle Edmondson"
       and iss[0]["queue"]["2"]["cut"] == 0)
    #  before the helper answers: Waking up; after: the ask and Skip
    pg.wait_for_timeout(1100)
    ck("the run waits with Waking up until the helper claims it",
       "Waking up" in pg.inner_text("#cardBody"))
    CUTRUN["seen"] = int(time.time() * 1000) + 60000
    pg.wait_for_timeout(1600)
    body = pg.inner_text("#cardBody")
    ck("a live helper turns the wait into the ask",
       "Hold a card to the reader" in body and "Skip this card" in body)
    #  the helper cuts one: a row appears, the seat fills, cut bumps
    CARDS["902099"] = {"villa": "2", "guest": "Michelle Edmondson",
                       "cut": 99, "expiry": at13(2)}
    CUTRUN["queue"]["2"]["cut"] = 1
    pg.wait_for_timeout(1600)
    ck("a cut card is a row: the seat fills from the table",
       pg.evaluate("()=>document.querySelectorAll('#cardBody .cslot.filled').length") == 1)
    #  Numbers CONTINUE across the row: the tick is card 1, so the amber
    #  seat is card 2 - a second run restarting at 1 calls the villa's
    #  second card its first (the owner's bug report, 12 Sep).
    ck("seat numbers continue after the cards in hand",
       pg.evaluate("""()=>{var s=[...document.querySelectorAll('#cardBody .cslot')]
         .map(e=>e.textContent.trim());
         return s.length===2 && s[0]==='' && s[1]==='2';}"""))
    del WRITES[:]
    pg.evaluate("()=>document.querySelector('[data-cardskip]').click()")
    pg.wait_for_timeout(300)
    skips = [w for w in WRITES if w["m"] == "PATCH" and "/cutrun/queue/2" in w["u"]]
    ck("Skip this card shrinks the ask to the cards already cut",
       skips and json.loads(skips[0]["b"]) == {"qty": 1})
    pg.evaluate("()=>document.getElementById('cardX').click()")
    pg.wait_for_timeout(300)
    offs = [w for w in WRITES if w["m"] == "PATCH" and "/cutrun.json" in w["u"]
            and json.loads(w["b"]).get("state") == "off"]
    ck("closing the run ends the request - it never lies in wait", bool(offs))
    del WRITES[:]
    CUTRUN.clear()
    pg.evaluate("()=>document.getElementById('issueBtn').click()")
    pg.wait_for_timeout(200)
    pg.evaluate("()=>document.querySelector('#issueDrop [data-key=all]').click()")
    pg.wait_for_timeout(500)
    puts = [json.loads(w["b"]) for w in WRITES
            if w["m"] == "PUT" and "/cutrun" in w["u"]]
    ck("All arrivals queues the arrivals and nobody else, a card per guest",
       puts and sorted(puts[0]["queue"].keys()) == ["12", "2"]
       and puts[0]["queue"]["12"]["qty"] == 3
       and puts[0]["queue"]["2"]["qty"] == 2)
    pg.evaluate("()=>document.getElementById('cardX').click()")
    pg.close()

    #  a run nobody answers dies with the queue law's own verdict
    CUTRUN.clear()
    pg2 = board()
    pg2.evaluate("()=>document.getElementById('issueBtn').click()")
    pg2.wait_for_timeout(200)
    pg2.evaluate("()=>document.querySelector('#issueDrop [data-key=all]').click()")
    CUTRUN.pop("seen", None)             # the PUT lands; no helper answers
    pg2.wait_for_timeout(12000)
    ck("ten silent seconds is a verdict, not a wait",
       "Encoder offline" in pg2.inner_text("#cardBody")
       and "Nothing was written" in pg2.inner_text("#cardBody")
       and CUTRUN.get("state") == "off")
    pg2.close()

    #  the hamburger knows this page, and this page omits itself
    pg3 = board()
    nav = pg3.evaluate("()=>document.getElementById('navDrop').innerHTML")
    ck("the menu stands, with this page's own link omitted",
       "front-desk.html" in nav and "keys.html" not in nav)
    pg3.close()
    pg4 = board(w=320)
    ck("the width law holds at 320",
       pg4.evaluate("()=>document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    pg4.close()

    # ── the Guest Profile's door: ?villa= marks that villa's card ──
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.add_init_script(SDK)
    pg.add_init_script("window.__EMAIL='staff@x';")
    pg.route("**firebasedatabase.app/**", fb)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.goto("http://localhost:8992/keys.html?villa=4")
    pg.wait_for_timeout(1200)
    ck("the profile's door marks the villa's card in the register",
       pg.evaluate("()=>{const e=document.querySelector('.arr.linked');"
                   "return !!e && e.dataset.villa === '4';}"))
    ck("and the first tap anywhere takes the mark off",
       pg.evaluate("()=>{document.body.click();"
                   "return !document.querySelector('.arr.linked');}"))
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
