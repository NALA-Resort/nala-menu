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
    "11":{"kind":"clean"}, "17":{"kind":"pre"}, "13":{"kind":"pre","done":now.isoformat()}, "8":{"departed":True}, "12":{"departed":True},
    "14":{"bfast":bf2}, "6":{"bfast":bf16}, "9":{"bfast":bf24}}
staff={"staff@nalaresort,com,au":{"name":"Admin","role":"admin"},
       "housekeeping@nalaresort,com,au":{"name":"Housekeeping","role":"housekeeping"},
       "chef@nalaresort,com,au":{"name":"Chef","role":"chef"},
       "waiter@nalaresort,com,au":{"name":"Waiter","role":"waiter"},
       "482913@staff,nala":{"name":"NALA Sync","role":"sync"}}
prevHk={"16":{"pushed":(now-datetime.timedelta(days=1)).isoformat()}}
def fb(route,request):
    u=request.url; m=request.method
    if m=="PATCH":
        WRITES.append({"u":u,"b":request.post_data})
        if STATE["fail"]: route.fulfill(status=401,body="no"); return
        route.fulfill(status=200,content_type="application/json",body=request.post_data); return
    body="null"
    if "/staff" in u: body=json.dumps(staff)
    elif "/responses/" in u: body=json.dumps(responses)
    elif "/manual/" in u: body=json.dumps(manual)
    elif "/roomguests/"+today in u: body=json.dumps(roomguests)
    elif "/roomguests/" in u: body="null"
    elif "/hk/"+today in u: body=json.dumps(hk)
    elif "/hk/" in u: body=json.dumps(prevHk)
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
    pg=page("staff@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    hd=pg.evaluate("()=>({k:'n/a',d:title.textContent,c:nClean.textContent,s:nSvc.textContent,dn:nDone.textContent,nav:getComputedStyle(navWrap).display})")
    ck("header row present", pg.evaluate("()=>!!document.querySelector('.daterow .navwrap')"))
    ck("date format with year", bool(re.match(r'^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) \d{1,2}(st|nd|rd|th) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$',hd["d"])))
    # villa 11 is a staff-set clean, so cleans is one higher than the dates imply
    ck("cleans 6 services 2 done 2", hd["c"]=="6" and hd["s"]=="2" and hd["dn"]=="2")
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
    # villa 16 was pushed yesterday, so it arrives today already departed
    ck("cleans: arrival today, then departed (16 pushed in), then the rest",
       ordr[2]=="8" and ordr[3:5]==["12","16"] and ordr[5:7]==["1","11"])
    # villa 17 is a pre-arrival: after the cleans, before the finished villa 7
    ck("a pre-arrival sits after the cleans and before finished work",
       ordr[7]=="17" and ordr[9]=="7")
    ck("finished sinks below outstanding, vacant last", ordr[-1]=="5")

    warn=pg.evaluate("""()=>{const g=n=>{const t=[...document.querySelectorAll('.tile')]
        .find(x=>x.querySelector('.rn').textContent===n);
      const b=t?t.querySelector('.sub b'):null;
      return b? {t:b.textContent, cls:b.className, col:getComputedStyle(b).color} : null;};
      return {twelveMin:g('2'), fourMin:g('14'), amber:g('6'), red:g('9')};}""")
    print("   breakfast timers:", warn)
    # Four bands, and the first one is the point of the exercise: a villa turned
    # around inside ten minutes is the thing going right, and it used to read
    # exactly like one nobody had touched.
    ck("4 minutes is green, because that is a villa being turned around fast",
       "fresh" in warn["fourMin"]["cls"] and warn["fourMin"]["col"]=="rgb(78, 107, 75)")
    ck("12 minutes has dropped out of green", "fresh" not in warn["twelveMin"]["cls"])
    ck("and is not amber yet either",
       "soon" not in warn["twelveMin"]["cls"] and "late" not in warn["twelveMin"]["cls"])
    ck("17 minutes turns amber", "soon" in warn["amber"]["cls"])
    ck("24 minutes turns red", "late" in warn["red"]["cls"]
       and warn["red"]["col"]=="rgb(168, 50, 30)")
    ck("no tile carries two bands at once", pg.evaluate(
       "()=>[...document.querySelectorAll('.tile .sub b')].every(b=>"
       "['fresh','soon','late'].filter(c=>b.classList.contains(c)).length<=1)"))
    chips=pg.evaluate("""()=>{const g=n=>[...document.querySelectorAll('#grid .tile')]
      .find(b=>b.querySelector('.rn').textContent===n).querySelector('.chip');
      const c=n=>{const e=g(n),s=getComputedStyle(e);return {bg:s.backgroundColor,fg:s.color,t:e.textContent};};
      return {clean:c('1'),svc:c('2')};}""")
    print("   chips:", chips)
    ck("Clean badge solid ink, Service badge unfilled",
       chips["clean"]["bg"]=="rgb(28, 28, 26)" and chips["svc"]["bg"]=="rgba(0, 0, 0, 0)"
       and chips["clean"]["fg"]!=chips["svc"]["fg"])
    ck("room7 done green with time (6-digit ISO)", "done" in t["7"]["cls"] and re.search(r'Done \d{2}:\d{2}',t["7"]["txt"]))
    ck("villa2 ready to service, with elapsed since noticed",
       "ready-svc" in t["2"]["cls"] and re.search(r'Available 1[12]m',t["2"]["txt"]))
    ck("room5 vacant faded", "vac" in t["5"]["cls"])
    ck("villa3 unknown, one label only",
       "Unknown" in t["3"]["txt"] and "Verify" not in t["3"]["txt"]
       and "Occupancy" not in t["3"]["txt"])

    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,3).click(); pg.wait_for_timeout(250)
    us = pg.locator("#sheetBox").inner_text().lower()
    print("   unknown sheet:", us.replace("\n"," | "))
    ck("an unknown villa offers nothing to complete",
       "mark as clean" not in us and "possibly available" not in us and "departed" not in us)
    ck("an unknown villa can be set to any of the three jobs",
       "to be cleaned" in us and "to be serviced" in us and "mark as empty" in us)
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
       "mark as clean" not in vs and "possibly available" not in vs)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(150)
    # clean room sheet has departed option; svc doesn't
    tile(pg,1).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room1 sheet:", repr(sh)[:220])
    sh=sh.lower()
    # a clean is decided by departure, not by someone glancing in
    ck("clean sheet: done + departed, and no availability mark",
       "mark as cleaned" in sh and "guest departed" in sh
       and "possibly available" not in sh)
    pg.locator(".pbtn.ghost",has_text="Close").click()
    tile(pg,2).click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheetBox").inner_text()
    print("   room2 sheet:", repr(sh)[:220])
    sh=sh.lower()
    ck("service sheet: no departed option, shows the note and a clear",
       "guest departed" not in sh and "marked available" in sh and "clear" in sh)

    # an existing mark stays clearable whatever the villa's job becomes
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(200)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^to be cleaned$/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^yes/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(400)
    tile(pg,2).click(); pg.wait_for_timeout(220)
    st2 = pg.locator("#sheetBox").inner_text().lower()
    print("   villa 2 once switched to a clean:", st2.replace("\n"," | "))
    ck("a stale availability mark can still be cleared on a clean",
       "marked available" in st2 and "clear" in st2
       and "possibly available" not in st2)
    # put villa 2 back to a service for the checks that follow
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/use booking dates/i.test(x.textContent)).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^yes/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(400)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    # mark room1 done
    tile(pg,1).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Mark as").click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn.solid",has_text="Yes -").click(); pg.wait_for_timeout(300)
    w=[x for x in WRITES if re.search(r"/hk/"+today+r"/1\.json",x["u"])]
    ck("PATCH done for room1", len(w)==1 and "done" in json.loads(w[0]["b"]))
    ck("room1 tile green, done count 2, sheet closed",
       pg.evaluate("()=>({c:nDone.textContent,cls:[...document.querySelectorAll('#grid .tile')].find(b=>b.querySelector('.rn').textContent==='1').className,ov:ov.className})")=={"c":"3","cls":"tile done","ov":"ov"})
    # breakfast stamp on a villa that has a job. Villa 2 is a service; 3 and 6
    # have no booking data so they are unknown and offer no cleaning actions.
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn",has_text="Clear").click(); pg.wait_for_timeout(200)
    pg.evaluate("()=>[...document.querySelectorAll('.pbtn')].find(x=>/yes/i.test(x.textContent)).click()")
    pg.wait_for_timeout(250)
    tile(pg,2).click(); pg.wait_for_timeout(150)
    pg.locator(".pbtn",has_text="Possibly available").click(); pg.wait_for_timeout(150)
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
    ck("done count back to 2", pg.evaluate("()=>nDone.textContent")=="2")

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

    # multi-select: only undecided villas, and one decision applies to all
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    pg.locator("#selToggle").click(); pg.wait_for_timeout(200)
    ck("toggle switches to Cancel with nothing picked",
       pg.locator("#selToggle").inner_text().strip().lower()=="cancel")
    picks=pg.evaluate("""()=>{const sel=[...document.querySelectorAll('.tile.selectable')]
        .map(t=>t.querySelector('.rn').textContent);
      const notSel=[...document.querySelectorAll('.tile:not(.selectable)')]
        .map(t=>t.querySelector('.rn').textContent);
      return {selectable:sel, blocked:notSel.slice(0,3)};}""")
    print("   selectable:", picks)
    ck("only undecided villas can be selected", len(picks["selectable"])>1)
    pg.evaluate("""()=>{const t=[...document.querySelectorAll('.tile.selectable')];
      t[0].click(); t[1].click();}""")
    pg.wait_for_timeout(200)
    ck("toggle switches to Options once villas are picked",
       pg.locator("#selToggle").inner_text().strip().lower()=="options")
    WRITES.clear()
    pg.locator("#selToggle").click(); pg.wait_for_timeout(250)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^to be cleaned$/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')]"
                ".find(x=>/^yes/i.test(x.textContent.trim())).click()")
    pg.wait_for_timeout(500)
    kinds=[x for x in WRITES if "/hk/" in x["u"] and "kind" in x["b"]]
    print("   multi writes:", [x["u"].split("/")[-1] for x in kinds])
    ck("one decision writes to every villa picked", len(kinds)==2)
    ck("the board leaves select mode afterwards",
       pg.locator("#selToggle").inner_text().strip().lower()=="select multiple")

    # a villa pushed yesterday arrives today as a clean, already departed
    t16=pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                    ".find(x=>x.querySelector('.rn').textContent==='16');"
                    "return {txt:t.innerText.toLowerCase().replace(/\\n/g,' | '), cls:t.className};}")
    print("   villa 16 (pushed yesterday):", t16)
    ck("a pushed villa returns tomorrow as a departed clean",
       "clean" in t16["txt"] and "departed" in t16["txt"] and "ready-clean" in t16["cls"])

    # villa 16 is departed because it was pushed in, not because of a mark
    tile(pg,16).click(); pg.wait_for_timeout(250)
    pin = pg.locator("#sheetBox").inner_text().lower()
    print("   pushed-in villa sheet:", pin.replace("\n"," | "))
    ck("a pushed-in villa is not offered a departure mark",
       "guest departed" not in pin and "undo departed" not in pin)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    # villa 11 is a clean nobody has marked departed, so it still offers one,
    # and villa 12 was marked by hand, so it offers the undo
    tile(pg,11).click(); pg.wait_for_timeout(250)
    ck("an unmarked clean is still offered a departure mark",
       "guest departed" in pg.locator("#sheetBox").inner_text().lower())
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,12).click(); pg.wait_for_timeout(250)
    ck("a hand-marked departure can be undone",
       "undo departed" in pg.locator("#sheetBox").inner_text().lower())
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    # pushing today: only offered where there is no arrival, and reads purple
    WRITES.clear()
    tile(pg,12).click(); pg.wait_for_timeout(250)
    ps = pg.locator("#sheetBox").inner_text().lower()
    ck("a clean with no arrival today can be pushed", "push villa" in ps)

    ck("a departed villa is not offered breakfast", "possibly available" not in ps)
    ck("a departed villa cannot be set to a service", "to be serviced" not in ps)
    ck("a departed villa cannot be marked empty", "mark as empty" not in ps)

    # pre-arrival: a villa nobody checks out of, but someone checks into
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    t17=pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                    ".find(x=>x.querySelector('.rn').textContent==='17');"
                    "return {txt:t.innerText.toLowerCase().replace(/\\n/g,' | '), cls:t.className};}")
    print("   villa 17 pre-arrival:", t17)
    ck("a pre-arrival reads Pre-arrival, arriving today, and takes no colour",
       "pre-arrival" in t17["txt"] and "arriving today" in t17["txt"]
       and "ready-" not in t17["cls"])
    tile(pg,17).click(); pg.wait_for_timeout(250)
    pre = pg.locator("#sheetBox").inner_text().lower()
    print("   pre-arrival sheet:", pre.replace("\n"," | "))
    ck("its completion button names the job", "mark as pre-arrived" in pre)

    ck("a pre-arrival offers only its own job, back to unknown, and close",
       "possibly available" not in pre and "to be cleaned" not in pre
       and "to be serviced" not in pre and "mark as empty" not in pre
       and "push villa" not in pre and "back to unknown" in pre)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,13).click(); pg.wait_for_timeout(250)
    predone = pg.locator("#sheetBox").inner_text().lower()
    print("   pre-arrived sheet:", predone.replace("\n"," | "))
    ck("a finished pre-arrival offers only undo, back to unknown, and close",
       "undo done" in predone and "back to unknown" in predone
       and "mark as pre-arrived" not in predone and "to be cleaned" not in predone
       and "mark as empty" not in predone)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    # and it can only be set from an unknown or vacant villa, never a service
    tile(pg,10).click(); pg.wait_for_timeout(250)
    ck("an unknown villa can be set as a pre-arrival",
       "set as pre-arrival" in pg.locator("#sheetBox").inner_text().lower())
    ck("a pre-arrival is not offered breakfast - nobody is there yet",
       "possibly available" not in pre)
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,2).click(); pg.wait_for_timeout(250)
    ck("a service cannot be set as a pre-arrival",
       "set as pre-arrival" not in pg.locator("#sheetBox").inner_text().lower())
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)
    tile(pg,12).click(); pg.wait_for_timeout(250)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')].find(x=>/push villa/i.test(x.textContent)).click()")
    pg.wait_for_timeout(180)
    pg.evaluate("()=>[...document.querySelectorAll('#sheetBox .pbtn')].find(x=>/yes - push/i.test(x.textContent)).click()")
    pg.wait_for_timeout(400)
    pw=[x for x in WRITES if "/12.json" in x["u"] and "pushed" in x["b"]]
    ck("pushing writes to that villa", len(pw)==1)
    t12=pg.evaluate("()=>{const t=[...document.querySelectorAll('.tile')]"
                    ".find(x=>x.querySelector('.rn').textContent==='12');"
                    "return {txt:t.innerText.toLowerCase(), cls:t.className,"
                    "col:getComputedStyle(t.querySelector('.chip')).color};}")
    print("   villa 12 once pushed:", t12)
    ck("a pushed villa reads Pushed, in purple, styled like finished work",
       "pushed" in t12["txt"] and "pushed" in t12["cls"] and "done" in t12["cls"]
       and t12["col"]=="rgb(107, 78, 155)")

    ordr2=pg.evaluate("()=>[...document.querySelectorAll('#grid .tile')].map(b=>b.querySelector('.rn').textContent)")
    print("   order after pushing 12:", ordr2)
    ck("a villa pushed today sinks below the finished ones",
       ordr2.index("12") > ordr2.index("7"))
    # villa 3 was decided earlier in this suite, so villa 10 is the unknown one
    ck("but stays above unknown and vacant",
       ordr2.index("12") < ordr2.index("10") and ordr2.index("12") < ordr2.index("5"))
    ck("a villa with an arrival today is not offered a push",
       "push villa" not in (tile(pg,8).click() or pg.wait_for_timeout(250) or
                            pg.locator("#sheetBox").inner_text().lower()))
    pg.evaluate("()=>closeSheet()"); pg.wait_for_timeout(120)

    shot=pg.screenshot(full_page=True)
    open("/home/claude/nala/_p4_cleaners.png","wb").write(shot)
    pg.close()
    # gate: the housekeeping login gets a menu, because Sign out lives in it
    pg=page("housekeeping@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1200)
    ck("housekeeping login: menu present, so there is a way to sign out",
       pg.evaluate("()=>getComputedStyle(navWrap).display")!="none")
    hknav=pg.evaluate("""()=>[].filter.call(document.querySelectorAll('#navDrop a'),
        a=>getComputedStyle(a).display!=='none').map(a=>a.textContent.trim())""")
    ck("housekeeping is offered no board it would be refused, but can sign out",
       "Sign out" in hknav and "Reservations" not in hknav and "Reservations Sheet" not in hknav)
    print("   housekeeping menu:", hknav)
    tile(pg,3).click(); pg.wait_for_timeout(300)
    hkSheet = pg.locator("#sheetBox").inner_text().lower()
    print("   housekeeping sheet:", hkSheet.replace("\n"," | "))
    ck("housekeeping login cannot change the job",
       "to be cleaned" not in hkSheet and "to be serviced" not in hkSheet
       and "admin options" not in hkSheet)

    print("   housekeeping sees:", hkSheet.replace("\n"," | "))
    ck("housekeeping sees no job controls at all, on any villa state",
       all(w not in hkSheet for w in
           ["to be cleaned","to be serviced","set as pre-arrival",
            "mark as empty","use booking dates","back to unknown"]))
    pg.close()

    # ---- roles: the helper, straight out of the shipped nala-shared.js ----
    pg=page("staff@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1200)

    # every dot becomes a comma, not just the first: a single replace would
    # key staff@nalaresort.com.au as staff@nalaresort,com.au and match nothing
    ck("emailKey converts every dot",
       pg.evaluate("()=>emailKey('Staff@NalaResort.Com.AU')")=="staff@nalaresort,com,au")

    roles=pg.evaluate("""()=>({
      staff: roleOf({email:'staff@nalaresort.com.au'}),
      hk:    roleOf({email:'HOUSEKEEPING@nalaresort.com.au'}),
      chef:  roleOf({email:'chef@nalaresort.com.au'}),
      hkm:   roleOf({email:'housekeeping.maria@nalaresort.com.au'}),
      ben:   roleOf({email:'ben@nalaresort.com.au'}),
      empty: roleOf(null)})""")
    ck("roleOf reads the record, not the address",
       roles["staff"]=="admin" and roles["hk"]=="housekeeping" and roles["chef"]=="chef")
    ck("roleOf is case insensitive on the address", roles["hk"]=="housekeeping")
    # the two failures the old prefix check made, named in ROLES.md
    ck("housekeeping.maria@ is not silently a cleaner", roles["hkm"] is None)
    ck("an unseeded address is not silently management", roles["ben"] is None)
    ck("no user is no role", roles["empty"] is None)

    # The PMS layer. Mews is the authority on who is in a villa and when they
    # leave; roomguests only knows what a guest typed after opening a link.
    mews = pg.evaluate("""()=>{
      const rg = { '1': {name:'Old Name', departs:'2026-01-01'},
                   '4': {name:'Link Guest', departs:'2026-09-20'} };
      const stays = {
        '1': {id:'r1', first:'Robyn', last:'Williams', phone:'0409',
              arrive:'2026-08-19', depart:'2026-08-27', adults:2},
        '2': {id:'r2', first:'New', last:'Villa', depart:'2026-08-30'},
        '9': 'r9-bare-id-from-the-older-shape'
      };
      const o = overlayStays(rg, stays);
      return { one:o['1'], two:o['2'], four:o['4'], nine:o['9'],
               noStays: overlayStays(rg, null)['1'] };
    }""")
    ck("the PMS replaces a stale departure date, which is what hkClassify reads",
       mews["one"]["departs"] == "2026-08-27")
    ck("and the PMS name wins over the one a guest typed",
       mews["one"]["name"] == "Robyn Williams")
    ck("a villa with no roomguests record at all still appears",
       mews["two"]["name"] == "New Villa")
    ck("a villa the PMS says nothing about is left alone",
       mews["four"]["name"] == "Link Guest")
    # /stays held a bare booking id before the summary was moved into it
    ck("an entry in the older shape is ignored rather than crashing",
       mews["nine"] is None)
    ck("no stays at all leaves roomguests exactly as it was",
       mews["noStays"]["name"] == "Old Name")

    # "we know who is in villa 4" is not "villa 4 has replied to us". Marking a
    # synced booking as link-opened put the icon on every night of every stay.
    marks = pg.evaluate("""()=>{
      const o = overlayStays(
        { '4': {name:'Clicked', departs:'2026-09-20'} },
        { '4': {id:'r4', first:'Clicked', last:'Guest', depart:'2026-09-20'},
          '5': {id:'r5', first:'Never', last:'Clicked', depart:'2026-09-21'} });
      return { four: isMewsOnly(o['4']), five: isMewsOnly(o['5']),
               none: isMewsOnly(null) };
    }""")
    ck("a booking known only from the PMS is not treated as link opened",
       marks["five"] is True)
    ck("a guest who did open their link keeps that fact after the overlay",
       marks["four"] is False)
    ck("an empty villa is neither", marks["none"] is False)

    # A guest moved after opening their link was left behind in the old villa,
    # because roomguests keeps a record until its own departure date passes.
    # Same person in two villas at once: the bug the Worker fixed on the /stays
    # side, reappearing one layer up.
    moved = pg.evaluate("""()=>{
      const rg = { '5': {name:'Jane Doe', phone:'0400000000', departs:'2026-08-25'},
                   '7': {name:'Someone Else', phone:'0411111111', departs:'2026-08-25'} };
      const stays = { '9': {id:'r1', first:'Jane', last:'Doe', phone:'+61400000000',
                            arrive:'2026-08-18', depart:'2026-08-25', adults:2} };
      const o = overlayStays(rg, stays);
      // matched on name alone, with no phone on either side
      const byName = overlayStays(
        { '3': {name:'Ann Brown', departs:'2026-08-25'} },
        { '8': {id:'r2', first:'Ann', last:'Brown', depart:'2026-08-25'} });
      // two genuine bookings that share a phone must both survive
      const shared = overlayStays({},
        { '2': {id:'a', first:'Sam', last:'Reed', phone:'0400', depart:'2026-08-25'},
          '6': {id:'b', first:'Sam', last:'Reed', phone:'0400', depart:'2026-08-25'} });
      return { five:o['5'], nine:o['9'], seven:o['7'],
               three:byName['3'], eight:byName['8'],
               sharedTwo:shared['2'], sharedSix:shared['6'] };
    }""")
    ck("a moved guest is gone from the villa they left",
       moved["five"] is None)
    ck("and present in the one the PMS says they are in",
       moved["nine"]["name"] == "Jane Doe")
    ck("an unrelated villa is untouched",
       moved["seven"]["name"] == "Someone Else")
    # +61400000000 and 0400000000 are one person
    ck("a phone written two ways still matches",
       moved["five"] is None)
    ck("a name match alone is enough when neither side has a phone",
       moved["three"] is None and moved["eight"]["name"] == "Ann Brown")
    ck("two PMS bookings sharing a phone both survive",
       moved["sharedTwo"] is not None and moved["sharedSix"] is not None)

    # The design said Mews wins on depart, over roomguests AND over the guest's
    # own answer. A response carries a copy of the dates from when the guest
    # replied, and that copy was winning, so a stay shortened in Mews still read
    # as a service on the departure day and the villa was never offered for
    # cleaning on the day it was vacated.
    prec = pg.evaluate("""()=>{
      const rg = overlayStays({}, { '5': {id:'r1', first:'Jane', last:'Doe',
                 phone:'0400', arrive:'2026-08-18', depart:'2026-08-22', adults:2} });
      const resp = { '0400': { name:'Jane Doe', room:'5', phone:'0400',
                     arrives:'2026-08-18', departs:'2026-08-25', status:'in',
                     pax:3, diets:['Nut allergy'], note:'window table',
                     at:'2026-08-18T10:00:00Z' } };
      const rec = roomRecord(5, resp, {}, rg);
      return { departs: rec.departs, pax: rec.pax, diets: rec.diets,
               note: rec.note, status: rec.status,
               job: hkClassify(rec, '2026-08-22', null) };
    }""")
    ck("a stay shortened in Mews beats the date the guest's reply carried",
       prec["departs"] == "2026-08-22")
    ck("so the villa is a clean on the day it is actually vacated",
       prec["job"] == "clean")
    ck("the dinner answer survives untouched: covers",
       prec["pax"] == 3)
    ck("dietaries", prec["diets"] == ["Nut allergy"])
    ck("notes and the dining status", prec["note"] == "window table" and
       prec["status"] == "in")

    # A guest who replied and was then moved left their answer on the old villa,
    # which held it open behind them.
    stray = pg.evaluate("""()=>{
      const rg = overlayStays({}, { '9': {id:'r1', first:'Jane', last:'Doe',
                 phone:'0400', arrive:'2026-08-18', depart:'2026-08-25'} });
      const resp = { '0400': { name:'Jane Doe', room:'5', phone:'0400',
                     status:'in', pax:2, at:'2026-08-18T10:00:00Z' } };
      return { old: roomRecord(5, resp, {}, rg),
               now: roomRecord(9, resp, {}, rg) };
    }""")
    ck("a response written from the old villa does not hold it open",
       stray["old"] is None)
    ck("and the villa the PMS names still reads the guest",
       stray["now"]["name"] == "Jane Doe")

    # Reception can see a villa is empty when Mews cannot, so a staff vacant is
    # allowed to contradict the PMS. It is stamped with the version it was
    # decided against, and dropped once Mews changes that booking.
    vac = pg.evaluate("""()=>{
      const mk = (upd) => overlayStays({}, { '5': {id:'r1', first:'Jane',
                 last:'Doe', depart:'2026-08-25', updated:upd} });
      const vacant = { status:'vacant', pax:0, room:'5', source:'manual',
                       pmsUpdated:'2026-08-16T10:00:00Z' };
      return {
        same:  roomRecord(5, {}, {'room-5':vacant}, mk('2026-08-16T10:00:00Z')),
        newer: roomRecord(5, {}, {'room-5':vacant}, mk('2026-08-17T09:00:00Z')),
        noPms: roomRecord(5, {}, {'room-5':{status:'vacant',pax:0,room:'5',
                                            source:'manual'}}, {}),
        fresh: vacantIsStale(vacant, {bookingId:'r1',
                                      pmsUpdated:'2026-08-16T10:00:00Z'})
      };
    }""")
    ck("a staff vacant holds while the booking is unchanged",
       vac["same"]["status"] == "vacant")
    ck("and is dropped once Mews changes that booking",
       vac["newer"]["status"] != "vacant")
    ck("a vacant on a villa the PMS knows nothing about is never stale",
       vac["noPms"]["status"] == "vacant")
    ck("vacantIsStale says no when the stamps agree", vac["fresh"] is False)


    # ── the one dinner cell ─────────────────────────────────────
    # One record per villa per night, replacing two that held the same fact:
    # /responses keyed by phone and /manual keyed by villa. Two cells is why
    # roomRecord needed precedence at all, and precedence is how two copies of
    # one fact quietly disagree.
    cell = pg.evaluate("""()=>{
      const rg = overlayStays({}, { '5': {id:'r1', first:'Jane', last:'Doe',
                 arrive:'2026-08-18', depart:'2026-08-22', adults:2} });
      const resp = { '0400': { name:'Jane Doe', room:'5', status:'out', pax:0,
                     at:'2026-08-18T09:00:00Z' } };
      const man  = { 'room-5': { status:'in', pax:9, room:'5', source:'manual' } };
      const din  = { '5': { status:'in', pax:3, diets:['Nut allergy'],
                     by:'staff', at:'2026-08-18T18:00:00Z' } };
      return {
        wins:    roomRecord(5, resp, man, rg, din),
        noCell:  roomRecord(5, resp, man, rg, {}),
        absent:  roomRecord(5, {}, {}, rg, {}),
        guestBy: roomRecord(5, {}, {}, rg, { '5': { status:'in', pax:2, by:'guest' } })
      };
    }""")
    ck("the cell wins outright over both older nodes",
       cell["wins"]["status"] == "in" and cell["wins"]["pax"] == 3)
    ck("and brings its dietaries with it, since it holds the whole answer",
       cell["wins"]["diets"] == ["Nut allergy"])
    ck("the guest's own facts still come from Mews above it",
       cell["wins"]["name"] == "Jane Doe")
    # And this is the argument for one cell, in one line. With no dinner cell
    # the fallback gives the RESPONSE, not the staff entry, because a staff
    # record only outranks a guest when it carries an override flag. I wrote
    # this test expecting the opposite, which is the point: nobody holds that
    # rule in their head correctly, including whoever wrote it.
    ck("with no cell, the older two still work while pages are moved across",
       cell["noCell"]["status"] == "out" and cell["noCell"]["pax"] == 0)
    ck("and no answer anywhere is still no answer",
       cell["absent"]["status"] is None)
    ck("a cell set by a guest reads the same as one set by staff",
       cell["guestBy"]["status"] == "in" and cell["guestBy"]["pax"] == 2)

    # Staff outrank a guest. This is the only precedence left in the app.
    lock = pg.evaluate("""()=>({
      staff: dinnerLocked({ status:'in', by:'staff' }),
      guest: dinnerLocked({ status:'in', by:'guest' }),
      none:  dinnerLocked(null)
    })""")
    ck("a cell set by staff is locked against the guest", lock["staff"] is True)
    ck("one set by a guest is not", lock["guest"] is False)
    ck("and an empty villa is not", lock["none"] is False)

    # A staff vacant on a PMS villa still expires when Mews changes the booking,
    # exactly as it did in the node this replaces.
    stale = pg.evaluate("""()=>{
      const mk = (upd) => overlayStays({}, { '5': {id:'r1', first:'Jane',
                 last:'Doe', depart:'2026-08-25', updated:upd} });
      const vac = { status:'vacant', pax:0, by:'staff',
                    pmsUpdated:'2026-08-16T10:00:00Z' };
      return { same:  roomRecord(5, {}, {}, mk('2026-08-16T10:00:00Z'), {'5':vac}),
               newer: roomRecord(5, {}, {}, mk('2026-08-17T09:00:00Z'), {'5':vac}) };
    }""")
    ck("a vacant in the cell holds while the booking is unchanged",
       stale["same"]["status"] == "vacant")
    ck("and is dropped once Mews changes that booking",
       stale["newer"]["status"] != "vacant")


    # The two printed sheets belong to another chat and cannot be edited here,
    # so they never learned to fetch the dinner cell. fetchStays picks it up
    # for the same date and roomRecord falls back to it, which is what keeps
    # screen and paper agreeing. Without this a villa booked on the board today
    # is missing from the chef's paper, and he has no way to know.
    fallback = pg.evaluate("""()=>{
      const rg = overlayStays({}, { '5': {id:'r1', first:'Jane', last:'Doe',
                 arrive:'2026-08-18', depart:'2026-08-22'} });
      DINNER_CELLS = { '5': { status:'in', pax:4, by:'staff' } };
      const withFallback = roomRecord(5, {}, {}, rg);
      const passedIn = roomRecord(5, {}, {}, rg, { '5': { status:'out', pax:0, by:'staff' } });
      DINNER_CELLS = {};
      return { withFallback: withFallback, passedIn: passedIn };
    }""")
    ck("a caller that fetched nothing still sees the cell",
       fallback["withFallback"]["status"] == "in" and fallback["withFallback"]["pax"] == 4)
    ck("and a caller that passed its own is not overridden by the fallback",
       fallback["passedIn"]["status"] == "out")


    # ── the moved guest, third home ─────────────────────────────
    # A guest answers dinner, Mews then moves them to another villa, and the
    # answer stays behind: the board shows a booking in an empty villa and
    # counts the covers twice. It cost an evening once and produced three Ben
    # Davidsons. /stays was fixed in the Worker and roomguests in overlayStays;
    # the dinner cell is the third place it can happen.
    moved = pg.evaluate("""()=>{
      const rg = overlayStays({}, { '9': {id:'b1', first:'Ben', last:'Davidson',
                 arrive:'2026-08-18', depart:'2026-08-22'} });
      const cells = { '5': { status:'in', pax:2, bookingId:'b1', by:'guest' },
                      '9': { status:'in', pax:2, bookingId:'b1', by:'guest' } };
      // no booking id at all: an external diner or a staff entry
      const anon  = { '5': { status:'in', pax:2, by:'staff' } };
      return {
        left:  roomRecord(5, {}, {}, rg, cells),
        now:   roomRecord(9, {}, {}, rg, cells),
        anon:  roomRecord(5, {}, {}, rg, anon),
        stale: dinnerElsewhere(cells, 5, rg),
        here:  dinnerElsewhere(cells, 9, rg),
        none:  dinnerElsewhere(anon, 5, rg)
      };
    }""")
    ck("the villa they left stops holding their booking",
       moved["left"] is None or moved["left"]["status"] is None)
    ck("and the villa Mews puts them in keeps it",
       moved["now"]["status"] == "in")
    ck("a cell with no booking id is never dropped, since Mews has no opinion",
       moved["anon"]["status"] == "in" and moved["none"] is False)
    ck("dinnerElsewhere says stale for the old villa", moved["stale"] is True)
    ck("and not for the new one", moved["here"] is False)


    # ── one party across several villas ─────────────────────────
    party = pg.evaluate("""()=>{
      const rg = overlayStays({}, {
        '2': {id:'j1', first:'Jane', last:'Smith', depart:'2026-08-22', groupId:'g1'},
        '3': {id:'j2', first:'Jane', last:'Smith', depart:'2026-08-22', groupId:'g1'},
        '7': {id:'k1', first:'Other', last:'Guest', depart:'2026-08-22', groupId:'g2'},
        '9': {id:'n1', first:'No',    last:'Group', depart:'2026-08-22'} });
      return { two: groupVillas(rg, '2'), three: groupVillas(rg, '3'),
               alone: groupVillas(rg, '7'), none: groupVillas(rg, '9'),
               carried: rg['2'].groupId };
    }""")
    ck("the group reaches the board record", party["carried"] == "g1")
    ck("a villa knows the others its party holds", party["two"] == ["3"])
    ck("from either side", party["three"] == ["2"])
    ck("a lone booking in a group of one has no others", party["alone"] == [])
    ck("and a booking with no group at all is never grouped", party["none"] == [])

    # The sync role is the Mews Worker's login. It is a real role, so roleOf
    # must return it rather than null, but it lands nowhere and grants nothing.
    sync=pg.evaluate("""()=>({
      role: roleOf({email:'482913@staff.nala'}),
      home: homeFor('sync'),
      caps: Object.keys(ROLE_GRANTS.sync||{}).length + (ROLE_GRANTS.sync||[]).length})""")
    ck("a sync record reads as the sync role, not as nothing", sync["role"]=="sync")
    ck("sync grants no capability at all", sync["caps"]==0)
    ck("sync lands on no page, so a human signing in as it is told, not looped",
       sync["home"] is None)

    # the matrix in ROLES.md, cell by cell
    M={"admin":       {"cleansBoard":1,"cleansMarks":1,"setJob":1,"resBoard":1,
                       "editBookings":1,"resSheet":1,"publishMenu":1,"manageStaff":1},
       "chef":        {"cleansBoard":0,"cleansMarks":0,"setJob":0,"resBoard":1,
                       "editBookings":0,"resSheet":1,"publishMenu":1,"manageStaff":0},
       "waiter":      {"cleansBoard":1,"cleansMarks":0,"setJob":0,"resBoard":1,
                       "editBookings":1,"resSheet":1,"publishMenu":0,"manageStaff":0},
       "housekeeping":{"cleansBoard":1,"cleansMarks":1,"setJob":0,"resBoard":0,
                       "editBookings":0,"resSheet":0,"publishMenu":0,"manageStaff":0},
       # the Mews sync Worker. Every cell zero, on purpose: its permission is
       # in the rules, not here, and a machine account must not gain a board
       # by someone adding a capability to a list and not thinking about it.
       "sync":        {"cleansBoard":0,"cleansMarks":0,"setJob":0,"resBoard":0,
                       "editBookings":0,"resSheet":0,"publishMenu":0,"manageStaff":0}}
    bad=[]
    for role,caps in M.items():
        for cap,want in caps.items():
            got=pg.evaluate("()=>can('%s','%s')"%(role,cap))
            if got!=bool(want): bad.append("%s/%s"%(role,cap))
    ck("can() matches the ROLES.md matrix in all 32 cells, wrong: "+str(bad), not bad)
    # the rename must not be the thing that locks the owner out
    ck("a record still saying 'staff' is read as admin",
       pg.evaluate("()=>can('staff','manageStaff')&&can('staff','setJob')"))
    ck("no record grants nothing", not pg.evaluate("()=>can(null,'resBoard')||can('typo','setJob')"))
    ck("admin is the FULL ACCESS role, not a middling one",
       pg.evaluate("()=>can('admin','manageStaff')&&can('admin','setJob')&&can('admin','editBookings')"))

    # ---- the matrix overriding the shipped defaults ----
    # The manager changing their mind in Settings. Only an explicit yes or no
    # counts: anything else and the shipped default stands, so a capability
    # added to the app next year is not switched off by a matrix written
    # before it existed.
    ck("a tick grants something the role did not ship with",
       pg.evaluate("""()=>{setPermissions({setJob:{housekeeping:true}});
                          const a=can('housekeeping','setJob');
                          setPermissions(null); return a===true;}"""))
    ck("and an untick takes away something it did",
       pg.evaluate("""()=>{setPermissions({cleansMarks:{housekeeping:false}});
                          const a=can('housekeeping','cleansMarks');
                          setPermissions(null); return a===false;}"""))
    ck("a role the matrix says nothing about keeps its default",
       pg.evaluate("""()=>{setPermissions({setJob:{housekeeping:true}});
                          const a=can('waiter','setJob'), b=can('waiter','resBoard');
                          setPermissions(null); return a===false&&b===true;}"""))
    ck("an action the matrix has never heard of keeps its default",
       pg.evaluate("""()=>{setPermissions({setJob:{housekeeping:true}});
                          const a=can('chef','publishMenu');
                          setPermissions(null); return a===true;}"""))
    ck("a value that is not a yes or a no is not an opinion",
       pg.evaluate("""()=>{setPermissions({resBoard:{chef:'maybe'}});
                          const a=can('chef','resBoard');
                          setPermissions(null); return a===true;}"""))
    # A stray false against admin, typed into the console at midnight, would
    # lock the only person who can undo it out of the page where it is undone.
    ck("the manager cannot be switched off by the matrix",
       pg.evaluate("""()=>{setPermissions({manageStaff:{admin:false},setJob:{admin:false}});
                          const a=can('admin','manageStaff')&&can('admin','setJob');
                          setPermissions(null); return a===true;}"""))
    ck("an empty matrix is the same as no matrix",
       pg.evaluate("""()=>{setPermissions({});
                          const a=can('housekeeping','cleansMarks')&&!can('housekeeping','resBoard');
                          setPermissions(null); return a===true;}"""))
    # The grid is drawn from these two lists, so what they contain is what a
    # manager can hand out. manageStaff being absent is the point: handing it
    # out is a second manager, not a permission, and it is done by changing a
    # role in the People list where it is visible.
    ck("manageStaff is not in the grid",
       pg.evaluate("()=>PERM_ACTIONS.every(a=>a[0]!=='manageStaff')"))
    ck("nor is admin a column, nor sync",
       pg.evaluate("()=>PERM_ROLES.indexOf('admin')<0&&PERM_ROLES.indexOf('sync')<0"))
    ck("every other capability is offered",
       pg.evaluate("""()=>ROLE_GRANTS.admin.filter(x=>x!=='manageStaff')
                        .every(x=>PERM_ACTIONS.some(a=>a[0]===x))"""))
    ck("and every action in the grid is a real one",
       pg.evaluate("()=>PERM_ACTIONS.every(a=>ROLE_GRANTS.admin.indexOf(a[0])>-1)"))
    ck("the defaults are still readable on their own",
       pg.evaluate("""()=>grantedByDefault('housekeeping','cleansMarks')===true
                        && grantedByDefault('housekeeping','setJob')===false"""))
    pg.close()

    # ---- the gate on the page ----
    # a chef has a board of their own, so they are sent to it rather than
    # refused: a refusal is the wrong answer when there is somewhere to go
    pg=page("chef@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1800)
    ck("a chef opening Cleans is sent to Reservations", pg.url.endswith("tally.html"))
    print("   chef on Cleans landed at:", pg.url.split("/")[-1])
    pg.close()

    # a login with no record at all: the case that used to be full access
    pg=page("ben@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    ck("an unseeded login is refused rather than trusted",
       pg.evaluate("()=>noAccess.className.indexOf('show')>-1 && getComputedStyle(grid).display=='none'"))
    pg.close()

    # a lookup that fails is not the same as a login that is not on the list
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body=sdk("staff@nalaresort.com.au")))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body="/*n*/"))
    def fbfail(route,request):
        if "/staff" in request.url: route.fulfill(status=500,body="nope"); return
        fb(route,request)
    pg.route("**firebasedatabase.app/**",fbfail)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    m=pg.evaluate("()=>noAccess.textContent")
    ck("a failed lookup blames the connection, not the login",
       "see the manager" not in m.lower() and "connection" in m.lower())
    ck("and offers a retry", pg.evaluate("()=>!!document.querySelector('#noAccess .na-retry')"))
    print("   lookup failed:", m)
    pg.close()

    # saved to the home screen, the app view must survive a link tap.
    # Safari hands an ordinary link to a new browser window, bars and all,
    # which no test browser reproduces, so this watches the navigation the
    # code would perform instead of the one the browser would.
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.add_init_script("""Object.defineProperty(navigator,'standalone',{get:()=>true});
        window.NALA_GO=function(u){ window.__went=u; };""")
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body=sdk("staff@nalaresort.com.au")))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body="/*n*/"))
    pg.route("**firebasedatabase.app/**",fb)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1300)
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    pg.locator("#navDrop a[href='housekeeping.html']").click(); pg.wait_for_timeout(250)
    went=pg.evaluate("()=>window.__went||null")
    print("   standalone nav:", went)
    ck("standalone: the app keeps the page instead of handing it to Safari",
       bool(went) and went.endswith("housekeeping.html"))
    ck("standalone: still on the same page, not navigated by the browser",
       pg.url.endswith("cleaners.html"))
    pg.close()

    # Chrome has no navigator.standalone, so the display mode is the only
    # signal there. This is the case that shipped broken.
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.add_init_script("""delete Object.getPrototypeOf(navigator).standalone;
        window.NALA_GO=function(u){ window.__went=u; };
        const mm=window.matchMedia;
        window.matchMedia=function(q){
          if(q.indexOf('display-mode: standalone')>-1) return {matches:true,media:q,
            addListener:function(){},removeListener:function(){},addEventListener:function(){},
            removeEventListener:function(){}};
          return mm.call(window,q); };""")
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body=sdk("staff@nalaresort.com.au")))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body="/*n*/"))
    pg.route("**firebasedatabase.app/**",fb)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1300)
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    pg.locator("#navDrop a[href='housekeeping.html']").click(); pg.wait_for_timeout(250)
    ck("display-mode standalone is honoured, not just Safari's flag",
       (pg.evaluate("()=>window.__went||''") or "").endswith("housekeeping.html"))
    pg.close()

    # an ordinary tab must be left completely alone
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.add_init_script("window.NALA_GO=function(u){ window.__went=u; };")
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body=sdk("staff@nalaresort.com.au")))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body="/*n*/"))
    pg.route("**firebasedatabase.app/**",fb)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1300)
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    pg.locator("#navDrop a[href='housekeeping.html']").click(); pg.wait_for_timeout(600)
    ck("ordinary tab: the browser navigates as normal, nothing intercepted",
       pg.url.endswith("housekeeping.html") and pg.evaluate("()=>window.__went||null") is None)
    pg.close()

    # the board sizes itself to the phone. Heights here are REAL usable
    # heights, not the marketing screen size: the status bar, home indicator
    # and browser bars all take their cut first.
    for label,w,h,mustFit in [("iPhone 14/15 app view",390,763,True),
                              ("iPhone 15 Max app",430,851,True),
                              ("iPhone 12 mini app",360,719,True),
                              ("iPhone 14/15 browser",390,664,True),
                              ("iPhone SE app view",375,647,True),
                              ("iPhone SE browser",375,553,False)]:
        q=b.new_page(viewport={"width":w,"height":h})
        q.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body=sdk("staff@nalaresort.com.au")))
        q.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body="/*n*/"))
        q.route("**firebasedatabase.app/**",fb)
        q.goto("http://localhost:8957/cleaners.html"); q.wait_for_timeout(1300)
        m=q.evaluate("""()=>{const g=document.getElementById('grid');
          const t=document.querySelector('.tile').getBoundingClientRect();
          const f=document.getElementById('footBar').getBoundingClientRect();
          return {page:document.body.scrollHeight-window.innerHeight,
                  gs:g.scrollHeight-g.clientHeight, tH:Math.round(t.height),
                  cols:getComputedStyle(g).gridTemplateColumns.split(' ').length,
                  footIn:Math.round(f.bottom)<=window.innerHeight+1};}""")
        ck("%s: the page itself never scrolls" % label, m["page"]<=1)
        ck("%s: footer stays on screen" % label, m["footIn"])
        ck("%s: three columns, never two" % label, m["cols"]==3)
        ck("%s: tiles stay tappable (%dpx)" % (label,m["tH"]), m["tH"]>=44)
        if mustFit:
            ck("%s: all 17 villas on one screen (tile %dpx)" % (label,m["tH"]), m["gs"]<=1)
        q.close()

    # double tap to zoom must be off on the board, and pinch zoom must NOT be
    pg=page("staff@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1300)
    ta=pg.evaluate("""()=>({body:getComputedStyle(document.body).touchAction,
        tile:getComputedStyle(document.querySelector('#grid .tile')).touchAction})""")
    print("   touch-action:", ta)
    ck("double tap zoom off on the board", ta["body"]=="manipulation")
    ck("pinch zoom still allowed, not 'none'", ta["body"]!="none")
    pg.close()

    # a waiter is on the Cleans board only to say a villa looks free after
    # breakfast. The rest is hidden, not disabled: this is about not pressing
    # something by accident.
    def marks(email, villa):
        q=page(email)
        q.goto("http://localhost:8957/cleaners.html"); q.wait_for_timeout(1400)
        tile(q, villa).click(); q.wait_for_timeout(400)
        out=q.evaluate("""()=>[].filter.call(document.querySelectorAll('#ov .pbtn'),
            e=>getComputedStyle(e).display!=='none').map(e=>e.textContent.trim())""")
        q.close(); return out

    w6 = marks("waiter@nalaresort.com.au", 6)
    print("   waiter, villa on service:", w6)
    ck("waiter reaches the Cleans board at all", "Close" in " ".join(w6))
    # "Possibly available" only shows on a villa set to Service whose guest is
    # staying, which this fixture has none of, so the positive case is checked
    # in waiter_svc below rather than pretended at here.
    ck("waiter sees the board itself, not a refusal",
       len(w6) > 0)
    ck("waiter cannot mark work done or push a villa",
       not any(k in " ".join(w6).lower() for k in
               ["mark as cleaned","mark as serviced","push"]))
    # a waiter clearing breakfast sees a guest leave before anyone else, so
    # departures are theirs to mark and to take back
    w8 = marks("waiter@nalaresort.com.au", 8)
    print("   waiter, departed villa:", w8)
    ck("waiter can undo a departure", any("undo departed" in x.lower() for x in w8))
    ck("but still cannot push that villa", not any("push" in x.lower() for x in w8))

    hk7 = marks("housekeeping@nalaresort.com.au", 7)
    print("   housekeeping, finished villa:", hk7)
    ck("housekeeping keeps its own marks, untouched by the waiter change",
       any("undo done" in x.lower() for x in hk7))
    w7 = marks("waiter@nalaresort.com.au", 7)
    ck("and the waiter does not get them", not any("undo done" in x.lower() for x in w7))

    # live updates: a poll must be cheap, and must never redraw under a hand
    pg=page("staff@nalaresort.com.au")
    hits=[]
    pg.on("request", lambda r: hits.append(r.url) if "firebasedatabase.app" in r.url else None)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    first=len(hits); hits.clear()
    pg.evaluate("()=>load()"); pg.wait_for_timeout(700)
    poll=len(hits)
    print("   requests: first load %d, one poll %d" % (first, poll))
    ck("a poll costs far less than a full load (%d vs %d)" % (poll, first), poll <= first/3)
    ck("a poll refetches none of the fortnight of roomguests",
       not any("/roomguests/" in u for u in hits))
    hits.clear()
    pg.evaluate("()=>load(true)"); pg.wait_for_timeout(900)
    ck("a full load does refetch them, so bookings are never stale",
       any("/roomguests/" in u for u in hits))

    # with a villa sheet open the board must hold still
    tile(pg,3).click(); pg.wait_for_timeout(300)
    before=pg.evaluate("()=>document.getElementById('ov').className")
    ck("a sheet is open", "show" in before)
    ck("the poll stands down while a sheet is open",
       pg.evaluate("()=>typeof CUR!=='undefined' && !!CUR"))
    pg.close()

    # notifications: the toggle must say why rather than fail quietly, and
    # signing out must take the subscription with it
    pg=page("staff@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1400)
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    label=pg.evaluate("()=>navNotify.textContent")
    print("   notify toggle in a plain tab:", label)
    ck("the menu offers notifications", pg.evaluate("()=>!!document.getElementById('navNotify')"))
    ck("with no push support it says unavailable, not nothing",
       "unavailable" in label.lower() or "notifications" in label.lower())
    ck("the VAPID key decodes to a P-256 point (65 bytes)",
       pg.evaluate("()=>b64ToU8(VAPID_PUBLIC).length")==65)
    ck("the worker address is set", pg.evaluate("()=>!!PUSH_URL && PUSH_URL.indexOf('http')===0"))
    ck("a device id is stable across calls",
       pg.evaluate("()=>deviceId()===deviceId()"))
    ck("the subscription path is keyed by the login, commas not dots",
       pg.evaluate("()=>subPath({email:'staff@nalaresort.com.au'})")
         .startswith("/pushsubs/staff@nalaresort,com,au/"))

    # signing out unsubscribes before it signs out
    order=pg.evaluate("""()=>{window.__order=[];
      window.pushOff=function(u,cb){window.__order.push('unsub'); cb('off');};
      window.NALA_SIGNOUT=function(){window.__order.push('signout');};
      document.getElementById('navSignout').click();
      return window.__order;}""")
    ck("sign out unsubscribes first, then signs out", order==["unsub","signout"])
    pg.close()

    # the four events, and which one a "done" tap counts as
    pg=page("staff@nalaresort.com.au")
    sent=[]
    pg.on("request", lambda r: sent.append(r.url) if "workers.dev" in r.url else None)
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    fired=pg.evaluate("""()=>{window.__fired=[];
      window.notifyPush=function(ev,n){window.__fired.push(ev+':'+n);};
      // villa 11 is a clean, villa 2 has a breakfast mark already
      setField(11,{done:new Date().toISOString()});
      setField(8,{departed:true});
      return null;}""")
    pg.wait_for_timeout(700)
    fired=pg.evaluate("()=>window.__fired")
    print("   events fired:", fired)
    ck("finishing a clean announces it as cleaned", "cleaned:11" in fired)
    ck("a departure announces itself", "departed:8" in fired)
    ck("the defaults name every event the app can fire",
       sorted(pg.evaluate("()=>Object.keys(NOTIFY_DEFAULTS.events)"))
         == ["available","cleaned","departed","menu","serviced"])
    # A menu going up is the manager's business, not the cleaners'. The chef
    # published it, so telling the chef is telling them what they just did.
    ck("a published menu goes to the manager only",
       pg.evaluate("""()=>NOTIFY_DEFAULTS.events.menu.admin===true
                       && NOTIFY_DEFAULTS.events.menu.housekeeping===false
                       && NOTIFY_DEFAULTS.events.menu.waiter===false
                       && NOTIFY_DEFAULTS.events.menu.chef===false"""))
    # A published menu has to reach the manager whether or not a manager has
    # a board open. It used to be announced from inside the Reservations board
    # only, so on a quiet afternoon the chef published and nobody was told.
    # It now lives in nala-shared.js and any signed in page announces it.
    ck("the announcement lives in the shared file, not in one board",
       "function announceMenu" in open("/home/claude/nala/nala-shared.js").read()
       and "menuhistory" not in open("/home/claude/nala/tally.html").read())
    ck("it runs itself once a page is signed in",
       pg.evaluate("()=>typeof announceMenu==='function'"))
    # The guest pages load the same file. The token is what keeps them out,
    # rather than a list of page names that would go stale.
    ck("a page with no sign in token announces nothing",
       pg.evaluate("""()=>{const t=window.__idToken; window.__idToken=null;
                          let hit=0; const f=window.fetch;
                          window.fetch=function(u){ if((''+u).indexOf('menu.json')>-1) hit++;
                                                    return f.apply(this,arguments); };
                          announceMenu(); window.fetch=f; window.__idToken=t;
                          return hit===0;}"""))
    # Firing the buzz before the row is written would spend the one
    # announcement on a menu that was never recorded.
    ck("the notification comes after the archive write, not before",
       open("/home/claude/nala/nala-shared.js").read()
         .index("if (!r.ok) return;")
       < open("/home/claude/nala/nala-shared.js").read()
         .index("notifyPush('menu', null, null)"))
    # The chef's SMS link was a second way to say the same thing, and it put
    # a personal mobile number in a public repository.
    brief = open("/home/claude/nala/CHEF-BRIEF.md").read()
    ck("the chef brief no longer carries a phone number",
       "0468067233" not in brief and "sms:" not in brief)
    ck("and says what tells management instead",
       "automatically" in brief)

    ck("cleaned and serviced reach everyone with Cleans access",
       pg.evaluate("""()=>NOTIFY_DEFAULTS.events.cleaned.waiter===true
                       && NOTIFY_DEFAULTS.events.cleaned.housekeeping===true
                       && NOTIFY_DEFAULTS.events.cleaned.chef===false"""))
    ck("departures stay with housekeeping and admin",
       pg.evaluate("""()=>NOTIFY_DEFAULTS.events.departed.waiter===false
                       && NOTIFY_DEFAULTS.events.departed.admin===true"""))
    ck("only an admin writes the settings",
       pg.evaluate("()=>{let hit=0; const f=window.fetch; window.fetch=function(u,o){ if(o&&o.method==='PUT'&&(''+u).indexOf('/notify')>-1) hit++; return f.apply(this,arguments);}; ensureNotifySettings('waiter'); window.fetch=f; return hit===0;}"))
    pg.close()

    # The two people who must never be removable, checked by rule rather
    # than by passcode: a code can be regenerated and the rule would then
    # protect nobody.
    src = open("/home/claude/nala/staff.html").read()
    ck("removal is protected by rule, not by a hardcoded passcode",
       "protectedReason" in src and "485211" not in src)
    ck("you cannot remove yourself", "This is you." in src)
    ck("the last admin cannot be removed", "last admin cannot be removed" in src)
    ck("the check runs again on confirm, not only where the bin was drawn",
       src.count("protectedReason(key)") >= 2)

    # sync is assignable, so the account can be made on this page instead of in
    # the Firebase console, but it has no phone and must not appear in the
    # notification matrix: a column there asks who to buzz on a login that
    # cannot be buzzed.
    ck("both role pickers offer sync", src.count("ROLES_ASSIGN.map") == 2)
    ck("the staff list sorts by the assignable order, so sync sorts last",
       src.count("ROLES_ASSIGN.indexOf") == 2)
    import re as _re
    # Counted with a boundary: PERM_ROLES.map ends in the same nine characters
    # and turned this into a false failure the day the permission grid landed.
    ck("the notification matrix stays on the human roles",
       len(_re.findall(r"(?<![A-Z_])ROLES\.map", src)) == 2 and "ROLES_ASSIGN" in src)

    # The permission grid is drawn from the shared lists rather than from a
    # second copy kept here, so adding a capability in one place adds the row.
    ck("the permission grid reads the shared lists",
       "PERM_ACTIONS.map" in src and "PERM_ROLES.map" in src)
    ck("it saves the moment a box is tapped, like the one above it",
       "savePerms()" in src and "'/permissions.json'" in src)
    # Only the boxes moved away from the default are stored. Writing every
    # cell would freeze today's defaults into the database, and the next
    # capability added would arrive switched off for everybody.
    ck("only the changed boxes are stored, not a copy of every cell",
       "grantedByDefault" in src and "PERMS[ac][r] = !now" in src)
    ck("a failed load says the app is running on its defaults",
       "running on its defaults" in src)
    ck("the matrix is loaded on the way in", "loadPerms();" in src)

    # Every staff page must load the SDK before auth.js. staff.html shipped
    # without it and showed "could not load the sign-in service" to everyone.
    for f in ["cleaners.html","tally.html","list.html","housekeeping.html","staff.html"]:
        src = open("/home/claude/nala/" + f).read()
        tags = [x.split("/")[-1] for x in
                _re.findall(r'<script[^>]*src=[\'"]([^\'"]+)', src)]
        ck("%s loads firebase before auth.js" % f,
           "firebase-app-compat.js" in tags and "firebase-auth-compat.js" in tags and
           tags.index("firebase-auth-compat.js") < [i for i,t in enumerate(tags)
                                                    if t.startswith("auth.js")][0])

    # Settings is admin only, and must not appear as a door to nowhere
    for email, who, expect in [("staff@nalaresort.com.au","admin",True),
                               ("housekeeping@nalaresort.com.au","housekeeping",False),
                               ("waiter@nalaresort.com.au","waiter",False),
                               ("chef@nalaresort.com.au","chef",False)]:
        q=page(email)
        q.goto("http://localhost:8957/cleaners.html"); q.wait_for_timeout(1400)
        vis=q.evaluate("""()=>{const a=document.querySelector('#navDrop a[href="staff.html"]');
            return !!a && getComputedStyle(a).display!=='none';}""")
        ck("%s %s Settings in the menu" % (who, "sees" if expect else "does not see"),
           vis == expect)
        q.close()

    # the link must actually call auth.js's signOut, not just look like it
    pg=page("staff@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1400)
    pg.evaluate("()=>{window.__out=0; window.NALA_SIGNOUT=function(){window.__out++;};}")
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    pg.locator("#navSignout").click(); pg.wait_for_timeout(200)
    ck("sign out calls NALA_SIGNOUT", pg.evaluate("()=>window.__out")==1)
    ck("and does not navigate away to '#'", "cleaners.html" in pg.url and "#" not in pg.url)
    pg.close(); b.close()
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
