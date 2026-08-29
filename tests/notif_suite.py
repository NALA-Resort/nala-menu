"""notifications.html, the per-person switch.

The page exists because of a bug the owner reported on 29 Aug: the masseuse
could not turn notifications on. The switch was a row inside the Settings
submenu, and for a spa or housekeeping login every OTHER row in that group is
hidden - so the only control either of them owns sat alone behind a collapsed
heading named after the pages they may not open. He never found it.

So the three things worth pinning here:

  1. Every role with a record may open it. It is the one page in the app with
     no permission behind it, and a spa login must land on it, because the
     whole point is the role that owns nothing else.
  2. The four browser states each say what to DO. Blocked and unavailable
     were dead ends when three words in a menu row was all they had.
  3. The list tells a person what will actually reach their phone, computed
     the way can() computes a permission: the stored matrix where it has an
     opinion, the shipped defaults where it has not. The masseuse has no
     column in the Settings grid, so this page is the only place the answer
     is visible at all.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8993), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

STAFF = {"staff@x":    {"name": "Admin",    "role": "admin"},
         "masseuse@x": {"name": "Masseuse", "role": "spa"},
         "hk@x":       {"name": "HK",       "role": "housekeeping"},
         "chef@x":     {"name": "Chef",     "role": "chef"},
         "waiter@x":   {"name": "Waiter",   "role": "waiter"}}

NOTIFY = {"on": True, "hours": {"from": "07:30", "to": "18:00"}, "events": {}}

WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u:   body = json.dumps(STAFF)
    elif "/notify" in u: body = json.dumps(NOTIFY)
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

#  The one table both halves answer to: a label with no default buzzes
#  nobody, and a default with no label is one nobody can see. Read out of the
#  shared file rather than restated, the phone_cases.json pattern.
SRC = open("nala-shared.js").read()
LABELS = re.findall(r"\['([A-Za-z]+)',\s*'[^']*'\]",
                    re.search(r"var NOTIFY_EVENTS = \[(.*?)\n\];", SRC, re.S).group(1))
DEFAULTS = re.search(r"var NOTIFY_DEFAULTS = \{(.*?)\n\};", SRC, re.S).group(1)
DEF_KEYS = re.findall(r"^\s{4}(\w+):\s*\{", DEFAULTS, re.M)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def page(email="masseuse@x", w=390):
        pg = b.new_page(viewport={"width": w, "height": 900})
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8993/notifications.html")
        pg.wait_for_timeout(1000)
        return pg

    # ── the one table, both ways round ──────────────────────────
    ck("every event with a label has defaults behind it",
       all(k in DEF_KEYS for k in LABELS))
    ck("and every event with defaults has a label",
       all(k in LABELS for k in DEF_KEYS))
    ck("the spa five are in it, which is what the grid cannot show",
       len([k for k in LABELS if k.startswith("spa")]) == 5)

    # ── who may open it ─────────────────────────────────────────
    #  No permission behind this page, on purpose: everybody owns their own
    #  phone. The masseuse most of all - it is the only control he has.
    for email, who in [("masseuse@x", "the masseuse"), ("hk@x", "a housekeeper"),
                       ("chef@x", "the chef"), ("waiter@x", "a waiter"),
                       ("staff@x", "an admin")]:
        pg = page(email)
        ck("%s may open it" % who,
           pg.evaluate("()=>getComputedStyle(document.getElementById('main'))"
                       ".display!=='none'"))
        pg.close()

    #  No record is no access, here as everywhere: a typo in an address must
    #  not be the thing that grants a page.
    pg = page("stranger@x")
    ck("a login with no staff record is refused",
       pg.evaluate("()=>document.getElementById('noAccess').className.indexOf('show')>-1")
       and pg.evaluate("()=>getComputedStyle(document.getElementById('main'))"
                       ".display==='none'"))
    #  And is not bounced: a login with no record has no home to be sent to,
    #  so a redirect would be a loop.
    ck("and stays on the page rather than being bounced",
       "notifications.html" in pg.url)
    pg.close()

    # ── the four states, each with something to do ──────────────
    pg = page("masseuse@x")
    states = pg.evaluate("""()=>{const out={};
       ['on','off','blocked','unsupported'].forEach(s=>{
         window.__paintNotify(s);
         out[s] = { head: document.getElementById('stateHead').textContent,
                    why:  document.getElementById('stateWhy').textContent,
                    act:  (document.getElementById('toggle')||{}).textContent || null,
                    mark: (document.querySelector('#switch .navmark')||{}).className || null,
                    sunk: !!document.querySelector('#switch .card.sunk') };
       });
       return out;}""")
    print("   states:", json.dumps(states, indent=1)[:400])
    ck("on says it is on, and offers to turn it off",
       "are on" in states["on"]["head"] and "off" in states["on"]["act"].lower())
    ck("off says it is off, and offers to turn it on",
       "are off" in states["off"]["head"] and "on" in states["off"]["act"].lower())
    ck("on wears a tick and off wears a cross",
       "on" in states["on"]["mark"] and "off" in states["off"]["mark"])
    #  The two that cannot be undone by tapping. In the menu row they had
    #  three words and no remedy; a page can say where the remedy is.
    ck("blocked wears no mark and names the phone's own settings",
       states["blocked"]["mark"] is None and
       "settings" in states["blocked"]["why"].lower())
    ck("and still offers a way to look again once it is allowed",
       states["blocked"]["act"] is not None)
    ck("unavailable names the Home Screen, which is the actual fix on iOS",
       "home screen" in states["unsupported"]["why"].lower())
    #  Nothing to do here, so it sinks. The colour law: not red, which would
    #  call a phone without the feature a failure.
    ck("and sinks rather than reddening, with no button to press",
       states["unsupported"]["sunk"] and states["unsupported"]["act"] is None)
    ck("it is per phone, and says so where somebody might assume otherwise",
       "phone" in states["on"]["why"].lower())

    # ── what will actually reach this phone ─────────────────────
    def listed(pg):
        return pg.evaluate("()=>[...document.querySelectorAll('#list .ev .nm')]"
                           ".map(e=>e.textContent)")
    got = listed(pg)
    print("   masseuse hears:", got)
    #  His four, from NOTIFY_DEFAULTS. Not Suggested: he just made that one.
    ck("the masseuse is told the four massage events he is routed",
       got == ["Massage requested", "Massage booked", "Massage cancelled",
               "Stay changed under a massage"])
    ck("and not the one he raised himself",
       "Massage suggested" not in got)
    ck("nor anything from the boards he cannot see",
       not any(x in got for x in ["Departed", "Cleaned", "Serviced",
                                  "Possibly available", "Menu published"]))
    ck("the sending hours are shown, since a silent evening is not a fault",
       "07:30" in pg.inner_text("#quiet") and "18:00" in pg.inner_text("#quiet"))
    pg.close()

    pg = page("hk@x")
    got = listed(pg)
    print("   housekeeper hears:", got)
    ck("a housekeeper gets her four and no massages",
       got == ["Departed", "Possibly available", "Cleaned", "Serviced"])
    pg.close()

    #  The chef is routed nothing at all by default. Silence under a switch
    #  reads as a broken switch, which is the confusion this page exists to
    #  end, so it says so in words.
    pg = page("chef@x")
    ck("a role routed nothing is told so, rather than shown an empty list",
       listed(pg) == [] and "nothing is routed" in pg.inner_text("#list").lower())
    pg.close()

    # ── the stored matrix beats the shipped default ─────────────
    #  Only boxes moved off the default are stored, so an absent key is the
    #  default standing and a present one wins. The same two-step can() does.
    NOTIFY["events"] = {"spaBooked": {"spa": False},
                        "departed":  {"spa": True}}
    pg = page("masseuse@x")
    got = listed(pg)
    print("   masseuse after an override:", got)
    ck("a stored false takes an event off his list",
       "Massage booked" not in got)
    ck("and a stored true puts one on it that the defaults never gave him",
       "Departed" in got)
    pg.close()

    # ── the manager's master switch ─────────────────────────────
    #  It beats every personal one, so a phone that is on and silent has to
    #  be told why here rather than left to wonder.
    NOTIFY["events"] = {}
    NOTIFY["on"] = False
    pg = page("masseuse@x")
    ck("all-off is explained, not left as an unexplained silence",
       "turned all notifications off" in pg.inner_text("#quiet").lower())
    pg.close()
    NOTIFY["on"] = True

    # ── the switch writes, and writes the role it is ────────────
    pg = page("masseuse@x")
    del WRITES[:]
    pg.evaluate("()=>{ window.__paintNotify('on'); document.getElementById('toggle').click(); }")
    pg.wait_for_timeout(700)
    dels = [w for w in WRITES if w["m"] == "DELETE" and "/pushsubs/" in w["u"]]
    ck("turning it off deletes this phone's subscription, not just the browser's",
       len(dels) == 1)
    ck("under the login's own key, commas not dots",
       bool(dels) and "/pushsubs/masseuse@x/" in dels[0]["u"])
    pg.close()

    # ── the menu ────────────────────────────────────────────────
    pg = page("staff@x")
    ck("the page omits its own link, like every other",
       pg.evaluate("""()=>![...document.querySelectorAll('#navDrop a')]
          .some(a=>a.getAttribute('href')==='notifications.html')"""))
    pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
