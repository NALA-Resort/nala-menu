/* The card-issuing runtime, shared. The Keys page owns issuing; Front
   Desk keeps exactly one shortcut - its key IS "cut all arrival keys"
   (the owner, 11 Sep) - and both go through here: one flow, two pages,
   or the boards would learn to disagree (CLAUDE.md rule 1).

   Rebuilt 11 Sep on the owner's model. The lasting record is the card
   table, /cards/<no>, one row per card in the world; THE REQUEST to cut
   is /cutrun, a short-lived thing that ends when the cutting ends and
   is never stored with the cards:

     { state: on|off|done, by, at, seen,
       queue: { <villa>: { guest, qty, cut, expiry, note? } } }

   The desk switches it on with the villas wanted. The helper on the
   desk PC heartbeats `seen`, works the queue in villa order, appends a
   ROW PER CARD to /cards as each one is cut, bumps queue/<villa>/cut,
   and sets state done when the queue is finished. Skip shrinks a
   villa's qty to its cut; Stop (or closing the run) switches state off
   and the helper stands down; ten silent seconds without a heartbeat
   is the queue law's own verdict - the run dies rather than lying in
   wait for an encoder with nobody at the desk (ruled 8 Sep).

   A page calls NalaCards.init(cfg) once, with:
     db         the database URL
     err        its error line
     rows()     the villas it may issue to: [{ villa, name, stay, arriving? }]
     bulkRows() the subset its bulk action cuts for
     bulkLabel, emptyLabel, menuHint   its drop's three wordings
     btn, drop  the elements the drop hangs from. A page with no drop
                (Front Desk) wires its own button to NalaCards.bulk().
   Loaders call .load(); date changes call .clear(). */
(function(){
var cfg = null;

function esc(s){
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
}
function nfetch(path){
  return fetch(cfg.db + path + '.json?v=' + Date.now())
    .then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); });
}
function nwrite(path, obj, method){
  return fetch(cfg.db + path + '.json', {
    method: method || 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(obj)
  }).then(function(r){ if (!r.ok) throw new Error(r.status); });
}
function rowOf(villa){
  return cfg.rows().filter(function(r){ return String(r.villa) === String(villa); })[0] || null;
}

/* the card table, for the drop's held counts and the run's seats -
   always through the shared readers, never this file's own idea */
var TABLE = [];          /* cardRows(/cards), as read */
function loadTable(){
  return nfetch('/cards')
    .then(function(j){ TABLE = cardRows(j); cardsPaint(); })
    .catch(function(){});
}
/* what the guest holds in hand: their live rows minus the lost one -
   a lost card is still out there, but it is not in anybody's hand */
function heldFor(villa){
  return cardsHeld(TABLE, villa, Date.now()).filter(function(r){
    return !r.lost; }).length;
}

/* ── the run ────────────────────────────────────────────────────────
   RUN is this page's viewport onto /cutrun while the overlay is open.
   The queue itself lives in the database; closing the overlay stops
   the run (state off), exactly as the cancel session's Stop does -
   a request that ends when the asking ends. */
var RUN = null;          /* { at } while the overlay is open */
var RUN_T = null;
var RUN_OFFLINE = false;
var CR = null;           /* /cutrun as last read */
var RUN_OFFLINE_MS = 10000;

function runStart(entries, title){
  var queue = {}, bad = [];
  entries.forEach(function(en){
    /* the ask's own till-when outranks the stay: a no-guest room and a
       cut past the stay's 1pm carry an expiry a person chose */
    var exp = en.expiry || cardExpiry(en.stay && en.stay.depart);
    if (!exp){ bad.push(en.villa); return; }
    queue[String(en.villa)] = { guest: String(en.name || '').slice(0, 80),
                                qty: en.qty, cut: 0, expiry: exp };
  });
  if (bad.length)
    cfg.err('Villa ' + bad.join(' & ') + ' has no departure date, so no card can be cut.');
  if (!Object.keys(queue).length) return;
  RUN = { at: Date.now(), title: title };
  RUN_OFFLINE = false; CR = null;
  nwrite('/cutrun', { state: 'on', by: window.NALA_ME || '', at: RUN.at,
                      queue: queue }, 'PUT')
    .catch(function(){
      cfg.err('The run did not start. This is usually the connection.');
    });
  document.getElementById('cardTitle').textContent = title;
  document.getElementById('cardOv').hidden = false;
  runRender();
  if (!RUN_T) RUN_T = setInterval(runPoll, 1000);
}
function runStop(){
  if (RUN) nwrite('/cutrun', { state: 'off' }).catch(function(){});
  if (RUN_T){ clearInterval(RUN_T); RUN_T = null; }
  RUN = null;
  document.getElementById('cardOv').hidden = true;
  loadTable();     /* cut cards changed every count */
  if (typeof render === 'function') render();
}
function runPoll(){
  if (!RUN) return;
  Promise.all([nfetch('/cutrun'), loadTable()]).then(function(res){
    if (!RUN) return;
    CR = res[0];
    /* nobody listening: the verdict, and the switch back off */
    if (CR && CR.state === 'on' && !RUN_OFFLINE &&
        (!CR.seen || CR.seen < RUN.at) && Date.now() - RUN.at > RUN_OFFLINE_MS){
      RUN_OFFLINE = true;
      nwrite('/cutrun', { state: 'off' }).catch(function(){});
    }
    runRender();
  }).catch(function(){});
}

