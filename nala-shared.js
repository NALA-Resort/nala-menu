/* NALA shared helpers - one copy of the logic every staff page repeats.
   Plain globals, same names the pages already use, so page code reads
   unchanged. See STYLEGUIDE.md and HANDOVER.md.                      v2 */

var DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app";
var ROOMS = 17;
var ALLERGENS = ['Nut allergy','Shellfish allergy','Egg allergy'];

/* ── dates ─────────────────────────────────────────────────── */
function dkey(d){
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}

// Safari only accepts 3 fractional digits in an ISO date; Python writes 6.
// Trim them so any timestamp parses on every browser.
function parseISO(s){
  if (!s) return null;
  var t = String(s).trim().replace(/(\.\d{3})\d+/, '$1');
  var d = new Date(t);
  if (!isNaN(d)) return d;
  d = new Date(t.replace(/\.\d+/, ''));      // drop fractions entirely
  return isNaN(d) ? null : d;
}

function parseDepDate(s){
  if(!s) return null;
  s = String(s).trim();
  var m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) return new Date(+m[3], +m[2]-1, +m[1]);
  var i = s.match(/^(\d{4})-(\d{2})-(\d{2})/);       // ISO - build a LOCAL date,
  if (i) return new Date(+i[1], +i[2]-1, +i[3]);     // never via the UTC parser
  var d = new Date(s);
  return isNaN(d) ? null : d;
}

function ord(n){
  var s=['th','st','nd','rd'], v=n%100;
  return n + (s[(v-20)%10] || s[v] || s[0]);
}

/* the one date format: Wd Dth Mon (see STYLEGUIDE.md) */
function dateLabel(d){
  var days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var mo=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return days[d.getDay()]+' '+ord(d.getDate())+' '+mo[d.getMonth()];
}

/* ── the standard header's date row ────────────────────────────
   Wires ‹ › Today and writes the one date format into #date/#title.
   Tolerates missing arrows (hc tally shows the date alone).
   Returns { VIEW, todayKey, isToday } for the page to use.        */
function initDateNav(){
  var VIEW = (function(){
    var q = new URLSearchParams(location.search).get('date');
    if (q && /^\d{4}-\d{2}-\d{2}$/.test(q)) {
      var p = q.split('-');
      return new Date(+p[0], +p[1]-1, +p[2]);
    }
    return new Date();
  })();
  function todayKey(){ return dkey(VIEW); }
  function isToday(){ return dkey(VIEW) === dkey(new Date()); }
  function shiftDate(n){
    var d = new Date(VIEW); d.setDate(d.getDate()+n);
    var q = new URLSearchParams(location.search);
    q.set('date', dkey(d));
    location.search = q.toString();
  }
  function goToday(){
    var q = new URLSearchParams(location.search);
    q.delete('date');
    location.search = q.toString();
  }
  var el = document.getElementById('date') || document.getElementById('title');
  if (el) el.textContent = dateLabel(VIEW);
  var pv = document.getElementById('dPrev'), nx = document.getElementById('dNext'),
      td = document.getElementById('dToday');
  if (pv) pv.onclick = function(){ shiftDate(-1); };
  if (nx) nx.onclick = function(){ shiftDate(1); };
  if (td){
    td.onclick = function(e){ if (e) e.preventDefault(); goToday(); };
    td.disabled = isToday();     // always visible; dimmed when already on today
  }
  /* Tapping the date itself opens the phone's own date picker, for the jump
     the arrows are bad at: next Friday is four taps of an arrow and one of a
     calendar. A real date input is laid invisibly over the label, so the tap
     that opens the picker is a genuine tap on a genuine input - iOS opens it
     from focus alone, where showPicker() does not exist on older Safari.
     Desktop browsers focus the field but only open the calendar from its
     icon, so showPicker() is called too, where it does exist. Picking today
     drops the ?date rather than pinning it, same as the Today button, so the
     page follows the clock again instead of freezing on a written date. */
  if (el){
    el.style.position = 'relative';
    el.style.cursor = 'pointer';
    var pick = document.createElement('input');
    pick.type = 'date';
    pick.value = dkey(VIEW);
    pick.setAttribute('aria-label', 'Choose a date');
    pick.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;'+
      'opacity:0;border:0;padding:0;margin:0;cursor:pointer;'+
      '-webkit-appearance:none;appearance:none;background:transparent;';
    pick.onclick = function(){
      if (pick.showPicker){ try { pick.showPicker(); } catch (e){} }
    };
    pick.onchange = function(){
      var v = pick.value;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return;
      var q = new URLSearchParams(location.search);
      if (v === dkey(new Date())) q.delete('date'); else q.set('date', v);
      location.search = q.toString();
    };
    el.appendChild(pick);
  }
  return { VIEW:VIEW, todayKey:todayKey, isToday:isToday };
}

/* ── room-guest look-back ──────────────────────────────────────
   Most recent record for a room across the previous fortnight.
   A guest who opened the link days ago still appears, unless
   they have departed. Reads each date individually so no
   permission is needed on the parent node.                       */
/* A fortnight of roomguests is 14 of the 19 requests a board makes, and it is
   the part that does not move: a booking recorded last Tuesday is still what
   it was. Polling it every 20 seconds alongside the things that DO move costs
   about five times the bandwidth for no extra freshness, so it is held for a
   few minutes and refetched on a full load.
   Pass force = true to ignore the cache.                                  */
var RG_CACHE = null, RG_AT = 0, RG_KEY = '', RG_MAX_AGE = 5 * 60 * 1000;

