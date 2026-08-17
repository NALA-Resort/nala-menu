"""front-desk.html, Front Desk Arrival.

Reception's screen for check-in. The two things most worth pinning down:

  1. An arrival is a stay whose FIRST night is the viewed date. /stays holds
     one row per night, so without that filter every in-house guest sits on
     the arrivals list for the whole of their stay.
  2. The screen is EDIT, not create. A guest who filled the form in from their
     phone must arrive prefilled, or reception retypes what the guest already
     gave and the form was pointless.

Confirmed means a dining status exists and reception has been through it at
the desk. It includes not dining.
"""
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8964), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")
def plus(d): return (now + datetime.timedelta(days=d)).strftime("%Y-%m-%d")

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STAYS = {
  "4":  {"id":"b4","first":"Robyn","last":"Williams","arrive":today,"depart":plus(4),"adults":2},
  "9":  {"id":"b9","first":"Konstantinos","last":"Papadopoulos","arrive":today,"depart":plus(2),"adults":4},
  "2":  {"id":"b2","first":"James","last":"Fisher","arrive":today,"depart":plus(6),"adults":2},
  "7":  {"id":"b7","first":"Mark","last":"Whitfield","arrive":today,"depart":plus(3),"adults":2},
  "11": {"id":"b11","first":"Priya","last":"Raghunathan","arrive":today,"depart":plus(5),"adults":3},
  "14": {"id":"b14","first":"Ann","last":"Brown","arrive":today,"depart":plus(1),"adults":1},
  # mid stay: in house tonight, arrived two days ago. Must NOT be an arrival.
  "3":  {"id":"b3","first":"Midstay","last":"Guest","arrive":plus(-2),"depart":plus(2),"adults":2},
  # the older shape, when the value was a bare booking id
  "5":  "bare-id-old-shape",
  # Mews sends a full timestamp on some mappings and a bare date on others
  "12": {"id":"b12","first":"Iso","last":"Stamp","arrive":today+"T04:00:00Z",
         "depart":plus(2)+"T02:00:00Z","adults":2}
}

