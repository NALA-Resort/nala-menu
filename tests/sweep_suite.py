"""The control sweep.

Every other suite asks whether a particular control does the particular thing it
is supposed to do. This one asks a blunter question of every control on every
page: when a person presses it, does ANYTHING happen?

That is the bug the owner described. "I press a button on the Clean screen and
nothing happens." A button wired to a function that was renamed, a handler
attached to an id that no longer exists, a link to a file that moved. The
feature suites do not catch these, because a suite tests the controls somebody
thought to write a test for, and a dead button is usually one nobody thought
about.

How a control is judged. Fresh page load per control, so no click can be
explained by the one before it. Snapshot the page, click, wait, look again.
Something happened if any of these changed: the URL, the page's own HTML, the
number of database writes, an alert or a print dialog, or which element has
focus. Nothing changed and no error thrown is the failure this suite exists to
report: a control the guest can press that does nothing at all.

Errors are recorded separately from deadness, because they are different bugs.
A control that throws is loud and will be found. A control that silently does
nothing is the one that reaches a guest.

Roles are swept only on the pages they actually reach. A chef sent from the
front desk to the tally board has not found a broken button, they have found
the role gate working, so the sweep records the redirect and moves on.

Run in batches. `python3 tests/sweep_suite.py cleaners front-desk` sweeps those
two; with no argument it sweeps everything, which takes longer than the
sandbox's patience.
"""
import threading, http.server, socketserver, json, time, os, sys, datetime, hashlib

os.chdir('/home/claude/nala')
# Overridable so several sweeps can run at once, one per page. Hard coded, the
# second copy dies on "Address already in use" before it has loaded anything,
# which reads as a broken page rather than a busy port.
PORT = int(os.environ.get("SWEEP_PORT", "8973"))

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

# Dialogs and printing block a real browser forever. Record them instead: both
# count as the page having done something.
TRAPS = """window.__EV=[];
window.alert=function(m){window.__EV.push('alert:'+m);};
window.confirm=function(m){window.__EV.push('confirm:'+m);return true;};
window.prompt=function(m){window.__EV.push('prompt:'+m);return '';};
window.print=function(){window.__EV.push('print');};
window.__ERRS=[];
window.addEventListener('error',function(e){window.__ERRS.push(String(e.message));});
window.addEventListener('unhandledrejection',function(e){
  window.__ERRS.push('unhandled rejection: '+String(e.reason&&e.reason.message||e.reason));});"""

now = datetime.datetime.now().astimezone()

# menu-print.html needs jsPDF, which comes from a CDN the sandbox cannot
# reach. The sweep reaches that page through the board's "Menu published"
# banner, but only on a day the chef has already published, which is why this
# went unseen until 20 Aug. The stand-in is print_suite's, copied rather than
# imported because importing print_suite runs it. If menu-print grows a jsPDF
# call the stub lacks, fix it THERE first; this copy only needs to not throw.
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
today = now.strftime("%Y-%m-%d")
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")

BOOKING = "sweep-booking-0001"

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "hk@x": {"name": "HK", "role": "housekeeping"}}

ROOMGUESTS = {"1": {"name": "James", "departs": today},
              "2": {"name": "Elena", "departs": plus(2)},
              "7": {"name": "Priya", "departs": today}}
HK = {"1": {"kind": "clean"}, "2": {"bfast": now.isoformat()},
      "7": {"done": now.isoformat()}}
BOOKINGS = {BOOKING: {"pms": {"villa": "1", "first": "James", "last": "Reed",
                             "arrive": today, "depart": plus(3),
                             "phone": "", "customerId": "cust-0001"},
                      "prearrival": {"diets": ["gluten"]}}}
MENU = {"bread": {"name": "Sourdough"}, "entree": {"name": "Scallops"},
        "main": {"name": "Barramundi"}, "dessert": {"name": "Pavlova"},
        "published": now.isoformat()}
