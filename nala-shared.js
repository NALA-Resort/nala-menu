/* NALA shared helpers - one copy of the logic every staff page repeats.
   Plain globals, same names the pages already use, so page code reads
   unchanged. See STYLEGUIDE.md and AUDIT.md.                      v2 */

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
function fetchRoomGuests(endKey, days){
  days = days || 14;
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
    return all;
  });
}

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

/* one room, one record: staff override beats the guest's own answer,
   whoever opened the link fills the gaps                            */
function roomRecord(n, responses, manual, roomguests){
  var mk = 'room-'+n, m = manual[mk];
  var best = null;
  for (var k in responses){
    var g = responses[k];
    if (String(g.room) !== String(n)) continue;
    if (!best || (g.at||'') > (best.at||'')) best = g;
  }
  var known = roomguests[String(n)] || {};
  if (m && m.override) return Object.assign({}, known, best || {}, m, { room:String(n) });
  if (best) return Object.assign({}, known, best);
  if (m)    return Object.assign({}, known, m, { room:String(n) });
  if (known.name) return Object.assign({}, known, { room:String(n), status:null });
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
  waiter:       ['resBoard','editBookings','resSheet'],
  housekeeping: ['cleansBoard','cleansMarks']
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
