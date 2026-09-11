/* The card-issuing runtime, shared. Front Desk and Keys both offer the
   same duty - queue a villa's cards, watch the helper write them, obey
   the queue law - and two copies of that flow is how boards learn to
   disagree (CLAUDE.md rule 1). Moved here from front-desk.html, 9 Sep,
   the night Keys gained its Issue button; front-desk's suite held the
   behaviour still while it moved.

   A page calls NalaCards.init(cfg) once, with:
     db        the database URL
     err       its error line
     dayKey()  the date its queue lives under
     rows()    the villas it may issue to: [{ villa, name, stay }]
     bulkRows() the subset its bulk row queues
     bulkLabel, emptyLabel, menuHint   its drop's three wordings
     btn, drop  the elements the drop hangs from
   The page's sheet reads NalaCards.jobFor; its loaders call .load();
   date changes call .clear(). Everything else lives in here. */
(function(){
var cfg = null;

function esc(s){
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
}
function day(){ return cfg.dayKey(); }
function nfetch(path){
  return fetch(cfg.db + path + '.json?v=' + Date.now())
    .then(function(r){ if (!r.ok) throw new Error(r.status); return r.json(); });
}
function rowOf(villa){
  return cfg.rows().filter(function(r){ return String(r.villa) === String(villa); })[0] || null;
}

/* ── key cards ─────────────────────────────────────────────────────
   The queue is /cardjobs/<date>/<villa> and the helper on the desk PC is
   the only thing that moves a job forward; this page queues, cancels and
   watches. Where a villa stands is always cardCell's answer - one reader,
   both boards, tests/card_cases.json - and the overlay below is a viewport
   onto the queue, deliberately not a controller: closing it changes
   nothing, because the cards are being written by a machine that cannot
   see this screen. */
var CARDS = {};          /* /cardjobs for the viewed date */
var CARD_TIMER = null;   /* the poll, alive only while the overlay is open */
var CARD_VILLA = null;   /* one villa's panel, or null for the day's run */
var CARD_ASK = null;     /* villa whose done record the desk wants to re-open:
                            the qty question shows again, and nothing is
                            written until Issue is pressed - a lost card must
                            not cost the record just for asking (9 Sep) */

function loadCards(){
  return nfetch('/cardjobs/' + day())
    .then(function(j){ CARDS = j || {}; cardsSweep(); cardsPaint(); })
    .catch(function(){});
}

/* A queue must never lie in wait. Ruled by the owner, 8 Sep: cards are
   written with a person standing at the encoder, seconds after the press.
   A queued job nobody claimed is an attempt that failed, so it is deleted
   rather than left to make the encoder demand cards at some later moment
   with nobody at the desk. The run screen gives its verdict at ten
   seconds; this sweep is the belt and braces at two minutes, for a queue
   left behind by a closed overlay or a dropped connection. */
var CARD_OFFLINE_MS = 10000, CARD_STALE_MS = 2 * 60 * 1000;
var CARD_DEAD_MS = 3 * 60 * 1000;   /* a write untouched this long is a dead PC */
var CARD_FAIL_HOLD_MS = 10 * 60 * 1000;  /* how long a failure stays a failure */
var CARD_OFFLINE = false;   /* the run screen's verdict, until reopened */

/* A queue behind a working encoder is never stale - learned from the mock,
   8 Sep, when the verdict fired mid-batch because the receptionist was
   pacing the cards and the villas behind the live one aged past ten
   seconds. Writing counts as alive only while its stamp is fresh: the
   helper refreshes at on the claim and on every card, so a PC that died
   mid-write stops counting, gets named in red, and frees the sweep. */
function cardsAlive(){
  var now = Date.now();
  return Object.keys(CARDS).some(function(v){
    var j = CARDS[v];
    return j && j.state === 'writing' && j.at && now - j.at < CARD_DEAD_MS;
  });
}
function cardsSweep(){
  var now = Date.now(), alive = cardsAlive();
  Object.keys(CARDS).forEach(function(v){
    var j = CARDS[v];
    if (!j) return;
    if (j.state === 'writing' && j.at && now - j.at > CARD_DEAD_MS){
      j.state = 'failed'; j.note = 'the desk PC stopped mid-write';
      fetch(cfg.db + '/cardjobs/' + day() + '/' + v + '.json', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: 'failed', note: j.note })
      }).catch(function(){});
    }
    if (!alive && j.state === 'queued' && j.at && now - j.at > CARD_STALE_MS)
      cancelJob(v);
    /* A failure is a fact about a MOMENT, not about a villa (owner,
       11 Sep: "only important at the time of failure"). Red while
       somebody is standing at the encoder; once the moment is well past,
       the record folds back to the cards that exist, and the drop stops
       teaching history. cancelJob is that fold: done at written, or
       gone if nothing was. */
    if (j.state === 'failed' && j.at && now - j.at > CARD_FAIL_HOLD_MS)
      cancelJob(v);
  });
}

