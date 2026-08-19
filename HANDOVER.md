# NALA menu app: handover

Written 17 Aug 2026, replacing thirteen documents that had grown to contradict
each other. **This is the only one you have to read.** Everything else is
reference, listed at the end.

**Last worked on 18 Aug 2026**, commit `ccf0094`. That day added test suites for
five untested pages, `.validate` rules on all fourteen nodes, the Mews timezone
fix, dated notes provenance, the cleans availability timer, the menu publish
notification, the orphan pre-arrival cleaner, vacant as the default villa state,
four role manuals, role gates on three pages that had none, the permission
matrix in Settings, and the Mews customer id. The live rules were pasted and
published that evening and match `rules.json`. Nothing is half finished: the
tree is clean and every suite was green at that commit.

**None of it has been tested by a human.** Every suite passes, and a suite is a
sandbox: it stubs Firebase, runs no real login, prints nothing, has no phone and
never sees Mews. Not one of the changes above has been used by a person on a
real device against live data. `TESTING.md` section 0 is the list of what to
tap, in order, and every item on it is unrun. Section 1 onward has been unrun
since the app was built.

So when the owner reports something not working, the first assumption is that it
does not work, not that they have misread it. Several times on 18 Aug their
instinct was right and this chat's reading of the code was wrong. A green suite
is evidence about the code, not about the app.

---

## What it is

A dinner service tool for NALA Resort, seventeen villas. Live at
**menu.nalaresort.com**, served by GitHub Pages from `main` in
`NALA-Resort/nala-menu`. Data in Firebase Realtime Database. Bookings arrive
from Mews through Zapier into a Cloudflare Worker.

Everyone works on a phone. Reception, housekeeping and the chef all use it
during service, one handed, interrupted.

---

## How to work here

**Reply in short point form.** What changed, what was found, what is left. The
explanation goes in the commit message, which is kept and can be read later. A
long reply is not thoroughness, it is work the user has to do. This is the
thing the user has asked for most often, so it is first on the list.

**Publish with `tools/push.py`.** Set `FILES` and `MSG`, run it, one commit.
It can add and update but **cannot delete**: use `tools/rm.py` for that. A
deletion that looks published and is not cost hours on 17 Aug.

**A write refused is not a login refused.** The database validates every field
it knows and refuses the WHOLE write when one fails, and the error it returns
is "Permission denied". That reads like a credentials fault and is usually not
one. On 18 Aug it cost an evening looking at logins that were fine. The Worker
now says which of the two it is; believe it. `tests/coercion_test.js` keeps the
Worker's payload and `rules.json` in step, since nothing else does.

**Fetch before pushing.** `/home/claude/publish.sh` refuses if `main` moved
since your last push. Written for a period when two chats published here; that
ended on 18 Aug, but the guard is kept against a stale clone.

**Run every suite before publishing.** Seventeen page suites, about 1200
assertions,
in `tests/`. See `tests/README.md`. They take about half an hour; publishing
without them is how the printed sheet went blind for two commits without a
single test failing.

**Mock up before you build anything visual.** Render it at 390pt, check 360,
do not break at 320. `STYLEGUIDE.md` first, always.

**Edits that can fail silently will.** Python's `str.replace` does nothing when
the text does not match and says nothing about it. Three bugs on 17 Aug came
from that: a function called but never defined, twice, and a duplicated fixture
key. Use something that errors on no match, and check every edit landed.

**Never em dashes.** Hyphen in a sentence, middot for a separator.

---

## Ownership

**One chat owns every file in the repo.** For part of 17 and 18 Aug a second
chat owned `list.html`, `menu-print.html` and `housekeeping.html` so design
work could run in parallel, and nothing else was allowed to touch them. The
owner ended that on 18 Aug. There is no longer any file that has to be handed
over rather than edited.

If a document still says otherwise, it is out of date and should be corrected
rather than obeyed.

**All four items inherited from that period were cleared on 18 Aug** in commit
`5e974f0`: the missing nav entries, the header bleed on the Service Sheet, the
em dash in `list.html`, and the missing role gate on `menu-print.html`.

