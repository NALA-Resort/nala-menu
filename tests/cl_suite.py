import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8957),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(0.3)
def sdk(email):
    return """window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("No Firebase App '[DEFAULT]' has been created"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'%s',getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'%s'});},25);},signOut:function(){}};"""%(email,email)
now=datetime.datetime.now().astimezone(); today=now.strftime("%Y-%m-%d")
def plus(d): return (now+datetime.timedelta(days=d)).strftime("%Y-%m-%d")
STATE={"fail":False}; WRITES=[]
responses={}
manual={"room-5":{"status":"vacant","pax":0,"room":"5","source":"manual"}}
roomguests={
 "1":{"name":"James","departs":today},
 "2":{"name":"Elena","departs":plus(2)},
 "7":{"name":"Priya","departs":today},
}
bf=(now-datetime.timedelta(minutes=12)).isoformat()
hk={"7":{"done":now.strftime("%Y-%m-%dT%H:%M:%S")+".123456"},"2":{"bfast":bf},
    "11":{"kind":"clean"}}
def fb(route,request):
    u=request.url; m=request.method
    if m=="PATCH":
        WRITES.append({"u":u,"b":request.post_data})
        if STATE["fail"]: route.fulfill(status=401,body="no"); return
        route.fulfill(status=200,content_type="application/json",body=request.post_data); return
    body="null"
    if "/responses/" in u: body=json.dumps(responses)
    elif "/manual/" in u: body=json.dumps(manual)
    elif "/roomguests/"+today in u: body=json.dumps(roomguests)
    elif "/roomguests/" in u: body="null"
    elif "/hk/" in u: body=json.dumps(hk)
    route.fulfill(status=200,content_type="application/json",body=body)
from playwright.sync_api import sync_playwright
P=F=0
def ck(n,c):
    global P,F
    print(("PASS " if c else "FAIL ")+n); P,F=(P+1,F) if c else (P,F+1)
def tile(pg,n):
    return pg.locator("#grid .tile").filter(has=pg.locator(".rn",has_text=re.compile(r"^%d$"%n)))
