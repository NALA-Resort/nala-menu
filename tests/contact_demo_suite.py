"""The Guest Contact demo (contact-demo.js): the real Guest Contact and Tasks
pages with made-up guests, entered as ?demo, before Twilio exists.

The owner, 29 Sep: "Maybe a demo environment is better?" Pinned down:

  1. Nothing leaves the page: no request reaches the database, the
     messenger or the push Worker - every one of them is answered in the
     tab. The network is watched, not assumed.
  2. The whole flow works on the made-up guests: a guest writes in, the
     message is sorted into a team's task, the team's login sees it and
     presses Done, a reply goes and its receipts come.
  3. The demo stays in the demo: moving between the two pages keeps it,
     a link anywhere else is stopped, and Leave demo forgets it.
  4. Off the demo the module does nothing: contact_suite runs the same
     pages without ?demo.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, sys

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
PORT = 8944
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)) if not cond and detail != "" else ""))
    P, F = (P + 1, F) if cond else (P, F + 1)

LEFT = []   # every request that tried to leave the machine
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(viewport={"width": 390, "height": 900}, timezone_id="Australia/Brisbane")
    def outside(route, request):
        LEFT.append(request.url)
        route.abort()
    ctx.route("**/*", lambda route, request: route.continue_()
              if request.url.startswith("http://localhost:%d/" % PORT) else outside(route, request))
    pg = ctx.new_page()
    def go(path):
        pg.goto("http://localhost:%d/%s" % (PORT, path)); pg.wait_for_timeout(1500)
    rows = lambda: pg.evaluate("""()=>[...document.querySelectorAll('#board .vrow')].map(e=>({
        ck:e.dataset.ck, s:e.dataset.state, nm:e.querySelector('.nm').textContent}))""")

    # ── 1. the list, with nothing leaving ──────────────────────────
    go("guest-contact.html?demo")
    ck("the demo says what it is at the top",
       "made-up guests" in (pg.text_content("#demoBar") or ""))
    ck("with no sign-in to get past", not pg.is_visible("text=Sign in"))
    rs = rows()
    by = {r["ck"]: r for r in rs if r["ck"]}
    ck("In-house shows the made-up guests, work first",
       rs and rs[0]["s"] == "fresh" and by["61412345678"]["nm"] == "Sarah Whitfield" and
       by["61411000009"]["s"] == "task" and by["61411000002"]["s"] == "done", rs[:4])
    ck("and nothing tried to reach the database, the messenger or Firebase",
       not [u for u in LEFT if "firebasedatabase" in u or "workers.dev" in u or "identitytoolkit" in u],
       LEFT)

    # ── 2. a guest writes in, and it is sorted into a task ─────────
    before = len([r for r in rows() if r["s"] == "fresh"])
    pg.click("#demoGuest")
    pg.select_option("#demoFrom", "61411000016")          # Jonah, villa 16, nothing yet
    pg.select_option("#demoCh", "wa")
    pg.fill("#demoText", "Could someone fix the outdoor shower?")
    pg.click("#demoSend"); pg.wait_for_timeout(800)
    rs = rows(); by = {r["ck"]: r for r in rs if r["ck"]}
    ck("a guest writing in lands New, at the top",
       by["61411000016"]["s"] == "fresh" and len([r for r in rs if r["s"] == "fresh"]) == before + 1, by.get("61411000016"))
    pg.click('.vrow[data-ck="61411000016"]'); pg.wait_for_timeout(1200)
    mid = pg.evaluate("()=>[...document.querySelectorAll('.msg.in')].map(e=>e.dataset.m).pop()")
    ck("their conversation holds the message, waiting to be sorted",
       "Could someone fix the outdoor shower?" in pg.text_content("#msgs") and
       pg.is_visible("#nt-" + mid) and pg.is_visible("#tk-" + mid), mid)
    pg.click("#tk-" + mid); pg.wait_for_timeout(200)
    pg.click("#tm-%s-maintenance" % mid); pg.wait_for_timeout(1200)
    tri = pg.evaluate("(m)=>document.querySelector('.msg[data-m=\"'+m+'\"] .tri').innerText", mid)
    ck("Task, Maintenance: the message is now Maintenance's, open", "Maintenance" in tri and "open" in tri, tri)

    # a reply, and its receipts
    pg.fill("#msgBox", "On our way to have a look.")
    pg.click("#sendBtn"); pg.wait_for_timeout(1200)
    ck("a reply goes, inside WhatsApp's 24 hours, on WhatsApp",
       "On our way to have a look." in pg.text_content("#msgs"))
    pg.wait_for_timeout(9500)
    last = pg.evaluate("()=>[...document.querySelectorAll('.msg.out .meta')].map(e=>e.textContent).pop()")
    ck("and its receipts come, as the handset's would", "Read" in last or "Delivered" in last, last)

    # past the 24 hours: James
    go("guest-contact.html?c=61438220761&t=up")
    ck("James wrote six days ago, so the box offers only the approved words, or SMS",
       pg.is_visible("#tplPrev") and not pg.is_visible("#msgBox"), pg.text_content("#compose") if pg.query_selector("#compose") else "")

    # ── 3. a team's login closes it ────────────────────────────────
    pg.select_option("#demoWho", "ray@demo"); pg.wait_for_timeout(1800)
    ck("looking as Ray, Maintenance, the demo opens Tasks", pg.url.split("?")[0].endswith("tasks.html"), pg.url)
    words = pg.evaluate("()=>[...document.querySelectorAll('#board .task')].map(e=>e.querySelector('.words').textContent)")
    ck("where the shower is, beside the umbrella, and nobody else's",
       "Could someone fix the outdoor shower?" in words and len(words) == 2, words)
    pg.wait_for_timeout(600)
    shower = pg.evaluate("""()=>{const c=[...document.querySelectorAll('#board .task')].filter(e=>
        e.querySelector('.words').textContent.indexOf('shower')>-1)[0];
        return [...c.querySelectorAll('.lg')].map(e=>e.textContent)}""")
    ck("the card carries the conversation since the request: Reception's reply",
       any(x.startswith("Reception") and "On our way to have a look." in x for x in shower), shower)
    ck("and the umbrella card shows the guest's photo",
       pg.evaluate("()=>[...document.querySelectorAll('#board img.tphoto')].some(i=>i.src.startsWith('blob:'))"))
    tid = pg.evaluate("""()=>[...document.querySelectorAll('#board .task')].filter(e=>
        e.querySelector('.words').textContent.indexOf('shower')>-1)[0].dataset.t""")
    pg.click('.task[data-t="%s"] .sbtn' % tid); pg.wait_for_timeout(1500)
    ck("Done closes it in Ray's name", "Done today" in pg.text_content("#doneSum"))
    go("guest-contact.html")
    ck("and Ray, who may not open Guest Contact, is sent to Tasks, still in the demo",
       pg.url.split("?")[0].endswith("tasks.html") and pg.is_visible("#demoBar"), pg.url)
    pg.select_option("#demoWho", "desk@demo"); pg.wait_for_timeout(1800)
    ck("back as Reception, Guest Contact again", pg.url.split("?")[0].endswith("guest-contact.html"))
    # the owner's own example: drinks by the pool, then which ones
    pg.select_option("#demoWho", "anna@demo"); pg.wait_for_timeout(2000)
    gin = pg.evaluate("""()=>{const c=document.querySelector('.task[data-t="t2gandt"]');
        return c ? {note:(c.querySelector('.tnote')||{}).textContent||'',
                    lg:[...c.querySelectorAll('.lg')].map(e=>e.textContent)} : null}""")
    ck("as Anna, Bar: the drinks arrive with the desk's note, and which drinks",
       bool(gin) and "Charge to villa 9" in gin["note"] and any("Tanqueray" in x for x in gin["lg"]) and
       any(x.startswith("Reception") for x in gin["lg"]), gin)
    pg.select_option("#demoWho", "desk@demo"); pg.wait_for_timeout(1800)

    # ── 4. it stays the demo ───────────────────────────────────────
    menu = pg.evaluate("""()=>[...document.querySelectorAll('#navDrop a')]
        .filter(a=>getComputedStyle(a).display!=='none').map(a=>a.getAttribute('href'))""")
    ck("the menu offers only the demo's two pages", set(h for h in menu if h and h != "#") <= {"tasks.html", "guest-contact.html"}, menu)
    pg.evaluate("()=>{const a=document.createElement('a');a.href='tally.html';a.id='out';a.textContent='out';document.body.appendChild(a);}")
    pg.click("#out"); pg.wait_for_timeout(400)
    ck("a link out of the demo is stopped, and says why",
       pg.url.split("?")[0].endswith("guest-contact.html") and "Only Guest Contact and Tasks" in pg.text_content("#demoSay"))
    pg.click("#demoReset"); pg.wait_for_timeout(1200)
    ck("Start again puts the made-up guests back as they were",
       [r["s"] for r in rows() if r["ck"] == "61411000016"] == ["none"])
    for w in (390, 320):
        pg.set_viewport_size({"width": w, "height": 900}); pg.wait_for_timeout(300)
        ck("the demo bar has no sideways scroll at %d" % w,
           not pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
    pg.set_viewport_size({"width": 390, "height": 900})
    ck("and through all of it nothing left the page for the live app",
       not [u for u in LEFT if "firebasedatabase" in u or "workers.dev" in u or "identitytoolkit" in u],
       [u for u in LEFT if "firebasedatabase" in u or "workers.dev" in u][:3])
    pg.click("#demoLeave"); pg.wait_for_timeout(800)
    ck("Leave demo forgets it", pg.url.split("?")[0].endswith("pages.html") and
       pg.evaluate("()=>sessionStorage.getItem('nalaContactDemo')") is None)
    br.close()

httpd.shutdown()
print("RESULT: %d passed, %d failed" % (P, F))
sys.exit(1 if F else 0)