DINNER = {"1": {"status": "in", "pax": 2, "by": "guest"}}
# front-desk reads s.id, not s.bookingId, and only rows whose arrive matches
# the day key become arrivals. Getting either wrong renders an empty list, and
# a sweep of an empty page proves nothing.
STAYS = {"1": {"id": BOOKING, "first": "James", "last": "Reed",
               "arrive": today, "depart": plus(3), "villa": "1"},
         "2": {"id": BOOKING + "-b", "first": "Elena", "last": "Cruz",
               "arrive": today, "depart": plus(1), "villa": "2"}}
# tag.html stores a plain list of dietary names per course, and calls indexOf
# on it. An object here throws, which is a fixture fault, not a page fault.
MENUTAGS = {"bread": [], "entree": ["gluten"], "main": [], "dessert": []}

WRITES = {"n": 0}

def fb(route, request):
    u = request.url
    if request.method in ("PATCH", "PUT", "POST", "DELETE"):
        WRITES["n"] += 1
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "{}")
        return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif "/roomguests/" + today in u: body = json.dumps(ROOMGUESTS)
    elif "/hk/" + today in u: body = json.dumps(HK)
    elif "/bookings/" + BOOKING + "/pms" in u: body = json.dumps(BOOKINGS[BOOKING]["pms"])
    elif "/bookings/" + BOOKING + "/prearrival" in u: body = json.dumps(BOOKINGS[BOOKING]["prearrival"])
    elif "/bookings/" + BOOKING in u: body = json.dumps(BOOKINGS[BOOKING])
    elif "/bookings" in u: body = json.dumps(BOOKINGS)
    # /menutags/ contains "/menu", so it has to be tested first or the tag
    # board is served the nightly menu and renders nothing.
    elif "/menutags/" in u: body = json.dumps(MENUTAGS)
    elif "/menuhistory" in u: body = "null"
    elif "/menu" in u: body = json.dumps(MENU)
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays" in u: body = json.dumps({today: STAYS})
    elif "/responses/" in u: body = "null"
    route.fulfill(status=200, content_type="application/json", body=body)

# Guest pages carry the booking in the link. Loaded bare they show a blocked
# state with nothing on it, and a sweep would call that a clean page.
GUEST_QS = ("?b=" + BOOKING + "&n=James&s=Reed&a=" + today + "&d=" + plus(3))

PAGES = [
    ("cleaners.html",     ""),
    ("front-desk.html",   ""),
    ("tally.html",        ""),
    ("tag.html",          ""),
    ("staff.html",        ""),
    ("stats.html",        ""),
    ("registration.html", ""),
    ("debug.html",        ""),
    ("pages.html",        ""),
    ("index.html",        GUEST_QS),
    ("prearrival.html",   GUEST_QS),
    ("welcome.html",      GUEST_QS),
]
ROLES = [("staff@x", "admin"), ("chef@x", "chef"),
         ("waiter@x", "waiter"), ("hk@x", "housekeeping")]

# A handful of controls do nothing on purpose and would otherwise be reported
# forever. Each needs a reason, and "it was failing" is not one.
EXPECTED_INERT = {
    # page, descriptor fragment : why
    ("pages.html", "a.p"): "the site map's own links are opened by pages_suite",
    ("tag.html", "#addBtn"): ("Add dietary returns on an empty box, which is "
                              "correct. Worth knowing that it gives the chef "
                              "no hint about why nothing happened."),
    # applyToSelected returns immediately on an empty selection, by design.
    # The sweep turns select mode on but cannot know to tick a room first.
    ("tally.html", "sbVac"): "bulk action with nothing selected does nothing",
    ("tally.html", "sbDin"): "bulk action with nothing selected does nothing",
    ("tally.html", "sbOut"): "bulk action with nothing selected does nothing",
    ("tally.html", "sbClear"): "bulk action with nothing selected does nothing",
}