function fetchRoomGuests(endKey, days, force){
  days = days || 14;
  if (!force && RG_CACHE && RG_KEY === endKey + ':' + days &&
      (Date.now() - RG_AT) < RG_MAX_AGE){
    return Promise.resolve(RG_CACHE);
  }
  var parts = endKey.split('-');
  var end = new Date(+parts[0], +parts[1]-1, +parts[2]);
  var jobs = [], keys = [];
  for (var i = days - 1; i >= 0; i--) {
    var d = new Date(end); d.setDate(d.getDate() - i);
    var k = dkey(d);
    keys.push(k);
    jobs.push(
      fetch(DB + '/roomguests/' + k + '.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .catch(function(){ return null; })
    );
  }
  return Promise.all(jobs).then(function(res){
    var all = {};
    res.forEach(function(day, i){ if (day) all[keys[i]] = day; });
    /* Only cache a complete answer. A partial fetch cached for five minutes
       would show a villa as empty because one day failed to load.       */
    if (res.every(function(day, i){ return day !== null || true; })){
      RG_CACHE = all; RG_AT = Date.now(); RG_KEY = endKey + ':' + days;
    }
    return all;
  });
}

function clearRoomGuestCache(){ RG_CACHE = null; RG_AT = 0; }

function resolveRoomGuests(all, todayK){
  var out = {};
  var dates = Object.keys(all || {}).filter(function(d){ return d <= todayK; }).sort();
  dates.forEach(function(d){
    var day = all[d] || {};
    for (var room in day){ out[room] = day[room]; }   // later dates overwrite earlier
  });
  // drop anyone checked out by this sheet's dinner: a guest departing on
  // the sheet date leaves that morning, so their last sheet is the night before
  for (var room in out){
    var dep = out[room] && out[room].departs;
    if (!dep) continue;
    var p = parseDepDate(dep);
    if (p && dkey(p) <= todayK) delete out[room];
  }
  return out;
}

/* ── guest misc ────────────────────────────────────────────── */
function tidyPhone(p){
  if (!p) return '';
  p = String(p).replace(/[^\d]/g,'');
  if (p.length === 9 && p[0] === '4') p = '0' + p;   // restore a lost leading zero
  return p;
}

/* ── renamed dietaries ─────────────────────────────────────────
   The owner renamed two pills on 26 Aug: a pill names the thing the guest
   cannot eat, so "Gluten free" and "Dairy free" are "Gluten" and "Dairy".
   Answers already saved carry the old wording - in dinner cells, in
   pre-arrival records, in /guests, in tonight's tags - and nothing sweeps a
   live database to rewrite a fact a guest gave us. So every reader maps the
   old name to the new one: displays show the new word, the old answers still
   light the chips and still hit the menu-tag comparison, and the next save
   of any record writes the new name back, which is how the data converges
   without a migration.

   The table is copied into index.html and prearrival.html, which are guest
   pages and deliberately load no staff code. tests/diet_renames.json is the
   shared table all three copies are checked against - add a rename there,
   never to one copy. */
var DIET_RENAMES = { 'Gluten free': 'Gluten', 'Dairy free': 'Dairy' };
function fixDietName(d){ return DIET_RENAMES[d] || d; }
function fixDietList(list){
  var out = [];
  (list || []).forEach(function(d){
    d = fixDietName(d);
    if (out.indexOf(d) === -1) out.push(d);
  });
  return out;
}
/* Tonight's tags, per course, as /menutags stores them. */
function fixTagNames(tags){
  if (!tags) return tags;
  var out = {};
  Object.keys(tags).forEach(function(c){
    out[c] = Array.isArray(tags[c]) ? fixDietList(tags[c]) : tags[c];
  });
  return out;
}
/* The master list, as /dietaries stores it: keyed by the name, so a rename
   moves the record to the new key. The keying transform is keyOf() on the
   pages that write the list - the same three steps, kept in step by the
   suites. If the database somehow holds both spellings the two records
   merge, active if either was. */
function fixDietMaster(master){
  if (!master) return master;
  var out = {};
  Object.keys(master).forEach(function(k){
    var d = master[k] || {};
    var nd = {}; for (var f in d) nd[f] = d[f];
    nd.name = fixDietName(d.name || k);
    var key = nd.name.trim().replace(/[.#$\/\[\]]/g,'').replace(/\s+/g,' ');
    if (out[key]) out[key].active = !!(out[key].active || nd.active);
    else out[key] = nd;
  });
  return out;
}
function dietMasterRenamed(master){
  return !!master && Object.keys(master).some(function(k){
    var n = (master[k] && master[k].name) || k;
    return fixDietName(n) !== n;
  });
}

/* ── dietary conflicts against the tagged menu ─────────────── */
function menuConflicts(menu, diets){
  if (!diets || !diets.length || !menu) return [];
  var hits = [];
  ['bread','entree','main','dessert'].forEach(function(k){
    var dish = menu[k];
    if (!dish || !dish.conflicts) return;
    dish.conflicts.forEach(function(tag){
      tag = fixDietName(tag);
      diets.forEach(function(d){
        d = fixDietName(d);
        if (String(d).toLowerCase() === String(tag).toLowerCase())
          hits.push({ dish: dish.name || k, diet: d });
      });
    });
  });
  return hits;
}

function dietHTML(diets, sep, cls){
  diets = fixDietList(diets);
  if(!diets.length) return '';
  cls = cls || 'allergen';
  return diets.map(function(d){
    return (ALLERGENS.indexOf(d)>-1 || /allerg/i.test(d)) ? '<span class="'+cls+'">'+d+'</span>' : d;
  }).join(sep || ' \u00b7 ');
}

/* ── housekeeping variants - deliberately different from above ──
   resolveRoomGuestsHK KEEPS guests departing today: they are the
   cleans. The dinner resolver drops them. Do not merge the two.   */
function resolveRoomGuestsHK(all, todayK){
  var out = {};
  var dates = Object.keys(all || {}).filter(function(d){ return d <= todayK; }).sort();
  dates.forEach(function(d){
    var day = all[d] || {};
    for (var room in day){ out[room] = day[room]; }
  });
  for (var room in out){
    var dep = out[room] && out[room].departs;
    if (!dep) continue;
    var p = parseDepDate(dep);
    if (p && dkey(p) < todayK) delete out[room];   // gone before today
  }
  return out;
}

/* One request, one date. Unlike roomguests, which needs a fortnight of history
   because a guest may have opened their link days ago, /stays is written by the
   PMS sync for every night of a stay, so the date being shown is the only date
   worth asking for. That is why each night carries the guest rather than a
   pointer: a pointer would cost a request per villa and undo the work that took
   a poll from nineteen requests to four.                                    */
/* The dinner cells for the date fetchStays was last called with.

   Every page that renders a night already calls fetchStays for that date, so
   the cells are fetched alongside and kept here. roomRecord falls back to this
   when a caller passes nothing, which means the two printed sheets pick the
   cell up without their own files changing.

   That matters because those two belong to a different chat. Without it, a
   villa booked on the board today shows on screen and is missing from the
   paper, which is the worst kind of wrong: the chef has no way to know.

   Worth making explicit later, when the sheets are next open: they should read
   /dinner themselves and pass it in, like the boards do. Until then this is
   the seam that keeps screen and paper agreeing.                          */
var DINNER_CELLS = {};

/* Which villas opened their menu link on the date fetchStays was last called
   with. Kept beside DINNER_CELLS for the same reason: every page that renders
   a night already asks for that night, so the marks ride along and no page
   grows a fetch of its own.

   It answers the question the dinner cell cannot. An empty cell says nobody
   has answered. It does not say whether anybody was asked. */
var OPENED_MARKS = {};

/* True when this villa opened its link on the night being shown. */
function openedTonight(villa, marks){
  var m = (marks || OPENED_MARKS)[String(villa)];
  return !!(m && m.at);
}

/* ── a phone number a machine can dial ─────────────────────────
   ClickSend wants E.164 and the Worker stores what Mews sends, untouched:
   real records hold `0412 345 678`, `+61412345678`, `0412345678` and worse,
   because a guest typed them. This turns each into +614XXXXXXXX or refuses.

   Refusal is deliberate: no guessing at an international number, a landline,
   or a mobile with the wrong number of digits. A wrong guess sends a guest's
   dinner link to a stranger; a refusal is a greyed row naming a Mews record
   that cannot be fixed here.

   The invitations Worker carries its own copy of this function, because a
   Worker cannot import from the site. worker/invites-test.mjs asserts both
   copies against one table of cases, so the two cannot drift apart quietly.

   NOT tidyPhone in list.html, which goes the other way: that one makes a
   number readable by a person, this one makes it dialable by a machine.  */
function normalisePhone(raw){
  var s = String(raw == null ? '' : raw).replace(/[\s().\-]/g, '');
  /* 0011 is Australia's international dial-out and 00 most of the world's:
     both mean the + of E.164. */
  if (/^0011[1-9]\d/.test(s))    s = '+' + s.slice(4);
  else if (/^00[1-9]\d/.test(s)) s = '+' + s.slice(2);
  if (/^04\d{8}$/.test(s))    return '+61' + s.slice(1);   /* the common case */
  if (/^614\d{8}$/.test(s))   return '+' + s;              /* plus went missing */
  /* Our own country we can judge: +61 must be a mobile, a landline is
     refused rather than sent. Any other full country code is not a guess -
     the guest typed where they live - and is sent as typed. Widened 25 Aug
     when (+64) 274875277, an ordinary NZ mobile, was refused. A foreign
     number typed WITHOUT its code still returns null: 0274875277 reads as an
     Australian landline, and guessing the country texts a stranger. */
  if (/^\+61\d+$/.test(s))    return /^\+614\d{8}$/.test(s) ? s : null;
  if (/^\+[1-9]\d{7,14}$/.test(s)) return s;
  return null;                                             /* not sent, ever  */
}

/* How sure are we that a sendable number is a MOBILE? Advisory only - the
   send is still the judge - shown as the tick or the question mark beside
   the number on the SMS pages. Countries where the mobile ranges are
   published and unambiguous get a tick; everywhere else, including all of
   +1 where mobiles and landlines share the same ranges, is honestly a
   question mark. Extend the table as guests arrive from new countries. */
var MOBILE_SHAPES = [
  /^\+614\d{8}$/,          /* Australia: 04 */
  /^\+642\d{7,9}$/,        /* New Zealand: 02 */
  /^\+447\d{9}$/,          /* United Kingdom: 07 */
  /^\+316\d{8}$/,          /* Netherlands: 06 */
  /^\+49(15|16|17)\d{7,9}$/, /* Germany */
  /^\+33[67]\d{8}$/,       /* France */
  /^\+3538\d{8}$/,         /* Ireland: 08 */
  /^\+65[89]\d{7}$/,       /* Singapore */
  /^\+852[569]\d{7}$/,     /* Hong Kong */
  /^\+861[3-9]\d{9}$/,     /* China */
  /^\+91[6-9]\d{9}$/,      /* India */
  /^\+81[789]0\d{8}$/,     /* Japan: 070/080/090 */
  /^\+27[678]\d{8}$/,      /* South Africa */
  /^\+9715\d{8}$/          /* UAE: 05 */
];
function phoneConfidence(raw){
  var e = normalisePhone(raw);
  if (!e) return null;
  for (var i = 0; i < MOBILE_SHAPES.length; i++)
    if (MOBILE_SHAPES[i].test(e)) return 'mobile';
  return 'unsure';
}

/* ── the number beside a guest's name ──────────────────────────
   The raw number, small and grey; the confidence mark (a tick where the
   country's mobile ranges are published and this number sits in one, a
   question mark where nobody can tell a mobile from a landline); and the
   pencil that edits it. Grown on the Pre-arrival SMS page, wanted by the
   Front Desk days later, so built here once rather than pasted twice.

   Each page styles .ph/.conf/.pen in its own sheet and wires the pencil
   itself - by delegation on a page built from strings, by onclick on one
   built from nodes - and both hand the tap to editPhoneNumber below.
   showPen=false leaves the pencil out where editing has nothing to offer
   (a completed form needs no number and a dead pencil reads as broken). */
function phoneBadgeHTML(raw, showPen){
  raw = String(raw == null ? '' : raw).trim();
  var esc = function(t){ return String(t).replace(/[&<>"]/g, function(c){
    return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]; }); };
  var h = '<span class="ph">' + (raw ? esc(raw) : 'no number') + '</span>';
  var confidence = raw ? phoneConfidence(raw) : null;
  if (confidence === 'mobile')
    h += '<span class="conf ok" title="Sits in this country’s published ' +
         'mobile ranges">✓</span>';
  else if (confidence)
    h += '<span class="conf un" title="A real number, but this country’s ' +
         'mobiles cannot be told from landlines; sending will find out">?</span>';
  if (showPen)
    h += '<span class="pen" role="button" aria-label="Edit number">✎</span>';
  return h;
}

/* The number editor behind the pencil. A browser prompt rather than a drawn
   form: it is rare, it is one field, and the keyboard it summons is the
   phone's own. What is saved is the normalised E.164 at /phonefix/<booking>,
   so the record can never hold a shape the send would refuse; the raw Mews
   value rides along as `was` for the audit. Mews itself stays wrong - it
   cannot be written from here - so the guest should still be corrected in
   Mews when somebody is in there. The fix outranks the Mews copy everywhere
   a number is read, because the next sync would revert an edit to the stay.

   cb hears the outcome: null after a successful save, otherwise the words to
   put on the page's error bar. Cancelling the prompt calls nothing at all. */
function editPhoneNumber(booking, cb){
  var typed = window.prompt(
    'Mobile number for ' + (booking.name || 'this guest') +
    '.\nInclude the country code for an overseas number, e.g. +64 27 487 5277.',
    String(booking.current || '').trim());
  if (typed == null) return;                       /* cancelled */
  var phone = normalisePhone(typed);
  if (!phone){
    cb('That is still not a sendable mobile number. Australian ' +
       'numbers can be typed as 04...; anything overseas needs its + country code.');
    return;
  }
  fetch(DB + '/phonefix/' + booking.id + '.json', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone: phone, was: String(booking.was || ''),
                           by: (window.NALA_USER && NALA_USER.email) || '',
                           at: new Date().toISOString() })
  }).then(function(r){
    if (!r.ok) throw new Error();
    cb(null);
  }).catch(function(){
    cb('The number did not save. Try again.');
  });
}

