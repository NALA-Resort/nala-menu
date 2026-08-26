"""flags.html, Flag Settings.

The admin's list of booking flags: the names the front desk can tick on a
booking and the FOH Sheet prints under the guest's name. Two things worth
pinning.

The first is tag.html's lesson, inherited whole: Save is a PUT of the entire
list, so a refused read must LOCK the page rather than read as an empty list,
or Save would replace the real list with the three seeded defaults.

The second is the automatic flag. Luxury Escapes rides on the Mews rate and
is not a row in this list, so the page has to say so, and has to refuse an
admin who tries to create it by hand - a hand-made copy would print twice on
the sheet the day a Luxury Escapes rate arrives.
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
httpd = http.server.ThreadingHTTPServer(("", 8981), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

def sdk(email="staff@x"):
    return """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'%s',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'%s'});},25);},
signOut:function(){}};""" % (email, email)

MASTER = {"VIP": {"name": "VIP", "active": True, "at": "t"},
          "Travel agent": {"name": "Travel agent", "active": True, "at": "t"},
          "Old badge": {"name": "Old badge", "active": False, "at": "t"}}

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "manager@x": {"name": "Manager", "role": "manager"},
         "chef@x": {"name": "Chef", "role": "chef"}}

STATE = {"master": MASTER, "fail": False}
WRITES = []

def fb(route, request):
    u, m = request.url, request.method
    if m in ("PUT", "PATCH", "DELETE"):
        WRITES.append({"m": m, "u": u, "b": request.post_data})
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    body = "null"
    if "/staff" in u: body = json.dumps(STAFF)
    elif "/flags" in u:
        if STATE["fail"]:
            route.fulfill(status=401, content_type="application/json",
                          body='{"error":"denied"}'); return
        body = json.dumps(STATE["master"])
    route.fulfill(status=200, content_type="application/json", body=body)

P = F = 0
def ck(name, cond):
    global P, F
    print(("PASS " if cond else "FAIL ") + name)
    P, F = (P + 1, F) if cond else (P, F + 1)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    def page(email="staff@x"):
        pg = b.new_page(viewport={"width": 390, "height": 900})
        pg.add_init_script(sdk(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:8981/flags.html")
        pg.wait_for_timeout(1200)
        return pg

    # ── the list ────────────────────────────────────────────────
    pg = page()
    rows = pg.evaluate("""()=>[...document.querySelectorAll('.mrow')]
        .map(r=>({name:r.querySelector('.mname').textContent,
                  off:r.className.includes('off'),
                  btn:r.querySelector('.mtog').textContent}))""")
    ck("the stored list paints, active flags first",
       [r["name"] for r in rows] == ["Travel agent", "VIP", "Old badge"])
    ck("an archived flag reads as archived and offers Restore",
       rows[2]["off"] and rows[2]["btn"] == "Restore")
    ck("an active one offers Archive", rows[0]["btn"] == "Archive")
    ck("the automatic flag is named so nobody re-creates it",
       "Luxury Escapes" in pg.locator("#autorow").inner_text()
       and "automatic" in pg.locator("#autorow").inner_text().lower())
    #  Scoped to /flags: nala-shared archives the menu history on any page
    #  load, which is its business and not this list's.
    ck("and no flag is written just by looking",
       not [x for x in WRITES if "/flags" in x["u"]])

    # ── adding and saving ───────────────────────────────────────
    pg.fill("#newName", "Honeymoon")
    pg.click("#addBtn"); pg.wait_for_timeout(200)
    ck("a new flag joins the list unsaved",
       pg.evaluate("()=>[...document.querySelectorAll('.mname')]"
                   ".some(e=>e.textContent==='Honeymoon')"))
    ck("and the save bar appears, because the list on screen has moved",
       pg.evaluate("()=>savebar.className.includes('show')"))
    del WRITES[:]
    pg.click("#saveBtn"); pg.wait_for_timeout(500)
    wrote = [x for x in WRITES if "/flags" in x["u"]]
    saved = json.loads(wrote[0]["b"]) if wrote else {}
    ck("Save PUTs the whole list with the new flag active",
       len(wrote) == 1 and wrote[0]["m"] == "PUT"
       and saved.get("Honeymoon", {}).get("active") is True
       and "VIP" in saved and "Old badge" in saved)

    # An empty box adds nothing: a blank flag is a pill with nothing on it.
    before = pg.evaluate("()=>document.querySelectorAll('.mrow').length")
    pg.fill("#newName", "   ")
    pg.click("#addBtn"); pg.wait_for_timeout(200)
    ck("a blank name is not added",
       pg.evaluate("()=>document.querySelectorAll('.mrow').length") == before)

    # ── the automatic flag cannot be created by hand ────────────
    pg.fill("#newName", "luxury escapes")
    pg.click("#addBtn"); pg.wait_for_timeout(200)
    ck("creating Luxury Escapes by hand is refused with the reason",
       not pg.evaluate("()=>[...document.querySelectorAll('.mname')]"
                       ".some(e=>/luxury/i.test(e.textContent))")
       and "automatic" in pg.locator("#err").inner_text())
    pg.close()

    # ── the locked read, tag.html's lesson ──────────────────────
    STATE["fail"] = True
    pg = page()
    del WRITES[:]
    #  Forced, because the button is disabled - which is half the assertion.
    pg.evaluate("()=>saveBtn.click()"); pg.wait_for_timeout(400)
    ck("a refused read locks the page instead of reading as empty",
       not [x for x in WRITES if "/flags" in x["u"]]
       and pg.evaluate("()=>saveBtn.disabled"))
    pg.close()
    STATE["fail"] = False

    # ── the seed, only where there is truly nothing ─────────────
    STATE["master"] = None
    pg = page()
    ck("an empty node seeds the owner's three examples, unsaved",
       pg.evaluate("()=>[...document.querySelectorAll('.mname')].map(e=>e.textContent)")
       == ["Breakfast included", "Travel agent", "VIP"]
       and not [x for x in WRITES if "/flags" in x["u"] and x["m"] != "GET"])
    pg.close()
    STATE["master"] = MASTER

    # ── the gate ────────────────────────────────────────────────
    #  manageStaff opens it, so a manager is sent home rather than shown a
    #  list they cannot keep, and so is the chef.
    for who in ("manager@x", "chef@x"):
        pg = page(who)
        ck("%s is sent to their own board" % who.split("@")[0],
           not pg.url.endswith("flags.html"))
        pg.close()

    b.close()

print("RESULT: %d passed, %d failed" % (P, F))
httpd.shutdown()
