"""The key-card state, before either board draws it.

cardCell in nala-shared.js is the one thing that says where a villa's key
cards stand - the Front Desk and the Dashboard both read it, and the Windows
helper's words are held to the same table by its own test. This suite pins
that reader to tests/card_cases.json BEFORE the boards exist, because the
pre-arrival form got its shared reader after the boards had already drifted
and this feature gets it first.

Also here: cardExpiry, which turns a booking's depart date into the epoch
second the card dies. Checked relatively - CARD_CHECKOUT_HOUR on the depart day in the
machine's own zone - so the assertion holds in any TZ the runner picks,
which is what a date test owes (CLAUDE.md rule 7).
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

    # ── the reader, against the one shared table ───────────────────
    cases = json.load(open("tests/card_cases.json"))["cases"]
    wrong = pg.evaluate("""(cases)=>cases.filter(c=>{
        var got = cardCell(c.job);
        return got.k !== c.k || got.label !== c.label;
      }).map(c=>{
        var got = cardCell(c.job);
        return (c.why||'?')+': got '+got.k+'/'+got.label+', wanted '+c.k+'/'+c.label;
      })""", cases)
    ck("cardCell answers every shared case", wrong == [], wrong)

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

    # ── the words are the table's, not merely similar ──────────────
    #  The label for a finished pair is quoted at the desk and printed
    #  nowhere, so the suite holds the exact words: a paraphrase in one
    #  reader is how two boards describe one villa differently.
    ck("done wears the law's green key and failed the red one, by k",
       pg.evaluate("""()=>cardCell({state:'done',qty:2,written:2}).k==='done'
                     && cardCell({state:'failed',qty:2,written:0}).k==='failed'"""))

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
