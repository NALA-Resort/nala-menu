"""publish.html, Publish Menu.

The chef photographs a handwritten sheet. He is not going to type it again, so
the menu chat reads the photo and hands him a link with the four courses
already in it. This page is where that reading gets checked by the person who
wrote the menu, and then published.

Three things make it worth pinning.

The menu travels in the address and nothing is written by arriving. A misread
word costs nothing until Publish is pressed. That is the whole reason it is a
link and not a write, and it is the difference between catching an OCR mistake
and serving one.

Publishing and tagging happen together. An untagged menu checks nothing: the
guest page and the front desk both compare a guest's declared allergies against
tonight's tags, so an untagged nut dish meets a nut allergy in silence. Tagging
was a separate page and a separate trip, and a separate trip gets skipped on a
busy night. The tags failing while the menu succeeds is the one failure that
looks like success from the outside, so it is reported loudly.

A read that fails is not an empty node. Treating the two the same would seed
the eight default dietaries over the chef's real list and then publish them.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, json, time, datetime, os, urllib.parse

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
httpd = http.server.ThreadingHTTPServer(("", 8975), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

def sdk(email="chef@x"):
    return """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'%s',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'%s'});},25);},
signOut:function(){}};""" % (email, email)

MASTER = {"Gluten free": {"name": "Gluten free", "active": True, "group": "common"},
          "Nut allergy": {"name": "Nut allergy", "active": True, "group": "common"},
          "Chilli":      {"name": "Chilli", "active": True, "group": "menu"},
          "Old thing":   {"name": "Old thing", "active": False, "group": "common"}}

STAFF = {"chef@x": {"name": "Chef", "role": "chef"},
         "staff@x": {"name": "Admin", "role": "admin"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STATE = {"master": MASTER, "tags": {}, "failMaster": False, "failTags": False,
         "failMenuSave": False, "failTagSave": False}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if "/menu.json" in u and STATE["failMenuSave"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        if "/menutags" in u and STATE["failTagSave"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    if "/dietaries" in u:
        if STATE["failMaster"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"Permission denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STATE["master"])); return
    if "/staff" in u:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STAFF)); return
    if "/menutags" in u:
        if STATE["failTags"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"Permission denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STATE["tags"])); return
    route.fulfill(status=200, content_type="application/json", body="null")

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def wrote(fragment):
    return [w for w in WRITES if fragment in w["u"]]

def published():
    """Writes this page is responsible for, which is the menu and tonight's
    tags. Not every write on the wire: nala-shared archives the day's menu to
    /menuhistory on load, once the published menu is dated today, and that is
    the shared script doing its job rather than anything this page did. An
    assertion counting all writes reads that as the page misbehaving, and did
    from the moment a menu was published for the current date."""
    return [w for w in WRITES
            if "/menu.json" in w["u"] or "/menutags/" in w["u"]]

LINK = ("?b=" + urllib.parse.quote("Tomato focaccia - whipped ricotta") +
        "&e=" + urllib.parse.quote("Hervey Bay scallops - burnt butter") +
        "&m=" + urllib.parse.quote("Sovereign lamb - salsa verde") +
        "&d=" + urllib.parse.quote("Mandarin cheesecake") +
        "&sf=e")

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_pub(query="", email="chef@x", w=390):
        del WRITES[:]
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(sdk(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8975/publish.html" + query)
        pg.wait_for_timeout(900)
        return pg

    def val(pg, i):
        return pg.evaluate("(i)=>document.getElementById(i).value", i)

    # ── the link fills the form ─────────────────────────────────
    pg = open_pub(LINK)
    ck("the dish names arrive from the link",
       val(pg, "n_bread") == "Tomato focaccia" and
       val(pg, "n_main") == "Sovereign lamb")
    #  Split on the FIRST dash only, so a description carrying one keeps its
    #  tail rather than losing everything after it.
    ck("a dish and its description are split apart",
       val(pg, "d_bread") == "whipped ricotta" and
       val(pg, "d_entree") == "burnt butter")
    ck("a dish with no dash is all name, which handwriting usually is",
       val(pg, "n_dessert") == "Mandarin cheesecake" and val(pg, "d_dessert") == "")
    ck("the seafood flag arrives set on the course named in the link",
       pg.evaluate("()=>s_entree.className.indexOf('on')>-1"))
    ck("and stays off on the courses not named",
       not pg.evaluate("()=>s_main.className.indexOf('on')>-1") and
       not pg.evaluate("()=>s_bread.className.indexOf('on')>-1"))

    #  The reason it is a link and not a write. Everything up to Publish is
    #  reversible, which is what makes an OCR mistake survivable.
    ck("arriving with a menu in the link publishes nothing at all",
       len(published()) == 0)

    # ── the reading can be corrected ────────────────────────────
    pg.fill("#n_main", "Sovereign lamb rump")
    pg.wait_for_timeout(200)
    ck("a misread dish can be fixed on the page",
       val(pg, "n_main") == "Sovereign lamb rump")
    ck("and the tagging list below follows the corrected name",
       "Sovereign lamb rump" in pg.inner_text("#tagblock"))
    pg.evaluate("()=>s_main.click()")
    ck("the seafood flag can be corrected too",
       pg.evaluate("()=>s_main.className.indexOf('on')>-1"))
    pg.evaluate("()=>s_main.click()")
    ck("and corrected back", not pg.evaluate("()=>s_main.className.indexOf('on')>-1"))
    ck("still nothing published", len(published()) == 0)
    pg.close()

    # ── tagging is on this page, not behind a link ──────────────
    pg = open_pub(LINK)
    ck("the dietaries come from the chef's list, not a list this page invented",
       "Gluten free" in pg.inner_text("#tagblock") and
       "Nut allergy" in pg.inner_text("#tagblock"))
    ck("a retired dietary is not offered",
       "Old thing" not in pg.inner_text("#tagblock"))
    ck("every course can be tagged, not just the main",
       pg.evaluate("()=>document.querySelectorAll('#tagblock .tagcourse').length") == 4)
    pg.close()

    # ── publishing ──────────────────────────────────────────────
    pg = open_pub(LINK)
    pg.evaluate("""()=>{ var t=[...document.querySelectorAll('#tagblock .tick')]
        .find(x=>x.getAttribute('data-c')==='main' &&
                 x.getAttribute('data-n')==='Nut allergy'); t.click(); }""")
    del WRITES[:]
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(900)

    mw = wrote("/menu.json")
    ck("Publish writes the menu", len(mw) == 1)
    if mw:
        body = json.loads(mw[0]["b"])
        ck("as a PUT, replacing last night's rather than merging into it",
           mw[0]["m"] == "PUT")
        ck("with the four courses and nothing else",
           set(body) == {"published", "bread", "entree", "main", "dessert"})
        ck("carrying the dish, the description and the flag",
           body["entree"]["name"] == "Hervey Bay scallops" and
           body["entree"]["desc"] == "burnt butter" and
           body["entree"]["aus"] is True)
        ck("and a publish time, which is what makes it tonight's",
           bool(body.get("published")))

    tw = wrote("/menutags/")
    ck("and writes tonight's tags in the same press", len(tw) == 1)
    if tw:
        ck("under tonight's date", today in tw[0]["u"])
        tagbody = json.loads(tw[0]["b"])
        #  The SHAPE, not just the presence of the word. This page shipped
        #  writing an object keyed by dietary name, while tag.html has always
        #  written an array of names and every reader walks it with forEach:
        #  an object throws there instead of flagging an allergy. The old
        #  assertion looked for the name anywhere in the body, which is true
        #  of both shapes, so it passed and caught nothing.
        ck("tonight's tags are arrays of names, as every reader expects",
           isinstance(tagbody.get("main"), list))
        ck("holding the name a guest declared, not a key derived from it",
           tagbody.get("main") == ["Nut allergy"])

    ck("the chef is told it is live",
       pg.evaluate("()=>done.className.indexOf('show')>-1"))
    ck("and the button is gone, so it cannot be pressed twice",
       pg.evaluate("()=>getComputedStyle(bar).display") == "none")
    pg.close()

    # ── a menu with a blank course ──────────────────────────────
    pg = open_pub("?b=Focaccia&m=Lamb")
    del WRITES[:]
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(500)
    ck("a half filled menu is refused", len(published()) == 0)
    ck("and names the courses still missing",
       "entr" in pg.inner_text("#err").lower() and
       "dessert" in pg.inner_text("#err").lower())
    pg.close()

    # ── the failure that looks like success ─────────────────────
    #  The menu is live and nothing is checking it. Silence here would leave
    #  the chef believing the allergy warnings were on.
    STATE["failTagSave"] = True
    pg = open_pub(LINK)
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(900)
    msg = pg.inner_text("#err").lower()
    ck("tags failing after the menu succeeds is said out loud",
       "live" in msg and "nothing is being checked" in msg)
    ck("and it is not reported as published",
       not pg.evaluate("()=>done.className.indexOf('show')>-1"))
    ck("the button comes back so it can be pressed again",
       not pg.evaluate("()=>pubBtn.disabled"))
    STATE["failTagSave"] = False
    pg.close()

    # ── a login without the permission ──────────────────────────
    STATE["failMenuSave"] = True
    pg = open_pub(LINK)
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(900)
    ck("a refused write says the role is wrong, not that the network is",
       "role to chef" in pg.inner_text("#err"))
    STATE["failMenuSave"] = False
    pg.close()

    # ── a failed read must not become an empty one ──────────────
    STATE["failMaster"] = True
    pg = open_pub(LINK)
    ck("a dietary list that would not load locks publishing",
       pg.evaluate("()=>pubBtn.disabled"))
    ck("and says why, in terms of what it is protecting",
       "overwritten" in pg.inner_text("#err"))
    del WRITES[:]
    #  Called directly rather than clicked, because a disabled button swallows
    #  the click and would prove nothing about the guard behind it.
    pg.evaluate("()=>pubBtn.onclick.call(pubBtn)"); pg.wait_for_timeout(500)
    ck("and the guard behind it publishes nothing even if pressed",
       len(published()) == 0)
    STATE["failMaster"] = False
    pg.close()

    #  Tags are different from the master list. Failing to read them means
    #  starting the ticks empty, which the chef can see and redo. Locking him
    #  out of publishing over it would be the worse trade.
    STATE["failTags"] = True
    pg = open_pub(LINK)
    ck("tonight's tags failing to load does not stop tonight's menu",
       not pg.evaluate("()=>pubBtn.disabled"))
    STATE["failTags"] = False
    pg.close()

    # ── republishing a corrected menu ───────────────────────────
    STATE["tags"] = {"main": ["Nut allergy"]}
    pg = open_pub(LINK)
    ck("ticks already made tonight come back, so a correction keeps them",
       pg.evaluate("""()=>[...document.querySelectorAll('#tagblock .tick')]
          .some(x=>x.getAttribute('data-c')==='main' &&
                   x.getAttribute('data-n')==='Nut allergy' &&
                   x.className.indexOf('on')>-1)"""))
    STATE["tags"] = {}
    pg.close()

    # ── no link at all ──────────────────────────────────────────
    pg = open_pub("")
    ck("the page still works with no link, typed by hand",
       pg.evaluate("()=>document.querySelectorAll('.c-name').length") == 4)
    ck("and says so rather than looking broken",
       "link" in pg.inner_text("#lede").lower())
    pg.close()

    # ── a role that may not publish ─────────────────────────────
    for who, role in (("waiter@x", "waiter"), ("housekeeping@x", "housekeeping")):
        pg = open_pub(LINK, email=who)
        pg.wait_for_timeout(600)
        gone = pg.evaluate("()=>!document.getElementById('wrap') || "
                           "getComputedStyle(document.getElementById('wrap')).display==='none'")
        ck("a " + role + " does not get the publish page", gone)
        pg.close()

    for who, role in (("chef@x", "chef"), ("staff@x", "admin")):
        pg = open_pub(LINK, email=who)
        pg.wait_for_timeout(600)
        ck("a " + role + " does",
           pg.evaluate("()=>getComputedStyle(document.getElementById('wrap')).display") != "none")
        pg.close()

    # ── it has to work on a phone ───────────────────────────────
    pg = open_pub(LINK, w=320)
    ck("nothing overflows the narrowest phone",
       pg.evaluate("()=>document.documentElement.scrollWidth<=320"))
    ck("the publish button is thumb sized",
       pg.evaluate("()=>pubBtn.getBoundingClientRect().height") >= 44)
    ck("and the inputs are 16px, or the phone zooms on focus",
       pg.evaluate("""()=>[...document.querySelectorAll('.c-name')]
          .every(i=>parseFloat(getComputedStyle(i).fontSize)>=16)"""))
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
errortrap.report()
