"""The paper ground: every page wearing `paper` beside `ui2`.

Ruled by the owner, 27 Sep, off mock-paper.html. The ground began as the
Claude app's own and moved a touch lighter the same day; its value is
--ground in nala-ui2.css and this suite reads it from there, because a
suite with its own copy of a colour passes while the page is wrong. His
first objection to the first mock is the rule this suite exists for:
"Cards and box backgrounds are transparent so there is no contrast." On a
white page a box with no fill of its own looks white; on paper it shows
the paper through it and stops being a card. So:

  1. The ground is the paper, on every page that wears it, and the paper
     is not the white its cards are made of.
  2. No box on a paper page lets the paper through: nothing with a border,
     or a tint and rounded corners, whose own fill is transparent,
     translucent, or the ground colour, unless something solid sits between
     it and the page. Found mechanically, never listed by hand - a list is
     what forgot the select bar's two quiet buttons and the Front Desk
     form's chips the first time.
  3. The same holds in the states a page opens into: its sheets, menus and
     other modes. The first build passed on every board as it loaded and
     still let the paper through the villa sheet's covers, the Add
     reservation chips, a completed arrival's summary, the key card run,
     the Issue keys menu and every page's hamburger menu.
  4. Reservations' cards grow OUTWARD (the owner: "Don't use so much. Look
     at your own app as example"): every villa tile keeps today's size and
     place with the paper on.
  5. Taking the class off gives back today's white page: the class is the
     whole switch, so any page can leave the paper in one edit.

The night is tests/paper_night.json: one fixture Saturday with the clock
held at 15:20 in Brisbane, so the boards draw every state they have.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re, glob

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8959), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

from night_harness import TREE, open_page   # the fixture night, shared with colour_suite

_g = re.search(r"body\.ui2\.paper\s*\{[^}]*--ground:\s*#([0-9A-Fa-f]{6})",
               open("nala-ui2.css", encoding="utf-8").read())
GROUND = "#" + _g.group(1).upper() if _g else None
PAPER = "rgb(%d, %d, %d)" % tuple(int(_g.group(1)[i:i + 2], 16) for i in (0, 2, 4)) if _g else None

# The boxes a paper page must not have. Outermost only: a see-through chip
# inside a solid card shows the card, not the paper.
FIND = """() => {
  const alphaOf = c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return 0;
    const p = m[1].split(',').map(Number); return p.length === 4 ? p[3] : 1; };
  const ground = getComputedStyle(document.body).backgroundColor;
  const solid = el => { const c = getComputedStyle(el).backgroundColor;
    return alphaOf(c) === 1 && c !== ground; };
  const hit = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (r.width < 20 || r.height < 14 || cs.display === 'none' ||
        cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    if (/^(INPUT|TEXTAREA|SELECT|OPTION|IMG|svg|path)$/i.test(el.tagName)) continue;
    // A sheet is paper like the page it rises over - the Front Desk form
    // the owner approved is one - so it is a ground, and what sits on it
    // must be solid.
    if (el.classList.contains('sheet')) continue;
    const sides = ['Top','Right','Bottom','Left'].filter(s =>
      parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none').length;
    const bg = cs.backgroundColor, a = alphaOf(bg);
    const boxed = sides >= 3 || (a > 0 && parseFloat(cs.borderTopLeftRadius) > 0);
    if (!boxed || !(a < 1 || bg === ground)) continue;
    let p = el.parentElement, covered = false;
    while (p && p !== document.body) { if (solid(p)) { covered = true; break; } p = p.parentElement; }
    if (covered) continue;
    let q = el.parentElement, inner = false;
    while (q && q !== document.body) { if (hit.some(h => h.el === q)) { inner = true; break; } q = q.parentElement; }
    hit.push({ el, inner, sig: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
               [...el.classList].map(c => '.' + c).join('') });
  }
  return [...new Set(hit.filter(h => !h.inner).map(h => h.sig))];
}"""

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else "  -> " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

# The pages that wear it, read off their own body tags: a page joins the
# paper by adding the class, and joins this suite the same moment.
WEARS = sorted(f for f in glob.glob("*.html")
               if not f.startswith(("demo-", "mock-"))
               and re.search(r'<body[^>]*class="[^"]*\bui2\b[^"]*\bpaper\b', open(f, encoding="utf-8").read()))
print("   pages on paper:", WEARS)
ck("nala-ui2.css gives the paper a ground, and it is not the cards' white",
   PAPER is not None and PAPER != "rgb(255, 255, 255)", GROUND)
# Nine boards on 27 Sep, then Publish Menu and Dietary the same day, then
# Spa reminders on 28 Sep: drawn on paper in mock-spa-reminders.html, beside
# Pre-arrival SMS whose dress it copies, and approved that way.
ck("the pages the owner put on paper wear it, and no others",
   WEARS == sorted(["tally.html", "front-desk.html", "dashboard.html", "cleaners.html", "spa.html",
                    "invitations.html", "arrivals-sms.html", "calendar.html", "keys.html",
                    "publish.html", "tag.html", "spa-reminders.html"]), WEARS)

def click_row(pg, sel, text):
    for r in pg.query_selector_all(sel):
        if text in r.inner_text():
            r.click(); return
    raise Exception("no row reading " + text)

# The states each page opens into, beyond the board as it loads.
STATES = {
  "tally.html": [("a villa's sheet", lambda pg: pg.click("#rooms .room >> nth=0")),
                 ("Add reservation", lambda pg: pg.click("#addExt")),
                 ("an invited guest's sheet", lambda pg: click_row(pg, "#listBookings .row", "Sarah Jones")),
                 ("select mode", lambda pg: (pg.click("#selToggle"), pg.wait_for_timeout(200),
                                             pg.click("#rooms .room >> nth=6")))],
  "front-desk.html": [("a completed arrival's summary", lambda pg: click_row(pg, "#board button.arr", "Reilly")),
                      ("the key card run", lambda pg: pg.click(".keybtn"))],
  "spa.html": [("a booking card", lambda pg: pg.click(".vrow >> nth=0"))],
  "cleaners.html": [("a villa's sheet", lambda pg: pg.click(".tile >> nth=0"))],
  "keys.html": [("the Issue keys menu", lambda pg: pg.click("#issueBtn"))],
  "calendar.html": [("the Clean colouring", lambda pg: pg.click(".mbtn >> nth=1"))],
  "arrivals-sms.html": [("the next 14 days", lambda pg: pg.click("#knob button >> nth=2"))],
  "invitations.html": [("the Arrivals list", lambda pg: pg.click(".arrivals > summary")),
                       ("the External guests list", lambda pg: pg.click(".extguests > summary")),
                       ("an external guest's sheet", lambda pg: (pg.click(".extguests > summary"),
                           pg.click(".extguests .vrow >> nth=0"))),
                       ("the invite sheet", lambda pg: (pg.click(".extguests > summary"),
                           pg.click("#extInvite")))],
  "dashboard.html": [("the menu", lambda pg: pg.click("#navBtn"))],
  "publish.html": [("Remove armed", lambda pg: pg.click("#rmBtn")),
                   ("the published screen", lambda pg: pg.click("#pubBtn"))],
  "tag.html": [("a hidden dietary", lambda pg: pg.click("#mng .mtog >> nth=0")),
               ("This menu only picked", lambda pg: pg.click("#gMenu"))],
}

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def page(name):
        return open_page(b, 8959, name)

    for name in WEARS:
        ctx, pg = page(name)
        ground = pg.evaluate("()=>getComputedStyle(document.body).backgroundColor")
        ck(name + ": the ground is the paper, %s" % GROUND, ground == PAPER, ground)
        rows = pg.evaluate("()=>document.querySelectorAll('.vrow,.arr,.tile,.card,.row,.tick,.mrow').length")
        ck(name + ": the fixture night puts rows on it, so the check below has something to see", rows > 0)
        hit = pg.evaluate(FIND)
        ck(name + ": no box lets the paper through", not hit, hit)

        if name == "tally.html":
            # Measured with the paper on, then off: the card takes its 8pt
            # from the page margin, never from the tiles.
            tiles = "()=>[...document.querySelectorAll('#rooms .room')].map(e=>{const r=e.getBoundingClientRect();return [r.left,r.width].map(v=>v.toFixed(2)).join('/')})"
            on = pg.evaluate(tiles)
            pg.evaluate("()=>document.body.classList.remove('paper')"); pg.wait_for_timeout(100)
            off = pg.evaluate(tiles)
            ck("tally.html: every villa tile keeps its size and place under the card",
               len(on) == 17 and on == off, (on[:3], off[:3]))
            pg.evaluate("()=>document.body.classList.add('paper')")

        if name == "front-desk.html":
            for r in pg.query_selector_all("#board button.arr"):
                if "Sharma" in r.inner_text():
                    r.click(); break
            pg.wait_for_timeout(600)
            ck("front-desk.html: a guest's form is open over the board",
               pg.evaluate("()=>[...document.querySelectorAll('.sheet')].some(s=>"
                           "s.getBoundingClientRect().height>0 && s.innerText.includes('Priya Sharma'))"))
            hit = pg.evaluate(FIND)
            ck("front-desk.html: nothing on the open form lets the paper through", not hit, hit)

        for label, act in STATES.get(name, []):
            sctx, spg = page(name)
            try:
                act(spg); spg.wait_for_timeout(600)
                hit = spg.evaluate(FIND)
                ck(name + ": nothing lets the paper through with " + label + " open", not hit, hit)
            except Exception as e:
                ck(name + ": " + label + " opens", False, str(e).split("\n")[0])
            sctx.close()

        # The whole switch is the one class.
        pg.evaluate("()=>document.body.classList.remove('paper')"); pg.wait_for_timeout(100)
        ck(name + ": taking the class off gives back today's white page",
           pg.evaluate("()=>getComputedStyle(document.body).backgroundColor") == "rgb(255, 255, 255)"
           and pg.evaluate("()=>getComputedStyle(document.body).getPropertyValue('--surface').trim()") == "")
        ctx.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
