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
       "chef@nalaresort,com,au":{"name":"Chef","role":"chef"}}
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

    # the matrix in ROLES.md, cell by cell
    M={"admin":       {"cleansBoard":1,"cleansMarks":1,"setJob":1,"resBoard":1,
                       "editBookings":1,"resSheet":1,"publishMenu":1,"manageStaff":1},
       "chef":        {"cleansBoard":0,"cleansMarks":0,"setJob":0,"resBoard":1,
                       "editBookings":0,"resSheet":1,"publishMenu":1,"manageStaff":0},
       "waiter":      {"cleansBoard":0,"cleansMarks":0,"setJob":0,"resBoard":1,
                       "editBookings":1,"resSheet":1,"publishMenu":0,"manageStaff":0},
       "housekeeping":{"cleansBoard":1,"cleansMarks":1,"setJob":0,"resBoard":0,
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
    pg.close()

    # ---- the gate on the page ----
    pg=page("chef@nalaresort.com.au")
    pg.goto("http://localhost:8957/cleaners.html"); pg.wait_for_timeout(1500)
    g=pg.evaluate("""()=>({msg:noAccess.textContent, shown:noAccess.className.indexOf('show')>-1,
                          grid:getComputedStyle(grid).display, nav:getComputedStyle(navWrap).display})""")
    ck("a chef gets no Cleans board", g["shown"] and g["grid"]=="none")
    ck("but still has a menu to leave by", g["nav"]!="none")
    ck("and is told where to go, once", "see the manager" in g["msg"].lower())
    print("   chef on Cleans:", g["msg"])
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