/* One shape per card: the guest's cards in hand stand filled, the ones
   still to cut are numbered CONTINUING after them - a tick then "2",
   never a tick then "1", which called the villa's second card its
   first (the owner's bug report, 12 Sep). The amber one is under the
   encoder now. Never the lifetime ledger - the wiped past is the
   register's story (owner, 11 Sep). */
function cslotsHTML(villa, q, active, writing){
  var held = heldFor(villa);
  var todo = Math.max(0, (+q.qty || 0) - (+q.cut || 0));
  var h = '';
  for (var i = 0; i < held; i++) h += '<i class="cslot filled"></i>';
  for (var j = 0; j < todo; j++){
    var now = active && writing && j === 0;
    h += '<i class="cslot' + (now ? ' now' : '') + '">' + (held + j + 1) + '</i>';
  }
  return (held + todo) ? '<div class="cslots">' + h + '</div>' : '';
}

/* What the card will do, from the queue's own expiry - the owner,
   9 Sep, with TTHotel's Validity column as the reference. */
function cardValidHTML(expiry){
  if (!expiry) return '';
  var ex = new Date(expiry * 1000);
  return '<div class="crun-valid">Valid ' +
         dateLabel(new Date()) + ' – ' + dateLabel(ex) +
         ', ' + String(ex.getHours()).padStart(2, '0') + ':' +
         String(ex.getMinutes()).padStart(2, '0') + '</div>';
}

var CARD_ASK_SVG = '<div class="cardask"><svg viewBox="0 0 140 96" fill="none" ' +
  'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" ' +
  'stroke-linejoin="round" aria-label="Hold a card to the reader">' +
  '<rect x="57" y="10" width="33" height="46" rx="5" transform="rotate(16 73 33)"/>' +
  '<path d="M58 50c-4 7-3 14 2 19 6 6 15 6 21 1l7-6"/>' +
  '<path d="M63 57c2-3 5-4 8-2M69 63c2-3 5-4 8-2"/>' +
  '<path class="wave w1" d="M40 30c-4 6-4 14 0 20"/>' +
  '<path class="wave w2" d="M30 24c-7 9-7 23 0 32"/>' +
  '<path class="wave w1" d="M106 30c4 6 4 14 0 20"/>' +
  '<path class="wave w2" d="M116 24c7 9 7 23 0 32"/>' +
  '</svg></div>';

function queuePairs(){
  var q = (CR && CR.queue) || {};
  return Object.keys(q).sort(function(a, b){ return (+a) - (+b); })
    .map(function(v){ return { villa: v, q: q[v] }; });
}

