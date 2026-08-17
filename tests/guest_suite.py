"""index.html, the guest page. Written 17 Aug.

This page had no suite and it is the only guest facing one. Stage D rewrites it
to take a booking id, so this exists to describe what it does TODAY and give
that rewrite something to fail against. Several behaviours pinned here are
expected to change: where that is true the assertion says so, so a red test
after the rewrite reads as "this changed on purpose" rather than "this broke".

It describes the code, not production. The URL carrying a phone was an earlier
plan and no live link uses it; the code still reads it, so the suite does too.
"""
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8956), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

WRITES = []
READS = []
STATE = {"profile": None, "tonight": None, "fail": False}

MENU = {"published": now.isoformat(),
        "bread": {"name": "Sourdough", "desc": "cultured butter"},
        "entree": {"name": "Prawns", "desc": "chilli, lime"},
        "main": {"name": "Satay Chicken", "desc": "peanut sauce", "tags": ["Nut allergy"]},
        "dessert": {"name": "Pavlova", "desc": "passionfruit"}}
DIETARIES = ["Nut allergy", "Vegetarian", "Gluten free", "Dairy free"]


def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    READS.append(u)
    body = "null"
    if "/dietaries" in u: body = json.dumps(DIETARIES)
    elif "/menutags/" in u: body = json.dumps({"main": ["Nut allergy"]})
    elif "/guests/" in u: body = json.dumps(STATE["profile"]) if STATE["profile"] else "null"
    elif "/responses/" in u:
        # Keyed strictly, so a page that asks for the wrong key gets nothing.
        # A loose mock would answer any path and hide exactly the Stage D
        # mistake this suite exists to catch.
        body = (json.dumps(STATE["tonight"])
                if (STATE["tonight"] and ("/responses/" + today + "/0400000001") in u)
                else "null")
    route.fulfill(status=200, content_type="application/json", body=body)


P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)