---

## The data model, which is the thing to understand first

**The booking id identifies a guest. The date and villa identify a night and a
place, not a person.**

| Node | Keyed by | Holds |
|---|---|---|
| `/bookings/<id>/pms` | Mews reservation GUID | the reservation as Mews states it |
| `/bookings/<id>/prearrival` | same | what the guest told us, for the whole stay |
| `/stays/<date>/<villa>` | date and villa | who is in which villa each night |
| `/dinner/<date>/<villa>` | date and villa | **one** dinner answer per villa per night |
| `/hk/<date>/<villa>` | date and villa | housekeeping state |
| `/combined/<date>/<gid>` | date | villas seated at one table |

**The dinner cell is one cell.** Whoever answers first sets it: the guest from
their link, reception at the desk, or staff on the board. After that only staff
can change it. `by` records who, `at` records when. This replaced two nodes
holding the same fact, which is what let a dietary added on one screen be wiped
by a save on another.

**Old and retired**, read-only, emptying as dates age out: `/responses`,
`/roomguests`, `/guests`. Nothing writes them. Delete the nodes and their rules
once no date in the look-back window uses them.

### The Mews id, which took most of a day to get right

The reservation GUID arrives under a **different field name on every trigger**:

| Trigger | Where the GUID is |
|---|---|
| New reservation | `Id` |
| Modification | `MewsId`, and `Id` is a 32 character key that changes every event |
| Cancellation | `Id` |

The Worker therefore takes **whichever value is a GUID**, by shape, not by name.
Anything that is not a GUID is refused with a message rather than stored.

Keying on the wrong field made every event look like a new booking: one guest in
three villas, and a move never clearing the villa it left. As of 17 Aug the Zaps
send the GUID as `Id` on all three, with the modification's own key as `Id2`.

Also carried: `groupId` (one party can hold several villas), `number` (the Mews
reservation number staff can read out, shown at the desk and on the card).

---

## What is built

**Staff:** Reservations (`tally.html`), Front Desk Arrival (`front-desk.html`),
Cleans (`cleaners.html`), Settings (`staff.html`), Menu Dietaries (`tag.html`),
Statistics (`stats.html`).

**Paper:** Reservations Sheet (`list.html`), Clean Sheet (`housekeeping.html`),
Registration Cards (`registration.html`), Printable Menu (`menu-print.html`).

**Guest:** the nightly menu (`index.html`), pre-arrival (`prearrival.html`),
welcome (`welcome.html`). All take `?b=<booking id>`. Pre-arrival also carries
name and dates for display, because it is sent before Mews has the booking.

**Tools:** Diagnostics (`debug.html`), site map (`pages.html`).

The flow it delivers: a guest fills in pre-arrival, reception confirms it at the
desk against the real menu, and the answer lands on the chef's board typed
rather than handwritten.

---

## Open, and what it needs

### Waiting on a person

1. **Cancellations have never been seen to fire.** The Zap does not trigger.
   Until it does, a cancelled booking stays on the board. Worker handles it and
   is tested; the feed is the only problem. Confirmed 18 Aug that the
   cancellation `Id` is the same GUID as the reservation's, so nothing needs
   building: when the feed fires it will match.

   **Re-examine this now.** It was written while every reservation write was
   failing validation, so a cancellation that did fire would have been refused
   with the same 401 as everything else and looked like a feed that never
   triggered. Fixed 18 Aug in `9fea5ba`. Cancel a test booking in Mews before
   assuming the trigger is still the problem.

   Worth knowing either way: Zapier's Mews integration lists a raw HTTP request
   action that carries the integration's own authentication, and Zapier has an
   API Request action in beta. Paired with a Schedule trigger that gives
   polling, which would remove the dependency on Mews firing at all. Zapier
   stopped enabling the feature for new integrations in July 2024, so whether
   it is switched on for this account is unknown. Ten minutes in the Zap editor
   under Mews actions would answer it.
