import errortrap   # fails the run if any page throws
import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=http.server.ThreadingHTTPServer(("",8953),Q)
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
# Villa 9 as Mews has it. Same name and departure as the guest written record,
# so nothing on the board shifts and the only new fact is the party size, which
# Mews knows and the app used to store and show nowhere.
stays={today:{"9":{"id":"res-9","first":"Priya","last":"","arrive":plus(-1),
                   "depart":plus(3),"adults":2,"updated":"2026-08-16T10:00:00Z"}}}
# Villa 9 pressed the menu link tonight and has not answered. Until 19 Aug this
# was inferred from the guest written roomguests record above, which stopped
# being written on 17 Aug, so the fixture was asserting a signal the live app
# could no longer produce. It is now a fact of its own, filed by night.
opened={today:{"9":{"at":now.isoformat(),"bookingId":"res-9"}}}
combined={"g1":{"rooms":["3","4"]}}
menu={"published":now.isoformat(),"bread":{"name":"Sourdough"},"entree":{"name":"Prawns"},
      "main":{"name":"Satay Chicken"},"dessert":{"name":"Pavlova"}}
menutags={"main":["Nut allergy"]}
staff={"staff@x":{"name":"Admin","role":"admin"},
       "chef@x":{"name":"Chef","role":"chef"},
       "waiter@x":{"name":"Waiter","role":"waiter"},
       "desk@x":{"name":"Desk","role":"staff"},
       "housekeeping@x":{"name":"Housekeeping","role":"housekeeping"}}