function jobFor(villa){ return CARDS[String(villa)] || null; }

/* Queue one villa. The expiry is the booking's own depart day at
   CARD_CHECKOUT_HOUR, built by cardExpiry; a booking whose depart Mews
   never sent cannot be carded and says so, rather than minting a card
   that never dies. */
function putJob(r, qty){
  var exp = cardExpiry(r.stay && r.stay.depart);
  if (!exp){ cfg.err('Villa ' + r.villa + ' has no departure date, so no card can be cut.'); return null; }
  var job = { qty: qty, expiry: exp, state: 'queued', written: 0,
              guest: r.name.slice(0, 80),
              by: window.NALA_ME || '', at: Date.now() };
  return fetch(cfg.db + '/cardjobs/' + day() + '/' + r.villa + '.json', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(job)
  }).then(function(res){ if (!res.ok) throw new Error(res.status);
                         CARDS[String(r.villa)] = job; });
}

/* More cards for a villa that already has some. The record GROWS - qty
   rises, written stands, the helper continues from written - because a
   re-issue that replaced the record read one extra card as the whole
   day's count (the owner, 9 Sep, live). PATCH, never PUT: written is
   the cards in the guest's hands and no button may zero it. */
function extendJob(r, more){
  var j = jobFor(r.villa);
  /* written + more, never old qty + more: qty is an ASK and an abandoned
     ask (a failed run) must not ride along - it is how a two-card villa
     came to carry a phantom third (owner, 10-11 Sep). The cards that
     exist plus the cards wanted now is the whole truth. */
  var patch = { qty: Math.min(99, (+j.written || 0) + more), state: 'queued',
                by: window.NALA_ME || '', at: Date.now() };
  return fetch(cfg.db + '/cardjobs/' + day() + '/' + r.villa + '.json', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch)
  }).then(function(res){ if (!res.ok) throw new Error(res.status);
                         Object.assign(j, patch); });
}

/* Cancelling forgets the attempt, never the cards: a job that already
   wrote some walks back to done at that count; only a job that wrote
   nothing is deleted. */
function cancelJob(villa){
  var j = jobFor(villa);
  if (j && +j.written > 0){
    var back = { state: 'done', qty: +j.written, at: Date.now() };
    return fetch(cfg.db + '/cardjobs/' + day() + '/' + villa + '.json', {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(back)
    }).then(function(){ Object.assign(j, back); cardsPaint(); });
  }
  return fetch(cfg.db + '/cardjobs/' + day() + '/' + villa + '.json',
               { method: 'DELETE' })
    .then(function(){ delete CARDS[String(villa)]; cardsPaint(); });
}

/* Encode all: a job for every arriving villa not already queued, writing
   or done. A failed one is queued again - the desk pressing the big button
   IS the retry - and a cancelled one comes back too, because pressing
   encode-all after cancelling is a change of mind, not an accident. */
function cardsEncodeAll(){
  CARD_OFFLINE = false;
  var made = [];
  cfg.bulkRows().forEach(function(r){
    var j = jobFor(r.villa);
    if (j && (j.state === 'queued' || j.state === 'writing' || j.state === 'done')) return;
    var p = putJob(r, (j && j.qty) || 2);
    if (p) made.push(p);
  });
  Promise.all(made).catch(function(){
    cfg.err('Some card jobs did not save. This is usually the connection.');
  }).then(function(){ cardsOpen(null); });
}

