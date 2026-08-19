/* Does what the Worker sends match what the rules will accept?
 *
 * These are two files nobody edits together. rules.json is pasted into the
 * Firebase console by hand; worker/mews-sync.js deploys from the repo. Nothing
 * connects them, so a field added to one and not the other is invisible until
 * it reaches production.
 *
 * When it does, the failure is worse than a plain outage. The database
 * validates every field it knows, and one wrong type refuses the WHOLE write.
 * The error is "Permission denied", which reads like a credentials fault, so
 * whoever is debugging goes looking at logins and secrets. That is 18 Aug:
 * check-ins failing with 401 while the sync account was fine, because
 * customerId was added and could arrive as something other than a string.
 *
 * So this loads the real rules and the real coercion helpers out of the real
 * Worker, and throws the values Zapier actually sends at them. Zapier promises
 * no types: the same field is a string on one trigger and a number on the
 * next, and a field that is normally a GUID arrives nested when Mews nests it.
 *
 *     node tests/coercion_test.js
 */
const targaryen = require('targaryen');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const rules = JSON.parse(fs.readFileSync(path.join(ROOT, 'rules.json'), 'utf8'));
const src = fs.readFileSync(path.join(ROOT, 'worker/mews-sync.js'), 'utf8');

/* Lifted out of the Worker rather than copied here, so this cannot pass
   against a version of the helpers that no longer ships. */
const NAMES = ['asText', 'asCount', 'asVilla', 'asNumberOrText'];
const helpers = NAMES.map(function (n) {
  const i = src.indexOf('function ' + n + '(');
  if (i < 0) throw new Error('the Worker no longer defines ' + n);
  let depth = 0, k = src.indexOf('{', i);
  for (;; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') depth--;
    if (depth === 0) break;
  }
  return src.slice(i, k + 1);
}).join('\n');
eval(helpers);

const data = {
  staff: { 'sync@nalaresort,com,au': { name: 'NALA Sync', role: 'sync' } },
  bookings: {}, stays: {}
};
const auth = { uid: 'sync', token: { email: 'sync@nalaresort.com.au' } };
const db = targaryen.database(rules, data).as(auth);

let P = 0, F = 0;
function ck(name, cond) {
  console.log((cond ? 'PASS ' : 'FAIL ') + name);
  cond ? P++ : F++;
}

const GUID = '6cb6d13f-beda-45eb-9c1b-b4880157a2bf';

/* Every shape a field has been seen to take, or plausibly could. Each is put
   through EVERY field at once: if any single one can refuse the write, the
   whole reservation is lost, so there is no value in testing them one by one. */
const SHAPES = [
  ['a GUID string', GUID],
  ['a number', 12345],
  ['a nested object', { Id: 'x' }],
  ['an array', ['a']],
  ['a boolean', true],
  ['null', null],
  ['an empty string', ''],
  ['a string past every length limit', 'x'.repeat(200)]
];

SHAPES.forEach(function (pair) {
  const label = pair[0], v = pair[1];

  const pms = {
    first: asText(v, 120), last: asText(v, 120), phone: asText(v, 40),
    arrive: asText(v, 40), depart: asText(v, 40), villa: asVilla(v),
    state: 'confirmed', mewsState: asText(v, 30),
    bookingNumber: asNumberOrText(v), groupId: asText(v, 64),
    customerId: asText(v, 64),
    adults: asCount(v, 0, 40), children: asCount(v, 0, 40),
    notes: null, notesType: null, spaceState: null, guestNotes: null,
    updated: asText(v, 40), syncedAt: new Date().toISOString()
  };
  ck('the booking write is accepted with every field ' + label,
     db.update('/bookings/' + GUID + '/pms', pms).allowed);

  /* id is the one field a night cannot do without: the rule requires it, and
     a night with no booking id cannot be matched back to anything. */
  const stay = {
    id: asText(GUID, 64),
    first: asText(v, 120), last: asText(v, 120), phone: asText(v, 40),
    arrive: asText(v, 40), depart: asText(v, 40),
    adults: asCount(v, 0, 40), groupId: asText(v, 64),
    number: asNumberOrText(v), updated: asText(v, 40)
  };
  ck('the night write is accepted with every field ' + label,
     db.update('/stays/2026-08-18/4', stay).allowed);
});

/* The other half of the test, and the more important half. Without these the
   suite would pass just as happily against rules that accepted anything, and
   would prove nothing about the coercion at all. */
ck('an object customerId is refused when NOT coerced',
   !db.update('/bookings/' + GUID + '/pms',
              { first: 'A', customerId: { Id: 'x' } }).allowed);
ck('a string adults is refused when NOT coerced',
   !db.update('/bookings/' + GUID + '/pms',
              { first: 'A', adults: '2' }).allowed);
ck('a numeric first name is refused when NOT coerced',
   !db.update('/bookings/' + GUID + '/pms', { first: 123 }).allowed);