function fetchStays(dateKey){
  return Promise.all([
    fetch(DB + '/stays/' + dateKey + '.json?v=' + Date.now())
      .then(function(r){ return r.ok ? r.json() : null; })
      /* A failure here must not empty the boards. Returning null means the
         merge simply falls back to roomguests, which is what it did before any
         of this existed.                                                   */
      .catch(function(){ return null; }),
    fetch(DB + '/dinner/' + dateKey + '.json?v=' + Date.now())
      .then(function(r){ return r.ok ? r.json() : null; })
      .catch(function(){ return null; }),
    /* A failed read here must not read as nobody opened anything: that would
       put every villa back in the never reached pile and send reception
       chasing guests who already answered. Null, and the caller shows no
       marks rather than wrong ones. */
    fetch(DB + '/opened/' + dateKey + '.json?v=' + Date.now())
      .then(function(r){ return r.ok ? r.json() : null; })
      .catch(function(){ return null; })
  ]).then(function(res){
    DINNER_CELLS = res[1] || {};
    OPENED_MARKS = res[2] || {};
    /* One more read per occupied villa: the reservation's own answers. There
       is one dietary list per person and it lives on the reservation, not on
       a night, so the boards have to be able to see it even when the viewed
       night holds no dinner cell at all. A failed read leaves that villa's
       entry empty and the merge falls back to the night, which is exactly
       yesterday's behaviour rather than a blank board. */
    var stays = res[0] || {}, map = {};
    return Promise.all(Object.keys(stays).map(function(v){
      var id = stays[v] && stays[v].id;
      if (!id) return null;
      return fetch(DB + '/bookings/' + id + '/prearrival.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .catch(function(){ return null; })
        .then(function(p){ if (p) map[String(v)] = p; });
    })).then(function(){
      PREARRIVAL_BY_VILLA = map;
      return res[0];
    });
  });
}

/* The reservation's dietaries, laid over a built record. The reservation wins
   when it has any, because an allergy is not true on Tuesday and false on
   Wednesday; the night's copy stands only as the fallback while older records
   still hold dietaries there and nowhere else. NOTES-AUDIT.md has the model
   and the correction: an earlier version said the night should win, and it
   was wrong. */
var PREARRIVAL_BY_VILLA = {};

/* When the arriving guest lands, as an hour on the 24 hour clock. Reception's
   approved hour wins outright; the guest's own slot stands next; and 2pm
   stands for every arrival that says nothing, because 2pm is the resort's
   standing promise, not a guess. disp is empty for that silent default: it
   sorts and warns like a stated 2pm but nobody set it, so nothing is drawn.

   Here rather than in a page, because the Cleans board and the printed Clean
   Sheet both render it, and two copies of when the guest lands is how screen
   and paper drift apart. The Worker holds the server side mirror. */
function effectiveEta(villa){
  var pre = PREARRIVAL_BY_VILLA[String(villa)] || {};
  var ap = Number(pre.arriveApproved);
  if (pre.arriveApproved != null && ap >= 11 && ap <= 23)
    return { h: ap, disp: hour12(ap), early: ap < 14 };
  var s = String(pre.arriveSlot || '');
  if (s === 'before2') return { h: 14, disp: '<2pm', early: true };
  if (s === 'after5')  return { h: 17, disp: '>5pm', early: false };
  /* Two digits are an hour, four are an hour and its half: the nine keys the
     guest's track writes. Same list as the three page copies. */
  if (/^1[4-7](30)?$/.test(s)){
    var hh = +s.slice(0, 2) + (s.length === 4 ? 0.5 : 0);
    return { h: hh, disp: hour12(hh), early: false };
  }
  return { h: 14, disp: '', early: false };
}
function hour12(h){
  var w = Math.floor(h);
  return (w > 12 ? w - 12 : w) + (h % 1 ? ':30' : '') + (w < 12 ? 'am' : 'pm');
}
function etaWord(disp){
  return disp === '<2pm' ? 'before 2pm' : disp === '>5pm' ? 'after 5pm' : disp;
}

function overlayReservationDiets(rec, villa){
  if (!rec) return rec;
  var pre = PREARRIVAL_BY_VILLA[String(villa)];
  if (!pre) return rec;
  if (pre.diets && pre.diets.length){
    rec.diets = pre.diets.slice();
    /* The reservation's list is the person's list, so dietaries are never
       "previous": a copy carried forward on roomguests is an old copy of a
       current fact, not an unconfirmed answer. Leaving prevDiets set showed
       the same allergy twice, once with a warning to ask first. */
    delete rec.prevDiets;
    if (pre.dnote){
      rec.dnote = pre.dnote;
      /* The bubble and its popover read the stamped field, and the stamp
         runs before this overlay, so a note living only on the reservation
         was invisible to both: the bubble called an explained Other
         unexplained and went red, and opened onto nothing. 20 Aug. */
      rec.dineDnote = pre.dnote;
      delete rec.prevDnote;
    }
  }
  return rec;
}

/* Turns one /stays/<date>/<villa> entry into the shape roomguests uses, so it
   can sit in the same merge instead of needing its own handling everywhere.
   Tolerates the older shape, where the value was the booking id as a bare
   string: those entries carry no guest and are ignored rather than crashing.  */
/* True when a record came from the PMS and the guest has not opened their link.
   The two are different facts and must not be conflated: "we know who is in
   villa 4" is not "villa 4 has replied to us". Conflating them puts the link
   opened mark on every synced booking, which is the exact signal the sync
   exists to stop staff relying on.                                         */
function isMewsOnly(rec){
  return !!(rec && rec.source === 'mews');
}

/* Is anybody attached to this villa on this date at all: a Mews reservation, a
   guest who opened their link, or a record reception typed in. It is the line
   between the two empty states on the boards, which mean different things and
   want different reactions.

     vacant   nobody is booked into this villa, so there is no question to ask
     awaiting somebody is, and they have not said yes or no to dinner yet

   A record with nothing in it is not a guest. `roomguests` carries empty
   objects around from older writes, and one of those showing as a booking was
   what made the boards look busier than the resort was. */
function hasGuestProfile(rec){
  return !!(rec && typeof rec === 'object' &&
            (rec.name || rec.bookingId || rec.departs || rec.arrives || rec.phone));
}

function mewsRecord(stay){
  if (!stay || typeof stay !== 'object') return null;
  var name = [stay.first, stay.last].filter(Boolean).join(' ').trim();
  if (!name && !stay.depart) return null;
  var out = { source:'mews', bookingId: stay.id, pmsUpdated: stay.updated || null };
  if (name)          out.name    = name;
  if (stay.phone)    out.phone   = stay.phone;
  if (stay.depart)   out.departs = stay.depart;
  if (stay.arrive)   out.arrives = stay.arrive;
  if (stay.adults)   out.adults  = stay.adults;
  /* The second guest, as Mews sent it. The Worker has written this onto
     every night since 19 Aug and this reader dropped it, which is why no
     board could ever show a companion the Zap delivered. */
  if (stay.companion) out.companion = stay.companion;
  /* One party can hold several villas. Two reservations under one group are
     not two guests who happen to share a surname, and a board that treats them
     as strangers will seat them apart. */
  if (stay.groupId)  out.groupId = stay.groupId;
  /* The human readable reservation number. Carried so reception can look a
     booking up in Mews without opening the app's own id, which is a GUID and
     no use to anybody standing at a desk. */
  if (stay.number)   out.number  = stay.number;
  return out;
}

/* The second guest's name, one reading for every surface that shows it.
   What a person typed - the guest at pre-arrival, or reception at the desk,
   both landing in prearrival.companion - wins; the name Mews sent stands
   behind it. The same order the desk's answersOf established, now read
   through here by every page. One name, never a list: whether a villa can
   hold more than one companion is an open decision in HANDOVER.md, and the
   field is a single value everywhere until it is settled. */
function companionOf(pre, rec){
  return String((pre && pre.companion) || (rec && rec.companion) || '').trim();
}

/* Every OTHER villa the same party holds tonight. Empty for the ordinary case
   of one booking in one villa, which is nearly all of them.

   It cannot tell a two villa booking from a guest who was moved: both look
   like one group across two villas with overlapping dates. Only a cancellation
   separates those, so this reports rather than decides. */
function groupVillas(roomguests, villa){
  var me = roomguests && roomguests[String(villa)];
  if (!me || !me.groupId) return [];
  var out = [];
  for (var v in roomguests){
    if (String(v) === String(villa)) continue;
    var r = roomguests[v];
    if (r && r.groupId === me.groupId) out.push(String(v));
  }
  return out.sort(function(a,b){ return (+a) - (+b); });
}

/* ── the pre-arrival form's state ──────────────────────────────
   Three states, the owner's ruling of 28 Aug:

     not started   nobody has answered anything
     incomplete    somebody has, and it has not been marked complete
     completed     the guest pressed Send, or the desk marked it complete

   It replaces two overlapping systems that could disagree. The Front Desk
   row tint was computed from the answers; `at` was a stamp written by
   something else entirely; and nothing reconciled them, so a booking could
   read completed on one board and incomplete on the other while holding
   nothing at all. Villa 17, 28 Aug.

   Read here rather than in each board for the same reason. Two readings of
   one state is how they came to disagree in the first place.

   prearrival.html cannot read any of this: it is a GUEST page and loads no
   staff code. Its half of the contract is tests/form_questions.json and
   tests/onenight_cases.json, which both suites answer to. */

/* The keys a guest can answer. Held here since 28 Aug: the Front Desk and
   Pre-arrival SMS each had their own copy and they had ALREADY drifted - the
   desk had learnt that a noDiets of false says nothing, and Pre-arrival SMS
   had not, so the two counted a cleared dietary differently. */
var GUEST_ANSWERS = ['arriveSlot','arriveNote','dining','diets','noDiets',
                     'dnote','purpose','approach','wellness','wellDay',
                     'wellTime','occasion','note','companion'];

function countGuestAnswers(p){
  if (!p) return 0;
  return GUEST_ANSWERS.filter(function(k){
    var v = p[k];
    if (v === undefined || v === null || v === '') return false;
    if (Array.isArray(v)) return v.length > 0;
    /* "No" is an answer - but only to a question with two sides. dining and
       wellness have them; noDiets is a flag, where true declares "nothing to
       declare" and false says nothing at all. */
    if (v === false) return k !== 'noDiets';
    return true;
  }).length;
}
function guestAnswered(p){ return countGuestAnswers(p) > 0; }

/* How many nights, from whatever shape Mews sent the dates in. parseDepDate
   builds a LOCAL date from the date part, so a full ISO timestamp and a bare
   date count the same - which they must, since Mews sends both. */
function stayNights(s){
  var a = parseDepDate(s && s.arrive), b = parseDepDate(s && s.depart);
  if (!a || !b) return null;
  return Math.round((b - a) / 86400000);
}
function oneNightStay(s){ return stayNights(s) === 1; }

/* What a booking must hold before it may be called complete: the three
   decisions the desk settles and other boards act on. The owner's ruling of
   28 Aug, asked and answered directly - purpose and dining approach are
   deliberately NOT here, because no board acts on them and blocking a
   completion over them would be blocking it over colour.

   A one night stay is not owed the treatment answer. The guest form never
   offers it - one afternoon is no window for the therapists, the owner ruled
   25 Aug - so a question never put to them cannot be held against them. */
function mandatoryAnswered(p, stay){
  if (!p) return false;
  var dinner  = p.dining === true || p.dining === false;
  var dietary = !!p.noDiets ||
                (Array.isArray(p.diets) ? p.diets.length > 0 : !!p.diets);
  var massage = p.wellness === true || p.wellness === false;
  return dinner && dietary && (massage || oneNightStay(stay));
}

/* Completed wants all three: the stamp, an answer behind it, and the
   mandatory answers still standing. Any one of them missing and it is not
   complete, whatever the record says it is.

   Checked on every read rather than trusted from the stamp, which is what
   makes this self healing. The old check in demanded dinner and dietary but
   never the massage, so it could stamp a multi night booking complete with
   the treatment question unasked - and that booking reads incomplete here
   from the moment this ships, with nothing to run and nothing to repair. */
function formState(p, stay){
  if (p && p.at && guestAnswered(p) && mandatoryAnswered(p, stay))
    return 'completed';
  return guestAnswered(p) ? 'incomplete' : 'notstarted';
}

/* Every OTHER villa the same party holds, said in the words both boards use.
   Takes the row and the list it came from - each entry a {villa, stay} - so a
   caller pays nothing for it beyond rows it has already loaded.

   groupVillas above answers the same question off a /roomguests map, which is
   the shape the cleaning boards hold. This one is the arrivals shape. They are
   two readers of one fact rather than two facts: whichever board asks, a party
   holding two villas is two reservations under one groupId.

   Plain text, with a real ampersand: the Front Desk builds its row by
   concatenation and escapes this on the way in, Pre-arrival SMS sets it as
   textContent. Returning markup would be wrong for one of them either way. */
function groupMatesText(row, rows){
  var g = row && row.stay && row.stay.groupId;
  if (!g) return '';
  var out = (rows || []).filter(function(x){
    return x !== row && x.stay && x.stay.groupId === g;
  }).map(function(x){ return String(x.villa); })
    .sort(function(a, b){ return (+a) - (+b); });
  if (!out.length) return '';
  return 'with ' + (out.length === 1 ? 'villa ' : 'villas ') + out.join(' & ');
}

/* Two records describe the same person if the PMS and a guest written entry
   agree on a phone or a name. Phones are compared on their last nine digits
   because Mews stores +61400000000 and a GuestTouch link carries 0400000000,
   and those are one person.

   SCAFFOLDING. This exists only because a roomguests record is keyed on what a
   guest's URL supplied rather than on the booking. Once every record carries a
   booking id the match is exact and this whole function goes: see stage 4.

   The name fallback is the weak half. It covers Mews sending no phone at all,
   which is villa 3's Zap mapping bug, so one workaround is propping up
   another. Two different real guests sharing a name would match, and the wrong
   villa's record would be dropped: rare, and silent, which is the combination
   worth knowing about. Fixing the villa 3 mapping removes the need for it.
   Only guest written entries are ever dropped, so a villa the PMS itself
   claims is never at risk.                                                 */
function samePerson(a, b){
  if (!a || !b) return false;
  var pa = String(a.phone || '').replace(/\D/g, '').slice(-9);
  var pb = String(b.phone || '').replace(/\D/g, '').slice(-9);
  if (pa && pa === pb) return true;
  var na = String(a.name || '').trim().toLowerCase();
  var nb = String(b.name || '').trim().toLowerCase();
  return !!(na && na === nb);
}

/* Lays the PMS over the guest written records. Mews wins on identity and
   dates, because it is the authority on who is in a villa and when they leave;
   roomguests only knows what a guest happened to type after opening a link.

   Done here, at the roomguests layer, rather than inside roomRecord, because
   tally.html reads roomguests directly in eight places and does not call
   roomRecord at all. Two mechanisms would let the board and the sheet disagree
   about the same villa, which is the failure that looks plausible.

   It sits BELOW responses in roomRecord, which is where the fields the PMS
   owns outright are reapplied on top. See pmsFields.                       */
function overlayStays(roomguests, stays){
  var out = Object.assign({}, roomguests || {});
  var pmsVillas = {};
  for (var villa in (stays || {})){
    var rec = mewsRecord(stays[villa]);
    if (!rec) continue;
    var had = out[String(villa)];
    var merged = Object.assign({}, had || {}, rec);
    /* source stays 'mews' ONLY when there was no guest written record to begin
       with. A guest who did open their link keeps that fact, so the link opened
       mark still means what it always meant. */
    if (had) delete merged.source;
    out[String(villa)] = merged;
    pmsVillas[String(villa)] = merged;
  }
  /* A guest moved after opening their link is left behind in the old villa.
     roomguests keeps a record until its own departure date passes, so the same
     person shows in two villas at once: exactly the bug the Worker fixed on the
     /stays side, reappearing one layer up because nothing cleans this side.

     The PMS is the authority on where somebody is, so any OTHER villa holding
     the same person is stale by definition and goes. Only guest written entries
     are dropped: a villa the PMS itself claims is never touched, so two genuine
     bookings that happen to share a phone stay put.                        */
  for (var v in out){
    if (pmsVillas[v]) continue;
    for (var pv in pmsVillas){
      if (samePerson(out[v], pmsVillas[pv])){ delete out[v]; break; }
    }
  }
  return out;
}

/* Where the PMS places a person, or null if it does not know them. Used to
   ignore a response a guest wrote while they were still in their old villa. */
function pmsVillaOf(roomguests, rec){
  for (var v in (roomguests || {})){
    var r = roomguests[v];
    if (r && r.bookingId && samePerson(r, rec)) return String(v);
  }
  return null;
}

/* The fields the PMS owns outright. Mews knows who is in a villa, when they
   arrive and leave and how many of them there are. It knows nothing about
   dinner, so dining, covers, notes and dietaries are never touched here: they
   would only be overwritten with nothing.

   This is reapplied ABOVE responses rather than left to the overlay, because a
   response carries a copy of the dates taken when the guest replied. That copy
   is a snapshot and goes stale the moment Mews changes the booking, and it was
   winning: a stay shortened in Mews still read as a service on the departure
   day, so the villa was never offered for cleaning on the day it was vacated.
   The design said Mews wins on depart. This is where that becomes true.    */
function pmsFields(known){
  if (!(known && known.bookingId)) return {};
  var out = {};
  ['name','departs','arrives','phone','adults'].forEach(function(k){
    if (known[k] !== undefined && known[k] !== null && known[k] !== '') out[k] = known[k];
  });
  return out;
}

/* A villa the PMS knows about can still be marked vacant by staff, after a
   warning, and that decision stands until Mews changes the booking. It is
   stamped with the PMS version it was made against: once Mews sends a newer
   one, the staff decision was about a different state of the world and is
   dropped rather than silently outliving the facts it was based on.        */
function vacantIsStale(m, known){
  return !!(m && m.status === 'vacant' && known && known.bookingId &&
            m.pmsUpdated !== known.pmsUpdated);
}

/* ── booking flags ─────────────────────────────────────────────
   Short facts pinned under a guest's name: VIP, Travel agent, Breakfast
   included - whatever the admin defines on the Flags settings page
   (flags.html, writing the /flags list, the dietaries shape). The desk
   ticks them per booking, admin only, and the ticks live at
   /bookflags/<booking id> as a plain list of names. The Service Sheet
   prints each as a pill under the guest name.

   One flag sets itself. The Worker carries the Mews rate name into
   pms.rate, and a booking whose rate is Luxury Escapes wears that pill
   with nobody ticking anything. Only that rate - the owner's ruling,
   26 Aug: every other rate name stays off the paper. Matched on the
   front of the string, case and spacing aside, because live rate names
   usually carry suffixes ("Luxury Escapes AU") and none has been seen
   from here yet - the companion field's standing caution. */
var RATE_FLAG = { label: 'Luxury Escapes', match: /^\s*luxury\s*escapes/i };

function rateFlagLabel(pms){
  return (pms && typeof pms.rate === 'string' && RATE_FLAG.match.test(pms.rate))
    ? RATE_FLAG.label : null;
}

/* Every pill a booking wears: the ticked names in their stored order, the
   rate's own last, duplicates folded case-blind so an admin who also made
   a "Luxury Escapes" flag does not print it twice. */
function bookingFlagLabels(pms, rec){
  var out = [], seen = {};
  (((rec || {}).flags) || []).forEach(function(t){
    t = String(t == null ? '' : t).trim();
    if (!t || seen[t.toLowerCase()]) return;
    seen[t.toLowerCase()] = true; out.push(t);
  });
  var r = rateFlagLabel(pms);
  if (r && !seen[r.toLowerCase()]) out.push(r);
  return out;
}

/* one room, one record: staff override beats the guest's own answer,
   whoever opened the link fills the gaps.

   The PMS is folded into roomguests by overlayStays before this runs, and the
   fields Mews owns outright are then reapplied ON TOP of the response, because
   a response carries a snapshot of the dates from when the guest replied. See
   pmsFields for why that snapshot cannot be allowed to win.                */
/* ── the dinner cell ───────────────────────────────────────────
   ONE record per villa per night, at /dinner/<date>/<villa>, holding the
   answer to "are you eating with us tonight" whoever gave it.

   It replaces two cells that held the same fact: /responses/<date>/<phone>
   when a guest replied, and /manual/<date>/room-<villa> when staff typed it.
   Two cells is why roomRecord needed precedence rules at all, and precedence
   rules are how two copies of one fact quietly disagree.

   The rule, which is what the app already did for guest replies and failed to
   do for staff ones: whoever answers first sets it, and after that only staff
   can change it. A guest opening their link sees what is booked rather than a
   question they could overwrite. `by` records who, `at` records when.

   Villa keyed, not booking keyed, because a board reads one night in one
   request and a booking-keyed node would cost one request per villa. The
   booking id rides along inside so the record still knows whose it is.     */
function dinnerRecord(cell){
  if (!cell || typeof cell !== 'object') return null;
  return cell;
}

/* A guest who answered dinner and was then moved leaves the answer behind in
   the villa they left, so the board shows a booking in an empty villa and
   counts the covers twice. Same bug as the one that produced three Ben
   Davidsons, in its third home: /stays was fixed in the Worker, roomguests in
   overlayStays, and this is the dinner cell.

   Mews is the authority on where somebody is. A cell whose booking id the PMS
   places in a DIFFERENT villa is stale by definition. Only cells carrying a
   booking id are touched: an external diner or a staff entry with no booking
   is not something Mews has an opinion about.

   It does not move the answer, only drops it. Moving it would be guessing that
   a booking made for one villa still holds for another, and a villa change is
   usually a change of party size or plan. The guest is asked again, which is
   what the empty villa on the board is telling reception to do. */
function dinnerElsewhere(cells, villa, roomguests){
  var cell = cells && cells[String(villa)];
  if (!cell || !cell.bookingId) return false;
  for (var v in (roomguests || {})){
    var r = roomguests[v];
    if (r && r.bookingId === cell.bookingId) return String(v) !== String(villa);
  }
  return false;
}

/* Staff outrank a guest, always. A guest cannot overwrite a booking reception
   made, and this is the only precedence left in the app. */
function dinnerLocked(cell){
  return !!(cell && cell.by === 'staff');
}

/* A note, a dietary and a dietary note are answers to one night's dinner
   invitation. Every node that holds them is partitioned by date except
   roomguests, which is deliberately carried forward for up to a fortnight so a
   guest keeps their villa across a stay. So a note written on Monday rode
   along into Tuesday and was rendered as Tuesday's answer. That is how a
   dietary from a previous night reaches the kitchen as though it were
   tonight's, which is the one failure here that ends up on a plate.

   Nothing is thrown away: an allergy is still an allergy and hiding it would
   be worse than mislabelling it. The record now says which night each answer
   belongs to, and the boards say so on screen. `note` and `dnote` keep their
   old meaning and their old values, because the printed sheets read them and
   are owned by another chat. */
var DINE_FIELDS = ['note', 'dnote', 'diets'];
function hasValue(v){
  if (v === undefined || v === null || v === '') return false;
  return !(Object.prototype.toString.call(v) === '[object Array]' && !v.length);
}
function withDineProvenance(out, tonight, known){
  DINE_FIELDS.forEach(function(k){
    var cap = k.charAt(0).toUpperCase() + k.slice(1);
    if (hasValue(tonight && tonight[k])) out['dine' + cap] = tonight[k];
    else if (hasValue(known && known[k])) out['prev' + cap] = known[k];
  });
  return out;
}

function roomRecord(n, responses, manual, roomguests, dinner){
  return overlayReservationDiets(
    roomRecordCore(n, responses, manual, roomguests, dinner), n);
}
function roomRecordCore(n, responses, manual, roomguests, dinner){
  var mk = 'room-'+n, m = manual[mk];
  var known = roomguests[String(n)] || {};
  /* A staff vacant made against an older version of the booking was a decision
     about a different state of the world, so it is dropped rather than left to
     outlive the facts behind it. */
  if (vacantIsStale(m, known)) m = null;

  /* The one cell wins outright when it exists. No merge, because there is
     nothing to merge it with: it holds the whole answer. The two older nodes
     are still read beneath it while links and pages are moved across, and both
     partition by date, so they empty themselves as the days pass rather than
     needing a migration. */
  /* A caller that fetched its own cells passes them. One that did not gets the
     ones fetchStays picked up for the same date. */
  var cells = dinner || DINNER_CELLS;
  var cell = dinnerElsewhere(cells, n, roomguests)
    ? null
    : dinnerRecord(cells && cells[String(n)]);
  if (cell && !vacantIsStale(cell, known))
    return withDineProvenance(
      Object.assign({}, known, cell, pmsFields(known), { room:String(n) }),
      cell, known);

  var best = null;
  for (var k in responses){
    var g = responses[k];
    if (String(g.room) !== String(n)) continue;
    /* A guest who replied and was then moved left their answer attached to the
       old villa. The PMS says where they actually are, so the answer does not
       hold this villa open behind them. */
    var at = pmsVillaOf(roomguests, g);
    if (at && at !== String(n)) continue;
    if (!best || (g.at||'') > (best.at||'')) best = g;
  }
  var pms = pmsFields(known);
  if (m && m.override) return withDineProvenance(
    Object.assign({}, known, best || {}, m, pms, { room:String(n) }), m, known);
  if (best) return withDineProvenance(
    Object.assign({}, known, best, pms), best, known);
  if (m)    return withDineProvenance(
    Object.assign({}, known, m, pms, { room:String(n) }), m, known);
  /* A booking with no name is still a booking. This used to require a name,
     so a villa Mews knows about but has sent no first or last name for
     returned nothing at all and showed on the Cleans board as unknown, with
     no clue that a reservation existed. hasGuestProfile is the test the rest
     of the app already uses for is anybody here, and a booking id or a pair
     of dates answers that perfectly well without a name.

     It matters most exactly when things are already going wrong: on 18 Aug
     every reservation write was being refused, so the app held dates and ids
     and no names, and the board went blank rather than showing the work. */
  if (hasGuestProfile(known)) return withDineProvenance(
    Object.assign({}, known, { room:String(n), status:null }), null, known);
  return null;
}

/* clean = departing on the sheet date; service = staying on;
   verify = no usable data. The housekeeping rule, in one place.  */
function hkClassify(rec, todayK, hk, leftThisMorning){
  /* A manager can set the job for the day by hand - most often on a villa the
     booking data cannot confirm - and that choice beats what the dates imply.
     Stored at /hk/<date>/<villa>/kind so it expires with the day.          */
  if (hk && (hk.kind === 'clean' || hk.kind === 'svc' ||
             hk.kind === 'pre'   || hk.kind === 'vac')) return hk.kind;
  if (rec && rec.status === 'vacant') return 'vac';
  /* Somebody slept here last night and left this morning. On a same day
     turnover the villa also has a new guest arriving, and tonight's record
     has overwritten last night's, so the departure is invisible in `rec`
     and the villa would read as a pre-arrival. It is a clean first: nobody
     can be shown into a room that has not been turned around. The caller
     passes this because only it holds both nights. */
  if (leftThisMorning) return 'clean';
  if (rec){
    var d = parseDepDate(rec.departs);
    var dk = d ? dkey(d) : null;
    /* A departure outranks an arrival, always. On a same day turnover both are
       true of the same villa, and the clean has to happen before anybody can
       be shown in: calling it a pre-arrival would hide the work that has to
       come first. */
    if (dk === todayK) return 'clean';
    /* Arriving today, nobody in last night. The villa needs preparing rather
       than cleaning, which is a different job with a different finished state:
       Pre-arrival becomes Pre-arrived. Checked before the staying-on rule
       because an arriving guest's departure is also in the future, so the
       stay-over test would otherwise swallow every arrival. */
    var a = parseDepDate(rec.arrives);
    if (a && dkey(a) === todayK) return 'pre';
    if (dk && dk > todayK) return 'svc';
    return 'ver';       // stale or missing departure
  }
  return 'ver';         // no data at all
}

/* ── roles and access ──────────────────────────────────────────
   Who may do what. The role comes from the record at /staff/<emailkey>,
   never from the address - the email only finds the record. Pages ask
   can(), never the email, so a permission changes in one place.
   Matrix and rationale in ROLES.md.                                   */

var STAFF_RECORDS = null;    /* the /staff map once loaded, null until then */

/* Firebase keys cannot hold a dot, so the key is the lowercased email with
   EVERY dot turned into a comma. Note the global regex: a plain
   replace('.', ',') changes only the first, which would key
   staff@nalaresort.com.au as staff@nalaresort,com.au and match nothing. */
function emailKey(email){
  return String(email || '').trim().toLowerCase().replace(/\./g, ',');
}

var ROLE_GRANTS = {
  admin:        ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','manageStaff','spaBoard'],
  /* Everything the admin holds except manageStaff, asked for 25 Aug: a
     management login that runs the whole day without the keys to Settings
     General, Pages or Diagnostics, which are the three manageStaff gates.
     Deliberately a role and not a permission column: handing manageStaff
     out is a second admin, and this is the role for everybody who is
     nearly one. spaBoard rides along because the definition is the admin's
     list, whatever joins it, minus that one key. */
  manager:      ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','spaBoard'],
  chef:         ['resBoard','resSheet','publishMenu'],
  waiter:       ['cleansBoard','resBoard','editBookings','resSheet','spaBoard'],
  housekeeping: ['cleansBoard','cleansMarks'],
  /* The masseuse, an external contractor with one screen: the Spa board and
     nothing else. Like the chef, a real login for a real person, but the
     rules also narrow what the account can READ - see /spa in rules.json -
     because hiding a link is not the same as refusing the data.          */
  spa:          ['spaBoard'],
  /* A machine account, held by the Mews sync Worker. Deliberately empty: it
     grants nothing in the UI and lands on no page, so a human signing in as
     it gets the "see the manager" message rather than a half working board.
     Its actual permission lives in the rules, which name the role directly
     and let it write only bookings/<id>/pms and stays. Listed here because a
     role that exists in the database and not in the code is what the next
     session trips over.                                                  */
  sync:         []
};

function isRole(r){ return Object.prototype.hasOwnProperty.call(ROLE_GRANTS, r); }

/* The full access role was called "staff" until the word collided with the
   /staff node, the staff@ login and the "staff" tier of user generally. It is
   "admin" now. Records written before the rename still say staff, so they are
   read as admin rather than as nothing: renaming a role must never be the
   thing that locks the owner out. Drop this once no record says staff.   */
function normaliseRole(r){ return r === 'staff' ? 'admin' : r; }

/* null means no usable record, and no record is no access. Deliberately not
   the lowest role: a typo in an address would otherwise grant something. */
/* The name on the staff record, for showing WHO did something rather than
   which address they signed in with. Falls back to the part of the address
   before the at sign, which is a poor name but a better one than nothing, and
   never to the full address: these appear on a board a guest can see over a
   shoulder. */
/* ── tonight's menu ───────────────────────────────────────────────────
   The menu moved into the database on 21 Aug, so that publishing needs a
   staff login rather than a GitHub token.

   A GitHub token cannot be narrowed to one file: the smallest scope that can
   write menu.json is Contents write, which is every file in the repository,
   including the pages and the Worker. So the chef's credential could change
   the whole live site, and no amount of care in the brief could stop it. The
   database CAN be narrowed: /menu is writable by a chef and an admin, and by
   nobody else, and the rules enforce it rather than the document.

   menu.json is still written alongside, and is still read as the fallback
   here, deliberately. Four screens read the menu and this is a live resort:
   the file means that if the node is empty, or a read fails, or something in
   this change is wrong, the guest's menu does not go dark. It can be dropped
   once a few services have gone by.                                       */
/* Three answers, not two. The guest page learned this on 22 Aug and this, the
   shared reader every staff page uses, did not.

   A node with a menu in it is a menu. A node that could not be read, or has
   never held anything, is silence, and the committed file stands in behind it
   so nobody is shown a placeholder while the chef swears the menu is up. A
   node that EXISTS and has been deliberately emptied is the resort saying
   there is no dinner tonight, and it has to beat the file. */
function fetchMenuNode(){
  return fetch(DB + '/menu.json?v=' + Date.now())
    .then(function(r){ return r.json(); })
    .then(function(m){
      if (m && m.published && m.main && m.main.name) return m;
      if (m && typeof m.published !== 'undefined' && !m.published)
        return { takenDown: true };
      return null;
    })
    .catch(function(){ return null; });
}

/* The committed file is a fallback, not an archive.

   Reported 23 Aug: the Reservations board showed an old menu. menu.json still
   held the menu of the 22nd, because publishing moved into the database and
   nothing has rewritten that file since. Whenever the database had nothing for
   tonight the reader handed back yesterday's dinner with no date on it, and
   every screen that asks this question - the board, the printed sheet, the
   dietary page - believed it.

   Each caller went on to check the date itself, or did not, and that is the
   fault: a reader that can return something stale makes every one of its
   callers responsible for noticing. It checks here now, once. A menu that is
   not for the day being asked about is not an answer to the question. */
function fetchMenuAnywhere(dayKey){
  /* The day being asked about: the caller's, else the page's browsed day, else
     the actual date. Never null. It defaulted to null on a page with no date
     navigation - menu-print.html has none - and null skipped the check
     entirely, so the one page that was showing a stale menu went on showing
     it. A guard that depends on a global the caller may not have is not a
     guard. */
  var want = dayKey ||
             (typeof todayKey === 'function' ? todayKey() : dkey(new Date()));
  return fetchMenuNode().then(function(m){
    if (m && m.takenDown) return null;
    if (m) return m;
    return fetch('menu.json?v=' + Date.now())
      .then(function(r){
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      })
      .then(function(f){
        if (!f || !f.published) return null;
        return dkey(new Date(f.published)) === want ? f : null;
      })
      /* Not null. "Nothing is published tonight" and "I could not find out"
         are different facts and a caller has to be able to tell them apart:
         one is no dinner, the other is a broken app, and a page that says the
         first when it means the second sends somebody to the kitchen to ask
         why there is no menu. Swallowing this to null is exactly the mistake
         the takedown had, one layer up. */
      .catch(function(){ return { failed: true }; });
  });
}

/* ── a dietary that outlives the booking ──────────────────────────────
   A dietary is about the person, not about a night or a reservation. Kept only
   on the booking, a guest who comes back next year arrives with an empty
   record and is asked all over again, having told us once already.

   So it is mirrored to /guests/<customerId>, the Mews customer, which is the
   only identifier that survives a booking ending. customerId has been
   collected on every booking since 18 Aug and this is what it was for.

   The booking keeps its copy and stays the working one: every screen reads it,
   tonight's service depends on it, and a guest record that failed to write
   must not take the evening's answers with it. This is a mirror, not a move,
   and it is deliberately quiet for the same reason.                        */
function rememberDietary(bookingId, diets, dnote){
  if (!bookingId) return Promise.resolve();
  return fetch(DB + '/bookings/' + bookingId + '/pms/customerId.json')
    .then(function(r){ return r.json(); })
    .then(function(cid){
      if (!cid) return;   /* older bookings have none: nothing to key on */
      return fetch(DB + '/guests/' + cid + '.json', {
        method: 'PATCH', headers: { 'Content-Type':'application/json' },
        body: JSON.stringify({ diets: diets || [], dnote: dnote || '',
                               updatedAt: new Date().toISOString() })
      });
    })
    .catch(function(){});
}

/* ── the purpose field ────────────────────────────────────────────────
   "Here for" is a multi select in both forms, so the pages hold it as a list.
   The database validates it as a single string, and one field of the wrong
   type refuses the WHOLE write, so a guest who ticked a reason could not save
   their pre-arrival form at all, and reception could not confirm them from the
   arrivals row. Neither screen said why: the message was the generic could not
   save, which reads as a connection problem.

   Stored as one string from here on. That needs no rules change, so nothing has
   to be pasted into the Firebase console and no guest is locked out while it
   is. Reading accepts either shape, because records written before today are
   already lists and will be for as long as those bookings live.            */
var PURPOSE_SEP = ' \u00b7 ';

function purposeList(v){
  if (Array.isArray(v)) return v.filter(Boolean);
  if (typeof v === 'string' && v.trim())
    return v.split(PURPOSE_SEP).map(function(x){ return x.trim(); }).filter(Boolean);
  return [];
}

function purposeText(v){
  return purposeList(v).join(PURPOSE_SEP);
}

function displayNameOf(user){
  var e = user && (typeof user === 'string' ? user : user.email);
  if (!e) return '';
  var rec = STAFF_RECORDS && STAFF_RECORDS[emailKey(e)];
  if (rec && rec.name) return String(rec.name);
  return String(e).split('@')[0];
}

/* A short tag for a person, for a board where the space is a tile.

   Initials, with the whole name as the fallback for anyone who has only one.
   Ben Davidson is BD, Ana is ANA, Jo is JO. A single letter is not a person
   and two staff whose names start alike would be the same badge, so a one word
   name takes three letters rather than one.

   Fed by shortTagFor below, not called with a stored name. Getting that wrong
   is what made a rename in Settings appear to do nothing. */
function shortNameOf(name){
  var parts = String(name == null ? '' : name).trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '';
  if (parts.length === 1) return parts[0].slice(0, 3).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

/* WHO did something, not what they were called at the time.

   takenBy and doneBy used to store the person's name as it read when the
   button was pressed. A record is a fact about the past, so it kept the old
   name for ever: renaming yourself in Settings changed nothing on any board,
   including your own claims, and looked like the shortening was broken.

   The staff key is stored instead, and the name is looked up when the tile is
   drawn. A rename now shows everywhere at once, on old records as well as new
   ones, and the way names are shortened can change again without rewriting
   anything.

   Records written before this hold a name rather than a key. Those are read as
   the name they hold, which is the best that can be done for them: they will
   not follow a rename, and there is nothing in them that could. */
function shortTagFor(stored){
  var v = String(stored == null ? '' : stored).trim();
  if (!v) return '';
  var rec = STAFF_RECORDS && STAFF_RECORDS[v];
  if (rec && rec.name) return shortNameOf(rec.name);
  /* Not a key we know: either an old record holding a plain name, or somebody
     since removed from Settings. Both read better as what they hold than as
     nothing at all. */
  return shortNameOf(v);
}

/* The full name behind a stored key, for the places with room for one. Same
   fallback as shortTagFor: an old record holding a name reads as that name. */
function fullNameFor(stored){
  var v = String(stored == null ? '' : stored).trim();
  if (!v) return '';
  var rec = STAFF_RECORDS && STAFF_RECORDS[v];
  return (rec && rec.name) ? rec.name : v;
}

/* The key a record should store: stable, and the same key /staff is filed
   under, so the lookup above is a direct hit rather than a search. */
function staffKeyOf(user){
  var e = user && (typeof user === 'string' ? user : user.email);
  return e ? emailKey(e) : '';
}

function roleOf(user){
  var e = user && (typeof user === 'string' ? user : user.email);
  if (!e || !STAFF_RECORDS) return null;
  var rec = STAFF_RECORDS[emailKey(e)];
  var r = normaliseRole(rec && rec.role);
  return isRole(r) ? r : null;
}

/* ── the permission matrix ─────────────────────────────────────
   ROLE_GRANTS above is what the app ships with. /permissions is the manager
   changing their mind, and it wins where it has an opinion.

   Only an explicit true or false counts as an opinion. A missing action, a
   missing role, or a value that is not a boolean all mean "no opinion", and
   the shipped default stands. That is deliberate: adding a new capability to
   ROLE_GRANTS must not silently switch it off for everybody because the
   matrix written last March has never heard of it.

   The manager is never overridable. A stray false against admin, typed in the
   Firebase console at midnight, would lock the only person who can undo it
   out of the page where it is undone. So admin is answered before the matrix
   is consulted at all.

   Matrix and rationale in ROLES.md.                                     */
var PERMISSIONS = null;      /* the /permissions map once loaded, null until then */

/* The actions a manager may hand out, in the order the grid shows them, in
   the words staff use rather than the words the code uses.

   manageStaff is deliberately not here. Handing it out hands out the ability
   to hand things out, which is not a permission, it is a second manager. Do
   that by changing somebody's role, where it is visible in the People list,
   rather than by a tick nobody will ever look at again.                  */
var PERM_ACTIONS = [
  ['resBoard',     'See Reservations'],
  ['editBookings', 'Edit a booking'],
  ['resSheet',     'See the Reservations Sheet'],
  /* Renamed 22 Aug. It was written when tagging was the whole of it; the same
     permission now opens the page that publishes the menu, takes it down and
     tags it, so a manager reading "Tag the menu dietaries" was being told
     about the smallest thing it grants. */
  ['publishMenu',  'Publish and tag the menu'],
  ['cleansBoard',  'See the Cleans board'],
  ['cleansMarks',  'Mark a clean done'],
  ['setJob',       'Change what a villa needs'],
  ['spaBoard',     'See the Spa board']
];

/* The columns. admin is absent because it always has everything, and a column
/* The columns. admin is absent because it always has everything, and a column
   of ticks nobody may untick teaches people the ticks do nothing. manager is
   absent for the same reason: the role IS "everything but manageStaff", and
   the rules refuse the matrix an opinion about it. sync is absent because it
   is a machine with no screen. spa is absent because it is an outside
   contractor: widening what that login can open is a decision for the rules,
   made deliberately, not a tick in a grid.                              */
var PERM_ROLES = ['chef','waiter','housekeeping'];

/* What the app shipped with, asked directly. The grid shows it beside the
   current answer so a manager can see what they have changed.           */
function grantedByDefault(role, what){
  var g = ROLE_GRANTS[normaliseRole(role)];
  return !!(g && g.indexOf(what) > -1);
}

function setPermissions(map){
  PERMISSIONS = (map && typeof map === 'object') ? map : null;
  return PERMISSIONS;
}

function can(role, what){
  var r = normaliseRole(role);
  /* Answered first, and only for a capability that exists: an unknown name is
     a typo, and a typo must not be the thing that grants the run of the app. */
  if (r === 'admin' && ROLE_GRANTS.admin.indexOf(what) > -1) return true;
  var row = PERMISSIONS && PERMISSIONS[what];
  if (row && typeof row[r] === 'boolean') return row[r];
  return grantedByDefault(r, what);
}

/* Where a role should land. Housekeeping opening the app got the Reservations
   board, which they may not see, so their first screen was a refusal. A role
   that cannot see the page it arrived on is a routing problem, not an access
   one: send them to their own board instead of telling them off.        */
var ROLE_HOME = { admin:'tally.html', manager:'tally.html', chef:'tally.html',
                  waiter:'tally.html', housekeeping:'cleaners.html',
                  spa:'spa.html' };
function homeFor(role){ return ROLE_HOME[normaliseRole(role)] || null; }

function setStaffRecords(map){
  STAFF_RECORDS = (map && typeof map === 'object') ? map : {};
  return STAFF_RECORDS;
}

/* Loads /staff once. On a network or permission failure the records stay
   null, which still grants nothing, but it is a DIFFERENT state from
   "signed in and not on the list" and the pages word it differently:
   telling someone to see the manager when the database simply did not
   answer sends them down the hall for nothing.                        */
/* The matrix is fetched here, with the records, rather than by each page.
   Every gate in the app already waits on loadStaff before it decides
   anything, so this is the one place where adding a second read cannot leave
   a page deciding with half the answer.

   A failed matrix read is NOT an error the pages hear about. The records are
   what decide whether somebody is staff at all; the matrix only adjusts what
   a known role may do, and the shipped defaults are a working app. Refusing
   everyone because an override list did not answer would turn a small outage
   into a locked door.                                                    */
function loadStaff(cb){
  var recs = null, err = null;
  fetch(DB + '/staff.json')
    .then(function(r){ return r.ok ? r.json() : Promise.reject(new Error('http ' + r.status)); })
    .then(function(j){ recs = setStaffRecords(j); })
    .catch(function(e){ STAFF_RECORDS = null; err = e; })
    .then(function(){
      return fetch(DB + '/permissions.json')
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(j){ setPermissions(j); })
        .catch(function(){ setPermissions(null); });
    })
    .then(function(){ cb(recs, err); });
}

/* ── staying inside the home screen app ────────────────────────
   A page saved to the home screen opens without Safari's bars, which is the
   whole point of saving it. Tapping an ordinary link from there hands the
   next page back to Safari, bars and all, so the app view lasts exactly one
   screen. Navigating by script instead keeps it inside.

   Only runs in standalone mode, so nothing changes in an ordinary tab. Links
   that leave the site, open a new tab, or do something on the page rather
   than go somewhere are left alone.                                     */
(function(){
  /* navigator.standalone is a Safari property and is undefined in Chrome,
     where a saved page still opens without the bars. Asking only Safari
     meant this did nothing at all on half the phones, which is why the app
     view kept being handed back to the browser.                        */
  function inApp(){
    if (window.navigator && window.navigator.standalone) return true;
    try {
      return window.matchMedia('(display-mode: standalone)').matches ||
             window.matchMedia('(display-mode: fullscreen)').matches ||
             window.matchMedia('(display-mode: minimal-ui)').matches;
    } catch (e){ return false; }
  }
  if (!inApp()) return;
  document.addEventListener('click', function(e){
    var a = e.target;
    while (a && a.nodeName !== 'A') a = a.parentNode;
    if (!a || !a.getAttribute) return;
    var href = a.getAttribute('href');
    if (!href || href.charAt(0) === '#') return;        /* in-page, or an action */
    if (a.target && a.target !== '_self') return;       /* meant for a new tab */
    if (/^(mailto|tel|sms):/i.test(href)) return;
    if (a.host && a.host !== location.host) return;     /* off site, let it go */
    e.preventDefault();
    /* Routed through a replaceable function purely so this can be tested:
       no browser but Safari does the breakout being worked around here, so
       the only checkable part is that the link is taken over at all.   */
    (window.NALA_GO || function(u){ location.href = u; })(a.href);
  });
})();

/* ── notifications ─────────────────────────────────────────────
   A phone subscribes once, from a tap, and the subscription is stored under
   its own login. The sending is done by a worker that holds the signing key:
   nothing secret lives here. The public key below is meant to be public.

   iOS only allows this for a site added to the Home Screen. In an ordinary
   tab the browser reports no support at all, so the toggle says why rather
   than failing silently.                                                 */
var VAPID_PUBLIC = 'BEP_gBL_c7YGzV9EoU8Bv5DeA79I32NUxjGA2atk1239hSBZXEatGYrIfI7nofzLwdVZ1fWw1ycBZ1lWrKlOZGs';
var PUSH_URL = 'https://nala-push.ben-681.workers.dev';

function pushSupported(){
  return !!(window.navigator && 'serviceWorker' in navigator &&
            'PushManager' in window && 'Notification' in window);
}

/* A stable id per phone, so re-subscribing replaces that phone's record
   instead of leaving a dead one behind every time.                      */
function deviceId(){
  var k = 'nala-device';
  try {
    var v = localStorage.getItem(k);
    if (!v){ v = 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2,8);
             localStorage.setItem(k, v); }
    return v;
  } catch (e){ return 'd-nostore'; }
}