VIS_FILTER = """(e)=>{
  const r=e.getBoundingClientRect(), s=getComputedStyle(e);
  if(r.width<1||r.height<1) return false;
  if(s.visibility==='hidden'||s.display==='none'||s.pointerEvents==='none') return false;
  if(e.disabled) return false;
  /* A bar parked below the screen with transform:translateY is still in the
     document and still has a size. A fixed element has to be on screen now,
     because scrolling will never reach it; anything else only has to be
     somewhere the page can scroll to. */
  let fixed=false;
  for(let a=e; a && a!==document.documentElement; a=a.parentElement){
    const p=getComputedStyle(a).position;
    if(p==='fixed'||p==='sticky'){ fixed=true; break; }
  }
  if(fixed) return !(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth);
  return r.top+scrollY < document.documentElement.scrollHeight;
}"""

VIS_SEL = ("button,a[href],[onclick],[role=button],"
           "input[type=submit],input[type=button]")

ENUM = """(()=>{
 const ok=%s;
 const out=[];
 document.querySelectorAll(%s).forEach(e=>{
   if(!ok(e)) return;
   const label=(e.textContent||'').trim().slice(0,28).replace(/\\s+/g,' ');
   out.push({tag:e.tagName.toLowerCase(), id:e.id||'',
             cls:(e.className||'').toString().split(' ').filter(Boolean)[0]||'',
             label:label, href:e.getAttribute('href')||''});
 });
 return out;})""" % (VIS_FILTER, json.dumps(VIS_SEL))

VIS_INDEX = """((i)=>{
  const ok=%s;
  const all=[...document.querySelectorAll(%s)];
  return all.indexOf(all.filter(ok)[i]);})""" % (VIS_FILTER, json.dumps(VIS_SEL))


SNAP = """()=>({url:location.href,
 /* The whole page, not the first few thousand characters. Sheet content sits
    deep in the body, so a sliced snapshot missed every change inside an open
    sheet and reported nineteen live controls as dead. Selecting a different
    cover count moves a class from one button to another and leaves the length
    identical, so length alone is not enough either. */
 html:(function(h){var x=5381,i=h.length;while(i)x=(x*33^h.charCodeAt(--i))>>>0;
   return h.length+':'+x;})(document.body.innerHTML),
 focus:(document.activeElement&&(document.activeElement.id||document.activeElement.tagName))||'',
 fmark:(document.activeElement&&document.activeElement.dataset&&document.activeElement.dataset.sweepTarget)||'',
 chosen:(function(){var e=document.querySelector('[data-sweep-target="1"]');
   if(!e) return false;
   if(e.getAttribute('aria-pressed')==='true') return true;
   if(e.getAttribute('aria-current')) return true;
   var c=' '+(e.className||'')+' ';
   return c.indexOf(' on ')>=0||c.indexOf(' active ')>=0
       ||c.indexOf(' selected ')>=0||c.indexOf(' current ')>=0;})(),
 ev:(window.__EV||[]).length,
 errs:(window.__ERRS||[]).slice()})"""


def handle_at(pg, i):
    return pg.locator(VIS_SEL).nth(pg.evaluate(VIS_INDEX, i))


def bring_into_view(h):
    """Sheet buttons open below the fold. Scroll the page, not just the
    element: the sheet is static inside the document, so the window is what
    has to move."""
    try:
        h.scroll_into_view_if_needed(timeout=2500)
    except Exception:
        pass
    try:
        h.evaluate("e=>{const r=e.getBoundingClientRect();"
                   "if(r.bottom>innerHeight||r.top<0)"
                   "window.scrollBy(0, r.top-innerHeight/2);}")
    except Exception:
        pass


def click_control(h):
    """Returns True if a real click landed, False if it took a scripted one.
    A control that can only be reached by script is worth knowing about: on a
    real phone it may be a control nobody can press."""
    try:
        h.click(timeout=3500, force=True)
        return True
    except Exception:
        h.evaluate("e=>e.click()")
        return False


def press(pg, i):
    h = handle_at(pg, i)
    bring_into_view(h)
    click_control(h)