PRE = {
  # filled in from the guest's phone, not yet confirmed at the desk
  "b4":  {"at":"2026-08-16T10:00:00Z","dining":True,"pax":2,
          "diets":["Nut allergy"],"dnote":"the daughter, severe",
          "arriveSlot":"16","purpose":["Celebration"],"approach":"most",
          "occasion":"anniversary","wellness":True,"wellDay":plus(1),"wellTime":"late morning",
          "note":"quiet villa please"},
  "b9":  {"at":"2026-08-16T11:00:00Z","dining":False,"noDiets":True,
          "arriveSlot":"before2","arriveNote":"flight lands 11am"},
  # confirmed at the desk
  "b7":  {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:00:00Z","dining":True,"pax":2},
  "b11": {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:05:00Z","dining":False},
  # opened the form, gave allergies, left the dinner question alone
  "b12": {"at":"2026-08-16T09:00:00Z","diets":["Gluten free"],"arriveSlot":"15"},
  # opened the pre-arrival link and never submitted it
  "b14": {"openedAt":"2026-08-16T08:00:00Z"}
}

WRITES = []
STATE = {"fail": False}

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
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u: body = "null"
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE[k]) if k in PRE else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.route("**/gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8964/front-desk.html")
        pg.wait_for_timeout(1600)
        return pg

    # ── who is an arrival ───────────────────────────────────────
    pg = board()
    villas = pg.evaluate("()=>[...document.querySelectorAll('.arr')].map(e=>e.dataset.villa)")
    ck("a guest mid stay is not an arrival, though they are in house tonight",
       "3" not in villas)
    ck("an entry in the older bare id shape is ignored rather than crashing",
       "5" not in villas)
    ck("a full ISO timestamp counts as arriving today, same as a bare date",
       "12" in villas)
    # The list is two sections, to confirm then confirmed, so it is ordered by
    # villa WITHIN each section rather than globally.
    todo = pg.evaluate("()=>[...document.querySelectorAll('.arr')].filter(e=>!e.className.includes('is-done')).map(e=>e.dataset.villa)")
    doneV = pg.evaluate("()=>[...document.querySelectorAll('.arr.is-done')].map(e=>e.dataset.villa)")
    # Slots are stored as keys, so the order is exact rather than parsed:
    # b9 before 2pm, b12 3pm, b4 4pm, then the guests who gave no time.
    ck("arrivals are ordered by the slot they chose",
       todo[:3] == ["9", "12", "4"])
    ck("and guests who gave no time sort last, by villa",
       todo[3:] == sorted(todo[3:], key=int))
    ck("and the ones still to do come first, because that is the job",
       villas == todo + doneV)
    # Arrived is a fraction: the number alone says nothing without the total.
    ck("arrived reads as a fraction of the day's arrivals",
       pg.evaluate("()=>nArr.textContent") == "2/7")
    # six arrivals, of which villas 7 and 11 are already confirmed
    # Of everyone arriving today, how many are eating tonight.
    ck("dining, not dining and not sure are counted separately",
       [pg.evaluate("()=>nIn.textContent"), pg.evaluate("()=>nOut.textContent"),
        pg.evaluate("()=>nUn.textContent")] == ["2", "2", "3"])
    ck("and the three add up to the day, so nobody looks for a missing one",
       sum(int(pg.evaluate("()=>%s.textContent" % i)) for i in ("nIn","nOut","nUn")) == 7)
    ck("they carry the same three colours as the fork icons",
       pg.evaluate("()=>[nIn.className,nOut.className,nUn.className].join()")
       == "stat-n dine,stat-n nodine,stat-n unsure")
    ck("the sections read as what the guest does, not what reception does",
       [e.strip() for e in pg.evaluate(
        "()=>[...document.querySelectorAll('.seclabel')].map(e=>e.textContent)")]
       == ["Arriving", "Arrived"])


    # ── no pills: every state is said once, by tint, section or icon ──
    # A pill repeating the tint makes the reader check whether the two agree
    # instead of reading one.
    ck("no row carries a pill at all",
       pg.evaluate("()=>document.querySelectorAll('.arr .pill').length") == 0)
    ck("and no paper icon either, since an amber row already says no form",
       pg.evaluate("()=>document.querySelectorAll('.arr .paper').length") == 0)
    # Before a guest arrives, the ETA is the fact reception plans around.
    ck("the arrival slot shows on the list, without opening anything",
       "4pm" in pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"] .arr-s').textContent"))
    ck("and carries more weight than the rest of the line",
       pg.evaluate("()=>!!document.querySelector('.arr[data-villa=\"4\"] .arr-s .eta')"))
    # Everyone here arrives today, so the range's first half is the same on
    # every row. How long they stay is the part that differs.
    ck("the row says how many nights, not a date range",
       "4 nights" in pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"] .arr-s').textContent"))
    ck("and one night is singular",
       "1 night" in pg.evaluate("()=>document.querySelector('.arr[data-villa=\"14\"] .arr-s').textContent"))
    ck("the full range is still in the sheet for anyone who needs the date",
       (pg.locator('.arr[data-villa="4"]').click(), pg.wait_for_timeout(300),
        pg.locator('.sum-btns button[data-act="edit"]').click(), pg.wait_for_timeout(400),
        "Mon 17-Fri 21" in pg.locator("#sheet").inner_text())[4])
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)
    # closing the sheet leaves the summary open behind it; collapse it so the
    # tests after this one start from a clean board
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    ck("but the note explaining an odd arrival stays off the row",
       "flight lands" not in pg.evaluate("()=>document.querySelector('.arr[data-villa=\"9\"] .arr-s').textContent"))


    # Whether they are eating, readable without opening anything.
    def fork(v):
        return pg.evaluate("()=>{const e=document.querySelector('.arr[data-villa=\"%s\"] .fork');"
                           "return e?e.className:null;}" % v)
    ck("a guest opted in for dinner reads green", fork("4") == "fork in")
    ck("one who declined reads red", fork("9") == "fork out")
    ck("a confirmed guest carries it too", fork("7") == "fork in")
    ck("and a confirmed decline", fork("11") == "fork out")
    # There is nothing to report about a guest who has not answered, and an
    # icon there would be an answer we do not have.
    # Every question on the form is mandatory, so a submitted form always has a
    # dining answer and grey can only mean no form. No form is a tentative yes,
    # which the kitchen cooks for, so it earns an icon rather than a blank.
    ck("a guest with no form still carries a fork, greyed", fork("2") == "fork un")
    # Grey is a real answer: they filled the form in and left dinner open.
    ck("and so does one who opened the link and stopped", fork("14") == "fork un")


    # Opened the pre-arrival link and did not finish. A different message from
    # the nightly dinner invite the Reservations board tracks: an icon on one
    # board says nothing about the other.
    def seen(v):
        return pg.evaluate("()=>!!document.querySelector('.arr[data-villa=\"%s\"] .seen')" % v)
    ck("a guest who opened the link and stopped shows it", seen("14"))
    ck("a guest who never opened it carries no link icon, only the grey fork",
       not seen("2") and fork("2") == "fork un")
    ck("and one who submitted has nothing left to say", not seen("4"))

    # The tint answers the thing reception scans for.
    def tint(v):
        return pg.evaluate("()=>document.querySelector('.arr[data-villa=\"%s\"]').className" % v)
    ck("a completed form tints the row green", "done-form" in tint("4"))
    ck("one still to do tints it amber", "todo-form" in tint("2"))
    ck("opened but unfinished still counts as to do", "todo-form" in tint("14"))

    # An opened-only record is not a form, so there is nothing to read back.
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(350)
    ck("an opened-only record drops down no summary",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0)
    ck("it opens the form instead", pg.evaluate("()=>backdrop.className.indexOf('show')>-1"))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)

    # The slot order has to be exact, since ordering the day depends on it.
    ck("the six slots run earliest to latest",
       pg.evaluate("()=>ETA_SLOTS.map(s=>s[0]).join()")
       == "before2,14,15,16,17,after5")
    ck("the row uses the short form so it does not truncate",
       pg.evaluate("()=>ETA_SLOTS.map(s=>s[2]).join()")
       == "Before 2pm,2pm,3pm,4pm,5pm,After 5pm")
    ck("and only the two open ended ones demand a note",
       pg.evaluate("()=>ETA_SLOTS.filter(s=>s[3]).map(s=>s[0]).join()")
       == "before2,after5")

    # ── tapping a completed row reads the answers back ──────────
    # Reception says them out loud, the guest agrees or does not, and one of
    # two buttons follows. No sheet unless something has to change.
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("tapping a completed row drops down their answers",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 1)
    ck("and does not open the edit sheet",
       pg.evaluate("()=>backdrop.className.indexOf('show')<0"))
    sumtxt = pg.locator(".sum").inner_text()
    ck("the dinner answer reads as a sentence", "Dining" in sumtxt and "2 guests" in sumtxt)
    ck("the dietary and whose it is", "Nut allergy" in sumtxt and "the daughter" in sumtxt)
    ck("the arrival time they gave", "4pm" in sumtxt)
    ck("the occasion", "anniversary" in sumtxt)
    ck("purpose, in words rather than a stored code", "Celebration" in sumtxt)
    # A wellness interest with no day or time is a note to nobody. When they
    # gave one, it reads beside the answer rather than needing the form opened.
    ck("wellness carries the day and time they chose, on the same line",
       "Interested" in sumtxt and "late morning" in sumtxt and
       ["Interested" in l and "late morning" in l for l in sumtxt.split("\n")].count(True) == 1)
    ck("dining approach, in words rather than 'most'",
       "Dining in most nights" in sumtxt)
    ck("and both ways out", pg.evaluate(
       "()=>[...document.querySelectorAll('.sum-btns button')].map(b=>b.dataset.act).join()")
       == "edit,confirm")
    ck("only one summary is ever open",
       (pg.locator('.arr[data-villa="9"]').click(), pg.wait_for_timeout(300),
        pg.evaluate("()=>document.querySelectorAll('.sum').length"))[2] == 1)
    ck("tapping the same row again closes it",
       (pg.locator('.arr[data-villa="9"]').click(), pg.wait_for_timeout(300),
        pg.evaluate("()=>document.querySelectorAll('.sum').length"))[2] == 0)

    # ── the sheet is edit, not create ───────────────────────────
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("edit opens the sheet on the villa tapped",
       "VILLA 4" in pg.locator("#sheet h3").inner_text().upper())
    ck("the guest's own answers are already there: dining",
       pg.evaluate("()=>sDin.className==='on'"))
    ck("their covers", pg.evaluate(
       "()=>[...document.querySelectorAll('#paxRow .pax')].find(e=>e.className.indexOf('on')>-1).textContent")=="2")
    ck("their dietary", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')].some(e=>e.textContent==='Nut allergy'&&e.className.indexOf('on')>-1)"))
    ck("the note about whose allergy it is",
       pg.evaluate("()=>fDnote.value") == "the daughter, severe")
    # ETA is not editable here: the guest is standing at the desk, so there is
    # nothing left to estimate. It is shown if they told us earlier.
    ck("the arrival time is shown, not offered for editing",
       pg.evaluate("()=>!document.getElementById('fArrive')") and
       "arrive approx 4pm" in pg.locator("#sheet").inner_text())
    ck("their special occasion", pg.evaluate("()=>fOcc.value") == "anniversary")
    ck("their free text", pg.evaluate("()=>fNote.value") == "quiet villa please")
    ck("purpose of visit, which is advisory and never drives logic",
       pg.evaluate("()=>[...document.querySelectorAll('#pChips .chip')]"
                   ".some(e=>e.textContent==='Celebration'&&e.className.indexOf('on')>-1)"))
    ck("and the wellness answer", pg.evaluate("()=>wYes.className==='on'"))
    ck("a day and a time appear once they are interested",
       pg.evaluate("()=>wWrap.style.display!=='none'"))
    ck("the days offered are only the nights they are here",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 5)
    ck("covers are shown because they are dining",
       pg.evaluate("()=>paxWrap.style.display!=='none'"))

    # ── confirming ──────────────────────────────────────────────
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("confirming writes the guest's own node", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("as a PATCH, so a field this screen does not carry survives",
           w[0]["m"] == "PATCH")
        ck("it is stamped confirmed", bool(body.get("confirmedAt")))
        ck("the answers go with it", body["dining"] is True and body["pax"] == 2
           and body["diets"] == ["Nut allergy"])
        ck("and 'at' is NOT overwritten, so it still means when the answers first existed",
           "at" not in body)
    ck("the sheet closes", pg.evaluate("()=>backdrop.className.indexOf('show')<0"))
    # Confirmation is the section, and the fork is the answer.
    ck("and the guest moves into the confirmed section without a reload",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") > -1)
    ck("with the fraction following", pg.evaluate("()=>nArr.textContent") == "3/7")
    pg.close()

    # ── a guest with no form goes straight to the form ──────────
    # There is nothing to read back, so a summary would say nothing.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    ck("a guest with no form skips the summary and opens the form",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0 and
       pg.evaluate("()=>backdrop.className.indexOf('show')>-1"))
    ck("a guest with no form gets the same fields, not a different flow",
       pg.evaluate("()=>!!document.getElementById('fDnote')&&!!document.getElementById('fOcc')"
                   "&&!!document.getElementById('sDin')&&!!document.getElementById('wYes')"))
    ck("and is told there is nothing to work from",
       "No pre-arrival form" in pg.locator("#sheet").inner_text())
    ck("nothing is preselected", pg.evaluate("()=>sDin.className===''&&sOut.className===''"))
    ck("covers stay hidden until someone says they are dining",
       pg.evaluate("()=>paxWrap.style.display==='none'"))
    # "none to declare" is a positive answer, not the absence of one
    pg.evaluate("()=>[...document.querySelectorAll('#dNone .chip')][0].click()")
    pg.locator("#sOut").click()
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]
    ck("a guest filled in at the desk saves the same shape", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("no allergies is recorded as an answer, not as an empty list",
           body["noDiets"] is True)
        ck("not dining is zero covers", body["dining"] is False and body["pax"] == 0)
        ck("and 'at' IS set, because the answers did not exist before",
           bool(body.get("at")))
    pg.close()

    # ── confirming from the summary, without opening anything ───
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b9/prearrival" in x["u"]]
    ck("confirm from the summary saves without opening the form", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("it saves exactly what was read back, not a blank",
           body["dining"] is False and body["noDiets"] is True)
        ck("stamped confirmed", bool(body.get("confirmedAt")))
    ck("and the summary closes behind it",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0)
    ck("the guest is now confirmed", pg.evaluate(
       "()=>document.querySelector('.arr[data-villa=\"9\"]').className").find("is-done") > -1)
    pg.close()

    # ── a failed save must not look like success ────────────────
    STATE["fail"] = True
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(600)
    ck("a rejected save says so", "Could not save" in pg.locator("#errBar").inner_text())
    ck("and the guest is put back rather than left looking confirmed",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"9\"]').className")
       .find("is-done") == -1)
    STATE["fail"] = False
    pg.close()


    # ── moving between days ─────────────────────────────────────
    # Wired by initDateNav in nala-shared.js, the same header every staff page
    # uses. Tested here because "the shared thing handles it" is exactly the
    # claim that turns out to be wrong on the one page nobody checked.
    pg = board()
    ck("Today is dimmed while already on today",
       pg.evaluate("()=>dToday.disabled === true"))
    pg.locator("#dNext").click(); pg.wait_for_timeout(1200)
    ck("forward moves the browsed date", "date=" + plus(1) in pg.url)
    ck("and Today wakes up once you have moved off it",
       pg.evaluate("()=>dToday.disabled === false"))
    ck("tomorrow has no arrivals in this fixture, and says so",
       "No arrivals" in pg.locator("#board").inner_text())
    pg.locator("#dPrev").click(); pg.wait_for_timeout(1200)
    pg.locator("#dPrev").click(); pg.wait_for_timeout(1200)
    ck("back moves it the other way", "date=" + plus(-1) in pg.url)
    pg.locator("#dToday").click(); pg.wait_for_timeout(1200)
    ck("Today returns to today and drops the parameter", "date=" not in pg.url)
    ck("and the arrivals are back",
       pg.evaluate("()=>document.querySelectorAll('.arr').length") == 7)
    pg.close()

    # ── access ──────────────────────────────────────────────────
    pg = board("housekeeping@x")
    ck("housekeeping is routed to their own board, not shown a refusal",
       pg.url.endswith("cleaners.html"))
    pg.close()
    pg = board("chef@x")
    ck("the chef has no business at the front desk",
       pg.evaluate("()=>noAccess.className.indexOf('show')>-1") or
       not pg.url.endswith("front-desk.html"))
    pg.close()

    # ── widths ──────────────────────────────────────────────────
    for w in (390, 360, 320):
        pg = board(w=w)
        ck("the board does not scroll sideways at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
        ck("nor does the summary at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
        ck("nor does the sheet at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
