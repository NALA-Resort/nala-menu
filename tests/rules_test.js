/* The database rules, checked against every write the app actually makes.
 *
 *   npm install targaryen        (once, in this directory)
 *   node tests/rules_test.js
 *
 * Rules are the one part of this app that cannot be tested by opening a page:
 * they run on Google's servers, the copy in the repo is not the deployed
 * thing, and a mistake in them shows up as a write that silently fails on
 * somebody's phone in the middle of service. So they are checked here instead,
 * with targaryen, which evaluates the rules exactly as the database does.
 *
 * The suite is in two halves and the first half matters more. Before asking
 * whether a bad write is refused, it asks whether every real write is still
 * allowed: a validate rule that is too strict does not look like a security
 * improvement, it looks like reception being unable to seat a guest.
 *
 * Every body below was copied from the code that sends it, not invented.
 */
const fs = require('fs');
const path = require('path');
const targaryen = require('targaryen');

/* RULES_FILE lets the same suite be pointed at another copy of the rules,
   which is how the new ones were diffed against the deployed ones before
   anybody was asked to paste them into the console. */
const RULES_PATH = process.env.RULES_FILE || path.join(__dirname, '..', 'rules.json');
const RULES = JSON.parse(fs.readFileSync(RULES_PATH, 'utf8'));

const TODAY = new Date().toISOString().slice(0, 10);
const NOW = new Date().toISOString();

/* The staff list the rules read to decide a role. The email key is the
   address with dots turned into commas, which is what auth.js sends. */
const SEED = {
  staff: {
    'staff@nalaresort,com,au':        { name: 'Admin', role: 'admin' },
    'reception@nalaresort,com,au':    { name: 'Reception', role: 'staff' },
    'chef@nalaresort,com,au':         { name: 'Chef', role: 'chef' },
    'waiter@nalaresort,com,au':       { name: 'Waiter', role: 'waiter' },
    'housekeeping@nalaresort,com,au': { name: 'HK', role: 'housekeeping' },
    '482913@staff,nala':              { name: 'NALA Sync', role: 'sync' }
  },
  dinner: { [TODAY]: {
    '2': { status: 'in', pax: 2, room: '2', by: 'staff', at: NOW },
    '3': { status: 'in', pax: 2, room: '3', by: 'guest', at: NOW }
  } },
  bookings: { 'b-1': { pms: { villa: '4', first: 'Robyn', last: 'Williams' } } }
};

/* The rules read auth.token.email, so the address has to be in the token
   claims rather than beside them, which is where the real Firebase SDK puts
   it. Written out per user so a typo shows up as one failing line rather than
   as a role quietly not applying. */
function signedIn(email) { return { uid: email, email: email, token: { email: email } }; }
const ADMIN  = signedIn('staff@nalaresort.com.au');
const DESK   = signedIn('reception@nalaresort.com.au');
const CHEF   = signedIn('chef@nalaresort.com.au');
const HK     = signedIn('housekeeping@nalaresort.com.au');
const WAITER = signedIn('waiter@nalaresort.com.au');
const SYNC   = signedIn('482913@staff.nala');
const GUEST  = null;

let P = 0, F = 0;
function ck(name, cond) {
  console.log((cond ? 'PASS ' : 'FAIL ') + name);
  cond ? P++ : F++;
}

const db = targaryen.database(RULES, SEED);
function as(user) { return user ? db.as(user) : db; }

function allowed(user, method, at, value) {
  const d = as(user);
  const r = method === 'update' ? d.update(at, value) : d.write(at, value);
  return r.allowed;
}
function can(name, user, at, value)    { ck(name, allowed(user, 'write', at, value) === true); }
function cannot(name, user, at, value) { ck(name, allowed(user, 'write', at, value) === false); }
function canPatch(name, user, at, value)    { ck(name, allowed(user, 'update', at, value) === true); }
function cannotPatch(name, user, at, value) { ck(name, allowed(user, 'update', at, value) === false); }

console.log('--- every write the app makes is still allowed ---');