# Twenty villa tiles open the same sheet. Two of each class of opener is
# enough to prove the buttons behind it are wired; more is only slower.
DEPTH2_PER_KIND = 2

P = F = 0
FAILURES = []
OFFSCREEN = []
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    if cond:
        P += 1
    else:
        F += 1
        FAILURES.append(name + ((" | " + detail) if detail else ""))

args = [a.lower() for a in sys.argv[1:]]
ROLE_NAMES = {"admin", "chef", "waiter", "housekeeping"}
want_roles = [a for a in args if a in ROLE_NAMES]
want = [a for a in args if a not in ROLE_NAMES]
pages = [p for p in PAGES if not want or any(w in p[0] for w in want)]

from playwright.sync_api import sync_playwright

def index_of(pg, want):
    hits = [k for k, c in enumerate(pg.evaluate(ENUM)) if descriptor(c) == want]
    if os.environ.get("SWEEP_DEBUG") and len(hits) > 1:
        print("   AMBIGUOUS", want, "matches", len(hits), "controls")
    return hits[0] if hits else -1


def descriptor(c):
    bits = c["tag"]
    if c["id"]: bits += "#" + c["id"]
    elif c["cls"]: bits += "." + c["cls"]
    if c["label"]: bits += ' "' + c["label"] + '"'
    return bits