def fb(route,request):
    u=request.url; m=request.method
    if m in ("PUT","DELETE","PATCH"):
        WRITES.append({"m":m,"u":u,"b":request.post_data})
        if STATE["fail"]:
            route.fulfill(status=401,content_type="application/json",body='{"error":"denied"}'); return
        route.fulfill(status=200,content_type="application/json",body=request.post_data or "null"); return
    body="null"
    if "/staff" in u: body=json.dumps(staff)
    elif "/responses/" in u: body=json.dumps(responses) if today in u else "{}"
    elif "/manual/" in u and today not in u: body="{}"
    elif "/manual/" in u: body=json.dumps(manual)
    elif "/stays/"+today in u: body=json.dumps(stays[today])
    elif "/stays/" in u: body="null"
    elif "/roomguests/"+today in u: body=json.dumps(roomguests[today])
    elif "/roomguests/" in u: body="null"
    elif "/opened/"+today in u: body=json.dumps(opened[today])
    elif "/opened/" in u: body="null"
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
    # The other half of the same signal. Villa 4 is booked and has not opened
    # its link, so it must stay bare: an icon there would tell reception the
    # message landed when nothing says it did.
    ck("room4 booked but never opened carries no mark", t["r"]["4"]["mark"]=="")
    ck("rooms 3+4 ringed as a group", t["grp"] and t["grpRooms"]==["3","4"])

    # 2 stats + tables
    s2=pg.evaluate("""()=>({c:+nCovers.textContent,o:+nOut.textContent,a:+nAwait.textContent,
        warn:tileAwait.className,tl:tablesLine.textContent})""")
    ck("covers 9", s2["c"]==9)
    ck("rooms out 1", s2["o"]==1)
    # Awaiting means somebody is in the villa and has not answered. An empty
    # villa is not an outstanding question, so it is not counted as one: villa
    # 4 has a guest and no reply, villa 9 has a Mews booking and no reply.
    ck("awaiting counts only villas with a guest in them",
       s2["a"]==2 and "warn" in s2["warn"])
    # The default, which is the whole point of the change.
    ck("a villa nobody is booked into reads as vacant, not awaiting",
       "room vacant" in t["r"]["11"]["cls"])
    ck("and a villa with a Mews booking and no reply reads as awaiting",
       "await" in t["r"]["9"]["cls"])
    ck("a guest written record with no reply is awaiting too",
       "await" in t["r"]["4"]["cls"])
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
    ck("menu published pill", "menu published" in pg.locator("#menuState").inner_text().lower())
    # both states are the same pill: the published one renders as an <a>, so a
    # selector matching only span left it unstyled but for its background
    def pill(): return pg.evaluate("""()=>{const e=document.querySelector('.menustate > *');
      const cs=getComputedStyle(e);
      const b=e.getBoundingClientRect();
      const rng=document.createRange(); rng.selectNodeContents(e);
      const t=rng.getBoundingClientRect();
      /* letter-spacing leaves a trailing space inside the box, so the text
         box is NOT the ink. Check the right padding compensates for it. */
      return {fs:cs.fontSize, pad:cs.padding, tt:cs.textTransform,
              r:cs.borderRadius, h:Math.round(b.height),
              inkOff:(parseFloat(cs.paddingLeft) -
                      (parseFloat(cs.paddingRight)+parseFloat(cs.letterSpacing))).toFixed(2)};}""")
    pubPill = pill()
    realPill = pg.evaluate("()=>document.querySelector('.menustate').innerHTML")
    pg.evaluate("""()=>{document.querySelector('.menustate').innerHTML =
      '<span class="no">Menu not published</span>';}""")
    pg.wait_for_timeout(100)
    unpubPill = pill()
    print("   published:", pubPill, "\n   unpublished:", unpubPill)
    ck("published and unpublished are the same pill", pubPill == unpubPill)
    ck("the text sits centred in the pill", abs(float(pubPill["inkOff"])) < 0.2)
    pg.evaluate("(h)=>{document.querySelector('.menustate').innerHTML=h;}", realPill)
    pg.wait_for_timeout(120)
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
    # Mews knows the party size, and it must never seed the covers picker:
    # covers is how many are eating tonight, and defaulting it here would
    # inflate the kitchen's count for every villa that has not replied.
    #
    # It moved into the snapshot on 18 Aug. It used to sit beside the name as
    # well, and two copies on one sheet was what pushed a long name onto a
    # second line and into the menu button.
    pg.locator("#gdEye").click(); pg.wait_for_timeout(600)
    gd9 = pg.locator("#sheet .gd").inner_text()
    ck("the villa sheet shows the party size Mews knows", "2 adults" in gd9)
    ck("and shows it once, not twice", gd9.count("2 adults") == 1)
    # The sheet stands on 120px of bottom padding at all times, so the card
    # sits in one consistent place on every login and the snapshot has room
    # to drop DOWN from the name, its natural direction. Floating it up was
    # tried on 20 Aug and collided with the top of the screen on the logins
    # whose sheets are tall; toggled padding was tried the same day and
    # moved the card. The panel's height is capped to the room the sheet
    # actually has, with its own scroll beyond that.
    box = pg.locator("#gdPanel").bounding_box()
    eyb = pg.locator("#gdEye").bounding_box()
    ck("the open snapshot sits fully on screen, no scrolling to find it",
       bool(box) and box["y"] >= 0 and box["y"] + box["height"] <= 900)
    ck("and drops down from the name",
       bool(box) and bool(eyb) and box["y"] >= eyb["y"])
    pg.locator("#gdEye").click(); pg.wait_for_timeout(250)
    ck("and the covers picker is still the app's own default, not Mews'",
       pg.evaluate("()=>document.querySelector('#paxRow .pax.on').textContent")=="2")
    pg.locator(".pax", has_text="4").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    # Writes go to the one dinner cell now, keyed by villa. /manual held the
    # same fact as /dinner and /bookings, which is how a dietary added here
    # became invisible at the front desk.
    w=[x for x in WRITES if "/dinner/"+today+"/9" in x["u"] and x["m"]=="PUT"]
    ck("PUT villa 9 pax4 in", len(w)==1 and json.loads(w[0]["b"])["pax"]==4 and json.loads(w[0]["b"])["status"]=="in")
    ck("stamped as set by staff, which locks it against the guest's own link",
       len(w)==1 and json.loads(w[0]["b"])["by"]=="staff")
    s5=pg.evaluate("()=>({c:+nCovers.textContent,a:+nAwait.textContent})")
    # Villa 9 has now answered, so the only villa still awaiting is 4.
    ck("covers 13, and one villa still awaiting after the save",
       s5["c"]==13 and s5["a"]==1)

    # 6 rollback on failure
    STATE["fail"]=True
    tile(pg,10).click(); pg.wait_for_timeout(200)
    pg.locator("#oIn").click(); pg.wait_for_timeout(400)
    err=pg.locator("#errBar").inner_text()
    s6=pg.evaluate("()=>({c:+nCovers.textContent,cls:[...document.querySelectorAll('#rooms .room')].find(b=>b.querySelector('.room-n').textContent==='10').className})")
    ck("failed write shows error banner", "Not saved" in err)
    # Villa 10 has nobody booked into it, so rolling back returns it to vacant
    # rather than to awaiting: that is what it was before the tap.
    ck("failed write rolled back to what the tile was before",
       "room vacant" in s6["cls"] and s6["c"]==13)
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
    wr=[x for x in WRITES if re.search(r"/dinner/"+today+r"/12\.json",x["u"]) and x["m"]=="PUT"]
    okr=len(wr)==1 and json.loads(wr[0]["b"])["name"]=="Chef Guest" and "Gluten free" in json.loads(wr[0]["b"])["diets"] and json.loads(wr[0]["b"])["pax"]==3
    ck("room reservation PUT with name+diets", okr)
    ck("room 12 tile dining, row shows name", "in" in pg.evaluate("()=>[...document.querySelectorAll('#rooms .room')].find(b=>b.querySelector('.room-n').textContent==='12').className") and "Chef Guest" in pg.locator("#listBookings").inner_text())

    # room edit shows guest data; pax update preserves details
    tile(pg,12).click(); pg.wait_for_timeout(200)
    sh12=pg.locator("#sheet").inner_text()
    ck("room sheet shows guest data", "Chef Guest" in sh12 and "Gluten free" in sh12)
    pg.locator(".pax", has_text="4").click()
    pg.locator("#oIn").click(); pg.wait_for_timeout(300)
    wr2=[x for x in WRITES if re.search(r"/dinner/"+today+r"/12\.json",x["u"])][-1]
    b12=json.loads(wr2["b"])
    ck("pax update kept name+diets", b12["pax"]==4 and b12.get("name")=="Chef Guest" and "Gluten free" in b12.get("diets",[]))

    # order independence: bulk Dining then Seat together must not touch the reservation
    pg.locator("#selToggle").click()
    tile(pg,12).click(); tile(pg,13).click(); pg.wait_for_timeout(150)
    pg.locator("#sbDin").click(); pg.wait_for_timeout(300)
    wb=[x for x in WRITES if re.search(r"/dinner/"+today+r"/12\.json",x["u"])][-1]
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
    w3=[x for x in WRITES if re.search(r"/dinner/"+today+r"/3\.json",x["u"])]
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
    wo=[x for x in WRITES if re.search(r"/dinner/[^\"]*/1\.json", x["u"]) and x["m"]=="PUT"]
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
    dest=[i for i in nav if i["href"]!="#"]
    # Live board then its sheet, reservations before cleans. Front Desk
    # Arrival sits with reservations, after the board it feeds.
    #  Grouped 22 Aug, to the owner's own sketch: the screens you work on, then
    #  what you print, then what you set. Named as the staff name them rather
    #  than as the files are named - the sheet everyone calls the FOH sheet was
    #  labelled Reservations Sheet, and Registration is the arrivals print.
    ck("menu labels and order",
       [i["t"] for i in dest]==["Front Desk","Cleans","Publish Menu",
                                "FOH Sheet","Clean Sheet","Arrivals",
                                "General","Dietary","Pages"] and
       [i["href"] for i in dest]==["front-desk.html","cleaners.html","publish.html",
                                   "list.html","housekeeping.html","registration.html",
                                   "staff.html","tag.html","pages.html"])
    #  Headings, not choices. Light grey and small so a signpost is not mistaken
    #  for a destination.
    grp = pg.evaluate("""()=>[...document.querySelectorAll('#navDrop .navgrp')]
        .map(e=>({t:e.textContent, tag:e.tagName,
                  c:getComputedStyle(e).color,
                  rule:getComputedStyle(e).borderTopWidth}))""")
    print("   nav groups:", grp)
    ck("the menu is divided under two headings", [g["t"] for g in grp] == ["Print", "Settings"])
    ck("and they are not links", all(g["tag"] != "A" for g in grp))
    ck("each sitting under a rule that does the dividing",
       all(g["rule"] != "0px" for g in grp))
    # signing out is an action, so it comes last, after the destinations
    ck("sign out is the last item in the menu", nav[-1]["t"]=="Sign out")
    ck("no menu label wraps to a second line", all(i["h"]<=38 for i in nav))
    rad=pg.evaluate("""()=>[...document.querySelectorAll('.foot .btn')].map(b=>{
      const c=getComputedStyle(b);
      return [c.borderTopLeftRadius,c.borderTopRightRadius,
              c.borderBottomRightRadius,c.borderBottomLeftRadius].join('|');})""")
    print("   foot radii:", rad)
    ck("footer outer lower corners rounded, inner corners square",
       len(rad)==2 and rad[0]=="0px|0px|0px|8px" and rad[1]=="0px|0px|8px|0px")
    # Reservations had no auto refresh at all, only the manual button
    hits=[]
    pg.on("request", lambda r: hits.append(r.url) if "firebasedatabase.app" in r.url else None)
    pg.evaluate("()=>load()"); pg.wait_for_timeout(700)
    poll=len(hits)
    print("   one poll:", poll, "requests")
    ck("the board can reload itself", pg.evaluate("()=>typeof load==='function'"))
    ck("a poll skips the fortnight of roomguests (%d requests)" % poll,
       poll>0 and not any("/roomguests/" in u for u in hits))
    ck("it stands down mid multi-select",
       pg.evaluate("()=>{selectMode=true; const b=busy(); selectMode=false; return b;}"))
    ck("and runs when nothing is in progress", pg.evaluate("()=>!busy()"))

    pg.close()

    # ---- roles on this board, per the ROLES.md matrix ----
    def as_role(email):
        q=b.new_page(viewport={"width":430,"height":930},device_scale_factor=2)
        q.route("**/firebase-app-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body=SDK.replace("staff@x",email)))
        q.route("**/firebase-auth-compat.js",lambda r,_:r.fulfill(status=200,
            content_type="application/javascript",body="/*n*/"))
        q.route("**firebasedatabase.app/**",fb)
        q.route("**/menu.json*",lambda r,_:r.fulfill(status=200,
            content_type="application/json",body=json.dumps(menu)))
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1500)
        return q

    # the chef opens the app to see who is eating and what they cannot have,
    # so the board stays; every way of writing to it goes
    q=as_role("chef@x")
    st=q.evaluate("""()=>({rooms:document.querySelectorAll('#rooms .room').length,
        blocked:noAccess.className.indexOf('show')>-1,
        sel:selToggle?getComputedStyle(selToggle).display:'gone',
        add:addExt?getComputedStyle(addExt).display:'gone',
        edit:window.CAN_EDIT, role:window.NALA_ROLE})""")
    ck("chef reads the board", not st["blocked"] and st["rooms"]>0 and st["role"]=="chef")
    ck("chef cannot edit bookings", st["edit"] is False)
    ck("chef gets no select-multiple and no add reservation",
       st["sel"]=="none" and st["add"]=="none")
    # the chef opens the sheet to READ it: the phone, the dietaries and the
    # comment are the reason they open the app at all
    q.evaluate("()=>openRoom(1, roomState(1))"); q.wait_for_timeout(400)
    live=q.evaluate("""()=>[].filter.call(document.querySelectorAll('#sheet button'),
        e=>getComputedStyle(e).display!=='none').map(e=>e.textContent.trim())""")
    txt=q.evaluate("()=>sheet.innerText")
    ck("chef opens the sheet and sees the guest's details",
       "0400" in txt and "allergy" in txt.lower())
    # The eye is excluded by id, not by trusting its label. It reveals what the
    # app already holds and writes nothing, and the chef is the person who most
    # wants it: they open this sheet to read the dietaries and the comment.
    # Everything else on a chef's sheet must still be Close and only Close.
    # Both controls belonging to the snapshot are excluded by id, not by
    # trusting their labels. Neither writes anything: one opens the panel and
    # one shuts it again.
    writes = q.evaluate("""()=>[].filter.call(document.querySelectorAll('#sheet button'),
        e=>getComputedStyle(e).display!=='none'
           && e.id!=='gdEye' && e.id!=='gdClose')
        .map(e=>e.textContent.trim())""")
    ck("chef's sheet offers nothing that writes, only Close",
       [x.lower() for x in writes]==["close"])
    ck("the chef is offered the guest snapshot, which only reads",
       q.evaluate("()=>!!document.getElementById('gdEye')"))
    ck("chef still sees the guest count, as a fact not a picker",
       q.evaluate("()=>!!document.querySelector('#paxRow .pax-fact') && !document.querySelector('#paxRow button')"))
    print("   chef sheet buttons:", live)
    print("   chef on Reservations: rooms=%s edit=%s" % (st["rooms"],st["edit"]))
    q.close()

    # a waiter has the same board and may write to it
    q=as_role("staff@x")
    q.evaluate("()=>openRoom(1, roomState(1))"); q.wait_for_timeout(400)
    ck("staff keeps the pax picker and the write controls",
       q.evaluate("""()=>document.querySelectorAll('#paxRow button').length===6
                      && !!document.getElementById('oSave')
                      && getComputedStyle(document.getElementById('oSave')).display!=='none'"""))
    q.close()

    q=as_role("waiter@x")
    ck("waiter keeps the full board",
       q.evaluate("()=>window.CAN_EDIT===true && noAccess.className.indexOf('show')<0"))
    q.close()

    # housekeeping is ROUTED, not refused: their own board is the right first
    # screen, and a refusal was the wrong answer to a routing problem
    q=as_role("housekeeping@x")
    q.wait_for_timeout(600)
    ck("housekeeping is sent to the Cleans board, not shown a refusal",
       q.url.endswith("cleaners.html"))
    q.close()

    # ── a new Mews reservation turns vacant into awaiting ──────
    # The spec, in the owner's words on 18 Aug: vacant means no guest profile
    # is attached to the villa; awaiting means one is, with no yes or no to
    # dinner for that day. A reservation arriving from Mews is what moves a
    # villa from the first to the second, for every night of the stay.
    q = as_role("staff@x"); q.wait_for_timeout(400)
    def tilecls(pg_, n):
        return pg_.evaluate("n=>[...document.querySelectorAll('#rooms .room')]"
                            ".find(b=>b.querySelector('.room-n').textContent===n).className", str(n))
    ck("villa 13 starts vacant, nobody is booked into it",
       "room vacant" in tilecls(q, 13))
    stays[today]["13"] = {"id":"res-13","first":"Nina","last":"Roy",
                          "arrive":plus(-1),"depart":plus(2),"adults":2,
                          "updated":"2026-08-18T02:00:00Z"}
    q.evaluate("()=>load(true)"); q.wait_for_timeout(900)
    ck("a reservation arriving from Mews turns it to awaiting",
       "await" in tilecls(q, 13))
    ck("and it is counted as a villa awaiting an answer",
       q.evaluate("()=>+nAwait.textContent") >= 1)
    del stays[today]["13"]
    q.evaluate("()=>load(true)"); q.wait_for_timeout(900)
    ck("and back to vacant when the reservation goes",
       "room vacant" in tilecls(q, 13))
    # An empty record is not a guest. roomguests carries these around from
    # older writes, and one of them counting as a booking made the board look
    # busier than the resort was.
    roomguests[today]["15"] = {}
    q.evaluate("()=>load(true)"); q.wait_for_timeout(900)
    ck("an empty record does not make a villa look occupied",
       "room vacant" in tilecls(q, 15))
    del roomguests[today]["15"]
    q.close()

    # ── the manager is told when a menu is published ───────────
    # The chef publishes by pushing a commit, so nothing in the database moves
    # and there is nothing to watch. Something signed in has to notice. This
    # used to hang off the Reservations board's own load, which meant the
    # manager was told when a manager happened to have this one board open.
    # It now lives in nala-shared.js and every signed in page announces it, so
    # the chef opening the tagging page is what tells management. Still must
    # not fire twice: the archive row is the record of having announced it.
    pushes = []
    q = as_role("staff@x")
    q.route("**/nala-push*/**", lambda r, req: (pushes.append(req.post_data),
        r.fulfill(status=200, content_type="application/json", body="{}")))
    q.route("**nala-push*", lambda r, req: (pushes.append(req.post_data),
        r.fulfill(status=200, content_type="application/json", body="{}")))
    q.reload(); q.wait_for_timeout(1800)
    ck("publishing a menu notifies", any('"event":"menu"' in (p or "") for p in pushes))
    # No actor. Everywhere else the actor is the person who tapped, so they are
    # not told about their own action. Here the chef caused it and the manager
    # merely has a board open: naming them would suppress the one notification
    # this exists to send.
    ck("and names nobody as having caused it, so nobody is excluded",
       all('"actor":""' in (p or "") or '"actor":null' in (p or "")
           for p in pushes if '"event":"menu"' in (p or "")))
    before = len(pushes)
    q.evaluate("()=>load(true)"); q.wait_for_timeout(1200)
    ck("and does not notify again on the next poll", len(pushes) == before)
    q.close()

    # ── a note belongs to a night ──────────────────────────────
    # roomguests is carried forward across a stay so a guest keeps their villa.
    # Anything left on an old record there is from an earlier night, and shown
    # as tonight's it is a stale dietary in front of the kitchen.
    roomguests[today]["11"] = {"name":"Carla","departs":plus(2),
                               "diets":["Shellfish allergy"],
                               "note":"quiet table",
                               "dnote":"severe, no cross contact"}
    responses["0400000011"] = {"status":"in","pax":2,"name":"Carla","room":"11",
                               "at":"2026-08-12T09:20:00"}
    q=as_role("staff@x"); q.wait_for_timeout(400)
    row=q.locator("#listBookings .row").filter(has_text="Carla").first
    ck("a dietary from an earlier night is not shown as tonight's",
       "Shellfish" not in row.inner_text())
    ck("but the villa still carries a bubble, so it is not hidden either",
       row.locator(".bub").count()==1)
    row.locator(".bub").click(); q.wait_for_timeout(400)
    # The headings are upper-cased in CSS, so compare on the rendered text.
    notes=q.locator("#sheet").inner_text().upper()
    ck("the bubble labels it as a previous night", "PREVIOUS DINING NOTES" in notes)
    ck("and shows what it was", "SHELLFISH" in notes)
    ck("and says not to cook to it without asking", "ASK BEFORE COOKING" in notes)
    ck("nothing is headed as tonight's that was not given tonight",
       "DINING NOTES" not in notes.replace("PREVIOUS DINING NOTES", ""))
    q.close()

    # The same villa once tonight's answer carries its own.
    responses["0400000011"] = {"status":"in","pax":2,"name":"Carla","room":"11",
                               "diets":["Vegan"],"note":"by the window",
                               "dnote":"no dairy at all","at":"2026-08-12T09:20:00"}
    q=as_role("staff@x"); q.wait_for_timeout(400)
    row=q.locator("#listBookings .row").filter(has_text="Carla").first
    ck("tonight's dietary is on the row", "VEGAN" in row.inner_text().upper())
    row.locator(".bub").click(); q.wait_for_timeout(400)
    notes=q.locator("#sheet").inner_text().upper()
    ck("tonight's dietaries are headed with their name",
       "DIETARY NOTES" in notes and "NO DAIRY AT ALL" in notes)
    ck("and nothing claims to be a note the guest has not written",
       "NO NOTE FROM THE GUEST" not in notes)
    ck("and tonight's answer replaces the old rather than sitting beside it",
       "PREVIOUS DINING NOTES" not in notes and "SHELLFISH" not in notes)
    ck("the dinner note is tonight's too, under its own name",
       "DINNER NOTES" in notes and "BY THE WINDOW" in notes)
    q.close()

    # A dinner note with no dietaries at all. The dietary section used to be
    # forced open by it and printed "No note from the guest yet": an empty
    # section apologising for being empty, above the one real note. Reported
    # from a phone on 20 Aug, villa 10, "Red shellfish".
    roomguests[today]["11"] = {"name":"Carla","departs":plus(2)}
    responses["0400000011"] = {"status":"in","pax":2,"name":"Carla","room":"11",
                               "note":"Red shellfish","at":"2026-08-12T09:20:00"}
    q=as_role("staff@x"); q.wait_for_timeout(400)
    row=q.locator("#listBookings .row").filter(has_text="Carla").first
    row.locator(".bub").click(); q.wait_for_timeout(400)
    notes=q.locator("#sheet").inner_text().upper()
    ck("a dinner note alone opens no dietary section",
       "DIETARY NOTES" not in notes)
    ck("and apologises for nothing", "NO NOTE FROM THE GUEST" not in notes)
    ck("the note itself is there under its name",
       "DINNER NOTES" in notes and "RED SHELLFISH" in notes)
    q.close()
    del responses["0400000011"]
    del roomguests[today]["11"]

    # ── the bubble's colour is one decision ─────────────────────────────
    # Worst wins: red to act on before cooking, amber to read, grey for
    # context the kitchen does not act on. Decided in bubbleState and
    # nowhere else, so it is tested as the function it is.
    q=as_role("staff@x"); q.wait_for_timeout(400)
    ck("a menu conflict is red",
       q.evaluate("()=>bubbleState([], {}, [{dish:'a',diet:'b'}], '')")=="red")
    ck("Other with nothing written is red",
       q.evaluate("()=>bubbleState([DIET_OTHER], {}, [], '')")=="red")
    ck("Other explained is not",
       q.evaluate("()=>bubbleState([DIET_OTHER], {dineDnote:'sesame'}, [], '')")=="amber")
    ck("a dietary note is amber",
       q.evaluate("()=>bubbleState([], {dineDnote:'x'}, [], '')")=="amber")
    ck("a dinner note is amber",
       q.evaluate("()=>bubbleState([], {dineNote:'x'}, [], '')")=="amber")
    ck("an earlier night's leavings are amber",
       q.evaluate("()=>bubbleState([], {prevDiets:['Vegan']}, [], '')")=="amber")
    ck("a booking note alone is grey",
       q.evaluate("()=>bubbleState([], {}, [], 'golf buggy please')")=="grey")
    ck("worst wins over grey",
       q.evaluate("()=>bubbleState([], {dineNote:'x'}, [], 'golf buggy')")=="amber")
    ck("nothing at all is no bubble",
       q.evaluate("()=>bubbleState([], {}, [], '')")=="")
    # The overlay settles provenance. Robyn's case, 20 Aug: Other ticked and
    # explained, but the note lived on the reservation only, the stamp runs
    # before the overlay, and the bubble read the stamped field: it called an
    # explained Other unexplained, went red, and opened onto nothing.
    ck("a reservation-only dietary note lands in the stamped field",
       q.evaluate("""()=>{PREARRIVAL_BY_VILLA['99']={diets:[DIET_OTHER],dnote:'Low tolerance to garlic'};
         const r=overlayReservationDiets({prevDnote:'old copy',prevDiets:['Vegan']},'99');
         delete PREARRIVAL_BY_VILLA['99'];
         return r.dineDnote==='Low tolerance to garlic'
             && !r.prevDnote && !r.prevDiets;}"""))
    ck("so an explained Other is amber, not red",
       q.evaluate("""()=>{PREARRIVAL_BY_VILLA['99']={diets:[DIET_OTHER],dnote:'garlic'};
         const r=overlayReservationDiets({},'99');
         delete PREARRIVAL_BY_VILLA['99'];
         return bubbleState(r.diets, r, [], '')==='amber';}"""))
    ck("and an unexplained Other stays red",
       q.evaluate("""()=>{PREARRIVAL_BY_VILLA['99']={diets:[DIET_OTHER]};
         const r=overlayReservationDiets({},'99');
         delete PREARRIVAL_BY_VILLA['99'];
         return bubbleState(r.diets, r, [], '')==='red';}"""))
    # The grey bubble opens the booking note under its name, and only that.
    q.evaluate("()=>openNotes('Villa 4', {}, [], 'A golf buggy on arrival')")
    q.wait_for_timeout(200)
    notes=q.locator("#sheet").inner_text().upper()
    ck("a grey bubble opens Booking notes",
       "BOOKING NOTES" in notes and "GOLF BUGGY" in notes)
    ck("and no kitchen sections it has nothing for",
       "DIETARY NOTES" not in notes and "DINNER NOTES" not in notes)
    q.close()

    # ── the guest snapshot behind the eye ───────────────────────────────
    # The sheet showed a name and a phone number. The dates, the head count
    # from Mews and the guest's own pre-arrival answers were all being
    # collected and shown nowhere, which is what a manager means by a board
    # with missing guest data.
    BID = "6cb6d13f-beda-45eb-9c1b-b4880157a2bf"
    SNAP_CASES = [
        ("a guest who answered themselves",
         {"4": {"id": BID, "first": "Kathryn", "last": "Steele",
                "phone": "0418387632", "arrive": today, "depart": plus(3),
                "adults": 2, "number": "10231"}},
         {"4": {"status": "in", "pax": 2, "by": "guest"}},
         {"arriveSlot": "15", "purpose": "A celebration", "note": "Late flight"},
         ["3 nights", "2 adults", "0418 387 632", "10231",
          "answered themselves", "Around 3pm", "Late flight"]),
        ("a booking Mews knows and nobody has answered",
         {"4": {"id": BID, "first": "Ana", "last": "Diaz", "arrive": today,
                "depart": plus(1), "adults": 2, "number": "10240"}},
         {}, None,
         ["1 night", "From Mews", "No pre-arrival answers yet"]),
        ("an answer taken at the desk",
         {"4": {"id": BID, "first": "Sol", "last": "Kim", "arrive": today,
                "depart": plus(1), "adults": 1, "number": "9"}},
         {"4": {"status": "in", "pax": 1, "by": "staff"}}, None,
         ["1 adult", "Answered at the desk"]),
        # The reported bug of 19 Aug: a dietary lives on the reservation, the
        # villa has NO dinner cell for the viewed night, and the board must
        # still show it. An allergy is not true on Tuesday and false on
        # Wednesday. Nothing asserted this before, which is why every suite
        # was green with the bug in place.
        ("a dietary on the reservation with no dinner cell",
         {"4": {"id": BID, "first": "Noor", "last": "Haddad", "arrive": today,
                "depart": plus(2), "adults": 2, "number": "10250"}},
         {},
         {"diets": ["Nut allergy"], "dnote": "Severe, carries an epipen"},
         ["Nut allergy", "Severe, carries an epipen"]),
    ]

    for label, stays, din, pre, expect in SNAP_CASES:
        def snap_fb(route, request, _s=stays, _d=din, _p=pre):
            u = request.url
            if "/stays/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(_s)); return
            if "/prearrival" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(_p) if _p else "null"); return
            if "/dinner/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(_d)); return
            fb(route, request)
        # 320pt, the narrowest phone: a detail panel is the easiest thing to
        # push off the edge of a small screen.
        q = b.new_page(viewport={"width": 320, "height": 1200})
        q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body=SDK))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", snap_fb)
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1700)
        q.evaluate("()=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent==='4').click()")
        q.wait_for_timeout(500)

        ck("%s: the name is the control" % label,
           q.evaluate("()=>{const e=document.getElementById('gdEye');"
                      "return !!e && e.tagName==='BUTTON'"
                      " && e.className.indexOf('gd-name')>-1;}"))
        # Shut to start with. Reception opens this sheet many times a service
        # to press one of three buttons, and detail sitting open in front of
        # them would be in the way every time for the once it is wanted.
        ck("%s: the panel starts shut" % label,
           not q.evaluate("()=>gdPanel.classList.contains('open')"))
        q.locator("#gdEye").click(); q.wait_for_timeout(1000)
        ck("%s: it opens" % label,
           q.evaluate("()=>gdPanel.classList.contains('open')"))
        text = q.evaluate("()=>gdPanel.textContent")
        for want in expect:
            ck("%s: shows %r" % (label, want), want in text)
        ck("%s: no sideways scroll at 320pt" % label,
           q.evaluate("()=>document.documentElement.scrollWidth"
                      "<=document.documentElement.clientWidth"))
        # Its own way out. Having to find the name again to shut it is the
        # wrong way round: by then you are reading the bottom of the panel
        # and the name is off the top of your attention.
        ck("%s: the panel carries its own Close" % label,
           q.evaluate("()=>!!document.getElementById('gdClose')"))
        q.locator("#gdClose").click(); q.wait_for_timeout(500)
        ck("%s: Close shuts it" % label,
           not q.evaluate("()=>gdPanel.classList.contains('open')"))
        # The card must not move at all. Two earlier attempts pushed it down,
        # and the second one collided with the guest picker as the panel grew.
        # Reception presses those three buttons from memory, so a control that
        # shifts under the thumb is worse than one that is hard to find.
        def card_top():
            return q.evaluate("""()=>{const g=document.getElementById('paxRow')
              ||document.querySelector('.pax-row');
              const d=[...document.querySelectorAll('.opt')][0];
              return [Math.round(g.getBoundingClientRect().top),
                      Math.round(d.getBoundingClientRect().top)];}""")
        q.locator("#gdEye").click(); q.wait_for_timeout(500)
        opened_at = card_top()
        q.locator("#gdClose").click(); q.wait_for_timeout(500)
        ck("%s: opening the panel does not move the card" % label,
           opened_at == card_top())
        ck("%s: the panel floats above the card" % label,
           int(q.evaluate("()=>getComputedStyle(gdPanel).zIndex") or 0) > 0
           and q.evaluate("()=>getComputedStyle(gdPanel).position") == "absolute")
        # The name still works as a toggle for anyone who reaches for it.
        # Asserted from a known shut state rather than from whatever the step
        # before happened to leave behind: a toggle test that inherits its
        # starting point tests the sequence, not the toggle.
        ck("%s: shut before testing the toggle" % label,
           not q.evaluate("()=>gdPanel.classList.contains('open')"))
        q.locator("#gdEye").click(); q.wait_for_timeout(500)
        ck("%s: the name still reopens it" % label,
           q.evaluate("()=>gdPanel.classList.contains('open')"))
        q.locator("#gdEye").click(); q.wait_for_timeout(400)
        ck("%s: and still shuts it" % label,
           not q.evaluate("()=>gdPanel.classList.contains('open')"))

        # Floating over the card means a tap outside lands on something the
        # panel is covering. It must shut first and swallow that tap, or
        # somebody clears a villa while trying to dismiss a panel.
        q.locator("#gdEye").click(); q.wait_for_timeout(500)
        ck("%s: open before testing the outside tap" % label,
           q.evaluate("()=>gdPanel.classList.contains('open')"))
        before_status = q.evaluate("()=>JSON.stringify(window.dinner||{})")
        box = q.evaluate("()=>{const r=gdPanel.getBoundingClientRect();"
                         "return [Math.round(r.left+r.width/2),"
                         "Math.round(Math.min(r.bottom+40,"
                         "window.innerHeight-6))];}")
        q.mouse.click(box[0], box[1]); q.wait_for_timeout(500)
        ck("%s: a tap outside shuts the panel" % label,
           not q.evaluate("()=>gdPanel.classList.contains('open')"))
        ck("%s: and that tap changes nothing underneath" % label,
           q.evaluate("()=>JSON.stringify(window.dinner||{})") == before_status)
        q.close()

    # ── the booking's notes in the panel ────────────────────────────────
    # Decided 20 Aug: the dropdown is the booking's notes. Staff notes join
    # it for the logins the rules allow, the arrival note leaves it because
    # it dies at check-in and belongs to the arrivals views, and a refused
    # read renders as no row at all: the section not existing IS the correct
    # rendering of not being allowed to see it.
    NPRE = {"arriveSlot": "15", "arriveNote": "Ferry lands 3pm",
            "note": "A golf buggy on arrival", "diets": ["Vegan"],
            "dnote": "Strict, no butter"}
    for label, email, internal_body, tier in [
        ("the admin", "staff@x",
         json.dumps({"note": "VIP, comp the champagne"}), "edit"),
        # Decided 20 Aug: the note is the whole team's. Every staff
        # login reads and writes it; the rules only fence out guests.
        ("the desk", "desk@x",
         json.dumps({"note": "VIP, comp the champagne"}), "edit-light"),
        ("the chef", "chef@x",
         json.dumps({"note": "VIP, comp the champagne"}), "edit-light"),
        # A refused or failed read renders no section and, above all, no
        # editor: an editor on an unverified blank invites overwriting a
        # note nobody saw.
        ("a refused read", "waiter@x",
         json.dumps({"error": "Permission denied"}), "none"),
    ]:
        def notes_fb(route, request, _b=internal_body):
            u = request.url
            if request.method != "GET":
                fb(route, request); return
            if "/stays/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"4": {"id": BID, "first": "Ana",
                                "last": "Diaz", "arrive": today, "depart": plus(2),
                                "adults": 2, "number": "10260"}})); return
            if "/prearrival" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(NPRE)); return
            if "/internal/" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=_b); return
            if "/dinner/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body="{}"); return
            fb(route, request)
        q = b.new_page(viewport={"width": 390, "height": 900})
        q.route("**/firebase-app-compat.js", lambda r,_,__e=email: r.fulfill(
            status=200, content_type="application/javascript",
            body=SDK.replace("staff@x", __e)))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", notes_fb)
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1700)
        q.evaluate("()=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent==='4').click()")
        q.wait_for_timeout(500)
        q.locator("#gdEye").click(); q.wait_for_timeout(1000)
        text = q.evaluate("()=>gdPanel.textContent")
        ck("%s: the booking note is there under its name" % label,
           "Booking notes" in text and "golf buggy" in text)
        ck("%s: the dietary note row carries its full name" % label,
           "Dietary notes" in text)
        ck("%s: the arrival slot stays" % label, "Around 3pm" in text)
        ck("%s: the arrival note is gone from the booking's panel" % label,
           "Ferry lands" not in text)
        if tier == "edit-light":
            ck("%s: the note displays as a row with an edit control" % label,
               "Staff notes" in text and "comp the champagne" in text
               and q.evaluate("()=>!document.getElementById('gdIntNote')"
                              "&&!!document.getElementById('gdIntEdit')"))
        if tier == "none":
            ck("%s: no staff section, no editor, no complaint" % label,
               "Staff notes" not in text and "denied" not in text
               and "Could not load" not in text
               and q.evaluate("()=>!document.getElementById('gdIntNote')"))
        if tier == "edit":
            # Decided 20 Aug, twice: the note READS as a row like every
            # other note, in full, and the box is a mode entered by the
            # edit control and left by saving. A note stuck permanently
            # inside a small editor cannot be read.
            ck("%s: the note displays as a row first" % label,
               "Staff notes" in text and "comp the champagne" in text
               and q.evaluate("()=>!document.getElementById('gdIntNote')"))
            q.locator("#gdIntEdit").click(); q.wait_for_timeout(300)
            ok = q.evaluate("""()=>{const t=document.getElementById('gdIntNote');
                const s=document.getElementById('gdIntSave');
                if(!t||!s) return {here:false};
                return {here:true, val:t.value, asleep:s.disabled,
                        labelled:!!document.querySelector('.gd-int label')};}""")
            ck("%s: the edit control opens the editor holding the note" % label,
               ok.get("here") and ok.get("val") == "VIP, comp the champagne")
            ck("%s: it carries a visible label" % label, ok.get("labelled"))
            # The 16px protocol: every focusable field on a phone is 16px or
            # more, because iOS zooms the page into anything smaller. Checked
            # across the whole page while the editor is open, so the next
            # field added below 16 fails here by name.
            small = q.evaluate("""()=>[...document.querySelectorAll(
                'input,textarea,select')].filter(el=>
                  parseFloat(getComputedStyle(el).fontSize)<16)
                .map(el=>el.id||el.className)""")
            ck("%s: no input under 16px (found: %s)" % (label, small),
               small == [])
            ck("%s: Save sleeps until something changes" % label, ok.get("asleep"))
            del WRITES[:]
            q.fill("#gdIntNote", "VIP, comp the champagne, late checkout")
            q.wait_for_timeout(200)
            ck("%s: typing wakes Save" % label,
               q.evaluate("()=>!document.getElementById('gdIntSave').disabled"))
            q.locator("#gdIntSave").click(); q.wait_for_timeout(700)
            w = [x for x in WRITES if "/internal/" in x["u"]]
            ck("%s: one PATCH to the staff node" % label,
               len(w) == 1 and w[0]["m"] == "PATCH")
            bodyw = json.loads(w[0]["b"]) if w else {}
            ck("%s: the note, when, and who" % label,
               bodyw.get("note") == "VIP, comp the champagne, late checkout"
               and bodyw.get("editedBy") == "staff@x"
               and bool(bodyw.get("editedAt")))
            ck("%s: saving returns the note to a readable row" % label,
               q.evaluate("()=>!document.getElementById('gdIntNote')")
               and "late checkout" in q.evaluate("()=>gdPanel.textContent"))
            # And the cache learned it: shut, reopen, the new text is the
            # row, without another fetch inventing the old one.
            q.locator("#gdClose").click(); q.wait_for_timeout(300)
            q.locator("#gdEye").click(); q.wait_for_timeout(700)
            ck("%s: reopening shows the saved text as the row" % label,
               "late checkout" in q.evaluate("()=>gdPanel.textContent")
               and q.evaluate("()=>!document.getElementById('gdIntNote')"))
        q.close()

    # ── the panel against the screen, not the sheet ─────────────────────
    # Reported twice on 20 Aug: the panel's allowance was measured from the
    # sheet's bottom, and the sheet's bottom is wherever that login's
    # buttons end. The staff sheet carries five buttons and fitted; the
    # chef's carries none and the panel ran off the screen. The law: the
    # open panel's bottom edge stays on the screen for EVERY login, and a
    # booking longer than the room scrolls inside the panel.
    for who in ["staff@x", "chef@x"]:
        def tallpre_fb(route, request):
            u = request.url
            if "/stays/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"4": {"id": BID, "first": "Ana",
                                "last": "Diaz", "arrive": today, "depart": plus(3),
                                "adults": 2, "number": "10261"}})); return
            if "/prearrival" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"arriveSlot": "15",
                                "purpose": "A celebration", "occasion": "An anniversary",
                                "approach": "mix", "wellness": True, "wellDay": plus(1),
                                "wellTime": "am", "note": "A golf buggy on arrival",
                                "diets": ["Vegan", "Gluten free"],
                                "dnote": "Strict, please, no butter at all"})); return
            if "/internal/" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"note": "VIP, comp the champagne"})); return
            if "/dinner/" + today in u:
                route.fulfill(status=200, content_type="application/json",
                              body="{}"); return
            fb(route, request)
        # 520pt tall: short enough that BOTH logins' bookings cannot fit,
        # so the law has to hold rather than the content happening to be
        # small. At 600 the chef's shorter content fitted and proved nothing.
        q = b.new_page(viewport={"width": 390, "height": 520})
        q.route("**/firebase-app-compat.js", lambda r,_,__w=who: r.fulfill(status=200,
            content_type="application/javascript", body=SDK.replace("staff@x", __w)))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", tallpre_fb)
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1700)
        q.evaluate("()=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent==='4').click()")
        q.wait_for_timeout(500)
        q.evaluate("()=>document.getElementById('gdEye')"
                   ".scrollIntoView({block:'center'})")
        q.wait_for_timeout(300)
        q.locator("#gdEye").click(); q.wait_for_timeout(1200)
        m = q.evaluate("""()=>{const p=document.getElementById('gdPanel');
            const r=p.getBoundingClientRect();
            return {open:p.classList.contains('open'),
                    bottom:Math.round(r.bottom), vh:window.innerHeight,
                    fits:p.scrollHeight<=p.clientHeight+2,
                    scrollable:getComputedStyle(p).overflowY==='auto'};}""")
        ck("%s: the panel opened" % who, m["open"])
        ck("%s: its bottom edge stays on the screen (%s <= %s)"
           % (who, m["bottom"], m["vh"]), m["bottom"] <= m["vh"])
        # Nothing unreachable: the panel's box ends on the screen (asserted
        # above), and whatever the box cannot hold is scrollable inside it.
        # Whether THIS content overflows depends on where the page sat, which
        # is the layout's business, not the law's.
        ck("%s: everything fits or scrolls, nothing unreachable" % who,
           m["fits"] or m["scrollable"])
        q.close()

    # ── one card size for every login ───────────────────────────────────
    # Decided 20 Aug from two phone screenshots: the admin's card, with its
    # full stack of buttons, is THE card. A login whose sheet draws fewer
    # controls gets the same height with the space standing empty, so the
    # card is one shape everywhere and the panel always has the same room.
    hs = {}
    def card_fb(route, request):
        u = request.url
        if "/staff" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(staff)); return
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"4": {"id": BID, "first": "Ana",
                            "last": "Diaz", "arrive": today, "depart": plus(2),
                            "adults": 2, "number": "10262"}})); return
        route.fulfill(status=200, content_type="application/json", body="{}")
    for who in ["staff@x", "chef@x"]:
        q = b.new_page(viewport={"width": 390, "height": 900})
        q.route("**/firebase-app-compat.js", lambda r,_,__w=who: r.fulfill(
            status=200, content_type="application/javascript",
            body=SDK.replace("staff@x", __w)))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", card_fb)
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1600)
        q.evaluate("()=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent==='4').click()")
        q.wait_for_timeout(500)
        hs[who] = q.evaluate("()=>{const s=document.getElementById('sheet');"
                             "return s?Math.round(s.getBoundingClientRect()"
                             ".height):0;}")
        q.close()
    ck("the chef's card is the admin's card (%s vs %s)"
       % (hs["chef@x"], hs["staff@x"]),
       abs(hs["chef@x"] - hs["staff@x"]) <= 2)
    ck("and it is the large one, not a shared small one (%s)" % hs["staff@x"],
       hs["staff@x"] >= 540)

    # A villa with nothing known offers no eye at all: a control that opens an
    # empty panel teaches people not to press it.
    def bare_fb(route, request):
        u = request.url
        if "/stays/" in u or "/dinner/" in u or "/responses/" in u or "/manual/" in u:
            route.fulfill(status=200, content_type="application/json", body="null"); return
        if "/roomguests/" in u:
            route.fulfill(status=200, content_type="application/json", body="null"); return
        fb(route, request)
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body=SDK))
    q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body="/*n*/"))
    q.route("**firebasedatabase.app/**", bare_fb)
    q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1600)
    q.evaluate("()=>[...document.querySelectorAll('button')]"
               ".find(b=>b.querySelector('.room-n')"
               "&&b.querySelector('.room-n').textContent==='4').click()")
    q.wait_for_timeout(500)
    ck("an empty villa offers no name to press",
       not q.evaluate("()=>!!document.getElementById('gdEye')"))
    q.close()

    # ── the group row ───────────────────────────────────────────────────
    # Mews puts a groupId on EVERY reservation, not only the ones spanning
    # villas, so reading its presence as "booked with another villa" put that
    # line on all seventeen. Reported from a real handset on 18 Aug as looking
    # like an exposed bug, which is exactly what it was.
    GB = "6cb6d13f-beda-45eb-9c1b-b4880157a2bf"
    group_stays = {
        "4": {"id": GB, "first": "Darren", "last": "Rubach", "arrive": today,
              "depart": plus(2), "adults": 2, "groupId": "G-A"},
        "5": {"id": GB[:-1] + "c", "first": "Mia", "last": "Rubach",
              "arrive": today, "depart": plus(2), "adults": 2, "groupId": "G-A"},
        "6": {"id": GB[:-1] + "d", "first": "Solo", "last": "Guest",
              "arrive": today, "depart": plus(1), "adults": 2, "groupId": "G-B"},
    }
    def group_fb(route, request):
        u = request.url
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(group_stays)); return
        if "/prearrival" in u:
            route.fulfill(status=200, content_type="application/json",
                          body="null"); return
        fb(route, request)
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body=SDK))
    q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body="/*n*/"))
    q.route("**firebasedatabase.app/**", group_fb)
    q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1700)

    def open_snapshot(villa):
        q.evaluate("(v)=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent===v).click()", villa)
        q.wait_for_timeout(400)
        q.locator("#gdEye").click(); q.wait_for_timeout(700)
        t = q.evaluate("()=>gdPanel.textContent")
        q.evaluate("()=>{const c=document.getElementById('oClose');if(c)c.click();}")
        q.wait_for_timeout(250)
        return t

    # Naming the other villa is the point: "booked with another villa" is a
    # riddle, "booked with villa 5" is a fact reception can act on.
    ck("a villa sharing a group names the villa it shares with",
       "villa 5" in open_snapshot("4"))
    ck("a villa with its own group says nothing about groups",
       "Booked with" not in open_snapshot("6"))
    q.close()

    # ── the seated-together bar ─────────────────────────────────────────
    # It ran the full width of the sheet and straight under the menu button,
    # which cut "Seat separately" in half on a real handset: a control you can
    # only half read is one you press by accident or not at all.
    def comb_fb(route, request):
        u = request.url
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(group_stays)); return
        if "/combined/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps({"g1": {"rooms": ["4", "5"]}})); return
        if "/prearrival" in u:
            route.fulfill(status=200, content_type="application/json",
                          body="null"); return
        fb(route, request)
    for w in (390, 320):
        q = b.new_page(viewport={"width": w, "height": 900})
        q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body=SDK))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", comb_fb)
        q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1700)
        q.evaluate("()=>[...document.querySelectorAll('button')]"
                   ".find(b=>b.querySelector('.room-n')"
                   "&&b.querySelector('.room-n').textContent==='4').click()")
        q.wait_for_timeout(500)
        geo = q.evaluate("""()=>{const u=document.querySelector('.comb-undo');
          const n=document.querySelector('.navwrap');
          if(!u) return null;
          const a=u.getBoundingClientRect(), b=n?n.getBoundingClientRect():null;
          return {clear: b ? a.right <= b.left : true,
                  readable: a.width > 60};}""")
        ck("at %dpt the seat-separately control clears the menu button" % w,
           bool(geo) and geo["clear"])
        ck("at %dpt it is wide enough to read" % w,
           bool(geo) and geo["readable"])
        q.close()

    # ── an unlisted allergy, here too ───────────────────────────────────
    # The desk gained an Other pill; this board edits the same dietaries on the
    # same guest and had no way to record one. A board that cannot show what
    # the desk recorded is a board that quietly loses it.
    WROTE = []
    def diet_fb(route, request):
        u = request.url
        if request.method in ("PUT", "PATCH"):
            WROTE.append((u.split("firebasedatabase.app")[1].split("?")[0],
                          request.post_data))
            route.fulfill(status=200, content_type="application/json",
                          body=request.post_data or "{}"); return
        if "/staff" in u:
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"staff@x": {"name": "A", "role": "admin"}})); return
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"4": {"id": "b4", "first": "K", "last": "S",
                                       "arrive": plus(-1), "depart": plus(3),
                                       "adults": 2}})); return
        if "/dinner/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                body=json.dumps({"4": {"status": "in", "pax": 2, "by": "staff"}})); return
        # The Mews customer. Without one there is nobody to key a lasting
        # dietary on, and the mirror correctly does nothing, which is what
        # happens for every booking written before 18 Aug.
        if "customerId" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps("cust-9f2b")); return
        fb(route, request)
    q = b.new_page(viewport={"width": 390, "height": 900})
    q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body=SDK))
    q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body="/*n*/"))
    q.route("**firebasedatabase.app/**", diet_fb)
    q.goto("http://localhost:8953/tally.html"); q.wait_for_timeout(1900)
    q.evaluate("""()=>[...document.querySelectorAll('button')]
      .find(b=>b.querySelector('.room-n')
        &&b.querySelector('.room-n').textContent==='4').click()""")
    q.wait_for_timeout(400)
    q.evaluate("""()=>{const b=[...document.querySelectorAll('#sheet button')]
      .find(x=>/edit details/i.test(x.textContent)); if(b)b.click();}""")
    q.wait_for_timeout(500)

    chips = q.evaluate("()=>[...document.querySelectorAll('#dietChips button')]"
                       ".map(b=>b.textContent.trim())")
    ck("the reservations board offers Other, like the desk", "Other" in chips)
    # Not in DIETARIES itself: that list is also the chef's, and Other is not a
    # dietary a dish can conflict with.
    ck("and it is the last of them, not mixed into the chef's list",
       bool(chips) and chips[-1] == "Other")

    # The box was summoned by Other alone, so a villa with Gluten free and
    # Shellfish ticked had nowhere to type whose, and how severe: the label
    # rendered on a day the note existed and vanished on a day it did not,
    # which read from a phone as the option itself coming and going. The
    # guest's own form has always shown the box for any ticked dietary.
    # Reported 20 Aug, villa 10.
    ck("the dietary note box starts hidden on a villa with nothing ticked",
       q.evaluate("()=>document.getElementById('xDnote').style.display==='none'"))
    q.evaluate("""()=>[...document.querySelectorAll('#dietChips button')]
      .find(b=>b.textContent.trim()==='Gluten free').click()""")
    q.wait_for_timeout(200)
    ck("any ticked dietary reveals it, not only Other",
       q.evaluate("()=>document.getElementById('xDnote').style.display!=='none'"))
    ck("and its label with it",
       q.evaluate("()=>{const l=document.getElementById('xDnoteLab');"
                  "return !!l && l.style.display!=='none';}"))
    q.evaluate("""()=>[...document.querySelectorAll('#dietChips button')]
      .find(b=>b.textContent.trim()==='Gluten free').click()""")
    q.wait_for_timeout(200)

    q.evaluate("""()=>[...document.querySelectorAll('#dietChips button')]
      .find(b=>b.textContent.trim()==='Other').click()""")
    q.wait_for_timeout(200)
    del WROTE[:]
    q.evaluate("()=>{const b=document.getElementById('oSave'); if(b)b.click();}")
    q.wait_for_timeout(600)
    ck("Other with an empty note saves nothing here either", not WROTE)

    # The allergy goes in the Dietary note, which belongs to the person and
    # rides to the reservation. Comments stays a note about tonight; an Other
    # typed there was stored in the box that expires at midnight, which is
    # the spicy meatballs bug in its purest form. Both fields filled here to
    # prove they land in different places.
    ck("the dietary note appears once Other is ticked",
       q.evaluate("()=>document.getElementById('xDnote').style.display!=='none'"))
    q.fill("#xDnote", "Severe sesame allergy")
    q.fill("#xNote", "Window table tonight")
    del WROTE[:]
    q.evaluate("()=>document.getElementById('oSave').click()")
    q.wait_for_timeout(700)
    saved = [json.loads(x[1]) for x in WROTE if x[1]]
    ck("and saves once the allergy is written down",
       bool(saved) and any(d.get("diets") == ["Other"] for d in saved))
    ck("with the note that explains it, on the person",
       any("sesame" in str(d.get("dnote", "")).lower() for d in saved))
    ck("while Comments stays a note about tonight",
       any("window" in str(d.get("note", "")).lower() for d in saved
           if "/dinner/" in "".join(x[0] for x in WROTE if x[1] == json.dumps(d))) or
       any("window" in str(json.loads(x[1]).get("note","")).lower()
           for x in WROTE if "/dinner/" in x[0] and x[1]))
    ck("and the reservation never receives tonight's comment",
       not any("window" in str(json.loads(x[1]).get("note","")).lower()
               for x in WROTE if "/bookings/" in x[0] and x[1]))

    # ── and the dietary has to outlive tonight ──────────────────────────
    # This board writes the one dinner cell, which lives under a date and is
    # gone at midnight. A dietary typed here was right this evening and gone
    # tomorrow, and nothing said so: the guest still had a booking and the
    # board still looked right. The desk had always written both places, so
    # the same allergy survived from one screen and not the other.
    paths = [x[0] for x in WROTE]
    ck("a dietary saved here reaches the booking, not only tonight",
       any("/bookings/b4/prearrival" in p for p in paths))
    ck("and still reaches tonight, which is what service reads",
       any("/dinner/" in p for p in paths))
    booked = [json.loads(x[1]) for x in WROTE
              if "/bookings/" in x[0] and x[1]]
    ck("the booking gets the dietaries themselves, not a reference to them",
       bool(booked) and any(b.get("diets") == ["Other"] for b in booked))
    # And onto the person. A dietary is about the guest, not about a night or
    # a reservation, so kept only on the booking a returning guest arrives
    # with an empty record and is asked all over again, having told us once.
    # customerId is the only identifier that outlives a booking.
    ck("and the dietary reaches the person, so next year they are not asked again",
       any("/guests/" in p for p in paths))
    q.close()

    b.close()
    open("/home/claude/nala/_p1_tally.png","wb").write(shot1)
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