with sync_playwright() as p:
    b=p.chromium.launch()
    def page(email):
        pg=b.new_page(viewport={"width":820,"height":1100},device_scale_factor=2)
        pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=sdk(email)))
        pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
        pg.route("**firebasedatabase.app/**",fb)
        return pg
    pg=page("ben@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    hd=pg.evaluate("()=>({k:'n/a',d:title.textContent,c:nClean.textContent,s:nSvc.textContent,dn:nDone.textContent,nav:getComputedStyle(navWrap).display})")
    ck("header row present", pg.evaluate("()=>!!document.querySelector('.daterow .navwrap')"))
    ck("date format with year", bool(re.match(r'^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) \d{1,2}(st|nd|rd|th) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$',hd["d"])))
    # villa 11 is a staff-set clean, so cleans is one higher than the dates imply
    ck("cleans 3 services 1 done 1", hd["c"]=="3" and hd["s"]=="1" and hd["dn"]=="1")
    ck("management login sees menu", hd["nav"]=="block")
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    ck("menu opens on tap", pg.evaluate("()=>navDrop.classList.contains('open')"))
    pg.locator(".stats").click(); pg.wait_for_timeout(150)
    t=pg.evaluate("""()=>{const o={};document.querySelectorAll('#grid .tile').forEach(b=>{
      o[b.querySelector('.rn').textContent]={cls:b.className,txt:b.textContent};});return o;}""")
    ck("room1 Clean occupied", "Clean" in t["1"]["txt"] and "Occupied" in t["1"]["txt"])
    ordr=pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].map(b=>b.querySelector('.rn').textContent)")
    print("   tile order:", ordr)
    ck("services first, then cleans, vacant last",
       ordr[0]=="2" and ordr[1:3]==["1","7"] and ordr[-1]=="5")
    chips=pg.evaluate("""()=>{const g=n=>[...document.querySelectorAll('#grid .tile')]
      .find(b=>b.querySelector('.rn').textContent===n).querySelector('.chip');
      const c=n=>{const e=g(n),s=getComputedStyle(e);return {bg:s.backgroundColor,fg:s.color,t:e.textContent};};
      return {clean:c('1'),svc:c('2')};}""")
    print("   chips:", chips)
    ck("Clean badge solid ink, Service badge unfilled",
       chips["clean"]["bg"]=="rgb(28, 28, 26)" and chips["svc"]["bg"]=="rgba(0, 0, 0, 0)"
       and chips["clean"]["fg"]!=chips["svc"]["fg"])
    ck("room7 done green with time (6-digit ISO)", "done" in t["7"]["cls"] and re.search(r'Done \d{2}:\d{2}',t["7"]["txt"]))
    ck("room2 breakfast amber with elapsed", "bfast" in t["2"]["cls"] and re.search(r'B.fast 1[12]m',t["2"]["txt"]))
    ck("room5 vacant faded", "vac" in t["5"]["cls"])
    ck("villa3 unknown, one label only",
       "Unknown" in t["3"]["txt"] and "Verify" not in t["3"]["txt"]
       and "Occupancy" not in t["3"]["txt"])

    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,3).click(); pg.wait_for_timeout(250)
    us = pg.locator("#sheetBox").inner_text().lower()
    print("   unknown sheet:", us.replace("\n"," | "))
    ck("an unknown villa offers nothing to complete",
       "villa done" not in us and "guest at breakfast" not in us and "departed" not in us)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)    # a vacant villa opens like any other, but offers no work to do
    pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].find(b=>b.className.includes('vac')).click()")
    pg.wait_for_timeout(200)
    vs = pg.locator("#sheetBox").inner_text().lower()
    print("   vacant sheet:", vs.replace("\n"," | "))
    ck("vacant tile opens its sheet", pg.evaluate("()=>ov.className").endswith("show"))
    ck("vacant sheet offers no cleaning actions",
       "villa done" not in vs and "guest at breakfast" not in vs)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(150)
    # clean room sheet has departed option; svc doesn't
    tile(pg,1).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room1 sheet:", repr(sh)[:220])
    sh=sh.lower()
    ck("clean sheet: done + breakfast + departed", "villa done" in sh and "guest at breakfast" in sh and "guest departed" in sh)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    tile(pg,2).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room2 sheet:", repr(sh)[:220])
    sh=sh.lower()
    ck("service sheet: no departed option, shows seated info + clear", "guest departed" not in sh and "seated at breakfast" in sh and "clear breakfast" in sh)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    # mark room1 done
    tile(pg,1).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Villa done").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Yes - done").click(); pg.wait_for_timeout(300)
    w=[x for x in WRITES if re.search(r"/hk/"+today+r"/1\.json",x["u"])]
    ck("PATCH done for room1", len(w)==1 and "done" in json.loads(w[0]["b"]))
    ck("room1 tile green, done count 2, sheet closed",
       pg.evaluate("()=>({c:nDone.textContent,cls:[...document.querySelectorAll('#grid .tile')].find(b=>b.querySelector('.rn').textContent==='1').className,ov:ov.className})")=={"c":"2","cls":"tile done","ov":"ov"})
    # breakfast stamp on a villa that has a job. Villa 2 is a service; 3 and 6
    # have no booking data so they are unknown and offer no cleaning actions.
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn",has_text="Clear breakfast").click(); pg.wait_for_timeout(200)
    pg.evaluate("()=>[...document.querySelectorAll('.pbtn')].find(x=>/yes/i.test(x.textContent)).click()")
    pg.wait_for_timeout(250)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn",has_text="Guest at breakfast").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn",has_text="10 min ago").click(); pg.wait_for_timeout(300)
    w=[x for x in WRITES if re.search(r"/hk/"+today+r"/2\.json",x["u"]) and "bfast" in x["b"] and "null" not in x["b"]]
    okb=False
    if w:
        ts=json.loads(w[0]["b"]).get("bfast",""); t3=datetime.datetime.fromisoformat(ts.replace("Z","+00:00"))
        okb=8<= (now.astimezone(datetime.timezone.utc)-t3.astimezone(datetime.timezone.utc)).total_seconds()/60 <=12
    ck("PATCH bfast ~10m ago", okb)
    ck("villa2 amber ~10m", "bfast" in pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].find(b=>b.querySelector('.rn').textContent==='2').className"))
    # rollback on rejection
    STATE["fail"]=True
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Villa done").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Yes - done").click(); pg.wait_for_timeout(400)
    ck("rejected write: error shown, sheet stays", "tell the manager" in pg.locator("#perr").inner_text())
    ck("rejected write rolled back", "done" not in pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].find(b=>b.querySelector('.rn').textContent==='2').className"))
    STATE["fail"]=False
    pg.locator(".pbtn.ghost",has_text="Back").click(); pg.wait_for_timeout(100)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    # undo done on room7
    tile(pg,7).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.warn",has_text="Undo done").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.warn",has_text="Yes - not done").click(); pg.wait_for_timeout(300)
    w=[x for x in WRITES if re.search(r"/hk/"+today+r"/7\.json",x["u"])]
    ck("PATCH done:null for room7", len(w)==1 and json.loads(w[0]["b"])["done"] is None)
    ck("done count back to 1", pg.evaluate("()=>nDone.textContent")=="1")

    # a manager can set the morning's job by hand, and it beats the dates
    t11=pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                    ".find(x=>x.querySelector('.rn').textContent==='11');"
                    "return t? t.innerText.toLowerCase().replace(/\\n/g,' | ') : null;}")
    print("   villa 11 tile:", t11)
    ck("villa 11 shows as a clean because staff set it", t11 and "clean" in t11)
    WRITES.clear()
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(150)
    tile(pg,3).click(); pg.wait_for_timeout(250)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^to be cleaned$/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(250)
    print("   confirm sheet:", pg.locator("#sheetBox").inner_text().replace("\n"," | "))
    ck("setting the job asks to confirm first, like every other action",
       "yes - to be cleaned" in pg.locator("#sheetBox").inner_text().lower())
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/yes/i.test(x.textContent) && /clean/i.test(x.textContent)).click()")
    pg.wait_for_timeout(300)
    kw=[x for x in WRITES if "/hk/" in x["u"] and "/3.json" in x["u"]]
    print("   kind write:", kw[-1]["b"] if kw else None)
    ck("setting the job writes kind to that villa's hk record",
       kw and json.loads(kw[-1]["b"]).get("kind")=="clean")

    shot=pg.screenshot(full_page=True)
    open("/home/claude/nala/_p4_cleaners.png","wb").write(shot)
    pg.close()
    # gate: housekeeping login sees no menu
    pg=page("housekeeping@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1200)
    ck("housekeeping login: menu hidden", pg.evaluate("()=>getComputedStyle(navWrap).display")=="none")
    tile(pg,3).click(); pg.wait_for_timeout(300)
    hkSheet = pg.locator("#sheetBox").inner_text().lower()
    print("   housekeeping sheet:", hkSheet.replace("\n"," | "))
    ck("housekeeping login cannot change the job",
       "to be cleaned" not in hkSheet and "to be serviced" not in hkSheet
       and "job for today" not in hkSheet)
    pg.close(); b.close()
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
