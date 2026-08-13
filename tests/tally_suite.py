import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=socketserver.TCPServer(("",8953),Q)
threading.Thread(target=httpd.serve_forever,daemon=True).start(); time.sleep(0.3)
SDK="""window.firebase={__i:false,initializeApp:function(){window.firebase.__i=true;},
auth:function(){ if(!window.firebase.__i) throw new Error("No Firebase App '[DEFAULT]' has been created"); return window.__A;}};
window.__A={onIdTokenChanged:function(cb){setTimeout(function(){cb({email:'staff@x',getIdToken:function(){return Promise.resolve('T');}});},20);},
onAuthStateChanged:function(cb){setTimeout(function(){cb({email:'staff@x'});},25);},signOut:function(){}};"""
now=datetime.datetime.now().astimezone(); today=now.strftime("%Y-%m-%d")
def plus(d): return (now+datetime.timedelta(days=d)).strftime("%Y-%m-%d")
STATE={"fail":False}
WRITES=[]
responses={
 "0400000001":{"status":"in","pax":2,"name":"James","room":"1","phone":"0400 000 001","diets":["Nut allergy"],"note":"Window seat please","at":"2026-08-12T09:00:00"},
 "0400000002":{"status":"out","room":"2","at":"2026-08-12T09:05:00"},
 "0400000003":{"status":"in","pax":2,"name":"Mark","room":"3","premenu":True,"nodiet":True,"at":"2026-08-12T09:10:00"},
 "0400000099":{"status":"in","pax":2,"name":"Outside Guest","phone":"0400 000 099","at":"2026-08-12T10:00:00"},
}
manual={
 "room-5":{"status":"vacant","pax":0,"room":"5","source":"manual"},
 "room-6":{"status":"in","pax":3,"room":"6","source":"manual"},
}
roomguests={today:{"9":{"name":"Priya","departs":plus(3)},"4":{"name":"Lucy","departs":plus(2)}}}
combined={"g1":{"rooms":["3","4"]}}
menu={"published":now.isoformat(),"bread":{"name":"Sourdough"},"entree":{"name":"Prawns"},
      "main":{"name":"Satay Chicken"},"dessert":{"name":"Pavlova"}}
