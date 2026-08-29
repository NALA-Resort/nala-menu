# BUDGET_APP_CONTEXT.md

Context for building a new HTML budgeting app that reuses the patterns of
`nala-menu` (the NALA resort's dinner-menu / reservation / housekeeping
system). Written for an assistant that has never seen this repo.

What this repo is: a live, guest-facing web app for a 17-villa resort.
Plain static HTML pages served by **GitHub Pages** at `menu.nalaresort.com`,
**Firebase Realtime Database + Firebase Auth** behind them, three
**Cloudflare Workers** for the server-side jobs (PMS sync, SMS sending, push
notifications), and **ClickSend** for SMS. No framework, no bundler, no build
step. All code below is quoted from the repo as of 29 Aug 2026. Anything that
looked like a credential is replaced with `REDACTED`; the shape is untouched.

A note on the repo's own philosophy, because it explains everything else:
`CLAUDE.md`'s rule is **"a fact lives in one file"** — one `NAV` array
generates every page's menu, one `formState()` decides a form's state for
every board, forced duplicates (a Worker can't import from the site) get a
shared JSON test table both copies are asserted against. Comments in this
codebase explain *why*, usually with the date of the incident that taught
the lesson. Preserve that style if you lift code.

---

## 1. The Cleaners / "Clean" page — tile system

File: `cleaners.html` (single self-contained page: its own `<style>`, its own
inline `<script>`, plus the shared files). 17 villas, one tile each, one
screen, no scrolling — the whole point of the board is seeing every villa at
once on a phone.

### 1.1 The container and grid layout

The page skeleton (the tiles are **not** in the HTML — the grid div is empty
and filled by JS):

```html
<body class="tier-app ui2">

<div class="wrap">
  <div class="daterow">
    <button class="dnav today" id="dToday">Today</button>
    <button class="dnav" id="dPrev">&#8249;</button>
    <div class="date" id="title"></div>
    <button class="dnav" id="dNext">&#8250;</button>
    <div class="navwrap" id="navWrap" style="display:none">
      <button class="navbtn" id="navBtn" aria-label="Menu"><span></span><span></span><span></span></button>
      <div class="navdrop" id="navDrop"></div>
    </div>
  </div>

  <div class="stats" id="statsRow">
    <div class="stat"><span class="stat-n" id="nClean">&ndash;</span><span class="stat-l">Cleans</span></div>
    <div class="stat"><span class="stat-n" id="nSvc">&ndash;</span><span class="stat-l">Services</span></div>
    <div class="stat" id="preWrap" style="display:none"><span class="stat-n" id="nPre">&ndash;</span><span class="stat-l">Pre-arrivals</span></div>
    <div class="stat"><span class="stat-n" id="nDone">&ndash;</span><span class="stat-l">Done</span></div>
  </div>

  <div class="noaccess" id="noAccess"></div>

  <div class="grid" id="grid"></div>

  <div class="legend" id="legend">
    <span><i class="lgb"></i>Clean</span>
    <span><i class="lgb svc"></i>Service</span>
    <span><i class="lgb arr"></i>Clean + arrival</span>
    <span><i class="lgb pre"></i>Pre-arrival</span>
    <span><i class="lgb dash"></i>Unknown</span>
  </div>

  <div class="foot bar" id="footBar">
    <button class="btn" onclick="location.reload()">Refresh</button>
    <button class="btn" id="selToggle">Select multiple</button>
  </div>
</div>

<div class="ov" id="ov"><div class="sheet" id="sheetBox"></div></div>
```

Grid CSS. The design decision: the board fills whatever height the phone has
left, rows share it, tiles have no fixed height. Comments are the repo's own:

```css
body { height:100vh; height:100dvh; }
/* flex:1 1, not the shared 1 0: a wrap that refuses to shrink pushes the
   page past the screen however small the tiles are told to be. */
body > .wrap { max-width:520px; margin:0 auto; flex:1 1 auto; min-height:0; }

.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(96px,1fr));
        gap:10px; flex:1 1 auto; min-height:0;
        grid-auto-rows:minmax(56px,1fr); overflow-y:auto; }
```

Responsive rules — note they are keyed on **orientation and height**, not
width breakpoints, and named as a column *count* because that is the fact
that has to hold:

```css
/* Three columns on any phone held upright, whatever the width. The grid was
   choosing by width alone, so a 320 point screen lost the third column to
   the body's own padding and dropped to two ... Named as a count rather
   than a minimum width, because what has to hold here is the number of
   columns, and a minimum width only implies it. */
@media (orientation: portrait) and (max-width: 520px) {
  .grid { grid-template-columns:repeat(3, 1fr) !important; }
}

/* A short phone held upright: six rows of villas and very little height to
   put them in. The rows give up what they can while staying above the tap
   target, rather than the board scrolling. */
@media (orientation: portrait) and (max-height: 620px) {
  .grid { grid-auto-rows:minmax(46px, 1fr) !important; gap:7px !important; }
  .tile { padding:6px 6px 5px !important; gap:3px !important; }
  .tile .rn { font-size:19px !important; }
  .tile .sub { font-size:8.5px !important; min-height:10px !important; }
  .legend { padding:4px 5px !important; font-size:6px !important; gap:1px !important; }
  .legend .lgb { width:12px; height:5px; }
}

/* Landscape on a phone. The height is what runs out, not the width ...
   Six columns makes it three rows, which does [fit]. Everything else in the
   furniture gives up what it can ... the tiles are the thing being tapped
   and shrink last. */
@media (orientation: landscape) and (max-height: 560px) {
  body { padding-top:calc(6px + env(safe-area-inset-top)); }
  .grid { grid-template-columns:repeat(6, 1fr) !important;
          grid-auto-rows:minmax(46px, 1fr) !important; gap:6px !important; }
  /* ...tile, badge, legend all scaled down in the same rule... */
}

@media (max-height: 720px) {
  body { padding-top:calc(12px + env(safe-area-inset-top)); }
  .stats { margin-bottom:6px !important; }
  .stat-n { font-size:22px; }
  .grid { gap:8px !important; }
}
```

One clever trick worth stealing: 17 villas in 3 columns leave exactly one
spare cell, and the **legend lives in the grid's 18th cell**, so the key
costs no height. Because `render()` clears the grid every pass, the legend
node is *held in a variable* and re-appended — a `getElementById` after the
first clear finds nothing:

```js
/* The key. Held rather than looked up, because every render clears the grid
   it now lives in, and a lookup after the first clear finds nothing. */
var LEGEND = null;
// ...in render(), after the tiles:
if (LEGEND) g.appendChild(LEGEND);
```

### 1.2 Full CSS for a single tile

```css
.tile { border:1.2px solid var(--rule); border-radius:10px; background:#fff;
        padding:10px 8px 9px; text-align:center; cursor:pointer; color:var(--ink);
        font-family:var(--ui-font); position:relative; min-height:0;
        display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px; }
.tile .rn { font-size:20px; font-weight:bold; }        /* the villa number */

/* The job bar ("chip"). No words on it - the word is in aria-label/title.
   Every bar is the same size; colour and pattern are the message. */
.tile .chip { display:block; width:56%; height:9px; padding:0; font-size:0;
              border:1.5px solid var(--bluebar); border-radius:5px;
              background:var(--bluebar); color:transparent; overflow:hidden; }
.tile .chip.svc { background:var(--greenbar); border-color:var(--greenbar); }
.tile .chip.pre { background:var(--amberbar); border-color:var(--amberbar); }
/* Half clean, half arrival: the bar shows the two jobs rather than a third
   pattern standing for them. The clean half leads because the clean has
   to happen first. */
.tile .chip.arr { border-color:var(--bluebar);
                  background:linear-gradient(90deg,
                    var(--bluebar) 0 50%, var(--amberbar) 50% 100%); }
/* Unknown is a gap in what we know, not a job: the only one with no fill
   and the only dashed one. Grey, because red is reserved for something
   being wrong. */
.tile .chip.ver { background:transparent; border-style:dashed;
                  border-color:var(--mid); }

/* Who is on it: initials in a filled badge, bottom right. Yours is inverted
   rather than coloured, because colour on this board means which job. */
.tile .who-badge { position:absolute; bottom:5px; right:5px;
                   min-width:20px; height:20px; padding:0 4px;
                   border-radius:10px; border:1.5px solid var(--ink);
                   background:var(--ink); color:var(--cream);
                   font-family:var(--ui-font); font-size:9px; font-weight:bold;
                   display:flex; align-items:center;
                   justify-content:center; box-sizing:border-box; }
.tile .who-badge.mine { background:var(--cream); color:var(--ink); }

/* The one line of text under the bar */
.tile .sub { font-size:9.5px; color:var(--mid); min-height:12px; }
.tile .sub b { color:var(--ink); }
/* Elapsed-time colour: green first ten minutes, ink from ten, amber from
   fifteen, red from twenty. The only place colour means time, not state. */
.tile .sub b.fresh { color:#4E6B4B; }
.tile .sub b.soon { color:var(--amberb); }
.tile .sub b.late { color:var(--red); }

/* Colour means "this villa is ready to work on now". A finished villa loses
   its colour entirely: it is no longer work, and must stop competing for
   attention. */
.tile.ready-clean { background:var(--blue);  border-color:var(--blueb); }
.tile.ready-svc   { background:var(--green); border-color:var(--greenb); }
.tile.done   { background:#F2F2EF; border-color:var(--rule); }
.tile.done .rn { opacity:.75; }
.tile.done .chip { opacity:.4; }
/* pushed reads like finished - it is off today's list - but purple says it
   is deferred rather than done */
.tile.pushed .chip { color:#6B4E9B; border-color:#C7B6E0; }
/* a vacant villa is not a job - visible for orientation, must not compete */
.tile.vac    { opacity:.22; }
/* multi-select */
.tile.sel    { outline:2px solid var(--ink); outline-offset:-2px; }
body.selmode .tile { opacity:.3; }
body.selmode .tile.selectable { opacity:1; }

/* Corner marks: strip/linen icons top-left, expected arrival time top-right */
.tile .task-icons { position:absolute; top:5px; left:5px; display:flex;
                    gap:3px; color:#55554F; }
.tile .task-icons svg { width:14px; height:14px; display:block; }
.tile.done .task-icons { opacity:.4; }
.tile .eta { position:absolute; top:5px; right:5px; font-family:var(--ui-font);
             font-size:9.5px; font-weight:bold; color:#55554F; }
.tile .eta.early { color:var(--amberbar); }
.tile .eta.due { color:var(--red); }
.tile.done .eta { opacity:.4; }
```

Page-local colour tokens (this page deliberately owns saturated "bar"
colours; the shared muted tints stayed for backgrounds — the comments explain
the arm's-length-readability incident that forced it):

```css
:root {
  --green:#E4EDE2;
  /* saturated, for the 9px bars only - the muted tokens vanish at that size */
  --amberbar:#E8891A;
  --bluebar:#2E74C0; --greenbar:#4E8F4A;
  --blue:#E7E9EF; --blueb:#8A90A8}
```

### 1.3 Every tile status

A tile's *kind* (what job the villa is) and its *day-state* (marks staff have
made) combine. Kinds, decided by `hkClassify` in `nala-shared.js`:

| kind | Meaning | Tile look |
|---|---|---|
| `clean` | guest departing today, villa needs a full clean | white tile, solid **blue** bar (`--bluebar:#2E74C0`); turns `.ready-clean` (fill `--blue:#E7E9EF`, border `--blueb:#8A90A8`) once the guest has departed |
| `clean` + arriving tonight | same clean, someone arrives after it | split bar `.chip.arr` — left half blue, right half amber `#E8891A` |
| `svc` | guest staying on, villa needs a service | solid **green** bar (`--greenbar:#4E8F4A`); tile turns `.ready-svc` (fill `--green:#E4EDE2`, border `--greenb:#7E937A`) once marked "possibly available" |
| `pre` | nobody in last night, guest arrives today — preparation, not cleaning | solid **amber** bar `.chip.pre` (`--amberbar:#E8891A`) |
| `ver` | unknown — no usable booking data | dashed grey outline bar `.chip.ver` (border `--mid:#999990`, no fill). The only dashed one on purpose |
| `vac` | empty villa, no job | no bar, `<span class="sub">Empty</span>`, whole tile `.vac { opacity:.22 }` |

Day-state overlays (from the `/hk/<date>/<villa>` record):

| state | Tile |
|---|---|
| done (`h.done` set) | `.done` — fill `#F2F2EF`, bar at 40% opacity, sub says `Done by <initials> HH:MM` |
| pushed to tomorrow (`h.pushed`) | `.done.pushed` — looks finished but the chip goes purple ink `#6B4E9B` / border `#C7B6E0`, sub says `Pushed` |
| claimed (`h.takenBy`, not done) | `.who-badge` with the claimer's initials; `.mine` (inverted) if it's you |
| stripped / linen (`h.stripped`, `h.linen`) | small grey SVG icons top-left |
| arriving, with ETA | `.eta` top-right; `.early` amber, `.due` red when the hour is close (today only) |
| selectable in multi-select | body gets `.selmode`; only `kind === 'ver'` rows get `.selectable`, the rest dim to opacity .3 |

The colour discipline behind all this is written down in `CLAUDE.md` as "the
colour law" (one meaning per colour, everywhere): red is **failure only**
(plus one ruled exception, a guest's allergy), amber is *attention/chase
this*, green is *done/confirmed*, terracotta is *a guest's negative answer*,
grey fill is *waiting on the other side*, cream is *work to do*, true white
is *an editable surface*. If you carry the tile system into the budget app,
carry the discipline: decide what each colour means once, write it down, and
never let a second meaning share a colour.

### 1.4 Tiles are generated from data in a loop

`load()` fetches ~8 database nodes in one `Promise.all`, builds
`STATE = { rows:[], hk:{} }`, and calls `render()`. The shape of the data
behind one tile:

```js
// one row (built in load(), one per villa 1..17):
{ n: 7,                    // villa number
  kind: 'clean',           // current job (staff override wins over booking)
  base: 'clean',           // what the booking dates alone say
  pushedIn: false,         // pushed yesterday and never finished
  pushedFrom: null,        // which day the push came from
  arrivingBooked: true }   // what the BOOKING says about tonight

// STATE.hk[7] - the day's writable record at /hk/<date>/<villa>:
{ kind: 'clean',                       // manager's override of the job
  departed: true,                      // guest has checked out
  bfast: '2026-08-29T08:12:00.000Z',   // "possibly available" timestamp
  takenBy: 'maria@staff,nala',         // who claimed it (email key)
  takenAt: '2026-08-29T08:30:00.000Z',
  stripped: '2026-08-29T08:40:00.000Z',
  linen: '2026-08-29T08:44:00.000Z',
  done: '2026-08-29T09:02:00.000Z',
  doneBy: 'maria@staff,nala',
  pushed: null,                        // ISO timestamp when deferred to tomorrow
  arriving: undefined,                 // true/false manager override, absent = booking decides
  carried: '2026-08-28' }              // stamp: this record was carried in from that day
```

The render loop (abridged to the mechanics — sorting comparators and sub-text
cases omitted, they're in `cleaners.html` lines 799–1012):

```js
function render(){
  var g=document.getElementById('grid'); g.innerHTML='';
  /* The job is derived here, not frozen at load, so setting one takes effect
     on the tile immediately instead of waiting for a refresh */
  STATE.rows.forEach(function(r){
    r.kind = (STATE.hk[r.n] && STATE.hk[r.n].kind) ? STATE.hk[r.n].kind : r.base;
  });
  STATE.rows.sort(function(a,b){
    return (rank(a)-rank(b)) || (sub(a)-sub(b)) || (eta(a)-eta(b)) ||
           (seated(a)-seated(b)) || (a.n-b.n);
  });
  STATE.rows.forEach(function(row){
    var h=STATE.hk[row.n]||{};
    var cls='tile';
    if (row.kind==='vac') cls+=' vac';
    else if (h.pushed) cls+=' done pushed';
    else if (h.done) cls+=' done';
    else if (row.kind==='clean' && (h.departed || row.pushedIn)) cls+=' ready-clean';
    else if (row.kind==='svc' && h.bfast) cls+=' ready-svc';

    /* The bar. `job` is the machine readable name, the word is what a screen
       reader says and a long press shows. */
    function bar(job, word, cls){
      return '<span class="chip'+(cls?' '+cls:'')+'" data-job="'+job+'"'+
             ' role="img" aria-label="'+esc(word)+'" title="'+esc(word)+'">'+
             esc(word)+'</span>';
    }
    var chip='';
    if (row.kind==='clean'){
      var arr = arrivingNow(row, h) && !h.pushed;
      chip = h.pushed ? bar('pushed', 'Pushed')
           : arr ? bar(h.done ? 'cleaned-pre' : 'clean-pre',
                       h.done ? 'Cleaned, ready for arrival' : 'Clean, arriving tonight',
                       'arr')
           : bar(h.done ? 'cleaned' : 'clean', h.done ? 'Cleaned' : 'Clean');
    }
    else if (row.kind==='svc')
      chip = bar(h.done ? 'serviced' : 'svc', h.done ? 'Serviced' : 'Service', 'svc');
    else if (row.kind==='pre')
      chip = bar(h.done ? 'pre-arrived' : 'pre', h.done ? 'Pre-arrived' : 'Pre-arrival', 'pre');
    else if (row.kind==='ver') chip = bar('ver', 'Unknown', 'ver');
    else chip='<span class="sub">Empty</span>';

    // ... sub text, who-badge, task icons, eta built the same way ...

    var el=document.createElement('button');    // a tile IS a <button>
    el.className=cls;
    el.innerHTML='<span class="rn">'+row.n+'</span>'+chip+
                 '<span class="sub">'+sub+'</span>'+badge+tasks+eta;
    el.onclick = function(){
      if (selectMode){
        if (!selectableRow(row)) return;
        if (selected[row.n]) delete selected[row.n]; else selected[row.n] = true;
        selLabel(); render(); return;
      }
      openSheet(row);
    };
    g.appendChild(el);
  });
  if (LEGEND) g.appendChild(LEGEND);
  document.getElementById('nClean').textContent=nClean;   // ...and the stats
}
```

A rendered tile therefore looks like:

```html
<button class="tile ready-clean">
  <span class="rn">7</span>
  <span class="chip arr" data-job="clean-pre" role="img"
        aria-label="Clean, arriving tonight" title="Clean, arriving tonight">Clean, arriving tonight</span>
  <span class="sub">Departed</span>
  <span class="who-badge" title="Maria S is on this villa"
        aria-label="Maria S is on this villa">MS</span>
  <span class="task-icons"><span role="img" aria-label="Stripped" title="Stripped"><svg>…</svg></span></span>
  <span class="eta due" role="img" aria-label="Arriving 2pm" title="Arriving 2pm">2pm</span>
</button>
```

Note the ordering rule: the corner marks are *drawn* in the corners by
absolute positioning but come **last in the markup**, so the tile still
*reads* villa → job → state → person for screen readers and tests.

All names that reach HTML pass through the page's own escaper:

```js
function esc(v){
  return String(v == null ? '' : v)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}
```

### 1.5 What happens on tap: the bottom sheet

Tap → `openSheet(row)` → a fixed overlay with a bottom sheet, whose contents
are re-drawn by `drawSheet(mode)` — `'menu'` is the option list, every other
mode is a confirm screen or a direct write. One sheet, many modes, no
separate modal components.

```css
.ov { position:fixed; inset:0; background:rgba(28,28,26,.45); display:none;
      align-items:flex-end; justify-content:center; z-index:40; }
.ov.show { display:flex; }
.sheet { background:var(--cream); width:100%; max-width:520px; border-radius:14px 14px 0 0;
         padding:22px 20px 30px; font-family:var(--ui-font); }
.pbtn { display:block; width:100%; padding:14px; margin-top:9px; font-size:12px;
        background:#fff; color:var(--ink);
        border:1px solid var(--ink); border-radius:6px; cursor:pointer; font-family:var(--ui-font); }
.pbtn.solid { background:var(--ink); color:#fff; }      /* the ONE primary */
.pbtn.ghost { border-color:var(--rule); color:var(--mid); }
.pbtn.warn  { border-color:var(--red); color:var(--red); }
.pdiv { font-family:var(--ui-font); font-size:9px; color:var(--mid); margin:14px 0 6px; }
.perr { color:var(--red); font-size:11px; margin-top:12px; min-height:14px; }
```

```js
var CUR=null;
function openSheet(row){ CUR=row; drawSheet('menu'); document.getElementById('ov').className='ov show'; }
function closeSheet(){ document.getElementById('ov').className='ov'; CUR=null; }
document.getElementById('ov').onclick=function(e){ if (e.target===this) closeSheet(); };
```

The option list is *built from the villa's state* — options that don't apply
simply are not there (hidden, not disabled: "this is about not pressing
something by accident, so the button simply is not there"). Abridged from
`drawSheet('menu')`:

```js
function drawSheet(mode){
  var b=document.getElementById('sheetBox');
  var n=CUR.n, h=STATE.hk[n]||{};
  var kindName = CUR.kind==='clean' ? 'Clean - departing today'
               : CUR.kind==='svc'   ? 'Service - staying on'
               : CUR.kind==='pre'   ? 'Pre-arrival - guest arriving today'
               : CUR.kind==='vac'   ? 'Empty' : 'Unknown';
  if (h.kind) kindName += ' - set by staff';
  var head='<h2>'+(CUR.multi ? (CUR.multi.length+' villas') : 'Villa '+n)+
           '</h2><div class="st">'+(CUR.multi ? 'Villas '+n : kindName)+'</div>';
  var err='<div class="perr" id="perr"></div>';

  if (mode==='menu'){
    var rows='';
    /* Claiming a job */
    if (!h.done && !CUR.multi){
      if (!h.takenBy){
        rows+='<button class="pbtn" onclick="drawSheet(\'take\')">I’ll take this one</button>';
      } else if (h.takenBy === window.NALA_KEY || h.takenBy === window.NALA_ME){
        rows+='<button class="pbtn" disabled style="opacity:.6">You took this at '+hhmm(h.takenAt)+'</button>';
        rows+='<button class="pbtn warn" onclick="drawSheet(\'untake\')">Hand it back</button>';
      } else {
        rows+='<button class="pbtn" disabled style="opacity:.6">'+esc(fullNameFor(h.takenBy))+' took this at '+hhmm(h.takenAt)+'</button>';
        rows+='<button class="pbtn" onclick="drawSheet(\'take\')">Take it over</button>';
      }
    }
    if (h.done){
      rows+='<button class="pbtn warn" onclick="drawSheet(\'undone\')">Undo done</button>';
    } else {
      rows+='<button class="pbtn solid" onclick="drawSheet(\'done\')">'+ICON_TICK+
            (CUR.kind==='clean' ? 'Mark as cleaned'
             : CUR.kind==='pre' ? 'Mark as pre-arrived' : 'Mark as serviced')+'</button>';
      // ...Possibly available / Push / Guest departed, each state-gated...
    }
    if (window.IS_MANAGER){
      // job-change options under an 'Admin options' divider, also state-gated
      // <div class="pdiv">Admin options</div> + To be cleaned / serviced / etc.
    }
    rows+='<button class="pbtn ghost" onclick="closeSheet()">Close</button>';
    b.innerHTML=head+rows+err;
  }

  /* confirm screens: one question, one solid/warn yes, one ghost back */
  if (mode==='done'){
    var doneWord = CUR.kind==='clean' ? 'cleaned'
                 : CUR.kind==='pre' ? 'pre-arrived' : 'serviced';
    b.innerHTML=head+
      '<div class="st" style="margin-bottom:6px">Mark villa '+n+' as '+doneWord+'?</div>'+
      '<button class="pbtn solid" id="doneGo">'+ICON_TICK+'Yes - '+doneWord+'</button>'+
      '<button class="pbtn ghost" onclick="drawSheet(\'menu\')">Back</button>'+err;
    /* Wired rather than serialised into an onclick, so the name can carry an
       apostrophe without breaking the attribute it is sitting in. */
    document.getElementById('doneGo').onclick = function(){
      setField(n, { done: new Date().toISOString(),
                    doneBy: window.NALA_KEY || window.NALA_ME || null },
               document.getElementById('perr'));
    };
    return;
  }

  /* reversible one-tap actions write straight through, no confirm:
     claiming, arrivals override, strip/linen toggles */
  if (mode==='take'){
    setField(n, { takenBy: window.NALA_KEY || window.NALA_ME || 'Someone',
                  takenAt: new Date().toISOString() },
             document.getElementById('perr'));
    return;
  }
  // push / unpush / dep / undep / clearbf / bfast(timerow) / k-* follow the
  // same two shapes: confirm screen, or straight write.
}
```

The interaction law (from `STYLEGUIDE.md`, "the button law", ruled 26 Aug):
**one solid primary per surface; destructive actions wear terracotta/red
outline (`.pbtn.warn`) and always confirm before writing; reversible one-tap
actions never confirm** (a confirm between a cleaner and a claim is the
reason they'd stop claiming). Multi-select exists only for tiles whose state
is undecided (`kind === 'ver'`), and applies one decision to many villas via
the same sheet.

### 1.6 Writes, optimistic updates, and how a tile updates

There are no realtime listeners (see §2). A tile updates three ways:

1. **Optimistically on tap.** `setField` mutates `STATE.hk[n]`, calls
   `render()` *immediately*, then sends the PATCH. On failure it rolls the
   state back and re-renders, and writes a human message to the sheet's red
   error line.
2. **A 20-second poll** re-runs `load()` — but *never while a sheet is open*
   (`CUR` set), so the board never redraws under someone's hand.
3. **On tab focus** (`visibilitychange`) a full reload, because a phone
   coming back from the pocket is when a stale board is most obvious.

```js
// ── writes ─────────────────────────────────────────────────
function patchRoom(n, obj){
  return fetch(DB+'/hk/'+todayKey()+'/'+n+'.json', {
    method:'PATCH', body:JSON.stringify(obj)
  }).then(function(r){
    if (!r.ok) throw new Error('rejected');
    return r.json();
  });
}

function setField(n, obj, errEl, btn){
  var prev=JSON.parse(JSON.stringify(STATE.hk[n]||{}));
  STATE.hk[n]=Object.assign({},prev,obj);
  for (var k in obj){ if (obj[k]===null) delete STATE.hk[n][k]; }
  render();                                    // optimistic, before the request leaves
  return saveFeedback(btn === undefined ? pressedButton() : btn, function(){
    return patchRoom(n,obj).then(function(){
      /* notifyPush('departed'|'available'|'cleaned'|'serviced', n, user)
         fires only after the write succeeds, and only on the live day */
    });
  }, {
    done:'Saved ✓',
    hold:400, then:closeSheet,
    fail:function(msg){
      if (!msg){ if (errEl) errEl.textContent = ''; return; }
      STATE.hk[n]=prev; render();              // rollback
      if (errEl) errEl.textContent = msg;
    }
  });
}

load(true);
setInterval(function(){ if(!CUR) render(); }, 30000);          // tick elapsed times
setInterval(function(){
  if (!CUR && !document.hidden) load().catch(function(){});
}, 20000);
document.addEventListener('visibilitychange', function(){
  if (!document.hidden && !CUR) load(true).catch(function(){});
});
```

`saveFeedback` is the shared button-state machine (Saving → Saved ✓ → close,
or restore + red line). It's in §6.4 — reuse it wholesale.

---

## 2. Data layer

### 2.1 What's used

- **Firebase Realtime Database** (RTDB), instance
  `https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app` —
  **not Firestore**. All data lives here.
- **Firebase Auth** (email/password) via the compat CDN SDK v10.14.1 —
  loaded per page:
  ```html
  <script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js"></script>
  <script src="https://www.gstatic.com/firebasejs/10.14.1/firebase-auth-compat.js"></script>
  <script src="auth.js?v=12"></script>
  <script src="nala-shared.js?v=46"></script>
  ```
- **No Firebase Hosting** (GitHub Pages serves the site), **no Firestore, no
  Storage, no Cloud Functions** (Cloudflare Workers instead), and crucially
  **no Firebase database SDK**: every read and write is a plain `fetch` to
  the RTDB REST API (`<DB>/<path>.json`).

### 2.2 Init/config block (keys redacted)

From `auth.js`. Note the repo's own stance, stated in both Workers: *"Firebase
web API keys are public by design ... The rules protect the data, not the
key"* — it is in a public repo today. Redacted here anyway as asked:

```js
(function(){
  var CFG = {
    apiKey: "REDACTED",
    authDomain: "nala-menu.firebaseapp.com",
    databaseURL: "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app",
    projectId: "nala-menu",
    storageBucket: "nala-menu.firebasestorage.app",
    messagingSenderId: "REDACTED",
    appId: "REDACTED"
  };
  // ...
  firebase.initializeApp(CFG);
})();
```

And the one constant every page's reads hang off, in `nala-shared.js`:

```js
var DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app";
var ROOMS = 17;
```

### 2.3 The auth shim — the cleverest thing in the data layer

`auth.js` monkey-patches `window.fetch`: any request to
`firebasedatabase.app` gets the current ID token appended as `?auth=`, and is
**queued until sign-in settles**. Page code therefore does bare `fetch(DB +
path)` with no auth awareness at all:

```js
window.__idToken = null;
var settled = false;      // becomes true once signed in with a token
var pending = [];         // queued database fetches while logged out

var _fetch = window.fetch;
function realFetch(u, o){
  if (window.__idToken){
    u += (u.indexOf('?') > -1 ? '&' : '?') + 'auth=' + window.__idToken;
  }
  return _fetch.call(window, u, o);
}
window.fetch = function(u, o){
  if (typeof u === 'string' && u.indexOf('firebasedatabase.app') > -1){
    if (!settled){
      return new Promise(function(res){ pending.push(function(){ res(realFetch(u, o)); }); });
    }
    return realFetch(u, o);
  }
  return _fetch.call(this, u, o);
};
function flush(){ var q = pending; pending = []; q.forEach(function(f){ try{ f(); }catch(e){} }); }
```

The token is refreshed by the SDK; `onIdTokenChanged` keeps
`window.__idToken` current and shows the sign-in overlay when it goes away.

### 2.4 Reads and writes — the exact calls

**Reads** are GETs with a cache-buster (RTDB REST responses can otherwise be
cached by intermediaries):

```js
function api(path){ return fetch(DB+path+'.json?v='+Date.now()).then(function(r){return r.json();}); }

// a full board load is one Promise.all of node reads:
return Promise.all([ api('/responses/'+todayKey()), api('/manual/'+todayKey()),
              fetchRoomGuests(todayKey(), 14, !!full), api('/hk/'+todayKey()), lastHk(14),
              fetchStays(todayKey()), api('/dinner/'+todayKey()),
              api('/stays/'+yest) ])
```

**Writes** are `PATCH` (merge) or `PUT` (replace) to the node's `.json` URL:

```js
// merge a few fields into one villa's day record:
fetch(DB+'/hk/'+todayKey()+'/'+n+'.json', { method:'PATCH', body:JSON.stringify(obj) })

// replace a record outright (Worker-side, token passed explicitly):
fetch(DB + "/invites/" + date + "/" + v + ".json?auth=" + encodeURIComponent(idToken),
  { method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rec) });
```

**There are no realtime listeners anywhere** — no `onValue`, no SSE, no
WebSocket, so there is nothing to tear down. Freshness comes from: 20-second
polling (paused while a sheet is open or the tab is hidden), reload on
`visibilitychange`, and a 5-minute in-memory cache for the expensive
multi-day reads (`RG_CACHE` in `nala-shared.js`). For a budget app this is a
deliberate, defensible choice: polling REST is dramatically simpler than the
SDK, works with the fetch shim, and the 20s staleness window is invisible for
human-paced data. If you need live multi-user cursors, this is the one part
to swap for the SDK's `onValue`.

**Important RTDB REST behaviours** the code leans on:
- Writing `null` for a key **deletes** it (that's how undo works:
  `setField(n,{done:null,doneBy:null},…)`).
- A validation failure anywhere in a write refuses the WHOLE write with
  `Permission denied` — which reads like a login failure and is not
  (cost an evening on 18 Aug; see §7).
- Keys cannot contain `.`, so emails are keyed with every dot turned into a
  comma: `emailKey('a.b@c.com') === 'a,b@c,com'`.

### 2.5 Security rules — `rules.json`, verbatim

Deployment note: this file is **hand-pasted into the Firebase console** by
the owner; committing it does nothing by itself. The convention when a
change needs it: end your reply with `Firebase rules change: yes` and say
whether the feature limps or fails until the paste. Two pastes are currently
outstanding (see `HANDOVER.md` items 10 and 12), so the deployed rules lag
this file slightly.

The recurring shapes to learn from it: every staff check is
`root.child('staff').child(auth.token.email.toLowerCase().replace('.',','))
.child('role').val()`; permission-matrix overrides appear as
`root.child('permissions').child('<action>').child(<role>).val() == true`;
guest-facing nodes are `.read: true` per *child* (unlistable — you need the
key/token to read one); `$other: {".validate": false}` closes a record to
unknown fields; and the `$other` catch-all at the top level means **any node
you forget to name is readable/writable by any non-spa staff login** — new
nodes must be added here deliberately.

```json
{
  "rules": {
    "guests": {
      "$cid": {
        ".read": true,
        ".write": true,
        "diets": {
          "$i": {
            ".validate": "newData.isString() && newData.val().length <= 80"
          }
        },
        "dnote": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "updatedAt": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "roomguests": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin'",
      "$date": {
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$room": {
          "name": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "phone": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "arrives": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "departs": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          }
        }
      }
    },
    "responses": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin'"
    },
    "dinner": {
      "$date": {
        ".read": true,
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$villa": {
          ".write": "auth != null || !data.exists() || data.child('by').val() != 'staff'",
          ".validate": "newData.hasChildren(['status'])",
          "status": {
            ".validate": "newData.isString() && (newData.val() == 'in' || newData.val() == 'out' || newData.val() == 'vacant')"
          },
          "pax": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "room": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9]{1,3}$/)"
          },
          "by": {
            ".validate": "newData.isString() && (newData.val() == 'staff' || newData.val() == 'guest')"
          },
          "source": {
            ".validate": "newData.isString() && newData.val().length <= 20"
          },
          "bookingId": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "name": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "phone": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "note": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "dnote": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "pmsUpdated": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "override": {
            ".validate": "newData.isBoolean()"
          },
          "flag": {
            ".validate": "newData.isBoolean()"
          },
          "premenu": {
            ".validate": "newData.isBoolean()"
          },
          "nodiet": {
            ".validate": "newData.isBoolean()"
          },
          "diets": {
            "$i": {
              ".validate": "newData.isString() && newData.val().length <= 80"
            }
          }
        }
      },
      ".read": "auth != null"
    },
    "opened": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      "$date": {
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$villa": {
          ".write": "auth != null || !data.exists() || newData.child('bookingId').val() == data.child('bookingId').val()",
          ".validate": "$villa.matches(/^[0-9]{1,3}$/) && newData.hasChildren(['at','bookingId'])",
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "bookingId": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "$other": {
            ".validate": false
          }
        }
      }
    },
    "manual": {
      "$date": {
        ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$key": {
          ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
          "status": {
            ".validate": "newData.isString() && (newData.val() == 'in' || newData.val() == 'out' || newData.val() == 'vacant')"
          },
          "pax": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "room": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9]{1,3}$/)"
          },
          "note": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "override": {
            ".validate": "newData.isBoolean()"
          }
        }
      },
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'"
    },
    "menutags": {
      "$date": {
        ".read": true,
        ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$course": {
          ".validate": "$course == 'bread' || $course == 'entree' || $course == 'main' || $course == 'dessert'",
          "$i": {
            ".validate": "newData.isString() && newData.val().length <= 80"
          }
        }
      }
    },
    "dietaries": {
      ".read": true,
      ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      "$key": {
        ".validate": "newData.hasChildren(['name'])",
        "name": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 80"
        },
        "active": {
          ".validate": "newData.isBoolean()"
        },
        "group": {
          ".validate": "newData.isString() && (newData.val() == 'common' || newData.val() == 'menu')"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "menuhistory": {
      ".read": "auth != null",
      ".write": "auth != null",
      "$date": {
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "bread": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "entree": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "main": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "dessert": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "mainDesc": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "published": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        }
      }
    },
    "alerts": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').exists()",
      "$date": {
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$villa": {
          ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'sync' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')",
          ".validate": "$villa.matches(/^[0-9]{1,3}$/) && newData.hasChildren(['at'])",
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "$other": {
            ".validate": false
          }
        }
      }
    },
    "pushsubs": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      "$emailkey": {
        ".write": "auth != null && $emailkey == auth.token.email.toLowerCase().replace('.',',')",
        "endpoint": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "role": {
          ".validate": "newData.isString() && newData.val().length <= 20"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "keys": {
          "$k": {
            ".validate": "newData.isString() && newData.val().length <= 300"
          }
        }
      }
    },
    "permissions": {
      ".read": "auth != null",
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff')",
      "$action": {
        ".validate": "$action == 'resBoard' || $action == 'editBookings' || $action == 'resSheet' || $action == 'publishMenu' || $action == 'cleansBoard' || $action == 'cleansMarks' || $action == 'setJob' || $action == 'spaBoard'",
        "$role": {
          ".validate": "newData.isBoolean() && ($role == 'chef' || $role == 'waiter' || $role == 'housekeeping')"
        }
      }
    },
    "notify": {
      ".read": "auth != null",
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff')",
      "on": {
        ".validate": "newData.isBoolean()"
      },
      "hours": {
        "from": {
          ".validate": "newData.isString() && newData.val().matches(/^[0-9]{1,2}:[0-9]{2}$/)"
        },
        "to": {
          ".validate": "newData.isString() && newData.val().matches(/^[0-9]{1,2}:[0-9]{2}$/)"
        },
        "$other": {
          ".validate": false
        }
      },
      "events": {
        "$event": {
          "$role": {
            ".validate": "newData.isBoolean()"
          }
        }
      },
      "$other": {
        ".validate": false
      }
    },
    "staff": {
      ".read": "auth != null",
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff')",
      "$emailkey": {
        ".validate": "newData.hasChildren(['role'])",
        "name": {
          ".validate": "newData.isString() && newData.val().length <= 120"
        },
        "role": {
          ".validate": "newData.isString() && (newData.val() == 'admin' || newData.val() == 'manager' || newData.val() == 'staff' || newData.val() == 'chef' || newData.val() == 'waiter' || newData.val() == 'housekeeping' || newData.val() == 'sync' || newData.val() == 'spa')"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "hk": {
      "$date": {
        ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$villa": {
          ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
          ".validate": "$villa.matches(/^[0-9]{1,3}$/)",
          "kind": {
            ".validate": "newData.isString() && (newData.val() == 'clean' || newData.val() == 'svc' || newData.val() == 'pre' || newData.val() == 'vac') && auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('setJob').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)"
          },
          "done": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "bfast": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "pushed": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "departed": {
            ".validate": "newData.isBoolean()"
          },
          "stripped": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "linen": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "carried": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          }
        }
      },
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'"
    },
    "bookings": {
      "$id": {
        ".read": true,
        "pms": {
          ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'sync' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')",
          "first": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "last": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "phone": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "arrive": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "depart": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "villa": {
            ".validate": "(newData.isString() && newData.val().length <= 10) || newData.isNumber()"
          },
          "state": {
            ".validate": "newData.isString() && newData.val().length <= 30"
          },
          "mewsState": {
            ".validate": "newData.isString() && newData.val().length <= 30"
          },
          "bookingNumber": {
            ".validate": "newData.isString() || newData.isNumber()"
          },
          "groupId": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "customerId": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "adults": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "children": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "updated": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "syncedAt": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "rate": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          }
        },
        "prearrival": {
          ".write": true,
          "dining": {
            ".validate": "newData.isBoolean()"
          },
          "pax": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "noDiets": {
            ".validate": "newData.isBoolean()"
          },
          "wellness": {
            ".validate": "newData.isBoolean()"
          },
          "diets": {
            "$i": {
              ".validate": "newData.isString() && newData.val().length <= 80"
            }
          },
          "dnote": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "note": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "arriveSlot": {
            ".validate": "newData.isString() && newData.val().length <= 60"
          },
          "arriveNote": {
            ".validate": "newData.isString() && newData.val().length <= 500"
          },
          "arriveApproved": {
            ".validate": "newData.isNumber() && newData.val() >= 11 && newData.val() <= 23 && auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')"
          },
          "purpose": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "approach": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "occasion": {
            ".validate": "newData.isString() && newData.val().length <= 200"
          },
          "wellDay": {
            ".validate": "newData.isString() && newData.val().length <= 60"
          },
          "wellQty": {
            ".validate": "newData.isNumber() && (newData.val() == 1 || newData.val() == 2)"
          },
          "wellDur": {
            ".validate": "newData.isNumber() && (newData.val() == 60 || newData.val() == 90 || newData.val() == 120)"
          },
          "wellDur2": {
            ".validate": "newData.isNumber() && (newData.val() == 60 || newData.val() == 90 || newData.val() == 120)"
          },
          "wellTime": {
            ".validate": "newData.isString() && newData.val().length <= 60"
          },
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "openedAt": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "confirmedAt": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "checkedInAt": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "companion": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "$other": {
            ".validate": false
          }
        },
        "dining": {
          ".write": "auth != null"
        }
      },
      ".read": "auth != null"
    },
    "stays": {
      ".read": "auth != null",
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'sync' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')",
      "$date": {
        ".validate": "$date.matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)",
        "$villa": {
          ".validate": "$villa.matches(/^[0-9]{1,3}$/) && newData.hasChildren(['id'])",
          "id": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "first": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "last": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "phone": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "arrive": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "depart": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "adults": {
            ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 40"
          },
          "groupId": {
            ".validate": "newData.isString() && newData.val().length <= 64"
          },
          "number": {
            ".validate": "newData.isString() || newData.isNumber()"
          },
          "updated": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          }
        }
      }
    },
    "spa": {
      ".read": "auth != null",
      "$id": {
        ".validate": "$id.matches(/^[A-Za-z0-9-]{4,64}$/)",
        "$tid": {
          ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'spa' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('spaBoard').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
          ".validate": "$tid.matches(/^[A-Za-z0-9_-]{1,32}$/) && newData.hasChildren(['status','at'])",
          "status": {
            ".validate": "newData.isString() && (newData.val() == 'requested' || newData.val() == 'suggested' || newData.val() == 'booked' || newData.val() == 'declined')"
          },
          "day": {
            ".validate": "newData.isString() && newData.val().matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)"
          },
          "time": {
            ".validate": "newData.isString() && newData.val().matches(/^((09|1[0-6]):(00|30)|17:00)$/)"
          },
          "reqDay": {
            ".validate": "newData.isString() && (newData.val() == '' || newData.val().matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/))"
          },
          "reqTime": {
            ".validate": "newData.isString() && newData.val().length <= 60"
          },
          "name": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "note": {
            ".validate": "newData.isString() && newData.val().length <= 300"
          },
          "source": {
            ".validate": "newData.isString() && (newData.val() == 'prearrival' || newData.val() == 'desk' || newData.val() == 'spa')"
          },
          "dur": {
            ".validate": "newData.isNumber() && (newData.val() == 60 || newData.val() == 90 || newData.val() == 120)"
          },
          "qty": {
            ".validate": "newData.isNumber() && (newData.val() == 1 || newData.val() == 2)"
          },
          "dur2": {
            ".validate": "newData.isNumber() && (newData.val() == 60 || newData.val() == 90 || newData.val() == 120)"
          },
          "told": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "manual": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "by": {
            ".validate": "newData.isString() && newData.val().length <= 120"
          },
          "at": {
            ".validate": "newData.isString() && newData.val().length <= 40"
          },
          "$other": {
            ".validate": false
          }
        }
      }
    },
    "spasettings": {
      ".read": true,
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')",
      "price60": {
        ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 10000"
      },
      "price90": {
        ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 10000"
      },
      "price120": {
        ".validate": "newData.isNumber() && newData.val() >= 0 && newData.val() <= 10000"
      },
      "by": {
        ".validate": "newData.isString() && newData.val().length <= 120"
      },
      "at": {
        ".validate": "newData.isString() && newData.val().length <= 40"
      },
      "$other": {
        ".validate": false
      }
    },
    "prearrivalinfo": {
      ".read": true,
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager')",
      "resort": {
        ".validate": "newData.isString() && newData.val().length <= 4000"
      },
      "dining": {
        ".validate": "newData.isString() && newData.val().length <= 4000"
      },
      "by": {
        ".validate": "newData.isString() && newData.val().length <= 120"
      },
      "at": {
        ".validate": "newData.isString() && newData.val().length <= 40"
      },
      "$other": {
        ".validate": false
      }
    },
    "phonefix": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      "$id": {
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('editBookings').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
        ".validate": "$id.matches(/^[A-Za-z0-9-]{4,64}$/) && newData.hasChildren(['phone'])",
        "phone": {
          ".validate": "newData.isString() && newData.val().matches(/^\\+[0-9]{8,15}$/)"
        },
        "was": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "by": {
          ".validate": "newData.isString() && newData.val().length <= 120"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "previnvites": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      "$id": {
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('editBookings').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
        ".validate": "$id.matches(/^[A-Za-z0-9-]{4,64}$/) && newData.hasChildren(['sentAt','status'])",
        "sentAt": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "template": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "by": {
          ".validate": "newData.isString() && newData.val().length <= 120"
        },
        "status": {
          ".validate": "newData.isString() && newData.val().length <= 30"
        },
        "to": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "body": {
          ".validate": "newData.isString() && newData.val().length <= 600"
        },
        "error": {
          ".validate": "newData.isString() && newData.val().length <= 300"
        },
        "token": {
          ".validate": "newData.isString() && newData.val().length <= 16"
        },
        "providerId": {
          ".validate": "newData.isString() && newData.val().length <= 64"
        },
        "arrive": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "villa": {
          ".validate": "newData.isString() && newData.val().length <= 10"
        },
        "delivery": {
          ".validate": "newData.isString() && (newData.val() == 'delivered' || newData.val() == 'failed')"
        },
        "deliveryText": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "deliveryAt": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "presmstemplates": {
      ".read": "auth != null",
      "$id": {
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('editBookings').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
        ".validate": "$id.matches(/^[a-z0-9]{1,24}$/) && newData.hasChildren(['label','body'])",
        "label": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 40"
        },
        "body": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 500"
        },
        "order": {
          ".validate": "newData.isNumber()"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "smstemplates": {
      ".read": "auth != null",
      "$id": {
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('editBookings').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
        ".validate": "$id.matches(/^[a-z0-9]{1,24}$/) && newData.hasChildren(['label','body'])",
        "label": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 40"
        },
        "body": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 500"
        },
        "order": {
          ".validate": "newData.isNumber()"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "links": {
      "$token": {
        ".read": true,
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('editBookings').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
        ".validate": "$token.matches(/^[a-z0-9]{4,16}$/) && newData.hasChildren(['b','r'])",
        "b": {
          ".validate": "newData.isString() && newData.val().length <= 64"
        },
        "r": {
          ".validate": "newData.isString() && newData.val().matches(/^[0-9]{1,3}$/)"
        },
        "d": {
          ".validate": "newData.isString() && newData.val().matches(/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "$other": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'"
    },
    "flags": {
      ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').exists() && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff')",
      "$key": {
        ".validate": "newData.hasChildren(['name'])",
        "name": {
          ".validate": "newData.isString() && newData.val().length > 0 && newData.val().length <= 80"
        },
        "active": {
          ".validate": "newData.isBoolean()"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "bookflags": {
      "$id": {
        ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').exists() && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff')",
        "flags": {
          "$i": {
            ".validate": "newData.isString() && newData.val().length <= 80"
          }
        },
        "by": {
          ".validate": "newData.isString() && newData.val().length <= 120"
        },
        "at": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "internal": {
      "$id": {
        ".read": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').exists() && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').exists() && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() != 'spa'",
        "note": {
          ".validate": "newData.isString() && newData.val().length <= 2000"
        },
        "fromMews": {
          ".validate": "newData.isString() && newData.val().length <= 2000"
        },
        "editedAt": {
          ".validate": "newData.isString() && newData.val().length <= 40"
        },
        "editedBy": {
          ".validate": "newData.isString() && newData.val().length <= 120"
        },
        "$other": {
          ".validate": false
        }
      }
    },
    "menu": {
      ".read": true,
      ".write": "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'chef' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'staff' || root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'manager' || root.child('permissions').child('publishMenu').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)",
      "published": {
        ".validate": "newData.isString() && newData.val().length <= 40"
      },
      "bread": {
        "name": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "desc": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "aus": {
          ".validate": "newData.isBoolean()"
        },
        "$other": {
          ".validate": false
        }
      },
      "entree": {
        "name": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "desc": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "aus": {
          ".validate": "newData.isBoolean()"
        },
        "$other": {
          ".validate": false
        }
      },
      "main": {
        "name": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "desc": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "aus": {
          ".validate": "newData.isBoolean()"
        },
        "$other": {
          ".validate": false
        }
      },
      "dessert": {
        "name": {
          ".validate": "newData.isString() && newData.val().length <= 200"
        },
        "desc": {
          ".validate": "newData.isString() && newData.val().length <= 500"
        },
        "aus": {
          ".validate": "newData.isBoolean()"
        },
        "$other": {
          ".validate": false
        }
      },
      "$other": {
        ".validate": false
      }
    }
  }
}
```

### 2.6 Collection/document structure with real examples

The full map is in `HANDOVER.md` ("The data model, which is the thing to
understand first"). The principle: **the booking id identifies a guest; date
and villa identify a night and a place, not a person.**

| Node | Keyed by | Holds |
|---|---|---|
| `/bookings/<id>/pms` | Mews reservation GUID | the reservation as the PMS states it (written only by the sync Worker) |
| `/bookings/<id>/prearrival` | same | what the guest told us (guest-writable) |
| `/stays/<date>/<villa>` | date + villa | who is in which villa each night |
| `/dinner/<date>/<villa>` | date + villa | ONE dinner answer per villa per night |
| `/hk/<date>/<villa>` | date + villa | housekeeping state (the Cleans board's node) |
| `/menu` | single node | tonight's four courses |
| `/staff/<emailkey>` | email with dots→commas | `{name, role}` |
| `/permissions/<action>/<role>` | – | boolean overrides of the shipped role grants |
| `/links/<token>` | 6-char token | `{b: bookingId, r: villa, d: date, at}` — resolves an SMS short link |
| `/invites/<date>/<villa>`, `/previnvites/<bookingId>` | – | one SMS send record per addressee |
| `/notify`, `/pushsubs/<emailkey>` | – | notification settings and web-push subscriptions |

A real-shaped `/hk/<date>/<villa>` record is in §1.4. A `/stays/<date>/<villa>`
entry looks like:

```json
{ "id": "8f3a2c1e-...-mews-guid", "first": "Alice", "last": "Ngata",
  "phone": "+64274875277", "arrive": "2026-08-27", "depart": "2026-08-30",
  "adults": 2, "number": "R1234", "updated": "2026-08-26T22:04:11Z" }
```

One habit worth copying: day-partitioned nodes (`/hk/<date>/…`) mean state
expires naturally with the day and browsing history is free — but state that
must *survive* midnight has to be explicitly carried forward. `cleaners.html`
does that carry on first load of each day (the `carried` stamp marks a record
as copied-in so staff undo beats the copy). A budget app's monthly pots will
hit the same design decision: partition by month, then decide what carries.

### 2.7 Offline, load failure, write failure in the UI

- **Writes**: optimistic update → rollback + red line on failure (§1.6). The
  failure wording distinguishes the only two causes a person acts on
  differently:
  ```js
  function saveFailWords(e){
    var m = '' + (e && (e.message || e));
    if (/rejected|denied|permission|401|403/i.test(m))
      return 'The change was not allowed - tell the manager.';
    return 'Not saved - check the connection and try again.';
  }
  ```
- **Reads**: the poll swallows errors (`load().catch(function(){})`) and just
  tries again in 20s; the board keeps showing the last good state. A failed
  *initial* staff lookup is treated as a distinct state from "not on the
  list" ("Could not check access. This is usually the connection, not your
  login." + a Try again button vs. "This login has no access… See the
  manager."). The repo's standing caution: **a failed read is not an empty
  one** — never let them take the same branch.
- **No offline persistence layer**: no service-worker caching (deliberately —
  see §7), no IndexedDB mirror. Offline, the app shows stale state and writes
  fail with the connection message.

---

## 3. ClickSend / SMS

### 3.1 Where it runs

A dedicated **Cloudflare Worker**: `worker/send-invites.js`, deployed by hand
in the Cloudflare dashboard as `nala-invites`
(`https://nala-invites.ben-681.workers.dev`). It is **not** deployed by
`worker/wrangler.jsonc` (that builds the separate `nala-mews-sync` Worker).
The browser never talks to ClickSend.

The security model, from the Worker's own header comment — this is the part
to copy verbatim into any app that sends SMS:

```js
/* The page proposes; this Worker decides. A browser can be edited, and a
 * browser that can name any phone number and any message body is a browser
 * that can send anything to anyone on the resort's sender ID. So for every
 * villa asked for, the stay and dinner cell are re-read from the database
 * here, the phone number comes off that record, and the link is rebuilt from
 * it. Nothing the browser typed reaches ClickSend except the message words,
 * and those are refused if they contain a URL.
 */
```

### 3.2 Credentials

Cloudflare dashboard **secrets** on the Worker, never in the repo (which is
public), never in the browser:

```
CLICKSEND_USERNAME  the API username from the ClickSend dashboard
CLICKSEND_API_KEY   the API key generated beside it
CLICKSEND_FROM      the verified own number, e.g. +61400000000. This is the
                    Guest Touch mobile, so replies land on that handset.
FB_API_KEY          REDACTED (the Firebase web API key; "a secret only for
                    tidiness" - it is public by design, the rules protect
                    the data)
```

`wrangler.jsonc` deliberately has **no `vars` block**: *"Declaring vars here
would overwrite what is deployed; secrets set in the dashboard survive a
deploy untouched."*

### 3.3 The complete send path, end to end

**Browser side** (`invitations.html`) — collect villas + template text, POST
to the Worker with the user's Firebase ID token; a URL typed into the message
is refused client-side too; every send takes an armed second press:

```js
var INVITES_URL = 'https://nala-invites.ben-681.workers.dev';

document.getElementById('sendBtn').onclick = function(){
  var sel = selected();
  if (!sel.length || MENU_STATE !== 'live') return;
  var body = msgBox.value;
  var err = document.getElementById('errBar');
  if (bodyHasUrl(body)){
    err.textContent = 'The message contains a link. Take it out: the menu ' +
      'link is added automatically for each guest.';
    return;
  }
  err.textContent = '';
  /* EVERY send takes a second press since 25 Aug, not only resends. */
  if (!ARMED){ ARMED = true; recount(); return; }
  ARMED = false;

  var btn = this;
  btn.disabled = true; btn.textContent = 'Sending…';
  fetch(INVITES_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ idToken: window.__idToken, date: TODAY,
                           villas: sel, template: tmplSel.value, body: body })
  })
  .then(function(r){ return r.json().then(function(j){ return { ok: r.ok, j: j }; }); })
  .then(function(res){
    if (!res.ok || !res.j || !res.j.results)
      throw new Error((res.j && res.j.error) || 'the sender did not answer');
    /* Per villa, not per batch: four of six succeeding is the normal case for
       a bad number, and it must be visible which two did not. Reload from the
       database rather than trusting the summary. */
    var failed = Object.keys(res.j.results).filter(function(v){
      return res.j.results[v].status !== 'sent';
    }).sort(function(a, b){ return (+a) - (+b); });
    if (failed.length)
      err.textContent = 'Did not send to villa' + (failed.length === 1 ? '' : 's') +
        ' ' + failed.join(', ') + '. The reason is on each row.';
    return load();
  })
  .catch(function(e){
    err.textContent = 'Nothing was sent: ' + (e && e.message ? e.message : 'unknown fault') + '.';
  })
  .then(function(){ recount(); });
};
```

**Worker side** (`worker/send-invites.js`), the whole pipeline. Step 1,
verify the caller's token server-side and derive `by` from it, never from
anything the browser claimed:

```js
const look = await fetch(
  "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=" + env.FB_API_KEY,
  { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ idToken }) });
const who = await look.json().catch(() => null);
const email = look.ok && who && who.users && who.users[0] && who.users[0].email;
if (!email) return reply(401, { error: "sign in again" });
```

Step 2, check the role may send (mirrors the page's `can()` for the one
permission the Worker cares about):

```js
let staffRec, permissions;
try {
  staffRec = await dbGet("/staff/" + emailKey(email), idToken);
  permissions = await dbGet("/permissions", idToken).catch(() => null);
} catch {
  return reply(403, { error: "could not read the staff record" });
}
const role = staffRec && staffRec.role;
if (!maySend(role, permissions))
  return reply(403, { error: "this login may not send invitations" });
```

Input validation before either step — date must be "tonight" (±36h, because
the Worker's clock is UTC and the resort's isn't), villa list ≤17 numerics,
message ≤500 chars, and **no URL in the body** (the link is added
server-side):

```js
const bodyHasUrl = (s) => /(https?:\/\/|www\.)/i.test(s || "");
// ...
if (bodyHasUrl(text))
  return reply(400, { error: "the message contains a URL; the link is added here, not typed" });
```

Steps 3–6, per villa — re-read, rebuild, send, record, report:

```js
const results = {};
for (const v of villas.map(String)) {
  const rec = { sentAt: new Date().toISOString(), template: template || "",
                by: email, status: "failed", to: "", body: "", error: "" };
  try {
    const stay = await dbGet("/stays/" + date + "/" + v, idToken);
    if (!stay || typeof stay !== "object" || !stay.id)
      throw new Error("no booking in this villa tonight");
    /* The desk's fixed number outranks the Mews copy:
       /phonefix/<booking> survives every sync. */
    const fix = await dbGet("/phonefix/" + stay.id, idToken).catch(() => null);
    const raw = String((fix && fix.phone) || stay.phone || "").trim();
    if (!raw) throw new Error("no phone number on the booking");
    const phone = normalisePhone(raw);
    if (!phone)
      throw new Error("number cannot be normalised for sending: " + raw);
    rec.to = phone;
    const token = await mintToken(idToken, stay.id, v, date, rec.sentAt);
    if (!token) throw new Error("the link token did not store, nothing sent");
    rec.token = token;
    rec.body = fillMarkers(text, "https://menu.nalaresort.com/?t=" + token);
    const cs = await clickSend(env, phone, rec.body);
    if (cs.ok) {
      rec.status = "sent";
      rec.providerId = (cs.msg && cs.msg.message_id) || "";
    } else {
      throw new Error((cs.msg && cs.msg.status) ||
                      (cs.out && cs.out.response_msg) || "ClickSend refused");
    }
  } catch (e) {
    rec.error = String((e && e.message) || e);
  }
  /* Written with the caller's own token, so the rules apply to the write
     exactly as they would from the page. A record that cannot be written
     is itself reported rather than swallowed. */
  try {
    const w = await fetch(
      DB + "/invites/" + date + "/" + v + ".json?auth=" + encodeURIComponent(idToken),
      { method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(rec) });
    if (!w.ok) throw new Error("record refused");
  } catch {
    rec.error = (rec.error ? rec.error + "; " : "") + "the record did not save";
    if (rec.status === "sent") rec.status = "sent-unrecorded";
  }
  results[v] = { status: rec.status, error: rec.error || undefined };
}
return reply(200, { results });
```

### 3.4 The actual ClickSend request and response handling

```js
const CLICKSEND = "https://rest.clicksend.com/v3/sms/send";

async function clickSend(env, phone, bodyText) {
  const send = await fetch(CLICKSEND, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Basic " + btoa(
        (env.CLICKSEND_USERNAME || "").trim() + ":" +
        (env.CLICKSEND_API_KEY || "").trim()),
    },
    body: JSON.stringify({ messages: [{
      from: (env.CLICKSEND_FROM || "").trim(),
      to: phone, body: bodyText, source: "nala-menu" }],
      /* No ClickSend shortener: the link is already short and already ours,
         so the guest sees menu.nalaresort.com, not a redirect domain.
         menu.nalaresort.com must still be registered at
         dashboard.clicksend.com/sms/website-registration, or a message
         carrying the link will not send at all. */
      shorten_urls: false }),
  });
  const out = await send.json().catch(() => null);
  const msg = out && out.data && out.data.messages && out.data.messages[0];
  return { ok: send.ok && msg && msg.status === "SUCCESS", msg: msg, out: out };
}
```

So the payload shape is `{ messages: [{ from, to, body, source }], shorten_urls }`,
auth is HTTP Basic of `username:api_key`, and success is
`response.data.messages[0].status === "SUCCESS"` — the HTTP 200 alone is not
enough. `message_id` is kept as `providerId` on the send record.

**Delivery is a second, later question.** "Sent" only means ClickSend
accepted the message. The Worker's `kind:"delivery"` path is called by the
pages on load for still-unconfirmed records: it fetches
`https://rest.clicksend.com/v3/sms/receipts/<message_id>`, treats status
code 200/201 as the handset saying yes, anything else as the carrier naming a
failure (kept in the carrier's own words in `deliveryText`), and PUTs the
verdict back onto the record. This **requires a delivery report rule with
action POLL in the ClickSend dashboard**, or every receipt reads as "nothing
yet".

### 3.5 Recipients, links, inbound

- **Recipient numbers come from the database, never the client**: the booking
  record's phone, overridden by `/phonefix/<bookingId>` (a number fixed at
  the desk survives every PMS re-sync). They pass through `normalisePhone`
  (E.164 or refused — the full function is in §6.4; there is a deliberate
  twin in the Worker because a Worker can't import from the site, and both
  copies are asserted against `tests/phone_cases.json`).
- **Links**: the Worker mints a 6-char token from a 31-letter alphabet (no
  0/O/1/l/i lookalikes), stores `{b,r,d,at}` at `/links/<token>` *before*
  sending (a link that arrives already resolving beats one that resolves
  eventually), and the SMS carries `menu.nalaresort.com/?t=<token>`. The
  message template uses a `<menu>`/`<form>` marker for where the link goes;
  no marker appends it as its own last line, "which is also where iPhones
  require it before they will draw the preview card".
- **Inbound**: send-only. No webhook, no reply parsing. Replies go to the
  `CLICKSEND_FROM` number, which is a real staffed handset by design.

---

## 4. Hosting and deployment

- **GitHub Pages** serves the repo root of `NALA-Resort/nala-menu` (public)
  at `menu.nalaresort.com` (the `CNAME` file at repo root holds exactly
  `menu.nalaresort.com`). Plain static files, **no build step**. Changes go
  live within minutes of a push to `main`.
- **Routing**: there is none. Every page is a real file
  (`cleaners.html`, `tally.html`, `index.html`, …) served at its own path;
  navigation is ordinary links, generated by `buildNav` from the `NAV` array.
  `404.html` exists for bad paths. Guest deep links are query strings
  (`/?t=<token>`, `?b=<bookingId>&r=<villa>`), resolved by page JS.
- **Deployment** is `tools/publish.sh "<message>" <file> [<file>...]` — it
  rewrites and runs `tools/push.py`, which commits the named files to `main`
  **via the GitHub contents/git API** (needs a token with `contents:write`
  at `/home/claude/.ghtoken`), then hard-resets the clone to the new
  `origin/main`. Two guards, both from real losses: it refuses if `main`
  moved since this clone last published, and refuses if a modified file
  isn't in the publish (the reset would silently discard it). **There is no
  dry run and no staging** — `CLAUDE.md`: "Never publish without being asked
  to, in that session, in as many words. A green suite is not permission."
- **Cloudflare's roles** (Cloudflare does NOT serve the site):
  - `nala-mews-sync` Worker — deployed by Cloudflare **Workers Builds** from
    this repo on every `main` commit, per `worker/wrangler.jsonc`
    (root directory `worker`, `main: mews-sync.js`, cron `*/5 * * * *`).
    Zapier posts Mews reservation events to it; it signs in as a machine
    `sync` staff account and writes exactly `/bookings/<id>/pms` and
    `/stays/<date>/<villa>`, nothing else.
  - `nala-invites` Worker — the SMS sender (§3), dashboard-managed,
    hand-pasted.
  - `nala-push` Worker — web-push sender (holds the VAPID signing key),
    dashboard-only, **not in this repo at all**. The site talks to it at
    `PUSH_URL = 'https://nala-push.ben-681.workers.dev'`.
- **Cache busting is manual and load-bearing**: shared files are referenced
  as `nala-shared.js?v=46`, `auth.js?v=12`, `nala-ui.css?v=17`,
  `nala-ui2.css?v=6` across 14 pages, hand-bumped. See §7 — this is the
  repo's #1 named gotcha.
- The service worker (`sw.js`) is push-only and **deliberately does no
  caching** (see §7).

---

## 5. Access control

- **Staff pages**: every staff page loads `auth.js`, which paints an instant
  full-screen cream overlay, then either removes it (session exists) or shows
  a **6-digit passcode pad**. The passcode IS the credential: the Firebase
  account is `<code>@staff.nala` with the same six digits as the password
  ("Six because Firebase rejects passwords under six characters"). The sixth
  keypress submits — there's no button. 5 failed attempts locks the pad for
  60s. An **email+password form** hides behind a 600ms long-press on the
  N A L A wordmark — the only way in for an address that can receive a
  password reset.
- **Roles come from the database, never the email address**: the record at
  `/staff/<emailkey>` holds `{name, role}`. Roles: `admin`, `manager`,
  `chef`, `waiter`, `housekeeping`, `spa`, `sync` (a machine account with an
  empty grant list), plus legacy `staff` normalised to `admin`. Capabilities
  are the 8 keys in `ROLE_GRANTS` (§6.4); pages ask `can(role, 'cleansBoard')`
  etc., and a `/permissions/<action>/<role>` boolean matrix (editable from
  Settings by admins) overrides the shipped defaults for `chef`, `waiter`,
  `housekeeping` only.
- **How different users see different things**:
  1. The hamburger menu is filtered per role (`navFilterShared`), but an
     *unlisted* link is left visible on purpose — hiding-by-default made new
     pages invisible until someone remembered a second file.
  2. Each page gates itself after `loadStaff()`: no capability → the boards
     are hidden and either a "no access, see the manager" message shows, or
     the login is **redirected to its own home board** (`homeFor(role)` —
     housekeeping lands on `cleaners.html`, spa on `spa.html`, everyone else
     `tally.html`), because a first screen that is a refusal is a routing
     problem, not an access one.
  3. Within a page, capabilities toggle body classes rather than disabling
     buttons — e.g. `document.body.classList.toggle('marks-limited',
     !can(role,'cleansMarks'))` and CSS hides the buttons those marks own.
     Hidden, not disabled: "this is about not pressing something by
     accident, so the button simply is not there."
  4. The rules enforce all of it again server-side (§2.5) — the UI filter is
     courtesy, the rules are the fence. The `spa` role is additionally
     narrowed at the *read* level in the rules, "because hiding a link is
     not the same as refusing the data."
- **Guest pages** (`index.html`, `prearrival.html`, `welcome.html`) load no
  staff code and have **no login**: capability-URL access. The SMS link token
  `?t=` resolves via the public-per-child `/links/<token>` node to a booking
  id, and the booking id is the secret. The rules let a guest read/write only
  the exact nodes those pages need (`/bookings/<id>/prearrival` write,
  `/dinner` cell first-write, `/menu` read…).

---

## 6. Conventions

### 6.1 File and folder structure

Everything at the repo root — pages, shared assets, and the documentation
set. Only three directories:

```
/                     ~25 .html pages, nala-shared.js, nala-ui.css, nala-ui2.css,
                      auth.js, sw.js, manifest.json, CNAME, menu.json (dead),
                      images, and a dozen *.md docs (CLAUDE.md, HANDOVER.md,
                      STYLEGUIDE.md, DESIGN.md, ROLES.md, SECURITY.md, SETUP.md,
                      TESTING.md, per-role MANUAL-*.md, feature briefs)
/tests                run.py (parallel runner with a COVERS map), one
                      *_suite.py per page (Python + Playwright against a
                      stubbed Firebase), *_test.js (node), and the shared
                      canon tables: nav_canon.json, phone_cases.json,
                      form_questions.json, onenight_cases.json, slots.json
/tools                publish.sh, push.py, rm.py, make-demo.py, width-check.py
/worker               mews-sync.js, send-invites.js, wrangler.jsonc, test stubs
```

`mock-*.html` files are static design mockups (the rule: mock at 390pt,
check 360, don't break at 320, before building anything visual);
`demo-*.html` are generated demo sheets.

### 6.2 Single-file pages, shared core

Each page is **self-contained**: its own `<style>` in the head, its own
inline `<script>` at the foot, plus exactly four shared files (auth, shared
JS, one or two shared CSS). No modules, no imports — `nala-shared.js` is
plain globals ("same names the pages already use, so page code reads
unchanged"). JS is deliberately ES5-flavoured in the site (var, function,
string concat, no arrow functions or template literals); the Workers use
modern JS (const, async/await, template-free). No JS framework, no CSS
framework — everything hand-rolled.

### 6.3 Shared variables / palette / font stack

`nala-ui.css`:

```css
:root {
  --cream:#F9F7F4; --ink:#1C1C1A; --mid:#999990; --rule:#E0E0DA; --red:#A8321E;
  --terra:#9E6455; --terra-b:rgba(184,106,90,.45); --terra-t:rgba(184,106,90,.16);
  --save-bg:#E4EDE2; --save-bdr:#7E937A; --save-ink:#5E7D67;
  /* Staff tools use the Apple system font: it is what every other app on the
     phone uses, its figures line up, and it is built for small sizes. */
  --ui-font:-apple-system, BlinkMacSystemFont, system-ui, 'Segoe UI', Roboto,
            Helvetica, Arial, sans-serif;
  --num-font:var(--ui-font);
}

/* Double tap to zoom is a hazard on a board of tap targets ... This turns
   that gesture off while LEAVING pinch zoom alone. The old user-scalable=no
   meta does not do this; iOS ignores it on purpose. */
body.tier-app, body.tier-print { touch-action:manipulation; }
```

`nala-ui2.css` is a second, opt-in dress (a page joins by adding `ui2` to its
body class) — explicitly a **migration seam, not a permanent second
stylesheet** — and it carries the colour law as named tokens:

```css
:root{
  --law-green:#5E7D67;  --law-green-t:rgba(122,160,130,.26);
  --law-green-b:rgba(122,160,130,.65);
  --law-terra:#9E6455;  --law-terra-t:rgba(184,106,90,.16);
  --law-terra-b:rgba(184,106,90,.45);
  --law-amber:#F6EAD5;  --law-amber-b:#C29A55;  --law-amber-ink:#8A6A2F;
  --law-red:#A8321E;
  --law-wait:rgba(28,28,26,.045);
  --law-save-bg:#E4EDE2; --law-save-bdr:#7E937A; --law-save-ink:#5E7D67;
}
```

For a new app: start with ONE stylesheet and these tokens; don't inherit the
two-dress situation, it exists only because 13 live pages couldn't be
restyled in one publish.

### 6.4 Shared helpers worth lifting (all in `nala-shared.js`)

- **`saveFeedback(btn, write, opts)`** + `pressedButton()` — the button
  state machine every write goes through: disables the button, shows
  `Saving`, lands on green `Saved`, restores + reports on failure, swallows
  the second tap. A document-level capture listener remembers the last
  pressed button so call sites don't thread references:
  ```js
  var SAVE_PRESSED = null;
  function pressedButton(){ return SAVE_PRESSED; }
  document.addEventListener('click', function(e){
    var t = e.target;
    SAVE_PRESSED = (t && t.closest) ? t.closest('button') : null;
  }, true);

  function saveFeedback(btn, write, opts){
    opts = opts || {};
    if (btn){
      if (btn.__saving) return Promise.resolve(null);    /* the second tap */
      if (btn.__rest === undefined) btn.__rest = btn.innerHTML;
      btn.__saving = true;
      btn.disabled = true;
      btn.classList.remove('saved');
      btn.classList.add('saving');
      btn.textContent = opts.busy || 'Saving';
    }
    saveFailSay(opts.fail, '');
    return Promise.resolve().then(write).then(function(v){
      if (btn){
        btn.__saving = false;
        btn.classList.remove('saving');
        btn.classList.add('saved');
        btn.textContent = opts.done || 'Saved';
      }
      if (opts.then){
        if (opts.hold && btn) setTimeout(function(){ opts.then(v); }, opts.hold);
        else opts.then(v);
      }
      return v;
    }, function(e){
      if (btn){
        btn.__saving = false;
        btn.classList.remove('saving');
        btn.classList.remove('saved');
        btn.disabled = false;
        btn.innerHTML = btn.__rest;
      }
      saveFailSay(opts.fail, saveFailWords(e));
      return null;
    });
  }
  ```
- **`normalisePhone(raw)`** — E.164 or `null`, never a guess:
  ```js
  function normalisePhone(raw){
    var s = String(raw == null ? '' : raw).replace(/[\s().\-]/g, '');
    if (/^0011[1-9]\d/.test(s))    s = '+' + s.slice(4);
    else if (/^00[1-9]\d/.test(s)) s = '+' + s.slice(2);
    if (/^04\d{8}$/.test(s))    return '+61' + s.slice(1);   /* the common case */
    if (/^614\d{8}$/.test(s))   return '+' + s;              /* plus went missing */
    if (/^\+61\d+$/.test(s))    return /^\+614\d{8}$/.test(s) ? s : null;
    if (/^\+[1-9]\d{7,14}$/.test(s)) return s;
    return null;                                             /* not sent, ever  */
  }
  ```
  plus `phoneConfidence` (is it recognisably a mobile) and `phoneBadgeHTML`.
- **Dates**: `dkey(d)` → `YYYY-MM-DD` local; `parseISO` (trims fractional
  seconds to 3 digits because Safari rejects Python's 6); `parseDepDate`
  (builds a LOCAL date from ISO, "never via the UTC parser"); `dateLabel`
  ("Wd Dth Mon" — the one date format, per STYLEGUIDE); `initDateNav()`
  (wires the ‹ › Today header row, returns `{VIEW, todayKey, isToday}`,
  reads `?date=` for browsing history).
- **Nav**: the `NAV` array + `buildNav()` + `navFilterShared(role)` +
  `NAV_NEEDS` derived from it. Adding a page = one entry here + the same
  line in `tests/nav_canon.json`:
  ```js
  var NAV = [
    { href:'front-desk.html',   label:'Front Desk',   need:'editBookings' },
    { href:'tally.html',        label:'Reservations', need:'resBoard'     },
    { href:'cleaners.html',     label:'Cleans',       need:'cleansBoard'  },
    { href:'spa.html',          label:'Spa',          need:'spaBoard'     },
    { href:'publish.html',      label:'Publish Menu', need:'publishMenu'  },
    { group:'Print', items:[ /* list.html, housekeeping.html, ... */ ] },
    { group:'SMS',   items:[ /* invitations.html, arrivals-sms.html */ ] },
    { group:'Settings', items:[ /* staff.html, tag.html, flags.html, pages.html,
                                   {action:'navNotify', label:'Notifications'} */ ] }
  ];
  ```
  Each page omits its own link; watch the permission keys — they are
  `resSheet` and `cleansBoard`, "not the `resBoard`/`cleanBoard` you would
  guess".
- **Roles**: `ROLE_GRANTS`, `can(role, what)`, `emailKey`, `loadStaff(cb)`,
  `homeFor(role)`:
  ```js
  var ROLE_GRANTS = {
    admin:        ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','manageStaff','spaBoard'],
    manager:      ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','spaBoard'],
    chef:         ['resBoard','resSheet','publishMenu'],
    waiter:       ['cleansBoard','resBoard','editBookings','resSheet','spaBoard'],
    housekeeping: ['cleansBoard','cleansMarks'],
    spa:          ['spaBoard'],
    sync:         []
  };
  function can(role, what){
    var r = normaliseRole(role);
    if (r === 'admin' && ROLE_GRANTS.admin.indexOf(what) > -1) return true;
    var row = PERMISSIONS && PERMISSIONS[what];
    if (row && typeof row[r] === 'boolean') return row[r];
    return grantedByDefault(r, what);
  }
  ```
- **Push**: `notifyPush(event, villa, user)` — fire-and-forget POST to the
  push Worker after a successful write; `wireNotify()` for the settings
  toggle; `pushOn/pushOff` managing `/pushsubs/<emailkey>` and the browser
  subscription (`VAPID_PUBLIC = 'REDACTED — a public key, meant to be
  public'`).
- **`formState(p, stay)`** — the three-state pattern (not
  started / incomplete / completed) computed on every read rather than
  trusted from a stamp, "which is what makes this self healing":
  ```js
  function formState(p, stay){
    if (p && p.at && guestAnswered(p) && mandatoryAnswered(p, stay))
      return 'completed';
    return guestAnswered(p) ? 'incomplete' : 'notstarted';
  }
  ```
- The standalone-PWA link interceptor (keeps a home-screen app out of
  Safari's bars by routing same-site link taps through `location.href`).

### 6.5 Naming and code style a new page should follow

- Lowercase single-word filenames (`cleaners.html`, `front-desk.html` the
  one hyphenated exception); suite named after the page in `tests/`.
- Page structure: `<body class="tier-app ui2">` → `.wrap` → `.daterow`
  header (Today ‹ date › + hamburger) → content → `.foot` bar → overlay
  `#ov` last → scripts at the foot in the order firebase-app, firebase-auth,
  `auth.js?v=`, `nala-shared.js?v=`, then the page's own script.
- The gate pattern from §1's page: wait for both firebase and the shared
  helpers (`typeof loadStaff !== 'function' → setTimeout(gate,300)`), then
  `onAuthStateChanged` → `loadStaff` → set `window.NALA_ROLE/USER/ME/KEY`,
  `IS_MANAGER = can(role,'setJob')`, toggle body capability classes, show
  the nav, `navFilter(role)`, gate or redirect.
- Comments: full sentences, explain **why**, name the date and the incident.
  No dead code kept "for later" — "Dead CSS carrying a description of the
  app is not inert" (a ruled principle).
- **Never em dashes** in text — "Hyphen in a sentence, middot for a
  separator" (an actual house rule, enforced in copy).
- One solid primary button per surface; destructive = terracotta outline +
  confirm; state-gated options are absent, not disabled.
- Every fact one file owns: if a test needs the same list a page draws,
  extract a JSON table both read (the `nav_canon.json` / `phone_cases.json`
  pattern). "A suite with its own copy can pass while the app is wrong."
- Prove a test can fail: "break the thing it tests and watch that test go
  red" before trusting a green tick.
- Replies that end a piece of work close with the publish-status block
  (Published / Firebase rules change / Human requirements / Ready to
  publish) — see `CLAUDE.md`.

---

## 7. Gotchas — what actually bit, be warned

1. **The `?v=` cache-buster is the whole caching story, and it's manual.**
   `nala-shared.js` and `auth.js` are cached by that query string and nothing
   else. It went unbumped through four changes; browsers ran old copies and
   "correct published fixes never reached the phone reporting them: the owner
   spent days retesting against old code." If a fix seems not to have landed,
   look here first. A missed bump serves stale JS to a waiter mid-service.
   Fix queued but not done: one number rewritten by a pre-publish script.
2. **Do NOT let a service worker cache.** `sw.js` handles push and "NOTHING
   ELSE. There is deliberately no fetch handler and no caching: a service
   worker that caches would serve stale pages after a publish, and 'clear
   your browser data' would become a permanent instruction."
3. **Safari date parsing.** Safari only accepts 3 fractional digits in an ISO
   timestamp; Python writes 6 → `parseISO` trims. And parse date-only strings
   into LOCAL dates by hand (`parseDepDate`), never via `new Date('YYYY-MM-DD')`,
   which is UTC and shifts a day in +10.
4. **Firebase Auth can hang on sign-in with multiple tabs open.** LOCAL
   persistence is IndexedDB; another tab can hold the lock and
   `signInWithEmailAndPassword` never settles — no error, just silence.
   Symptom: "works first time, then fails, then works in a different
   browser." The owner had eight tabs open. Fix in `auth.js`: ask for LOCAL
   with a 2.5s cap, fall back to SESSION, and put a 15s timeout on the
   sign-in with a message that names the real cause ("Close any other tabs
   on this site").
5. **RTDB deletes keys written as `null`** — good for undo, but it silently
   ate a `pmsUpdated: null` stamp, which read back `undefined`, failed a
   `!== null` comparison, and discarded a staff decision
   (the `vacantIsStale` bug, still listed as parked).
6. **"Permission denied" usually isn't a login problem.** RTDB validates
   every field it knows and refuses the WHOLE write when one fails, with the
   same message as an auth refusal. Cost an evening staring at logins that
   were fine.
7. **A failed read is not an empty one.** A cleanup tool once counted 0
   records for 4 nodes it *couldn't read*, reported success, and deleted
   nothing. Never let a refused read and an empty node take the same branch.
8. **`emailKey` must replace EVERY dot** (global regex). A single-replace
   keyed `staff@nalaresort.com.au` as `staff@nalaresort,com.au` and matched
   nothing. (RTDB *rules'* `replace()` replaces all occurrences, unlike JS.)
9. **ClickSend specifics**: the sending domain must be registered at
   `dashboard.clicksend.com/sms/website-registration` or "a message carrying
   the link will not send at all" — it "fails on the first real send and
   looks like a bug in the page". `status === "SUCCESS"` per message, not
   HTTP 200, is the success test. "Sent" ≠ delivered: receipts need a
   delivery report rule with action **POLL** configured, and arrive late.
   Refuse URLs in operator-typed message bodies; add the link server-side
   (also an Australian-sender-ID/compliance concern — the resort's name is
   in every template).
10. **iOS web push only works for a site added to the Home Screen**; in a tab
    the browser reports no support — so say why instead of failing silently.
    Every iOS push must show *something* or the phone buzzes over nothing.
    iOS shows the notification title bold and appends "from <app>" itself —
    don't title every banner with the app's name or the actual fact becomes
    small print (`sw.js` promotes the body to the title when that happens).
11. **Mobile layout**: choose grid columns by orientation + height, not width
    (a 320pt phone loses a column to body padding; a sideways Galaxy runs out
    of height, not width). `height:100dvh` with `flex:1 1 auto; min-height:0`
    on the wrap, or the page scrolls instead of the grid. `touch-action:
    manipulation` to kill double-tap zoom without killing pinch.
    `env(safe-area-inset-top)` in body padding.
12. **`Infinity` as a sort sentinel breaks comparators**: two Infinities
    subtract to `NaN` and "NaN silently breaks the whole comparator" — use
    99.
13. **GitHub Pages quirks**: a build can wedge at "building, duration 0" —
    the fix is any fresh push (`.build-nudge` exists for exactly this).
    `raw.githubusercontent.com` caches ~5 minutes, so verifying a deploy
    needs a cache-buster.
14. **The repo is public** — nothing secret goes in it, ever. Worker
    credentials live in the Cloudflare dashboard; the one number the site
    needs (manager's mobile) lives in the *database*, not the repo. "Tokens
    pasted into a chat are burned" — say so and rotate.
15. **Wrangler `name` mismatch fails silently**: a different `name` in
    `wrangler.jsonc` than the dashboard Worker "quietly creates a SECOND
    Worker on a different subdomain, leaves the live one untouched and
    stale ... while every deploy appears to succeed."
16. **Optimistic-update + clear-the-error-line interaction**: `saveFeedback`
    calls the fail handler once with an empty message to clear the previous
    error; a fail handler that treats "" as a refusal rolls back every
    successful save on screen (this happened — the guard is in §1.6's
    `setField`).

---

## 8. Reusability verdict

- **Tile grid — lift as-is.** The CSS is small, token-based, and already
  solves the hard problems (fixed column counts by orientation, no-scroll
  height sharing, shrink-order under pressure, the legend-in-the-spare-cell
  trick). For pots: `rn` becomes the pot name, the chip bar becomes the
  pot's state bar, `sub` becomes the balance line. Keep tiles as `<button>`s
  and keep the corner-marks-last markup order. You'll re-tune the column
  counts for your pot count (the 3/6-column rules assume 17+1 cells).
- **Tile press / options interaction — lift as-is.** `openSheet`/`drawSheet`
  /`closeSheet`, the `.ov`/`.sheet` CSS, the `.pbtn` set, and the law behind
  them (one solid primary, warn-outline + confirm for destructive,
  straight-through writes for one-tap-reversible, state-gated options that
  are absent rather than disabled). Also take `saveFeedback` + `setField`'s
  optimistic-write-with-rollback wholesale — it's the best-debugged code in
  the repo (read the long comment in `cleaners.html` about the empty fail
  message before touching it).
- **Firebase wiring — lift with modification.** The pattern (RTDB REST +
  fetch shim in `auth.js` + polling, no DB SDK) transfers cleanly and is
  much less code than the SDK. You need: your own Firebase project + config,
  your own `rules.json` written from scratch **in the same style** (per-node
  role checks, `$other:{".validate":false}`, validate lengths/enums on every
  field — do NOT copy this app's rules, and do not replicate its permissive
  `$other` catch-all), and a decision on the polling interval. Budget data is
  money: consider whether last-write-wins PATCH is enough or whether you need
  transactions — RTDB REST has no transactions; the SDK's `runTransaction`
  or a Worker-mediated write would be the upgrade path if two people can
  edit one pot simultaneously.
- **ClickSend integration — lift with modification.** The Worker is the part
  to keep: token verification via `accounts:lookup`, role check against the
  DB, server-side re-read of recipient data, URL-refusal in operator text,
  per-recipient result map, a send record written win-or-lose, and the
  delivery-receipt poll. It's coupled to this app's nodes (`/stays`,
  `/phonefix`, `/invites`, menu backstop), so you'll rewrite the middle
  ("which recipients, which link") and keep the skeleton, `clickSend()`,
  `normalisePhone` + its shared test table, and the secrets discipline
  unchanged. A budgeting app may not need SMS at all — if it does (alerts?),
  this is the shape.
- **Deployment setup — rebuild, simpler.** GitHub Pages + CNAME + no build
  step: keep that, it's ideal for this class of app. But `publish.sh`/
  `push.py` (API-committing with a hard reset, token at a fixed path) exists
  because the original dev environment was a network-restricted sandbox that
  couldn't `git push`. For a new repo, plain `git push` (Pages auto-deploys)
  is strictly better. Adopt a *versioned* asset scheme from day one (one
  `?v=` constant injected by a tiny pre-publish script) instead of
  inheriting 14 hand-bumped copies. Keep the no-staging discipline honest:
  if there's no staging, never push unasked.

---

## Things you'll need that weren't asked for

1. **The test culture is half the value.** Python+Playwright suites per page
   run against a *stubbed* Firebase via `tests/run.py` (parallel, `--changed`
   mode, a COVERS map; the full run takes ~15 min and is for pre-publish
   only). Shared JSON "canon" tables (`nav_canon.json`, `phone_cases.json`)
   are how forced duplicates stay honest. Two cautions that transfer: a green
   stubbed suite proves nothing about real sign-in/push/printing (device
   test those), and one Playwright route can accidentally answer two sources
   (`**/menu.json*` matched both the DB URL and a committed file, untesting
   every fallback path).
2. **The colour law and button law** (`CLAUDE.md`, `STYLEGUIDE.md`) are
   rulings, not taste: one meaning per colour everywhere; red = failure
   only; selection never wears red; one solid primary per surface;
   destructive = terracotta outline + confirm. Suites assert the
   Reservations tile colours **by computed colour, not class name**, so a
   drive-by restyle fails by name. Decide the budget app's equivalents
   before the first screen, write them in its CLAUDE.md.
3. **The three-state form pattern** (`formState`, §6.4) — states are
   computed from the data on every read, never trusted from a stamp; editing
   never changes state; exactly one gated control moves it; the walk-back is
   the same control in terracotta with a confirm. Directly applicable to
   anything like "budget month closed / reconciling / open".
4. **PWA bits**: `manifest.json` + apple-touch meta on every page; the
   standalone-mode link interceptor in `nala-shared.js` (without it every
   tap hands the home-screen app back to Safari); `touch-action:
   manipulation`.
5. **The multi-writer discipline**: one dinner cell, first writer sets it,
   `by`/`at` on every record, staff-over-guest precedence, and
   "two readings of one state is how [two boards] came to disagree" — one
   function owns each derivation. For money data this matters double.
6. **Day-partitioned state needs an explicit carry-forward** (§2.6) — the
   `carried` stamp pattern, and "browsing a past day must read it, never
   rewrite it" (`isToday()` guards every write and every live-clock urgency
   colour).
7. **Docs that made the system maintainable**: `CLAUDE.md` (how features get
   added; the 28-mechanical-edits story), `HANDOVER.md` (the only doc a new
   session must read), `SECURITY.md` (rotation list — pasted tokens are
   burned), `ROLES.md` (code wins over the doc when they disagree). Start
   the budget app with the first two on day one.
8. **Known live constraints** if you touch this system: rules changes need a
   hand-paste into the Firebase console; the `nala-push` Worker's source
   exists only in the Cloudflare dashboard; `menu.json` at the root is dead
   weight kept for deletion; and the known-failing tests are listed at the
   bottom of `HANDOVER.md` — anything else failing is yours.
