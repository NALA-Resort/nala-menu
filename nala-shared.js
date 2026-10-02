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

/* A moment as staff read it: "Sun 27 Sep 3:10pm" - the short day the
   Pre-arrival SMS rows print, then timeOf's clock. The day is the PARSED
   stamp's, in the device's zone, never the ISO string's first ten
   characters: those are the UTC day, and in Brisbane anything before 10am
   is still the day before in UTC, so a slice dates every morning's stamp a
   day early (CLAUDE.md rule 7). Empty for a stamp that does not parse, so
   a caller leaves the words out rather than printing "Invalid Date".

   Held together by non-breaking spaces: a narrow card breaks the line
   BEFORE a stamp, never inside it - "Completed by guest Tue 22 Sep" over
   "8:10am" was the first build at 390. A time or a date is right or it is
   useless (STYLEGUIDE.md, the trim rule), and half of one on each line is
   neither. */
function stampOf(iso){
  var d = parseISO(iso); if (!d) return '';
  return [['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()], d.getDate(),
          ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov',
           'Dec'][d.getMonth()], timeOf(iso)].join('\u00a0');
}

/* the one date format: Wd Dth Mon (see STYLEGUIDE.md) */
function dateLabel(d){
  var days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  var mo=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return days[d.getDay()]+' '+ord(d.getDate())+' '+mo[d.getMonth()];
}

/* ── the dinner time ───────────────────────────────────────────
   The bookable seatings, 5pm to 8pm every quarter hour, and the ONE reading
   of a stored time. A booking stores 24h "17:30" (or no field at all - every
   booking made before 8 Sep has none, and no time is a valid answer); every
   screen renders it through dinnerTimeLabel, so the board and the printed
   sheet cannot disagree about what half past five looks like. */
var DINNER_TIMES = (function(){
  var out = [];
  for (var m = 17*60; m <= 20*60; m += 15)
    out.push(String(Math.floor(m/60)).padStart(2,'0')+':'+String(m%60).padStart(2,'0'));
  return out;
})();
/* "17:30" -> "5:30"; anything else -> "", so a missing or garbage time reads
   as no time rather than as text on a kitchen sheet. The pm is left to the
   caller: the sheet's picker says "5:30 pm", the row and the printed sheet
   say "5:30" - every seating is an evening. */
function dinnerTimeLabel(t){
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(t || '')) return '';
  var h = +t.slice(0,2);
  return (((h + 11) % 12) + 1) + ':' + t.slice(3);
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
  /* Dashes a phone or a document typed (the en dash, the minus) and a space
     that does not break are punctuation too. */
  var s = String(raw == null ? '' : raw).replace(/[\s().\-\u2010-\u2015\u2212]/g, '');
  /* 0011 is Australia's international dial-out and 00 most of the world's:
     both mean the + of E.164. */
  if (/^0011[1-9]\d/.test(s))    s = '+' + s.slice(4);
  else if (/^00[1-9]\d/.test(s)) s = '+' + s.slice(2);
  /* A 0 typed after a country code - "+44 (0)7700 900123", "+64 027..." -
     is that country's trunk prefix, which a number dialled from abroad
     drops. In these countries nothing follows the code with a 0, so taking
     it out is reading the number, not guessing at it. Italy and a few
     others do keep a real 0 there, so this is a list and not a rule; no
     country code begins another, so a prefix names exactly one. Added
     30 Sep, the owner asking for country codes checked properly: "+44
     (0)..." went out to a number that does not exist, "+61 (0)4..." was
     refused. */
  var TRUNK_ZERO = ['61','64','44','353','49','33','31','32','41','43','358','86','91',
                    '81','82','27','971','972','66','62','60','63','84','886','90'];
  for (var i = 0; i < TRUNK_ZERO.length; i++)
    if (s.indexOf('+' + TRUNK_ZERO[i] + '0') === 0){
      s = '+' + TRUNK_ZERO[i] + s.slice(TRUNK_ZERO[i].length + 2); break;
    }
  if (/^04\d{8}$/.test(s))    return '+61' + s.slice(1);   /* the common case */
  /* the plus went missing, and perhaps the national 0 was left in too */
  if (/^610?4\d{8}$/.test(s)) return '+61' + s.slice(-9);
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
   (a completed form needs no number and a dead pencil reads as broken).
   bare leaves the number itself out, for a line that already shows it:
   Chat's row for a number on no booking, whose name is the number. */
function phoneBadgeHTML(raw, showPen, bare){
  raw = String(raw == null ? '' : raw).trim();
  var esc = function(t){ return String(t).replace(/[&<>"]/g, function(c){
    return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c]; }); };
  var h = bare ? '' : '<span class="ph">' + (raw ? esc(raw) : 'no number') + '</span>';
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

/* The reservations a night can need: every booking that departs on or
   after it. A guest asleep on a night leaves after it, so the night's
   villas are all in here, and the read stops growing with every booking
   ever made - /bookings keeps them all and nothing prunes it (2 Oct).
   Asked from the day before, so a departure stored a day early, as a UTC
   date can be, still falls inside.

   The query needs ".indexOn": ["pms/depart"] on /bookings (rules.json).
   Until the rules carry it the database refuses the query, and this reads
   the whole node as it always did. A refused query must never read as no
   bookings: the boards would lose an arriving guest's form, their dinner
   answer and their allergy with it, and nothing would look wrong. */
function fetchBookingsFrom(dateKey){
  function whole(){
    return fetch(DB + '/bookings.json?v=' + Date.now())
      .then(function(r){ return r.ok ? r.json() : null; })
      .catch(function(){ return null; });
  }
  var d = parseDepDate(dateKey);
  if (!d) return whole();
  d.setDate(d.getDate() - 1);
  return fetch(DB + '/bookings.json?orderBy=' + encodeURIComponent('"pms/depart"') +
               '&startAt=' + encodeURIComponent('"' + dkey(d) + '"') + '&v=' + Date.now())
    .then(function(r){ return r.ok ? r.json() : whole(); })
    .catch(function(){ return whole(); });
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
      .catch(function(){ return null; }),
    /* The reservation's own answers, for every occupied villa: one dietary
       list per person, living on the reservation not the night, so the boards
       see it even when the viewed night holds no dinner cell. One read,
       plucked per villa, in place of a fetch per villa: the RTDB REST
       endpoint is HTTP/1.1, so those per-villa reads ran six at a time, and
       this reader is shared by the Dashboard, Reservations, the Front Desk's
       neighbours, the Guest profile and more - so one read here speeds all of
       them. Since 2 Oct only the bookings departing from this night on
       (fetchBookingsFrom, above). A failed read leaves the villas unset and
       the merge falls back to the night, exactly as a failed per-villa read
       did - not a blank board. */
    fetchBookingsFrom(dateKey)
  ]).then(function(res){
    DINNER_CELLS = res[1] || {};
    OPENED_MARKS = res[2] || {};
    var stays = res[0] || {}, all = res[3] || {}, map = {};
    Object.keys(stays).forEach(function(v){
      var id = stays[v] && stays[v].id;
      if (!id) return;
      var b = all[id];
      var p = (b && b.prearrival) ? b.prearrival : null;
      if (p) map[String(v)] = p;   /* unset villa falls back to the night */
    });
    PREARRIVAL_BY_VILLA = map;
    return res[0];
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
  return effectiveEtaOf(PREARRIVAL_BY_VILLA[String(villa)]);
}
/* The same reading, handed the record rather than a villa. The Front Desk
   reads each arrival's prearrival itself and never fills the map above, so
   until 25 Sep its rows read the guest's slot on their own: villa 8 asked
   for before 2pm, reception approved 1pm, and the desk still said Before
   2pm while the cleaners worked to 1pm. */
function effectiveEtaOf(pre){
  pre = pre || {};
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
/* Whether the massage question holds an answer, from BOTH places one can
   live. The form's own yes/no is the guest's opening ask; a record at
   /spa/<booking> is what became of it, and the 27 Aug rule the sheet's
   Wellness lines and the row's lotus already follow - the live spa state
   outranks the form, whose answer stands in only while no record has been
   born from it - holds for the STATE as well. Before 10 Sep it did not:
   a booking whose massage the masseuse had already booked could still
   read "treatments unanswered" at the desk and sit amber for good,
   because the ask had been keyed straight onto the Spa board (or the
   form's answer walked back at the desk after the booking), so no
   wellness boolean existed here while the outcome hung one node away.

   ANY status-bearing record answers it: booked and declined are
   outcomes, suggested and requested are the ask in hand - exactly the
   set the sheet prints and the lotus draws. A malformed entry says
   nothing, as it does to those two readers. */
function massageAnswered(p, spa){
  if (p && (p.wellness === true || p.wellness === false)) return true;
  var r = spa || {};
  return Object.keys(r).some(function(tid){
    var t = r[tid];
    return !!(t && typeof t === 'object' && t.status);
  });
}

function mandatoryAnswered(p, stay, spa){
  if (!p) return false;
  var dinner  = p.dining === true || p.dining === false;
  var dietary = !!p.noDiets ||
                (Array.isArray(p.diets) ? p.diets.length > 0 : !!p.diets);
  return dinner && dietary &&
         (massageAnswered(p, spa) || oneNightStay(stay));
}

/* Completed wants all three: the stamp, an answer behind it, and the
   mandatory answers still standing. Any one of them missing and it is not
   complete, whatever the record says it is.

   Checked on every read rather than trusted from the stamp, which is what
   makes this self healing. The old check in demanded dinner and dietary but
   never the massage, so it could stamp a multi night booking complete with
   the treatment question unasked - and that booking reads incomplete here
   from the moment this ships, with nothing to run and nothing to repair. */
/* spa is the booking's /spa/<id> node, so the massage answer can be read
   from the outcome as well as the ask - see massageAnswered above. It
   fills only the massage slot of the mandatory three: records at /spa
   alone never make a form look started, and completed still wants the
   stamp. Every reader passes it - the Front Desk holds it per row, the
   Dashboard and Pre-arrival SMS read the node whole - because a reader
   without it is a second, stricter reading of one state, which is how
   two boards came to disagree about villa 17. */
/* Arrived: Front Desk's checkedInAt stamp, read one way. Front Desk is the
   screen that writes it; dashboard.html and front-desk.html each carried
   this line until 12 Sep, when the Guest Profile became a third reader -
   the consolidation the dashboard's own comment scheduled for exactly
   this moment. */
function isArrived(p){ return !!(p && p.checkedInAt); }

function formState(p, stay, spa){
  if (p && p.at && guestAnswered(p) && mandatoryAnswered(p, stay, spa))
    return 'completed';
  return guestAnswered(p) ? 'incomplete' : 'notstarted';
}

/* The form's moments, a date and a time on each, as the open cards say
   them - the owner's rulings of 28 Sep, taken one question at a time:

     Opened Fri 25 Sep 7:10pm              the FIRST opening, firstOpenedAt
     Completed by guest Sat 26 Sep 2:08pm  `at`, and who: completedBy
     Last opened Sat 26 Sep 3:49pm         the LATEST opening, openedAt

   IN TIME ORDER, so the card reads as what happened: a form the desk
   completed before the guest ever looked reads Completed, then Opened, and
   is not reversed. Open cards only, in grey ("a secondary type of
   information"): the Front Desk summary and form and the Guest Profile
   carry it, and a closed card - a Front Desk row, a Pre-arrival SMS row -
   never does.

   Last opened is said only when it is a different minute from the first:
   a guest who came once has one opening. A record with no first opening
   says its one stamp as Last opened, because that is all it is - every
   visit moved openedAt until 28 Sep, and a record opened before the first
   was kept, or before the rules paste, has no first to say.

   Completed is said ONLY when formState says completed: a record can hold
   `at` while the state reads incomplete (the villa 17 record, or one
   stamped before 28 Aug's three states), and quoting it there would be a
   second reading of one state. Who is the guest's Send or the desk's Mark
   as completed; a form completed before completedBy existed, or before the
   rules paste, is a plain Completed rather than a guess. */
var FORM_WHO = { guest: 'Completed by guest', desk: 'Completed at the desk' };
function formStamps(p, stay, spa){
  if (!p) return [];
  var lines = [], first = stampOf(p.firstOpenedAt), last = stampOf(p.openedAt);
  if (first) lines.push({ t: parseISO(p.firstOpenedAt), s: 'Opened ' + first });
  if (formState(p, stay, spa) === 'completed' && stampOf(p.at))
    lines.push({ t: parseISO(p.at),
                 s: (FORM_WHO[p.completedBy] || 'Completed') + ' ' + stampOf(p.at) });
  if (last && last !== first)
    lines.push({ t: parseISO(p.openedAt), s: 'Last opened ' + last });
  /* Stable on a tie: the order pushed, which is the order things happen. */
  return lines.map(function(l, i){ l.i = i; return l; })
    .sort(function(a, b){ return (a.t - b.t) || (a.i - b.i); })
    .map(function(l){ return l.s; });
}

/* Where a booking stands on its PRE-ARRIVAL SMS - the one reader for it, so
   the sending page and the Dashboard cannot disagree about who is still to
   send (CLAUDE.md rule 7). Five kinds, off the same records the desk reads:
   pre is /bookings/<id>/prearrival (the form), invite is /previnvites/<id>
   (the send), fix is /phonefix/<id> (a corrected number that outranks Mews),
   spa is /spa/<id> (the massage outcome, since 10 Sep).

     done     the completed form, whatever route the answers came by - it
              outranks everything, so a guest who finished is never "to send"
     open     opened or part answered: follow-up work, not a send, so it
              outranks a missing number too (a guest mid-form is not nophone)
     nophone  no usable mobile - cannot be sent from here, only fixed
     sent     a delivery not known to have failed; waiting on the form
     ready    STILL TO SEND: never asked, a failed send, or a delivery the
              handset never got (the carrier accepted it but it bounced, so
              it is the sender's problem again)

   arrivals-sms.html builds its band lines from this kind; the Dashboard
   counts the 'ready' ones. Held to tests/presms_cases.json, read by both
   suites - the phone_cases.json pattern, so whichever side drifts fails by
   name. */
function preSmsState(stay, pre, invite, fix, spa){
  if (formState(pre, stay, spa) === 'completed') return 'done';
  var raw = String((fix && fix.phone) || (stay && stay.phone) || '').trim();
  var phone = raw ? normalisePhone(raw) : null;
  if (pre && (pre.openedAt || countGuestAnswers(pre))) return 'open';
  if (!raw || !phone) return 'nophone';
  if (invite && invite.status === 'sent' && invite.delivery !== 'failed')
    return 'sent';
  return 'ready';
}

/* Whether a booking's LAST pre-arrival SMS attempt failed - a send the carrier
   rejected, or one it accepted that the handset never got. It is still 'ready'
   (to send) either way, so preSmsState folds both into that band; this is the
   finer reading the screens use to COLOUR it: a failed attempt is a failure,
   which wears red (the colour law), where a never-asked one is only pending.
   The sending page reddens the row's words; the Dashboard rings the villa's
   pill. One reader so the two cannot disagree about which is which. Held to
   tests/presms_cases.json alongside preSmsState.

   The spa reminder log (/spareminders, 28 Sep) is written by the same
   Worker in the same shape, status and delivery alike, so it is read here
   too rather than through a copy of these two lines. */
function preSmsFailed(invite){
  if (!invite || !invite.status) return false;
  return invite.status !== 'sent' || invite.delivery === 'failed';
}

/* ── key cards ───────────────────────────────────────────────────────
   One table, /cards/<no>, one row per card that exists in the world,
   keyed by the number the encoder reports - the serial belongs to the
   plastic (TTHotel's own behaviour; the owner, 11 Sep). A row is
   { villa, guest, cut, expiry, lost?, by? }. The helper appends a row
   as it cuts a card and removes the row it wipes; the desk flags lost
   and removes by hand. SCREENS COUNT ROWS - the model of 11 Sep - and
   they count through the readers below, held to
   tests/cardstate_cases.json. A request to cut cards lives at /cutrun
   for the minutes the run takes and is never stored with the cards. */

/* When a key card stops opening the door on departure day. One number,
   because the moment a guest's card dies is a fact two systems state:
   the desk quotes it and every card carries it. Written into the card
   as an epoch by cardExpiry, which builds it in the DEVICE's zone -
   staff devices live at the resort, the same assumption every board
   already makes when it says "today". */
var CARD_CHECKOUT_HOUR = 13;   /* 1pm, the owner, 9 Sep - was 11 */

function cardExpiry(dep){
  var d = parseDepDate(dep);
  if (!d) return null;
  return Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate(),
                             CARD_CHECKOUT_HOUR, 0, 0).getTime() / 1000);
}

