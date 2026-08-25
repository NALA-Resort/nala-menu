# NALA menu app: handover

**This is the only document you have to read.** Everything else is reference and
is listed at the end.

---

## Starting from nothing

You are most likely reading this having fetched it from
`raw.githubusercontent.com`, with no clone and no credentials. Get the clone
first; everything below assumes it.

    git clone https://github.com/NALA-Resort/nala-menu.git /home/claude/nala
    cd /home/claude/nala

The suites expect the working copy at exactly that path.

This section exists because the first version of this document assumed a clone
and a token that a fresh chat does not have, and the owner tried it cold and
stopped at the first step.

The repo is **public** (until `SECURITY.md` job 4), so the clone needs no
credential. Publishing does.

**To publish you need a GitHub token** with `contents: write` on
`NALA-Resort/nala-menu`, saved to `/home/claude/.ghtoken`. Ask the owner for it;
it is his to issue and it is never written into this repo. Two have already been
leaked into chat and are on his list to rotate, so do not reuse one you find in
a transcript.

    printf '%s' 'ghp_...' > /home/claude/.ghtoken

**`tools/publish.sh` publishes for real the moment that token exists**, from any
clone, including a scratch one: the token lives at a fixed path outside the
repo, so a second clone made for testing inherits it. On 23 Aug a run of it "to
check it works from a fresh clone" put a commit called `test` on `main`. It
changed nothing, because the file it published was byte for byte identical, but
the log carries it. **There is no dry run. Do not invoke it to find out whether
it works.**

**To run the suites** you need Playwright and Chromium, and targaryen for the
rules test:

    pip install playwright --break-system-packages && playwright install chromium
    npm install targaryen          # once, in the repo root

Both were already present in the sandbox this was written in. Check before
installing.

**What the sandbox cannot do.** It cannot reach Firebase, Google or
`menu.nalaresort.com`: every request returns the egress proxy's own 403. That is
a network allowlist on the owner's account rather than a hard limit, and it has
been so since the first session. It means every check here is local Playwright
against a stubbed Firebase, and **nothing you do can be verified against live
data**. Say that plainly rather than reporting a stubbed pass as proof. The
domains to add, if he ever wants that: `identitytoolkit.googleapis.com` and
`nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app`.

**Where things are.** The site is the repo root, served by GitHub Pages at
`menu.nalaresort.com`. Scripts are in `tools/`. Tests are in `tests/`. The
Cloudflare Workers are `worker/mews-sync.js` and `worker/send-invites.js`; the
notification Worker lives in the Cloudflare dashboard and is **not** in this
repo. Once `DEPLOY.md`'s one-time setup is done, a push to `main` deploys the
Workers and `rules.json` by itself; until then they are pasted per `SETUP.md`.

**Then ask the owner what he wants to work on.** Do not start on anything in the
open lists below because it is written down. They are there so you can answer
when he asks what is outstanding, not so you can pick.

Consolidated 23 Aug 2026 from `HANDOVER.md` and `PARKED.md`, which had grown to
843 and 213 lines and overlapped: the handover carried an open-work section and
the parked file was a second one, so two sessions editing on the same day
collided in both. **Both are deleted.** If either reappears, something has
restored an old clone: delete it again rather than merging it back, or the
collision this exists to end comes back with it.

The dated diary entries that made up half the old file are gone. The git log
holds that history in more detail, attached to the code it explains, and every
commit here is written to be read later.

---

## What it is

A web app for a seventeen villa resort. Mews is the source of truth for
reservations; a Cloudflare Worker takes what Zapier sends and writes it to
Firebase; a set of static pages read and write the rest. It is live at
`menu.nalaresort.com` and in use during service.

The flow it delivers: a guest fills in pre-arrival, reception confirms it at the
desk against the real menu, and the answer lands on the chef's board typed
rather than handwritten.

The chef's own flow: he photographs the handwritten menu, a chat reads it and
hands him a link, he checks the reading against his handwriting on
`publish.html`, ticks the dietaries and publishes. `CHEF-BRIEF.md` is what that
chat is given.

---

## How to work here

**Reply in short point form.** What changed, what was found, what is left. The
explanation goes in the commit message, which is kept and can be read later. A
long reply is not thoroughness, it is work the user has to do. This is the thing
the user has asked for most often, so it is first on the list.

**Give an estimate before starting any fix or upgrade.** One line, before the
first edit, split three ways: writing, verifying, publishing. Say what would
make it longer.

    Roughly: 5 min to write, 5 min of suites, 1 min to publish. Longer if the
    rules need a change, because that needs a paste into the console.

