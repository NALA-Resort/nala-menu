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
     served, and no bar for a login with one page or no staff record. And
     drawn as the iPhone's own (iOS 26), the owner's ask the same day: a
     capsule 62pt tall floating 21pt above the foot and in from the sides,
     icons in a 28pt box, the page you are on in a grey capsule, and two
     or three tabs on a narrow bar. The icons are Lucide's line icons, the
     owner's choice the same day, whole, drawn thinner than Lucide's own
     and with no name under them, both his asks - the name kept out of
     sight for a screen reader.
  4. Nothing sits under it: the page's footer stands on it - sticky, fixed,
     and Publish's bar - with no row showing between them, a sheet and the
     select and save bars cover it, the foot of a long page scrolls clear
     of it, and beside the capsule a finger still reaches the page.
  5. The menu's counts ride on its icons, and not on the page you are on.
  6. It fits: no sideways scroll at 320, and held sideways it is the
     phone's compact bar, while the Cleans board keeps its villas on a
     screen.
  7. It is on every ui2 page with a menu, and on no printed sheet, on
     screen or on paper.
  8. Pull to refresh, which took the Refresh buttons' place the same day so
     the boards' footers could go: in the Home Screen app a long pull from
     the top reloads Reservations, Cleans and the Dashboard, and nothing
     else reloads - a short pull, a pull from the bar, under a sheet or
     from part-way down, a page that never asked, a browser tab.

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