function b64ToU8(base64){
  var pad = '='.repeat((4 - base64.length % 4) % 4);
  var s = (base64 + pad).replace(/-/g, '+').replace(/_/g, '/');
  var raw = atob(s);
  var out = new Uint8Array(raw.length);
  for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function subPath(user){
  return '/pushsubs/' + emailKey(user && user.email) + '/' + deviceId() + '.json';
}

/* Whether this phone is currently subscribed. Asked of the browser rather
   than of a saved flag, because the browser is the thing that decides: a
   subscription can be dropped by iOS without telling anyone.            */
function pushState(cb){
  if (!pushSupported()) return cb('unsupported');
  if (Notification.permission === 'denied') return cb('blocked');
  navigator.serviceWorker.getRegistration().then(function(reg){
    if (!reg) return cb('off');
    reg.pushManager.getSubscription().then(function(sub){ cb(sub ? 'on' : 'off'); },
                                          function(){ cb('off'); });
  }, function(){ cb('off'); });
}

function pushOn(user, role, cb){
  if (!pushSupported()) return cb('unsupported');
  navigator.serviceWorker.register('/sw.js').then(function(reg){
    return Notification.requestPermission().then(function(perm){
      if (perm !== 'granted') throw new Error('denied');
      return reg.pushManager.subscribe({
        userVisibleOnly: true,                 /* iOS requires this */
        applicationServerKey: b64ToU8(VAPID_PUBLIC)
      });
    });
  }).then(function(sub){
    var j = sub.toJSON();
    return fetch(DB + subPath(user), {
      method: 'PUT',
      body: JSON.stringify({ endpoint: j.endpoint, keys: j.keys,
                             role: role, at: new Date().toISOString() })
    });
  }).then(function(){ cb('on'); })
    .catch(function(e){ cb((e && e.message === 'denied') ? 'blocked' : 'failed'); });
}

/* Off means gone from the database as well: a record left behind would keep
   the phone on the list and the notification would arrive anyway.        */
function pushOff(user, cb){
  var done = function(){ cb('off'); };
  fetch(DB + subPath(user), { method: 'DELETE' }).catch(function(){}).then(function(){
    if (!pushSupported()) return done();
    navigator.serviceWorker.getRegistration().then(function(reg){
      if (!reg) return done();
      reg.pushManager.getSubscription().then(function(sub){
        if (!sub) return done();
        sub.unsubscribe().then(done, done);
      }, done);
    }, done);
  });
}

/* Tell the worker something happened. Deliberately not awaited by whatever
   called it: a notification that fails must never cost someone their mark,
   which is already saved by the time this runs.                          */
function notifyPush(event, villa, user){
  if (!PUSH_URL || !window.__idToken) return;
  try {
    fetch(PUSH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: window.__idToken, event: event,
                             villa: villa, actor: emailKey(user && user.email) })
    }).catch(function(){});
  } catch (e){}
}