/* Where ONE card stands - the only judge, all screens. Precedence is
   expired > lost > today > live, because each earlier answer makes the
   later ones moot: an expired card is the Expired list whether or not
   it was lost first, and a lost card's expiry day is not the guest's
   problem. today (expires before the next midnight) is when the 12h
   clock takes over on screen. Cases live in
   tests/cardstate_cases.json - add there, not in a suite. */
function cardState(row, now){
  var exp = (+((row && row.expiry) || 0)) * 1000;
  if (!exp || exp <= now) return 'expired';
  if (row.lost) return 'lost';
  return dkey(new Date(exp)) === dkey(new Date(now)) ? 'today' : 'live';
}

/* The /cards tree as a list, villa order then cut order, junk skipped.
   Every screen walks THIS list rather than the raw tree, so the sort
   and the shape cannot drift between boards. The serial is carried as
   `no` for writes and lookups and never rendered - the wording law. */
function cardRows(tree){
  var out = [];
  Object.keys(tree || {}).forEach(function(no){
    var r = tree[no];
    if (!r || typeof r !== 'object') return;
    out.push({ no: String(no), villa: String(r.villa == null ? '' : r.villa),
               guest: r.guest || '', cut: +r.cut || 0,
               expiry: +r.expiry || 0, lost: !!r.lost, by: r.by || '' });
  });
  out.sort(function(a, b){ return ((+a.villa) - (+b.villa)) || (a.cut - b.cut); });
  return out;
}

/* The rows a villa holds now: everything of theirs not yet expired.
   A lost card is still held against the villa - it is out there opening
   the door - which is why the count the issue drop quotes includes it. */
function cardsHeld(rows, villa, now){
  return (rows || []).filter(function(r){
    return String(r.villa) === String(villa) && cardState(r, now) !== 'expired';
  });
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
/* One wording, both boards. A short form was written on 31 Aug to buy back
   the name's width on the Front Desk row and the owner ruled against it the
   same day: the phrase is "with villa 15" wherever a party is named. Kept as
   one function rather than two so the boards cannot drift into naming a
   party differently, which is why this moved out of the pages on 28 Aug. */
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

/* What the massage mark on a Front Desk row says, in one place because the
   row's icon and the sheet's Wellness lines are the same fact and drifted
   once already: until 27 Aug the sheet read only the form, so a massage the
   masseuse had booked still said "Interested" at the desk.

   Precedence is what the DESK owes, not what happened last. A suggestion
   outranks everything because it is the only one of these the desk has to
   act on: the masseuse has offered another time and somebody must put it to
   the guest. Then booked, then an ask still waiting on the masseuse, and a
   decline last, because a party with one massage booked and one declined is
   a party with a massage.

   No request and no records returns '' and the row draws no mark, the same
   rule the fork follows: an icon for a question nobody asked is an answer we
   do not have. A "no thank you" is not a request either - it is the absence
   of one - so it draws nothing rather than borrowing the declined colour,
   which belongs to a request the resort could not fill. */
function massageState(spa, pre){
  var seen = { suggested:false, booked:false, requested:false, declined:false },
      fromForm = false;
  Object.keys(spa || {}).forEach(function(tid){
    var t = (spa || {})[tid];
    if (!t || typeof t !== 'object' || !t.status) return;
    if (t.source === 'prearrival') fromForm = true;
    if (seen.hasOwnProperty(t.status)) seen[t.status] = true;
  });
  /* The form's ask stands in only while no record has been born from it,
     which is the spa board's own rule for the same ask. */
  if (pre && pre.wellness === true && !fromForm) seen.requested = true;
  if (seen.suggested) return 'sugg';
  if (seen.booked)    return 'done';
  if (seen.requested) return 'wait';
  if (seen.declined)  return 'decl';
  return '';
}

/* The live spa state, in sentences. Until 27 Aug the Front Desk summary
   read only the prearrival answers, so nothing that happened on the Spa
   board - a booking, a suggestion, a decline - ever reached it, and
   reception told a guest their booked massage was "Interested". The
   records at /spa/<booking> are the current truth; the form's answer
   stands in only while no record has been born from it, which is the spa
   board's own rule for the same ask.

   Lifted out of front-desk.html on 23 Sep, when the printed Arrivals card
   (registration.html) made the same mistake the desk had: it read only
   the form, and printed "Interested" under a massage the masseuse had
   already booked. Two renderings of one guest's massages is how paper and
   screen come to disagree, so both pages read this one.

   strong wraps the status word in <b>: the card is read across a desk,
   and on paper there is no colour to carry it. */
function spaDayLabel(key){
  if (isAnyDay(key)) return SPA_ANY_DAY_LABEL;
  var d = parseDepDate(key); if (!d) return String(key == null ? '' : key);
  var D = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  return D[d.getDay()] + ' ' + d.getDate();
}
function spaEsc(t){
  return String(t == null ? '' : t).replace(/[&<>"]/g, function(c){
    return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c];
  });
}
function spaStateLines(spa, strong){
  var lines = [], answered = false;
  function st(w){ return strong ? '<b>' + w + '</b>' : w; }
  Object.keys(spa || {}).sort().forEach(function(tid){
    var t = (spa || {})[tid];
    if (!t || typeof t !== 'object' || !t.status) return;
    if (t.source === 'prearrival') answered = true;
    var two = t.qty === 2 ? 'Two massages \u00b7 ' : '';
    var when = (t.day ? spaDayLabel(t.day) : '') +
               (t.time ? ' \u00b7 ' + spaSlotLabel(t.time) : '');
    if (t.status === 'booked')
      lines.push(two + st('Booked') + ' \u00b7 ' + when +
                 (t.manual ? ' \u00b7 approved at the desk' : ''));
    else if (t.status === 'suggested')
      lines.push(two + st('Suggested') + ' ' + when + ' \u00b7 waiting on the guest');
    else if (t.status === 'requested')
      lines.push(two + st('Asked') +
                 (t.reqDay ? ' \u00b7 ' + spaDayLabel(t.reqDay) : '') +
                 (t.reqTime ? ' \u00b7 ' + spaEsc(t.reqTime) : '') +
                 ' \u00b7 waiting on the masseuse');
    else if (t.status === 'declined')
      lines.push(st('Declined') + (t.note ? ' \u00b7 ' + spaEsc(t.note) : '') +
                 (t.told ? ' \u00b7 guest told' : ' \u00b7 let the guest know'));
  });
  return { lines: lines, answered: answered };
}
/* The whole Wellness answer: the live records, the form's ask while no
   record has been born from it, or the form's no. [] means unanswered.
   pre needs only wellness, wellDay and wellTime. */
