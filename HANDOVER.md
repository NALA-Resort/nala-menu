# NALA menu app: handover

Written 17 Aug 2026, replacing thirteen documents that had grown to contradict
each other. **This is the only one you have to read.** Everything else is
reference, listed at the end.

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

**Publish with `tools/push.py`.** Set `FILES` and `MSG`, run it, one commit.
It can add and update but **cannot delete**: use `tools/rm.py` for that. A
deletion that looks published and is not cost hours on 17 Aug.

**Fetch before pushing.** A second chat owns the print work, and both publish to
`main`. `/home/claude/publish.sh` refuses if `main` moved since your last push.

**Run every suite before publishing.** Fifteen of them, about 900 assertions,
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

## What another chat owns

The print chat owns `list.html`, `menu-print.html` and `housekeeping.html`.
Do not edit them. If a change is needed there, do it in shared code or hand it
over.

**It currently owes three nav entries** in `list.html` and `housekeeping.html`:
Front Desk Arrival, Registration and Pages. Plus the 320pt header bleed on the
Service Sheet and the one em dash in `list.html`.

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
   is tested; the feed is the problem.
2. **GuestTouch links** need `?b=<booking id>`. Nightly menu needs only that;
   pre-arrival also takes name and dates.
3. **Rotate four credentials:** GitHub token, Firebase key, `sync` passcode,
   shared secret. All have been pasted into chat. Issue two GitHub tokens,
   `nala-menu publish` and `nala-menu chef`, so either can be revoked alone.
4. **Delete leftover Firebase Auth logins** for anyone removed on Settings.
   Their access is already gone; this frees the passcode for reuse.
5. **Does Mews send true UTC?** The Worker takes the date part of `StartUtc`;
   the app uses the phone's clock. At UTC+8 an arrival after 4pm local would be
   recorded on the night before. One evening check-in in the Zap history settles
   it.
6. **Confirm dinner and breakfast hours.** Still provisional.
7. **The pre-arrival help line** under "will you dine on your first night" is a
   marked placeholder. The guest answers before that night's menu exists, so
   something has to stand in for it.

`TESTING.md` has ten checks a sandbox cannot run, ordered by what would hurt
most. Nothing there has been done.

### Mine to build

- ~~No `.validate` rule anywhere~~ **written 18 Aug, NOT DEPLOYED.** `rules.json`
  now bounds every node: types, ranges, allowed values, text lengths, and date
  and villa key formats. `tests/rules_test.js` checks them with targaryen, 68
  assertions. Twenty six shapes the live database accepts today are refused by
  the new file, and not one real write the app makes is broken by it, which was
  checked by running the same suite against both copies.

  **The repo copy is now ahead of what is deployed.** Until it is pasted into
  the Firebase console and Published, none of it is real.

  Writing them turned up a live permissions hole: housekeeping could set a
  villa's job, which `ROLES.md` has always said they cannot. Write permission
  in Firebase cascades down and cannot be taken back at a child, so the rule on
  `kind` never did anything, because write was already granted at the villa
  above it. The restriction now lives in a validate rule, which does not
  cascade.
- **Nothing reports the sync stopping.** If the Zap dies the boards do not go
  red, they show fewer bookings, which looks like a quiet week. Needs a
  heartbeat, which needs a Zapier schedule trigger to be honest.
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
- **Orphan `prearrival` records** against cancelled or mistyped ids sit forever.
- **Write back to Mews:** check-in status and dietaries into the reservation.
  Needs the Connector API. The hook is marked in `front-desk.html`.
- **Map Customer Id**, which identifies a guest across all their stays.

### Discussed, not designed

- Editing a registration card and saving from paper, rather than at the screen.
  Front Desk already edits the same data, and two editors for one record is how
  they drift.
- Widening the Mews look-ahead beyond about 84 hours. It is a boards question
  only: pre-arrival works without it.

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

## The rest of the documents

- `PARKED.md` questions waiting on an answer, each with the decision taken in
  the meantime so nothing is stalled on them.
- `STYLEGUIDE.md` before anything visual. Not optional.
- `TESTING.md` the ten checks only a human can run.
- `PLAN.md` the ordered build queue.
- `DESIGN.md` who owns which data, the screens, and why the identifiers are
  what they are.
- `SETUP.md` Firebase, Cloudflare and Zapier configuration.
- `CHEF-BRIEF.md` how the chef publishes a menu.
- `ROLES.md` the permission matrix.
- `tests/README.md` what each suite covers.
- `rules.json` a copy of the live database rules. **Not deployed from here:**
  paste it into the Firebase console and press Publish.
