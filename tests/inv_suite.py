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

#  The pre-arrival window, for arrivals-sms.html. /stays holds every night
#  mews-sync knows about; an arrival on d is the stay at /stays/<d> whose own
#  arrive IS d. Villa 8 is in house already (arrived yesterday), so it must
#  not appear; villa 3 spans two nights, so it must appear once.
def dplus(n): return (now + datetime.timedelta(days=n)).strftime("%Y-%m-%d")
def stay(id, first, last, phone, a, d, extra=None):
    s = {"id": id, "first": first, "last": last, "phone": phone,
         "arrive": dplus(a), "depart": dplus(d)}
    s.update(extra or {})
    return s
NIGHTS = {
  dplus(1): {"6":  stay("pa-ready", "Harper", "Quinn", "+61 411 000 001", 1, 3),
             "8":  stay("pa-inhouse", "Old", "Guest", "+61 411 000 008", -1, 2),
             "14": stay("pa-done", "Robyn", "Carter", "+61 411 000 002", 1, 2)},
  dplus(2): {"3":  stay("pa-sent", "Anna", "Lindqvist", "+61 411 000 003", 2, 4),
             "9":  stay("pa-landline", "D.", "Kessler", "07 3358 1122", 2, 3)},
  dplus(3): {"3":  stay("pa-sent", "Anna", "Lindqvist", "+61 411 000 003", 2, 4),
             "12": stay("pa-open", "Kai", "Werner", "+61 411 000 004", 3, 5)},
  dplus(10): {"5": stay("pa-far", "Grace", "Ito", "+61 411 000 005", 10, 12)},
}
PRE_RECS = {
  #  A form a guest actually finished: the dietary question is required of
  #  them, so a record without one was never a completed form. It carries one
  #  since 28 Aug, when completed stopped meaning "has a stamp" and started
  #  meaning "has the stamp AND the mandatory answers" - formState, shared
  #  with the Front Desk so the two boards cannot disagree about it again.
  "pa-done": {"at": now.isoformat(), "openedAt": now.isoformat(),
              "dining": True, "noDiets": True},
  "pa-open": {"openedAt": now.isoformat(), "purpose": "Rest"},
}
PREINV = {
  "pa-sent": {"status": "sent", "sentAt": now.isoformat(), "to": "+61411000003",
              "by": "staff@x", "providerId": "mid-s", "delivery": "delivered"},
}

STATE = {"menu": MENU, "menufail": False}
WRITES = []
SENT = []            # every POST that reached the stubbed Worker
WORKER = {"reply": None}   # per-villa results the stub answers with

FIXES = {}   # bookingId -> the /phonefix record, persisted across the stub

