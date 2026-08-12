import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8955),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(0.3)
SDK="""window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("No Firebase App '[DEFAULT]' has been created"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},signOut:function(){}};"""
now=datetime.datetime.now().astimezone(); today=now.strftime("%Y-%m-%d")
def plus(d): return (now+datetime.timedelta(days=d)).strftime("%Y-%m-%d")
responses={
 "0400000001":{"status":"in","pax":2,"name":"James","room":"1","phone":"0400000001",
   "diets":["Nut allergy","Vegetarian"],"note":"Window seat","dnote":"Very allergic","premenu":True,
   "arrives":plus(-2),"departs":plus(1),"at":"T1"},
 "0400000002":{"status":"out","room":"2","at":"T2"},
 "0400000003":{"status":"in","pax":2,"name":"Mark","room":"3","arrives":plus(-1),"departs":plus(3),"at":"T3"},
 "0400000090":{"status":"in","pax":2,"name":"Zara","phone":"400000090","at":"T4"},
 "0400000091":{"status":"in","pax":2,"name":"Bob","phone":"0400000091","at":"T5"},
}
manual={
 "room-5":{"status":"vacant","pax":0,"room":"5","source":"manual"},
 "ext-777":{"status":"in","pax":3,"name":"Alfie","phone":"0455 555 555","source":"manual"},
 "extcancel-0400000091":{"status":"out","override":True,"source":"manual"},
}
roomguests={"4":{"name":"Lucy","departs":plus(2)},"9":{"name":"Priya","departs":plus(3)}}
combined={"g1":{"rooms":["3","4"]}}
# publish timestamp with SIX fractional digits — the Safari killer
menu={"published":now.strftime("%Y-%m-%dT%H:%M:%S")+".123456",
      "bread":{"name":"Sourdough"},"entree":{"name":"Prawns"},
      "main":{"name":"Satay Chicken"},"dessert":{"name":"Pavlova"}}
menutags={"main":["Nut allergy"]}
def fb(route,request):
    u=request.url; body="null"
    if "/responses/" in u: body=json.dumps(responses)
    elif "/manual/" in u: body=json.dumps(manual)
    elif "/roomguests/"+today in u: body=json.dumps(roomguests)
    elif "/roomguests/" in u: body="null"
    elif "/combined/" in u: body=json.dumps(combined)
    elif "/menutags/" in u: body=json.dumps(menutags)
    route.fulfill(status=200,content_type="application/json",body=body)
