"""index.html, the guest page.

Written 17 Aug, BEFORE the stage 4 rewrite, deliberately. It describes what the
page does today rather than what it should do, so that the rewrite has
something to fail against. Several behaviours pinned here are ones stage 4
intends to change: the URL carrying guest data, the response keyed on phone,
the write to /roomguests. When those tests fail, check the change was meant.

Two of them exist to contradict the handover, which says the responses key is
written and never read. It is read, at index.html:846, and this suite proves
it.

No Firebase SDK on this page and no sign in: db() is a plain fetch, so the
harness only has to intercept the database host.
"""
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8962), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

STATE = {"guests": {}, "responses": {}, "menu": None, "dietaries": None,
         "menutags": None, "fail": False}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/menu" in u and "menutags" not in u:
        body = json.dumps(STATE["menu"]) if STATE["menu"] else "null"
    elif "/dietaries" in u:
        body = json.dumps(STATE["dietaries"]) if STATE["dietaries"] else "null"
    elif "/menutags/" in u:
        body = json.dumps(STATE["menutags"]) if STATE["menutags"] else "null"
    elif "/guests/" in u:
        key = u.split("/guests/")[1].split(".json")[0]
        body = json.dumps(STATE["guests"].get(key)) if key in STATE["guests"] else "null"
    elif "/responses/" in u:
        key = u.split("/responses/")[1].split(".json")[0]
        body = json.dumps(STATE["responses"].get(key)) if key in STATE["responses"] else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def wrote(fragment):
    return [w for w in WRITES if fragment in w["u"]]

MENU = {"published": now.isoformat(),
        "bread": {"name": "Sourdough"}, "entree": {"name": "Prawns"},
        "main": {"name": "Satay Chicken"}, "dessert": {"name": "Pavlova"}}

# The chef's master list of dietaries, as tag.html writes it: keyed records
# with active, name and group. Inactive ones never reach the guest.
DIETS = {"nut":    {"name": "Nut allergy",  "group": "common", "active": True},
         "gluten": {"name": "Gluten free",  "group": "common", "active": True},
         "retired":{"name": "Old Entry",    "group": "common", "active": False}}
