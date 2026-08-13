#!/usr/bin/env python3
"""Build standalone offline demo copies of the printed sheets.

Each output is ONE file with no network calls at all: the shared CSS and JS
are inlined, the Firebase and auth scripts are removed, and fetch() is
replaced by a canned busy-night dataset. Save it to the phone and open it
from Files - it works with no signal and cannot write to the database.

    python3 tools/make-demo.py

Writes demo-tally.html, demo-reservations.html, demo-cleans.html and
demo-clean.html at the repo root.
Re-run it after changing a sheet; the demo does not track changes by itself.
"""
import re, os, datetime, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# ── a busy night, fixed so the sheet looks the same every time ──────────
ROOMS = 17
def build_data():
    names = ["James Harrington","Elena Petrova","Mark Whitfield","Lucy Whitfield",
             "David Chen","Priya Sharma","Tom Ashby","Ruby Vance","Claire Donnelly",
             "Sam Okafor","Nina Brandt","Owen Reilly","Hana Sato","Marco Bianchi",
             "Freya Lindqvist","Jonah Adeyemi","Iris Kovac"]
    diets = {3:["Nut allergy"], 7:["Dairy free"], 11:["Coeliac"], 15:["Vegetarian"]}
    notes = {1:"Window seat please", 8:"Birthday", 12:"Quiet corner"}
    resp, rg, hk = {}, {}, {}
    for r in range(1, ROOMS+1):
        phone = "04000000%02d" % r
        rg[str(r)] = {"name": names[r-1], "arrives":"~D-2~",
                      "departs": ("~D0~" if r % 5 == 0 else "~D+2~")}
        if r in (6, 13):                       # not dining
            resp[phone] = {"status":"out","room":str(r),"name":names[r-1],"at":"~D0~T09:00:00"}
        elif r in (9, 16):                     # no answer yet - left out of responses
            pass
        else:
            resp[phone] = {"status":"in","pax": 2 if r % 3 else 3, "room":str(r),
                           "name":names[r-1], "phone":"0400 000 0%02d" % r,
                           "at":"~D0~T09:%02d:00" % (r % 60)}
            if r in diets: resp[phone]["diets"] = diets[r]
            if r in notes: resp[phone]["note"]  = notes[r]
    for r in (1, 2):  hk[str(r)] = {"bfast":"~D0~T07:5%d:00" % r}
    for r in (5, 10): hk[str(r)] = {"done":"~D0~T10:0%d:00" % r}
    hk["15"] = {"departed": True}
    manual = {"ext-1": {"status":"in","pax":2,"name":"Cane","source":"manual",
                        "diets":["Dairy free"],"external":True},
              "ext-2": {"status":"in","pax":2,"name":"Jill","source":"manual","external":True},
              "ext-3": {"status":"in","pax":2,"name":"Larry","source":"manual",
                        "note":"Birthday","external":True}}
    combined = {"g1": {"rooms":["3","4"]}, "g2": {"rooms":["7","8","9"]}}
    return dict(responses=resp, roomguests=rg, hk=hk, manual=manual, combined=combined)