/* front-desk.html dinnerCell(), the fullest cell anything writes */
can('Front Desk writes a full dinner cell', DESK, `/dinner/${TODAY}/5`, {
  status: 'in', pax: 4, room: '5', bookingId: 'b-1', by: 'staff', at: NOW,
  diets: ['Gluten free', 'Nut allergy'], dnote: 'coeliac, not a preference',
  note: 'anniversary', pmsUpdated: NOW
});
can('and one with no dietaries at all', DESK, `/dinner/${TODAY}/6`, {
  status: 'out', pax: 0, room: '6', bookingId: 'b-1', by: 'staff', at: NOW,
  diets: [], dnote: '', note: ''
});

/* tally.html writeManual() and its variants */
can('Reservations marks a villa vacant', DESK, `/dinner/${TODAY}/7`,
    { status: 'vacant', pax: 0, room: '7', source: 'manual' });
can('Reservations seats a walk-in with an override', DESK, `/dinner/${TODAY}/8`,
    { status: 'in', pax: 2, room: '8', override: true, source: 'manual' });
can('Reservations writes an external diner with a name and note', DESK, `/dinner/${TODAY}/9`,
    { status: 'in', pax: 2, name: 'Ben Davidson', phone: '0400000000',
      note: 'friend of the owner', diets: ['Vegan'], source: 'manual' });

/* index.html, the guest answering their own dinner, signed in to nothing */
/* index.html, the whole cell as the guest page sends it, flags and all */
can('a guest answers dinner in an empty villa', GUEST, `/dinner/${TODAY}/10`,
    { status: 'in', pax: 2, flag: true, premenu: false, nodiet: false,
      note: 'we may be a little late', dnote: 'coeliac',
      diets: ['Gluten free'], room: '10', bookingId: 'b-1',
      by: 'guest', at: NOW });
can('and declines without leaving anything behind', GUEST, `/dinner/${TODAY}/12`,
    { status: 'out', pax: 0, flag: false, premenu: false, nodiet: false,
      note: '', dnote: '', diets: [], room: '12', bookingId: 'b-1',
      by: 'guest', at: NOW });
can('a guest overwrites their own earlier answer', GUEST, `/dinner/${TODAY}/3`,
    { status: 'out', pax: 0, room: '3', by: 'guest', at: NOW });
cannot('but a guest cannot overwrite a staff decision', GUEST, `/dinner/${TODAY}/2`,
       { status: 'in', pax: 2, room: '2', by: 'guest', at: NOW });

/* prearrival.html, the guest form. No sign in at all. */
canPatch('the guest pre-arrival form saves', GUEST, '/bookings/b-1/prearrival', {
  arriveSlot: 'Afternoon, 2pm to 5pm', arriveNote: 'flight lands at noon',
  dining: true, pax: 2, diets: ['Gluten free'], noDiets: false,
  dnote: 'coeliac', purpose: 'Anniversary', approach: 'Quiet',
  wellness: true, wellDay: 'Thursday', wellTime: 'Morning',
  occasion: 'tenth anniversary', note: 'a quiet table if there is one',
  at: NOW
});
canPatch('and stamps that the link was opened', GUEST, '/bookings/b-1/prearrival',
         { openedAt: NOW });

/* index.html markOpened(). The menu link is a different link from the
   pre-arrival form, and its mark is filed by night rather than on the guest,
   so opening Monday's link says nothing about Thursday. */
can('the guest menu link marks itself opened', GUEST, `/opened/${TODAY}/5`,
    { at: NOW, bookingId: 'b-1' });
can('and staff may clear the night', ADMIN, `/opened/${TODAY}/5`, null);
cannot('a mark without a booking is refused', GUEST, `/opened/${TODAY}/6`,
       { at: NOW });
cannot('and so is a mark carrying anything else', GUEST, `/opened/${TODAY}/6`,
       { at: NOW, bookingId: 'b-1', status: 'in' });
cannot('a villa that is not a number is refused', GUEST, `/opened/${TODAY}/abc`,
       { at: NOW, bookingId: 'b-1' });
cannot('and a date that is not a date', GUEST, '/opened/tonight/5',
       { at: NOW, bookingId: 'b-1' });