/* ── the drop ── */
function cardsDrawDrop(){
  var d = cfg.drop;
  if (!cfg.rows().length){
    d.innerHTML = '<button disabled style="color:var(--mid)">' + cfg.emptyLabel + '</button>';
    return;
  }
  var h = '';
  cfg.rows().forEach(function(r){
    var cc = cardCell(jobFor(r.villa));
    h += '<button data-key="' + r.villa + '">Villa ' + r.villa +
         ' · ' + esc(r.name) +
         '<span class="kd-state card-' + cc.k + '">' +
         (cc.k === 'none' ? '' : esc(cc.label)) + '</span></button>';
  });
  h += '<button class="kd-all" data-key="all">' + esc(cfg.bulkLabel) + '' +
       '<span class="navbadge">' + cfg.bulkRows().length + '</span></button>';
  d.innerHTML = h;
}

/* ── the overlay ── */
function cardsOpen(villa){
  CARD_VILLA = villa;
  /* Picking a guest to issue to ALWAYS lands on the quantity question
     (owner, 11 Sep: it looked gated on pre-arrival; it was gated on
     whether a record existed, and a status sheet in front of the ask
     read as no choice at all). The render guard below is the one judge
     of the exception - a job the encoder is on right now shows its run,
     because asking mid-write would be a lie - so a stale cache here
     corrects itself on the next poll. */
  CARD_ASK = villa != null ? villa : null;
  CARD_OFFLINE = false;
  /* the question starts fresh: a quantity left over from another villa's
     ask is nobody's answer */
  document.getElementById('cardBody').setAttribute('data-qty', 2);
  document.getElementById('cardOv').hidden = false;
  cardRender();
  loadCards();
  if (!CARD_TIMER) CARD_TIMER = setInterval(loadCards, 1500);
}
function cardsClose(){
  document.getElementById('cardOv').hidden = true;
  if (CARD_TIMER){ clearInterval(CARD_TIMER); CARD_TIMER = null; }
  render();
}
function cardsPaint(){
  if (!document.getElementById('cardOv').hidden) cardRender();
  if (cfg.drop.classList.contains('open')) cardsDrawDrop();
}

/* One shape per card, from the same job the words come from: filled means
   written, the amber one is under the encoder now, an outline is to come,
   and a failure marks the slot it stopped on in red ink. */
function cslotsHTML(j, cc, active){
  var q = (j && +j.qty) || 0, n = Math.min((j && +j.written) || 0, q), h = '';
  /* A wiped or lost card is nobody's key any more: its slot sinks (the
     law's nothing-to-do-here) so the ticks always agree with the caption
     - both count through cardLife, found on villa 4's sheet, 10 Sep. */
  var L = j ? cardLife(j, 0) : null, gone = L ? L.back + L.lost : 0;
  for (var i = 0; i < q; i++){
    var st = i < n - gone ? 'filled'
       : i < n ? 'gone'
       : i === n && cc.k === 'writing' && active ? 'now'
       : i === n && cc.k === 'failed' ? 'fail' : '';
    h += '<i class="cslot' + (st ? ' ' + st : '') + '">' +
         (st === 'filled' || st === 'fail' ? '' : i + 1) + '</i>';
  }
  return q ? '<div class="cslots">' + h + '</div>' : '';
}

/* What the card will do, from the job's own expiry - the owner, 9 Sep,
   with TTHotel's Validity column as the reference. From is the day on
   the screen (a card lives from the moment it is written); to is read
   off the expiry stamp, hour included, so this line can never disagree
   with what the encoder was told. */
function cardValidHTML(expiry){
  if (!expiry) return '';
  var ex = new Date(expiry * 1000);
  return '<div class="crun-valid">Valid ' +
         dateLabel(parseISO(day())) + ' – ' + dateLabel(ex) +
         ', ' + String(ex.getHours()).padStart(2, '0') + ':' +
         String(ex.getMinutes()).padStart(2, '0') + '</div>';
}

/* One villa's block in the run: the state in cardCell's words, the envelope
   line the moment it lands, red only when the encoder truly failed. */
