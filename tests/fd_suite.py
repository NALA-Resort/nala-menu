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
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8964), Q)
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
def short(d):
    """The way the sheet writes a date: Mon 17. Built from the clock rather
    than typed, because a suite that only passes on the day it was written
    fails every following morning and teaches everyone to ignore it."""
    t = now + datetime.timedelta(days=d)
    return t.strftime("%a ") + str(t.day)
RANGE_4 = short(0) + "-" + short(4)

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STAYS = {
  "4":  {"id":"b4","first":"Robyn","last":"Williams","arrive":today,"depart":plus(4),
         "adults":2,"number":1159},
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
          "arriveSlot":"16","arriveApproved":15,"purpose":["A celebration"],"approach":"most",
          "occasion":"anniversary","wellness":True,"wellDay":plus(1),"wellTime":"late morning",
          "note":"quiet villa please"},
  "b9":  {"at":"2026-08-16T11:00:00Z","dining":False,"noDiets":True,
          "arriveSlot":"before2","arriveNote":"flight lands 11am"},
  # confirmed at the desk
  "b7":  {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:00:00Z",
          "checkedInAt":"2026-08-17T14:00:00Z","dining":True,"pax":2},
  "b11": {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:05:00Z",
          "checkedInAt":"2026-08-17T14:05:00Z","dining":False},
  # opened the form, gave allergies, left the dinner question alone
  "b12": {"at":"2026-08-16T09:00:00Z","diets":["Gluten free"],"arriveSlot":"15"},
  # opened the pre-arrival link and never submitted it
  "b14": {"openedAt":"2026-08-16T08:00:00Z"}
}

# Tonight's dish tags, written by the chef at publish. The guest's form was
# filled in days before this existed.
TAGS = {"main": ["Nut allergy"]}

# Tonight's dinner cells, keyed by villa. Seeded per test.
DINNER = {}

# The booking as Mews states it. Its villa is a single value, so it settles a
# disagreement with /stays.
PMS = {}