/* ── announcing a published menu ───────────────────────────────
   The chef publishes by pushing a commit, so nothing in the database moves
   and there is nothing for a listener to watch. Something signed in has to
   notice. This used to live inside the Reservations board, which meant the
   manager was told when a manager happened to have that one board open, and
   on a quiet afternoon that is nobody.

   So it lives here and every staff page calls it on load. The chef's own next
   step after publishing is to open the tagging page, which is signed in and
   calls this, so in the normal course of a service the manager is told within
   a minute of the menu going up by the very person who put it up.

   It is still a poll rather than a push, and the honest limit is that if no
   staff device opens anything at all, nobody is told. Closing that needs the
   notification Worker to fire on the commit itself, and the Worker is not in
   this repo.

   Runs once per published menu. The archive row is the record of having
   announced it: if the row already matches, this has been done, and a second
   board loading a minute later reads that and stops. Two boards loading in
   the same second can still both announce, which is a duplicate buzz rather
   than a wrong one, and is not worth a lock to prevent.               */
function announceMenu(){
  /* Guests must not call this. The rules refuse them the write, so the worst
     case is a refused request rather than a wrong notification, but there is
     no reason to make it.                                                */
  if (!window.__idToken) return;
  fetchMenuAnywhere()
    .then(function(m){
      m = m || {};
      var filled = ['bread','entree','main','dessert'].every(function(k){
        return m[k] && m[k].name && m[k].name.trim() !== '';
      });
      /* The menu's own stamp, not Last-Modified: GitHub rewrites that on
         every deploy, so it cannot say when the chef published.         */
      var pub = m.published ? parseISO(m.published) : null;
      var today = dkey(new Date());
      if (!filled || !pub || dkey(pub) !== today) return;
      var main = (m.main && m.main.name) || '';
      return fetch(DB + '/menuhistory/' + today + '.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(existing){
          if (existing && existing.main === main &&
              existing.published === m.published) return;
          return fetch(DB + '/menuhistory/' + today + '.json', {
            method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
              bread:   (m.bread   && m.bread.name)   || '',
              entree:  (m.entree  && m.entree.name)  || '',
              main:    main,
              dessert: (m.dessert && m.dessert.name) || '',
              mainDesc: (m.main   && m.main.desc)    || '',
              published: m.published || '',
              at: new Date().toISOString()
            })
          }).then(function(r){
            /* Only after the row is written. A refused write means the row is
               not there, so the next page to load will try again, and firing
               the notification first would have used up the one announcement
               on a menu that was never recorded. */
            if (!r.ok) return;
            /* No actor. Everywhere else the actor is the person who caused the
               event, so the Worker can avoid telling them about their own tap.
               Here the person who caused it is the chef, and the person whose
               page happened to notice did not do anything. Passing them would
               suppress the notification for the very manager it is meant to
               reach. */
            notifyPush('menu', null, null);
          });
        });
    })
    .catch(function(){});
}