STUB = """
<script>
/* ── OFFLINE DEMO ─────────────────────────────────────────────────────
   No Firebase, no auth, no network. Fixed data below. Writes do nothing. */
(function(){
  var DATA = __DATA__;
  function todayISO(){ var d=new Date();
    return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
  function shift(n){ var d=new Date(); d.setDate(d.getDate()+n);
    return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
  function dates(o){                 /* ~D0~ / ~D+2~ / ~D-2~ -> real dates */
    return JSON.parse(JSON.stringify(o), function(k,v){
      if (typeof v !== 'string') return v;
      return v.replace(/~D([+-]?\\d*)~/g, function(m,n){ return shift(n===''?0:parseInt(n,10)); });
    });
  }
  var D = dates(DATA), TODAY = todayISO();

  window.firebase = { initializeApp:function(){},
    auth:function(){ return { onIdTokenChanged:function(cb){ cb({email:'demo@nala',
      getIdToken:function(){ return Promise.resolve('demo'); }}); },
      onAuthStateChanged:function(cb){ cb({email:'demo@nala'}); }, signOut:function(){} }; } };
  window.__idToken = 'demo';

  function reply(body){
    return Promise.resolve({ ok:true, status:200,
      headers:{ get:function(){ return null; } },
      json:function(){ return Promise.resolve(body); },
      text:function(){ return Promise.resolve(JSON.stringify(body)); } });
  }
  window.fetch = function(url, opts){
    url = String(url);
    if (opts && opts.method && opts.method !== 'GET') return reply(null);   /* writes go nowhere */
    if (url.indexOf('menu.json') > -1)
      return reply({published:new Date().toISOString(), bread:{name:'Sourdough'},
                    entree:{name:'Prawn cocktail'}, main:{name:'Satay chicken'},
                    dessert:{name:'Pavlova'}});
    function on(p){ return url.indexOf(p) > -1; }
    if (on('/responses/'))  return reply(on(TODAY) ? D.responses : {});
    if (on('/manual/'))     return reply(on(TODAY) ? D.manual    : {});
    if (on('/roomguests/')) return reply(on(TODAY) ? D.roomguests: null);
    if (on('/hk/'))         return reply(on(TODAY) ? D.hk        : {});
    if (on('/combined/'))   return reply(on(TODAY) ? D.combined  : {});
    return reply(null);
  };
  document.addEventListener('DOMContentLoaded', function(){
    var b = document.createElement('div');
    b.textContent = 'OFFLINE DEMO - fixed data, nothing saves';
    b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99;background:#A8321E;'
      + 'color:#fff;font:10px/1.9 Helvetica,Arial,sans-serif;letter-spacing:.14em;'
      + 'text-align:center;text-transform:uppercase;';
    var s = document.createElement('style');
    s.textContent = '@media print { .demoband { display:none !important; } }';
    b.className = 'demoband';
    document.head.appendChild(s); document.body.appendChild(b);
  });
})();
</script>
"""

def inline(html):
    css = open('nala-ui.css').read()
    shared = open('nala-shared.js').read()
    html = re.sub(r'<link rel="stylesheet" href="nala-ui\.css\?v=\d+">',
                  lambda m: '<style>\n' + css + '\n</style>', html)
    html = re.sub(r'<script src="nala-shared\.js\?v=\d+"></script>',
                  lambda m: '<script>\n' + shared + '\n</script>', html)
    html = re.sub(r'<script src="https://www\.gstatic\.com/firebasejs/[^"]+"></script>\s*', '', html)
    html = re.sub(r'<script src="auth\.js\?v=\d+"></script>\s*', '', html)
    return html

def build(src, out, links):
    html = inline(open(src).read())
    stub = STUB.replace('__DATA__', json.dumps(build_data()))
    html = html.replace('<script>', stub + '<script>', 1)
    for a, b in links.items():                      # keep the nav usable offline
        html = html.replace('href="%s"' % a, 'href="%s"' % b)
    html = html.replace('<title>', '<title>DEMO · ', 1)
    open(out, 'w').write(html)
    print('wrote %s  (%d KB)' % (out, len(html)//1024))

LINKS = {'tally.html':'demo-tally.html',       'list.html':'demo-reservations.html',
         'cleaners.html':'demo-cleans.html',   'housekeeping.html':'demo-clean.html'}
build('tally.html',        'demo-tally.html',        LINKS)   # Reservations (live board)
build('list.html',         'demo-reservations.html', LINKS)   # Reservations Sheet
build('cleaners.html',     'demo-cleans.html',       LINKS)   # Cleans (live board)
build('housekeeping.html', 'demo-clean.html',        LINKS)   # Clean sheet
