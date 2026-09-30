"""The colour law, held to every staff board: one colour per meaning.

Ruled by the owner 25 Aug; made to hold 27 Sep, when he found the greens,
reds and oranges "all over the place" and an audit bore him out: Front Desk
drew a completed form at less than half the law's green, "menu published"
was three different greens on two boards, and a count of villas still to
answer was red. Each board had copied a colour, then adjusted its copy.

So the values live in one table, tests/colour_law.json, and this suite
holds the app to it from both ends:

  1. nala-ui2.css defines the law's tokens with exactly the table's values,
     and nala-ui.css's older copy for the printed sheets agrees (rule 3).
  2. Every green, amber and red a board PAINTS - fills, the tint drawn
     over the paper's white, borders, text, icon strokes - is one of the
     table's values, on the board as it loads and in the sheets and modes
     it opens into. A board painting anything else fails by name, with the
     element and the colour. Nothing is listed by hand: the page is read.
     Cleans' job colours are allowed on Cleans alone (page_keys).
  3. It saw enough to mean something: every meaning the law has turns up
     somewhere on the fixture night, so a pass is not a blind one.

Values, not meanings. A law colour used for the wrong thing - red on a
count that is only waiting - passes here; the suite of the page that owns
the meaning holds that (tally_suite holds the awaiting count to ink).

The night is tests/paper_night.json, read through tests/night_harness.py.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
PORT = 8961
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

from night_harness import open_page

LAW = json.load(open("tests/colour_law.json"))

def norm(v):
    """Any CSS colour this suite meets, as (r, g, b, alpha to 3 places)."""
    v = v.strip()
    m = re.fullmatch(r"#([0-9A-Fa-f]{6})", v)
    if m:
        h = m.group(1); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]*)\)", v)
    if m:
        p = [float(x) for x in m.group(1).replace("/", ",").split(",")]
        return (round(p[0]), round(p[1]), round(p[2]), round(p[3] if len(p) == 4 else 1.0, 3))
    raise ValueError("not a colour: " + v)

def show(t):
    return ("#%02X%02X%02X" % t[:3]) if t[3] == 1 else "rgba(%d,%d,%d,%g)" % t

TOKENS = {k: norm(v["value"]) for k, v in LAW["tokens"].items() if not k.startswith("_")}
ALLOWED = set(TOKENS.values()) | {norm(a["value"]) for a in LAW["allergy"]["values"]}
PAGE_KEY = {page: {norm(a["value"]) for a in k["values"]} for page, k in LAW["page_keys"].items()}

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not detail else "  -> " + str(detail)))
    P, F = (P + 1, F) if cond else (P, F + 1)

# ── 1. the stylesheets define the table ─────────────────────────────────
def props(css):
    """Every custom property a stylesheet sets at :root, comments dropped."""
    out = {}
    for body in re.findall(r"^:root\s*\{(.*?)^\}", css, re.S | re.M):
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        out.update({k.strip(): v.strip() for k, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body)})
    return out

ui2 = props(open("nala-ui2.css", encoding="utf-8").read())
for name, want in TOKENS.items():
    got = ui2.get(name)
    ck("nala-ui2.css: %s is the law's %s" % (name, show(want)),
       got is not None and norm(got) == want, got)

ui1 = props(open("nala-ui.css", encoding="utf-8").read())
for old, law in LAW["print_tokens"].items():
    if old.startswith("_"): continue
    got = ui1.get(old)
    ck("nala-ui.css: the printed sheets' %s is the law's %s" % (old, show(TOKENS[law])),
       got is not None and norm(got) == TOKENS[law], got)

# ── 2. every board paints only the table ───────────────────────────────
# Read off the rendered page. A colour's FAMILY is judged on its own rgb, not
# as it lands: a .11 green is a green however faint, and a warm grey (the
# quiet fill, the hairline) is no family at all.
PAINTED = """() => {
  const parse = c => { const m = c && c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
    const p = m[1].replace('/', ',').split(',').map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length >= 4 ? p[3] : 1 }; };
  const fam = c => { const mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b), d = mx - mn;
    if (d < 10) return null;
    let h; if (mx === c.r) h = ((c.g - c.b) / d) % 6; else if (mx === c.g) h = (c.b - c.r) / d + 2;
    else h = (c.r - c.g) / d + 4; h = (h * 60 + 360) % 360;
    if (h >= 75 && h < 175) return 'green'; if (h >= 22 && h < 75) return 'amber';
    if (h < 22 || h >= 330) return 'red'; return null; };
  const sig = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    [...el.classList].slice(0, 3).map(c => '.' + c).join('');
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (r.width < 3 || r.height < 3 || cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const add = (prop, raw) => { const c = parse(raw); if (!c || c.a === 0 || !fam(c)) return;
      out.push({ prop, fam: fam(c), raw, sig: sig(el) }); };
    const g = (cs.backgroundImage || '').match(/linear-gradient\\((rgba?\\([^)]*\\))/);
    add('fill', g ? g[1] : cs.backgroundColor);
    for (const s of ['Top', 'Right', 'Bottom', 'Left'])
      if (parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none')
        add('border', cs['border' + s + 'Color']);
    const ins = (cs.boxShadow || '').match(/(rgba?\\([^)]*\\))[^,]*inset/);
    if (ins) add('edge', ins[1]);
    if ([...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) add('ink', cs.color);
    if (el instanceof SVGElement) { add('icon', cs.fill); add('icon', cs.stroke); }
  }
  return out;
}"""

def click_text(sel, text):
    def act(pg):
        for r in pg.query_selector_all(sel):
            if text in r.inner_text():
                r.click(); return
        raise Exception("nothing under %s reads %s" % (sel, text))
    return act

# Each board as it loads, then every sheet and mode that shows a state the
# load does not: a colour the fixture night never draws is a colour nobody
# checked.
BOARDS = {
  "tally.html": [("a villa's sheet", lambda pg: pg.click("#rooms .room >> nth=0")),
                 ("Add reservation", lambda pg: pg.click("#addExt")),
                 ("an invited guest's sheet", click_text("#listBookings .row", "Sarah Jones")),
                 ("select mode", lambda pg: (pg.click("#selToggle"), pg.wait_for_timeout(200),
                                             pg.click("#rooms .room >> nth=6")))],
  "front-desk.html": [("an incomplete form", click_text("#board button.arr", "Sharma")),
                      ("a completed arrival's summary", click_text("#board button.arr", "Reilly")),
                      ("the key card run", lambda pg: pg.click(".keybtn"))],
  "dashboard.html": [("the menu", lambda pg: pg.click("#navBtn"))],
  "cleaners.html": [("a villa's sheet", lambda pg: pg.click(".tile >> nth=0")),
                    ("a finished villa's sheet", lambda pg: pg.click(".tile.done >> nth=0"))],
  "spa.html": [("a booked card", click_text(".vrow", "James")),
               ("a suggested card", click_text(".vrow", "Tom Ashby")),
               ("a declined card", click_text(".vrow", "Owen Reilly"))],
  "invitations.html": [("the Arrivals list", lambda pg: pg.click(".arrivals > summary")),
                       ("the External guests list", lambda pg: pg.click(".extguests > summary")),
                       ("an external guest's sheet", lambda pg: (pg.click(".extguests > summary"),
                           pg.click(".extguests .vrow >> nth=0"))),
                       ("the invite sheet", lambda pg: (pg.click(".extguests > summary"),
                           pg.click("#extInvite")))],
  "arrivals-sms.html": [("the next 14 days", lambda pg: pg.click("#knob button >> nth=2"))],
  "spa-reminders.html": [("the preview of a changed booking",
                          lambda pg: pg.select_option("#pvSel", "b17/t9"))],
  "calendar.html": [("the Clean colouring", lambda pg: pg.click(".mbtn >> nth=1")),
                    ("the Dining colouring", lambda pg: pg.click(".mbtn >> nth=2")),
                    ("the Spa colouring", lambda pg: pg.click(".mbtn >> nth=3"))],
  "keys.html": [("a card's sheet", lambda pg: pg.click("#list .arr >> nth=0"))],
  "publish.html": [("Remove armed", lambda pg: pg.click("#rmBtn"))],
  "tag.html": [("a hidden dietary", lambda pg: pg.click("#mng .mtog >> nth=0"))],
  "guest.html?b=b1": [],
  "guest.html?b=b8": [],
  "guest.html?b=b14": [],
  "stats.html": [],
  # Chat and Tasks, 29 Sep: the list with every state a guest's row
  # can wear, a conversation with every state a message can be in (a task
  # open and done, no task, new, read, a send that failed) and its team
  # picker, and the Tasks page.
  "guest-contact.html": [("Upcoming", lambda pg: pg.click("#tabUp"))],
  "guest-contact.html?c=61410007919&b=b1": [("a message's team picker",
                                             lambda pg: pg.click("#tk-in-SMb"))],
  "tasks.html": [],
}

# COLOUR_ONLY=front-desk.html,keys.html narrows the boards, for a quick look
# while working; the full run always reads every board.
ONLY = [x for x in os.environ.get("COLOUR_ONLY", "").split(",") if x]
if ONLY:
    BOARDS = {k: v for k, v in BOARDS.items() if k.split("?")[0] in ONLY}

SEEN = set()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for board, states in BOARDS.items():
        page = board.split("?")[0]
        allowed = ALLOWED | PAGE_KEY.get(page, set())
        for label, act in [("as it loads", None)] + states:
            ctx, pg = open_page(b, PORT, board)
            try:
                if act: act(pg); pg.wait_for_timeout(600)
                got = pg.evaluate(PAINTED)
            except Exception as e:
                ck("%s: %s opens" % (board, label), False, str(e).split("\n")[0]); ctx.close(); continue
            bad, seen_here = {}, 0
            for g in got:
                t = norm(g["raw"]); SEEN.add(t); seen_here += 1
                if t not in allowed:
                    bad.setdefault(show(t), set()).add(g["sig"] + " " + g["prop"])
            ck("%s, %s: every green, amber and red is the law's" % (board, label), not bad,
               "; ".join("%s on %s" % (c, ", ".join(sorted(s)[:3])) for c, s in sorted(bad.items())))
            ctx.close()
    b.close()

# ── 3. the pass saw something ──────────────────────────────────────────
for token in [] if ONLY else ["--law-green", "--law-green-t", "--law-green-b", "--law-save-bg", "--law-amber",
              "--law-amber-b", "--law-amber-ink", "--law-terra", "--law-terra-t", "--law-terra-b", "--law-red"]:
    ck("the fixture night paints %s somewhere, so its absence elsewhere means something" % token,
       TOKENS[token] in SEEN)

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