2. **GuestTouch links** need `?b=<booking id>`. Nightly menu needs only that;
   pre-arrival also takes name and dates. The full mapping onto Mews field
   names, and what goes wrong if `b` resolves to the customer id or the
   reservation number instead of the reservation GUID, is written out in
   `SETUP.md` job 7. The owner was briefing a programmer on this on 18 Aug.
3. **Work through `SECURITY.md`.** Four jobs, about forty five minutes, all of
   it done by the owner in a browser and none of it doable from here. Written
   one action per step, with what breaks while each is half done. The owner
   said on 18 Aug they would action it that night, so check before assuming any
   of it is still outstanding.

   - **Rotate the five credentials:** two GitHub tokens, `sync` passcode,
     shared secret, and the Firebase web API key. All have been pasted into
     chat. The two GitHub tokens are `nala-menu publish` and `nala-menu chef`,
     issued separately so either can be revoked alone. The passcode and the
     secret each stop the Mews sync while they are half done.
   - **The Firebase web API key is the exception: advise against rotating it.**
     It is public by design, it is in `auth.js` and in every browser that has
     loaded the app, and rotating it breaks the site between the new key
     existing and somebody publishing it into the code. Restricting it by
     referrer is the job that helps.
   - **Delete leftover Firebase Auth logins** for anyone removed on Settings.
     Their access is already gone; this frees the six digit passcode for reuse.
   - **Restrict the Firebase key** to `nalaresort.com` in the Google Cloud
     console, and prune the Authorised domains list in Firebase Auth. **Leave
     `localhost` in that list**: it is how the suites sign in, and removing it
     turns every suite red for a reason nobody would guess at.
   - **Optionally make the repository private.** Needs GitHub Team, since
     `NALA-Resort` is an organisation. It hides the documents, the rules copy
     and the tests. It does not hide the app, which is served to browsers and
     always readable. Going private can silently drop Cloudflare's access to
     the repo and stop the Worker deploying.

   If the owner reports a step that does not match what is on screen, fix
   `SECURITY.md` at the same time as answering. These consoles rename things.
5. ~~Does Mews send true UTC?~~ **Answered 18 Aug: it does.** 04:00Z is 2pm at
   the resort, UTC+10. The Worker converted nothing, so any timestamp after 2pm
   UTC was filed a day early, which is every arrival before 10am local and
   every checkout before 10am local. Fixed, with six cases in the Worker suite.
   The app still takes "today" from the phone's clock, which agrees as long as
   the phone is at the resort.
6. ~~Confirm dinner and breakfast hours.~~ **Answered 18 Aug.** Dinner 6:00 to
   6:30, breakfast 8:00 to 9:30. Nothing displays them yet: no page has ever
   stated a service time. Where they should appear is a design decision, so it
   is in `PARKED.md` with a proposal rather than guessed at here.
7. **The pre-arrival dining description is placeholder copy.** Asked for on
   18 Aug: a short description of how dining works, above the opt in rather
   than under it, because the guest is being asked to commit to something
   nobody has described. Written and live. The seating time in it is real; the
   rest stands in and is deliberately plausible, because the page is live and
   a guest may read it before the final words arrive. Breakfast is not
   mentioned, as asked. The marker is a comment in the source, not on screen.
   Replace the words in `prearrival.html`, id `dineHelp`. The guest answers before that night's menu exists, so
   something has to stand in for it.

`TESTING.md` has ten checks a sandbox cannot run, ordered by what would hurt
most. Nothing there has been done.

### Mine to build

- ~~No `.validate` rule anywhere~~ **written and deployed 18 Aug.** `rules.json`
  now bounds every node: types, ranges, allowed values, text lengths, and date
  and villa key formats. `tests/rules_test.js` checks them with targaryen, 68
  assertions. Twenty six shapes the database accepted before are now refused, and
  not one real write the app makes is broken by it, which was checked by running
  the same suite against both copies.

  **Published to the console 18 Aug.** The repo copy and the live rules match.
  `TESTING.md` section 0 is the six tap smoke test that has not been run yet:
  the one thing the suite cannot prove is that a page does not write a field
  nobody wrote down, and such a write now fails silently.

  Writing them turned up a live permissions hole: housekeeping could set a
  villa's job, which `ROLES.md` has always said they cannot, confirmed by the
  owner on 18 Aug. Write permission
  in Firebase cascades down and cannot be taken back at a child, so the rule on
  `kind` never did anything, because write was already granted at the villa
  above it. The restriction now lives in a validate rule, which does not
  cascade.