function wellnessLines(spa, pre, strong){
  var s = spaStateLines(spa, strong), lines = s.lines.slice();
  pre = pre || {};
  if (pre.wellness === true && !s.answered){
    var w = strong ? '<b>Interested</b>' : 'Interested';
    if (pre.wellDay)  w += ' \u00b7 ' + spaDayLabel(pre.wellDay);
    if (pre.wellTime) w += ' \u00b7 ' + spaEsc(pre.wellTime);
    lines.push(w + ' \u00b7 waiting on the masseuse');
  }
  if (!lines.length && pre.wellness === false) lines.push('Not interested');
  return lines;
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

/* Does this dinner cell belong to the booking now in the villa? A cell stamps
   the booking it was written for; when the villa is later held by a DIFFERENT
   booking - Mews moved or renamed one, the room changed hands - the cell is
   somebody else's answer and is not tonight's for whoever is here now.

   The one owner of that fact. It was decided three ways before: the
   Reservations board through dinnerElsewhere, the dining history inline in
   histNight, and the Invitations board and Dashboard not at all - they read
   /dinner/<date>/<villa> raw, so a cell orphaned by a villa change sat an
   unasked new arrival under "answered · set by reception" on the SMS page
   and counted them as a cover on the Dashboard, while Reservations - correctly
   - showed the villa awaiting and the guest was never asked (villa 4, 19 Sep).

   A cell with no booking id is a walk-in or an old staff entry Mews has no
   opinion about, so it stays; a villa with no known booking id likewise cannot
   contradict the cell. Only two known ids that disagree make it stale. */
function cellIsForBooking(cell, bookingId){
  return !(cell && cell.bookingId && bookingId && cell.bookingId !== bookingId);
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
   what the empty villa on the board is telling reception to do.

   Two ways a cell goes stale, and they need different tests. The booking the
   cell was made for now sits in ANOTHER villa: the moved guest, the original
   case. Or THIS villa is now held by a DIFFERENT booking: the room changed
   hands, and without this test the new arrival wore the previous guest's
   dinner answer and dietary note - seen live 3 Sep, after a rename in Mews
   orphaned the cell. A cell whose booking the PMS no longer knows AT ALL is
   deliberately left standing: an empty roomguests can also mean a failed
   read, and "A failed read is not an empty one" (HANDOVER.md).

   The whole list is scanned rather than stopping at the first match, because
   returning on the first one answered about the lowest numbered villa rather
   than the one asked about - the parked "party in two villas loses the higher
   one's dinner" bug, closed here. */
function dinnerElsewhere(cells, villa, roomguests){
  var cell = cells && cells[String(villa)];
  if (!cell || !cell.bookingId) return false;
  var here = (roomguests || {})[String(villa)];
  if (here && here.bookingId && !cellIsForBooking(cell, here.bookingId)) return true;
  var elsewhere = false;
  for (var v in (roomguests || {})){
    var r = roomguests[v];
    if (r && r.bookingId === cell.bookingId){
      if (String(v) === String(villa)) return false;
      elsewhere = true;
    }
  }
  return elsewhere;
}

/* Staff outrank a guest, always. A guest cannot overwrite a booking reception
   made, and this is the only precedence left in the app. */
function dinnerLocked(cell){
  return !!(cell && cell.by === 'staff');
}

/* The answer the guest already gave for tonight, read from their pre-arrival
   form. The owner's ruling of 28 Aug: the form asks about the first night,
   reception never declines to pass an answer on, so it is not theirs to pass
   on - any screen asking "has this villa answered dinner" reads it.

   Read, NEVER written. This is not a second dinner cell and must never be
   saved as one: it is a reading of /bookings/<id>/prearrival, and the real
   cell at /dinner/<date>/<villa> still wins outright the moment anyone sets
   one - every caller checks the cell first. Writing this shape to /dinner
   would turn one fact into two copies, which is the disease this function
   exists to cure (4 Sep: the SMS page and the front desk each read one store
   and told reception different things about the same villa).

   Only on the night they ARRIVE - dateKey is the night being rendered, and
   the gate is the arrival date matching it, because the form asks about the
   first night alone and one answer must not speak for a whole stay. rec is
   whatever night record the caller holds: roomguests entries spell the
   arrival `arrives`, raw /stays entries spell it `arrive`, and both are
   honoured so no caller has to translate.

   Any answer they gave counts, not only a finished form: the guest page
   saves each question as it is left, so an abandoned form still holds real
   answers, and an answer given is a thing the kitchen should know (the same
   ruling). Returns the dinner-cell shape so callers render it exactly as
   they render a cell, plus fromForm so nothing mistakes it for one. */
/* A diner with no villa. Two shapes, because they arrive two ways: a digital
   reply under /responses with no room on it, and a staff-added ext- key under
   /manual. Both are tonight's by definition - an external has no carried
   forward record to confuse theirs with.

   Lived in tally.html's render until 8 Sep, where the Dashboard could not
   reach it, so that page counted the manual shape only and quietly lost every
   externally booked table that came in through a link. `skip` is the
   optimistic cancel set the Reservations board holds while a delete is in
   flight; nothing else has one. */
function externalDiners(responses, manual, skip){
  var out = [], k;
  responses = responses || {}; manual = manual || {}; skip = skip || {};
  for (k in responses){
    var g = responses[k];
    if (g && !g.room && g.status === 'in' && !skip[k] && !manual['extcancel-' + k])
      out.push({ key:k, src:'digital', g:g });
  }
  for (k in manual){
    if (k.indexOf('ext-') !== 0) continue;
    if (manual[k].status !== 'in') continue;
    out.push({ key:k, src:'manual', g:manual[k] });
  }
  return out;
}

/* One head unless the record says otherwise. A dining row with no pax is a
   person who has said yes, so it counts as one, not as nought. */
function dinerPax(g){ return (g && +g.pax) || 1; }

/* ── external guests invited by SMS (28 Sep) ──────────────────────
   Somebody from outside the resort rings for dinner. Invitations' External
   guests drop-down sends them tonight's menu, and the Worker creates their
   booking: the External reservation Reservations' Add + makes, at
   /manual/<date>/ext-<token>, with source 'invite' and status 'awaiting'
   until they accept ('in') or decline ('out') from the link. Once 'in' it is
   an ordinary external diner and externalDiners above counts it like any
   other; until then it is nobody's cover. The send itself is recorded at
   /extinvites/<date>/<key>, apart from the villas' /invites.

   Two boards draw these and the Dashboard counts them, so the reading is
   here, once (rule 1): which bookings are invitations, and where one stands.
   tests/extinvite_cases.json holds the states; the Invitations suite runs
   every case through this function. */
function extInvites(manual){
  var out = [];
  for (var k in (manual || {})){
    var g = manual[k];
    if (k.indexOf('ext-') !== 0 || !g || g.source !== 'invite') continue;
    out.push({ key:k, g:g });
  }
  return out;
}

/* Where one invited guest stands. kind is the Invitations band - 'ready' is
   work to do (a text that failed or never arrived), 'sent' is waiting on the
   guest, 'answered' is in or out. `line` is the plain words and `bad` the
   failure's, drawn red; Reservations quotes `bad` under its grey row. */
function extInviteState(g, send){
  g = g || {};
  var pax = dinerPax(g);
  /* The seating reception agreed on the phone, when it agreed one (28 Sep,
     the owner: "It's just missing a time slot"). dinnerTimeLabel is the one
     reading of a stored time; the pm is the caller's, as on the sheets. */
  var seat = dinnerTimeLabel(g.time) ? ' at ' + dinnerTimeLabel(g.time) + ' pm' : '';
  var who = g.by === 'staff' ? 'set by reception'
          : g.at ? 'answered ' + timeOf(g.at) : 'answered';
  if (g.status === 'in')
    return { kind:'answered', in:true, bad:'',
             line:'Accepted · table for ' + pax + seat + ' · ' + who };
  if (g.status === 'out')
    return { kind:'answered', in:false, bad:'', line:'Declined · ' + who };
  var table = 'Table for ' + pax + seat;
  if (send && send.status === 'failed')
    return { kind:'ready', line:table, bad:'send failed ' + timeOf(send.sentAt) +
             (send.error ? ' · ' + send.error : '') };
  if (send && send.delivery === 'failed')
    return { kind:'ready', line:table, bad:'not delivered' +
             (send.deliveryText ? ' · ' + send.deliveryText : '') };
  if (send && send.sentAt)
    return { kind:'sent', bad:'', line:table + ' · sent ' + timeOf(send.sentAt) +
             (send.delivery === 'delivered' ? ' · delivered'
              : send.providerId ? ' · delivery unconfirmed' : '') };
  /* The booking stands but its send record does not: the text went and the
     record failed to save (the Worker says sent-unrecorded). Waiting. */
  return { kind:'sent', bad:'', line:table + ' · invited ' + timeOf(g.invitedAt) };
}

/* The night a booking ARRIVES, matched against the night being rendered. The
   one definition of "arriving tonight", so the pre-arrival form (which asks
   about the first night alone) and the Invitations board (which sets arriving
   guests aside from the send) cannot disagree about which night that is. rec
   is whatever night record the caller holds: roomguests entries spell it
   `arrives`, raw /stays entries spell it `arrive`, and both are honoured.
   parseDepDate, never a string slice: a stay's date is local, and a slice
   would read the wrong day for the resort's pre-10am-UTC working morning. */
function isArrivalNight(rec, dateKey){
  var arr = rec && (rec.arrives || rec.arrive);
  var d = arr ? parseDepDate(arr) : null;
  return !!(d && dkey(d) === dateKey);
}

/* The guest's dinner intent as one reading. pre.dining is the pre-arrival
   answer; the Calendar colours a whole booking by it and formDinnerCell
   states the same in/out for a night, so both read it here rather than each
   testing pre.dining its own way. 'none' is the unanswered case - the
   Calendar's grey - and is never reached through formDinnerCell, which
   returns null before it asks. */
function diningState(pre){
  if (pre && pre.dining === true)  return 'in';
  if (pre && pre.dining === false) return 'out';
  return 'none';
}

function formDinnerCell(villa, pre, rec, dateKey){
  if (!pre || (pre.dining !== true && pre.dining !== false)) return null;
  if (!isArrivalNight(rec, dateKey)) return null;
  return {
    status: diningState(pre),
    pax:    pre.dining ? (pre.pax || rec.adults || 2) : 0,
    room:   String(villa),
    diets:  pre.diets || [],
    nodiet: !!pre.noDiets,
    dnote:  pre.dnote || '',
    note:   pre.note || '',
    by:     'guest',
    fromForm: true
  };
}

/* ── a night gone by: what the villa answered ─────────────────────
   The Reservations board's own order for one villa on one night, for the
   pages that look BACK - the Dining history (Reservations, Guest Profile)
   and both Statistics tabs: the cell, when it is this booking's
   (cellIsForBooking); else, on the night the booking arrived and only
   then, the guest's own form answer (formDinnerCell), which the board
   showed, the kitchen cooked for, and nothing ever writes as a cell - the
   owner's ruling of 28 Aug.

   Until 27 Sep every lookback read the cell alone, so an arrival night
   answered on the form read as not dined: Statistics listed tonight's
   guests as having eaten nothing all week, and a guest on their second
   night had "Dined 0 of 1". The Dashboard's first fault again (CLAUDE.md,
   rule 7), in the pages that remember.

   stay is the raw /stays entry for the villa that night (it spells the
   arrival `arrive`), cell the /dinner cell, pre the booking's prearrival:
   null when it has none, UNDEFINED when it was not read. Then the answer
   is undefined too - but only on the one night the form alone could
   settle, so a lookback reads /bookings/<id>/prearrival for that night
   and no other, and a read that failed stays unknown, never a no. Returns
   the answer in the dinner-cell shape, or null when there was none. */
function nightAnswer(villa, date, stay, cell, pre){
  if (cell && typeof cell === 'object' && cellIsForBooking(cell, stay && stay.id))
    return cell;
  if (!isArrivalNight(stay, date)) return null;
  if (pre === undefined) return undefined;
  return formDinnerCell(villa, pre, stay, date);
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

/* dateKey is OPT-IN. With it, a record that nothing else answers falls back
   to the guest's own pre-arrival form answer for that night (formDinnerCell),
   so the caller agrees with the Reservations board about an arriving guest
   who answered days ago. The printed sheets pass it, so the paper the chef
   holds agrees with the board; so does Publish, whose dietary rings ask who
   is dining tonight - without it a guest the board showed dining rang there
   as unconfirmed (villa 5, 24 Sep). Without it nothing changes, which is
   deliberate: the other callers (Cleans, Housekeeping, Debug) render nights
   other than the one PREARRIVAL_BY_VILLA was last fetched for, and a
   fallback they did not ask for is how a Monday answer would leak into a
   Tuesday board. A caller that wants the form must say which night it is
   rendering, and have called fetchStays for that night. */
function roomRecord(n, responses, manual, roomguests, dinner, dateKey){
  return overlayReservationDiets(
    roomRecordCore(n, responses, manual, roomguests, dinner, dateKey), n);
}
function roomRecordCore(n, responses, manual, roomguests, dinner, dateKey){
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
  /* Nothing about tonight from anyone - so, for a caller that named the
     night, the guest's own form answer, exactly as the Reservations board
     reads it. Below every staff record on purpose: the cell, a response and
     a manual entry all outrank it, so this decides nothing anybody has
     already decided. */
  if (dateKey){
    var form = formDinnerCell(n, PREARRIVAL_BY_VILLA[String(n)], known, dateKey);
    if (form) return withDineProvenance(
      Object.assign({}, known, form, pms, { room:String(n) }), form, known);
  }
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

/* Which clean band a room is in on a day - the Calendar colours the villa
   number by it. Three bands, all off hkClassify plus the day's done flag, so
   the Calendar and the cleaning boards cannot come to disagree about what a
   room is: cleaners.html reads the same kind and the same h.done to letter
   its chips (Cleaned / Clean / Serviced / Pre-arrived).

     inhouse   occupied and staying on - neither a turnaround nor a room
               standing ready, so its own neutral band. Checked first,
               because a serviced stay-over is still occupied.
     dirty     a turnaround or a prep not yet done, or a departure carried
               across midnight and not done - a job standing open.
     cleaned   done, vacant, or nothing the dates can confirm - a room
               ready, or with nothing owed on it. */
function roomCleanState(rec, dateK, hk, left){
  var h = hk || {};
  var kind = hkClassify(rec, dateK, hk, left);
  if (kind === 'svc') return 'inhouse';
  if (h.done) return 'cleaned';
  if (kind === 'clean' || kind === 'pre') return 'dirty';
  if (h.carried && h.departed) return 'dirty';   // a departure clean rolled over
  return 'cleaned';
}

/* How soon an arrival turns a requires-cleaning room into a flagged one on
   the Calendar - ruled two days by the owner, 20 Sep. One number, owned
   here so a change is a change in one place. */
var CLEAN_FLAG_DAYS = 2;

/* Does this arrival fall within the flag window, counting from `from` where
   today is 0 (inclusive both ends)? Midday-anchored through parseDepDate so a
   bare date and a full ISO stamp land the same day and no zone west of UTC
   shifts the count - the date law (CLAUDE.md rule 7). */
function arrivalFlagsClean(arrive, from, days){
  var a = parseDepDate(arrive); if (!a || !from) return false;
  var n = (days == null ? CLEAN_FLAG_DAYS : days);
  var a0 = new Date(a.getFullYear(), a.getMonth(), a.getDate(), 12);
  var f0 = new Date(from.getFullYear(), from.getMonth(), from.getDate(), 12);
  var diff = Math.round((a0 - f0) / 864e5);
  return diff >= 0 && diff <= n;
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
  admin:        ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','manageStaff','spaBoard','tasks','guestReply'],
  /* Everything the admin holds except manageStaff, asked for 25 Aug: a
     management login that runs the whole day without the keys to Settings
     General, Pages or Diagnostics, which are the three manageStaff gates.
     Deliberately a role and not a permission column: handing manageStaff
     out is a second admin, and this is the role for everybody who is
     nearly one. spaBoard rides along because the definition is the admin's
     list, whatever joins it, minus that one key. */
  manager:      ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','spaBoard','tasks','guestReply'],
  /* tasks, 29 Sep: the Tasks page, where each team closes what a guest's
     message became. Every human role holds it; which tasks a login SEES is
     its teams, set per login in Settings > General, and the rules hold the
     same line - a login reads only its own teams' tasks.
     guestReply, 30 Sep: a reply to a guest (the owner: "a toggle in
     settings for a role being able to respond to messages"). The desk's
     roles ship with it, as they did before it was a switch; a team's role
     switched on replies from its own open tasks. The Worker asks it too,
     as mayDo - contact_cases.json "grants" holds the two to one answer. */
  chef:         ['resBoard','resSheet','publishMenu','tasks'],
  waiter:       ['cleansBoard','resBoard','editBookings','resSheet','spaBoard','tasks','guestReply'],
  housekeeping: ['cleansBoard','cleansMarks','tasks'],
  /* The masseuse, an external contractor with one screen: the Spa board and
     nothing else. Like the chef, a real login for a real person, but the
     rules also narrow what the account can READ - see /spa in rules.json -
     because hiding a link is not the same as refusing the data.          */
  spa:          ['spaBoard','tasks'],
  /* A machine account, held by the Mews sync Worker. Deliberately empty: it
     grants nothing in the UI and lands on no page, so a human signing in as
     it gets the "see the manager" message rather than a half working board.
     Its actual permission lives in the rules, which name the role directly
     and let it write only bookings/<id>/pms and stays. Listed here because a
     role that exists in the database and not in the code is what the next
     session trips over.                                                  */
  sync:         [],
  /* The Chat Worker's machine account, 29 Sep: sync's pattern. It
     writes the guests' messages as they arrive and as they go, which the
     rules let it do and nothing else. No screen, so no grants.          */
  contact:      []
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

/* Whether tonight's menu is live for a dinner invitation's link: published,
   and before the midnight that ends its publish day. m is fetchMenuAnywhere's
   answer; a read that failed is not live, and the caller says which it was.
   The Invitations page's own gate until 30 Sep, moved here when Chat's
   templates came to ask the same question: the Worker's backstop allows a
   day's grace, so a morning's send against it alone would link last
   night's menu. */
function menuLive(m, now){
  var pub = m && !m.failed && m.published ? parseISO(m.published) : null;
  if (!pub || isNaN(pub)) return false;
  var expiry = new Date(pub); expiry.setHours(24, 0, 0, 0);
  return (now || new Date()) < expiry;
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
   and it is deliberately quiet for the same reason.

   WHICH person: prearrival.forCustomerId first, the person the answers were
   given for, and only then pms.customerId, the person Mews holds the booking
   for now. The two differ the moment a receptionist re-attributes a
   reservation in Mews, and the answers are personal - the owner's ruling of
   3 Sep - so they must keep following the person who gave them rather than
   whoever now owns the booking. When no stamp exists yet the mirror writes
   one, because this is the moment an answer is being given and the booking's
   current person is exactly who it is for; quiet, since until the rules
   paste the field is refused and keying on pms.customerId is yesterday's
   behaviour, not a failure. */
function rememberDietary(bookingId, diets, dnote){
  if (!bookingId) return Promise.resolve();
  /* Only the halves the caller actually holds. The board's editors send a
     dnote only when one exists, and a PATCH that filled the gap with '' was
     erasing the person's standing note on every note-less save. An empty
     string given ON PURPOSE still clears: undefined means "not my field",
     '' means "cleared". */
  var body = { updatedAt: new Date().toISOString() };
  if (diets !== undefined) body.diets = diets || [];
  if (dnote !== undefined) body.dnote = dnote || '';
  return fetch(DB + '/bookings/' + bookingId + '/prearrival/forCustomerId.json')
    .then(function(r){ return r.json(); })
    .catch(function(){ return null; })
    .then(function(stamped){
      if (stamped) return stamped;
      return fetch(DB + '/bookings/' + bookingId + '/pms/customerId.json')
        .then(function(r){ return r.json(); })
        .then(function(cid){
          if (cid){
            fetch(DB + '/bookings/' + bookingId + '/prearrival.json', {
              method: 'PATCH', headers: { 'Content-Type':'application/json' },
              body: JSON.stringify({ forCustomerId: cid })
            }).catch(function(){});
          }
          return cid;
        });
    })
    .then(function(cid){
      if (!cid) return;   /* older bookings have none: nothing to key on */
      return fetch(DB + '/guests/' + cid + '.json', {
        method: 'PATCH', headers: { 'Content-Type':'application/json' },
        body: JSON.stringify(body)
      });
    })
    .catch(function(){});
}


/* ── dining history ───────────────────────────────────────────
   What a stay has eaten so far: the nights it sat, one a row, and the
   three courses the kitchen served, from /menuhistory - the archive Past
   Menus reads. For the chef planning tonight: "I did steak two nights
   ago, was this guest in that night?"

   It follows the BOOKING through /stays, not the villa: a guest moved
   mid-stay carries their nights with them, and a cell stamped with a
   different booking id is a different party's answer, not theirs. Reads
   only, on demand, so it costs nothing until somebody asks.

   Lived in tally.html until 12 Sep, when the Guest Profile became its
   second reader - the rule 3 moment, so the copy moved here whole. The
   viewed date arrives as a parameter because the two readers hold their
   own idea of "today". */
var HIST_MAX = 14;     /* the fortnight the roomguests look-back already uses */

function histNights(known, view){
  var a = known && known.arrives ? parseDepDate(known.arrives) : null;
  if (!a) return [];
  var from = dkey(a), nights = [];
  var d = new Date(view); d.setDate(d.getDate() - 1);
  while (nights.length < HIST_MAX && dkey(d) >= from){
    nights.push(dkey(d));
    d.setDate(d.getDate() - 1);
  }
  return nights;
}

/* A failed read is not an empty one - the standing caution. A refusal or a
   dropped connection comes back marked, so a night that could not be read
   says so rather than reporting that the guest never dined. */
function histGet(path){
  return fetch(DB + path + '.json?v=' + Date.now())
    .then(function(r){
      if (!r.ok) return { ok:false };
      return r.json().then(function(d){ return { ok:true, data:d }; });
    })
    .catch(function(){ return { ok:false }; });
}

/* The dish, not the garnish: the chef writes "Lamb rump, smoked eggplant"
   and the table has three columns of 90px, so everything from the first
   comma stays in the kitchen. The same reading Statistics leans on. */
function dishShort(v){
  return String(v == null ? '' : v).split(',')[0].trim();
}

function histNight(date, id){
  return Promise.all([
    histGet('/stays/' + date),
    histGet('/dinner/' + date),
    histGet('/menuhistory/' + date)
  ]).then(function(r){
    var row = { date: date };
    if (!r[0].ok || !r[1].ok){ row.failed = true; return row; }
    var stays = r[0].data || {};
    var villa = null;
    for (var v in stays){
      if (stays[v] && stays[v].id === id){ villa = v; break; }
    }
    if (!villa) return row;   /* stays holds no villa for this booking that night */
    /* The night's answer as the board read it: the cell - somebody else's
       never becomes this guest's history - else, on the arrival night, the
       guest's own form, read only when that is the night being asked. */
    var cell = (r[1].data || {})[villa], stay = stays[villa];
    var ans = nightAnswer(villa, date, stay, cell);
    return (ans !== undefined ? Promise.resolve(ans)
      : histGet('/bookings/' + id + '/prearrival').then(function(p){
          return p.ok ? nightAnswer(villa, date, stay, cell, p.data || null)
                      : undefined;
        })
    ).then(function(ans){
      if (ans === undefined){ row.failed = true; return row; }
      if (!ans || ans.status !== 'in') return row;
      row.dined = true;
      var m = (r[2].ok && r[2].data) || null;
      if (m && ['entree','main','dessert'].some(function(k){ return dishShort(m[k]); }))
        row.menu = { entree: dishShort(m.entree), main: dishShort(m.main),
                     dessert: dishShort(m.dessert) };
      else if (!r[2].ok) row.menuFailed = true;
      return row;
    });
  });
}

/* Its own escaper rather than a page's: both reading pages define esc, but
   each page's own, and a shared function must not depend on whichever copy
   the page happened to write. */
function histEsc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); }

/* Only the nights they sat - the owner's ruling, 7 Sep: a missed night is
   noise on a busy page, and the summary line already carries the count. */
function histRowsHTML(rows){
  var dined = rows.filter(function(r){ return r.dined; });
  var failed = rows.filter(function(r){ return r.failed; }).length;
  var h = '<div class="hist-sum">Dined ' + dined.length + ' of ' + rows.length +
          (rows.length === 1 ? ' night so far' : ' nights so far') + '</div>';
  if (dined.length){
    h += '<table class="htab">' +
         '<tr><th></th><th>Entr\u00e9e</th><th>Main</th><th>Dessert</th></tr>' +
         dined.map(function(row){
           var d = parseDepDate(row.date);
           var day = d
             ? ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][d.getDay()] + ' ' + d.getDate()
             : row.date;
           var cells = row.menu
             ? ['entree','main','dessert'].map(function(k){
                 return '<td>' + histEsc(row.menu[k]) + '</td>';
               }).join('')
             : '<td class="none" colspan="3">' +
               (row.menuFailed ? 'Menu could not be read' : 'Menu not recorded') +
               '</td>';
           return '<tr><td class="hd">' + histEsc(day) + '</td>' + cells + '</tr>';
         }).join('') +
         '</table>';
  }
  /* A failed read is not a night not dined, and must never count as one. */
  if (failed)
    h += '<div class="hist-note">' + failed +
         (failed === 1 ? ' night' : ' nights') + ' could not be read</div>';
  return h;
}

/* What each dining-approach key says to staff. The desk's own wording for
   the three keys it defined, plus the 23 Aug rewrite's frequency keys -
   records hold both generations, so every reader must speak both. Lived in
   front-desk.html until 12 Sep, when the Guest Profile became a second
   reader. */
var APPROACH_LABEL = { most:'Dining in most nights', mix:'A mix of in and out',
                       out:'Mostly eating out', few:'A few nights',
                       once:'Probably just once', unsure:'Not sure yet' };

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
  ['spaBoard',     'See the Spa board'],
  ['tasks',        'See their team\u2019s tasks'],
  ['guestReply',   'Reply to guests']
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
/* navigator.standalone is a Safari property and is undefined in Chrome,
   where a saved page still opens without the bars. Asking only Safari
   meant this did nothing at all on half the phones, which is why the app
   view kept being handed back to the browser. Shared since 30 Sep with
   pull to refresh, which only the Home Screen app needs.              */
function inHomeScreenApp(){
  if (window.navigator && window.navigator.standalone) return true;
  try {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.matchMedia('(display-mode: fullscreen)').matches ||
           window.matchMedia('(display-mode: minimal-ui)').matches;
  } catch (e){ return false; }
}
(function(){
  if (!inHomeScreenApp()) return;
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
function notifyPush(event, villa, user, extra){
  if (!PUSH_URL || !window.__idToken) return Promise.resolve(null);
  var msg = { idToken: window.__idToken, event: event,
              villa: villa, actor: emailKey(user && user.email) };
  /* A guest task names its team (29 Sep): the push Worker buzzes that
     team's members rather than a role. */
  if (extra) Object.keys(extra).forEach(function(k){ msg[k] = extra[k]; });
  /* Answers with what the push Worker said, or null when it could not be
     asked: a page that says how the alert went reads it (Chat's tasks,
     1 Oct); every other caller lets it go, as before. */
  try {
    return fetch(PUSH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(msg)
    }).then(function(r){
      return r.json().catch(function(){ return null; })
        .then(function(j){ return r.ok && j ? j : null; });
    }).catch(function(){ return null; });
  } catch (e){ return Promise.resolve(null); }
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
      /* Every course's name AND description, the menu as the guest read it.
         Until 27 Sep only the main's description was kept, so Past Menus
         showed three bare dish names under one described main, and what
         was never archived cannot be shown for those nights. */
      var row = { published: m.published || '' };
      ['bread','entree','main','dessert'].forEach(function(k){
        row[k]          = (m[k] && m[k].name) || '';
        row[k + 'Desc'] = (m[k] && m[k].desc) || '';
      });
      return fetch(DB + '/menuhistory/' + today + '.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(existing){
          var announced = !!(existing && existing.main === main &&
                             existing.published === m.published);
          /* An announced row still missing a description - tonight's, archived
             before descriptions were kept - is rewritten, silently: the
             manager was told about this menu once already. */
          if (announced && Object.keys(row).every(function(k){
                return (existing[k] || '') === row[k]; })) return;
          row.at = new Date().toISOString();
          return fetch(DB + '/menuhistory/' + today + '.json', {
            method:'PUT', headers:{'Content-Type':'application/json'},
            body: JSON.stringify(row)
          }).then(function(r){
            /* Only after the row is written. A refused write means the row is
               not there, so the next page to load will try again, and firing
               the notification first would have used up the one announcement
               on a menu that was never recorded. */
            if (!r.ok) return;
            if (announced) return;   /* a refresh is not a new menu */
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
    spaStay:      { spa:true,  admin:true, manager:true, housekeeping:false, waiter:false, chef:false },
    /* A guest wrote to Chat (29 Sep): the desk, who answer and
       sort it. Fired by the Worker as the message lands. */
    guestMessage: { spa:false, admin:true, manager:true, housekeeping:false, waiter:true, chef:false },
    /* A task made from a guest's message (1 Oct, the owner: "It also
       doesn't have the option to allow task notifications in settings").
       It goes to the people in the task's team; this row says which of
       their roles are told. On for every role to start, the masseuse's
       included, since a team is chosen person by person. */
    guestTask:    { spa:true,  admin:true, manager:true, housekeeping:true,  waiter:true, chef:true }
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


/* ── Chat ─────────────────────────────────────────────
   The staff inbox for guests' messages, SMS and WhatsApp through Twilio.
   Asked for by the owner, 29 Sep, to replace Guest Touch: every guest by
   booking - Upcoming, In-house, Past - and every reply caught here. Built
   from mock-guest-contact.html; GUEST-CONTACT.md is the whole brief and
   the setup. The Worker (worker/guest-contact.js) carries twins of the
   readers it needs, held to the same table, tests/contact_cases.json.

   The data, one fact to a place:
     /contact/<ck>            one guest mobile's thread: phone, lastAt,
                              lastIn, lastInCh, lastInWa, preview, dir,
                              profile, wa (the guest's WhatsApp consent),
                              waBad, optout. Written by the Worker; wa by
                              the desk.
     /contactmsgs/<ck>/<id>   each message, in and out. The Worker writes
                              it; the desk writes only how it was sorted.
     /contactnew/<ck>/<id>    a guest message nobody has sorted yet. Being
                              here IS being new; nothing else says so.
     /tasks/<team>/<id>       what a message became: open, then done.
     /contactsettings/teams/<team>
                              a team: label, off (retired), added, and
                              members/<emailkey>, who does its tasks.
   <ck> is the guest's number in E.164 without its plus, which a Firebase
   key can hold. */

/* The Chat Worker (worker/guest-contact.js), which Chat
   asks to send and Tasks asks for a task's conversation. One address for
   both pages. */
var CONTACT_URL = 'https://nala-contact.ben-681.workers.dev';

/* The SMS pages' sender (worker/send-invites.js): Invitations, Pre-arrival
   SMS and Spa reminders, and since 30 Sep Chat's templates, which go
   through it so the page that owns each text records it as sent. One
   address for the four; it was typed into each of the first three. */
var INVITES_URL = 'https://nala-invites.ben-681.workers.dev';

/* The six teams the owner started with (29 Sep). The key is what the
   database stores; the label is what staff read. The list itself is
   contactTeams below: these six, as Settings names them, and any added. */
var CONTACT_TEAMS = [
  { key:'bar',          label:'Bar' },
  { key:'kitchen',      label:'Kitchen' },
  { key:'housekeeping', label:'Housekeeping' },
  { key:'maintenance',  label:'Maintenance' },
  { key:'spa',          label:'Spa' },
  { key:'frontdesk',    label:'Front desk' }
];

/* The team list, the one reading of it (29 Sep, editable in Settings >
   General, Teams): the six above under whatever name Settings gave them,
   then each team added there, oldest first, from
   /contactsettings/teams/<key>. A team removed there is not deleted but
   retired (off): it takes no new tasks and is offered nowhere, and its
   name stays, so a conversation still says whose a task was. all includes
   the retired, for reading back; without it, only the teams in use.
   Held to tests/contact_cases.json, teams. */
function contactTeams(settings, all){
  var teams = (settings && settings.teams) || {}, out = [];
  CONTACT_TEAMS.forEach(function(t){
    var s = teams[t.key] || {};
    out.push({ key: t.key, label: String(s.label || t.label), off: s.off === true });
  });
  Object.keys(teams).filter(function(k){
    var s = teams[k];
    return /^[a-z]{2,20}$/.test(k) && s && typeof s === 'object' && s.label &&
           !CONTACT_TEAMS.some(function(t){ return t.key === k; });
  }).sort(function(a, b){
    var x = String(teams[a].added || ''), y = String(teams[b].added || '');
    return x < y ? -1 : x > y ? 1 : (a < b ? -1 : 1);
  }).forEach(function(k){
    out.push({ key: k, label: String(teams[k].label), off: teams[k].off === true });
  });
  return all ? out : out.filter(function(t){ return !t.off; });
}
function teamLabel(key, settings){
  var t = contactTeams(settings, true).filter(function(x){ return x.key === key; })[0];
  return t ? t.label : String(key || '');
}

/* The teams one login does tasks for, off /contactsettings. Set per login
   in Settings > General (the owner, 29 Sep): the grounds login can hold
   Maintenance alone while the housekeepers hold Housekeeping. A retired
   team is nobody's. */
function teamsOf(settings, email){
  var key = emailKey(email), teams = (settings && settings.teams) || {};
  return contactTeams(settings).filter(function(t){
    var m = teams[t.key] && teams[t.key].members;
    return !!(m && m[key] === true);
  }).map(function(t){ return t.key; });
}

/* Every open task of the teams named, as { team: { id: task } }: the one
   reading of "open" (29 Sep), which Chat, Tasks, the menu's Tasks
   count and the Dashboard all call, so no two of them can disagree about
   what is still to do. Asked of the database by its index on state, then
   checked here, so a record that is not open never passes for one. A team
   that cannot be read fails the whole read: a count missing a team says
   less than it knows. */
function contactOpenTasks(teams){
  teams = teams || [];
  return Promise.all(teams.map(function(k){
    return fetch(DB + '/tasks/' + k + '.json?orderBy=' + encodeURIComponent('"state"') +
                 '&equalTo=' + encodeURIComponent('"open"') + '&v=' + Date.now())
      .then(function(r){
        if (!r.ok) throw new Error('/tasks/' + k + ' HTTP ' + r.status);
        return r.json();
      })
      .then(function(j){
        var out = {};
        Object.keys(j || {}).forEach(function(id){
          if (j[id] && j[id].state === 'open') out[id] = j[id];
        });
        return out;
      });
  })).then(function(all){
    var map = {};
    teams.forEach(function(k, i){ map[k] = all[i]; });
    return map;
  });
}

/* A guest's thread key: normalisePhone's E.164, less the plus. Null when
   the number is not sendable, and no thread can exist for it. */
function contactKey(raw){
  var e = normalisePhone(raw);
  return e ? e.slice(1) : null;
}

/* WhatsApp's 24 hours, Meta's rule: free text only within a day of the
   guest's last WhatsApp message; after that only approved wording. The
   Worker has a twin and refuses free text outside it. */
var WA_WINDOW_MS = 24 * 60 * 60 * 1000;
function waWindow(lastInWa, nowMs){
  var d = parseISO(lastInWa);
  if (!d) return { open:false, until:null };
  var until = d.getTime() + WA_WINDOW_MS;
  return { open: nowMs < until, until: until };
}

/* Has this guest agreed to WhatsApp? Only if they asked for it - staff
   switch it on in the conversation, and the switch records who and when,
   because the request IS the consent Meta wants - or wrote to us there
   themselves. The owner, 29 Sep: WhatsApp is for an international guest
   who asks; SMS for everyone else. A number WhatsApp said it does not
   know (waBad) is SMS until the guest writes on WhatsApp again. */
function waAgreed(t){
  if (!t || t.waBad) return false;
  return !!((t.wa && t.wa.on === true) || t.lastInWa);
}

/* Which way a message from us goes, and whether it may be free text:
     none   the guest texted STOP; nothing goes until they text START
     wa     WhatsApp, free text: they wrote on WhatsApp within 24 hours
     watpl  WhatsApp, approved wording only: they agreed, but have not
            written in the last 24 hours
     sms    SMS, free text
   A guest who wrote in the last 24 hours is answered the way they wrote.
   until is when the WhatsApp window closes, for the line above the box. */
function contactChannel(t, nowMs){
  t = t || {};
  if (t.optout) return { ch:'none', until:null };
  var inAt = parseISO(t.lastIn);
  if (inAt && nowMs - inAt.getTime() < WA_WINDOW_MS)
    return t.lastInCh === 'wa'
      ? { ch:'wa', until: inAt.getTime() + WA_WINDOW_MS }
      : { ch:'sms', until:null };
  if (waAgreed(t)) return { ch:'watpl', until:null };
  return { ch:'sms', until:null };
}

/* Where one guest stands on the list, which is the colour the row wears
   (the colour law, CLAUDE.md):
     nophone  no sendable mobile, no thread       sunk, not pressable
     none     nothing sent or received            sunk
     fresh    a message nobody has sorted         white: work to do
     task     sorted, a task still open           amber: chase this
     sent     only we have written                the law's waiting grey
     done     all sorted, nothing open            done green
   fresh counts their unsorted messages, open their open tasks. */
function contactRowState(t, fresh, open, hasPhone){
  if (fresh > 0) return 'fresh';
  if (open > 0) return 'task';
  if (!t || !t.lastAt) return hasPhone ? 'none' : 'nophone';
  if (!t.lastIn) return 'sent';
  return 'done';
}

/* The approved WhatsApp wording, for when a guest's 24 hours have run out.
   Three copies must say the same thing: these words (the preview), the
   Worker's (what the record says went) and Twilio's template, which Meta
   approved under its Content SID. The first two answer to
   tests/contact_cases.json; GUEST-CONTACT.md holds the text to submit.
   Plain characters only: a curly quote makes an SMS fallback cost triple.
   {first} is the booking's first name, else "there"; {arrive} its day. */
var CONTACT_TEMPLATES = [
  { id:'question', label:'A quick question',
    text:'Hi {first}, it\'s Nala Resort with a quick question about your stay. ' +
         'Could you reply to this message when you have a moment?' },
  { id:'arrival', label:'Your arrival', arriving:true,
    text:'Hi {first}, we look forward to welcoming you to Nala Resort on ' +
         '{arrive}. If there is anything we can prepare before you arrive, ' +
         'just reply to this message.' }
];
function contactTemplateText(id, first, arrive){
  var t = CONTACT_TEMPLATES.filter(function(x){ return x.id === id; })[0];
  if (!t) return '';
  first = String(first == null ? '' : first).trim() || 'there';
  var d = parseDepDate(arrive), day = '';
  if (d) day = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday',
                'Saturday'][d.getDay()] + ' ' + d.getDate() + ' ' +
               ['January','February','March','April','May','June','July',
                'August','September','October','November','December'][d.getMonth()];
  return t.text.split('{first}').join(first).split('{arrive}').join(day || 'your arrival day');
}

/* A new key for a task, sortable by when it was made. */
function contactId(){
  var r = '', abc = 'abcdefghijklmnopqrstuvwxyz0123456789';
  for (var i = 0; i < 6; i++) r += abc.charAt(Math.floor(Math.random() * abc.length));
  return 't' + Date.now().toString(36) + r;
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
  /* First, because it is the page that says where the day is up to and hands
     off to all the others. It needs only resBoard: every card's own door is
     gated separately by the permission its page already answers to. */
  { href:'dashboard.html',    label:'Dashboard',    need:'resBoard'     },
  /* The whole house on one screen. cleansBoard, not resBoard, so the
     grounds and housekeeping logins can see who is in and for how long -
     the page's whole point (the owner, 12 Sep). A bar only OPENS a guest
     profile for a login that also holds resBoard: the board is broad, the
     detail behind it is not. */
  { href:'calendar.html',     label:'Calendar',     need:'cleansBoard'  },
  { href:'front-desk.html',   label:'Front Desk',   need:'editBookings' },
  /* Chat, 29 Sep: the guests' messages, SMS and WhatsApp, and what
     each one became. editBookings, the SMS pages' own gate - the owner's
     answer to who may read and answer them. Tasks beside it: what the
     messages became, for the team that does them. Every human role may open
     it; each login sees its own teams' tasks, reception every team's. */
  { href:'guest-contact.html', label:'Chat', need:'editBookings' },
  { href:'tasks.html',        label:'Tasks',        need:'tasks'        },
  /* The desk's other duty, so the desk's own gate. */
  { href:'keys.html',         label:'Keys',         need:'editBookings' },
  { href:'tally.html',        label:'Reservations', need:'resBoard'     },
  { href:'cleaners.html',     label:'Cleans',       need:'cleansBoard'  },
  { href:'spa.html',          label:'Spa',          need:'spaBoard'     },
  { href:'publish.html',      label:'Publish Menu', need:'publishMenu'  },
  /* Its door was the Stats button in Reservations' footer until 30 Sep,
     when the owner cleared the footers for the tab bar ("could be placed
     in the menu or could become one of the icons for the chef"). Both: it
     is here, and last in TABBAR, where only the chef has room for it. */
  { href:'stats.html',        label:'Statistics',   need:'resBoard'     },
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
      { href:'arrivals-sms.html', label:'Pre-arrival', need:'editBookings' },
      /* The text to a guest with a booked treatment, the morning of or up
         to 7 days ahead (the owner, 28 Sep). editBookings, the Worker's
         own gate for sending. */
      { href:'spa-reminders.html', label:'Spa reminders', need:'editBookings' } ] },
  { group:'Settings', items:[
      { href:'staff.html', label:'General', need:'manageStaff' },
      { href:'tag.html',   label:'Dietary', need:'publishMenu' },
      /* Admin only, like General and Pages: the flags an admin defines here
         are ticked on the front desk sheet by admins alone. */
      { href:'flags.html', label:'Flags',   need:'manageStaff' },
      { href:'pages.html', label:'Pages',   need:'manageStaff' },
      /* A switch, not a destination: wireNotify below owns it. No need key,
         so the filter leaves it alone - a housekeeper subscribes to her own
         alerts. */
      { action:'navNotify', label:'Notifications' } ] }
];

/* The staff pages with no hamburger entry, reached from inside another page,
   each named with the door that opens it. They were the audit's finding,
   12 Sep: four gated pages the Settings grid could never speak about,
   because the grid's page list is NAV and these are not in NAV. Listed here
   so NAV_NEEDS and the grid see every gated page, without putting a link in
   the menu. A new page reached from a board rather than the menu goes here,
   or the pageaccess suite names it by file.                             */
var NAV_UNLISTED = [
  { href:'guest.html',     label:'Guest Profile', need:'resBoard'     }, /* a calendar bar */
  { href:'templates.html', label:'SMS Templates', need:'editBookings' }, /* the two SMS pages */
  { href:'debug.html',     label:'Diagnostics',   need:'manageStaff'  }  /* Front Desk's foot */
];

/* Which permission opens each page, derived from NAV plus NAV_UNLISTED so
   the three cannot disagree. Kept under its old name because the filter and
   the suites ask this question by it. */
var NAV_NEEDS = (function(){
  var out = {};
  NAV.concat(NAV_UNLISTED).forEach(function(e){
    (e.items || [e]).forEach(function(i){ if (i.href) out[i.href] = i.need; });
  });
  return out;
})();

/* ── per-page access ───────────────────────────────────────────
   Which pages a role may open, as its own question, asked by page name.
   Until 12 Sep the only knob was the capability grid: Keys borrowed
   editBookings, Statistics borrowed resBoard, and taking one page off a
   role meant taking every page that borrowed the same word. The owner asked
   for the pages themselves as switches.

   The model is the permission matrix's, one layer up. A page's DEFAULT is
   its capability in NAV_NEEDS - a new page needs no ceremony beyond its NAV
   entry, and arrives open to whoever holds its capability, exactly as
   before. /permissions/pages/<key>/<role> is the manager changing their
   mind about ONE page, and only an explicit true or false is an opinion.

   Two doors that stay shut, both in the rules as well as here, because the
   grid is not the only way to write there: an admin page (need manageStaff)
   never reads the override - handing out a Settings page is handing out
   manageStaff under another name - and admin itself is answered before the
   override is consulted, so a stray row cannot lock the owner out.      */
function pageKey(href){
  return String(href || '').split('?')[0].replace(/\.html$/, '');
}

/* ── a page the admin tries before the staff see it ─────────────
   The owner, 29 Sep: Chat published before Twilio is set up, so
   its screens can be tried on the live app, and the admin's alone until
   the owner opens it. A page listed here opens to the admin only until
   /permissions/open/<page> is true - the switch is in Settings, General,
   Teams - and from then on as its NAV entry says, to whoever holds its
   capability. Absent is shut, so a publish that lands before anybody
   decides shows the staff nothing. Its menu entry, its menu count and its
   Dashboard card all ask canOpen, so they follow. */
var PREVIEW_PAGES = { 'guest-contact': true, 'tasks': true };
function previewShut(role, href){
  var k = pageKey(href);
  if (!PREVIEW_PAGES[k] || normaliseRole(role) === 'admin') return false;
  var open = PERMISSIONS && PERMISSIONS.open;
  return !(open && open[k] === true);
}

function canOpen(role, href){
  var need = NAV_NEEDS[href];
  /* A page nobody has listed is merely ungated, not shut: the same answer
     the menu filter gives, for the same reason - the failure must not look
     like a broken link. The pageaccess suite is what catches the listing. */
  if (need === undefined) return true;
  if (need === 'manageStaff') return can(role, need);
  var r = normaliseRole(role);
  if (r === 'admin') return true;
  if (previewShut(r, href)) return false;
  var pages = PERMISSIONS && PERMISSIONS.pages;
  var row = pages && pages[pageKey(href)];
  if (row && typeof row[r] === 'boolean') return row[r];
  return can(role, need);
}

/* The rows the Settings grid offers, derived from the same two lists as
   NAV_NEEDS so a page added to the menu is a switch the same day - which is
   the complaint that built all this. Admin pages are not offered, and the
   Notifications action is a switch, not a page. Grouped entries carry their
   group, because "Menu" alone in a flat list reads as Publish Menu.      */
var PAGE_GRID = (function(){
  var out = [];
  NAV.concat(NAV_UNLISTED).forEach(function(e){
    (e.items || [e]).forEach(function(i){
      if (!i.href || NAV_NEEDS[i.href] === 'manageStaff') return;
      var label = (e.group ? e.group + ' · ' : '') + i.label;
      out.push([pageKey(i.href), 'Open ' + label, i.href]);
    });
  });
  return out;
})();

/* The massage mark: one centre petal and a mirrored pair, on the fork's own
   24 grid, stroked so it carries its state in the stroke colour. Drawn for
   Front Desk's rows on 31 Aug; here since 30 Sep, for any page to draw. */
var LOTUS_PATHS =
  '<path d="M12 3.4c2.5 2.9 3.7 5.5 3.7 7.8 0 2.4-1.2 4.5-3.7 6.2' +
  '-2.5-1.7-3.7-3.8-3.7-6.2 0-2.3 1.2-4.9 3.7-7.8z"/>' +
  '<path d="M11.4 17.5c-2.8.5-5.2-.2-7-2C2.5 13.6 1.9 11.2 2.2 8.6' +
  'c2.6-.3 5 .3 6.8 2.1"/>' +
  '<path d="M12.6 17.5c2.8.5 5.2-.2 7-2 1.9-1.9 2.5-4.3 2.2-6.9' +
  'c-2.6-.3-5 .3-6.8 2.1"/>';
var ICON_LOTUS = '<svg viewBox="0 0 24 24">' + LOTUS_PATHS + '</svg>';

/* Every page's icon, one per page in NAV: the tab bar draws the pages on
   TABBAR with them, and the menu draws every page it lists with its own
   (buildNav). The suite fails a page on either that has none. Lucide's
   (lucide.dev), the set the owner chose on 30 Sep off mock-tab-icons.html
   - "Let's use lucid" - with list-todo for the Dashboard, which "is
   actually a daily checklist", clock-alert for Tasks, which "are important
   'do it now' jobs", messages-square for Chat, chart-gantt for Statistics
   and plane-landing for Arrivals, all his picks; the rest of the menu's
   as mock-tabbar.html proposed them and he took them with the menu from
   the foot (mock-menu-tab.html, "B"). Line icons on Lucide's 24 grid,
   drawn thinner than Lucide's own at his ask (nala-ui2.css); each is
   copied unchanged from its own file in lucide-static 1.49.0, named
   beside it, so a swap is a name looked up at lucide.dev and its paths
   pasted here.

   Lucide's licence, which asks to travel with its icons:

   ISC License

   Copyright (c) 2026 Lucide Icons and Contributors

   Permission to use, copy, modify, and/or distribute this software for any
   purpose with or without fee is hereby granted, provided that the above
   copyright notice and this permission notice appear in all copies.

   THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
   WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
   MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
   ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
   WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
   ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
   OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.   */
var PAGE_ICONS = {
  'dashboard.html':     /* list-todo, the day's checklist, which the Dashboard is */
    '<path d="M13 5h8"/><path d="M13 12h8"/><path d="M13 19h8"/><path d="m3 17 2 2 4-4"/><rect x="3" y="4" width="6" height="6" rx="1"/>',
  'tally.html':         /* utensils */
    '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>',
  'cleaners.html':      /* brush-cleaning */
    '<path d="m16 22-1-4"/><path d="M19 14a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2h-3a1 1 0 0 1-1-1V4a2 2 0 0 0-4 0v5a1 1 0 0 1-1 1H6a2 2 0 0 0-2 2v1a1 1 0 0 0 1 1"/><path d="M19 14H5l-1.973 6.767A1 1 0 0 0 4 22h16a1 1 0 0 0 .973-1.233z"/><path d="m8 22 1-4"/>',
  'guest-contact.html': /* messages-square, the owner's pick */
    '<path d="M16 10a2 2 0 0 1-2 2H6.828a2 2 0 0 0-1.414.586l-2.202 2.202A.71.71 0 0 1 2 14.286V4a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/><path d="M20 9a2 2 0 0 1 2 2v10.286a.71.71 0 0 1-1.212.502l-2.202-2.202A2 2 0 0 0 17.172 19H10a2 2 0 0 1-2-2v-1"/>',
  'tasks.html':         /* clock-alert, the important, do it now jobs */
    '<path d="M12 6v6l4 2"/><path d="M20 12v5"/><path d="M20 21h.01"/><path d="M21.25 8.2A10 10 0 1 0 16 21.16"/>',
  'front-desk.html':    /* concierge-bell */
    '<path d="M3 20a1 1 0 0 1-1-1v-1a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v1a1 1 0 0 1-1 1Z"/><path d="M20 16a8 8 0 1 0-16 0"/><path d="M12 4v4"/><path d="M10 4h4"/>',
  'spa.html':           /* flower */
    '<circle cx="12" cy="12" r="3"/><path d="M12 16.5A4.5 4.5 0 1 1 7.5 12 4.5 4.5 0 1 1 12 7.5a4.5 4.5 0 1 1 4.5 4.5 4.5 4.5 0 1 1-4.5 4.5"/><path d="M12 7.5V9"/><path d="M7.5 12H9"/><path d="M16.5 12H15"/><path d="M12 16.5V15"/><path d="m8 8 1.88 1.88"/><path d="M14.12 9.88 16 8"/><path d="m8 16 1.88-1.88"/><path d="M14.12 14.12 16 16"/>',
  'calendar.html':      /* calendar-days */
    '<path d="M8 2v3"/><path d="M16 2v3"/><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M8 13h.01"/><path d="M12 13h.01"/><path d="M16 13h.01"/><path d="M8 17h.01"/><path d="M12 17h.01"/><path d="M16 17h.01"/>',
  'keys.html':          /* key-round */
    '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
  'publish.html':       /* book-open-text */
    '<path d="M12 5v16"/><path d="M16 13h2"/><path d="M16 9h2"/><path d="M20.001 19A2 2 0 0022 17V5a2 2 0 00-1.999-2L16 3.002A5 5 0 0012 5a5 5 0 00-4-2H4a2 2 0 00-2 2v12a2 2 0 001.999 2H8a5 5 0 014 2 5 5 0 014-2z"/><path d="M6 13h2"/><path d="M6 9h2"/>',
  'stats.html':         /* chart-gantt, the owner's pick */
    '<path d="M10 6h8"/><path d="M12 16h6"/><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M8 11h7"/>',
  /* the rest of the menu, which the bar never carries */
  'list.html':          /* clipboard-list, the FOH sheet */
    '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
  'housekeeping.html':  /* clipboard-check, the clean sheet */
    '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
  'registration.html':  /* plane-landing, Arrivals, the owner's pick */
    '<path d="M2 22h20"/><path d="M3.77 10.77 2 9l2-4.5 1.1.55c.55.28.9.84.9 1.45s.35 1.17.9 1.45L8 8.5l3-6 1.05.53a2 2 0 0 1 1.09 1.52l.72 5.4a2 2 0 0 0 1.09 1.52l4.4 2.2c.42.22.78.55 1.01.96l.6 1.03c.49.88-.06 1.98-1.06 2.1l-1.18.15c-.47.06-.95-.02-1.37-.24L4.29 11.15a2 2 0 0 1-.52-.38Z"/>',
  'menu-print.html':    /* scroll-text, the printed menu */
    '<path d="M15 12h-5"/><path d="M15 8h-5"/><path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
  'past-menus.html':    /* history */
    '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  'invitations.html':   /* send */
    '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
  'arrivals-sms.html':  /* clipboard-pen, the pre-arrival form */
    '<path d="M16 4h2a2 2 0 0 1 2 2v2"/><path d="M21.34 15.664a1 1 0 1 0-3.004-3.004l-5.01 5.012a2 2 0 0 0-.506.854l-.837 2.87a.5.5 0 0 0 .62.62l2.87-.837a2 2 0 0 0 .854-.506z"/><path d="M8 22H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
  'spa-reminders.html': /* bell */
    '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  'staff.html':         /* users, General: the staff */
    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><path d="M16 3.128a4 4 0 0 1 0 7.744"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/>',
  'tag.html':           /* wheat-off, Dietary */
    '<path d="m2 22 10-10"/><path d="m16 8-1.17 1.17"/><path d="M3.47 12.53 5 11l1.53 1.53a3.5 3.5 0 0 1 0 4.94L5 19l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z"/><path d="m8 8-.53.53a3.5 3.5 0 0 0 0 4.94L9 15l1.53-1.53c.55-.55.88-1.25.98-1.97"/><path d="M10.91 5.26c.15-.26.34-.51.56-.73L13 3l1.53 1.53a3.5 3.5 0 0 1 .28 4.62"/><path d="M20 2h2v2a4 4 0 0 1-4 4h-2V6a4 4 0 0 1 4-4Z"/><path d="M11.47 17.47 13 19l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L5 19l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z"/><path d="m16 16-.53.53a3.5 3.5 0 0 1-4.94 0L9 15l1.53-1.53a3.49 3.49 0 0 1 1.97-.98"/><path d="M18.74 13.09c.26-.15.51-.34.73-.56L21 11l-1.53-1.53a3.5 3.5 0 0 0-4.62-.28"/><line x1="2" x2="22" y1="2" y2="22"/>',
  'flags.html':         /* flag */
    '<path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.333 2q2 0 3.067-.8A1 1 0 0 1 20 4v10a1 1 0 0 1-.4.8A6 6 0 0 1 16 16c-3 0-5-2-8-2a6 6 0 0 0-4 1.528"/>',
  'pages.html':         /* files */
    '<path d="M15 2h-4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8"/><path d="M16.706 2.706A2.4 2.4 0 0 0 15 2v5a1 1 0 0 0 1 1h5a2.4 2.4 0 0 0-.706-1.706z"/><path d="M5 7a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h8a2 2 0 0 0 1.732-1"/>'
};

/* The menu's own marks, which are not pages: the bar's menu icon, and the
   menu's Notifications switch and Logout. Lucide's, as above. */
var MENU_ICONS = {
  menu:      '<path d="M4 5h16"/><path d="M4 12h16"/><path d="M4 19h16"/>',
  navNotify: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M22 8c0-2.3-.8-4.3-2-6"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/><path d="M4 2C2.8 3.7 2 5.7 2 8"/>',
  signout:   '<path d="m16 17 5-5-5-5"/><path d="M21 12H9"/><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
};

/* A menu row's icon, on the second dress only: the printed sheets' older
   menu has no room drawn for one. */
function navIcon(key){
  var d = PAGE_ICONS[key] || MENU_ICONS[key];
  if (!d || !document.body || !/(^|\s)ui2(\s|$)/.test(document.body.className)) return '';
  return '<span class="navic"><svg viewBox="0 0 24 24" aria-hidden="true">' + d + '</svg></span>';
}

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
    if (i.action){ a.href = '#'; a.className = 'navaction'; a.id = i.action; }
    else a.href = i.href;
    var ic = navIcon(i.action || i.href);
    if (ic) a.innerHTML = ic + '<span class="navlabel"></span>';
    (a.querySelector('.navlabel') || a).textContent = i.label;
    return a;
  }
  NAV.forEach(function(e){
    if (!e.group){
      if (e.href !== here) drop.appendChild(makeLink(e));
      return;
    }
    var items = e.items.filter(function(i){ return i.action || i.href !== here; });
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
  so.innerHTML = navIcon('signout') + '<span class="navlabel">Logout</span>';
  so.onclick = function(ev){
    ev.preventDefault();
    var u = window.NALA_USER || null;
    try { u = firebase.auth().currentUser || u; } catch (ex){}
    var go = function(){ if (window.NALA_SIGNOUT) NALA_SIGNOUT(); else location.reload(); };
    /* The tab bar's icons kept on this phone were this login's: the next
       login is drawn its own. */
    try { localStorage.removeItem(TABS_KEPT); localStorage.removeItem(COUNTS_KEPT); } catch (ex){}
    /* Unsubscribe first, while the token is still valid enough to delete
       the record. If it fails, sign out anyway: being stuck signed in
       would be the worse outcome. */
    if (u && typeof window.pushOff === 'function') window.pushOff(u, go);
    else go();
  };
  drop.appendChild(so);
}
buildNav();

/* ── the tab bar ─────────────────────────────────────────────────────────
   Icons along the foot of the screen for the pages used most: one icon a
   page, five at most, and a page this login cannot open is not there; the
   menu comes after them. The owner, 30 Sep, naming the admin's five:
   Dashboard, Reservations, Cleans, Chat and Tasks - then, off
   mock-menu-rise.html, "5 pages plus the menu".

   A shortcut into the menu, not a second menu. Every page on it keeps its
   place in NAV, its label is its NAV entry's, and whether it is offered is
   canOpen's answer - the menu filter's own question - so the bar and the
   menu cannot disagree about a page, and a page switched off for a role in
   Settings leaves both at once.

   TABBAR is the order of preference: a login gets the first TABBAR_MAX
   pages of it that it may open, drawn in this order. The admin's five lead,
   so the admin, who may open everything, gets exactly those. The rest are
   the other boards on the menu's top level, for the logins that cannot open
   all five - a housekeeper's Calendar, the masseuse's Spa, the chef's
   Publish Menu and Statistics. The Print, SMS and Settings pages stay in
   their submenus.

   Every login with a page to go to draws the same bar, one page and the
   menu included: the owner, 1 Oct, "They should all be the same". The
   page you are on stays on the bar, marked and not a link, so the icons
   never move under the thumb.

   tests/nav_canon.json holds the order and what each role is offered, the
   menu's own pattern: change the bar there too, or the suites name it.   */
var TABBAR = ['dashboard.html', 'tally.html', 'cleaners.html', 'guest-contact.html',
              'tasks.html', 'front-desk.html', 'spa.html', 'calendar.html',
              'keys.html', 'publish.html', 'stats.html'];
/* Five pages, and the menu after them: the owner, 30 Sep, off
   mock-menu-rise.html, "5 pages plus the menu". */
var TABBAR_MAX = 5;


/* The menu's top-level entries by page, taken as this file loads - as
   NAV_NEEDS is - and not read from NAV later: Past Menus names its date
   control NAV, a page global that replaces this list once the page's own
   script runs, and a bar that asked NAV then found no pages at all. The
   bar carries no group's pages, so the top level is the whole search.   */
var NAV_TOP = (function(){
  var out = {};
  NAV.forEach(function(e){ if (e.href) out[e.href] = e; });
  return out;
})();
function navEntry(href){
  return Object.prototype.hasOwnProperty.call(NAV_TOP, href) ? NAV_TOP[href] : null;
}

/* What the bar offers this login: the first TABBAR_MAX pages of TABBAR it may
   open, in TABBAR's order - or none, when it may open none. A page
   missing from NAV is never offered: canOpen calls an unlisted page ungated,
   which is right for a menu link and wrong for this. */
function tabsFor(role){
  var out = [];
  for (var i = 0; i < TABBAR.length && out.length < TABBAR_MAX; i++){
    if (navEntry(TABBAR[i]) && canOpen(role, TABBAR[i])) out.push(TABBAR[i]);
  }
  return out;
}

/* Draws the bar, from the menu filter below: it runs once the role and the
   permissions are known, so a signed-out page, or a login with no staff
   record, draws none. Only where the menu is, and only on a page wearing
   ui2, whose sheet (nala-ui2.css) holds the bar's dress and the rules that
   keep the page's own footer and sheets clear of it. The printed sheets
   wear the older dress and keep the menu alone until they join.
   What it offered is kept on the phone, for the next page to draw at once
   (below).                                                              */
var TABS_KEPT = 'nala-tabs';
/* The counts the bar last wore, kept beside its icons (the owner, 1 Oct:
   they were "still flashing between page loads", gone until each page's
   login landed and asked again). Drawn with the bar, then the live ones
   take their place as they land (drawNavCounts). Logout forgets them. */
var COUNTS_KEPT = 'nala-counts';
function keptCounts(){
  var k = {};
  try { k = JSON.parse(localStorage.getItem(COUNTS_KEPT) || '{}') || {}; } catch (e){ k = {}; }
  Object.keys(k).forEach(function(id){
    var t = /^tab-[a-z-]+$/.test(id) && document.getElementById(id);
    if (t && +k[id] > 0) navBadge(t.querySelector('.tabic'), +k[id]);
  });
}
function buildTabs(role){
  if (!tabsPage()) return;
  var tabs = tabsFor(role);
  try { localStorage.setItem(TABS_KEPT, tabs.join(' ')); } catch (e){}
  drawTabs(tabs);
}
function tabsPage(){
  var body = document.body;
  return !!(body && document.getElementById('navDrop') &&
            /(^|\s)ui2(\s|$)/.test(body.className));
}
function drawTabs(tabs){
  if (!tabsPage()) return;
  var body = document.body, key = tabs.join(' ');
  var bar = document.getElementById('tabBar');
  if (bar && bar.getAttribute('data-tabs') === key) return;   /* drawn already */
  if (bar) bar.parentNode.removeChild(bar);
  body.classList.toggle('hastabs', tabs.length > 0);
  if (!tabs.length) return;
  var here = location.pathname.split('/').pop() || 'index.html';
  bar = document.createElement('nav');
  bar.id = 'tabBar';
  /* One bar for every login, however few its icons (nala-ui2.css). */
  bar.className = 'tabbar';
  bar.setAttribute('aria-label', 'Pages');
  bar.setAttribute('data-tabs', key);
  var row = document.createElement('div');
  row.className = 'tabrow';
  tabs.forEach(function(href){
    var a = document.createElement('a');
    a.id = 'tab-' + pageKey(href);
    /* Not a link on its own page: pressing it could only reload the page,
       and a reload throws away whatever was being typed there. */
    if (href === here) a.setAttribute('aria-current', 'page');
    else a.href = href;
    /* Lucide's 24 grid fills the icon's 28pt box, so its largest glyph,
       20 of the grid, stands 23pt: Apple's size for a square one. */
    /* The name is in the link but not shown under the icon (nala-ui2.css):
       a screen reader says it with the count, and a mouse sees it here. */
    a.title = navEntry(href).label;
    a.innerHTML = '<span class="tabic"><svg viewBox="0 0 24 24" aria-hidden="true">' +
                  PAGE_ICONS[href] + '</svg></span>' +
                  '<span class="tablbl">' + navEntry(href).label + '</span>';
    row.appendChild(a);
  });
  /* The menu, last: the iPhone's More tab (the owner, 30 Sep, off
     mock-menu-rise.html). It raises the page's own menu from the foot of
     the screen, beside itself (nala-ui2.css), and the hamburger at the top
     of the page stands down. The page's own button still does the opening,
     hidden, so each page's menu code - open, and shut on a tap elsewhere -
     is untouched. Blue while you are on a page the bar does not carry, as
     the phone's More tab is: that page is in here. */
  var m = document.createElement('button');
  m.type = 'button';
  m.id = 'tab-menu';
  m.className = 'tabmenu' + (tabs.indexOf(here) < 0 ? ' here' : '');
  m.title = 'Menu';
  m.setAttribute('aria-expanded', 'false');
  m.innerHTML = '<span class="tabic"><svg viewBox="0 0 24 24" aria-hidden="true">' +
                MENU_ICONS.menu + '</svg></span><span class="tablbl">Menu</span>';
  m.addEventListener('click', function(e){
    e.stopPropagation();          /* the page shuts its menu on any other tap */
    /* Not while auth.js's cover waits on the login, the bar standing on
       it: the page is not there yet, nor the menu's filter for the login. */
    if (document.getElementById('nalaCover')) return;
    var btn = document.getElementById('navBtn');
    if (btn) btn.click();
  });
  row.appendChild(m);
  bar.appendChild(row);
  body.appendChild(bar);
  keptCounts();
  /* Behind the open menu, a shade over the page: a tap on it only shuts the
     menu, where a tap on the page would also press what is under it. */
  var drop = document.getElementById('navDrop');
  if (!document.getElementById('menuShade')){
    var shade = document.createElement('div');
    shade.id = 'menuShade';
    shade.className = 'menushade';
    drop.parentNode.insertBefore(shade, drop.nextSibling);
  }
  /* The menu icon says whether the menu is open, and is blue while it is
     (nala-ui2.css). */
  if (!drop.getAttribute('data-watched') && window.MutationObserver){
    drop.setAttribute('data-watched', '1');
    new MutationObserver(function(){
      var t = document.getElementById('tab-menu');
      if (t) t.setAttribute('aria-expanded', drop.classList.contains('open') ? 'true' : 'false');
    }).observe(drop, { attributes:true, attributeFilter:['class'] });
  }
}

/* The bar at once, before the login is known. Every tap on it opens a new
   page, and the login takes a moment to land on each: a bar drawn only
   then went with the tap and came back after the page. The owner, 30 Sep:
   "Why does the menu bar need to disappear every icon press and load with
   the page. It should stay there". So the icons this phone was last given
   are drawn as this file loads, and stand on auth.js's cover while it
   waits (nala-ui2.css). buildTabs puts the login's own in their place
   when they differ - a phone handed to another login, a page switched off
   in Settings since - and Logout forgets them. The bar only saves the
   moment: every page it leads to asks for the login itself.           */
(function(){
  var kept = '';
  try { kept = localStorage.getItem(TABS_KEPT) || ''; } catch (e){}
  var tabs = kept.split(' ').filter(function(h){
    return navEntry(h) && Object.prototype.hasOwnProperty.call(PAGE_ICONS, h);
  });
  if (tabs.length) drawTabs(tabs);
})();

/* ── the foot of the screen, after the keyboard ──────────────────────────
   Safari on the iPhone can keep the screen's foot where the keyboard's top
   was after the keyboard has gone: the bar 294pt up on Settings (the
   number pad's height, 1 Oct) and about 400pt up in Chat (the keyboard's,
   2 Oct), Chat's box with it and the page carrying on underneath them -
   the owner: "fix the sticky footer menu once and for all". A scroll of a
   point and back, tried first, did not move it.

   So the page measures instead of trusting: where Safari's foot is (a
   fixed probe at bottom 0) and where the visible screen ends (the visual
   viewport). On a page that is right they agree, and nothing moves. When
   Safari's foot is a keyboard's worth short, --footfix is the difference,
   and everything that stands at the foot reads it (nala-ui2.css): the
   bar, its menu, a page's footer and save bar, Chat's box, a sheet. It is
   asked again as the keyboard goes, the page scrolls or turns, or the app
   comes back, so it lets go the moment Safari is right again. Nothing is
   moved while a field is typed in, where the phone's own placing is
   right, or while the page is pinched in. Each time it moves anything, the
   numbers go to this phone's log, which Diagnostics shows: if the foot is
   ever wrong again, they say why. */
var FOOT_MIN = 150;            /* a keyboard's worth; no screen edge moves so far */
var FOOT_LOG = 'nala-footlog';
function typingNow(){
  var a = document.activeElement;
  if (!a) return false;
  if (a.isContentEditable || /^(TEXTAREA|SELECT)$/.test(a.tagName)) return true;
  return a.tagName === 'INPUT' &&
         !/^(checkbox|radio|button|submit|reset|range|color|file|image|hidden)$/i.test(a.type);
}
function footDrift(){
  var vv = window.visualViewport;
  if (!vv || !document.body || typingNow() || Math.abs(vv.scale - 1) > 0.01) return 0;
  var p = document.getElementById('footProbe');
  if (!p){
    p = document.createElement('div');
    p.id = 'footProbe';
    p.setAttribute('aria-hidden', 'true');
    p.style.cssText = 'position:fixed;left:0;bottom:0;width:0;height:0;' +
                      'visibility:hidden;pointer-events:none';
    document.body.appendChild(p);
  }
  var d = vv.offsetTop + vv.height - p.getBoundingClientRect().top;
  return d >= FOOT_MIN ? Math.round(d) : 0;
}
function footCheck(why){
  var root = document.documentElement;
  var was = parseInt(root.style.getPropertyValue('--footfix'), 10) || 0;
  var d = footDrift();
  if (d === was) return;
  root.style.setProperty('--footfix', d + 'px');
  if (!d) return;
  var vv = window.visualViewport, p = document.getElementById('footProbe');
  try {
    var log = JSON.parse(localStorage.getItem(FOOT_LOG) || '[]') || [];
    log.push({ at: new Date().toISOString(), page: location.pathname.split('/').pop(),
               why: why, moved: d, probe: Math.round(p.getBoundingClientRect().top),
               vv: [Math.round(vv.offsetTop), Math.round(vv.height), vv.scale],
               inner: window.innerHeight, client: root.clientHeight,
               screen: [screen.width, screen.height], scroll: Math.round(window.scrollY),
               standalone: !!navigator.standalone });
    localStorage.setItem(FOOT_LOG, JSON.stringify(log.slice(-20)));
  } catch (e){}
}
(function(){
  var queued = false;
  function soon(why){
    if (queued) return;
    queued = true;
    requestAnimationFrame(function(){ queued = false; footCheck(why); });
  }
  var vv = window.visualViewport;
  if (vv){
    vv.addEventListener('resize', function(){ soon('resize'); setTimeout(function(){ footCheck('settled'); }, 400); });
    vv.addEventListener('scroll', function(){ soon('scroll'); });
  }
  window.addEventListener('scroll', function(){ soon('scroll'); }, { passive:true });
  window.addEventListener('resize', function(){ soon('resize'); });
  window.addEventListener('orientationchange', function(){ setTimeout(function(){ footCheck('turn'); }, 400); });
  window.addEventListener('pageshow', function(){ soon('show'); });
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) soon('back'); });
  document.addEventListener('focusin', function(){ soon('focus'); });
  document.addEventListener('focusout', function(){
    setTimeout(function(){ footCheck('keyboard'); }, 450);
  });
})();

/* ── pull to refresh ─────────────────────────────────────────────────────
   Drag the page down from its top and let go: it reloads. The owner, 30
   Sep, clearing footers for the tab bar: "the refresh button could be a
   normal drag down to refresh". A board asks for it with one call,
   pullToRefresh(), where its Refresh button was: Reservations, Cleans and
   the Dashboard.

   Only in the Home Screen app, which has no pull of its own and is where
   the staff work. Safari and Chrome tabs already pull to refresh, and a
   second pull on top of theirs would reload twice.

   A pull counts only from the very top of the page, and never from inside
   the menu, a sheet, the tab bar or anything fixed, or from a box that
   scrolls on its own and is not at its own top: a drag that means
   something else is never taken for one. Past PTR_PULL the mark turns
   ink, and letting go there reloads; anywhere short of it, nothing.      */
var PTR_PULL = 70;          /* how far the mark travels to arm a release */
var PTR_ON = false;
var PTR_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true">' +
  '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/></svg>';
function pullToRefresh(refresh){
  if (PTR_ON || !inHomeScreenApp()) return;
  PTR_ON = true;
  var go = refresh || function(){ location.reload(); };
  var mark = null, y0 = null, pulled = 0;
  function blocked(t){
    var drop = document.getElementById('navDrop');
    if (drop && drop.classList.contains('open')) return true;
    for (var e = t; e && e.nodeType === 1 && e !== document.body; e = e.parentElement){
      var cs = getComputedStyle(e);
      if (cs.position === 'fixed' || cs.position === 'sticky') return true;
      if (/(auto|scroll)/.test(cs.overflowY) && e.scrollTop > 0) return true;
    }
    return false;
  }
  function draw(dy){
    if (!mark){
      mark = document.createElement('div');
      mark.className = 'ptr';
      mark.id = 'ptrMark';
      mark.innerHTML = PTR_ICON;
      document.body.appendChild(mark);
    }
    mark.style.opacity = dy ? String(0.35 + 0.65 * Math.min(dy / PTR_PULL, 1)) : '0';
    mark.style.transform = 'translateY(' + (Math.min(dy, PTR_PULL * 1.2) - 60) + 'px)' +
                           ' rotate(' + Math.round(dy * 3) + 'deg)';
    mark.classList.toggle('ready', dy >= PTR_PULL);
  }
  document.addEventListener('touchstart', function(e){
    y0 = null;
    if (e.touches.length !== 1 || window.scrollY > 0 || blocked(e.target)) return;
    y0 = e.touches[0].clientY;
    pulled = 0;
  }, { passive:true });
  document.addEventListener('touchmove', function(e){
    if (y0 === null) return;
    /* Half the finger's travel, so the mark lags it, as a phone's own does. */
    pulled = window.scrollY > 0 ? 0 : Math.max(0, (e.touches[0].clientY - y0) / 2);
    draw(pulled);
  }, { passive:true });
  document.addEventListener('touchend', function(){
    if (y0 === null) return;
    y0 = null;
    if (pulled < PTR_PULL){ draw(0); return; }
    mark.classList.add('spin');
    go();
  });
  document.addEventListener('touchcancel', function(){
    if (y0 === null) return;
    y0 = null;
    draw(0);
  });
}

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
    links[i].style.display = canOpen(role, href) ? '' : 'none';
  }
  hideEmptyGroups(drop);
  buildTabs(role);            /* before the counts, which the icons wear too */
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
/* What is booked, in words. Both lengths on a pair, in order - "1.5 hr +
   1 hr" - because the masseuse plans his day by time and length, and a
   hidden second length was the bug that forced the pair onto one tile.

   Lifted out of spa.html's serviceOf on 9 Sep so the Dashboard's reminder
   says the same thing the Spa board does. */
function spaOffering(rec){
  return rec.qty === 2
    ? 'Two massages \u00B7 ' + (spaDur(rec.dur) ? spaDur(rec.dur).short : '?') +
      ' + ' + (spaDur(rec.dur2) ? spaDur(rec.dur2).short : '?')
    : 'Massage' + (spaDur(rec.dur) ? ' \u00B7 ' + spaDur(rec.dur).short : '');
}

function spaDur(m){
  for (var i = 0; i < SPA_DURS.length; i++)
    if (SPA_DURS[i].m === +m) return SPA_DURS[i];
  return null;
}

/* "Any day", the chip a guest picks when the day does not matter to them
   (ruled 31 Aug). It is an ANSWER and not silence, which is the whole
   point of it: before this, a guest who was easy about the day and a
   guest who never reached the question both stored an empty string, and
   the masseuse could not tell one from the other. Absent and "any" are as
   different here as absent and false are for wellness.

   It lives ONLY in wellDay, the guest's own answer. It must NEVER be
   written to a /spa record's reqDay: that rule validates a date or the
   empty string and would refuse the write, so the masseuse would tap Book
   and get an error. spa.html translates it to an in-memory reqAny flag on
   the way in and books a real day on the way out.

   Forced copy in prearrival.html, because a guest page loads no staff
   code; both are pinned to tests/slots.json. */
var SPA_ANY_DAY = 'any';
var SPA_ANY_DAY_LABEL = 'Any day';
function isAnyDay(v){ return String(v == null ? '' : v) === SPA_ANY_DAY; }

/*  who still owes an action on a spa item
    ------------------------------------------------------------------
    The board and the hamburger badge must agree about this, so it is
    decided here once and read in both places rather than written twice.

    Two people can owe the same item. A guest's request needs the masseuse
    to answer it AND the desk to know it was asked, the owner's ruling of
    7 Sep: reception fields the guest's next question about it, and cannot
    do that from a board they have no reason to open. Once she answers, the
    item leaves her count and stays on the desk's until the guest is told.

      requested   the guest asked, unanswered      masseuse and desk
      suggested   a different time offered         desk, to put to the guest
      declined    and the guest not yet told       desk, to tell the guest
      booked, or a told decline                    nobody

    Nothing here can be dismissed by hand. A cleared badge would mean "I
    have seen this" while reading as "this is done", and it is the guest
    who pays the difference when the two drift apart: the work clears it
    or it stays. The owner asked for a clear button on 7 Sep and agreed
    to this instead.

    A day that has passed stops counting, because nobody can act on last
    Tuesday. An Any day request has no day to age out and keeps asking
    until it is answered - which is the point of it.                    */

/*  An ask is spoken for once answering it has written a real record.
    That is the source stamp, not the status: a decline is an answer. */
function spaAskSpokenFor(recs){
  var r = recs || {};
  return Object.keys(r).some(function(tid){
    return (r[tid] || {}).source === 'prearrival';
  });
}

/*  The day an item is chasing. A suggestion chases the day offered; an
    ask or a decline chases the day requested. Any day has none.        */
function spaItemDay(rec){
  if (!rec || rec.reqAny) return '';
  return rec.status === 'suggested' ? (rec.day || '')
                                    : (rec.reqDay || rec.day || '');
}

function spaOwedBy(rec, today){
  var owed = { spa: false, desk: false };
  if (!rec || !rec.status) return owed;
  var d = spaItemDay(rec);
  if (d && today && d < today) return owed;
  if (rec.status === 'requested'){ owed.spa = true; owed.desk = true; }
  else if (rec.status === 'suggested') owed.desk = true;
  else if (rec.status === 'declined' && !rec.told) owed.desk = true;
  return owed;
}

/*  Both counts from the two nodes they live in. The unanswered asks are
    not in /spa at all - they are still only a line on a pre-arrival form
    - so the bookings node is read as well, which is why this takes both.

    A cancelled booking is not a request anybody can act on, and neither
    is one whose guest has already left: an Any day ask would otherwise
    sit in the masseuse's badge for good, a fortnight after the villa was
    turned over.                                                        */
function spaOwedCounts(spa, bookings, today){
  var out = { spa: 0, desk: 0 };
  spa = spa || {}; bookings = bookings || {};
  function add(rec){
    var o = spaOwedBy(rec, today);
    if (o.spa) out.spa++;
    if (o.desk) out.desk++;
  }
  Object.keys(spa).forEach(function(id){
    var byId = spa[id] || {};
    Object.keys(byId).forEach(function(tid){
      var r = byId[tid];
      if (r && typeof r === 'object' && r.status) add(r);
    });
  });
  Object.keys(bookings).forEach(function(id){
    var b = bookings[id] || {}, p = b.prearrival, pms = b.pms || {};
    if (!p || typeof p !== 'object' || p.wellness !== true) return;
    if (String(pms.state || '').toLowerCase() === 'cancelled') return;
    var dep = String(pms.depart || '').slice(0, 10);
    if (dep && today && dep < today) return;
    if (spaAskSpokenFor(spa[id])) return;
    var any = isAnyDay(p.wellDay);
    add({ status: 'requested', reqAny: any,
          reqDay: any ? '' : (p.wellDay || '') });
  });
  return out;
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

/* ── spa reminders ───────────────────────────────────────────
   A text to each guest with a booked treatment, saying what is booked and
   when. The owner's rulings, 28 Sep, off mock-spa-reminders.html: the
   morning of, not the day before; the desk presses Send on
   spa-reminders.html, nothing goes out on its own; the Gentle reminder
   wording; nothing in the text but the treatment, its length, the day and
   the time. Then, the same day, once it was live: "the same filter options
   as the pre arrival SMS (3, 7, 14 days)", and once that was live, "the
   tabs should be today, 3 days and 7 days, with today as default". So the
   page opens on today's treatments, looks up to SPA_REMIND_DAYS ahead, and
   a text can go early; but only today's rows come ticked, so the morning
   text is still what one press of Send does.

   ONE builder writes the words and ONE reader says where a treatment's
   reminder stands, and every screen reads them: the sending page, the
   Dashboard's spa card, the Spa board, the Guest Profile. The invitations
   Worker cannot import from the site, so it carries a twin of the builder,
   and both answer to tests/spareminder_cases.json - the phone_cases.json
   pattern: add a case there, not to a suite.

   What went out lives at /spareminders/<booking>/<tid>, written by the
   Worker: { sentAt, by, status, to, body, error, template, providerId,
   delivery?, deliveryText?, day, time, qty, dur, dur2? }. The last five are
   the booking as THAT text quoted it, which is how a treatment moved after
   its text is caught. Not on the /spa record itself: spa.html writes that
   whole, by PUT, and would wipe it on the next save.                    */
var SPA_WEEKDAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
var SPA_MONTHS = ['January','February','March','April','May','June','July',
                  'August','September','October','November','December'];

/* How far ahead a reminder can go: Spa reminders' longest look, and so the
   Spa board's test for whether a treatment's text can be sent yet. The
   Worker cannot import it and fences sends with its own copy; both answer
   to `horizon` in tests/spareminder_cases.json. */
var SPA_REMIND_DAYS = 7;

/* The local day keys from today, n of them (all SPA_REMIND_DAYS if n is
   left out): Pre-arrival SMS's own reading of "the next n days", today
   counted as the first. */
function spaRemindDays(n){
  var out = [];
  for (var i = 0; i < (n || SPA_REMIND_DAYS); i++){
    var d = new Date(); d.setDate(d.getDate() + i);
    out.push(dkey(d));
  }
  return out;
}

/* "Sunday 27 September at 10:30 am", or the time alone. The day is spelt
   out, never "today": a text is right whenever it lands, and the Worker
   that writes it runs on UTC. Built from the date's own digits, never
   through a Date in the device's zone. */
function spaWhenText(day, time, withDay){
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day || ''));
  var t = spaSlotLabel(time);
  if (!withDay || !m) return t;
  var d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return SPA_WEEKDAYS[d.getUTCDay()] + ' ' + d.getUTCDate() + ' ' +
         SPA_MONTHS[d.getUTCMonth()] + ' at ' + t;
}

