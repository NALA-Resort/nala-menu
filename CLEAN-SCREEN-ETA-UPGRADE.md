# Clean screen ETA upgrade

Agreed with the owner by voice, 21 Aug 2026. This file replaces an earlier
draft of the same name, which contradicted itself about which corner the ETA
sits in and predated several decisions. Nothing in that draft survives except
by being restated here. If any statement in this file conflicts with an
earlier one, this file wins.

Three jobs. They touch different files, so they can be built in any order and
by different sessions, but no file may have two writers at once.

---

## The idea in one paragraph

Two o'clock is the resort's standing promise: every villa is worked to be
ready by 2pm, and a guest who says nothing is assumed to arrive then. The
cleans board currently knows nothing about arrival times, so a cleaner cannot
tell an 11am arrival from a 5pm one. This puts the time on the tile, colours
it when it demands attention, and sorts the arrivals by it.

---

## The shared field

The desk writes it, the cleans board reads it, the Worker reads it.

    /bookings/<id>/prearrival/arriveApproved

A plain number: the hour on a 24 hour clock, 11 to 23. Absent when reception
has not approved a time.

It sits BESIDE the guest's own `arriveSlot`, never replacing it. The guest's
answer is what they asked for; this is what reception agreed to. Collapsing
the two loses the only record of who decided.

`arriveNote` is unchanged. It is where the guest writes "hoping to arrive at
11", and it is what reception reads before approving.

### Why the early hours are not on the guest form

"Before 2pm" is not an arrival slot. It is a refusal with a polite face.
Offering 11am or midday as pickable options would read as an invitation, and
the resort would then be declining what it appeared to offer. So the early
times are reception's to give, not the guest's to take: the guest asks in the
note, reception decides, and the agreed hour is recorded. An early time on
the board is therefore authoritative. A person agreed to it.

---

## Job 1: the desk

Files: `front-desk.html`, `rules.json`, `tests/fd_suite.py`.

The arrival time editor already offers the six guest slots. Add reception's
approved time as a separate control in the same editor: the hours 11am
through 11pm, on the hour, plus a clear option.

Reception may set it freely. Specifically:

- It does NOT require a completed pre-arrival form. A guest who telephones is
  as valid as one who used the link.
- It does NOT require the villa's current guest to have departed. Approving
  an 11am arrival into a villa somebody is still sleeping in is allowed, and
  the resulting red tile is the prompt to chase the departure. Do not add a
  guard for this. The owner considered it and declined it.
- It may be any hour in range regardless of what the guest picked, so a guest
  who chose "Around 4pm" and later rang to say half three can be set to 15.

Rules: `arriveApproved` needs a write path for admin and staff roles only. A
guest holding a pre-arrival link must not be able to set it. Validate as a
number between 11 and 23 inclusive.

Tests: reception can approve a time; a guest cannot; the approved time and
the guest's slot coexist without either overwriting the other; clearing the
approved time leaves the slot intact; a value outside 11 to 23 is refused.

Do not touch `cleaners.html`.

---

## Job 2: the cleans board

Files: `cleaners.html`, `tests/cl_suite.py`.

### What the board already has

`load()` at line 642 calls `fetchStays(todayKey())`, which populates
`PREARRIVAL_BY_VILLA` in `nala-shared.js` as a side effect. That map is the
reservation's whole prearrival record per villa, so BOTH `arriveSlot` and the
new `arriveApproved` arrive with it. No new fetch is needed.

`fetchStays` is uncached and re-reads on every call, and line 1409 polls
`load()` every twenty seconds while no villa sheet is open. So a time
approved at the desk reaches a cleaner's board within twenty seconds without
a refresh. Do not add a listener or a timer.

### The effective ETA

Every villa with an arrival today has one, resolved in this order:

1. `arriveApproved` if present: that hour.
2. Otherwise the guest's `arriveSlot` mapped to an hour:
   `before2` -> 14, `14` -> 14, `15` -> 15, `16` -> 16, `17` -> 17,
   `after5` -> 17.
3. Otherwise 14.

Step 3 is the important one and it is not a fallback for missing data. **Two
o'clock is the default for every arrival, whatever its source.** A booking
with no pre-arrival form, a form left unanswered, and a manager's manual
"Arriving tonight" tick are all 2pm arrivals. An absent ETA is not an unknown
one: it is the standing promise.

Note `before2` and `after5` resolve to 14 and 17 for ordering and for the red
countdown, while displaying differently. See below.

### What counts as an arrival

Exactly what `arrivingNow(row, h)` at line 792 already decides: the manager's
override if set, otherwise the booking. Do not introduce a second definition.
A villa where `arrivingNow` is false shows no ETA and is not sorted by one.

### What the corner shows

**Top left of the tile.** Time only. No label, no words, no icon.

- An approved hour renders as itself: `11am`, `12pm`, `1pm` ... `11pm`.
- A guest slot renders `2pm`, `3pm`, `4pm`, `5pm` for the four middle ones.
- The two open ended slots carry a bound rather than a promise, sign first:
  `before2` displays `<2pm`, `after5` displays `>5pm`.
- A villa with no arrival shows nothing at all. Most cleans are this.

An approved hour always wins the display, including over `before2`: a guest
who asked "before 2pm" and was approved for 11 shows `11am`, not `<2pm`.

### Colour

Default: the same grey as the strip and linen icons, `#55554F`.