This is a rule because of 19 Aug. A seventy line fix took thirty minutes, the
user had opted into it believing it was small, and it WAS small: the time went
on suites run one at a time and on a suite that hung. None of that was visible
from outside, so a fix proceeding normally was indistinguishable from one that
had gone wrong. The estimate is not a promise about speed. It is what lets the
user tell those two apart and decide whether to spend the time at all.

Update the estimate out loud when it moves, and say why. An estimate that
silently doubles is worse than none.

**Publish with `bash tools/publish.sh "<message>" <file> [<file>...]`.** It
rewrites `tools/push.py`, runs it, and ends in a hard reset, so a file you
changed but did not pass is discarded: it refuses rather than discard, and
refuses again if `main` moved since this clone last published. Never call
`push.py` directly. Deletions need `tools/rm.py`; a deletion that looked
published and was not cost hours on 17 Aug.

These live in the repo, not in the sandbox, which is wiped between sessions.
They were sandbox-only until 23 Aug, which meant the first instruction in this
document did not work on a fresh session. If `tools/publish.sh` is missing you
are on an old clone: `git pull`.

It needs a GitHub token in `tools/push.py`'s environment. That token is the
owner's to issue and is never written into this repo.

**Run the suites with `python3 tests/run.py`.** One command, in parallel, prints
a table. Do not type them out one at a time.

    python3 tests/run.py              # everything except the demo check
    python3 tests/run.py --changed    # only what covers your modified files
    python3 tests/run.py tally index  # by name

Run everything before a publish. Publishing without them is how the printed
sheet went blind for two commits without a single test failing.

**Mock up before you build anything visual.** Render it at 390pt, check 360, do
not break at 320. `STYLEGUIDE.md` first, always.

**Edits that can fail silently will.** Python's `str.replace` does nothing when
the text does not match and says nothing about it. Use something that errors on
no match, and check every edit landed. When replacing a whole function, match
its braces rather than taking a window of characters: a window left four pages
of broken JavaScript on 23 Aug.

**Never em dashes.** Hyphen in a sentence, middot for a separator.

---

## Ownership

