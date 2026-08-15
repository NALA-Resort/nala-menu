# NALA menu app - handover

Written 14 Aug 2026, updated 15 Aug. Covers everything since the previous
handover (12 Aug),
and carries forward that handover's open items so this file stands alone.

Companion documents:
- **firebase-rules.json** - a copy of the live database rules. The console is
  the source of truth; this is here so a change can be written and reviewed
  before it is pasted, and so the next session can see them without asking.
- **STYLEGUIDE.md** - what things must look like and how to work. Read the
  first section before touching anything visual.
- **AUDIT.md** - what was found and changed during the four-part cleanup.
- **tests/README.md** - how to run the suites.

---

## What this is

A dinner-service tool for a 17-villa resort. Three tiers:

| Tier | Pages | Job |
|------|-------|-----|
| **app** | tally.html (Reservations), cleaners.html (Cleans) | Fast operational reading on a phone, one hand, interrupted |
| **print** | list.html (Reservations Sheet), housekeeping.html (Clean Sheet) | Paper clarity, minimum ink |
| **guest** | index.html (menu + RSVP), welcome.html | Brand |

Shared: `nala-ui.css` (all controls), `nala-shared.js` (dates, villa records,
clean/service rules), `auth.js`.

Live at `menu.nalaresort.com`. Data in Firebase RTDB.

---

## How to work here

**Push.** Edit `FILES` and `MSG` in `/home/claude/push.py`, then run it. It
writes a single commit. GitHub occasionally 503s; just retry.

**Test.** Five Playwright suites, all must stay green:

```
python3 tests/tally_suite.py    # 71 - Reservations
python3 tests/list_suite.py     # 29 - Reservations Sheet
python3 tests/hk_suite.py       # 22 - Clean Sheet
python3 tests/cl_suite.py       # 68 - Cleans
python3 tests/auth_suite.py     #  6 - sign-in
```

**Demos.** `python3 tools/make-demo.py` rebuilds four self-contained offline
copies (`demo-tally.html` and friends) with fixed busy-night data. They inline
everything and stub the network, so they are the safe place to look at a
change. Rebuild them in the same commit as any page change.

**Firebase rules.** I cannot change them; there is no service account and I
would not suggest one for a file edited a few times a year. Write the new
rules into `firebase-rules.json`, show the user, they paste into the console.
Keep the file in step with what is live.

**Cache.** Changing a shared file means bumping its `?v=` on every page that
references it, in the same commit. Current: `nala-ui.css?v=9`,
`nala-shared.js?v=6`, `auth.js?v=7`.

---

## Conventions (carried forward, still binding)

- **Mock up before you build.** Every visual change is rendered and shown
  before it is published. This is the first section of the styleguide and it
  was learned expensively - see Lessons below.
- **Clean up after.** A change ends with a pass over the whole block touched,
  not just the edited lines: rules fighting each other, dead rules, comments
  describing behaviour the code no longer has, containers that cost layout
  width, shorthand doing more than intended.
- **Never touch a file not named in the request.** Ask one question if
  ambiguous.
- **Never touch `auth.js`** without explicit instruction in those words.
- **`index.html` is the guest page** and is never changed casually.
- **No em dashes**, anywhere, including code comments.
- Every reply: files changed, commit title, and whether Firebase changed.

---

## Since the last handover

### Reservations (tally.html)

- **Dietaries are pills.** Allergy = solid red with the word "allergy"
  dropped, since the fill says it. Preference = tinted red, full label. Pills
  sit on their own line under the name.
- **Villas, not rooms**, in every visible label. The word "room" survives only
  in code: database paths (`roomguests/`, `room-N`), variables, ids, CSS class
  names. Renaming those would orphan every stored booking.
- **The villa number leads each booking line** at 15px bold, then a dash, then
  the name. The word "villa" is dropped - every row is one.
- **Phone is off the row**, it lives on the edit sheet where it is used.
- **The notes bubble is icon-only** in a fixed 20px slot, so a booking with a
  note occupies the same width as one without and the pax column never shifts.