/* Called from here rather than from each page, so a page added later gets it
   without anybody remembering to. Waits for the sign in token, which only
   exists on staff pages: the guest pages load this file too and must never
   run it, and the absence of a token is what keeps them out rather than a
   list of page names that would go stale.

   Gives up after a minute. A page that has not signed in by then is a signed
   out browser sitting on a login screen, and polling it forever is a request
   every second for as long as the tab is open.                          */
(function(){
  var tries = 0;
  /* Checked immediately as well as on the interval. A menu announced two
     seconds after the board is usable is two seconds in which the chef opens
     the tagging page, sees it work, and closes it again. */
  function tick(){
    if (window.__idToken){ announceMenu(); return true; }
    return ++tries > 60;
  }
  if (tick()) return;
  var t = setInterval(function(){ if (tick()) clearInterval(t); }, 1000);
})();

/* The event types and the words a person reads for them. ONE list, two
   readers since 29 Aug: the Settings grid draws a row per entry, and
   notifications.html tells each person which of these will reach their own
   phone. staff.html held the only copy until the second reader arrived.

   The keys must match NOTIFY_DEFAULTS.events below, and notif_suite asserts
   that both ways round - an event with no row here is one nobody can see,
   and a row with no defaults is one that buzzes nobody.                  */
var NOTIFY_EVENTS = [
  ['departed',     'Departed'],
  ['available',    'Possibly available'],
  ['cleaned',      'Cleaned'],
  ['serviced',     'Serviced'],
  ['menu',         'Menu published'],
  ['spaRequest',   'Massage requested'],
  ['spaSuggested', 'Massage suggested'],
  ['spaBooked',    'Massage booked'],
  ['spaCancelled', 'Massage cancelled'],
  ['spaStay',      'Stay changed under a massage']
];

