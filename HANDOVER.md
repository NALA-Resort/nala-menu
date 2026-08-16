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
- **HANDOVER-MEWS.md** - the Mews to Zapier to Worker to Firebase sync, written
  16 Aug. Read it before touching bookings, the boards' guest data, or the
  pre-arrival work. It carries the original brief, the live configuration, and
  one change that was written but not published.
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

**First thing in a new session.** The sandbox is wiped between sessions, so
`/home/claude/push.py` and `/home/claude/.ghtoken` are both gone. The
publisher is kept in the repo: copy `tools/push.py` to `/home/claude/push.py`.
The token is not, and cannot be, because this repo is public. **Ask the user
for a GitHub token with contents:write and save it to `/home/claude/.ghtoken`.**
Ask at the start, not at the moment of the first push, so it is not discovered
halfway through a change.

**Test.** Five Playwright suites, all must stay green:

```
python3 tests/tally_suite.py    # 85 - Reservations
python3 tests/list_suite.py     # 42 - Reservations Sheet
python3 tests/hk_suite.py       # 22 - Clean Sheet
python3 tests/cl_suite.py       # 161 - Cleans
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

Thirty seven commits on 15 and 16 August. In order of consequence:

**Roles, stage one, shipped.** The email prefix check is gone. `roleOf()` and
`can()` in `nala-shared.js`, gates on Cleans, Reservations and the Sheet, and
the rules changed to match. The chef reads the reservations board and opens a
booking to see dietaries but writes nothing; the waiter has the board plus the
Cleans marks for departures and breakfast; housekeeping is unchanged.

**Passcode sign in.** A six digit keypad replaced the email form as the way in,
with the email form kept behind a long press on the wordmark. `auth.js` was
touched, with permission, and gained a test suite in the same commit: 6 tests
to 30.

**Notifications.** Web push, four events, a Cloudflare Worker sender.

**A Settings page.** `staff.html`.

**Boards refresh themselves** every 20 seconds, fetching only the four paths
that actually change. A full reload happens on returning to the app. This cut
a poll from 19 requests to 4, which is the difference between about 9GB and
1.9GB a month across five phones.

**The Cleans board fits one screen.** The rows share whatever height the phone
has rather than a fixed tile height, tested at real usable heights across
twelve devices.

**The home screen app stays an app.** Tapping a link used to hand the next
page back to the browser with all its bars.

**Printing rebuilt.** Also a square home screen icon, since the wide wordmark
was being stretched into it.

**No double tap zoom** on staff pages, and sign in fields are 16px so iOS
stops zooming the page when they are tapped.

## Next piece of work

**Mews PMS sync**, backlog item 6. Nothing designed yet.

Roles stage two is effectively done: `staff.html` covers managing people and
roles, which is what it described.

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

**Passcodes, not emails.** Everyone signs in on a six digit keypad. The code
IS the credential: the account is `<code>@staff.nala` with the same six digits
as the password. Six because Firebase rejects passwords under six characters.

The email form still exists as the recovery door, behind a **long press on the
NALA wordmark**. Only `admin@nalaresort.com.au` uses it. Keep it: Firebase can
send a password reset to a real address and cannot to `485211@staff.nala`.

**Roles come from the database, never from the address.** Each person has a
record at `/staff/<emailkey>` with `name` and `role`, where emailkey is the
lowercased address with every dot turned into a comma. No record means no
access, deliberately, so a typo grants nothing.

Four roles: `admin`, `chef`, `waiter`, `housekeeping`. The full access role
was called `staff` until the word collided with the `/staff` node; records
saying `staff` are still read as `admin` by `normaliseRole`, and that alias
can go once none do.

`nala-shared.js` holds the whole matrix in `ROLE_GRANTS` and answers through
`can(role, capability)`. Pages never ask which role someone has. Changing a
permission is one word on one line.

**What the database enforces**, as opposed to what the UI merely hides: only
an `admin` may write `hk/<date>/<villa>/kind`, `/staff` or `/notify`. Everything
else the roles do is UI only. Hiding a button prevents accidents, not
determined pokes, and the waiter restrictions in particular are CSS.

`/pushsubs/<emailkey>` is writable only by that person, readable by any
signed in user, because the push worker reads it with the caller's own token.

Rules live in the console. Nobody here has write access, so a rules change
means pasting the current ones in and getting a complete replacement back.
Do not write one from memory: `extcancel` exists only in the rules.

Still open: anyone who knows a guest's phone number can write that guest's
booking. Fixing it properly means signed links.

## Settings page

`staff.html`, admin only, reached from **Settings** in the hamburger. It ended
the console typing for staff and notifications, and should be the first place
you reach for before telling anyone to open Firebase.

It lists everyone, adds a person (creating the login and the record together),
changes names and roles, and removes people. Removing deletes the `/staff`
record, which is the actual revoke because the rules require it. It cannot
delete the Firebase Auth login: that is a console tidy up, and it means the
passcode cannot be reused until it is done.

Two people can never be removed, by rule rather than by passcode: yourself,
and the last remaining admin.

The same page holds the notification settings.

## Notifications

Real web push. A phone buzzes on the lock screen when a villa is marked.

- iOS only allows this for a site added to the Home Screen. In a browser tab
  the toggle says it is unavailable, because it is.
- The toggle is per phone, in the hamburger. Signing out unsubscribes.
- Four events: `departed`, `available`, `cleaned`, `serviced`. One "mark as
  done" tap is `cleaned` or `serviced` depending on the villa's job.
- Nobody is told about their own tap.
- Quiet hours and per role targeting live at `/notify`, changed on the
  Settings page. The app writes the defaults itself if the node is missing.

**The sender is a Cloudflare Worker**, not in this repo. Source is handed over
separately. It holds the VAPID private key and no database credential: the
phone sends its own Firebase token, the worker passes it to the database, and
the rules decide. An expired token gets a 401 and nothing is sent.

`sw.js` handles notifications and nothing else. It has no fetch handler and no
caching on purpose: a caching service worker would serve stale pages after
every publish and make "clear your browser data" a permanent instruction.

## Printing

Two paths, and the difference matters.

`window.print()` on an iPhone hands the printer a **bitmap**, which is why the
paper came out soft and pixelated. It is fine from a computer.

So both sheets build a **real PDF** with jsPDF and embedded Raleway. The
Reservations Sheet has a PDF button beside Print; the menu has always worked
this way. On a phone the PDF goes to the **share sheet**, because Print is in
there, and a download leaves someone hunting through Files.

The printed HTML has no tinted rows: on screen they group the sheet, on paper
they read as a photocopy. It fits one page at any margin from 10mm to 25mm,
which is checked in the suite.

Browser headers and footers are the print dialog's, not ours. No CSS removes
them. The PDF path avoids them entirely.

## Print design is being done in a parallel chat

The print and PDF work is owned by a second chat running at the same time.
That chat owns `list.html`, `menu-print.html` and `housekeeping.html`. This
one must not edit those three, and that chat must not edit anything else.

Both chats publish to main through the same script, and each commit lands on
top of whatever main is at that moment. There is no merge and no warning: two
chats editing one file means the second silently replaces the first. Fetch
before editing and check main has not moved.

**Shared file version bumps stay with this chat.** If `nala-shared.js`,
`nala-ui.css` or `auth.js` changes, this chat bumps the `?v=` everywhere. Two
chats bumping the same version will fight.

**That work is visual only**: font size, weight, spacing, rules, what sits
where on the page. It is not to change what the sheets MEAN or where their
data comes from. If a print change seems to need a data change, or a change
to `nala-shared.js`, it stops and comes back here.

## Backlog

**1. Rotate the GitHub token. STILL OPEN and now worse.** One token serves
both the owner and the chef brief, and it has been pasted into chat more than
once. Issue two fine grained tokens, `nala-menu publish` and `nala-menu chef`,
so either can be revoked without breaking the other.

**2. Do NOT commit the chef brief.** The earlier note said to. The repo is
public, so a token pushed there is world readable and GitHub revokes it
automatically, breaking the chef's publishing. Strip the token first if it
ever goes in.

**3. Remove the merge-tag test panel** from `welcome.html` once GuestTouch is
settled.

**4. Clear stale test data** in villas 3, 4 and 5.

**5. Confirm dinner and breakfast hours.** Still provisional.

**6. Mews PMS sync.** Not started, and the next piece of work. The intent is
Mews to Zapier to GitHub, presumably to stop `roomguests` being kept by hand.
Worth settling before any code: what Zapier writes to, whether it writes to the
database directly or commits a file, and what happens when a booking changes
after the fact.

**7. Sign in form flash.** Fixed. The pad appeared on a 500ms timer, so every
load with a good session flashed a sign in screen first. It now appears only
when auth reports nobody signed in.

**8. Delete the leftover Firebase Auth logins** for anyone removed on the
Settings page. Their access is already gone; this frees the passcode for reuse.

**9. `list.html` still contains one em dash**, the no reply marker in the HTML
table, and the suite asserts on it.

---

## Known gaps and risks

**`auth.js` now has a suite, 30 tests.** `index.html` still has none, and it
is the guest page.

**A green suite is not proof.** On 16 Aug the passcode screen shipped with 30
passing tests and broke sign in on a real phone for two hours. The suites stub
Firebase entirely, so they check the logic and the layout and can say nothing
about how the real SDK behaves on a real handset. Anything touching sign in,
push, or printing needs a device before it is believed.

**The thing that actually broke it was cached state**, not code: Firebase's
stored session on that phone was wedged, and clearing the browser's site data
fixed it instantly. Try that first, before any theory.

**Know which gates are real.** The database enforces only three things: who
may write `kind`, `/staff` and `/notify`, all admin. Every other role
restriction is the UI hiding buttons, which prevents accidents and nothing
else. The waiter's Cleans restrictions in particular are CSS.

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

**The role mechanism is a single email prefix check.** It cannot express the
four roles that were asked for, and it misfires on per-person logins:
`housekeeping.maria@` would be a cleaner, `maria@` would silently be full
access. Replacing it is the next piece of work; see ROLES.md.

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
