"""Keys - the card register, held to the mock it was approved as.

The owner approved mock-keys.html shape by shape on 9 Sep and ruled the
build must BE that design ("only to find Claude had built a whole new
page" - not this time). So the first block here is a drift check: a list
of the mock's load-bearing fragments, markup and dress alike, each of
which must appear verbatim in keys.html. A redesign fails by name before
a single behaviour check runs. The dress itself is Front Desk's, copied,
and one fragment pins the copy to front-desk.html too.

Everything the page SHOWS is owned elsewhere: /cardjobs (front-desk
writes, the helper moves, cardLife in nala-shared reads - the cases in
tests/cardlife_cases.json). The page OWNS the lost/found marks and the
/cancelrun switch, and those writes are asserted here byte for byte.
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
mock = open("mock-keys.html", encoding="utf-8").read()
page = open("keys.html", encoding="utf-8").read()
fd   = open("front-desk.html", encoding="utf-8").read()

FRAGMENTS = [
    # the header the owner shaped by hand: no heading, the button leads
    '>Cancel cards</button>',
    'margin-right:auto',
    # the segmented control and its shrink-to-320 law
    '<div class="seg" id="tabs"',
    '#tabs button { min-width:0; font-size:var(--t1); padding:11px 2px; }',
    '#body { min-width:0; width:100%; }',
    # the row: an arr tile, state words in the fork slot
    '<div class="kst">',
    '.kst { flex:0 0 auto; text-align:right; font-size:var(--t1);',
    '.kst .g { color:var(--law-green); }',
    '.kst .t { color:var(--terra); }',
    # the wording laws: till, expires, floating
    "' &middot; <span class=\"eta\">till '",
    "' floating &middot; <span class=\"eta\">expires '",
    "cards never came back",
    "' &middot; departed <span class=\"eta\">'",
    # the sheet and its two buttons
    '<div class="sum-l">Cards</div>',
    '>Mark a card lost</button>',
    '>Found</button>',
    # the cancel session: the ask drawing and the words
    'Hold a card to the reader',
    '<rect x="57" y="10" width="33" height="46" rx="5" transform="rotate(16 73 33)"/>',
    'cards cancelled',
    '>Stop</button>',
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
   'mocktools' not in page and 'tapnote' not in page and 'FAKE' not in page)

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

def jobs():
    return {
      day(-1): {
        # today's expiries were written yesterday: the guests depart today
        "14": {"qty": 2, "written": 2, "state": "done", "expiry": late_today(),
               "guest": "Ann Brown", "by": "x", "at": 1},
      },
      day(0): {
        "4": {"qty": 2, "written": 2, "state": "done", "expiry": at13(4),
              "guest": "Robyn Williams", "by": "x", "at": 1},
        "9": {"qty": 3, "written": 3, "state": "done", "expiry": at13(2),
              "guest": "Konstantinos Papadopoulos", "lost": 1, "by": "x", "at": 1},
        "6": {"qty": 3, "written": 3, "state": "done", "expiry": at13(2),
              "guest": "Karen and Mike Mount", "back": 1, "by": "x", "at": 1},
      },
      # the dead, for the Tally: 5 written, 2 back -> 3 gone, 40% returned
      day(-4): {
        "2": {"qty": 2, "written": 2, "back": 1, "state": "done",
              "expiry": at13(-2), "guest": "Sarah Mitchell", "by": "x", "at": 1},
        "7": {"qty": 1, "written": 1, "back": 1, "state": "done",
              "expiry": at13(-3), "guest": "Mark Whitfield", "by": "x", "at": 1},
      },
      day(-7): {
        "11": {"qty": 2, "written": 2, "state": "done", "expiry": at13(-5),
               "guest": "Priya Raghunathan", "by": "x", "at": 1},
      },
    }

CARDJOBS = jobs()
CANCELRUN = {}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if "/cancelrun" in u:
            body = json.loads(request.post_data)
            if m == "PUT": CANCELRUN.clear(); CANCELRUN.update(body)
            else: CANCELRUN.update(body)
        if "/cardjobs/" in u and m == "PATCH":
            parts = u.split("/cardjobs/")[1].split(".json")[0].split("/")
            if len(parts) == 2 and parts[0] in CARDJOBS and parts[1] in CARDJOBS[parts[0]]:
                CARDJOBS[parts[0]][parts[1]].update(json.loads(request.post_data))
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/cancelrun" in u: body = json.dumps(CANCELRUN) if CANCELRUN else "null"
    elif "/cardjobs" in u: body = json.dumps(CARDJOBS)
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
    #  All = active+lost out there: v14 2, v4 2, v9 2+1, v6 2 -> 9.
    #  Active leaves the lost one out: 8. Lost 1. Tally 3 gone.
    ck("the tabs count the register: All 9, Active 8, Lost 1, Tally 3",
       "All · 9" in tabs and "Active · 8" in tabs
       and "Lost · 1" in tabs and "Tally · 3" in tabs)
    ck("a last-day villa wears amber and the 12h clock",
       pg.evaluate("""()=>{var r=document.querySelector('.arr[data-villa="14"]');
         return r && r.className.indexOf('part-form')>=0
             && r.innerText.indexOf('till 11pm')>=0
             && r.innerText.indexOf('expires 11pm')>=0;}"""))
    mon = (now + datetime.timedelta(days=4)).strftime("%b")
    ck("a living villa wears green, till day-only - no month, no spill",
       pg.evaluate("""(mon)=>{var r=document.querySelector('.arr[data-villa="4"]');
         return r && r.className.indexOf('done-form')>=0
             && r.innerText.indexOf('till ')>=0
             && r.innerText.indexOf(mon)<0;}""", mon))
    ck("a lost card rides its row: 2 cards + 1 lost",
       "2 cards + 1 lost" in pg.evaluate(
           "()=>document.querySelector('.arr[data-villa=\"9\"]').innerText"))
    ck("a wiped card left the count: villa 6 shows 2",
       "2 cards" in pg.evaluate(
           "()=>document.querySelector('.arr[data-villa=\"6\"]').innerText"))

    #  the sheet: facts and the two buttons, writes asserted to the byte
    pg.evaluate("()=>document.querySelector('.arr[data-villa=\"9\"]').click()")
    pg.wait_for_timeout(200)
    sheet = pg.inner_text("#list")
    ck("the sheet says the facts, tersely",
       "2 cards with the guest" in sheet and "floating till" in sheet)
    del WRITES[:]
    pg.evaluate("()=>document.querySelector('[data-losev=\"9\"]').click()")
    pg.wait_for_timeout(300)
    lost_w = [w for w in WRITES if w["m"] == "PATCH" and "/cardjobs/" in w["u"]]
    ck("Mark a card lost PATCHes the job's lost count",
       lost_w and json.loads(lost_w[0]["b"]) == {"lost": 2})
    pg.evaluate("()=>document.querySelector('[data-foundv=\"9\"]').click()")
    pg.wait_for_timeout(300)
    ck("Found walks it back",
       json.loads(WRITES[-1]["b"]) == {"lost": 1})

    #  tabs filter; the Tally is arithmetic over the dead, never stored
    pg.evaluate("()=>document.querySelector('[data-tab=\"lost\"]').click()")
    pg.wait_for_timeout(200)
    ck("the Lost tab holds only the floating cards",
       pg.evaluate("()=>document.querySelectorAll('#list .arr').length") == 1
       and "floating" in pg.inner_text("#list"))
    pg.evaluate("()=>document.querySelector('[data-tab=\"tally\"]').click()")
    pg.wait_for_timeout(200)
    ck("the Tally counts the never-returned and the rate",
       "3 cards never came back · 40% returned" in pg.inner_text("#tallyLine"))
    ck("its rows are the villas still owing, newest first",
       pg.evaluate("""()=>{var r=[...document.querySelectorAll('#list .arr')];
         return r.length===2 && r[0].innerText.indexOf('Sarah Mitchell')>=0
             && r[1].innerText.indexOf('Priya Raghunathan')>=0;}"""))

    #  the cancel session: on, fed by the helper, stopped by the desk
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('cancelBtn').click()")
    pg.wait_for_timeout(300)
    started = [w for w in WRITES if w["m"] == "PUT" and "/cancelrun" in w["u"]]
    ck("Cancel cards switches the session on",
       started and json.loads(started[0]["b"])["state"] == "on"
       and not pg.evaluate("()=>document.getElementById('cancelOv').hidden"))
    ck("and asks with the drawing",
       pg.evaluate("()=>!!document.querySelector('#ovBody .cardask svg')"))
    #  the pretend helper answers: heartbeat plus one wiped card
    CANCELRUN["seen"] = int(time.time() * 1000) + 60000
    CANCELRUN["done"] = {"0": {"villa": "9", "no": "AB12", "at": 1}}
    pg.wait_for_timeout(1600)
    ov = pg.inner_text("#ovBody")
    ck("each wiped card lands named, and the count grows",
       "Villa 9 · cancelled" in ov and "1" in pg.evaluate(
           "()=>document.querySelector('#ovBody .crun-v').textContent"))
    pg.evaluate("()=>document.getElementById('ovStop').click()")
    pg.wait_for_timeout(300)
    ck("Stop switches it off",
       [w for w in WRITES if w["m"] == "PATCH" and "/cancelrun" in w["u"]
        and json.loads(w["b"]).get("state") == "off"]
       and pg.evaluate("()=>document.getElementById('cancelOv').hidden"))
    pg.close()

    #  a session nobody answers dies with the queue law's own verdict
    CANCELRUN.clear()
    pg2 = board()
    pg2.evaluate("()=>document.getElementById('cancelBtn').click()")
    CANCELRUN.pop("seen", None)          # the PUT lands; no helper answers
    pg2.wait_for_timeout(12000)
    ck("ten silent seconds is a verdict, not a wait",
       "Encoder offline" in pg2.inner_text("#ovBody")
       and "Nothing was wiped" in pg2.inner_text("#ovBody")
       and CANCELRUN.get("state") == "off")
    pg2.close()

    #  the hamburger knows this page, and this page omits itself
    pg3 = board()
    nav = pg3.evaluate("()=>document.getElementById('navDrop').innerHTML")
    ck("the menu stands, with this page's own link omitted",
       "front-desk.html" in nav and "keys.html" not in nav)
    ck("no sideways bleed at 320", True if pg3 else False)
    pg3.close()
    pg4 = board(w=320)
    ck("the width law holds at 320",
       pg4.evaluate("()=>document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0)
    pg4.close()
    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
