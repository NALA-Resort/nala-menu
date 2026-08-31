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
import threading, http.server, socketserver, json, time, datetime, os, base64

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

STATE = {"pms": None, "pre": None, "info": None, "fail": False}
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
    if "/spasettings" in u:
        body = json.dumps({"price60": 180, "price90": 250, "price120": 310})
    elif "/dietaries" in u: body = json.dumps(DIETS)
    elif "/prearrivalinfo" in u:
        body = json.dumps(STATE["info"]) if STATE["info"] else "null"
    elif "/prearrival" in u: body = json.dumps(STATE["pre"]) if STATE["pre"] else "null"
    elif "/pms" in u: body = json.dumps(STATE["pms"]) if STATE["pms"] else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

# photos.test stands in for the resort site's CDN, where the owner takes the
# note photos from. Anything under /dead/ is a retired address and 404s,
# which is exactly what a rotted CDN link does.
PNG1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
    "DUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
def photo_route(route, request):
    if "/dead/" in request.url:
        route.fulfill(status=404, body=""); return
    route.fulfill(status=200, content_type="image/png", body=PNG1)

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

    def drag(pg, idx):
        """Set the arrival track, as the input event a real drag fires."""
        pg.eval_on_selector("#trail",
            "(e,i)=>{e.value=i;e.dispatchEvent(new Event('input'))}", idx)
        pg.wait_for_timeout(150)

    def guest(link=LINK, w=390, begin=True):
        pg = b.new_page(viewport={"width": w, "height": 844})
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**photos.test/**", photo_route)
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8967/prearrival.html" + link)
        pg.wait_for_timeout(900)
        #  A fresh link lands on the greeting since 23 Aug evening; most
        #  sections are about the questions, so they walk through it.
        if begin and pg.evaluate("()=>{var i=document.getElementById('intro');"
                                 "return i && i.style.display!=='none';}"):
            pg.locator("#begin").click(); pg.wait_for_timeout(250)
        return pg

    # ── landing ─────────────────────────────────────────────────
    del WRITES[:]
    pg = guest(begin=False)
    ck("the guest lands on a greeting, not a question",
       pg.evaluate("()=>intro.style.display!=='none'") and
       pg.evaluate("()=>form.className") == "hide")
    ck("greeted by name from the link",
       "Robyn" in pg.locator("#greet").inner_text())
    ck("and told how long they are staying",
       "4 nights" in pg.locator("#sub").inner_text())
    ck("with why the form exists and a way in",
       pg.locator(".intro-why").inner_text().strip() != "" and
       pg.locator("#begin").is_visible())
    pg.locator("#begin").click(); pg.wait_for_timeout(250)
    ck("Begin hands the whole screen to the first question",
       pg.evaluate("()=>!document.querySelector('header').offsetParent") and
       pg.evaluate("()=>form.className") == "")

    opened = wrote("/bookings/res-guid-1/prearrival")
    ck("landing stamps that the link was opened", len(opened) == 1)
    if opened:
        ck("and stamps nothing else, because nothing has been answered",
           list(opened[0]["b"].keys()) == ["openedAt"])
        ck("as a PATCH, so it cannot wipe an existing record",
           opened[0]["m"] == "PATCH")
    ck("and it is the form, not a thank you",
       pg.evaluate("()=>done.className.indexOf('hide')>-1"))
    #  The demo's Back to Settings link must exist nowhere a real guest can
    #  be: a guest page offering a staff door reads as a mistake even
    #  though Settings gates itself.
    ck("a real guest link never offers a staff door",
       pg.evaluate("()=>!document.querySelector('a[href*=\"staff\"]')"))

    # ── one question to a page ──────────────────────────────────
    ck("the guest is shown one question, not eight",
       pg.evaluate("()=>document.querySelectorAll('.q.now').length") == 1)
    ck("and it is the first one, which since 23 Aug is what brings them",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    ck("with a count, so the form has a visible end",
       pg.locator("#prog").inner_text().strip() != "")
    ck("there is no Back on the first page",
       "hide" in pg.evaluate("()=>back.className"))
    ck("the button reads Next, not Send, until the last page",
       pg.locator("#send").text_content().strip() == "Next")

    # Every page carries an explanation behind a Read more, and every one of
    # them is shut. The constraint lives in there; the invitation stays on the
    # page. The details element became a plain button on 23 Aug, to the
    # approved mockup, but the rule it obeys did not change.
    #  Every page except the dining one, which asks nothing and carries no
    #  Read more because it IS the reading.
    ck("every page can explain why it is asking",
       pg.evaluate("()=>[...document.querySelectorAll('.q')]"
                   ".every(q=>q.id==='qDining'||"
                   "(q.querySelector('.more')&&q.querySelector('.more-b')))"))
    ck("and none of them is open to begin with",
       pg.evaluate("()=>!document.querySelector('.more-b.show')"))
    ck("the button says Read more while shut",
       pg.evaluate("()=>[...document.querySelectorAll('.more')]"
                   ".every(b=>b.textContent==='Read more')"))

    jump(pg, "qDiet")
    # The chef's master list, not a list this page invented. The list above
    # still stores "Gluten free", as one saved before the 26 Aug renames does;
    # the guest is offered the renamed pill, never the old wording. The rename
    # table is this page's own copy (guest pages load no staff code), kept in
    # step with tests/diet_renames.json.
    ck("dietary choices come from the chef's list, renamed on the way in",
       "Gluten" in pg.locator("#dietChips").inner_text())
    ck("and never under the old wording",
       "Gluten free" not in pg.locator("#dietChips").inner_text())
    RENAMES = json.load(open("tests/diet_renames.json"))
    ck("the page's rename table matches tests/diet_renames.json",
       pg.evaluate("()=>DIET_RENAMES") == RENAMES)
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
    #  The list sits behind a Yes since the owner's 23 Aug evening call:
    #  None and Yes side by side first, the pills revealed beneath a Yes.
    pg.locator("#dYes").click(); pg.wait_for_timeout(200)
    ck("saying yes reveals the list on this page",
       pg.evaluate("()=>dietWrap.className.indexOf('show')>-1"))
    ck("a guest can declare an allergy that is not on the list",
       "Other" in pg.locator("#dietChips").inner_text())
    pg.evaluate("()=>[...document.querySelectorAll('#dietChips .chip')]"
                ".find(b=>b.textContent.trim()==='Other').click()")
    pg.wait_for_timeout(150)
    ck("choosing it opens the note",
       pg.eval_on_selector("#dietNote", "e=>getComputedStyle(e).display") != "none")
    ck("and puts the cursor in it, since the note is the answer",
       pg.evaluate("()=>document.activeElement.id") == "dietNote")
    ck("choosing it clears no allergies to declare",
       pg.evaluate("()=>a.noDiets") is False)
    pg.evaluate("()=>[...document.querySelectorAll('#dietChips .chip')]"
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
    jump(pg, "qEta")
    del WRITES[:]
    drag(pg, 3)                                    # 3:00pm, key 15
    ck("a drag is not a decision to leave, so the track never advances by itself",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    nxt(pg)
    w = wrote("/bookings/res-guid-1/prearrival")
    ck("leaving a page saves that page", len(w) == 1)
    if w:
        ck("with the answer on it", w[0]["b"].get("arriveSlot") == "15")
        ck("and no finished stamp, because it is not finished",
           "at" not in w[0]["b"])
        ck("as a PATCH, so it cannot wipe what is already there",
           w[0]["m"] == "PATCH")
    ck("Next carries them to the week, which follows arrival since 23 Aug",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")

    #  A page saves only its own fields. A PATCH carrying every field would
    #  write empty strings over answers the guest has not reached yet.
    if w:
        ck("and only the fields belonging to that page",
           set(w[0]["b"].keys()) <= {"arriveSlot", "arriveNote"})

    del WRITES[:]
    pg.evaluate("()=>[...document.querySelectorAll('#approachOpts .opt')][1].click()")
    nxt(pg)
    ck("going forward saves the page being left",
       len(wrote("/prearrival")) == 1)
    del WRITES[:]
    pg.locator("#back").click(); pg.wait_for_timeout(450)
    ck("and so does going back, so a change is never lost to a Back tap",
       len(wrote("/prearrival")) == 1)
    ck("Back returns to the question before",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")
    ck("with the answer still selected",
       pg.evaluate("()=>[...document.querySelectorAll('#approachOpts .opt')]"
                   ".some(b=>b.className.indexOf('on')>-1)"))
    pg.locator("#back").click(); pg.wait_for_timeout(450)
    ck("and Back again to the one before that",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    ck("with the track still holding that answer too",
       pg.evaluate("()=>tval.textContent") == "3:00pm")
    ck("no page save is ever mistaken for a finished form",
       len(sent("/prearrival")) == 0)
    pg.close()

    # ── no answer turns the page ────────────────────────────────
    #  Auto progress went on 30 Aug, the owner's ruling: a clean answer
    #  used to carry the guest onward by itself after a pause, which read
    #  as the form rushing them and made a mis-tap cost a Back to undo.
    #  Every answer now stays put - the ones that open a follow up on
    #  their own page and the ones that open nothing alike - and Next is
    #  the one way forward. The older rule stands underneath: what an
    #  answer opens up lives on the page where it was given.
    pg = guest()
    jump(pg, "qDine")
    pg.locator("#dIn").click(); pg.wait_for_timeout(600)
    ck("answering dinner stays put, though it opens nothing",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    ck("with the choice showing as made",
       pg.evaluate("()=>dIn.className.indexOf('on')>-1"))
    nxt(pg)
    ck("Next, not the answer, turns the page",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    jump(pg, "qWell")
    pg.locator("#wYes").click(); pg.wait_for_timeout(600)
    ck("saying yes to a treatment does not skip past the days it opens",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qWell")
    ck("and the days are on that same page",
       pg.evaluate("()=>wWrap.style.display!=='none'"))
    jump(pg, "qEta")
    drag(pg, 8)                                    # the After 5pm end
    pg.wait_for_timeout(450)
    ck("an open ended arrival stays put too, because it opens a note",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    ck("and the note it demands is on this page, marked required",
       pg.evaluate("()=>etaNeeds.classList.contains('req')"))
    pg.close()

    # ── the walk, page by page ──────────────────────────────────
    #  A page will not let a guest past it unanswered, and says why on the
    #  page rather than marking six things at once and jumping to the top.
    pg = guest()
    del WRITES[:]
    nxt(pg)
    ck("an unanswered page does not advance",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    ck("and nothing is sent", len(sent("/prearrival")) == 0)
    ck("it names what is missing, in words",
       "what kind of stay" in pg.locator("#err").inner_text())
    ck("and marks only the page in front of them",
       pg.evaluate("()=>document.querySelectorAll('.q.miss').length") == 1)
    ck("without hiding the question being asked",
       pg.evaluate("()=>qPurpose.className.indexOf('now')>-1"))
    #  Single choice since the 23 Aug brief: one answer replaces another and,
    #  opening nothing, it carries the guest onward by itself.
    pg.evaluate("()=>[...document.querySelectorAll('#purposeOpts .opt')][2].click()")
    pg.wait_for_timeout(150)
    ck("one answer replaces another",
       pg.evaluate("()=>a.purpose.length") == 1)
    pg.evaluate("()=>[...document.querySelectorAll('#purposeOpts .opt')][0].click()")
    pg.wait_for_timeout(450)
    ck("choosing again keeps exactly one",
       pg.evaluate("()=>a.purpose.join()") == "Mostly relaxing at Nala")
    ck("and the page holds still until Next",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qPurpose")
    nxt(pg)
    ck("which carries them onward, to arrival",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta")
    nxt(pg)
    ck("which must be answered",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta" and
       "when you expect to arrive" in pg.locator("#err").inner_text())
    # an open ended slot has to carry a note, and the note is on this page
    drag(pg, 8)
    ck("choosing After 5pm asks for a rough time",
       pg.evaluate("()=>etaNeeds.classList.contains('req')"))
    nxt(pg)
    ck("and will not go on without one",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qEta" and
       "rough time" in pg.locator("#err").inner_text())
    pg.fill("#etaNote", "flight gets in at 6")
    # a fixed slot does not, but nor does it advance: Next does
    drag(pg, 5)                                    # 4:00pm, key 16
    #  The box itself stays on the page since 23 Aug evening, so the page is
    #  one height wherever the thumb sits; only the demand comes and goes.
    ck("a fixed slot needs no note, though the box remains",
       pg.evaluate("()=>!etaNeeds.classList.contains('req')") and
       pg.evaluate("()=>!!etaNeeds.offsetParent"))
    nxt(pg)
    ck("and Next carries them onward, to the week",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")

    nxt(pg)
    ck("the week must be answered",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")
    pg.evaluate("()=>[...document.querySelectorAll('#approachOpts .opt')][0].click()")
    nxt(pg)
    ck("then the first night",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    nxt(pg)
    ck("which must be answered too",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDine")
    pg.locator("#dIn").click(); nxt(pg)
    ck("then allergies", pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    nxt(pg)
    ck("which will not be skipped",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qDiet")
    # "None" is a positive answer - it writes noDiets, same record as ever.
    pg.locator("#dNone").click(); nxt(pg)
    ck("then treatments", pg.evaluate("()=>document.querySelector('.q.now').id") == "qWell")
    pg.locator("#wYes").click(); pg.wait_for_timeout(400)
    ck("saying yes offers only the days they are here",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 5)
    pg.evaluate("()=>[...document.querySelectorAll('#wDays .chip')][1].click()")
    #  The resting choice is an answer, not a blank: the question is not
    #  mandatory, and left alone it used to reach the masseuse as an empty
    #  string - a request with no time on it (the owner, 30 Aug).
    ck("the time is a slot list pinned to the canonical table, after Any time",
       pg.evaluate("""()=>[...document.querySelectorAll('#wTime option')]
           .map(o=>o.value)""")
       == ["Any time"] + [x["label"] for x in
                  __import__("json").load(open("tests/slots.json"))["slots"]])
    ck("and it is what the control rests on, in words a guest can read",
       pg.evaluate("()=>wTime.value") == "Any time" and
       pg.evaluate("()=>wTime.options[wTime.selectedIndex].textContent") == "Any time")
    ck("and a time left alone is sent as that answer, not as an empty one",
       pg.evaluate("()=>{collect(); return fullPayload().wellTime;}") == "Any time")
    #  A quantity of one leaves its column alone on the row, and it must
    #  not stretch to fill it: the length select was full width until a
    #  second appeared beside it.
    ck("a lone control keeps its half of the row rather than stretching",
       pg.evaluate("""()=>{
           const d=document.getElementById('wDur').getBoundingClientRect();
           const page=document.querySelector('.page').clientWidth;
           return d.width < page*0.6;}"""))
    #  One word, so the label cannot wrap and shove its pills down a line
    #  out of step with the control beside them.
    ck("the quantity label is one word, and its pills hold the line",
       pg.evaluate("""()=>{
           const labs=[...document.querySelectorAll('#wWrap .pair .sublabel')]
             .map(x=>x.textContent.trim());
           if (labs.indexOf('Quantity')<0) return false;
           const t=document.getElementById('wTime').getBoundingClientRect();
           const q=document.getElementById('wQty').getBoundingClientRect();
           return Math.abs(t.top-q.top)<4;}"""))
    pg.select_option("#wTime", "2:00 pm")
    # How many and how long, with the manager's price beside each length -
    # the whole point is that the guest sees the cost before they ask.
    ck("one massage is the resting answer and the second length stays hidden",
       pg.evaluate("()=>document.querySelector('#wQty .chip.on').textContent") == "One" and
       pg.evaluate("()=>!document.getElementById('wDur2').offsetParent"))
    ck("each length carries its price from the manager's settings",
       pg.evaluate("()=>[...document.querySelectorAll('#wDur option')].map(o=>o.textContent)")
       == ["1 hour · $180", "1.5 hours · $250", "2 hours · $310"])
    pg.evaluate("()=>[...document.querySelectorAll('#wQty .chip')][1].click()")
    pg.wait_for_timeout(200)
    ck("asking for two demands two lengths",
       pg.evaluate("()=>!!document.getElementById('wDur2').offsetParent"))
    #  Two small controls to a row, ruled 30 Aug: a select holding four
    #  words was taking a whole line, and the second massage sat under the
    #  first when it belongs beside it. Asserted by where they land, not by
    #  class name, and only above the width where the words stop fitting.
    ck("the small controls pair two to a row, the second beside the first",
       pg.evaluate("""()=>{
           const pairs=[...document.querySelectorAll('#wWrap .pair')];
           if (pairs.length!==2) return false;
           const page=document.querySelector('.page').clientWidth;
           return pairs.every(p=>{
             const c=[...p.children]
               .filter(x=>getComputedStyle(x).display!=='none');
             if (c.length!==2) return false;
             const a=c[0].getBoundingClientRect(), b=c[1].getBoundingClientRect();
             return Math.abs(a.top-b.top)<2 && b.left>=a.right-1
               && a.width < page*0.6;});}"""))
    ck("which massage is which reads as headings, not inside the options",
       pg.evaluate("()=>getComputedStyle(document.getElementById('wDurLab')).display") != "none" and
       pg.evaluate("()=>document.getElementById('wDurLab').textContent") == "First massage" and
       pg.evaluate("()=>document.getElementById('wDur2Lab').textContent") == "Second massage" and
       pg.evaluate("()=>[...document.querySelectorAll('#wDur2 option')].map(o=>o.textContent)")
       == ["1 hour · $180", "1.5 hours · $250", "2 hours · $310"])
    pg.select_option("#wDur", "90")
    pg.select_option("#wDur2", "60")
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
        ck("dining, and covers absent rather than zero when Mews sent no count",
           body["dining"] is True and "pax" not in body)
        ck("no allergies is recorded as an answer, not an empty list",
           body["noDiets"] is True and body["diets"] == [])
        ck("purpose and approach", body["purpose"] and body["approach"] == "most")
        ck("the treatment day and time", body["wellDay"] and body["wellTime"] == "2:00 pm")
        ck("how many and how long, as numbers the rules can bound",
           body["wellQty"] == 2 and body["wellDur"] == 90 and body["wellDur2"] == 60)
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
    #  Reopening went on 23 Aug: the owner judged a guest re-editing days-old
    #  answers a worse source of truth than a call, and reception can change
    #  every answer at the desk, so a submitted form is sealed.
    STATE["pre"] = {"at": "2026-08-16T10:00:00Z", "arriveSlot": "15",
                    "dining": False, "noDiets": True, "purpose": ["Mostly out exploring"],
                    "approach": "mix", "wellness": False, "occasion": "anniversary"}
    pg = guest()
    ck("a guest who already sent it sees the thank you, not a blank form",
       pg.evaluate("()=>done.className.indexOf('hide')<0"))
    ck("and the thank you offers no way back in",
       pg.evaluate("()=>!document.getElementById('again')") and
       pg.evaluate("()=>form.className") == "hide")
    ck("not even the frame's own buttons",
       pg.evaluate("()=>foot.style.display") == "none")
    pg.close()

    #  A guest who got halfway and stopped is a different case: pages save as
    #  they are left, so they resume at the first page they have not answered.
    #  The record carries an occasion from before the field left the form;
    #  it must not crash the resume, and the send must not erase it.
    STATE["pre"] = {"arriveSlot": "15", "purpose": ["Mostly out exploring"],
                    "occasion": "anniversary", "note": "ground floor please"}
    pg = guest(begin=False)
    ck("a form in progress reopens, because it was never finished",
       pg.evaluate("()=>form.className") == "")
    ck("without asking a returning guest to Begin again",
       pg.evaluate("()=>intro.style.display") == "none")
    ck("at the first page they have not answered",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")
    jump(pg, "qElse")
    ck("with their answers still there",
       pg.evaluate("()=>note.value") == "ground floor please")
    ck("and an old record's occasion is not erased by the send shape",
       pg.evaluate("()=>!('occasion' in fullPayload())"))
    jump(pg, "qEta")
    ck("and the track still holding their arrival",
       pg.evaluate("()=>tval.textContent") == "3:00pm")

    #  Every other answer is in place here, so an "Other" carrying no note is
    #  the one thing between this form and Send. It has to be: it tells the
    #  kitchen a guest has an allergy and nothing about what it is, which is
    #  worse than silence, because it looks answered.
    jump(pg, "qDiet")
    del WRITES[:]
    pg.locator("#dYes").click(); pg.wait_for_timeout(200)
    pg.evaluate("()=>[...document.querySelectorAll('#dietChips .chip')]"
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
      a.purpose=['Mostly out exploring']; a.approach='few'; a.wellness=false;
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
    why = pg.locator("#qDine .more-b")
    ck("how dinner works is there to be opened", why.count() == 1)
    ck("but shut, so the page is an invitation and not a briefing",
       pg.evaluate("()=>!document.querySelector('#qDine .more-b.show')"))
    wt = why.text_content()   # closed, so inner_text would see nothing
    #  The owner's 23 Aug words replaced the placeholder; the promise the
    #  suite protects is the same one: the menu comes later, finalised.
    ck("it explains the menu comes once finalised",
       "finalised" in wt)
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
    #  The owner's 23 Aug words carry the same limits in new phrases.
    for qid, word in (("qEta", "5pm"), ("qDiet", "menu changes"),
                      ("qWell", "fill quickly")):
        jump(pg, qid)
        ck("the limit on " + qid + " is kept, inside the explanation",
           word in pg.locator("#" + qid + " .more-b").text_content())
        ck("and is not the first thing a guest reads on " + qid,
           word not in pg.locator("#" + qid + " .q-h").inner_text())
    pg.close()

    # ── the guest form's own content, written from Settings ─────
    #  /prearrivalinfo drives three things. The welcome image on the
    #  landing - an image and ONLY an image, owner text there was ruled
    #  ugly (29 Aug). The dining page - the owner's image and words on a
    #  page of their own, with the dinner question following. And the Read
    #  more replacements, where a filled entry replaces the built-in copy
    #  and an empty one keeps it. Everything lands as text or an <img>,
    #  never markup. The editor's half of this contract is in spa_suite,
    #  which already drives staff.html signed in.
    STATE["info"] = {
        "welcomeImage": "https://photos.test/villa.jpg",
        "welcomeImageCrop": "top", "welcomeImageHeight": "tall",
        "diningImage": "https://photos.test/dinner.jpg",
        "diningText": "#Dining at Nala#\n"
                      "Dinner is one menu, written each morning\n"
                      "around what is *best* that day.\n\n"
                      "It is served at your villa or by the pool.",
        "intro": "The owner's own welcome line.",
        "titles": {"dine": "Joining us for dinner?"},
        "descs": {"dine": "We serve from *6pm*."},
        "more": {"dine": "The owner's *own words* about how dinner works."}}
    pg = guest(begin=False)
    pg.wait_for_timeout(300)
    #  Every word of a page is his to write: its heading, the description
    #  under it, the words behind Read more - and the introduction line on
    #  the landing (30 Aug). What he leaves empty keeps the page's own
    #  wording, so the two are asserted side by side.
    ck("the introduction line is his where he has written one",
       "own welcome line" in pg.locator(".intro-why").inner_text())
    ck("the welcome image is on the landing",
       pg.evaluate("()=>{var i=welcomeImg.querySelector('img');"
                   "return i?i.src:null;}") == "https://photos.test/villa.jpg")
    ck("an image and only an image - no text rides along",
       pg.evaluate("()=>welcomeImg.children.length") == 1 and
       pg.evaluate("()=>welcomeImg.textContent.trim()") == "")
    #  A portrait photo at natural size swallowed the landing whole (the
    #  owner's own, 30 Aug): an image is a cropped band, capped in height,
    #  anchored where the owner said. Asserted by computed style, so a
    #  class that stops resolving fails by name. Tall is half the screen.
    ck("cropped as a band, anchored top, capped at the tall height",
       pg.evaluate("()=>{var s=getComputedStyle(welcomeImg.querySelector('img'));"
                   "return s.objectFit+'|'+s.objectPosition+'|'+"
                   "Math.round(parseFloat(s.maxHeight));}")
       == "cover|50% 0%|" + str(round(844 * 0.50)))
    pg.locator("#begin").click(); pg.wait_for_timeout(250)
    live = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    ck("the dining page joins the walk straight after arrival time, in "
       "front of every dining question",
       "qDining" in live and
       live.index("qDining") == live.index("qEta") + 1 and
       live.index("qDining") < live.index("qApproach"))
    jump(pg, "qDining")
    ck("its image tops the page, the words beneath",
       pg.evaluate("()=>{var i=diningImg.querySelector('img');"
                   "return i?i.src:null;}") == "https://photos.test/dinner.jpg" and
       pg.evaluate("()=>diningImg.getBoundingClientRect().bottom"
                   "<=diningText.getBoundingClientRect().top+1"))
    ck("with nothing chosen, an image wears the centred banner default",
       pg.evaluate("()=>{var s=getComputedStyle(diningImg.querySelector('img'));"
                   "return s.objectFit+'|'+s.objectPosition+'|'+"
                   "Math.round(parseFloat(s.maxHeight));}")
       == "cover|50% 50%|" + str(round(844 * 0.38)))
    ck("as paragraphs, split on the blank line",
       pg.evaluate("()=>document.querySelectorAll('#diningText .info-p').length") == 2)
    #  The grammar's two marks, asked for once real copy met flat
    #  paragraphs (30 Aug): # opens a heading, asterisk pairs turn bold.
    #  Both land as elements with the marks stripped - never markup.
    #  Written "#Dining at Nala#", which is how the owner typed it and how
    #  half the world writes the mark: no space after the hash, closing
    #  hashes on the end. It reached a guest with the hashes showing.
    ck("a # line is a heading however the hashes are typed, marks stripped",
       pg.evaluate("()=>{var h=document.querySelector('#diningText .info-h');"
                   "return h?h.textContent:null;}") == "Dining at Nala" and
       pg.evaluate("()=>getComputedStyle(document.querySelector"
                   "('#diningText .info-h')).fontWeight") == "600")
    ck("and asterisk pairs turn bold, the marks gone from the page",
       pg.evaluate("()=>{var el2=document.querySelector('#diningText .info-p strong');"
                   "return el2?el2.textContent:null;}") == "best" and
       "*" not in pg.locator("#diningText").inner_text())
    ck("bold works in a Read more replacement too",
       pg.evaluate("()=>{var el2=document.querySelector('#qDine .more-b strong');"
                   "return el2?el2.textContent:null;}") == "own words")
    del WRITES[:]
    nxt(pg)
    ck("Next carries straight to the first dining question: the page asks nothing",
       pg.evaluate("()=>document.querySelector('.q.now').id") == "qApproach")
    ck("and reading is not answering, so nothing was written",
       len(wrote("/prearrival")) == 0)
    ck("the owner's Read more replaces the built-in words on the dinner page",
       pg.evaluate("()=>document.querySelector('#qDine .more-b').textContent")
       == "The owner's own words about how dinner works.")
    ck("and so do his heading and his description",
       pg.evaluate("()=>document.querySelector('#qDine .q-t').textContent")
       == "Joining us for dinner?" and
       pg.evaluate("()=>document.querySelector('#qDine .q-h').textContent")
       == "We serve from 6pm.")
    ck("a description takes the marks, a heading stays plain text",
       pg.evaluate("()=>!!document.querySelector('#qDine .q-h strong')") and
       pg.evaluate("()=>!document.querySelector('#qDine .q-t strong')"))
    ck("while a page he left empty keeps its built-in words",
       "Reception is here until 5pm" in
       pg.evaluate("()=>document.querySelector('#qEta .more-b').textContent") and
       pg.evaluate("()=>document.querySelector('#qEta .q-t').textContent")
       == "What time do you expect to arrive?")
    pg.close()

    #  A one night stay keeps its dinner question, so it keeps the page.
    #  And the one-night bending of qDine's built-in Read more must never
    #  bend the owner's replacement, whichever order the fetches land in.
    pg = guest(link="?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0)
                    + "&d=" + plus(1))
    live1n = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    ck("a one night guest still gets the dining page, after arrival time",
       "qDining" in live1n and
       live1n.index("qDining") == live1n.index("qEta") + 1)
    ck("and the owner's Read more, not the one-night rewrite",
       pg.evaluate("()=>document.querySelector('#qDine .more-b').textContent")
       == "The owner's own words about how dinner works.")
    #  A heading he writes is the heading on every stay length: the app's
    #  one-night bending has nothing left to bend, which is the cost of
    #  writing one and is said on the tab.
    ck("and his heading too, in place of the one-night wording",
       pg.evaluate("()=>document.querySelector('#qDine .q-t').textContent")
       == "Joining us for dinner?")
    pg.close()

    #  The photo-line rule lives on in the dining text, and the guards
    #  hold: a dead image removes itself (the CDN rewrites addresses, and
    #  a broken-image glyph says something is wrong with a form that is
    #  fine), an address inside a sentence stays text, only https speaks,
    #  and a Read more replacement lands as text, never markup.
    STATE["info"] = {
        "welcomeImage": "https://photos.test/dead/gone.jpg",
        "diningImage": "https://photos.test/pool2.jpg",
        "diningImageCrop": "bottom", "diningImageHeight": "natural",
        "diningText": "One menu, written daily.\n"
                      "https://photos.test/pool.jpg\n"
                      "Photos live at https://photos.test/x.jpg online.\n"
                      "http://photos.test/notsecure.jpg\n"
                      "Doors at 6pm *sharp",
        "more": {"dine": "<b>Bold</b> & <img src=x onerror=boom()>"}}
    pg = guest(begin=False)
    pg.wait_for_timeout(600)
    ck("a welcome image whose address has rotted removes itself",
       pg.evaluate("()=>welcomeImg.querySelectorAll('img').length") == 0)
    pg.locator("#begin").click(); pg.wait_for_timeout(250)
    jump(pg, "qDining")
    ck("a photo line in the dining text draws as the photo",
       pg.evaluate("()=>{var i=document.querySelector('#diningText img');"
                   "return i?i.src:null;}") == "https://photos.test/pool.jpg")
    ck("natural means the whole photo, uncropped, anchored where asked",
       pg.evaluate("()=>{var s=getComputedStyle(diningImg.querySelector('img'));"
                   "return s.maxHeight+'|'+s.objectPosition;}")
       == "none|50% 100%")
    ck("an address inside a sentence stays text, and http is not a photo",
       "https://photos.test/x.jpg" in pg.locator("#diningText").inner_text() and
       "http://photos.test/notsecure.jpg" in pg.locator("#diningText").inner_text()
       and pg.evaluate("()=>document.querySelectorAll('#diningText img').length") == 1)
    ck("an unpaired asterisk stays a literal asterisk",
       "*sharp" in pg.locator("#diningText").inner_text())
    ck("a Read more replacement is text on the page, never markup",
       pg.evaluate("()=>!document.querySelector("
                   "'#qDine .more-b b, #qDine .more-b img')") and
       "<b>Bold</b>" in pg.evaluate(
           "()=>document.querySelector('#qDine .more-b').textContent"))
    pg.close()

    STATE["info"] = None
    pg = guest(begin=False)
    ck("with nothing set, the landing is exactly what it was",
       pg.evaluate("()=>welcomeImg.children.length") == 0 and
       "A few details before you arrive" in
       pg.locator(".intro-why").inner_text())
    pg.locator("#begin").click(); pg.wait_for_timeout(200)
    ck("and the walk has no dining page",
       "qDining" not in pg.evaluate("()=>liveSteps().map(s=>s.id)"))
    pg.close()

    # ── widths ──────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = guest(w=w)
        ck("the form does not scroll sideways at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.close()


    # ── the 23 Aug revision, asserted as decisions ──────────────
    #  The order of the eight, as a list, so a later reshuffle is deliberate.
    pg = guest()
    #  Page kickers were added and scrapped within the hour on 23 Aug -
    #  clutter without a proper design pass. Only their spacing survives.
    ck("the pages run who, why, when, dining, the week, tonight, dietaries, "
       "treatments, anything else",
       pg.evaluate("()=>STEPS.map(s=>s.id).join(',')") ==
       "qCompanion,qPurpose,qEta,qDining,qApproach,qDine,qDiet,qWell,qElse")

    #  The nine keys, in order, in all four files that hold a copy. A test
    #  that reads one copy proves nothing about the other three, and
    #  registration.html prints an unknown key raw onto a card a guest signs.
    KEYS = ["before2","14","1430","15","1530","16","1630","17","after5"]
    ck("the guest form holds the nine keys in order",
       pg.evaluate("()=>ETA_SLOTS.map(s=>s[0]).join(',')") == ",".join(KEYS))
    import re as _re
    fd = open("front-desk.html").read()
    ck("and so does the front desk",
       [m for m in _re.findall(r"\['(\w+)',\s*'Around|\['(before2|after5)'", fd)] and
       _re.search(r"var ETA_SLOTS = \[(.*?)\];", fd, _re.S) and
       [t for t in _re.findall(r"\['([\w]+)'", _re.search(
           r"var ETA_SLOTS = \[(.*?)\];", fd, _re.S).group(1))] == KEYS)
    rg = open("registration.html").read()
    rgm = _re.search(r"var ETA_SLOTS = \{(.*?)\};", rg, _re.S).group(1)
    got = _re.findall(r"(?:\{|,)\s*'?([\w]+)'?\s*:", "{" + rgm)
    ck("and registration, whose fallback prints an unknown key raw",
       got == KEYS)
    sh = open("nala-shared.js").read()
    ck("and the shared mapper accepts every numbered key the track writes",
       bool(_re.search(r"1\[4-7\]\(30\)\?", sh)))
    ck("with the two open ends named beside them",
       "'before2'" in sh and "'after5'" in sh)

    #  The track produces the right key at both ends and at a half hour.
    jump(pg, "qEta")
    drag(pg, 0)
    ck("the left end of the track is before2",
       pg.evaluate("()=>a.eta") == "before2")
    ck("and it demands a note before the page advances",
       (nxt(pg), pg.evaluate("()=>document.querySelector('.q.now').id"))[1] == "qEta")
    drag(pg, 8)
    ck("the right end is after5", pg.evaluate("()=>a.eta") == "after5")
    ck("which demands one too",
       (nxt(pg), pg.evaluate("()=>document.querySelector('.q.now').id"))[1] == "qEta")
    drag(pg, 2)
    ck("and the half hours in the middle write their four digit key",
       pg.evaluate("()=>a.eta") == "1430")
    pg.close()

    #  An error changes no height anywhere: the foot grew when its line was
    #  display:none, and covered the page it was refusing.
    pg = guest()
    h1 = pg.evaluate("()=>foot.getBoundingClientRect().height")
    y1 = pg.evaluate("()=>send.getBoundingClientRect().top")
    nxt(pg)                                        # refused: purpose unanswered
    ck("an error is shown in space already paid for",
       "show" in pg.evaluate("()=>err.className") and
       pg.evaluate("()=>foot.getBoundingClientRect().height") == h1)
    ck("so the buttons hold perfectly still",
       pg.evaluate("()=>send.getBoundingClientRect().top") == y1)
    pg.close()

    #  Every page fits 390 x 780 with its Read more open, the nav fixed to
    #  the foot. Walked with follow ups open too, which is stricter than the
    #  brief asks, because those are the pages a real guest sees.
    pg = guest(w=390)
    pg.set_viewport_size({"width": 390, "height": 780})
    pg.wait_for_timeout(200)
    seq = ["qCompanion","qPurpose","qEta","qApproach","qDine","qDiet","qWell","qElse"]
    live = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    for qid in [q for q in seq if q in live]:
        jump(pg, qid)
        ck("read more is closed arriving on " + qid,
           pg.evaluate("()=>!document.querySelector('.more-b.show')"))
        pg.evaluate("(q)=>document.querySelector('#'+q+' .more').click()", qid)
        if qid == "qEta": drag(pg, 8)
        if qid == "qDiet":
            pg.locator("#dYes").click()
        if qid == "qWell":
            pg.locator("#wYes").click()
        pg.wait_for_timeout(200)
        ck(qid + " fits a phone with its Read more open",
           pg.evaluate("()=>{var s=document.querySelector('.scrollarea');"
                       "return s.scrollHeight<=s.clientHeight;}"))
        ck("and the nav is part of the frame on " + qid + ", not the content",
           pg.evaluate("()=>{var f=document.getElementById('foot');"
                       "var r=f.getBoundingClientRect();"
                       "return !document.querySelector('.scrollarea').contains(f)"
                       " && r.bottom<=window.innerHeight+1;}"))
    pg.close()

    #  A one night stay has no week ahead: the only night is the first
    #  night, and that page asks it. Dates come from the link here; Mews
    #  overriding them re-syncs the same way the companion page does.
    ONE = "?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0) + "&d=" + plus(1)
    pg = guest(link=ONE)
    live = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    ck("a one night stay is not asked about the week ahead",
       "qApproach" not in live)
    ck("nor what kind of stay it is planning",
       "qPurpose" not in live)
    ck("and its dinner question has no \"first night\", only the night",
       pg.evaluate("()=>document.querySelector('#qDine .q-t').textContent")
       == "Will you dine with us?" and
       pg.evaluate("()=>dOut.textContent") == "Not this time")
    ck("nor offered a treatment its stay has no window for",
       "qWell" not in live)
    ck("but still about tonight and dietaries",
       all(q in live for q in ("qDine", "qDiet")))
    ck("and the count says four, not eight",
       pg.locator("#prog").inner_text().strip().lower().endswith("of 4"))
    #  The answered walk must still send: approach and purpose were never
    #  asked, so an empty either cannot hold the form hostage.
    pg.evaluate("""()=>{
      a.eta='15'; a.dining=false;
      a.noDiets=true;
    }""")
    jump(pg, "qElse")
    del WRITES[:]
    pg.locator("#send").click(); pg.wait_for_timeout(600)
    w1 = sent("/bookings/res-guid-1/prearrival")
    ck("and the form sends without either", len(w1) == 1)
    if w1:
        ck("with wellness absent, not false, because it was never asked",
           "wellness" not in w1[0]["b"])
    pg.close()

    #  One table, two readers. The Front Desk names the questions a guest has
    #  not answered yet, so it has to hold exactly this form's required list -
    #  no more (it would chase a question nobody was asked, which is what the
    #  retired `occasion` field would have done) and no fewer. This side
    #  asserts the form requires exactly the steps the table names.
    Q = json.load(open("tests/form_questions.json"))
    req = [q["step"] for q in Q["questions"]]
    one = [q["step"] for q in Q["questions"] if q["askedOnOneNight"]]
    pg = guest(link="?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0)
                    + "&d=" + plus(3))
    live = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    blocks = pg.evaluate("(ids)=>ids.map(i=>!!missingOn(i))", live)
    required = [i for i, b in zip(live, blocks) if b]
    print("   the form requires:", required, "the table says:", req)
    #  Every one of them must actually BE a question this form asks. Filtering
    #  the table down to the steps that exist would let a retired question sit
    #  in it unnoticed, which is the exact drift the table is here to catch.
    print("   table questions the form does not ask:",
          [q for q in req if q not in live])
    ck("every question the table names is one the form actually asks",
       all(q in live for q in req))
    ck("the form requires exactly the questions the table names, in its order",
       required == req)
    ck("and nothing the table calls optional holds a guest up",
       all(s_ not in required for s_ in Q["_optional"]))
    pg.close()
    #  And on a one night stay, only the ones the table says are still asked.
    pg = guest(link="?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0)
                    + "&d=" + plus(1))
    live1 = pg.evaluate("()=>liveSteps().map(s=>s.id)")
    blocks1 = pg.evaluate("(ids)=>ids.map(i=>!!missingOn(i))", live1)
    req1 = [i for i, b in zip(live1, blocks1) if b]
    print("   short-list questions a one night form does not ask:",
          [q for q in one if q not in live1])
    ck("and every short-list question is one a one night form still asks",
       all(q in live1 for q in one))
    ck("a one night stay is required exactly the short list, no more",
       req1 == one)
    ck("and is never asked the ones the table says it is not",
       not any(q["step"] in live1 for q in Q["questions"]
               if not q["askedOnOneNight"]))
    pg.close()

    #  One table, two readers. Which stays are shown the treatment question
    #  is decided here and has to be known at the Front Desk, or a one night
    #  guest who answered everything they were asked tints amber for ever -
    #  villas 16 and 17, 28 Aug. This page loads no staff code, so the rule
    #  cannot be shared in code; tests/onenight_cases.json is what both
    #  copies answer to. Add a case there, not here.
    cases = json.load(open("tests/onenight_cases.json"))["cases"]
    bad = []
    for nights, want, why in cases:
        q = guest(link="?b=res-guid-1&n=Robyn&s=Williams&a=" + plus(0)
                       + "&d=" + plus(nights))
        live = q.evaluate("()=>liveSteps().map(s=>s.id)")
        q.close()
        if ("qWell" not in live) != bool(want):
            bad.append("%d nights: wanted one-night %s, treatment page %s (%s)"
                       % (nights, want,
                          "hidden" if "qWell" not in live else "shown", why))
    print("   one night cases the guest form reads wrongly:", bad)
    ck("the treatment question is hidden on exactly the stays the table names",
       bad == [] and len(cases) >= 5)

    #  The day chips read the resolved dates, not the raw link: a link with
    #  no dates whose booking Mews knows still offers the days - the demo
    #  itself was dateless and offered none for a spell.
    STATE["pms"] = {"first": "Robyn", "adults": 2,
                    "arrive": plus(0), "depart": plus(2)}
    pg = guest(link="?b=res-guid-1&n=Robyn")
    jump(pg, "qWell")
    pg.locator("#wYes").click(); pg.wait_for_timeout(250)
    ck("a dateless link still offers the days Mews knows",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 3)
    pg.close()
    STATE["pms"] = None

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

    ck("the demo opens the greeting rather than the incomplete link message",
       q.evaluate("()=>document.getElementById('intro').style.display!=='none'"))
    q.locator("#begin").click(); q.wait_for_timeout(300)
    ck("and Begin opens the form",
       q.evaluate("()=>document.getElementById('form').className.indexOf('hide')<0"))
    ck("with a guest to greet",
       "Alex" in q.evaluate("()=>document.getElementById('greet').textContent"))
    #  No banner at all since 30 Aug, the owner stripping the last line of
    #  it: the demo landing is exactly what a guest sees. The way back to
    #  Settings waits on the thank-you screen instead - the demo's last
    #  page - because a landing link was behind the walk the moment Begin
    #  was tapped.
    ck("and the landing carries no banner and no staff door - a guest's own",
       q.evaluate("()=>!document.querySelector('#intro .note-box')") and
       q.evaluate("()=>!document.querySelector('a[href*=\"staff\"]')"))
    ck("opening it reads the public Settings notes and nothing else",
       calls != [] and
       all(m == "GET" and "/prearrivalinfo" in u for m, u in calls))

    q.evaluate("""()=>{
      trail.value=2; trail.dispatchEvent(new Event('input'));
      document.getElementById('dIn').click();
      document.getElementById('dNone').click();
      const p=document.querySelector('#purposeOpts button'); if(p)p.click();
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
    #  The write-preview loop: Settings links here to preview, and the way
    #  back sits on this, the demo's last page. The real-link check above
    #  holds the other half: no staff door anywhere a guest can be.
    ck("and the thank-you screen offers the way back to Settings",
       q.evaluate("()=>{const a=document.querySelector('#done a');"
                  "return a ? a.getAttribute('href') : null;}") == "staff.html")
    ck("and writes nothing, which is the whole point",
       not [c for c in calls if c[0] in ("PATCH", "PUT", "POST")])
    q.close()

    #  And once the notes CAN be read, the demo previews them live - that is
    #  what the one read is for - while the warranty holds: still that one
    #  node, still no writes.
    calls2 = []
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.on("request", lambda r: calls2.append((r.method, r.url))
         if "firebasedatabase.app" in r.url else None)
    def demo_fb(route, request):
        body = (json.dumps({"welcomeImage": "https://photos.test/villa.jpg",
                            "diningText": "One menu, written daily.",
                            "more": {"dine": "Owner words."}})
                if "/prearrivalinfo" in request.url else "null")
        route.fulfill(status=200, content_type="application/json", body=body)
    q.route("**firebasedatabase.app/**", demo_fb)
    q.route("**photos.test/**", photo_route)
    q.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    q.goto("http://localhost:8967/prearrival.html?b=demo"); q.wait_for_timeout(1500)
    ck("with the record readable, the demo shows the welcome image",
       q.evaluate("()=>welcomeImg.querySelectorAll('img').length") == 1)
    ck("and gains the dining page",
       "qDining" in q.evaluate("()=>liveSteps().map(s=>s.id)") and
       "One menu" in q.evaluate("()=>diningText.textContent"))
    ck("and the owner's Read more on the dinner page",
       "Owner words." == q.evaluate(
           "()=>document.querySelector('#qDine .more-b').textContent"))
    ck("still having read only the Guest form record, and written nothing",
       all(m == "GET" and "/prearrivalinfo" in u for m, u in calls2))
    q.close()

    b.close()
print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
