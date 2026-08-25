# Roles and access - design

Agreed 15 Aug, built 17 Aug, table corrected 18 Aug against the code. It
replaced a single check in `cleaners.html`: does the signed-in email begin with
"housekeeping". That could not express four roles, and it failed badly on
per-person accounts - `housekeeping.maria@` would be a cleaner but `maria@`
would silently be management.

**The table below is the one in `ROLE_GRANTS` in `nala-shared.js`. If they ever
disagree, the code is what runs and this file is wrong.** They did disagree
until 18 Aug: this said a waiter had no access to the Cleans board, and the
code has given them one since the day it was written.

## The six roles

`staff`, `chef`, `waiter`, `housekeeping` - four when this was agreed - and
two added 25 Aug, in separate sessions that met at the merge: `manager` and
`spa`.

Note "staff" is the FULL ACCESS role, not a middling one. The existing admin
account is `staff@nalaresort.com.au`, so it maps to this role by name, which
is convenient but coincidental - the role comes from the record, never from
the address.

`manager` is the admin's grants minus `manageStaff`, and nothing else. That
one exclusion is what keeps the three manageStaff gates - Settings General,
Pages and Diagnostics - the admin's alone. It is a role rather than a row on
the permissions grid because handing out `manageStaff` is a second admin
(see below), and this is the role for somebody who is nearly one. For the
same reason it is not a grid column: the role IS its definition, and the
rules refuse the matrix an opinion about it.

`spa` is the masseuse, an outside contractor, added 25 Aug. Like the chef, a
real login for a real person with one job on one screen - but where the
chef's login can read the whole database like any staff login, the spa
login's READS are narrowed in the rules as well: it can reach `/spa`,
`/stays`, a booking by its id (which is public by design, the guest links
depend on it), `/staff` and `/permissions` for its own gate, and the public
menu nodes. The dining and housekeeping boards, internal notes, phone
corrections, SMS records, push endpoints and the settings catch-all all
refuse it by role. It is deliberately absent from the permissions grid in
Settings: widening an outside contractor's access is a rules decision, made
in a commit, not a tick in a grid.

| | Cleans board | Set a villa's job | Reservations board | Edit bookings | Reservations Sheet | Publish menu | Manage staff | Spa board |
|---|---|---|---|---|---|---|---|---|
| **admin** | yes | yes | yes | yes | yes | yes | yes | yes |
| **manager** | yes | yes | yes | yes | yes | yes | no | yes |
| **chef** | no | no | read only | no | read and print | yes | no | no |
| **waiter** | availability and departures | no | yes | yes | yes | no | no | yes |
| **housekeeping** | marks only | no | no | no | no | no | no | no |
| **spa** | no | no | no | no | no | no | no | yes |

"Marks only" means `done`, `bfast`, `departed`, `pushed` - the cleaner's own
work. Not `kind`.

A waiter is on the Cleans board for one reason: clearing breakfast puts them
in the villa before anybody else knows the guest has gone. So they get
`cleansBoard` but not `cleansMarks`, which in practice means they may say a
villa looks available and may mark or unmark a departure, and the buttons for
finishing work or pushing a villa to tomorrow are hidden rather than disabled.

### Pages with no permission of their own

Three pages are gated on a permission borrowed from elsewhere, because
inventing one for each would be four names for four pages:

| Page | Needs | Why |
|---|---|---|
| Diagnostics | `manageStaff` | It deletes live data. Admin only - the manager role deliberately lacks it. |
| Menu Dietaries | `publishMenu` | The chef's page, and the manager's. |
| Statistics | `resBoard` | Reading, no writes, same audience as the board. |
| Site map | `manageStaff` | A map of the whole app is an admin tool. |

Until 18 Aug the first two had no gate at all, which meant any login that
could sign in could open Diagnostics and run Clean Slate. The rules cannot
catch that: the deletes it makes are the same writes those roles legitimately
make elsewhere, so the page has to be the gate.

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

## Changing it without changing the code

`ROLE_GRANTS` is what the app ships with. `/permissions` is the manager
changing their mind, and it is edited from the grid in Settings.

```
/permissions/<action>/<role> = true | false
```

Only the boxes moved away from the shipped default are stored. A missing
action, a missing role, or a value that is not a boolean all mean no opinion,
and the default stands. That is on purpose: writing every cell would freeze
today's defaults into the database, and the next capability added to the app
would arrive switched off for everybody with nothing to say why.

Two things the grid will not do, both enforced in the rules as well as in the
page, because the page is not the only way to write there:

- **`manageStaff` cannot be handed out.** Handing out the ability to hand
  things out is a second manager, not a permission. Do it by changing
  somebody's role in the People list, where it is visible.
- **`admin` is not a column.** `can()` answers for admin before it consults
  the matrix, so a stray `false` typed into the Firebase console cannot lock
  the only person who can undo it out of the page where it is undone.

`loadStaff()` fetches the matrix along with the records, so no page had to
change. A failed matrix read is not reported to the pages: the records decide
whether somebody is staff at all, the matrix only adjusts what a known role
may do, and the defaults are a working app. Refusing everyone because an
override list did not answer would turn a small outage into a locked door.

**What the grid actually enforces.** Only `setJob` is enforced by the database
as well, because it is the only one of the seven that is a write the rules can
see. The other six hide a button. That is enough for an honest mistake and it
is not a lock, and the note under the grid says so rather than implying more
than it does.

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

**Creating a login no longer needs the console.** This section said it did,
from before the staff screen was built, and the correction is this file's own
rule working: the code moved and the document had not. Add someone on
Settings with a name, a role and a six digit passcode, and the page creates
the Firebase login itself - the passcode becomes `<code>@staff.nala`, made on
a second Firebase app so the manager is not signed out mid task - then writes
the staff record. The person signs in on the passcode pad with those six
digits. This is the only way staff are added in practice, the masseuse
included.

**Deleting is still two places.** Removing someone on Settings deletes their
record, which ends their access at every gate, but the Firebase Auth login
survives and holds the passcode hostage - the console deletion frees it.
That leftover is item 1 in `SECURITY.md`'s standing jobs. Removing someone in
the console alone also works, immediately, whatever their record says.

**Passwords cannot be listed.** Firebase stores them hashed; nobody, including
the owner, can read one back. The staff screen lists PEOPLE and their roles,
not passwords. Resetting a password is a console action or a reset email.