- **Bug fixed:** a staff override used to hide the guest's pre-menu tag and
  "no dietaries confirmed" note. The screen took the staff record as the whole
  truth; it now merges the guest's answer underneath, as the printed sheet
  always did.
- **Menu state pill:** both published and unpublished states are now the same
  pill. The rule selected `span` only, and the published state renders as an
  `<a>`, so it had been unstyled but for its background.

### Reservations Sheet (list.html)

- **Dietaries and comments share one column** at their combined width, pills
  on the first line, comment beneath. Split across two narrow columns, a busy
  guest stacked three deep and left the row half empty.

### Cleans (cleaners.html) - most of the work

This page grew a full state machine. See the next section.

### Everywhere

- **San Francisco.** Staff tools moved off Georgia, whose old-style figures
  made the stats look randomly sized (6 and 8 rise, 5, 7 and 9 drop). Set once
  as `--ui-font`; no page hardcodes a font stack any more. **Guest pages
  deliberately do not use these tokens** - they carry the brand and set their
  own font, so the staff font can change without touching them.
- **Em dashes removed** from every page, shared file and document.

### Guest pages

- Pricing lifted off the bottom edge of the screen (`index.html`).
- Welcome page greeting is generic - no guest name is displayed, even when the
  link carries one.
- A **temporary merge-tag test panel** is live on `welcome.html`, shown only
  when the link carries `&t=1`. **Remove it when GuestTouch is settled.**

---

## The Cleans state machine

Each villa has a **job** for the day, stored at `/hk/<date>/<villa>/kind` when
set by hand, otherwise derived from the booking dates by `hkClassify()` in
`nala-shared.js`. A hand-set job beats the dates.

| Job | Means | Set from |
|-----|-------|----------|
| **Service** | Guest staying on | Dates, or by hand |
| **Clean** | Guest departing today | Dates, or by hand |
| **Pre-arrival** | Nobody checking out, someone checking in; needs a look | Unknown or empty villas only, never a service |
| **Unknown** | The dates cannot place it | Default when there is no data |
| **Empty** | Not a job at all | By hand |

Marks, all under `/hk/<date>/<villa>`, all expiring with the day:

| Mark | Means |
|------|-------|
| `bfast` | **Possibly available** - someone noticed the villa is free. Services only. Ages amber at 15 min, red at 20 |
| `departed` | The guest has gone |
| `done` | The job is finished |
| `pushed` | A clean deferred to tomorrow |

**Colour means "ready to work on now"**, and which colour says which job:
white = not ready, blue = ready to clean (departed), green = ready to service
(marked available), light grey + green tick = finished, very pale = empty.
**Orange is deliberately unused, held for a warning state.**

**Order, top left is highest priority:**

1. Services, the one noticed free longest ago first
2. Cleans: departed with an arrival today, then departed, then the rest
3. Pre-arrivals
4. Finished work
5. Pushed today
6. Unknown
7. Empty

**Only offer what a villa can take.** A departed villa can only be cleaned: no
availability mark, no service, no empty. A pre-arrival has one job and one
outcome, so its sheet is only Mark as pre-arrived (or Undo done), Back to
unknown, Close. An unknown villa offers all three jobs but nothing to
complete.

**Push.** A clean with no arrival that day can be deferred. It reads Pushed in
purple over finished-work grey, sorts below the finished villas for the rest
of today, and returns tomorrow as a clean that is already departed, at
priority 2.

**Admin options** groups everything management-only: the three jobs and the
revert. A cleaner sees only the job, the marks and Close.

**Multi-select** in the footer applies one decision to several undecided
villas. Only unknown villas can be picked; the rest dim.

---

## Logins and rules

Two accounts in Firebase Auth:

- `staff@...` - management. Sees the nav menu and the Admin options group.
- `housekeeping@...` - cleaners. Sees the job, the marks and Close.

