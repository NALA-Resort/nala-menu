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
          "arriveBy":"4pm","purpose":["Celebration"],"approach":"most",
          "occasion":"anniversary","wellness":True,"note":"quiet villa please"},
  "b9":  {"at":"2026-08-16T11:00:00Z","dining":False,"noDiets":True},
  # confirmed at the desk
  "b7":  {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:00:00Z","dining":True,"pax":2},
  "b11": {"at":"2026-08-15T10:00:00Z","confirmedAt":"2026-08-17T14:05:00Z","dining":False}
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
    ck("arrivals are ordered by villa within each section",
       todo == sorted(todo, key=int) and doneV == sorted(doneV, key=int))
    ck("and the ones still to do come first, because that is the job",
       villas == todo + doneV)
    ck("the count is the arrivals, not every stay",
       pg.evaluate("()=>nArr.textContent") == str(len(villas)))
    # six arrivals, of which villas 7 and 11 are already confirmed
    ck("to confirm counts only those reception has not been through",
       pg.evaluate("()=>nLeft.textContent") == "4")
    ck("and goes red while any remain",
       pg.evaluate("()=>tileLeft.className.indexOf('due')>-1"))

    # ── the pills say what state each guest is in ───────────────
    def pill(v):
        return pg.evaluate("()=>{const e=document.querySelector('.arr[data-villa=\"%s\"] .pill');"
                           "return e?e.className+'|'+e.textContent:null;}" % v)
    ck("a guest with no form at all", "none|No form" in pill("2"))
    ck("a guest who filled it in but has not been confirmed", "part|Form done" in pill("4"))
    ck("a confirmed guest shows the answer, not the word confirmed",
       "din|Dining" in pill("7"))
    ck("and confirmed includes not dining", "out|Not dining" in pill("11"))

    # ── the sheet is edit, not create ───────────────────────────
    pg.locator('.arr[data-villa="4"]').click(); pg.wait_for_timeout(400)
    ck("the sheet opens on the villa tapped",
       "VILLA 4" in pg.locator("#sheet h3").inner_text().upper())
    ck("the guest's own answers are already there: dining",
       pg.evaluate("()=>sDin.className==='on'"))
    ck("their covers", pg.evaluate(
       "()=>[...document.querySelectorAll('#paxRow .pax')].find(e=>e.className.indexOf('on')>-1).textContent")=="2")
    ck("their dietary", pg.evaluate(
       "()=>[...document.querySelectorAll('#dChips .chip')].some(e=>e.textContent==='Nut allergy'&&e.className.indexOf('on')>-1)"))
    ck("the note about whose allergy it is",
       pg.evaluate("()=>fDnote.value") == "the daughter, severe")
    ck("their arrival time", pg.evaluate("()=>fArrive.value") == "4pm")
    ck("their special occasion", pg.evaluate("()=>fOcc.value") == "anniversary")
    ck("their free text", pg.evaluate("()=>fNote.value") == "quiet villa please")
    ck("purpose of visit, which is advisory and never drives logic",
       pg.evaluate("()=>[...document.querySelectorAll('#pChips .chip')]"
                   ".some(e=>e.textContent==='Celebration'&&e.className.indexOf('on')>-1)"))
    ck("and the wellness answer", pg.evaluate("()=>wYes.className==='on'"))
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
    ck("and the guest moves to confirmed without a reload",
       "din|Dining" in pill("4"))
    ck("with the count following", pg.evaluate("()=>nLeft.textContent") == "3")
    pg.close()

    # ── a guest with no form is the same screen, empty ──────────
    pg = board()
    pg.locator('.arr[data-villa="2"]').click(); pg.wait_for_timeout(400)
    ck("a guest with no form gets the same fields, not a different flow",
       pg.evaluate("()=>!!document.getElementById('fArrive')"))
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

    # ── a failed save must not look like success ────────────────
    STATE["fail"] = True
    pg = board()
    pg.locator('.arr[data-villa="9"]').click(); pg.wait_for_timeout(400)
    pg.locator("#sDin").click()
    pg.locator("#sConfirm").click(); pg.wait_for_timeout(600)
    ck("a rejected save says so", "Could not save" in pg.locator("#errBar").inner_text())
    ck("and the guest is put back rather than left looking confirmed",
       "part|Form done" in pill("9"))
    STATE["fail"] = False
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
        ck("nor does the sheet at %dpt" % w, not pg.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
