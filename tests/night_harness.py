"""The fixture night both page-dress suites render against.

tests/paper_night.json is one Saturday, 26 Sep 2026, with the clock held at
15:20 in Brisbane, so the boards draw every state they have. paper_suite and
colour_suite read it through here, so there is one fake database and one fake
sign-in, not a copy in each suite.
"""
import json
from urllib.parse import urlparse, parse_qs, unquote

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},
signOut:function(){}};"""

TREE = json.load(open("tests/paper_night.json"))["tree"]
CLOCK = "2026-09-26T15:20:00+10:00"


def resolve(url):
    """Read the fixture the way the database answers: the node at the path,
    and a ranged read ordered by key cut to its startAt..endAt."""
    u = urlparse(url)
    node = TREE
    for seg in [unquote(s) for s in u.path.replace(".json", "").split("/") if s]:
        node = node.get(seg) if isinstance(node, dict) else None
    q = parse_qs(u.query)
    if q.get("orderBy", [""])[0] == '"$key"' and isinstance(node, dict):
        lo = json.loads(q.get("startAt", ['""'])[0]); hi = json.loads(q.get("endAt", ['""'])[0])
        node = {k: v for k, v in node.items() if lo <= k <= hi} or None
    return json.dumps(node)


def fb(route, request):
    """Writes are answered with what was sent and change nothing: the night
    stays the night for every page that opens after."""
    if request.method != "GET":
        route.fulfill(status=200, content_type="application/json",
                      body=request.post_data or "null"); return
    route.fulfill(status=200, content_type="application/json", body=resolve(request.url))


def open_page(browser, port, name, width=390):
    """A page on the fixture night at a phone's width, settled."""
    ctx = browser.new_context(viewport={"width": width, "height": 844},
                              timezone_id="Australia/Brisbane")
    pg = ctx.new_page()
    pg.clock.set_fixed_time(CLOCK)
    pg.add_init_script(SDK)
    pg.route("**firebasedatabase.app/**", fb)
    pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    pg.goto("http://localhost:%d/%s" % (port, name))
    pg.wait_for_timeout(2000)
    return ctx, pg
