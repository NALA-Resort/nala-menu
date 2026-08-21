# Clean screen ETA upgrade

Agreed with the owner by voice, 21 Aug 2026. Nine decisions, all settled.
Split into two halves so no file has two writers. Read the whole thing before
starting your half: the two halves share one stored field.

---

## The shared field

The desk writes it, the cleans board reads it. Whoever builds first defines it.

    /bookings/<id>/prearrival/arriveApproved

A plain number, the hour on a 24 hour clock, 11 to 23. Absent when reception
has not approved a time. It sits BESIDE the guest's own `arriveSlot`, never
replacing it: the guest's answer is what they asked for, this is what
reception agreed to, and losing the difference loses the audit trail.

`arriveNote` is unchanged. It is where the guest writes "hoping to arrive at
11" and it is what reception reads before approving.

---

## Why this exists

"Before 2pm" on the guest form is not an arrival slot, it is a refusal with a
polite face. Two o'clock is the standing promise and the villas are worked to
it. Offering a guest 11am or midday as pickable options would read as an
invitation, and the resort would then be declining things it appeared to
offer.

So the early times are reception's to give, not the guest's to take. A guest
picks Before 2pm, explains in the note, reception decides, and if it is
approved the agreed hour is recorded. An early time on the cleans board is
therefore authoritative: a person agreed to it.

---

## Half one, for Claude Code: the desk

Files: `front-desk.html`, `rules.json`, `tests/fd_suite.py`.

The arrival time editor already offers the six guest slots. Add reception's
approved time as a separate control in the same editor: the hours 11am
through 11pm, on the hour, plus a clear option.

Rules: `arriveApproved` needs a write path for admin and staff roles only.
A guest holding a pre-arrival link must not be able to set it. Validate it
as a number between 11 and 23.

Tests: reception can approve a time; a guest cannot; the approved time and
the guest's slot coexist without either overwriting the other; clearing the
approved time leaves the slot intact.

Do not touch `cleaners.html`.

---

## Half two: the cleans board

Files: `cleaners.html`, `tests/cl_suite.py`.

The board already calls `fetchStays(todayKey())` at line 654, which populates
`PREARRIVAL_BY_VILLA` in `nala-shared.js` as a side effect. The ETA is
available with no extra reads.

### What the corner shows

Top right of the tile, the time and nothing else. No label, no words.

Precedence: the approved hour when there is one, otherwise the guest's slot.

The four middle slots render as `2pm`, `3pm`, `4pm`, `5pm`. The two
open ended ones carry a bound rather than a promise, sign first:

    before2  ->  <2pm
    after5   ->  >5pm

An approved hour renders as its own time, `11am` through `11pm`.

Nothing shows on a villa with no arrival today.

### Colour

Same grey as the strip and linen icons, `#55554F`, by default.

Orange, `--amberbar` / `#E8891A`, when the arrival is before 2pm: the
`before2` slot, or an approved hour of 13 or lower. This is the only case
that needs the cleaner to work faster than the standing promise, which is
the whole point of the colour.

Red from one hour before the time, and red beats orange. By then the message
is not "prioritise this", it is "they are nearly here". For `before2`
without an approved hour, treat the deadline as 2pm, so red from 1pm. For
`after5`, treat it as 5pm, so red from 4pm.

2pm and later stays grey until it goes red. The board already re-renders on
`setInterval` every 30 seconds at line 1403, so no new timer is needed.

### Sorting

In `render()`, line 803. Arrivals sort by ETA, earliest first, ahead of the
existing blocks.

The important part: a villa with an arrival and no stated ETA counts as 2pm.
An absent ETA is not unknown, it is the standing promise. So an unstated
arrival sorts alongside the ones that said 2pm, and a 4pm arrival correctly
falls BELOW every no-ETA arrival, because that guest asked for later.

Order: 11am, 1pm, then the 2pm block (stated and unstated together, equal,
falling back to villa number), then 3pm, 4pm, 5pm and beyond.

Villas with no arrival at all fall back to the current logic untouched:
departed with someone arriving, then departed, then the rest.

### Finished work still sinks

An ETA does not pin a villa to the top once the work is done. The board is a
work list and a ready villa is not work. A cleaned villa sinks as it does
today, keeping its ETA in the corner so anyone glancing at it can still see
when the guest lands.

### The corners

All three corners now carry something, and the ETA displaces the icons:

    top left      ETA
    top right     strip and linen icons
    bottom right  who-badge, the initials

Bottom left stays empty.

Note the icons and the badge are swapping sides. They were placed opposite
each other deliberately, and the icons are two small glyphs where the badge
is a filled circle, so check the narrow phone breakpoint: `.tile .who-badge`
at line 101 has its own small-screen rule and `.tile .task-icons` at line
251 does not. Report back if it reads cramped rather than quietly shipping it.

---

## House rules, both halves

`git fetch` before pushing. Publish with `/home/claude/publish.sh`, never
`push.py`. If `main` has moved, rebase onto it, never push over.

Run your own suite before publishing. `tests/run.py` exceeds the sandbox
command timeout, so run suites individually, and background `sweep_suite.py`
to a log: it takes well over 900 seconds and a `timeout 900` has killed it
partway before.

Reasoning goes in the commit message.

Known pre-existing failures on `main`, not yours: two in `cl_suite` about
pushed villas, two in `rules_test` about a waiter and internal notes, one in
`tally_suite` about a 16px input.
