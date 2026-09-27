"""past-menus.html, the Past Menus page.

Written 27 Sep, after the owner's screenshot of Sunday's menu: one described
main under three bare dish names. The archive row at /menuhistory/<date>
kept mainDesc alone, so nothing else could be shown. announceMenu
(nala-shared.js) now archives every course's description as <course>Desc,
and this page sets each under its own course. Nights archived before then
carry mainDesc only and show just that one: an empty slot pretending there
was a description would be a lie about what the guest read.

The archive write itself is asserted in tally_suite, where announceMenu's
other half - telling the manager once - already lives.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8978), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},
signOut:function(){}};"""
STAFF = {"staff@x": {"name": "Admin", "role": "admin"}}
ROW = {"v": None}

def fb(route, request):
    u = request.url
    body = "null"
    if "/menuhistory/" in u: body = json.dumps(ROW["v"])
    elif "/staff" in u:      body = json.dumps(STAFF)
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def courses(pg):
    return pg.evaluate(
        "()=>[...document.querySelectorAll('#board .course')].map(e=>({"
        "label:e.querySelector('.clabel').textContent,"
        "name:e.querySelector('.cname').textContent,"
        "desc:e.querySelector('.cdesc') ? e.querySelector('.cdesc').textContent : null}))")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_night(row):
        ROW["v"] = row
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.add_init_script(SDK)
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8978/past-menus.html")
        pg.wait_for_timeout(1100)
        return pg

    # ── a night archived since 27 Sep: every course described ──
    pg = open_night({
        "bread": "Warm sourdough", "breadDesc": "cultured butter",
        "entree": "Cured salmon", "entreeDesc": "beetroot, horseradish",
        "main": "Barramundi", "mainDesc": "asparagus, macadamia",
        "dessert": "Chocolate mousse", "dessertDesc": "hazelnut praline",
        "published": now.isoformat()})
    c = {x["label"]: x for x in courses(pg)}
    ck("the four courses are set", len(c) == 4)
    ck("each course carries the description the guest read",
       c.get("Bread", {}).get("desc") == "cultured butter"
       and c.get("Entrée", {}).get("desc") == "beetroot, horseradish"
       and c.get("Main", {}).get("desc") == "asparagus, macadamia"
       and c.get("Dessert", {}).get("desc") == "hazelnut praline")
    ck("under its own dish, not beside another",
       c.get("Entrée", {}).get("name") == "Cured salmon"
       and c.get("Dessert", {}).get("name") == "Chocolate mousse")
    ck("no sideways scroll at 390", not pg.evaluate(
        "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
    pg.close()

    # ── a night archived before: the main's description alone ──
    pg = open_night({"bread": "Sourdough", "entree": "Crudo", "main": "Lamb rump",
                     "dessert": "Pavlova", "mainDesc": "pomegranate, mint",
                     "published": now.isoformat()})
    c = {x["label"]: x for x in courses(pg)}
    ck("an older night still shows the main's description",
       c.get("Main", {}).get("desc") == "pomegranate, mint")
    ck("and no empty slot for the three it never kept",
       [x["label"] for x in courses(pg) if x["desc"] is not None] == ["Main"])
    pg.close()

    # ── a course the chef left undescribed ────────────────────
    pg = open_night({"bread": "Sourdough", "breadDesc": "",
                     "entree": "Crudo", "entreeDesc": "  ",
                     "main": "Lamb rump", "mainDesc": "",
                     "dessert": "Pavlova", "dessertDesc": "lemon curd",
                     "published": now.isoformat()})
    ck("a blank description draws no slot",
       [x["label"] for x in courses(pg) if x["desc"] is not None] == ["Dessert"])
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