function runRender(){
  if (!RUN) return;
  var body = document.getElementById('cardBody');
  if (RUN_OFFLINE){
    body.innerHTML = '<div class="cardov-in">' +
      '<div class="cardhold"><b>Encoder offline.</b> Nothing was written ' +
      '· open Nala card helper from the desk PC’s taskbar, then ' +
      'try again.</div></div>';
    return;
  }
  var pairs = queuePairs();
  if (!pairs.length){
    body.innerHTML = '<div class="cardov-in"><div class="crun">' +
      '<div class="crun-s">Waking up…</div></div></div>';
    return;
  }
  var awake = CR && CR.seen && CR.seen >= RUN.at;
  var over = CR && CR.state !== 'on';
  /* the active villa is the first unfinished, unfailed one - the
     helper's own order, so the highlight and the encoder agree about
     whose card is on the pad */
  var activeVilla = null;
  pairs.forEach(function(p){
    if (activeVilla || p.q.note) return;
    if ((+p.q.cut || 0) < (+p.q.qty || 0)) activeVilla = p.villa;
  });
  var total = 0, cut = 0;
  pairs.forEach(function(p){ total += +p.q.qty || 0; cut += Math.min(+p.q.cut || 0, +p.q.qty || 0); });
  var h = total ? '<div class="cprog"><i style="width:' +
          Math.round(cut / total * 100) + '%"></i></div>' : '';
  if (over || !activeVilla)
    h += '<div class="crun"><div class="crun-s card-done">' +
         cut + (cut === 1 ? ' card cut' : ' cards cut') +
         ' · envelope and hand over</div></div>';
  pairs.forEach(function(p){
    var q = p.q, r = rowOf(p.villa);
    var name = q.guest || (r && r.name) || '';
    var done = (+q.cut || 0) >= (+q.qty || 0);
    var active = !over && p.villa === activeVilla;
    var writing = active && awake;
    var cls = 'crun' + (active ? ' now' : '') + (done ? ' is-done' : '') +
              (q.note ? ' is-failed' : '');
    h += '<div class="' + cls + '">' +
      '<div class="crun-v">Villa ' + esc(p.villa) +
      '<small>' + esc(name) + '</small></div>' +
      (writing ? CARD_ASK_SVG +
        '<div class="crun-s">Hold a card to the reader</div>' : '') +
      cslotsHTML(p.villa, q, active, writing) +
      (active && !awake
        ? '<div class="crun-s"><span class="cwake"><i></i><i></i><i></i></span>Waking up…</div>'
        : '') +
      (q.note ? '<div class="crun-s card-failed">write failed · ' +
                esc(String(q.note)) + '</div>' : '') +
      (done && heldFor(p.villa) > 0
        ? '<div class="crun-env">Envelope villa ' + esc(p.villa) + '’s cards</div>' : '') +
      cardValidHTML(q.expiry) +
      (writing
        ? '<div class="sum-btns"><button class="terra" data-cardskip="' +
          esc(p.villa) + '">Skip this card</button></div>'
        : '') +
      '</div>';
  });
  if (over || !activeVilla)
    h += '<div class="sum-btns" style="margin-top:16px">' +
         '<button class="go wide" id="runDone">Done</button></div>';
  body.innerHTML = '<div class="cardov-in">' + h + '</div>';
}

/* Skip this card: the villa closes at the cards already cut. The ask
   shrinks to the cut count and the helper's own poll moves it on -
   never a delete, because the cards that exist are rows already. */
function runSkip(villa){
  var q = (CR && CR.queue && CR.queue[villa]) || null;
  if (!q) return;
  nwrite('/cutrun/queue/' + villa, { qty: +q.cut || 0 }).catch(function(){});
  q.qty = +q.cut || 0;
  runRender();
}

/* ── the ask ────────────────────────────────────────────────────────────────
   Picking a guest ALWAYS lands on the quantity question (owner,
   11 Sep); issuing more later is simply another run - the rows the
   guest already holds stand as filled seats, nothing continues from a
   written count.

   When the expiry is NOT a settled fact - a room with no guest, or a
   cut after the stay's own 1pm has passed - the sheet also asks till
   when, as a date and a time (the owner, 11 Sep: ask, never assume),
   defaulting to the next 1pm. And a villa can be reached by NUMBER,
   the drop's own last row before the batch action: the pad covers the
   rooms no guest map lists (the owner, 11 Sep). */
var ASK = null;   /* { villa, name, stay, vacant } while the sheet is open */