/* The booking as a text quotes it, one comparable string. A pair's second
   length counts; one massage's leftover dur2 does not, because the record
   of a single massage simply never states one. */
function spaQuote(r){
  var q = r && r.qty === 2 ? 2 : 1;
  return [(r && r.day) || '', (r && r.time) || '', q, +(r && r.dur) || 0,
          q === 2 ? (+r.dur2 || 0) : 0].join('|');
}

/* A text that reached the guest, as far as anybody knows: accepted by the
   carrier and not since reported undelivered. The same reading as
   preSmsFailed, from the other side. */
function spaReminderGood(rem){
  return !!(rem && rem.status === 'sent' && rem.delivery !== 'failed');
}

/* What <booking> becomes: the treatment and its lengths on one line, the
   day and time on the next. When the guest already holds a text quoting
   something else (prev is that text's record), a third line says what it
   changed from, so one template serves a first reminder and a corrected
   one alike. Plain GSM characters only: one middot or curly quote turns a
   text into UCS-2 and triples its cost. */
function spaBookingText(rec, prev){
  var d1 = spaDur(rec.dur), d2 = spaDur(rec.dur2), what;
  if (rec.qty === 2){
    what = 'Two massages';
    if (d1 && d2) what += ', ' + (d1.m === d2.m ? d1.label + ' each'
                                                : d1.label + ' and ' + d2.label);
  } else what = 'Massage' + (d1 ? ', ' + d1.label : '');
  var out = what + '\n' + spaWhenText(rec.day, rec.time, true);
  if (spaReminderGood(prev) && spaQuote(prev) !== spaQuote(rec)){
    if (prev.day !== rec.day)
      out += '\n(changed from ' + spaWhenText(prev.day, prev.time, true) + ')';
    else if (prev.time !== rec.time)
      out += '\n(changed from ' + spaWhenText(prev.day, prev.time, false) + ')';
    else out += '\n(changed since our last message)';
  }
  return out;
}

