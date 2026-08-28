"""pages.html, the site map.

The point of this page is that a link which fails here fails everywhere, so the
suite's real job is to open every link it lists and confirm the file is served.
A site map that lies is worse than none: it is the thing you check when you are
already unsure.

It also checks the reverse, which is the failure a hand written map always
reaches eventually: a page exists in the repo and the map does not mention it.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re, urllib.request

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8966), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"}}

def fb(route, request):
    body = json.dumps(STAFF) if "/staff" in request.url else "null"
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_map(email="staff@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8966/pages.html")
        pg.wait_for_timeout(900)
        return pg

    pg = open_map()
    links = pg.evaluate("()=>[...document.querySelectorAll('#body a.p')]"
                        ".map(a=>a.getAttribute('href'))")
    ck("the map lists something", len(links) > 10)

    # Every link is opened for real. This is the whole point of the page.
    broken = []
    for href in links:
        code = urllib.request.urlopen(
            "http://localhost:8966/" + href, timeout=10).getcode()
        if code != 200: broken.append(href + " -> " + str(code))
    ck("every link on the map actually resolves", not broken)
    if broken: print("   broken:", broken)

    # The reverse, which is where a hand written map rots: a page ships and
    # nobody adds it here.
    on_disk = set(f for f in os.listdir(".") if f.endswith(".html"))
    # Compared on the file, not the whole address. The pre-arrival form is
    # linked as prearrival.html?b=demo, because without a booking id it can
    # only show the incomplete-link message and the one form a guest sees was
    # the one nobody here could open. A query string does not make it a
    # different page.
    def just_file(u):
        return str(u).split("?")[0].split("#")[0]
    listed = set(just_file(x) for x in links) | set(
        just_file(x) for x in
        pg.evaluate("()=>[...document.querySelectorAll('#body .p-f')]"
                    ".map(e=>e.textContent)"))
    missing = sorted(on_disk - listed)
    ck("no page exists in the repo that the map does not mention", not missing)
    if missing: print("   unlisted:", missing)

    # Nothing is unbuilt at the moment. When something is, it must be named
    # and not linked: a map should describe the app being built, not only the
    # one that exists, or the next person wonders what they missed.
    ck("anything not built is named but not linked",
       pg.evaluate("()=>[...document.querySelectorAll('.p.todo')]"
                   ".every(e=>e.tagName!=='A')"))

    #  One list, the same on every page, minus the page you are on. Standing on
    #  the site map, a link to the site map is one more thing to read and no
    #  way to anywhere. Pages is in every OTHER page's hamburger, which is what
    #  was actually asked for, and that is checked from a page that is not this
    #  one.
    #  Read from tests/nav_canon.json, the one table of the menu's shape,
    #  rather than restated here: four suites each holding the order is why
    #  adding a page meant editing them all.
    _nc = json.load(open("tests/nav_canon.json"))
    CANON = [h for h, _t in _nc["top"]] + \
            [h for _g, items in _nc["groups"] for h, _t in items]
    got = pg.evaluate("""()=>[...document.querySelectorAll('.navdrop a')]
        .map(a=>a.getAttribute('href')).filter(h=>h!=='#')""")
    ck("the map's own hamburger lists every other page, in the one order",
       got == [h for h in CANON if h != "pages.html"])
    ck("and not itself", "pages.html" not in got)

    for w in (390, 360, 320):
        q = open_map(w=w)
        ck("the map does not scroll sideways at %dpt" % w, not q.evaluate(
           "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    pg.close()

    # A map of the whole app is an admin tool, gated like Settings.
    q = open_map("chef@x")
    q.wait_for_timeout(600)
    ck("a chef is sent to their own board rather than shown the map",
       not q.url.endswith("pages.html"))
    q.close()
    q = open_map("housekeeping@x")
    q.wait_for_timeout(600)
    ck("and so is housekeeping", not q.url.endswith("pages.html"))
    q.close()

    b.close()

    # ── one filter, not nine ────────────────────────────────────
    #  Reported 23 Aug: a housekeeper had no Notifications switch on the Cleans
    #  board, which is the very page the switch used to live on. Six pages
    #  carried their own copy of the menu filter with their own map, all
    #  written before nala-shared.js grew one and none touched since. They knew
    #  nothing of Publish Menu, Dietary or the switch, and they hid whatever
    #  they did not recognise rather than leaving it alone. So those three
    #  vanished on exactly the pages that kept a copy.
    #
    #  Read from the source rather than from a rendered page: a private copy
    #  that happens to agree today is still the thing that goes stale next
    #  time a page is added.
    import glob, re as _re
    offenders = []
    for f in sorted(glob.glob("*.html")):
        if f.startswith("demo-"):
            continue                      # snapshots, rebuilt from the real pages
        src = open(f, encoding='utf-8').read()
        #  Guard on the exact string the parser below anchors to: a page that
        #  merely MENTIONS navFilterShared in a comment is not an offender,
        #  and the loose guard crashed on the first one that did.
        if "function navFilter" not in src:
            continue
        #  The function itself, brace matched, rather than a window of
        #  characters after it: an 800 character window swept up the page's own
        #  access gate and called it a menu filter.
        i = src.index("function navFilter")
        j = src.index("{", i); depth = 0; end = j
        for k in range(j, len(src)):
            if src[k] == "{": depth += 1
            elif src[k] == "}":
                depth -= 1
                if depth == 0:
                    end = k + 1; break
        body = src[i:end]
        if "manageStaff" in body or "style.display" in body:
            offenders.append(f)
    print("   pages with their own menu filter:", offenders)
    ck("no page keeps its own copy of the menu filter", offenders == [])

    # ── the shared files carry one version, and it is current ───
    #  The ?v= on the shared files is the whole caching story on this site,
    #  and the STYLESHEETS were not in this check until 28 Aug: nala-ui.css
    #  could be edited and published without a single bump, and every phone
    #  would go on using the CSS it already had. A restyle is exactly the
    #  change that hole swallows.
    #  and it had not been bumped in four changes: the sign-in persistence fix,
    #  the menu filter, the notifications switch. Browsers went on running the
    #  old copies, so fixes that were published and correct simply never
    #  reached the phone that reported them. The owner guessed cache before I
    #  looked.
    import glob as _g, re as _r, subprocess as _sp
    vers = {}
    for f in sorted(_g.glob("*.html")):
        if f.startswith("demo-"):
            continue
        for m in _r.finditer(
                r'(nala-shared\.js|auth\.js|nala-ui\.css|nala-ui2\.css)\?v=(\d+)',
                open(f, encoding='utf-8').read()):
            vers.setdefault(m.group(1), set()).add(m.group(2))
    print("   shared file versions:", {k: sorted(v) for k, v in vers.items()})
    ck("every page asks for the same version of each shared file",
       all(len(v) == 1 for v in vers.values()))

    #  And the version has to move when the file does. A file changed since its
    #  last bump is a file the browser will not fetch.
    stale = []
    for name, v in vers.items():
        vv = list(v)[0]
        touched = _sp.run(["git", "log", "-1", "--format=%H", "--", name],
                          capture_output=True, text=True).stdout.strip()
        bumped = _sp.run(["git", "log", "-1", "--format=%H", "-S",
                          name + "?v=" + vv],
                         capture_output=True, text=True).stdout.strip()
        if not touched or not bumped:
            continue
        order = _sp.run(["git", "rev-list", "--count",
                         bumped + ".." + touched], capture_output=True, text=True)
        if order.returncode == 0 and order.stdout.strip().isdigit() \
           and int(order.stdout.strip()) > 0:
            stale.append(name)
    print("   shared files changed since their version was bumped:", stale)
    ck("no shared file has changed since the version browsers ask for",
       stale == [])

    # ── the house style, enforced rather than written down ───────────
    #  Every rule below is one STYLEGUIDE.md already states in prose and
    #  nothing checked. Measured on 28 Aug, before any of this: 64% of
    #  font-size declarations were off the declared 8/11/15/20/27 scale,
    #  --ink was redefined in 18 pages and --cream in 17 despite "defined
    #  once in nala-ui.css", 87 font stacks were hardcoded against "no page
    #  hardcodes a font stack", and --green meant a pale fill on five pages
    #  and a dark ink on two. A rule nobody can fail is a rule that rots.
    #
    #  Scoped to pages carrying `ui2`, the second dress, because those are
    #  the pages that have been converted. As a page joins the dress it
    #  joins these checks, which is what makes the migration one way.
    #  Not anchored to a line start: `:root { --a:x; --b:y; }` on one line
    #  is how every page declares these, and an anchored pattern reads only
    #  the first. `--x:` appears only in declarations, never in var(--x).
    #  Comments are stripped before any of this. These files explain their
    #  own tokens constantly - "Not --amber: that name is the colour law's
    #  attention FILL" is prose, not a declaration - and a checker that reads
    #  prose as code cries wolf until somebody turns it off.
    def decomment(t):
        return _r.sub(r'/\*.*?\*/', ' ', t, flags=_r.S)
    OWNED = set(_r.findall(r'(--[a-z0-9-]+)\s*:',
                decomment(open("nala-ui2.css", encoding="utf-8").read())))
    def style_of(txt):
        m = _r.search(r'<style>(.*?)</style>', txt, _r.S)
        return m.group(1) if m else ""

    ui2, bad_link, bad_tok, bad_font, bad_size, bad_zoom = [], [], [], [], [], []
    for f in sorted(_g.glob("*.html")):
        if f.startswith(("demo-", "mock-")):
            continue
        txt = open(f, encoding="utf-8").read()
        wears = _r.search(r'<body[^>]*class="[^"]*\bui2\b', txt) is not None
        links = _r.search(r'<link[^>]+nala-ui2\.css', txt) is not None
        if wears != links:
            bad_link.append(f)
        if not wears:
            continue
        ui2.append(f)
        st = style_of(txt)
        #  A page that redefines a shared token silently wins over the sheet,
        #  because :root and body.ui2 are the same specificity and the page
        #  comes later. That is how --green came to mean two things.
        for t in _r.findall(r'(--[a-z0-9-]+)\s*:', decomment(st)):
            if t in OWNED:
                bad_tok.append(f + " " + t)
        #  "No page hardcodes a font stack. Changing the staff font is one
        #  line." It was one line and 87 places.
        if _r.search(r'font-family:\s*(?!var\()', decomment(st)):
            bad_font.append(f)
        #  Sizes come from the scale or they are picked by eye. A deliberate
        #  exception is allowed the way CLAUDE.md allows any other: say why,
        #  in the file, next to the thing. Mark the line `off-scale: reason`
        #  and this stops asking. The Cleans board's tile internals are the
        #  first: its tiles are a fixed grid the owner has ruled stays as it
        #  is, and inflating the type inside them would overflow it.
        for line in st.splitlines():
            if "off-scale:" in line:
                continue
            for m in _r.findall(r'font-size:\s*([0-9.]+(?:px|rem))',
                                _r.sub(r'/\*.*?\*/', ' ', line)):
                bad_size.append(f + " " + m)
        #  Takes pinch zoom from anyone who needs it, and never did the job
        #  it was added for; touch-action:manipulation does that instead.
        if "user-scalable=no" in txt:
            bad_zoom.append(f)

    print("   pages wearing the second dress:", ui2)
    ck("a page wears the dress and links its sheet, or neither", not bad_link)
    if bad_link: print("   mismatched:", bad_link)
    ck("no page redefines a token the shared sheet owns", not bad_tok)
    if bad_tok: print("   redefined:", bad_tok)
    ck("no page hardcodes a font stack", not bad_font)
    if bad_font: print("   hardcoded:", bad_font)
    ck("every font size comes from the scale, not by eye", not bad_size)
    if bad_size: print("   off-scale:", sorted(set(bad_size)))
    ck("no page takes pinch zoom away", not bad_zoom)
    if bad_zoom: print("   user-scalable=no:", bad_zoom)


# ── every control has a shape ────────────────────────────────────────
#  Reported by the owner off a screenshot, 29 Aug: the Reservations sheet's
#  buttons were square while everything round them was rounded. The radius
#  pass rewrote the values it found, and .opt and .selbtn declared none at
#  all, so there was nothing to rewrite and nothing to notice. debug.html
#  was worse - bare <button> elements with no class, so four buttons that
#  delete records had no dress and nothing saying they were destructive.
#
#  A missing declaration is invisible to a grep, so this one reads the
#  rendered page. The footer row is exempt by the corner law: it sits hard
#  against the bottom of the screen and squares off on purpose.
_dressed = [f for f in sorted(_g.glob("*.html"))
            if not f.startswith(("demo-", "mock-"))
            and _r.search(r'<body[^>]*class="[^"]*\bui2\b', open(f, encoding="utf-8").read())]
_square = []
with sync_playwright() as p2:
    b2 = p2.chromium.launch()
    for f in _dressed:
        q = b2.new_page(viewport={"width": 390, "height": 844})
        q.add_init_script(SDK)
        q.add_init_script("window.__EMAIL='admin@nalaresort.com.au';")
        q.goto("http://localhost:8966/" + f)
        q.wait_for_timeout(700)
        got = q.evaluate("""()=>{const out=[];
          document.querySelectorAll('button,a.btn,input[type=button]').forEach(e=>{
            const c=getComputedStyle(e), r=e.getBoundingClientRect();
            if(r.width<8||r.height<8) return;
            if(c.borderTopLeftRadius==='0px' && c.borderBottomRightRadius==='0px'
               && !e.closest('.foot'))
              out.push((e.className||e.tagName)+' "'+e.textContent.trim().slice(0,18)+'"');});
          return [...new Set(out)];}""")
        q.close()
        if got:
            _square.append(f + ": " + ", ".join(got[:3]))
    b2.close()
ck("every control has a shape, none left square", not _square)
for x in _square:
    print("   square:", x)

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