- **Nothing reports the sync stopping.** If the Zap dies the boards do not go
  red, they show fewer bookings, which looks like a quiet week. Needs a
  heartbeat, which needs a Zapier schedule trigger to be honest.

  **This is also why the Cleans board says Unknown rather than Empty** for a
  villa with no booking on either night, and the reasoning is worth keeping
  because it looks like a missing feature. Mews only ever tells us about
  reservations, so there is no positive signal for a vacant villa: absence is
  the only evidence available, and absence cannot tell a quiet night from a
  broken sync. On 19 Aug every reservation write was being refused, `/stays`
  genuinely held nothing, and a board willing to read absence as vacant would
  have reported seventeen empty villas with total confidence.

  A heartbeat is what would earn it. With the Worker recording its last
  successful run, absence becomes conditional: no booking and a sync twenty
  minutes old is vacant; no booking and a sync from yesterday is unknown, and
  says so loudly. Until then Unknown is the honest answer and "Mark as empty"
  is the manager saying what the data cannot.
- **The notification Worker is not in this repo.** It holds the VAPID key and
  exists only on the owner's machine. If lost, a working feature cannot be
  rebuilt.
- ~~Five pages have no suite~~ **done 18 Aug.** `welcome`, `debug`, `stats`,
  `tag` and `menu-print` now have one each, 184 assertions. Writing them found
  three live bugs, all fixed: Statistics was reading only the retired
  `/responses` node so every night since 17 Aug was invisible; it grouped by
  cut name before animal, so a lamb rump counted as beef; and Menu Dietaries
  treated a refused read as an empty list, seeded the eight defaults over it,
  and offered a Save that would have written them over the chef's real list.
  `debug` and `menu-print` were already correct.
- ~~Orphan `prearrival` records~~ **done 18 Aug.** Diagnostics has a find and
  clear pair for them, listing before deleting like the other two. Deliberately
  narrow: only a booking Mews calls cancelled, and an id Mews has no record of
  at all. A stay merely in the past is never listed, because those answers are
  the record of a guest who came, and "looks old to me" is not a rule to apply
  to somebody's words about their own allergies. Only the `prearrival` child is
  deleted, since the rules grant write there and not on the booking, so an id
  with nothing else on it is left as an empty shell rather than half deleted.
  Fourteen cases in the Diagnostics suite, including that a refused read is not
  reported as a clean database.
- **Write back to Mews:** check-in status and dietaries into the reservation.
  Needs the Connector API. The hook is marked in `front-desk.html`.
- ~~Map Customer Id~~ **done 18 Aug.** Read by GUID shape from `CustomerId`,
  `AccountId` and their variants, so Zapier's own 32 character event key cannot
  land there and attach every booking to a customer who does not exist. Stored
  on `/bookings/<id>/pms` only: the nights are read constantly and never need
  it, while the write back to Mews happens once per booking. Stored now because
  backfilling it means replaying every reservation event that has ever fired,
  and Zapier does not keep them.
- ~~Vacant as the default villa state~~ **done 18 Aug**, to the owner's
  definition: vacant means no guest profile is attached to the villa for that
  date; awaiting means one is and there is no yes or no to dinner yet. A Mews
  reservation moves a villa from the first to the second for every night of the
  stay. Nothing is written: it is what the board shows in the absence of an
  answer. The awaiting count now means villas somebody has to chase, which on a
  quiet night used to read seventeen.

#### Asked for 18 Aug

1. **Cleans timers: green for the first ten minutes.** Today the elapsed
   figure beside "Available" is plain ink until 15 minutes, amber from 15, red
   from 20. There is no green at all, so a villa turned around inside the
   window looks the same as one nobody has touched. Ink to green under 10,
   ink 10 to 15, then the existing amber and red. `cleaners.html:489` and the
   three rules at `cleaners.html:95`. Colours already exist as `--green` and
   `--greenb`. Mock at 390 first: this is the tile everyone reads at a glance.
