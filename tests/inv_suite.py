"""invitations.html, sending the menu link by SMS.

The page decides who to send to; a Cloudflare Worker does the sending and is
stubbed here, exactly as Firebase is. The things most worth pinning down:

  1. The link is built from the stay record, never from anything typed, and
     carries the booking id AND the villa. The 22 Aug failure was a link with
     a merge field unmerged; a link a human can edit is the same failure
     waiting.
  2. Nothing sends before the menu is published, and a failed menu read is
     worded as the connection, never as no menu.
  3. Failures are per villa: four of six succeeding is the normal case for a
     bad number, and it must be visible which two did not.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, datetime, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8977), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

now = datetime.datetime.now().astimezone()
today = now.strftime("%Y-%m-%d")

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

#  Villa 4: ready. Villa 7: answered yes, by the guest. Villa 11: answered no,
#  by staff. Villa 2: no phone. Villa 9: already sent to. Villa 14: a send
#  that failed. Villa 5: the older bare id shape, which must not crash.
STAYS = {
  "4":  {"id":"b4-guid","first":"Robyn","last":"Williams","phone":"+61 411 111 111","adults":2},
  "7":  {"id":"b7-guid","first":"Mark","last":"Whitfield","phone":"+61 422 222 222","adults":2},
  "11": {"id":"b11-guid","first":"Priya","last":"Raghunathan","phone":"+61 433 333 333","adults":3},
  "2":  {"id":"b2-guid","first":"James","last":"Fisher","adults":2},
  #  A real Mews record: a landline typed into the mobile field. ClickSend
  #  wants E.164 and this cannot become it, so it is as unsendable as no
  #  number and for the same reason - it is a Mews record, not fixable here.
  "3":  {"id":"b3-guid","first":"Tomas","last":"Lind","phone":"02 9999 9999","adults":2},
  "9":  {"id":"b9-guid","first":"Nadia","last":"Okonkwo","phone":"+61 444 444 444","adults":2},
  "14": {"id":"b14-guid","first":"Ann","last":"Brown","phone":"+61 455 555 555","adults":1},
  "5":  "bare-id-old-shape",
}
DINNER = {
  "7":  {"status":"in","pax":2,"by":"guest","at":now.replace(hour=16,minute=12).isoformat()},
  "11": {"status":"out","by":"reception@x","at":now.replace(hour=15,minute=0).isoformat()},
}
INVITES = {
  "9":  {"status":"sent","sentAt":now.replace(hour=17,minute=5).isoformat(),
         "to":"+61 444 444 444","by":"staff@x"},
  "14": {"status":"failed","sentAt":now.replace(hour=17,minute=6).isoformat(),
         "error":"INVALID_RECIPIENT","by":"staff@x"},
}
MENU = {"bread":{"name":"Sourdough"},"entree":{"name":"Scallops"},
        "main":{"name":"Barramundi"},"dessert":{"name":"Pavlova"},
        "published": now.isoformat()}

STATE = {"menu": MENU, "menufail": False}
WRITES = []
SENT = []            # every POST that reached the stubbed Worker
WORKER = {"reply": None}   # per-villa results the stub answers with

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE", "POST"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/opened/" in u: body = "null"
    elif "/invites/" + today in u: body = json.dumps(INVITES)
    elif "/bookings/" in u: body = "null"
    elif "/menutags/" in u: body = "null"
    elif "/menuhistory" in u: body = json.dumps({"main": "Barramundi",
                                                 "published": MENU["published"]})
    elif u.split("?")[0].endswith("/menu.json"):
        if STATE["menufail"]:
            route.abort(); return
        body = json.dumps(STATE["menu"]) if STATE["menu"] else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

def wk(route, request):
    SENT.append(json.loads(request.post_data))
    villas = SENT[-1]["villas"]
    results = WORKER["reply"] or {v: {"status": "sent"} for v in villas}
    route.fulfill(status=200, content_type="application/json",
                  body=json.dumps({"results": results}))

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)) if not cond and detail else ""))
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def board(email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**nala-invites.ben-681.workers.dev/**", wk)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        # menu.json, the committed fallback: present and stale, as in the real
        # repo, so the shared reader refuses it by date. Serving a 404 here
        # would read as a FAILED read, which is a different state and worded
        # differently on the page. When the connection is down, it is down
        # for the file too.
        def fallback(r):
            if STATE["menufail"]:
                r.abort(); return
            stale = dict(MENU, published=(now - datetime.timedelta(days=2)).isoformat())
            r.fulfill(status=200, content_type="application/json",
                      body=json.dumps(stale))
        pg.route("**localhost:8977/menu.json*", fallback)
        pg.goto("http://localhost:8977/invitations.html")
        pg.wait_for_timeout(1600)
        return pg

    # ── the four states ─────────────────────────────────────────
    pg = board()
    def row(v): return pg.locator('.vrow[data-villa="%s"]' % v)
    ck("a villa with no dinner answer is ticked by default",
       "on" in (row("4").get_attribute("class") or ""))
    ck("one that has answered is not",
       "on" not in (row("7").get_attribute("class") or ""))
    ck("and its reason is on the row, with the pax and the time",
       "Dining · 2 · answered 4:12pm" in row("7").inner_text())
    ck("an answer set by staff says so rather than a time",
       "Not dining · set by reception" in row("11").inner_text())
    ck("but both stay tickable, for the guest who wants to see tonight's menu",
       not row("7").is_disabled() and not row("11").is_disabled())
    ck("a villa whose number cannot be normalised cannot be ticked either",
       row("3").is_disabled())
    ck("and says why, naming the number so reception can fix it in Mews",
       "Not a mobile number · 02 9999 9999" in row("3").inner_text())
    ck("a villa with no phone number cannot be ticked at all",
       row("2").is_disabled())
    ck("with the reason on the row, because it cannot be fixed here",
       "No phone number" in row("2").inner_text())
    ck("a villa already sent to is unticked and shows the time",
       "on" not in (row("9").get_attribute("class") or "")
       and "Sent 5:05pm" in row("9").inner_text())
    ck("a failed send is not a sent villa: ticked again, reason showing",
       "on" in (row("14").get_attribute("class") or "")
       and "INVALID_RECIPIENT" in row("14").inner_text())
    ck("the older bare id shape is skipped rather than crashing",
       pg.evaluate("()=>document.querySelectorAll('.vrow[data-villa=\"5\"]').length") == 0)
    ck("villas run in villa order",
       pg.evaluate("()=>[...document.querySelectorAll('.vrow')].map(e=>e.dataset.villa)")
       == ["2", "3", "4", "7", "9", "11", "14"])
    ck("the counts say the same thing as the rows",
       [pg.evaluate("()=>%s.textContent" % i) for i in ("nSend","nAns","nSent","nNoPh")]
       == ["2", "2", "1", "2"])
    ck("the button carries the count",
       pg.evaluate("()=>sendBtn.textContent") == "Send to 2 guests")

    # ── ticking ────────────────────────────────────────────────
    row("7").click(); pg.wait_for_timeout(150)
    ck("an answered villa can still be brought in",
       "on" in (row("7").get_attribute("class") or "")
       and pg.inner_text("#nSend") == "3")
    row("7").click(); pg.wait_for_timeout(150)

    # ── the message ────────────────────────────────────────────
    ck("the box holds the template, with the marker and the resort's name",
       "<link>" in pg.input_value("#msgBox") and "Nala Resort" in pg.input_value("#msgBox"))
    ck("the short template, link included, is one segment and says so",
       "1 segment" in pg.inner_text("#msgCount"))
    pg.select_option("#tmpl", "reminder"); pg.wait_for_timeout(100)
    ck("choosing a template rewrites the box",
       "not heard about dinner" in pg.input_value("#msgBox"))
    ck("and the longer one, link included, is about two segments",
       "2 segments" in pg.inner_text("#msgCount"))
    pg.fill("#msgBox", "Menu here: https://evil.example/x"); pg.wait_for_timeout(150)
    ck("typing a URL is warned about as it is typed",
       "cannot be typed" in pg.inner_text("#msgWarn"))
    del SENT[:]
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(300)
    ck("and the send is refused: the body cannot be made to carry a second URL",
       SENT == [] and "contains a link" in pg.inner_text("#errBar"))
    pg.select_option("#tmpl", "ready"); pg.wait_for_timeout(100)

    # ── sending ────────────────────────────────────────────────
    del SENT[:]
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(500)
    ck("one press sends when nobody is being sent to twice", len(SENT) == 1)
    ck("the page proposes villas and words, never numbers and never a link",
       SENT and sorted(SENT[0]["villas"]) == ["14", "4"]
       and "<link>" in SENT[0]["body"]
       and "http" not in SENT[0]["body"]
       and "phone" not in json.dumps(SENT[0]))
    ck("and says which day it is proposing for", SENT and SENT[0]["date"] == today)

    # ── sending twice takes a second press ─────────────────────
    pg = board()
    row("9").click(); pg.wait_for_timeout(150)     # already sent tonight
    ck("the button says what it is about to do",
       pg.evaluate("()=>sendBtn.textContent") == "Send to 3 guests, 1 of them again")
    del SENT[:]
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(300)
    ck("the first press does not send", SENT == [])
    ck("it asks for the second",
       "Press again" in pg.evaluate("()=>sendBtn.textContent"))
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(500)
    ck("the second press sends", len(SENT) == 1 and "9" in SENT[0]["villas"])

    # ── a partial failure names which villas failed ────────────
    pg = board()
    WORKER["reply"] = {"4": {"status": "sent"},
                       "14": {"status": "failed", "error": "INVALID_RECIPIENT"}}
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(600)
    ck("the two that did not go are named",
       "villa 14" in pg.inner_text("#errBar").replace("villas", "villa"))
    WORKER["reply"] = None

    # ── nothing sends before the menu is published ─────────────
    STATE["menu"] = None
    pg = board()
    ck("with no menu published the send button is disabled",
       pg.locator("#sendBtn").is_disabled())
    ck("and the page says why",
       "No menu is published" in pg.inner_text("#menuGate"))
    STATE["menu"] = dict(MENU,
        published=(now - datetime.timedelta(days=2)).isoformat())
    pg = board()
    ck("a menu published two days ago is not tonight's menu",
       pg.locator("#sendBtn").is_disabled())
    STATE["menu"] = MENU
    STATE["menufail"] = True
    pg = board()
    ck("a failed menu read refuses too, worded as the connection",
       pg.locator("#sendBtn").is_disabled()
       and "connection" in pg.inner_text("#menuGate"))
    STATE["menufail"] = False

    # ── the link comes off the stay record ─────────────────────
    #  The page never builds the outgoing link itself: that is the Worker's,
    #  from its own read. What the page must prove is that its one builder
    #  carries both parameters, so the eventual short token is a one-function
    #  swap here and in the Worker.
    pg = board()
    ck("the link built for a villa carries its booking id AND its villa number",
       pg.evaluate("()=>inviteLink(ROWS['4'].stay.id, '4')")
       == "https://menu.nalaresort.com/?b=b4-guid&r=4")

    # ── the number rule, against the one shared table ──────────
    #  normalisePhone exists twice: here in nala-shared.js for deciding
    #  sendability, and again in the Worker for sending, because a Worker
    #  cannot import from the site. Both are held to tests/phone_cases.json;
    #  invites-test.mjs runs the same file through both copies. A case added
    #  there fails whichever copy has not learned it.
    cases = json.load(open("tests/phone_cases.json"))["cases"]
    wrong = pg.evaluate("""(cases)=>cases.filter(c=>normalisePhone(c[0])!==c[1])
        .map(c=>c[0]+' -> '+normalisePhone(c[0])+', wanted '+c[1])""",
        [[c[0], c[1]] for c in cases])
    ck("the page's copy of the number rule matches every shared case",
       wrong == [], wrong)

    # ── who may see it ─────────────────────────────────────────
    for who in ("chef@x", "housekeeping@x"):
        q = board(who); q.wait_for_timeout(600)
        ck("a %s is sent to their own board rather than shown the page" % STAFF[who]["role"],
           not q.url.endswith("invitations.html"))
        q.close()
    q = board("waiter@x")
    ck("a waiter holds editBookings and gets the page",
       q.url.endswith("invitations.html")
       and q.locator(".vrow").count() == 7)
    q.close()

    # The link in the hamburger lives on every other page and is filtered by
    # the same permission. Checked from one of them.
    pg2 = b.new_page(viewport={"width": 390, "height": 900})
    pg2.add_init_script(SDK)
    pg2.route("**firebasedatabase.app/**", fb)
    pg2.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg2.goto("http://localhost:8977/tally.html")
    pg2.wait_for_timeout(1600)
    seen = pg2.evaluate("""()=>{ const out={};
      ['waiter','chef','housekeeping','admin'].forEach(r=>{
        window.NALA_NAVFILTER(r);
        out[r]=[...document.querySelectorAll('#navDrop a')]
          .filter(a=>getComputedStyle(a).display!=='none')
          .map(a=>a.getAttribute('href'));
      }); return out; }""")
    ck("the hamburger offers Invitations to a waiter and the manager",
       "invitations.html" in seen["waiter"] and "invitations.html" in seen["admin"])
    ck("and to nobody who cannot open it",
       "invitations.html" not in seen["chef"]
       and "invitations.html" not in seen["housekeeping"])
    pg2.close()

    # ── widths ─────────────────────────────────────────────────
    for w in (390, 360, 320):
        q = board(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