function next1pm(){
  var d = new Date();
  if (d.getHours() >= CARD_CHECKOUT_HOUR) d.setDate(d.getDate() + 1);
  return { date: dkey(d),
           time: String(CARD_CHECKOUT_HOUR).padStart(2, '0') + ':00' };
}
function askOpen(villa){
  RUN = null;
  if (villa == null){
    ASK = null;   /* the pad asks first */
  } else {
    var r = rowOf(villa);
    ASK = r ? { villa: String(r.villa), name: r.name, stay: r.stay }
            : { villa: String(villa), name: 'No guest', vacant: true };
  }
  document.getElementById('cardTitle').textContent =
    ASK ? 'Key cards · villa ' + ASK.villa : 'Key cards';
  document.getElementById('cardBody').setAttribute('data-qty', 2);
  document.getElementById('cardOv').hidden = false;
  askRender();
}
/* settled: the stay's 1pm, still ahead. Anything else is a question. */
function askNeedsWhen(){
  if (!ASK || ASK.vacant) return true;
  var exp = cardExpiry(ASK.stay && ASK.stay.depart);
  return !exp || exp * 1000 <= Date.now();
}
function askExpiry(){
  if (!askNeedsWhen()) return cardExpiry(ASK.stay && ASK.stay.depart);
  var d = document.getElementById('askDate');
  var t = document.getElementById('askTime');
  if (!d || !d.value) return null;
  var p = d.value.split('-'), q = ((t && t.value) || '13:00').split(':');
  var ms = new Date(+p[0], +p[1] - 1, +p[2], +q[0], +q[1] || 0).getTime();
  return isNaN(ms) ? null : Math.floor(ms / 1000);
}
function askExpiryDefault(def){
  var p = def.date.split('-'), q = def.time.split(':');
  return Math.floor(new Date(+p[0], +p[1] - 1, +p[2], +q[0], +q[1]).getTime() / 1000);
}
function askRender(){
  var body = document.getElementById('cardBody');
  if (!ASK){
    /* the number pad: seventeen villas, one tap - no list, no keyboard */
    var h = '<div class="cardov-in"><div class="crun">' +
      '<div class="crun-s" style="margin-bottom:8px">Which villa?</div>' +
      '<div class="pax-row" style="flex-wrap:wrap">';
    for (var n = 1; n <= ROOMS; n++)
      h += '<button class="pax" data-cardvilla="' + n + '">' + n + '</button>';
    body.innerHTML = h + '</div></div></div>';
    return;
  }
  var q = +(body.getAttribute('data-qty') || 2);
  var held = heldFor(ASK.villa);
  var when = askNeedsWhen(), def = next1pm();
  body.innerHTML = '<div class="cardov-in"><div class="crun">' +
    '<div class="crun-v">Villa ' + esc(ASK.villa) + '<small>' +
    esc(ASK.name) + '</small></div>' +
    '<div class="crun-s">How many ' + (held ? 'more cards' : 'cards') + '?' +
    '<span class="cqty"><button data-cardq="-1">&minus;</button><span>' + q +
    '</span><button data-cardq="1">+</button></span></div>' +
    (when
      ? '<div class="crun-s" style="margin-top:10px">Till when?</div>' +
        '<div style="display:flex;gap:8px;margin-top:6px">' +
        '<input type="date" id="askDate" value="' + def.date + '">' +
        '<input type="time" id="askTime" value="' + def.time + '"></div>' +
        '<div class="crun-s card-failed" id="askWhy" hidden></div>'
      : '') +
    '<span id="askValid">' +
    cardValidHTML(when ? askExpiryDefault(def)
                       : cardExpiry(ASK.stay && ASK.stay.depart)) +
    '</span>' +
    '<div class="sum-btns"><button class="go wide" data-cardissue="' +
    esc(ASK.villa) + '">Issue ' + q +
    (held ? ' more' : q === 1 ? ' card' : ' cards') +
    '</button></div></div></div>';
}

/* the bulk action: no quantity asked - a card per guest on the booking
   (the owner, 11 Sep), the odd villa out corrected by its own ask */
function bulk(){
  var entries = cfg.bulkRows().map(function(r){
    return { villa: r.villa, name: r.name, stay: r.stay,
             qty: Math.max(1, Math.min(99, (r.stay && +r.stay.adults) || 2)) };
  });
  if (!entries.length){ cfg.err(cfg.emptyLabel); return; }
  runStart(entries, 'Key cards · ' + cfg.bulkLabel.toLowerCase());
}

