/* Can a matrix in the database actually enforce a permission, the way the
   notifications matrix decides who gets told? The rules already read the
   database to find a role, so the question is only whether they can read one
   more node. Tested rather than argued. */
const t = require('targaryen');

const RULES = { rules: {
  permissions: {
    ".read": "auth != null",
    ".write": "auth != null && root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin'",
    "$action": { "$role": { ".validate": "newData.isBoolean()" } }
  },
  hk: { "$date": { "$villa": {
    ".read": "auth != null",
    ".write": "auth != null",
    "kind": { ".validate":
      "auth != null && (root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val() == 'admin' || root.child('permissions').child('setJob').child(root.child('staff').child(auth.token.email.toLowerCase().replace('.',',')).child('role').val()).val() == true)" }
  } } }
}};

function db(matrix) {
  return t.database(RULES, {
    staff: {
      'staff@n,com':        { name: 'Admin', role: 'admin' },
      'housekeeping@n,com': { name: 'HK', role: 'housekeeping' },
      'waiter@n,com':       { name: 'W', role: 'waiter' }
    },
    permissions: matrix
  });
}
const who = e => ({ uid: e, token: { email: e } });
const HK = who('housekeeping@n.com'), ADMIN = who('staff@n.com'), W = who('waiter@n.com');
const K = '/hk/2026-08-18/4/kind';

let P = 0, F = 0;
const ck = (n, c) => { console.log((c ? 'PASS ' : 'FAIL ') + n); c ? P++ : F++; };

const off = db({ setJob: { housekeeping: false, waiter: false } });
ck('with the box unticked, housekeeping cannot set the job',
   off.as(HK).write(K, 'clean').allowed === false);
ck('the manager always can, matrix or no matrix',
   off.as(ADMIN).write(K, 'clean').allowed === true);

const on = db({ setJob: { housekeeping: true, waiter: false } });
ck('ticking the box in Settings actually lets them',
   on.as(HK).write(K, 'clean').allowed === true);
ck('and leaves the role beside it alone',
   on.as(W).write(K, 'clean').allowed === false);

const missing = db(null);
ck('with no matrix at all it falls back to manager only',
   missing.as(HK).write(K, 'clean').allowed === false &&
   missing.as(ADMIN).write(K, 'clean').allowed === true);

ck('housekeeping cannot tick their own box',
   off.as(HK).write('/permissions/setJob/housekeeping', true).allowed === false);
ck('the manager can', off.as(ADMIN).write('/permissions/setJob/housekeeping', true).allowed === true);
ck('and the box has to be a yes or a no',
   off.as(ADMIN).write('/permissions/setJob/housekeeping', 'sometimes').allowed === false);

console.log('RESULT: %d passed, %d failed', P, F);
