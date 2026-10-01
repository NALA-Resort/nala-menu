"""guest-contact.html and tasks.html, the guests' messages and the tasks they
become.

The owner, 29 Sep: a module to replace Guest Touch - every guest by booking,
Upcoming, In-house and Past, one conversation each on SMS or WhatsApp, every
reply caught here - and, the same day, "this chat service is predominantly a
task request... I would like that message to be able to be tagged or marked
as done or marked as no task required." GUEST-CONTACT.md is the brief. The
Worker is stubbed here and tested in worker/contact-test.mjs. Pinned down:

  1. The shared readers say what tests/contact_cases.json says, in the page,
     in two zones - the Worker's twins answer to the same table.
  2. Each guest's row is contactRowState's reading, in the colour law's
     tokens: new white, task open amber, sent grey, sunk, and all done
     white, not green (the owner, 30 Sep).
  3. Every guest message is sorted, No task or a task for a team, in ONE
     write that also takes it off the new list; a team's Done is its own.
  4. The box says which way a message goes before it goes, and past
     WhatsApp's 24 hours offers only the approved words, or SMS.
  5. What a guest writes is text, never markup.
  6. Tasks: a team's login sees its own teams' open tasks and closes them.

The clock is held at 3:20pm on Tuesday 29 Sep, Brisbane, and every check
that turns on the day runs in UTC too (CLAUDE.md, rule 7).
"""
import errortrap   # fails the run if any page throws
import threading, http.server, socketserver, json, time, os, re, sys
from urllib.parse import urlparse, parse_qs, unquote

os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
PORT = 8941
httpd = http.server.ThreadingHTTPServer(("", PORT), Q)
threading.Thread(target=httpd.serve_forever, daemon=True).start(); time.sleep(0.3)