function crunHTML(r, active){
  var j = jobFor(r.villa), cc = cardCell(j);
  var cls = 'crun' + (active ? ' now' : '') +
            (cc.k === 'done' ? ' is-done' : '') +
            (cc.k === 'failed' ? ' is-failed' : '');
  /* the active writing villa asks with the drawing below, not words */
  /* The active QUEUED villa pulses while the helper claims it - about
     five seconds of silence at the desk read as "is this working?"
     (owner, 11 Sep). Movement only until a signal that cannot lie: the
     claim happens after the encoder answered, so the hand drawing IS
     "reader found", and the ten-second verdict owns the other ending.
     Other queued villas keep the owner's one word of 8 Sep. */
  var line = cc.k === 'writing' && active ? ''
      : cc.k === 'queued' && active
        ? '<span class="cwake"><i></i><i></i><i></i></span>Waking up\u2026'
      : cc.k === 'queued' ? 'Queued'
      : esc(cc.label);
  /* the whole block is a door: seeing a guest on the run and not being
     able to issue to them is the complaint of 11 Sep ("why are you
     showing Wayne and not able to issue cards to him?") */
  var h = '<div class="' + cls + '" data-cardopen="' + r.villa + '">' +
          '<div class="crun-v">Villa ' + r.villa +
          '<small>' + esc(r.name) + '</small></div>' +
          cslotsHTML(j, cc, active) +
          (cc.k === 'writing' && active ? '<div class="cardask"><svg viewBox="0 0 140 96" fill="none" ' +
      'stroke="currentColor" stroke-width="2.6" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-label="Hold a card to the reader">' +
      '<rect x="57" y="10" width="33" height="46" rx="5" transform="rotate(16 73 33)"/>' +
      '<path d="M58 50c-4 7-3 14 2 19 6 6 15 6 21 1l7-6"/>' +
      '<path d="M63 57c2-3 5-4 8-2M69 63c2-3 5-4 8-2"/>' +
      '<path class="wave w1" d="M40 30c-4 6-4 14 0 20"/>' +
      '<path class="wave w2" d="M30 24c-7 9-7 23 0 32"/>' +
      '<path class="wave w1" d="M106 30c4 6 4 14 0 20"/>' +
      '<path class="wave w2" d="M116 24c7 9 7 23 0 32"/>' +
      '</svg></div>' : '') +
          (line || (cc.k === 'failed' && j && j.note)
            ? '<div class="crun-s card-' + cc.k + '">' + line +
              (cc.k === 'failed' && j && j.note ? ' · ' + esc(String(j.note)) : '') +
              '</div>'
            : '') +
          (cc.k !== 'cancelled' ? cardValidHTML(j && j.expiry) : '');
  /* an envelope needs cards to go in it */
  if (cc.k === 'done' && (function(){ var Le = cardLife(j, 0);
      return Le && Le.active > 0; })())
    h += '<div class="crun-env">Envelope villa ' + r.villa + '’s cards</div>';
  if (cc.k === 'queued' || cc.k === 'failed')
    h += '<div class="sum-btns"><button class="terra" data-cardcancel="' +
         r.villa + '">Cancel</button></div>';
  return h + '</div>';
}