The page decides by whether the email begins with "housekeeping". **The
database enforces it too**: the rules allow any signed-in user to write
`done`, `bfast`, `departed` and `pushed`, but only a non-housekeeping account
may write `kind`. So a cleaner cannot set a villa's job even by sending the
request directly.

Rules live in the console (Realtime Database, Rules). Nobody here has write
access to them, so a rules change means pasting the current ones in, getting
a complete replacement back, and pasting it once. Do not write a replacement
from memory: the `extcancel` path exists only in the rules and would be
dropped, breaking guest cancellations.

Still open in the rules: anyone who knows a guest's phone number can write
that guest's booking. Fixing it properly means signed links.

## Backlog

**1. Rotate the GitHub token.** The classic PAT is exposed in the chef brief.
Revoke it, issue fine-grained per-user tokens, reissue the brief FIRST.

**2. Commit `CHEF-BRIEF.md` to the repo.** It exists at
`/mnt/user-data/outputs/CHEF-BRIEF.md` but was never committed.

**3. Remove the merge-tag test panel** from `welcome.html` once GuestTouch is
settled.

**4. Clear stale test data** in villas 3, 4 and 5.

**5. Confirm dinner and breakfast hours.** Still provisional.

**6. Mews PMS sync.** Not started.

**7. Sign-in form flash and spinner.** Touched and reverted twice. Leave alone
until it can be tested against real Firebase.

---

## Known gaps and risks

**No test suite on `index.html` or `auth.js`.** Every episode that went badly
over these three days happened on one of those two files. Everything with a
suite has been reliable. This is the single most useful thing to fix.

**The manager gate is enforced, not cosmetic.** As of 15 Aug the database
rules restrict `hk/<date>/<villa>/kind` to accounts whose email does not begin
with `housekeeping`. Cleaners keep `done`, `bfast`, `departed` and `pushed`,
which is their work. The `housekeeping@nalaresort.com.au` login exists.

Note the rules still carry a `$other` catch-all granting any signed-in user
read and write on paths not named explicitly. That is what lets new fields
work without a rules change; it is also why anything genuinely sensitive must
be named explicitly, as `kind` now is.

**Anyone who knows a phone number can write that guest's booking.**
`responses/<date>/<phone>` is writable without signing in, because guests must
be able to reply. Fixing it properly means signed links, which is a project
rather than a rules edit.

**Arrival detection is fragile.** "Arriving today" reads the villa's record in
today's `roomguests` bucket, which is written when a guest opens their link.
If the incoming guest opens theirs before the outgoing guest leaves, their
record replaces the departing one and the villa stops looking like a clean on
the day it most needs cleaning. Pre-existing, not introduced by this work, but
the arrival priority leans on it.

**Same phone, two villas.** Bookings are keyed by phone
(`responses/<date>/<phone>`), so one guest booking two villas produces one
record and the covers count comes up short. Discussed at length; no change
made. Room-plus-check-in-date was the leading alternative if a booking ID
never materialises from GuestTouch.

**Print header repetition** has still never been confirmed on a real phone.

**Georgia, San Francisco and the iOS fonts are not installed in the sandbox.**
Renders fall back, so anything font-dependent needs the user's eyes. There is
a `font-test.html` page live for exactly this.

---

## Lessons that earned their place in the styleguide

Worth reading before the next visual change, because they were paid for.

**Mock up first.** Changes that were mocked went in as one commit each and
stayed. Changes published first and iterated on the phone took four and five
commits and twice ended in a revert. The commit log on 13 Aug shows both
patterns an hour apart.

**Fix what you changed, not what it broke.** Several times a change of mine
caused a knock-on and the instinct was to adjust the thing that was already
right. The footer was correct; the confirmation card should have been built to
fit it.

**Measure, don't reason.** Every time a measurement came first, the fix was
right. Every time it was reasoned about, it was a patch. The group ring eating
24px of width, the pill's trailing letter-space, the stats font - all found by
measuring, none by looking.

**A subjective target must be made concrete before code is written.** "Make it
more pronounced" produced four attempts and a revert. "To be cleaned, to be
serviced, manager only" produced one commit.