menutags={"main":["Nut allergy"]}
def fb(route,request):
    u=request.url; m=request.method
    if m in ("PUT","DELETE","PATCH"):
        WRITES.append({"m":m,"u":u,"b":request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401,content_type="application/json",body='{"error":"denied"}'); return
        route.fulfill(status=200,content_type="application/json",body=request.post_data or "null"); return
    body="null"
    if "/responses/" in u: body=json.dumps(responses) if today in u else "{}"
    elif "/manual/" in u and today not in u: body="{}"
    elif "/manual/" in u: body=json.dumps(manual)
    elif "/roomguests/"+today in u: body=json.dumps(roomguests[today])
    elif "/roomguests/" in u: body="null"
    elif "/combined/" in u: body=json.dumps(combined)
    elif "/menutags/" in u: body=json.dumps(menutags)
    elif "/menuhistory/" in u: body="null"
    route.fulfill(status=200,content_type="application/json",body=body)
from playwright.sync_api import sync_playwright
def tile(pg,n):
    return pg.locator("#rooms .room").filter(has=pg.locator(".room-n",has_text=re.compile(r"^%d$"%n)))
P=F=0
def ck(name,cond):
    global P,F
    print(("PASS " if cond else "FAIL ")+name); P,F=(P+1,F) if cond else (P,F+1)
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":430,"height":930},device_scale_factor=2)
    pg.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body=SDK))
    pg.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,content_type="application/javascript",body="/*n*/"))
    pg.route("**firebasedatabase.app/**",fb)
    pg.route("**/menu.json*",lambda r,_:r.fulfill(status=200,content_type="application/json",body=json.dumps(menu)))
    pg.goto("http://localhost:8953/tally.html"); pg.wait_for_timeout(1500)

    # 1 tiles
    t=pg.evaluate("""()=>{
      const r={},tiles=document.querySelectorAll('#rooms .room');
      tiles.forEach(b=>{const n=b.querySelector('.room-n').textContent;
        r[n]={cls:b.className,pax:b.querySelector('.room-p').textContent,
              mark:b.querySelector('.mark')?(b.querySelector('.mark').className):''};});
      return {r,grp:!!document.querySelector('.tilegrp'),
        grpRooms:[...(document.querySelector('.tilegrp')||{querySelectorAll:()=>[]}).querySelectorAll('.room-n')].map(e=>e.textContent)};}""")
    ck("room1 dining + guest icon", "room in" in t["r"]["1"]["cls"] and t["r"]["1"]["mark"]=="mark")
    ck("room2 declined", "room out" in t["r"]["2"]["cls"])
    ck("room5 vacant", "room vacant" in t["r"]["5"]["cls"])
    ck("room6 dining 3p staff", t["r"]["6"]["pax"]=="3p")
    ck("room9 awaiting + link-opened mark", "await" in t["r"]["9"]["cls"] and "seen" in t["r"]["9"]["mark"])
    ck("rooms 3+4 ringed as a group", t["grp"] and t["grpRooms"]==["3","4"])

    # 2 stats + tables
    s2=pg.evaluate("""()=>({c:+nCovers.textContent,o:+nOut.textContent,a:+nAwait.textContent,
        warn:tileAwait.className,tl:tablesLine.textContent})""")
    ck("covers 9", s2["c"]==9)
    ck("rooms out 1", s2["o"]==1)
    ck("awaiting 12 + red number", s2["a"]==12 and "warn" in s2["warn"])
    ck("tables line named not multiplied",
       "3 twos" in s2["tl"] and "1 three" in s2["tl"] and "×" not in s2["tl"]
       and "4 tables" in s2["tl"])

    wrap=pg.evaluate("""()=>{const t=document.getElementById('tablesLine');
      const prev=t.textContent;
      t.textContent='11 twos \u00b7 2 threes \u00b7 1 four \u00b7 1 five \u00b7 15 tables';
      const r=document.createRange(); r.selectNodeContents(t);
      const lines=new Set([...r.getClientRects()].map(b=>Math.round(b.top))).size;
      const over=t.scrollWidth>t.clientWidth;
      t.textContent=prev;
      return {lines:lines, over:over};}""")
    print("   busiest make-up:", wrap)
    ck("make-up line stays on one line at 390pt, even a full house",
       wrap["lines"]==1 and not wrap["over"])
    # 3 bookings list
    bl=pg.evaluate("""()=>{
      const rows=[...document.querySelectorAll('#listBookings .row')];
      return {n:rows.length,
        stub:!!document.querySelector('.row.stubrow'),
        stubTxt:(document.querySelector('.row.stubrow')||{}).textContent||'',
        grpbox:!!document.querySelector('.grpbox'),
        conflict:!!document.querySelector('.row.conflict .bub.flag'),
        ext:[...rows].some(r=>r.textContent.includes('External'))};}""")
    ck("stub row for silent group member", bl["stub"] and "4" in bl["stubTxt"] and "Awaiting" in bl["stubTxt"])
    ck("group boxed in bookings", bl["grpbox"])
    ck("dietary conflict flagged", bl["conflict"])
    ck("external booking listed", bl["ext"])

    # menu pill
    ck("menu published pill", "Menu published" in pg.locator("#menuState").inner_text())
    pg.locator("#navBtn").click(); pg.wait_for_timeout(150)
    ck("nav menu opens on tap", pg.evaluate("()=>navDrop.classList.contains('open')"))
    pg.locator(".stats").click(); pg.wait_for_timeout(150)

    # 4 notes bubble
    pg.locator(".row.conflict .bub").click(); pg.wait_for_timeout(200)
    sh=pg.locator("#sheet").inner_text()
    ck("notes sheet shows dish conflict + guest note", "Satay Chicken" in sh and "Nut allergy" in sh and "Window seat" in sh)
    pg.locator("#npClose").click(); pg.wait_for_timeout(150)

    # tap targets (while a notes bubble is on screen)
    tt=pg.evaluate("""()=>{const d=document.querySelector('#dPrev');const r=d.getBoundingClientRect();
      const bub=document.querySelector('.bub'); const ps=bub?getComputedStyle(bub,'::after'):null; const br=ps?(ps.top+'|'+ps.content):'';
      return {w:r.width,h:r.height,bub:br};}""")
    ck("dnav 36x36", abs(tt["w"]-36)<1 and abs(tt["h"]-36)<1)
    # the bubble is a 20px icon with an 11px pad each side: a 42px tap target
    ck("bubble hit area extended", tt["bub"].startswith("-11px"))

    sp=pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#listBookings .row')];
      const pax=[...new Set(rows.filter(r=>r.querySelector('.row-right'))
        .map(r=>Math.round(r.querySelector('.row-right').getBoundingClientRect().right)))];
      const gaps=[...new Set(rows.filter(r=>r.querySelector('.row-name')).map(r=>{const n=r.querySelector('.row-name');
        const nx=r.querySelector('.dietline')||r.querySelector('.row-sub');
        return nx? Math.round(nx.getBoundingClientRect().top-n.getBoundingClientRect().bottom):null;})
        .filter(x=>x!==null))];
      return {paxEdges:pax, gaps:gaps};}""")
    print("   spacing:", sp)
    ck("a note never shifts the pax column", len(sp["paxEdges"])==1)
    ck("one gap under the name whatever follows it", max(sp["gaps"])-min(sp["gaps"])<=1)
    # 5 staff sets room 9 dining pax4
    tile(pg,9).click(); pg.wait_for_timeout(200)
    ck("open-room sheet shows seen note", "opened the link" in pg.locator("#sheet").inner_text())
    pg.locator(".pax", has_text="4").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    w=[x for x in WRITES if "/manual/"+today+"/room-9" in x["u"] and x["m"]=="PUT"]
    ck("PUT room-9 pax4 in", len(w)==1 and json.loads(w[0]["b"])["pax"]==4 and json.loads(w[0]["b"])["status"]=="in")
    s5=pg.evaluate("()=>({c:+nCovers.textContent,a:+nAwait.textContent})")
    ck("covers 13 awaiting 11 after save", s5["c"]==13 and s5["a"]==11)

    # 6 rollback on failure
    STATE["fail"]=True
    tile(pg,10).click(); pg.wait_for_timeout(200)
    pg.locator("#oIn").click(); pg.wait_for_timeout(400)
    err=pg.locator("#errBar").inner_text()
    s6=pg.evaluate("()=>({c:+nCovers.textContent,cls:[...document.querySelectorAll('#rooms .room')].find(b=>b.querySelector('.room-n').textContent==='10').className})")
    ck("failed write shows error banner", "Not saved" in err)
    ck("failed write rolled back (tile await, covers 13)", "await" in s6["cls"] and s6["c"]==13)
    STATE["fail"]=False

    # colours must resolve to real pixels, not classes
    col=pg.evaluate("""()=>{
      const bg=e=>e?getComputedStyle(e).backgroundColor:'none';
      const inTile=[...document.querySelectorAll('#rooms .room')].find(b=>b.className.includes(' in'));
      return {tile:bg(inTile)};}""")
    ck("dining tile tint resolves", col["tile"].startswith("rgba(122, 160, 130"))
    tile(pg,10).click(); pg.wait_for_timeout(200)
    col2=pg.evaluate("""()=>({din:getComputedStyle(document.querySelector('.opt.solid')).backgroundColor,
      out:getComputedStyle(document.querySelector('.opt.out')).backgroundColor,
      vac:getComputedStyle(document.querySelector('.opt.vac')).backgroundColor})""")
    ck("sheet buttons green/terra/slate", col2["din"]=="rgb(94, 125, 103)" and col2["out"]=="rgb(158, 100, 85)" and col2["vac"]=="rgb(87, 87, 94)")
    pg.locator("#oClose").click(); pg.wait_for_timeout(150)

    # 7 select multiple + combine
    pg.locator("#selToggle").click()
    tile(pg,11).click()
    tile(pg,12).click()
    pg.wait_for_timeout(150)
    _sc=pg.evaluate("()=>({t:selCount.textContent,cls:selBar.className,sel:Object.keys(window.selected||{})})")
    print("   selbar state:",_sc)
    ck("selbar shows 2 selected", "2 rooms" in _sc["t"])
    sb=pg.evaluate("""()=>{const b=document.getElementById('selBar');const r=b.getBoundingClientRect();
      const din=getComputedStyle(document.getElementById('sbDin')).backgroundColor;
      const rows=[...b.querySelectorAll('.selbtn')].map(x=>Math.round(x.getBoundingClientRect().height));
      return {pos:getComputedStyle(b).position,top:Math.round(r.top),bottom:Math.round(r.bottom),vh:window.innerHeight,din,rows};}""")
    print("   selbar geom:", sb)
    ck("selbar fixed, pinned to bottom, fully on screen", sb["pos"]=="fixed" and abs(sb["bottom"]-sb["vh"])<=1 and sb["top"]>60)
    ck("selbar buttons coloured + sane height", sb["din"]=="rgb(94, 125, 103)" and all(38<=h<=56 for h in sb["rows"]))
    pg.locator("#sbComb").click(); pg.wait_for_timeout(300)
    wc=[x for x in WRITES if "/combined/" in x["u"]]
    okc=False
    if wc:
        bodyc=json.loads(wc[-1]["b"])
        okc=any(sorted(v.get("rooms",[]))==["11","12"] for v in bodyc.values())
    ck("combine PUT with rooms 11+12", okc)
    grp2=pg.evaluate("""()=>[...document.querySelectorAll('.tilegrp')].map(g=>[...g.querySelectorAll('.room-n')].map(e=>e.textContent).join(','))""")
    ck("11+12 ringed on grid", "11,12" in grp2)
    pg.locator("#selToggle").click()
    tile(pg,11).click()
    tile(pg,12).click()
    pg.wait_for_timeout(150)
    _u=pg.evaluate("()=>({btn:sbComb.textContent,sel:Object.keys(window.selected||{}),comb:JSON.stringify(window.combined)})")
    print("   uncombine state:",_u)
    ck("same selection offers Seat separately", "Seat separately" in _u["btn"])
    pg.locator("#sbDone").click(); pg.wait_for_timeout(150)

    # 8 add external
    pg.locator("#addExt").click(); pg.wait_for_timeout(200)
    pg.fill("#xName","Walk In"); pg.fill("#xPhone","0499 111 222")
    pg.locator(".pax", has_text="5").click()
    pg.locator(".chip", has_text="Vegan").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    we=[x for x in WRITES if re.search(r"/manual/"+today+r"/ext-\d+", x["u"])]
    okx=len(we)==1 and json.loads(we[0]["b"])["pax"]==5 and "Vegan" in json.loads(we[0]["b"])["diets"]
    ck("external PUT pax5 vegan", okx)
    ck("external row appears; covers 18", pg.evaluate("()=>+nCovers.textContent")==18 and "Walk In" in pg.locator("#listBookings").inner_text())

    # add reservation for an in-house room with details
    pg.locator("#addExt").click(); pg.wait_for_timeout(200)
    ck("sheet titled Add reservation", "add reservation" in pg.locator("#sheet h3").inner_text().lower())
    pg.locator("#segRoom").click(); pg.wait_for_timeout(150)
    pg.locator(".rmp", has_text=re.compile(r"^12$")).click()
    pg.fill("#xName","Chef Guest")
    pg.locator(".pax", has_text="3").click()
    pg.locator(".chip", has_text="Gluten free").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    wr=[x for x in WRITES if re.search(r"/manual/"+today+r"/room-12\.json",x["u"]) and x["m"]=="PUT"]
    okr=len(wr)==1 and json.loads(wr[0]["b"])["name"]=="Chef Guest" and "Gluten free" in json.loads(wr[0]["b"])["diets"] and json.loads(wr[0]["b"])["pax"]==3
    ck("room reservation PUT with name+diets", okr)
    ck("room 12 tile dining, row shows name", "in" in pg.evaluate("()=>[...document.querySelectorAll('#rooms .room')].find(b=>b.querySelector('.room-n').textContent==='12').className") and "Chef Guest" in pg.locator("#listBookings").inner_text())

    # room edit shows guest data; pax update preserves details
    tile(pg,12).click(); pg.wait_for_timeout(200)
    sh12=pg.locator("#sheet").inner_text()
    ck("room sheet shows guest data", "Chef Guest" in sh12 and "Gluten free" in sh12)
    pg.locator(".pax", has_text="4").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    wr2=[x for x in WRITES if re.search(r"/manual/"+today+r"/room-12\.json",x["u"])][-1]
    b12=json.loads(wr2["b"])
    ck("pax update kept name+diets", b12["pax"]==4 and b12.get("name")=="Chef Guest" and "Gluten free" in b12.get("diets",[]))

    # order independence: bulk Dining then Seat together must not touch the reservation
    pg.locator("#selToggle").click()
    tile(pg,12).click(); tile(pg,13).click(); pg.wait_for_timeout(150)
    pg.locator("#sbDin").click(); pg.wait_for_timeout(300)
    wb=[x for x in WRITES if re.search(r"/manual/"+today+r"/room-12\.json",x["u"])][-1]
    bb=json.loads(wb["b"])
    ck("bulk Dining kept name, diets and pax 4", bb.get("name")=="Chef Guest" and "Gluten free" in bb.get("diets",[]) and bb["pax"]==4)
    pg.locator("#selToggle").click()
    tile(pg,12).click(); tile(pg,13).click(); pg.wait_for_timeout(150)
    _st=pg.evaluate("()=>({btn:sbComb.textContent,sel:Object.keys(window.selected||{}),comb:JSON.stringify(window.combined),mode:window.selectMode})")
    print("   seat state:",_st)
    ck("button reads Seat together", "Seat together" in _st["btn"])
    pg.locator("#sbComb").click(); pg.wait_for_timeout(300)
    ck("reservation survives seating", "Chef Guest" in pg.locator("#listBookings").inner_text())
    ck("12+13 ringed", "12,13" in pg.evaluate("()=>[...document.querySelectorAll('.tilegrp')].map(g=>[...g.querySelectorAll('.room-n')].map(e=>e.textContent).join(','))"))
    tile(pg,12).click(); pg.wait_for_timeout(200)
    ck("room sheet notes seating + keeps guest data", "Seated with Villa 13" in pg.locator("#sheet").inner_text() and "Chef Guest" in pg.locator("#sheet").inner_text())
    pg.locator("#oClose").click(); pg.wait_for_timeout(150)

    # Edit details on a digital room booking (room 3, Mark)
    tile(pg,3).click(); pg.wait_for_timeout(200)
    pg.locator("#oDetails").click(); pg.wait_for_timeout(200)
    ck("details form prefilled with Mark", pg.evaluate("()=>xName.value")=="Mark")
    pg.fill("#xPhone","0400 333 333")
    pg.locator(".chip", has_text="Vegan").click()
    pg.locator("#oSave").click(); pg.wait_for_timeout(300)
    w3=[x for x in WRITES if re.search(r"/manual/"+today+r"/room-3\.json",x["u"])]
    b3=json.loads(w3[-1]["b"])
    ck("details save: override with phone+diets, pax kept", b3.get("override")==True and b3["phone"]=="0400 333 333" and "Vegan" in b3["diets"] and b3["pax"]==2 and b3["name"]=="Mark")
    ck("row shows new dietary", "VEGAN" in pg.locator("#listBookings").inner_text().upper())

    pm=pg.evaluate("""()=>{const r=[...document.querySelectorAll('#listBookings .row')]
        .find(x=>/Mark/.test(x.textContent));
      return r ? {txt:r.innerText.replace(/\\n/g,' | ')} : null;}""")
    print("   villa 3 after staff override:", pm)
    ck("staff override keeps the guest's pre-menu tag",
       pm and "PRE-MENU" in pm["txt"].upper())
    dp=pg.evaluate("""()=>{const r=[...document.querySelectorAll('#listBookings .row')]
        .find(x=>x.querySelector('.dpill'));
      if(!r) return null;
      const pills=[...r.querySelectorAll('.dpill')].map(e=>({t:e.textContent,
        al:e.className.includes('dpill-al'), bg:getComputedStyle(e).backgroundColor}));
      const line=r.querySelector('.dietline').getBoundingClientRect();
      const nm=r.querySelector('.row-name').getBoundingClientRect();
      const ph=r.querySelector('.phinline');
      return {pills:pills, below: Math.round(line.top) >= Math.round(nm.bottom)-1,
              phoneOnNameLine: ph ? Math.abs(Math.round(ph.getBoundingClientRect().top - nm.top))<12 : null};}""")
    print("   pills:", dp)
    ck("dietaries render as pills below the name, phone on the name line",
       dp and len(dp["pills"])>0 and dp["below"] and dp["phoneOnNameLine"] is not False)
    ck("allergy pill solid, word 'allergy' dropped",
       all(("ALLERGY" not in p["t"].upper()) for p in dp["pills"] if p["al"]))

    geo=pg.evaluate("""()=>{const rows=[...document.querySelectorAll('#listBookings .row')];
      const w=r=>Math.round(r.getBoundingClientRect().width);
      const grouped=[...new Set(rows.filter(r=>r.closest('.grpbox')).map(w))];
      const plain=[...new Set(rows.filter(r=>!r.closest('.grpbox')).map(w))];
      const dropped=rows.filter(r=>{const n=r.querySelector('.row-name'),t=r.querySelector('.row-right');
        return n&&t&&Math.round(t.getBoundingClientRect().top)>Math.round(n.getBoundingClientRect().bottom)-2;}).length;
      return {grouped, plain, dropped, overflow:document.scrollingElement.scrollWidth-innerWidth};}""")
    print("   row geometry:", geo)
    ck("grouping a booking does not narrow its row",
       geo["grouped"] and geo["plain"] and set(geo["grouped"])==set(geo["plain"]))
    ck("no row wraps and nothing overflows the screen",
       geo["dropped"]==0 and geo["overflow"]<=0)
    ov=pg.evaluate("""()=>{const n=document.querySelector('#listBookings .row-name .nm');
      const long='Konstantinos Papadopoulos';
      const keep=n.innerHTML; n.innerHTML=long;
      const r={doc: document.scrollingElement.scrollWidth - innerWidth,
               nameLines: Math.round(n.getBoundingClientRect().height) <= 20};
      n.innerHTML=keep; return r;}""")
    print("   long name:", ov)
    ck("a long name never widens the page, and never breaks mid-name",
       ov["doc"]<=0 and ov["nameLines"])    # guest data on a digital room booking's sheet
    tile(pg,1).click(); pg.wait_for_timeout(200)
    sh1=pg.locator("#sheet").inner_text()
    ck("digital room sheet shows name+phone+diets+note", "James" in sh1 and "0400 000 001" in sh1 and "Nut allergy" in sh1 and "Window seat" in sh1)
    pg.locator("#oClose").click(); pg.wait_for_timeout(150)

    # manual external edit: prefilled, save changes
    row=pg.locator("#listBookings .row", has_text="Walk In")
    row.locator(".edit").click(); pg.wait_for_timeout(200)
    ck("edit prefilled", pg.evaluate("()=>xName.value")=="Walk In")
    pg.fill("#xName","Walk In Party")
    pg.locator("#oSave").click(); pg.wait_for_timeout(300)
    we2=[x for x in WRITES if re.search(r"/manual/"+today+r"/ext-\d+",x["u"])][-1]
    ck("external save-changes PUT", json.loads(we2["b"])["name"]=="Walk In Party")
    ck("row renamed", "Walk In Party" in pg.locator("#listBookings").inner_text())

    # 9 override cancel of guest booking (room 1)
    tile(pg,1).click(); pg.wait_for_timeout(200)
    ck("guest-confirmed sheet", "Confirmed by the guest" in pg.locator("#sheet").inner_text())
    pg.locator("#oCancel").click(); pg.wait_for_timeout(200)
    pg.locator("#cYes").click(); pg.wait_for_timeout(300)
    wo=[x for x in WRITES if re.search(r"/room-1\.json", x["u"]) and x["m"]=="PUT"]
    oko=len(wo)==1 and json.loads(wo[0]["b"])["override"]==True and json.loads(wo[0]["b"])["status"]=="out"
    ck("override cancel PUT", oko)
    ck("room1 shows guest-cancelled icon", pg.evaluate("""()=>{
      const b=[...document.querySelectorAll('#rooms .room')].find(x=>x.querySelector('.room-n').textContent==='1');
      return b.className.includes('out') && !!b.querySelector('.mark svg line');}"""))

    shot1=pg.screenshot(full_page=True)

    # 11 off-today
    pg.goto("http://localhost:8953/tally.html?date="+plus(1)); pg.wait_for_timeout(1200)
    off=pg.evaluate("""()=>({today:!dToday.disabled && getComputedStyle(dToday).display!=='none',
      href:[...document.querySelectorAll('.navdrop a')].find(a=>a.href.includes('list')).getAttribute('href')})""")
    ck("Today button enabled off-today", off["today"])
    ck("print link carries browsed date", off["href"]=="list.html?date="+plus(1))
    ft=pg.evaluate("""()=>{const f=document.querySelector('.foot');const r=f.getBoundingClientRect();
      return {b:Math.round(r.bottom),vh:window.innerHeight,doc:document.scrollingElement.scrollHeight};}""")
    print("   short page:", ft)
    ck("footer pinned to screen bottom on short page", abs(ft["b"]-ft["vh"])<=1)
    nav=pg.evaluate("""()=>[...document.querySelectorAll('.navdrop a')].map(a=>({
      t:a.textContent,h:Math.round(a.getBoundingClientRect().height),
      href:a.getAttribute('href').split('?')[0]}))""")
    print("   nav items:", nav)
    ck("menu labels and order",
       [i["t"] for i in nav]==["Reservations Sheet","Cleans","Clean sheet"] and
       [i["href"] for i in nav]==["list.html","cleaners.html","housekeeping.html"])
    ck("no menu label wraps to a second line", all(i["h"]<=38 for i in nav))
    rad=pg.evaluate("""()=>[...document.querySelectorAll('.foot .btn')].map(b=>{
      const c=getComputedStyle(b);
      return [c.borderTopLeftRadius,c.borderTopRightRadius,
              c.borderBottomRightRadius,c.borderBottomLeftRadius].join('|');})""")
    print("   foot radii:", rad)
    ck("footer outer lower corners rounded, inner corners square",
       len(rad)==2 and rad[0]=="0px|0px|0px|8px" and rad[1]=="0px|0px|8px|0px")
    pg.close(); b.close()
    open("/home/claude/nala/_p1_tally.png","wb").write(shot1)
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
