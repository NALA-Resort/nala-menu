"""welcome.html, the page a guest lands on before anything else.

It is the first thing GuestTouch sends and it is opened on a phone, often on a
shared one, often in a lobby with someone standing behind. So the two things
worth pinning are that it shows nothing about the guest, and that it hands the
booking id on to the menu, because a guest who arrives at the menu without one
cannot answer their own dinner.

The page writes nothing. That is asserted rather than assumed: every database
request is intercepted and the count has to stay at zero.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8971), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

DB_HITS = []

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def open_page(query="", w=390, h=844):
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.route("**/*.firebasedatabase.app/**",
                 lambda r, req: (DB_HITS.append(req.url),
                                 r.fulfill(status=200, content_type="application/json",
                                           body="null")))
        pg.route("**/fonts.googleapis.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.route("**/fonts.gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8971/welcome.html" + query)
        pg.wait_for_timeout(400)
        return pg

    B = "?b=abc-123-def"

    pg = open_page(B)

    # ── the booking id is carried, not consumed ───────────────
    ck("the menu button carries the booking id through",
       "b=abc-123-def" in pg.get_attribute("#menuBtn", "href"))
    ck("and it points at the menu, not back at itself",
       pg.get_attribute("#menuBtn", "href").split("?")[0] in ("/", "./", "index.html"))

    # A link that arrives without a booking id still has to open. The guest
    # reaches the menu and is asked who they are there, which is a worse
    # experience than being known, but not a dead end.
    q = open_page("")
    ck("a link with no booking id still opens the menu",
       q.get_attribute("#menuBtn", "href") is not None
       and q.locator("#menuBtn").is_visible())
    q.close()

    # ── nothing about the guest is on screen ──────────────────
    body = pg.inner_text("body")
    ck("the greeting is generic, not the guest's name",
       "Welcome to Nala" in pg.inner_text("#greet"))
    ck("the booking id is nowhere in the visible text", "abc-123-def" not in body)

    # A name in the link is a real case: pre-arrival is sent with one, and the
    # same link shape gets pasted around. It must not be echoed here.
    q = open_page("?b=abc-123-def&n=Robyn%20Williams&villa=4")
    t = q.inner_text("body")
    ck("a name in the link is not shown", "Robyn" not in t and "Williams" not in t)
    ck("a villa number in the link is not shown either",
       "villa 4" not in t.lower())
    ck("but it is still passed to the menu",
       "n=Robyn" in q.get_attribute("#menuBtn", "href"))
    q.close()

    # ── it writes nothing, and reads nothing ──────────────────
    ck("the page makes no database request at all", not DB_HITS)

    # ── the ways out ──────────────────────────────────────────
    # There used to be a Text Us button here printing a mobile number. The
    # guest is reading this page from a link in a message from that number, so
    # it told them something they already had, and it put a personal mobile on
    # a public page. The words point at the thread they are already in.
    src = open("/home/claude/nala/welcome.html").read()
    ck("no phone number is printed on the page", "0468067233" not in src)
    ck("nor any sms link at all", "sms:" not in src)
    ck("and the page says to reply to the message instead",
       "reply to the message" in src)
    ck("the button that printed it is gone",
       pg.locator("a.btn.outline").count() == 0)
    # A style rule with nothing to style is how a stylesheet stops describing
    # the page it belongs to.
    ck("and its styles went with it",
       ".btn.outline {" not in src and ".btn .sub {" not in src)

    # Pressed one handed by someone who has just arrived.
    box = pg.locator("#menuBtn").bounding_box()
    ck("the menu button is a comfortable tap target", box["height"] >= 44)

    ck("the logo actually loads",
       pg.evaluate("()=>{var i=document.querySelector('.logo');"
                   "return i.complete && i.naturalWidth>0;}"))

    # ── it is a link somebody shares, so the preview matters ──
    for prop in ("og:title", "og:image", "og:description"):
        ck("the link preview carries %s" % prop, pg.evaluate(
            "p=>!!document.querySelector('meta[property=\"'+p+'\"]')"
            "&&document.querySelector('meta[property=\"'+p+'\"]').content.length>0", prop))

    pg.close()

    # ── phone geometry ────────────────────────────────────────
    for w in (390, 360, 320):
        q = open_page(B, w=w)
        ck("no sideways scroll at %dpt" % w, not q.evaluate(
            "()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        q.close()

    # The whole point of the layout is that it is one screen. An SE is the
    # short one that catches it, and the short-screen rules exist for it.
    for w, h, name in ((390, 844, "a modern phone"), (375, 667, "an SE")):
        q = open_page(B, w=w, h=h)
        ck("it fits one screen on %s" % name, q.evaluate(
            "()=>document.documentElement.scrollHeight<=document.documentElement.clientHeight+2"))
        q.close()

    # Landscape is not the way anyone reads this, but a phone rotates in a
    # pocket and the page should not collapse when it does.
    q = open_page(B, w=740, h=360)
    ck("landscape does not scroll sideways", q.evaluate(
        "()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
    q.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
