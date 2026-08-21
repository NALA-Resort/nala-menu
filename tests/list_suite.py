import errortrap   # fails the run if any page throws
import threading,http.server,socketserver,json,time,datetime,os,re
os.chdir('/home/claude/nala')
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
httpd=http.server.ThreadingHTTPServer(("",8955),Q)
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
#  Villas the PMS knows about, which is where the booking ids come from. The
#  internal note hangs off the reservation, not the night, so a sheet can only
#  reach one through the id on the stay.
STAYS={"1":{"id":"b1","name":"James"},"3":{"id":"b3","name":"Mark"},
       "4":{"id":"b4","name":"Lucy"},"9":{"id":"b9","name":"Priya"}}
internal={"b1":{"note":"Owner's friend, do not charge for wine"},
          "b3":{"fromMews":"Complained about noise last stay"},
          "b9":{"note":""}}

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
    elif "/stays/"+today in u: body=json.dumps(STAYS)
    elif "/stays/" in u: body="null"
    elif "/internal/" in u:
        k=u.split("/internal/")[1].split(".json")[0]
        body=json.dumps(internal[k]) if k in internal else "null"
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
              mixColour:getComputedStyle(m.querySelector('.stat-n')).color,
              rows:Math.round(document.querySelector('.stats').getBoundingClientRect().height)};}""")
    print("   header geom:", hg)
    ck("make-up left-anchored, covers right-anchored, one row",
       hg["mixLeft"]<=20 and hg["covRight"]>=hg["vw"]-20 and hg["rows"]<=46)
    # Reversed on 18 Aug. The make-up is the instruction a waiter reads to set
    # the room; covers is the kitchen's number and nobody sets a table from
    # it. The make-up was the smaller of the two and in label grey, so the one
    # instruction on the sheet had to be hunted for. Asserted as a comparison
    # rather than as fixed pixel sizes, so the sizes can be tuned without a
    # test failing over a point.
    ck("the make-up is the larger of the two, not the smaller",
       float(hg["mixSize"][:-2]) > float(hg["covSize"][:-2]))
    ck("and it is set in ink, not in label grey",
       hg["mixColour"] == "rgb(28, 28, 26)")

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
    print("   rows:", rw["n"], "data:", len(d), "blanks:", rw["blanks"])
    # One fewer than before: villa 5 is vacant and no longer takes a line.
    ck("18 data rows + pad to 21 total",
       len(d)==18 and rw["n"]==21 and rw["blanks"]==3)
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
    ck("r4 known-but-silent shows dash", d[3]["din"]=="\u2013" and "row-unk" in d[3]["cls"])
    # Villa 5 is vacant, so it is not on the sheet at all: the sheet is read
    # down in service and every line on it should be somebody to look after.
    # That shifts every row after it up by one.
    ck("vacant villa 5 is absent, not listed empty",
       all("row-vacant" not in x["cls"] for x in d)
       and all(x["name"] != "Vacant" for x in d))
    ck("the villa after the vacant one is not renumbered",
       any(x["room"] == "6" for x in d))
    ck("r9 Priya listed silent", d[7]["name"]=="Priya" and d[7]["din"]=="\u2013")
    ext=d[16:]
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

    # The reported bug of 19 Aug, on the sheet that goes to the kitchen: a
    # dietary on the reservation, no dinner cell for the viewed night, viewed
    # on TOMORROW's date. An allergy does not expire overnight. Checked in the
    # PDF's own text, not only on screen, because the printed copy is the one
    # a plate is cooked from.
    BID7 = "7a1b2c3d-1111-2222-3333-444455556666"
    stays7 = {"7": {"id": BID7, "first": "Mara", "last": "Okafor",
                    "arrive": plus(-1), "depart": plus(3), "adults": 2,
                    "number": "10260"}}
    pre7 = {"diets": ["Egg allergy"], "dnote": "Anaphylaxis"}
    def diet_fb(route, request):
        u = request.url
        if "/stays/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(stays7)); return
        if "/bookings/" + BID7 + "/prearrival" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(pre7)); return
        if "/responses/" in u or "/manual/" in u or "/dinner/" in u \
           or "/combined/" in u or "/roomguests/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body="null"); return
        fb(route, request)
    q = b.new_page(viewport={"width": 900, "height": 1100})
    q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body=SDK))
    q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body="/*n*/"))
    q.route("**firebasedatabase.app/**", diet_fb)
    q.goto("http://localhost:8955/list.html?date="+plus(1)); q.wait_for_timeout(1400)
    # dietPills shortens "Egg allergy" to "Egg"; the dnote prints whole.
    # The pill renders uppercase by CSS, so the visible text is EGG: compare
    # case-blind rather than against the stored casing.
    t7 = q.locator("body").inner_text().lower()
    ck("reservation dietary reaches the sheet on screen",
       "egg" in t7 and "anaphylaxis" in t7)
    q.emulate_media(media="print")
    pdf7 = q.pdf(format="A4")
    open("/home/claude/nala/_p2_dietpdf.pdf","wb").write(pdf7)
    import subprocess
    txt = subprocess.run(["pdftotext","/home/claude/nala/_p2_dietpdf.pdf","-"],
                         capture_output=True, text=True).stdout
    ck("reservation dietary is in the printed PDF text",
       "egg" in txt.lower() and "anaphylaxis" in txt.lower())
    q.close()

    # The PDF button was removed on 18 Aug: it rebuilt the sheet by hand and
    # so carried less than the page it came from, and a second version of a
    # document that is silently missing things is worse than no second
    # version. These assert it stays gone, machinery included, because a
    # half-removed feature is how a dead button appears.
    src = open("/home/claude/nala/list.html").read()
    ck("no PDF button", 'id="sheetPdf"' not in src)
    ck("and no PDF machinery left behind",
       "sheetPDF" not in src and "jspdf" not in src.lower()
       and "addFileToVFS" not in src)

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

    #  The staff note belongs to the reservation and is management's. The sheet
    #  is carried into service and left on a pass, so it is gated on the role
    #  rather than on the permission that opens the page: a chef and a waiter
    #  may both read this sheet and neither may read that note.
    q=as_role("staff@x")
    q.wait_for_timeout(1200)   # the notes are one read per villa, after the role
    ck("the staff note reaches the sheet",
       q.evaluate("()=>[...document.querySelectorAll('.snote')]"
                   ".some(e=>e.textContent.indexOf('do not charge for wine')>-1)"))
    ck("and is labelled so nobody cooks to it",
       q.evaluate("()=>[...document.querySelectorAll('.snote')]"
                   ".every(e=>e.textContent.indexOf('Staff')>-1)"))
    ck("what Mews said stands in when nobody has rewritten it",
       q.evaluate("()=>document.body.innerText.indexOf('Complained about noise')>-1"))
    ck("an empty note prints nothing at all",
       q.evaluate("()=>[...document.querySelectorAll('.snote')].length===2"))
    q.close()

    q=as_role("chef@x")
    q.wait_for_timeout(1200)
    ck("the chef reads the sheet but not the staff note",
       q.evaluate("()=>document.querySelectorAll('.snote').length===0"))
    ck("chef reads and prints the sheet",
       q.evaluate("""()=>noAccess.className.indexOf('show')<0
                      && document.querySelectorAll('table tbody tr').length>0
                      && getComputedStyle(footBar).display!='none'"""))
    q.close()

    q=as_role("waiter@x")
    q.wait_for_timeout(1200)
    ck("nor does a waiter carrying it into service",
       q.evaluate("()=>document.querySelectorAll('.snote').length===0"))
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

    # The header make-up grows with the number of party sizes in the house.
    # A full mixed night ran to 397pt and pushed the covers figure off the
    # right edge at every phone width, not at 320 only as first recorded, so
    # the whole page scrolled sideways. Checked with the widest house the
    # sheet can hold rather than the tidy one the other assertions use.
    MIXED = {}
    for i in range(1, 18):
        MIXED["room-%d" % i] = {"status": "in", "room": str(i),
                                "pax": [2,3,4,2,5,3,6,2,4][i % 9] or 2}
    for w in (390, 360, 320):
        q = b.new_page(viewport={"width": w, "height": 900})
        q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body=SDK))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        def mixed_fb(route, request, _m=MIXED):
            u = request.url
            if "/responses/" in u:
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(_m)); return
            fb(route, request)
        q.route("**firebasedatabase.app/**", mixed_fb)
        q.route("**/menu.json*", lambda r,_: r.fulfill(status=200,
            content_type="application/json", body=json.dumps(menu)))
        q.goto("http://localhost:8955/list.html"); q.wait_for_timeout(1600)
        m = q.evaluate("""()=>({vw:document.documentElement.clientWidth,
                              sw:document.documentElement.scrollWidth,
                              mix:document.querySelector('.statmix').textContent.trim()})""")
        print("   %dpt: scroll %d, make-up %r" % (w, m["sw"], m["mix"][:44]))
        ck("a full mixed house does not bleed sideways at %dpt" % w,
           m["sw"] <= m["vw"])
        q.close()

    # ── the make-up wording ─────────────────────────────────────────────
    # Plurals were built by adding an s to the spelled number, which gave
    # "2 sixs" on any night with two tables of six. Found on the printed
    # sheet on 18 Aug, on the line a waiter reads first.
    WORD_CASES = [
        ({1:6},                      "1 six"),
        ({1:6, 2:6},                 "2 sixes"),
        ({1:2},                      "1 two"),
        ({1:7, 2:7, 3:7},            "3 sevens"),
        ({1:2, 2:2, 3:6, 4:6},       "2 twos \u00b7 2 sixes"),
    ]
    for pax, expect in WORD_CASES:
        def word_fb(route, request, _p=pax):
            u = request.url
            if "/roomguests/" in u and today in u:
                route.fulfill(status=200, content_type="application/json",
                    body=json.dumps({str(i): {"name": "G%d" % i, "departs": today}
                                     for i in _p})); return
            if "/responses/" in u:
                route.fulfill(status=200, content_type="application/json",
                    body=json.dumps({"room-%d" % i: {"status": "in", "pax": _p[i],
                                                     "room": str(i)} for i in _p})); return
            # The base fixture combines villas 3 and 4 onto one table, and
            # carries Alfie, a walk-in party of three in /manual. Both would
            # add tables this case never asked for.
            if "/combined/" in u or "/manual/" in u:
                route.fulfill(status=200, content_type="application/json",
                              body="null"); return
            fb(route, request)
        q = b.new_page(viewport={"width": 390, "height": 900})
        q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body=SDK))
        q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
            content_type="application/javascript", body="/*n*/"))
        q.route("**firebasedatabase.app/**", word_fb)
        q.route("**/menu.json*", lambda r,_: r.fulfill(status=200,
            content_type="application/json", body=json.dumps(menu)))
        q.goto("http://localhost:8955/list.html"); q.wait_for_timeout(1500)
        got = q.evaluate("()=>tblBreak.textContent").strip()
        ck("make-up reads %r" % expect, got == expect, )
        if got != expect:
            print("      got %r" % got)
        q.close()

    b.close()
print("RESULT: %d passed, %d failed" % (P,F))
httpd.shutdown()