ck('an over long groupId is refused when NOT coerced',
   !db.update('/bookings/' + GUID + '/pms',
              { first: 'A', groupId: 'x'.repeat(200) }).allowed);

/* A name is never invented to satisfy a validator. A number where a name
   should be is not a name, and writing it would put a lie on the board. */
ck('a bad name becomes nothing rather than a made up string',
   asText({ First: 'x' }, 120) === null && asText(true, 120) === null);
ck('a bad head count becomes nothing rather than zero',
   asCount('lots', 0, 40) === null && asCount({}, 0, 40) === null);
ck('a head count outside the possible range is dropped, not clamped',
   asCount(999, 0, 40) === null && asCount(-1, 0, 40) === null);
ck('a number is accepted as text, because Zapier sends ids both ways',
   asText(12345, 64) === '12345');
ck('a numeric head count sent as text is read as a number',
   asCount('2', 0, 40) === 2);

/* ── the pre-arrival form ────────────────────────────────────────────
 * Same fault, found on 19 Aug from the other end. "Here for" is a multi
 * select, both forms held it as a list, and the rule validates one string.
 * One field of the wrong type refuses the WHOLE write, so a guest who ticked
 * a reason silently failed to save their entire form, and reception could not
 * confirm them from the arrivals row. Both screens said only "could not save",
 * which reads as a connection problem.
 *
 * The helpers are lifted out of the shipped nala-shared.js for the same reason
 * as the Worker's: a copy here would pass after the real one drifted.
 */
const shared = fs.readFileSync(path.join(ROOT, 'nala-shared.js'), 'utf8');
const grab = function (n) {
  const i = shared.indexOf('function ' + n + '(');
  if (i < 0) throw new Error('nala-shared.js no longer defines ' + n);
  let depth = 0, k = shared.indexOf('{', i);
  for (;; k++) {
    if (shared[k] === '{') depth++;
    else if (shared[k] === '}') depth--;
    if (depth === 0) break;
  }
  return shared.slice(i, k + 1);
};
eval("var PURPOSE_SEP=' \u00b7 ';" + grab('purposeList') + grab('purposeText'));

[[], ['A celebration'], ['A celebration', 'Exploring the area']].forEach(function (v) {
  ck('a pre-arrival with ' + v.length + ' purpose(s) is accepted',
     db.update('/bookings/' + GUID + '/prearrival',
               { dining: true, purpose: purposeText(v) }).allowed);
  ck('and the same purposes as a raw list are still refused, uncoerced',
     v.length === 0 ||
     !db.update('/bookings/' + GUID + '/prearrival',
                { dining: true, purpose: v }).allowed);
});

/* Records written before 19 Aug hold a list and will for as long as those
   bookings live, so reading has to accept both shapes forever. */
ck('a list written before today still reads back',
   purposeList(['A celebration', 'Exploring the area']).length === 2);
ck('and so does the string written from now on',
   purposeList('A celebration \u00b7 Exploring the area').length === 2);
ck('nothing chosen stays nothing, rather than becoming a phantom entry',
   purposeList('').length === 0 && purposeList(null).length === 0
   && purposeList(undefined).length === 0);

/* The guest page keeps its own copy on purpose: it must not load staff code.
   The separator has to match, or a guest's answers come back as one long
   string on the desk. */
const guest = fs.readFileSync(path.join(ROOT, 'prearrival.html'), 'utf8');
ck('the guest page carries its own copy, not the staff file',
   guest.indexOf('function purposeText') > -1
   /* The script TAG, not any mention of it: the comment saying why the file
      is not loaded here is exactly the sentence a text search trips over. */
   && !/<script[^>]+nala-shared\.js/.test(guest));
ck('and separates purposes the same way the staff copy does',
   (guest.match(/PURPOSE_SEP\s*=\s*'([^']*)'/) || [])[1] ===
   (shared.match(/PURPOSE_SEP\s*=\s*'([^']*)'/) || [])[1]);

/* ── the short name on the Cleans board ──────────────────────────────
 * This was initials, and initials do not work here: the staff record holds
 * ONE name field, and most of them are a single first name, so nearly
 * everybody came out as one letter. B is not a person, and it reached a real
 * board before anybody noticed, because the fixtures all used two names.
 */
eval(grab('shortNameOf'));
[['Ben Doyle', 'BEN'],
 ['Ana',       'ANA'],      // the case initials got wrong
 ['Jo',        'JO'],       // shorter than three, taken as it is
 ['bo',        'BO'],
 ['  Ana Ruiz ', 'ANA'],    // stray spaces from a typed field
 ['',          ''],
 [null,        ''],
 [undefined,   '']].forEach(function (pair) {
  ck('a staff name of ' + JSON.stringify(pair[0]) + ' reads as ' +
     JSON.stringify(pair[1]), shortNameOf(pair[0]) === pair[1]);
});
ck('two people with different first names do not collide',
   shortNameOf('Ana') !== shortNameOf('Ben'));

console.log('RESULT: ' + P + ' passed, ' + F + ' failed');
process.exit(F ? 1 : 0);