/* ── the drop ── */
function cardsDrawDrop(){
  var d = cfg.drop;
  if (!d) return;
  var h = '';
  if (!cfg.rows().length)
    h += '<button disabled style="color:var(--mid)">' + cfg.emptyLabel + '</button>';
  cfg.rows().forEach(function(r){
    var n = heldFor(r.villa);
    var state = n ? '<span class="kd-state card-done">' + n + ' held</span>'
      : r.leaving ? '<span class="kd-state">departs 1pm</span>'
      : r.arriving ? '<span class="kd-state">arriving</span>'
      : '<span class="kd-state">no cards</span>';
    h += '<button data-key="' + esc(r.villa) + '">Villa ' + esc(r.villa) +
         ' · ' + esc(r.name) + state + '</button>';
  });
  /* the door to a room no guest map lists - a number, not a list */
  h += '<button data-key="pad">Villa by number</button>';
  h += '<button class="kd-all" data-key="all">' + esc(cfg.bulkLabel) + '' +
       '<span class="navbadge">' + cfg.bulkRows().length + '</span></button>';
  d.innerHTML = h;
}
function cardsPaint(){
  if (RUN && !document.getElementById('cardOv').hidden) runRender();
  if (cfg.drop && cfg.drop.classList.contains('open')) cardsDrawDrop();
}

/* the wiring: the button toggles its drop (or is the bulk action),
   the drop picks, the overlay acts */
function wire(){
  var b = cfg.btn, d = cfg.drop;
  if (b && d){
    b.onclick = function(e){ e.stopPropagation();
      if (!d.classList.contains('open')) cardsDrawDrop();
      d.classList.toggle('open'); };
    document.addEventListener('click', function(){ d.classList.remove('open'); });
    d.addEventListener('click', function(e){
      var t = e.target.closest('[data-key]');
      if (!t) return;
      var k = t.getAttribute('data-key');
      if (k === 'all') bulk();
      else if (k === 'pad') askOpen(null);
      else askOpen(k);
    });
  } else if (b){
    b.onclick = function(e){ e.stopPropagation(); bulk(); };
  }
  document.getElementById('cardX').onclick = runStop;
  document.getElementById('cardBody').addEventListener('click', function(e){
    var pv = e.target.closest('[data-cardvilla]');
    if (pv){ askOpen(pv.getAttribute('data-cardvilla')); return; }
    var q = e.target.closest('[data-cardq]');
    if (q){
      var body = document.getElementById('cardBody');
      var now = +(body.getAttribute('data-qty') || 2) + (+q.getAttribute('data-cardq'));
      /* 99, the rules' own sanity bound and nothing tighter (11 Sep) */
      /* the till-when inputs survive the redraw: read before, restore after */
      var dEl = document.getElementById('askDate'), tEl = document.getElementById('askTime');
      var dv = dEl && dEl.value, tv = tEl && tEl.value;
      body.setAttribute('data-qty', Math.min(99, Math.max(1, now)));
      if (ASK) askRender();
      if (dv && document.getElementById('askDate')) document.getElementById('askDate').value = dv;
      if (tv && document.getElementById('askTime')) document.getElementById('askTime').value = tv;
      return;
    }
    var iss = e.target.closest('[data-cardissue]');
    if (iss && ASK){
      var n2 = +(document.getElementById('cardBody').getAttribute('data-qty') || 2);
      var exp = askExpiry();
      var why = document.getElementById('askWhy');
      if (askNeedsWhen()){
        /* asked, so answered: no date is no card, and a time already
           gone would mint a card born dead */
        if (!exp){ if (why){ why.textContent = 'Pick a day.'; why.hidden = false; } return; }
        if (exp * 1000 <= Date.now()){
          if (why){ why.textContent = 'That time has already passed.'; why.hidden = false; }
          return;
        }
      }
      runStart([{ villa: ASK.villa, name: ASK.name, stay: ASK.stay,
                  qty: n2, expiry: exp }],
               'Key cards · villa ' + ASK.villa);
      return;
    }
    var sk = e.target.closest('[data-cardskip]');
    if (sk){ runSkip(sk.getAttribute('data-cardskip')); return; }
    if (e.target.closest('#runDone')){ runStop(); return; }
  });
  /* the chosen till-when reflects in the Valid line the moment it lands */
  document.getElementById('cardBody').addEventListener('change', function(e){
    if (e.target.id !== 'askDate' && e.target.id !== 'askTime') return;
    var v = document.getElementById('askValid'), exp = askExpiry();
    if (v) v.innerHTML = exp ? cardValidHTML(exp) : '';
  });
}

window.NalaCards = {
  init: function(c){ cfg = c; wire(); },
  load: loadTable,
  bulk: bulk,
  open: askOpen,
  clear: function(){ TABLE = []; }
};
})();
