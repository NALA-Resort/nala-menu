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
  "pa-done": {"at": now.isoformat(), "openedAt": now.isoformat(), "dining": True},
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
    elif "/stays/" + today in u: body = json.dumps(STAYS)
    elif "/stays/" in u:
        d = u.split("/stays/")[1].split(".json")[0]
        body = json.dumps(NIGHTS[d]) if d in NIGHTS else "null"
    elif "/dinner/" + today in u: body = json.dumps(DINNER)
    elif "/opened/" in u: body = "null"
    elif "/invites/" + today in u: body = json.dumps(INVITES)
    elif "/previnvites/" in u:
        bid = u.split("/previnvites/")[1].split(".json")[0]
        body = json.dumps(PREINV[bid]) if bid in PREINV else "null"
    elif "/phonefix/" in u:
        bid = u.split("/phonefix/")[1].split(".json")[0]
        body = json.dumps(FIXES[bid]) if bid in FIXES else "null"
    elif "/phonefix" in u:
        body = json.dumps(FIXES) if FIXES else "null"
    elif "/presmstemplates" in u: body = "null"
    elif "/smstemplates" in u:
        body = json.dumps(STATE["templates"]) if STATE.get("templates") else "null"
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
                                              : el.dataset.villa)""")
    ck("the four bands render in order, headers counting, work first done sunk",
       seq == ["H:To send · 2", "4", "14",
               "H:Waiting on a reply · 1", "9",
               "H:Answered · 2", "7", "11",
               "H:Cannot send · 2", "2", "3"], seq)
    ck("a failed send sits in To send, its reason on the row",
       seq[1:3] == ["4", "14"]
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

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
