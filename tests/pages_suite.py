"""pages.html, the site map.

The point of this page is that a link which fails here fails everywhere, so the
suite's real job is to open every link it lists and confirm the file is served.
A site map that lies is worse than none: it is the thing you check when you are
already unsure.

It also checks the reverse, which is the failure a hand written map always
reaches eventually: a page exists in the repo and the map does not mention it.
"""
import threading, http.server, socketserver, json, time, os, re, urllib.request

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("", 8966), Q)
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
        pg.route("**/*.firebasedatabase.app/**", fb)
        pg.route("**/gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
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
    listed = set(links) | set(
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

    ck("Pages is in the hamburger, where it was asked for",
       pg.evaluate("()=>[...document.querySelectorAll('.navdrop a')]"
                   ".some(a=>a.getAttribute('href')==='pages.html')"))

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

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