function cardRender(){
  var body = document.getElementById('cardBody');
  var one = CARD_VILLA != null ? rowOf(CARD_VILLA) : null;

  /* One villa: the qty question, then its live block. */
  if (one){
    document.getElementById('cardTitle').textContent =
      'Key cards · villa ' + one.villa;
    var j = jobFor(one.villa);
    /* the poll can reveal the encoder is ON this villa: the question
       yields to the run - asking for a quantity mid-write is a lie */
    if (CARD_ASK == one.villa && j &&
        (j.state === 'queued' || j.state === 'writing')) CARD_ASK = null;
    if (!j || j.state === 'cancelled' || CARD_ASK == one.villa){
      var q = +(body.getAttribute('data-qty') || 2);
      /* a living job means these are ADDED cards, and the words say so */
      var more = j && j.state !== 'cancelled' && +j.written > 0;
      body.innerHTML = '<div class="cardov-in"><div class="crun">' +
        '<div class="crun-v">Villa ' + one.villa + '<small>' +
        esc(one.name) + '</small></div>' +
        '<div class="crun-s">How many ' + (more ? 'more cards' : 'cards') + '?' +
        '<span class="cqty"><button data-cardq="-1">&minus;</button><span>' + q +
        '</span><button data-cardq="1">+</button></span></div>' +
        cardValidHTML(cardExpiry(one.stay.depart)) +
        '<div class="sum-btns"><button class="go wide" data-cardissue="' +
        one.villa + '">Issue ' + q + (more ? ' more' : q === 1 ? ' card' : ' cards') +
        '</button></div></div></div>';
      return;
    }
    /* A finished villa is not a closed one: a guest loses a card, a second
       arrives late. The button re-opens the question only - the done record
       stands until Issue actually writes a new job over it. */
    body.innerHTML = '<div class="cardov-in">' + crunHTML(one, true) +
      (cardCell(j).k === 'done' || cardCell(j).k === 'failed'
        ? '<div class="sum-btns"><button data-cardagain="' + one.villa +
          '">Issue ' + (+j.written > 0 ? 'more cards' : 'cards') +
          '</button></div>'
        : '') + '</div>';
    return;
  }

  /* The day: every villa with a job, villa order, the first unfinished one
     active. The desk PC being silent is said in amber, not left as a
     mystery: a job nobody has claimed inside ten seconds means the helper
     is not running, and that is a fact worth a sentence. */
  document.getElementById('cardTitle').textContent = 'Key cards · ' +
    dateLabel(parseISO(day()));
  /* Villa order, not the sheet's sort: the helper writes lowest villa
     first, and the run screen must agree with it about whose card is on
     the pad. Found by the slot suite, 8 Sep: the sheet sorts by ETA, so
     the highlighted villa could differ from the one being written. */
  /* The run is the day's WORK, not the day's history: a done record
     whose every card has since been wiped has nothing happening and
     nothing to hand over, so it does not stand here with ghost slots
     asking for an envelope (owner, 11 Sep). The register and the Tally
     hold what happened. */
  var withJobs = cfg.rows().filter(function(r){
    var j = jobFor(r.villa);
    if (!j) return false;
    if (j.state !== 'done') return true;
    var L = cardLife(j, 0);
    return !!(L && L.active > 0);
  }).sort(function(a, b){ return (+a.villa) - (+b.villa); });
  /* The verdict outlives the queue it deleted: once the encoder is judged
     offline the notice holds until the run is reopened, or the jobs that
     were just removed would take their explanation with them. */
  var offlineHTML = '<div class="cardhold"><b>Encoder offline.</b> ' +
    'Nothing was written \u00b7 open Nala card helper from the desk ' +
    'PC\u2019s taskbar, then try again.</div>';
  if (!withJobs.length){
    body.innerHTML = '<div class="cardov-in">' + (CARD_OFFLINE ? offlineHTML
      : '<div class="crun"><div class="crun-s">Nothing queued. ' +
        esc(cfg.menuHint) + '</div></div>') + '</div>';
    return;
  }
  /* the batch's one bar: cards written over cards wanted, cancelled jobs
     excluded because they are no longer wanted */
  var total = 0, doneCards = 0;
  withJobs.forEach(function(r){
    var j = jobFor(r.villa);
    if (j.state === 'cancelled') return;
    total += +j.qty || 0;
    doneCards += Math.min(+j.written || 0, +j.qty || 0);
  });
  /* The active villa is the one the encoder is ON, whatever its position:
     a writing job anywhere outranks the first queued one. Only when
     nothing is writing does the highlight fall to the next queued or
     failed villa, which is where the helper will go. */
  var writingNow = withJobs.filter(function(r){
    return cardCell(jobFor(r.villa)).k === 'writing';
  })[0];
  var activeSeen = false, oldestWait = 0;
  var h = total ? '<div class="cprog"><i style="width:' +
          Math.round(doneCards / total * 100) + '%"></i></div>' : '';
  withJobs.forEach(function(r){
    var j = jobFor(r.villa), cc = cardCell(j);
    var active = writingNow ? r === writingNow
      : !activeSeen && (cc.k === 'queued' || cc.k === 'failed');
    if (active) activeSeen = true;
    if (cc.k === 'queued' && j.at) oldestWait = Math.max(oldestWait, Date.now() - j.at);
    h += crunHTML(r, active);
  });
  /* Ten seconds unclaimed and the attempt has failed: delete what is still
     queued - the owner's ruling - so the encoder can never start demanding
     cards later with nobody at the desk. Villas already written or being
     written are the helper's and are left alone. */
  if (!cardsAlive() && oldestWait > CARD_OFFLINE_MS){
    CARD_OFFLINE = true;
    withJobs.forEach(function(r){
      var j = jobFor(r.villa);
      if (j && j.state === 'queued') cancelJob(r.villa);
    });
  }
  if (CARD_OFFLINE)
    h = offlineHTML + h;
  body.innerHTML = '<div class="cardov-in">' + h + '</div>';
}

