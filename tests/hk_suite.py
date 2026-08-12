import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8956),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(0.3)
SDK="""window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("No Firebase App '[DEFAULT]' has been created"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},signOut:function(){}};"""
now=datetime.datetime.now().astimezone(); today=now.strftime("%Y-%m-%d")
def plus(d): return (now+datetime.timedelta(days=d)).strftime("%Y-%m-%d")
STATE={"break":False}
responses={"0400000002":{"status":"in","pax":2,"name":"Elena","room":"2","arrives":plus(-3),"departs":plus(2),"at":"T1"}}
manual={"room-5":{"status":"vacant","pax":0,"room":"5","source":"manual"}}
roomguests={
 "1":{"name":"James","arrives":plus(-2),"departs":today},
 "2":{"name":"Elena","arrives":plus(-3),"departs":plus(2)},
 "3":{"name":"Gone","departs":plus(-1)},
 "4":{"name":"Lucy","arrives":plus(-1),"departs":plus(3)},
 "7":{"name":"Priya","departs":today},
 "8":{"name":"Dev","departs":plus(1)},
}
donets=now.strftime("%Y-%m-%dT%H:%M:%S")+".123456"
hk={"1":{"done":donets},"2":{"bfast":now.isoformat()},"4":{"departed":True},"7":{"bfast":now.isoformat(),"done":now.isoformat()}}
def fb(route,request):
    u=request.url; body="null"
    if STATE["break"] and "/responses/" in u:
        route.fulfill(status=500,body="err"); return
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
with sync_playwright() as p:
    b=p.chromium.launch()
    def page():
        pg=b.new_page(viewport={"width":900,"height":1100})
        pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=SDK))
        pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
        pg.route("**firebasedatabase.app/**",fb)
        return pg
    pg=page()
    pg.goto("http://localhost:8956/housekeeping.html"); pg.wait_for_timeout(1400)
    hd=pg.evaluate("()=>({k:'n/a',d:title.textContent,c:nClean.textContent,s:nSvc.textContent,v:nVer.textContent,vd:getComputedStyle(verWrap).display})")
    ck("printkick present for paper", pg.evaluate("()=>document.querySelector('.printkick').textContent.includes('HC print')"))
    ck("date format", bool(re.match(r'^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) \d{1,2}(st|nd|rd|th) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$',hd["d"])))
    ck("cleans 2 services 3", hd["c"]=="2" and hd["s"]=="3")
    ck("verify 11 shown", hd["v"]=="11" and hd["vd"]!="none")
    rw=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')].map(t=>({cls:t.className,
      room:t.cells[0].textContent.trim(),svc:t.cells[1].textContent.trim(),
      arr:t.cells[2].textContent.trim(),dep:t.cells[3].textContent.trim(),
      done:t.cells[4].innerHTML,insp:t.cells[6].innerHTML}))""")
    order=[r["room"] for r in rw]
    ck("jobs only: 3 services, 2 cleans, then 3 blank write-in rows",
       len(rw)==8 and order[:3]==["2","4","8"] and order[3:5]==["1","7"] and order[5:]==["","",""])
    ck("verify and vacant rooms are off the sheet",
       not any("Verify" in r["svc"] or "Vacant" in r["svc"] for r in rw))
    wi=[r for r in rw if r["cls"]=="writein"]
    ck("write-in rows blank but carry both tick boxes",
       len(wi)==3 and all(r["room"]=="" and r["svc"]=="" and r["arr"]=="" and r["dep"]==""
                          and "box" in r["done"] and "box" in r["insp"] for r in wi))
    r1=[r for r in rw if r["room"]=="1"][0]
    ck("room1 Clean chip + done tick with time (6-digit ISO parsed)", "Clean" in r1["svc"] and "✓" in r1["done"] and re.search(r'\d{2}:\d{2}',r1["done"]))
    r2=[r for r in rw if r["room"]=="2"][0]
    ck("room2 Service + At breakfast", "Service" in r2["svc"] and "At breakfast" in r2["svc"])
    r4=[r for r in rw if r["room"]=="4"][0]
    ck("room4 Departed subtag", "Departed" in r4["svc"])
    r7=[r for r in rw if r["room"]=="7"][0]
    ck("room7 done clears breakfast subtag", "At breakfast" not in r7["svc"] and "✓" in r7["done"])
    ck("room2 arrival+departs columns", r2["arr"]!="" and r2["dep"]!="")
    # A5 portrait at 96dpi with the 10mm @page margin: 484 x 718 printable px
    pa=page(); pa.emulate_media(media="print")
    pa.set_viewport_size({"width":484,"height":718})
    pa.goto("http://localhost:8956/housekeeping.html"); pa.wait_for_timeout(1400)
    fits=pa.evaluate("()=>Math.round(document.scrollingElement.scrollHeight)")
    print("   sheet height at A5 width:", fits, "of 718")
    ck("whole sheet fits one A5 page", fits<=718)
    # worst case: every room a job, plus the three write-ins, still one page
    pa.evaluate("""()=>{const tb=document.getElementById('rows');
      const t=[...tb.querySelectorAll('tr')].find(r=>!r.querySelector('.subtag') && r.className!=='writein');
      while (tb.querySelectorAll('tr').length < 20) tb.appendChild(t.cloneNode(true));}""")
    pa.wait_for_timeout(150)
    full=pa.evaluate("()=>Math.round(document.querySelector('.stamp').getBoundingClientRect().bottom)")
    print("   20-row sheet bottom:", full, "of 718")
    ck("full house of 17 jobs plus write-ins still fits A5", full<=718)
    pa.close()
    ck("stamp present", bool(re.match(r'^Printed \d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}[ap]m$', pg.locator("#stamp").inner_text(), re.I)))
    shot=pg.screenshot(full_page=True)
    pg.emulate_media(media="print")
    pr=pg.evaluate("""()=>({foot:getComputedStyle(document.querySelector('.foot')).display,
      nav:getComputedStyle(document.querySelector('.navwrap')).display,
      dnav:getComputedStyle(document.querySelector('.dnav')).display,
      stamp:getComputedStyle(document.querySelector('.stamp')).display,
      mgr:getComputedStyle(document.querySelector('.mgrstrip')).display})""")
    ck("print hides controls, keeps stamp+manager strip", pr["foot"]=="none" and pr["nav"]=="none" and pr["dnav"]=="none" and pr["stamp"]!="none" and pr["mgr"]!="none")
    pg.emulate_media(media="screen")
    pg.close()

    pg=page()
    pg.goto("http://localhost:8956/housekeeping.html?date="+plus(1)); pg.wait_for_timeout(1400)
    ck("Today button enabled off-today", pg.evaluate("()=>!dToday.disabled"))
    r8=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')].map(t=>({room:t.cells[0].textContent.trim(),svc:t.cells[1].textContent.trim()})).find(r=>r.room==='8')""")
    ck("room8 is Clean on tomorrow's sheet", "Clean" in r8["svc"])
    pg.close()

    pg=page()
    STATE["break"]=True
    pg.goto("http://localhost:8956/housekeeping.html"); pg.wait_for_timeout(1400)
    err=pg.evaluate("()=>({t:document.getElementById('rows').textContent,cs:(document.querySelector('#rows td')||{}).colSpan||0})")
    ck("load failure shows red message across 7 cols", "Could not load" in err["t"] and err["cs"]==7)
    STATE["break"]=False
    pg.close(); b.close()
    open("/home/claude/nala/_p3_hk.png","wb").write(shot)
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