#  The /spa node, whole, as arrivals-sms reads it since 10 Sep: a record
#  born on the Spa board answers the massage question (massageAnswered,
#  nala-shared.js), so the page reads the node the way the Dashboard does.
SPA_ALL = {}

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE", "POST"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        #  /phonefix persists, because the fix flow reloads and must see it.
        if m == "PUT" and "/phonefix/" in u:
            FIXES[u.split("/phonefix/")[1].split(".json")[0]] = \
                json.loads(request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/permissions" in u: body = "null"
    elif u.split("?")[0].endswith("/stays.json"):
        #  arrivals-sms.html's one ranged read over the window, orderBy="$key".
        #  The window is today's stays plus the NIGHTS days; return the nights
        #  whose keys fall inside [startAt, endAt].
        from urllib.parse import urlparse, parse_qs, unquote
        q = parse_qs(urlparse(u).query)
        lo = unquote(q.get("startAt", ['""'])[0]).strip('"')
        hi = unquote(q.get("endAt", ['"￿"'])[0]).strip('"')
        allstays = dict(NIGHTS); allstays[today] = STAYS
        win = {k: v for k, v in allstays.items() if lo <= k <= hi}
        body = json.dumps(win) if win else "null"
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u:
        d = u.split("/stays/")[1].split(".json")[0]
        body = json.dumps(NIGHTS[d]) if d in NIGHTS else "null"
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/opened/" in u: body = "null"
    elif "/invites/" + today in u: body = json.dumps(INVITES)
    elif u.split("?")[0].endswith("/previnvites.json"):
        #  arrivals-sms reads the send log whole now, plucked by id.
        body = json.dumps(PREINV) if PREINV else "null"
    elif "/previnvites/" in u:
        bid = u.split("/previnvites/")[1].split(".json")[0]
        body = json.dumps(PREINV[bid]) if bid in PREINV else "null"
    elif "/phonefix/" in u:
        bid = u.split("/phonefix/")[1].split(".json")[0]
        body = json.dumps(FIXES[bid]) if bid in FIXES else "null"
    elif "/phonefix" in u:
        body = json.dumps(FIXES) if FIXES else "null"
    elif "/spa.json" in u: body = json.dumps(SPA_ALL)
    elif "/presmstemplates" in u: body = "null"
    elif "/smstemplates" in u:
        body = json.dumps(STATE["templates"]) if STATE.get("templates") else "null"
    elif u.split("?")[0].endswith("/bookings.json"):
        #  arrivals-sms reads prearrival from the whole node now, plucked by
        #  id - the same records the per-id /prearrival branch below serves.
        body = json.dumps({bid: {"prearrival": p} for bid, p in PRE_RECS.items()})
    elif "/bookings/" in u and "/prearrival" in u:
        bid = u.split("/bookings/")[1].split("/")[0]
        body = json.dumps(PRE_RECS[bid]) if bid in PRE_RECS else "null"
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
    who = SENT[-1].get("villas") or SENT[-1].get("bookings") or []
    results = WORKER["reply"] or {v: {"status": "sent"} for v in who}
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
    #  Since 25 Aug an unsendable row is tappable, but to FIX, never to tick:
    #  the tap opens the number editor and no tick appears.
    pg.on("dialog", lambda d: d.dismiss())
    ck("a villa whose number cannot be normalised offers a fix, not a tick",
       not row("3").is_disabled())
    row("3").click(); pg.wait_for_timeout(200)
    ck("and tapping it never ticks it",
       "on" not in (row("3").get_attribute("class") or ""))
    ck("and shows the number beside the name, with the pencil that edits it",
       "02 9999 9999" in row("3").locator(".ph").text_content()
       and row("3").locator(".pen").count() == 1)
    ck("a villa with no phone number offers to add one",
       not row("2").is_disabled()
       and "No phone number" in row("2").inner_text()
       and "no number" in row("2").locator(".ph").text_content()
       and row("2").locator(".pen").count() == 1)
    ck("a sendable row shows its number too, in the small grey font",
       "+61 411 111 111" in row("4").locator(".ph").text_content())
    #  The confidence mark: tick for a published mobile range, question mark
    #  where a country's mobiles cannot be told from landlines.
    ck("an Australian mobile wears the tick",
       row("4").locator(".conf.ok").count() == 1)
    ck("the rule itself: NL mobile certain, +1 honestly unsure",
       pg.evaluate("()=>phoneConfidence('+31612762241')") == "mobile"
       and pg.evaluate("()=>phoneConfidence('+1 415 555 2671')") == "unsure"
       and pg.evaluate("()=>phoneConfidence('02 9999 9999')") is None)
    ck("a villa already sent to is unticked and shows the time",
       "on" not in (row("9").get_attribute("class") or "")
       and "Sent 5:05pm" in row("9").inner_text())
    ck("a failed send is not a sent villa: ticked again, reason showing",
       "on" in (row("14").get_attribute("class") or "")
       and "INVALID_RECIPIENT" in row("14").inner_text())
    ck("the older bare id shape is skipped rather than crashing",
       pg.evaluate("()=>document.querySelectorAll('.vrow[data-villa=\"5\"]').length") == 0)
    ck("villas run in villa order within their bands",
       pg.evaluate("()=>[...document.querySelectorAll('.vrow')].map(e=>e.dataset.villa)")
       == ["4", "14", "9", "7", "11", "2", "3"])
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
       "<menu>" in pg.input_value("#msgBox") and "Nala Resort" in pg.input_value("#msgBox"))
    ck("the short template, link included, is one segment and says so",
       "1 segment" in pg.inner_text("#msgCount"))
    pg.select_option("#tmpl", "reminder"); pg.wait_for_timeout(100)
    ck("choosing a template rewrites the box",
       "not heard about dinner" in pg.input_value("#msgBox"))
    #  With the 70 character GUID link this template was two segments; the
    #  37 character token link is what brings it under 160. If this fails
    #  after a template edit, the words got longer, not the link.
    ck("and even the longest one, link included, stays one segment",
       "1 segment" in pg.inner_text("#msgCount"))
    pg.fill("#msgBox", "Menu here: https://evil.example/x"); pg.wait_for_timeout(150)
    ck("typing a URL is warned about as it is typed",
       "cannot be typed" in pg.inner_text("#msgWarn"))
    del SENT[:]
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(300)
    ck("and the send is refused: the body cannot be made to carry a second URL",
       SENT == [] and "contains a link" in pg.inner_text("#errBar"))
    pg.select_option("#tmpl", "ready"); pg.wait_for_timeout(100)

    # ── sending ────────────────────────────────────────────────
    #  Since 25 Aug EVERY send takes the confirm press, not only resends.
    del SENT[:]
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(300)
    ck("the first press never sends, even to fresh villas",
       SENT == [] and "Please confirm" in pg.evaluate("()=>sendBtn.textContent"))
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(500)
    ck("the confirmed press sends", len(SENT) == 1)
    ck("the page proposes villas and words, never numbers and never a link",
       SENT and sorted(SENT[0]["villas"]) == ["14", "4"]
       and "<menu>" in SENT[0]["body"]
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
       "Please confirm" in pg.evaluate("()=>sendBtn.textContent"))
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(500)
    ck("the second press sends", len(SENT) == 1 and "9" in SENT[0]["villas"])

    # ── a partial failure names which villas failed ────────────
    pg = board()
    WORKER["reply"] = {"4": {"status": "sent"},
                       "14": {"status": "failed", "error": "INVALID_RECIPIENT"}}
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(200)
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
    # The check answers both ways: a live menu is a green pill saying so, not
    # a silent absence of the red one. Just the fact, no timestamp.
    pg = board()
    ck("a published menu is a green pill saying Menu published",
       pg.text_content("#menuPill").strip() == "Menu published"
       and "ok" in pg.get_attribute("#menuPill", "class"))

    # ── the page holds no link builder at all ──────────────────
    #  The Worker mints a short token per send and stores it against the
    #  booking id and villa; the page never sees a link and cannot build one,
    #  so an edited browser has nothing to substitute. What the page DOES
    #  own is the counter's budget for the link the Worker will add: the
    #  token link is exactly 37 characters.
    pg = board()
    ck("the page cannot build a link: the Worker mints the token",
       pg.evaluate("()=>typeof inviteLink") == "undefined")
    ck("the counter budgets the 37 character token link",
       pg.evaluate("()=>LINK_SAMPLE.length") == 37)

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

    # ── the status bands, INVITATIONS-STATUS.md ────────────────
    #  Colour assertions by computed style, not class name: the tints are the
    #  contract with the Reservations board.
    pg = board()
    seq = pg.evaluate("""()=>[...document.getElementById('board').children]
        .map(el=>el.classList.contains('grp') ? 'H:'+el.textContent
              : el.classList.contains('grouptitle') ? 'IH'
              : el.classList.contains('arrivals') ? 'ARR'
              : el.dataset.villa)""")
    #  Everyone here is in house (no arrival dates on the fixture), so the
    #  In-house title leads and there is no Arrivals dropdown.
    ck("the four bands render in order, under the In-house title, done sunk",
       seq == ["IH",
               "H:To send · 2", "4", "14",
               "H:Waiting on a reply · 1", "9",
               "H:Answered · 2", "7", "11",
               "H:Cannot send · 2", "2", "3"], seq)
    ck("a failed send sits in To send, its reason on the row",
       seq[2:4] == ["4", "14"]
       and "Send failed" in row("14").inner_text())
    tint = lambda v: pg.evaluate(
        "s=>getComputedStyle(document.querySelector(s))",
        '.vrow[data-villa="%s"]' % v)
    din, out, wait = tint("7"), tint("11"), tint("9")
    ck("an answered dining villa wears the Reservations green tile",
       din["backgroundColor"] == "rgba(122, 160, 130, 0.26)"
       and din["borderTopColor"] == "rgba(122, 160, 130, 0.65)")
    ck("a not-dining villa the terracotta",
       out["backgroundColor"] == "rgba(184, 106, 90, 0.16)"
       and out["borderTopColor"] == "rgba(184, 106, 90, 0.45)")
    #  Chrome stores the .045 alpha as 8-bit and reads it back as 0.043.
    ck("waiting is grey, not a promise of green, solid and full strength",
       wait["backgroundColor"].startswith("rgba(28, 28, 26, 0.04")
       and wait["borderTopStyle"] == "solid" and wait["opacity"] == "1")
    grey = tint("2")
    ck("cannot-send is dashed, sunk, its tick hidden",
       grey["borderTopStyle"] == "dashed" and grey["opacity"] == "0.62"
       and pg.evaluate("()=>getComputedStyle(document.querySelector("
           "'.vrow[data-villa=\\\"2\\\"] .tick')).visibility") == "hidden")
    #  A band with nothing in it shows no header.
    INVITES_BAK = dict(INVITES)
    INVITES.clear()
    pg = board()
    ck("a band with nothing in it shows no header",
       "Waiting" not in pg.inner_text("#board")
       and pg.locator("#board .grp").count() == 3)
    INVITES.update(INVITES_BAK)
    pg.close()

    # ── a dinner cell whose booking has left the villa ─────────
    #  Villa 4, 19 Sep. Reception set a dining answer; Mews then moved the
    #  booking and a new guest took the villa. The Reservations board dropped
    #  the stale cell (dinnerElsewhere) and showed the villa AWAITING, but this
    #  page read /dinner raw and sat the new, unasked guest under "Dining · 5 ·
    #  set by reception" in Answered - so nobody sent them an invitation, the
    #  one thing the board exists to stop. Both boards read the cell through
    #  cellIsForBooking now, so both drop the same one. Isolated fixture so the
    #  band counts above are left alone.
    STAYS_BAK, DINNER_BAK = dict(STAYS), dict(DINNER)
    STAYS.clear(); STAYS.update({
      #  All in house (arrived before tonight) so they sit in the main list,
      #  not the Arrivals dropdown - this block is about the stale cell, not
      #  the arrivals split.
      "6": stay("b6-now", "Lynette", "Burns", "+61 458 792 134", -1, 2),
      "7": stay("b7-now", "Sadie",   "Cole",  "+61 466 000 007", -1, 2),
      "8": stay("b8-now", "Otto",    "Frei",  "+61 466 000 008", -1, 2),
    })
    DINNER.clear(); DINNER.update({
      #  Stale: stamped with the booking that has since left villa 6.
      "6": {"status": "in", "pax": 5, "by": "reception@x", "bookingId": "b6-was",
            "at": now.replace(hour=9, minute=43).isoformat()},
      #  Live: the cell's booking is the one in villa 7 now.
      "7": {"status": "in", "pax": 2, "by": "reception@x", "bookingId": "b7-now",
            "at": now.replace(hour=9, minute=41).isoformat()},
      #  A walk-in / pre-cell staff entry Mews has no opinion about: no booking
      #  id, so nothing can call it stale. It stays answered.
      "8": {"status": "in", "pax": 2, "by": "reception@x",
            "at": now.replace(hour=9, minute=40).isoformat()},
    })
    pg = board()
    ck("a cell whose booking has left the villa is not tonight's answer: the "
       "new guest lands in To send, ticked, not under Answered",
       row("6").get_attribute("data-state") == "ready"
       and "Not asked" in row("6").inner_text()
       and "set by reception" not in row("6").inner_text()
       and "on" in (row("6").get_attribute("class") or ""))
    ck("a cell whose booking is still in the villa stays answered",
       row("7").get_attribute("data-state") == "answered"
       and "set by reception" in row("7").inner_text())
    ck("a cell with no booking id is a walk-in nothing can orphan: still answered",
       row("8").get_attribute("data-state") == "answered")
    ck("the SMS board and the Reservations board drop the same stale cell",
       pg.evaluate("()=>dinnerElsewhere({'6':{status:'in',bookingId:'b6-was'}},"
                   "'6',{'6':{bookingId:'b6-now'}})") is True
       and pg.evaluate("()=>cellIsForBooking({bookingId:'b6-was'},'b6-now')") is False
       and pg.evaluate("()=>cellIsForBooking({bookingId:'b7-now'},'b7-now')") is True
       and pg.evaluate("()=>cellIsForBooking({},'b7-now')") is True)
    STAYS.clear(); STAYS.update(STAYS_BAK)
    DINNER.clear(); DINNER.update(DINNER_BAK)
    pg.close()

    # ── templates.html, where the messages are edited ──────────
    def tpage(email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8977/templates.html")
        pg.wait_for_timeout(1600)
        return pg

    STATE["templates"] = None
    del WRITES[:]
    pg = tpage()
    ck("an empty node is seeded with the three built-ins, one write each",
       len([w for w in WRITES if "/smstemplates/" in w["u"]]) == 3)
    ck("and three cards render",
       pg.locator("#cards .card").count() == 3)
    ck("each built-in ends with the marker on its own last line",
       all(json.loads(w["b"])["body"].endswith("\n<menu>")
           for w in WRITES if "/smstemplates/" in w["u"]))

    #  A URL typed into a template is refused at the editor, the same rule as
    #  the sending page and the Worker.
    box = pg.locator("#cards .card").first.locator("textarea")
    box.fill("See https://evil.example/x"); pg.wait_for_timeout(120)
    ck("a typed URL blocks Save and says why",
       pg.locator("#cards .card").first.locator(".save").is_disabled()
       and "cannot be typed" in pg.locator("#cards .card").first.inner_text())

    #  Save tidies: the marker is moved to the end, and its old name is
    #  renamed, so what the database holds is always the preview-safe shape.
    del WRITES[:]
    box.fill("The menu <link> is attached. Nala Resort"); pg.wait_for_timeout(120)
    pg.locator("#cards .card").first.locator(".save").click(); pg.wait_for_timeout(300)
    saved = [w for w in WRITES if "/smstemplates/" in w["u"]]
    ck("saving moves the marker to the end, under its new name",
       len(saved) == 1 and
       json.loads(saved[0]["b"])["body"] == "The menu  is attached. Nala Resort\n<menu>")

    #  Deleting is a two-press action, like Send.
    del WRITES[:]
    dbtn = pg.locator("#cards .card").first.locator(".del")
    dbtn.click(); pg.wait_for_timeout(120)
    ck("the first press of Delete deletes nothing",
       [w for w in WRITES if w["m"] == "DELETE"] == []
       and "press again" in dbtn.text_content())
    dbtn.click(); pg.wait_for_timeout(300)
    ck("the second press deletes, and the card goes",
       len([w for w in WRITES if w["m"] == "DELETE"]) == 1
       and pg.locator("#cards .card").count() == 2)
    pg.close()

    #  The edited set is what the sending page offers. The built-ins survive
    #  only as a fallback for a failed read.
    STATE["templates"] = {"own": {"label": "House words", "order": 1,
                                  "body": "Our words tonight. Nala Resort\n<menu>"}}
    pg = tpage()
    ck("a saved set renders instead of the built-ins, without reseeding",
       pg.locator("#cards .card").count() == 1
       and "House words" in pg.locator("#cards .card").first.locator("input").input_value())
    pg.close()
    pg = board()
    ck("the sending page offers the edited set",
       pg.locator("#tmpl option").count() == 1
       and pg.locator("#tmpl option").first.text_content() == "House words"
       and "Our words tonight" in pg.input_value("#msgBox"))
    pg.close()
    STATE["templates"] = None

    # ── arrivals-sms.html, the pre-arrival window ──────────────
    def apage(email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**nala-invites.ben-681.workers.dev/**", wk)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8977/arrivals-sms.html")
        pg.wait_for_timeout(1600)
        return pg

    pg = apage()
    seq = pg.evaluate("""()=>[...document.getElementById('board').children]
        .map(el=>el.classList.contains('grp') ? 'H:'+el.textContent
                                              : el.dataset.booking)""")
    ck("the five bands render in order: send, follow up, waiting, done, cannot",
       seq == ["H:To send · 1", "pa-ready",
               "H:Opened, not finished · 1", "pa-open",
               "H:Waiting on the form · 1", "pa-sent",
               "H:Form completed · 1", "pa-done",
               "H:Cannot send · 1", "pa-landline"], seq)
    ck("a guest already in house is not an arrival",
       "pa-inhouse" not in seq)
    ck("a booking spanning two nights is listed once",
       seq.count("pa-sent") == 1)
    ck("an arrival past the window is not offered",
       "pa-far" not in seq)

    #  The shared table both this page and the Dashboard answer to
    #  (tests/presms_cases.json): the send-state itself, preSmsState in
    #  nala-shared.js. Proven here on the SMS page's copy and again in
    #  dash_suite on the board's, so the one reader cannot drift between them
    #  - the phone_cases.json pattern (CLAUDE.md rule 1).
    CASES = json.load(open("/home/claude/nala/tests/presms_cases.json"))["cases"]
    bad = [c["name"] for c in CASES
           if pg.evaluate("c=>preSmsState(c.stay,c.pre,c.invite,c.fix,c.spa)", c)
              != c["state"]]
    ck("preSmsState agrees with the shared table on every case (%d)" % len(CASES),
       not bad)
    badf = [c["name"] for c in CASES
            if pg.evaluate("c=>preSmsFailed(c.invite)", c) != c["failed"]]
    ck("preSmsFailed agrees with the shared table on every case", not badf)

    arow = lambda id: pg.locator('.vrow[data-booking="%s"]' % id)
    #  The 25 Aug safety pass: nothing is pre-ticked, every send is a
    #  deliberate tick, and Select all scopes itself to To send.
    ck("nothing is ticked until somebody ticks it",
       pg.locator(".vrow.on").count() == 0)
    pg.locator("#selAll").click(); pg.wait_for_timeout(150)
    ck("select-all ticks the To send band and nothing else",
       "on" in (arow("pa-ready").get_attribute("class") or "")
       and "on" not in (arow("pa-sent").get_attribute("class") or "")
       and "on" not in (arow("pa-open").get_attribute("class") or ""))
    pg.locator("#selAll").click(); pg.wait_for_timeout(150)
    ck("and a second press clears its own ticks",
       pg.locator(".vrow.on").count() == 0)
    pg.locator("#selAll").click(); pg.wait_for_timeout(150)
    ck("a completed form cannot be sent to again from here",
       arow("pa-done").is_disabled())
    ck("an opened, unfinished form can be chased",
       not arow("pa-open").is_disabled())
    ck("the row says when the guest arrives",
       "arrives" in arow("pa-ready").inner_text())
    ck("a handset receipt shows on the row: sent AND delivered",
       "delivered" in arow("pa-sent").inner_text())
    #  The colour law (CLAUDE.md): opened-not-finished is the front desk's
    #  amber - attention, not the red family - asserted by computed colour.
    amber = pg.evaluate(
        "s=>getComputedStyle(document.querySelector(s)).backgroundColor",
        '.vrow[data-booking="pa-open"]')
    ck("opened-not-finished wears the front desk's amber, not red",
       amber == "rgb(246, 234, 213)")
    #  A record still unconfirmed makes the page ask the Worker for receipts.
    PREINV["pa-sent"] = dict(PREINV["pa-sent"]); PREINV["pa-sent"].pop("delivery")
    del SENT[:]
    pg2 = apage()
    ck("the page asks for receipts for anything sent but unconfirmed",
       any(x.get("kind") == "delivery" and x.get("pres") == ["pa-sent"]
           for x in SENT))
    ck("and says so on the row until the receipt lands",
       "delivery unconfirmed" in pg2.locator('.vrow[data-booking="pa-sent"]').inner_text())
    pg2.close()
    PREINV["pa-sent"]["delivery"] = "delivered"
    del SENT[:]
    ck("the counts strip says the same as the bands",
       [pg.evaluate("()=>%s.textContent" % i)
        for i in ("nSend","nWait","nOpen","nDone")] == ["1","1","1","1"])

    #  A stamp WITH answers behind it but missing a mandatory one. The old
    #  check in demanded dinner and dietary and never the massage, so it
    #  could stamp a multi night booking complete with the treatment
    #  question never asked. Completed now wants the mandatory answers still
    #  standing, so such a record reads incomplete here from the moment this
    #  ships - and the link is sendable again, which is the point.
    PRE_RECS["pa-halfdone"] = {"at": now.isoformat(), "dining": True,
                               "noDiets": True}
    NIGHTS[dplus(1)]["15"] = stay("pa-halfdone", "Half", "Done",
                                  "+61 411 000 015", 1, 4)
    pg5 = apage()
    hrow = pg5.locator('.vrow[data-booking="pa-halfdone"]')
    ck("a stamp missing a mandatory answer is not a completed form",
       "b-done" not in (hrow.get_attribute("class") or ""))
    ck("and that guest can be chased again",  not hrow.is_disabled())
    pg5.close()
    #  Give it the treatment answer and it is complete, on four nights.
    PRE_RECS["pa-halfdone"]["wellness"] = False
    pg5 = apage()
    hrow = pg5.locator('.vrow[data-booking="pa-halfdone"]')
    ck("with every mandatory answer in, the same record reads completed",
       "b-done" in (hrow.get_attribute("class") or ""))
    pg5.close()
    #  Or let the Spa board answer it. The owner's report of 10 Sep: a
    #  massage the masseuse had already approved, and the form still amber
    #  with treatments named missing - the ask had been keyed straight onto
    #  the board, so no wellness boolean existed on the form while the
    #  outcome hung at /spa. massageAnswered (nala-shared.js) reads both
    #  places, so a record born there answers the question here as well.
    del PRE_RECS["pa-halfdone"]["wellness"]
    SPA_ALL["pa-halfdone"] = {"t1": {"status": "booked", "day": dplus(2),
                                     "time": "14:00", "source": "desk",
                                     "at": "x"}}
    pg5 = apage()
    hrow = pg5.locator('.vrow[data-booking="pa-halfdone"]')
    ck("a massage the Spa board holds answers the treatment question here too",
       "b-done" in (hrow.get_attribute("class") or ""))
    pg5.close()
    del SPA_ALL["pa-halfdone"]
    del PRE_RECS["pa-halfdone"]; del NIGHTS[dplus(1)]["15"]

    #  A stamp with nothing behind it. Seen live on villa 17, 28 Aug: the
    #  Front Desk's confirm wrote `at` onto a record holding no answers, so
    #  this page read Form completed and the link could never be sent to that
    #  guest again - and the desk had no way back either. A guest cannot
    #  submit an empty form (the slot, dinner and dietary questions are all
    #  required), so a stamp standing alone was always the desk's and never
    #  theirs. The desk's copy of this test is hasForm in front-desk.html.
    PRE_RECS["pa-phantom"] = {"at": now.isoformat(),
                              "confirmedAt": now.isoformat()}
    NIGHTS[dplus(1)]["16"] = stay("pa-phantom", "Tim", "Martin",
                                  "+61 416 237 128", 1, 2)
    pg3 = apage()
    prow = pg3.locator('.vrow[data-booking="pa-phantom"]')
    ck("a stamp with no answer behind it is not a completed form",
       "b-done" not in (prow.get_attribute("class") or ""))
    ck("and that guest can still be sent the link, which is the whole point",
       not prow.is_disabled() and "Not asked" in prow.inner_text())
    pg3.close()
    del PRE_RECS["pa-phantom"]
    del NIGHTS[dplus(1)]["16"]

    #  One party, two villas. Two rows is correct - each villa has its own
    #  link and its own answers - but until 28 Aug nothing here said they were
    #  one party, so the same handset could be sent two different forms by
    #  somebody who thought they were texting two guests. The words and the
    #  reader are the Front Desk's, from nala-shared.js.
    NIGHTS[dplus(1)]["16"] = stay("pa-grp-a", "Tim", "Martin",
                                  "+61 416 237 128", 1, 2,
                                  {"groupId": "grp-tim"})
    NIGHTS[dplus(1)]["17"] = stay("pa-grp-b", "Tim", "Martin",
                                  "+61 416 237 128", 1, 2,
                                  {"groupId": "grp-tim"})
    pg4 = apage()
    ck("each villa of one party names the other",
       "with villa 17" in
       pg4.locator('.vrow[data-booking="pa-grp-a"]').inner_text()
       and "with villa 16" in
       pg4.locator('.vrow[data-booking="pa-grp-b"]').inner_text())
    ck("a booking on its own says nothing about a party",
       "with villa" not in
       pg4.locator('.vrow[data-booking="pa-ready"]').inner_text())
    pg4.close()
    del NIGHTS[dplus(1)]["16"]; del NIGHTS[dplus(1)]["17"]

    #  Fixing the number: the tap opens a prompt, the save is the NORMALISED
    #  E.164 to /phonefix/<booking>, and on reload the guest is sendable.
    #  The 25 Aug case verbatim: an NZ mobile with its country code.
    pg.on("dialog", lambda d: d.accept("(+64) 274875277"))
    del WRITES[:]
    arow("pa-landline").click(); pg.wait_for_timeout(900)
    fixw = [w for w in WRITES if "/phonefix/pa-landline" in w["u"]]
    ck("the fix saves normalised, with the Mews value kept as `was`",
       len(fixw) == 1 and json.loads(fixw[0]["b"])["phone"] == "+64274875277"
       and json.loads(fixw[0]["b"])["was"] == "07 3358 1122")
    ck("and the guest climbs out of Cannot send, ready to message",
       arow("pa-landline").get_attribute("data-state") == "ready"
       and not arow("pa-landline").is_disabled()
       and "on" not in (arow("pa-landline").get_attribute("class") or ""))
    FIXES.clear()

    #  The knob widens the window and the far arrival appears.
    pg.locator('#knob button[data-days="14"]').click(); pg.wait_for_timeout(900)
    ck("fourteen days finds the arrival seven could not",
       pg.locator('.vrow[data-booking="pa-far"]').count() == 1)
    pg.locator('#knob button[data-days="7"]').click(); pg.wait_for_timeout(900)

    #  Sending posts booking ids with kind pre; the Worker owns the rest.
    #  EVERY send takes the red second press, not only resends. The knob
    #  reloads above cleared the ticks, so tick afresh - which is itself the
    #  safety feature working.
    del SENT[:]
    pg.locator("#selAll").click(); pg.wait_for_timeout(150)
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(300)
    ck("the first press of Send sends nothing and asks for the confirm",
       SENT == [] and "Please confirm" in pg.evaluate("()=>sendBtn.textContent"))
    pg.locator("#sendBtn").click(); pg.wait_for_timeout(600)
    ck("send posts the ticked bookings, as kind pre",
       len(SENT) == 1 and SENT[0].get("kind") == "pre"
       and SENT[0].get("bookings") == ["pa-ready"]
       and "villas" not in SENT[0])
    ck("and the template's marker is the form's",
       "<form>" in SENT[0]["body"])
    pg.close()

    #  The same permission as Invitations: a housekeeper is turned away.
    pg = apage(email="housekeeping@x")
    ck("a role without editBookings is turned away from the window",
       pg.locator("#sendBtn").count() == 0
       or not pg.locator("#sendBtn").is_visible())
    pg.close()

    # ── the guest's own answer reaches the sender ──────────────
    #  Found 4 Sep: this page read the /dinner cell alone, so an arriving
    #  guest who had answered dinner on their pre-arrival form days ago sat
    #  in To send, PRE-TICKED, and one press away from being re-asked a
    #  question the kitchen was already cooking to. The reader is now
    #  formDinnerCell in nala-shared.js - the Reservations board's own, the
    #  28 Aug ruling - and the cell still outranks it absolutely.
    F_STAYS = {
      "4":  {"id": "fb4", "first": "Rosalie", "last": "Stibbard",
             "phone": "+61 418 229 808", "arrive": today, "depart": dplus(2),
             "adults": 2},
      "6":  {"id": "fb6", "first": "Andrew", "last": "Sykes",
             "phone": "+61 467 216 449", "arrive": today, "depart": dplus(2),
             "adults": 2},
      "9":  {"id": "fb9", "first": "Mid", "last": "Stay",
             "phone": "+61 411 000 009", "arrive": dplus(-2),
             "depart": dplus(1), "adults": 2},
      "11": {"id": "fb11", "first": "Cell", "last": "Wins",
             "phone": "+61 411 000 011", "arrive": today, "depart": dplus(1),
             "adults": 2},
    }
    F_FORMS = {
      "fb4":  {"dining": False, "noDiets": True},
      "fb6":  {"dining": True, "pax": 2, "diets": ["Shellfish allergy"]},
      "fb9":  {"dining": True, "pax": 2},
      "fb11": {"dining": True, "pax": 2},
    }
    F_CELLS = {"11": {"status": "out", "pax": 0, "by": "staff",
                      "at": now.isoformat()}}
    def form_fb(route, request):
        u = request.url
        if request.method != "GET":
            fb(route, request); return
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(F_STAYS)); return
        if "/dinner/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(F_CELLS)); return
        if "/invites/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body="{}"); return
        if u.split("?")[0].endswith("/bookings.json"):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({k: {"prearrival": v}
                                           for k, v in F_FORMS.items()})); return
        if "/bookings/" in u and "/prearrival" in u:
            k = u.split("/bookings/")[1].split("/")[0]
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(F_FORMS[k]) if k in F_FORMS
                               else "null"); return
        fb(route, request)
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.add_init_script(SDK)
    pg.add_init_script("window.__EMAIL='staff@x';")
    pg.route("**firebasedatabase.app/**", form_fb)
    pg.route("**nala-invites.ben-681.workers.dev/**", wk)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.goto("http://localhost:8977/invitations.html")
    pg.wait_for_timeout(1600)
    frow = lambda v: pg.locator('.vrow[data-villa="%s"]' % v)
    #  A form answer only ever speaks for the ARRIVAL night (formDinnerCell),
    #  so any guest reading "answered on the pre-arrival form" is arriving
    #  tonight and belongs in the Arrivals dropdown, set aside from the send.
    ck("form-answered guests are arriving guests, in the Arrivals dropdown",
       pg.locator('.arrivals .vrow[data-villa="6"]').count() == 1
       and pg.locator('.arrivals .vrow[data-villa="4"]').count() == 1
       and pg.locator('.arrivals .vrow[data-villa="11"]').count() == 1)
    ck("the dropdown counts them and a mid-stay guest is NOT among them",
       "3 guests" in pg.inner_text(".arrivals > summary")
       and pg.locator('.arrivals .vrow[data-villa="9"]').count() == 0)
    #  Their state is decided before they are folded away: data-state is
    #  readable while collapsed, then open the dropdown to read the rows.
    ck("a guest who answered their pre-arrival form is Answered, not To send",
       frow("6").get_attribute("data-state") == "answered")
    ck("and is not pre-ticked: re-asking is a deliberate tap, never the default",
       "on" not in (frow("6").get_attribute("class") or ""))
    ck("a form decline is Answered too, so nobody chases them",
       frow("4").get_attribute("data-state") == "answered")
    pg.click(".arrivals > summary"); pg.wait_for_timeout(150)   # open to read the rows
    ck("the dining answer reads off the form",
       "Dining · 2 · answered on the pre-arrival form" in frow("6").inner_text())
    ck("the decline reads Not dining",
       "Not dining · answered on the pre-arrival form" in frow("4").inner_text())
    #  By computed colour: the tints are the contract with the Reservations
    #  board, and a confirmed arrival wears the same green tile as an in-house
    #  diner, exactly as a cell does.
    tintf = lambda v: pg.evaluate(
        "s=>getComputedStyle(document.querySelector(s))",
        '.vrow[data-villa="%s"]' % v)
    ck("a confirmed arrival wears the Reservations green tile, a decline terracotta",
       tintf("6")["backgroundColor"] == "rgba(122, 160, 130, 0.26)"
       and tintf("4")["backgroundColor"] == "rgba(184, 106, 90, 0.16)")
    ck("but only on the night they arrive: mid-stay is in house, To send, ticked",
       frow("9").get_attribute("data-state") == "ready"
       and "on" in (frow("9").get_attribute("class") or "")
       and pg.locator('.arrivals .vrow[data-villa="9"]').count() == 0)
    ck("a dinner cell outranks the form absolutely",
       "Not dining · set by reception" in frow("11").inner_text())
    ck("the strip totals both groups: three answered, mid-stay the one to send",
       pg.inner_text("#nAns") == "3" and pg.inner_text("#nSend") == "1")

    #  The one reader, against the one shared table - the phone_cases.json
    #  pattern. Every screen that draws this fact answers to
    #  tests/form_dinner_cases.json; add cases there, never here.
    fcases = json.load(open("tests/form_dinner_cases.json"))["cases"]
    def offdate(rec):
        r = dict(rec)
        off = r.pop("arriveOffset", None)
        fld = r.pop("arriveField", None)
        if off is not None:
            r[fld] = dplus(off)
        return r
    got = pg.evaluate("""(a)=>a.cases.map(c=>{
        const out = formDinnerCell('7', c.pre, c.rec, a.today);
        if (out === null) return null;
        const t = {}; Object.keys(c.expect).forEach(k=>t[k]=out[k]);
        return t; })""",
        {"cases": [{"pre": c["pre"], "rec": offdate(c["rec"]),
                    "expect": c["expect"] or {}} for c in fcases],
         "today": today})
    wrongf = [fcases[i]["name"] for i in range(len(fcases))
              if got[i] != fcases[i]["expect"]]
    ck("the page answers every shared form-dinner case", wrongf == [], wrongf)
    pg.close()

    # ── the Arrivals split: set aside, unticked, confirm a confirmed diner ──
    #  Approved 19 Sep: arriving guests are rarely invited, so they fold into a
    #  dropdown, unticked; a confirmed diner among them wears the green tile and
    #  asks before it joins a send.
    STAYS_BAK, DINNER_BAK = dict(STAYS), dict(DINNER)
    STAYS.clear(); STAYS.update({
      "4":  stay("i4",  "In",  "House",    "+61 400 000 004", -1, 2),  # in house, no answer
      "15": stay("a15", "Arri", "Ving",    "+61 400 000 015",  0, 2),  # arriving, no answer
      "16": stay("a16", "Con",  "Firmed",  "+61 400 000 016",  0, 2),  # arriving, dining
    })
    DINNER.clear(); DINNER.update({
      "16": {"status": "in", "pax": 2, "by": "guest", "bookingId": "a16",
             "at": now.replace(hour=9, minute=30).isoformat()},
    })
    pg = board()
    ck("an in-house guest with no answer is pre-ticked in the To send band, not the dropdown",
       "on" in (row("4").get_attribute("class") or "")
       and pg.locator('.arrivals .vrow[data-villa="4"]').count() == 0)
    ck("an arriving guest with no answer is in the dropdown and NOT pre-ticked",
       pg.locator('.arrivals .vrow[data-villa="15"]').count() == 1
       and "on" not in (row("15").get_attribute("class") or ""))
    ck("a confirmed-dining arrival is answered, in the dropdown, and not ticked",
       row("16").get_attribute("data-state") == "answered"
       and pg.locator('.arrivals .vrow[data-villa="16"]').count() == 1
       and "on" not in (row("16").get_attribute("class") or ""))
    ck("the In-house title carries the in-house total",
       "1 guest" in pg.inner_text(".grouptitle"))
    pg.click(".arrivals > summary"); pg.wait_for_timeout(150)
    ck("a confirmed arrival wears the green tile inside the dropdown",
       pg.evaluate("s=>getComputedStyle(document.querySelector(s)).backgroundColor",
                   '.arrivals .vrow[data-villa="16"]') == "rgba(122, 160, 130, 0.26)")
    #  Inviting a confirmed diner asks first. Dismissed -> stays unticked.
    pg.once("dialog", lambda d: d.dismiss())
    row("16").click(); pg.wait_for_timeout(150)
    ck("inviting a confirmed-dining arrival asks first; dismissed, it stays unticked",
       "on" not in (row("16").get_attribute("class") or ""))
    #  Accepted -> it joins the send.
    pg.once("dialog", lambda d: d.accept())
    row("16").click(); pg.wait_for_timeout(150)
    ck("confirmed at the prompt, it joins the send",
       "on" in (row("16").get_attribute("class") or ""))
    #  A not-yet-answered arrival ticks with no prompt at all.
    seen = []
    pg.on("dialog", lambda d: (seen.append(1), d.accept()))
    row("15").click(); pg.wait_for_timeout(150)
    ck("a not-yet-answered arrival ticks straight through, no prompt",
       "on" in (row("15").get_attribute("class") or "") and seen == [])
    STAYS.clear(); STAYS.update(STAYS_BAK)
    DINNER.clear(); DINNER.update(DINNER_BAK)
    pg.close()

    # ── widths ─────────────────────────────────────────────────
    for w in (390, 360, 320):
        q = board(w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()
    q = tpage()
    ck("no sideways scroll on the template editor at 390pt", not q.evaluate(
       "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
    q.close()
    q = apage()
    ck("no sideways scroll on the pre-arrival window at 390pt", not q.evaluate(
       "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
    q.close()

    # ── the Send footer stays at the foot of the screen ──────────
    #  The owner's report, 26 Sep: once Arrivals was opened, the sticky
    #  footer on his iPhone stopped short and rode up with the scroll, rows
    #  showing beneath it. Chromium never shows that fault, so the first
    #  check holds the page to the fixed footer that cannot have it, and the
    #  rest check the fixed one is done right. A day shaped like his: five
    #  arrivals and four in house, long enough to scroll once Arrivals opens.
    STAYS_BAK, DINNER_BAK = dict(STAYS), dict(DINNER)
    STAYS.clear(); STAYS.update({
      v: stay("f" + v, "Guest", "V" + v, "+61 400 000 0%02d" % int(v), a, 2)
      for v, a in (("2", 0), ("6", 0), ("8", 0), ("12", 0), ("16", 0),
                   ("5", -2), ("15", -1), ("9", -1), ("13", -3))})
    DINNER.clear()
    FOOT = """()=>{const f=document.querySelector('.foot').getBoundingClientRect(),
      b=document.getElementById('sendBtn').getBoundingClientRect(),
      r=document.querySelector('.vrow[data-villa="5"]').getBoundingClientRect(),
      l=document.querySelector('.linknote').getBoundingClientRect();
      return {pos:getComputedStyle(document.querySelector('.foot')).position,
              top:f.top, bottom:f.bottom, h:innerHeight, link:l.bottom,
              bl:b.left, br:b.right, rl:r.left, rr:r.right};}"""
    pg = board()
    pg.click(".arrivals > summary"); pg.wait_for_timeout(200)
    at = {}
    for where, y in (("top", "0"), ("middle", "document.documentElement.scrollHeight/3"),
                     ("end", "document.documentElement.scrollHeight")):
        pg.evaluate("()=>scrollTo(0,%s)" % y); pg.wait_for_timeout(150)
        at[where] = pg.evaluate(FOOT)
    ck("the Send footer is fixed to the screen, not sticky in the page",
       at["top"]["pos"] == "fixed", at["top"]["pos"])
    ck("with Arrivals opened it stays at the foot of the screen, however far scrolled",
       all(abs(g["bottom"] - g["h"]) <= 1 for g in at.values()), at)
    ck("and at the end of the list nothing is left hidden under it",
       at["end"]["link"] <= at["end"]["top"], at["end"])
    ck("the button keeps to the list's own column on a phone",
       abs(at["top"]["bl"] - at["top"]["rl"]) <= 1 and
       abs(at["top"]["br"] - at["top"]["rr"]) <= 1, at["top"])
    pg.close()
    pg = board(w=1280)
    g = pg.evaluate(FOOT)
    ck("and on a desktop, rather than stretching across the window",
       abs(g["bl"] - g["rl"]) <= 1 and abs(g["br"] - g["rr"]) <= 1, g)
    pg.close()
    STAYS.clear(); STAYS.update(STAYS_BAK)
    DINNER.clear(); DINNER.update(DINNER_BAK)


    # ── the Guest Profile's door: ?open=<booking> marks that guest's row ──
    pg = b.new_page(viewport={"width": 390, "height": 900})
    pg.add_init_script(SDK)
    pg.add_init_script("window.__EMAIL='staff@x';")
    pg.route("**firebasedatabase.app/**", fb)
    pg.route("**nala-invites.ben-681.workers.dev/**", wk)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.goto("http://localhost:8977/arrivals-sms.html?open=pa-sent")
    pg.wait_for_timeout(1600)
    ck("the profile's door marks the guest's row on the SMS board",
       pg.evaluate("()=>{const e=document.querySelector('.vrow.linked');"
                   "return !!e && e.dataset.booking === 'pa-sent';}"))
    pg.close()

    b.close()

# ── the trim rule ────────────────────────────────────────────────────
#  Reported by the owner off a screenshot, 29 Aug: a long name pushed the
#  phone number, the confidence mark and the edit pencil off the right
#  edge. "Chloe Roveglia +61448925599 ." and "Amanda Sinclair +614004519"
#  - the two things reception needed were the two that went.
#
#  The name is the only field that may trim, because it is the only one
#  that survives being half shown. A phone number does not: half of one
#  still LOOKS like a number and somebody will read it out. A control does
#  not either - a pencil clipped to two pixels cannot be pressed.
#
#  Forced with a name longer than any real guest's, because the fault only
#  shows when the row cannot fit and the real board usually can.
_trim = """<button class="vrow"><div class="v">14</div><div class="mid">
  <div class="nm trimrow"><span class="trim">Amanda Penelope Sinclair-Fotheringay-Wodehouse</span>
  <span class="ph">+61400451982</span><span class="conf ok">&#10003;</span>
  <span class="pen">&#9998;</span></div><div class="st">Sent</div></div>
  <div class="tick">&#10003;</div></button>"""
with sync_playwright() as p3:
    b3 = p3.chromium.launch()
    q = b3.new_page(viewport={"width": 390, "height": 500})
    q.goto("http://localhost:8977/invitations.html")
    q.wait_for_timeout(900)
    got = q.evaluate("""(html)=>{const d=document.createElement('div');
        d.style.maxWidth='390px'; d.innerHTML=html;
        document.body.appendChild(d);
        const row=d.querySelector('.vrow').getBoundingClientRect();
        const t=d.querySelector('.trim');
        const ph=d.querySelector('.ph'), pen=d.querySelector('.pen');
        const r=e=>e.getBoundingClientRect();
        const out={nameTrimmed:t.scrollWidth>t.clientWidth,
                   phoneWhole:r(ph).right<=row.right+1 && r(ph).width>0,
                   phoneText:ph.textContent,
                   pencilWhole:r(pen).right<=row.right+1 && r(pen).width>0};
        d.remove(); return out;}""", _trim)
    q.close(); b3.close()
print("   trim rule:", got)
ck("a name too long for its row is the thing that trims", got["nameTrimmed"])
ck("and the phone number survives whole", got["phoneWhole"] and got["phoneText"] == "+61400451982")
ck("and the pencil is still there to press", got["pencilWhole"])


print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
