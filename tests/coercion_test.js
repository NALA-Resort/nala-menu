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

/* ── who did it, on the Cleans board ─────────────────────────────────
 * Two faults, one after the other, both found on a real board.
 *
 * First it was initials against a record that holds ONE name field, so a
 * single first name came out as one letter. B is not a person, and two staff
 * whose names start alike were the same badge.
 *
 * Then, renaming Ben to Ben Davidson in Settings changed nothing at all, which
 * looked like the shortening was still broken and was not. takenBy and doneBy
 * stored the NAME as it read when the button was pressed, so every record kept
 * the old one for ever. The key is stored now and the name is looked up when
 * the tile is drawn.
 */
eval("var STAFF_RECORDS=null;" + grab('shortNameOf') + grab('shortTagFor')
     + grab('fullNameFor'));
STAFF_RECORDS = {
  'ben@nala,com': { name: 'Ben Davidson', role: 'housekeeping' },
  'ana@nala,com': { name: 'Ana',          role: 'housekeeping' }
};

[['Ben Davidson', 'BD'],
 ['Ana',          'ANA'],   // one word: three letters, never one
 ['Jo',           'JO'],
 ['  Ana Ruiz ',  'AR'],
 ['',             ''],
 [null,           ''],
 [undefined,      '']].forEach(function (pair) {
  ck('a name of ' + JSON.stringify(pair[0]) + ' shortens to ' +
     JSON.stringify(pair[1]), shortNameOf(pair[0]) === pair[1]);
});
ck('two people whose names start alike are not the same badge',
   shortNameOf('Ana') !== shortNameOf('Ali'));

/* The rename. This is the whole point of storing a key. */
ck('a record holding a key follows a rename in Settings',
   shortTagFor('ben@nala,com') === 'BD');
ck('and the full name behind it is the new one too',
   fullNameFor('ben@nala,com') === 'Ben Davidson');

/* Records written before the change hold a plain name. They cannot follow a
   rename, but they must still read as somebody. */
ck('an older record holding a name still reads as that name',
   shortTagFor('Ben') === 'BEN' && fullNameFor('Ben') === 'Ben');
ck('and a key for somebody since removed reads as the key, not as blank',
   shortTagFor('gone@nala,com') !== '');
ck('nothing stored stays nothing, so the phrase can drop',
   shortTagFor('') === '' && shortTagFor(null) === '' && fullNameFor(null) === '');

/* The board writes the key, not the name. A single grep is worth more here
   than any amount of reasoning: this is the line that regressed. */
const cleaners = fs.readFileSync(path.join(ROOT, 'cleaners.html'), 'utf8');
ck('the board stores the staff key when a job is taken',
   /takenBy:\s*window\.NALA_KEY/.test(cleaners));
ck('and when a job is finished',
   /doneBy:\s*window\.NALA_KEY/.test(cleaners));

/* ── the two forms have to ask the same questions ────────────────────
 * front-desk.html and prearrival.html are the SAME form: one filled in by the
 * guest, one filled in with them at the desk. They cannot share their option
 * lists, because the guest page deliberately does not load nala-shared.js and
 * sharing would put staff code in a guest's browser. So the lists are
 * duplicated on purpose, and nothing but this checks they agree.
 *
 * They did not. Purpose is stored as the LABEL, not a key, so a list differing
 * by one word threw the guest's answer away: they chose "A celebration", the
 * desk offered "Celebration", nothing matched, the chip came up unselected and
 * the next save dropped it.
 */
const desk = fs.readFileSync(path.join(ROOT, 'front-desk.html'), 'utf8');

function listOf(src, name) {
  const i = src.indexOf('var ' + name + ' = ');
  if (i < 0) throw new Error(name + ' is gone from one of the forms');
  const end = src.indexOf('];', i);
  return src.slice(i, end + 1)
            .match(/'((?:[^'\\]|\\.)*)'/g)
            .map(function (x) { return x.slice(1, -1); });
}

/* Purpose is compared exactly, because the label IS the stored value. */
const dp = listOf(desk, 'PURPOSE'), gp = listOf(guest, 'PURPOSE');
ck('both forms offer the same reasons for the stay, word for word',
   JSON.stringify(dp) === JSON.stringify(gp));

/* The arrival slots: the desk carries a short form as well, so only the keys
   and the guest facing wording are compared. */
const de = listOf(desk, 'ETA_SLOTS'), ge = listOf(guest, 'ETA_SLOTS');
ck('both forms offer the same arrival times',
   ge.every(function (v) { return de.indexOf(v) > -1; }));
ck('and the desk can actually set one, rather than only read it back',
   /id="eChips"/.test(desk) && /a\.arriveSlot\s*=/.test(desk));
ck('including the note the open ended slots ask for',
   /id="fEtaNote"/.test(desk) && /a\.arriveNote\s*=/.test(desk));

/* Approach stores a key, so its labels are free to differ. They are matched
   anyway: reading a guest back a different sentence to the one they answered
   is how you lose them at the desk. */
const da = listOf(desk, 'APPROACH'), ga = listOf(guest, 'APPROACH');
ck('and the same words about how they plan to eat',
   JSON.stringify(da) === JSON.stringify(ga));

/* Every field the guest can answer must be settable at the desk, or a guest
   with no form has no way to have it recorded. */
['arriveSlot', 'arriveNote', 'dining', 'pax', 'diets', 'noDiets', 'dnote',
 'purpose', 'approach', 'occasion', 'wellness', 'wellDay', 'wellTime', 'note',
 'companion'
].forEach(function (f) {
  ck('the desk saves ' + f, new RegExp('\\b' + f + '\\s*:').test(desk));
});

/* ── the companion ───────────────────────────────────────────────────
 * The second guest's name. Usually gathered on the pre-arrival form, but Mews
 * has it when the booking was taken over the phone, so both forms need it and
 * the desk has to be able to correct whatever Mews holds.
 */
ck('the guest form asks who is coming with them',
   /id="companion"/.test(guest) && /a\.companion/.test(guest));
ck('and the desk offers the same field',
   /id="fCompanion"/.test(desk) && /a\.companion/.test(desk));
/* Asked only when there is somebody else to name. A booking for one has no
   companion, and the question would read as nobody having looked. */
ck('the guest is asked only when the booking is for more than one',
   /adults\s*>=\s*2/.test(guest));
ck('and so is the desk', /adults\)\s*>=\s*2/.test(desk));
/* The rules had $other false on prearrival, so a field they do not name is
   refused outright: this one needed adding, and needs the console paste. */
ck('the rules accept it, which they did not before',
   !!rules.rules.bookings.$id.prearrival.companion);
ck('a name saves, and something the length of a paragraph does not',
   db.update('/bookings/' + GUID + '/prearrival', { companion: 'Ana Ruiz' }).allowed
   && !db.update('/bookings/' + GUID + '/prearrival',
                 { companion: 'x'.repeat(200) }).allowed);
/* The Worker's field name is a guess against Zapier's flattening of nested
   Mews objects, so what is asserted is that it is coerced like everything
   else: a wrong guess must yield null, never a rejected write. */
ck('the Worker carries it onto the booking and the night',
   /companion:\s*asText/.test(fs.readFileSync(path.join(ROOT, 'worker/mews-sync.js'), 'utf8')));

console.log('RESULT: ' + P + ' passed, ' + F + ' failed');
process.exit(F ? 1 : 0);
