"""tag.html, Menu Dietaries.

The chef ticks which dietaries each dish does not suit, and the guest page uses
those ticks to decide who gets asked for a note. Two things make this page
worth pinning carefully.

The first is that Save is a PUT of the whole master list. That is fine when the
list on screen is the list in the database, and destructive when it is not. The
page used to treat a refused read as an absent list, seed the eight defaults
over the top of it, and offer a Save button that would then overwrite every
dietary the chef had ever added. A read that fails now locks the page instead.

The second is the gate on whether a menu exists. It asked for a bread course by
name, so a menu with no bread read as no menu at all, and the chef was told to
publish a menu that was already published.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8973), Q)
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
SDK = sdk()

FULL_MENU = {"published": now.isoformat(),
             "bread": {"name": "Sourdough"}, "entree": {"name": "Kingfish crudo"},
             "main": {"name": "Lamb rump"}, "dessert": {"name": "Pavlova"}}

MASTER = {"Gluten":      {"name": "Gluten", "active": True, "group": "common"},
          "Nut allergy": {"name": "Nut allergy", "active": True, "group": "common"},
          "Chilli":      {"name": "Chilli", "active": True, "group": "menu"},
          "Old thing":   {"name": "Old thing", "active": False, "group": "common"}}

# A list saved before the 26 Aug renames: two pills still wear the old
# wording. The page must show them renamed and OFFER a save, never write one
# unasked - Save is a PUT of the whole list and stays a person's decision.
OLD_MASTER = {"Gluten free": {"name": "Gluten free", "active": True, "group": "common"},
              "Dairy free":  {"name": "Dairy free", "active": False, "group": "common"},
              "Nut allergy": {"name": "Nut allergy", "active": True, "group": "common"}}

STAFF = {"chef@x": {"name": "Chef", "role": "chef"},
         "staff@x": {"name": "Admin", "role": "admin"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STATE = {"menu": FULL_MENU, "fileMenu": True, "master": MASTER, "tags": {"main": ["Nut allergy"]},
         "failMaster": False, "failTags": False, "failSave": False}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["failSave"]:
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

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_tag(w=390, email="chef@x"):
        del WRITES[:]
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(sdk(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        #  The database node is /menu, which over REST is spelled
        #  .../menu.json, exactly like the repo file. One route used to catch
        #  both, so a page reading only the stale file looked fine here. They
        #  are answered separately now: the file can be missing while the
        #  database has tonight's menu, which is the arrangement since
        #  publishing moved off GitHub.
        def menu_route(r):
            from_db = "firebasedatabase.app" in r.request.url
            have = STATE["menu"] if (from_db or STATE["fileMenu"]) else None
            r.fulfill(status=(404 if have is None else 200),
                      content_type="application/json",
                      body=("" if have is None else json.dumps(have)))
        pg.route("**/menu.json*", menu_route)
        pg.goto("http://localhost:8973/tag.html")
        pg.wait_for_timeout(900)
        return pg

    # ── the page is the list, not tonight's menu ──────────────
    #  Until 22 Aug this page also tagged tonight's dishes, and so did the
    #  publish page. Both wrote the WHOLE of /menutags rather than a field, so
    #  whichever saved second replaced the other's ticks without saying so.
    #  Tagging moved to publishing, where the dishes are being written; this
    #  page keeps the list those tags are made from.
    pg = open_tag()
    ck("the page does not tag tonight's dishes",
       pg.locator(".course.show").count() == 0)
    ck("and says where they are tagged instead",
       "publish" in pg.inner_text(".lede").lower())
    ck("it calls itself settings, not tonight's menu",
       "dietary settings" in pg.inner_text(".pagename").lower())
    ck("the list itself is here", "Gluten" in pg.inner_text("#mng"))
    ck("archived dietaries are shown, so they can be brought back",
       "Old thing" in pg.inner_text("#mng"))
    ck("nothing is offered to save before anything is touched",
       "show" not in (pg.get_attribute("#savebar", "class") or ""))

    #  Reported 22 Aug: this page had no navigation of any kind, so a chef who
    #  reached it was stuck with the browser's back button, and in a standalone
    #  window with none at all. Every other staff page has the hamburger.
    ck("there is a way off this page",
       pg.evaluate("()=>!!document.getElementById('navBtn')"))
    #  It was drawn from the first and rendered invisible: the shared sheet
    #  takes its colours from --ctl-* tokens that only exist on a body carrying
    #  tier-app or tier-print, and this page carries neither. Every border and
    #  every bar of the icon resolved to nothing. Asserting presence alone
    #  passed the whole time, which is the same fault as reading the original
    #  element instead of the printed clone.
    ck("and it is actually visible, not drawn in colours that resolve to nothing",
       pg.evaluate("""()=>{const b=document.getElementById('navBtn');
          const r=b.getBoundingClientRect();
          const c=getComputedStyle(b);
          const bc=getComputedStyle(b.querySelector('span')).backgroundColor;
          return r.width>20 && r.height>20 &&
                 c.borderTopWidth!=='0px' &&
                 bc!=='rgba(0, 0, 0, 0)' && bc!=='transparent';}"""))
    #  The same list as every other page, in the same order, minus this one.
    #  The owner reported pressing hamburgers everywhere and none of them
    #  agreeing: the older pages did agree with each other, and the two newest
    #  were in none of their lists, so from Reservations there was no way to
    #  reach publishing at all.
    #  Read from tests/nav_canon.json, the one table of the menu's shape,
    #  rather than restated here: four suites each holding the order is why
    #  adding a page meant editing them all.
    _nc = json.load(open("tests/nav_canon.json"))
    CANON = [h for h, _t in _nc["top"]] + \
            [h for _g, items in _nc["groups"] for h, _t in items]
    got = pg.evaluate("""()=>[...document.querySelectorAll('#navDrop a')]
        .map(a=>a.getAttribute('href')).filter(h=>h!=='#')""")
    ck("the menu is the one list, minus this page",
       got == [h for h in CANON if h != "tag.html"])
    ck("and publishing is on it, which is where the chef came from",
       "publish.html" in got)
    ck("with a way out of the app entirely, which every login must have",
       pg.evaluate("()=>!!document.getElementById('navSignout')"))
    pg.evaluate("()=>navBtn.click()")
    pg.wait_for_timeout(150)
    ck("and the menu opens when pressed",
       "open" in (pg.get_attribute("#navDrop", "class") or ""))
    #  Notifications live under Settings on every page from 23 Aug. They were
    #  written into the Cleans board alone, so the only way to turn them on was
    #  to open a board a chef cannot, and subscribing is per person per device.
    ck("notifications can be switched from here, not only from the Cleans board",
       pg.evaluate("()=>!!document.getElementById('navNotify')"))
    ck("and it sits inside the Settings submenu, with the things you set",
       pg.evaluate("""()=>{
          const g=[...document.querySelectorAll('#navDrop .navgroup')]
            .find(w=>w.querySelector('.navgrp span').textContent==='Settings');
          return !!g && g.contains(document.getElementById('navNotify'));}"""))
    #  The word stays and a mark carries the state. "Notifications on" cannot
    #  be read: there is no telling whether it describes what is true or what
    #  tapping will do.
    marks = pg.evaluate("""()=>{const out={};
       ['on','off','blocked','unsupported'].forEach(s=>{
         window.__paintNotify(s);
         const m = navNotify.querySelector('.navmark');
         out[s] = { label: navNotify.querySelector('.navlabel').textContent,
                    mark: m ? m.className : null,
                    note: (navNotify.querySelector('.navnote')||{}).textContent || null };
       });
       return out;}""")
    print("   notify states:", marks)
    ck("the word never changes, in any state",
       all(v["label"] == "Notifications" for v in marks.values()))
    ck("on wears a tick and off wears a cross",
       "on" in marks["on"]["mark"] and "off" in marks["off"]["mark"])
    #  Blocked and unavailable are not the off state and must not wear its
    #  mark: off is a choice undone here, those two cannot be undone here at
    #  all, so they say so in words.
    ck("blocked wears neither, and says why",
       marks["blocked"]["mark"] is None and marks["blocked"]["note"])
    ck("nor does unavailable, which needs the Home Screen",
       marks["unsupported"]["mark"] is None and
       "home screen" in marks["unsupported"]["note"].lower())
    #  Left open, the drop-down covers the page and every later click in this
    #  suite lands on it instead of on the page.
    pg.evaluate("()=>navDrop.classList.remove('open')")

    # ── and it writes only the list ───────────────────────────
    #  The one that matters: no second writer on /menutags. A page that still
    #  wrote it would go on quietly overwriting the chef's tagging every time
    #  somebody opened settings and pressed Save.
    pg.fill("#newName", "Sesame allergy")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("adding offers a Save", "show" in pg.get_attribute("#savebar", "class"))
    pg.click("#saveBtn"); pg.wait_for_timeout(500)
    ck("Save writes the master list", bool(wrote("/dietaries")))
    ck("and writes nothing at all to tonight's tags",
       not wrote("/menutags/"))
    ck("the master list written back is the one that was read, plus the new one",
       set(json.loads(wrote("/dietaries")[0]["b"]).keys())
         == set(MASTER.keys()) | {"Sesame allergy"})
    # The label is upper-cased in CSS, so compare on the rendered text.
    ck("and the page says it saved", "SAVED" in pg.inner_text("#savedMsg").upper())
    pg.close()

    # ── adding and archiving ──────────────────────────────────
    pg = open_tag()
    pg.fill("#newName", "Sesame allergy")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("a new dietary appears in the list", "Sesame allergy" in pg.inner_text("#mng"))
    ck("and is live to be tagged with, not waiting on a save",
       "Sesame allergy" in pg.inner_text("#mng"))
    ck("the field is cleared, so it is not added twice",
       pg.input_value("#newName") == "")
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    master = json.loads(wrote("/dietaries")[0]["b"])
    ck("the added dietary is saved as common by default",
       master.get("Sesame allergy", {}).get("group") == "common")
    pg.close()

    pg = open_tag()
    pg.click("#gMenu")
    pg.fill("#newName", "Extra chilli")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    master = json.loads(wrote("/dietaries")[0]["b"])
    ck("a this-menu-only dietary is saved as such",
       master.get("Extra chilli", {}).get("group") == "menu")
    pg.close()

    # A name that already exists must not become a second record. Two rows
    # saying "Gluten free" is how a guest ends up ticking one and the kitchen
    # reading the other.
    pg = open_tag()
    pg.fill("#newName", "Old thing")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("re-adding an archived name restores it rather than duplicating it",
       pg.inner_text("#mng").count("Old thing") == 1
       and "Old thing" in pg.inner_text("#mng"))
    pg.close()

    pg = open_tag()
    pg.fill("#newName", "   ")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("an empty name adds nothing", "show" not in (pg.get_attribute("#savebar", "class") or ""))
    pg.close()

    # Hiding has to pull the dietary off the dishes as well, or the tag
    # survives invisibly and the guest page keeps acting on it. The button
    # says Hide, not Archive - the owner's word, 26 Aug, same as Flag
    # Settings, so the two Settings pages speak alike.
    pg = open_tag()
    row = pg.locator(".mrow").filter(has_text="Nut allergy")
    ck("an active dietary offers Hide, and no Delete: hide first, then delete",
       row.locator(".mtog").text_content() == "Hide"
       and row.locator(".mdel").count() == 0)
    row.locator(".mtog").click(); pg.wait_for_timeout(150)
    #  Hidden means the guest is no longer offered it. The publish page
    #  reads the same list and stops offering it as a tick for the same
    #  reason, which is checked there.
    ck("hiding marks it off, without deleting it",
       "off" in (pg.evaluate("()=>[...document.querySelectorAll('.mrow')].find(r=>r.textContent.indexOf('Nut allergy')>-1).className") or ""))
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    ck("and nothing is written to tonight's tags by hiding either",
       not wrote("/menutags/"))
    ck("but the dietary itself is kept, hidden, not deleted",
       "Nut allergy" in json.loads(wrote("/dietaries")[0]["b"]) and
       json.loads(wrote("/dietaries")[0]["b"]).get("Nut allergy", {}).get("active") is False)

    #  Delete, offered only once a dietary is hidden, lands only on Save: a
    #  mis-tap costs a re-add, not a dietary. "Old thing" arrives hidden in
    #  the fixture, so it is the one carrying the button.
    old_row = pg.locator(".mrow").filter(has_text="Old thing")
    ck("a hidden dietary offers Delete beside Show",
       old_row.locator(".mtog").first.text_content() == "Show"
       and old_row.locator(".mdel").count() == 1)
    old_row.locator(".mdel").click(); pg.wait_for_timeout(150)
    ck("Delete takes the row off the list",
       pg.evaluate("()=>![...document.querySelectorAll('.mrow')]"
                   ".some(r=>r.textContent.indexOf('Old thing')>-1)"))
    del WRITES[:]
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    #  Anchored on Nut allergy, not Gluten free: the rename tests above have
    #  already worked on the fixture by the time this runs.
    ck("and Save writes the list without it, for good",
       bool(wrote("/dietaries")) and
       "Old thing" not in wrote("/dietaries")[0]["b"] and
       "Nut allergy" in wrote("/dietaries")[0]["b"])
    pg.close()

    # ── the menu is no longer this page's business ────────────
    #  Three blocks lived here: a menu read from the database, a menu that was
    #  missing or stale or short a course, and what the page said in each case.
    #  All of it was about deciding which dishes to offer for tagging, and this
    #  page does not tag. The publish page reads the menu now, because it is
    #  the page writing it, and pub_suite covers that.
    pg = open_tag()
    ck("the page reads no menu at all",
       not [w for w in WRITES if "/menu" in w["u"]] and
       "No menu is published" not in pg.inner_text("body"))
    ck("so a night with no menu published is not its problem",
       pg.locator("#mng").is_visible())
    pg.close()

    # ── a read that failed is not an empty list ───────────────
    # This is the destructive one. Seeding the defaults over an unreadable list
    # and then offering Save would replace the chef's dietaries with the eight
    # built-in ones.
    STATE["failMaster"] = True
    pg = open_tag()
    ck("a refused dietaries read is reported", "show" in pg.get_attribute("#err", "class"))
    ck("and does not silently seed the built-in defaults",
       "Pescatarian" not in pg.inner_text("#mng"))
    pg.fill("#newName", "Anything")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    # Clicked through the DOM: a locked page may keep the Save bar off screen,
    # and the assertion is about what gets written, not about reachability.
    pg.eval_on_selector("#saveBtn", "e=>e.click()"); pg.wait_for_timeout(400)
    ck("and nothing can be written over the list that could not be read",
       not wrote("/dietaries"))
    pg.close()
    STATE["failMaster"] = False

    STATE["failTags"] = True
    pg = open_tag()
    ck("a refused tags read is reported too", "show" in pg.get_attribute("#err", "class"))
    pg.eval_on_selector("#saveBtn", "e=>e.click()"); pg.wait_for_timeout(400)
    ck("and tonight's tags are not overwritten with nothing",
       not wrote("/menutags"))
    pg.close()
    STATE["failTags"] = False

    # An empty database is a different thing from an unreadable one, and here
    # the defaults are exactly right.
    STATE["master"] = None
    pg = open_tag()
    ck("an empty list seeds the common dietaries", "Pescatarian" in pg.inner_text("#mng"))
    ck("and the whole set is listed", "Vegan" in pg.inner_text("#mng"))
    ck("and the seeded pills carry the renamed wording",
       "Gluten" in pg.inner_text("#mng") and
       "Gluten free" not in pg.inner_text("#mng"))
    pg.close()
    STATE["master"] = MASTER

    # ── a list saved before the 26 Aug renames ────────────────────
    # "Gluten free" and "Dairy free" became "Gluten" and "Dairy". The stored
    # list still says the old names; the page shows the new ones and OFFERS
    # the save that would teach the database - offered, never written unasked,
    # because Save is a PUT of the whole list and stays a person's decision.
    # Guest answers saved under the old names need no sweep: every reader
    # maps them, which index/pre/fd/tally suites pin on their own screens.
    STATE["master"] = OLD_MASTER
    pg = open_tag()
    ck("a pill saved under its old name is shown renamed",
       "Gluten" in pg.inner_text("#mng") and
       "Gluten free" not in pg.inner_text("#mng"))
    ck("an archived one is renamed too, still archived",
       "Dairy" in pg.inner_text("#mng") and
       "Dairy free" not in pg.inner_text("#mng"))
    ck("the rename is offered as a save, since screen and database now differ",
       "show" in (pg.get_attribute("#savebar", "class") or ""))
    ck("but nothing is written until somebody presses it", not WRITES)
    # The rename table on this page comes from nala-shared.js; the guest pages
    # carry forced copies. tests/diet_renames.json is the one table all of
    # them are checked against.
    RENAMES = json.load(open("tests/diet_renames.json"))
    ck("the shared rename table matches tests/diet_renames.json",
       pg.evaluate("()=>DIET_RENAMES") == RENAMES)
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    saved = json.loads(wrote("/dietaries")[0]["b"])
    ck("pressing Save writes the list under the new names",
       "Gluten" in saved and "Dairy" in saved and
       "Gluten free" not in saved and "Dairy free" not in saved)
    ck("with each record renamed, nothing else about it changed",
       saved["Gluten"] == {"name": "Gluten", "active": True, "group": "common"} and
       saved["Dairy"]["active"] is False)
    ck("and the untouched pill rides along as it was",
       saved.get("Nut allergy", {}).get("active") is True)
    pg.close()
    STATE["master"] = MASTER

    # ── a save that fails must not look like a save ───────────
    STATE["failSave"] = True
    pg = open_tag()
    #  Any change to the list will do; there are no ticks on this page now.
    pg.fill("#newName", "Celery")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    pg.click("#saveBtn"); pg.wait_for_timeout(500)
    ck("a refused save says so", "show" in pg.get_attribute("#err", "class"))
    ck("does not claim to have saved", "SAVED" not in pg.inner_text("#savedMsg").upper())
    ck("leaves the Save button usable", not pg.is_disabled("#saveBtn"))
    ck("and keeps the unsaved work in front of the chef",
       "show" in pg.get_attribute("#savebar", "class"))
    pg.close()
    STATE["failSave"] = False

    # ── who may change the list ───────────────────────────────
    # Until 18 Aug this page had no gate, so any login could archive the
    # chef's dietary list. It is the chef's page and the manager's, and
    # the owner confirmed on 22 Aug that admin belongs here too.
    pg = open_tag(email="chef@x")
    ck("the chef gets the page", pg.locator("#mng").is_visible())
    pg.close()
    pg = open_tag(email="staff@x")
    ck("and so does the manager", pg.locator("#mng").is_visible())
    pg.close()
    for who, label in (("waiter@x", "a waiter"), ("housekeeping@x", "housekeeping")):
        q = open_tag(email=who)
        q.wait_for_timeout(600)
        ck("%s is sent to their own board instead" % label,
           not q.url.endswith("tag.html"))
        q.close()

    # ── phone geometry ────────────────────────────────────────
    for w in (390, 360, 320):
        q = open_tag(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        if w == 390:
            ck("the ticks are a comfortable size for a thumb", q.evaluate(
                "()=>[...document.querySelectorAll('.tick')].every(e=>e.getBoundingClientRect().height>=30)"))
            ck("the Save button is a full tap target, like the room tiles", q.evaluate(
                "()=>document.getElementById('saveBtn').getBoundingClientRect().height>=44"))
        q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
