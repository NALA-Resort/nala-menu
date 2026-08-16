# Morning of 17 Aug

Overnight session. Four commits, all suites green throughout. Two things need
you before anything else moves, both at the bottom.

Baseline before I started: 393 assertions. Now 421.

| Suite | Before | Now |
|---|---|---|
| tally | 85 | 87 |
| list | 42 | 42 |
| hk | 22 | 22 |
| cleans | 176 | 193 |
| auth | 30 | 30 |
| worker | 38 | 47 |

---

## What shipped

**`847f046` The Worker.** Reception's Mews notes no longer reach
`/bookings/<id>/pms`, which anyone holding a booking id can read. They are
written as explicit nulls rather than simply omitted, so bookings synced before
tonight lose them on their next event instead of only new ones being clean. A
space name the app does not recognise is refused rather than written to a
`/stays` key no board reads, and the reply names the rejected value so it
surfaces in the Zap history. Dead `staleVilla` removed. `cleared` now counts
what was actually deleted rather than reporting the previous booking's night
count regardless.

**`8236405` Precedence and the moved guest.** Mews now wins name, dates, villa,
phone and party size above `responses`. Measured before and after on a stay
Mews shortened: the villa classified as a service on its departure day, and now
classifies as a clean. A guest moved between villas is cleared out of the one
they left, and a response they wrote from the old villa no longer holds it
open. The vacant override warns first on a Mews villa, is stamped with the
booking version it was decided against, and drops when Mews next changes that
booking. `nala-shared.js` at v19 across all six pages, demos rebuilt.

**`9d94400` Party size.** Mews knows how many people are booked in and the app
was storing it and showing it nowhere. It now appears beside the name on the
villa sheet.

Two mockups are in the repo for you to look at: `mock-vacant.png` is the
warning panel, `mock-adults.png` is the villa sheet with the party size.

---

## Questions I answered myself

**Should the warning block a vacant, or only warn?** Warn. Reception can see a
villa and Mews cannot, so the person standing in the building is the better
authority. Blocking would make the board wrong and unfixable.

**How long does the override last?** Until Mews next changes that booking. It
is stamped with the PMS version it was decided against. Once Mews sends a newer
one, the decision was about a different state of the world.

**Should the party size fill in the covers picker?** No. Covers is how many are
eating tonight and belongs to the kitchen; party size is how many are staying
and belongs to Mews. They are often the same. Defaulting one to the other would
inflate the kitchen's count for every villa that has not replied, and the error
would be invisible.

**Move the notes fields behind auth, or drop them?** Drop. Moving them needs a
rules change, which only you can paste, so it would have stalled. Nothing reads
them: stage 6 writes notes TO Mews from the app, it never reads them back. If a
later stage needs them, give them a node with an auth rule and do the rules
first.

**How do you match a moved guest across two villas?** Phone on the last nine
digits, because Mews holds `+61400000000` and a link carries `0400000000` and
those are one person. Name as a fallback when neither side has a phone. Only
guest written entries are ever dropped, so two real bookings that share a phone
both survive.

**What counts as a valid villa?** An integer 1 to 17, matching `ROOMS`. Mews
sends whatever the space is called and nobody here controls that mapping.

**Should the mockup have shipped as it first rendered?** No. It printed the
date as `2026-08-19` against the styleguide's single date format, and said "the
PMS" where every other word on screen says Mews. Both fixed before publishing.

**Did the print chat collide with me?** No. My first collision warning was
false: I was comparing against my own stale local clone. `publish.sh` now
records what I last pushed and compares against that, so a warning means
another chat rather than me.

---

## Questions that need you

**1. WITHDRAWN. Do not paste the rules.** I asked for a `prearrival` rule
requiring `pms` to exist first. That blocks the guest-first case the design
depends on: the link goes at seven days, Mews arrives later, so the guest
writes before `pms` exists. Reverted, `rules.json` is back to what is live, and
there is nothing to paste. A `.validate` bounding shape and size is still worth
adding, and cannot be tested from here. See `GUEST-DATA.md`.

**2. RESOLVED in conversation.** Cancellations can be made to fire from
Zapier, which removes what was the largest open risk. Original note follows.

**Cancellations had never been seen to fire.** Handled correctly in the
Worker and covered by tests, but the Zap that would deliver one filters on
reservations *starting* in a window, and a cancelled reservation may drop out
of that filter entirely. If it never fires, a cancelled guest keeps their villa
and prints a registration card. Cancel a test booking in Mews and watch the Zap
history. This is the most expensive unknown left and it needs a real booking.

---

## Still open, none of it blocked on me

Zapier work, which I cannot reach: villa 3's missing phone mapping, and
widening the lookahead. CORRECTED: the lookahead does NOT block stage 3. The
pre-arrival link carries the guest's name and dates for display, so the page
works before Mews has the booking. It is a boards question only.

No backfill is needed. A few bookings get added by hand and every new one
arrives through Mews.

Then making vacant the default villa state, and rotating the four credentials.

Stage 3 still needs the picklist answer. Front Desk Arrival is newly specified
in `GUEST-DATA.md` and is ready to build.

The full reasoning for all of it is in `MEWS-AUDIT.md`, including the section
on the old guest written path and the new PMS path both running, which is the
real content of stage 4.

## One thing I found and did not fix

`tally.html` lines 391 to 393 use en dashes as loading placeholders for the
three stat numbers. The styleguide bans them in prose. As a placeholder glyph
it is arguably a different thing, it is pre-existing, and changing it is a
visual decision rather than a correction, so I left it. Backlog item 9 already
covers the em dash in `list.html`, which the suite asserts on.
