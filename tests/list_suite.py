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
#  Villa 1 carries a Mews companion AND a pre-arrival one, because the typed
#  name must win; villa 3 a Mews copy alone, because a name only the Zap
#  delivered must still reach paper; villa 9 none, so a sheet without second
#  guests stays exactly as it was. The angle brackets in Ana's name are the
#  escaping check: the cell is built by concatenation.
STAYS={"1":{"id":"b1","first":"James","companion":"Zoe Wrong"},
       "3":{"id":"b3","first":"Mark","companion":"Aria Stone"},
       "4":{"id":"b4","name":"Lucy"},"9":{"id":"b9","name":"Priya"}}
prearrival={"b1":{"companion":"Ana <Ruiz>"}}
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
    elif "/bookings/" in u and "/prearrival" in u:
        k=u.split("/bookings/")[1].split("/")[0]
        body=json.dumps(prearrival[k]) if k in prearrival else "null"
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

    #  ── the second guest, under the name they travel with ──────────
    cells=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
      .filter(r=>r.querySelector('.c-room')&&r.querySelector('.c-name'))
      .map(r=>({
        room:r.querySelector('.c-room').textContent.trim(),
        html:r.querySelector('.c-name').innerHTML,
        sub:(r.querySelector('.c-name .sub')||{}).textContent||''}))""")
    byroom={c["room"]:c for c in cells}
    ck("the name the guest typed prints under the primary guest",
       byroom["1"]["sub"] == "Ana <Ruiz>")
    ck("and outranks the copy Mews sent for the same villa",
       "Zoe Wrong" not in byroom["1"]["html"])
    ck("a companion only Mews knows still reaches the paper",
       byroom["3"]["sub"] == "Aria Stone")
    ck("a villa with no second guest carries no line for one",
       byroom["9"]["sub"] == "")
    ck("and the typed name lands as text, not as markup",
       "&lt;Ruiz&gt;" in byroom["1"]["html"])
    #  The kicker is gone, and so is the header it left behind. It named the
    #  document to whoever was already holding it, and the page has no room for
    #  two headers above a table that carries its own column headings.
    ck("no kicker naming the document to its own reader",
       pg.evaluate("()=>!document.querySelector('.printkick')"))
    ck("and no summary block above the table at all",
       pg.evaluate("()=>!document.getElementById('pHead')"))

    #  The day's summary is at the foot now, beside the timestamp, and the
    #  table starts at the top of the paper where the reading starts.
    pf = pg.evaluate("""()=>({d:fDate.textContent.trim(), m:fMix.textContent.trim(),
        t:fTables.textContent.trim(), c:fCovers.textContent.trim(),
        all:document.getElementById('pFoot').textContent.replace(/\s+/g,' ').trim()})""")
    print("   printed foot:", pf["all"])
    ck("the foot carries the date the sheet is for", pf["d"] == hd["d"])
    ck("and the make-up, which is the instruction to whoever sets the room",
       "3 twos" in pf["m"] and "1 three" in pf["m"])
    ck("and the table count as its checksum", pf["t"] == "4 tables")
    ck("and the covers", pf["c"] == "9")

    #  One voice. The top of the sheet said this in four different sizes and
    #  weights, which read as four separate announcements rather than one
    #  sentence about tonight.
    pg.emulate_media(media="print")
    pg.wait_for_timeout(200)
    look = pg.evaluate("""()=>{const f=document.getElementById('pFoot');
        const kids=[...f.querySelectorAll('span')].filter(e=>!e.className.includes('sep'));
        const g=e=>{const c=getComputedStyle(e);
          return c.fontSize+'/'+c.fontWeight+'/'+c.fontFamily+'/'+c.textTransform;};
        return {shown:getComputedStyle(f).display!=='none',
                styles:[...new Set(kids.map(g))],
                oneLine:Math.round(f.getBoundingClientRect().height) < 30};}""")
    print("   foot styles:", look["styles"])
    ck("the foot prints", look["shown"])
    ck("and every part of it is set the same way, not four styles in a row",
       len(look["styles"]) == 1)
    ck("and it is one line", look["oneLine"])
    #  Half again as large as it started, and bold. It moved to the foot to
    #  stop competing with the table for the top of the page, and at nine point
    #  it overcorrected into small print: this is the line that says what
    #  tonight is, and whoever sets the room reads it before anything else.
    ck("and it is set loud enough to be the thing read first",
       look["styles"] and float(look["styles"][0].split("px")[0]) >= 13
       and "/700/" in look["styles"][0])
    #  The timestamp keeps its own smaller style: it is about the piece of
    #  paper, not about the service.
    ck("the printed timestamp stays its own size, below and quieter",
       pg.evaluate("""()=>{const a=getComputedStyle(document.getElementById('pFoot')).fontSize;
          const b=getComputedStyle(document.getElementById('stamp')).fontSize;
          return parseFloat(b) < parseFloat(a);}"""))
    ck("and nothing is cloned into the table head any more",
       pg.evaluate("()=>!document.querySelector('#printHead .phead')"))

    #  A browser repeats thead and tfoot on every printed page and will not
    #  repeat a plain block. As a div after the table this line flowed like any
    #  other content, so the day the sheet spilled the summary went to the
    #  bottom of page two and page one ended on a cut-off row.
    ft = pg.evaluate("""()=>{const f=document.getElementById('pFoot');
        const t=f&&f.closest('tfoot');
        return {inFoot:!!t,
                group:t?getComputedStyle(t).display:null,
                lastInTable:!!(t&&t.parentNode.lastElementChild===t)};}""")
    print("   summary placement:", ft)
    ck("the summary lives in the table's own footer, not loose after it",
       ft["inFoot"])
    ck("declared as a footer group, which is the thing a browser repeats",
       ft["group"] == "table-footer-group")
    ck("and it is the last thing in the table",
       ft["lastInTable"])
    #  The timestamp travels with it. Left outside the table it flowed as its
    #  own block, and a sheet whose rows filled the last page put the stamp
    #  alone on the next one: a whole sheet of paper carrying one line of small
    #  print. Verified by rendering a deliberately short page and reading the
    #  PDF, which is the only way to see a page break at all.
    st = pg.evaluate("""()=>{const f=document.getElementById('stampFoot');
        const o=document.getElementById('stamp');
        return {inFoot:!!(f&&f.closest('tfoot')),
                printed:f?getComputedStyle(f).display!=='none':false,
                outsideHidden:o?getComputedStyle(o).display==='none':true,
                same:!!(f&&o&&f.textContent.trim()===o.textContent.trim()),
                text:f?f.textContent.trim():''};}""")
    print("   stamp:", st)
    ck("the timestamp travels inside the footer, not loose after the table",
       st["inFoot"] and st["printed"])
    ck("and the screen's own copy does not print twice",
       st["outsideHidden"])
    ck("and both say the same thing",
       st["same"] and st["text"].lower().startswith("printed"))

    #  The browser prints its own header and footer on top of this sheet: the
    #  URL, the date and time a second time, and a page number, under a
    #  timestamp the sheet had already printed itself. They belong to the print
    #  dialog and no stylesheet can remove them, except that Chrome and Edge
    #  drop them when the page margin is zero. So the margin moves to the body
    #  and the ink stays where it was.
    css = pg.evaluate("""()=>[...document.styleSheets]
      .flatMap(s=>{try{return [...s.cssRules]}catch(e){return []}})
      .filter(r=>r.constructor.name==='CSSPageRule')
      .map(r=>r.style.margin).join('|')""")
    print("   @page margin:", repr(css))
    ck("the printed page asks for no margin of its own", css.strip() in ("0", "0px"))
    pad = pg.evaluate("()=>getComputedStyle(document.body).padding")
    print("   body padding in print:", pad)
    #  Printers have an unprintable edge of a few millimetres. 10mm is inside
    #  the safe area on every consumer printer and matches what @page gave up.
    ck("and the body carries that margin instead, clear of the unprintable edge",
       all(float(v.replace("px","")) >= 30 for v in pad.split()))
    pg.emulate_media(media="screen")

    #  print-color-adjust is INHERITED. Set on the flagged row's cell it was
    #  handed to every coloured thing inside it, and a browser honours exact
    #  colour by rasterising: the Yes, the No and the checkout date printed
    #  soft while the black around them stayed sharp. Asked for on the pills
    #  alone now, where a missing fill would cost an allergy its visibility.
    #  Read in PRINT media, because that is the only place these rules apply
    #  and a screen-media reading would pass whatever the print rules said.
    pg.emulate_media(media="print")
    adj = pg.evaluate("""()=>{
      const g=e=>e?getComputedStyle(e).printColorAdjust||
                   getComputedStyle(e).webkitPrintColorAdjust:null;
      const row=[...document.querySelectorAll('#rows tr')]
        .find(t=>t.className.indexOf('row-conflict')>-1);
      if(!row) return {none:true};
      return {cell:g(row.querySelector('td')),
              yes:g(row.querySelector('.yes')||row.querySelector('.no')),
              pill:g(document.querySelector('.dpill'))};}""")
    print("   colour-adjust:", adj)
    ck("a flagged row does not force exact colour on its own cell",
       adj.get("cell") != "exact")
    ck("so the coloured text inside it is not rasterised",
       adj.get("yes") != "exact")
    ck("while a dietary pill still asks for its fill",
       adj.get("pill") == "exact")
    pg.emulate_media(media="screen")
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
    #  Villas Mews has said nothing about are no longer listed. On a sheet of
    #  seventeen with a handful of bookings, those were most of the lines, and
    #  they were what pushed the sheet onto a second page: a labelled row with
    #  a dash in the dinner column and nothing to do about it. What remains is
    #  villas with a booking or an answer, plus the externals.
    ck("only villas somebody knows something about are listed",
       [x["room"] for x in d] == ["1","2","3","4","9","ext","ext"])
    #  Four spare lines on a night this light. HOW MANY is decided by measured
    #  print height now, not by a row count: the fourteen-row cap of 22 Aug
    #  assumed even rows, and rows stopped being even when the comments column
    #  became a stack. On 26 Aug one staff note - a raw Mews order dump - ran
    #  to nine printed lines inside ONE row, the count could not see it, and
    #  the last blank plus the day's summary printed on a second page carrying
    #  nothing else.
    ck("a light house gets its four spare lines",
       rw["blanks"] == 4 and rw["n"] == len(d) + 4)
    #  The budget is the page's own fact, read from it rather than restated
    #  here, so this suite cannot drift from what the sheet actually does.
    #  window.-qualified so a sheet that has LOST the budget reads as a FAIL
    #  with a name on it rather than a ReferenceError that kills the suite.
    budget = pg.evaluate("()=>window.PRINT_TABLE_BUDGET_MM || 0")
    print("   print budget:", budget, "mm")
    ck("the print budget leaves real room for what no stylesheet can see",
       isinstance(budget, (int, float)) and 200 <= budget <= 260)
    #  The invariant that replaced the cap: laid out at the print metrics (the
    #  same .pmeasure rules the page itself measures with), a table still
    #  carrying blank rows fits the budget, summary footer included.
    def printed_mm(page):
        return page.evaluate("""()=>{
          const box=document.createElement('div'); box.className='pmeasure';
          const c=document.querySelector('#sheetScroller table').cloneNode(true);
          c.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
          box.appendChild(c); document.body.appendChild(box);
          const h=c.getBoundingClientRect().height;
          document.body.removeChild(box);
          return h/96*25.4;}""")
    mm = printed_mm(pg)
    print("   printed table: %.0fmm of %dmm" % (mm, budget))
    ck("and with its blanks in it the printed table fits that budget",
       mm <= budget)
    ck("and the measuring box is never left in the page",
       pg.evaluate("()=>!document.querySelector('.pmeasure')"))
    r1=d[0]
    ck("r1 conflict row + FLAG + PRE-MENU", "row-conflict" in r1["cls"] and "FLAG" in r1["name"] and "PRE-MENU" in r1["name"])
    ck("r1 dietaries as pills, allergy solid and shortened",
       "NUT" in r1["diet"].upper() and "VEGETARIAN" in r1["diet"].upper()
       and "ALLERGY" not in r1["diet"].upper()
       and 'dpill dpill-al' in r1["dietHTML"] and 'class="dpill"' in r1["dietHTML"])
    ck("r1 checkout tomorrow red", "checkout" in pg.evaluate("()=>document.querySelectorAll('#rows tr')[0].querySelector('td.c-dep').innerHTML"))

    #  The FLAG badge said a guest had a conflict tonight and never said which
    #  one. The detail lived only in the bubble on Reservations, which is a
    #  screen, and this sheet exists for the moments nobody is at a screen: it
    #  goes on the pass. A waiter could read that something was wrong with a
    #  table and not what.
    clash = pg.evaluate("""()=>{const e=document.querySelectorAll('#rows tr')[0]
        .querySelectorAll('.dclash'); return [...e].map(x=>x.textContent.trim());}""")
    print("   clash lines:", clash)
    ck("the flagged row names the dish and the dietary it clashes with",
       len(clash) == 1 and "Satay Chicken" in clash[0] and "Nut allergy" in clash[0])
    #  Same wording as the bubble, so paper and screen do not disagree in
    #  front of a guest.
    ck("in the wording the bubble uses",
       clash and clash[0].strip().startswith("Satay Chicken"))
    #  A guest not dining cannot clash with tonight's menu, which is the guard
    #  the row colour already used.
    ck("a guest who is not dining carries no clash line",
       pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
          .filter(t=>t.className.indexOf('row-out')>-1)
          .every(t=>!t.querySelector('.dclash'))"""))
    ck("and neither does a guest with no conflict",
       pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
          .filter(t=>t.className.indexOf('row-conflict')<0)
          .every(t=>!t.querySelector('.dclash'))"""))
    #  Every flagged row explains itself. A flag with no reason is the bug.
    ck("every flagged row says why it is flagged",
       pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
          .filter(t=>t.className.indexOf('row-conflict')>-1)
          .every(t=>!!t.querySelector('.dclash'))"""))

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
    #  The note now shares the dietary line rather than sitting in its own
    #  block beneath the pills. Same words, one line up.
    ck("r1 comment and dietary note both reach the sheet",
       "Window seat" in r1["dietHTML"] and "Very allergic" in r1["dietHTML"])

    hdr=pg.evaluate("""()=>{const th=[...document.querySelectorAll('thead th')].map(x=>x.textContent.trim());
      const dc=document.querySelector('thead th.c-dc');
      const cells=document.querySelector('#rows tr').cells.length;
      return {heads:th, span:dc?+dc.getAttribute('colspan'):0, cells:cells};}""")
    print("   header:", hdr)
    ck("dietaries and comments are one column at combined width",
       hdr["span"]==2 and hdr["cells"]==8 and "Comments" not in hdr["heads"])
    #  Reversed on purpose, 22 Aug. The note used to sit in a block BENEATH
    #  the pills, which made every dietary guest two lines tall inside a row
    #  eight columns wide. The comments column is its own stack of ruled lines
    #  now, and the dietary line spreads across the whole width of it: pills
    #  and note beside each other, on one line, with the staff note on the next
    #  and a blank one under both to write on.
    lay=pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
      .filter(t=>t.querySelector('.crow.diet .dwrap') && t.querySelector('.crow.diet .inote'))
      .map(t=>{const p=t.querySelector('.crow.diet .dwrap').getBoundingClientRect();
               const c=t.querySelector('.crow.diet .inote').getBoundingClientRect();
               return {sameLine: Math.abs(Math.round(c.top)-Math.round(p.top)) < 8};})""")
    print("   pills-beside-note rows:", lay)
    ck("the note sits beside the pills on one dietary line",
       len(lay)>0 and all(r["sameLine"] for r in lay))
    #  The writing line is the reason the stack exists: until now the only
    #  place to note "moved to 7pm" against a named guest was the spare rows
    #  at the foot, which belong to nobody.
    ck("every listed guest gets a blank line of their own to write on",
       pg.evaluate("""()=>[...document.querySelectorAll('#rows tr')]
          .filter(t=>!t.className.includes('blank'))
          .every(t=>!!t.querySelector('.crow.write'))"""))
    ck("and the writing line is always last in the stack",
       pg.evaluate("""()=>[...document.querySelectorAll('#rows tr .cbox')]
          .every(b=>b.lastElementChild &&
                    b.lastElementChild.className.indexOf('write')>-1)"""))
    ck("r2 declined tinted", "row-out" in d[1]["cls"] and d[1]["din"]=="No")
    ck("rooms 3+4 boxed pair", "g-in g-first" in d[2]["cls"] and "g-in g-last" in d[3]["cls"] and d[3]["name"]=="Lucy")
    ck("r4 known-but-silent shows dash", d[3]["din"]=="\u2013" and "row-unk" in d[3]["cls"])
    # Villa 5 is vacant, so it is not on the sheet at all: the sheet is read
    # down in service and every line on it should be somebody to look after.
    # That shifts every row after it up by one.
    ck("vacant villa 5 is absent, not listed empty",
       all("row-vacant" not in x["cls"] for x in d)
       and all(x["name"] != "Vacant" for x in d))
    ck("dropping a villa does not renumber the ones after it",
       any(x["room"] == "9" for x in d))
    ck("and no warning while the house has bookings in it",
       pg.evaluate("()=>getComputedStyle(syncWarn).display") == "none")
    #  By name rather than by index: the row list changes length whenever the
    #  house does, and an index here would break on a quiet night rather than
    #  on a real fault.
    priya=[x for x in d if x["name"]=="Priya"]
    ck("r9 Priya listed silent",
       len(priya)==1 and priya[0]["din"]=="\u2013" and priya[0]["room"]=="9")
    ext=[x for x in d if x["room"]=="ext"]
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
    # -enc UTF-8, because pdftotext defaults to Latin-1 and the runner sets
    # PYTHONUTF8: a middot in the sheet decoded as invalid UTF-8 and stdout
    # came back None, which crashed the suite instead of failing a check.
    txt = subprocess.run(["pdftotext","-enc","UTF-8","/home/claude/nala/_p2_dietpdf.pdf","-"],
                         capture_output=True, text=True, encoding="utf-8").stdout
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
       q.evaluate("()=>[...document.querySelectorAll('.crow.staff')]"
                   ".some(e=>e.textContent.indexOf('do not charge for wine')>-1)"))
    ck("and is labelled so nobody cooks to it",
       q.evaluate("()=>[...document.querySelectorAll('.crow.staff')]"
                   ".every(e=>e.textContent.indexOf('Staff')>-1)"))
    ck("what Mews said stands in when nobody has rewritten it",
       q.evaluate("()=>document.body.innerText.indexOf('Complained about noise')>-1"))
    ck("an empty note prints nothing at all",
       q.evaluate("()=>[...document.querySelectorAll('.crow.staff')].length===2"))
    q.close()

    #  A note cleared on purpose, which until 22 Aug reappeared as the Mews
    #  original because empty was read as absent. This sheet is printed and
    #  left on a pass, so a note somebody deleted coming back on paper is the
    #  worst of the three places that happened.
    internal["b3"] = {"fromMews": "Complained about noise last stay", "note": ""}
    q = as_role("staff@x")
    q.wait_for_timeout(1200)
    ck("a note cleared on purpose does not print the Mews original",
       q.evaluate("()=>document.body.innerText.indexOf('Complained about noise')<0"))
    ck("and prints no empty staff line either",
       q.evaluate("()=>[...document.querySelectorAll('.crow.staff')].length===1"))
    q.close()
    internal["b3"] = {"fromMews": "Complained about noise last stay"}

    #  ── the night that found the row-count cap out ──────────
    #  26 Aug: a sheet under its row cap and over the page. One staff note -
    #  a raw Mews order dump - ran to nine printed lines inside one row, so
    #  counting rows said the sheet fitted while measuring said it did not,
    #  and the last blank went to a second page with the day's summary under
    #  it: a printed page whose only ink was a footer. Drawn tall here on
    #  purpose, three dump-sized notes across twelve dining villas, so the
    #  measured answer and the counted answer disagree and the suite catches
    #  whichever one the page is using.
    DUMP = ("createdUtc: 2026-07-07T06:28:44Z id: c20eda2e-4c43-4e57-b62b "
            "orderId: 203a773e-4fd0-4418-ad4d text: Hi, would prefer a view "
            "over the beach rather than the pool, please. Many thanks, very "
            "much looking forward to our stay :) type: General "
            "updatedUtc: 2026-07-07T06:28:44Z") * 2
    heavy_resp, heavy_guests, heavy_stays, heavy_internal = {}, {}, {}, {}
    for i in range(1, 13):
        heavy_resp["04000001%02d" % i] = {
            "status": "in", "pax": 2, "room": str(i), "name": "Guest %d" % i,
            "arrives": plus(-2), "departs": plus(2),
            "diets": ["Dairy free", "Gluten free"],
            "dnote": "No chilli, no cold food or drink below room temperature"}
        heavy_guests[str(i)] = {"name": "Guest %d" % i, "departs": plus(2)}
        heavy_stays[str(i)] = {"id": "hb%d" % i, "name": "Guest %d" % i}
    for i in (1, 2, 3):
        heavy_internal["hb%d" % i] = {"fromMews": DUMP}
    def heavy_fb(route, request):
        u = request.url
        if "/responses/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(heavy_resp)); return
        if "/roomguests/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(heavy_guests)); return
        if "/stays/" + today in u:
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(heavy_stays)); return
        if "/internal/" in u:
            k = u.split("/internal/")[1].split(".json")[0]
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(heavy_internal.get(k))); return
        if "/manual/" in u or "/combined/" in u:
            route.fulfill(status=200, content_type="application/json",
                          body="null"); return
        fb(route, request)
    q = b.new_page(viewport={"width": 900, "height": 1100})
    q.route("**/firebase-app-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body=SDK))
    q.route("**/firebase-auth-compat.js", lambda r,_: r.fulfill(status=200,
        content_type="application/javascript", body="/*n*/"))
    q.route("**firebasedatabase.app/**", heavy_fb)
    q.route("**/menu.json*", lambda r,_: r.fulfill(status=200,
        content_type="application/json", body=json.dumps(menu)))
    q.goto("http://localhost:8955/list.html"); q.wait_for_timeout(2600)
    hv = q.evaluate("""()=>({
        blanks:document.querySelectorAll('#rows tr.blank').length,
        guests:[...document.querySelectorAll('#rows tr')]
          .filter(t=>!t.className.includes('blank')).length,
        notes:document.querySelectorAll('.crow.staff').length})""")
    mmh = printed_mm(q)
    print("   heavy house: %d guests, %d blanks, %.0fmm of %dmm, %d staff notes"
          % (hv["guests"], hv["blanks"], mmh, budget, hv["notes"]))
    #  The notes are what make the rows tall, and they land AFTER the sheet
    #  first draws, which is why the measurement re-runs when they do. A green
    #  here on a sheet with no notes painted would be testing the wrong night.
    ck("the dump-sized staff notes are on the sheet being measured",
       hv["notes"] == 3)
    ck("every guest is still on the sheet, whatever the budget says",
       hv["guests"] == 12)
    ck("spare lines are dropped before they can spill",
       hv["blanks"] == 0 or mmh <= budget)
    ck("and a house too tall for one page sheds all of them",
       hv["blanks"] == 0)
    q.close()

    #  ── the whole house silent ──────────────────────────────
    #  Hiding villas Mews has said nothing about is only safe while silence
    #  means an empty villa. Mews sends reservations and nothing else, so
    #  silence is also what a broken sync looks like, and on 19 Aug every write
    #  was being refused and /stays genuinely held nothing. The old sheet said
    #  so by accident: seventeen labelled rows with dashes were unmistakable.
    #  Hidden, the same morning prints a short calm sheet that looks correct,
    #  which is the worse failure. So it says it out loud instead.
    keep = (STAYS.copy(), dict(roomguests), dict(manual), dict(responses))
    STAYS.clear(); roomguests.clear(); manual.clear(); responses.clear()
    q = as_role("staff@x")
    q.wait_for_timeout(600)
    ck("a house with no bookings at all is called out, not printed blank",
       q.evaluate("()=>getComputedStyle(syncWarn).display") != "none")
    warn = q.evaluate("()=>syncWarn.textContent").lower()
    ck("and names the likely cause rather than the house being empty",
       "sync" in warn and "empty house" in warn)
    ck("and says not to trust the sheet",
       "trust" in warn)
    q.close()
    STAYS.update(keep[0]); roomguests.update(keep[1])
    manual.update(keep[2]); responses.update(keep[3])

    q=as_role("chef@x")
    q.wait_for_timeout(1200)
    ck("the chef reads the sheet but not the staff note",
       q.evaluate("()=>document.querySelectorAll('.crow.staff').length===0"))
    ck("chef reads and prints the sheet",
       q.evaluate("""()=>noAccess.className.indexOf('show')<0
                      && document.querySelectorAll('table tbody tr').length>0
                      && getComputedStyle(footBar).display!='none'"""))
    q.close()

    q=as_role("waiter@x")
    q.wait_for_timeout(1200)
    ck("nor does a waiter carrying it into service",
       q.evaluate("()=>document.querySelectorAll('.crow.staff').length===0"))
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
