"""The card readers, before any board draws them.

cardState in nala-shared.js is the one thing that says where a card
stands - the Keys register, the issue run's seats and the Dashboard all
count through it - and cardRows is the one walk over the /cards tree.
This suite pins both to tests/cardstate_cases.json, the shared table:
a case added there fails whichever reader has not learned it. The
pre-arrival form got its shared reader after the boards had already
drifted; the cards got theirs first, and the rebuild keeps it so.

Also here: cardExpiry, which turns a booking's depart date into the
epoch second the card dies. Checked relatively - CARD_CHECKOUT_HOUR on
the depart day in the machine's own zone - so the assertion holds in
any TZ the runner picks, which is what a date test owes (rule 7).
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8990), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

P = F = 0
def ck(name, cond, detail=None):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or detail is None
          else " :: " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    #  A bare page with the stubs the script's load-time wiring reaches for,
    #  because this suite is about the functions rather than any board.
    pg.set_content("<html><body><div id='navDrop'></div><div id='navBtn'></div></body></html>")
    pg.add_script_tag(url="http://localhost:8990/nala-shared.js")
    pg.wait_for_timeout(300)

    # ── the one judge, against the one shared table ────────────────
    #  now is a fixed LOCAL noon; "expires" becomes an epoch relative to
    #  it - past two days back, today at 23:00 (after noon, before the
    #  next midnight), future two days on at 13:00, now exactly noon,
    #  none no field at all - so every case holds in any TZ (rule 7).
    cases = json.load(open("tests/cardstate_cases.json"))["cases"]
    wrong = pg.evaluate("""(cases)=>{
        var now = new Date(2026, 8, 15, 12, 0, 0).getTime();
        function expOf(k){
          if (k === 'none') return 0;
          if (k === 'now') return now / 1000;
          if (k === 'past') return new Date(2026, 8, 13, 13, 0, 0).getTime() / 1000;
          if (k === 'today') return new Date(2026, 8, 15, 23, 0, 0).getTime() / 1000;
          return new Date(2026, 8, 17, 13, 0, 0).getTime() / 1000;
        }
        return cases.filter(function(c){
          var row = { villa: '9', expiry: expOf(c.expires), lost: c.lost };
          return cardState(row, now) !== c.state;
        }).map(function(c){
          var row = { villa: '9', expiry: expOf(c.expires), lost: c.lost };
          return (c.why || '?') + ': got ' + cardState(row, now) +
                 ', wanted ' + c.state;
        });
      }""", cases)
    ck("cardState answers every shared case", wrong == [], wrong)

    # ── the walk over the tree ─────────────────────────────────────
    got = pg.evaluate("""()=>{
        var rows = cardRows({
          '900001': { villa: '9', guest: 'K', cut: 5, expiry: 100 },
          '900002': { villa: '4', guest: 'R', cut: 9, expiry: 100 },
          '900003': { villa: '9', guest: 'K', cut: 1, expiry: 100, lost: true },
          'junk':   'not a row'
        });
        return rows.map(function(r){ return r.villa + ':' + r.no; });
      }""")
    ck("cardRows walks villa order then cut order, junk skipped",
       got == ["4:900002", "9:900003", "9:900001"], got)

    # ── what a villa holds ─────────────────────────────────────────
    held = pg.evaluate("""()=>{
        var now = new Date(2026, 8, 15, 12, 0, 0).getTime();
        var live = new Date(2026, 8, 17, 13, 0, 0).getTime() / 1000;
        var dead = new Date(2026, 8, 13, 13, 0, 0).getTime() / 1000;
        var rows = cardRows({
          '1': { villa: '9', cut: 1, expiry: live },
          '2': { villa: '9', cut: 2, expiry: live, lost: true },
          '3': { villa: '9', cut: 3, expiry: dead },
          '4': { villa: '6', cut: 4, expiry: live }
        });
        return { nine: cardsHeld(rows, '9', now).length,
                 nineInHand: cardsHeld(rows, '9', now)
                   .filter(function(r){ return !r.lost; }).length,
                 six: cardsHeld(rows, 6, now).length };
      }""")
    ck("cardsHeld counts the villa's unexpired rows, lost included",
       held["nine"] == 2 and held["six"] == 1, held)
    ck("minus the lost one is what the guest has in hand",
       held["nineInHand"] == 1, held)

    # ── the expiry ─────────────────────────────────────────────────
    #  Relative, not absolute: whatever zone this runs in, the epoch it
    #  makes must read back as CHECKOUT o'clock on the depart day in that
    #  same zone. An absolute epoch here would be the UTC-slice bug with
    #  a test wrapped around it.
    exp = pg.evaluate("""()=>{
        var t = cardExpiry('2026-09-14');
        var d = new Date(t*1000);
        return { h: d.getHours(), m: d.getMinutes(),
                 day: d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')
                      +'-'+String(d.getDate()).padStart(2,'0'),
                 hour: CARD_CHECKOUT_HOUR };
      }""")
    ck("a card dies at checkout hour on the depart day",
       exp["h"] == exp["hour"] and exp["m"] == 0 and exp["day"] == "2026-09-14", exp)
    #  Pinned on both sides on purpose: moving the hour must edit this
    #  line too, so it is never moved by accident. 11 until 9 Sep, when
    #  the owner ruled 1pm on seeing the first live card.
    ck("checkout hour is the agreed 1pm", exp["hour"] == 13, exp)
    ck("a Mews-shaped timestamp gives the same day as its date part",
       pg.evaluate("()=>cardExpiry('2026-09-14T04:00:00Z') === cardExpiry('2026-09-14')")
       or pg.evaluate("()=>new Date(cardExpiry('2026-09-14T04:00:00Z')*1000).getHours()") == 13)
    ck("no depart date, no expiry, rather than an invented one",
       pg.evaluate("()=>cardExpiry(null) === null && cardExpiry('') === null"))

    # ── the tally-era readers are gone, not merely unused ──────────
    #  cardCell and cardLife were the counters' readers; a survivor is a
    #  second way to answer the one question, which is the disease the
    #  rebuild exists to cure.
    ck("cardCell and cardLife do not survive the rebuild",
       pg.evaluate("()=>typeof cardCell === 'undefined' && typeof cardLife === 'undefined'"))

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
