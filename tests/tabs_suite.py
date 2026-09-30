"""The tab bar: icons along the foot of the screen for the pages used most.

Asked by the owner, 30 Sep: one icon a page, five at most, and a page a
login cannot open is not there; the admin's five are Dashboard,
Reservations, Cleans, Chat and Tasks. buildTabs in nala-shared.js draws it
from TABBAR, and tests/nav_canon.json ("tabs") is what this suite expects of
it: the order, the cap, and what each role is offered with Chat and Tasks
shut and open. The phone_cases.json pattern: the app's list and the canon
answer to each other, and whichever side a change misses fails by name.

  1. The canon and the app agree: the order, the cap, every page on the bar
     a board on the menu's top level with a drawing of its own.
  2. Each role is offered what the canon says, on the shipped grants, with
     the preview pages shut and then open, and a page switched off for a
     role in Settings leaves its bar.
  3. As drawn: the icons in order under their menu names, the page you are
     on marked and not a link, every other one a link to a page that is
     served, and no bar for a login with one page or no staff record.
  4. Nothing sits under it: the page's footer stands on it - sticky, fixed,
     and Publish's bar - a sheet and the select and save bars cover it, and
     the foot of a long page scrolls clear of it.
  5. The menu's counts ride on its icons, and not on the page you are on.
  6. It fits: every label whole at 390, no sideways scroll at 320, and
     under 600pt of height it steps aside so the boards keep their room.
  7. It is on every ui2 page with a menu, and on no printed sheet, on
     screen or on paper.

The night is tests/paper_night.json, read through tests/night_harness.py,
with a login for each role added here.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, glob, re
import urllib.request

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
PORT = 8968
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

import night_harness
from night_harness import TREE, CLOCK, fb

CANON = json.load(open("tests/nav_canon.json"))
TABS = CANON["tabs"]
LABEL = {h: t for h, t in CANON["top"]}
ROLES = ["admin", "manager", "chef", "waiter", "housekeeping", "spa"]
EMAIL = {r: r + "@x" for r in ROLES}
EMAIL["admin"] = "staff@x"            # the night's own admin, Ana
for r in ROLES:
    TREE["staff"].setdefault(EMAIL[r], {"name": r.title(), "role": r})
PREVIEW_OPEN = {"open": {"guest-contact": True, "tasks": True}}

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL,
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL});},25);},
signOut:function(){}};"""

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else "  -> " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

