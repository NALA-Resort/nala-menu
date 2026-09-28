"""spa-reminders.html, the morning text to a guest with a treatment booked.

The owner, 28 Sep: "a text message gently reminding the guests that they
have a booking", with its details, sent on the MORNING OF the treatment by
the desk pressing Send. The page proposes; the Worker (stubbed here, tested
in worker/invites-test.mjs) re-reads every record and writes the words. The
things most worth pinning down:

  1. Where each treatment stands is spaReminderState's reading, and the
     words are spaReminderText's - both held to tests/spareminder_cases.json
     here, the Worker's twin to the same table there.
  2. The preview is the text the guest gets, a changed booking included.
  3. Nothing sends without the second press, and the POST names exactly the
     ticked treatments.
  4. A failed read draws nothing: without the send log the page cannot tell
     who has been texted, and a list drawn anyway could text somebody twice.

The clock is held at 10:15 on Monday 5 Oct and every check that turns on the
day runs in two zones, UTC and Brisbane - CLAUDE.md: a date test that only
runs in one zone is blind to a whole class of bug.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8996), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

DAY, TOMORROW = "2026-10-05", "2026-10-06"
ZONES = {"UTC": "2026-10-05T10:15:00+00:00",
         "Australia/Brisbane": "2026-10-05T10:15:00+10:00"}

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "waiter@x": {"name": "Waiter", "role": "waiter"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"},
         "masseuse@x": {"name": "Masseuse", "role": "spa"}}

def bk(first, last, phone, villa):
    return {"pms": {"first": first, "last": last, "phone": phone, "villa": villa,
                    "arrive": "2026-10-03", "depart": "2026-10-08"}}
#  One morning with every state on it, the clock at 10:15:
#    2 Elena   15:30  a pair, never sent                       ready
#    4 Omar    14:00  one massage, never sent                  ready
#    7 Priya   13:00  sent, the handset never got it           ready, red words
#   17 Freya   16:00  sent quoting 11:30, moved since          changed
#   13 Nina    12:00  sent quoting 12:00, delivered            sent
#    9 Ruby    12:30  a landline in Mews                       nophone
#    3 Mark    09:30  started, never sent                      late
#  and two that are not this page's: a suggestion today, a booking tomorrow.
BOOKINGS = {
  "b-elena": bk("Elena", "Petrova", "+61 411 000 002", "2"),
  "b-omar":  bk("Omar", "Haddad", "0411 000 004", "4"),
  "b-priya": bk("Priya", "Sharma", "+61411000007", "7"),
  "b-freya": bk("Freya", "Lindqvist", "+61 411 000 017", "17"),
  "b-nina":  bk("Nina", "Brandt", "+61 411 000 013", "13"),
  "b-ruby":  bk("Ruby", "Vance", "07 3358 1122", "9"),
  "b-mark":  bk("Mark", "Whitfield", "+61 411 000 003", "3"),
  "b-tom":   bk("Tom", "Ashby", "+61 411 000 008", "8"),
}
STAYS = {v: {"id": b, "first": BOOKINGS[b]["pms"]["first"], "last": BOOKINGS[b]["pms"]["last"],
             "arrive": "2026-10-03", "depart": "2026-10-08"}
         for b, v in (("b-elena", "2"), ("b-omar", "4"), ("b-priya", "7"), ("b-freya", "17"),
                      ("b-nina", "13"), ("b-ruby", "9"), ("b-mark", "3"), ("b-tom", "8"))}
def booked(time, dur=60, **k):
    return dict({"status": "booked", "day": DAY, "time": time, "dur": dur, "qty": 1}, **k)
SPA = {
  "b-elena": {"t1": booked("15:30", 60, qty=2, dur2=90)},
  "b-omar":  {"t2": booked("14:00")},
  "b-priya": {"t3": booked("13:00")},
  "b-freya": {"t4": booked("16:00")},
  "b-nina":  {"t5": booked("12:00", 90)},
  "b-ruby":  {"t6": booked("12:30")},
  "b-mark":  {"t7": booked("09:30")},
  "b-tom":   {"t8": {"status": "suggested", "day": DAY, "time": "15:00", "dur": 60, "qty": 1},
              "t9": dict(booked("10:00"), day=TOMORROW)},
}
REMS = {
  "b-priya": {"t3": {"status": "sent", "sentAt": DAY + "T08:05:00+10:00", "providerId": "mid-p",
                     "delivery": "failed", "deliveryText": "Handset unreachable",
                     "day": DAY, "time": "13:00", "qty": 1, "dur": 60}},
  "b-freya": {"t4": {"status": "sent", "sentAt": DAY + "T08:05:00+10:00", "providerId": "mid-f",
                     "delivery": "delivered", "day": DAY, "time": "11:30", "qty": 1, "dur": 60}},
  "b-nina":  {"t5": {"status": "sent", "sentAt": DAY + "T08:05:00+10:00", "providerId": "mid-n",
                     "day": DAY, "time": "12:00", "qty": 1, "dur": 90}},
}
TPL_REMIND = ("Hello <first>, a gentle reminder of your booking with us:\n\n<booking>\n\n"
              "If you need to change anything, just reply to this message. Nala Resort")

STATE = {"remfail": False, "empty": False}
WRITES, SENT = [], []
WORKER = {"reply": None}
FIXES = {}

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE", "POST"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        if m == "PUT" and "/phonefix/" in u:
            FIXES[u.split("/phonefix/")[1].split(".json")[0]] = json.loads(request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    path = u.split("firebasedatabase.app")[1].split("?")[0]
    body = "null"
    if path.startswith("/staff"): body = json.dumps(STAFF)
    elif path.startswith("/permissions"): body = "null"
    elif path == "/stays/" + DAY + ".json": body = json.dumps(STAYS)
    elif path == "/spa.json": body = "null" if STATE["empty"] else json.dumps(SPA)
    elif path == "/spareminders.json":
        if STATE["remfail"]:
            route.fulfill(status=500, content_type="application/json", body='{"error":"x"}'); return
        body = json.dumps(REMS)
    elif path == "/bookings.json": body = json.dumps(BOOKINGS)
    elif path == "/phonefix.json": body = json.dumps(FIXES) if FIXES else "null"
    elif path == "/spasmstemplates.json": body = "null"
    route.fulfill(status=200, content_type="application/json", body=body)

def wk(route, request):
    SENT.append(json.loads(request.post_data))
    last = SENT[-1]
    if last.get("kind") == "delivery":
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"results": {}, "changed": 0})); return
    who = [t["b"] + "/" + t["t"] for t in last.get("treatments") or []]
    results = WORKER["reply"] or {k: {"status": "sent"} for k in who}
    route.fulfill(status=200, content_type="application/json",
                  body=json.dumps({"results": results}))

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)) if not cond and detail else ""))
    P, F = (P + 1, F) if cond else (P, F + 1)

def shown(style):
    """A row's surface colour: on a paper page a colour-law tint is a
    gradient layer over opaque white, elsewhere the fill - inv_suite's
    reading, so the contract numbers stay the law's."""
    mm = re.search(r"linear-gradient\((rgba?\([^)]*\))", style.get("backgroundImage") or "")
    return mm.group(1) if mm else style["backgroundColor"]

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def page(email="staff@x", w=390, tz="UTC", q=""):
        ctx = b.new_context(viewport={"width": w, "height": 900}, timezone_id=tz)
        pg = ctx.new_page()
        pg.clock.set_fixed_time(ZONES[tz])
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**nala-invites.ben-681.workers.dev/**", wk)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8996/spa-reminders.html" + q)
        pg.wait_for_timeout(1400)
        pg.ctx = ctx
        return pg
    def done(pg): pg.ctx.close()
    def row(pg, bid): return pg.locator('.vrow[data-booking="%s"]' % bid)
    ROWS_JS = """()=>[...document.querySelectorAll('.vrow')].map(e=>({b:e.dataset.booking,
        t:e.dataset.tid, s:e.dataset.state, on:e.classList.contains('on'),
        dis:e.disabled, bk:e.querySelector('.bk').textContent,
        st:e.querySelector('.st').textContent}))"""

    # ── the morning's rows, in both zones ────────────────────────
    for tz in ZONES:
        pg = page(tz=tz)
        rows = {r["b"]: r for r in pg.evaluate(ROWS_JS)}
        want = {"b-elena": "ready", "b-omar": "ready", "b-priya": "ready",
                "b-freya": "changed", "b-nina": "sent", "b-ruby": "nophone", "b-mark": "late"}
        ck("[%s] every treatment booked today is listed, in the state the shared reader gives" % tz,
           {k: v["s"] for k, v in rows.items()} == want, {k: v["s"] for k, v in rows.items()})
        ck("[%s] a suggestion and tomorrow's booking are not this morning's texts" % tz,
           "b-tom" not in rows)
        grps = pg.evaluate("()=>[...document.querySelectorAll('.grp')].map(e=>e.textContent)")
        ck("[%s] the bands, work first: to send, changed, reminded, cannot, started" % tz,
           grps == ["To send · 3", "Changed since the reminder · 1", "Reminded · 1",
                    "Cannot send · 1", "Already started · 1"], grps)
        ck("[%s] the page's states are spaReminderState's, not its own" % tz,
           pg.evaluate("""()=>[...document.querySelectorAll('.vrow')].every(e=>{
             const r=ROWS[e.dataset.booking+'/'+e.dataset.tid].row;
             return spaReminderState(r.rec, r.rem, r.raw, Date.now())===e.dataset.state;})"""))
        done(pg)

    pg = page()
    rows = {r["b"]: r for r in pg.evaluate(ROWS_JS)}
    ck("what is owed comes ticked: the never-sent, the failed and the changed",
       all(rows[k]["on"] for k in ("b-elena", "b-omar", "b-priya", "b-freya")))
    ck("a reminded guest is not ticked, but can be, to send again on purpose",
       not rows["b-nina"]["on"] and not rows["b-nina"]["dis"])
    ck("a started treatment cannot be ticked at all", rows["b-mark"]["dis"] and not rows["b-mark"]["on"])
    ck("a landline row stays pressable, because pressing it fixes the number",
       not rows["b-ruby"]["dis"] and not rows["b-ruby"]["on"])
    ck("each row says what is booked: the time, then the offering, lengths in order",
       rows["b-elena"]["bk"] == "3:30 pm · Two massages · 1 hr + 1.5 hr",
       rows["b-elena"]["bk"])
    ck("and what became of its text",
       rows["b-omar"]["st"] == "Not reminded yet" and
       rows["b-freya"]["st"].startswith("The text said 11:30 am") and
       rows["b-nina"]["st"].startswith("Sent ") and rows["b-nina"]["st"].endswith("delivery unconfirmed") and
       rows["b-mark"]["st"] == "Started 9:30 am · no reminder went", rows)
    ck("a text the handset never got says so in the carrier's words, in red",
       "Not delivered · Handset unreachable" in rows["b-priya"]["st"] and
       pg.evaluate("""()=>getComputedStyle(document.querySelector(
         '.vrow[data-booking="b-priya"] .st .bad')).color""") == "rgb(168, 50, 30)")
    sty = lambda bid: pg.evaluate("""(b)=>{const s=getComputedStyle(document.querySelector(
        '.vrow[data-booking="'+b+'"]'));return {backgroundColor:s.backgroundColor,
        backgroundImage:s.backgroundImage,borderStyle:s.borderTopStyle,opacity:s.opacity};}""", bid)
    ck("a changed booking is the law's amber: the guest holds the wrong time",
       shown(sty("b-freya")) == "rgb(246, 234, 213)", sty("b-freya"))
    ck("a reminded one is the law's done green", shown(sty("b-nina")) == "rgba(122, 160, 130, 0.26)",
       sty("b-nina"))
    ck("and the two with nothing to send are the sunk, dashed rows",
       all(sty(k)["borderStyle"] == "dashed" and float(sty(k)["opacity"]) < 0.7
           for k in ("b-ruby", "b-mark")))
    st = pg.evaluate("()=>['nSend','nSent','nAll'].map(i=>document.getElementById(i).textContent)")
    ck("the counts: four ticked, one reminded, seven booked today", st == ["4", "1", "7"], st)

    # ── the words, against the one table the Worker answers to ───
    T = json.load(open("tests/spareminder_cases.json"))
    bad = pg.evaluate("""(T)=>{const out=[];
      T.text.forEach(c=>{ if (spaReminderText(c.tpl,c.first,c.rec,c.prev)!==c.want) out.push(c.name); });
      T.state.forEach(c=>{ const [d,t]=c.now.split('T'), [y,m,dd]=d.split('-').map(Number),
                           [h,mi]=t.split(':').map(Number);
        if (spaReminderState(c.rec,c.rem,c.raw,new Date(y,m-1,dd,h,mi).getTime())!==c.want)
          out.push(c.name); });
      return out; }""", T)
    ck("the page's builder and reader say what the shared table says, every case (%d)" %
       (len(T["text"]) + len(T["state"])), not bad and len(T["text"]) > 10, bad)

    # ── the preview is the text the guest gets ───────────────────
    pv = pg.evaluate("()=>({meta:document.getElementById('pvMeta').textContent, text:document.getElementById('pvText').textContent, opts:[...document.querySelectorAll('#pvSel option')].map(o=>o.textContent)})")
    ck("the preview offers exactly the ticked guests, in the day's time order",
       pv["opts"] == ["7 · Priya Sharma", "4 · Omar Haddad", "2 · Elena Petrova",
                      "17 · Freya Lindqvist"], pv["opts"])
    ck("and shows the first one's whole text, the Gentle reminder filled",
       pv["meta"] == "Text message to Priya Sharma" and pv["text"] ==
       "Hello Priya, a gentle reminder of your booking with us:\n\nMassage, 1 hour\n"
       "Monday 5 October at 1:00 pm\n\nIf you need to change anything, just reply to this message. "
       "Nala Resort", pv)
    pg.select_option("#pvSel", "b-freya/t4"); pg.wait_for_timeout(100)
    ck("a changed booking's preview says what it changed from",
       "Monday 5 October at 4:00 pm\n(changed from 11:30 am)\n" in pg.inner_text("#pvText"))
    pg.select_option("#pvSel", "b-priya/t3"); pg.wait_for_timeout(100)
    ck("a text the handset never got is not 'corrected', only sent",
       "changed" not in pg.inner_text("#pvText"))
    cnt = pg.inner_text("#msgCount")
    ck("the count is the longest of the ticked guests' own texts, in segments",
       re.match(r"^Longest of the 4: \d{3} characters · 2 segments$", cnt) is not None, cnt)
    pg.select_option("#tmpl", "short"); pg.wait_for_timeout(100)
    ck("the Short wording fits one segment",
       pg.inner_text("#msgCount").endswith("1 segment"), pg.inner_text("#msgCount"))
    pg.select_option("#tmpl", "remind"); pg.wait_for_timeout(100)

    # ── the message's own refusals, before any send ──────────────
    def typed(text):
        pg.fill("#msgBox", text); pg.wait_for_timeout(80)
        return pg.inner_text("#msgWarn")
    ck("a curly apostrophe is named: it would send the text as unicode",
       "“’”" in typed(TPL_REMIND.replace("Hello", "We’re glad. Hello")) and
       "segments" in pg.inner_text("#msgWarn"))
    ck("taking <booking> out is refused: the guest would not be told what or when",
       "<booking>" in typed(TPL_REMIND.replace("<booking>", "your massage")))
    ck("so is a link marker, and a web address",
       "<menu>" in typed(TPL_REMIND + "\n<menu>") and "link" in typed(TPL_REMIND + " www.x.com"))
    n0 = len(SENT)
    pg.click("#sendBtn"); pg.wait_for_timeout(200)
    ck("and Send says why rather than sending", len(SENT) == n0 and
       "link" in pg.inner_text("#errBar"))
    pg.fill("#msgBox", TPL_REMIND); pg.wait_for_timeout(80)
    ck("the plain template raises nothing", pg.inner_text("#msgWarn") == "")

    # ── sending takes two presses, and names exactly the ticked ──
    row(pg, "b-omar").click(); pg.wait_for_timeout(80)
    ck("unticking a guest takes them out of the count and the preview",
       pg.inner_text("#nSend") == "3" and
       "4 · Omar Haddad" not in pg.evaluate("()=>[...document.querySelectorAll('#pvSel option')].map(o=>o.textContent)"))
    n0 = len(SENT)
    pg.click("#sendBtn"); pg.wait_for_timeout(150)
    ck("the first press arms the send and sends nothing",
       len(SENT) == n0 and pg.inner_text("#sendBtn") ==
       "Please confirm · send to 3 guests, 1 of them again")
    pg.click("#sendBtn"); pg.wait_for_timeout(700)
    last = SENT[-1] if len(SENT) > n0 else {}
    ck("the second press sends, as kind spa, the three ticked treatments and nothing else",
       last.get("kind") == "spa" and last.get("idToken") == "T" and
       sorted((t["b"], t["t"]) for t in last.get("treatments", [])) ==
       [("b-elena", "t1"), ("b-freya", "t4"), ("b-priya", "t3")], last)
    ck("with the template's words, placeholders unfilled: the Worker fills them",
       last.get("body") == TPL_REMIND and last.get("template") == "remind")
    done(pg)

    WORKER["reply"] = {"b-omar/t2": {"status": "failed", "error": "INVALID_RECIPIENT"},
                       "b-elena/t1": {"status": "sent"}, "b-priya/t3": {"status": "sent"},
                       "b-freya/t4": {"status": "sent"}}
    pg = page()
    pg.click("#sendBtn"); pg.click("#sendBtn"); pg.wait_for_timeout(700)
    ck("a partial failure names the guest who was not texted",
       "Did not send to Omar Haddad" in pg.inner_text("#errBar"), pg.inner_text("#errBar"))
    WORKER["reply"] = None
    done(pg)

    # ── the number, fixed from the row ───────────────────────────
    pg = page()
    pg.once("dialog", lambda d: d.accept("0412 345 678"))
    row(pg, "b-ruby").click(); pg.wait_for_timeout(700)
    fx = [w for w in WRITES if w["m"] == "PUT" and "/phonefix/b-ruby" in w["u"]]
    ck("pressing a landline row asks for a mobile and saves the fix, normalised",
       bool(fx) and json.loads(fx[-1]["b"])["phone"] == "+61412345678", fx[-1:] or WRITES[-3:])
    ck("and the row comes back sendable, ticked",
       pg.evaluate("()=>{const e=document.querySelector('.vrow[data-booking=\"b-ruby\"]');"
                   "return e.dataset.state+':'+e.classList.contains('on');}") == "ready:true")
    FIXES.clear()
    done(pg)

    # ── receipts are asked for, once ─────────────────────────────
    pg = page()
    dl = [s for s in SENT if s.get("kind") == "delivery"]
    ck("a sent text with no verdict yet is sent to the Worker for its receipt",
       bool(dl) and {"b": "b-nina", "t": "t5"} in dl[-1].get("spas", []) and
       {"b": "b-freya", "t": "t4"} not in dl[-1].get("spas", []), dl[-1:])
    done(pg)

    # ── the Spa board's door marks the guest ─────────────────────
    pg = page(q="?open=b-freya")
    ck("?open=<booking> marks that guest's row",
       pg.evaluate("()=>document.querySelector('.vrow[data-booking=\"b-freya\"]').classList.contains('linked')"))
    done(pg)

    # ── a failed read draws nothing ──────────────────────────────
    STATE["remfail"] = True
    pg = page()
    ck("without the send log nothing is drawn, so nobody can be texted twice",
       pg.locator(".vrow").count() == 0 and pg.is_disabled("#sendBtn") and
       "twice" in pg.inner_text("#errBar"), pg.inner_text("#errBar"))
    STATE["remfail"] = False
    done(pg)
    STATE["empty"] = True
    pg = page()
    ck("a morning with no treatments says so, and offers no message to write",
       "No treatments booked today" in pg.inner_text("#board") and
       not pg.is_visible("#msgBox"))
    STATE["empty"] = False
    done(pg)

    # ── who may see it ───────────────────────────────────────────
    for who in ("chef@x", "housekeeping@x", "masseuse@x"):
        q = page(who); q.wait_for_timeout(500)
        ck("a %s is sent to their own board rather than shown the page" % STAFF[who]["role"],
           not q.url.endswith("spa-reminders.html"))
        done(q)
    q = page("waiter@x")
    ck("a waiter holds editBookings and gets the page",
       q.url.endswith("spa-reminders.html") and q.locator(".vrow").count() == 7)
    done(q)

    # ── the words' own home: SMS Templates' third set ────────────
    t = b.new_page(viewport={"width": 390, "height": 900})
    t.add_init_script(SDK)
    t.route("**firebasedatabase.app/**", fb)
    t.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    t.goto("http://localhost:8996/templates.html"); t.wait_for_timeout(1400)
    spa_cards = t.evaluate("""()=>[...document.querySelectorAll('#spacards .card')].map(c=>({
        id:c.dataset.id, label:c.querySelector('input').value,
        body:c.querySelector('textarea').value, count:c.querySelector('.count').textContent}))""")
    ck("SMS Templates holds a third set, Spa reminder templates, seeded with the two wordings",
       t.is_visible("#secSpa") and [c["label"] for c in spa_cards] == ["Gentle reminder", "Short"] and
       spa_cards[0]["body"] == TPL_REMIND, spa_cards)
    seeded = [w for w in WRITES if w["m"] == "PUT" and "/spasmstemplates/" in w["u"]]
    ck("and writes them down the first time, so the database holds the one copy",
       len(seeded) == 2)
    ck("each counts a real guest's text through the shared builder: Gentle is 2 segments, "
       "Short 1 - and 2 only for a long name, a pair and a changed-from line at once",
       spa_cards[0]["count"].startswith("Typically ") and
       spa_cards[0]["count"].endswith("2 segments") and
       spa_cards[1]["count"].endswith("1 segment, up to 2"), [c["count"] for c in spa_cards])
    box = '#spacards .card[data-id="remind"] textarea'
    save = '#spacards .card[data-id="remind"] .save'
    warn = '#spacards .card[data-id="remind"] .warn'
    t.fill(box, TPL_REMIND.replace("<booking>", "your massage")); t.wait_for_timeout(80)
    ck("a spa template cannot be saved without <booking>",
       "<booking>" in t.inner_text(warn) and t.is_disabled(save))
    t.fill(box, TPL_REMIND + "\n<menu>"); t.wait_for_timeout(80)
    ck("nor with a link marker, because a spa reminder carries no link",
       "<menu>" in t.inner_text(warn) and t.is_disabled(save))
    t.fill(box, TPL_REMIND.replace("Hello", "Good morning")); t.wait_for_timeout(80)
    n0 = len(WRITES)
    t.click(save); t.wait_for_timeout(500)
    put = [w for w in WRITES[n0:] if w["m"] == "PUT" and "/spasmstemplates/remind" in w["u"]]
    ck("a good one saves as typed, its placeholders where they were put",
       bool(put) and json.loads(put[-1]["b"])["body"] == TPL_REMIND.replace("Hello", "Good morning"))
    legend = t.inner_text("#legend")
    ck("the legend explains <first> and <booking>, and <first> is no longer 'coming later'",
       "<booking>" in legend and "Coming later" not in legend)
    ck("the spa template box shows the whole wording without scrolling",
       t.evaluate("()=>{const e=document.querySelector('%s');return e.scrollHeight<=e.clientHeight+2;}" % box))
    t.close()

    # ── the Send footer, and the widths ──────────────────────────
    pg = page()
    FOOT = """()=>{const f=document.querySelector('.foot').getBoundingClientRect(),
      l=document.getElementById('pvArea').getBoundingClientRect();
      return {pos:getComputedStyle(document.querySelector('.foot')).position,
              top:f.top, bottom:f.bottom, h:innerHeight, last:l.bottom};}"""
    pg.evaluate("()=>scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(150)
    g = pg.evaluate(FOOT)
    ck("the Send footer is fixed to the foot of the screen, Invitations' rule",
       g["pos"] == "fixed" and abs(g["bottom"] - g["h"]) <= 1, g)
    ck("and at the end of the page the preview is not hidden under it",
       g["last"] <= g["top"], g)
    ck("the message box shows the whole template without scrolling",
       pg.evaluate("()=>{const t=document.getElementById('msgBox');return t.scrollHeight<=t.clientHeight+2;}"))
    done(pg)
    for w in (390, 360, 320):
        q = page(w=w)
        ck("no sideways scroll at %d" % w,
           q.evaluate("()=>document.documentElement.scrollWidth<=innerWidth"))
        ck("at %d no number or control is cut off" % w, q.evaluate("""()=>
          [...document.querySelectorAll('.vrow .ph, .vrow .pen, .vrow .tick, #sendBtn')]
            .every(e=>{const r=e.getBoundingClientRect(); return r.right<=innerWidth+0.5 && r.width>0;})"""))
        done(q)
    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
raise SystemExit(1 if F else 0)
