import threading,http.server,socketserver,json,time,os,sys
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8958),Q)
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
        out={"form":pg.evaluate("()=>!!document.getElementById('naGo')"),"errs":errs}
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

print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