from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_page(query="?p=0400000001&n=James%20Fox&r=4", menu=MENU, width=390):
        pg = b.new_page(viewport={"width": width, "height": 844})
        pg.route("**/*.firebasedatabase.app/**", fb)
        if menu is None:
            pg.route("**/menu.json*", lambda r: r.fulfill(status=404, body=""))
        else:
            pg.route("**/menu.json*", lambda r: r.fulfill(
                status=200, content_type="application/json", body=json.dumps(menu)))
        pg.goto("http://localhost:8956/index.html" + query)
        pg.wait_for_timeout(1200)
        return pg

    def last_response_write():
        w = [x for x in WRITES if "/responses/" in x["u"] and x["m"] == "PUT"]
        return json.loads(w[-1]["b"]) if w else None

    # ── who gets the panel at all ───────────────────────────────
    # An unidentified visitor sees the menu and is never asked to reply. This is
    # the only thing stopping a stranger writing a response for a villa.
    WRITES.clear()
    pg = open_page("")
    ck("with no link parameters the reply panel never appears",
       pg.locator("#rsvp").get_attribute("class") != "show")
    ck("and nothing at all is written",
       len([x for x in WRITES if x["m"] in ("PUT", "PATCH")]) == 0)
    ck("but the menu is still readable, which is the page's other job",
       "Satay Chicken" in pg.locator("#stateMenu").inner_text())
    pg.close()

    WRITES.clear()
    pg = open_page("?p=0400000001")
    ck("a phone without a name is not enough",
       pg.locator("#rsvp").get_attribute("class") != "show")
    pg.close()

    WRITES.clear()
    pg = open_page("?n=James%20Fox")
    ck("a name without a phone is not enough",
       pg.locator("#rsvp").get_attribute("class") != "show")
    pg.close()

    # ── opening the link records the guest ──────────────────────
    # CHANGES AT STAGE D: roomguests stops being written from this page at all.
    WRITES.clear()
    STATE["profile"] = None; STATE["tonight"] = None
    pg = open_page()
    ck("an identified guest gets the panel",
       pg.locator("#rsvp").get_attribute("class") == "show")
    rg = [x for x in WRITES if "/roomguests/" in x["u"]]
    ck("STAGE D: opening the link writes roomguests for the villa", len(rg) == 1)
    ck("STAGE D: keyed by date and room number",
       ("/roomguests/" + today + "/4") in rg[0]["u"])
    body = json.loads(rg[0]["b"])
    ck("STAGE D: carrying name and phone from the URL",
       body["name"] == "James Fox" and body["phone"] == "0400000001")

    # ── the first question ──────────────────────────────────────
    ck("a guest who has not replied is asked to choose",
       pg.locator("#bIn").is_visible() and pg.locator("#bOut").is_visible())

    # ── declining ───────────────────────────────────────────────
    pg.locator("#bOut").click(); pg.wait_for_timeout(200)
    ck("declining asks for confirmation rather than saving at once",
       pg.locator("#bYes").is_visible())
    pg.locator("#bYes").click(); pg.wait_for_timeout(400)
    r = last_response_write()
    ck("a decline saves status out", r["status"] == "out")
    ck("with no covers", r["pax"] == 0)
    ck("and no note carried over", r["note"] == "" and r["dnote"] == "")
    pg.close()

    # ── accepting, with a dietary that does not clash ───────────
    WRITES.clear()
    STATE["tonight"] = None
    pg = open_page()
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    ck("accepting opens the details step",
       pg.locator("#paxRow").is_visible() and pg.locator("#chips").is_visible())
    pg.locator(".pax", has_text="2").click()
    pg.locator(".chip", has_text="Vegetarian").click()
    pg.locator("#note").fill("Anniversary")
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    r = last_response_write()
    ck("accepting saves status in", r["status"] == "in")
    ck("with the covers chosen", r["pax"] == 2)
    ck("the dietary selected", r["diets"] == ["Vegetarian"])
    ck("and the guest's note", r["note"] == "Anniversary")
    ck("a dietary the menu does not clash with raises no flag", r["flag"] is False)
    prof = [x for x in WRITES if "/guests/" in x["u"] and x["m"] == "PATCH"]
    ck("STAGE D: the profile is patched with name, room and dates too",
       len(prof) == 1 and json.loads(prof[-1]["b"])["room"] == "4")
    ck("STAGE D: and standing dietaries are kept on it for future nights",
       json.loads(prof[-1]["b"])["diets"] == ["Vegetarian"])
    pg.close()

    # ── a dietary that clashes with tonight's menu ──────────────
    # The chef tags a dish. Confirming with a conflicting dietary and no note
    # would put a guest in front of a dish they cannot eat with nothing said.
    WRITES.clear()
    pg = open_page()
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Nut allergy").click(); pg.wait_for_timeout(200)
    ck("a conflicting dietary warns the guest",
       pg.locator("#cf").is_visible())
    pg.locator("#bSave").click(); pg.wait_for_timeout(300)
    ck("and confirming is refused until they say something",
       last_response_write() is None)
    ck("with the field marked rather than a silent failure",
       "miss" in (pg.locator("#dnote").get_attribute("class") or ""))
    pg.locator("#dnote").fill("Happy with an alternative")
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    r = last_response_write()
    ck("once explained it saves", r is not None and r["status"] == "in")
    ck("and is flagged for the kitchen", r["flag"] is True)
    ck("carrying what the guest said", r["dnote"] == "Happy with an alternative")
    pg.close()

    # ── untoggling the clash clears the note ───────────────────
    WRITES.clear()
    pg = open_page()
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator(".chip", has_text="Nut allergy").click(); pg.wait_for_timeout(150)
    pg.locator("#dnote").fill("typed then changed my mind")
    pg.locator(".chip", has_text="Nut allergy").click(); pg.wait_for_timeout(150)
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    r = last_response_write()
    ck("a note typed for a dietary that was then removed is not saved",
       r["dnote"] == "" and r["flag"] is False)
    pg.close()

    # ── before the menu is published ───────────────────────────
    # A guest can still confirm, but must acknowledge that they are doing it
    # without seeing the menu, and their dietaries are not claimed for tonight.
    WRITES.clear()
    pg = open_page(menu=None)
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    pg.locator("#bSave").click(); pg.wait_for_timeout(300)
    ck("before the menu is out, confirming needs an acknowledgment",
       last_response_write() is None)
    pg.locator("#ack").click(); pg.wait_for_timeout(150)
    pg.locator("#bSave").click(); pg.wait_for_timeout(400)
    r = last_response_write()
    ck("acknowledged, it saves", r is not None and r["status"] == "in")
    ck("marked as a pre-menu confirmation", r["premenu"] is True)
    ck("and no dietaries are claimed for tonight", r["diets"] == [])
    pg.close()

    # ── coming back to a reply already made ────────────────────
    WRITES.clear(); READS.clear()
    STATE["tonight"] = {"status": "in", "pax": 3, "diets": ["Gluten free"],
                        "note": "Window table", "at": now.isoformat()}
    pg = open_page()
    txt = pg.locator("#rsvp").inner_text()
    ck("a guest who already replied is not asked again",
       pg.locator("#bIn").count() == 0)
    ck("they are shown what they confirmed", "Confirmed for 3 guests" in txt)
    ck("and offered a way to change it before the cutoff",
       pg.locator("#bEdit").is_visible() if now.hour < 12 else
       pg.locator("#bEdit").count() == 0)
    # STAGE D: this read is keyed by phone. The handover twice says the key is
    # only written and never read. It is read here, and re-keying to the booking
    # id breaks the returning guest unless this changes with it.
    ck("STAGE D: tonight's answer is fetched by phone, not by booking",
       any(("/responses/" + today + "/0400000001") in u for u in READS))
    pg.close()

    # ── the standing profile fills the gaps ────────────────────
    WRITES.clear()
    STATE["tonight"] = None
    STATE["profile"] = {"diets": ["Dairy free"], "room": "9"}
    pg = open_page()
    pg.locator("#bIn").click(); pg.wait_for_timeout(300)
    on = pg.evaluate("()=>[...document.querySelectorAll('.chip.on')].map(c=>c.textContent.trim())")
    ck("standing dietaries from the profile are pre-selected",
       "Dairy free" in on)
    pg.close()
    STATE["profile"] = None

    # ── a save that fails ──────────────────────────────────────
    WRITES.clear()
    STATE["fail"] = True
    pg = open_page()
    pg.locator("#bOut").click(); pg.wait_for_timeout(200)
    pg.locator("#bYes").click(); pg.wait_for_timeout(500)
    ck("a rejected write still leaves the page usable rather than blank",
       pg.locator("#rsvp").get_attribute("class") == "show")
    pg.close()
    STATE["fail"] = False

    # ── width ──────────────────────────────────────────────────
    # Mock at 390, check at 360, do not break at 320.
    for w in (390, 360, 320):
        pg = open_page(width=w)
        bleed = pg.evaluate(
            "()=>document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
        ck("the guest page does not bleed sideways at %dpt" % w, not bleed)
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