canPatch('Front Desk confirms the same record', DESK, '/bookings/b-1/prearrival', {
  dining: true, pax: 2, diets: [], noDiets: true, dnote: '',
  arriveSlot: '', arriveNote: '', purpose: '', approach: '',
  occasion: '', wellness: false, wellDay: '', wellTime: '', note: '',
  confirmedAt: NOW, checkedInAt: NOW
});

/* The approved arrival hour: reception's to give, never the guest's. Write
   on prearrival cascades from the node, so the gate lives in the validate
   rule, the setJob pattern. A validate rule does not run on a delete, so a
   guest CLEARING it is accepted risk, logged in PARKED.md as the logs
   upgrade. */
canPatch('reception approves an arrival hour', DESK,
         '/bookings/b-1/prearrival', { arriveApproved: 11 });
canPatch('a manager can too, at the top of the range', ADMIN,
         '/bookings/b-1/prearrival', { arriveApproved: 23 });
canPatch('the approved hour and the guest slot coexist in one save', DESK,
         '/bookings/b-1/prearrival', { arriveSlot: '16', arriveApproved: 15 });
canPatch('and reception can clear it', DESK,
         '/bookings/b-1/prearrival', { arriveApproved: null });
cannotPatch('the guest cannot set one, even a sensible one', GUEST,
            '/bookings/b-1/prearrival', { arriveApproved: 15 });
cannotPatch('nor smuggle one in with an honest save', GUEST,
            '/bookings/b-1/prearrival',
            { dining: true, arriveApproved: 11, at: NOW });
cannotPatch('housekeeping does not approve arrivals', HK,
            '/bookings/b-1/prearrival', { arriveApproved: 15 });
cannotPatch('below the range is refused', DESK,
            '/bookings/b-1/prearrival', { arriveApproved: 10 });
cannotPatch('above the range is refused', DESK,
            '/bookings/b-1/prearrival', { arriveApproved: 24 });
cannotPatch('an hour written as text is refused', DESK,
            '/bookings/b-1/prearrival', { arriveApproved: '15' });

/* The arriving-soon marker. The Worker writes it before it sends, so a villa
   is announced once however many cron wakes cross its red hour. */
can('the sync writes the arriving-soon marker', SYNC,
    '/alerts/2026-09-10/5', { at: NOW });
can('a manager can clear one', ADMIN, '/alerts/2026-09-10/5', null);
cannot('a guest cannot write one', GUEST, '/alerts/2026-09-10/5', { at: NOW });
ck('nor read the list of them',
   as(GUEST).read('/alerts/2026-09-10').allowed === false);
cannot('a marker with extra fields is refused', SYNC,
       '/alerts/2026-09-10/5', { at: NOW, actor: 'x' });
cannot('and a marker on a villa that is not a number', SYNC,
       '/alerts/2026-09-10/spa', { at: NOW });

/* worker/mews-sync.js */
canPatch('the Mews sync writes a reservation', SYNC, '/bookings/b-2/pms', {
  first: 'Mark', last: 'Whitfield', phone: '+61400000002',
  arrive: '2026-09-10', depart: '2026-09-13', villa: '3',
  state: 'confirmed', mewsState: 'Started', bookingNumber: '10421',
  groupId: 'g-1', adults: 2, children: 1,
  notes: null, notesType: null, spaceState: null, guestNotes: null,
  updated: NOW, syncedAt: NOW
});
can('and one villa night per night of the stay', SYNC, '/stays/2026-09-10/3', {
  id: 'b-2', first: 'Mark', last: 'Whitfield', phone: '+61400000002',
  arrive: '2026-09-10', depart: '2026-09-13', adults: 2,
  groupId: 'g-1', number: '10421', updated: NOW
});
can('a cancelled booking is cleared by deleting the night', SYNC, '/stays/2026-09-10/3', null);

/* cleaners.html patchRoom() */
can('housekeeping marks a villa cleaned', HK, `/hk/${TODAY}/4`, { done: NOW });
can('and marks breakfast delivered', HK, `/hk/${TODAY}/4`, { bfast: NOW });
can('a manager sets the job for a villa by hand', DESK, `/hk/${TODAY}/4/kind`, 'pre');
canPatch('and can do it for several villas at once, the way the board does',
         DESK, `/hk/${TODAY}/4`, { kind: 'pre' });