**Orange** (`--amberbar`, `#E8891A`) when the effective ETA is before 2pm,
which means an approved hour of 13 or lower, or the `before2` slot with no
approved hour. Orange is an instruction: this villa has to be finished ahead
of the standing promise. Nothing at 2pm or later is ever orange, because 2pm
needs no special handling.

**Red** from one hour before the effective ETA, and red beats orange. By then
the message is not "prioritise this" but "they are nearly here". A `before2`
villa with no approved hour goes red at 1pm; an `after5` villa at 4pm.

**Once the villa is done, the ETA goes grey and stays grey**, regardless of
the hour. Colour here is an instruction and a finished villa has no
instruction left. The time itself remains visible so anyone glancing at the
tile can still see when that guest lands. It fades with the rest of the tile
under the existing `.tile.done` rule.

No new timer. Line 1403 already re-renders every thirty seconds.

### Sorting

In `render()`, line 803.

**The block order does not change.** `korder` stays as it is: services above
cleans. A service is attempted while the guest is out and that window shuts
when they wander back, so an arrival must not displace one. The owner was
asked directly and chose this.

The ETA orders villas WITHIN the existing blocks, as a new tie-break above
the current `sub()`: among cleans, those with an arrival sort by effective
ETA, earliest first.

Because every arrival resolves to an hour, there is no separate "no ETA"
group. An unstated arrival is 2pm and sorts among the stated 2pms; between
two villas on the same hour there is no priority at all and they fall back to
villa number, exactly as the board does everywhere else. The only difference
between them is cosmetic: one shows `2pm` in the corner and the other shows
nothing.

A 4pm arrival therefore sorts BELOW every villa that never stated a time.
That is correct and deliberate: that guest asked for later.

**Finished work still sinks.** An ETA does not pin a villa to the top once it
is done. `rank()` already sinks a done villa and that must not change: the
board is a work list and a ready villa is not work.

Villas with no arrival at all keep today's behaviour untouched.

### The corners

    top left      ETA
    top right     strip and linen icons
    bottom right  who-badge, the initials
    bottom left   empty

The icons and the badge swap sides. Both already have narrow-screen rules
(`.tile .who-badge` line 101, `.tile .task-icons` line 103), so both need
their positions updated in the small breakpoint as well as the main one.

Check the narrow phone tile after the swap: the icons are two small glyphs
where the badge is a single filled circle, so the right edge will sit
differently. Report back if it reads cramped rather than quietly adjusting
the design.

---

## Job 3: arriving-soon notification

Files: `worker/wrangler.jsonc`, `worker/mews-sync.js`, `worker/test.mjs`.

Build this last, and only after Job 1 and Job 2 are published: it reads the
field Job 1 writes and mirrors the logic Job 2 renders.

When a villa crosses the one hour mark and turns red, and **no housekeeper
has claimed it**, send a notification. A villa somebody is already working on
stays quiet: the point is to catch the case where a guest is close and nobody
is on it.

This must be server side. Every existing notification is fired page side by
`notifyPush()` in `nala-shared.js` line 1155, because every existing event is
triggered by somebody tapping something. This one is triggered by nothing
happening, so there is no tap to hang it on, and a page-side version would
fire once per open device or not at all.

The change is additive and restructures nothing:

- Add a cron trigger to `worker/wrangler.jsonc`. Five minutes is fine.
- Add a `scheduled()` handler to `worker/mews-sync.js`. The existing fetch
  handler and everything Zapier posts to it are untouched.
- On each wake: read today's stays and the prearrival records, compute the
  same effective ETA as Job 2, and for each arriving villa now inside its red
  hour that is neither claimed nor done, send once.
- Send once. A marker in the database naming the villa and the date, written
  before the send and checked first, in the manner of `announceMenu()` at
  line 1189.

No evening cutoff is needed. Management resolves the board at the end of
every day: a villa is either marked cleaned or falls through to pushed, and
either way it has sunk and is no longer unclaimed work. A late red never
finds anything to announce.

The same cron unblocks the parked sync heartbeat, which has been waiting on
exactly this. Do not build the heartbeat here, but do not design the trigger
so it cannot host one later.

---

## Decisions taken and closed

Restated so they are not reopened:

- Guests never see hours earlier than 2pm. Reception approves them.
- No guard on approving a time before the current guest has departed.
- Reception may approve a time with no pre-arrival form at all.
- 2pm is the default for every arrival, including a manual tick.
- A stated 2pm and a silent one rank equally. Only the icon differs.
- Services stay above ETA arrivals.
- A finished villa sinks and its ETA goes grey.
- A changed ETA is shown silently. No flag, no highlight.
- No evening cutoff for red.
- ETA top left, icons top right, initials bottom right.

---

## House rules

`git fetch` before pushing. Publish with `/home/claude/publish.sh`, passing
the message and the file list as arguments: it commits and pushes for you,
and it ends in `git reset --hard`, so a file you changed but did not pass is
discarded. Never call `push.py` directly. If `main` has moved, rebase onto
it, never push over.

Run your own suite before publishing. `tests/run.py` exceeds the sandbox
command timeout, so run suites individually, and background `sweep_suite.py`
to a log: it takes well over 900 seconds and a `timeout 900` has killed it
partway before.

Reasoning goes in the commit message, not in a comment.

If Job 2 ships before Job 1, `arriveApproved` simply does not exist yet and
every tile falls back to its guest slot. That is correct behaviour, not a
bug.

Known pre-existing failures on `main`, not yours: two in `cl_suite` about
pushed villas, two in `rules_test` about a waiter and internal notes, one in
`tally_suite` about a 16px input.
