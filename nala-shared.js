/* NALA shared helpers — one copy of the logic every staff page repeats.
   Plain globals, same names the pages already use, so page code reads
   unchanged. See STYLEGUIDE.md and AUDIT.md.                      v1 */

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
  var d = new Date(s);
  return isNaN(d) ? null : d;
}

function ord(n){
  var s=['th','st','nd','rd'], v=n%100;
  return n + (s[(v-20)%10] || s[v] || s[0]);
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
  var days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  var mo=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var el = document.getElementById('date') || document.getElementById('title');
  if (el) el.textContent =
    days[VIEW.getDay()]+' '+VIEW.getDate()+' '+mo[VIEW.getMonth()]+' '+VIEW.getFullYear();
  var pv = document.getElementById('dPrev'), nx = document.getElementById('dNext'),
      td = document.getElementById('dToday');
  if (pv) pv.onclick = function(){ shiftDate(-1); };
  if (nx) nx.onclick = function(){ shiftDate(1); };
  if (td){
    td.onclick = function(e){ if (e) e.preventDefault(); goToday(); };
    if (!isToday()) td.classList.add('show');
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
