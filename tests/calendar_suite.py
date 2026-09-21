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
put(12, "b4", "Katelyn", "Tree", plus(-40), plus(40))
# fully inside the month BEHIND: the owner's 12 Sep rule - the board
# reaches a month back so near history is a swipe, not a date jump
put(5, "b5", "Carlo", "Sacco", plus(-21), plus(-18))
PRE = {"b1": {"at": now.isoformat(), "dining": True, "noDiets": True, "wellness": False},
       "b3": {"dining": True}}
SPA = {}
HK = {}                      # the day's housekeeping record; the Clean dot reads it
STATE = {"failDays": set()}

def fb(route, request):
    u = request.url
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif "/spa.json" in u: body = json.dumps(SPA) if SPA else "null"
    elif "/hk/" in u: body = json.dumps(HK) if HK else "null"
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
# ── the selector reads owners, it does not re-derive (rule 7) ───────
ck("dining colour reads diningState, the dinner-intent owner",
   "diningState(" in PAGE)
ck("spa colour reads massageState, the spa-loop owner",
   "massageState(" in PAGE)
ck("the clean state reads roomCleanState, not the dates re-worked",
   "roomCleanState(" in PAGE)
ck("the clean flag window is arrivalFlagsClean, owned in one place",
   "arrivalFlagsClean(" in PAGE)
