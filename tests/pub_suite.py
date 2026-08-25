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
import re
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
         "failMenuSave": False, "failTagSave": False, "menu": None,
         "mobile": "+61400000000"}
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
    if "/settings/managerMobile" in u:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(STATE["mobile"])); return
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
       pg.evaluate("""()=>['entree','main']
          .every(k=>document.getElementById('s_'+k).className.indexOf('on')<0)"""))
    #  A bread course and a dessert do not have a main protein, so the button
    #  there was a question with one answer, on the two courses where pressing
    #  it by accident puts (AUS) beside a focaccia on the guests' phones.
    ck("AUS is offered on the entree and the main",
       pg.evaluate("()=>!!(document.getElementById('s_entree') && document.getElementById('s_main'))"))
    ck("and not on the bread or the dessert",
       pg.evaluate("()=>!document.getElementById('s_bread') && !document.getElementById('s_dessert')"))
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
        ck("and false on the courses that cannot carry it at all",
           body["bread"]["aus"] is False and body["dessert"]["aus"] is False)
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

    #  Telling the manager, by the chef's own tap. announceMenu sends a push
    #  when it fires; this is the belt to those braces, and it is what the
    #  brief carried before the token was retired.
    pg.wait_for_timeout(500)
    link = pg.evaluate("""()=>{const a=document.querySelector('.notifylink');
        return a ? {href:a.getAttribute('href'),
                    h:Math.round(a.getBoundingClientRect().height)} : null;}""")
    print("   notify link:", link)
    ck("and offered a message to the manager", bool(link))
    if link:
        ck("addressed to the number, not to a name",
           link["href"].startswith("sms:+61400000000"))
        ck("with the words already in it, so nothing has to be typed",
           "menu%20is%20published" in link["href"] and
           "menu.nalaresort.com" in link["href"])
        ck("as a real target for a thumb", link["h"] >= 44)
    #  The number is NOT in this repository. It was taken out on 18 Aug and
    #  this repo is public until SECURITY.md job 4 is done.
    ck("and the number is nowhere in the page's own source",
       "61400000000" not in open("publish.html").read())
    ck("nor any other mobile number",
       not re.search(r"sms:\+?[0-9]{6,}", open("publish.html").read()))
    ck("and the button is gone, so it cannot be pressed twice",
       pg.evaluate("()=>getComputedStyle(bar).display") == "none")
    #  Reported 22 Aug: publishing hid the courses and the ticks and left the
    #  rest standing - the headings, the field for adding a dietary, the line
    #  about keeping one for good. A finished page with half its furniture on
    #  it reads as one that half worked, and the chef looks for what he is
    #  meant to do next.
    left = pg.evaluate("""()=>[...document.querySelectorAll('#wrap > *')]
        .filter(e=>getComputedStyle(e).display!=='none')
        .map(e=>e.id || e.className.split(' ')[0])""")
    print("   left on the finished page:", left)
    ck("nothing is left standing but the finish and the way off it",
       all(x in ("done", "navrow", "wordmark", "pagename", "demobar")
           for x in left))
    #  And there IS a way off it. This is the other half of the same report:
    #  the menu was drawn all along and rendered invisible, because the shared
    #  stylesheet takes its colours from tokens only a tier-app body carries.
    ck("the way off the page is there",
       pg.evaluate("()=>!!document.getElementById('navBtn')"))
    ck("and is actually visible, not drawn in colours that resolve to nothing",
       pg.evaluate("""()=>{const b=document.getElementById('navBtn');
          const r=b.getBoundingClientRect();
          const c=getComputedStyle(b);
          const bar=b.querySelector('span');
          const bc=getComputedStyle(bar).backgroundColor;
          return r.width>20 && r.height>20 &&
                 c.borderTopWidth!=='0px' &&
                 bc!=='rgba(0, 0, 0, 0)' && bc!=='transparent';}"""))
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
    ck("the finished screen is not a full stop",
       pg.evaluate("()=>{const a=document.querySelector('#doneActs .doneact');"
                   "return !!a && a.getAttribute('href')==='publish.html';}"))
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

    # ── every field big enough not to zoom the phone ────────────
    #  Safari zooms the page when a field under 16px takes focus and does not
    #  zoom back out, so the chef finishes the menu on a page he has to pinch
    #  and drag. The description field was 14.
    #  With a menu up, which is when the bar carries its second row and is at
    #  its tallest. Measured against the short bar it clears at any padding and
    #  the check proves nothing about the case that was reported.
    STATE["menu"] = {"published": now.isoformat(),
                     "bread": {"name": "Focaccia"}, "entree": {"name": "Scallops"},
                     "main": {"name": "Lamb"}, "dessert": {"name": "Pavlova"}}
    pg = open_pub(LINK, w=390)
    pg.wait_for_timeout(500)
    ck("the bar is at its tallest, with a menu up to take down",
       pg.evaluate("()=>getComputedStyle(removeRow).display") != "none")
    ck("no field on the page is under 16px",
       pg.evaluate("""()=>[...document.querySelectorAll('input,textarea')]
          .every(e=>parseFloat(getComputedStyle(e).fontSize) >= 16)"""))
    #  The bar is fixed to the bottom and grew a second row when Remove
    #  arrived. Under it, the last row of ticks is an allergy the chef cannot
    #  reach.
    #  Scrolled to the foot first: unscrolled, the last tick is simply below
    #  the viewport and the measurement says nothing about the bar.
    pg.evaluate("()=>window.scrollTo(0, document.body.scrollHeight)")
    pg.wait_for_timeout(300)
    room = pg.evaluate("""()=>{const t=[...document.querySelectorAll('#tagblock .tick')].pop();
        const b=document.getElementById('bar');
        if(!t||!b) return null;
        return Math.round(b.getBoundingClientRect().top - t.getBoundingClientRect().bottom);}""")
    print("   gap under the last tick, page scrolled to the foot:", room)
    #  The rule, stated as the rule rather than as a distance that happens to
    #  be positive today: the page's bottom padding has to clear the bar with
    #  room to spare. A phone eats into whatever is left - the home indicator
    #  sits over the bottom of the viewport and rubber-band scrolling hides a
    #  little more - so a gap that merely exists on a desktop viewport is a
    #  dietary that cannot be tapped in a kitchen.
    box = pg.evaluate("""()=>({pad:parseFloat(getComputedStyle(document.body).paddingBottom),
        bar:Math.round(document.getElementById('bar').getBoundingClientRect().height)})""")
    print("   bottom padding %s against a bar of %s" % (box["pad"], box["bar"]))
    ck("the page reserves more room than the bar takes, with margin to spare",
       box["pad"] >= box["bar"] + 40)
    ck("so the last dietary clears it when scrolled to the foot",
       room is not None and room > 0)
    STATE["menu"] = None
    pg.close()

    # ── a dietary that is not on the list ───────────────────────
    #  The model the owner set on 22 Aug. The settled list lives on the
    #  settings page and is what a guest is offered; here the chef ticks from
    #  it, and adds a one-off when tonight's menu needs something the list has
    #  not got. A dish with sesame in it, on a night nobody has sesame on the
    #  list yet. If he finds he is adding the same one weekly it has stopped
    #  being a one-off and belongs on the settings page, which is what the line
    #  under the field says.
    pg = open_pub(LINK)
    ck("the chef ticks from the settled list",
       "Gluten free" in pg.inner_text("#tagblock"))
    ck("and can add something it has not got",
       pg.evaluate("()=>!!document.getElementById('newDiet')"))
    #  Linked, but into a new tab. Everything on this page lives in memory
    #  until Publish, so navigating away mid-menu would cost the chef every
    #  correction he has made to the machine's reading of his handwriting.
    #  Opened beside the page, the page is still standing when he returns.
    ck("the page says where a one-off becomes permanent",
       "dietary settings" in pg.inner_text(".dietlink").lower())
    ck("and links there",
       pg.evaluate("()=>{const a=document.querySelector('.dietlink a');"
                   "return !!a && a.getAttribute('href')==='tag.html';}"))
    ck("beside this page, not instead of it",
       pg.evaluate("()=>document.querySelector('.dietlink a').target") == "_blank")

    #  The example is the point of the placeholder. "Something not on the list"
    #  describes the field; "e.g. raw fish" tells the chef what to type into it.
    ck("the field shows an example rather than describing itself",
       pg.get_attribute("#newDiet", "placeholder") == "e.g. raw fish")
    ck("but the menu does, for later",
       pg.evaluate("()=>[...document.querySelectorAll('#navDrop a')]"
                   ".some(a=>a.getAttribute('href')==='tag.html')"))

    #  One list, the same on every page, minus the page you are on. The owner
    #  reported pressing hamburgers everywhere and none of them agreeing; the
    #  older pages did agree with each other, and the two new ones were in none
    #  of their lists, so from Reservations there was no way to reach
    #  publishing at all.
    #  Grouped 22 Aug to the owner's own sketch: what you work on, what you
    #  print, what you set.
    CANON = ["front-desk.html", "tally.html", "invitations.html", "arrivals-sms.html", "cleaners.html", "publish.html",
             "list.html", "housekeeping.html", "registration.html", "menu-print.html", "past-menus.html",
             "staff.html", "tag.html", "pages.html"]
    got = pg.evaluate("""()=>[...document.querySelectorAll('#navDrop a')]
        .map(a=>a.getAttribute('href')).filter(h=>h!=='#')""")
    print("   publish nav:", got)
    ck("the menu lists every other page, in the one order",
       got == [h for h in CANON if h != "publish.html"])
    ck("and never itself", "publish.html" not in got)

    del WRITES[:]
    pg.fill("#newDiet", "Sesame")
    pg.locator("#addDiet").click(); pg.wait_for_timeout(600)
    ck("a one-off appears at once, because the next thing he does is tick it",
       "Sesame" in pg.inner_text("#tagblock"))
    #  Written straight away rather than held until Publish: the guest page
    #  reads this list, and a dietary a guest cannot declare warns nobody.
    dw = [w for w in WRITES if "/dietaries" in w["u"]]
    ck("and goes onto the list the guest page reads", len(dw) == 1)
    if dw:
        ck("as this-menu-only, not as one of the settled ones",
           json.loads(dw[0]["b"]).get("Sesame", {}).get("group") == "menu")
    ck("the field is cleared, so it is not added twice",
       val(pg, "newDiet") == "")
    ck("and it is not ticked on anything by being added",
       pg.evaluate("""()=>[...document.querySelectorAll('#tagblock .tick')]
          .filter(x=>x.getAttribute('data-n')==='Sesame')
          .every(x=>x.className.indexOf('on')<0)"""))
    ck("adding one does not disturb the menu being read",
       val(pg, "n_main") == "Sovereign lamb")
    pg.close()

    #  A one-off already on the list is not added twice.
    STATE["master"] = dict(MASTER); STATE["master"]["Sesame"] = {
        "name": "Sesame", "active": True, "group": "menu"}
    pg = open_pub(LINK)
    del WRITES[:]
    pg.fill("#newDiet", "Sesame")
    pg.locator("#addDiet").click(); pg.wait_for_timeout(400)
    ck("a name already on the list is refused, not duplicated",
       not [w for w in WRITES if "/dietaries" in w["u"]] and
       "already on the list" in pg.inner_text("#err"))
    pg.close()

    #  The one that keeps the tick list short. Every one-off ever made would
    #  otherwise pile up under the commons, and by the end of a season the chef
    #  reads a list of every one-off since March to find the eight that matter.
    STATE["tags"] = {}
    pg = open_pub(LINK)
    pg.wait_for_timeout(400)
    ck("an old one-off nobody has ticked tonight is not in the way",
       "Sesame" not in pg.inner_text("#tagblock"))
    ck("while the settled list is always there",
       "Gluten free" in pg.inner_text("#tagblock"))
    pg.close()

    #  But one that IS on tonight's menu comes back, or reopening the page
    #  would lose the tick and the dietary with it.
    STATE["tags"] = {"main": ["Sesame"]}
    pg = open_pub(LINK)
    pg.wait_for_timeout(400)
    ck("a one-off already tagged tonight comes back with its tick",
       "Sesame" in pg.inner_text("#tagblock") and
       pg.evaluate("""()=>[...document.querySelectorAll('#tagblock .tick')]
          .some(x=>x.getAttribute('data-n')==='Sesame' &&
                   x.getAttribute('data-c')==='main' &&
                   x.className.indexOf('on')>-1)"""))
    pg.close()
    STATE["tags"] = {}; STATE["master"] = MASTER

    # ── coming back to a menu already published ─────────────────
    #  The page had one door: the link the chat builds. Opened any other way it
    #  showed four empty boxes, so after publishing there was no way to correct
    #  a dish, retag a course or take the menu down, and "press the link again"
    #  is not an answer. The link is a shortcut for the first publish of the
    #  night now, not the only way in.
    STATE["menu"] = {"published": now.isoformat(),
                     "bread": {"name": "Focaccia", "desc": "ricotta", "aus": False},
                     "entree": {"name": "Scallops", "desc": "", "aus": True},
                     "main": {"name": "Lamb", "desc": "salsa verde", "aus": False},
                     "dessert": {"name": "Pavlova", "desc": "", "aus": False}}
    pg = open_pub("")
    pg.wait_for_timeout(700)
    ck("opened with no link, the page shows what is published",
       val(pg, "n_main") == "Lamb" and val(pg, "d_main") == "salsa verde")
    ck("with AUS as it was published", pg.evaluate("()=>s_entree.className.indexOf('on')>-1"))
    ck("and says so, rather than looking like a blank form",
       "as the guests see it" in pg.inner_text("#lede"))
    ck("the button says it is a change, not a first publish",
       pg.locator("#pubBtn").text_content().strip() == "Publish changes")
    ck("and the way to take it down is offered",
       pg.evaluate("()=>getComputedStyle(removeRow).display") != "none")
    pg.close()

    #  A link is the chat handing over a NEW menu and beats what is up.
    pg = open_pub(LINK)
    pg.wait_for_timeout(700)
    ck("a link still wins over what is already published",
       val(pg, "n_main") == "Sovereign lamb")
    pg.close()
    STATE["menu"] = None

    #  Nothing is published, so there is nothing to come back to.
    pg = open_pub("")
    pg.wait_for_timeout(600)
    ck("with nothing published the page is a blank form, as it always was",
       val(pg, "n_main") == "")
    ck("and offers no way to take down a menu that is not there",
       pg.evaluate("()=>getComputedStyle(removeRow).display") == "none")
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
    #  A rehearsal never offers to tell anybody: a message saying the menu is
    #  published is a lie about a menu nobody can see.
    ck("the chef is told the guests see no menu",
       "removed" in pg.inner_text("#done").lower())
    ck("and offered the way back to publishing one",
       "publish tonight" in pg.inner_text("#doneActs").lower())
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

    # ── who sees what in the menu ───────────────────────────────
    #  NAV_NEEDS maps a link to the permission that opens it, and the filter
    #  hides what a role cannot use. publish.html and tag.html were missing
    #  from that map until 22 Aug, so every login saw them: a housekeeper's
    #  menu offered to publish the dinner menu, and tapping it bounced her
    #  back to her own board. Nothing tested this map, which is why.
    pg = open_pub(LINK)
    seen = pg.evaluate("""()=>{
      const out = {};
      ['chef','waiter','housekeeping','admin'].forEach(r=>{
        window.NALA_NAVFILTER(r);
        out[r] = [...document.querySelectorAll('#navDrop a')]
          .filter(a=>getComputedStyle(a).display!=='none')
          .map(a=>a.getAttribute('href')).filter(h=>h!=='#');
      });
      return out;
    }""")
    print("   menu by role:", seen)
    ck("a housekeeper is not offered the menu pages",
       "tag.html" not in seen["housekeeping"] and
       "publish.html" not in seen["housekeeping"])
    ck("nor a waiter", "tag.html" not in seen["waiter"] and
       "publish.html" not in seen["waiter"])
    ck("the chef is", "tag.html" in seen["chef"])
    ck("and the manager is", "tag.html" in seen["admin"])
    #  Every link left standing has to open. A link that bounces you back is a
    #  door to nowhere, which is worse than no link.
    NEEDS = {"tally.html":"resBoard", "front-desk.html":"editBookings",
             "invitations.html":"editBookings",
             "arrivals-sms.html":"editBookings",
             "list.html":"resSheet", "publish.html":"publishMenu",
             "tag.html":"publishMenu", "cleaners.html":"cleansBoard",
             "housekeeping.html":"cleansBoard", "registration.html":"editBookings",
             "menu-print.html":"resSheet", "past-menus.html":"resBoard",
             "staff.html":"manageStaff", "pages.html":"manageStaff"}
    ck("every link in the menu has a permission behind it",
       all(h in NEEDS for r in seen for h in seen[r]))
    #  A heading with nothing under it promises something that is not there.
    empty = pg.evaluate("""()=>{
      window.NALA_NAVFILTER('housekeeping');
      return [...document.querySelectorAll('#navDrop .navgrp')]
        .filter(g=>getComputedStyle(g).display!=='none')
        .map(g=>g.textContent);
    }""")
    print("   headings a housekeeper sees:", empty)
    #  Settings now holds Notifications, which is not filtered by role: a
    #  housekeeper subscribes to her own alerts. So the heading correctly
    #  stands for her, and what proves the rule still works is that she is
    #  offered the switch and none of the pages she cannot open.
    ck("a heading only stands when something under it does",
       empty == ["Print", "Settings"])
    ck("and the housekeeper's Settings holds the switch and nothing else",
       pg.evaluate("""()=>{ window.NALA_NAVFILTER('housekeeping');
          const k=[...navDrop.children];
          const g=k.findIndex(e=>e.textContent==='Settings' &&
                                 e.className.indexOf('navgrp')>-1);
          return k.slice(g+1).filter(e=>e.tagName==='A' &&
                 e.className.indexOf('signout')<0 &&
                 getComputedStyle(e).display!=='none')
                 .map(e=>e.id); }""") == ["navNotify"])
    pg.evaluate("()=>window.NALA_NAVFILTER('admin')")
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