/* Write permission in Firebase cascades downwards and cannot be taken back at
   a child, so the old rule putting the restriction on kind's .write never did
   anything: permission was already granted at the villa above it. ROLES.md has
   said housekeeping may not set a villa's job since the day it was written.
   The restriction lives in the validate rule instead, which does not cascade. */
cannot('housekeeping cannot set the job themselves', HK, `/hk/${TODAY}/4/kind`, 'pre');
cannotPatch('nor by patching the villa around it', HK, `/hk/${TODAY}/4`,
            { kind: 'pre' });
cannotPatch('nor tucked in beside a mark they are allowed to make', HK,
            `/hk/${TODAY}/4`, { done: NOW, kind: 'vac' });
/* Confirmed 18 Aug: setting the job is the manager's, nobody else's. */
cannot('a waiter cannot set the job either', WAITER, `/hk/${TODAY}/4/kind`, 'clean');
cannot('nor the chef', CHEF, `/hk/${TODAY}/4/kind`, 'clean');
canPatch('housekeeping can still mark a villa clean', HK, `/hk/${TODAY}/4`, { done: NOW });
canPatch('and clear a mark they made by mistake', HK, `/hk/${TODAY}/4`, { done: null });
can('and Clean Slate can still delete the whole villa record', ADMIN,
    `/hk/${TODAY}/4`, null);

/* tag.html */
can('the chef saves the dietary list', CHEF, '/dietaries', {
  'Gluten free': { name: 'Gluten free', active: true, group: 'common' },
  'Extra chilli': { name: 'Extra chilli', active: false, group: 'menu' }
});
can("and tonight's tags", CHEF, `/menutags/${TODAY}`,
    { main: ['Nut allergy'], entree: ['Gluten free', 'Dairy free'] });

/* tally.html menu history */
can('the menu is archived for statistics', CHEF, `/menuhistory/${TODAY}`, {
  bread: 'Sourdough', entree: 'Kingfish crudo', main: 'Lamb rump',
  dessert: 'Pavlova', mainDesc: 'pomegranate, mint', published: NOW, at: NOW
});

/* staff.html */
can('an admin adds a staff member', ADMIN, '/staff/new@nalaresort,com,au',
    { name: 'New Person', role: 'waiter' });
can('and saves the notification settings', ADMIN, '/notify', {
  on: true, hours: { from: '07:30', to: '18:00' },
  events: {
    departed:  { housekeeping: true, admin: true, waiter: false, chef: false },
    available: { housekeeping: true, admin: true, waiter: false, chef: false },
    cleaned:   { housekeeping: true, admin: true, waiter: true,  chef: false },
    serviced:  { housekeeping: true, admin: true, waiter: true,  chef: false }
  }
});

/* nala-shared.js pushOn() */
can('a phone registers for notifications', DESK, '/pushsubs/reception@nalaresort,com,au', {
  endpoint: 'https://fcm.googleapis.com/fcm/send/abc123', role: 'staff', at: NOW,
  keys: { p256dh: 'BEl62iUYgUivxIkv69yViEuiBIa40HI', auth: 'k8JV6sjdEQ' }
});
cannot('but not for somebody else', DESK, '/pushsubs/chef@nalaresort,com,au',
       { endpoint: 'https://fcm.googleapis.com/fcm/send/abc123' });

/* debug.html write test */
can('the diagnostics write test still writes', ADMIN, `/roomguests/${TODAY}/99`,
    { name: 'Write Test', phone: '0400000000', departs: '2026-12-31', at: NOW });

console.log('--- and the shapes that should never reach the database ---');

cannot('a dinner status nobody uses', DESK, `/dinner/${TODAY}/11`,
       { status: 'maybe', pax: 2, room: '11' });
cannot('a cell with no status at all', DESK, `/dinner/${TODAY}/11`,
       { pax: 2, room: '11', by: 'staff' });