**One writer per file.** A second session (Claude Code, on the owner's desktop)
works this same repo and was active again on 23 Aug. Coordination is by commit
message and by not touching a file somebody else is in.

Both sessions edited this document and the parked list on 23 Aug and the
numbering collided in each, which is part of why they are now one file. If you
are the second session, say which files you are taking.

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
| `/menu` | single node | tonight's four courses |
| `/menutags/<date>` | date | which dietaries each course clashes with |
| `/dietaries` | single node | the list a guest chooses from |
| `/settings/managerMobile` | single node | for the Notify link; not in this repo |

**The dinner cell is one cell.** Whoever answers first sets it: the guest from
their link, reception at the desk, or staff on the board. After that only staff
can change it. `by` records who, `at` records when. This replaced two nodes
holding the same fact, which is what let a dietary added on one screen be wiped
by a save on another.

**The menu has one reader**, `fetchMenuAnywhere` in `nala-shared.js`. It reads
the database first and falls back to the committed `menu.json`, refuses a file
that is not for the day being asked about, and reports an unreadable menu
separately from an absent one. Three different pages had grown their own version
of this and each was wrong differently.

**Old and retired**, read-only, emptying as dates age out: `/responses`,
`/roomguests`, `/guests`. Nothing writes them.

### The Mews id, which took most of a day to get right

The reservation GUID arrives under a **different field name on every trigger**:
new reservation `Id`, modification `MewsId` (its `Id` is a 32 character key that
changes every event), cancellation `Id`. The Worker takes **whichever value is a
GUID, by shape, not by name**, and refuses anything else with a message rather
than storing it.

Keying on the wrong field made every event look like a new booking: one guest in
three villas, and a move never clearing the villa it left.

Also carried: `groupId` (one party can hold several villas), `number` (the Mews
reservation number staff read out).

---

## What is built

**Staff:** Reservations (`tally.html`), Front Desk Arrival (`front-desk.html`),
Cleans (`cleaners.html`), Publish Menu (`publish.html`), Settings
(`staff.html`), Dietary Settings (`tag.html`), Statistics (`stats.html`).

**Paper:** Reservations Sheet (`list.html`), Clean Sheet (`housekeeping.html`),
Registration Cards (`registration.html`), Printable Menu (`menu-print.html`).

**Guest:** the nightly menu (`index.html`), pre-arrival (`prearrival.html`),
welcome (`welcome.html`). All take `?b=<booking id>`.

**Tools:** Diagnostics (`debug.html`), site map (`pages.html`).

**The menu on every staff page is one list** in one order, minus the page you
are on, grouped: the screens you work on, then Print, then Settings, then Sign
out. `NAV_NEEDS` in `nala-shared.js` maps each link to the permission that opens
it. **Add a page and add it there**, or it appears in everyone's menu. Six pages
once kept private copies of that filter and hid whatever they did not
recognise; `pages_suite` now fails if any page keeps one.

---

## Standing cautions

**A green suite is not proof.** The suites stub Firebase entirely. On 16 Aug the
passcode screen shipped with 30 passing tests and broke sign in on a real phone
for two hours. Anything touching sign in, push or printing needs a device.

**Break the fix and watch the test fail.** Five times in three days to 23 Aug a
new assertion was aimed next to the thing rather than at it and passed while the
bug shipped: a variable instead of the screen, a substring instead of the shape,
the original element instead of the printed clone, a button's presence instead
of whether it renders, a gap measured before scrolling. A test written after a
fix proves nothing until it has been seen to fail without it.

**Bump `?v=` when you change a shared file.** `nala-shared.js` and `auth.js` are
cached by that query string and nothing else. It went unbumped through four
changes to 23 Aug, so browsers ran old copies and correct published fixes never
reached the phone reporting them: the owner spent days retesting against old
code. `pages_suite` fails if either file has been touched since the version
browsers ask for. **If a fix seems not to have landed, look here first.**

**One route cannot answer two sources.** The database URL and the committed file
both end in `/menu.json`, so `pg.route("**/menu.json*")` catches both. Three
suites did that, which is why every menu fallback path was untested and a stale
file reached the printed menu unnoticed.

**A write refused is not a login refused.** The database validates every field
it knows and refuses the WHOLE write when one fails, returning "Permission
denied". That reads like a credentials fault and usually is not. On 18 Aug it
cost an evening looking at logins that were fine.

**A failed read is not an empty one.** Clean Slate counted 0 records for four
nodes it could not read, reported success, and deleted nothing. The same shape
recurs: an empty node and a refused read must never take the same branch.

**Never put a credential in this repo.** It is public until `SECURITY.md` job 4.
The chef brief carried a GitHub token until 22 Aug; it now carries no token, no
passcode and no code, which is why it is in the repo at all. The manager's
mobile lives in the database for the same reason.

**The sandbox cannot reach Firebase, Google or the live site.** Every check here
is local Playwright against a stub. That is a network allowlist on the owner's
account, not a hard limit, and it has been that way since the first session. Say
so rather than reporting stubbed results as verification.

**The sandbox proxy lies about the live site.** curl to `menu.nalaresort.com`
returns the proxy's own 403, which greps as "the old build". Verify deploys by
the Pages build API and `raw.githubusercontent.com`.

**A Pages build can wedge** at status building, duration 0. The fix is a fresh
push: a one-line change to `.build-nudge`.

**Fonts.** Georgia, San Francisco and the iOS system fonts are not installed
here, so every render falls back. `font-test.html` exists for this.

**The demo sheets are rebuilt on request**, by `tools/make-demo.py`. Any change
to a sheet leaves them behind; that is expected and not a reason to hold up a
fix. `tests/run.py` reports how many have drifted.

---

## Open: waiting on the owner

None of these can move without him.

1. **Work through `SECURITY.md`.** Four jobs, about forty five minutes, all in a
   browser. Rotate the credentials (including two GitHub tokens that have been
   pasted into chat), delete the leftover Firebase logins, lock the Firebase key
   to the site, make the repository private.
2. **Decide the guest page's dietaries: gone for good, or back, and how.** The
   whole of it, including how to do either, is the first entry under Parked
   decisions below. It is listed here only so the question is visible when he
   asks what is outstanding.
3. **Set `/settings/managerMobile`** in the Firebase console, as a plain string
   like `+61400000000`. The publish page reads the Notify management link from
   there. Until it is set the line reads as it did before, with no error.
4. **Delete `menu.json` from the repo.** It holds the menu of 22 Aug and nothing
   rewrites it now that publishing is in the database. Harmless since 23 Aug,
   because the reader refuses a file that is not for the day being asked about,
   but it is dead weight that only ever misleads.
5. **Cancellations have never been seen to fire.** The Zap does not trigger.
   Until it does, a cancelled booking stays on the board. The Worker handles it
   and is tested; the feed is the only problem.
6. **GuestTouch links** need `?b={{bookingId}}&r={{roomnumber}}`. This failed
   for real on 22 Aug: the invitations went out with `{{bookingId}}` unmerged,
   so every confirmation was refused while the guest was thanked. The guest page
   now says when an answer did not save, and `r` is the villa fallback. Bare
   digits: `Room 12` is treated as absent rather than cleaned into a guess.
7. **The pre-arrival dining description is placeholder copy.** Standing in and
   live. Only the 6:00 to 6:30 seating is a real fact; the rest is invented and
   should be his. `prearrival.html`, id `dineHelp`.
8. **Confirm the Mews companion field** against a live Zap run.
9. **`TESTING.md`** is the checks only a human can run. **All of it unrun.**

---

## Open: parked decisions

Each carries the decision taken in the meantime, so nothing is stalled.

**The guest page's dietaries, hidden 23 Aug.** This is owner item 2 above and
the detail lives here, in one place, so an edit to one cannot leave the other
saying something else. The nightly menu page is a yes or no with a confirmation
while it is hidden.

To remove for good: delete the
four fields of the confirm step and the two save checks that stand aside under
`hide-diet`. To bring back: remove the class from the body tag. The suite
carries both states under `DIET_HIDDEN`. A standing dietary from pre-arrival
still rides on the answer and still flags a clash to the kitchen either way.

**Companions on the reservations sheet.** The sheet prints one name per villa
and never printed the companion. The owner reported "only companion zero
prints", which does not match anything in the sheet, so the fault is not
established: either the sheet simply never had the field, or `companionName()`
in the Worker picks the wrong one. It returns the first companion who is not the
booker, deliberately. **Settle first whether a villa can hold more than one
companion**, because the field is a single value everywhere and printing two
means changing the shape of the record.

**A party in two villas loses the higher one's dinner.** `dinnerElsewhere` drops
a cell when the booking id appears under a different villa, which is right for a
guest who moved rooms. But it returns on the FIRST match, and JavaScript
iterates integer-like keys in ascending order, so it answers about the lowest
numbered villa rather than the one asked about. Never caught because every
fixture omits `bookingId` from the cell, so the gate has not once been
exercised. Production cells always carry one.

**A vacant mark can be discarded the moment it is made.** Marking a villa vacant
where Mews has a booking stamps `pmsUpdated` so the decision expires when Mews
changes. When Mews sends no `UpdatedUtc` that stamp is `null`, Firebase deletes
a key written as null, it reads back `undefined`, and `vacantIsStale` compares
`undefined !== null` and discards the mark. There is a second candidate for what
the owner saw: on Reservations a villa with no booking already draws as vacant,
so marking it changes nothing and nothing is wrong. Which villa decides whether
this is one bug or two.

**Vacant versus Unknown on the Cleans board.** Mews only sends reservations, so
absence cannot tell a quiet night from a broken sync, and the board says Unknown
rather than guessing. A heartbeat would retire it and was impossible until the
Worker gained a cron on 21 Aug. Now buildable.

**Two finished Worker edits** are written and waiting on a deploy. The reasoning
is in commit `25076ad`.

**A logs upgrade**, named 21 Aug: the Worker writes nothing durable, so a sync
that misbehaves leaves no trace to read afterwards.

**Statistics counts a vacant villa as nobody, not as a no.** Deliberate for now.
Also unsettled: how far back Statistics should look.

**Dish groups** and **where the service hours should appear** were both raised
and neither is designed.

---

## Known failing tests, none of them new

- `cl_suite`: "a pushed villa returns tomorrow as a departed clean" and "a
  pushed-in villa is not offered a departure mark".
- `tally_suite`: "the admin: no input under 16px".
- `rules_test`: two "a waiter may not" about internal notes, from the other
  session widening `/internal` to any staff role.

Anything else failing is yours.

---

## The rest of the documents

- `STYLEGUIDE.md` before anything visual. Not optional.
- `NOTES-AUDIT.md` **read before touching any note or dietary.** The four note
  model, every place free text about a guest is stored, and one live bug with
  the fix worked out.
- `SECURITY.md` the credential rotations and the lock-down, click by click.
- `SETUP.md` Firebase, Cloudflare and Zapier configuration.
- `DEPLOY.md` how `rules.json` and the Workers deploy from `main` without
  pasting, and the one-time setup that turns it on.
- `DESIGN.md` who owns which data and why the identifiers are what they are.
- `ROLES.md` the permission matrix. Where it and the code disagree, the code
  wins and the document gets corrected.
- `TESTING.md` the checks only a human can run.
- `PLAN.md` the ordered build queue.
- `CHEF-BRIEF.md` what the menu chat is given: read the photo, show the four
  courses back, hand over a link.
- `CHEF-BRIEF-CONSOLE.md` the fallback for a chat with no network, which pastes
  JSON into the Firebase console. Kept because the scripted path failed at
  service time once and there was nothing behind it.
- `START-HERE.md` the one line to paste into a new chat, which fetches this
  file. Nine lines and deliberately never changes. Everything it used to carry
  is here instead.
- `MANUAL-ADMIN.md`, `MANUAL-CHEF.md`, `MANUAL-WAITER.md`,
  `MANUAL-HOUSEKEEPING.md`: one cheat sheet per role, what the screens are for
  rather than how to tap them. Writing them found three real holes, which is
  what they were half for.