SDK = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x',
getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:window.__EMAIL||'staff@x'});},25);},
signOut:function(){}};"""

TODAY = "2026-09-29"
ZONES = {"Australia/Brisbane": "2026-09-29T15:20:00+10:00",
         "UTC": "2026-09-29T05:20:00+00:00"}
SHOTS = os.environ.get("SHOTS")

STAFF = {"staff@x": {"name": "Admin", "role": "admin"},
         "ben@x": {"name": "Ben Davidson", "role": "waiter"},
         "waiter@x": {"name": "Anna Lee", "role": "waiter"},
         "chef@x": {"name": "Chef", "role": "chef"},
         "housekeeping@x": {"name": "HK", "role": "housekeeping"},
         "grounds@x": {"name": "Ray Grounds", "role": "housekeeping"},
         "masseuse@x": {"name": "Masseuse", "role": "spa"}}
# Opened to the staff, as they will be used; the preview's shut side is
# section 8, which empties this.
PERMS = {"open": {"guest-contact": True, "tasks": True}}
SETTINGS = {"teams": {"kitchen": {"members": {"chef@x": True}},
                      "maintenance": {"members": {"grounds@x": True}},
                      "housekeeping": {"members": {"housekeeping@x": True}},
                      "spa": {"members": {"masseuse@x": True}}}}

def night(d0, d1):
    out, y, m, d = [], 2026, int(d0[5:7]), int(d0[8:10])
    import datetime
    a = datetime.date.fromisoformat(d0); b = datetime.date.fromisoformat(d1)
    while a < b:
        out.append(a.isoformat()); a += datetime.timedelta(days=1)
    return out
GUESTS = [  # villa, booking, first, last, phone, arrive, depart
    ("7",  "b-sarah",  "Sarah",  "Whitfield",  "0412 345 678",      "2026-09-27", "2026-10-02"),
    ("12", "b-lea",    "Léa",    "Martin",     "+33 6 12 34 56 78", "2026-09-26", "2026-10-01"),
    ("4",  "b-lucy",   "Lucy",   "Whitfield",  "0411 000 004",      "2026-09-28", "2026-10-02"),
    ("9",  "b-priya",  "Priya",  "Sharma",     "+61 411 000 009",   "2026-09-27", "2026-10-03"),
    ("15", "b-owen",   "Owen",   "Reilly",     "0411 000 015",      "2026-09-25", "2026-09-30"),
    ("2",  "b-claire", "Claire", "Donnelly",   "0411 000 002",      "2026-09-27", "2026-10-02"),
    ("11", "b-sam",    "Sam",    "Okafor",     "0411 000 011",      "2026-09-28", "2026-10-03"),
    ("16", "b-jonah",  "Jonah",  "Adeyemi",    "0411 000 016",      "2026-09-29", "2026-10-04"),
    ("14", "b-hana",   "Hana",   "Sato",       "",                  "2026-09-28", "2026-09-30"),
    ("5",  "b-james",  "James",  "Harrington", "+61 438 220 761",   "2026-10-03", "2026-10-06"),
    ("3",  "b-robyn",  "Robyn",  "Carter",     "0411 000 003",      "2026-09-20", "2026-09-24"),
]
NIGHTS = {}
for v, b, f, l, ph, a, d in GUESTS:
    for n in night(a, d):
        NIGHTS.setdefault(n, {})[v] = {"id": b, "first": f, "last": l, "phone": ph,
                                       "arrive": a, "depart": d, "adults": 2}
SARAH, LEA, UNK, JAMES = "61412345678", "33612345678", "61423555019", "61438220761"
T = lambda hm, day=TODAY: day + "T" + hm + ":00+10:00"
THREADS = {
  SARAH: {"phone": "+61412345678", "lastAt": T("15:14"), "lastIn": T("15:14"), "lastInCh": "wa",
          "lastInWa": T("15:14"), "dir": "in",
          "preview": "Also, it's Tom's 40th tonight! Any chance of a candle on his dessert?",
          "wa": {"on": True, "by": "ben@x", "at": "2026-09-22T10:40:00+10:00"}},
  LEA: {"phone": "+33612345678", "lastAt": T("14:47"), "lastIn": T("14:47"), "lastInCh": "wa",
        "lastInWa": T("14:47"), "dir": "in", "preview": "Bonjour! Is the pool heated?"},
  UNK: {"phone": "+61423555019", "lastAt": T("13:05"), "lastIn": T("13:05"), "lastInCh": "sms",
        "dir": "in", "preview": "Hi, is there a table for 4 at dinner tonight?"},
  "61411000004": {"phone": "+61411000004", "lastAt": T("15:02"), "lastOut": T("15:02"), "dir": "out",
                  "preview": "Good afternoon Lucy."},
  "61411000009": {"phone": "+61411000009", "lastAt": T("15:05"), "lastIn": T("15:05"), "lastInCh": "wa",
                  "lastInWa": T("15:05"), "dir": "in", "preview": "Could we get two gin and tonics at the pool?"},
  "61411000015": {"phone": "+61411000015", "lastAt": T("11:20"), "lastOut": T("11:20"), "dir": "out",
                  "preview": "Your late checkout is confirmed for 1pm tomorrow."},
  "61411000002": {"phone": "+61411000002", "lastAt": T("10:00", "2026-09-28"),
                  "lastIn": T("10:00", "2026-09-28"), "lastInCh": "sms", "dir": "in",
                  "preview": "Perfect, thank you so much!"},
  "61411000011": {"phone": "+61411000011", "lastAt": T("09:00", "2026-09-27"),
                  "lastIn": T("08:50", "2026-09-27"), "lastInCh": "sms", "dir": "out",
                  "preview": "Of course, fresh towels are on their way."},
  JAMES: {"phone": "+61438220761", "lastAt": T("10:20", "2026-09-23"), "lastIn": T("09:52", "2026-09-23"),
          "lastInCh": "wa", "lastInWa": T("09:52", "2026-09-23"), "dir": "out",
          "preview": "Hi James, yes, there's room for two cars."},
  "61400000077": {"phone": "+61400000077", "lastAt": T("09:00"), "lastIn": T("09:00"), "lastInCh": "sms",
                  "dir": "in", "preview": "STOP", "optout": {"at": T("09:00"), "word": "STOP"}},
}
FRESH = {SARAH: {"in-SMcandle": True}, LEA: {"in-SMlea": True}, UNK: {"in-SMunk": True}}
TASKS = {
  "maintenance": {"t1umbrella": {"ck": SARAH, "msg": "in-SMumbrella", "villa": "7", "name": "Sarah Whitfield",
                                 "text": "The umbrella on our deck won't close. Could someone take a look?",
                                 "state": "open", "at": T("15:13"), "by": "ben@x"}},
  "kitchen": {"t5cake": {"ck": "61400000088", "msg": "in-SMcake", "villa": "10", "name": "Nina Brandt",
                         "text": "Could the kitchen do a gluten free birthday cake for tomorrow?",
                         "state": "open", "at": T("15:15"), "by": "ben@x"}},
  "bar": {"t2gandt": {"ck": "61411000009", "msg": "in-SMgin", "villa": "9", "name": "Priya Sharma",
                      "text": "Could we get two gin and tonics at the pool?", "state": "open",
                      "at": T("15:06"), "by": "ben@x"}},
  "spa": {"t0massage": {"ck": SARAH, "msg": "in-SMmassage", "villa": "7", "name": "Sarah Whitfield",
                        "text": "Could we book a couples massage for Sunday afternoon?", "state": "done",
                        "at": T("10:40", "2026-09-22"), "by": "ben@x", "doneAt": T("11:05", "2026-09-22"),
                        "doneBy": "ben@x", "doneDay": "2026-09-22"}},
  "housekeeping": {"t3towels": {"ck": "61411000011", "msg": "in-SMtowels", "villa": "11", "name": "Sam Okafor",
                                "text": "Could we get some fresh towels?", "state": "done", "at": T("08:52", "2026-09-27"),
                                "by": "ben@x", "doneAt": T("09:30", "2026-09-27"), "doneBy": "housekeeping@x",
                                "doneDay": TODAY},
                   "t4robe": {"ck": "61411000011", "msg": "in-SMrobe", "villa": "11", "name": "Sam Okafor",
                              "text": "And a second robe please", "state": "done", "at": T("09:00"),
                              "by": "ben@x", "doneAt": T("09:40"), "doneBy": "housekeeping@x",
                              "doneDay": TODAY}},
}
MSGS = {SARAH: {
  "in-SMmassage": {"dir": "in", "ch": "wa", "at": "2026-09-22T10:31:00+10:00",
                   "body": "Done! We arrive Saturday around 4pm. Could we book a couples massage for Sunday afternoon?",
                   "sorted": {"by": "ben@x", "at": "2026-09-22T10:40:00+10:00"},
                   "tasks": {"spa": "t0massage"}},
  "oreply1": {"dir": "out", "ch": "wa", "at": "2026-09-22T11:05:00+10:00", "by": "ben@x", "kind": "staff",
              "body": "Lovely, thank you Sarah. Sunday at 2pm is yours.", "status": "read"},
  "in-SMumbrella": {"dir": "in", "ch": "wa", "at": T("15:12"),
                    "body": "The umbrella on our deck won't close. Could someone take a look?",
                    "media": {"0": {"url": "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1",
                                    "type": "image/png"}},
                    "sorted": {"by": "ben@x", "at": T("15:13")}, "tasks": {"maintenance": "t1umbrella"}},
  "in-SMcandle": {"dir": "in", "ch": "wa", "at": T("15:14"),
                  "body": "Also, it's Tom's 40th tonight! Any chance of a candle on his dessert?"},
  "in-SMthanks": {"dir": "in", "ch": "wa", "at": "2026-09-22T11:07:00+10:00", "body": "Thank you!",
                  "sorted": {"by": "ben@x", "at": "2026-09-22T11:10:00+10:00"}},
}, UNK: {
  "in-SMunk": {"dir": "in", "ch": "sms", "at": T("13:05"),
               "body": "Hi, is there a table for 4? <img src=x onerror=\"window.__XSS=1\"> <b>bold</b>"},
}, JAMES: {
  "in-SMjames": {"dir": "in", "ch": "wa", "at": T("09:52", "2026-09-23"),
                 "body": "All done, thanks. Is there parking for two cars?",
                 "sorted": {"by": "ben@x", "at": T("10:00", "2026-09-23")}},
}}
# Priya, villa 9: the owner's own example (29 Sep) - drinks by the pool,
# then which ones, after the task was made - and the desk's note on it.
MSGS["61411000009"] = {
  "in-SMgin": {"dir": "in", "ch": "wa", "at": T("15:05"), "body": "Could we get two gin and tonics at the pool?",
               "sorted": {"by": "ben@x", "at": T("15:06")}, "tasks": {"bar": "t2gandt"}},
  "obar1": {"dir": "out", "ch": "wa", "at": T("15:07"), "by": "ben@x", "kind": "staff", "status": "read",
            "body": "Of course! Which gin, and where are you sitting?"},
  "in-SMgin2": {"dir": "in", "ch": "wa", "at": T("15:09"),
                "body": "Tanqueray with lime, on the loungers by the steps.",
                "sorted": {"by": "ben@x", "at": T("15:10")}}}
TASKS["bar"]["t2gandt"].update({"note": "Charge to villa 9", "noteBy": "ben@x", "noteAt": T("15:10")})

PREVINVITES = {"b-sarah": {"sentAt": "2026-09-22T10:02:00+10:00", "status": "sent", "to": "+61412345678",
                           "body": "Good morning. Ahead of your stay with us, a few questions. Nala Resort\nhttps://menu.nalaresort.com/prearrival.html?t=k7m2qx",
                           "by": "waiter@x", "delivery": "delivered",
                           # the first text, which the nudge above replaced (30 Sep)
                           "earlier": [{"sentAt": "2026-09-20T16:30:00+10:00", "status": "sent",
                                        "to": "+61412345678", "by": "ben@x", "delivery": "delivered",
                                        "body": "Good afternoon. Ahead of your stay with us, a few questions so everything is ready when you arrive. Nala Resort\nhttps://menu.nalaresort.com/prearrival.html?t=q9w3ze"}]}}
# Robyn, who has left, heard from us only by the pre-arrival form an SMS page
# sent: Chat's list takes it for her last message (30 Sep).
PREVINVITES["b-robyn"] = {"sentAt": "2026-09-15T15:10:00+10:00", "status": "sent", "to": "+61411000003",
                          "by": "ben@x", "delivery": "delivered",
                          "body": "Good afternoon. Ahead of your stay with us, a few questions so everything is ready when you arrive. Nala Resort\nhttps://menu.nalaresort.com/prearrival.html?t=r0b1n5"}
# the dinner invitations, as invitations.html's Worker records them, and an
# outside guest's, for the number on no booking
INVITES = {"2026-09-28": {"7": {"sentAt": "2026-09-28T16:02:00+10:00", "status": "sent", "to": "+61412345678",
                                "by": "ben@x", "delivery": "delivered",
                                "body": "Tonight\u2019s menu is ready. Nala Resort\nhttps://menu.nalaresort.com/?t=ab3xyz"}}}
EXTINVITES = {"2026-09-28": {"ext-k2m9": {"sentAt": "2026-09-28T16:20:00+10:00", "status": "sent",
                                          "to": "+61423555019", "by": "ben@x",
                                          "body": "Good afternoon. Tonight\u2019s menu, and a place to tell us if you will join us. Nala Resort\nhttps://menu.nalaresort.com/?t=k2m9pp"}}}

# The Templates page's three sets (templates.html's built-ins), tonight's
# menu, and a massage tomorrow for Priya: what Chat's Templates offers
# (30 Sep).
TMPL = {"/presmstemplates.json": {
          "before": {"label": "Before you arrive", "order": 1, "body": "Good afternoon. Ahead of your stay with us, a few questions so everything is ready when you arrive. Nala Resort\n<form>"},
          "nudge": {"label": "A gentle reminder", "order": 2, "body": "A reminder, when you have a moment: a few questions ahead of your stay, so everything is ready when you arrive. Nala Resort\n<form>"}},
        "/smstemplates.json": {
          "join": {"label": "Will you join us", "order": 2, "body": "Good afternoon. Tonight\u2019s menu, and a place to tell us if you will join us. Nala Resort\n<menu>"},
          "ready": {"label": "Menu is ready", "order": 1, "body": "Tonight\u2019s menu is ready. Nala Resort\n<menu>"}},
        "/spasmstemplates.json": {
          "remind": {"label": "Gentle reminder", "order": 1, "body": "Hello <first>, a gentle reminder of your booking with us:\n\n<booking>\n\nIf you need to change anything, just reply to this message. Nala Resort"}}}
SPA = {"b-priya": {"t7": {"status": "booked", "day": "2026-09-30", "time": "10:30", "qty": 1, "dur": 60},
                   "t6": {"status": "booked", "day": "2026-09-29", "time": "09:00", "qty": 1, "dur": 60}}}
MENU = {"published": "2026-09-29T13:05:00+10:00", "bread": {"name": "Sourdough"}, "entree": {"name": "Crudo"},
        "main": {"name": "Lamb shoulder"}, "dessert": {"name": "Lemon tart"}}

STATE = {"hello": {"ready": True, "wa": True, "test": False, "buzz": False}, "send": None,
         "readfail": False, "menu": MENU, "inv": None}
WRITES, SENT, BUZZ, READS, INV = [], [], [], [], []
# a 1x1 photo in the mock's neutral grey: a red stand-in read as a fault
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c633879783b00049c02442e077d7e0000000049454e44ae426082")

def js(v): return json.dumps(v)
def fb(route, request):
    u, m = request.url, request.method
    path = unquote(u.split("firebasedatabase.app")[1].split("?")[0])
    q = parse_qs(urlparse(u).query)
    if m in ("PUT", "PATCH", "DELETE", "POST"):
        WRITES.append({"m": m, "p": path, "b": json.loads(request.post_data or "null")})
        route.fulfill(status=200, content_type="application/json", body=request.post_data or "null"); return
    if STATE["readfail"] and path.startswith("/contact"):
        route.fulfill(status=500, content_type="application/json", body='{"error":"x"}'); return
    READS.append((path, q))
    body = None
    if path == "/staff.json": body = STAFF
    elif path == "/stays.json":
        lo, hi = json.loads(q["startAt"][0]), json.loads(q["endAt"][0])
        body = {d: v for d, v in NIGHTS.items() if lo <= d <= hi} or None
    elif path == "/phonefix.json": body = None
    elif path == "/contact.json":
        # the list's one query: the threads that moved since a stamp
        lo = json.loads(q["startAt"][0]) if q.get("orderBy") == ['"lastAt"'] else ""
        body = {k: v for k, v in THREADS.items() if (v.get("lastAt") or "") >= lo} or None
    elif path == "/contactnew.json":
        body = {k: True for k in FRESH} if "shallow" in q else FRESH
    elif path == "/contactsettings.json": body = SETTINGS
    elif path == "/permissions.json": body = PERMS or None
    elif path.startswith("/contact/"): body = THREADS.get(path[9:-5])
    elif path.startswith("/contactnew/"): body = FRESH.get(path[12:-5])
    elif path.startswith("/contactmsgs/"): body = MSGS.get(path[13:-5])
    elif path.startswith("/tasks/"):
        parts = path[7:-5].split("/")
        team = TASKS.get(parts[0], {})
        if len(parts) == 2: body = team.get(parts[1])
        else:
            key = json.loads(q["orderBy"][0]) if "orderBy" in q else None
            want = json.loads(q["equalTo"][0]) if "equalTo" in q else None
            body = {k: v for k, v in team.items() if key is None or v.get(key) == want} or None
    elif path == "/previnvites.json": body = PREVINVITES
    elif path == "/spareminders.json": body = None
    elif path == "/invites.json":
        lo, hi = json.loads(q["startAt"][0]), json.loads(q["endAt"][0])
        body = {d: v for d, v in INVITES.items() if lo <= d <= hi} or None
    elif path.startswith("/previnvites/"): body = PREVINVITES.get(path[13:-5])
    elif path.startswith("/invites/"): body = INVITES.get(path[9:-5])
    elif path.startswith("/extinvites/"): body = EXTINVITES.get(path[12:-5])
    elif path in TMPL: body = TMPL[path]
    elif path.startswith("/spa/"): body = SPA.get(path[5:-5])
    elif path == "/menu.json": body = STATE["menu"]
    route.fulfill(status=200, content_type="application/json", body=js(body))

# The SMS pages' sender, worker/send-invites.js, stood in for Chat's
# Templates: what it was asked, and its answer.
def inv(route, request):
    b = json.loads(request.post_data)
    INV.append(b)
    if STATE["inv"]:
        st, rep = STATE["inv"]
    else:
        key = (b["bookings"][0] if b.get("kind") == "pre" else
               b["treatments"][0]["b"] + "/" + b["treatments"][0]["t"] if b.get("kind") == "spa" else
               b["villas"][0])
        st, rep = 200, {"results": {key: {"status": "sent"}}}
    route.fulfill(status=st, content_type="application/json", body=js(rep))

def wk(route, request):
    b = json.loads(request.post_data)
    SENT.append(b)
    # old: the Worker in Cloudflare from before a door this page knows
    if STATE.get("old") and b.get("kind") in ("delete", "check"):
        route.fulfill(status=400, content_type="application/json", body=js({"error": "unknown kind"})); return
    if b.get("kind") == "delete":
        route.fulfill(status=200, content_type="application/json", body=js({"deleted": b.get("m")})); return
    if b.get("kind") == "check":
        route.fulfill(status=200, content_type="application/json", body=js({"check": STATE.get("check") or [
            {"key": "twilio", "ok": True, "say": "Twilio accepts the Account SID and the Auth Token."},
            {"key": "test", "ok": None, "say": "Test mode is off: Chat can message any guest."}]})); return
    if b.get("kind") == "hello":
        route.fulfill(status=200, content_type="application/json", body=js(STATE["hello"])); return
    if b.get("kind") in ("media", "taskmedia"):
        route.fulfill(status=200, content_type="image/png", body=PNG); return
    if b.get("kind") == "tasklog":
        # the Worker's reading, played here: the request and all after it,
        # until Done. worker/contact-test.mjs holds the real one to it.
        import datetime
        ms = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp()
        logs, routes = {}, {}
        for it in b.get("tasks", []):
            task = TASKS.get(it["team"], {}).get(it["t"])
            if not task: continue
            msgs = MSGS.get(task["ck"], {})
            frm = ms(msgs[task["msg"]]["at"]) if task["msg"] in msgs else ms(task["at"])
            until = ms(task["doneAt"]) if task.get("state") == "done" and task.get("doneAt") else float("inf")
            theirs = lambda m: m["dir"] == "in" and m.get("tasks") and it["team"] not in m["tasks"]
            ids = sorted([k for k, m in msgs.items() if frm <= ms(m["at"]) <= until and not theirs(m)],
                         key=lambda k: ms(msgs[k]["at"]))
            logs[it["team"] + "/" + it["t"]] = [{"id": k, "dir": msgs[k]["dir"], "ch": msgs[k]["ch"],
                "body": msgs[k].get("body", ""), "at": msgs[k]["at"],
                "by": msgs[k].get("by", "") if msgs[k]["dir"] == "out" else "",
                "photos": len(msgs[k].get("media", {}))} for k in ids]
            # which way a reply would go, for every open card: the page
            # alone decides whether its role may send one (section 9)
            if task.get("state") == "open":
                routes[it["team"] + "/" + it["t"]] = STATE.get("route") or {"ch": "wa", "until": None}
        route.fulfill(status=200, content_type="application/json",
                      body=js({"logs": logs, "routes": routes})); return
    st, rep = STATE["send"] or (200, {"id": "onew", "ch": "wa", "status": "queued"})
    route.fulfill(status=st, content_type="application/json", body=js(rep))

def push(route, request):
    BUZZ.append(json.loads(request.post_data or "{}"))
    route.fulfill(status=200, content_type="application/json", body="{}")

P = F = 0
def ck(name, cond, detail=""):
    global P, F
    print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)) if not cond and detail != "" else ""))
    P, F = (P + 1, F) if cond else (P, F + 1)
def shown(style):
    mm = re.search(r"linear-gradient\((rgba?\([^)]*\))", style.get("backgroundImage") or "")
    return mm.group(1) if mm else style["backgroundColor"]

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    br = p.chromium.launch()

    def page(q="", email="ben@x", w=390, tz="Australia/Brisbane", file="guest-contact.html"):
        ctx = br.new_context(viewport={"width": w, "height": 900}, timezone_id=tz)
        pg = ctx.new_page()
        pg.clock.set_fixed_time(ZONES[tz])
        pg.add_init_script(SDK)
        pg.add_init_script("window.__EMAIL=%s;" % json.dumps(email))
        pg.route("**firebasedatabase.app/**", fb)
        pg.route("**nala-contact.ben-681.workers.dev/**", wk)
        pg.route("**nala-push.ben-681.workers.dev/**", push)
        pg.route("**nala-invites.ben-681.workers.dev/**", inv)
        pg.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
        pg.goto("http://localhost:%d/%s%s" % (PORT, file, q))
        pg.wait_for_timeout(1300)
        pg.ctx = ctx
        return pg
    def done(pg): pg.ctx.close()
    def rows(pg):
        return pg.evaluate("""()=>[...document.querySelectorAll('#board .vrow')].map(e=>({
          ck:e.dataset.ck, b:e.dataset.b, s:e.dataset.state, v:e.querySelector('.v').textContent,
          nm:e.querySelector('.nm').textContent, l3:(e.querySelector('.l3 .meta')||e.querySelector('.l3')).textContent,
          num:(e.querySelector('.l3 .num')||{}).textContent||'', pen:!!e.querySelector('.l3 .pen'),
          pv:e.querySelector('.pv').textContent, dis:e.tagName!=='BUTTON'||e.disabled,
          order:[...e.querySelector('.mid').children].map(x=>x.className.split(' ')[0])}))""")
    def shot(pg, name):
        if SHOTS: pg.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=True)

    # ── 1. the shared readers, in the page, in both zones ─────────────
    CASES = json.load(open("tests/contact_cases.json"))
    for tz in ZONES:
        pg = page(tz=tz)
        res = pg.evaluate("""(T)=>{
          const win = T.window.cases.every(([l,n,o,u])=>{const w=waWindow(l,Date.parse(n));
            return w.open===o && (u===null ? w.until===null : w.until===Date.parse(u));});
          const ch = T.channel.cases.every(([t,n,c])=>contactChannel(t,Date.parse(n)).ch===c);
          const row = T.row.cases.every(([t,f,o,h,s])=>contactRowState(t,f,o,h)===s);
          const tpl = T.templates.cases.every(([i,f,a,w])=>contactTemplateText(i,f,a)===w);
          const teams = T.teams.cases.every(([s,a,w])=>JSON.stringify(contactTeams(s,a)
            .map(t=>[t.key,t.label,t.off]))===JSON.stringify(w));
          const tof = T.teamsof.cases.every(([s,e,w])=>JSON.stringify(teamsOf(s,e))===JSON.stringify(w));
          return {win, ch, row, tpl, teams, tof};}""", CASES)
        ck("[%s] the page's readers say what contact_cases.json says: %s" % (tz, res),
           all(res.values()), res)
        done(pg)

    # ── 2. the list ────────────────────────────────────────────────────
    for tz in ZONES:
        pg = page(tz=tz)
        rs = rows(pg)
        grps = pg.evaluate("()=>[...document.querySelectorAll('#board .grp')].map(e=>e.textContent)")
        ck("[%s] In-house opens, work first: new, task open, sent, all done, nothing" % tz,
           grps == ["New · 3", "Task open · 1", "Sent, no reply · 2", "All done · 3", "No messages · 2"], grps)
        by = {r["ck"] or r["b"]: r for r in rs}
        ck("[%s] every row wears contactRowState's reading" % tz,
           by[SARAH]["s"] == "fresh" and by[LEA]["s"] == "fresh" and by[UNK]["s"] == "fresh" and
           by["61411000009"]["s"] == "task" and by["61411000004"]["s"] == "sent" and
           by["61411000015"]["s"] == "sent" and by["61411000002"]["s"] == "done" and
           by["61411000011"]["s"] == "done" and by["61411000016"]["s"] == "none" and
           by["b-hana"]["s"] == "nophone", {k: v["s"] for k, v in by.items()})
        ck("[%s] and the page decides nothing itself" % tz, pg.evaluate("""()=>rowsOf().filter(r=>r.tab==='in')
            .every(r=>r.state===contactRowState(r.t, r.ck?freshOf(r.ck):0, r.ck?tasksOf(r.ck).length:0, !!r.ck))"""))
        done(pg)

    pg = page()
    rs = rows(pg); by = {r["ck"] or r["b"]: r for r in rs}
    ck("a guest's row: villa, name, the time they last wrote, their words, the count",
       by[SARAH]["v"] == "7" and by[SARAH]["nm"] == "Sarah Whitfield" and
       by[SARAH]["pv"].startswith("Also, it's Tom's 40th") and
       pg.evaluate("()=>document.querySelector('.vrow[data-ck=\"%s\"] .cnt').textContent" % SARAH) == "1", by[SARAH])
    ck("and how they write, when they leave, and a task still open",
       by[SARAH]["l3"] == "WhatsApp · leaves Fri 2 Oct · Maintenance open", by[SARAH]["l3"])
    ck("a number on no booking lands on In-house, its number for a name",
       by[UNK]["v"] == "?" and by[UNK]["nm"] == "0423 555 019" and "not on any booking" in by[UNK]["l3"], by[UNK])
    ck("what we said last reads as ours", by["61411000004"]["pv"] == "You: Good afternoon Lucy.")
    ck("a guest with no mobile cannot be opened", by["b-hana"]["dis"] and
       by["b-hana"]["pv"] == "No mobile number on the booking")
    ck("a guest nothing was sent to can be, to start the conversation", not by["b-jonah" if "b-jonah" in by else "61411000016"]["dis"])
    ck("the tab counts the guests with something new",
       pg.evaluate("()=>['cUp','cIn','cPast'].map(i=>document.getElementById(i).textContent)") == ["", "3", ""])
    sty = lambda k: pg.evaluate("""(k)=>{const e=document.querySelector('.vrow[data-ck="'+k+'"]')||
        document.querySelector('.vrow[data-b="'+k+'"]');const s=getComputedStyle(e);
        return {backgroundColor:s.backgroundColor,backgroundImage:s.backgroundImage,
        borderStyle:s.borderTopStyle,opacity:s.opacity};}""", k)
    ck("new is work to do: plain white", shown(sty(SARAH)) == "rgb(255, 255, 255)", sty(SARAH))
    ck("a task open is the law's amber", shown(sty("61411000009")) == "rgb(246, 234, 213)", sty("61411000009"))
    # .045 is drawn as .043: Chrome keeps alpha in 256 steps. inv_suite's reading.
    ck("only we have written is the law's waiting grey",
       shown(sty("61411000004")).startswith("rgba(28, 28, 26, 0.04"), sty("61411000004"))
    # The owner, 30 Sep: "Otherwise, all the cards would be green."
    ck("all done is plain white, not the done green", shown(sty("61411000002")) == "rgb(255, 255, 255)",
       sty("61411000002"))
    ck("and nothing on the list is green", pg.evaluate("""()=>![...document.querySelectorAll('#board .vrow')].some(e=>{
        const s=getComputedStyle(e);return /122, 160, 130|126, 147, 122|228, 237, 226/.test(
        s.backgroundColor+s.backgroundImage+s.borderTopColor);})"""))
    ck("nothing sent and no number are sunk and dashed",
       all(sty(k)["borderStyle"] == "dashed" and float(sty(k)["opacity"]) < 0.7 for k in ("61411000016", "b-hana")))
    # The owner, 30 Sep: "the phone number, its validity" as on the SMS pages.
    ck("each guest's number as the SMS pages show it: the number, its tick, the pencil",
       by[SARAH]["num"] == "0412 345 678\u2713" and by[SARAH]["pen"] and
       by[LEA]["num"] == "+33 6 12 34 56 78\u2713" and by[LEA]["pen"], [by[SARAH], by[LEA]])
    geo = pg.evaluate("""(k)=>{const r=document.querySelector('.vrow[data-ck="'+k+'"]'),
        pe=r.querySelector('.pen'); if(!pe) return {penAt:0, midIsPen:false};
        const p=pe.getBoundingClientRect(), b=r.getBoundingClientRect(),
        mid=document.elementFromPoint(b.left+b.width/2, b.top+b.height/2);
        return {penAt:(p.left-b.left)/b.width, midIsPen:!!(mid&&mid.closest('.pen'))}}""", SARAH)
    ck("the pencil sits at the line's right-hand end, clear of the middle where a tap opens the conversation",
       geo["penAt"] > 0.8 and not geo["midIsPen"], geo)
    ck("a number on no booking, already its name, wears the tick alone and no pencil",
       by[UNK]["num"] == "\u2713" and not by[UNK]["pen"], by[UNK])
    ck("the details first, the last message at the bottom (the owner, 30 Sep)",
       by[SARAH]["order"] == ["l1", "l3", "l2"], by[SARAH]["order"])
    ck("a booking with no mobile says so, with the pencil to add one",
       by["b-hana"]["num"] == "no number" and by["b-hana"]["pen"], by["b-hana"])
    del WRITES[:]
    if pg.query_selector('.vrow[data-b="b-hana"] .pen'):
        pg.once("dialog", lambda d: d.accept("0411 999 888"))
        pg.click('.vrow[data-b="b-hana"] .pen'); pg.wait_for_timeout(500)
    fix = [w for w in WRITES if w["p"] == "/phonefix/b-hana.json"]
    ck("the pencil saves the corrected number at /phonefix, as the SMS pages' does, and opens nothing",
       fix and fix[0]["m"] == "PUT" and fix[0]["b"]["phone"] == "+61411999888" and
       "c=" not in pg.evaluate("()=>location.search"), fix)
    pg.click('.vrow[data-b="b-hana"] .nm'); pg.wait_for_timeout(200)
    ck("and a row with no number still cannot be opened", "c=" not in pg.evaluate("()=>location.search"))
    ck("and no status here is red", pg.evaluate("""()=>![...document.querySelectorAll('#board *')].some(e=>
        getComputedStyle(e).color==='rgb(168, 50, 30)')"""))
    shot(pg, "gc-list")

    pg.click("#tabUp"); pg.wait_for_timeout(150)
    rs = rows(pg)
    ck("Upcoming: the guests arriving, with their nights",
       [r["nm"] for r in rs] == ["James Harrington"] and rs[0]["l3"] == "WhatsApp · arrives Sat 3 Oct · 3 nights", rs)
    ck("and the address remembers the tab", pg.evaluate("()=>location.search") == "?t=up")
    pg.click("#tabPast"); pg.wait_for_timeout(150)
    rs = rows(pg)
    ck("Past: the guests who have left", [r["nm"] for r in rs] == ["Robyn Carter"] and
       rs[0]["l3"] == "SMS · left Thu 24 Sep", rs)
    ck("and a guest Chat never wrote to shows the last text an SMS page sent them: sent, by the page's name",
       rs[0]["s"] == "sent" and rs[0]["pv"].startswith("Pre-arrival form: Good afternoon.") and
       not rs[0]["pv"].startswith("You:"), rs[0])
    pg.fill("#find", "whit"); pg.wait_for_timeout(150)
    rs = rows(pg)
    ck("a search reaches every tab: both Whitfields, wherever their dates are",
       sorted(r["nm"] for r in rs) == ["Lucy Whitfield", "Sarah Whitfield"] and
       all(r["l3"].startswith("In-house") for r in rs), rs)
    pg.fill("#find", "5"); pg.wait_for_timeout(150)
    rs = rows(pg)
    ck("a villa number finds the villa", [r["nm"] for r in rs] == ["James Harrington"] and
       rs[0]["l3"].startswith("Upcoming"), rs)
    pg.fill("#find", "0438 220"); pg.wait_for_timeout(150)
    ck("and so does part of a number", [r["nm"] for r in rows(pg)] == ["James Harrington"])
    pg.fill("#find", ""); pg.click("#tabIn"); pg.wait_for_timeout(150)
    pg.click('.vrow[data-ck="%s"]' % SARAH); pg.wait_for_timeout(300)
    ck("a row opens that guest's conversation", "c=%s&b=b-sarah&t=in" % SARAH in pg.url, pg.url)
    done(pg)

    # Each read at its own pace: a poll reads the messages, and the bookings
    # (two months of nights) only when the Mews sync may have moved them.
    for q, name in (("", "the list's poll reads the threads that moved"),
                    ("?c=%s&b=b-sarah" % SARAH, "a conversation's poll reads its own messages")):
        pg = page(q)
        n = len(READS)
        pg.evaluate("()=>refresh()"); pg.wait_for_timeout(500)
        got = [p for p, _ in READS[n:]]
        want = ("/contact.json" if not q else "/contactmsgs/%s.json" % SARAH)
        ck(name + ", not the nights again", want in got and "/stays.json" not in got and
           "/phonefix.json" not in got and (not q or "/contact.json" not in got), got)
        done(pg)
    ck("and the list asks the database for the recent threads only, by lastAt",
       any(p == "/contact.json" and qq.get("orderBy") == ['"lastAt"'] and qq.get("startAt")
           for p, qq in READS), [qq for p, qq in READS if p == "/contact.json"][:1])

    # ── 3. one conversation ────────────────────────────────────────────
    pg = page("?c=%s&b=b-sarah" % SARAH)
    ck("the conversation is titled with the guest, and says where they are",
       pg.text_content("#title") == "Sarah Whitfield" and
       "Villa 7 · leaves Fri 2 Oct · 2 guests" in pg.text_content("#ctx") and
       "0412 345 678" in pg.text_content("#ctx"))
    ck("the list is not shown, the back button is", not pg.is_visible("#listView") and pg.is_visible("#backBtn"))
    ck("the WhatsApp switch is on, and says who recorded the guest asking and when",
       pg.get_attribute("#waSw", "aria-checked") == "true" and
       pg.text_content("#waWords").startswith("WhatsApp: asked for, Ben Tue"), pg.text_content("#waWords"))
    order = pg.evaluate("()=>[...document.querySelectorAll('#msgs .msg')].map(e=>e.dataset.m)")
    ck("every message both ways in time order, the pre-arrival texts and the dinner invitation among them",
       order == ["page1", "page0", "in-SMmassage", "oreply1", "in-SMthanks", "page2", "in-SMumbrella",
                 "in-SMcandle"], order)
    days = pg.evaluate("()=>[...document.querySelectorAll('#msgs .day')].map(e=>e.textContent)")
    ck("the time over each stretch of talk, as the iPhone puts it",
       days == ["Sun 20 Sep 4:30pm", "Tue 22 Sep 10:02am", "Yesterday 4:02pm", "Today 3:12pm"], days)
    meta = lambda m: pg.evaluate("(m)=>{const e=document.querySelector('.msg[data-m=\"'+m+'\"] .meta');return e?e.textContent:''}", m)
    ck("each page's text says what it was, who sent it and how it went",
       meta("page0") == "Pre-arrival form · Anna · SMS · Delivered" and
       meta("page1") == "Pre-arrival form · Ben · SMS · Delivered" and
       meta("page2") == "Dinner invitation · Ben · SMS · Delivered", [meta("page0"), meta("page1"), meta("page2")])
    bub = lambda m: pg.evaluate("(m)=>{const c=getComputedStyle(document.querySelector('.msg[data-m=\"'+m+'\"] .bub'));"
                                "return [c.backgroundColor,c.color,c.backgroundImage.indexOf('gradient')>-1]}", m)
    ck("the guest's words on the iPhone's grey, ours on its blue in white",
       bub("in-SMmassage") == ["rgb(233, 233, 235)", "rgb(0, 0, 0)", False] and
       bub("oreply1") == ["rgb(10, 132, 255)", "rgb(255, 255, 255)", True], [bub("in-SMmassage"), bub("oreply1")])
    ck("with the iPhone's tail on each run's last bubble",
       pg.evaluate("()=>getComputedStyle(document.querySelector('.msg[data-m=\"oreply1\"] .bub'),'::before').backgroundColor")
       == "rgb(10, 132, 255)" and "end" in pg.get_attribute('.msg[data-m="in-SMcandle"]', "class"))
    tri = lambda m: pg.evaluate("(m)=>{const t=document.querySelector('.msg[data-m=\"'+m+'\"] .tri');return t?t.innerText.replace(/\\s+/g,' ').trim():''}", m)
    ck("a new message waits to be sorted: No task, or Task", tri("in-SMcandle") == "No task Task", tri("in-SMcandle"))
    ck("a task still open says whose it is, beside its Done", tri("in-SMumbrella").startswith("Maintenance · open Done"),
       tri("in-SMumbrella"))
    ck("a task done says who did it", tri("in-SMmassage").startswith("Spa · done by Ben"), tri("in-SMmassage"))
    ck("a message that needed nothing says so", tri("in-SMthanks").startswith("No task · Ben"), tri("in-SMthanks"))
    pill = lambda sel: pg.evaluate("(s)=>{const e=document.querySelector(s);const c=getComputedStyle(e);return [c.backgroundColor,c.color]}", sel)
    ck("Task and No task are bordered as buttons are, square to the round pills (the owner, 30 Sep)",
       pg.evaluate("""()=>{const c=getComputedStyle(document.querySelector('#tk-in-SMcandle'));
         return c.borderTopWidth==='1px' && c.borderTopStyle==='solid' && c.borderTopColor!=='rgba(0, 0, 0, 0)' &&
                parseFloat(c.borderTopLeftRadius) < 14}"""))
    ck("open is the law's amber, done the law's green pill",
       pill('.msg[data-m="in-SMumbrella"] .tp.open') == ["rgb(246, 234, 213)", "rgb(138, 106, 47)"] and
       pill('.msg[data-m="in-SMmassage"] .tp.done') == ["rgb(228, 237, 226)", "rgb(94, 125, 103)"])
    pg.wait_for_timeout(300)
    ck("the guest's photo comes through the Worker",
       pg.evaluate("()=>document.querySelector('.msg[data-m=\"in-SMumbrella\"] img.photo').src.startsWith('blob:')") and
       any(s.get("kind") == "media" and s.get("m") == "in-SMumbrella" for s in SENT))
    ck("inside the 24 hours, the box says WhatsApp and until when",
       pg.text_content("#win") == "Sends on WhatsApp · free text until 3:14pm tomorrow", pg.text_content("#win"))
    shot(pg, "gc-thread")

    del WRITES[:]
    pg.click("#nt-in-SMcandle"); pg.wait_for_timeout(500)
    w = WRITES[-1] if WRITES else {}
    ck("No task is one write: the message sorted, and off the new list",
       w.get("m") == "PATCH" and w.get("p") == "/.json" and
       w["b"].get("contactmsgs/%s/in-SMcandle/sorted" % SARAH, {}).get("by") == "ben@x" and
       "contactnew/%s/in-SMcandle" % SARAH in w["b"] and w["b"]["contactnew/%s/in-SMcandle" % SARAH] is None, w)
    done(pg)

    pg = page("?c=%s&b=b-sarah" % SARAH)
    del WRITES[:]; del BUZZ[:]
    pg.click("#tk-in-SMcandle"); pg.wait_for_timeout(150)
    teams = pg.evaluate("()=>[...document.querySelectorAll('.msg[data-m=\"in-SMcandle\"] .tri .sbtn')].map(e=>e.textContent)")
    ck("Task offers the teams, and a way back", teams == ["Bar", "Kitchen", "Housekeeping", "Maintenance",
                                                          "Spa", "Front desk", "Cancel"], teams)
    shot(pg, "gc-pick")
    pg.fill("#tn-in-SMcandle", "Candle on the dessert, table by the window")
    pg.click("#tm-in-SMcandle-kitchen"); pg.wait_for_timeout(500)
    w = WRITES[-1] if WRITES else {"b": {}}
    tk = [k for k in w["b"] if k.startswith("tasks/kitchen/")]
    rec = w["b"][tk[0]] if tk else {}
    ck("a team makes the task, the message's link to it, and sorts it, in one write",
       len(tk) == 1 and rec.get("state") == "open" and rec.get("ck") == SARAH and rec.get("msg") == "in-SMcandle" and
       rec.get("villa") == "7" and rec.get("name") == "Sarah Whitfield" and rec.get("by") == "ben@x" and
       rec.get("text", "").startswith("Also, it's Tom's") and
       w["b"].get("contactmsgs/%s/in-SMcandle/tasks/kitchen" % SARAH) == tk[0].split("/")[2] and
       "contactmsgs/%s/in-SMcandle/sorted" % SARAH in w["b"] and
       w["b"].get("contactnew/%s/in-SMcandle" % SARAH, "x") is None, w)
    ck("with the desk's note for the team, in the desk's name",
       rec.get("note") == "Candle on the dessert, table by the window" and rec.get("noteBy") == "ben@x" and
       bool(rec.get("noteAt")), rec)
    ck("and no buzz goes out until BUZZ is set on the Chat Worker", BUZZ == [])
    del WRITES[:]
    pg.click("#nb-in-SMumbrella-maintenance"); pg.wait_for_timeout(150)
    pg.fill("#te-in-SMumbrella-maintenance", "Bring the long ladder")
    pg.click("#ns-in-SMumbrella-maintenance"); pg.wait_for_timeout(500)
    w = WRITES[-1] if WRITES else {"b": {}}
    ck("an open task's note is written afterwards, in one write, in the desk's name",
       w["b"].get("tasks/maintenance/t1umbrella/note") == "Bring the long ladder" and
       w["b"].get("tasks/maintenance/t1umbrella/noteBy") == "ben@x", w)
    done(pg)

    STATE["hello"]["buzz"] = True
    pg = page("?c=%s&b=b-sarah" % SARAH)
    del BUZZ[:]
    pg.click("#tk-in-SMcandle"); pg.wait_for_timeout(150); pg.click("#tm-in-SMcandle-bar")
    # the buzz follows the write and the button's 300ms Saved hold: waited
    # for, not guessed at, which a fixed 500ms was under a loaded machine
    for _ in range(30):
        if BUZZ: break
        pg.wait_for_timeout(100)
    ck("once it does, the team's phones are buzzed, the team named, as staff read its name",
       len(BUZZ) == 1 and BUZZ[0].get("event") == "guestTask" and BUZZ[0].get("team") == "bar" and
       BUZZ[0].get("label") == "Bar" and BUZZ[0].get("villa") == "7", BUZZ)
    STATE["hello"]["buzz"] = False
    del WRITES[:]
    pg.click("#dn-in-SMumbrella-maintenance"); pg.wait_for_timeout(500)
    w = WRITES[-1] if WRITES else {"b": {}}
    ck("Done closes the task in the desk's name, today",
       w["b"].get("tasks/maintenance/t1umbrella/state") == "done" and
       w["b"].get("tasks/maintenance/t1umbrella/doneBy") == "ben@x" and
       w["b"].get("tasks/maintenance/t1umbrella/doneDay") == TODAY, w)
    done(pg)

    pg = page("?c=%s&b=b-sarah" % SARAH)
    pg.click("#tk-in-SMumbrella"); pg.wait_for_timeout(150)
    teams = pg.evaluate("()=>[...document.querySelectorAll('.msg[data-m=\"in-SMumbrella\"] .tri .sbtn')].map(e=>e.textContent)")
    ck("a team the message already has a task with is not offered again", "Maintenance" not in teams and "Bar" in teams, teams)
    pg.click("#cx-in-SMumbrella"); pg.wait_for_timeout(150)
    ck("and Cancel puts the message back as it was", tri("in-SMumbrella").startswith("Maintenance · open Done"))
    # ── the box and Send, the phone's (the owner, 1 Oct) ──────────────
    # "sticky above the footer menu", a box that grows "so the whole
    # message can be seen", and Send "on side of text Box"
    GEO = """()=>{const r=q=>document.querySelector(q).getBoundingClientRect();
      const c=r('#compose'), t=document.getElementById('tabBar'), x=r('#msgBox'), s=r('#sendBtn');
      const box=document.getElementById('msgBox'), el=document.scrollingElement;
      const m=[...document.querySelectorAll('#msgs .msg')].pop();
      return {ct:c.top, cb:c.bottom, bar:t?t.getBoundingClientRect().top:null,
              strip:t?getComputedStyle(t).backgroundImage:null,
              x:[x.left,x.top,x.right,x.bottom], h:x.height, s:[s.left,s.top,s.right,s.bottom],
              dis:document.getElementById('sendBtn').disabled, sh:box.scrollHeight, ch:box.clientHeight,
              oy:getComputedStyle(box).overflowY, last:m?m.getBoundingClientRect().bottom:null,
              top:el.scrollTop, end:el.scrollTop+innerHeight>=el.scrollHeight-1,
              long:el.scrollHeight>innerHeight*1.5, half:innerHeight/2}}"""
    g = pg.evaluate(GEO)
    ck("the box and Send stand on the tab bar, the newest message above them",
       g["bar"] is not None and abs(g["cb"] - g["bar"]) <= 1 and g["end"] and g["last"] <= g["ct"] + 1, g)
    ck("and the strip under the bar is solid there, as under any page's footer", g["strip"] == "none", g)
    ck("the box starts one line tall, with Send, round, in its right end and grey until there are words",
       g["h"] == 40 and g["s"][2] - g["s"][0] == 32 and g["s"][3] - g["s"][1] == 32 and
       g["x"][2] - 8 <= g["s"][2] <= g["x"][2] and g["x"][1] <= g["s"][1] and g["s"][3] <= g["x"][3] and
       g["dis"], g)
    pg.evaluate("()=>window.scrollTo(0,0)"); pg.wait_for_timeout(150)
    g = pg.evaluate(GEO)
    ck("read from the top of the conversation, they stay on the bar",
       g["long"] and g["top"] == 0 and abs(g["cb"] - g["bar"]) <= 1, g)
    pg.evaluate("()=>window.scrollTo(0,document.scrollingElement.scrollHeight)"); pg.wait_for_timeout(150)
    pg.fill("#msgBox", "Happy birthday to Tom!\nThe kitchen will bring a candle with dessert.\n"
                       "Is there a time that suits?\nWe can also chill a bottle of something.\nJust say.")
    pg.wait_for_timeout(150)
    g = pg.evaluate(GEO)
    ck("five lines typed: the box grows to show them all, Send at its foot and blue",
       g["h"] >= 40 + 4 * 22 and g["sh"] <= g["ch"] + 1 and g["oy"] == "hidden" and
       abs((g["x"][3] - 4) - g["s"][3]) <= 1 and not g["dis"], g)
    ck("still on the bar, and the page followed, so the newest message is not under the box",
       abs(g["cb"] - g["bar"]) <= 1 and g["end"] and g["last"] <= g["ct"] + 1, g)
    pg.fill("#msgBox", "\n".join("Line %d of a very long message" % i for i in range(40)))
    pg.wait_for_timeout(150)
    g = pg.evaluate(GEO)
    ck("a very long one stops at half the screen and scrolls inside the box",
       g["h"] <= g["half"] + 1 and g["oy"] == "auto" and g["sh"] > g["ch"], g)
    del SENT[:]
    pg.fill("#msgBox", "Happy birthday to Tom!")
    pg.click("#sendBtn"); pg.wait_for_timeout(700)
    sends = [s for s in SENT if s.get("kind") == "send"]
    ck("Send hands the Worker the words, the guest and their booking, never a channel",
       len(sends) == 1 and sends[0]["text"] == "Happy birthday to Tom!" and sends[0]["ck"] == SARAH and
       sends[0]["booking"] == "b-sarah" and "via" not in sends[0] and "template" not in sends[0], sends)
    ck("and the box empties once it has gone", pg.input_value("#msgBox") == "")
    g = pg.evaluate(GEO)
    ck("back to one line, Send grey again, its arrow back", g["h"] == 40 and g["dis"] and
       pg.evaluate("()=>!!document.querySelector('#sendBtn svg')"), g)
    done(pg)

    STATE["send"] = (403, {"test": True, "error": "Test mode: only the test phones can be messaged."})
    STATE["hello"]["test"] = True
    pg = page("?c=%s&b=b-sarah" % SARAH)
    ck("test mode says so at the top", pg.is_visible("#testBar") and "Test mode" in pg.text_content("#testBar"))
    pg.fill("#msgBox", "Hello")
    pg.click("#sendBtn"); pg.wait_for_timeout(700)
    ck("and a refused send says the Worker's own words, in red, under the button",
       "Test mode: only the test phones" in pg.text_content("#sendErr") and
       pg.evaluate("()=>getComputedStyle(document.getElementById('sendErr')).color") == "rgb(168, 50, 30)" and
       pg.input_value("#msgBox") == "Hello", pg.text_content("#sendErr"))
    STATE["send"] = None; STATE["hello"]["test"] = False
    done(pg)

    # ── 4. past the 24 hours ───────────────────────────────────────────
    pg = page("?c=%s&b=b-james&t=up" % JAMES)
    ck("past the 24 hours the box says why, and when the guest last wrote",
       pg.text_content("#win").startswith("James last wrote Wed 23 Sep. After 24 hours WhatsApp only carries wording Meta has approved"),
       pg.text_content("#win"))
    chips = pg.evaluate("()=>[...document.querySelectorAll('#tpls .chip')].map(e=>[e.textContent,e.classList.contains('on')])")
    ck("and offers the approved messages, Your arrival to a guest still to arrive",
       chips == [["A quick question", True], ["Your arrival", False]], chips)
    ck("with no box to type free text into", not pg.is_visible("#msgBox"))
    g = pg.evaluate("""()=>{const c=document.getElementById('compose').getBoundingClientRect(),
        t=document.getElementById('tabBar'), el=document.scrollingElement,
        s=document.getElementById('sendBtn').getBoundingClientRect(),
        p=document.querySelector('#tplPrev .bub').getBoundingClientRect();
      return {cb:c.bottom, bar:t?t.getBoundingClientRect().top:null, short:el.scrollHeight<=innerHeight+1,
              s:[s.left,s.top,s.right,s.bottom], p:[p.left,p.top,p.right,p.bottom], dis:document.getElementById('sendBtn').disabled}}""")
    ck("a short conversation's words stand on the bar too, Send beside them, never over them",
       g["short"] and g["bar"] is not None and abs(g["cb"] - g["bar"]) <= 1 and
       g["s"][0] >= g["p"][2] and g["s"][3] <= g["p"][3] + 1 and not g["dis"], g)
    ck("the preview is the approved words with the guest's name",
       pg.text_content("#tplPrev") == "Hi James, it's Nala Resort with a quick question about your stay. Could you reply to this message when you have a moment?")
    pg.click("#tpl-arrival"); pg.wait_for_timeout(100)
    ck("and the booking's day", "on Saturday 3 October" in pg.text_content("#tplPrev"))
    shot(pg, "gc-closed")
    del SENT[:]
    pg.click("#sendBtn"); pg.wait_for_timeout(600)
    sends = [s for s in SENT if s.get("kind") == "send"]
    ck("Send asks for the approved message by name, with the booking to fill it from",
       len(sends) == 1 and sends[0].get("template") == "arrival" and sends[0].get("booking") == "b-james" and
       "text" not in sends[0], sends)
    done(pg)
    pg = page("?c=%s&b=b-james&t=up" % JAMES)
    pg.click("#viaBtn"); pg.wait_for_timeout(100)
    ck("SMS instead opens the box, and says it is SMS",
       pg.is_visible("#msgBox") and pg.text_content("#win").startswith("Sends by SMS · free text, as you chose"))
    del SENT[:]
    pg.fill("#msgBox", "Your transfer is at 2pm.")
    pg.click("#sendBtn"); pg.wait_for_timeout(600)
    sends = [s for s in SENT if s.get("kind") == "send"]
    ck("and Send asks for SMS", len(sends) == 1 and sends[0].get("via") == "sms" and
       sends[0].get("text") == "Your transfer is at 2pm.", sends)
    done(pg)

    pg = page("?c=61400000077")
    ck("a guest who texted STOP cannot be sent anything, and the page says why",
       "This guest texted STOP" in pg.text_content("#win") and not pg.is_visible("#msgBox") and
       not pg.is_visible("#sendBtn"))
    done(pg)

    STATE["hello"]["wa"] = False
    pg = page("?c=%s&b=b-sarah" % SARAH)
    ck("with no WhatsApp sender set up, the box says SMS, and why",
       pg.text_content("#win") == "Sends by SMS · WhatsApp is not set up yet", pg.text_content("#win"))
    STATE["hello"]["wa"] = True
    done(pg)

    # ── 5. what a guest writes is text ─────────────────────────────────
    pg = page("?c=%s" % UNK)
    ck("a message holding markup is shown as the characters it is",
       pg.evaluate("()=>!document.querySelector('#msgs img') && !document.querySelector('#msgs b') && !window.__XSS") and
       "<img src=x onerror=" in pg.text_content("#msgs"))
    ck("a number on no booking says so, and is titled by its number",
       pg.text_content("#title") == "0423 555 019" and "Not on any booking" in pg.text_content("#ctx"))
    ck("and an outside guest's dinner invitation is in their conversation, before their answer",
       pg.evaluate("()=>[...document.querySelectorAll('#msgs .msg')].map(e=>e.dataset.m)") == ["page0", "in-SMunk"] and
       pg.text_content('.msg[data-m="page0"] .meta') == "Dinner invitation · Ben · SMS · Sent",
       pg.evaluate("()=>[...document.querySelectorAll('#msgs .msg')].map(e=>e.innerText)"))
    done(pg)

    del WRITES[:]
    pg = page("?c=%s&b=b-sarah" % SARAH)
    pg.click("#waSw"); pg.wait_for_timeout(400)
    w = [x for x in WRITES if x["p"] == "/contact/%s/wa.json" % SARAH]
    ck("the WhatsApp switch records the guest's consent, with who and when",
       len(w) == 1 and w[0]["m"] == "PUT" and w[0]["b"]["on"] is False and w[0]["b"]["by"] == "ben@x" and
       w[0]["b"]["at"].startswith("2026-09-29"), w)
    done(pg)

    STATE["readfail"] = True
    pg = page()
    ck("a failed read draws no list and says why",
       "Could not read the guests" in pg.text_content("#errBar") and not rows(pg))
    STATE["readfail"] = False
    done(pg)

    # ── who may open it ───────────────────────────────────────────────
    for email, allowed in (("staff@x", True), ("waiter@x", True), ("chef@x", False),
                           ("housekeeping@x", False), ("masseuse@x", False)):
        pg = page(email=email)
        at = pg.url.split("/")[-1].split("?")[0]
        ck("%s %s Chat" % (email.split("@")[0], "opens" if allowed else "is sent away from"),
           (at == "guest-contact.html") == allowed, at)
        done(pg)

    # ── widths ────────────────────────────────────────────────────────
    for q in ("", "?c=%s&b=b-sarah" % SARAH, "?c=%s&b=b-james&t=up" % JAMES):
        for w in (390, 360, 320):
            pg = page(q, w=w)
            ck("no sideways scroll at %d%s" % (w, " in a conversation" if q else " on the list"),
               not pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
            done(pg)

    # ── 6. Tasks ──────────────────────────────────────────────────────
    if os.path.exists("tasks.html"):
        def cards(pg):
            return pg.evaluate("""()=>[...document.querySelectorAll('#board .task')].map(e=>({
              team:e.closest('[data-team]')?e.closest('[data-team]').dataset.team:e.dataset.team,
              id:e.dataset.t, nm:e.querySelector('.nm').textContent,
              words:e.querySelector('.words').textContent}))""")
        pg = page(email="ben@x", file="tasks.html")
        cs = cards(pg)
        ck("the desk sees every team's open tasks, oldest first by team",
           [c["id"] for c in cs] == ["t2gandt", "t1umbrella", "t5cake"] and
           pg.evaluate("()=>[...document.querySelectorAll('.grp')].map(e=>e.textContent)") ==
           ["Bar · 1", "Maintenance · 1", "Kitchen · 1"], cs)
        ck("and each card's words open that guest's conversation",
           pg.get_attribute('.task[data-t="t2gandt"] a.words', "href") == "guest-contact.html?c=61411000009")
        ck("in the guest's own words", cs[0]["words"] == "Could we get two gin and tonics at the pool?" and
           cs[0]["nm"] == "Priya Sharma", cs)
        pg.wait_for_timeout(400)
        ck("the bar's card carries the desk's note",
           "Charge to villa 9" in (pg.text_content('.task[data-t="t2gandt"] .tnote') or ""))
        lg = pg.evaluate("()=>[...document.querySelectorAll('.task[data-t=\"t2gandt\"] .lg')].map(e=>e.textContent)")
        ck("and its conversation since the request: the desk's reply, then the guest's answer",
           len(lg) == 2 and lg[0].startswith("Ben 3:07pm") and "Which gin" in lg[0] and
           lg[1].startswith("Guest 3:09pm") and "Tanqueray" in lg[1], lg)
        ck("asked of the Worker for every open card in one call",
           any(b.get("kind") == "tasklog" and len(b.get("tasks", [])) == 3 for b in SENT),
           [b for b in SENT if b.get("kind") == "tasklog"][:1])
        ck("an open task is the law's amber", pg.evaluate(
           "()=>getComputedStyle(document.querySelector('.task')).backgroundColor") == "rgb(246, 234, 213)")
        shot(pg, "tasks-desk")
        done(pg)
        pg = page(email="grounds@x", file="tasks.html")
        cs = cards(pg)
        ck("the grounds login sees Maintenance's alone", [c["id"] for c in cs] == ["t1umbrella"], cs)
        pg.wait_for_timeout(500)
        ck("with the guest's photo on it, through the Worker's task door",
           pg.evaluate("()=>{const i=document.querySelector('.task[data-t=\"t1umbrella\"] img.tphoto');"
                       "return !!(i && i.src.startsWith('blob:'))}"))
        del WRITES[:]
        pg.click('.task[data-t="t1umbrella"] [data-act="done"]'); pg.wait_for_timeout(500)
        w = WRITES[-1] if WRITES else {"b": {}}
        ck("and closes it in its own name, today",
           w.get("m") == "PATCH" and w.get("p") == "/tasks/maintenance/t1umbrella.json" and
           w["b"] == {"state": "done", "doneAt": w["b"].get("doneAt"), "doneBy": "grounds@x", "doneDay": TODAY}, w)
        shot(pg, "tasks-grounds")
        done(pg)
        pg = page(email="housekeeping@x", file="tasks.html")
        ck("a team with nothing open says so, and counts what it did today",
           cards(pg) == [] and "Nothing open" in pg.text_content("#board") and
           pg.text_content("#doneSum") == "Done today · 2", pg.text_content("#board"))
        done(pg)
        pg = page(email="chef@x", file="tasks.html")
        ck("the chef sees Kitchen's", [c["id"] for c in cards(pg)] == ["t5cake"])
        ck("and its card is not a door to a conversation the chef cannot open",
           pg.evaluate("()=>[...document.querySelectorAll('.task a')].length") == 0)
        done(pg)
        SETTINGS_BAK = json.loads(json.dumps(SETTINGS)); SETTINGS["teams"]["spa"]["members"] = {}
        pg = page(email="masseuse@x", file="tasks.html")
        ck("a login with no team is told how to get one",
           "No team is set for this login" in pg.text_content("#board"))
        SETTINGS.clear(); SETTINGS.update(SETTINGS_BAK)
        done(pg)
        for w in (390, 320):
            pg = page(email="ben@x", file="tasks.html", w=w)
            ck("Tasks has no sideways scroll at %d" % w,
               not pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
            done(pg)

    # ── 7. the teams, as Settings names them (29 Sep) ──────────────────
    # contactTeams is the one reading of the list: a renamed team, an added
    # one, a retired one, as Chat, Tasks and Settings each offer it.
    SETTINGS_BAK = json.loads(json.dumps(SETTINGS))
    SETTINGS["teams"]["kitchen"]["label"] = "Kitchen pass"
    SETTINGS["teams"]["frontdesk"] = {"label": "Reception"}
    SETTINGS["teams"]["bar"] = {"off": True}            # retired, Priya's gin still open
    SETTINGS["teams"]["poolbar"] = {"label": "Pool bar", "added": "2026-09-29T01:00:00.000Z",
                                    "members": {"housekeeping@x": True}}
    pg = page("?c=%s&b=b-sarah" % SARAH)
    pg.click("#tk-in-SMcandle"); pg.wait_for_timeout(150)
    teams = pg.evaluate("()=>[...document.querySelectorAll('.msg[data-m=\"in-SMcandle\"] .tri .sbtn')].map(e=>e.textContent)")
    ck("Task offers the teams by their names in Settings, an added one last, a removed one not at all",
       teams == ["Kitchen pass", "Housekeeping", "Maintenance", "Spa", "Reception", "Pool bar", "Cancel"], teams)
    done(pg)
    pg = page()
    by = {r["ck"]: r for r in rows(pg) if r["ck"]}
    ck("a removed team's task still open still shows, under its name",
       by["61411000009"]["s"] == "task" and by["61411000009"]["l3"].endswith("Bar open"), by["61411000009"])
    done(pg)
    pg = page(email="ben@x", file="tasks.html")
    grps = pg.evaluate("()=>[...document.querySelectorAll('#board .grp')].map(e=>e.textContent)")
    ck("Tasks heads each team with its name in Settings, and keeps a removed team's open task",
       grps == ["Bar · 1", "Maintenance · 1", "Kitchen pass · 1"], grps)
    done(pg)
    pg = page(email="housekeeping@x", file="tasks.html")
    ck("a login on an added team sees it", "Nothing open for Housekeeping, Pool bar." in
       pg.text_content("#board"), pg.text_content("#board"))
    done(pg)

    def staffpg(w=390):
        p = page(email="staff@x", file="staff.html", w=w)
        p.click('[data-t="tTeams"]'); p.wait_for_timeout(150)
        return p
    def sheet_err(p): return (p.text_content("#sErr") or "").strip()
    def team_writes(): return [x for x in WRITES if x["p"].startswith("/contactsettings/")]
    pg = staffpg()
    names = pg.evaluate("()=>[...document.querySelectorAll('#teamList .person')].map(e=>"
                        "[e.querySelector('.nm').textContent,e.querySelector('.sub').textContent])")
    ck("Settings lists the teams in use, each with who does its tasks",
       names == [["Kitchen pass", "Chef"], ["Housekeeping", "HK"], ["Maintenance", "Ray Grounds"],
                 ["Spa", "Masseuse"], ["Reception", "Nobody yet"], ["Pool bar", "HK"]], names)
    ck("and a removed team below them, with a way back",
       pg.evaluate("()=>[...document.querySelectorAll('#teamGone .evrow')].map(e=>e.innerText.replace(/\\s+/g,' ').trim())")
       == ["Bar Bring back"])
    del WRITES[:]
    for name, want in (("Pool Bar", "There is already a team called Pool bar."),
                       ("bar", "Bar was removed: bring it back below the list."),
                       ("12", "The name needs at least two letters.")):
        pg.click("#addTeamBtn"); pg.fill("#tNew", name)
        pg.click("#sheet .btn.solid"); pg.wait_for_timeout(150)
        ck("adding %r is refused: %s" % (name, want), sheet_err(pg) == want and team_writes() == [], sheet_err(pg))
        pg.click("#sheet .btn.ghost"); pg.wait_for_timeout(100)
    pg.click("#addTeamBtn"); pg.fill("#tNew", "Gardens & Grounds")
    pg.click("#sheet .btn.solid"); pg.wait_for_timeout(700)
    w = team_writes()
    ck("a new team is stored under its name's letters, named and dated",
       len(w) == 1 and w[0]["m"] == "PATCH" and w[0]["p"] == "/contactsettings/teams/gardensgrounds.json" and
       w[0]["b"]["label"] == "Gardens & Grounds" and str(w[0]["b"].get("added", "")).startswith("2026-09-29T"), w)
    ck("and joins the list at the end", pg.evaluate(
       "()=>[...document.querySelectorAll('#teamList .person .nm')].map(e=>e.textContent)")[-1] == "Gardens & Grounds")
    del WRITES[:]
    pg.click('#teamList [data-tk="maintenance"]'); pg.wait_for_timeout(100)
    pg.fill("#tName", "spa"); pg.click("#sheet .btn.solid"); pg.wait_for_timeout(150)
    ck("renaming to another team's name is refused",
       sheet_err(pg) == "There is already a team called Spa." and team_writes() == [], sheet_err(pg))
    pg.fill("#tName", "Grounds"); pg.click("#sheet .btn.solid"); pg.wait_for_timeout(700)
    w = team_writes()
    ck("a rename changes the name alone, never the key its tasks are under",
       len(w) == 1 and w[0]["p"] == "/contactsettings/teams/maintenance.json" and w[0]["b"] == {"label": "Grounds"}, w)
    del WRITES[:]
    pg.click('#teamList [data-tk="kitchen"]'); pg.wait_for_timeout(100)
    rm = pg.evaluate("()=>{const b=document.querySelector('#sheet .btn.terra');const s=getComputedStyle(b);"
                     "return [b.textContent,s.color]}")
    ck("Remove team wears the button law's terracotta, never red", rm[0] == "Remove team" and
       rm[1] != "rgb(168, 50, 30)", rm)
    pg.click("#sheet .btn.terra"); pg.wait_for_timeout(100)
    ck("and asks first", "Remove Kitchen pass?" in pg.text_content("#sheet") and team_writes() == [])
    pg.click("#sheet .btn.terra"); pg.wait_for_timeout(400)
    ck("a team with a task still open is not removed, and says what to do",
       sheet_err(pg) == "Kitchen pass has 1 open task. Close it on Tasks first." and team_writes() == [],
       sheet_err(pg))
    pg.click("#sheet .btn.ghost"); pg.wait_for_timeout(100)
    pg.click("#sheet .btn.ghost"); pg.wait_for_timeout(100)
    pg.click('#teamList [data-tk="housekeeping"]'); pg.wait_for_timeout(100)
    pg.click("#sheet .btn.terra"); pg.wait_for_timeout(100)
    pg.click("#sheet .btn.terra"); pg.wait_for_timeout(800)
    w = team_writes()
    ck("one with nothing open is retired, not deleted: its name stays on its tasks",
       len(w) == 1 and w[0]["p"] == "/contactsettings/teams/housekeeping.json" and w[0]["b"] == {"off": True}, w)
    ck("and moves to Removed", "Housekeeping" in pg.text_content("#teamGone") and
       "Housekeeping" not in pg.text_content("#teamList"))
    del WRITES[:]
    pg.click('#teamGone [data-back="bar"]'); pg.wait_for_timeout(700)
    w = team_writes()
    ck("Bring back undoes the retiring and nothing else",
       len(w) == 1 and w[0]["p"] == "/contactsettings/teams/bar.json" and w[0]["b"] == {"off": None}, w)
    shot(pg, "staff-teams")
    done(pg)
    pg = page(email="staff@x", file="staff.html")
    pg.click('#people .person:has-text("Ray Grounds")'); pg.wait_for_timeout(150)
    sw = pg.evaluate("()=>[...document.querySelectorAll('#teamRows .evrow span')].map(e=>e.textContent)")
    ck("a person's switches offer the teams in use, by their names", sw ==
       ["Kitchen pass", "Housekeeping", "Maintenance", "Spa", "Reception", "Pool bar"], sw)
    done(pg)
    for w in (390, 320):
        pg = staffpg(w)
        ck("the Teams tab has no sideways scroll at %d" % w,
           not pg.evaluate("()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1"))
        done(pg)
    SETTINGS.clear(); SETTINGS.update(SETTINGS_BAK)

    # ── 8. tried by the admin before the staff see it (29 Sep) ─────────
    # PREVIEW_PAGES: published before Twilio is set up, Chat and
    # Tasks are the admin's alone until Settings opens them to the staff.
    PERMS_BAK = json.loads(json.dumps(PERMS)); PERMS.clear()
    menu = lambda p: p.evaluate("""()=>[...document.querySelectorAll('#navDrop a')]
        .filter(a=>getComputedStyle(a).display!=='none').map(a=>a.getAttribute('href'))""")
    for email, file in (("waiter@x", "guest-contact.html"), ("waiter@x", "tasks.html"),
                        ("grounds@x", "tasks.html"), ("masseuse@x", "tasks.html")):
        pg = page(email=email, file=file)
        at = pg.url.split("/")[-1].split("?")[0]
        ck("shut, %s is sent away from %s" % (email.split("@")[0], file), at != file, at)
        done(pg)
    pg = page(email="waiter@x", file="tally.html")
    m = menu(pg)
    ck("and the waiter's menu offers neither",
       "guest-contact.html" not in m and "tasks.html" not in m and len(m) > 3, m)
    done(pg)
    pg = page(email="staff@x")
    ck("while the admin opens Chat", pg.url.split("/")[-1].split("?")[0] == "guest-contact.html")
    m = menu(pg)
    ck("and finds Tasks in the menu", "tasks.html" in m, m)
    done(pg)
    pg = page(email="staff@x", file="staff.html")
    pg.click('[data-t="tTeams"]'); pg.wait_for_timeout(150)
    ck("Settings says the two are the admin's alone, the switch off",
       pg.get_attribute("#gcOpen", "aria-checked") == "false" and
       "Only you see Chat and Tasks" in pg.text_content("#gcOpenNote"))
    del WRITES[:]
    pg.click("#gcOpen"); pg.wait_for_timeout(400)
    w = [x for x in WRITES if x["p"].startswith("/permissions")]
    ck("On opens both to the staff in one write",
       len(w) == 1 and w[0]["m"] == "PATCH" and w[0]["p"] == "/permissions/open.json" and
       w[0]["b"] == {"guest-contact": True, "tasks": True} and
       pg.get_attribute("#gcOpen", "aria-checked") == "true", w)
    ck("and the Roles tab's copy knows, so its next save cannot shut them again",
       pg.evaluate("()=>PERMS.open['guest-contact']===true && PERMS.open.tasks===true"))
    del WRITES[:]
    pg.click("#gcOpen"); pg.wait_for_timeout(400)
    w = [x for x in WRITES if x["p"].startswith("/permissions")]
    ck("and Off takes both back",
       len(w) == 1 and w[0]["b"] == {"guest-contact": None, "tasks": None} and
       pg.get_attribute("#gcOpen", "aria-checked") == "false", w)
    done(pg)
    PERMS.update(PERMS_BAK)
    # Published before the Worker exists: its address answers nothing.
    ctx = br.new_context(viewport={"width": 390, "height": 900}, timezone_id="Australia/Brisbane")
    q = ctx.new_page(); q.clock.set_fixed_time(ZONES["Australia/Brisbane"])
    q.add_init_script(SDK); q.add_init_script("window.__EMAIL='staff@x';")
    q.route("**firebasedatabase.app/**", fb)
    q.route("**nala-contact.ben-681.workers.dev/**", lambda r: r.abort())
    q.route("**gstatic.com/**", lambda r: r.fulfill(status=200, body=""))
    q.goto("http://localhost:%d/guest-contact.html" % PORT); q.wait_for_timeout(1300)
    ck("with no Worker to answer, the page says so at the top rather than at Send",
       q.is_visible("#testBar") and "The messenger is not answering" in q.text_content("#testBar"),
       q.text_content("#testBar"))
    ctx.close()
    pg = page(email="waiter@x", file="tally.html")
    m = menu(pg)
    ck("opened, the waiter's menu has both", "guest-contact.html" in m and "tasks.html" in m, m)
    done(pg)

    # ── 9. a reply from the card, for a role Settings lets reply (30 Sep) ─
    # The owner: "a toggle in settings for a role being able to respond to
    # messages". The Worker's half - refused unless switched on, only to an
    # open task's guest - is worker/contact-test.mjs; this is the page's.
    pg = page(email="grounds@x", file="tasks.html"); pg.wait_for_timeout(500)
    ck("housekeeping ships without it: the card has Done and no Reply",
       pg.is_visible('.task[data-t="t1umbrella"] [data-act="done"]') and
       not pg.query_selector('.task[data-t="t1umbrella"] [data-act="reply"]'))
    done(pg)
    pg = page(email="staff@x", file="staff.html")
    pg.click('[data-t="tRoles"]'); pg.wait_for_timeout(150)
    pg.click('#permPick [data-r="2"]'); pg.wait_for_timeout(100)
    ck("Settings, Roles: Reply to guests, off for housekeeping as it ships",
       "Reply to guests" in pg.text_content("#permList") and
       pg.get_attribute("#may-guestReply", "aria-checked") == "false")
    del WRITES[:]
    pg.click("#may-guestReply"); pg.wait_for_timeout(400)
    w = [x for x in WRITES if x["p"] == "/permissions.json"]
    ck("switched on, it is saved with the rest of who may do what, the opening kept",
       len(w) == 1 and w[0]["m"] == "PUT" and w[0]["b"].get("guestReply") == {"housekeeping": True} and
       w[0]["b"].get("open") == PERMS.get("open"), w)
    pg.click('#permPick [data-r="1"]'); pg.wait_for_timeout(100)
    ck("and the waiter, at the desk, ships with it on",
       pg.get_attribute("#may-guestReply", "aria-checked") == "true")
    done(pg)
    PERMS["guestReply"] = {"housekeeping": True}
    RB, RS, RF = "#rb-maintenance-t1umbrella", "#rs-maintenance-t1umbrella", "#rf-maintenance-t1umbrella"
    pg = page(email="grounds@x", file="tasks.html"); pg.wait_for_timeout(500)
    ck("switched on, the card offers Reply beside Done", pg.is_visible("#rp-maintenance-t1umbrella") and
       pg.is_visible('.task[data-t="t1umbrella"] [data-act="done"]'))
    pg.click("#rp-maintenance-t1umbrella"); pg.wait_for_timeout(150)
    ck("which opens a box, saying which way it goes as the Worker says it",
       pg.is_visible(RB) and "To the guest, on WhatsApp" in pg.text_content('.task[data-t="t1umbrella"] .rwin') and
       pg.evaluate("()=>document.activeElement && document.activeElement.id") == RB[1:])
    ck("the box is the editable white, its Send the one solid on the card",
       pg.evaluate("(s)=>getComputedStyle(document.querySelector(s)).backgroundColor", RB) == "rgb(255, 255, 255)" and
       pg.evaluate("()=>document.querySelectorAll('.task[data-t=\"t1umbrella\"] .btn.solid').length") == 1)
    del SENT[:]
    pg.click(RS); pg.wait_for_timeout(200)
    ck("an empty reply goes nowhere, and says why",
       not [b for b in SENT if b.get("kind") == "send"] and "Write the reply first" in pg.text_content(RF))
    pg.fill(RB, "On my way with a new one.")
    pg.click(RS); pg.wait_for_timeout(200)
    sheet = pg.text_content("#sheet") if pg.is_visible("#sheet") else ""
    ck("Send first asks: it goes straight to the guest, by name and villa, not to Reception (the owner, 30 Sep)",
       "Send this to Sarah Whitfield?" in sheet and "villa 7" in sheet and "on WhatsApp" in sheet and
       "not a message to Reception" in sheet and "On my way with a new one." in sheet and
       not [b for b in SENT if b.get("kind") == "send"], sheet)
    pg.click("#toBack"); pg.wait_for_timeout(150)
    ck("Back sends nothing and keeps the words",
       not pg.is_visible("#sheet") and pg.input_value(RB) == "On my way with a new one." and
       not [b for b in SENT if b.get("kind") == "send"])
    pg.click(RS); pg.wait_for_timeout(150)
    pg.click("#toGuest"); pg.wait_for_timeout(900)
    sd = [b for b in SENT if b.get("kind") == "send"]
    ck("Send to guest hands the Worker the words and the task",
       len(sd) == 1 and sd[0]["team"] == "maintenance" and sd[0]["t"] == "t1umbrella" and
       sd[0]["text"] == "On my way with a new one." and "via" not in sd[0] and "template" not in sd[0], sd)
    ck("and once sent the pop-up and the box close, and the card asks for its conversation again",
       not pg.is_visible("#sheet") and not pg.query_selector(RB) and
       len([b for b in SENT if b.get("kind") == "tasklog"]) >= 1)
    STATE["send"] = (409, {"error": "This guest texted STOP. Nothing can be sent until they text START."})
    pg.click("#rp-maintenance-t1umbrella"); pg.wait_for_timeout(100)
    pg.fill(RB, "Hello again"); pg.click(RS); pg.wait_for_timeout(150)
    pg.click("#toGuest"); pg.wait_for_timeout(500)
    ck("a refusal is said in the Worker's words, and what was typed stays",
       "texted STOP" in pg.text_content("#toErr") and pg.input_value(RB) == "Hello again", pg.text_content("#toErr"))
    STATE["send"] = None
    shot(pg, "tasks-reply")
    done(pg)
    STATE["route"] = {"ch": "watpl", "until": None}
    del SENT[:]
    pg = page(email="grounds@x", file="tasks.html"); pg.wait_for_timeout(500)
    pg.click("#rp-maintenance-t1umbrella"); pg.wait_for_timeout(100)
    say = pg.text_content('.task[data-t="t1umbrella"] .rwin')
    pg.fill(RB, "Your umbrella is fixed."); pg.click(RS); pg.wait_for_timeout(150)
    by = pg.text_content("#sheet")
    pg.click("#toGuest"); pg.wait_for_timeout(700)
    sd = [b for b in SENT if b.get("kind") == "send"]
    ck("past WhatsApp's 24 hours the card says so, and the reply goes by SMS",
       "24 hours have passed" in say and "SMS" in say and "by SMS" in by and len(sd) == 1 and
       sd[0].get("via") == "sms", [say, by, sd])
    done(pg)
    STATE["route"] = {"ch": "none", "until": None}
    pg = page(email="grounds@x", file="tasks.html"); pg.wait_for_timeout(500)
    ck("a guest who texted STOP: the card says so, and offers no Reply",
       "texted STOP" in pg.text_content('.task[data-t="t1umbrella"]') and
       not pg.query_selector("#rp-maintenance-t1umbrella"))
    done(pg)
    STATE["route"] = None
    pg = page(email="chef@x", file="tasks.html"); pg.wait_for_timeout(500)
    ck("the chef, not switched on, only reads", len(cards(pg)) == 1 and
       not pg.query_selector('[data-act="reply"]'))
    done(pg)
    PERMS["guestReply"] = {"waiter": False}
    pg = page("?c=%s&b=b-sarah" % SARAH, email="waiter@x")
    ck("the desk's waiter switched off: the conversation reads, with no box to reply in",
       pg.query_selector(".msg") is not None and not pg.is_visible("#msgBox") and
       not pg.is_visible("#sendBtn") and "switched off for this login" in pg.text_content("#win"))
    done(pg)
    pg = page("?c=%s&b=b-sarah" % SARAH, email="staff@x")
    ck("while the admin, never switched off, has it", pg.is_visible("#msgBox") and pg.is_visible("#sendBtn"))
    done(pg)
    del PERMS["guestReply"]

    # ── 10. the setup check (30 Sep) ────────────────────────────────
    # The owner, a test text refused and Twilio's console no help: "Why
    # don't you just create an error webhook url". The Worker's words are
    # held to worker/contact-test.mjs; here, Chat showing them.
    box = lambda p: p.evaluate("()=>{const b=document.getElementById('setupBox');"
                               "return getComputedStyle(b).display==='none'?null:b.innerText}")
    pg = page(email="staff@x"); pg.wait_for_timeout(400)
    ck("all working and live, the admin's Chat shows no setup check", box(pg) is None, box(pg))
    done(pg)
    STATE["hello"]["test"] = True
    pg = page(email="staff@x"); pg.wait_for_timeout(400)
    ck("in test mode it shows, and says everything is working",
       (box(pg) or "").startswith("Setup check: everything is working"), box(pg))
    done(pg)
    STATE["hello"]["test"] = False
    STATE["check"] = [
        {"key": "twilio", "ok": True, "say": "Twilio accepts the Account SID and the Auth Token."},
        {"key": "webhook", "ok": False, "say": "Twilio hands the number's texts to nowhere. It should be "
                                               "https://nala-contact.ben-681.workers.dev/twilio/in by HTTP POST."},
        {"key": "inbound", "ok": False, "say": "The last text Twilio passed here was refused: its signature did "
                                               "not match TWILIO_AUTH_TOKEN.", "at": "2026-09-29T13:46:31+10:00"},
        {"key": "test", "ok": None, "say": "Test mode is on: Chat can only message 1 phone."}]
    pg = page(email="staff@x"); pg.wait_for_timeout(400)
    t = (box(pg) or "").replace("\xa0", " ")
    ck("a thing to fix shows at the top of Chat in the Worker's words, with when",
       t.startswith("Setup check: 2 things to fix") and "should be https://nala-contact.ben-681.workers.dev/twilio/in" in t and
       "Tue 29 Sep 1:46pm" in t, t)
    ck("a line to fix is failure's red, a working one the done green",
       pg.evaluate("()=>getComputedStyle(document.querySelector('#setupBox .sr.bad')).color") == "rgb(168, 50, 30)" and
       pg.evaluate("()=>getComputedStyle(document.querySelector('#setupBox .sr.ok .mk')).color") == "rgb(94, 125, 103)")
    del SENT[:]
    pg.click("#setupAgain"); pg.wait_for_timeout(300)
    ck("Check again asks the Worker again", any(b.get("kind") == "check" for b in SENT))
    done(pg)
    del SENT[:]
    pg = page(email="waiter@x"); pg.wait_for_timeout(400)
    ck("the waiter's Chat neither asks nor shows it", box(pg) is None and
       not any(b.get("kind") == "check" for b in SENT))
    done(pg)
    STATE["check"] = None

    # ── 11. a photo drawn once, and the admin's delete (30 Sep) ────────
    # The owner, testing: a guest's photo "flashing on and off", and "is it
    # possible to delete individual items from a message stream?"
    del SENT[:]
    pg = page("?c=%s&b=b-sarah" % SARAH, email="staff@x"); pg.wait_for_timeout(800)
    media = lambda: len([b for b in SENT if b.get("kind") == "media"])
    first = media()
    pg.evaluate("()=>refresh()"); pg.wait_for_timeout(500)
    pg.evaluate("()=>{TH.sent=TH.sent.slice(); DRAWN_SIG=''; return refresh()}"); pg.wait_for_timeout(500)
    ck("a guest's photo is fetched once, and a redraw draws it at once rather than blanking it",
       first == 1 and media() == 1 and
       pg.evaluate("()=>document.querySelector('.msg[data-m=\"in-SMumbrella\"] img.photo').src.startsWith('blob:')"),
       [first, media()])
    ck("and the 8-second refresh redraws only when the conversation has moved",
       pg.evaluate("""()=>{const a=document.querySelector('.msg[data-m="in-SMthanks"]');
         return refresh().then(()=>a===document.querySelector('.msg[data-m="in-SMthanks"]'))}"""))
    pg.click('.msg[data-m="oreply1"] .bub'); pg.wait_for_timeout(150)
    ck("the admin taps a message for Delete message, the button law's terracotta",
       pg.is_visible("#dl-oreply1") and "terra" in pg.get_attribute("#dl-oreply1", "class"))
    pg.click('.msg[data-m="page0"] .bub'); pg.wait_for_timeout(150)
    ck("never on an SMS page's text, which that page owns",
       not pg.query_selector('.msg[data-m="page0"] [data-act="delask"]'))
    del SENT[:]
    pg.click("#dl-oreply1"); pg.wait_for_timeout(150)
    sh = pg.text_content("#sheet") if pg.is_visible("#sheet") else ""
    ck("and a sheet asks first, quoting it, and saying the guest keeps their copy",
       "Delete this message?" in sh and "The guest keeps it on their phone" in sh and
       not [b for b in SENT if b.get("kind") == "delete"], sh)
    pg.click("#delKeep"); pg.wait_for_timeout(150)
    ck("Keep it deletes nothing", not pg.is_visible("#sheet") and not [b for b in SENT if b.get("kind") == "delete"])
    pg.click("#dl-oreply1"); pg.wait_for_timeout(150)
    pg.click("#delGo"); pg.wait_for_timeout(700)
    ck("Delete asks the Worker, which alone writes the messages",
       [(b.get("ck"), b.get("m")) for b in SENT if b.get("kind") == "delete"] == [(SARAH, "oreply1")] and
       not pg.is_visible("#sheet"))
    done(pg)
    pg = page("?c=%s&b=b-sarah" % SARAH, email="ben@x"); pg.wait_for_timeout(600)
    pg.click('.msg[data-m="oreply1"] .bub'); pg.wait_for_timeout(150)
    ck("the desk's waiter taps and gets no Delete: the admin's alone",
       not pg.query_selector('[data-act="delask"]'))
    done(pg)
    # The owner, 30 Sep, Delete tried before the Worker's paste: "unknown
    # kind". Said as what it means, where it happens and at the top.
    STATE["old"] = True
    pg = page("?c=%s&b=b-sarah" % SARAH, email="staff@x"); pg.wait_for_timeout(800)
    ck("a Worker older than the page is named at the top, for the admin",
       "older than this page" in (pg.text_content("#setupBox") or ""), pg.text_content("#setupBox"))
    pg.click('.msg[data-m="oreply1"] .bub'); pg.wait_for_timeout(150)
    pg.click("#dl-oreply1"); pg.wait_for_timeout(150)
    pg.click("#delGo"); pg.wait_for_timeout(700)
    ck("and a Delete it does not know says to paste the Worker, not unknown kind",
       "Paste worker/guest-contact.js" in pg.text_content("#delErr") and
       "unknown kind" not in pg.text_content("#delErr"), pg.text_content("#delErr"))
    done(pg)
    STATE["old"] = False

    # ── 12. every template, from the send area (30 Sep) ──────────────
    # The owner: "we should have access to all the templates from the send
    # area". Each set goes as its own page sends it, through that page's
    # Worker, so the page records it and this conversation shows it.
    PRIYA = "61411000009"
    tsheet = lambda pg: pg.evaluate("""()=>({
        groups:[...document.querySelectorAll('#sheet .tg')].map(e=>e.textContent),
        why:[...document.querySelectorAll('#sheet .tw')].map(e=>e.textContent),
        btns:[...document.querySelectorAll('#sheet button[data-tset]')].map(e=>
          e.dataset.tset+':'+e.dataset.tid+(e.dataset.ttr?':'+e.dataset.ttr:''))})""")
    for tz in ZONES:
        del INV[:]
        pg = page("?c=%s&b=b-priya" % PRIYA, tz=tz); pg.wait_for_timeout(600)
        tb = pg.evaluate("""()=>{const b=document.getElementById('tmplBtn'),s=getComputedStyle(b);
          return {shown:b.offsetParent!==null, border:s.borderTopStyle+' '+s.borderTopWidth,
          cls:b.className}}""")
        ck("[%s] the send area has Templates, a button bordered as one" % tz,
           tb["shown"] and tb["border"] == "solid 1px" and "sbtn" in tb["cls"], tb)
        pg.click("#tmplBtn"); pg.wait_for_timeout(500)
        o = tsheet(pg)
        ck("[%s] the sheet holds every set: the form, tonight's menu, the spa reminder" % tz,
           o["groups"] == ["Pre-arrival form", "Tonight\u2019s menu", "Spa reminder"], o)
        ck("[%s] and offers only what its page would send: no form to a guest in house" % tz,
           "Only before a guest arrives." in o["why"] and not [x for x in o["btns"] if x.startswith("pre:")], o)
        ck("[%s] tonight's menu, live, in the Templates page's order" % tz,
           [x for x in o["btns"] if x.startswith("menu:")] == ["menu:ready", "menu:join"], o)
        # Begun is by the device's clock (spaTreatmentStarted): at 3:20pm in
        # Brisbane this morning's 9am has begun; a device in UTC reads
        # 5:20am, before it, as every board does.
        want = ["spa:remind:t7"] if tz == "Australia/Brisbane" else ["spa:remind:t6", "spa:remind:t7"]
        ck("[%s] tomorrow's massage, Spa reminders' own row; this morning's, once begun, is not offered" % tz,
           [x for x in o["btns"] if x.startswith("spa:")] == want and
           any("Wednesday 30 September at 10:30 am" in w for w in o["why"]), o)
        pg.click('#sheet button[data-tset="menu"][data-tid="ready"]'); pg.wait_for_timeout(200)
        cmp = pg.evaluate("""()=>({win:document.getElementById('win').textContent,
          prev:(document.querySelector('#tplPrev .bub')||{}).innerText,
          box:getComputedStyle(document.getElementById('msgBox')).display,
          back:document.getElementById('writeBtn').offsetParent!==null,
          head:document.getElementById('backBtn').offsetParent!==null,
          sheet:document.getElementById('backdrop').className})""")
        ck("[%s] picked, the box shows its words as the guest will read them, and says how it goes" % tz,
           cmp["prev"] == "Tonight\u2019s menu is ready. Nala Resort\nhttps://menu.nalaresort.com/?t=\u2026" and
           "Goes by SMS as Invitations sends it" in cmp["win"] and cmp["box"] == "none" and
           cmp["back"] and cmp["head"] and "show" not in cmp["sheet"], cmp)
        before = len([r for r in READS if r[0] == "/invites/2026-09-29.json"])
        pg.click("#sendBtn"); pg.wait_for_timeout(1500)
        ck("[%s] Send asks the SMS pages' sender for tonight's villa, as Invitations would" % tz,
           len(INV) == 1 and INV[0].get("kind") is None and INV[0].get("date") == TODAY and
           INV[0].get("villas") == ["9"] and INV[0].get("template") == "ready" and
           INV[0].get("body") == TMPL["/smstemplates.json"]["ready"]["body"] and INV[0].get("idToken") == "T",
           INV)
        ck("[%s] and nothing through Chat's own Worker" % tz,
           not [b for b in SENT if b.get("kind") == "send"])
        after = len([r for r in READS if r[0] == "/invites/2026-09-29.json"])
        ck("[%s] then the conversation re-reads the page's record, and the box is back to typing" % tz,
           after > before and pg.evaluate("()=>getComputedStyle(document.getElementById('msgBox')).display") != "none"
           and not pg.evaluate("()=>PICKT"), [before, after])
        done(pg)

    del INV[:]
    pg = page("?c=%s&b=b-priya" % PRIYA); pg.wait_for_timeout(600)
    pg.click("#tmplBtn"); pg.wait_for_timeout(500)
    pg.click('#sheet button[data-tset="spa"][data-tid="remind"]'); pg.wait_for_timeout(200)
    want = pg.evaluate("""()=>spaReminderText(TOFFER.sets.spa[0].body,'Priya',TOFFER.spa[0].rec,null)""")
    ck("a spa reminder's preview is the shared builder's text, the Worker's twin",
       pg.inner_text("#tplPrev .bub") == want and "Hello Priya" in want and "10:30 am" in want,
       [pg.inner_text("#tplPrev .bub"), want])
    shot(pg, "gc-template")
    pg.click("#sendBtn"); pg.wait_for_timeout(1500)
    ck("and goes as a spa reminder for that treatment",
       len(INV) == 1 and INV[0].get("kind") == "spa" and INV[0].get("treatments") == [{"b": "b-priya", "t": "t7"}]
       and INV[0].get("template") == "remind", INV)
    pg.click("#tmplBtn"); pg.wait_for_timeout(500)
    pg.click('#sheet button[data-tset="menu"][data-tid="join"]'); pg.wait_for_timeout(200)
    pg.click("#writeBtn"); pg.wait_for_timeout(150)
    ck("Write instead goes back to typing, nothing sent",
       len(INV) == 1 and pg.is_visible("#msgBox") and not pg.evaluate("()=>PICKT"))
    done(pg)

    # James arrives on the 3rd: the form, and a failure said in red
    del INV[:]
    STATE["inv"] = (200, {"results": {"b-james": {"status": "failed", "error": "no phone number on the booking"}}})
    STATE["hello"] = {"ready": True, "wa": True, "test": True, "buzz": False}
    pg = page("?c=%s&b=b-james" % JAMES); pg.wait_for_timeout(600)
    pg.click("#tmplBtn"); pg.wait_for_timeout(500)
    o = tsheet(pg)
    ck("a guest still to arrive is offered the form; not tonight's menu",
       [x for x in o["btns"] if x.startswith("pre:")] == ["pre:before", "pre:nudge"] and
       "Only for a guest in house tonight." in o["why"], o)
    pg.click('#sheet button[data-tset="pre"][data-tid="nudge"]'); pg.wait_for_timeout(200)
    ck("in test mode the box says a template is not held back",
       "Test mode does not hold this back: it goes to James." in pg.text_content("#win"),
       pg.text_content("#win"))
    pg.click("#sendBtn"); pg.wait_for_timeout(1500)
    ck("the form goes as Pre-arrival SMS sends it, by booking",
       len(INV) == 1 and INV[0].get("kind") == "pre" and INV[0].get("bookings") == ["b-james"] and
       INV[0].get("template") == "nudge", INV)
    ck("and a text that did not go says why, in failure's red, and stays picked to try again",
       "no phone number on the booking" in pg.text_content("#sendErr") and
       pg.evaluate("()=>getComputedStyle(document.getElementById('sendErr')).color") == "rgb(168, 50, 30)" and
       pg.evaluate("()=>!!PICKT"), pg.text_content("#sendErr"))
    done(pg)
    STATE["inv"] = None
    STATE["hello"] = {"ready": True, "wa": True, "test": False, "buzz": False}

    # yesterday's menu is not tonight's; a number on no booking has none
    STATE["menu"] = dict(MENU, published="2026-09-28T13:05:00+10:00")
    pg = page("?c=%s&b=b-priya" % PRIYA); pg.wait_for_timeout(600)
    pg.click("#tmplBtn"); pg.wait_for_timeout(500)
    o = tsheet(pg)
    ck("last night's menu offers no invitation: the Invitations page's own gate, menuLive",
       not [x for x in o["btns"] if x.startswith("menu:")] and
       any("not published yet" in w for w in o["why"]), o)
    done(pg)
    STATE["menu"] = MENU
    pg = page("?c=%s" % UNK); pg.wait_for_timeout(600)
    pg.click("#tmplBtn"); pg.wait_for_timeout(300)
    ck("a number on no booking is told why there are none",
       "This number is on no booking" in pg.text_content("#sheet") and not pg.query_selector("#sheet [data-tset]"))
    done(pg)
    for w in (360, 320):
        pg = page("?c=%s&b=b-priya" % PRIYA, w=w); pg.wait_for_timeout(600)
        pg.click("#tmplBtn"); pg.wait_for_timeout(500)
        pg.click('#sheet button[data-tset="spa"][data-tid="remind"]'); pg.wait_for_timeout(200)
        ck("at %d, the send area with a template picked does not bleed sideways" % w,
           pg.evaluate("()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth"))
        done(pg)

    br.close()

print("RESULT: %d passed, %d failed" % (P, F))
sys.exit(1 if F else 0)