/* The template filled for one guest. <first> is the booking's first name,
   left out cleanly - the space before it too - when Mews has none;
   <booking> is spaBookingText. Nothing else is touched. The Worker's twin
   does exactly this, character for character. */
function spaReminderText(tpl, first, rec, prev){
  first = String(first == null ? '' : first).trim();
  var s = String(tpl == null ? '' : tpl);
  s = first ? s.split('<first>').join(first) : s.replace(/ ?<first>/g, '');
  return s.split('<booking>').join(spaBookingText(rec, prev));
}

/* Whether a treatment has begun, by the device's clock: staff devices live
   at the resort, the assumption every board makes when it says "today". A
   record with no day or time is never late. */
function spaTreatmentStarted(rec, nowMs){
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String((rec && rec.day) || ''));
  var t = /^(\d{2}):(\d{2})$/.exec(String((rec && rec.time) || ''));
  if (!m || !t) return false;
  return new Date(+m[1], +m[2] - 1, +m[3], +t[1], +t[2]).getTime() <= nowMs;
}

/* Where one treatment's reminder stands, the only judge, all screens:

     sent      a text reached the guest quoting the booking as it stands
     late      the treatment has begun without one: nothing is left to do,
               so it sinks rather than nags - the work clears it, the same
               self-clearing as every other queue here
     nophone   no number a text can go to; the desk can fix it
     changed   a text reached the guest, but the booking has moved since:
               they hold the wrong time, so it is owed again
     ready     still to send - never sent, a send that failed, or one the
               handset never got

   rec is the /spa record, rem its /spareminders record or null, raw the
   number the Worker will read (the desk's fix, then Mews), nowMs the clock.
   Held to tests/spareminder_cases.json. */
