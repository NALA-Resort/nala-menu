import errortrap   # fails the run if any page throws
import threading,http.server,socketserver,json,time,os,sys
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=http.server.ThreadingHTTPServer(("",8958),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(0.3)

# app-compat only. firebase exists, firebase.auth does NOT — auth-compat failed.
APP_ONLY = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;}};"""
# what arrives when the recovery fetch succeeds
AUTH_LATE = """window.__A={onIdTokenChanged:function(cb){window.__CB=cb;setTimeout(function(){cb(null);},10);},
signInWithEmailAndPassword:function(e,p){window.__SIGNED=[e,p];
  setTimeout(function(){ if(window.__CB) window.__CB({email:e,getIdToken:function(){return Promise.resolve('T');}}); },20);
  return Promise.resolve({});},
signOut:function(){}};
window.firebase.auth=function(){ if(!window.firebase.__i) throw new Error("no app"); return window.__A;};"""

def fb(route,request): route.fulfill(status=200,content_type="application/json",body="null")

from playwright.sync_api import sync_playwright
P=F=0
def ck(n,c):
    global P,F
    print(("PASS " if c else "FAIL ")+n); P,F=(P+1,F) if c else (P,F+1)

WORKING = """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;}};
""" + AUTH_LATE

def run(mode, page="tally.html"):
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={"width":390,"height":844})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        def app_route(r,_): r.fulfill(status=200,content_type="application/javascript",
            body=(WORKING if mode=="healthy" else APP_ONLY))
        def auth_route(r,_):
            if mode=="healthy": r.fulfill(status=200,content_type="application/javascript",body="/*n*/")
            elif mode=="recover" and "?r=" in r.request.url:
                r.fulfill(status=200,content_type="application/javascript",body=AUTH_LATE)
            elif mode=="norecover": r.fulfill(status=500,body="")
            else: r.fulfill(status=200,content_type="application/javascript",body="/*missing*/")
        pg.route("**/firebase-app-compat.js*",app_route)
        pg.route("**/firebase-auth-compat.js*",auth_route)
        pg.route("**firebasedatabase.app/**",fb)
        pg.goto("http://localhost:8958/"+page); pg.wait_for_timeout(1400)
        out={"pad":pg.evaluate("()=>!!document.getElementById('nalaPad')"),"errs":errs}
        # the email form is the fallback, behind the long press on the wordmark
        pg.evaluate("()=>window.__NALA_PAD_EMAIL&&window.__NALA_PAD_EMAIL()"); pg.wait_for_timeout(200)
        out["form"]=pg.evaluate("()=>!!document.getElementById('naGo')")
        if out["form"]:
            pg.fill("#naEmail","staff@nala"); pg.fill("#naPass","secret")
            pg.click("#naGo"); pg.wait_for_timeout(2500)
            out["signed"]=pg.evaluate("()=>window.__SIGNED||null")
            out["disabled"]=pg.evaluate("()=>{const b=document.getElementById('naGo');return b?b.disabled:None;}".replace("None","null"))
            out["msg"]=pg.evaluate("()=>{const e=document.getElementById('naErr');return e?e.textContent:'';}")
            out["clear"]=pg.evaluate("()=>!document.getElementById('nalaAuthBox')")
        b.close()
        return out

# 1. auth-compat missing at load, arrives when we fetch it on the tap
r=run("recover")
print("   recover:", r)
ck("SDK missing at load: form appears, no page error", r["form"] and not r["errs"])
ck("tap fetches the SDK and signs in", r.get("signed")==["staff@nala","secret"])
ck("overlay clears once the token lands", r.get("clear") is True)

# 2. SDK cannot be recovered — the button must come back with a message
r=run("norecover")
print("   norecover:", r)
ck("unrecoverable: button re-enabled, never left dead",
   r.get("disabled") is False and len(r.get("msg",""))>0)
ck("unrecoverable: message names the cause", "sign-in service" in r.get("msg","").lower())

# 3. healthy SDK: the ordinary path is untouched
r=run("healthy")
print("   healthy:", r)
ck("healthy SDK: sign-in goes straight through", r.get("signed")==["staff@nala","secret"])


# ---- the passcode pad ----
def pad(fn, page="tally.html", h=844):
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(viewport={"width":390,"height":h})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/firebase-app-compat.js*",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body=WORKING))
        pg.route("**/firebase-auth-compat.js*",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body="/*n*/"))
        pg.route("**firebasedatabase.app/**",fb)
        pg.goto("http://localhost:8958/"+page); pg.wait_for_timeout(1400)
        out=fn(pg); out["errs"]=errs
        b.close(); return out

def tap(pg, digits):
    for d in digits:
        pg.click('.naKey[data-k="%s"]'%d); pg.wait_for_timeout(60)

# 4. the pad is the default way in, and it is the approved shape
r=pad(lambda pg: pg.evaluate("""()=>({
  pad:!!document.getElementById('nalaPad'),
  slots:document.querySelectorAll('.naSlot').length,
  keys:[].map.call(document.querySelectorAll('.naKey'),k=>k.getAttribute('data-k')),
  signin:!!document.getElementById('naGo'),
  emailLink:/use email/i.test(document.body.innerText)})"""))
print("   pad:", {k:v for k,v in r.items() if k!="errs"})
ck("pad is the default sign-in, not the email form", r["pad"] and not r["signin"])
ck("six slots", r["slots"]==6)
ck("keypad is 0-9 plus backspace, no sign-in button",
   r["keys"]==["1","2","3","4","5","6","7","8","9","0","back"])
ck("no visible email link: it is behind the long press", not r["emailLink"])
ck("pad renders without a page error", not r["errs"])

# 5. slots pinned 162px from the top and keypad hard to the bottom, in every
#    state and at both heights: a message must never move the thumb target
def geom(pg):
    return pg.evaluate("""()=>{const s=document.querySelector('.naSlot').getBoundingClientRect(),
      k=document.getElementById('naKeys').getBoundingClientRect(),
      m=document.getElementById('naPadMsg').getBoundingClientRect();
      return {slotTop:Math.round(s.top), keyBottom:Math.round(window.innerHeight-k.bottom),
              msgH:Math.round(m.height), keyH:Math.round(
                document.querySelector('.naKey').getBoundingClientRect().height)};}""")
tall=pad(geom); short=pad(geom, h=667)
def with_msg(pg):
    pg.evaluate("()=>{naPadMsg.textContent='Sign-in service did not load - check the connection and reload.';}")
    pg.wait_for_timeout(80); return geom(pg)
tallmsg=pad(with_msg); shortmsg=pad(with_msg, h=667)
print("   geometry:", tall, short, tallmsg, shortmsg)
ck("slots sit 162px from the top", tall["slotTop"]==162)
ck("slot position identical at both heights and with a two-line message",
   len({tall["slotTop"],short["slotTop"],tallmsg["slotTop"],shortmsg["slotTop"]})==1)
ck("keypad hard against the bottom, 22px, in every state",
   {tall["keyBottom"],short["keyBottom"],tallmsg["keyBottom"],shortmsg["keyBottom"]}=={22})
ck("keys are 58px tall", tall["keyH"]==58)
ck("message zone never falls below 52px", min(tall["msgH"],short["msgH"])>=52)

# 6. six presses submit on their own, and the code IS the credential
def six(pg):
    tap(pg,"482913"); pg.wait_for_timeout(600)
    return {"signed":pg.evaluate("()=>window.__SIGNED||null"),
            "clear":pg.evaluate("()=>!document.getElementById('nalaPad')")}
r=pad(six)
print("   submit:", {k:v for k,v in r.items() if k!="errs"})
ck("the sixth press submits with no button",
   r["signed"]==["482913@staff.nala","482913"])
ck("overlay clears once the token lands", r["clear"] is True)

# 7. dots, not digits, and backspace takes one off
def dots(pg):
    tap(pg,"4821")
    return {"code":pg.evaluate("()=>nalaPad.getAttribute('data-code')"),
            "shown":pg.evaluate("""()=>[].filter.call(document.querySelectorAll('.naSlot'),
                s=>getComputedStyle(s.firstChild).display!=='none').length"""),
            "leaks":pg.evaluate("()=>/4821/.test(document.getElementById('naSlots').innerText)")}
r=pad(dots)
ck("four presses fill four slots", r["shown"]==4 and r["code"]=="4821")
ck("slots show a dot, never the digit", not r["leaks"])
def back(pg):
    tap(pg,"4821"); pg.click('.naKey[data-k="back"]'); pg.wait_for_timeout(80)
    return {"code":pg.evaluate("()=>nalaPad.getAttribute('data-code')")}
ck("backspace removes one digit", pad(back)["code"]=="482")

# 8. a wrong code reddens all six and clears them
def wrong(pg):
    pg.evaluate("""()=>{window.__A.signInWithEmailAndPassword=function(){
        return Promise.reject({code:'auth/wrong-password'});};}""")
    tap(pg,"111111"); pg.wait_for_timeout(500)
    return {"code":pg.evaluate("()=>nalaPad.getAttribute('data-code')"),
            "red":pg.evaluate("""()=>[].filter.call(document.querySelectorAll('.naSlot'),
                s=>getComputedStyle(s).borderColor==='rgb(168, 50, 30)').length"""),
            "msg":pg.evaluate("()=>naPadMsg.textContent")}
r=pad(wrong)
print("   wrong:", {k:v for k,v in r.items() if k!="errs"})
ck("wrong code turns all six slots red", r["red"]==6)
ck("wrong code clears the slots", r["code"]=="")
ck("wrong code says so", "passcode" in r["msg"].lower())

# 9. five attempts, then a minute
def lock(pg):
    pg.evaluate("""()=>{window.__A.signInWithEmailAndPassword=function(){
        return Promise.reject({code:'auth/wrong-password'});};}""")
    for _ in range(5):
        tap(pg,"111111"); pg.wait_for_timeout(320)
    m=pg.evaluate("()=>naPadMsg.textContent")
    tap(pg,"9"); pg.wait_for_timeout(120)
    return {"msg":m,"afterLock":pg.evaluate("()=>nalaPad.getAttribute('data-code')")}
r=pad(lock)
print("   lockout:", {k:v for k,v in r.items() if k!="errs"})
ck("five wrong attempts locks the pad", "too many" in r["msg"].lower())
ck("locked pad ignores further presses", r["afterLock"]=="")

# 9b. the pad must never sit silent: a slow or dead request still says something
def hang(pg):
    pg.evaluate("""()=>{window.__A.signInWithEmailAndPassword=function(){
        return new Promise(function(){});};}""")   # never settles
    for d in "482913": pg.click('.naKey[data-k="%s"]'%d); pg.wait_for_timeout(50)
    pg.wait_for_timeout(400)
    return {"msg":pg.evaluate("()=>naPadMsg.textContent")}
r=pad(hang)
print("   pending:", {k:v for k,v in r.items() if k!="errs"})
ck("the sixth press says something at once, never a dead pad", len(r["msg"])>0)

def missing(pg):
    pg.evaluate("""()=>{window.__A.signInWithEmailAndPassword=function(){
        return Promise.reject({code:'auth/user-not-found'});};}""")
    for d in "482913": pg.click('.naKey[data-k="%s"]'%d); pg.wait_for_timeout(50)
    pg.wait_for_timeout(400)
    return {"msg":pg.evaluate("()=>naPadMsg.textContent")}
r=pad(missing)
print("   no account:", {k:v for k,v in r.items() if k!="errs"})
ck("a passcode with no account says so, not 'wrong passcode'",
   "no account" in r["msg"].lower())

# 9c. a persistence store that will not answer
#  The SDK defaults to LOCAL persistence, which is IndexedDB, and the sign-in
#  waits on that store before it resolves. Another tab of the same origin can
#  hold it, and then the sign-in never settles at all: no network error, no
#  rejection, fifteen seconds of nothing and then a message about the
#  connection while the phone shows full signal.
#
#  Reported 22 Aug as "works first time, then the link fails, then works in a
#  different browser", which is the shape of browser-held state and not of a
#  network. Eight tabs were open. Closing them fixed it.
#
#  LOCAL is asked for with a short cap and SESSION is the fallback, because
#  sessionStorage takes no cross-tab lock and cannot hang. A session that does
#  not outlive the tab beats a staff member who cannot sign in at all.
def locked(pg):
    pg.evaluate("""()=>{
      window.__log = [];
      var P = {LOCAL:'local', SESSION:'session', NONE:'none'};
      window.firebase.auth.Auth = { Persistence: P };
      window.__A.__store = 'local';
      window.__A.setPersistence = function(x){
        window.__log.push(x);
        if (x === 'local') return new Promise(function(){});   // never answers
        window.__A.__store = x; return Promise.resolve();
      };
      var real = window.__A.signInWithEmailAndPassword;
      window.__A.signInWithEmailAndPassword = function(e, p){
        /* the real SDK waits on the store, so a locked one hangs the sign-in */
        if (window.__A.__store === 'local') return new Promise(function(){});
        return real(e, p);
      };
    }""")
    for d in "482913": pg.click('.naKey[data-k="%s"]'%d); pg.wait_for_timeout(50)
    pg.wait_for_timeout(4000)
    return {"log": pg.evaluate("()=>window.__log"),
            "signed": pg.evaluate("()=>window.__SIGNED || null"),
            #  Gone is the best answer available: the sign-in went through and
            #  the overlay took itself away.
            "msg": pg.evaluate("()=>{var e=document.getElementById('naPadMsg');"
                               "return e ? e.textContent : '(pad gone)';}")}
r = pad(locked)
print("   locked store:", {k:v for k,v in r.items() if k!="errs"})
ck("a store that will not answer is asked once, then given up on",
   r["log"] == ["local", "session"])
ck("and the sign-in goes through on the store that cannot lock",
   bool(r["signed"]))
ck("without waiting out the fifteen second timeout",
   "no answer" not in r["msg"].lower())

# 10. the fallback door still opens and still works
def fallback(pg):
    pg.evaluate("()=>window.__NALA_PAD_EMAIL()"); pg.wait_for_timeout(200)
    ok=pg.evaluate("()=>!!document.getElementById('naGo')")
    pg.fill("#naEmail","staff@nalaresort.com.au"); pg.fill("#naPass","longpassword")
    pg.click("#naGo"); pg.wait_for_timeout(800)
    return {"form":ok,"signed":pg.evaluate("()=>window.__SIGNED||null")}
r=pad(fallback)
ck("the email fallback opens from the pad", r["form"] is True)
ck("and signs in with a real address, which can receive a reset",
   r["signed"]==["staff@nalaresort.com.au","longpassword"])

print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