WRITES = []
#  The chef's list, which is the one the kitchen recognises. "Sesame allergy"
#  is one he added; it must reach the desk or a guest with it can only be
#  recorded as a typed note. "Red pepper spice" is marked this-menu-only and
#  is a warning about tonight's cooking, so it belongs on the nightly form.
DIETS = {"gf":  {"name": "Gluten free",      "active": True,  "group": "common"},
         "nut": {"name": "Nut allergy",      "active": True,  "group": "common"},
         "ses": {"name": "Sesame allergy",   "active": True,  "group": "common"},
         "chi": {"name": "Red pepper spice", "active": True,  "group": "menu"},
         "old": {"name": "Retired Entry",    "active": False, "group": "common"}}

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
    if "/dietaries" in u: body = json.dumps(DIETS)
    elif "/staff" in u: body = json.dumps(STAFF)
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/dinner/" in u: body = "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u: body = "null"
    elif "/menutags/" in u:
        body = json.dumps(TAGS) if today in u else "null"
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE[k]) if k in PRE else "null"
    elif "/bookings/" in u and "/pms" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PMS[k]) if k in PMS else "null"
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
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
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
    # Arrived counts guests checked in, not guests confirmed. Reception can
    # verify the answers on the phone the day before; the guest turns up later.
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
        RANGE_4 in pg.locator("#sheet").inner_text())[4])
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
    ck("purpose, in words rather than a stored code", "A celebration" in sumtxt)
    # A wellness interest with no day or time is a note to nobody. When they
    # gave one, it reads beside the answer rather than needing the form opened.
    ck("wellness carries the day and time they chose, on the same line",
       "Interested" in sumtxt and "late morning" in sumtxt and
       ["Interested" in l and "late morning" in l for l in sumtxt.split("\n")].count(True) == 1)
    ck("dining approach, in words rather than 'most'",
       "Dining in most nights" in sumtxt)
    ck("and three ways out: edit, confirm, or confirm and check in", pg.evaluate(
       "()=>[...document.querySelectorAll('.sum-btns button')].map(b=>b.dataset.act).join()")
       == "edit,confirm,checkin")
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
    #  The desk offered eight fixed dietaries while the guest form offered the
    #  chef's, so anything he added existed everywhere except at the one place
    #  a guest is standing in front of somebody.
    ck("a dietary the chef added reaches the desk", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')]"
       ".some(e=>e.textContent==='Sesame allergy')"))
    ck("and a retired one does not", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')]"
       ".every(e=>e.textContent!=='Retired Entry')"))
    ck("a this-menu-only dietary stays on the nightly form", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')]"
       ".every(e=>e.textContent!=='Red pepper spice')"))
    ck("and Other is still offered beside them", pg.evaluate(
       "()=>[...document.querySelectorAll('#dNone .chip')]"
       ".some(e=>e.textContent==='Other')"))
    # This used to say the arrival time was deliberately read only, on the
    # reasoning that the guest is standing at the desk so there is nothing left
    # to estimate. That is true of a guest in front of you and of nobody else:
    # a guest with no form has no arrival time at all, and one who rings to say
    # they are running late has one that is wrong. The desk can set it now,
    # with the same slots and the same words the guest was offered.
    ck("the arrival time can be set at the desk, not only read back",
       pg.evaluate("()=>!!document.getElementById('eChips')"))
    ck("and the slot the guest chose comes up already selected",
       pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
         .some(e=>/Around 4pm/.test(e.textContent) && e.className.indexOf('on')>-1)"""))
    ck("their special occasion", pg.evaluate("()=>fOcc.value") == "anniversary")
    ck("their free text", pg.evaluate("()=>fNote.value") == "quiet villa please")
    # The desk offered "Celebration" and the guest's form offered "A
    # celebration". Purpose is stored as the LABEL, not a key, so nothing
    # matched: the chip came up unselected and the next save from the desk
    # dropped the guest's answer. The guest's wording is now used on both,
    # because it is what every record written so far already holds.
    ck("purpose of visit, which is advisory and never drives logic",
       pg.evaluate("()=>[...document.querySelectorAll('#pChips .chip')]"
                   ".some(e=>e.textContent==='A celebration'&&e.className.indexOf('on')>-1)"))
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
    # Confirming alone does NOT move them: they have not arrived yet.
    ck("confirming leaves them under Arriving, because they have not arrived",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") == -1)
    ck("and the arrived count does not move either",
       pg.evaluate("()=>nArr.textContent") == "2/7")
    pg.close()

    # ── reception's approved hour, beside the guest's slot ──────
    # The guest asks, reception decides. The approved hour is its own field:
    # setting it never touches the slot the guest chose, clearing it leaves
    # that slot standing, and the desk offers every hour 11am to 11pm
    # whatever the guest answered, because a guest who chose Around 4pm and
    # rang to say half three can be set to 3pm.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the desk offers thirteen hours, 11am through 11pm",
       pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                   ".map(b=>b.textContent).join()")
       == "11am,12pm,1pm,2pm,3pm,4pm,5pm,6pm,7pm,8pm,9pm,10pm,11pm")
    ck("the approved hour comes up selected from the record",
       pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                   ".find(b=>b.className.indexOf('on')>-1).textContent") == "3pm")
    ck("with the guest's own slot still selected beside it",
       pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
         .some(e=>/Around 4pm/.test(e.textContent) && e.className.indexOf('on')>-1)"""))
    # Reception moves it to 1pm, an hour the guest's form never offers.
    pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                ".find(b=>b.textContent==='1pm').click()")
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("approving writes the hour as a number",
       len(w) == 1 and json.loads(w[0]["b"]).get("arriveApproved") == 13)
    if w:
        ck("and the guest's slot goes with it, untouched",
           json.loads(w[0]["b"])["arriveSlot"] == "16")
    # Tapping the chosen hour again is the way back, like the slot chips.
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                ".find(b=>b.className.indexOf('on')>-1).click()")
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("clearing writes null rather than omitting the key, or nothing clears",
       len(w) == 1 and "arriveApproved" in json.loads(w[0]["b"])
       and json.loads(w[0]["b"])["arriveApproved"] is None)
    if w:
        ck("and clearing leaves the guest's slot intact",
           json.loads(w[0]["b"])["arriveSlot"] == "16")
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
    ck("the guest is confirmed but still arriving", pg.evaluate(
       "()=>document.querySelector('.arr[data-villa=\"9\"]').className").find("is-done") == -1)
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





    # ── the confirmation has to reach the chef ──────────────────
    # The chef's board reads /manual, not /bookings. Without this the path
    # stops one step short: reception types "dining, two guests, nut allergy"
    # and Reservations still shows that villa as awaiting, which is the
    # handwritten sheet problem the project exists to remove.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(350)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(600)
    man = [x for x in WRITES if "/dinner/" in x["u"] and x["u"].split("/dinner/")[1].startswith(today)]
    ck("confirming writes the one dinner cell", len(man) == 1)
    if man:
        rec = json.loads(man[0]["b"])
        ck("as dining, with the covers", rec["status"] == "in" and rec["pax"] == 2)
        ck("carrying the dietaries the kitchen acts on",
           rec["diets"] == ["Nut allergy"] and "daughter" in rec["dnote"])
        ck("and the booking it belongs to, so the record knows whose it is",
           rec["bookingId"] == "b4")
        # This is what stops a guest overwriting it from their link afterwards.
        ck("stamped as set by staff", rec["by"] == "staff")
        ck("written to the night they arrive, keyed by villa",
           today in man[0]["u"] and man[0]["u"].split("/dinner/")[1].startswith(today + "/4")) 
    pg.close()

    # Not dining has to reach the board too, or the villa sits as awaiting all
    # evening and somebody chases a guest who already said no.
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(350)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(600)
    man = [x for x in WRITES if "/dinner/" in x["u"] and "/9.json" in x["u"]]
    ck("a guest who declined is put on the board as not dining", len(man) == 1)
    if man:
        rec = json.loads(man[0]["b"])
        ck("with no covers", rec["status"] == "out" and rec["pax"] == 0)
        ck("and no allergies, because they declared none",
           rec["diets"] == [] and rec["dnote"] == "")
    pg.close()

    # A confirmation the chef never sees is worse than one that visibly failed.
    STATE["fail"] = True
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(350)
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(700)
    ck("if either write is rejected the guest is put back, not left half done",
       "Could not save" in pg.locator("#errBar").inner_text() and
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") == -1)
    STATE["fail"] = False
    pg.close()



    # ── confirm and check in ────────────────────────────────────
    # Two different events. Reception can verify the answers on the phone the
    # day before; the guest arrives hours later. Only the second moves them.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(350)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("check in saves the answers like confirm does", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("stamped confirmed", bool(body.get("confirmedAt")))
        ck("and stamped arrived, which confirm alone does not",
           bool(body.get("checkedInAt")))
    ck("and moves them to Arrived on the spot",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") > -1)
    ck("with the count following", pg.evaluate("()=>nArr.textContent") == "3/7")
    pg.close()

    # This used to assert the opposite: that confirming again kept a guest
    # arrived, on the reasoning that a guest who has arrived has arrived. True
    # of guests, not of taps. The two buttons sit together, check in is the
    # big one, and there was no way back from pressing it by mistake. Confirm
    # arriving is that way back, which is what its name says.
    PRE["b4"]["checkedInAt"] = "2026-08-17T15:00:00Z"
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(350)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("confirming arriving puts an accidentally checked in guest back",
       len(w) == 1 and json.loads(w[0]["b"])["checkedInAt"] is None)
    pg.close()
    del PRE["b4"]["checkedInAt"]

    # The sheet offers the same two, since a guest with no form never sees a
    # summary at all.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    ck("the form offers check in as well as confirm",
       pg.evaluate("()=>!!document.getElementById('sCheckin')") and
       pg.evaluate("()=>!!document.getElementById('sConfirm')"))
    pg.locator("#sOut").click()
    pg.evaluate("()=>[...document.querySelectorAll('#dNone .chip')][0].click()")
    del WRITES[:]
    pg.locator("#sCheckin").click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]
    ck("and checking in from the form arrives them too",
       len(w) == 1 and bool(json.loads(w[0]["b"]).get("checkedInAt")))
    pg.close()

    # ── the bug found in testing on 17 Aug ──────────────────────
    # Reception saved a dietary at check in, the Reservations board added
    # another, and the next save from the desk wiped it. Three nodes held
    # `diets` and none of them owned it: the desk read the booking, the board
    # wrote /manual, and neither knew about the other.
    PRE["b4"]["diets"] = ["Nut allergy"]
    DINNER["4"] = {"status": "in", "pax": 2, "by": "staff",
                   "diets": ["Nut allergy", "Vegan"], "dnote": "the daughter"}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("a dietary added on the board is visible at the desk",
       "Vegan" in pg.locator(".sum").inner_text())
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="confirm"]').click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/dinner/" in x["u"] and "/4.json" in x["u"]]
    ck("and saving again at the desk does not wipe it",
       len(w) == 1 and json.loads(w[0]["b"])["diets"] == ["Nut allergy", "Vegan"])
    pg.close()
    DINNER.clear()

    # ── the allergy nobody could have flagged earlier ───────────
    # The guest answered days before tonight's menu existed, so check-in is the
    # first moment the two halves can be compared, and reception is holding the
    # menu. It warns rather than blocks: they settle it in conversation.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    sumtxt = pg.locator(".sum").inner_text()
    ck("a dietary tonight's menu contains is flagged at the desk",
       "Nut allergy" in sumtxt and "main contains" in sumtxt)
    ck("and it does not block confirming, since reception can resolve it",
       pg.evaluate("()=>!!document.querySelector('.sum-btns button[data-act=\"confirm\"]')"))
    pg.close()

    # A guest who is not dining cannot clash with tonight's menu.
    PRE["b4"]["dining"] = False
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("a guest who is not dining is never flagged",
       "contains" not in pg.locator(".sum").inner_text())
    PRE["b4"]["dining"] = True
    pg.close()

    # A dietary the chef did not tag is not a conflict. No keyword guessing,
    # same rule as the guest page.
    TAGS.clear(); TAGS.update({"dessert": ["Gluten free"]})
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("an untagged dietary is not invented into a conflict",
       "contains" not in pg.locator(".sum").inner_text())
    pg.close()
    TAGS.clear(); TAGS.update({"main": ["Nut allergy"]})

    # ── checking in needs an answer ─────────────────────────────
    # These used to be asked at every save, including Confirm arriving, which
    # meant reception could not write down what they heard across the day: a
    # dietary at nine, an arrival time at noon. The form kept none of it until
    # all of it existed, so it went on paper instead.
    #
    # They are asked at CHECK IN, the last moment anyone still can, where a
    # guest sent to their villa with no dining answer is a cover the kitchen
    # never hears about.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    del WRITES[:]
    pg.locator("#sCheckin").click(); pg.wait_for_timeout(400)
    ck("checking in a blank guest saves nothing",
       len([x for x in WRITES if "/prearrival" in x["u"]]) == 0)
    ck("and says what is missing rather than doing nothing",
       "dinner and dietaries" in pg.locator("#sMiss").inner_text())
    ck("marking the fields that need it",
       pg.evaluate("()=>diningSeg.className.indexOf('miss')>-1") and
       pg.evaluate("()=>dChips.className.indexOf('miss')>-1"))
    pg.locator("#sOut").click(); pg.wait_for_timeout(200)
    ck("answering one clears the warning", pg.evaluate(
       "()=>sMiss.className.indexOf('show')<0"))
    pg.locator("#sCheckin").click(); pg.wait_for_timeout(400)
    ck("but the other is still required",
       len([x for x in WRITES if "/prearrival" in x["u"]]) == 0 and
       "dietaries" in pg.locator("#sMiss").inner_text())
    # "None to declare" is a positive answer, so it satisfies the requirement
    pg.evaluate("()=>[...document.querySelectorAll('#dNone .chip')][0].click()")
    pg.wait_for_timeout(200)
    pg.locator("#sCheckin").click(); pg.wait_for_timeout(500)
    ck("no allergies to declare counts as having asked",
       len([x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]) == 1)
    pg.close()



    # The GUID is the key, but nobody can read a GUID out over the phone. The
    # reservation number is what staff see in Mews.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the sheet shows the Mews reservation number",
       "Mews 1159" in pg.locator("#sheet").inner_text())
    pg.close()

    # ── one party, two villas ───────────────────────────────────
    # A family booking two villas is two reservations under one group. Two rows
    # is correct: two villas, two registration cards, two sets of answers. What
    # would be wrong is showing them as strangers who share a surname.
    STAYS["6"] = {"id":"bj1","first":"Jane","last":"Smith","arrive":today,
                  "depart":plus(2),"adults":2,"groupId":"grp-jane"}
    STAYS["8"] = {"id":"bj2","first":"Jane","last":"Smith","arrive":today,
                  "depart":plus(2),"adults":2,"groupId":"grp-jane"}
    pg = board()
    villas = pg.evaluate("()=>[...document.querySelectorAll('.arr')].map(e=>e.dataset.villa)")
    ck("both villas of one party are listed, because both need checking in",
       "6" in villas and "8" in villas)
    def line(v):
        return pg.evaluate("()=>document.querySelector('.arr[data-villa=\"%s\"] .arr-s').textContent" % v)
    ck("and each says which other villa the party holds",
       "villa 8" in line("6") and "villa 6" in line("8"))
    ck("a booking on its own says nothing about a party",
       "with villa" not in line("4"))
    pg.close()

    # Three villas reads as a list, not as three separate notes.
    STAYS["10"] = {"id":"bj3","first":"Jane","last":"Smith","arrive":today,
                   "depart":plus(2),"adults":2,"groupId":"grp-jane"}
    pg = board()
    ck("three villas in one party read as a list",
       "villas 8 & 10" in pg.evaluate(
         "()=>document.querySelector('.arr[data-villa=\"6\"] .arr-s').textContent"))
    pg.close()
    for v in ("6", "8", "10"): del STAYS[v]

    # ── one booking, three villas ───────────────────────────────
    # Seen live on 17 Aug: the same guest listed in villas 13, 14 and 15. A
    # move leaves an entry behind in /stays and the Worker only clears it on
    # that booking's next event, so anything stranded earlier just sits there.
    for v in ("13", "15", "16"):
        STAYS[v] = {"id": "bmoved", "first": "Ben", "last": "Davidson",
                    "arrive": today, "depart": plus(1), "adults": 2}
    PMS["bmoved"] = {"villa": "15"}
    pg = board()
    villas = pg.evaluate("()=>[...document.querySelectorAll('.arr')].map(e=>e.dataset.villa)")
    ck("one booking gets one row, not three",
       len([v for v in villas if v in ("13","15","16")]) == 1)
    ck("and it is the villa Mews says they are in", "15" in villas)
    ck("so the arrivals count is not inflated either",
       pg.evaluate("()=>nArr.textContent").split("/")[1] == "8")
    pg.close()

    # With no pms to ask, one row is still right and three are not.
    del PMS["bmoved"]
    pg = board()
    villas = pg.evaluate("()=>[...document.querySelectorAll('.arr')].map(e=>e.dataset.villa)")
    ck("with nothing to ask, it still shows one row",
       len([v for v in villas if v in ("13","15","16")]) == 1)
    pg.close()
    for v in ("13", "15", "16"): del STAYS[v]

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

    # ── an allergy that is not on the list ──────────────────────
    # Reported 19 Aug: dietary notes were not saving. The list of pills does
    # not cover every allergy, an answer is required, so the only way past was
    # "No allergies to declare" -- which is a lie, and which also wipes the
    # note the real allergy had just been typed into, because nothing to
    # declare means nothing to write down.
    pg = board()
    pg.locator("#board .arr").first.click(); pg.wait_for_timeout(600)
    # A guest who already filled the form in gets their answers read back
    # first, so the form is one step further in for them.
    if pg.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
        pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
        pg.wait_for_timeout(600)
    pg.locator("#sDin").click(); pg.wait_for_timeout(200)

    extra = pg.evaluate("()=>[...document.querySelectorAll('#dNone button')]"
                        ".map(b=>b.textContent.trim())")
    print("   answers beside the list:", extra)
    ck("there is a way to say the allergy is not on the list", "Other" in extra)
    # The two answers that are not on the list are opposites: one says there
    # is nothing to write down, the other says the answer is only in the note.
    ck("and it sits beside 'no allergies', not inside the list",
       "No allergies to declare" in extra and len(extra) == 2)

    pg.evaluate("()=>[...document.querySelectorAll('#dNone button')]"
                ".find(b=>b.textContent.trim()==='Other').click()")
    pg.wait_for_timeout(250)
    ck("choosing it clears 'no allergies', since they contradict",
       pg.evaluate("""()=>[...document.querySelectorAll('#dNone button')]
         .find(b=>/^No allergies/.test(b.textContent)).className.indexOf('on')<0"""))

    # Other with an empty note tells the kitchen nothing, and looks like an
    # answer, which is worse than no answer at all.
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(700)
    ck("'Other' with an empty note does not save", not WRITES)
    ck("and says what is actually needed",
       "notes" in pg.evaluate("()=>document.getElementById('sMiss').textContent").lower())

    pg.fill("#fDnote", "Severe sesame allergy")
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(900)
    saved = [json.loads(x["b"]) for x in WRITES if x["b"]]
    print("   saved:", [(d.get("diets"), d.get("dnote")) for d in saved])
    ck("with a note it saves, and the note survives",
       bool(saved) and all(d.get("dnote") == "Severe sesame allergy" for d in saved))
    # Stored as an ordinary dietary, so the chef's board, the sheet and the
    # rules need no changes: they already carry a list of strings.
    ck("and 'Other' rides along as an ordinary dietary",
       all(d.get("diets") == ["Other"] for d in saved))
    ck("without claiming there is nothing to declare",
       all(not d.get("noDiets") for d in saved))
    pg.close()

    # ── the way back from an accidental check in ────────────────
    # The two buttons sit together and check in is the big one, so it gets
    # pressed by mistake. checkedInAt used to be set and never cleared, on the
    # reasoning that a guest who has arrived has arrived, which is true of
    # guests and not of taps.
    ARRIVED = dict(PRE_FULL) if "PRE_FULL" in dir() else None
    arrived_pre = {"at": now.isoformat(), "dining": True, "pax": 2,
                   "diets": ["Gluten free"], "noDiets": False,
                   "confirmedAt": now.isoformat(),
                   "checkedInAt": now.isoformat()}
    def arrived_fb(route, request):
        u = request.url
        if request.method not in ("PUT", "PATCH", "DELETE") and "/prearrival" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(arrived_pre)); return
        fb(route, request)
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.add_init_script(SDK)
    pg.add_init_script("window.__EMAIL=%s;" % json.dumps("staff@x"))
    pg.route("**firebasedatabase.app/**", arrived_fb)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.goto("http://localhost:8964/front-desk.html"); pg.wait_for_timeout(1700)

    # Every guest reads as arrived under this fixture, so the assertions name
    # the one villa being acted on rather than asking whether ANY row is
    # arrived, which would be true either way and prove nothing.
    villa = pg.evaluate("()=>document.querySelector('#board .arr').dataset.villa")
    ck("the guest being acted on starts out marked as arrived",
       pg.evaluate("(v)=>document.querySelector('.arr[data-villa=\"'+v+'\"]')"
                   ".className.indexOf('is-done')>-1", villa))
    pg.evaluate("()=>document.querySelector('#board .arr').click()")
    pg.wait_for_timeout(700)
    labels = pg.evaluate("()=>[...document.querySelectorAll('.sum-btns button')]"
                         ".map(b=>b.dataset.act+':'+b.textContent.trim())")
    print("   summary buttons:", labels)
    # Always the same words: it is an action, not a state. A label that
    # changed to "Confirmed" read as finished and gave no hint of a way back.
    ck("the button says where it puts them, not that they are done",
       "confirm:Confirm arriving" in labels)

    del WRITES[:]
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=confirm]').click()")
    pg.wait_for_timeout(900)
    sent = [json.loads(x["b"]) for x in WRITES if x["b"] and "/prearrival" in x["u"]]
    ck("confirming arriving clears the check in",
       bool(sent) and all("checkedInAt" in d and d["checkedInAt"] is None for d in sent))
    ck("and that guest goes back to the arriving list",
       pg.evaluate("(v)=>{const e=document.querySelector('.arr[data-villa=\"'+v+'\"]');"
                   "return !!e && e.className.indexOf('is-done')<0;}", villa))
    # The answers are still confirmed: only where the guest is has changed.
    ck("without throwing away the answers that were confirmed",
       bool(sent) and all(d.get("confirmedAt") for d in sent))
    pg.close()

    # ── adding what you hear, when you hear it ──────────────────────────
    # The required answers used to be required at every save, so reception
    # could not write down a dietary at nine and an arrival time at noon: the
    # form refused to keep any of it until all of it existed, and it went on
    # paper instead, which is the thing this screen replaces.
    #
    # They are required at CHECK IN, which is the last moment anyone can still
    # ask, and where a guest sent to their villa with no dining answer is a
    # cover the kitchen never hears about.
    # Villa 14 has a stay and no pre-arrival at all, so nothing has been
    # answered for it. Earlier blocks answer villa 2, and a test that inherits
    # another test's answers is testing the order they ran in.
    PRE.pop("b14", None)
    pg = board()
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(600)
    if pg.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
        pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
        pg.wait_for_timeout(600)

    pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
        .find(b=>/Around 3pm/.test(b.textContent)).click()""")
    pg.wait_for_timeout(200)
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(900)
    saved = [json.loads(x["b"]) for x in WRITES if x["b"] and "/prearrival" in x["u"]]
    ck("an arrival time alone can be saved, with nothing else answered",
       bool(saved) and saved[0].get("arriveSlot") == "15")
    # No dining answer, no dinner cell. The cell has to say in or out and there
    # is no third value, so writing one for a guest nobody has asked yet puts
    # them on the kitchen's board as NOT dining: a decision nobody made.
    ck("and no dinner cell is written for a guest nobody has asked yet",
       not [x for x in WRITES if "/dinner/" in x["u"]])
    pg.close()

    # Check in still insists, because it is the last moment to ask.
    PRE.pop("b14", None)
    pg = board()
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(600)
    if pg.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
        pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
        pg.wait_for_timeout(600)
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sCheckin').click()")
    pg.wait_for_timeout(700)
    ck("checking in with nothing answered saves nothing", not WRITES)
    ck("and says what is still needed",
       pg.evaluate("()=>document.getElementById('sMiss').textContent").strip() != "")

    # The one check that survives a partial save: Other means the answer is in
    # the note, so Other with an empty note is not an incomplete answer, it is
    # a wrong one. It tells the kitchen there is something to know and never
    # says what.
    pg.evaluate("""()=>[...document.querySelectorAll('#dNone button')]
        .find(b=>b.textContent.trim()==='Other').click()""")
    pg.wait_for_timeout(250)
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(700)
    ck("even a partial save refuses Other with an empty note", not WRITES)
    pg.fill("#fDnote", "Severe sesame allergy")
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(900)
    ck("and keeps it once the note is there", bool(WRITES))
    pg.close()

    # ── the internal note ───────────────────────────────────────────────
    # The one note a guest must never see, which is why it does not live under
    # the booking: /bookings has read set to true so the pre-arrival form can
    # read it without signing in, and a note about a guest stored there would
    # be one URL away from the guest it is about.
    INTERNAL = {"b4": {"fromMews": "Complained about noise last stay"}}
    def note_fb(route, request):
        u = request.url
        if request.method not in ("PUT", "PATCH", "DELETE") and "/internal/b4" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(INTERNAL["b4"])); return
        fb(route, request)

    def desk_as(email):
        pgx = b.new_page(viewport={"width": 390, "height": 900})
        pgx.add_init_script(SDK)
        pgx.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pgx.route("**firebasedatabase.app/**", note_fb)
        pgx.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pgx.goto("http://localhost:8964/front-desk.html")
        pgx.wait_for_timeout(1700)
        pgx.locator('.arr[data-villa="4"]').click(); pgx.wait_for_timeout(500)
        if pgx.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
            pgx.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
            pgx.wait_for_timeout(900)
        return pgx

    pg = desk_as("staff@x")
    ck("a manager is offered the internal note",
       pg.evaluate("()=>!!document.getElementById('fInternal')"))
    # Seeded from Mews and shown, which is the point of reading it at all: the
    # two systems used to hold different facts and neither showed the other's.
    ck("and it arrives holding what Mews said",
       "noise" in (pg.evaluate("()=>document.getElementById('fInternal').value") or ""))

    # Written only when it changed, so opening a sheet and closing it does not
    # stamp an edit nobody made.
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(800)
    ck("closing without touching it writes nothing",
       not [x for x in WRITES if "/internal/" in x["u"]])
    pg.close()

    pg = desk_as("staff@x")
    pg.fill("#fInternal", "Do not seat near the kitchen")
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(900)
    wrote = [json.loads(x["b"]) for x in WRITES if "/internal/" in x["u"] and x["b"]]
    ck("an edit is saved to its own node, away from the booking",
       bool(wrote) and wrote[0].get("note") == "Do not seat near the kitchen")
    # The staff key, not the name: a rename in Settings has to carry, which is
    # the lesson the Cleans board learned the hard way.
    ck("recording who edited it, by key",
       bool(wrote) and wrote[0].get("editedBy") == "staff@x")
    # Its own write, not part of the both-or-neither pair: management's private
    # record failing must not roll back the guest's answers.
    ck("and it does not ride along with the guest's answers",
       any("/prearrival" in x["u"] for x in WRITES))
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
