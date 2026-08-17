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
staff={"staff@x":{"name":"Admin","role":"admin"},
       "chef@x":{"name":"Chef","role":"chef"},
       "waiter@x":{"name":"Waiter","role":"waiter"},
       "housekeeping@x":{"name":"Housekeeping","role":"housekeeping"}}
def fb(route,request):
    u=request.url; body="null"
    if "/staff" in u: body=json.dumps(staff)
    elif "/responses/" in u: body=json.dumps(responses)
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
      const c=[...document.querySelectorAll('.stat')].filter(e=>!e.closest('#printHead')).pop();
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
        name:cell(t,0),room:cell(t,1),din:cell(t,4),pax:cell(t,5),stay:cell(t,6),
        diet:(t.querySelector('.dwrap')||{textContent:''}).textContent.trim(),
        dietHTML:(t.querySelector('td.c-dc')||{innerHTML:''}).innerHTML,
        com:(t.querySelector('.dcom')||{textContent:''}).textContent.trim(),
        html:t.cells[0].innerHTML}));
      return {n:trs.length, data, blanks:trs.filter(t=>t.className.includes('blank')).length};}""")
    d=rw["data"]
    ck("19 data rows + pad to 21 total", len(d)==19 and rw["n"]==21 and rw["blanks"]==2)
    r1=d[0]
    ck("r1 conflict row + FLAG + PRE-MENU", "row-conflict" in r1["cls"] and "FLAG" in r1["name"] and "PRE-MENU" in r1["name"])
    ck("r1 dietaries as pills, allergy solid and shortened",
       "NUT" in r1["diet"].upper() and "VEGETARIAN" in r1["diet"].upper()
       and "ALLERGY" not in r1["diet"].upper()
       and 'dpill dpill-al' in r1["dietHTML"] and 'class="dpill"' in r1["dietHTML"])
    ck("r1 checkout tomorrow red", "checkout" in pg.evaluate("()=>document.querySelectorAll('#rows tr')[0].querySelector('td.c-dep').innerHTML"))

    rowsz=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')].map(r=>{
      const c=r.querySelector('td.c-dep')||r.cells[6];
      if(!c) return null;
      return {t:c.textContent.trim(), h:Math.round(c.getBoundingClientRect().height),
              ws:getComputedStyle(c).whiteSpace};}).filter(Boolean)""")
    stays=[r for r in rowsz if r["t"]]
    print("   stay cells:", [r["t"] for r in stays][:5])
    ck("stay reads Wd D-Wd D, no ordinals, no 'to'",
       all(("to" not in r["t"]) and ("th" not in r["t"]) and ("rd" not in r["t"]) for r in stays))
    ck("stay column never wraps", all(r["ws"]=="nowrap" for r in stays))
    tall=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr td.c-dep')]
      .filter(c=>c.textContent.trim()).map(c=>{
        const r=document.createRange(); r.selectNodeContents(c);
        const boxes=r.getClientRects();
        const tops=new Set([...boxes].map(b=>Math.round(b.top)));
        return {t:c.textContent.trim(), lines:tops.size};})""")
    print("   stay text lines:", tall)
    ck("every stay cell renders on one line", all(t["lines"]==1 for t in tall))
    ck("r1 comment + dietary note", "Window seat" in r1["com"] and "Dietary: Very allergic" in r1["com"])

    hdr=pg.evaluate("""()=>{const th=[...document.querySelectorAll('thead th')].map(x=>x.textContent.trim());
      const dc=document.querySelector('thead th.c-dc');
      const cells=document.querySelector('#rows tr').cells.length;
      return {heads:th, span:dc?+dc.getAttribute('colspan'):0, cells:cells};}""")
    print("   header:", hdr)
    ck("dietaries and comments are one column at combined width",
       hdr["span"]==2 and hdr["cells"]==8 and "Comments" not in hdr["heads"])
    rows=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
      .filter(t=>t.querySelector('.dwrap') && t.querySelector('.dcom'))
      .map(t=>{const p=t.querySelector('.dwrap').getBoundingClientRect();
               const c=t.querySelector('.dcom').getBoundingClientRect();
               return {below: Math.round(c.top) >= Math.round(p.bottom)-1};})""")
    print("   pills-then-comment rows:", rows)
    ck("comment sits beneath the pills, not beside them",
       len(rows)>0 and all(r["below"] for r in rows))
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


    # (auth-failure checks parked with the auth.js rollback — see HANDOVER.md)
    open("/home/claude/nala/_p2_list.png","wb").write(shot)
    pg.close()

    # the PDF: text drawn as text, because iOS prints the page as a bitmap
    src = open("/home/claude/nala/list.html").read()
    ck("the sheet can build a real PDF", "function sheetPDF" in src)
    ck("it draws from captured data, not by reading the table back",
       "SHEET.push" in src and "innerHTML" not in src.split("function sheetPDF")[1][:4000])
    ck("a PDF button is offered", 'id="sheetPdf"' in src)
    ck("fonts are embedded, so the text stays vector", "addFileToVFS" in src)

    # the PDF must reach the share sheet on a phone: Print lives in there,
    # and a download leaves someone hunting through Files for it
    ck("the PDF is offered to the share sheet first", "navigator.canShare" in src)
    ck("with a new tab as the fallback", "window.open(url" in src)
    ck("and a download only if the tab was blocked",
       src.index("navigator.canShare") < src.index("a.download"))

    # printed: no tinted rows, and the sheet fills the page
    pg2=b.new_page(viewport={"width":1000,"height":1200})
    pg2.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body=SDK))
    pg2.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
        content_type="application/javascript",body="/*n*/"))
    pg2.route("**firebasedatabase.app/**",fb)
    pg2.route("**/menu.json*",lambda r,_:r.fulfill(status=200,
        content_type="application/json",body=json.dumps(menu)))
    pg2.goto("http://localhost:8955/list.html"); pg2.wait_for_timeout(1600)
    pg2.emulate_media(media="print")
    tint=pg2.evaluate("""()=>[].map.call(document.querySelectorAll('tbody tr td'),
        e=>getComputedStyle(e).backgroundColor)
        .filter(c=>c!=='rgba(0, 0, 0, 0)' && c!=='transparent'
                   && c!=='rgb(255, 255, 255)').length""")
    ck("no tinted rows on paper, whatever the villa's state (%d found)" % tint, tint==0)
    rowH=pg2.evaluate("""()=>{const r=document.querySelector('tbody tr');
        return Math.round(r.getBoundingClientRect().height);}""")
    print("   printed row height:", rowH, "px")
    ck("rows have room to be written on (%dpx)" % rowH, rowH >= 34)
    pg2.emulate_media(media="screen")
    tintScreen=pg2.evaluate("""()=>[].map.call(document.querySelectorAll('tbody tr td'),
        e=>getComputedStyle(e).backgroundColor)
        .filter(c=>c!=='rgba(0, 0, 0, 0)' && c!=='transparent').length""")
    ck("but the screen keeps its tints for grouping", tintScreen>0)
    pg2.close()

    # ---- roles on the sheet, per the ROLES.md matrix ----
    def as_role(email):
        q=b.new_page(viewport={"width":900,"height":1100})
        q.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body=SDK.replace("staff@x",email)))
        q.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body="/*n*/"))
        q.route("**firebasedatabase.app/**",fb)
        q.route("**/menu.json*",lambda r,_:r.fulfill(status=200,
            content_type="application/json",body=json.dumps(menu)))
        q.goto("http://localhost:8955/list.html"); q.wait_for_timeout(1500)
        return q

    q=as_role("chef@x")
    ck("chef reads and prints the sheet",
       q.evaluate("""()=>noAccess.className.indexOf('show')<0
                      && document.querySelectorAll('table tbody tr').length>0
                      && getComputedStyle(footBar).display!='none'"""))
    q.close()

    q=as_role("housekeeping@x")
    q.wait_for_timeout(600)
    ck("housekeeping is sent to the Cleans board, not shown a refusal",
       q.url.endswith("cleaners.html"))
    # a login with no record has nowhere to be sent, so it still gets the message
    q.close()
    q=as_role("nobody@x")
    q.wait_for_timeout(600)
    ck("a login with no role still gets the message, having nowhere to go",
       "see the manager" in q.evaluate("()=>noAccess.textContent").lower())
    q.close()
    b.close()
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
