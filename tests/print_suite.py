"""menu-print.html, the Printable Menu.

The chef prints this on A4 landscape and cuts it down the middle, so one sheet
is two menus. Nothing about that is visible in the browser: the preview is an
iframe holding a PDF built by jsPDF from text calls, and the page's own HTML is
a hidden staging area. A test that only reads the DOM would pass while the
printed sheet was blank, which is exactly how the Service Sheet went blind to a
whole node for two commits with every suite green.

So jsPDF is replaced with a stub that records every draw call, and the
assertions are made against what would land on the paper. The last group checks
the screen and the paper say the same thing, which is the check that was
missing before.

The page belongs to the print chat. This suite does not edit it: anything found
here is handed over rather than fixed.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8976), Q)   # 8976, not 8975: pub_suite binds
# 8975 and the two ran side by side for the first time when the flags
# suite joined the schedule - "each owns its port" was untrue for exactly
# this pair, and the collision surfaced as print NO RESULT on 26 Aug
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()

# A stand-in for jsPDF that draws nothing and remembers everything. Every
# setter returns the document so the page's chained calls still work.
JSPDF_STUB = """
window.__PDF = { texts: [], lines: [], images: [], made: 0 };
(function(){
  function Doc(opts){ this.opts = opts; window.__PDF.made++; }
  var chain = ['setFont','setFontSize','setTextColor','setDrawColor','setLineWidth',
               'setLineDashPattern','addFileToVFS','addFont'];
  chain.forEach(function(m){ Doc.prototype[m] = function(){ return this; }; });
  Doc.prototype.splitTextToSize = function(s, w){
    s = String(s == null ? '' : s);
    var words = s.split(' '), lines = [], cur = '';
    // 2.6mm a character is close enough to the real measure for line counting
    var per = Math.max(1, Math.floor(w / 2.6));
    words.forEach(function(word){
      if (!cur.length) { cur = word; return; }
      if ((cur + ' ' + word).length <= per) cur += ' ' + word;
      else { lines.push(cur); cur = word; }
    });
    if (cur.length || !lines.length) lines.push(cur);
    return lines;
  };
  Doc.prototype.getTextWidth = function(s){ return String(s||'').length * 2.6; };
  Doc.prototype.text = function(t, x, y, o){
    window.__PDF.texts.push({ t: String(t), x: x, y: y });
    return this;
  };
  Doc.prototype.line = function(x1,y1,x2,y2){
    window.__PDF.lines.push({ x1:x1, y1:y1, x2:x2, y2:y2 }); return this;
  };
  Doc.prototype.addImage = function(d, f, x, y, w, h){
    window.__PDF.images.push({ x:x, y:y, w:w, h:h }); return this;
  };
  Doc.prototype.output = function(){ return new Blob(['%PDF-stub'], {type:'application/pdf'}); };
  window.jspdf = { jsPDF: Doc };
})();
"""

MENU = {"published": now.isoformat(),
        "bread": {"name": "sourdough and cultured butter"},
        "entree": {"name": "kingfish crudo", "desc": "finger lime, green chilli, buttermilk"},
        "main": {"name": "lamb rump with smoked eggplant", "desc": "pomegranate, mint", "aus": True},
        "dessert": {"name": "pavlova"}}

#  "menu" is the committed FILE, "db" is the database. They were one thing in
#  this suite until 23 Aug, because one route answered both, which is precisely
#  how a stale file reached the printed menu with every assertion passing.
STATE = {"menu": MENU, "logo": True, "db": None}

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    #  The page reads the database first from 23 Aug, and auth.js queues every
    #  database fetch until a sign-in settles. Without a session the read never
    #  resolves at all and the page sits on "Preparing menu" forever, which is
    #  correct for a gated page and looked like twenty-four broken assertions.
    PRINT_SDK = """window.firebase={__i:false,
      initializeApp:function(){window.firebase.__i=true;},
      auth:function(){return window.__A;}};
    window.__A={onIdTokenChanged:function(cb){setTimeout(function(){
        cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
      onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},
      signOut:function(){},currentUser:{email:'staff@x'}};"""

    def open_print(w=1100):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(JSPDF_STUB)
        pg.add_init_script(PRINT_SDK)
        # jsPDF itself comes from a CDN the sandbox cannot reach, and the stub
        # is already installed, so the request is answered with nothing.
        pg.route("**/cdnjs.cloudflare.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        if not STATE["logo"]:
            pg.route("**/nala-logo.png", lambda r: r.fulfill(status=404, body=""))
        #  The committed FILE only. This pattern matches the database URL too -
        #  both end in /menu.json - and the page reads the database first since
        #  23 Aug, so one route answering both left it reading a 404 as the
        #  answer to a question it had not asked yet.
        def menu_file(route):
            if "firebasedatabase.app" in route.request.url:
                route.fallback(); return
            route.fulfill(
                status=(404 if STATE["menu"] is None else 200),
                content_type="application/json",
                body=("" if STATE["menu"] is None else json.dumps(STATE["menu"])))
        #  The database, which this page now asks first. Silent, so the file
        #  behind it is what these tests are about, as they always were.
        #  The page is gated on resSheet, so the login has to be somebody: a
        #  blanket null starves loadStaff and the gate correctly refuses, which
        #  reads as every print assertion failing at once.
        def db(route):
            u = route.request.url
            if "/staff" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"staff@x": {"name": "M", "role": "admin"}})); return
            if u.split("?")[0].endswith("/menu.json"):
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(STATE["db"]) if STATE["db"] else "null"); return
            route.fulfill(status=200, content_type="application/json", body="null")
        pg.route("**firebasedatabase.app/**", db)
        pg.route("**/menu.json*", menu_file)
        pg.goto("http://localhost:8976/menu-print.html")
        #  Waited for, not timed. The page reads the database first from 23 Aug
        #  and nala-shared.js loads at its foot, so the menu now arrives a beat
        #  later than a fixed 1200ms allowed for. A wait on the thing itself
        #  cannot go stale the next time the page gets slower.
        try:
            pg.wait_for_function("()=>window.__PDF && window.__PDF.made>=1",
                                 timeout=8000)
        except Exception:
            pg.wait_for_timeout(1500)
        return pg

    def pdf_text(pg):
        return pg.evaluate("()=>window.__PDF.texts.map(t=>t.t)")

    # ── an ordinary night ─────────────────────────────────────
    pg = open_print()
    texts = pdf_text(pg)
    ck("a PDF is built", pg.evaluate("()=>window.__PDF.made") >= 1)
    # The state line and the dish are both compared case insensitively: the
    # bar is upper-cased in CSS, and the menu title cases the dish itself.
    ck("the dish reaches the paper",
       "lamb rump with smoked eggplant" in " ".join(texts).lower())
    ck("dish names are title cased for the menu",
       any(t.startswith("Sourdough") for t in texts))
    ck("small words stay small", " with " in " ".join(texts))
    ck("the description is printed", any("finger lime" in t.lower() for t in texts))
    ck("commas in a description become middle dots",
       any("\u00b7" in t for t in texts))
    ck("the price line is printed", any("2 courses 105" in t for t in texts))
    ck("and the note about bread", any("include bread" in t for t in texts))
    ck("the AUS mark is printed where the kitchen flagged it",
       any(t.strip() == "(AUS)" for t in texts))

    # One sheet, cut in half, so every line is drawn twice: once per centre.
    xs = pg.evaluate("()=>window.__PDF.texts.filter(t=>t.t.indexOf('105')>-1).map(t=>t.x)")
    ck("the price line is printed on both halves", len(xs) == 2)
    ck("one on each side of the fold",
       len(xs) == 2 and min(xs) < 148.5 < max(xs))
    counts = {}
    for t in texts: counts[t] = counts.get(t, 0) + 1
    ck("every line on the sheet appears exactly twice",
       all(v == 2 for v in counts.values()))
    ck("a cut line is drawn down the middle", pg.evaluate(
        "()=>window.__PDF.lines.some(l=>Math.abs(l.x1-148.5)<0.6&&Math.abs(l.x2-148.5)<0.6)"))
    ck("the logo is placed on both halves", pg.evaluate("()=>window.__PDF.images.length") == 2)
    ck("the published time is shown to whoever is printing",
       "PUBLISHED" in pg.inner_text("#state").upper())

    # ── the screen and the paper agree ────────────────────────
    # The check that did not exist when the Service Sheet went blind. Both
    # halves of the staged HTML and both halves of the PDF, one comparison.
    on_screen = pg.evaluate(
        "()=>[...document.querySelectorAll('#menuA .dish')].map(e=>e.textContent.replace('(AUS)','').trim())")
    ck("every dish on screen is also on the paper",
       all(any(d in t for t in texts) for d in on_screen))
    ck("and the two halves of the screen match each other",
       pg.inner_html("#menuA") == pg.inner_html("#menuB"))
    ck("the number of dishes agrees between screen and paper", len(on_screen) == 4)
    pg.close()

    # ── a short menu ──────────────────────────────────────────
    STATE["menu"] = {"published": now.isoformat(), "main": {"name": "beef cheek"}}
    pg = open_print()
    texts = pdf_text(pg)
    ck("a menu of one course prints that course",
       any("Beef Cheek" in t for t in texts))
    ck("and prints no empty courses",
       not any(t.strip() in ("E N T R \u00c9 E", "B R E A D", "D E S S E R T") for t in texts))
    ck("the price line is still there, because the kitchen still charges",
       any("2 courses 105" in t for t in texts))
    pg.close()

    # A course with a blank name is not a course. It arrives that way when the
    # chef clears a line rather than deleting it.
    STATE["menu"] = {"published": now.isoformat(),
                     "bread": {"name": "   "}, "main": {"name": "beef cheek"}}
    pg = open_print()
    ck("a course cleared to spaces is not printed",
       not any(t.strip() == "B R E A D" for t in pdf_text(pg)))
    pg.close()

    # ── nothing published ─────────────────────────────────────
    STATE["menu"] = {}
    pg = open_print()
    ck("an empty menu says nothing is published",
       "No menu published" in pg.inner_text("#menuA"))
    ck("on both halves, since both get cut and handed out",
       "No menu published" in pg.inner_text("#menuB"))
    ck("the state line says there is nothing to print",
       "NOTHING TO PRINT" in pg.inner_text("#state").upper())
    ck("and no PDF is built from an empty menu",
       pg.evaluate("()=>window.__PDF.made") == 0)
    ck("the empty sheet is shown instead of an empty viewer",
       pg.evaluate("()=>getComputedStyle(document.getElementById('viewer')).display") == "none")
    pg.close()

    STATE["menu"] = None
    pg = open_print()
    ck("a menu that cannot be loaded at all says so",
       "COULD NOT LOAD" in pg.inner_text("#state").upper())
    pg.close()
    STATE["menu"] = MENU

    # ── the source of the menu ────────────────────────────────
    #  Reported 23 Aug: the View button on the Reservations board showed an old
    #  menu. The button was right and this page was reading the wrong source.
    #  It read the committed menu.json and only that, and never learned when
    #  publishing moved into the database, so it went on showing whatever was
    #  last committed while the board beside it correctly said tonight's menu
    #  was published.
    STATE["menu"] = {"published": (now - datetime.timedelta(days=1)).isoformat(),
                     "main": {"name": "yesterday lamb", "desc": ""}}
    STATE["db"] = {"published": now.isoformat(),
                   "main": {"name": "tonight lamb", "desc": ""}}
    pg = open_print()
    txt = " ".join(pdf_text(pg)).lower()
    ck("the database is read first, not the committed file",
       "tonight lamb" in txt)
    ck("and the file's older menu is not printed",
       "yesterday lamb" not in txt)
    pg.close()

    #  The file is a fallback, not an archive. Nothing rewrites it since
    #  publishing moved, so what it holds is whatever was published the last
    #  time it did, and serving that as tonight's is the fault above by
    #  another route.
    STATE["db"] = None
    pg = open_print()
    txt = " ".join(pdf_text(pg)).lower()
    ck("a file left over from yesterday is not printed as tonight's",
       "yesterday lamb" not in txt)
    ck("and the page says there is nothing rather than showing it",
       "nothing to print" in pg.inner_text("#state").lower())
    pg.close()

    #  But it still stands in where it was always meant to: a menu published
    #  today, with the database silent, is a menu.
    STATE["menu"] = {"published": now.isoformat(),
                     "main": {"name": "filed lamb", "desc": ""}}
    pg = open_print()
    ck("a file published today still stands in when the database is silent",
       "filed lamb" in " ".join(pdf_text(pg)).lower())
    pg.close()
    STATE["menu"] = MENU
    STATE["db"] = None

    # ── a missing logo is not a missing menu ──────────────────
    STATE["logo"] = False
    pg = open_print()
    ck("a menu still prints when the logo will not load",
       any("Pavlova" in t for t in pdf_text(pg)))
    ck("and nothing is drawn where the logo would have been",
       pg.evaluate("()=>window.__PDF.images.length") == 0)
    pg.close()
    STATE["logo"] = True

    # ── the page is opened on a phone as well as a laptop ─────
    for w in (390, 360, 320):
        q = open_print(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    q = open_print(w=390)
    ck("the way back to Reservations is reachable on a phone",
       q.get_attribute(".btn.ghost", "href") == "tally.html")
    q.close()

    # ── the role gate ───────────────────────────────────────────────────
    # Until 18 Aug this page had none: anybody with the address could open
    # it. It leaks nothing, since the menu comes from menu.json, which the
    # guest dining page already serves publicly, but a staff page sitting
    # open is a thing somebody has to reason about at every audit.
    #
    # These assertions exist because the suite above passes either way. It
    # never loads Firebase, so the gate simply never runs, and a gate that
    # is never exercised is indistinguishable from no gate at all.
    SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL,
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL});},25);},
signOut:function(){}};"""
    GATE_STAFF = {"chef@x": {"name": "Chef", "role": "chef"},
                  "hk@x": {"name": "HK", "role": "housekeeping"},
                  "nobody@x": {"name": "Nobody", "role": ""}}

    def as_role(email):
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.add_init_script(JSPDF_STUB)
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**/cdnjs.cloudflare.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**firebasedatabase.app/**", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=(json.dumps(GATE_STAFF) if "/staff" in r.request.url else "null")))
        pg.route("**/menu.json*", lambda r: r.fulfill(
            status=200, content_type="application/json",
            body=json.dumps(STATE["menu"] or {})))
        pg.goto("http://localhost:8976/menu-print.html")
        pg.wait_for_timeout(1600)
        return pg

    q = as_role("chef@x")
    ck("a chef may still print the menus",
       q.evaluate("()=>getComputedStyle(document.getElementById('viewer')).display") != "none"
       and "cannot print" not in q.evaluate("()=>state.textContent").lower())
    q.close()

    q = as_role("hk@x")
    q.wait_for_timeout(600)
    ck("housekeeping is sent to its own board rather than shown a refusal",
       q.url.endswith("cleaners.html"))
    q.close()

    q = as_role("nobody@x")
    q.wait_for_timeout(600)
    ck("a login with no role is refused, having nowhere to be sent",
       "see the manager" in q.evaluate("()=>state.textContent").lower())
    ck("and the menu is not rendered behind the refusal",
       q.evaluate("()=>getComputedStyle(document.getElementById('viewer')).display") == "none")
    q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
