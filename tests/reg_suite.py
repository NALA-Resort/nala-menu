"""registration.html, the printed card handed over at check in.

Print tier. Two things matter more than anything else on a page that ends up on
paper:

  1. An unanswered question prints as a rule to write on, not as blank space.
     The card is the working document at the desk, so a gap has to be writable.
  2. One card per page. A card that breaks across a page break is a card
     somebody hands over half of.

It also carries the menu conflict, and here it earns its place twice over: the
card goes to the kitchen, and the kitchen is who acts on it.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8970), Q)
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

STAFF = {"staff@x": {"name":"Admin","role":"admin"},
         "housekeeping@x": {"name":"HK","role":"housekeeping"}}

STAYS = {
  # b4's Mews companion is the decoy the guest's typed name must beat; b9's
  # is a name only Mews knows, which must still print rather than a blank rule.
  "4":  {"id":"b4","first":"Robyn","last":"Williams","arrive":today,"depart":plus(4),
         "adults":2,"number":1159,"companion":"Wrong Name"},
  "9":  {"id":"b9","first":"Konstantinos","last":"Papadopoulos","arrive":today,"depart":plus(2),"adults":4,
         "companion":"Eleni Papadopoulou"},
  "2":  {"id":"b2","first":"James","last":"Fisher","arrive":today,"depart":plus(6),"adults":2},
  # in house, arrived two days ago. Must not get a card this morning.
  "3":  {"id":"b3","first":"Midstay","last":"Guest","arrive":plus(-2),"depart":plus(2),"adults":2},
  "5":  "bare-id-old-shape"
}

PRE = {
  "b4": {"at":"2026-08-16T10:00:00Z","arriveSlot":"16","dining":True,"pax":2,
         "companion":"Imogen Clarke",
         "diets":["Nut allergy"],"dnote":"the daughter, severe",
         "purpose":["A celebration"],"approach":"most","occasion":"anniversary",
         "wellness":True,"wellDay":plus(1),"wellTime":"late morning",
         "note":"quiet villa please"},
  "b9": {"at":"2026-08-16T11:00:00Z","arriveSlot":"before2",
         "arriveNote":"flight lands 11am","dining":False,"noDiets":True,
         "purpose":["A short break"],"approach":"out","wellness":False}
  # b2 has sent nothing: its card must be blank and writable throughout
}
TAGS = {"main": ["Nut allergy"]}

# The booking as Mews states it. Its villa settles a disagreement with /stays.
PMS = {}

# The Spa board's records, /spa/<booking>. Empty until the wellness block.
SPADB = {}

def fb(route, request):
    u = request.url
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/menutags/" in u: body = json.dumps(TAGS) if today in u else "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u: body = "null"
    elif "/bookings/" in u and "/prearrival" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE[k]) if k in PRE else "null"
    elif "/bookings/" in u and "/pms" in u:
        k = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PMS[k]) if k in PMS else "null"
    elif "/spa/" in u:
        k = u.split("/spa/")[1].split(".json")[0].split("/")[0]
        body = json.dumps(SPADB[k]) if k in SPADB else "null"
    else: body = "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def sheet(email="staff@x"):
        pg = b.new_page(viewport={"width": 794, "height": 1123})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8970/registration.html")
        pg.wait_for_timeout(1600)
        return pg

    pg = sheet()
    ck("one card per arriving villa",
       pg.evaluate("()=>document.querySelectorAll('.card').length") == 3)
    ck("a guest mid stay gets no card, though they are in house tonight",
       "Midstay" not in pg.locator("#cards").inner_text())
    ck("an entry in the older bare id shape is ignored rather than crashing",
       pg.evaluate("()=>document.querySelectorAll('.card').length") == 3)
    ck("cards are ordered by villa",
       pg.evaluate("()=>[...document.querySelectorAll('.c-villa')].map(e=>e.textContent)")
       == ["2", "4", "9"])

    def card(v):
        return pg.evaluate("()=>[...document.querySelectorAll('.card')]"
                           ".find(c=>c.querySelector('.c-villa').textContent==='%s').innerText" % v)

    c4 = card("4")
    ck("the guest's answers are printed", "Approx 4pm" in c4 and "anniversary" in c4)
    ck("dinner with the covers", "Dining" in c4 and "2 guests" in c4)
    ck("the dietary and whose it is", "Nut allergy" in c4 and "the daughter" in c4)
    ck("the treatment day and time", "Interested" in c4 and "late morning" in c4)
    #  The 23 Aug rewrite asks frequency; "most" now prints as its new words.
    ck("dining plans in words, not a stored code", "Most nights" in c4)
    # .c-stay is uppercased by CSS, so innerText comes back shouting.
    # On paper it is the only way back to the PMS record: the card has no GUID.
    ck("the card carries the Mews reservation number", "MEWS 1159" in c4.upper())
    ck("the stay as a range, since paper has room for it",
       " TO " in c4.upper() and "NIGHTS" in c4.upper())

    # The card goes to the kitchen and the kitchen is who acts.
    ck("an allergy the night's menu contains is called out on paper",
       "Menu conflict" in c4)
    ck("and not on a guest who is not dining", "Menu conflict" not in card("9"))

    c9 = card("9")
    ck("an open ended arrival carries the note explaining it",
       "Before 2pm" in c9 and "flight lands 11am" in c9)
    ck("no allergies is printed as an answer, not left blank",
       "None to declare" in c9)

    # ── the second guest ─────────────────────────────────────────
    # .lbl is uppercased by CSS, so innerText comes back shouting.
    ck("the second guest prints, named from the form",
       "SECOND GUEST" in c4.upper() and "Imogen Clarke" in c4)
    ck("and the name the guest typed outranks the Mews copy",
       "Wrong Name" not in c4)
    ck("a companion only Mews knows still prints, not a blank rule",
       "Eleni Papadopoulou" in c9)
    ck("a booking of two with nobody named keeps the rule to write on",
       "SECOND GUEST" in card("2").upper())

    # A guest who sent nothing. This is the case the card exists for.
    #
    # Counting .val.blank alone stopped meaning anything on 19 Aug, when an
    # unanswered question started printing the guest form's own options as
    # tick boxes instead of an empty rule. Three questions still take a rule,
    # the rest take boxes or writing lines, and the assertion that matters is
    # that NO question is left with nothing to fill in.
    fillable = pg.evaluate("""()=>{const c=[...document.querySelectorAll('.card')]
      .find(c=>c.querySelector('.c-villa').textContent==='2');
      const rows=[...c.querySelectorAll('.row')];
      return {total:rows.length, ok:rows.filter(r=>r.querySelector(
        '.val.blank, .ticks, .notelines')).length};}""")
    ck("a guest who sent nothing gets somewhere to answer every question",
       fillable["total"] > 0 and fillable["ok"] == fillable["total"])

    ticked = pg.evaluate("""()=>{const c=[...document.querySelectorAll('.card')]
      .find(c=>c.querySelector('.c-villa').textContent==='2');
      return [...c.querySelectorAll('.tk')].map(e=>e.textContent);}""")
    ck("and the boxes offer the same dietaries the guest form does",
       "Gluten" in ticked and "Nut allergy" in ticked and "Other" in ticked)
    ck("under the renamed wording, since the pills lost their 'free' on 26 Aug",
       "Gluten free" not in ticked and "Dairy" in ticked)
    ck("and Dining carries a count, because Dining alone is not a cover number",
       "How many" in card("2"))

    # Arriving is read at a glance and its answer is a time plus a reason.
    # Six boxes there would crowd out the room to write the reason.
    ck("but Arriving is a rule to write on, not boxes",
       pg.evaluate("""()=>{const c=[...document.querySelectorAll('.card')]
         .find(c=>c.querySelector('.c-villa').textContent==='2');
         const r=c.querySelector('.row.eta');
         return !!r && !r.querySelector('.tk') && !!r.querySelector('.val.blank');}"""))
    ck("but their name and stay are still printed, because Mews knows those",
       "James Fisher" in card("2"))

    ck("every card has somewhere to sign",
       pg.evaluate("()=>document.querySelectorAll('.card .sig').length") == 3)
    ck("and the sheet says when it was printed",
       "PRINTED" in pg.locator("#stamp").inner_text().upper())

    # A card split across a page is a card handed over in halves.
    ck("no card is taller than a printable page",
       pg.evaluate("""()=>[...document.querySelectorAll('.card')]
         .every(c=>c.getBoundingClientRect().height < 1000)"""))
    ck("each card starts a new page",
       pg.evaluate("""()=>[...document.querySelectorAll('.card')].slice(0,-1)
         .every(c=>getComputedStyle(c).breakAfter==='page'
                || getComputedStyle(c).pageBreakAfter==='always')"""))
    pg.close()


    # ── the Wellness row is the Spa board's truth, not the form's ─
    # Found 23 Sep: the card read the form alone, so a massage the masseuse
    # had booked, suggested or declined still printed "Interested". The
    # words are the Front Desk summary's (wellnessLines, nala-shared.js).
    def well(v):
        return pg.evaluate("""()=>{const c=[...document.querySelectorAll('.card')]
          .find(c=>c.querySelector('.c-villa').textContent==='%s');
          const r=[...c.querySelectorAll('.row')]
          .find(r=>r.querySelector('.lbl').textContent==='Wellness');
          return r.querySelector('.val').innerText;}""" % v)
    pg = sheet()
    w = well("4")
    ck("the form's ask with no record reads Interested, waiting on the masseuse",
       "Interested" in w and "late morning" in w and "waiting on the masseuse" in w)
    ck("and a guest who said no still reads Not interested", well("9") == "Not interested")
    pg.close()
    CASES = [
      ("booked", {"t1": {"status":"booked","day":plus(1),"time":"14:00",
                         "source":"prearrival","at":"x"}},
       ["Booked", "2:00 pm"], ["Interested"]),
      ("booked at the desk", {"t1": {"status":"booked","day":plus(1),"time":"14:00",
                         "manual":True,"source":"prearrival","at":"x"}},
       ["Booked", "approved at the desk"], ["Interested"]),
      ("suggested", {"t1": {"status":"suggested","day":plus(2),"time":"16:30",
                            "source":"prearrival","at":"x"}},
       ["Suggested", "4:30 pm", "waiting on the guest"], ["Interested"]),
      ("asked", {"t1": {"status":"requested","reqDay":plus(1),"reqTime":"late morning",
                        "source":"prearrival","at":"x"}},
       ["Asked", "waiting on the masseuse"], ["Interested"]),
      ("declined", {"t1": {"status":"declined","note":"nothing free",
                           "source":"prearrival","at":"x"}},
       ["Declined", "nothing free", "let the guest know"], ["Interested"]),
      ("declined, told", {"t1": {"status":"declined","note":"nothing free","told":True,
                           "source":"prearrival","at":"x"}},
       ["Declined", "guest told"], ["let the guest know"]),
    ]
    for name, rec, has, hasnt in CASES:
        SPADB["b4"] = rec
        pg = sheet()
        w = well("4")
        ck("a %s massage prints as %s" % (name, has[0]),
           all(x in w for x in has) and not any(x in w for x in hasnt))
        pg.close()
    SPADB["b4"] = {"t1": {"status":"booked","day":plus(1),"time":"14:00",
                          "source":"prearrival","at":"x"}}
    pg = sheet()
    ck("the status word is bold, because paper has no colour to carry it",
       pg.evaluate("""()=>[...document.querySelectorAll('.card .val b')]
         .some(b=>b.textContent==='Booked')"""))
    pg.close()
    # A record keyed straight onto the board, with no form answer at all:
    # the card has an answer, so it prints it rather than tick boxes.
    SPADB["b2"] = {"t1": {"status":"booked","day":plus(1),"time":"10:00","at":"x"}}
    pg = sheet()
    w = well("2")
    ck("a board booking with no form answer prints, not as boxes",
       "Booked" in w and "10:00 am" in w and "Not interested" not in w)
    pg.close()
    SPADB.clear()

    # Three cards for one guest is three registration forms at the desk. A move
    # leaves entries behind in /stays and the Worker only clears them on that
    # booking's next event.
    for v in ("13", "15", "16"):
        STAYS[v] = {"id":"bmoved","first":"Ben","last":"Davidson",
                    "arrive":today,"depart":plus(1),"adults":2}
    PMS["bmoved"] = {"villa": "15"}
    pg = sheet()
    villas = pg.evaluate("()=>[...document.querySelectorAll('.c-villa')].map(e=>e.textContent)")
    ck("one booking prints one card, not three",
       len([v for v in villas if v in ("13","15","16")]) == 1)
    ck("and it is the villa Mews says they are in", "15" in villas)
    pg.close()
    for v in ("13", "15", "16"): del STAYS[v]
    del PMS["bmoved"]

    # Nothing to print is a sentence, not an empty page.
    STAYS_BACKUP = dict(STAYS)
    STAYS.clear()
    pg = sheet()
    ck("a day with no arrivals says so", "No arrivals" in pg.locator("#cards").inner_text())
    pg.close()
    STAYS.update(STAYS_BACKUP)

    pg = sheet("housekeeping@x")
    pg.wait_for_timeout(600)
    ck("housekeeping is sent to their own board rather than shown a refusal",
       not pg.url.endswith("registration.html"))
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