# Tonight's dish tags, written per day, NOT stored on the dish itself.
TAGS = {"main": ["Nut allergy"]}

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def menu_route(route, request):
        """menu.json is a committed FILE, not database state: the chef
        publishes by pushing a commit. The suite must control it or the page
        reads whatever the chef last published."""
        if STATE["menu"] is None:
            route.fulfill(status=404, content_type="application/json", body="")
        else:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(STATE["menu"]))

    def guest(query, w=390):
        """Open the guest page with a given link, at phone width."""
        pg = b.new_page(viewport={"width": w, "height": 844})
        pg.route("**/menu.json*", menu_route)
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.goto("http://localhost:8962/index.html" + query)
        pg.wait_for_timeout(900)
        return pg

    LINK = "?p=0400000001&n=James%20Fisher&r=4&a=" + today + "&d=" + today

    # ── the RSVP panel only appears for an identified guest ──────
    # initRSVP returns early without both a phone and a name. Stage 4 replaces
    # this test entirely: the link will carry a booking id instead.
    STATE.update({"menu": MENU, "guests": {}, "responses": {}})
    del WRITES[:]
    pg = guest("")
    ck("a bare link shows no RSVP panel at all",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')<0"))
    ck("and writes nothing", len(WRITES) == 0)
    pg.close()

    del WRITES[:]
    pg = guest("?p=0400000001")
    ck("a phone with no name is still not an identified guest",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')<0"))
    pg.close()

    del WRITES[:]
    pg = guest("?n=James%20Fisher")
    ck("and a name with no phone is not either",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')<0"))
    pg.close()

    # ── opening the link records who is in the villa ─────────────
    # Stage 4 removes this write. index.html is one of TWO writers of
    # /roomguests; welcome.html is the other.
    del WRITES[:]
    pg = guest(LINK)
    rg = wrote("/roomguests/" + today + "/4")
    ck("opening the link records the guest in their villa", len(rg) == 1)
    if rg:
        body = json.loads(rg[0]["b"])
        ck("with the name, phone and dates the URL supplied",
           body["name"] == "James Fisher" and body["phone"] == "0400000001"
           and body["departs"] == today)
        ck("and a timestamp, so a later opener wins", "at" in body)
    ck("the panel is shown for an identified guest",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')>-1"))
    ck("and the first question is whether they are dining",
       "dining with us" in pg.locator("#rsvp").inner_text())
    pg.close()

    # a link with no villa is an external booking: nothing to record
    del WRITES[:]
    pg = guest("?p=0400000009&n=Outside%20Guest")
    ck("a link with no villa records no villa",
       len(wrote("/roomguests/")) == 0)
    pg.close()

    # ── the responses key IS read, contradicting the handover ────
    # HANDOVER-MEWS.md says twice that this key is written and never read.
    # It is read here, to restore what the guest already answered tonight.
    STATE["responses"] = {today + "/0400000001": {
        "status": "in", "pax": 3, "diets": ["Nut allergy"],
        "note": "window table", "dnote": "no sauce",
        "at": "2026-08-17T09:00:00Z"}}
    del WRITES[:]
    pg = guest(LINK)
    txt = pg.locator("#rsvp").inner_text()
    ck("a guest who already replied sees their answer, not a fresh question",
       "dining with us" not in txt)
    ck("which means the responses key is read, not only written",
       "window table" in txt or "Edit" in txt or "change" in txt.lower())
    pg.close()

    # ── the standing profile fills what the link leaves out ──────
    # The stored profile backfills what the link left out. This is the second
    # source of guest facts that stage 4 removes: /guests holds standing
    # dietaries only after it, not a name, villa or dates.
    STATE["responses"] = {}
    STATE["guests"] = {"0400000002": {"name": "Ann Brown", "room": "7",
                                      "arrives": today, "departs": today,
                                      "diets": ["Gluten free"]}}
    del WRITES[:]
    pg = guest("?p=0400000002&n=Ann%20Brown")
    ck("a link with no villa writes no villa record, even when the profile has one",
       len(wrote("/roomguests/")) == 0)
    pg.locator("#bIn").click(); pg.wait_for_timeout(400)
    ck("the standing dietary from the profile is preselected",
       pg.evaluate("()=>{const c=[...document.querySelectorAll('#chips .chip')]"
                   ".find(e=>e.textContent.indexOf('Gluten')>-1);"
                   "return !!c && c.className.indexOf('on')>-1;}"))
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    w = wrote("/responses/" + today + "/0400000002")
    ck("and is saved with the reply without the guest retyping it",
       len(w) == 1 and "Gluten free" in json.loads(w[0]["b"])["diets"])
    if w:
        body = json.loads(w[0]["b"])
        ck("the villa the profile supplied reaches the response too",
           body["room"] == "7")
    pg.close()

    # ── declining ───────────────────────────────────────────────
    STATE["guests"] = {}
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bOut").click(); pg.wait_for_timeout(200)
    ck("declining asks for confirmation rather than saving at once",
       len(wrote("/responses/")) == 0)
    ck("and offers a way back", pg.locator("#bBack").count() == 1)
    pg.locator("#bBack").click(); pg.wait_for_timeout(200)
    ck("back returns to the question", pg.locator("#bIn").count() == 1)
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(400)
    w = wrote("/responses/" + today + "/0400000001")
    ck("confirming writes the response", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("not dining is zero covers", body["status"] == "out" and body["pax"] == 0)
        ck("and carries no note or dietary note", body["note"] == "" and body["dnote"] == "")
        # The identity and date fields stage 4 removes. Named so the rewrite
        # has to notice them going.
        ck("the payload copies the URL's identity and dates, which stage 4 removes",
           body["name"] == "James Fisher" and body["room"] == "4"
           and body["phone"] == "0400000001" and body["departs"] == today)
    ck("and the profile is updated alongside it",
       len(wrote("/guests/0400000001")) == 1)
    pg.close()

    # ── accepting, with a dietary that clashes with the menu ─────
    STATE["dietaries"] = DIETS
    STATE["menutags"] = TAGS
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    chip = pg.locator(".chip", has_text="Nut allergy")
    if chip.count():
        chip.first.click(); pg.wait_for_timeout(200)
        pg.locator("#bSave").click(); pg.wait_for_timeout(300)
        ck("a dietary that clashes with tonight's menu blocks the save",
           len(wrote("/responses/")) == 0)
        ck("and marks the note field as the thing that is missing",
           pg.locator("#dnote.miss").count() == 1)
        pg.fill("#dnote", "severe, no substitutes")
        pg.locator("#bSave").click(); pg.wait_for_timeout(400)
        w = wrote("/responses/" + today + "/0400000001")
        ck("once the note is given the save goes through", len(w) == 1)
        if w:
            body = json.loads(w[0]["b"])
            ck("and the response is flagged for the kitchen", body["flag"] is True)
            ck("with the guest's own words kept",
               body["dnote"] == "severe, no substitutes")
    else:
        ck("dietary chips render for an accepting guest", False)
    pg.close()

    # ── before the menu is published ─────────────────────────────
    # A guest can still reply, but must acknowledge that they are confirming
    # without having seen the menu.
    STATE["menu"] = None
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator("#bSave").click(); pg.wait_for_timeout(300)
    ck("with no menu published, confirming needs the acknowledgment first",
       len(wrote("/responses/")) == 0)
    ack = pg.locator("#ack")
    if ack.count():
        ack.click(); pg.wait_for_timeout(150)
        pg.locator("#bSave").click(); pg.wait_for_timeout(400)
        w = wrote("/responses/" + today + "/0400000001")
        ck("acknowledged, the reply saves", len(w) == 1)
        if w:
            body = json.loads(w[0]["b"])
            ck("and is marked as made before the menu existed",
               body["premenu"] is True)
    pg.close()

    # ── a write that fails must not look like success ────────────
    STATE["menu"] = MENU
    STATE["fail"] = True
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(500)
    ck("a rejected write is recorded rather than swallowed",
       pg.evaluate("()=>window.__nalaWriteFailed===true"))
    STATE["fail"] = False
    pg.close()


    # ── ported from a second suite for this page ────────────────
    # Two suites for index.html existed for one night, from a stopped
    # generation. These four cases were only in the other one. The rest
    # overlapped, so the other suite was removed and these came across.

    # A dietary the menu does NOT contain must raise nothing. The positive
    # case is easy to get right and the negative is where a flag starts
    # crying wolf.
    STATE.update({"menu": MENU, "dietaries": DIETS, "menutags": TAGS,
                  "guests": {}, "responses": {}})
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    chip = pg.locator(".chip", has_text="Gluten free")
    if chip.count():
        chip.first.click(); pg.wait_for_timeout(150)
        pg.locator("#bSave").click(); pg.wait_for_timeout(400)
        w = wrote("/responses/" + today + "/0400000001")
        ck("a dietary tonight's menu does not contain raises no flag",
           len(w) == 1 and json.loads(w[0]["b"])["flag"] is False)
    else:
        ck("a non clashing dietary chip renders", False)
    pg.close()

    # Typed a note for a clash, then removed the dietary. The note has to go
    # with it or the kitchen reads an instruction about a dish nobody is
    # avoiding.
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Nut allergy").first.click(); pg.wait_for_timeout(150)
    pg.fill("#dnote", "typed then changed my mind")
    pg.locator(".chip", has_text="Nut allergy").first.click(); pg.wait_for_timeout(150)
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    w = wrote("/responses/" + today + "/0400000001")
    ck("a note typed for a dietary that was then removed is not saved",
       len(w) == 1 and json.loads(w[0]["b"])["dnote"] == "")
    pg.close()

    # The page has two jobs. A visitor with no link still gets the menu.
    STATE["responses"] = {}
    pg = guest("")
    ck("with no link the menu is still readable, which is the page's other job",
       pg.evaluate("()=>{const m=document.getElementById('stateMenu');"
                   "return !!m && m.style.display!=='none';}"))
    pg.close()

    # A guest who replied can still change it, until the cutoff.
    STATE["responses"] = {today + "/0400000001": {
        "status": "in", "pax": 3, "diets": ["Gluten free"],
        "note": "window table", "at": "2026-08-17T09:00:00Z"}}
    pg = guest(LINK)
    ck("a guest who already replied is offered a way to change it",
       pg.locator("#bEdit").count() == 1)
    pg.close()
    STATE["responses"] = {}

    # ── the page at Android widths ───────────────────────────────
    # New standard as of 17 Aug: mock at 390, check at 360, do not break at 320.
    for w in (390, 360, 320):
        pg = guest(LINK, w=w)
        bleed = pg.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1")
        ck("the guest page does not scroll sideways at %dpt" % w, not bleed)
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