/* the wiring: the key toggles its drop, the drop picks, the overlay acts */
function wire(){
  var b = cfg.btn, d = cfg.drop;
  b.onclick = function(e){ e.stopPropagation();
    if (!d.classList.contains('open')) cardsDrawDrop();
    d.classList.toggle('open'); };
  document.addEventListener('click', function(){ d.classList.remove('open'); });
  d.addEventListener('click', function(e){
    var t = e.target.closest('[data-key]');
    if (!t) return;
    var k = t.getAttribute('data-key');
    if (k === 'all') cardsEncodeAll(); else cardsOpen(k);
  });
  document.getElementById('cardX').onclick = cardsClose;
  document.getElementById('cardBody').addEventListener('click', function(e){
    var q = e.target.closest('[data-cardq]');
    if (q){
      var body = document.getElementById('cardBody');
      var now = +(body.getAttribute('data-qty') || 2) + (+q.getAttribute('data-cardq'));
      /* 99, not the invented 6: "if I feel like issuing 1000 cards to a
         room I can - it just goes to the tally" (owner, 11 Sep). The
         rules' own sanity bound is the only ceiling. */
      body.setAttribute('data-qty', Math.min(99, Math.max(1, now)));
      cardRender(); return;
    }
    var iss = e.target.closest('[data-cardissue]');
    if (iss){
      var r = rowOf(iss.getAttribute('data-cardissue'));
      var body2 = document.getElementById('cardBody');
      var n2 = +(body2.getAttribute('data-qty') || 2);
      /* a villa with a living job GROWS it; only a blank or cancelled
         slate gets a fresh one - the record is never replaced (9 Sep) */
      var j2 = r && jobFor(r.villa);
      var p = r && (j2 && j2.state !== 'cancelled'
                    ? extendJob(r, n2) : putJob(r, n2));
      CARD_ASK = null;
      if (p) p.then(cardRender).catch(function(){
        cfg.err('The card job did not save. This is usually the connection.');
      });
      return;
    }
    var ag = e.target.closest('[data-cardagain]');
    if (ag){
      CARD_ASK = ag.getAttribute('data-cardagain');
      document.getElementById('cardBody').setAttribute('data-qty', 2);
      cardRender(); return;
    }
    var opn = e.target.closest('[data-cardopen]');
    if (opn && CARD_VILLA == null && !e.target.closest('button')){
      cardsOpen(opn.getAttribute('data-cardopen')); return;
    }
    var c = e.target.closest('[data-cardcancel]');
    if (c){
      /* Destructive, so it confirms - the button law. Two taps on the same
         button, the Mark-as-completed pattern, rather than a dialog. */
      if (c.getAttribute('data-armed')){ cancelJob(c.getAttribute('data-cardcancel')); return; }
      c.setAttribute('data-armed', '1'); c.textContent = 'Confirm cancel';
      setTimeout(function(){ if (c.isConnected){ c.removeAttribute('data-armed');
        c.textContent = 'Cancel'; } }, 4000);
    }
  });
}

window.NalaCards = {
  init: function(c){ cfg = c; wire(); },
  load: loadCards,
  open: cardsOpen,
  jobFor: jobFor,
  clear: function(){ CARDS = {}; }
};
})();
