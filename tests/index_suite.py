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
import errortrap   # fails the run if any page throws
# This suite refuses a write on purpose, to prove the guest is told. The page
# is supposed to complain about it.
errortrap.expect("failed: 401")
import threading, http.server, socketserver, json, time, datetime, os, re

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8962), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

# The booking as Mews states it. Villa, name and dates come from here, never
# from the link, because the link is older than the database by definition.
PMS = {"villa": "4", "first": "Robyn", "last": "Williams",
       "phone": "+61400000001", "arrive": "2026-08-17", "depart": "2026-08-21"}

STATE = {"pms": PMS, "pre": None, "dinner": None, "menu": None,
         "dietaries": None, "menutags": None, "fail": False, "dbmenu": None}
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
    elif u.split("?")[0].endswith("/menu.json"):
        #  The DATABASE menu, which is a different thing from the committed
        #  file the page falls back to. One route used to answer both and the
        #  page's whole fallback path went untested because of it.
        body = json.dumps(STATE["dbmenu"]) if STATE["dbmenu"] is not None else "null"
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
        pg.route("**firebasedatabase.app/**", fb)
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

    # ── opening the link records the look and nothing else ──────
    # The old page recorded the guest in /roomguests on arrival. Mews does that
    # now, through /stays, and for guests who never open their link at all, so
    # that write went. It took with it the only evidence anybody had LOOKED,
    # which is the fact reception acts on, and for two days the boards drew a
    # distinction nothing was feeding. One write is right here, and it is a
    # mark against tonight, not a guest record coming back.
    del WRITES[:]
    pg = guest(LINK)
    pg.wait_for_timeout(400)
    marks = [w for w in WRITES if "/opened/" in w["u"]]
    ck("opening the link marks the night as looked at",
       len(marks) == 1 and marks[0]["m"] == "PUT")
    ck("and files it against the villa Mews gives, not the link",
       len(marks) == 1 and "/opened/%s/4.json" % today in marks[0]["u"])
    ck("and carries the booking so the mark can be traced",
       len(marks) == 1 and json.loads(marks[0]["b"]).get("bookingId") == "res-guid-1")
    ck("and writes nothing else at all", len(WRITES) == len(marks))
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
    # The Change link is hidden after the noon cutoff, so this depends on the
    # clock. Pinned to before noon rather than left to fail every afternoon.
    ck("and is offered a way to change their own answer, before the cutoff",
       pg.evaluate("()=>{ const was = Date.prototype.getHours;"
                   "Date.prototype.getHours = function(){ return 9; };"
                   "try { stepDone({status:'in', pax:3, by:'guest'});"
                   "return !!document.getElementById('bEdit'); }"
                   "finally { Date.prototype.getHours = was; } }"))
    ck("and not offered it after the cutoff",
       pg.evaluate("()=>{ const was = Date.prototype.getHours;"
                   "Date.prototype.getHours = function(){ return 14; };"
                   "try { stepDone({status:'in', pax:3, by:'guest'});"
                   "return !document.getElementById('bEdit'); }"
                   "finally { Date.prototype.getHours = was; } }"))
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
    #  This check existed from the start and asserted the internal flag only.
    #  The flag was set correctly the whole time and nothing looked at it: the
    #  page called stepDone on the line after the write, so five days of
    #  refused writes read to guests as confirmations. A test that watches a
    #  variable instead of the screen passes while the bug ships.
    STATE["fail"] = True
    pg = guest(LINK)
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(700)
    ck("a rejected write is recorded rather than swallowed",
       pg.evaluate("()=>window.__nalaWriteFailed===true"))
    seen = pg.inner_text("#rsvp").lower()
    ck("and the guest is told it did not save",
       "not saved" in seen)
    ck("and is NOT thanked for a booking that does not exist",
       "look forward" not in seen and "confirmed for" not in seen)
    ck("and is pointed at the one thing that can fix it",
       "reception" in seen)
    ck("and can try again",
       pg.locator("#bEdit").count() == 1)
    STATE["fail"] = False
    pg.close()

    # ── a booking with no villa ─────────────────────────────────
    #  The dinner cell is filed by villa. From 17 Aug, when the link stopped
    #  carrying the villa, it came only from /bookings/<id>/pms, and a booking
    #  Mews had not assigned a room to left it empty. The path built then was
    #  /dinner/<date>/ with nothing on the end, which is the date node holding
    #  every villa's answer for the night. The database refused it, which is
    #  the only reason this was a lost booking rather than a wiped service.
    #
    #  There is no second place to look: /stays needs a login and this page is
    #  the one page with no login. So it is refused and said out loud. A cell
    #  filed under a guessed villa would lay a table and cook for it.
    STATE["pms"] = {k: v for k, v in PMS.items() if k != "villa"}
    pg = guest(LINK)
    del WRITES[:]
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(700)
    ck("a booking with no villa writes no dinner cell at all",
       len([w for w in WRITES if "/dinner/" in w["u"]]) == 0)
    ck("and never builds a path at the date node",
       not any(re.search(r"/dinner/\d{4}-\d{2}-\d{2}/?\.json", w["u"]) for w in WRITES))
    seen = pg.inner_text("#rsvp").lower()
    ck("the guest is told, in terms of what went wrong",
       "not saved" in seen and "villa" in seen)
    ck("and not thanked",
       "look forward" not in seen and "confirmed for" not in seen)
    #  Dietaries are written after the cell lands, not beside it. Recording
    #  requirements against a dinner nobody knows about is how a kitchen ends
    #  up with an allergy note and no cover.
    ck("and no dietaries are filed against a dinner that was refused",
       len([w for w in WRITES if "prearrival" in w["u"]]) == 0)
    STATE["pms"] = PMS
    pg.close()

    # ── the villa from the link ─────────────────────────────────
    #  22 Aug: the invite links went out with the booking id unmerged, as the
    #  literal text {{bookingId}}. /bookings/{{bookingId}}/pms returned nothing,
    #  the villa was blank, every confirmation was refused, and every guest was
    #  thanked. `r` is the villa carried in the link so the night survives that.
    #  A fallback and nothing more: Mews is written once per change and a link
    #  is written once, ever.
    STATE["pms"] = None
    pg = guest(LINK + "&r=12")
    del WRITES[:]
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(700)
    dw = [w for w in WRITES if "/dinner/" in w["u"]]
    ck("a booking that does not resolve still files against the link's villa",
       len(dw) == 1 and "/12.json" in dw[0]["u"])
    seen = pg.inner_text("#rsvp").lower()
    ck("and the answer is taken, not refused",
       "not saved" not in seen and "noted" in seen)
    #  The id was junk in exactly this case, so anything filed against the
    #  BOOKING has nowhere real to go. A dietary written to a node named after
    #  the placeholder looks recorded and is not, which is worse than not
    #  writing it. The villa fallback makes this reachable, so it is guarded.
    ck("but nothing is filed against a booking id that resolved to nothing",
       len([w for w in WRITES if "prearrival" in w["u"]]) == 0)
    pg.close()

    #  Mews outranks the link. A villa is current in one and frozen in the
    #  other, so the link is read only when Mews has said nothing.
    STATE["pms"] = PMS          # villa 4
    pg = guest(LINK + "&r=12")
    del WRITES[:]
    pg.locator("#bOut").click(); pg.wait_for_timeout(150)
    pg.locator("#bYes").click(); pg.wait_for_timeout(700)
    dw = [w for w in WRITES if "/dinner/" in w["u"]]
    ck("Mews wins over the link when both name a villa",
       len(dw) == 1 and "/4.json" in dw[0]["u"])
    pg.close()

    #  The cell is keyed on the villa number. "Room 12" is not a villa number,
    #  and cleaning it up would be guessing at the one value that decides which
    #  table gets laid.
    for bad in ("Room%2012", "Villa%2012", "abc", "1234"):
        STATE["pms"] = None
        pg = guest(LINK + "&r=" + bad)
        del WRITES[:]
        pg.locator("#bOut").click(); pg.wait_for_timeout(150)
        pg.locator("#bYes").click(); pg.wait_for_timeout(600)
        ck("a villa of '" + bad + "' in the link is treated as absent",
           len([w for w in WRITES if "/dinner/" in w["u"]]) == 0)
        pg.close()
    STATE["pms"] = PMS

    # ── a menu taken down ───────────────────────────────────────
    #  Reported 22 Aug: the chef pressed Remove and the menu stayed on the
    #  guests' phones. The takedown had worked. Blanking the database node made
    #  it look like silence, the page fell back to the committed file, and the
    #  file still held the menu published through GitHub earlier that day.
    #
    #  Three answers, not two. A node with a menu is a menu. A node that could
    #  not be read, or has never held anything, is silence, and the file stands
    #  in behind it so a guest is never shown a placeholder while the chef
    #  swears the menu is up. A node that exists and has been deliberately
    #  emptied is the resort saying there is no dinner, and it has to win.
    STATE["menu"] = MENU          # the file still holds tonight's
    STATE["dbmenu"] = {"published": "",
                       "bread": {"name": "", "desc": "", "aus": False},
                       "entree": {"name": "", "desc": "", "aus": False},
                       "main": {"name": "", "desc": "", "aus": False},
                       "dessert": {"name": "", "desc": "", "aus": False}}
    pg = guest(LINK)
    pg.wait_for_timeout(900)
    seen = pg.inner_text("body")
    ck("a menu taken down does not come back from the committed file",
       MENU["main"]["name"] not in seen)
    pg.close()

    #  And the fallback still does its job where it was always meant to: a
    #  database that has never held a menu is silence, not a takedown.
    STATE["dbmenu"] = None
    pg = guest(LINK)
    pg.wait_for_timeout(900)
    ck("a database with no menu at all still falls back to the file",
       MENU["main"]["name"] in pg.inner_text("body"))
    pg.close()

    #  A published menu in the database beats the file, which is the ordinary
    #  case since publishing moved off GitHub.
    STATE["dbmenu"] = dict(MENU); STATE["dbmenu"]["main"] = {"name": "Database lamb"}
    pg = guest(LINK)
    pg.wait_for_timeout(900)
    ck("and a menu in the database wins over the file",
       "Database lamb" in pg.inner_text("body"))
    pg.close()
    STATE["dbmenu"] = None

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