/* The notification settings, written by the app the first time an admin opens
   a board and finds none. Typing this into the console by hand was slow and
   easy to get wrong, and every new event type would mean doing it again.
   Only an admin may write /notify, which the rules enforce, so this quietly
   does nothing for everyone else.                                        */
var NOTIFY_DEFAULTS = {
  on: true,
  hours: { from: '07:30', to: '18:00' },
  events: {
    departed:  { housekeeping:true, admin:true, manager:true, waiter:false, chef:false },
    available: { housekeeping:true, admin:true, manager:true, waiter:false, chef:false },
    cleaned:   { housekeeping:true, admin:true, manager:true, waiter:true,  chef:false },
    serviced:  { housekeeping:true, admin:true, manager:true, waiter:true,  chef:false },
    /* The chef publishes by pushing a commit, not by writing here, so nothing
       in the database changes when a menu goes up. The board notices on its
       next load and fires this. Off for the chef, who already knows: they
       just published it. */
    menu:      { housekeeping:false, admin:true, manager:true, waiter:false, chef:false },
    /* The spa loop's five, the owner's ask of 27 Aug: the earlier each side
       hears, the earlier the guest gets an answer. The masseuse's spa key is
       stored here but his column never renders in the Settings grid - a
       sixth column squeezes it at 320, and his one control is his own
       Notifications toggle - the push Worker reads the stored key all the
       same. spaRequest fires from the desk's asks and from the mews-sync
       sweep that announces a guest's form; spaSuggested is the masseuse's
       counter-offer, off for him because he just made it; spaStay is the
       Worker's alone - a Mews cancellation or date change under a live
       treatment. */
    spaRequest:   { spa:true,  admin:true, manager:true, housekeeping:false, waiter:false, chef:false },
    spaSuggested: { spa:false, admin:true, manager:true, housekeeping:false, waiter:false, chef:false },
    spaBooked:    { spa:true,  admin:true, manager:true, housekeeping:false, waiter:false, chef:false },
    spaCancelled: { spa:true,  admin:true, manager:true, housekeeping:false, waiter:false, chef:false },
    spaStay:      { spa:true,  admin:true, manager:true, housekeeping:false, waiter:false, chef:false }
  }
};

function ensureNotifySettings(role){
  if (normaliseRole(role) !== 'admin') return;
  fetch(DB + '/notify.json')
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(cfg){
      /* Only fill in what is missing. Overwriting would undo the manager's
         own choices every time a board loaded.                          */
      if (!(cfg && cfg.events && cfg.hours)){
        var merged = {
          on:     (cfg && typeof cfg.on === 'boolean') ? cfg.on : NOTIFY_DEFAULTS.on,
          hours:  (cfg && cfg.hours) ? cfg.hours : NOTIFY_DEFAULTS.hours,
          events: (cfg && cfg.events) ? cfg.events : NOTIFY_DEFAULTS.events
        };
        return fetch(DB + '/notify.json', { method:'PUT', body: JSON.stringify(merged) });
      }
      /* A settings node that already stood when an event type was added
         later - the spa five, 27 Aug - holds no key for it, and a keyless
         event buzzes nobody. Fill in ONLY the missing events, each with
         its defaults, so a new queue starts announcing without a console
         paste; an event already present is the manager's own ticks and is
         never touched. */
      var missing = {}, any = false;
      Object.keys(NOTIFY_DEFAULTS.events).forEach(function(ev){
        if (!cfg.events[ev]){ missing[ev] = NOTIFY_DEFAULTS.events[ev]; any = true; }
      });
      if (any) return fetch(DB + '/notify/events.json',
        { method:'PATCH', body: JSON.stringify(missing) });
    })
    .catch(function(){});
}


/* ── the staff menu ──────────────────────────────────────────────────────
   ONE list. Every page carries an empty <div id="navDrop"> and buildNav
   below writes the menu into it, so a link, a label or a group changes
   here and nowhere else. Until 26 Aug the markup was pasted into every
   page - the 28-edit story CLAUDE.md opens with - and adding a page meant
   editing them all and missing one.

   The shape is the owner's, 26 Aug: the boards you work on as plain links,
   then three collapsible submenus - Print, SMS, Settings - where the old
   menu had every page flat under two headings. Seventeen rows was too many
   to scan; nine is not. The SMS pages left the top level the same day.

   `need` is the permission behind each link, the same keys can() answers.
   A link with the wrong key here is offered to roles that cannot open it -
   publish.html and tag.html shipped unlisted and a housekeeper's menu
   offered to publish the dinner menu - and note the keys the suites once
   guarded by name: the sheets need resSheet and cleansBoard, not the
   resBoard/cleanBoard you would guess.

   Each page omits its own link; buildNav reads location for that. Sign out
   is built last, never filtered, and never inside a group: every login has
   to be able to get out. tests/nav_canon.json is the suites' copy of this
   shape - change the menu there too, or the suites will name the drift.  */
var NAV = [
  { href:'front-desk.html',   label:'Front Desk',   need:'editBookings' },
  { href:'tally.html',        label:'Reservations', need:'resBoard'     },
  { href:'cleaners.html',     label:'Cleans',       need:'cleansBoard'  },
  { href:'spa.html',          label:'Spa',          need:'spaBoard'     },
  { href:'publish.html',      label:'Publish Menu', need:'publishMenu'  },
  { group:'Print', items:[
      { href:'list.html',         label:'FOH Sheet',   need:'resSheet'     },
      { href:'housekeeping.html', label:'Clean Sheet', need:'cleansBoard'  },
      { href:'registration.html', label:'Arrivals',    need:'editBookings' },
      { href:'menu-print.html',   label:'Menu',        need:'resSheet'     },
      { href:'past-menus.html',   label:'Past Menus',  need:'resBoard'     } ] },
  { group:'SMS', items:[
      { href:'invitations.html',  label:'Invitations', need:'editBookings' },
      /* "SMS" is the heading, so the row does not repeat it - the Print
         group's "Menu" pattern. */
      { href:'arrivals-sms.html', label:'Pre-arrival', need:'editBookings' } ] },
  { group:'Settings', items:[
      { href:'staff.html', label:'General', need:'manageStaff' },
      { href:'tag.html',   label:'Dietary', need:'publishMenu' },
      /* Admin only, like General and Pages: the flags an admin defines here
         are ticked on the front desk sheet by admins alone. */
      { href:'flags.html', label:'Flags',   need:'manageStaff' },
      { href:'pages.html', label:'Pages',   need:'manageStaff' } ] },
  /* Last, below the submenus, and a page of its own since 29 Aug. It was a
     switch inside Settings, which is where an admin looks for it and nowhere
     near where anybody else does: for a masseuse or a housekeeper every other
     row in that group is hidden, so the only control they own sat alone
     behind a collapsed heading named after the one thing they may not do.
     The owner reported it 29 Aug - the masseuse could not find it at all and
     could not turn notifications on.

     No need key, deliberately: everybody subscribes to their own alerts, and
     a login with one board still has a phone. NAV_NEEDS below must therefore
     not record it - see the note there. */
  { href:'notifications.html', label:'Notifications' }
];

/* Which permission opens each link, derived from NAV so the two cannot
   disagree. Kept under its old name because the filter and the suites ask
   this question by it. */
var NAV_NEEDS = (function(){
  var out = {};
  NAV.forEach(function(e){
    /* A link with no permission is left OUT rather than stored as undefined.
       The filter asks `href in NAV_NEEDS` and only then calls can(), so an
       undefined value here would be a question no role can answer true -
       can(role, undefined) is false for admin too - and the row would be
       hidden from everybody. Absent means "not mine to judge", which is the
       behaviour Notifications wants. */
    (e.items || [e]).forEach(function(i){ if (i.href && i.need) out[i.href] = i.need; });
  });
  return out;
})();

/* Writes the menu into #navDrop. Runs at load on every page that has one;
   pages built without a menu (the printed sheets, the guest pages) simply
   have no div and nothing happens. */
var NAV_CHEV = '<svg class="navchev" viewBox="0 0 12 12" width="11" height="11" ' +
  'aria-hidden="true"><path d="M2.5 4.5 L6 8 L9.5 4.5" fill="none" ' +
  'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" ' +
  'stroke-linejoin="round"/></svg>';

function buildNav(){
  var drop = document.getElementById('navDrop');
  if (!drop || drop.getAttribute('data-built')) return;
  drop.setAttribute('data-built', '1');
  var here = location.pathname.split('/').pop() || 'index.html';
  function makeLink(i){
    var a = document.createElement('a');
    a.href = i.href;
    a.textContent = i.label;
    return a;
  }
  NAV.forEach(function(e){
    if (!e.group){
      if (e.href !== here) drop.appendChild(makeLink(e));
      return;
    }
    var items = e.items.filter(function(i){ return i.href !== here; });
    if (!items.length) return;
    var wrap = document.createElement('div');
    wrap.className = 'navgroup';
    var head = document.createElement('button');
    head.type = 'button';
    head.className = 'navgrp';
    head.setAttribute('aria-expanded', 'false');
    head.innerHTML = '<span>' + e.group + '</span>' + NAV_CHEV;
    /* stopPropagation, because every page closes the menu on a document
       click: opening a submenu must not be the tap that shuts the menu. */
    head.onclick = function(ev){
      ev.stopPropagation();
      var open = wrap.className.indexOf('open') > -1;
      wrap.className = open ? 'navgroup' : 'navgroup open';
      head.setAttribute('aria-expanded', open ? 'false' : 'true');
    };
    var sub = document.createElement('div');
    sub.className = 'navsub';
    items.forEach(function(i){ sub.appendChild(makeLink(i)); });
    wrap.appendChild(head);
    wrap.appendChild(sub);
    drop.appendChild(wrap);
  });
  /* Wired here, not in the pages: sixteen copies of this handler lived in
     the pages until 26 Aug, in two flavours - only the Cleans board and
     Settings remembered to unsubscribe push first. One copy now, the
     careful flavour, for every page. */
  var so = document.createElement('a');
  so.href = '#'; so.className = 'signout'; so.id = 'navSignout';
  so.textContent = 'Logout';
  so.onclick = function(ev){
    ev.preventDefault();
    var u = window.NALA_USER || null;
    try { u = firebase.auth().currentUser || u; } catch (ex){}
    var go = function(){ if (window.NALA_SIGNOUT) NALA_SIGNOUT(); else location.reload(); };
    /* Unsubscribe first, while the token is still valid enough to delete
       the record. If it fails, sign out anyway: being stuck signed in
       would be the worse outcome. */
    if (u && typeof window.pushOff === 'function') window.pushOff(u, go);
    else go();
  };
  drop.appendChild(so);
}
buildNav();

