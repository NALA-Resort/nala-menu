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

# The booking as Mews states it. Villa, name and dates come from here, never
# from the link, because the link is older than the database by definition.
PMS = {"villa": "4", "first": "Robyn", "last": "Williams",
       "phone": "+61400000001", "arrive": "2026-08-17", "depart": "2026-08-21"}

STATE = {"pms": PMS, "pre": None, "dinner": None, "menu": None,
         "dietaries": None, "menutags": None, "fail": False}
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
    if "/dietaries" in u:
        body = json.dumps(STATE["dietaries"]) if STATE["dietaries"] else "null"
    elif "/menutags/" in u:
        body = json.dumps(STATE["menutags"]) if STATE["menutags"] else "null"
    elif "/pms" in u:
        body = json.dumps(STATE["pms"]) if STATE["pms"] else "null"
    elif "/prearrival" in u:
        body = json.dumps(STATE["pre"]) if STATE["pre"] else "null"
    elif "/dinner/" in u:
        body = json.dumps(STATE["dinner"]) if STATE["dinner"] else "null"
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

    # The whole link. A booking id, and a name for the greeting that is never
    # written back.
    # The whole link. A booking id, and a name for the greeting that is never
    # written back.
    LINK = "?b=res-guid-1&n=Robyn&s=Williams"

    def cell(): return "/dinner/" + today + "/4"

    # ── who gets the panel ──────────────────────────────────────
    # A booking, not a phone. The old page needed a phone AND a name in the
    # link, which is what made /responses/<date>/<phone> guessable in order.
    STATE.update({"menu": MENU, "pre": None, "dinner": None})
    del WRITES[:]
    pg = guest("")
    ck("a bare link shows no RSVP panel at all",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')<0"))
    ck("and writes nothing", len(WRITES) == 0)
    ck("but the menu is still readable, which is the page's other job",
       pg.evaluate("()=>{const m=document.getElementById('stateMenu');"
                   "return !!m && m.style.display!=='none';}"))
    pg.close()

    del WRITES[:]
    pg = guest("?n=Robyn&s=Williams")
    ck("a name with no booking is not an identified guest",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')<0"))
    pg.close()

    # ── opening the link writes nothing ─────────────────────────
    # The old page recorded the guest in /roomguests on arrival. Mews does that
    # now, through /stays, and for guests who never open their link at all.
    del WRITES[:]
    pg = guest(LINK)
    ck("opening the link writes nothing anywhere", len(WRITES) == 0)
    ck("the panel is shown for a guest with a booking",
       pg.evaluate("()=>document.getElementById('rsvp').className.indexOf('show')>-1"))
    ck("and the first question is whether they are dining",
       "dining with us" in pg.locator("#rsvp").inner_text())
    pg.close()

    # ── declining ───────────────────────────────────────────────
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bOut").click(); pg.wait_for_timeout(200)
    ck("declining asks for confirmation rather than saving at once",
       len(wrote("/dinner/")) == 0)
    pg.locator("#bBack").click(); pg.wait_for_timeout(200)
    ck("back returns to the question", pg.locator("#bIn").count() == 1)
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(400)
    w = wrote(cell())
    ck("confirming writes the one dinner cell", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("keyed by the villa Mews says they are in, not by their phone",
           cell() in w[0]["u"])
        ck("not dining is zero covers", body["status"] == "out" and body["pax"] == 0)
        ck("stamped as set by the guest, which is what lets staff override it",
           body["by"] == "guest")
        ck("carrying the booking it belongs to", body["bookingId"] == "res-guid-1")
        # The point of the rewrite: this page does not own these facts.
        ck("and none of Mews' facts are copied into it",
           not any(k in body for k in ("name","phone","arrives","departs","first","last")))
    pg.close()

    # ── accepting, with a dietary the menu contains ─────────────
    STATE["dietaries"] = DIETS
    STATE["menutags"] = TAGS
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Nut allergy").first.click(); pg.wait_for_timeout(200)
    pg.locator("#bSave").click(); pg.wait_for_timeout(300)
    ck("a dietary that clashes with tonight's menu blocks the save",
       len(wrote("/dinner/")) == 0)
    ck("and marks the note field as the thing that is missing",
       pg.locator("#dnote.miss").count() == 1)
    pg.fill("#dnote", "severe, no substitutes")
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    w = wrote(cell())
    ck("once the note is given the save goes through", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("and is flagged for the kitchen", body["flag"] is True)
        ck("with the guest's own words kept", body["dnote"] == "severe, no substitutes")
    ck("standing dietaries are kept on the booking for the rest of the stay",
       len(wrote("/bookings/res-guid-1/prearrival")) == 1)
    pg.close()

    # A dietary the menu does not contain must raise nothing: the negative case
    # is where a flag starts crying wolf.
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Gluten free").first.click(); pg.wait_for_timeout(150)
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    w = wrote(cell())
    ck("a dietary tonight's menu does not contain raises no flag",
       len(w) == 1 and json.loads(w[0]["b"])["flag"] is False)
    pg.close()

    # Typed a note for a clash, then removed the dietary. The note goes with it
    # or the kitchen reads an instruction about a dish nobody is avoiding.
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Nut allergy").first.click(); pg.wait_for_timeout(150)
    pg.fill("#dnote", "typed then changed my mind")
    pg.locator(".chip", has_text="Nut allergy").first.click(); pg.wait_for_timeout(150)
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    w = wrote(cell())
    ck("a note typed for a dietary that was then removed is not saved",
       len(w) == 1 and json.loads(w[0]["b"])["dnote"] == "")
    pg.close()

    # ── before the menu is published ────────────────────────────
    STATE["menu"] = None
    del WRITES[:]
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator("#bSave").click(); pg.wait_for_timeout(300)
    ck("with no menu published, confirming needs the acknowledgment first",
       len(wrote("/dinner/")) == 0)
    ack = pg.locator("#ack")
    if ack.count():
        ack.click(); pg.wait_for_timeout(150)
        pg.locator("#bSave").click(); pg.wait_for_timeout(400)
        w = wrote(cell())
        ck("acknowledged, the reply saves", len(w) == 1)
        if w:
            ck("and is marked as made before the menu existed",
               json.loads(w[0]["b"])["premenu"] is True)
        ck("but nothing is claimed as a standing dietary for future nights",
           len(wrote("/bookings/res-guid-1/prearrival")) == 0)
    pg.close()
    STATE["menu"] = MENU

    # ── coming back to an answer already given ──────────────────
    STATE["dinner"] = {"status": "in", "pax": 3, "diets": ["Gluten free"],
                       "by": "guest", "at": "2026-08-17T09:00:00Z"}
    pg = guest(LINK)
    txt = pg.locator("#rsvp").inner_text()
    ck("a guest who already replied is not asked again", "dining with us" not in txt)
    ck("and is offered a way to change their own answer",
       pg.locator("#bEdit").count() == 1)
    pg.close()

    # ── a booking reception made at the desk ────────────────────
    # This is the case the old page could not see at all: it read /responses
    # and never /manual, so a guest opening their link could overwrite a
    # booking staff had made. One cell removes that.
    STATE["dinner"] = {"status": "in", "pax": 2, "by": "staff",
                       "at": "2026-08-17T14:00:00Z"}
    del WRITES[:]
    pg = guest(LINK)
    txt = pg.locator("#rsvp").inner_text()
    ck("a booking staff made is shown to the guest, not hidden",
       "dining with us" not in txt)
    ck("but they are not offered a way to change it",
       pg.locator("#bEdit").count() == 0)
    ck("and nothing they can do writes over it", len(wrote("/dinner/")) == 0)
    # Belt as well as braces. Hiding the link stops the ordinary route; this
    # checks the guard behind it, because a hidden button is not a rule.
    pg.evaluate("()=>{ try { save('in'); } catch(e) {} }")
    pg.wait_for_timeout(400)
    ck("and calling save directly still writes nothing",
       len(wrote("/dinner/")) == 0)
    pg.close()
    STATE["dinner"] = None

    # ── standing dietaries from their own pre-arrival ───────────
    STATE["pre"] = {"diets": ["Gluten free"], "at": "2026-08-15T10:00:00Z"}
    pg = guest(LINK)
    pg.locator("#bIn").click(); pg.wait_for_timeout(400)
    ck("a dietary given at pre-arrival is preselected, not retyped",
       pg.evaluate("()=>[...document.querySelectorAll('#chips .chip')]"
                   ".some(e=>e.textContent.indexOf('Gluten')>-1"
                   "&&e.className.indexOf('on')>-1)"))
    pg.close()
    STATE["pre"] = None

    # ── a write that fails must not look like success ───────────
    STATE["fail"] = True
    pg = guest(LINK)
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(500)
    ck("a rejected write is recorded rather than swallowed",
       pg.evaluate("()=>window.__nalaWriteFailed===true"))
    STATE["fail"] = False
    pg.close()

    # ── the page at Android widths ──────────────────────────────
    for w in (390, 360, 320):
        pg = guest(LINK, w=w)
        bleed = pg.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1")
        ck("the guest page does not scroll sideways at %dpt" % w, not bleed)
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