with sync_playwright() as p:
    b = p.chromium.launch()

    def open_page(email, page, qs, width=390):
        pg = b.new_page(viewport={"width": width, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script(TRAPS)
        pg.add_init_script(JSPDF_STUB)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/cdnjs.cloudflare.com/**", lambda r: r.fulfill(status=200, body=""))
        failed = []
        pg.on("requestfailed", lambda r: failed.append(r.url.split("/")[-1][:50]))
        # A link that navigates to a missing page still changes the URL, and
        # the first version of this suite counted that as the control working.
        # Watch what the navigation actually returned.
        bad = []
        def _resp(r):
            try:
                if r.request.resource_type == "document" and r.status >= 400:
                    bad.append("%d %s" % (r.status, r.url.split("/")[-1][:40]))
            except Exception:
                pass
        pg.on("response", _resp)
        pg.on("pageerror", lambda e: None)   # captured in-page by TRAPS
        pg.goto("http://localhost:%d/%s%s" % (PORT, page, qs), timeout=12000)
        pg.wait_for_timeout(750)
        return pg, failed, bad

    swept = dead = threw = broken = 0
    depth2_used = {}

    # ── layout at the three phone widths ────────────────────────────────
    # The click sweep runs at 390 only, because a handler that is not wired
    # is not wired at any size and pressing everything three times over would
    # treble an already slow run. What does change with width is layout, so
    # that is checked separately and for every page and role.
    #
    # 390 is the mock width, 360 the common Android, 320 the narrowest phone
    # still in use. A page that scrolls sideways on a phone is read one
    # handed during service, so a column pushed off the edge is invisible
    # rather than merely awkward.
    for page, qs in pages:
        for email, role in ROLES:
            if want_roles and role not in want_roles:
                continue
            for w in (390, 360, 320):
                try:
                    pg, failed, bad = open_page(email, page, qs, width=w)
                except Exception as ex:
                    ck("%s as %s at %dpt loads" % (page, role, w), False, str(ex)[:70])
                    continue
                if pg.url.split("/")[-1].split("?")[0] != page:
                    pg.close(); continue
                m = pg.evaluate("""()=>{
                  const de=document.documentElement;
                  const over=[...document.querySelectorAll('body *')].filter(e=>{
                    const r=e.getBoundingClientRect();
                    if(r.width<1||r.height<1) return false;
                    const s=getComputedStyle(e);
                    if(s.position==='fixed') return false;
                    /* A scroller is allowed to be wider than the screen: that
                       is what it is for. Only the page itself must not be. */
                    let p=e.parentElement;
                    while(p){ const ps=getComputedStyle(p);
                      if(ps.overflowX==='auto'||ps.overflowX==='scroll') return false;
                      p=p.parentElement; }
                    return r.right > de.clientWidth + 1;})
                    .map(e=>(e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+
                             ((e.className||'').toString().split(' ')[0]||'')));
                  return {vw:de.clientWidth, sw:de.scrollWidth,
                          over:[...new Set(over)].slice(0,4)};}""")
                ck("%s as %s does not scroll sideways at %dpt" % (page, role, w),
                   m["sw"] <= m["vw"] + 1, ", ".join(m["over"]))
                pg.close()


    for page, qs in pages:
        for email, role in ROLES:
            if want_roles and role not in want_roles:
                continue
            try:
                pg, failed, bad = open_page(email, page, qs)
            except Exception as ex:
                ck("%s as %s loads" % (page, role), False, str(ex)[:80])
                continue

            landed = pg.url.split("/")[-1].split("?")[0]
            if landed != page:
                print("SKIP %s as %s -> sent to %s (role gate)" % (page, role, landed))
                pg.close()
                continue

            ctrls = pg.evaluate(ENUM)
            load_errs = pg.evaluate("()=>window.__ERRS||[]")
            ck("%s as %s loads without error" % (page, role),
               not load_errs, "; ".join(load_errs[:3]))
            ck("%s as %s has controls to press" % (page, role), len(ctrls) > 0)
            pg.close()

            for i, c in enumerate(ctrls):
                d = descriptor(c)
                if any(page == ep and frag in d for (ep, frag) in EXPECTED_INERT):
                    continue
                swept += 1
                try:
                    pg, failed, bad = open_page(email, page, qs)
                    del bad[:]
                    live = pg.evaluate(ENUM)
                    if i >= len(live):
                        pg.close(); continue
                    w0 = WRITES["n"]
                    handle = handle_at(pg, i)
                    bring_into_view(handle)
                    try: handle.scroll_into_view_if_needed(timeout=2000)
                    except Exception: pass
                    handle.evaluate("e=>e.dataset.sweepTarget='1'")
                    before = pg.evaluate(SNAP)
                    real = click_control(handle)
                    if not real: OFFSCREEN.append("%s as %s: %s" % (page, role, d))
                    pg.wait_for_timeout(320)
                    after = pg.evaluate(SNAP)
                    landed_bad = list(bad)
                    errs = [e for e in after["errs"] if e not in before["errs"]]
                    # Focus only counts when it lands somewhere OTHER than the
                    # control just pressed. Clicking anything focuses it, so a
                    # bare focus change is true of a dead button too, and
                    # counting it made this suite pass its own planted fault.
                    focus_moved = (after["focus"] != before["focus"]
                                   and after["fmark"] != "1")
                    moved = (after["url"] != before["url"]
                             or after["html"] != before["html"]
                             or focus_moved
                             or after["ev"] != before["ev"]
                             or WRITES["n"] != w0)
                    if errs:
                        threw += 1
                        ck("%s as %s: %s throws nothing" % (page, role, d),
                           False, "; ".join(errs[:2]))
                    else:
                        ck("%s as %s: %s throws nothing" % (page, role, d), True)
                    if landed_bad:
                        broken += 1
                        ck("%s as %s: %s goes somewhere real" % (page, role, d),
                           False, "; ".join(landed_bad[:2]))
                    if not moved and before["chosen"]:
                        ck("%s as %s: %s is already chosen, so does nothing"
                           % (page, role, d), True)
                    else:
                        if not moved:
                            dead += 1
                        ck("%s as %s: %s does something" % (page, role, d), moved)

                    # Depth two. Opening a villa on the Cleans screen reveals
                    # "Mark as cleaned", "Push villa", "Guest departed": the
                    # buttons that do the actual work, and the ones a person
                    # means when they say they pressed something and nothing
                    # happened. A sweep that only presses what is on screen at
                    # load never reaches them.
                    opened = []
                    kind = (c["tag"] + "." + c["cls"]) if not c["id"] else ("#" + c["id"])
                    budget = DEPTH2_PER_KIND - depth2_used.get((page, role, kind), 0)
                    if budget > 0 and not landed_bad and after["url"] == before["url"]:
                        now_ctrls = pg.evaluate(ENUM)
                        seen = set(descriptor(x) for x in live)
                        opened = [x for x in now_ctrls
                                  if descriptor(x) not in seen]
                        if opened:
                            depth2_used[(page, role, kind)] = \
                                depth2_used.get((page, role, kind), 0) + 1
                    pg.close()

                    for c2 in opened:
                        d2 = descriptor(c2)
                        if any(page == ep and frag in d2
                               for (ep, frag) in EXPECTED_INERT):
                            continue
                        swept += 1
                        try:
                            pg2, failed2, bad2 = open_page(email, page, qs)
                            press(pg2, i)
                            # The sheet finishes painting after its own reads
                            # land. Clicking into a half painted sheet lets the
                            # repaint wipe the change, which reads as a dead
                            # button.
                            pg2.wait_for_timeout(750)
                            j = index_of(pg2, d2)
                            if j < 0:
                                pg2.close(); swept -= 1; continue
                            del bad2[:]
                            w1 = WRITES["n"]
                            h2 = handle_at(pg2, j)
                            bring_into_view(h2)
                            try: h2.scroll_into_view_if_needed(timeout=2000)
                            except Exception: pass
                            h2.evaluate("e=>e.dataset.sweepTarget='1'")
                            b2 = pg2.evaluate(SNAP)
                            real2 = click_control(h2)
                            if not real2: OFFSCREEN.append(label)
                            pg2.wait_for_timeout(320)
                            a2 = pg2.evaluate(SNAP)
                            e2 = [e for e in a2["errs"] if e not in b2["errs"]]
                            fm2 = (a2["focus"] != b2["focus"] and a2["fmark"] != "1")
                            mv2 = (a2["url"] != b2["url"] or a2["html"] != b2["html"]
                                   or fm2 or a2["ev"] != b2["ev"]
                                   or WRITES["n"] != w1)
                            label = "%s as %s: %s > %s" % (page, role, d, d2)
                            if e2:
                                threw += 1
                                ck(label + " throws nothing", False, "; ".join(e2[:2]))
                            else:
                                ck(label + " throws nothing", True)
                            if bad2:
                                broken += 1
                                ck(label + " goes somewhere real", False,
                                   "; ".join(bad2[:2]))
                            if os.environ.get("SWEEP_DEBUG") and not mv2:
                                print("   DEBUG", d2,
                                      "| urlsame", a2["url"]==b2["url"],
                                      "| html b", b2["html"], "a", a2["html"],
                                      "| focus", b2["focus"], a2["focus"],
                                      "| chosen", b2["chosen"])
                            if not mv2 and b2["chosen"]:
                                ck(label + " is already chosen, so does nothing", True)
                            else:
                                if not mv2:
                                    dead += 1
                                ck(label + " does something", mv2)
                            pg2.close()
                        except Exception as ex:
                            ck("%s as %s: %s > %s is clickable" % (page, role, d, d2),
                               False, str(ex)[:90])
                            try: pg2.close()
                            except Exception: pass
                except Exception as ex:
                    ck("%s as %s: %s is clickable" % (page, role, d),
                       False, str(ex)[:90])
                    try: pg.close()
                    except Exception: pass

    b.close()

print("\n--- sweep ---")
print("controls pressed:", swept)
print("threw an error:", threw)
print("did nothing:", dead)
print("led to a missing page:", broken)
if OFFSCREEN:
    print("\nreachable only by script, check these can be pressed on a phone:")
    for o in OFFSCREEN[:15]: print("  " + o)
print("\nPASS %d  FAIL %d" % (P, F))
if FAILURES:
    print("\nfailures:")
    for f in FAILURES: print("  " + f)
httpd.shutdown()