ck("the colour-state selector is on the page, Clean among its modes",
   'id="modes"' in PAGE and 'data-m="clean"' in PAGE and 'data-m="spa"' in PAGE)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    # ── the colour-state selector, by computed colour ──────────────────
    #  render() is driven directly with a fixed fixture, so this asserts the
    #  paint - the tile contract between boards - without the board's network
    #  reads, and it pins the CSS/JS class contract every mode depends on.
    #  Green/amber/terracotta/grey are the colour law's, shared with
    #  Reservations, the Front Desk and Spa; a rename there fails here.
    pgc = b.new_page(viewport={"width": 390, "height": 844})
    pgc.add_init_script(SDK)
    pgc.goto("http://localhost:8985/calendar.html")
    pgc.wait_for_timeout(700)
    paint = pgc.evaluate("""()=>{
      function dk(o){ var d=new Date(); d.setDate(d.getDate()+o);
        return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+
               '-'+String(d.getDate()).padStart(2,'0'); }
      function bk(v,id,a,dp,pre){ return {id:id,villa:String(v),
        stay:{id:id,first:'F',last:'L'+v,arrive:a,depart:dp},pre:pre}; }
      var bookings={
        b1:bk(1,'b1',dk(-1),dk(3),{at:new Date().toISOString(),dining:true,noDiets:true,wellness:false}),
        b2:bk(2,'b2',dk(-1),dk(3),{dining:false}),
        b3:bk(3,'b3',dk(-1),dk(3),null),
        b4:bk(4,'b4',dk(-1),dk(3),{wellness:true}),
        b5:bk(5,'b5',dk(0),dk(3),null),
        b6:bk(6,'b6',dk(3),dk(6),null)
      };
      var spa={ b1:{t:{status:'booked'}}, b4:{} };
      var nightBy={}; nightBy[dk(0)]={
        '1':{arrive:dk(-1),depart:dk(3)}, '2':{arrive:dk(-1),depart:dk(3)},
        '3':{arrive:dk(-1),depart:dk(3)}, '4':{arrive:dk(-1),depart:dk(3)},
        '5':{arrive:dk(-3),depart:dk(0)}, '6':{arrive:dk(-3),depart:dk(0)} };
      var hk={ '1':{done:true} };   // v1 serviced -> cleaned; v5/v6 depart today -> dirty
      render(bookings, spa, 0, hk, nightBy);
      var W=document.getElementById('wrap');
      function setMode(m){ W.className='chartwrap m-'+m; }
      function bar(v){ return document.querySelectorAll('.vrow')[v-1].querySelector('.bar'); }
      function fill(v){ return getComputedStyle(bar(v)).backgroundColor; }
      function rowcls(v){ return document.querySelectorAll('.vrow')[v-1].className; }
      var o={};
      setMode('form');   o.form=[fill(1),fill(2),fill(3)];
      setMode('dining'); o.din=[fill(1),fill(2),fill(3)];
      setMode('spa');    o.spa=[fill(1),fill(3),fill(4)];
      setMode('clean');
      o.cleanpill=fill(1);
      o.dotshown=getComputedStyle(document.querySelector('.rmdot')).display;
      o.rows={v1:rowcls(1), v5:rowcls(5), v6:rowcls(6)};
      o.v5vnum=getComputedStyle(document.querySelectorAll('.vrow')[4].querySelector('.vnum')).backgroundColor;
      return o;
    }""")
    GREEN="rgba(122, 160, 130, 0.26)"; AMBER="rgb(246, 234, 213)"
    TERRA="rgba(184, 106, 90, 0.16)"
    def grey(c): return c.startswith("rgba(28, 28, 26, 0.04")
    ck("Pre-arrival paints completed green, incomplete amber, not-started grey",
       paint["form"][0]==GREEN and paint["form"][1]==AMBER and grey(paint["form"][2]))
    ck("Dining paints in green, out terracotta, no-answer grey",
       paint["din"][0]==GREEN and paint["din"][1]==TERRA and grey(paint["din"][2]))
    ck("Spa paints booked green, none the sunk transparent, to-answer grey",
       paint["spa"][0]==GREEN and paint["spa"][1]=="rgba(0, 0, 0, 0)" and grey(paint["spa"][2]))
    ck("Clean greys every pill - the room's status is not the booking's",
       grey(paint["cleanpill"]))
    ck("the clean dot shows only on the Clean screen", paint["dotshown"]=="block")
    ck("a serviced occupied room reads cleaned, no flag",
       "rm-clean" in paint["rows"]["v1"] and "flag" not in paint["rows"]["v1"])
    ck("requires cleaning + arrival within 2 days flags the row amber",
       "rm-dirty" in paint["rows"]["v5"] and "flag" in paint["rows"]["v5"]
       and paint["v5vnum"]==AMBER)
    ck("requires cleaning but arrival further off is the dot alone, no flag",
       "rm-dirty" in paint["rows"]["v6"] and "flag" not in paint["rows"]["v6"])
    pgc.close()

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
       len(bars(pg)) == 5 and "Christison, Adam" in bl and "Vlahov, Kim" in bl)
    ck("the window reaches a month back: a stay three weeks ago is on "
       "the board to swipe to", "Sacco, Carlo" in bl)
    ck("and the board opens on the viewed day, not on the month behind",
       pg.eval_on_selector("#wrap", "e=>e.scrollLeft") == 29 * 64)
    #  The label names the month under the LEFT EDGE and follows the
    #  swipe. Computed once from the window's first day it said August
    #  into mid-September - the owner's live find, 12 Sep.
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    def month_of(days):
        d = now + datetime.timedelta(days=days)
        return "%s %d" % (MONTHS[d.month - 1], d.year)
    ck("the month label names the day under the left edge on open",
       pg.eval_on_selector("#monthLbl", "e=>e.textContent") == month_of(-1))
    pg.eval_on_selector("#wrap", "e=>{e.scrollLeft=0;}")
    pg.wait_for_timeout(150)
    ck("swiped to the window's start, it names the month behind",
       pg.eval_on_selector("#monthLbl", "e=>e.textContent") == month_of(-30))
    pg.eval_on_selector("#wrap", "e=>{e.scrollLeft=e.scrollWidth;}")
    pg.wait_for_timeout(150)
    #  The leftmost visible day at full scroll depends on viewport width,
    #  so the expected month comes from the landed scroll position, not
    #  from a guessed day count - a guess false-fails near month ends.
    end_i = pg.eval_on_selector("#wrap", "e=>Math.floor(e.scrollLeft/64)")
    ck("swiped to the window's end, it names the month ahead",
       end_i > 40 and
       pg.eval_on_selector("#monthLbl", "e=>e.textContent") == month_of(end_i - 30))
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
    ck("the default board fits every villa on one screen, no page scroll",
       pg.evaluate("()=>document.documentElement.scrollHeight - "
                   "document.documentElement.clientHeight") <= 0)
    #  The first publish put the header at the screen's absolute top - the
    #  page frame every board hand-sets was missing (the owner's 12 Sep
    #  screenshot). The daterow must start below the page's own padding.
    ck("the page frame holds the header off the screen top",
       pg.evaluate("()=>document.querySelector('.daterow')"
                   ".getBoundingClientRect().top") >= 20)
    pg.close()

    #  The fit is MEASURED, not a hard-coded chrome guess: on a taller
    #  phone with a taller header the rows must still end inside the
    #  screen. 430x932 is the large iPhone the guess failed on.
    pg = board(w=430, h=932)
    ck("the fitted board ends inside a large phone's screen too",
       pg.evaluate("()=>document.documentElement.scrollHeight - "
                   "document.documentElement.clientHeight") <= 0
       and len(bars(pg)) == 5)
    pg.close()

    # ── the board is broad, the detail behind it is not ─────────
    pg = board(email="housekeeping@x")
    ck("housekeeping sees the board - it is who the board is for",
       pg.url.endswith("calendar.html") and len(bars(pg)) == 5)
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