def open_as(b, email, page, w=390, h=844, perms=None):
    """A page on the fixture night, signed in as email, settled."""
    if perms is None: TREE.pop("permissions", None)
    else: TREE["permissions"] = perms
    ctx = b.new_context(viewport={"width": w, "height": h}, timezone_id="Australia/Brisbane")
    pg = ctx.new_page()
    pg.clock.set_fixed_time(CLOCK)
    pg.add_init_script(SDK)
    pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
    pg.route("**firebasedatabase.app/**", fb)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
    # The Workers (push, Chat, the SMS sends): nothing here asks them anything
    # that matters, and the sandbox cannot reach them.
    pg.route("**.workers.dev/**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
    pg.goto("http://localhost:%d/%s" % (PORT, page))
    pg.wait_for_timeout(2000)
    return ctx, pg

def press(pg, sel):
    """Press something the way a finger does. A press that cannot land - the
    thing is covered, or gone - is reported by the check that needed it,
    never thrown: one blocked press must not end the run unreported."""
    try:
        pg.click(sel, timeout=5000)
        return None
    except Exception as e:
        return "the press did not land: " + str(e).split("\n")[0][:90]

BAR = """()=>{const b=document.getElementById('tabBar');
  if(!b) return null;
  const cs=getComputedStyle(b), r=b.getBoundingClientRect();
  return {shown:cs.display!=='none', top:r.top, bottom:r.bottom, h:r.height,
    hastabs:document.body.classList.contains('hastabs'),
    tabs:[...b.querySelectorAll('.tabrow > a')].map(a=>({id:a.id,
      href:a.getAttribute('href'), cur:a.getAttribute('aria-current'),
      label:a.querySelector('.tablbl').textContent,
      icon:a.querySelectorAll('svg > *').length,
      badge:(a.querySelector('.navbadge')||{}).textContent||''}))};}"""

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    # ── 1. the canon and the app agree ─────────────────────────────────
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    app = pg.evaluate("""()=>({order:TABBAR, max:TABBAR_MAX,
        top:NAV.filter(e=>e.href).map(e=>e.href),
        icons:TABBAR.map(h=>(TAB_ICONS[h]||'').length)})""")
    ck("TABBAR is the canon's order", app["order"] == TABS["order"], app["order"])
    ck("TABBAR_MAX is the canon's five", app["max"] == TABS["max"] == 5, app["max"])
    ck("every page on the bar is a board on the menu's top level",
       all(h in app["top"] and h in LABEL for h in app["order"]))
    ck("and every one has a drawing of its own", all(n > 0 for n in app["icons"]), app["icons"])
    ck("the admin's five lead the order: Dashboard, Reservations, Cleans, Chat, Tasks",
       [LABEL[h] for h in TABS["order"][:5]] == ["Dashboard", "Reservations", "Cleans", "Chat", "Tasks"])

    # ── 2. what each role is offered ───────────────────────────────────
    got = pg.evaluate("""([roles, open])=>{const out={shut:{},open:{}};
        setPermissions(null); roles.forEach(r=>out.shut[r]=tabsFor(r));
        setPermissions(open); roles.forEach(r=>out.open[r]=tabsFor(r));
        setPermissions(null); return out;}""", [ROLES, PREVIEW_OPEN])
    for r in ROLES:
        ck("%s, Chat and Tasks still the admin's: %s" % (r, [LABEL[h] for h in TABS["roles"][r]] or "no bar"),
           got["shut"][r] == TABS["roles"][r], got["shut"][r])
        ck("%s, Chat and Tasks open: %s" % (r, [LABEL[h] for h in TABS["roles_open"][r]] or "no bar"),
           got["open"][r] == TABS["roles_open"][r], got["open"][r])
    ck("never more than five, whoever it is",
       all(len(v) <= 5 for s in got.values() for v in s.values()))
    # A page switched off for a role in Settings leaves the bar, and the next
    # page the role may open takes the place.
    off = pg.evaluate("""(open)=>{
        setPermissions(Object.assign({pages:{tally:{waiter:false}}}, open));
        const t=tabsFor('waiter'); setPermissions(null); return t;}""", PREVIEW_OPEN)
    ck("a page switched off for the waiter leaves the waiter's bar",
       off == ["dashboard.html", "cleaners.html", "guest-contact.html", "tasks.html", "front-desk.html"], off)
    # canOpen calls a page nobody listed ungated. The bar must not believe it.
    stray = pg.evaluate("""()=>{TABBAR.unshift('nowhere.html');
        const t=tabsFor('admin'); TABBAR.shift(); return t;}""")
    ck("a page missing from the menu is never offered", "nowhere.html" not in stray, stray)
    ck("no role, no bar", pg.evaluate("()=>tabsFor(null)") == [])
    ctx.close()

    # ── 3. as drawn ───────────────────────────────────────────────────
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    bar = pg.evaluate(BAR)
    ck("the admin's Reservations wears the bar", bool(bar and bar["shown"]), bar)
    if bar:
        ck("its icons, in order, under their menu names",
           [(t["label"]) for t in bar["tabs"]] == [LABEL[h] for h in TABS["roles"]["admin"]],
           [t["label"] for t in bar["tabs"]])
        ck("every icon is drawn", all(t["icon"] > 0 for t in bar["tabs"]))
        cur = [t for t in bar["tabs"] if t["cur"]]
        ck("the page you are on is marked, once, and is not a link",
           len(cur) == 1 and cur[0]["id"] == "tab-tally" and cur[0]["cur"] == "page"
           and cur[0]["href"] is None, cur)
        others = [t["href"] for t in bar["tabs"] if not t["cur"]]
        ck("every other icon is a link to its page",
           others == [h for h in TABS["roles"]["admin"] if h != "tally.html"], others)
        dead = [h for h in others
                if urllib.request.urlopen("http://localhost:%d/%s" % (PORT, h), timeout=10).getcode() != 200]
        ck("and every one of those pages is served", not dead, dead)
        ck("the page makes room for it", bar["hastabs"])
        # Pressed, an icon goes to its page.
        miss = press(pg, "#tab-cleaners"); pg.wait_for_timeout(900)
        ck("pressing Cleans opens the Cleans board",
           not miss and pg.url.split("/")[-1].startswith("cleaners.html"), miss or pg.url)
    ctx.close()

    ctx, pg = open_as(b, EMAIL["housekeeping"], "cleaners.html")
    bar = pg.evaluate(BAR)
    ck("housekeeping on Cleans: Cleans and Calendar, Cleans marked",
       bool(bar) and [(t["label"], bool(t["cur"])) for t in bar["tabs"]] == [("Cleans", True), ("Calendar", False)],
       bar and [(t["label"], t["cur"]) for t in bar["tabs"]])
    ctx.close()

    ctx, pg = open_as(b, EMAIL["housekeeping"], "cleaners.html", perms=PREVIEW_OPEN)
    bar = pg.evaluate(BAR)
    ck("and Tasks joins them once the owner opens it",
       bool(bar) and [t["label"] for t in bar["tabs"]] == ["Cleans", "Tasks", "Calendar"],
       bar and [t["label"] for t in bar["tabs"]])
    ctx.close()

    ctx, pg = open_as(b, EMAIL["spa"], "spa.html")
    ck("the masseuse, with the Spa board alone, gets no bar and no room for one",
       pg.evaluate(BAR) is None and not pg.evaluate("()=>document.body.classList.contains('hastabs')"))
    ctx.close()

    ctx, pg = open_as(b, "nobody@x", "tally.html")
    ck("a login with no staff record gets no bar", pg.evaluate(BAR) is None)
    ctx.close()

    # ── 4. nothing sits under it ──────────────────────────────────────
    def foot_on_bar(page, sel, label):
        ctx, pg = open_as(b, EMAIL["admin"], page)
        m = pg.evaluate("""(sel)=>{const f=document.querySelector(sel), t=document.getElementById('tabBar');
            if(!f||!t) return null;
            return {foot:f.getBoundingClientRect().bottom, bar:t.getBoundingClientRect().top};}""", sel)
        ck("%s: %s stands on the bar, not under it" % (page, label),
           bool(m) and abs(m["foot"] - m["bar"]) <= 1, m)
        ctx.close()
    foot_on_bar("tally.html", ".foot", "the sticky footer")
    foot_on_bar("invitations.html", "body > .foot", "the fixed Send footer")
    foot_on_bar("publish.html", "#bar", "the Publish bar")

    def covered(pg):
        """What the finger lands on at the middle of the bar: the ids of the
        element hit and everything it sits in, innermost first."""
        return pg.evaluate("""()=>{const r=document.getElementById('tabBar').getBoundingClientRect();
            let e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); const ids=[];
            for(; e && e!==document.body; e=e.parentElement) if(e.id) ids.push(e.id);
            return ids;}""")

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    ck("the bar is what a finger meets at the foot of the board", "tabBar" in covered(pg), covered(pg))
    miss = press(pg, "#rooms .room >> nth=0"); pg.wait_for_timeout(600)
    ck("a villa's sheet covers it", not miss and "tabBar" not in covered(pg), miss or covered(pg))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    miss = press(pg, "#selToggle"); pg.wait_for_timeout(200)
    miss = miss or press(pg, "#rooms .room >> nth=6"); pg.wait_for_timeout(500)
    ck("select mode's bar rises over it", not miss and "selBar" in covered(pg), miss or covered(pg))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "tag.html")
    pg.evaluate("()=>document.getElementById('savebar').classList.add('show')"); pg.wait_for_timeout(500)
    ck("Dietary's save bar rises over it", "savebar" in covered(pg), covered(pg))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "dashboard.html")
    m = pg.evaluate("""()=>{window.scrollTo(0, document.documentElement.scrollHeight); return null;}""")
    pg.wait_for_timeout(200)
    m = pg.evaluate("""()=>({end:document.getElementById('board').getBoundingClientRect().bottom,
        bar:document.getElementById('tabBar').getBoundingClientRect().top,
        long:document.documentElement.scrollHeight>innerHeight+200})""")
    ck("the foot of a long page scrolls clear of it", m["long"] and m["end"] <= m["bar"] + 1, m)
    ctx.close()

    # ── 5. the counts ─────────────────────────────────────────────────
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    pg.wait_for_timeout(800)
    bar = pg.evaluate(BAR)
    menu = pg.evaluate("""()=>{const o={};document.querySelectorAll('#navDrop a').forEach(a=>{
        const n=a.querySelector('.navbadge'); if(n) o[a.getAttribute('href')]=n.textContent;});return o;}""")
    pairs = [(t["href"], t["badge"], menu.get(t["href"], "")) for t in (bar or {}).get("tabs", [])
             if not t["cur"]]
    ck("Chat and Tasks wear the menu's counts on their icons, and no icon a count the menu lacks",
       bool(menu.get("guest-contact.html")) and bool(menu.get("tasks.html")) and
       pairs and all(on_icon == in_menu for _h, on_icon, in_menu in pairs), (pairs, menu))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "guest-contact.html")
    pg.wait_for_timeout(800)
    bar = pg.evaluate(BAR)
    ck("on Chat, its own icon asks for no count, and Tasks still wears one",
       bool(bar) and [t["badge"] for t in bar["tabs"] if t["id"] == "tab-guest-contact"] == [""]
       and [t["badge"] for t in bar["tabs"] if t["id"] == "tab-tasks"][0] != "",
       bar and [(t["id"], t["badge"]) for t in bar["tabs"]])
    ctx.close()

    # ── 6. it fits ────────────────────────────────────────────────────
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    whole = pg.evaluate("""()=>[...document.querySelectorAll('#tabBar .tablbl')]
        .filter(l=>l.scrollWidth>l.clientWidth+0.5).map(l=>l.textContent)""")
    ck("at 390 every label reads whole", whole == [], whole)
    ctx.close()
    for w in (360, 320):
        ctx, pg = open_as(b, EMAIL["admin"], "tally.html", w=w)
        m = pg.evaluate("""()=>{const t=[...document.querySelectorAll('#tabBar .tabrow > a')];
            return {side:document.documentElement.scrollWidth-document.documentElement.clientWidth,
                    inside:t.every(a=>{const r=a.getBoundingClientRect();return r.left>=-0.5&&r.right<=innerWidth+0.5;}),
                    n:t.length};}""")
        ck("at %d all five icons sit on the screen, and nothing scrolls sideways" % w,
           m["n"] == 5 and m["inside"] and m["side"] <= 1, m)
        ctx.close()
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html", h=560)
    m = pg.evaluate("""()=>({bar:getComputedStyle(document.getElementById('tabBar')).display,
        foot:Math.round(document.querySelector('.foot').getBoundingClientRect().bottom), vh:innerHeight})""")
    ck("under 600pt of height the bar steps aside, and the footer takes the foot again",
       m["bar"] == "none" and abs(m["foot"] - m["vh"]) <= 1, m)
    ctx.close()

    # ── 7. where it is drawn ──────────────────────────────────────────
    # Read off the pages themselves: a page with a menu wears the bar if it
    # wears the second dress, whose sheet holds the bar's own.
    WITH_MENU = sorted(f for f in glob.glob("*.html")
                       if not f.startswith(("demo-", "mock-"))
                       and 'id="navDrop"' in open(f, encoding="utf-8").read())
    for f in WITH_MENU:
        ui2 = re.search(r'<body[^>]*class="[^"]*\bui2\b', open(f, encoding="utf-8").read()) is not None
        ctx, pg = open_as(b, EMAIL["admin"], f)
        if pg.url.split("/")[-1].split("?")[0] != f:
            ck("%s opens for the admin" % f, False, pg.url); ctx.close(); continue
        bar = pg.evaluate(BAR)
        if ui2:
            ck("%s wears the bar" % f, bool(bar and bar["shown"] and len(bar["tabs"]) == 5),
               "no bar" if not bar else [t["label"] for t in bar["tabs"]])
        else:
            ck("%s, a printed sheet, keeps the menu alone" % f, bar is None)
        ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    pg.emulate_media(media="print"); pg.wait_for_timeout(200)
    ck("and it never reaches paper",
       pg.evaluate("()=>getComputedStyle(document.getElementById('tabBar')).display") == "none")
    ctx.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
