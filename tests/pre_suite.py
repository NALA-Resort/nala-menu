"""prearrival.html, the guest's pre-arrival form.

Guest tier, no sign in, reached only from a link. The things most worth pinning
down are the ones that are easy to get wrong and invisible when they are:

  1. One question to a page, and everything an answer opens up stays on the
     page where the answer was given. A guest must never say yes on one page
     and meet the cost of yes on the next.
  2. Every page saves as it is left, so a guest who stops halfway has still
     told us the two things that matter most. `at` is written by the final
     send ALONE: answers with no `at` are a form in progress, answers with one
     are a form finished, and that is what the desk reads.
  3. The opened stamp IS written on landing, because without it a message that
     never arrived looks the same as one that arrived and was ignored.
  4. The link's name and dates are shown and NEVER written back. They are Mews'
     facts, and a copy taken here would be stale the moment Mews changed them.
  5. Send is a PATCH. Reception may already have confirmed this booking, and a
     PUT would wipe confirmedAt and un-confirm a guest at the desk.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8967), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

now = datetime.datetime.now().astimezone()
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")

# The chef's master list. An inactive entry must never reach a guest.
DIETS = {"gf":  {"name": "Gluten free", "active": True, "group": "common"},
         "nut": {"name": "Nut allergy", "active": True, "group": "common"},
         "chi": {"name": "Red pepper spice", "active": True, "group": "menu"},
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

def sent(frag):
    """A finished form. Only the final send carries `at`, so a page save can
    never be mistaken for a completed one."""
    return [w for w in wrote(frag) if isinstance(w["b"], dict) and w["b"].get("at")]

LINK = ("?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0) + "&d=" + plus(4))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def jump(pg, sid):
        """Test-only jump to a page, for the checks that are about a control
        rather than about the walk. The walk itself is clicked through."""
        pg.evaluate("""(sid)=>{var l=liveSteps();
          for(var i=0;i<l.length;i++) if(l[i].id===sid){ showStep(i); return; }}""", sid)
        pg.wait_for_timeout(150)

    def nxt(pg):
        pg.locator("#send").click(); pg.wait_for_timeout(320)

    def guest(link=LINK, w=390):
        pg = b.new_page(viewport={"width": w, "height": 844})
        pg.route("**firebasedatabase.app/**", fb)
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

    # ── one question to a page ──────────────────────────────────
    ck("the guest is shown one question, not eight",
       pg.evaluate("()=>document.querySelectorAll('.q.now').length") == 1)
    ck("and it is the first one",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    ck("with a count, so the form has a visible end",
       pg.locator("#prog").inner_text().strip() != "")
    ck("there is no Back on the first page",
       "hide" in pg.evaluate("()=>back.className"))
    ck("the button reads Next, not Send, until the last page",
       pg.locator("#send").text_content().strip() == "Next")

    # Every page carries an explanation, and every one of them is shut. The
    # constraint lives in there; the invitation stays on the page.
    ck("every page can explain why it is asking",
       pg.evaluate("()=>[...document.querySelectorAll('.q')]"
                   ".every(q=>q.querySelector('details.why'))"))
    ck("and none of them is open to begin with",
       pg.evaluate("()=>[...document.querySelectorAll('details.why')]"
                   ".every(d=>!d.open)"))

    jump(pg, "qDiet")
    # The chef's master list, not a list this page invented.
    ck("dietary choices come from the chef's list",
       "Gluten free" in pg.locator("#dietChips").inner_text())
    ck("and a retired entry never reaches a guest",
       "Retired" not in pg.locator("#dietChips").inner_text())
    #  A "this menu only" entry is a warning about tonight's cooking, such as
    #  a chilli heat level. This form is filled days ahead, when the menu for
    #  the arrival night does not exist, so offering one asks a guest about a
    #  dish nobody has planned. Those belong on the nightly form.
    ck("a this-menu-only dietary is not offered days ahead",
       "Red pepper spice" not in pg.locator("#dietChips").inner_text())

    # ── an allergy that is not on the list ──────────────────────
    #  Filled in days ahead with nobody to ask, so a guest whose allergy is
    #  not among the chef's entries needs somewhere to put it. Without this
    #  the only ways past were a chip that is not their allergy, or declaring
    #  nothing at all.
    ck("a guest can declare an allergy that is not on the list",
       "Other" in pg.locator("#dietNone").inner_text())
    pg.evaluate("()=>[...document.querySelectorAll('#dietNone .chip')]"
                ".find(b=>b.textContent.trim()==='Other').click()")
    pg.wait_for_timeout(150)
    ck("choosing it opens the note",
       pg.eval_on_selector("#dietNote", "e=>getComputedStyle(e).display") != "none")
    ck("and puts the cursor in it, since the note is the answer",
       pg.evaluate("()=>document.activeElement.id") == "dietNote")
    ck("choosing it clears no allergies to declare",
       pg.evaluate("()=>a.noDiets") is False)
    pg.evaluate("()=>[...document.querySelectorAll('#dietNone .chip')]"
                ".find(b=>b.textContent.trim()==='Other').click()")
    pg.wait_for_timeout(120)
    ck("and it can be taken back off",
       pg.evaluate("()=>a.diets.indexOf('Other')") == -1)

    pg.close()

    # ── a page saves as it is left ──────────────────────────────
    #  This reverses the old rule that nothing was written before Send. That
    #  rule existed because a half filled record could not be told apart from
    #  a considered one; `at` now tells them apart. The gain is that a guest
    #  who gives up at question five has still told the resort when they are
    #  arriving and what they cannot eat, which are the two the resort would
    #  otherwise have to telephone for.
    pg = guest()
    del WRITES[:]
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')]"
                ".find(b=>b.textContent.indexOf('3pm')>-1).click()")
    pg.wait_for_timeout(500)
    w = wrote("/bookings/res-guid-1/prearrival")
    ck("leaving a page saves that page", len(w) == 1)
    if w:
        ck("with the answer on it", w[0]["b"].get("arriveSlot") == "15")
        ck("and no finished stamp, because it is not finished",
           "at" not in w[0]["b"])
        ck("as a PATCH, so it cannot wipe what is already there",
           w[0]["m"] == "PATCH")
    ck("a clean answer carries the guest to the next page by itself",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")

    #  A page saves only its own fields. A PATCH carrying every field would
    #  write empty strings over answers the guest has not reached yet.
    if w:
        ck("and only the fields belonging to that page",
           set(w[0]["b"].keys()) <= {"arriveSlot", "arriveNote"})

    del WRITES[:]
    pg.locator("#dOut").click(); pg.wait_for_timeout(500)
    ck("going forward saves the page being left",
       len(wrote("/prearrival")) == 1)
    del WRITES[:]
    pg.locator("#back").click(); pg.wait_for_timeout(450)
    ck("and so does going back, so a change is never lost to a Back tap",
       len(wrote("/prearrival")) == 1)
    ck("Back returns to the question before",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    ck("with the answer still selected",
       pg.evaluate("()=>dOut.className.indexOf('on')>-1"))
    pg.locator("#back").click(); pg.wait_for_timeout(450)
    ck("and Back again to the one before that",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    ck("with that answer still selected too",
       pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')]"
                   ".some(b=>b.className.indexOf('on')>-1)"))
    ck("no page save is ever mistaken for a finished form",
       len(sent("/prearrival")) == 0)
    pg.close()

    # ── an answer that opens a follow up stays put ──────────────
    #  The rule the owner set: a guest must never say yes on one page and be
    #  shown what yes costs on the next, because the only way back from that
    #  is to return and change an answer they meant.
    pg = guest()
    jump(pg, "qDine")
    pg.locator("#dIn").click(); pg.wait_for_timeout(600)
    ck("saying yes to dinner does not skip past the question it opens",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    ck("and how many of you is on that same page",
       pg.evaluate("()=>paxWrap.style.display!=='none'"))
    jump(pg, "qWell")
    pg.locator("#wYes").click(); pg.wait_for_timeout(600)
    ck("saying yes to a treatment does not skip past the days it opens",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qWell")
    ck("and the days are on that same page",
       pg.evaluate("()=>wWrap.style.display!=='none'"))
    jump(pg, "qEta")
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')]"
                ".find(b=>b.textContent.indexOf('After')>-1).click()")
    pg.wait_for_timeout(600)
    ck("an open ended arrival stays put too, because it opens a note",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    pg.close()

    # ── the walk, page by page ──────────────────────────────────
    #  A page will not let a guest past it unanswered, and says why on the
    #  page rather than marking six things at once and jumping to the top.
    pg = guest()
    del WRITES[:]
    nxt(pg)
    ck("an unanswered page does not advance",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    ck("and nothing is sent", len(sent("/prearrival")) == 0)
    ck("it names what is missing, in words",
       "when you expect to arrive" in pg.locator("#err").inner_text())
    ck("and marks only the page in front of them",
       pg.evaluate("()=>document.querySelectorAll('.q.miss').length") == 1)
    ck("without hiding the question being asked",
       pg.evaluate("()=>qEta.className.indexOf('now')>-1"))

    # an open ended slot has to carry a note, and the note is on this page
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')].find(b=>b.textContent.indexOf('After')>-1).click()")
    pg.wait_for_timeout(400)
    ck("choosing After 5pm asks for a rough time",
       pg.evaluate("()=>etaNote.style.display!=='none'"))
    nxt(pg)
    ck("and will not go on without one",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta" and
       "rough time" in pg.locator("#err").inner_text())
    pg.fill("#etaNote", "flight gets in at 6")
    # a fixed slot does not
    pg.evaluate("()=>[...document.querySelectorAll('#etaOpts .opt')].find(b=>b.textContent.indexOf('4pm')>-1).click()")
    pg.wait_for_timeout(500)
    ck("a fixed slot needs no note", pg.evaluate("()=>etaNote.style.display==='none'"))
    ck("and carries them onward", pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")

    nxt(pg)
    ck("the first night must be answered",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    pg.locator("#dIn").click(); pg.wait_for_timeout(400)
    ck("saying yes asks how many, on the same page",
       pg.evaluate("()=>paxWrap.style.display!=='none'"))
    nxt(pg)
    ck("then allergies", pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    nxt(pg)
    ck("which will not be skipped",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    # "none to declare" is a positive answer and satisfies it
    pg.evaluate("()=>[...document.querySelectorAll('#dietNone .chip')][0].click()")
    pg.wait_for_timeout(200)
    nxt(pg)
    ck("no allergies to declare counts as answering",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    nxt(pg)
    ck("what brings them must be answered",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    pg.evaluate("()=>[...document.querySelectorAll('#purposeChips .chip')][2].click()")
    pg.wait_for_timeout(150)
    ck("a multi select does not run off the moment one is ticked",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    nxt(pg)
    ck("then how they plan to eat",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")
    pg.evaluate("()=>[...document.querySelectorAll('#approachOpts .opt')][0].click()")
    pg.wait_for_timeout(500)
    ck("then treatments", pg.evaluate("()=>document.querySelector('.q.now').id") == "qWell")
    pg.locator("#wYes").click(); pg.wait_for_timeout(400)
    ck("saying yes offers only the days they are here",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 5)
    pg.evaluate("()=>[...document.querySelectorAll('#wDays .chip')][1].click()")
    pg.fill("#wTime", "late morning")
    nxt(pg)
    ck("and the last page is the optional one",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qElse")
    ck("where the button becomes Send",
       pg.locator("#send").text_content().strip() == "Send to Nala")

    # the two optional ones are genuinely optional
    del WRITES[:]
    nxt(pg); pg.wait_for_timeout(400)
    w = sent("/bookings/res-guid-1/prearrival")
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
        #  The send writes the whole record again, not just the last page, so
        #  a page save lost to a bad connection costs the guest nothing.
        ck("the send carries the whole form, not only the last page",
           all(k in body for k in ("arriveSlot","dining","diets","purpose",
                                   "approach","wellness")))
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
    ck("reopening starts at the first question, not wherever it left off",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    jump(pg, "qElse")
    ck("with their answers still there",
       pg.evaluate("()=>occasion.value") == "anniversary")
    jump(pg, "qDine")
    ck("and their choices still selected",
       pg.evaluate("()=>dOut.className.indexOf('on')>-1"))

    #  Every other answer is in place here, so an "Other" carrying no note is
    #  the one thing between this form and Send. It has to be: it tells the
    #  kitchen a guest has an allergy and nothing about what it is, which is
    #  worse than silence, because it looks answered.
    jump(pg, "qDiet")
    del WRITES[:]
    pg.evaluate("()=>[...document.querySelectorAll('#dietNone .chip')]"
                ".find(b=>b.textContent.trim()==='Other').click()")
    pg.wait_for_timeout(150)
    nxt(pg)
    ck("an allergy declared as Other with no note is refused",
       "allergy or requirement" in pg.inner_text("#err"))
    ck("and the page does not advance",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    ck("and nothing is written, not even a page save",
       len(wrote("/prearrival")) == 0)
    pg.fill("#dietNote", "Sesame")
    del WRITES[:]
    nxt(pg)
    w2 = wrote("/bookings/res-guid-1/prearrival")
    ck("with the note written it goes through", len(w2) == 1)
    if w2:
        ck("Other is stored as an ordinary dietary the kitchen already reads",
           "Other" in (w2[0]["b"].get("diets") or []))
        ck("and a refused page never saved a half answer first",
           len(w2) == 1)
        ck("and the note beside it says what the allergy is",
           w2[0]["b"].get("dnote") == "Sesame")
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
    #  Answered directly rather than clicked through, because this is about
    #  what a rejected send does, not about the walk.
    pg.evaluate("""()=>{
      a.eta='16'; a.dining=false; a.noDiets=true;
      a.purpose=['A short break']; a.approach='mix'; a.wellness=false;
    }""")
    jump(pg, "qElse")
    pg.locator("#send").click(); pg.wait_for_timeout(700)
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
    jump(pg, "qDine")
    intro = pg.locator("#dineHelp")
    ck("the dining description is on the page", intro.is_visible())
    #  The seating time is a commitment the guest is agreeing to by saying
    #  yes, so it stays in the open. Hiding a commitment behind a tap is the
    #  same mistake as putting a follow up question on the next page.
    ck("the seating time stays on the page, because saying yes agrees to it",
       "6:00" in intro.inner_text() and "6:30" in intro.inner_text())
    why = pg.locator("#dineWhy")
    ck("how dinner works is there to be opened", why.count() == 1)
    ck("but shut, so the page is an invitation and not a briefing",
       pg.evaluate("()=>!dineWhy.open"))
    wt = why.text_content()   # closed, so inner_text would see nothing
    ck("it explains why there is no menu to show yet",
       "not exist yet" in wt or "will not exist" in wt)
    ck("breakfast is not mentioned, which was asked for",
       "breakfast" not in wt.lower())
    ck("no placeholder marker is left where a guest can read it",
       "PLACEHOLDER" not in pg.inner_text("body"))
    ck("it sits above the two buttons, not below them", pg.evaluate(
       "()=>document.getElementById('dineHelp').getBoundingClientRect().bottom"
       "<=document.querySelector('#qDine .opts').getBoundingClientRect().top+1"))
    ck("and it is one block, not a stack of two",
       pg.locator("#qDine .q-h").count() == 1)

    #  The four that used to open by telling a guest what they could not have.
    #  Each limit is still on the page, one tap away, and no longer the first
    #  thing read.
    for qid, word in (("qEta", "5pm"), ("qDiet", "menu is set"),
                      ("qWell", "peak season")):
        jump(pg, qid)
        ck("the limit on " + qid + " is kept, inside the explanation",
           word in pg.locator("#" + qid + " .why-b").text_content())
        ck("and is not the first thing a guest reads on " + qid,
           word not in pg.locator("#" + qid + " .q-h").inner_text())
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
    q.route("**firebasedatabase.app/**", lambda r: r.fulfill(
        status=200, content_type="application/json", body="null"))
    q.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
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
    q.evaluate("()=>{ var l=liveSteps(); showStep(l.length-1); }")
    q.wait_for_timeout(200)
    q.locator("#send").click()
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