function navFilterShared(role){
  var drop = document.getElementById('navDrop');
  if (!drop) return;
  var links = drop.getElementsByTagName('a');
  for (var i = 0; i < links.length; i++){
    if (links[i].className.indexOf('signout') > -1) continue;
    var href = (links[i].getAttribute('href') || '').split('?')[0];
    /* An unlisted link is left alone rather than hidden. Hiding by default
       would make every new menu entry invisible until somebody remembered
       to add it here, and the failure would look like the link was broken. */
    if (!(href in NAV_NEEDS)) continue;
    links[i].style.display = can(role, NAV_NEEDS[href]) ? '' : 'none';
  }
  hideEmptyGroups(drop);
  navActionBadges(role);
}

/* ── treatment hours ─────────────────────────────────────────
   Nine to five on the half hour, the owner's numbers, 25 Aug. The Spa board
   and the front desk read this list; the guest form keeps its own copy
   because a guest page never loads this file, and BOTH copies are asserted
   against tests/slots.json - the phone_cases.json pattern. The database
   rules hold the same range. Change the hours in the table first.       */
var SPA_SLOTS = (function(){
  var out = [];
  for (var h = 9; h <= 17; h++){
    out.push((h < 10 ? '0' : '') + h + ':00');
    if (h < 17) out.push((h < 10 ? '0' : '') + h + ':30');
  }
  return out;
})();
function spaSlotLabel(t){
  if (!t) return '';
  var p = String(t).split(':'), h = +p[0];
  return (h % 12 || 12) + ':' + p[1] + ' ' + (h < 12 ? 'am' : 'pm');
}
/* The treatment lengths, on the same terms as the slots: one list here for
   the staff pages, a forced copy on the guest form, both pinned to
   tests/slots.json. label is what the guest reads, short is what a tile
   wears, and the price key is what /spasettings stores against it.      */
var SPA_DURS = [
  { m: 60,  label: '1 hour',    short: '1 hr'   },
  { m: 90,  label: '1.5 hours', short: '1.5 hr' },
  { m: 120, label: '2 hours',   short: '2 hr'   }
];
function spaDur(m){
  for (var i = 0; i < SPA_DURS.length; i++)
    if (SPA_DURS[i].m === +m) return SPA_DURS[i];
  return null;
}

/* The way back from what a guest or the desk stored: the label itself, a
   24 hour HH:MM, or a bare H:MM that only fits the afternoon (a guest
   writing 2:00 means 2pm; one writing 10:00 already matches the morning).
   Anything else - "afternoon", "before dinner" - is a wish, not a slot,
   and returns null rather than a guess.                                 */
function spaSlotFromText(s){
  s = String(s || '').trim().toLowerCase();
  if (!s) return null;
  for (var i = 0; i < SPA_SLOTS.length; i++)
    if (SPA_SLOTS[i] === s ||
        spaSlotLabel(SPA_SLOTS[i]).toLowerCase() === s) return SPA_SLOTS[i];
  var m = s.match(/^([0-9]{1,2})[:.]([0-5][0-9])\s*(am|pm)?$/);
  if (!m) return null;
  var h = +m[1];
  if (m[3] === 'pm' && h < 12) h += 12;
  var t = (h < 10 ? '0' : '') + h + ':' + m[2];
  if (SPA_SLOTS.indexOf(t) > -1) return t;
  if (!m[3] && h < 12){
    t = (h + 12) + ':' + m[2];
    if (SPA_SLOTS.indexOf(t) > -1) return t;
  }
  return null;
}

/* ── the action icon ─────────────────────────────────────────
   A number beside a menu entry meaning: something in there waits on you.
   Never stored - it is recomputed from the queue it counts on every page
   load, which is exactly why it "stays until the action is done" without
   anything having to remember to clear it. Owner's naming, 25 Aug, first
   carried by Spa: suggestions the masseuse has made that the desk has not
   yet put to the guest. Add an entry to NAV_ACTIONS for the next feature
   that earns one.

   The fetch rides auth.js's queue, so it waits for a login like every
   other database read, and a failed count is no badge rather than an
   error: the menu must never break because a queue could not be asked. */
var NAV_ACTIONS = [
  { href: 'spa.html', need: 'spaBoard', count: function(cb){
      if (typeof DB === 'undefined') return;
      fetch(DB + '/spa.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(spa){
          /* Two queues wait on the desk: suggestions to put to the guest,
             and declines the guest has not yet been told about - a told
             decline carries its stamp and stops counting, 25 Aug. A stale
             record whose day has passed stops chasing too: nobody can act
             on last Tuesday. */
          var today = dkey(new Date()), n = 0;
          Object.keys(spa || {}).forEach(function(id){
            Object.keys(spa[id] || {}).forEach(function(tid){
              var r2 = spa[id][tid] || {};
              var d = r2.status === 'suggested' ? r2.day
                                                : (r2.reqDay || r2.day);
              if (d && d < today) return;
              if (r2.status === 'suggested') n++;
              else if (r2.status === 'declined' && !r2.told) n++;
            });
          });
          cb(n);
        }).catch(function(){});
  } }
];
var NAV_BADGED = {};       /* one count per entry per page load */
function navActionBadges(role){
  var drop = document.getElementById('navDrop');
  if (!drop) return;
  NAV_ACTIONS.forEach(function(a){
    if (NAV_BADGED[a.href] || !can(role, a.need)) return;
    var links = drop.getElementsByTagName('a'), link = null;
    for (var i = 0; i < links.length; i++){
      if ((links[i].getAttribute('href') || '').split('?')[0] === a.href){
        link = links[i]; break;
      }
    }
    if (!link) return;               /* the entry's own page omits its link */
    NAV_BADGED[a.href] = true;
    a.count(function(n){
      if (!n) return;
      if (link.className.indexOf('hasact') < 0) link.className += ' hasact';
      var b = document.createElement('span');
      b.className = 'navbadge';
      b.textContent = n > 9 ? '9+' : String(n);
      link.appendChild(b);
    });
  });
}

/* A submenu with nothing in it. A role that may open none of the printed
   sheets would otherwise get a Print submenu that opens onto nothing: a
   promise of something that is not there, which reads as a page that failed
   to load rather than as a thing this login cannot do. The whole group goes,
   header and all. Notifications carries no permission, so Settings stands
   for every login: a housekeeper subscribes to her own alerts. */
function hideEmptyGroups(drop){
  var groups = drop.querySelectorAll('.navgroup');
  for (var i = 0; i < groups.length; i++){
    var links = groups[i].querySelectorAll('a'), any = false;
    for (var j = 0; j < links.length; j++){
      if (links[j].style.display !== 'none'){ any = true; break; }
    }
    groups[i].style.display = any ? '' : 'none';
  }
}
window.NALA_NAVFILTER = navFilterShared;

/* Pages that never filtered their own menu get it applied for them. Pages
   that call it themselves are unaffected: running twice is harmless. */
(function(){
  var tries = 0;
  var t = setInterval(function(){
    if (++tries > 60) { clearInterval(t); return; }
    if (!window.NALA_ROLE) return;
    navFilterShared(window.NALA_ROLE);
    clearInterval(t);
  }, 250);
})();

/* ── what a save says back ───────────────────────────────────
   One save, one visible answer.

   Before 27 Aug six surfaces - the desk, both tallies, spa, staff and the
   guest's own confirm - wrote to the database with nothing happening on
   screen: no press, no wait, no word when it landed. The writes are
   optimistic and roll back on failure, which is good discipline and is
   exactly why nobody noticed: the board redrew, so the button never had to
   say anything. On a slow connection that leaves somebody holding a dead
   looking control, and a second tap wrote a second time.

   Five other pages had each hand written their own version of the answer -
   templates, flags, tag, publish, prearrival, arrivals-sms - which is why
   they had all drifted apart. This is that answer, once.

       saveFeedback(btn, write, opts)

   btn    the button that was pressed
   write  a function returning a promise for the write
   opts   busy  label while writing               default 'Saving'
          done  label once it lands               default 'Saved'
          hold  ms to hold Saved before then()    default 0
          then  runs after a successful write - close the sheet, re-render
          fail  an element to carry the red line, or a function(message)

   Returns a promise that never rejects. The button and the fail line have
   already said what happened; a caller that also had to catch would be a
   second report of one event.

   The button RESTS at Saved - the owner's ruling, 27 Aug - until armSave()
   puts it back, which is what an edit does. Never a timer: a label that
   times out goes back to saying Save about a record with nothing left to
   save, which is the same lie as saying nothing at all.                */
/* Which button was pressed. Threading a reference through every call site -
   cleaners alone writes from about forty - is forty chances to miss one, and
   a button added next month would be missed by construction. One capture
   listener instead: the press already knows which button it was, so nothing
   has to be remembered at the far end. Capture phase, because several of
   these handlers redraw or close their surface and the event never bubbles
   back up to here.                                                       */
var SAVE_PRESSED = null;
function pressedButton(){ return SAVE_PRESSED; }
document.addEventListener('click', function(e){
  var t = e.target;
  SAVE_PRESSED = (t && t.closest) ? t.closest('button') : null;
}, true);

function saveFeedback(btn, write, opts){
  opts = opts || {};
  /* A caller with no button still gets the rollback and the red line: the
     button is how this SAYS what happened, not how it knows.            */
  if (btn){
    if (btn.__saving) return Promise.resolve(null);    /* the second tap */
    /* innerHTML rather than the label: several of these buttons carry a
       tick or a count inside them, and textContent would restore the words
       having eaten the markup.                                          */
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
      btn.textContent = opts.done || 'Saved'; /* stays disabled: nothing to save */
    }
    if (opts.then){
      /* The hold is the green being seen. With no button there is no green,
         so there is nothing to wait for.                                */
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

/* An edit means there is something to save again. Harmless on a button that
   is not resting at Saved, so it can be called from anything that changes
   the record.

   Nothing calls this yet, and that is not an oversight. The four boards
   wired on 27 Aug all close their sheet once the write lands, so none of
   them rests at Saved. The surfaces that DO stay open - templates, flags,
   tag - each still wear their own button dress, and the green belongs to
   .btn; converting a page's dress is the per-page pass those are queued
   for (BUTTONS-AUDIT.md), and this is the half of the ruling waiting for
   them, so the first one across does not write it again.               */
function armSave(btn){
  if (!btn || btn.__saving) return;
  if (!btn.classList.contains('saved')) return;
  btn.classList.remove('saved');
  btn.disabled = false;
  if (btn.__rest !== undefined) btn.innerHTML = btn.__rest;
}

function saveFailSay(target, msg){
  if (!target) return;
  if (typeof target === 'function'){ target(msg); return; }
  target.textContent = msg || '';
  if (target.classList) target.classList.toggle('show', !!msg);
}

/* Two failures a person acts on differently: the database refused the write,
   which is a permission and needs the manager, and the write never arrived,
   which needs another go. Anything else is the second one.              */
function saveFailWords(e){
  var m = '' + (e && (e.message || e));
  if (/rejected|denied|permission|401|403/i.test(m))
    return 'The change was not allowed - tell the manager.';
  return 'Not saved - check the connection and try again.';
}