function spaReminderState(rec, rem, raw, nowMs){
  var good = spaReminderGood(rem);
  if (good && spaQuote(rem) === spaQuote(rec)) return 'sent';
  if (spaTreatmentStarted(rec, nowMs)) return 'late';
  if (!normalisePhone(raw)) return 'nophone';
  return good ? 'changed' : 'ready';
}

/* Every treatment booked on `day`, with what its reminder needs, in time
   order: the one list the sending page and the Dashboard's card both walk,
   so the two cannot disagree about who is owed a text. spa is /spa whole,
   rems /spareminders whole, stays /stays/<day>, bookings /bookings whole,
   fixes /phonefix whole - every one a node other screens already read.

   The number is the Worker's own reading - the desk's fix, then Mews'
   record - so a row that looks sendable here is one the Worker will send.
   The villa is the night's row holding the booking, a join of two owned
   facts, falling back to Mews' own villa for a booking with no row. */
function spaReminderRows(day, spa, rems, stays, bookings, fixes, nowMs){
  var stayOf = {}, villaOf = {}, out = [];
  Object.keys(stays || {}).forEach(function(v){
    var s = stays[v];
    if (s && typeof s === 'object' && s.id){ stayOf[s.id] = s; villaOf[s.id] = v; }
  });
  Object.keys(spa || {}).forEach(function(id){
    var t = spa[id];
    if (!t || typeof t !== 'object') return;
    Object.keys(t).forEach(function(tid){
      var r = t[tid];
      if (!r || typeof r !== 'object' || r.status !== 'booked' || r.day !== day) return;
      var pms = ((bookings || {})[id] || {}).pms || {}, st = stayOf[id] || {};
      var fix = (fixes || {})[id];
      var raw = String((fix && fix.phone) || pms.phone || '').trim();
      var rem = ((rems || {})[id] || {})[tid] || null;
      if (rem && typeof rem !== 'object') rem = null;
      out.push({ id: id, tid: tid, rec: r, rem: rem, raw: raw,
                 villa: villaOf[id] || (pms.villa != null ? String(pms.villa) : ''),
                 first: pms.first || '',
                 name: ((pms.first || st.first || '') + ' ' +
                        (pms.last || st.last || '')).trim() || r.name || 'Guest',
                 state: spaReminderState(r, rem, raw, nowMs) });
    });
  });
  out.sort(function(a, b){
    return String(a.rec.time || '').localeCompare(String(b.rec.time || '')) ||
           (+a.villa || 99) - (+b.villa || 99);
  });
  return out;
}