from playwright.sync_api import sync_playwright
P=F=0
def ck(n,c):
    global P,F
    print(("PASS " if c else "FAIL ")+n); P,F=(P+1,F) if c else (P,F+1)
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":900,"height":1100})
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=SDK))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
    pg.route("**firebasedatabase.app/**",fb)
    pg.route("**/menu.json*",lambda r,_:r.fulfill(status=200,content_type="application/json",body=json.dumps(menu)))
    pg.goto("http://localhost:8955/list.html"); pg.wait_for_timeout(1500)

    hd=pg.evaluate("()=>({k:'n/a',d:title.textContent,t:nTables.textContent,tb:tblBreak.textContent,tw:nTablesWord.textContent,c:nCovers.textContent})")
    ck("printkick present for paper", pg.evaluate("()=>document.querySelector('.printkick').textContent.includes('Res print')"))
    ck("date format", bool(re.match(r'^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) \d{1,2}(st|nd|rd|th) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$',hd["d"])))
    ck("covers 9", hd["c"]=="9")
    ck("tables 4, make-up named not multiplied",
       hd["t"]=="4" and "3 twos" in hd["tb"] and "1 three" in hd["tb"]
       and "×" not in hd["tb"] and hd["tw"]=="tables")
    hg=pg.evaluate("""()=>{const m=document.querySelector('.stat.statmix');
      const c=[...document.querySelectorAll('.stat')].pop();
      const mn=m.querySelector('.stat-n').getBoundingClientRect();
      const cn=c.querySelector('.stat-n').getBoundingClientRect();
      return {mixLeft:Math.round(mn.left), covRight:Math.round(cn.right),
              wrapLeft:Math.round(document.body.getBoundingClientRect().left),
              vw:innerWidth, mixSize:getComputedStyle(m.querySelector('.stat-n')).fontSize,
              covSize:getComputedStyle(c.querySelector('.stat-n')).fontSize,
              rows:Math.round(document.querySelector('.stats').getBoundingClientRect().height)};}""")
    print("   header geom:", hg)
    ck("make-up left-anchored, covers right-anchored, one row",
       hg["mixLeft"]<=20 and hg["covRight"]>=hg["vw"]-20 and hg["rows"]<=46)
    ck("make-up one step below covers", hg["mixSize"]=="15px" and hg["covSize"]=="20px")

    rw=pg.evaluate("""()=>{
      const trs=[...document.querySelectorAll('#rows tr')];
      const cell=(tr,i)=>tr.cells[i].textContent.trim();
      const data=trs.filter(t=>!t.className.includes('blank')).map(t=>({cls:t.className,
        name:cell(t,0),room:cell(t,1),din:cell(t,4),pax:cell(t,5),stay:cell(t,6),diet:cell(t,7),com:cell(t,8),
        html:t.cells[0].innerHTML}));
      return {n:trs.length, data, blanks:trs.filter(t=>t.className.includes('blank')).length};}""")
    d=rw["data"]
    ck("19 data rows + pad to 21 total", len(d)==19 and rw["n"]==21 and rw["blanks"]==2)
    r1=d[0]
    ck("r1 conflict row + FLAG + PRE-MENU", "row-conflict" in r1["cls"] and "FLAG" in r1["name"] and "PRE-MENU" in r1["name"])
    ck("r1 dietaries comma-joined, allergen marked", "Nut allergy, Vegetarian" in r1["diet"] and 'class="allergen"' in pg.evaluate("()=>document.querySelectorAll('#rows tr')[0].cells[7].innerHTML"))
    ck("r1 checkout tomorrow red", "checkout" in pg.evaluate("()=>document.querySelectorAll('#rows tr')[0].cells[6].innerHTML"))
    ck("r1 comment + dietary note", "Window seat" in r1["com"] and "Dietary: Very allergic" in r1["com"])
    ck("r2 declined tinted", "row-out" in d[1]["cls"] and d[1]["din"]=="No")
    ck("rooms 3+4 boxed pair", "g-in g-first" in d[2]["cls"] and "g-in g-last" in d[3]["cls"] and d[3]["name"]=="Lucy")
    ck("r4 known-but-silent shows dash", d[3]["din"]=="—" and "row-unk" in d[3]["cls"])
    ck("r5 vacant muted", "row-vacant" in d[4]["cls"] and d[4]["name"]=="Vacant")
    ck("r9 Priya listed silent", d[8]["name"]=="Priya" and d[8]["din"]=="—")
    ext=d[17:]
    ck("externals sorted Alfie,Zara with ext cell", (ext[0]["name"].startswith("Alfie") and ext[1]["name"].startswith("Zara")) and all(e["room"]=="ext" for e in ext))
    ck("cancelled external Bob excluded", all("Bob" not in e["name"] for e in ext))
    ck("Zara phone tidied to leading zero", "0400000090" in ext[1]["name"] or "0400000090" in pg.evaluate("()=>[...document.querySelectorAll('#rows tr')].filter(t=>t.textContent.includes('Zara'))[0].innerHTML"))
    ck("stamp present", bool(re.match(r'^Printed \d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}[ap]m$', pg.locator("#stamp").inner_text(), re.I)))

    scr=pg.evaluate("""()=>({foot:getComputedStyle(document.querySelector('.foot')).display,
      nav:getComputedStyle(document.querySelector('.navwrap')).display,
      dnav:getComputedStyle(document.querySelector('.dnav')).display})""")
    ck("screen shows foot+nav+arrows", scr["foot"]!="none" and scr["nav"]!="none" and scr["dnav"]!="none")
    shot=pg.screenshot(full_page=True)
    pg.emulate_media(media="print")
    pr=pg.evaluate("""()=>({foot:getComputedStyle(document.querySelector('.foot')).display,
      nav:getComputedStyle(document.querySelector('.navwrap')).display,
      dnav:getComputedStyle(document.querySelector('.dnav')).display,
      stamp:getComputedStyle(document.querySelector('.stamp')).display,
      date:getComputedStyle(document.querySelector('.date')).display})""")
    ck("print hides foot+nav+arrows, keeps date+stamp", pr["foot"]=="none" and pr["nav"]=="none" and pr["dnav"]=="none" and pr["stamp"]!="none" and pr["date"]!="none")
    pdf=pg.pdf(format="A4")
    open("/home/claude/nala/_p2_print.pdf","wb").write(pdf)
    pg.emulate_media(media="screen")

    pg.goto("http://localhost:8955/list.html?date="+plus(1)); pg.wait_for_timeout(1200)
    ck("Today button enabled off-today", pg.evaluate("()=>!dToday.disabled"))
    ck("off-today date matches param", str((now+datetime.timedelta(days=1)).day) in pg.locator("#title").inner_text())


    # the sign-in button must never die silently (see AUDIT.md)
    BROKEN = SDK.replace("onIdTokenChanged", "xIdTokenChanged")
    pb = b.new_page(viewport={"width":390,"height":844})
    pb.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=BROKEN))
    pb.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
    pb.route("**firebasedatabase.app/**",fb)
    pb.goto("http://localhost:8955/list.html"); pb.wait_for_timeout(1200)
    st=pb.evaluate("""()=>({box:(document.getElementById('nalaAuthBox')||{}).innerText||'',
      form:!!document.getElementById('naGo'),
      reload:!!(document.getElementById('naReload')||document.getElementById('naReload2'))})""")
    print("   broken-SDK panel:", repr(st["box"])[:90])
    ck("auth SDK missing: says so and offers reload, no dead form",
       st["reload"] and not st["form"] and "sign-in service" in st["box"].lower())
    pb.close()

    NOSIGN = SDK.replace("onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);}",
                         "onIdTokenChanged:function(cb){setTimeout(function(){cb(null);},20);}")
    pc = b.new_page(viewport={"width":390,"height":844})
    pc.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=NOSIGN))
    pc.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
    pc.route("**firebasedatabase.app/**",fb)
    pc.goto("http://localhost:8955/list.html"); pc.wait_for_timeout(1200)
    if pc.evaluate("()=>!!document.getElementById('naGo')"):
        pc.fill("#naEmail","a@b.c"); pc.fill("#naPass","x")
        pc.click("#naGo"); pc.wait_for_timeout(300)
        st2=pc.evaluate("()=>({dis:naGo.disabled, err:naErr.textContent})")
        print("   dead-button check:", st2)
        ck("sign-in call impossible: button re-enabled with a message",
           st2["dis"] is False and len(st2["err"])>0)
    else:
        ck("sign-in call impossible: button re-enabled with a message", False)
    pc.close()
    open("/home/claude/nala/_p2_list.png","wb").write(shot)
    pg.close(); b.close()
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
