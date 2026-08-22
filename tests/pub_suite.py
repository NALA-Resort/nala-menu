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
         "failMenuSave": False, "failTagSave": False, "menu": None}
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
    if u.rstrip("/").endswith("/menu.json") or "/menu.json?" in u:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STATE["menu"])); return
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

#  No sf. AUS is a button on the page and nothing else: the link used to carry
#  a guess at it, worked out by the chat from a paragraph of fish species, and
#  the page drew a toggle beside every course anyway.
LINK = ("?b=" + urllib.parse.quote("Tomato focaccia - whipped ricotta") +
        "&e=" + urllib.parse.quote("Hervey Bay scallops - burnt butter") +
        "&m=" + urllib.parse.quote("Sovereign lamb - salsa verde") +
        "&d=" + urllib.parse.quote("Mandarin cheesecake"))

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
    #  AUS is the chef's, and only the chef's. A link cannot set it and the
    #  chat is told not to try, because it was a machine guessing from
    #  handwriting at something the man who wrote the menu already knows.
    ck("nothing arrives ticked for AUS, whatever the link says",
       pg.evaluate("""()=>['bread','entree','main','dessert']
          .every(k=>document.getElementById('s_'+k).className.indexOf('on')<0)"""))
    ck("the button says what it does, not what it means",
       pg.evaluate("()=>s_main.textContent.trim()") == "AUS" and
       "(AUS)" in pg.inner_text("#courses"))
    pg.close()

    #  Opened WITH the old parameter, or this proves nothing: a link that
    #  cannot set AUS has to be shown a link trying to.
    pg = open_pub(LINK + "&sf=e")
    ck("even when a link still carries the old sf parameter",
       pg.evaluate("()=>s_entree.className.indexOf('on')<0"))
    pg.close()
    pg = open_pub(LINK)

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
    ck("AUS is set by pressing it",
       pg.evaluate("()=>s_main.className.indexOf('on')>-1"))
    pg.evaluate("()=>s_main.click()")
    ck("and unset by pressing it again",
       not pg.evaluate("()=>s_main.className.indexOf('on')>-1"))
    ck("still nothing published", len(published()) == 0)
    pg.close()

    # ── tagging is on this page, not behind a link ──────────────
    pg = open_pub(LINK + "&sf=e")
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
        ck("carrying the dish and the description",
           body["entree"]["name"] == "Hervey Bay scallops" and
           body["entree"]["desc"] == "burnt butter")
        ck("and AUS false on a dish nobody pressed it for",
           body["entree"]["aus"] is False)
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

    # ── the rehearsal ───────────────────────────────────────────
    #  ?demo=1 sends every write to /demo instead of the real node, so the
    #  whole thing can be tried end to end - a real sign in, a real write, a
    #  real read back - without tonight's menu changing on the guests' phones.
    #  No rules change was needed: rules.json has an $other catch-all granting
    #  a signed in user read and write on a node it does not name.
    pg = open_pub(LINK + "&demo=1")
    ck("a rehearsal says so, loudly, before anything is pressed",
       pg.evaluate("()=>demoBar.className.indexOf('show')>-1"))
    ck("and says it in terms of what it does not do",
       "guests" in pg.inner_text("#demoBar").lower())
    pg.evaluate("""()=>{var t=[...document.querySelectorAll('#tagblock .tick')]
        .find(x=>x.getAttribute('data-c')==='main'); t.click();}""")
    del WRITES[:]
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(900)

    #  The whole point: nothing lands on a node any guest or board reads.
    ck("the menu is written to the sandbox, not the live node",
       len([w for w in WRITES if "/demo/menu.json" in w["u"]]) == 1)
    ck("and tonight's tags with it",
       len([w for w in WRITES if "/demo/menutags/" in w["u"]]) == 1)
    ck("and nothing at all touches the live menu or the live tags",
       not [w for w in WRITES
            if "/demo/" not in w["u"] and
               ("/menu.json" in w["u"] or "/menutags/" in w["u"])])
    #  A demo that half happens is worse than none: the prefix is decided in
    #  one place so the menu cannot go to the sandbox while the tags go live.
    ck("both halves go to the same place",
       len([w for w in WRITES if "/demo/" in w["u"]]) == 2)
    ck("the chef is told it was a rehearsal, not that it is live",
       "rehearsal" in pg.inner_text("#done").lower())
    ck("and is not sent to the guest site, which would show the real menu",
       "menu.nalaresort.com" not in pg.evaluate("()=>doneWhere.innerHTML"))
    pg.close()

    #  The dietary list is read LIVE even in a rehearsal: it is the chef's real
    #  list and ticking against invented ones would prove nothing.
    pg = open_pub(LINK + "&demo=1")
    ck("the rehearsal ticks against the chef's real dietary list",
       "Gluten free" in pg.inner_text("#tagblock"))
    ck("and reads its own tags, not tonight's real ones",
       len([w for w in WRITES if "/menutags/" in w["u"] and "/demo/" not in w["u"]]) == 0)
    pg.close()

    #  Without the flag, nothing changes.
    pg = open_pub(LINK)
    del WRITES[:]
    pg.locator("#pubBtn").click(); pg.wait_for_timeout(900)
    ck("a normal publish still goes to the live node",
       len([w for w in WRITES if "/demo/" in w["u"]]) == 0 and
       len([w for w in WRITES if "/menu.json" in w["u"]]) == 1)
    ck("and carries no rehearsal banner",
       pg.evaluate("()=>demoBar.className.indexOf('show')<0"))
    pg.close()

    # ── taking a menu down ──────────────────────────────────────
    #  Restored 22 Aug. "Remove menu" was in the brief until 21 Aug and was
    #  lost with the Rules section in the rewrite that changed how publishing
    #  worked. It matters because the guest page keeps a published menu until
    #  midnight of its own day: a wrong one put up at five has no way off the
    #  phones for seven hours, and publishing a corrected one is no answer when
    #  the correction is that there is no dinner.
    pg = open_pub(LINK)
    ck("nothing to remove when no menu is up",
       pg.evaluate("()=>getComputedStyle(removeRow).display") == "none")
    pg.close()

    STATE["menu"] = {"published": now.isoformat(),
                     "bread": {"name": "Focaccia"}, "entree": {"name": "Scallops"},
                     "main": {"name": "Lamb"}, "dessert": {"name": "Pavlova"}}
    pg = open_pub(LINK)
    pg.wait_for_timeout(400)
    ck("the way down is offered once a menu is up",
       pg.evaluate("()=>getComputedStyle(removeRow).display") != "none")

    #  One press arms it, and the second says what it will do. It is a stride
    #  from Publish on a phone at service time, and this is the one control
    #  here that destroys rather than replaces.
    del WRITES[:]
    pg.locator("#rmBtn").click(); pg.wait_for_timeout(200)
    ck("one press does not take a menu down",
       len(WRITES) == 0)
    ck("it arms, and says what the next press does",
       "take it down" in pg.locator("#rmBtn").text_content().lower())

    pg.locator("#rmBtn").click(); pg.wait_for_timeout(900)
    mw = [w for w in WRITES if "/menu.json" in w["u"]]
    ck("the second press takes it down", len(mw) == 1)
    if mw:
        body = json.loads(mw[0]["b"])
        #  The guest page checks `published` before anything else and shows its
        #  placeholder without it.
        ck("with no publish time, which is what the guest page reads as none",
           body.get("published") == "")
        ck("and the courses blanked, so nothing can surface them again",
           all(body[c]["name"] == "" for c in ("bread","entree","main","dessert")))
    #  A menu removed while its tags stay is a night where the front desk
    #  checks a guest's allergies against dishes nobody is cooking.
    tw = [w for w in WRITES if "/menutags/" in w["u"]]
    ck("and tonight's dietary ticks go with it", len(tw) == 1 and
       json.loads(tw[0]["b"] or "{}") == {})
    ck("the chef is told the guests see no menu",
       "removed" in pg.inner_text("#done").lower())
    pg.close()

    #  A rehearsal takes down the rehearsal, never the real menu.
    pg = open_pub(LINK + "&demo=1")
    pg.wait_for_timeout(400)
    del WRITES[:]
    pg.locator("#rmBtn").click(); pg.wait_for_timeout(200)
    pg.locator("#rmBtn").click(); pg.wait_for_timeout(900)
    ck("a rehearsal removal touches only the sandbox",
       all("/demo/" in w["u"] for w in WRITES) and len(WRITES) == 2)
    pg.close()
    STATE["menu"] = None

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
