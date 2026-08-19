"""prearrival.html, the guest's pre-arrival form.

Guest tier, no sign in, reached only from a link. The things most worth pinning
down are the ones that are easy to get wrong and invisible when they are:

  1. Nothing is written until Send, except the opened stamp. A half filled
     record would make "form done" mean "some fields exist".
  2. The opened stamp IS written on landing, because without it a message that
     never arrived looks the same as one that arrived and was ignored.
  3. The link's name and dates are shown and NEVER written back. They are Mews'
     facts, and a copy taken here would be stale the moment Mews changed them.
  4. Send is a PATCH. Reception may already have confirmed this booking, and a
     PUT would wipe confirmedAt and un-confirm a guest at the desk.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8967), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")

# The chef's master list. An inactive entry must never reach a guest.
DIETS = {"gf":  {"name": "Gluten free", "active": True},
         "nut": {"name": "Nut allergy", "active": True},
         "old": {"name": "Retired Entry", "active": False}}

STATE = {"pms": None, "pre": None, "fail": False}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH"):
        WRITES.append({"m": m, "u": u, "b": json.loads(request.post_data or "null")})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/dietaries" in u: body = json.dumps(DIETS)
    elif "/prearrival" in u: body = json.dumps(STATE["pre"]) if STATE["pre"] else "null"
    elif "/pms" in u: body = json.dumps(STATE["pms"]) if STATE["pms"] else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

def wrote(frag):
    return [w for w in WRITES if frag in w["u"]]

LINK = ("?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0) + "&d=" + plus(4))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def guest(link=LINK, w=390):
        pg = b.new_page(viewport={"width": w, "height": 844})
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8967/prearrival.html" + link)
        pg.wait_for_timeout(900)
        return pg

    # ── landing ─────────────────────────────────────────────────
    del WRITES[:]
    pg = guest()
    ck("the guest is greeted by name from the link",
       "Robyn" in pg.locator("#greet").inner_text())
    ck("and told how long they are staying",
       "4 nights" in pg.locator("#sub").inner_text())

    opened = wrote("/bookings/res-guid-1/prearrival")
    ck("landing stamps that the link was opened", len(opened) == 1)
    if opened:
        ck("and stamps nothing else, because nothing has been answered",
           list(opened[0]["b"].keys()) == ["openedAt"])
        ck("as a PATCH, so it cannot wipe an existing record",
           opened[0]["m"] == "PATCH")
    ck("the form is shown, not a thank you",
       pg.evaluate("()=>form.className") == "")

    # The chef's master list, not a list this page invented.
    ck("dietary choices come from the chef's list",
       "Gluten free" in pg.locator("#dietChips").inner_text())
    ck("and a retired entry never reaches a guest",
       "Retired" not in pg.locator("#dietChips").inner_text())

    # ── nothing is written while filling in ─────────────────────
    del WRITES[:]
    pg.locator("#dIn").click(); pg.wait_for_timeout(150)
    pg.evaluate("()=>[...document.querySelectorAll('#dietChips .chip')][0].click()")
    pg.locator("#occasion").fill("anniversary")
    pg.wait_for_timeout(300)
    ck("answering writes nothing at all until Send", len(WRITES) == 0)

    # ── mandatory fields, one at a time ─────────────────────────
    pg = guest()
    del WRITES[:]
    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("sending an empty form saves nothing", len(wrote("/prearrival")) == 0)
    ck("and names the first thing missing rather than marking six at once",
       pg.evaluate("()=>document.querySelectorAll('.q.miss').length") == 1)
    ck("starting with the arrival time",
       pg.evaluate("()=>qEta.className.indexOf('miss')>-1"))
    ck("saying so in words", "when you expect to arrive" in pg.locator("#err").inner_text())

    # an open ended slot has to carry a note
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')].find(b=>b.textContent.indexOf('After')>-1).click()")
    pg.wait_for_timeout(200)
    ck("choosing After 5pm asks for a rough time",
       pg.evaluate("()=>etaNote.style.display!=='none'"))
    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("and will not send without one",
       len(wrote("/prearrival")) == 0 and "rough time" in pg.locator("#err").inner_text())
    pg.fill("#etaNote", "flight gets in at 6")
    # a fixed slot does not
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')].find(b=>b.textContent.indexOf('4pm')>-1).click()")
    pg.wait_for_timeout(200)
    ck("a fixed slot needs no note", pg.evaluate("()=>etaNote.style.display==='none'"))

    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("then the first night", pg.evaluate("()=>qDine.className.indexOf('miss')>-1"))
    pg.locator("#dIn").click(); pg.wait_for_timeout(150)
    ck("saying yes asks how many", pg.evaluate("()=>paxWrap.style.display!=='none'"))

    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("then allergies", pg.evaluate("()=>qDiet.className.indexOf('miss')>-1"))
    # "none to declare" is a positive answer and satisfies it
    pg.evaluate("()=>[...document.querySelectorAll('#dietNone .chip')][0].click()")
    pg.wait_for_timeout(150)
    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("no allergies to declare counts as answering",
       pg.evaluate("()=>qDiet.className.indexOf('miss')<0"))
    ck("then what brings them", pg.evaluate("()=>qPurpose.className.indexOf('miss')>-1"))
    pg.evaluate("()=>[...document.querySelectorAll('#purposeChips .chip')][2].click()")

    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("then how they plan to eat", pg.evaluate("()=>qApproach.className.indexOf('miss')>-1"))
    pg.evaluate("()=>[...document.querySelectorAll('#approachOpts .opt')][0].click()")

    pg.locator("#send").click(); pg.wait_for_timeout(300)
    ck("then treatments", pg.evaluate("()=>qWell.className.indexOf('miss')>-1"))
    pg.locator("#wYes").click(); pg.wait_for_timeout(200)
    ck("saying yes offers only the days they are here",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 5)
    pg.evaluate("()=>[...document.querySelectorAll('#wDays .chip')][1].click()")
    pg.fill("#wTime", "late morning")

    # the two optional ones are genuinely optional
    del WRITES[:]
    pg.locator("#send").click(); pg.wait_for_timeout(500)
    w = wrote("/bookings/res-guid-1/prearrival")
    ck("with the six answered, it sends without the optional two", len(w) == 1)
    if w:
        body = w[0]["b"]
        ck("as a PATCH, so a confirmation already made at the desk survives",
           w[0]["m"] == "PATCH")
        ck("the arrival slot goes as a key, not as typed words",
           body["arriveSlot"] == "16")
        ck("the note from the rejected slot does not tag along",
           body["arriveNote"] == "flight gets in at 6")
        ck("dining and covers", body["dining"] is True and body["pax"] == 2)
        ck("no allergies is recorded as an answer, not an empty list",
           body["noDiets"] is True and body["diets"] == [])
        ck("purpose and approach", body["purpose"] and body["approach"] == "most")
        ck("the treatment day and time", body["wellDay"] and body["wellTime"] == "late morning")
        ck("and a timestamp for when the answers first existed", bool(body["at"]))
        # The whole point of DESIGN.md: identity and dates are Mews'.
        for f in ("name", "first", "last", "villa", "room", "arrive", "depart",
                  "arrives", "departs", "phone"):
            if f in body:
                ck("the guest page must never write " + f, False)
        ck("nothing about who they are or when they stay is written back",
           not any(f in body for f in
                   ("name","first","last","villa","room","arrive","depart","phone")))
    ck("and they are thanked", pg.evaluate("()=>done.className.indexOf('hide')<0"))
    pg.close()

    # ── coming back to it ───────────────────────────────────────
    STATE["pre"] = {"at": "2026-08-16T10:00:00Z", "arriveSlot": "15",
                    "dining": False, "noDiets": True, "purpose": ["A short break"],
                    "approach": "mix", "wellness": False, "occasion": "anniversary"}
    pg = guest()
    ck("a guest who already sent it sees the thank you, not a blank form",
       pg.evaluate("()=>done.className.indexOf('hide')<0"))
    pg.locator("#again").click(); pg.wait_for_timeout(300)
    ck("and can reopen it, because plans change",
       pg.evaluate("()=>form.className") == "")
    ck("with their answers still there",
       pg.evaluate("()=>occasion.value") == "anniversary" and
       pg.evaluate("()=>dOut.className.indexOf('on')>-1"))
    pg.close()
    STATE["pre"] = None

    # ── Mews is fresher than the link ───────────────────────────
    STATE["pms"] = {"first": "Roberta", "arrive": plus(0), "depart": plus(2)}
    pg = guest()
    pg.wait_for_timeout(600)
    ck("when Mews has the booking, its name wins over the link's",
       "Roberta" in pg.locator("#greet").inner_text())
    pg.close()
    STATE["pms"] = None

    # ── a link with no booking id ───────────────────────────────
    del WRITES[:]
    pg = guest("?n=Robyn")
    ck("a link with no booking id shows a message rather than a broken form",
       pg.evaluate("()=>form.className") == "hide" and
       "incomplete" in pg.locator("#doneT").inner_text())
    ck("and writes nothing anywhere", len(WRITES) == 0)
    pg.close()

    # ── a failed send must not look like success ────────────────
    STATE["fail"] = True
    pg = guest()
    pg.evaluate("""()=>{
      [...document.querySelectorAll('#etaOpts .opt')][3].click();
      dIn.click();
      [...document.querySelectorAll('#dietNone .chip')][0].click();
      [...document.querySelectorAll('#purposeChips .chip')][0].click();
      [...document.querySelectorAll('#approachOpts .opt')][1].click();
      wNo.click();
    }""")
    pg.wait_for_timeout(200)
    pg.locator("#send").click(); pg.wait_for_timeout(600)
    ck("a rejected send says so rather than thanking them",
       pg.evaluate("()=>done.className.indexOf('hide')>-1") and
       "did not send" in pg.locator("#err").inner_text())
    ck("and lets them try again",
       pg.evaluate("()=>send.disabled === false"))
    STATE["fail"] = False
    pg.close()

    # ── the dining description ──────────────────────────────────
    # Placeholder copy, but the shape is not a placeholder: the guest is asked
    # to commit to dinner on a night whose menu does not exist yet, so the
    # explanation has to be read BEFORE the two buttons, not under them.
    pg = guest()
    intro = pg.locator("#dineHelp")
    ck("the dining description is on the page", intro.is_visible())
    ck("it states the seating time, which is the one thing a guest plans around",
       "6:00" in intro.inner_text() and "6:30" in intro.inner_text())
    ck("it explains why there is no menu to show yet",
       "not exist yet" in intro.inner_text() or "will not exist" in intro.inner_text())
    ck("breakfast is not mentioned, which was asked for",
       "breakfast" not in intro.inner_text().lower())
    ck("no placeholder marker is left where a guest can read it",
       "PLACEHOLDER" not in pg.inner_text("body"))
    ck("it sits above the two buttons, not below them", pg.evaluate(
       "()=>document.getElementById('dineHelp').getBoundingClientRect().bottom"
       "<=document.querySelector('#qDine .opts').getBoundingClientRect().top+1"))
    ck("and it is one block, not a stack of two",
       pg.locator("#qDine .q-h").count() == 1)
    pg.close()

    # ── widths ──────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = guest(w=w)
        ck("the form does not scroll sideways at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.close()


    # ── the demo booking ────────────────────────────────────────────────
    # The site map linked here with no booking id, so the one form a guest
    # actually sees was the one nobody at the resort could open: it showed the
    # incomplete-link message and nothing else. b=demo opens it with a made up
    # guest.
    #
    # The whole point is that it writes nothing, so that is what is asserted,
    # by watching the requests rather than by trusting the branch.
    calls = []
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.on("request", lambda r: calls.append((r.method, r.url))
         if "firebasedatabase.app" in r.url else None)
    q.route("**/*.firebasedatabase.app/**", lambda r: r.fulfill(
        status=200, content_type="application/json", body="null"))
    q.route("**/gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    q.goto("http://localhost:8967/prearrival.html?b=demo"); q.wait_for_timeout(1500)

    ck("the demo opens the form rather than the incomplete link message",
       q.evaluate("()=>document.getElementById('form').className.indexOf('hide')<0"))
    ck("with a guest to greet",
       "Alex" in q.evaluate("()=>document.getElementById('greet').textContent"))
    ck("and says plainly that it is a demonstration",
       "demonstration" in q.evaluate(
           "()=>{const n=document.querySelector('#form .note-box');"
           "return n?n.textContent:'';}").lower())
    ck("opening it touches the database not at all", not calls)

    q.evaluate("""()=>{
      document.querySelectorAll('#etaOpts button')[2].click();
      document.getElementById('dIn').click();
      const d=document.querySelector('#dietNone button'); if(d)d.click();
      const p=document.querySelector('#purposeChips button'); if(p)p.click();
      const a=document.querySelector('#approachOpts button'); if(a)a.click();
      document.getElementById('wNo').click();}""")
    q.wait_for_timeout(300)
    q.evaluate("()=>[...document.querySelectorAll('button')]"
               ".find(x=>/send to nala/i.test(x.textContent)).click()")
    q.wait_for_timeout(900)
    ck("sending it shows the guest what they would see",
       q.evaluate("()=>document.getElementById('done').className") == "done")
    ck("while saying nothing was saved",
       "nothing was saved" in q.evaluate(
           "()=>document.getElementById('doneS').textContent").lower())
    ck("and writes nothing, which is the whole point",
       not [c for c in calls if c[0] in ("PATCH", "PUT", "POST")])
    q.close()

    b.close()
print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
