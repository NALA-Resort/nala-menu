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
 "8":{"name":"Owen","departs":today,"arrives":today},   # departed, arrival today
 "12":{"name":"Sam","departs":today},          # departed, nobody arriving
 "14":{"name":"Iris","departs":plus(3)},       # a service, seated later than villa 2
}
bf=(now-datetime.timedelta(minutes=12)).isoformat()
bf2=(now-datetime.timedelta(minutes=4)).isoformat()
bf16=(now-datetime.timedelta(minutes=17)).isoformat()   # amber band
bf24=(now-datetime.timedelta(minutes=24)).isoformat()   # red band
hk={"7":{"done":now.strftime("%Y-%m-%dT%H:%M:%S")+".123456"},"2":{"bfast":bf},
    "11":{"kind":"clean"}, "8":{"departed":True}, "12":{"departed":True},
    "14":{"bfast":bf2}, "6":{"bfast":bf16}, "9":{"bfast":bf24}}
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
    ck("cleans 5 services 2 done 1", hd["c"]=="5" and hd["s"]=="2" and hd["dn"]=="1")
    ck("management login sees menu", hd["nav"]=="block")
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    ck("menu opens on tap", pg.evaluate("()=>navDrop.classList.contains('open')"))
    pg.locator(".stats").click(); pg.wait_for_timeout(150)
    t=pg.evaluate("""()=>{const o={};document.querySelectorAll('#grid .tile').forEach(b=>{
      o[b.querySelector('.rn').textContent]={cls:b.className,txt:b.textContent};});return o;}""")
    ck("room1 Clean occupied", "Clean" in t["1"]["txt"] and "Occupied" in t["1"]["txt"])
    ordr=pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].map(b=>b.querySelector('.rn').textContent)")
    print("   tile order:", ordr)
    # services, then cleans, then finished work, then unknown, then vacant
    # services by how long the guest has been seated (villa 2 at 12m before
    # villa 14 at 4m), then cleans: departed with an arrival today (8),
    # departed (12), then the rest; finished (7) sinks; vacant (5) last
    ck("services lead, seated longest first", ordr[0]=="2" and ordr[1]=="14")
    ck("cleans: arrival today, then departed, then the rest",
       ordr[2]=="8" and ordr[3]=="12" and ordr[4:6]==["1","11"])
    ck("finished sinks below outstanding, vacant last",
       ordr[6]=="7" and ordr[-1]=="5")

    warn=pg.evaluate("""()=>{const g=n=>{const t=[...document.querySelectorAll('.tile')]
        .find(x=>x.querySelector('.rn').textContent===n);
      const b=t?t.querySelector('.sub b'):null;
      return b? {t:b.textContent, cls:b.className, col:getComputedStyle(b).color} : null;};
      return {twelveMin:g('2'), fourMin:g('14'), amber:g('6'), red:g('9')};}""")
    print("   breakfast timers:", warn)
    ck("a guest seated under 15 minutes is not warned yet", warn["fourMin"]["cls"]=="el")
    ck("12 minutes is not yet amber", warn["twelveMin"]["cls"]=="el")
    ck("17 minutes turns amber", "soon" in warn["amber"]["cls"])
    ck("24 minutes turns red", "late" in warn["red"]["cls"]
       and warn["red"]["col"]=="rgb(168, 50, 30)")
    chips=pg.evaluate("""()=>{const g=n=>[...document.querySelectorAll('#grid .tile')]
      .find(b=>b.querySelector('.rn').textContent===n).querySelector('.chip');
      const c=n=>{const e=g(n),s=getComputedStyle(e);return {bg:s.backgroundColor,fg:s.color,t:e.textContent};};
      return {clean:c('1'),svc:c('2')};}""")
    print("   chips:", chips)
    ck("Clean badge solid ink, Service badge unfilled",
       chips["clean"]["bg"]=="rgb(28, 28, 26)" and chips["svc"]["bg"]=="rgba(0, 0, 0, 0)"
       and chips["clean"]["fg"]!=chips["svc"]["fg"])
    ck("room7 done green with time (6-digit ISO)", "done" in t["7"]["cls"] and re.search(r'Done \d{2}:\d{2}',t["7"]["txt"]))
    ck("villa2 ready to service, with elapsed",
       "ready-svc" in t["2"]["cls"] and re.search(r'B.fast 1[12]m',t["2"]["txt"]))
    ck("room5 vacant faded", "vac" in t["5"]["cls"])
    ck("villa3 unknown, one label only",
       "Unknown" in t["3"]["txt"] and "Verify" not in t["3"]["txt"]
       and "Occupancy" not in t["3"]["txt"])

    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,3).click(); pg.wait_for_timeout(250)
    us = pg.locator("#sheetBox").inner_text().lower()
    print("   unknown sheet:", us.replace("\n"," | "))
    ck("an unknown villa offers nothing to complete",
       "mark as clean" not in us and "guest at breakfast" not in us and "departed" not in us)
    ck("an unknown villa can be set to any of the three jobs",
       "to be cleaned" in us and "to be serviced" in us and "mark as vacant" in us)
    ck("unknown is grey, not an alarm",
       "rgb(153, 153, 144)" in pg.evaluate(
         "()=>{const c=[...document.querySelectorAll('.tile .chip.ver')][0];"
         "return c? getComputedStyle(c).color+' '+getComputedStyle(c).borderColor : '';}"))

    # a vacant villa opens like any other, but offers no work to do
    pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].find(b=>b.className.includes('vac')).click()")
    pg.wait_for_timeout(200)
    vs = pg.locator("#sheetBox").inner_text().lower()
    print("   vacant sheet:", vs.replace("\n"," | "))
    ck("vacant tile opens its sheet", pg.evaluate("()=>ov.className").endswith("show"))
    ck("vacant sheet offers no cleaning actions",
       "mark as clean" not in vs and "guest at breakfast" not in vs)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(150)
    # clean room sheet has departed option; svc doesn't
    tile(pg,1).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room1 sheet:", repr(sh)[:220])
    sh=sh.lower()
    ck("clean sheet: done + breakfast + departed", "mark as cleaned" in sh and "guest at breakfast" in sh and "guest departed" in sh)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    tile(pg,2).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room2 sheet:", repr(sh)[:220])
    sh=sh.lower()
    ck("service sheet: no departed option, shows seated info + clear", "guest departed" not in sh and "seated at breakfast" in sh and "clear breakfast" in sh)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    # mark room1 done
    tile(pg,1).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Mark as").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Yes -").click(); pg.wait_for_timeout(300)
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
    ck("villa2 ready to service ~10m", "ready-svc" in pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].find(b=>b.querySelector('.rn').textContent==='2').className"))
    # rollback on rejection
    STATE["fail"]=True
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Mark as").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Yes -").click(); pg.wait_for_timeout(400)
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

    # setting a job must show on the tile at once, without a refresh
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,6).click(); pg.wait_for_timeout(220)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^to be cleaned$/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/yes/i.test(x.textContent) && /clean/i.test(x.textContent)).click()")
    pg.wait_for_timeout(350)
    live = pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                       ".find(x=>x.querySelector('.rn').textContent==='6');"
                       "return t.innerText.toLowerCase().replace(/\\n/g,' | ');}")
    print("   villa 6 right after setting:", live)
    ck("the tile changes as soon as the job is set, no refresh needed",
       "clean" in live and "unknown" not in live)

    tile(pg,6).click(); pg.wait_for_timeout(200)
    ck("the completion button names the job", "mark as cleaned" in pg.locator("#sheetBox").inner_text().lower())
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')].find(x=>/mark as/i.test(x.textContent)).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')].find(x=>/^yes/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(350)
    fin = pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                      ".find(x=>x.querySelector('.rn').textContent==='6');"
                      "return t.innerText.toLowerCase().replace(/\\n/g,' | ');}")
    print("   villa 6 once finished:", fin)
    ck("a finished villa reads in the past tense", "cleaned" in fin)

    cols=pg.evaluate("""()=>{const g=n=>{const t=[...document.querySelectorAll('.tile')]
        .find(x=>x.querySelector('.rn').textContent===n);
      return t? {cls:t.className, bg:getComputedStyle(t).backgroundColor} : null;};
      return {finished:g('6'), readySvc:g('2')};}""")
    print("   colours:", cols)
    ck("a finished villa carries no job colour",
       "done" in cols["finished"]["cls"] and cols["finished"]["bg"]!=cols["readySvc"]["bg"])
    ck("a finished villa shows a tick beside the past-tense word",
       pg.evaluate("()=>!!document.querySelector('.tile.done .dtick')"))
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)

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
