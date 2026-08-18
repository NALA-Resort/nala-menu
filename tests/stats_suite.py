"""stats.html, the Statistics page.

Written after finding that the page reads only /responses, which nothing has
written since the one dinner cell replaced it on 17 Aug. Every night served
since then is invisible here, and the page says "No data recorded yet" rather
than saying anything is wrong. This suite describes where the numbers should
come from now:

  /dinner/<date>/<villa>   the live answer, one per villa per night
  /responses/<date>/<key>  the retired node, still read so the older nights in
                           the look-back window do not vanish from the history
  /menuhistory/<date>      what was on the menu that night, written by tally

The rules that matter beyond the arithmetic:

  a villa is counted once, and the cell wins when both nodes hold it
  a staff vacant mark is not a guest declining dinner, so it is not counted
  a read that fails says so, rather than reporting an empty history

That last one is the Clean Slate lesson in a second place: a page that cannot
read its data must never render as a page whose data is empty.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8972), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
def dkey(n):
    return (now - datetime.timedelta(days=n)).strftime("%Y-%m-%d")
def weekday(n):
    return (now - datetime.timedelta(days=n)).strftime("%A")

def sdk(email="staff@x"):
    return """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'%s',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'%s'});},25);},
signOut:function(){}};""" % (email, email)
SDK = sdk()

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STATE = {"dinner": {}, "responses": {}, "menuhistory": {}, "fail": None}

def fb(route, request):
    u = request.url
    for node in ("dinner", "responses", "menuhistory"):
        if "/" + node in u:
            if STATE["fail"] == node:
                route.fulfill(status=401, content_type="application/json",
                              body='{"error":"Permission denied"}')
                return
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(STATE[node]))
            return
    if "/staff" in u:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STAFF)); return
    route.fulfill(status=200, content_type="application/json", body="null")

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def cell(status="in", pax=2, by="guest", diets=None, **kw):
    r = {"status": status, "pax": pax, "by": by,
         "at": now.isoformat(), "source": "manual"}
    if diets: r["diets"] = diets
    r.update(kw)
    return r

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_stats(w=390, email="staff@x"):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(sdk(email))
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.route("**/gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8972/stats.html")
        pg.wait_for_timeout(1100)
        return pg

    def rows(pg, section):
        return pg.evaluate(
            "id=>[...document.querySelectorAll('#'+id+' .stat')].map(e=>({"
            "name:(e.querySelector('.stat-name')||{}).textContent||'',"
            "sub:(e.querySelector('.stat-sub')||{}).textContent||'',"
            "val:(e.querySelector('.stat-val')||{}).textContent||'',"
            "bar:(e.querySelector('.bar i')||{style:{}}).style.width}))", section)

    # ── the live node is the point of the whole exercise ──────
    # Two nights, both recorded the way the app records them today: one cell
    # per villa, keyed by villa, under /dinner.
    STATE["dinner"] = {
        dkey(1): {"1": cell(pax=2), "2": cell(pax=4), "3": cell("out", 0)},
        dkey(2): {"1": cell(pax=2), "5": cell(pax=2)},
    }
    STATE["menuhistory"] = {
        dkey(1): {"main": "Eye fillet of beef", "published": now.isoformat()},
        dkey(2): {"main": "Barramundi, charred leek", "published": now.isoformat()},
    }
    pg = open_stats()

    ck("nights recorded in the dinner cell are counted at all",
       "2 nights" in pg.inner_text("#range"))
    # 6 covers on one night, 4 on the other, so 5 a night.
    ck("the headline is the average covers a night",
       pg.inner_text("#hCovers").strip() == "5")

    g = rows(pg, "byProtein")
    names = [r["name"] for r in g]
    ck("the main course is grouped by protein", "Beef" in names and "Fish" in names)
    beef = [r for r in g if r["name"] == "Beef"][0]
    # Two in and one out on the beef night.
    ck("take-up is the share of replies that said yes", beef["val"].strip() == "67%")
    ck("and the bar matches the number", beef["bar"].startswith("67"))
    ck("the covers average is per night, not per dining villa",
       "6.0 covers" in beef["sub"])

    d = rows(pg, "byDay")
    ck("nights are grouped by weekday",
       set([r["name"] for r in d]) == set([weekday(1), weekday(2)]))
    ck("the busiest weekday sorts first", d[0]["name"] == weekday(1))
    pg.close()

    # ── the retired node is still read, for the older nights ──
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2)}}
    STATE["responses"] = {dkey(40): {"+61400000001": {"room": "6", "status": "in",
                                                      "pax": 3, "at": now.isoformat()}}}
    STATE["menuhistory"] = {dkey(40): {"main": "Lamb rump"}}
    pg = open_stats()
    ck("a night held only in the retired node is still counted",
       "2 nights" in pg.inner_text("#range"))
    ck("and its menu is grouped like any other",
       "Lamb" in [r["name"] for r in rows(pg, "byProtein")])
    pg.close()

    # ── one villa, one answer ─────────────────────────────────
    # The same villa on the same night in both nodes is one guest, not two.
    # A double count here would inflate every cover number on the page.
    STATE["responses"] = {dkey(1): {"+61400000001": {"room": "1", "status": "in",
                                                     "pax": 2, "at": now.isoformat()}}}
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2)}}
    STATE["menuhistory"] = {}
    pg = open_stats()
    ck("a villa in both nodes is counted once", pg.inner_text("#hCovers").strip() == "2")
    pg.close()

    # And when the two disagree, the cell is the answer, because that is the
    # rule everywhere else in the app.
    STATE["responses"] = {dkey(1): {"+61400000001": {"room": "1", "status": "in",
                                                     "pax": 6, "at": now.isoformat()}}}
    STATE["dinner"] = {dkey(1): {"1": cell("out", 0)}}
    pg = open_stats()
    ck("where they disagree the dinner cell wins",
       pg.inner_text("#hCovers").strip() == "0")
    pg.close()

    # ── a vacant villa is not a guest saying no ───────────────
    # Reception marks empty villas vacant every day. Counting those as declines
    # would drag the take-up rate towards zero and make every menu look bad.
    STATE["responses"] = {}
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2), "2": cell("vacant", 0, by="staff"),
                                 "3": cell("vacant", 0, by="staff")}}
    STATE["menuhistory"] = {dkey(1): {"main": "Pork belly"}}
    pg = open_stats()
    pork = [r for r in rows(pg, "byProtein") if r["name"] == "Pork"]
    ck("vacant villas are not counted as declines",
       bool(pork) and pork[0]["val"].strip() == "100%")
    ck("and are not counted as covers", pg.inner_text("#hCovers").strip() == "2")
    pg.close()

    # A night that is nothing but vacant marks is not a night of service.
    STATE["dinner"] = {dkey(1): {"1": cell("vacant", 0, by="staff")},
                       dkey(2): {"1": cell(pax=2)}}
    STATE["menuhistory"] = {}
    pg = open_stats()
    ck("a night with nothing but vacant marks is not a recorded night",
       "1 night" in pg.inner_text("#range"))
    pg.close()

    # ── dietaries ─────────────────────────────────────────────
    STATE["dinner"] = {dkey(1): {"1": cell(diets=["Gluten free", "Nut allergy"]),
                                 "2": cell(diets=["Gluten free"]),
                                 "3": cell("out", 0, diets=["Vegan"])}}
    pg = open_stats()
    dt = rows(pg, "byDiet")
    ck("dietaries are tallied", [r["name"] for r in dt][:1] == ["Gluten free"])
    ck("and counted, not merely listed",
       [r["val"].strip() for r in dt if r["name"] == "Gluten free"] == ["2"])
    ck("a dietary on a guest who is not dining is still recorded",
       "Vegan" in [r["name"] for r in dt])
    pg.close()

    # ── the dish name decides the group, and the animal wins ──
    # Every one of these was mis-grouped before: the cut names live in the beef
    # list, and the beef list was consulted first, so a lamb rump was beef.
    DISHES = [("Lamb rump, smoked eggplant", "Lamb"),
              ("Pork belly, apple", "Pork"),
              ("Beef cheek, red wine", "Beef"),
              ("Eye fillet, cafe de paris", "Beef"),
              ("Tuna steak, sesame", "Fish"),
              ("Duck breast, cherry", "Duck"),
              ("Market fish, brown butter", "Fish"),
              ("Chawanmushi, seasonal vegetables", "Vegetarian"),
              ("Something the chef invented", "Other")]
    STATE["responses"] = {}
    STATE["dinner"] = {}
    STATE["menuhistory"] = {}
    for i, (dish, group) in enumerate(DISHES):
        STATE["dinner"][dkey(i + 1)] = {"1": cell(pax=2)}
        STATE["menuhistory"][dkey(i + 1)] = {"main": dish}
    pg = open_stats()
    got = dict((r["name"], True) for r in rows(pg, "byProtein"))
    for dish, group in DISHES:
        ck("%s is grouped as %s" % (dish.split(",")[0], group), group in got)
    pg.close()

    # ── the empty states, which have to say different things ──
    STATE["dinner"] = {}; STATE["responses"] = {}; STATE["menuhistory"] = {}
    pg = open_stats()
    ck("with genuinely nothing recorded it says so",
       "No data" in pg.inner_text("#range"))
    ck("and explains that statistics build up over time",
       "build up" in pg.inner_text("#byProtein"))
    pg.close()

    # The failure that matters: the read was refused. Saying "no data" here
    # would be the page reporting a broken permission as a quiet month.
    STATE["fail"] = "dinner"
    pg = open_stats()
    txt = pg.inner_text("body")
    ck("a refused read is reported as a problem, not as no data",
       "No data recorded yet" not in txt)
    ck("and says the numbers could not be read",
       "could not" in txt.lower() or "not be read" in txt.lower())
    pg.close()
    STATE["fail"] = None

    # ── the look-back window ──────────────────────────────────
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2)},
                       dkey(400): {"1": cell(pax=99)}}
    pg = open_stats()
    ck("nights older than the look-back window are ignored",
       "1 night" in pg.inner_text("#range")
       and pg.inner_text("#hCovers").strip() == "2")
    pg.close()

    # ── who may read the numbers ──────────────────────────────
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2)}}
    q = open_stats(email="housekeeping@x")
    q.wait_for_timeout(700)
    ck("housekeeping is sent to their own board rather than the numbers",
       not q.url.endswith("stats.html"))
    q.close()

    # ── phone geometry and the way back ───────────────────────
    STATE["dinner"] = {dkey(1): {"1": cell(pax=2, diets=["Gluten free"])}}
    STATE["menuhistory"] = {dkey(1): {"main": "Mushroom risotto"}}
    for w in (390, 360, 320):
        q = open_stats(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        if w == 390:
            ck("every bar stays inside its track", q.evaluate(
                "()=>[...document.querySelectorAll('.bar i')].every(e=>"
                "e.getBoundingClientRect().width<=e.parentElement.getBoundingClientRect().width+1)"))
            ck("the way back to Reservations is there",
               q.get_attribute(".btn", "href") == "tally.html")
            ck("a vegetarian main is grouped as vegetarian",
               "Vegetarian" in [r["name"] for r in rows(q, "byProtein")])
        q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