cannot('a pax count that is text', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: '2', room: '11' });
cannot('a negative pax', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: -3, room: '11' });
cannot('a party of four hundred', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: 400, room: '11' });
cannot('a villa number that is a word', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: 2, room: 'pool bar' });
cannot('a date key that is not a date', DESK, '/dinner/tonight/11',
       { status: 'in', pax: 2, room: '11' });
cannot('an essay in the note field', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: 2, room: '11', note: 'x'.repeat(2000) });
cannot('a dietary that is an object', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: 2, room: '11', diets: [{ name: 'Vegan' }] });
cannot('an answer attributed to nobody in particular', DESK, `/dinner/${TODAY}/11`,
       { status: 'in', pax: 2, room: '11', by: 'the internet' });

cannot('a guest inventing a field on the pre-arrival form', GUEST,
       '/bookings/b-1/prearrival', { dining: true, isVip: true });
cannot('a guest sending a novel through it', GUEST,
       '/bookings/b-1/prearrival', { note: 'x'.repeat(4000) });
cannot('a guest claiming forty two people', GUEST,
       '/bookings/b-1/prearrival', { dining: true, pax: 42 });
cannot('a guest writing the PMS record', GUEST, '/bookings/b-1/pms', { villa: '1' });

cannot('a staff role that does not exist', ADMIN, '/staff/x@y,com',
       { name: 'X', role: 'owner' });
cannot('a staff record with no role', ADMIN, '/staff/x@y,com', { name: 'X' });
cannot('a housekeeping job that is not one of the four', DESK, `/hk/${TODAY}/4/kind`, 'later');
cannot('quiet hours that are not a time', ADMIN, '/notify/hours/from', 'morning');
cannot('a dietary record with no name', CHEF, '/dietaries/x', { active: true });
cannot('a dietary group that is neither', CHEF, '/dietaries/x',
       { name: 'X', group: 'sometimes' });
cannot('a tag on a course that is not on the menu', CHEF, `/menutags/${TODAY}`,
       { canapes: ['Nut allergy'] });
cannot('a stay night with no booking id', SYNC, '/stays/2026-09-10/3',
       { first: 'Mark', last: 'Whitfield' });
cannot('a stay in a villa that is not a number', SYNC, '/stays/2026-09-10/poolhouse',
       { id: 'b-2' });
cannot('a menu history entry that is not a date', CHEF, '/menuhistory/lastnight',
       { main: 'Lamb rump' });

/* The same cascade, checked everywhere else it could bite. A rule that only
   works because nothing above it grants write is a rule that stops working the
   day somebody widens the parent. */
cannotPatch('a guest cannot reach the PMS record through the booking', GUEST,
            '/bookings/b-1', { pms: { villa: '9' } });
cannot('nor write the whole booking in one go', GUEST, '/bookings/b-1',
       { prearrival: { dining: true }, pms: { villa: '9' } });
cannotPatch('the chef cannot promote themselves through the staff node', CHEF,
            '/staff', { 'chef@nalaresort,com,au': { name: 'Chef', role: 'admin' } });
cannot('a guest cannot write the dietary list the menu page reads', GUEST,
       '/dietaries/x', { name: 'X', active: true, group: 'common' });
cannot('a guest cannot tag tonight\'s menu', GUEST, `/menutags/${TODAY}`,
       { main: ['Nut allergy'] });

console.log('--- and the permissions that were already there ---');

cannot('a signed out browser cannot read the whole guest list', GUEST, '/bookings', null);
ck('a signed out browser can read one booking it has the id for',
   db.read('/bookings/b-1').allowed === true);
ck('and tonight\'s menu tags, which the guest page needs',
   db.read(`/menutags/${TODAY}`).allowed === true);
ck('but not the staff list', db.read('/staff').allowed === false);
cannot('the chef cannot edit the staff list', CHEF, '/staff/x@y,com',
       { name: 'X', role: 'admin' });
cannot('housekeeping cannot write a reservation', HK, '/stays/2026-09-10/3',
       { id: 'b-2' });

console.log('--- the permission matrix ---');