def open_as(b, email, page, w=390, h=844, perms=None, app=False, touch=False):
    """A page on the fixture night, signed in as email, settled. app: as the
    Home Screen app, on a touch screen; touch: a touch screen in a tab."""
    if perms is None: TREE.pop("permissions", None)
    else: TREE["permissions"] = perms
    ctx = b.new_context(viewport={"width": w, "height": h}, timezone_id="Australia/Brisbane",
                        has_touch=app or touch)
    pg = ctx.new_page()
    if app:
        pg.add_init_script("Object.defineProperty(navigator,'standalone',{get:function(){return true;}});")
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
  const c=b.querySelector('.tabrow').getBoundingClientRect();
  return {shown:cs.display!=='none', top:r.top, bottom:r.bottom, h:r.height,
    cap:{top:c.top, bottom:c.bottom, left:c.left, right:c.right, h:c.height},
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

    # The iPhone's own bar, iOS 26: Apple's numbers (the HIG's tab bars and
    # SF Symbols pages, and the system bar as measured for FabBar), so the
    # staff meet the bar their phone already draws. On a 390 x 844 phone.
    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    bar = pg.evaluate(BAR)
    c = bar and bar["cap"]
    ck("it floats as the phone's does: a capsule 62pt tall, 21pt above the foot of the screen",
       bool(c) and c["h"] == 62 and c["bottom"] == 844 - 21, c)
    ck("and 21pt in from either side", bool(c) and c["left"] == 21 and c["right"] == 390 - 21, c)
    ck("the page keeps the 83pt the phone's bar keeps: 62 of bar and 21 under it",
       pg.evaluate("()=>getComputedStyle(document.body).getPropertyValue('--tabroom').trim()") == "83px"
       and bar["h"] == 83 and bar["top"] == c["top"], bar)
    look = pg.evaluate("""()=>{const a=[...document.querySelectorAll('#tabBar .tabrow > a')];
      const px=v=>parseFloat(v);
      return a.map(t=>{const s=t.querySelector('svg'), i=t.querySelector('.tabic').getBoundingClientRect(),
          l=t.querySelector('.tablbl'), lr=l.getBoundingClientRect(), cs=getComputedStyle(l),
          parts=[...s.children].map(e=>{const c=getComputedStyle(e);
            return {dot:e.getAttribute('fill')==='currentColor', fill:c.fill, stroke:c.stroke,
                    w:px(c.strokeWidth)};}),
          k=s.getBoundingClientRect(), g=s.getBBox(), m=s.getScreenCTM(), v=s.viewBox.baseVal,
          sw=px(getComputedStyle(s).strokeWidth);
        /* the drawing and half its line either side, inside the grid it is
           drawn on: nothing cut off at the box's edge */
        const whole=g.x-1>=v.x-0.01 && g.y-1>=v.y-0.01 &&
                    g.x+g.width+1<=v.x+v.width+0.01 && g.y+g.height+1<=v.y+v.height+0.01;
        return {id:t.id, box:[Math.round(k.width), Math.round(k.height)], whole,
          grid:[v.x, v.y, v.width, v.height],
          glyph:[+((g.width+sw)*m.a).toFixed(1), +((g.height+sw)*m.d).toFixed(1)], parts,
          name:l.textContent, shown:[Math.round(lr.width), Math.round(lr.height)],
          pill:{bg:getComputedStyle(t).backgroundColor, h:Math.round(t.getBoundingClientRect().height),
                r:px(getComputedStyle(t).borderTopLeftRadius)}};});}""")
    ck("its icons stand in a 28pt box, the phone's", all(t["box"] == [28, 28] for t in look),
       [(t["id"], t["box"]) for t in look])
    ck("Lucide's line icons, the owner's choice: every part a line, nothing filled but Lucide's own dots",
       all(p["stroke"] != "none" and (p["fill"] == "none" or p["dot"]) for t in look for p in t["parts"]),
       [(t["id"], [(p["fill"], p["stroke"]) for p in t["parts"]]) for t in look])
    ck("drawn thinner than Lucide's own 2, at 1.5 on its 24 grid (the owner's ask), the grid filling the box",
       all(p["w"] == 1.5 for t in look for p in t["parts"]) and all(t["grid"] == [0, 0, 24, 24] for t in look),
       [(t["id"], t["grid"], sorted({p["w"] for p in t["parts"]})) for t in look])
    ck("every icon whole: nothing cut off at the edge of its box",
       all(t["whole"] for t in look), [t["id"] for t in look if not t["whole"]])
    dash = [t for t in look if t["id"] == "tab-dashboard"]
    ck("the Dashboard's checklist stands 23pt wide: Apple's size for a square glyph on a tab",
       dash and 22.5 <= dash[0]["glyph"][0] <= 24, dash and dash[0]["glyph"])
    ck("no name under the icons (the owner's ask), each kept out of sight for a screen reader",
       all(t["shown"][0] <= 1 and t["shown"][1] <= 1 for t in look) and
       [t["name"] for t in look] == [LABEL[h] for h in TABS["roles"]["admin"]],
       [(t["id"], t["name"], t["shown"]) for t in look])
    cur = [t for t in look if t["id"] == "tab-tally"]
    ck("the page you are on sits in a grey capsule as tall as the bar, the selection grey",
       cur and cur[0]["pill"]["bg"] == "rgba(28, 28, 26, 0.1)" and cur[0]["pill"]["h"] == 58
       and cur[0]["pill"]["r"] >= 29, cur and cur[0]["pill"])
    ck("and no other page does", all(t["pill"]["bg"] == "rgba(0, 0, 0, 0)" for t in look if t["id"] != "tab-tally"),
       [(t["id"], t["pill"]["bg"]) for t in look])
    ctx.close()

    ctx, pg = open_as(b, EMAIL["housekeeping"], "cleaners.html")
    bar = pg.evaluate(BAR)
    ck("housekeeping on Cleans: Cleans and Calendar, Cleans marked",
       bool(bar) and [(t["label"], bool(t["cur"])) for t in bar["tabs"]] == [("Cleans", True), ("Calendar", False)],
       bar and [(t["label"], t["cur"]) for t in bar["tabs"]])
    # Two tabs keep the phone's narrow bar rather than two long pills.
    w = pg.evaluate("()=>[...document.querySelectorAll('#tabBar .tabrow > a')].map(a=>a.getBoundingClientRect().width)")
    c = bar and bar["cap"]
    ck("and two tabs keep a narrow bar, 98pt a tab, centred",
       w == [98, 98] and bool(c) and abs(c["left"] - (390 - c["right"])) <= 1, (w, c))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["housekeeping"], "cleaners.html", perms=PREVIEW_OPEN)
    bar = pg.evaluate(BAR)
    ck("and Tasks joins them once the owner opens it",
       bool(bar) and [t["label"] for t in bar["tabs"]] == ["Cleans", "Tasks", "Calendar"],
       bar and [t["label"] for t in bar["tabs"]])
    w = pg.evaluate("()=>[...document.querySelectorAll('#tabBar .tabrow > a')].map(a=>a.getBoundingClientRect().width)")
    c = bar and bar["cap"]
    ck("three still keep the narrow bar, centred: the phone fills the width from four",
       w == [98, 98, 98] and bool(c) and abs(c["left"] - (390 - c["right"])) <= 1, (w, c))
    ctx.close()

    ctx, pg = open_as(b, EMAIL["spa"], "spa.html")
    ck("the masseuse, with the Spa board alone, gets no bar and no room for one",
       pg.evaluate(BAR) is None and not pg.evaluate("()=>document.body.classList.contains('hastabs')"))
    ctx.close()

    ctx, pg = open_as(b, "nobody@x", "tally.html")
    ck("a login with no staff record gets no bar", pg.evaluate(BAR) is None)
    ctx.close()

    # ── 4. nothing sits under it ──────────────────────────────────────
    STRIP = """()=>{const t=document.getElementById('tabBar'), c=getComputedStyle(t);
        return {image:c.backgroundImage.slice(0, 15), colour:c.backgroundColor,
                ground:getComputedStyle(document.body).backgroundColor};}"""
    def foot_on_bar(page, sel, label):
        ctx, pg = open_as(b, EMAIL["admin"], page)
        m = pg.evaluate("""(sel)=>{const f=document.querySelector(sel), t=document.querySelector('#tabBar .tabrow');
            if(!f||!t) return null;
            return {foot:f.getBoundingClientRect().bottom, bar:t.getBoundingClientRect().top};}""", sel)
        ck("%s: %s stands on the bar, not under it" % (page, label),
           bool(m) and abs(m["foot"] - m["bar"]) <= 1, m)
        # and the strip the bar floats in is the ground, so no row shows
        # between the footer and the capsule
        g = pg.evaluate(STRIP)
        ck("%s: with no row showing between them" % page,
           g["image"] == "none" and g["colour"] == g["ground"], g)
        ctx.close()
    foot_on_bar("arrivals-sms.html", ".foot", "the sticky Send footer")
    foot_on_bar("invitations.html", "body > .foot", "the fixed Send footer")
    foot_on_bar("publish.html", "#bar", "the Publish bar")
    # The footer's corner law, held here since Reservations' footer went:
    # square but for the two outer lower corners. One button is both.
    ctx, pg = open_as(b, EMAIL["admin"], "arrivals-sms.html")
    rad = pg.evaluate("""()=>[...document.querySelectorAll('.foot .btn')].map(b=>{const c=getComputedStyle(b);
        return [c.borderTopLeftRadius,c.borderTopRightRadius,c.borderBottomRightRadius,
                c.borderBottomLeftRadius].join('|');})""")
    ck("and its button keeps the footer's corners: square above, rounded at the outer foot",
       rad == ["0px|0px|8px|8px"], rad)
    ctx.close()

    def covered(pg):
        """What the finger lands on at the middle of the bar: the ids of the
        element hit and everything it sits in, innermost first."""
        return pg.evaluate("""()=>{const r=document.getElementById('tabBar').getBoundingClientRect();
            let e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); const ids=[];
            for(; e && e!==document.body; e=e.parentElement) if(e.id) ids.push(e.id);
            return ids;}""")

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html")
    ck("the bar is what a finger meets at the foot of the board", "tabBar" in covered(pg), covered(pg))
    # Where there is no footer, what scrolls under the capsule fades into the
    # ground, as the phone's content does under its bars; and the strip
    # beside the capsule is the page's, to a finger.
    g = pg.evaluate(STRIP)
    ck("on a page with no footer, what scrolls under it fades into the ground",
       g["image"].startswith("linear-gradient"), g)
    beside = pg.evaluate("""()=>{const c=document.querySelector('#tabBar .tabrow').getBoundingClientRect();
        const e=document.elementFromPoint(c.left/2, c.top+c.height/2);
        return !!e && !e.closest('#tabBar');}""")
    ck("and beside the capsule a finger reaches the page, not the bar", beside)
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
    g = pg.evaluate(STRIP)
    ck("Chat's list, whose Send lives in a conversation, keeps the fade",
       g["image"].startswith("linear-gradient"), g)
    bar = pg.evaluate(BAR)
    ck("on Chat, its own icon asks for no count, and Tasks still wears one",
       bool(bar) and [t["badge"] for t in bar["tabs"] if t["id"] == "tab-guest-contact"] == [""]
       and [t["badge"] for t in bar["tabs"] if t["id"] == "tab-tasks"][0] != "",
       bar and [(t["id"], t["badge"]) for t in bar["tabs"]])
    ctx.close()

    # ── 6. it fits ────────────────────────────────────────────────────
    for w in (360, 320):
        ctx, pg = open_as(b, EMAIL["admin"], "tally.html", w=w)
        m = pg.evaluate("""()=>{const t=[...document.querySelectorAll('#tabBar .tabrow > a')];
            return {side:document.documentElement.scrollWidth-document.documentElement.clientWidth,
                    inside:t.every(a=>{const r=a.getBoundingClientRect();return r.left>=-0.5&&r.right<=innerWidth+0.5;}),
                    n:t.length};}""")
        ck("at %d all five icons sit on the screen, and nothing scrolls sideways" % w,
           m["n"] == 5 and m["inside"] and m["side"] <= 1, m)
        ctx.close()
    # Held sideways it stays. It stepped aside under 600pt until the Cleans
    # footer went the same day, which gave the board back more than the bar
    # takes: seventeen villas still fit the smallest phone on its side.
    ctx, pg = open_as(b, EMAIL["admin"], "cleaners.html", w=667, h=320)
    m = pg.evaluate("""()=>{const g=document.getElementById('grid'), t=document.getElementById('tabBar');
        return {bar:!!t&&getComputedStyle(t).display!=='none',
                page:document.documentElement.scrollHeight-innerHeight,
                grid:g.scrollHeight-g.clientHeight,
                clear:g.getBoundingClientRect().bottom<=(t?t.getBoundingClientRect().top:innerHeight)+1};}""")
    ck("a phone on its side keeps the bar, and the Cleans board every villa on one screen",
       m["bar"] and m["page"] <= 1 and m["grid"] <= 1 and m["clear"], m)
    # the phone's compact bar: shorter, nearer the foot, smaller icons
    m = pg.evaluate("""()=>{const c=document.querySelector('#tabBar .tabrow').getBoundingClientRect();
        return {h:c.height, under:innerHeight-c.bottom,
                icons:[...new Set([...document.querySelectorAll('#tabBar .tabic')].map(i=>
                  Math.round(i.getBoundingClientRect().width)))]};}""")
    ck("held sideways it is the phone's compact bar: 44pt, 8pt off the foot, 22pt icons",
       m["h"] == 44 and m["under"] == 8 and m["icons"] == [22], m)
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

    # ── 8. pull to refresh ────────────────────────────────────────────
    # A finger down the screen from (x, y), dy in all, then lifted: the
    # touches a phone sends, dispatched where the finger lands.
    PULL = """([x, y0, dy])=>{const t=document.elementFromPoint(x, y0);
      const at=y=>new Touch({identifier:1, target:t, clientX:x, clientY:y, pageX:x, pageY:y+scrollY});
      const send=(type, y, list)=>t.dispatchEvent(new TouchEvent(type, {bubbles:true, cancelable:true,
        touches:list, targetTouches:list, changedTouches:[at(y)]}));
      send('touchstart', y0, [at(y0)]);
      for (let i=1; i<=10; i++) send('touchmove', y0+dy*i/10, [at(y0+dy*i/10)]);
      const m=document.getElementById('ptrMark'), armed=!!m && m.classList.contains('ready');
      send('touchend', y0+dy, []);
      return {armed, on:(t.id||t.tagName)};}"""

    def pulled(pg, dy=200, x=195, y0=180):
        """Pull, and say whether the page reloaded and whether the mark armed."""
        pg.evaluate("()=>{window.__stay=1;}")
        g = pg.evaluate(PULL, [x, y0, dy])
        pg.wait_for_timeout(1500)
        try:
            pg.wait_for_load_state("load", timeout=5000)
            g["reloaded"] = pg.evaluate("()=>window.__stay!==1")
        except Exception as e:
            g["reloaded"] = "unsure: " + str(e).split("\n")[0][:60]
        return g

    for page, name in (("tally.html", "Reservations"), ("cleaners.html", "Cleans"),
                       ("dashboard.html", "the Dashboard")):
        ctx, pg = open_as(b, EMAIL["admin"], page, app=True)
        gone = pg.evaluate("""()=>[...document.querySelectorAll('button,a')]
            .filter(b=>/^refresh$/i.test(b.textContent.trim())).length""")
        ck("%s keeps no Refresh button" % name, gone == 0, gone)
        g = pulled(pg)
        ck("in the Home Screen app, a long pull from the top reloads %s" % name,
           g["armed"] and g["reloaded"] is True, g)
        ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html", app=True)
    g = pulled(pg, dy=80)
    ck("a short pull only shows the mark, and reloads nothing", not g["armed"] and g["reloaded"] is False, g)
    mid = pg.evaluate("()=>{const r=document.querySelector('#tabBar .tabrow').getBoundingClientRect();return r.top+r.height/2;}")
    g = pulled(pg, y0=mid)
    ck("nor does a pull that starts on the tab bar", g["reloaded"] is False, g)
    pg.evaluate("()=>window.scrollTo(0, 400)"); pg.wait_for_timeout(200)
    g = pulled(pg)
    ck("nor a pull from part-way down the page", g["reloaded"] is False, g)
    pg.evaluate("()=>window.scrollTo(0, 0)"); pg.wait_for_timeout(200)
    miss = press(pg, "#rooms .room >> nth=0"); pg.wait_for_timeout(600)
    g = pulled(pg)
    ck("nor one under an open sheet", not miss and g["reloaded"] is False, miss or g)
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "front-desk.html", app=True)
    g = pulled(pg)
    ck("a page that never asked for it does not reload", not g["armed"] and g["reloaded"] is False, g)
    ctx.close()

    ctx, pg = open_as(b, EMAIL["admin"], "tally.html", touch=True)
    g = pulled(pg)
    ck("in a browser tab the pull is the browser's own: none of ours",
       not g["armed"] and g["reloaded"] is False, g)
    ctx.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