2. **The notes bubble is showing the wrong notes.** It should carry only the
   dietaries and notes written on the dining invitation, and it must say which
   night they belong to: "Today's dining notes" against "Previous dining
   notes". Right now a note from an earlier stay reads as tonight's, which is
   the kind of thing that reaches a plate. The dinner cell is per date, so the
   date is already there to stamp with. Check every board that renders the
   bubble, not just the one it was noticed on.
3. ~~Chef brief needs a link to Menu Dietaries.~~ **Done 18 Aug.** Step 4 of
   the brief now prints three lines: the confirmation, a link to tag tonight's
   dietaries, and the notify link. Tagging comes after publishing because the
   page has nothing to tag before it.
4. **Publishing the menu notifies the manager. Built 18 Aug, NOT PROVEN.**
   `menu` is a new event in the existing per event, per role list, on for the
   manager and nobody else. The chef publishes by pushing a commit, so nothing
   in the database moves and there is nothing to watch: the notification hangs
   off the one moment the app can tell, which is a board noticing the menu
   changed and archiving it for Statistics. It fires once per published menu,
   and it names no actor, because naming the manager whose board happened to
   notice would suppress the one notification it exists to send.

   Two things stop this being finished. **If no staff board is open, nobody is
   told until one is.** A commit hook into the notification Worker would close
   that. And **the notification Worker is not in this repo**, so whether it
   handles an event called `menu` is unknown and untestable from here. Until
   that is confirmed on a real phone, the manual notify link stays in the chef
   brief. Removing it first would leave the manager relying on something nobody
   has seen work.
5. **The demo sheets do not update themselves.** Asked 18 Aug. They are
   standalone copies built by `python3 tools/make-demo.py`, and they cover four
   pages only: Reservations, the Reservations Sheet, Cleans and the Clean
   Sheet. Nothing rebuilds them on a commit, so any change to those four pages
   leaves the demos showing the old one until somebody runs the script. Worth
   putting in whatever checklist ends up governing a release, or better,
   running it from the same place the suites run.
6. **Not a bug: no menu published means nothing to tag.** Reported 18 Aug as
   "cannot select dietaries, only archive them". The tick rows are built from
   tonight's published menu, and `menu.json` was last published 17 Aug at 9:26,
   so the page correctly had no dishes to offer and only the manage list was
   interactive. The page does say so, and it was still read as broken, which
   makes it a wording problem rather than a logic one. Say it where the ticks
   would have been, not above them.

### Discussed, not designed

- Editing a registration card and saving from paper, rather than at the screen.
  Front Desk already edits the same data, and two editors for one record is how
  they drift.
- Widening the Mews look-ahead beyond about 84 hours. It is a boards question
  only: pre-arrival works without it.
- ~~A permission matrix in Settings~~ **done 18 Aug.** Roles against what each
  may do, on screen and editable, rather than the table in `ROLES.md` and a
  rules file only a developer can read. The reason it was worth doing is the
  hole found the same day: housekeeping could set a villa's job for months
  because the rule that forbade it never ran, and nothing anywhere showed the
  gap between what the document said and what the database allowed.

  `/permissions/<action>/<role>` holds only the boxes moved away from the
  shipped defaults, and `can()` treats anything that is not an explicit true or
  false as no opinion. Storing every cell would have frozen today's defaults
  into the database, so the next capability added to the app would arrive
  switched off for everybody with nothing to say why. `loadStaff()` fetches the
  matrix with the records, so no page needed changing, and a failed matrix read
  is not reported to the pages: the defaults are a working app, and refusing
  everyone because an override list did not answer turns a small outage into a
  locked door.

  Two invariants are in the rules and not only in the page, since the page is
  not the only way to write there. `manageStaff` cannot be handed out, because
  handing out the ability to hand things out is a second manager rather than a
  permission. And `admin` is not a column, and is answered before the matrix is
  consulted, so a stray false typed into the console cannot lock the only
  person who can undo it out of the page where it is undone.

  Two limits stay, both from the probe. The rule text still has to exist per
  node, so toggling a row is free but ADDING a row is still a rules change and
  still a paste. And only `setJob` is a write these rules can see, so it is the
  only one of the seven enforced by the database; the other six hide a button,
  which is honest-mistake protection and not a lock. The note under the grid
  and the manager's manual both say so rather than implying more.

