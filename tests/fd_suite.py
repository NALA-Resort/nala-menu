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
         "manager@x": {"name": "Manager", "role": "manager"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

STAYS = {
  # b4 carries an AU mobile (confidence tick), b9 a +1 number (honestly
  # unsure), and b2 none at all: the three states the number row can show.
  "4":  {"id":"b4","first":"Robyn","last":"Williams","arrive":today,"depart":plus(4),
         "adults":2,"number":1159,"phone":"+61 411 222 333"},
  "9":  {"id":"b9","first":"Konstantinos","last":"Papadopoulos","arrive":today,"depart":plus(2),"adults":4,
         "phone":"+1 415 555 2671"},
  "2":  {"id":"b2","first":"James","last":"Fisher","arrive":today,"depart":plus(6),"adults":2},
  "7":  {"id":"b7","first":"Mark","last":"Whitfield","arrive":today,"depart":plus(3),"adults":2},
  "11": {"id":"b11","first":"Priya","last":"Raghunathan","arrive":today,"depart":plus(5),"adults":3},
  "14": {"id":"b14","first":"Ann","last":"Brown","arrive":today,"depart":plus(1),"adults":1},
  "6":  {"id":"b6","first":"Nadia","last":"Okonkwo","arrive":today,"depart":plus(3),"adults":2},
  "8":  {"id":"b8","first":"Tomas","last":"Lind","arrive":today,"depart":plus(2),"adults":2},
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
          "companion":"Imogen Clarke",
          "arriveSlot":"16","arriveApproved":15,"purpose":["A celebration"],"approach":"most",
          "occasion":"anniversary","wellness":True,"wellDay":plus(1),"wellTime":"late morning",
          "note":"quiet villa please"},
  # The suite's completed booking, and what the summary tests open. It needs
  # all three mandatory answers or formState calls it incomplete - which,
  # since 1 Sep, means a tap opens the form rather than the summary.
  "b9":  {"at":"2026-08-16T11:00:00Z","dining":False,"noDiets":True,
          "wellness":False,
          "arriveSlot":"before2","arriveNote":"flight lands 11am"},
  # confirmed at the desk
  "b7":  {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:00:00Z",
          "checkedInAt":"2026-08-17T14:00:00Z","dining":True,"pax":2},
  "b11": {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:05:00Z",
          "checkedInAt":"2026-08-17T14:05:00Z","dining":False},
  # opened the form, gave allergies, left the dinner question alone
  "b12": {"at":"2026-08-16T09:00:00Z","diets":["Gluten free"],"arriveSlot":"15"},
  # opened the pre-arrival link and never submitted it
  "b14": {"openedAt":"2026-08-16T08:00:00Z"},
  # started the form and stopped partway. Possible since the guest page began
  # saving each page as it is left: real answers, no `at`, and the rest still
  # unasked. Its own villa rather than villa 2's, because villa 2 is this
  # suite's guest-with-no-form and three other checks lean on that.
  "b6":  {"openedAt":"2026-08-16T07:00:00Z","arriveSlot":"15",
          "dining":False,"noDiets":True},
  # reception approved a time on the telephone for a guest who never touched
  # the form. The desk's answer, not the guest's, so it must not on its own
  # make a form look started.
  "b8":  {"arriveApproved":15}
}

# Tonight's dish tags, written by the chef at publish. The guest's form was
# filled in days before this existed.
TAGS = {"main": ["Nut allergy"]}

# Tonight's dinner cells, keyed by villa. Seeded per test.
DINNER = {}

# The treatments at /spa/<booking>, seeded per test: the Wellness row reads
# these first and falls back to the form only while no record answers it.
SPADB = {}

# The booking as Mews states it. Its villa is a single value, so it settles a
# disagreement with /stays. b4's companion is the decoy the guest's own typed
# name must beat; b9's is a name only Mews knows, which must still read back.
PMS = {"b4": {"villa": "4", "companion": "Wrong Name"},
       "b9": {"villa": "9", "companion": "Eleni Papadopoulou"}}

WRITES = []
FIXES = {}   # bookingId -> the /phonefix record, persisted across the stub
#  The chef's list, which is the one the kitchen recognises. "Sesame allergy"
#  is one he added; it must reach the desk or a guest with it can only be
#  recorded as a typed note. "Red pepper spice" is marked this-menu-only and
#  is a warning about tonight's cooking, so it belongs on the nightly form.
DIETS = {"gf":  {"name": "Gluten free",      "active": True,  "group": "common"},
         "nut": {"name": "Nut allergy",      "active": True,  "group": "common"},
         "ses": {"name": "Sesame allergy",   "active": True,  "group": "common"},
         "chi": {"name": "Red pepper spice", "active": True,  "group": "menu"},
         "old": {"name": "Retired Entry",    "active": False, "group": "common"}}

# The admin's flag list, as flags.html writes it, with one archived entry
# that must never be offered as a chip; and the ticks per booking, as this
# page writes them to /bookflags.
FLAGS = {"VIP": {"name": "VIP", "active": True},
         "Travel agent": {"name": "Travel agent", "active": True},
         "Breakfast included": {"name": "Breakfast included", "active": True},
         "Honeymoon": {"name": "Honeymoon", "active": False}}
BOOKFLAGS = {}

