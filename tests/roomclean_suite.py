"""The Calendar's Clean layer, pinned as pure readers against a shared table.

roomCleanState, diningState and arrivalFlagsClean live in nala-shared.js so the
Calendar reads the room's clean state rather than working it out (rule 7):
hkClassify owns the job kind, roomCleanState turns that plus the day's done
flag into the binary the dot draws, and arrivalFlagsClean owns the two-day
window that turns a requires-cleaning room into a flagged one.

Everything here is route-independent - it loads nala-shared.js into a bare page
and calls the functions - so it needs no network mocking. Dates are offsets
from a fixed local `today`, so the cases hold in any zone (the date law).
"""
import threading, http.server, socketserver, json, time, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8993), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

P = F = 0
def ck(name, cond, detail=None):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or detail is None else " :: " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

CASES = json.load(open("tests/roomclean_cases.json"))

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content("<html><body><div id='navDrop'></div><div id='navBtn'></div></body></html>")
    pg.add_script_tag(url="http://localhost:8993/nala-shared.js")
    pg.wait_for_timeout(300)

    # ── roomCleanState against the shared table ────────────────────────
    wrong = pg.evaluate("""(C)=>{
        function dstr(base, off){ var q = base.split('-');
          var d = new Date(+q[0], +q[1]-1, +q[2]); d.setDate(d.getDate() + off);
          return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+
                 '-'+String(d.getDate()).padStart(2,'0'); }
        var base = C.today, bad = [];
        C.clean.forEach(function(c){
          var rec = null;
          if (c.rec){ rec = {};
            if ('arr' in c.rec) rec.arrives = dstr(base, c.rec.arr);
            if ('dep' in c.rec) rec.departs = dstr(base, c.rec.dep); }
          var got = roomCleanState(rec, base, c.hk || {}, !!c.left);
          if (got !== c.want) bad.push(c.why + ': got ' + got + ', wanted ' + c.want);
        });
        return bad;
      }""", CASES)
    ck("roomCleanState answers every shared case", wrong == [], wrong)

    # ── diningState ────────────────────────────────────────────────────
    dwrong = pg.evaluate("""(C)=>{
        return C.dining.filter(function(c){ return diningState(c.pre) !== c.want; })
          .map(function(c){ return JSON.stringify(c.pre) + ' -> ' + diningState(c.pre); });
      }""", CASES)
    ck("diningState answers every shared case", dwrong == [], dwrong)

    # ── arrivalFlagsClean: the two-day window, inclusive both ends ─────
    fwrong = pg.evaluate("""(C)=>{
        function dstr(base, off){ var q = base.split('-');
          var d = new Date(+q[0], +q[1]-1, +q[2]); d.setDate(d.getDate() + off);
          return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+
                 '-'+String(d.getDate()).padStart(2,'0'); }
        var q = C.today.split('-');
        var from = new Date(+q[0], +q[1]-1, +q[2], 9, 0, 0);   // any hour: midday-anchored inside
        return C.flag.filter(function(c){
          return arrivalFlagsClean(dstr(C.today, c.arr), from) !== c.want;
        }).map(function(c){ return c.why + ': got ' +
          arrivalFlagsClean(dstr(C.today, c.arr), from) + ', wanted ' + c.want; });
      }""", CASES)
    ck("arrivalFlagsClean answers every shared case", fwrong == [], fwrong)

    # ── the window is owned in one place, and it is two days ───────────
    ck("CLEAN_FLAG_DAYS is 2, owned in nala-shared.js",
       pg.evaluate("()=>CLEAN_FLAG_DAYS") == 2)

    # ── prove the table can fail (rule 5): a done room is never dirty ───
    ck("a done room never reads dirty, whatever the job",
       pg.evaluate("""()=>roomCleanState({departs:'2026-09-15'}, '2026-09-15',
                        {done:true}, true) === 'cleaned'"""))
    ck("a requires-cleaning room is not silently cleaned",
       pg.evaluate("""()=>roomCleanState({departs:'2026-09-15'}, '2026-09-15',
                        {}, false) === 'dirty'"""))

    b.close()

httpd.shutdown()
print("\nRESULT: %d passed, %d failed" % (P, F))
raise SystemExit(1 if F else 0)
