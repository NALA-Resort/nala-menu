"""Check every board for horizontal overflow at Android widths.

The app has no width media queries at all, so it has never been checked below
the 390pt iPhone the styleguide mocks at. 360pt is the common Samsung Galaxy
width, 320pt is the narrowest phone still in use. Uses the demo files because
they are self contained and need no database.
"""
import threading, http.server, socketserver, time, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8974), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

PAGES = ["demo-tally.html", "demo-reservations.html",
         "demo-cleans.html", "demo-clean.html"]
WIDTHS = [390, 360, 320]

PROBE = """()=>{
  const de = document.documentElement;
  const over = [];
  document.querySelectorAll('*').forEach(el=>{
    const r = el.getBoundingClientRect();
    if (r.width === 0) return;
    if (r.right > de.clientWidth + 1 || r.left < -1) {
      over.push((el.id ? '#'+el.id : el.tagName.toLowerCase()+'.'+
        (el.className||'').toString().split(' ')[0]) +
        ' [' + Math.round(r.left) + ' to ' + Math.round(r.right) + ']');
    }
  });
  return { scroll: de.scrollWidth, client: de.clientWidth,
           over: [...new Set(over)].slice(0,6) };
}"""

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for page in PAGES:
        for w in WIDTHS:
            pg = b.new_page(viewport={"width": w, "height": 800})
            pg.goto("http://localhost:8974/" + page)
            pg.wait_for_timeout(900)
            r = pg.evaluate(PROBE)
            bleeds = r["scroll"] > r["client"] + 1
            print("%-24s %3dpt  scroll=%-4d client=%-4d  %s" % (
                page, w, r["scroll"], r["client"],
                ("OVERFLOWS: " + "; ".join(r["over"])) if (bleeds or r["over"]) else "ok"))
            pg.close()
    b.close()
httpd.shutdown()