/* The matrix is the manager changing the shipped defaults from Settings. Most
   of what it changes is a button appearing or not appearing, which the rules
   cannot see. Setting the job a villa needs is the exception: it is a write,
   so it can be enforced here as well, and it is the one worth enforcing
   because it decides what housekeeping is sent to do. */
function withPerms(perms) {
  return targaryen.database(RULES, Object.assign({}, SEED, { permissions: perms }));
}
const KIND = `/hk/${TODAY}/4/kind`;

ck('with no matrix at all, only the manager sets the job',
   as(HK).write(KIND, 'clean').allowed === false &&
   as(ADMIN).write(KIND, 'clean').allowed === true);

const ticked = withPerms({ setJob: { housekeeping: true, waiter: false } });
ck('ticking the box in Settings lets housekeeping set it',
   ticked.as(HK).write(KIND, 'clean').allowed === true);
ck('and leaves the role in the next column alone',
   ticked.as(WAITER).write(KIND, 'clean').allowed === false);

const untickedM = withPerms({ setJob: { housekeeping: false } });
ck('unticking it takes the job back off them',
   untickedM.as(HK).write(KIND, 'clean').allowed === false);
ck('and the manager is unaffected either way',
   untickedM.as(ADMIN).write(KIND, 'clean').allowed === true);

can('the manager ticks a box', ADMIN, '/permissions/setJob/housekeeping', true);
cannot('housekeeping cannot tick their own box', HK,
       '/permissions/setJob/housekeeping', true);
cannot('the chef cannot tick anybody\'s', CHEF,
       '/permissions/publishMenu/waiter', true);
cannot('and a box has to be a yes or a no', ADMIN,
       '/permissions/setJob/housekeeping', 'sometimes');

/* Two invariants that live in the rules rather than in the page, because the
   page is not the only way to write here. Handing out manageStaff hands out
   the ability to hand things out, which is a second manager rather than a
   permission. And a false against admin would lock the only person who can
   undo it out of the page where it is undone. */
cannot('manageStaff cannot be handed out at all', ADMIN,
       '/permissions/manageStaff/waiter', true);
cannot('the manager cannot be switched off, even by hand', ADMIN,
       '/permissions/setJob/admin', false);
cannot('nor can a capability that does not exist be invented', ADMIN,
       '/permissions/deleteEverything/waiter', true);
ck('anyone signed in may read it, because every gate in the app needs it',
   as(HK).read('/permissions').allowed === true);
cannot('a signed out browser cannot read it', GUEST, '/permissions', null);

console.log('--- the customer id ---');

canPatch('the sync writes the customer id onto the booking', SYNC,
         '/bookings/b-1/pms', { customerId: '7c1e4a90-3b55-4a11-9d02-b4a900c12abc' });
cannotPatch('but not something the length of a paragraph', SYNC,
            '/bookings/b-1/pms',
            { customerId: 'x'.repeat(65) });


/* ── internal notes ──────────────────────────────────────────────────
 * The one note a guest must never see, which is exactly why it cannot live
 * under /bookings: that node has read set to true, because the pre-arrival
 * form reads it without signing in. A note about a guest stored there would
 * be one URL away from the guest it is about.
 *
 * The last assertion is the contrast, and it is the reason this node exists.
 */
(function internalNotes(){
  var data = { staff:{ 'bd@x':{name:'B',role:'admin'}, 'wt@x':{name:'W',role:'waiter'},
                       'st@x':{name:'S',role:'staff'}, 'sy@x':{name:'Y',role:'sync'} },
               internal:{ b4:{ fromMews:'noise' } } };
  var as = function(e){
    return targaryen.database(RULES, data).as(e ? {uid:e, token:{email:e}} : null);
  };
  ck('a manager may read an internal note', as('bd@x').read('/internal/b4').allowed);
  ck('and a staff login may too',           as('st@x').read('/internal/b4').allowed);
  ck('a waiter may not',                   !as('wt@x').read('/internal/b4').allowed);
  ck('nor may anybody signed out',         !as(null).read('/internal/b4').allowed);
  ck('a manager may write one',
     as('bd@x').update('/internal/b4', {note:'x', editedAt:'2026-08-19T00:00:00Z'}).allowed);
  ck('a waiter may not',                   !as('wt@x').update('/internal/b4', {note:'x'}).allowed);
  ck('the sync may seed one from Mews',     as('sy@x').update('/internal/b4', {fromMews:'y'}).allowed);
  ck('a field nobody named is refused',    !as('bd@x').update('/internal/b4', {sneaky:'x'}).allowed);
  ck('and so is something the length of a book',
     !as('bd@x').update('/internal/b4', {note:new Array(3000).join('x')}).allowed);
  ck('while a booking stays readable by anyone holding the link, which is why this node exists',
     as(null).read('/bookings/b4/prearrival').allowed);
})();