/* ── the action icon ─────────────────────────────────────────
   A number beside a menu entry meaning: something in there waits on you.
   Never stored - it is recomputed from the queue it counts on every page
   load, and while the page stays open (navRecount), which is exactly why
   it "stays until the action is done" without anything having to
   remember to clear it. Owner's naming, 25 Aug, first
   carried by Spa: suggestions the masseuse has made that the desk has not
   yet put to the guest. Add an entry to NAV_ACTIONS for the next feature
   that earns one.

   The fetch rides auth.js's queue, so it waits for a login like every
   other database read, and a failed count is no badge rather than an
   error: the menu must never break because a queue could not be asked. */
var NAV_ACTIONS = [
  { href: 'spa.html', need: 'spaBoard', count: function(role, cb){
      if (typeof DB === 'undefined') return;
      /* The badge shows what THIS login still owes, not every open item.
         The masseuse seeing the desk's two queues, or the desk seeing hers,
         is a badge that says "you have something to do" to somebody who
         does not - and a badge that cries wolf is one nobody reads.

         Who is who: the spa role is the masseuse, and every other login
         holding spaBoard is the desk. spaOwedCounts decides the rest.

         In practice the masseuse holds one screen and is always standing
         on it, so this badge is the desk's instrument - her own channel is
         the push notification. The split is wired and tested all the same:
         the day she is given a second screen is the wrong day to discover
         she has been shown reception's queue all along.

         Both nodes or neither. A half read would quietly undercount, and
         a badge that is wrong in the safe-looking direction is worse than
         no badge: it says done when the answer is unknown. */
      function node(path){
        return fetch(DB + path + '.json?v=' + Date.now())
          .then(function(r){
            if (!r.ok) throw new Error(path + ' HTTP ' + r.status);
            return r.json();
          });
      }
      Promise.all([node('/spa'), node('/bookings')]).then(function(res){
        var c = spaOwedCounts(res[0], res[1], dkey(new Date()));
        cb(role === 'spa' ? c.spa : c.desk);
      }).catch(function(){});
  } },
  /* Chat, 29 Sep: the guests with a message nobody has sorted.
     /contactnew holds exactly those, one child per guest, so the count is
     its keys - asked shallow, because the badge needs no message text. */
  { href: 'guest-contact.html', need: 'editBookings', live: true, count: function(role, cb){
      if (typeof DB === 'undefined') return;
      fetch(DB + '/contactnew.json?shallow=true&v=' + Date.now())
        .then(function(r){
          if (!r.ok) throw new Error('/contactnew HTTP ' + r.status);
          return r.json();
        })
        .then(function(j){ cb(j ? Object.keys(j).length : 0); })
        .catch(function(){});
  } },
  /* Tasks: the open tasks this login does. A team's own login counts its
     teams; the desk, who sort every message, counts every team's. All the
     teams or no badge: a count missing a team says less than it knows. */
  { href: 'tasks.html', need: 'tasks', live: true, count: function(role, cb){
      if (typeof DB === 'undefined') return;
      var u = window.NALA_USER;
      fetch(DB + '/contactsettings.json?v=' + Date.now())
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(cfg){
          /* The desk counts retired teams too: one only retires with
             nothing open, and a count that could miss a task is worse. */
          var teams = can(role, 'editBookings')
            ? contactTeams(cfg, true).map(function(t){ return t.key; })
            : teamsOf(cfg, u && u.email);
          return contactOpenTasks(teams);
        })
        .then(function(open){
          var n = 0;
          Object.keys(open).forEach(function(k){ n += Object.keys(open[k] || {}).length; });
          cb(n);
        })
        .catch(function(){});
  } }
];
/* Asked when a page opens, and again while it stays open (the owner,
   1 Oct: a guest's text did not show on Chat's icon "until after a page
   refresh"). Chat's and Tasks', a guest waiting on the answer, every 30
   seconds while the page is in front; every count the moment the phone
   brings the app back, or the back button brings a page back. Each live
   ask is small - Chat's is /contactnew's keys alone, Tasks' the open
   tasks - and Spa's, which reads every booking, waits for those moments.
   A failed ask keeps the count it had: the last one known, rather than a
   badge gone because a queue could not be asked this once. */
