# Roles and access - design

Agreed 15 Aug. Not built yet. This replaces the current mechanism, which is a
single check in `cleaners.html`: does the signed-in email begin with
"housekeeping". That cannot express four roles, and it fails badly on
per-person accounts - `housekeeping.maria@` would be a cleaner but `maria@`
would silently be management.

## The four roles

`staff`, `chef`, `waiter`, `housekeeping`.

Note "staff" is the FULL ACCESS role, not a middling one. The existing admin
account is `staff@nalaresort.com.au`, so it maps to this role by name, which
is convenient but coincidental - the role comes from the record, never from
the address.

| | Cleans board | Set a villa's job | Reservations board | Edit bookings | Reservations Sheet | Publish menu | Manage staff |
|---|---|---|---|---|---|---|---|
| **staff** | yes | yes | yes | yes | yes | yes | yes |
| **chef** | no | no | read only | no | read and print | yes | no |
| **waiter** | no | no | yes | yes | yes | no | no |
| **housekeeping** | marks only | no | no | no | no | no | no |

"Marks only" means `done`, `bfast`, `departed`, `pushed` - the cleaner's own
work. Not `kind`.

**No record means no access.** Someone who signs in without a staff record
gets no boards and a message to see the manager. Deliberately not the lowest
role: a typo in an email would otherwise silently grant access.

The chef DOES open the app - to see who is eating and their dietaries, and to
print the sheet. So the chef role is real, not notional. They publish the menu
through the chef brief using the GitHub token, not through the app.

## Where the record lives

`/staff/<emailkey>` where `emailkey` is the email lowercased with `.` replaced
by `,` (Firebase keys cannot contain a dot):

```json
"staff": {
  "staff@nalaresort,com,au":        { "name": "Ben",          "role": "staff" },
  "housekeeping@nalaresort,com,au": { "name": "Housekeeping", "role": "housekeeping" }
}
```

Keyed by email rather than by uid so a record can be created BEFORE the person
first signs in, and so the list is readable by a human.

Seed those two records as part of stage one, or `staff@` loses access the
moment the new check goes live.

## How it is read

A helper in `nala-shared.js`, NOT in `auth.js`. That file is under a standing
"do not touch" instruction, has been reverted twice, and cannot be tested here
against real Firebase. `nala-shared.js` has a suite and is safe to change.

```
roleOf(user) -> 'staff' | 'chef' | 'waiter' | 'housekeeping' | null
can(role, 'setJob' | 'editBookings' | 'manageStaff' | ...) -> bool
```

Pages ask `can()`, never the email. One place to change a permission.

## Rules

The database must enforce it too - hiding a control is not preventing a write.
Current rules already do this for `hk/<date>/<villa>/kind` via an email prefix
check; that becomes a role lookup:

```
"kind": {
  ".write": "auth != null && root.child('staff')
              .child(auth.token.email.replace('.',','))
              .child('role').val() == 'staff'"
}
```

`/staff` itself: readable by any signed-in user (the pages need it), writable
only by a `staff` role.

**Warning learned the hard way:** never write a replacement ruleset from
memory. `extcancel` exists only in the rules and nowhere in the code, and
dropping it would silently break guest cancellations. Start from
`rules.json`, which is a copy of what is live.

## Build order

**Stage one - roles enforced.**
1. Seed `/staff` with the two existing accounts
2. `roleOf()` and `can()` in nala-shared.js, with tests
3. Replace the email check in cleaners.html
4. Gate tally.html and list.html per the matrix
5. New rules for Ben to paste
6. Verify by signing in as each role

**Stage two - the staff screen.**
A page where a `staff` role sees everyone, changes a role, and removes
someone. Mock it before building.

## What this does NOT do

**Creating and deleting logins stays in the Firebase console.** Doing it from
a web page needs server-side admin credentials, which is a large piece of work
and more access than is warranted here. The console creates the login, the app
decides what it may do. Removing someone in the console kills their access
immediately, whatever their role record says.

**Passwords cannot be listed.** Firebase stores them hashed; nobody, including
the owner, can read one back. The staff screen lists PEOPLE and their roles,
not passwords. Resetting a password is a console action or a reset email.