/* ── a dietary that outlives the booking ─────────────────────────────
 * Kept against the Mews customer, which is the only identifier that survives
 * a booking ending. Reachable by a guest holding their own link, like the
 * booking is, so they can read back and correct what we hold about them.
 */
(function guestDietaries(){
  var data = { staff:{ 'st@x':{name:'S',role:'staff'} }, guests:{} };
  var as = function(e){
    return targaryen.database(RULES, data).as(e ? {uid:e, token:{email:e}} : null);
  };
  var CID = 'cust-6cb6d13f-beda-45eb-9c1b';
  ck('a guest holding their link may record a dietary against themselves',
     as(null).update('/guests/' + CID,
       {diets:['Nut allergy'], dnote:'severe', updatedAt:'2026-08-19T00:00:00Z'}).allowed);
  ck('and read back what we hold about them', as(null).read('/guests/' + CID).allowed);
  ck('staff may write one too',  as('st@x').update('/guests/' + CID, {diets:[]}).allowed);
  ck('a field nobody named is refused',
     !as('st@x').update('/guests/' + CID, {secret:'x'}).allowed);
  ck('a note the length of a paragraph is refused',
     !as('st@x').update('/guests/' + CID, {dnote:new Array(600).join('x')}).allowed);
  ck('and an entry longer than any dietary name is too',
     !as('st@x').update('/guests/' + CID, {diets:[new Array(100).join('x')]}).allowed);
})();


/* ── publishing the menu ─────────────────────────────────────────────
 * The menu moved into the database on 21 Aug so that publishing needs a staff
 * login rather than a GitHub token. A token cannot be narrowed to one file:
 * the smallest scope that can write menu.json is Contents write, which is
 * every file in the repository. A role can be narrowed, and these are the
 * assertions that make that true rather than merely intended.
 */
(function menuPublishing(){
  var data = { staff:{ 'ch@x':{name:'C',role:'chef'}, 'ad@x':{name:'A',role:'admin'},
                       'wt@x':{name:'W',role:'waiter'} },
               permissions:{}, menu:{} };
  var as = function(e){
    return targaryen.database(RULES, data).as(e ? {uid:e, token:{email:e}} : null);
  };
  var M = { published:'2026-08-21T07:54:48+10:00',
            bread:{name:'Focaccia',desc:'paprika butter',aus:false},
            entree:{name:'Poblano',desc:'braised beef',aus:false},
            main:{name:'Kingfish',desc:'corn, saffron',aus:true},
            dessert:{name:'Tres leches',desc:'coconut',aus:false} };
  ck('a chef may publish the menu',  as('ch@x').write('/menu', M).allowed);
  ck('and so may an admin',          as('ad@x').write('/menu', M).allowed);
  ck('a waiter may not',            !as('wt@x').write('/menu', M).allowed);
  ck('nor may anybody signed out',  !as(null).write('/menu', M).allowed);
  /* Guests read the menu without signing in. That is the whole point of it. */
  ck('a guest signed out can read it', as(null).read('/menu').allowed);
  ck('a course nobody named is refused',
     !as('ch@x').write('/menu', Object.assign({}, M, {supper:{name:'x'}})).allowed);
  ck('the seafood flag must be a flag, not a word',
     !as('ch@x').write('/menu',
        Object.assign({}, M, {main:{name:'K',desc:'c',aus:'yes'}})).allowed);
})();

console.log('RESULT: %d passed, %d failed', P, F);
process.exit(F ? 1 : 0);