var NAV_N = {};            /* href: the last count heard */
var NAV_ROLE = null;
var NAV_EVERY = 30000;
/* The counts the opening asked: the role and the pages counted. The menu
   filter runs twice as a page opens - the page's own call, then the timer
   at the foot of this file - and until 2 Oct each pass asked every count,
   so Reservations opened asking Chat's, Tasks' and Spa's queues twice,
   Spa's reading every booking both times: 10 of its 47 database requests.
   A pass that would ask the same counts again asks nothing; another role,
   or a page newly counted, asks at once. The timers and the return to the
   app ask through navRecount and are not held here. */
var NAV_ASKED = null;
function navLink(href){
  var drop = document.getElementById('navDrop');
  if (!drop) return null;
  var links = drop.getElementsByTagName('a');
  for (var i = 0; i < links.length; i++){
    if ((links[i].getAttribute('href') || '').split('?')[0] === href) return links[i];
  }
  return null;
}
/* Whether this login is shown a count for the page: it may do the work and
   open the page, and the page has a link or an icon to wear it. One test,
   for the asking and for the opening's check above. */
function navCounts(a, role){
  /* The tab bar's icon for the page wears the same count (30 Sep), from
     the same one fetch - on the page you are on too: the owner, "Don't
     mute the counters when the icon is selected". The menu leaves out
     the page you are on, so there the icon alone carries it. */
  return can(role, a.need) && canOpen(role, a.href) &&
         !!(navLink(a.href) || document.getElementById('tab-' + pageKey(a.href)));
}
function navActionBadges(role){
  var first = NAV_ROLE === null;
  NAV_ROLE = role;
  var what = role + ' ' + NAV_ACTIONS.filter(function(a){ return navCounts(a, role); })
                                     .map(function(a){ return a.href; }).join(' ');
  if (what !== NAV_ASKED){ NAV_ASKED = what; navRecount(false); }
  if (!first) return;
  setInterval(function(){ if (!document.hidden) navRecount(true); }, NAV_EVERY);
  document.addEventListener('visibilitychange', function(){
    if (!document.hidden) navRecount(false);
  });
  window.addEventListener('pageshow', function(e){ if (e.persisted) navRecount(false); });
}
function navRecount(liveOnly){
  var role = NAV_ROLE;
  NAV_ACTIONS.forEach(function(a){
    if (liveOnly && !a.live) return;
    if (!navCounts(a, role)) return;
    var asked = a.asked = (a.asked || 0) + 1;
    a.count(role, function(n){
      if (asked < (a.heard || 0)) return;          /* an older answer, come late */
      a.heard = asked;
      NAV_N[a.href] = n || 0;
      drawNavCounts();
    });
  });
}
function navBadge(host, n){
  var b = host.querySelector('.navbadge');
  if (!n){ if (b) b.parentNode.removeChild(b); return; }
  if (!b){
    b = document.createElement('span');
    b.className = 'navbadge';
    host.appendChild(b);
  }
  b.textContent = n > 9 ? '9+' : String(n);
}
function drawNavCounts(){
  var rest = 0, waiting = false, keep = {};
  try { keep = JSON.parse(localStorage.getItem(COUNTS_KEPT) || '{}') || {}; } catch (e){ keep = {}; }
  NAV_ACTIONS.forEach(function(a){
    var link = navLink(a.href), tab = document.getElementById('tab-' + pageKey(a.href));
    if (!(a.href in NAV_N)){
      /* a page the menu's icon counts for, not answered yet this page */
      if (link && !tab && can(NAV_ROLE, a.need) && canOpen(NAV_ROLE, a.href)) waiting = true;
      return;
    }
    var n = NAV_N[a.href];
    if (link){
      navBadge(link, n);
      link.classList.toggle('hasact', !!n);
    }
    if (tab){ navBadge(tab.querySelector('.tabic'), n); keep[tab.id] = n; }
    /* A count whose page is in the menu and not on the bar - Spa, for
       the admin - adds to the menu icon's, so nothing waits behind a
       closed menu. */
    else if (link) rest += n;
  });
  /* The menu's icon is a sum: it keeps what it wore until every page it
     counts for has answered, rather than flashing a part of it. */
  var m = document.getElementById('tab-menu');
  if (m && !waiting){ navBadge(m.querySelector('.tabic'), rest); keep['tab-menu'] = rest; }
  try { localStorage.setItem(COUNTS_KEPT, JSON.stringify(keep)); } catch (e){}
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

/* The Notifications entry, wired wherever it appears.

   It lived on the Cleans board alone until 23 Aug, written into that page, so
   the only way to turn notifications on or off was to go to a board a chef
   cannot open. The push helpers were shared all along; only the wiring was
   not. Nothing here is board specific.

   It is a switch and not a destination, so it says what it will do rather than
   what it is: Notifications on means they are on, and tapping turns them off.
   A menu entry that reads the same in both states is a menu entry nobody
   trusts. */
function wireNotify(){
  var nb = document.getElementById('navNotify');
  if (!nb || nb.getAttribute('data-wired')) return;
  nb.setAttribute('data-wired', '1');

  /* The word stays put and a mark carries the state.

     It used to read "Notifications on" and "Notifications off", which is
     unreadable: there is no way to tell whether the words describe what is
     true or what tapping will do. Half the menus in the world use each. A tick
     or a cross beside a fixed word cannot be read as an instruction.

     Blocked and unavailable are not the off state and must not wear its mark.
     Off is a choice this person made and can undo here; blocked was decided in
     the phone's own settings, and unavailable means the site is not on the
     Home Screen and no tap here will change it. Both say so in words, because
     a mark that means "you cannot fix this from here" does not exist. */
  var TICK  = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">' +
              '<path d="M1 6.5 L4.5 10 L11 2" fill="none" stroke="currentColor" ' +
              'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CROSS = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">' +
              '<path d="M2 2 L10 10 M10 2 L2 10" fill="none" stroke="currentColor" ' +
              'stroke-width="1.8" stroke-linecap="round"/></svg>';

  function paint(state){
    var mark = state === 'on'  ? '<span class="navmark on">' + TICK + '</span>'
             : state === 'off' ? '<span class="navmark off">' + CROSS + '</span>'
             : '';
    var word = state === 'blocked'     ? 'Blocked on this phone'
             : state === 'unsupported' ? 'Add to Home Screen first'
             : '';
    nb.innerHTML = navIcon('navNotify') + '<span class="navlabel">Notifications</span>' +
                   (word ? '<span class="navnote">' + word + '</span>' : mark);
    nb.setAttribute('data-state', state);
  }

  /* Exposed for the suites: the three states cannot otherwise be produced in
     a headless browser, which reports every one of them as blocked. */
  window.__paintNotify = paint;
  if (typeof pushState === 'function') pushState(paint);

  nb.onclick = function(e){
    e.preventDefault(); e.stopPropagation();
    if (typeof pushOn !== 'function') return;
    var u = null;
    try { u = firebase.auth().currentUser; } catch (ex){}
    var st = nb.getAttribute('data-state');
    if (st === 'unsupported'){
      alert('Notifications need the app added to the Home Screen. Open the ' +
            'share menu and choose Add to Home Screen, then try again.');
      return;
    }
    if (st === 'blocked'){
      alert('Notifications are blocked for this site. Turn them on in your ' +
            'phone settings, then try again.');
      return;
    }
    nb.innerHTML = navIcon('navNotify') + '<span class="navlabel">Notifications</span>' +
                   '<span class="navnote">working</span>';
    if (st === 'on') pushOff(u, paint);
    else pushOn(u, window.NALA_ROLE, function(r){
      paint(r);
      if (r === 'blocked') alert('Notifications were not allowed. You can turn them on in your phone settings.');
      if (r === 'failed')  alert('Could not turn notifications on. Check the connection and try again.');
    });
  };
}
window.NALA_WIRENOTIFY = wireNotify;

/* Pages that never filtered their own menu get it applied for them. Pages
   that call it themselves are unaffected: running twice draws the menu and
   the bar again, and asks no count twice (navActionBadges). */
(function(){
  var tries = 0;
  var t = setInterval(function(){
    if (++tries > 60) { clearInterval(t); return; }
    if (!window.NALA_ROLE) return;
    navFilterShared(window.NALA_ROLE);
    wireNotify();
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
   which needs another go. Anything else is the second one.

   Except an error that already speaks the person's language. A page's own
   pre-write check (the Spa board's sanity read, 9 Sep) refuses with a line
   naming what actually stands and what to do about it; flattening that to
   "check the connection" sends them to the wrong remedy, which is the exact
   mistake this function exists to prevent. Such an error carries said:true
   and its message rides through untouched.                              */
function saveFailWords(e){
  var m = '' + (e && (e.message || e));
  if (e && e.said) return m;
  if (/rejected|denied|permission|401|403/i.test(m))
    return 'The change was not allowed - tell the manager.';
  return 'Not saved - check the connection and try again.';
}

/* Where one villa stands on tonight's dinner invitation, and the ONE reader
   that says so. Lived in invitations.html until 8 Sep, where the Dashboard
   could not reach it, so that board reconstructed the answer and got it
   wrong in a way nobody would have seen until a guest was not asked: a
   FAILED send climbs back into 'ready' here, and the reconstruction counted
   it as sent.

   kind is the fact; line is how that page says it. A caller that only wants
   to know who is still owed an invitation reads kind === 'ready'.

     nophone   no usable mobile on the booking, so nothing can be sent
     answered  they have already said, by cell or on their pre-arrival form
     sent      accepted by the carrier, and not since failed delivery
     ready     still to ask, INCLUDING a send that failed

   dateKey is a parameter rather than the page's TODAY: a guard that depends
   on a global the caller may not have is not a guard. */
function timeOf(iso){
  var d = parseISO(iso); if (!d) return '';
  var h = d.getHours(), m = String(d.getMinutes()).padStart(2, '0');
  return (h % 12 || 12) + ':' + m + (h < 12 ? 'am' : 'pm');
}

function stateOf(villa, stay, cell, invite, fix, dateKey){
  /* A number fixed at the desk (/phonefix/<booking>) outranks the Mews copy:
     Mews cannot be written from here and its next sync would revert any edit
     made to the stay. The Worker reads the same record before sending. */
  var raw = String((fix && fix.phone) || (stay && stay.phone) || '').trim();
  if (!raw) return { kind:'nophone', line:'No phone number on the booking \u00B7 tap to add one',
                     tickable:false, fixable:true, ticked:false };
  if (!normalisePhone(raw))
    return { kind:'nophone', line:'Not a mobile number \u00B7 ' + raw + ' \u00B7 tap to fix',
             tickable:false, fixable:true, ticked:false };
  /* The cell is tonight's answer only if it belongs to the booking now in the
     villa - the same guard the Reservations board applies through
     dinnerElsewhere. Reading it raw put a moved booking's "set by reception"
     onto whoever took the villa next, so an unasked arrival sat in Answered and
     was never sent an invitation (villa 4, 19 Sep). stay is this villa's
     current booking; stay.id is its booking id, which is what a cell stamps. */
  if (!cellIsForBooking(cell, stay && stay.id)) cell = null;
  if (cell && cell.status){
    var what = cell.status === 'in'
      ? 'Dining' + (cell.pax ? ' \u00B7 ' + cell.pax : '') : 'Not dining';
    var who = cell.by === 'guest'
      ? (cell.at ? 'answered ' + timeOf(cell.at) : 'answered')
      : 'set by reception';
    return { kind:'answered', in: cell.status === 'in',
             line: what + ' \u00B7 ' + who, tickable:true, ticked:false };
  }
  /* No cell - so read what the guest already said on their pre-arrival form,
     through the same reader the Reservations board uses (formDinnerCell,
     nala-shared.js: arrival night only, any answer given counts, the cell
     above wins the moment anyone sets one). Until 4 Sep this page read the
     cell alone, so an arriving guest who had answered days ago sat in To
     send, PRE-TICKED, and Send would have re-asked a question we were
     already cooking to. Unticked, like every answered row: sending anyway
     is a deliberate second tap, not the default. */
  var form = formDinnerCell(villa, PREARRIVAL_BY_VILLA[String(villa)], stay, dateKey);
  if (form)
    return { kind:'answered', in: form.status === 'in',
             line: (form.status === 'in'
                     ? 'Dining' + (form.pax ? ' \u00B7 ' + form.pax : '')
                     : 'Not dining') + ' \u00B7 answered on the pre-arrival form',
             tickable:true, ticked:false };
  if (invite && invite.status === 'sent'){
    /* "Sent" is only ClickSend accepting the message; the handset receipt
       is the real answer. A failed delivery is the sender's problem again,
       so it climbs back into To send with the carrier's words. */
    if (invite.delivery === 'failed')
      return { kind:'ready', bad:true, tickable:true, ticked:false,
               line:'Not delivered' +
                    (invite.deliveryText ? ' \u00b7 ' + invite.deliveryText : '') };
    return { kind:'sent', tickable:true, ticked:false,
             line:'Sent ' + timeOf(invite.sentAt) +
                  (invite.delivery === 'delivered' ? ' \u00b7 delivered'
                   : invite.providerId ? ' \u00b7 delivery unconfirmed' : '') };
  }
  if (invite && invite.status === 'failed')
    return { kind:'ready', line:'Send failed ' + timeOf(invite.sentAt) +
             (invite.error ? ' \u00B7 ' + invite.error : ''), bad:true,
             tickable:true, ticked:true };
  return { kind:'ready', line:'Not asked, not answered', tickable:true, ticked:true };
}

/* Which day a spa record belongs to on the board. Moved out of spa.html
   on 8 Sep so the Dashboard could reuse it rather than rebuild it.

   Which day a record belongs to on the board. A booked or suggested
   treatment sits on its own day; a request and a decline sit on the day the
   guest asked about, because that is when somebody will look for them. */
function dayOf(rec){
  if (rec.status === 'booked' || rec.status === 'suggested') return rec.day || '';
  return rec.reqDay || rec.day || '';
}
