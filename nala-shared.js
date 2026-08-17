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

/* ── dietary conflicts against the tagged menu ─────────────── */
function menuConflicts(menu, diets){
  if (!diets || !diets.length || !menu) return [];
  var hits = [];
  ['bread','entree','main','dessert'].forEach(function(k){
    var dish = menu[k];
    if (!dish || !dish.conflicts) return;
    dish.conflicts.forEach(function(tag){
      diets.forEach(function(d){
        if (String(d).toLowerCase() === String(tag).toLowerCase())
          hits.push({ dish: dish.name || k, diet: d });
      });
    });
  });
  return hits;
}

function dietHTML(diets, sep, cls){
  if(!diets||!diets.length) return '';
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
      .catch(function(){ return null; })
  ]).then(function(res){
    DINNER_CELLS = res[1] || {};
    return res[0];
  });
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
  /* One party can hold several villas. Two reservations under one group are
     not two guests who happen to share a surname, and a board that treats them
     as strangers will seat them apart. */
  if (stay.groupId)  out.groupId = stay.groupId;
  return out;
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
  if (known.name) return withDineProvenance(
    Object.assign({}, known, { room:String(n), status:null }), null, known);
  return null;
}

/* clean = departing on the sheet date; service = staying on;
   verify = no usable data. The housekeeping rule, in one place.  */
function hkClassify(rec, todayK, hk){
  /* A manager can set the job for the day by hand - most often on a villa the
     booking data cannot confirm - and that choice beats what the dates imply.
     Stored at /hk/<date>/<villa>/kind so it expires with the day.          */
  if (hk && (hk.kind === 'clean' || hk.kind === 'svc' ||
             hk.kind === 'pre'   || hk.kind === 'vac')) return hk.kind;
  if (rec && rec.status === 'vacant') return 'vac';
  if (rec){
    var d = parseDepDate(rec.departs);
    var dk = d ? dkey(d) : null;
    if (dk === todayK) return 'clean';
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
  admin:        ['cleansBoard','cleansMarks','setJob','resBoard','editBookings','resSheet','publishMenu','manageStaff'],
  chef:         ['resBoard','resSheet','publishMenu'],
  waiter:       ['cleansBoard','resBoard','editBookings','resSheet'],
  housekeeping: ['cleansBoard','cleansMarks'],
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
function roleOf(user){
  var e = user && (typeof user === 'string' ? user : user.email);
  if (!e || !STAFF_RECORDS) return null;
  var rec = STAFF_RECORDS[emailKey(e)];
  var r = normaliseRole(rec && rec.role);
  return isRole(r) ? r : null;
}

function can(role, what){
  var g = ROLE_GRANTS[normaliseRole(role)];
  return !!(g && g.indexOf(what) > -1);
}

/* Where a role should land. Housekeeping opening the app got the Reservations
   board, which they may not see, so their first screen was a refusal. A role
   that cannot see the page it arrived on is a routing problem, not an access
   one: send them to their own board instead of telling them off.        */
var ROLE_HOME = { admin:'tally.html', chef:'tally.html', waiter:'tally.html',
                  housekeeping:'cleaners.html' };
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
function loadStaff(cb){
  fetch(DB + '/staff.json')
    .then(function(r){ return r.ok ? r.json() : Promise.reject(new Error('http ' + r.status)); })
    .then(function(j){ cb(setStaffRecords(j), null); })
    .catch(function(err){ STAFF_RECORDS = null; cb(null, err); });
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

/* The notification settings, written by the app the first time an admin opens
   a board and finds none. Typing this into the console by hand was slow and
   easy to get wrong, and every new event type would mean doing it again.
   Only an admin may write /notify, which the rules enforce, so this quietly
   does nothing for everyone else.                                        */
var NOTIFY_DEFAULTS = {
  on: true,
  hours: { from: '07:30', to: '18:00' },
  events: {
    departed:  { housekeeping:true, admin:true, waiter:false, chef:false },
    available: { housekeeping:true, admin:true, waiter:false, chef:false },
    cleaned:   { housekeeping:true, admin:true, waiter:true,  chef:false },
    serviced:  { housekeeping:true, admin:true, waiter:true,  chef:false }
  }
};

function ensureNotifySettings(role){
  if (normaliseRole(role) !== 'admin') return;
  fetch(DB + '/notify.json')
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(cfg){
      /* Only fill in what is missing. Overwriting would undo the manager's
         own choices every time a board loaded.                          */
      if (cfg && cfg.events && cfg.hours) return;
      var merged = {
        on:     (cfg && typeof cfg.on === 'boolean') ? cfg.on : NOTIFY_DEFAULTS.on,
        hours:  (cfg && cfg.hours) ? cfg.hours : NOTIFY_DEFAULTS.hours,
        events: (cfg && cfg.events) ? cfg.events : NOTIFY_DEFAULTS.events
      };
      return fetch(DB + '/notify.json', { method:'PUT', body: JSON.stringify(merged) });
    })
    .catch(function(){});
}