---

## Things that were true and are not

Worth knowing because they are written elsewhere and they are wrong now.

- The guest link used to carry a phone number. It never shipped, and the whole
  scheme is gone.
- `roomRecord` used to merge `responses` and `manual` by precedence. One cell
  replaced both, and the merge with it.
- `prearrival.dining` was briefly a separate field. It was a third copy of the
  dinner answer and was removed.
- Confirming at the desk used to move a guest to Arrived. Confirming and
  checking in are now two buttons and two fields.

---

## Standing cautions

**A green suite is not proof.** The suites stub Firebase entirely. On 16 Aug the
passcode screen shipped with 30 passing tests and broke sign in on a real phone
for two hours. Anything touching sign in, push or printing needs a device.

**When a page dies, look for a failed read reported as empty.** Clean Slate
counted 0 records for four nodes it could not read, reported success, and
deleted nothing.

**Never commit the chef brief.** The repo is public, GitHub auto-revokes a token
pushed to it, and that breaks the chef's publishing.

**Fonts.** Georgia, San Francisco and the iOS system fonts are not installed in
the sandbox, so every render falls back. `font-test.html` exists for this.

---

## The manuals

Four cheat sheets, one per role, written 18 Aug: `MANUAL-ADMIN.md`,
`MANUAL-CHEF.md`, `MANUAL-WAITER.md`, `MANUAL-HOUSEKEEPING.md`. Each says what
the screens are for and why they behave as they do, not how to tap them.

They were written partly to be handed out and partly as an audit. Explaining a
design to somebody who has not read the code is the fastest way to find the
places where the code does not agree with itself. Writing these four found
three:

1. **Diagnostics had no role gate.** Any login that could sign in could open it
   and run Clean Slate, which deletes the operational database. A cleaner, a
   waiter, the chef. Now manager only. The rules cannot catch this, because the
   deletes it makes are the same writes those roles legitimately make
   elsewhere, so the page has to be the gate.
2. **Menu Dietaries and Statistics had no gate either.** Dietaries is now the
   chef's and the manager's, Statistics matches the Reservations board.
3. **`ROLES.md` said a waiter has no access to the Cleans board.** The code has
   given them one since it was written, deliberately, so they can say a villa
   looks free after breakfast. The document was wrong, not the code, and it
   now says which of the two wins when they disagree.

## The rest of the documents

- `PARKED.md` questions waiting on an answer, each with the decision taken in
  the meantime so nothing is stalled on them.
- `STYLEGUIDE.md` before anything visual. Not optional.
- `TESTING.md` the checks only a human can run: section 0 is everything that
  changed on 18 Aug, sections 1 onward the older ones. **All of it unrun.**
- `PLAN.md` the ordered build queue.
- `DESIGN.md` who owns which data, the screens, and why the identifiers are
  what they are.
- `SETUP.md` Firebase, Cloudflare and Zapier configuration.
- `NOTES-AUDIT.md` every place free text about a guest is stored, what it is
  for and how long it lasts. **It names one live bug:** the reservations board
  writes a dietary note to the night only, so one typed there is gone at
  midnight, while the same note from the desk survives. Fix that before the
  larger question of typing notes.
- `SECURITY.md` the credential rotations, the login tidy up, locking the
  Firebase key to the site, and what making the repository private does and
  does not protect. Click by click, because all of it is done by the owner in a
  browser and none of it can be done from here.
- `CHEF-BRIEF.md` how the chef publishes a menu.
- `ROLES.md` the permission matrix.
- `tests/README.md` what each suite covers.
- `rules.json` a copy of the live database rules. **Not deployed from here:**
  paste it into the Firebase console and press Publish.