STATE = {"fail": False}

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        #  /phonefix persists, because the fix flow reloads and must see it.
        if m == "PUT" and "/phonefix/" in u:
            FIXES[u.split("/phonefix/")[1].split(".json")[0]] = \
                json.loads(request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/phonefix/" in u:
        bid = u.split("/phonefix/")[1].split(".json")[0]
        body = json.dumps(FIXES[bid]) if bid in FIXES else "null"
    elif "/dietaries" in u: body = json.dumps(DIETS)
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
    elif "/bookflags/" in u:
        k = u.split("/bookflags/")[1].split(".json")[0]
        body = json.dumps(BOOKFLAGS[k]) if k in BOOKFLAGS else "null"
    elif "/spa/" in u:
        k = u.split("/spa/")[1].split(".json")[0]
        body = json.dumps(SPADB[k]) if k in SPADB else "null"
    elif "/flags" in u: body = json.dumps(FLAGS)
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
    # b9 before 2pm, then 3pm from b6 and b12, then b4 at 4pm, then the guests
    # who gave no time. Villa 6's answer counts even though it was left on a
    # form the guest never finished: a stated time is a stated time.
    ck("arrivals are ordered by the slot they chose",
       todo[:4] == ["9", "6", "12", "4"])
    ck("and guests who gave no time sort last, by villa",
       todo[4:] == sorted(todo[4:], key=int))
    ck("and the ones still to do come first, because that is the job",
       villas == todo + doneV)
    # Arrived is a fraction: the number alone says nothing without the total.
    # Arrived counts guests checked in, not guests confirmed. Reception can
    # verify the answers on the phone the day before; the guest turns up later.
    ck("arrived reads as a fraction of the day's arrivals",
       pg.evaluate("()=>nArr.textContent") == "2/9")
    # nine arrivals, of which villas 7 and 11 are already checked in
    # Of everyone arriving today, how many are eating tonight.
    ck("dining, not dining and not sure are counted separately",
       [pg.evaluate("()=>nIn.textContent"), pg.evaluate("()=>nOut.textContent"),
        pg.evaluate("()=>nUn.textContent")] == ["2", "3", "4"])
    ck("and the three add up to the day, so nobody looks for a missing one",
       sum(int(pg.evaluate("()=>%s.textContent" % i)) for i in ("nIn","nOut","nUn")) == 9)
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
    # Big enough to read at a glance. Asked for by the owner 28 Aug: at 19px
    # it was smaller than the villa number beside it while carrying the one
    # fact the row exists to show at speed. Asserted in rendered pixels, not
    # a class, because the class cannot say how big the stylesheet drew it.
    #  And the right colour, read from the pixels rather than the class.
    #  The class check above passed for a day while all three forks were
    #  drawn BLACK: the conversion had dropped this page's --dine and
    #  --nodine, and an undefined custom property does not fall back, it
    #  computes to nothing. The classes were right the whole time. The
    #  reasoning on the size assertion below - "the class cannot say how
    #  big the stylesheet drew it" - is exactly as true of colour.
    forkcol = pg.evaluate("""()=>{const probe=v=>{const e=document.createElement('span');
        e.style.color='var('+v+')';document.body.appendChild(e);
        const c=getComputedStyle(e).color;e.remove();return c;};
      const f=c=>{const e=document.querySelector('.arr .fork.'+c+' svg');
        return e?getComputedStyle(e).fill:null;};
      return {in:f('in'), out:f('out'), un:f('un'),
              dine:probe('--dine'), nodine:probe('--nodine')};}""")
    print("   fork colours:", forkcol)
    ck("a fork for a guest who is dining wears the dining colour",
       forkcol["in"] == forkcol["dine"])
    ck("and one for a guest who is not wears the not-dining colour",
       forkcol["out"] == forkcol["nodine"])
    ck("and nobody has answered draws no fork to colour at all",
       forkcol["un"] is None)

    ck("the fork is big enough to read across a desk",
       pg.evaluate("()=>{const e=document.querySelector('.arr .fork');"
                   "const r=e.getBoundingClientRect();"
                   "return Math.round(r.width);}") >= 26)
    ck("a guest opted in for dinner reads green", fork("4") == "fork in")
    ck("one who declined reads red", fork("9") == "fork out")
    ck("a confirmed guest carries it too", fork("7") == "fork in")
    ck("and a confirmed decline", fork("11") == "fork out")
    # There is nothing to report about a guest who has not answered, and an
    # icon there would be an answer we do not have.
    # Every question on the form is mandatory, so a submitted form always has a
    # dining answer and grey can only mean no form. No form is a tentative yes,
    # which the kitchen cooks for, so it earns an icon rather than a blank.
    #  Was "still carries a fork, greyed". Ruled by the owner 29 Aug: a solid
    #  grey knife and fork does not say "nobody has answered", it says
    #  something the reader has to decode. Only dining and not dining draw.
    ck("a guest with no form carries no fork at all", fork("2") is None)
    # Grey is a real answer: they filled the form in and left dinner open.
    ck("and neither does one who opened the link and stopped", fork("14") is None)


    # Opened the pre-arrival link and did not finish. A different message from
    # the nightly dinner invite the Reservations board tracks: an icon on one
    # board says nothing about the other.
    def seen(v):
        return pg.evaluate("()=>!!document.querySelector('.arr[data-villa=\"%s\"] .seen')" % v)
    ck("a guest who opened the link and stopped shows it", seen("14"))
    ck("a guest who never opened it carries no link icon, only the grey fork",
       not seen("2") and fork("2") is None)
    ck("and one who submitted has nothing left to say", not seen("4"))

    # ── a dinner set on the Reservations board reaches this list ──────
    # Found 4 Sep: the row's fork and the three counters read the raw form
    # (r.pre.dining) while this same page's summary, edit sheet and check-in
    # save all read answersOf - the desk's ONE merged reading, cell over
    # form. So a dinner reception set on the Reservations board, which
    # writes only the cell, left the row forkless here and counted Not
    # sure: three readings of one guest, two of them right. The fork and
    # the counters answer to answersOf now, like everything else.
    DINNER["2"] = {"status": "in", "pax": 2, "by": "staff", "at": "x"}
    DINNER["9"] = {"status": "in", "pax": 4, "by": "staff", "at": "x"}
    pgc = board()
    forkc = lambda v: pgc.evaluate(
        "()=>{const e=document.querySelector('.arr[data-villa=\"%s\"] .fork');"
        "return e?e.className:null;}" % v)
    ck("a cell with no form behind it draws the fork",
       forkc("2") == "fork in")
    ck("the cell outranks the form on the row, exactly as it does in the sheet",
       forkc("9") == "fork in")
    ck("and the counters count the merged reading, not the raw form",
       [pgc.evaluate("()=>%s.textContent" % i) for i in ("nIn", "nOut", "nUn")]
       == ["4", "2", "3"])
    pgc.close()
    DINNER.clear()

    # The tint reads completeness, the owner's ruling of 26 Aug: grey until
    # somebody answers something, amber while only some answers exist, green
    # only once dinner, dietary and massage all hold one. It used to read
    # whether the form was submitted, which let one saved field paint a row
    # green and an untouched row wear the same amber as one half done.
    def tint(v):
        return pg.evaluate("()=>document.querySelector('.arr[data-villa=\"%s\"]').className" % v)
    ck("a guest with every answer tints the row green", "done-form" in tint("4"))
    ck("one nobody has edited reads not-started", "todo-form" in tint("2"))
    ck("opened but never answered is still not-started", "todo-form" in tint("14"))
    # By computed colour, because the class alone cannot say what the
    # stylesheet paints it: not-started is grey now, and must not come back
    # amber, which would make an untouched row read as one half done.
    ck("and not-started wears grey, not the part-done amber",
       pg.evaluate("()=>getComputedStyle(document.querySelector('.arr[data-villa=\"2\"]')).backgroundColor")
       != pg.evaluate("()=>getComputedStyle(document.querySelector('.arr[data-villa=\"6\"]')).backgroundColor"))

    # ── started and not finished ────────────────────────────────
    #  A third state, and only since the guest page began saving each page as
    #  it is left. Before that a record either existed or did not.
    ck("a form started and not finished is marked apart from one not started",
       "part-form" in tint("6") and "part-form" not in tint("2"))
    ck("and is not mistaken for a finished one",
       "done-form" not in tint("6"))
    ck("it stays amber, because it is still a row to do something about",
       "todo-form" not in tint("6") and
       pg.evaluate("()=>getComputedStyle(document.querySelector("
                   "'.arr[data-villa=\"6\"]')).borderLeftWidth") == "3px")
    #  Left on both, the icon and the marked edge would be the same fact twice
    #  in one row, which is what the pills were removed for.
    ck("the link icon steps aside once there are answers to show instead",
       not seen("6"))
    ck("but still speaks for a guest who opened it and answered nothing",
       seen("14"))
    #  A time reception approved by telephone is the desk answering, not the
    #  guest. Counting it would make every such booking look half filled.
    ck("an approved arrival time alone does not make a form look started",
       "todo-form" in tint("8") and "part-form" not in tint("8"))

    # An opened-only record is not a form, so there is nothing to read back.
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(350)
    ck("an opened-only record drops down no summary",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0)
    ck("it opens the form instead", pg.evaluate("()=>backdrop.className.indexOf('show')>-1"))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)

    # The slot order has to be exact, since ordering the day depends on it.
    #  Nine since 23 Aug: the guest's track offers half hours, and position in
    #  this list is the sort, so the halves slot between their hours.
    ck("the nine slots run earliest to latest",
       pg.evaluate("()=>ETA_SLOTS.map(s=>s[0]).join()")
       == "before2,14,1430,15,1530,16,1630,17,after5")
    ck("the row uses the short form so it does not truncate",
       pg.evaluate("()=>ETA_SLOTS.map(s=>s[2]).join()")
       == "Before 2pm,2pm,2:30pm,3pm,3:30pm,4pm,4:30pm,5pm,After 5pm")
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
    #  Was "SECOND GUEST": .sum-l used to be uppercased by CSS so innerText
    #  came back shouting. The second dress sets labels in sentence case, so
    #  the assertion no longer pins the casing - it was never the point, and
    #  a test that fails when a label stops shouting is a test about CSS.
    #  What matters is that the label and the name are both on the summary.
    ck("the second guest, under the name on the row above",
       "second guest" in sumtxt.lower() and "Imogen Clarke" in sumtxt)
    ck("and the name the guest typed outranks the Mews copy",
       "Wrong Name" not in sumtxt)
    #  Two ways out since 28 Aug. Confirm arriving sat between these: it
    #  stamped the form complete and cleared checkedInAt, and once the state
    #  moved to its own gated control the only thing it still did was
    #  un-arrive a guest, under a name that said the opposite.
    ck("and two ways out: edit, or check in", pg.evaluate(
       "()=>[...document.querySelectorAll('.sum-btns button')].map(b=>b.dataset.act).join()")
       == "edit,checkin")
    ck("only one summary is ever open",
       (pg.locator('.arr[data-villa="9"]').click(), pg.wait_for_timeout(300),
        pg.evaluate("()=>document.querySelectorAll('.sum').length"))[2] == 1)
    ck("tapping the same row again closes it",
       (pg.locator('.arr[data-villa="9"]').click(), pg.wait_for_timeout(300),
        pg.evaluate("()=>document.querySelectorAll('.sum').length"))[2] == 0)

    #  ── which rows open a summary at all, 1 Sep ──────────────
    #  Only a completed row reads its answers back. Grey and amber open the
    #  form, because on those there is something to fill in and the tap should
    #  land where the work is. Before this, any row with any answer on it
    #  opened a half-filled summary with an Edit button under it, so every
    #  amber row cost reception two taps to reach what they had opened it for.
    #  Runs with nothing open: the assertion is that the tap opens the FORM,
    #  which a summary left over from an earlier row would mask.
    for v, why in (("12", "part answered"), ("2", "not started")):
        pg.locator('.arr[data-villa="%s"]' % v).click(); pg.wait_for_timeout(500)
        ck("a %s row opens the form instead, where the work is" % why,
           pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0 and
           pg.evaluate("()=>backdrop.className.indexOf('show')>-1"))
        pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(300)
    #  Which is what makes the summary's green honest: the only row it can
    #  hang off is already green.
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(400)
    ck("so the summary's green can only ever sit under a green row",
       "done-form" in pg.evaluate(
         "()=>{const s=document.querySelector('.sum');"
         "return s?s.previousElementSibling.className:'';}"))
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)

    # A companion only Mews knows: nobody typed it here, and reception still
    # has to greet both people.
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    ck("a companion only Mews knows reads back at the desk",
       "Eleni Papadopoulou" in pg.locator(".sum").inner_text())
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.close()

    # ── the wellness row is the Spa board's truth, not the form's ─
    # Found 27 Aug: the masseuse books the massage and the desk still read
    # "Interested", because the sheet never read /spa. A record born from
    # the form replaces the Interested line; the form's ask stands in only
    # while nobody has answered it - the spa board's own rule.
    SPADB["b4"] = {"t1": {"status": "booked", "day": plus(1), "time": "14:00",
                          "source": "prearrival", "at": "x"}}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    sumtxt = pg.locator(".sum").inner_text()
    ck("a booked massage reads Booked on the sheet, day and time attached",
       "Booked" in sumtxt and "2:00 pm" in sumtxt)
    ck("and the form's Interested line stands down, answered",
       "Interested" not in sumtxt)
    pg.close()
    SPADB["b4"] = {"t1": {"status": "declined", "reqDay": plus(1),
                          "reqTime": "late morning", "note": "nothing free",
                          "source": "prearrival", "at": "x"}}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    sumtxt = pg.locator(".sum").inner_text()
    ck("a declined ask says so, why, and what the desk still owes the guest",
       "Declined" in sumtxt and "nothing free" in sumtxt and
       "let the guest know" in sumtxt and "Interested" not in sumtxt)
    pg.close()
    SPADB["b4"] = {"t1": {"status": "suggested", "day": plus(2), "time": "16:30",
                          "source": "prearrival", "at": "x"}}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("a suggestion shows as waiting on the guest",
       (lambda t: "Suggested" in t and "4:30 pm" in t and
                  "waiting on the guest" in t)(pg.locator(".sum").inner_text()))
    pg.close()

    # ── the massage mark on the row, 31 Aug ─────────────────────
    # The same four states the sheet spells out above, readable without
    # opening anything, from the same massageState so the mark and the words
    # under it cannot disagree about one guest.
    #
    # Colour is read from the rendered pixels, never from the class. The fork
    # beside it taught that: its class check passed for a day while all three
    # forks drew BLACK, because the conversion had dropped this page's --dine
    # and an undefined custom property does not fall back, it computes to
    # nothing. A class cannot say what the stylesheet drew.
    def lotus_colour(villa):
        return pg.evaluate(
          "()=>{const e=document.querySelector('.arr[data-villa=\"%s\"] .lotus svg');"
          "return e?getComputedStyle(e).stroke:null;}" % villa)
    def lotus_class(villa):
        return pg.evaluate(
          "()=>{const e=document.querySelector('.arr[data-villa=\"%s\"] .lotus');"
          "return e?e.className:null;}" % villa)

    SPADB["b4"] = {"t1": {"status": "booked", "day": plus(1), "time": "14:00",
                          "source": "prearrival", "at": "x"}}
    pg = board()
    probe = pg.evaluate("""()=>{const p=v=>{const e=document.createElement('span');
        e.style.color='var('+v+')';document.body.appendChild(e);
        const c=getComputedStyle(e).color;e.remove();return c;};
      return {dine:p('--dine'), nodine:p('--nodine'), mid:p('--mid')};}""")
    ck("a booked massage wears the done colour, the same green as a dining fork",
       lotus_class("4") == "lotus done" and lotus_colour("4") == probe["dine"])
    #  Null-safe on purpose: written as a bare querySelector first, and when
    #  the mark was removed wholesale to prove these assertions bite, this
    #  one THREW instead of failing, which stopped the suite and hid the five
    #  behind it. A test that explodes reports one fault where there are six.
    ck("the mark is the fork's size, so the two read as a pair of facts",
       (pg.evaluate("()=>{const e=document.querySelector('.arr .lotus');"
                    "return e?Math.round(e.getBoundingClientRect().width):0;}") or 0) >= 26)
    #  Red is failure and an allergy. A declined massage is neither: it is an
    #  answer, and terracotta is the law's word for one. Ruled 31 Aug.
    ck("and it is never the law's red, which belongs to failure and allergies",
       lotus_colour("4") != pg.evaluate("""()=>{const e=document.createElement('span');
         e.style.color='var(--red)';document.body.appendChild(e);
         const c=getComputedStyle(e).color;e.remove();return c;}"""))
    pg.close()

    SPADB["b4"] = {"t1": {"status": "declined", "reqDay": plus(1),
                          "source": "prearrival", "at": "x"}}
    pg = board()
    ck("a declined ask wears terracotta, the same ink the spa board gives it",
       lotus_class("4") == "lotus decl" and lotus_colour("4") == probe["nodine"])
    pg.close()

    SPADB["b4"] = {"t1": {"status": "suggested", "day": plus(2), "time": "16:30",
                          "source": "prearrival", "at": "x"}}
    pg = board()
    ck("a suggestion wears amber, because it is the one the desk must act on",
       lotus_class("4") == "lotus sugg")
    ck("and it is neither the waiting grey nor the booked green",
       lotus_colour("4") not in (probe["mid"], probe["dine"]))
    #  No word beside the amber. The owner removed it 1 Sep along with the
    #  answered count, on one principle: the amber IS the message, and a
    #  word restating it ate the line the ETA needs.
    ck("the amber says it on its own, with no word restating the colour",
       "suggested" not in pg.evaluate(
         "()=>document.querySelector('.arr[data-villa=\"4\"] .arr-s').textContent"))
    ck("and the stay line fits without clipping now that it is shorter",
       pg.evaluate("()=>{const e=document.querySelector"
                   "('.arr[data-villa=\"4\"] .arr-s');"
                   "return e.scrollWidth <= e.clientWidth + 1;}"))
    pg.close()

    #  Precedence is what the desk OWES, not what happened last: a party with
    #  one massage booked and one suggested still needs somebody to ring the
    #  guest about the suggestion.
    SPADB["b4"] = {"t1": {"status": "booked", "day": plus(1), "time": "14:00",
                          "source": "prearrival", "at": "x"},
                   "t2": {"status": "suggested", "day": plus(2), "time": "16:30",
                          "source": "desk", "at": "x"}}
    pg = board()
    ck("a suggestion outranks a booking on the same guest, because it is owed",
       lotus_class("4") == "lotus sugg")
    pg.close()
    del SPADB["b4"]

    pg = board()
    #  b4's form says yes and nothing has answered it yet.
    ck("a form asking with nothing answering it yet waits in grey",
       lotus_class("4") == "lotus wait" and lotus_colour("4") == probe["mid"])
    ck("a guest who never opened the form draws no mark",
       lotus_class("2") is None)
    pg.close()
    #  A no thank you is the absence of a request, not a declined one, so it
    #  must not borrow the declined colour. Written first against villa 9,
    #  which has no wellness key AT ALL - the assertion passed while the code
    #  said the opposite, because it was aimed at "never asked" and named
    #  "said no". A state needs a booking that is actually in it.
    PRE["b12"]["wellness"] = False
    pg = board()
    ck("a no thank you draws no mark either, the way an unanswered dinner does",
       lotus_class("12") is None)
    pg.close()
    del PRE["b12"]["wellness"]
    pg = board()

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
    #  The master list above still stores "Gluten free", as a list saved
    #  before the 26 Aug renames does. The desk shows the renamed pill and
    #  never the old wording - the rename table in nala-shared.js, which
    #  tests/diet_renames.json keeps in step with the guest pages' copies.
    ck("a pill stored under its old name is offered renamed", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')]"
       ".some(e=>e.textContent==='Gluten')"))
    ck("and the old wording is gone from the desk", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')]"
       ".every(e=>e.textContent!=='Gluten free')"))
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
    #  The desk must offer exactly what the guest was offered. A chip the
    #  guest can pick and the desk cannot draw is villa 17 again: two
    #  screens describing one booking and disagreeing about it.
    ck("the days offered are the nights they are here, then Any day",
       pg.evaluate("()=>document.querySelectorAll('#wDays .chip').length") == 6)
    ck("and Any day closes the row, in the order the guest saw it",
       pg.evaluate("()=>[...document.querySelectorAll('#wDays .chip')]"
                   ".pop().textContent")
       == json.load(open("tests/slots.json"))["anyDay"]["label"])
    ck("covers are shown because they are dining",
       pg.evaluate("()=>paxWrap.style.display!=='none'"))

    # ── saving from the sheet ───────────────────────────────────
    # The sheet's quiet button is Save, not a second Confirm arriving.
    # Renamed by the owner, 26 Aug, after the old wording did what it said: a
    # sheet opened, changed nowhere and "confirmed" saved decisions nobody
    # had made. Save keeps what is on the sheet and decides nothing;
    # confirming belongs to the summary, where the guest has just agreed to
    # the answers out loud.
    ck("the sheet's quiet button says Save",
       pg.evaluate("()=>sConfirm.textContent.trim()") == "Save")
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("saving writes the guest's own node", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("as a PATCH, so a field this screen does not carry survives",
           w[0]["m"] == "PATCH")
        ck("a save is not a confirmation, so nothing is stamped confirmed",
           "confirmedAt" not in body)
        ck("nor moved: where the guest is is not the sheet's to change",
           "checkedInAt" not in body)
        ck("the answers go with it", body["dining"] is True and body["pax"] == 2
           and body["diets"] == ["Nut allergy"])
        ck("and 'at' is NOT written, so it still means when the answers first existed",
           "at" not in body)
    ck("the sheet closes", pg.evaluate("()=>backdrop.className.indexOf('show')<0"))
    # Saving does not move them: they have not arrived.
    ck("saving leaves them under Arriving, because they have not arrived",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") == -1)
    ck("and the arrived count does not move either",
       pg.evaluate("()=>nArr.textContent") == "2/9")
    pg.close()

    # ── the bug of 26 Aug: a bare save invented answers ─────────
    # Open a blank guest, change nothing, press the sheet's quiet button.
    # The old save wrote dining:null and wellness:null for questions nobody
    # had asked, the optimistic merge read null as false, and the reopened
    # sheet showed Not dining and Not interested selected - decisions nobody
    # made. It also stamped `at`, so the untouched row went green as a
    # finished form.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]
    ck("a bare save answers no question nobody answered",
       len(w) == 1 and not any(k in json.loads(w[0]["b"]) for k in
       ("dining", "pax", "wellness", "wellQty", "wellDur", "noDiets")))
    ck("and carries no stamp: not confirmed, not arrived, not a finished form",
       len(w) == 1 and not any(k in json.loads(w[0]["b"]) for k in
       ("confirmedAt", "checkedInAt", "at")))
    ck("and writes no dinner cell, because nobody has asked them yet",
       not [x for x in WRITES if "/dinner/" in x["u"]])
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    ck("reopening the sheet offers every question still unanswered",
       pg.evaluate("()=>sDin.className===''&&sOut.className===''"
                   "&&wYes.className===''&&wNo.className===''"))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(300)
    ck("and the row stays grey, because nothing was edited",
       "todo-form" in pg.evaluate(
         "()=>document.querySelector('.arr[data-villa=\"2\"]').className"))
    pg.close()

    # ── the way back to nobody-asked ────────────────────────────
    # Ruled by the owner, 26 Aug: every answer must be undoable. The chips
    # always toggled off; the two segments could only switch sides, so a
    # mis-tapped Dining could become Not dining but never again unknown -
    # and unknown is the only honest state for a question without an answer.
    # Tapping the chosen side again now clears it, the save writes the clear
    # (null through the PATCH deletes the key), and an existing dinner cell
    # is deleted with it, because a cell has no third value and the villa
    # must go back to awaiting.
    DINNER["4"] = {"status": "in", "pax": 2, "by": "staff",
                   "diets": ["Nut allergy"], "dnote": "the daughter"}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the answers arrive selected, as before",
       pg.evaluate("()=>sDin.className==='on'&&wYes.className==='on'"))
    pg.locator("#sDin").click(); pg.wait_for_timeout(150)
    # Neither side is chosen any more - but the one the record held keeps a
    # dark border, so an accidental deselect reads as a gap where an answer
    # used to be rather than as a question nobody ever asked. The owner's
    # ask of 28 Aug; it lasts as long as the sheet is open.
    ck("tapping the chosen dining answer again clears the segment",
       pg.evaluate("()=>sDin.className!=='on'&&sOut.className!=='on'"))
    ck("and the answer just taken off keeps its border, so the slip shows",
       pg.evaluate("()=>sDin.className==='was'&&sOut.className===''"))
    ck("and the covers go with it, since they only mean something dining",
       pg.evaluate("()=>paxWrap.style.display==='none'"))
    pg.locator("#wYes").click(); pg.wait_for_timeout(150)
    ck("the wellness segment gives the same way back",
       pg.evaluate("()=>wYes.className!=='on'&&wNo.className!=='on'"))
    ck("marking what was taken off there too",
       pg.evaluate("()=>wYes.className==='was'&&wNo.className===''"))
    ck("and the day and time fold away with it",
       pg.evaluate("()=>wWrap.style.display==='none'"))
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("the save writes the clear as null, not omission, or nothing clears",
       len(w) == 1 and "dining" in json.loads(w[0]["b"])
       and json.loads(w[0]["b"])["dining"] is None
       and json.loads(w[0]["b"])["pax"] is None)
    ck("wellness clears the same way, taking day, time and lengths with it",
       len(w) == 1 and all(json.loads(w[0]["b"]).get(k, "MISSING") is None
       for k in ("wellness", "wellDay", "wellTime", "wellQty", "wellDur")))
    ck("and the dinner cell is deleted, so the villa reads awaiting again",
       len([x for x in WRITES if x["m"] == "DELETE"
            and ("/dinner/" + today + "/4") in x["u"]]) == 1)
    #  Was "goes back to grey". There is no grey fork now: clearing the
    #  answer removes the icon, which is the same fact said by absence.
    ck("the fork goes away again",
       pg.evaluate("()=>{const e=document.querySelector("
                   "'.arr[data-villa=\"4\"] .fork'); return e?e.className:null;}") is None)
    ck("and the row drops from green to part answered",
       "part-form" in pg.evaluate(
         "()=>document.querySelector('.arr[data-villa=\"4\"]').className"))
    #  And having dropped to amber it opens the FORM, not a summary - the
    #  owner's ruling of 1 Sep. Reading a cleared answer back to a guest is
    #  not what reception needs on a row with a hole in it; filling it is.
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("and tapping it now opens the form rather than a summary",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0 and
       pg.evaluate("()=>!!document.getElementById('sDin')"))
    pg.close()
    DINNER.clear()

    # A record that never held the answer gets no null either: the clear is
    # written only when there is something to clear, or every bare save
    # would stamp deletions over keys that do not exist.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    pg.locator("#sDin").click(); pg.wait_for_timeout(150)
    pg.locator("#sDin").click(); pg.wait_for_timeout(150)
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]
    ck("answering and un-answering before ever saving writes no dining at all",
       len(w) == 1 and "dining" not in json.loads(w[0]["b"]))
    ck("and deletes no cell, since none was ever written",
       not [x for x in WRITES if x["m"] == "DELETE"])
    pg.close()

    # ── reception's hour, only where the slots cannot say it ────
    # The owner's ruling of 27 Aug: the desk corrects a mid-afternoon time
    # by tapping the guest's own slot row, so the approved row's twenty five
    # chips were nineteen restatements and six real jobs. It now appears
    # only for the two open-ended slots: the early hours behind "before
    # 2pm", which only reception can grant, and the actual hour behind
    # "after 5pm", pinned for whoever waits at the desk. Any other slot
    # hides the row entirely. Setting an hour still never touches the slot
    # the guest chose, and clearing it leaves that slot standing.
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    # b9 asked "before 2pm" and typed the note reception approves against.
    ck("an early ask offers the six early half hours and nothing else",
       pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                   ".map(b=>b.textContent).join()")
       == "11am,11:30am,12pm,12:30pm,1pm,1:30pm")
    ck("under a label that says what it is",
       "Early arrival" in pg.evaluate("()=>apLab.textContent"))
    ck("with the guest's own note on screen to approve against",
       pg.evaluate("()=>fEtaNote.value") == "flight lands 11am")
    pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                ".find(b=>b.textContent==='12pm').click()")
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b9/prearrival" in x["u"]]
    ck("approving writes the hour as a number",
       len(w) == 1 and json.loads(w[0]["b"]).get("arriveApproved") == 12)
    if w:
        ck("and the guest's slot goes with it, untouched",
           json.loads(w[0]["b"])["arriveSlot"] == "before2")
    pg.close()

    # After 5pm is the other open end: the hour is pinned, not approved.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    ck("with no slot chosen there is no hour row at all",
       pg.evaluate("()=>apChips.style.display==='none'"))
    pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
        .find(b=>/After 5pm/.test(b.textContent)).click()""")
    pg.wait_for_timeout(200)
    ck("choosing After 5pm offers the evening half hours",
       pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                   ".map(b=>b.textContent).join()")
       == "5:30pm,6pm,6:30pm,7pm,7:30pm,8pm,8:30pm,9pm,9:30pm,10pm,10:30pm,11pm")
    ck("worded as when they arrive, since nobody refuses a late guest",
       "Arriving at" in pg.evaluate("()=>apLab.textContent"))
    pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
        .find(b=>/Around 3pm/.test(b.textContent)).click()""")
    pg.wait_for_timeout(200)
    ck("an hour the slots can already say hides the row again",
       pg.evaluate("()=>apChips.style.display==='none'"))
    pg.close()

    # A stored hour from the wide-open days, or one whose slot has since
    # changed, is painted anyway, selected - the purpose-chip lesson - so
    # the next save cannot silently drop a time somebody agreed to.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("b4's stored 3pm survives as the one offered chip, selected",
       pg.evaluate("()=>[...document.querySelectorAll('#apChips button')]"
                   ".map(b=>b.textContent+':'+b.className).join()") == "3pm:chip on")
    ck("and the label says it is kept, not offered",
       "kept" in pg.evaluate("()=>apLab.textContent"))
    ck("with the guest's own slot still selected beside it",
       pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
         .some(e=>/Around 4pm/.test(e.textContent) && e.className.indexOf('on')>-1)"""))
    # Tapping the chosen hour again is the way back, like the slot chips.
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

    # ── the time rails scroll instead of wrapping ───────────────
    # Nine slots was three rows of chips on a phone. A time sequence is the
    # one control safe to scroll sideways: the order says what is off
    # screen. The rail scrolls itself; the page must not.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the slot chips stand in one scrollable rank",
       pg.evaluate("()=>getComputedStyle(eChips).flexWrap") == "nowrap"
       and pg.evaluate("()=>getComputedStyle(eChips).overflowX") == "auto")
    ck("and the sheet still does not scroll sideways",
       not pg.evaluate("()=>document.documentElement.scrollWidth>"
                       "document.documentElement.clientWidth+1"))
    ck("the rail opens with the guest's chosen slot in view",
       pg.evaluate("""()=>{const on=eChips.querySelector('.chip.on');
         const r=on.getBoundingClientRect(), b=eChips.getBoundingClientRect();
         return r.left>=b.left-1 && r.right<=b.right+1;}"""))
    # The owner's ruling of 27 Aug, once the time rails proved themselves:
    # every row of choices wears the same dress. A wrapped row costs vertical
    # space, the scarce dimension on a phone held at a desk, and changes
    # height as the answers change; a rail costs none and never moves.
    # Named one by one rather than by counting `.rail`, so a row ADDED to the
    # sheet without the dress fails here by name rather than passing a total.
    for row in ("eChips", "apChips", "dChips", "dNone", "pChips", "aChips",
                "wDays", "fWqty", "fkChips", "paxRow"):
        ck("%s stands in one scrollable rank" % row,
           pg.evaluate("()=>{const e=document.getElementById('%s');"
                       "const s=getComputedStyle(e);"
                       "return s.flexWrap==='nowrap'&&s.overflowX==='auto';}" % row))
    # Was: "a row that fits stays centred under its centred label". The
    # labels are not centred any more - the sheet got topic headings and a
    # left edge on 29 Aug, because one ribbon of identical centred captions
    # gave the eye nothing to run down. A centred row under a left aligned
    # label is a row that has slipped, so the rails start at the left too.
    # Starting left keeps the half of the old bargain that mattered: the
    # first chip is always at the margin, so an overflowing row is only ever
    # clipped on the right, where it can be scrolled from.
    # The topics have to be tellable apart, which is what the owner asked
    # for: a heading is heavier than a label, and the space above a heading
    # is bigger than the space between a label and its own control. Before
    # this the labels were all one size and the rhythm was 16 above, 8
    # below, so a caption sat nearly as close to the answer above it as to
    # the question it belonged to.
    hier = pg.evaluate("""()=>{/* not .first: the top heading deliberately has no rule and
          no space above it, since nothing precedes it to separate from. */
       const g=document.querySelector('.sheet-group:not(.first)');
       const l=document.querySelector('.sheet-label');
       if(!g||!l) return null;
       const gs=getComputedStyle(g), ls=getComputedStyle(l);
       return {gSize:parseFloat(gs.fontSize), lSize:parseFloat(ls.fontSize),
               gWeight:parseInt(gs.fontWeight), lWeight:parseInt(ls.fontWeight),
               gTop:parseFloat(gs.marginTop)+parseFloat(gs.paddingTop),
               lTop:parseFloat(ls.marginTop), lBottom:parseFloat(ls.marginBottom),
               rule:gs.borderTopWidth};}""")
    print("   form hierarchy:", hier)
    ck("a topic heading outweighs a field label",
       hier and hier["gSize"] > hier["lSize"] and hier["gWeight"] > hier["lWeight"])
    ck("a topic is separated by more space than a label is",
       hier and hier["gTop"] > hier["lTop"] and hier["rule"] != "0px")
    ck("a label sits closer to its own control than to what came before",
       hier and hier["lTop"] >= hier["lBottom"] * 2)

    ck("a rail starts where its label starts",
       pg.evaluate("""()=>{const r=document.getElementById('dNone');
          const lab=[...document.querySelectorAll('.sheet-label,.sheet-group')]
            .filter(e=>e.getBoundingClientRect().width>0).pop();
          return getComputedStyle(r).justifyContent==='flex-start' &&
                 getComputedStyle(lab).textAlign==='left';}"""))
    pg.close()

    # ── the dress is declared once, in the markup ───────────────
    # clearMiss and flagMissing used to REBUILD the dietary row's class from
    # a literal - className = 'chips' - which silently undressed the rail,
    # and only after somebody answered a dietary, which is the worst kind of
    # bug: invisible until the screen is in use. The miss mark is a state
    # laid on the dress now, added and removed on its own.
    #  Driven off the Other-with-no-note refusal since 28 Aug: check in no
    #  longer demands anything, so it no longer marks anything either.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    pg.evaluate("""()=>{ var c=[...document.querySelectorAll('#dNone .chip')]
        .find(x=>/^other$/i.test(x.textContent.trim())); if(c) c.click(); }""")
    pg.wait_for_timeout(200)
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(400)
    ck("a wrong answer still marks its row",
       pg.evaluate("()=>fDnote.className.indexOf('miss')>-1"))
    ck("without undressing the rail underneath the mark",
       pg.evaluate("()=>dChips.className.indexOf('rail')>-1"))
    pg.evaluate("""()=>{ var c=[...document.querySelectorAll('#dNone .chip')]
        .find(x=>/^other$/i.test(x.textContent.trim())); if(c) c.click(); }""")
    pg.wait_for_timeout(250)
    ck("and taking the wrong answer back clears the mark",
       pg.evaluate("()=>fDnote.className.indexOf('miss')<0"))
    ck("with the rail still standing",
       pg.evaluate("()=>getComputedStyle(dChips).flexWrap") == "nowrap")
    pg.close()

    # ── a rail keeps its place across a repaint ─────────────────
    # Every row rebuilds itself on every tap, and a scrolled rail jumping
    # back to its start would take the chip just pressed off the screen.
    # It does not, with no help from the page: the clear and the refill run
    # in ONE task, so the browser never lays out the empty row and never
    # clamps scrollLeft. Asserted because it is the behaviour reception
    # depends on, whoever provides it - the page held it with a save and
    # restore first, and breaking that changed this line not at all, which
    # is why the code went and the assertion stayed.
    pg = board(w=320)
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    pg.evaluate("()=>{eChips.scrollLeft=120;}")
    pg.wait_for_timeout(150)
    moved = pg.evaluate("()=>eChips.scrollLeft")
    pg.evaluate("""()=>[...document.querySelectorAll('#eChips button')]
        .find(b=>/Around 5pm/.test(b.textContent)).click()""")
    pg.wait_for_timeout(250)
    ck("a tap repaints the rail where it stood, not back at its start",
       moved > 0 and abs(pg.evaluate("()=>eChips.scrollLeft") - moved) < 2)
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
        # This used to stamp `at` on the reasoning that the answers did not
        # exist before. But `at` is the whole test for a finished form, and a
        # desk save can be one answer of six: check in stamps it instead,
        # once everything required has actually been asked.
        ck("and 'at' is NOT set by a save, so a part-answered guest never "
           "reads as a finished form", "at" not in body)
    pg.close()

    # ── checking in from the summary, without opening anything ──
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(500)
    w = [x for x in WRITES if "/bookings/b9/prearrival" in x["u"]]
    ck("check in from the summary saves without opening the form", len(w) == 1)
    if w:
        body = json.loads(w[0]["b"])
        ck("it saves exactly what was read back, not a blank",
           body["dining"] is False and body["noDiets"] is True)
        ck("stamped arrived, and nothing else: checking in is a visual move "
           "of the tile, not a decision about the form",
           bool(body.get("checkedInAt")) and "at" not in body
           and "confirmedAt" not in body)
    ck("and the summary closes behind it",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0)
    ck("and the tile moves to Arrived, which is the whole job", pg.evaluate(
       "()=>document.querySelector('.arr[data-villa=\"9\"]').className").find("is-done") > -1)
    pg.close()

    # ── a failed save must not look like success ────────────────
    STATE["fail"] = True
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
    # The words come from the shared saveFailWords now, not this page: a
    # refusal is a PERMISSION and needs the manager, which is a different
    # errand from a write that never arrived. The desk's throw carried the
    # bare word "save" until 27 Aug, so neither could be told apart and a
    # rules rejection read as "check the connection" - the wrong remedy.
    ck("a rejected save says so", "not allowed"
       in pg.locator("#errBar").inner_text().lower())
    ck("and names the right errand, since a refusal is not a bad connection",
       "manager" in pg.locator("#errBar").inner_text().lower()
       and "connection" not in pg.locator("#errBar").inner_text().lower())
    ck("with the reassurance the desk acts on",
       "Nothing was changed" in pg.locator("#errBar").inner_text())
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
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
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
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
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
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(700)
    ck("if either write is rejected the guest is put back, not left half done",
       "not allowed" in pg.locator("#errBar").inner_text().lower() and
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
        ck("stamped arrived, and nothing else: checking in is a visual move "
           "of the tile, not a decision about the form",
           bool(body.get("checkedInAt")) and "at" not in body
           and "confirmedAt" not in body)
        ck("and stamped arrived, which confirm alone does not",
           bool(body.get("checkedInAt")))
    ck("and moves them to Arrived on the spot",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"4\"]').className")
       .find("is-done") > -1)
    ck("with the count following", pg.evaluate("()=>nArr.textContent") == "3/9")
    pg.close()

    # This used to assert the opposite: that confirming again kept a guest
    # arrived, on the reasoning that a guest who has arrived has arrived. True
    # of guests, not of taps, and there was no way back from pressing it by
    # mistake. The way back was Confirm arriving until 28 Aug; it is the check
    # in button itself now, a toggle, which is where an undo belongs.
    PRE["b4"]["checkedInAt"] = "2026-08-17T15:00:00Z"
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(350)
    del WRITES[:]
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b4/prearrival" in x["u"]]
    ck("pressing check in again puts an accidentally arrived guest back",
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
    # And touches the form's STATE not at all, the owner's model of 28 Aug.
    # Check in used to stamp `at` here, having asked for two of the three
    # mandatory answers - so a multi night guest could be marked completed
    # with the treatment question never put to them, and the row then tinted
    # amber beside its own completed stamp. Arriving is a fact about a
    # person; finishing the questionnaire is its own control now.
    ck("and does NOT call the form completed, which is not its job",
       len(w) == 1 and "at" not in json.loads(w[0]["b"]))
    ck("nor writes confirmedAt, which nothing in the app ever read",
       len(w) == 1 and "confirmedAt" not in json.loads(w[0]["b"]))
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
    pg.locator('.sum-btns button[data-act="checkin"]').click(); pg.wait_for_timeout(600)
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
    ck("and it does not block the way out, since reception can resolve it",
       pg.evaluate("()=>!!document.querySelector('.sum-btns button[data-act=\"checkin\"]')"))
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

    # ── checking in asks for nothing ────────────────────────────
    # It used to refuse without a dining and a dietary answer, and before
    # that the same questions were asked at every save, which meant reception
    # could not write down what they heard across the day and it went on
    # paper instead.
    #
    # The owner ruled 28 Aug that checking a guest in is a visual move of the
    # tile so reception can see who is here. A control that refuses is not a
    # visual move. What the guard protected - a guest sent to their villa with
    # the kitchen never hearing about the cover - is the row's own colour now,
    # amber until the mandatory answers are in, and the gate on Mark as
    # completed, which is the control that actually claims the form is done.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    del WRITES[:]
    pg.locator("#sCheckin").click(); pg.wait_for_timeout(600)
    w = [x for x in WRITES if "/bookings/b2/prearrival" in x["u"]]
    ck("checking in a guest nobody has asked anything is not refused",
       len(w) == 1 and bool(json.loads(w[0]["b"]).get("checkedInAt")))
    ck("and it does not pretend their form is finished",
       len(w) == 1 and "at" not in json.loads(w[0]["b"]))
    ck("nothing is flagged as missing, because nothing was demanded",
       pg.evaluate("()=>sMiss.className.indexOf('show')<0"))
    pg.close()

    # The one check that survives, because it is about an answer being WRONG
    # rather than missing: Other with an empty note tells the kitchen there is
    # something to know and never says what.
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    pg.evaluate("""()=>{ var c=[...document.querySelectorAll('#dNone .chip')]
        .find(x=>/^other$/i.test(x.textContent.trim())); if(c) c.click(); }""")
    pg.wait_for_timeout(200)
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(500)
    ck("Other with an empty note is refused, and said",
       len([x for x in WRITES if "/prearrival" in x["u"]]) == 0 and
       "allergy" in pg.locator("#sMiss").inner_text().lower())
    pg.close()



    # The GUID is the key, but nobody can read a GUID out over the phone. The
    # reservation number is what staff see in Mews.
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(300)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the sheet shows the Mews reservation number",
       "Mews 1159" in pg.locator("#sheet").inner_text())
    pg.close()

    # ── the desk says what is actually missing ──────────────────
    # Seen live, 28 Aug: a guest answered every question and never pressed
    # Send, so `at` was never written, and the desk told reception the form
    # was unfinished and to look for blanks - of which there were none. The
    # note names the outstanding questions now, and says so when there are
    # none, because those are two different conversations to have with a
    # guest. The labels come from tests/form_questions.json, which the guest
    # form's own required list answers to as well.
    QT = json.load(open("tests/form_questions.json"))
    STAYS["17"] = {"id": "b17", "first": "Tim", "last": "Martin",
                   "arrive": today, "depart": plus(3), "adults": 2,
                   "phone": "+61 416 237 128"}
    #  Every question but the treatment one, and no `at`: the shape of a
    #  guest who walked the whole form and stopped before Send.
    PRE["b17"] = {"openedAt": "2026-08-27T22:00:00Z", "arriveSlot": "15",
                  "dining": True, "pax": 2, "noDiets": True,
                  "purpose": "A celebration", "approach": "most"}
    pg = board()
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    note = pg.locator("#sheet .note-box").last.inner_text()
    print("   the note reads:", note)
    wellness_label = [q["desk"] for q in QT["questions"]
                      if q["key"] == "wellness"][0]
    ck("the note names the one question still outstanding",
       wellness_label in note)
    ck("and names no question the guest has already answered",
       not any(q["desk"] in note for q in QT["questions"]
               if q["key"] != "wellness"))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)
    pg.close()
    #  Nothing outstanding at all: the case that started this. The desk must
    #  not send reception hunting for blanks that do not exist.
    PRE["b17"]["wellness"] = False
    pg = board()
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    note = pg.locator("#sheet .note-box").last.inner_text()
    print("   with everything answered:", note)
    ck("a form with every question answered says nothing is outstanding",
       "never pressed Send" in note and "Nothing is outstanding" in note)
    ck("and still says the form is not marked finished, because it is not",
       "not marked finished" in note)
    ck("naming no question at all, since none is missing",
       not any(q["desk"] in note for q in QT["questions"]))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)
    pg.close()
    #  A one night guest is never asked the long-stay three, so the desk must
    #  never name them as missing - the retired-question trap in miniature.
    STAYS["17"]["depart"] = plus(1)
    PRE["b17"] = {"openedAt": "2026-08-27T22:00:00Z", "arriveSlot": "15"}
    pg = board()
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    note = pg.locator("#sheet .note-box").last.inner_text()
    print("   one night, dietary outstanding:", note)
    ck("a one night stay is never asked to account for the long-stay three",
       not any(q["desk"] in note for q in QT["questions"]
               if not q["askedOnOneNight"]))
    ck("but is still asked for the dietary it was offered",
       [q["desk"] for q in QT["questions"] if q["key"] == "dietary"][0] in note)
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)
    pg.close()
    del PRE["b17"]; del STAYS["17"]

    # ── a stamp with nothing behind it ──────────────────────────
    # Seen live on villa 17, 28 Aug. `at` says the answers exist, and the
    # desk's confirm wrote it onto a record holding none: this board went
    # amber (anyAnswers yes, fullAnswers no), Pre-arrival SMS read Form
    # completed and would not send the link again, and nothing on either
    # screen could put it back. A guest can never submit an empty form - the
    # slot, dinner and dietary questions are all required - so a stamp
    # standing alone was always the desk's and never a guest's. Both ends are
    # fixed; this is the reading end, and it is what heals the records already
    # written.
    STAYS["17"] = {"id": "b17", "first": "Tim", "last": "Martin",
                   "arrive": today, "depart": plus(1), "adults": 2,
                   "phone": "+61 416 237 128"}
    PRE["b17"] = {"at": "2026-08-27T22:56:00Z",
                  "confirmedAt": "2026-08-27T22:56:00Z"}
    pg = board()
    def cls(v):
        return pg.evaluate("()=>document.querySelector("
                           "'.arr[data-villa=\"%s\"]').className" % v)
    ck("a stamp with no answer behind it is not a finished form",
       "done-form" not in cls("17"))
    ck("nor a form somebody started: it reads as nobody asked",
       "todo-form" in cls("17") and "part-form" not in cls("17"))
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(350)
    ck("and it drops down no summary, because there is nothing to read back",
       pg.evaluate("()=>document.querySelectorAll('.sum').length") == 0)
    ck("it opens the form instead, which is the way back",
       pg.evaluate("()=>backdrop.className.indexOf('show')>-1"))
    pg.evaluate("()=>sClose.click()"); pg.wait_for_timeout(250)
    pg.close()
    del PRE["b17"]

    # ── the state is its own control ────────────────────────────
    # The owner's model of 28 Aug: three states, and editing and saving move
    # between none of them. One button marks a form completed, the same
    # button walks it back, and it is available only once the mandatory
    # answers are in - dinner, dietary and massage, the ruling of 28 Aug.
    #  Three nights, so the treatment question IS owed here. The block above
    #  leaves villa 17 a one nighter, where it is not.
    STAYS["17"]["depart"] = plus(3)
    pg = board()
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    ck("the mark button is offered, and refused until the answers are in",
       pg.evaluate("()=>!!sMark") and pg.evaluate("()=>sMark.disabled"))
    ck("and says which answers it is waiting on",
       "dining" in pg.evaluate("()=>sMarkWhy.textContent"))
    ck("it offers to complete, not to walk back, on a form nobody has marked",
       pg.evaluate("()=>sMark.textContent") == "Mark as completed")
    pg.locator("#sOut").click(); pg.wait_for_timeout(200)
    pg.evaluate("()=>[...document.querySelectorAll('#dNone .chip')][0].click()")
    pg.wait_for_timeout(200)
    ck("two of the three is still not enough on a three night stay",
       pg.evaluate("()=>sMark.disabled"))
    ck("and the treatment question is what it is still waiting on",
       "treatments" in pg.evaluate("()=>sMarkWhy.textContent"))
    pg.locator("#wNo").click(); pg.wait_for_timeout(250)
    ck("the last mandatory answer brings it alive under the finger",
       not pg.evaluate("()=>sMark.disabled"))
    ck("wearing the solid dress, since it is the primary act on this sheet",
       "solid" in pg.evaluate("()=>sMark.className"))
    #  A plain Save still decides nothing.
    del WRITES[:]
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(700)
    w = [x for x in WRITES if "/bookings/b17/prearrival" in x["u"]]
    ck("saving with every answer in still does not complete the form",
       len(w) == 1 and "at" not in json.loads(w[0]["b"]))
    ck("and the row is still amber, because nobody has marked it",
       "part-form" in cls("17"))
    #  The mark is what moves it.
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    del WRITES[:]
    pg.locator("#sMark").click(); pg.wait_for_timeout(700)
    w = [x for x in WRITES if "/bookings/b17/prearrival" in x["u"]]
    ck("marking it completed is what writes the state",
       len(w) == 1 and bool(json.loads(w[0]["b"]).get("at")))
    ck("and the row goes green", "done-form" in cls("17"))
    pg.close()

    # ── and the way back ────────────────────────────────────────
    # The same button, walking it back. It wears terracotta and asks first,
    # the button law: marking a form incomplete puts the guest back into To
    # send on Pre-arrival SMS, where the link can be sent to them again.
    PRE["b17"] = {"at": "2026-08-27T22:56:00Z", "arriveSlot": "15",
                  "dining": False, "noDiets": True, "wellness": False}
    pg = board()
    ck("a completed form reads green", "done-form" in cls("17"))
    pg.locator('.arr[data-villa="17"]').click(); pg.wait_for_timeout(400)
    pg.locator('.sum-btns button[data-act="edit"]').click(); pg.wait_for_timeout(400)
    ck("the button now offers the way back",
       pg.evaluate("()=>sMark.textContent") == "Mark as incomplete")
    ck("in terracotta, never solid, because it walks something back",
       "terra" in pg.evaluate("()=>sMark.className")
       and "solid" not in pg.evaluate("()=>sMark.className"))
    #  Cancelling the question costs nothing.
    pg.once("dialog", lambda d: d.dismiss())
    del WRITES[:]
    pg.locator("#sMark").click(); pg.wait_for_timeout(500)
    ck("and cancelling its question writes nothing at all",
       not [x for x in WRITES if "/bookings/b17/prearrival" in x["u"]])
    pg.once("dialog", lambda d: d.accept())
    del WRITES[:]
    pg.locator("#sMark").click(); pg.wait_for_timeout(700)
    w = [x for x in WRITES if "/bookings/b17/prearrival" in x["u"]]
    ck("accepting it clears the state, and only the state",
       len(w) == 1 and "at" in json.loads(w[0]["b"])
       and json.loads(w[0]["b"])["at"] is None)
    ck("the answers are left exactly where they were",
       len(w) == 1 and json.loads(w[0]["b"]).get("dining") is False)
    ck("and the row drops to amber, not to grey: the answers are still there",
       "part-form" in cls("17"))
    pg.close()
    del PRE["b17"]

    # ── a one night stay can reach green ────────────────────────
    # The guest form offers no treatment question on a one night stay, so
    # `wellness` is never written for one, and fullAnswers demanded it
    # anyway: villas 16 and 17 on 28 Aug were one night each and could not
    # have tinted green however completely they answered. A question nobody
    # was asked cannot be held against them.
    STAYS["17"]["depart"] = plus(1)     # a one nighter again, for this one
    PRE["b17"] = {"at": "2026-08-27T22:56:00Z", "arriveSlot": "15",
                  "dining": True, "pax": 2, "noDiets": True}
    STAYS["10"] = {"id": "b10", "first": "Long", "last": "Stayer",
                   "arrive": today, "depart": plus(3), "adults": 2}
    PRE["b10"] = dict(PRE["b17"])
    pg = board()
    ck("a one night guest who answered everything asked tints green",
       "done-form" in cls("17"))
    ck("and the same answers over three nights read incomplete, stamp and "
       "all, because the treatment question WAS asked and is unanswered",
       "part-form" in cls("10"))
    #  One table, two readers: the guest form decides which questions a one
    #  night stay is shown, this board has to know the same rule, and neither
    #  can import from the other. tests/onenight_cases.json is what they both
    #  answer to - add a case there, not here.
    cases = json.load(open("tests/onenight_cases.json"))["cases"]
    bad = []
    for nights, want, why in cases:
        got = pg.evaluate("(d)=>oneNightStay({arrive:d.a, depart:d.b})",
                          {"a": plus(0), "b": plus(nights)})
        if bool(got) != bool(want):
            bad.append("%d nights: wanted %s, got %s (%s)"
                       % (nights, want, got, why))
    print("   one night cases the desk reads wrongly:", bad)
    ck("the desk reads the one night rule exactly as the guest form does",
       bad == [] and len(cases) >= 5)
    pg.close()
    del PRE["b17"]; del STAYS["17"]
    del PRE["b10"]; del STAYS["10"]

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
    #  The mark moved off the stay line and up beside the name on 31 Aug, to
    #  give the row back the width the massage mark spends. It keeps the full
    #  phrase: a short "villa 8" was tried the same day and the owner ruled
    #  against it.
    def mark(v):
        return pg.evaluate(
          "()=>{var e=document.querySelector('.arr[data-villa=\"%s\"] .arr-with');"
          "return e?e.textContent:''}" % v)
    ck("and each says which other villa the party holds",
       mark("6") == "with villa 8" and mark("8") == "with villa 6")
    ck("the mark sits beside the name, not down on the stay line",
       "villa 8" not in line("6"))
    #  A half-written villa number is worse than none, so the mark never
    #  takes the ellipsis - the name does.
    ck("and the mark is never the thing that gets clipped",
       pg.evaluate("()=>{const e=document.querySelector"
                   "('.arr[data-villa=\"6\"] .arr-with');"
                   "return e.scrollWidth <= e.clientWidth + 1;}"))
    ck("and the name keeps an element of its own to be clipped in",
       pg.evaluate("()=>!!document.querySelector('.arr[data-villa=\"6\"] .arr-top .arr-n')"))
    ck("a booking on its own says nothing about a party",
       mark("4") == "" and "villa" not in line("4"))
    pg.close()

    # Three villas reads as a list, not as three separate notes.
    STAYS["10"] = {"id":"bj3","first":"Jane","last":"Smith","arrive":today,
                   "depart":plus(2),"adults":2,"groupId":"grp-jane"}
    pg = board()
    ck("three villas in one party read as a list",
       pg.evaluate("()=>document.querySelector('.arr[data-villa=\"6\"] .arr-with')"
                   ".textContent") == "with villas 8 & 10")
    #  The SMS page reads the very same function, so the two boards cannot
    #  name a party differently.
    #  groupMatesShort excludes the row itself by identity, so the row passed
    #  in has to BE the one in the list. Written the other way first, and it
    #  failed by naming the party's own villa back at it.
    ck("and the phrase the SMS line uses is built from that same list",
       pg.evaluate("()=>{var a={stay:{groupId:'g'},villa:'6'},"
                   "b={stay:{groupId:'g'},villa:'8'};"
                   "return groupMatesText(a,[a,b]);}") == "with villa 8")
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
    #  wellness answered, so formState calls this completed. Since 1 Sep only
    #  a completed row opens its summary; an incomplete one opens the form and
    #  there would be no .sum-btns to read.
    arrived_pre = {"at": now.isoformat(), "dining": True, "pax": 2,
                   "diets": ["Gluten free"], "noDiets": False,
                   "wellness": False,
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
    # The undo lives on the check in button itself since 28 Aug, and the
    # label says so rather than leaving a pressed-by-mistake guest stuck.
    ck("an arrived guest is offered the way back, in words",
       any(l.startswith("checkin:") and "undo" in l.lower() for l in labels))

    del WRITES[:]
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=checkin]').click()")
    pg.wait_for_timeout(900)
    sent = [json.loads(x["b"]) for x in WRITES if x["b"] and "/prearrival" in x["u"]]
    ck("pressing it again clears the check in",
       bool(sent) and all("checkedInAt" in d and d["checkedInAt"] is None for d in sent))
    ck("and that guest goes back to the arriving list",
       pg.evaluate("(v)=>{const e=document.querySelector('.arr[data-villa=\"'+v+'\"]');"
                   "return !!e && e.className.indexOf('is-done')<0;}", villa))
    # Only where the guest is has changed. The answers ride along untouched,
    # and no state is claimed about the form either way.
    ck("without touching the form's state",
       bool(sent) and all("at" not in d for d in sent))
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

    # Check in insists on nothing since 28 Aug: it is a visual move of the
    # tile. It saves what is on the sheet and arrives them, and the form's
    # state is left to the control that is actually gated on the answers.
    PRE.pop("b14", None)
    pg = board()
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(600)
    if pg.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
        pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
        pg.wait_for_timeout(600)
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sCheckin').click()")
    pg.wait_for_timeout(700)
    ck("checking in with nothing answered still arrives them",
       len([x for x in WRITES if "/bookings/b14/prearrival" in x["u"]]) == 1)
    ck("and claims nothing about the form",
       all("at" not in json.loads(x["b"])
           for x in WRITES if "/bookings/b14/prearrival" in x["u"]))

    # The one check that survives a partial save: Other means the answer is in
    # the note, so Other with an empty note is not an incomplete answer, it is
    # a wrong one. It tells the kitchen there is something to know and never
    # says what.
    #  The sheet is reopened first: check in no longer refuses, so it saved
    #  and closed behind itself just above.
    pg.locator('.arr[data-villa="14"]').click(); pg.wait_for_timeout(600)
    if pg.evaluate("()=>!!document.querySelector('.sum-btns [data-act=edit]')"):
        pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
        pg.wait_for_timeout(600)
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

    # ── clearing a note ─────────────────────────────────────────
    #  Reported 22 Aug: a staff note could only be saved with something in it,
    #  so the only way to remove one was to leave a character behind. Nothing
    #  refused the write. The note saved as an empty string exactly as asked,
    #  and the READ then treated empty as absent and put the Mews original back
    #  in its place, so the note appeared to survive deletion.
    INTERNAL["b4"] = {"fromMews": "Complained about noise last stay",
                      "note": "Do not seat near the kitchen"}
    pg = desk_as("staff@x")
    ck("an edited note is what shows, not the Mews original",
       pg.evaluate("()=>document.getElementById('fInternal').value")
         == "Do not seat near the kitchen")
    pg.fill("#fInternal", "")
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(900)
    wrote = [json.loads(x["b"]) for x in WRITES if "/internal/" in x["u"] and x["b"]]
    ck("clearing the box saves the clearing",
       bool(wrote) and wrote[0].get("note") == "")
    pg.close()

    #  The state that write leaves behind, read back. This is the half that was
    #  broken: an empty edited note is a decision that this booking needs no
    #  note, and it outranks what Mews sent.
    INTERNAL["b4"] = {"fromMews": "Complained about noise last stay", "note": ""}
    pg = desk_as("staff@x")
    ck("and a cleared note stays cleared when the sheet is reopened",
       pg.evaluate("()=>document.getElementById('fInternal').value") == "")
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(800)
    ck("and closing it again writes nothing, since nothing changed",
       not [x for x in WRITES if "/internal/" in x["u"]])
    pg.close()

    #  The fallback still does its job where it was always meant to: a booking
    #  nobody has edited shows what Mews sent.
    INTERNAL["b4"] = {"fromMews": "Complained about noise last stay"}
    pg = desk_as("staff@x")
    ck("a note nobody has touched still shows the Mews original",
       "noise" in (pg.evaluate("()=>document.getElementById('fInternal').value") or ""))
    pg.close()

    # ── the booking flags ───────────────────────────────────────
    #  Short facts pinned under the guest's name: VIP, Travel agent, whatever
    #  the admin defined on Flag Settings. Ticked here per booking, admin
    #  only, stored at /bookflags. One flag sets itself: a Mews rate STARTING
    #  with Luxury Escapes, that rate and no other - the owner's ruling.
    PMS["b4"]["rate"] = "Luxury Escapes AU"
    PMS["b9"]["rate"] = "Flexible with Breakfast"
    BOOKFLAGS["b9"] = {"flags": ["VIP", "Old badge"], "by": "x", "at": "t"}
    pg = board()
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("a Luxury Escapes rate pins its pill before anybody ticks anything",
       "Luxury Escapes" in pg.locator(".sum").inner_text())
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(700)
    def chip(label):
        return pg.evaluate("""()=>{const b=[...document.querySelectorAll('#fkChips .chip')]
            .find(x=>x.textContent==='%s'); return b?b.className:null;}""" % label)
    ck("the sheet offers the admin's list as chips, none ticked yet",
       chip("VIP") == "chip" and chip("Travel agent") == "chip"
       and chip("Breakfast included") == "chip")
    ck("an archived flag is not offered", chip("Honeymoon") is None)
    ck("and the automatic one is words, not a chip, since a tick could not turn it off",
       chip("Luxury Escapes") is None
       and "automatic" in pg.locator(".flag-src").inner_text())
    #  Nothing ticked, so a confirm must not stamp a flag record on the
    #  booking: an edit nobody made, the internal-note lesson.
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(800)
    ck("confirming without touching the flags writes no flag record",
       not [x for x in WRITES if "/bookflags" in x["u"]])
    pg.close()

    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(400)
    t = pg.locator(".sum").inner_text()
    ck("a rate that is not Luxury Escapes pins nothing",
       "Luxury Escapes" not in t and "Flexible" not in t)
    ck("while the ticked names show, a retired one included",
       "VIP" in t and "Old badge" in t)
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(700)
    ck("a stored tick arrives ticked", chip("VIP") == "chip on")
    ck("and a stored name the list no longer offers is painted anyway, "
       "selected, so a save cannot silently drop it",
       chip("Old badge") == "chip on")
    ck("no automatic line without the Luxury Escapes rate",
       pg.locator(".flag-src").count() == 0)
    #  Travel agent on, Old badge off: the save carries the whole new set.
    for label in ("Travel agent", "Old badge"):
        pg.evaluate("""()=>[...document.querySelectorAll('#fkChips .chip')]
            .find(x=>x.textContent==='%s').click()""" % label)
        pg.wait_for_timeout(150)
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(800)
    w = [x for x in WRITES if "/bookflags/b9" in x["u"]]
    ck("the ticks are saved to their own node, whole, with who and when",
       len(w) == 1 and w[0]["m"] == "PUT"
       and json.loads(w[0]["b"])["flags"] == ["VIP", "Travel agent"]
       and json.loads(w[0]["b"])["by"] == "staff@x")
    #  Its own write, outside the both-or-neither pair: a flag refused by the
    #  rules must not roll tonight's answers back.
    ck("and it rides beside the guest's answers, not inside them",
       any("/prearrival" in x["u"] for x in WRITES)
       and not [x for x in WRITES if "/prearrival" in x["u"]
                and "Travel agent" in (x["b"] or "")])
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(400)
    t = pg.locator(".sum").inner_text()
    ck("the summary then reads the new set back",
       "Travel agent" in t and "Old badge" not in t)
    pg.close()

    #  Admin only. A manager reads the pills but is offered no chips, and
    #  their save must not carry a flag write at all.
    pg = board("manager@x")
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(400)
    ck("a manager still reads the pills on the summary",
       "VIP" in pg.locator(".sum").inner_text())
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(700)
    ck("but is offered no flag chips",
       pg.evaluate("()=>!document.getElementById('fkChips')"))
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(800)
    ck("and their save carries no flag write",
       not [x for x in WRITES if "/bookflags" in x["u"]])
    pg.close()
    del PMS["b4"]["rate"]; del PMS["b9"]["rate"]; BOOKFLAGS.clear()

    # ── the number beside the name, the SMS pages' display at the desk ──
    #  Asked for 25 Aug: the same three parts the Pre-arrival SMS rows carry,
    #  from the same shared builder, so the two screens cannot drift apart.
    #  The raw number small and grey, the confidence mark, the pencil.
    pg = board()
    def nrow(v): return pg.locator('.arr[data-villa="%s"]' % v)
    ck("a row shows its number in the small grey font, on its own line so the "
       "fork and link icons cannot clip the pencil off the edge",
       "+61 411 222 333" in nrow("4").locator(".arr-p .ph").text_content())
    ck("an Australian mobile wears the confidence tick",
       nrow("4").locator(".conf.ok").count() == 1)
    ck("a +1 number is honestly unsure",
       nrow("9").locator(".conf.un").count() == 1)
    ck("a booking with no number says so instead of showing nothing",
       "no number" in nrow("2").locator(".ph").text_content()
       and nrow("2").locator(".conf").count() == 0)
    ck("and every row carries the pencil, arrived guests included",
       pg.evaluate("()=>[...document.querySelectorAll('.arr')]"
                   ".every(e=>!!e.querySelector('.pen'))"))

    #  The pencil edits the number: prompt, normalise, save to /phonefix with
    #  the Mews value kept as `was`. The tap must not also open the summary
    #  the row underneath it would open.
    pg.on("dialog", lambda d: d.accept("(+64) 274875277"))
    del WRITES[:]
    nrow("4").locator(".pen").click(); pg.wait_for_timeout(900)
    fixw = [w for w in WRITES if "/phonefix/b4" in w["u"]]
    ck("the pencil saves the fix normalised, with the Mews value as `was`",
       len(fixw) == 1 and json.loads(fixw[0]["b"])["phone"] == "+64274875277"
       and json.loads(fixw[0]["b"])["was"] == "+61 411 222 333")
    ck("without opening the summary underneath",
       pg.evaluate("()=>!document.querySelector('.sum')"))
    ck("and the row then shows the fix, which outranks the Mews copy",
       "+64274875277" in nrow("4").locator(".ph").text_content())
    FIXES.clear()
    pg.close()

    # ── the "no allergies" pill survives the cell it creates ────────────
    #  Reported 27 Aug: confirm a guest, reopen the sheet after any change,
    #  and "No allergies to declare" sat deselected - and the next save wrote
    #  that deselection onto the booking as a fact nobody stated. The cell
    #  the confirm had written outranks the booking on read-back, and the
    #  desk neither wrote the answer into it nor asked for it by the cell's
    #  name: the cell spells it `nodiet` (the guest page's coinage, already
    #  in rules.json), and the desk was reading a `noDiets` no cell ever
    #  carried. The answer is a dietary like any other and rides where the
    #  dietaries ride.
    del WRITES[:]
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=checkin]').click()")
    pg.wait_for_timeout(700)
    cw = [json.loads(x["b"]) for x in WRITES
          if ("/dinner/" + today + "/9") in x["u"] and x["m"] == "PUT"]
    ck("saving from the summary writes the answer into the cell, under the cell's name",
       len(cw) == 1 and cw[0].get("nodiet") is True)
    pg.close()

    #  The round trip: the same cell read back, seeded as the confirm wrote it.
    DINNER["9"] = {"status": "out", "pax": 0, "room": "9", "by": "staff",
                   "diets": [], "dnote": "", "nodiet": True,
                   "at": "2026-08-17T14:00:00Z"}
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    ck("the summary still reads the answer back over the cell",
       "No allergies to declare" in pg.locator(".sum").inner_text())
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(600)
    ck("and the pill opens selected, not deselected",
       pg.evaluate("""()=>[...document.querySelectorAll('#dNone .chip')]
         .find(b=>/^No allergies/.test(b.textContent)).className.indexOf('on')>-1"""))
    #  A save that touches nothing must keep saying it, on both nodes.
    del WRITES[:]
    pg.evaluate("()=>document.getElementById('sConfirm').click()")
    pg.wait_for_timeout(700)
    saved = [json.loads(x["b"]) for x in WRITES if "/bookings/b9/prearrival" in x["u"]]
    ck("an untouched save keeps saying no allergies on the booking",
       bool(saved) and all(d.get("noDiets") is True for d in saved))
    cw = [json.loads(x["b"]) for x in WRITES
          if ("/dinner/" + today + "/9") in x["u"] and x["m"] == "PUT"]
    ck("and on the cell",
       bool(cw) and all(d.get("nodiet") is True for d in cw))
    pg.close()

    #  A cell from before the fix carries no key at all, which says nothing
    #  either way, so the booking's answer shows through rather than being
    #  outranked by silence.
    DINNER["9"] = {"status": "out", "pax": 0, "room": "9", "by": "staff",
                   "at": "2026-08-17T14:00:00Z"}
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(600)
    ck("a cell that predates the answer does not outrank the booking",
       pg.evaluate("""()=>[...document.querySelectorAll('#dNone .chip')]
         .find(b=>/^No allergies/.test(b.textContent)).className.indexOf('on')>-1"""))
    pg.close()

    #  A dietary on the cell contradicts a stored "none": the list wins,
    #  whichever node each came from, or the sheet opens claiming both.
    DINNER["9"] = {"status": "in", "pax": 2, "room": "9", "by": "staff",
                   "diets": ["Gluten free"], "at": "2026-08-17T14:00:00Z"}
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(300)
    pg.evaluate("()=>document.querySelector('.sum-btns [data-act=edit]').click()")
    pg.wait_for_timeout(600)
    ck("a dietary added on the kitchen's board beats the booking's old 'none'",
       pg.evaluate("""()=>[...document.querySelectorAll('#dNone .chip')]
         .find(b=>/^No allergies/.test(b.textContent)).className.indexOf('on')<0"""))
    pg.close()
    DINNER.clear()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
