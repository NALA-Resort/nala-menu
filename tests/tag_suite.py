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
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8973), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'chef@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'chef@x'});},25);},
signOut:function(){}};"""

FULL_MENU = {"published": now.isoformat(),
             "bread": {"name": "Sourdough"}, "entree": {"name": "Kingfish crudo"},
             "main": {"name": "Lamb rump"}, "dessert": {"name": "Pavlova"}}

MASTER = {"Gluten free": {"name": "Gluten free", "active": True, "group": "common"},
          "Nut allergy": {"name": "Nut allergy", "active": True, "group": "common"},
          "Chilli":      {"name": "Chilli", "active": True, "group": "menu"},
          "Old thing":   {"name": "Old thing", "active": False, "group": "common"}}

STATE = {"menu": FULL_MENU, "master": MASTER, "tags": {"main": ["Nut allergy"]},
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

    def open_tag(w=390):
        del WRITES[:]
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.route("**/gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/menu.json*", lambda r: r.fulfill(
            status=(404 if STATE["menu"] is None else 200),
            content_type="application/json",
            body=("" if STATE["menu"] is None else json.dumps(STATE["menu"]))))
        pg.goto("http://localhost:8973/tag.html")
        pg.wait_for_timeout(900)
        return pg

    def ticks(pg, course_index=2):
        return pg.locator(".course").nth(course_index).locator(".tick")

    # ── the ordinary day ──────────────────────────────────────
    pg = open_tag()
    ck("every published course is offered for tagging",
       pg.locator(".course.show").count() == 4)
    ck("the dish name is shown, not the course key",
       "Lamb rump" in pg.inner_text(".course:nth-of-type(3)"))
    ck("archived dietaries are not offered as ticks",
       "Old thing" not in pg.inner_text("#courses"))
    ck("an active dietary is offered on every course",
       ticks(pg).filter(has_text="Gluten free").count() == 1)
    ck("what is already tagged comes back ticked",
       ticks(pg).filter(has_text="Nut allergy").first.get_attribute("class").find("on") > -1)
    ck("nothing is offered to save before anything is touched",
       "show" not in (pg.get_attribute("#savebar", "class") or ""))

    # ── ticking, and what Save writes ─────────────────────────
    ticks(pg).filter(has_text="Gluten free").first.click()
    pg.wait_for_timeout(150)
    ck("ticking offers a Save", "show" in pg.get_attribute("#savebar", "class"))
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    ck("Save writes the master list", bool(wrote("/dietaries")))
    ck("and tonight's tags, dated", bool(wrote("/menutags/" + today)))
    tags = json.loads(wrote("/menutags/" + today)[0]["b"])
    ck("the tick reaches the write body",
       "Gluten free" in tags.get("main", []) and "Nut allergy" in tags.get("main", []))
    ck("the master list written back is the one that was read",
       set(json.loads(wrote("/dietaries")[0]["b"]).keys()) == set(MASTER.keys()))
    # The label is upper-cased in CSS, so compare on the rendered text.
    ck("and the page says it saved", "SAVED" in pg.inner_text("#savedMsg").upper())
    pg.close()

    # Untick, and the tag has to actually leave the write. A tick that only
    # ever adds is how a dish ends up flagged for everything.
    pg = open_tag()
    ticks(pg).filter(has_text="Nut allergy").first.click()
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    body = json.loads(wrote("/menutags/" + today)[0]["b"])
    ck("unticking removes the tag from the write", "Nut allergy" not in body.get("main", []))
    pg.close()

    # ── adding and archiving ──────────────────────────────────
    pg = open_tag()
    pg.fill("#newName", "Sesame allergy")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("a new dietary appears in the list", "Sesame allergy" in pg.inner_text("#mng"))
    ck("and immediately on every course", "Sesame allergy" in pg.inner_text("#courses"))
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
       and "Old thing" in pg.inner_text("#courses"))
    pg.close()

    pg = open_tag()
    pg.fill("#newName", "   ")
    pg.click("#addBtn"); pg.wait_for_timeout(150)
    ck("an empty name adds nothing", "show" not in (pg.get_attribute("#savebar", "class") or ""))
    pg.close()

    # Archiving has to pull the dietary off the dishes as well, or the tag
    # survives invisibly and the guest page keeps acting on it.
    pg = open_tag()
    row = pg.locator(".mrow").filter(has_text="Nut allergy")
    row.locator(".mtog").click(); pg.wait_for_timeout(150)
    ck("archiving removes it from the courses", "Nut allergy" not in pg.inner_text("#courses"))
    pg.click("#saveBtn"); pg.wait_for_timeout(400)
    body = json.loads(wrote("/menutags/" + today)[0]["b"])
    ck("and from the tags that get written", "Nut allergy" not in body.get("main", []))
    ck("but the dietary itself is kept, archived, not deleted",
       json.loads(wrote("/dietaries")[0]["b"]).get("Nut allergy", {}).get("active") is False)
    pg.close()

    # ── a menu that is missing, stale, or short a course ──────
    STATE["menu"] = None
    pg = open_tag()
    ck("with no menu at all the page says so",
       "show" in pg.get_attribute("#nomenu", "class"))
    ck("and offers no courses to tag", pg.locator(".course.show").count() == 0)
    ck("but the dietary list is still manageable", "Gluten free" in pg.inner_text("#mng"))
    pg.close()

    STATE["menu"] = dict(FULL_MENU)
    STATE["menu"]["published"] = (now - datetime.timedelta(days=2)).isoformat()
    pg = open_tag()
    ck("yesterday's menu is not offered as tonight's",
       "show" in pg.get_attribute("#nomenu", "class"))
    pg.close()

    # The gate used to be the bread course by name. Chef does not always serve
    # bread, and on those nights the page insisted no menu was published.
    STATE["menu"] = {"published": now.isoformat(),
                     "entree": {"name": "Kingfish crudo"},
                     "main": {"name": "Lamb rump"}, "dessert": {"name": "Pavlova"}}
    pg = open_tag()
    ck("a menu with no bread course is still a published menu",
       "show" not in (pg.get_attribute("#nomenu", "class") or ""))
    ck("and its three courses are all offered", pg.locator(".course.show").count() == 3)
    pg.close()
    STATE["menu"] = FULL_MENU

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
    ck("and they are offered on the dishes", "Vegan" in pg.inner_text("#courses"))
    pg.close()
    STATE["master"] = MASTER

    # ── a save that fails must not look like a save ───────────
    STATE["failSave"] = True
    pg = open_tag()
    ticks(pg).first.click()
    pg.click("#saveBtn"); pg.wait_for_timeout(500)
    ck("a refused save says so", "show" in pg.get_attribute("#err", "class"))
    ck("does not claim to have saved", "SAVED" not in pg.inner_text("#savedMsg").upper())
    ck("leaves the Save button usable", not pg.is_disabled("#saveBtn"))
    ck("and keeps the unsaved work in front of the chef",
       "show" in pg.get_attribute("#savebar", "class"))
    pg.close()
    STATE["failSave"] = False

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
