# NALA Menu App — Code & Usability Audit

Working document for the four-part cleanup (Aug 2026). One section per page,
written before each rebuild. Companion to STYLEGUIDE.md: the styleguide says
what things must look like; this records what was found and what was changed.

---

## Part 1 · Res tally (tally.html)

**Job:** FOH glance-and-fix screen during prep and service. Phone, one hand,
interrupted constantly. Everything must be readable at arm's length and
tappable with a thumb.

### Code health findings

| # | Finding | Action |
|---|---------|--------|
| T1 | Pax picker written three times (room sheet 1–6, add-external 1–8, edit-external 1–8) — same code, drifted copies | Consolidated into one `paxPicker(max, get, set)` helper |
| T2 | Dining/terracotta/slate palette hardcoded ~14 times as raw hex + rgba across tiles, swatches, marks, sheet buttons — the classic "adjusted and rewritten" residue | Promoted to `:root` tokens (`--green/--terra/--slate` + tint/border variants); every rule now reads from one source |
| T3 | `.room` rule split across two blocks; stray empty comment gaps from earlier deletions | Merged and removed |
| T4 | Manual-status writes were optimistic with **no rollback**: if Firebase rejected a write, the screen kept showing the unsaved state until refresh. Combined-tables writes already rolled back — inconsistent | All manual writes now go through one `saveManual()` with the same rollback-and-rerender pattern as `saveCombined()` |
| T5 | External-cancel of a digital booking mutated shared state without failure handling | Same rollback treatment, including `cancelledExt` |
| T6 | `render()` was a 215-line monolith (tile ordering, tile painting, row collection, stats, bookings) | Tile ordering and tile painting lifted into named functions; stats computed in one clear pass |
| T7 | Icon constants scattered through the file | Grouped in one block |
| T8 | `fetchRoomGuests` issues 14 parallel GETs per load (a fortnight's look-back). Parallel, so wall-time is one round-trip; heaviest thing on the page but correct and simple | **Left as is** — noted for future caching if load feels slow on resort wifi |
| T9 | Select-multiple writes one PUT per room rather than a single multi-key PATCH | **Left as is** — per-key writes match the security rules exactly; batching saves little at 17 rooms |

### Usability findings

| # | Finding | Action |
|---|---------|--------|
| T10 | Notes bubble (💬) tap target was 26 px — well under the 44 px finger minimum; easy to miss mid-service | Invisible hit area extended to ~42 px |
| T11 | Pax circles 38 px | Bumped to 42 px |
| T12 | Date arrows 34×32 px (shared control) | Bumped to 38×34 px in nala-ui.css — all pages benefit |
| T13 | Failed save only showed a 6-second banner while the screen kept the phantom state (see T4) | Rollback makes the screen tell the truth; banner explains why |
| T14 | Affordance confusion (info boxed like buttons), three date formats, header drift | Fixed in the standardisation pass that preceded this audit |
| T15 | Full-page reload as Refresh | **Kept deliberately** — on an ops tool, dumb-and-reliable beats clever |

### Explicitly protected
Guest page, Firebase paths, identity model, noon cutoff, all write shapes
(`/manual`, `/combined` records unchanged byte-for-byte).

---

## Part 2 · Res print (list.html)

**Job:** the printed A4 dinner service sheet. Paper first: write-in table
columns, checkout warnings, dietary flags a chef can trust at a glance.

### Code health findings

| # | Finding | Action |
|---|---------|--------|
| L1 | Three identical yyyy-mm-dd formatters in one file (`dkey`, `key`, `depDateKey`) | One `dkey`, in the new shared file |
| L2 | Whole helper layer (`dkey`, `parseDepDate`, `tidyPhone`, `ord`, `fetchRoomGuests`, `resolveRoomGuests`, `menuConflicts`, `dietHTML`, the entire date-nav block) copy-pasted across tally / res print / hc print, each copy drifting | **New `nala-shared.js`** now owns one canonical copy; res print converted, hc print in Part 3, res tally retrofitted in Part 4 |
| L3 | **Latent Safari bug:** publish timestamp parsed with raw `new Date()`. The chef's Python push writes 6-digit fractional seconds, which Safari rejects — so on iPhones the menu could read as unpublished and **dietary conflict flags silently never fired on this sheet**. Tally had the `parseISO` fix; the prints never got it | Shared `parseISO` used everywhere; regression test feeds a 6-digit timestamp and asserts the flag still raises |
| L4 | Dead code: `stamp()` targeting a `#stamp` element that didn't exist, orphaned `.bar`/`.stamp`/`.counts b`/`.hint`/`.key` CSS, unused `dining`/`notDining` arrays, unused `groupMates` | Removed — except the stamp, which was a good idea half-finished (see L6) |
| L5 | External table-count keyed on `r.key` which was never set, silently falling back to `Math.random()` | Externals now carry their real keys |
| L6 | The print stamp: a paper sheet that gets reprinted through the evening needs to say which copy is current | Completed: quiet "Printed 11/8/2026 7:07pm" line above the footer, on screen and on paper |

### Usability findings
Already sound: write-in columns ruled for pen, blank rows padded to 21,
checkout-tomorrow in red, conflict rows tinted with print-color-adjust,
group boxing matching the tally's rings, vacant rooms kept as labelled
write-in space. No layout changes made; 533 lines became 388.

### Verified
22-check suite: full row semantics (conflict + flag + pre-menu, declined
tint, silent-guest dash, vacant, group pair, external sort and cancellation,
phone tidy-up, checkout red), stats maths, blank-row padding, stamp, screen
vs print visibility, off-today date handling — plus the Safari-fraction
regression test. All passing; A4 PDF generated for visual check.

---

## Part 3 · HC print (housekeeping.html)

**Job:** the printed A4 morning housekeeping run sheet — who cleans, who
services, tick boxes for done and inspection, manager write-in strips —
plus on-screen it mirrors the cleaners' live progress marks.

### Code health findings

| # | Finding | Action |
|---|---------|--------|
| H1 | Cloned wholesale from the dinner sheet and never pruned: ~45 lines of CSS with no matching markup here (dinner/breakfast write-in columns, Yes/No colours, conflict flags, checkout reds, pre-menu tags, group boxing, blank-row padding) | All removed |
| H2 | Same triple-copied helper layer as the other pages (three date formatters again, `ord`, `parseDepDate`, `fetchRoomGuests`, date-nav block) | Now from nala-shared.js |
| H3 | `stayHTML` — 14 lines never called on this page (the sheet shows Arrival and Departs as separate columns) | Removed with its orphaned `.checkout` style |
| H4 | `resolveRoomGuestsHK` looks like a duplicate of the shared resolver but is **deliberately different**: it keeps guests departing today, because they are the cleans | **Kept local**, comment retained — the audit records it so nobody "deduplicates" it later |
| H5 | Cleaner timestamps parsed with raw `new Date()` — currently safe (the cleaners app writes clean ISO) but the same Safari trap as Part 3's flag bug | Defensive `parseISO` |
| H6 | Error message spanned 8 columns of a 7-column table | colspan fixed |
| H7 | Two different reds on paper (#8a1f1f vs #A8321E) | One red |

### Usability
The sheet's design was already right for its job. One addition, mirroring
res print: the **Printed date-time stamp**, because this sheet gets
reprinted mid-morning once cleaner marks start landing, and paper copies
need to say which is current.

### Verified
17-check suite, all passing: stats and the verify counter, row ordering
(cleans → services → verify → vacant), cleaner marks (done tick with time,
At-breakfast subtag and its clearing, Departed), stale-departure handling,
vacant rows, the 6-digit-fraction timestamp regression, screen vs print
visibility including the manager strips, tomorrow's sheet classifying a
tomorrow-departure as Clean, and the failure message. 372 lines became 262.

---

## Part 4 · HC tally (cleaners.html) + res tally retrofit

**Job:** the cleaners' live board. Least technical users in the building,
working with gloves on. Big tiles, three actions, confirmation on every
write, self-refreshing.

### Code health findings

| # | Finding | Action |
|---|---------|--------|
| K1 | The housekeeping resolver was duplicated a **second** time here — the deliberate variant now had two drifting copies of its own | `resolveRoomGuestsHK` moved into nala-shared.js with its do-not-merge warning; both HC pages use the one copy |
| K2 | `roomRecord` (staff-override-beats-guest merge) copy-pasted identically across res print, HC print and HC tally | One shared `roomRecord`; all three converted |
| K3 | The clean/service/verify classification — the housekeeping business rule — written out twice | One shared `hkClassify`; a rule change now lands on the screen and the paper simultaneously |
| K4 | This page's `parseDepDate` had an ISO branch the others lacked; the others parsed ISO departure dates through the UTC parser and were correct **only because Queensland sits east of Greenwich** | Shared `parseDepDate` gained the explicit local-date ISO branch — every page now timezone-proof |
| K5 | Its `fetchRoomGuests` was a clumsier double-loop rewrite of the same fortnight look-back | Shared version |
| K6 | Cleaner timestamps through raw `new Date()` | `parseISO`, as elsewhere |
| K7 | Rejection message told cleaners "the security rules need the hk path added" — stale advice from before the rules catch-all, and useless to a cleaner | Now: "The change was not allowed - tell the manager." |
| K8 | Date re-rendered inside every render tick despite never changing | Set once at startup |

### Usability
Already the best-designed page for its audience: whole-tile tap targets,
full-width buttons, confirm steps on every write, elapsed breakfast
minutes, optimistic updates with rollback. No changes needed.

### Res tally retrofit (closing the loop)
Res tally's private copies of the date block, look-back, conflict and
dietary helpers replaced with nala-shared.js; its 34-check suite re-run
in full. `roomState` stays local — it returns source/override detail the
sheet UI needs, a different job from the shared `roomRecord`.

### Verified
21-check cleaners suite (tiles, counts, sheet flows per room kind, done /
breakfast / departed writes with PATCH bodies, rejection rollback and
message, undo, the menu gate for management vs housekeeping logins) — then
**all four suites re-run against shared v2: 94 checks, zero failures.**

---

## Close-out

Four pages, one shared stylesheet, one shared logic file, one styleguide,
this audit. Every helper that existed in multiple drifting copies now has
exactly one home; the two deliberate variants are documented at that home.
Line counts: tally 1274→1145, res print 533→367, HC print 372→220,
HC tally 387→320 — about 500 lines gone with zero behaviour lost, one
Safari bug fixed, rollbacks made universal, and every claim above backed
by a passing check.

---

## Post-audit regressions (12 Aug, recorded for honesty)

1. **Self-referential palette tokens.** Part 1's cleanup script inserted the
   `:root` colour definitions and then ran its hex→var replacement over the
   whole file, rewriting the definitions it had just written into
   `--green:var(--green)`. Every state colour on res tally was invalid from
   Part 1 until today: tile tints, sheet buttons, multi-select buttons
   (whose white labels on cream read as a blank, broken bar). The suites
   validated class names, never computed colours, so 35 checks stayed green
   around a colourless page. Fixed; the tally suite now asserts computed
   background colours for tiles, sheet buttons and the select bar, plus the
   bar's fixed-bottom geometry.
2. **Nav script ordered before its markup.** Two header restructures moved
   the menu button below the script that wires it, silently killing the
   menu (and on hc tally, the management gate). Fixed — scripts now sit
   after the markup on all four pages, and suites tap the menu open.

Lesson applied everywhere: verification must assert rendered outcomes
(pixels, geometry, interaction), not markup shape.

## Dead sign-in button (12 Aug, found by Ben on his phone)

Symptom: sign-in form appears, Sign in does nothing.

Cause: `go()` disabled the button and then called
`firebase.auth().signInWithEmailAndPassword(...)`. If auth-compat had not
arrived — a flaky connection is enough — that call threw before the promise
existed, so nothing re-enabled the button and no message was written. A
silent grey button, indistinguishable from a hung app. The same shape had
been there since auth.js v1; the v2 work did not introduce it and did not
catch it either, because every test stubbed a working SDK.

Fix (v3): check what each moment actually needs — a usable session layer at
load, a usable sign-in method at the tap — and never let the button end a
tap disabled. If the service is missing at load, say so and offer Reload
rather than presenting a form that cannot work.

Lesson: any control that disables itself pending an async call must
re-enable on every path out, including the throw. Two suite checks now
cover both failure shapes.

### Follow-on break, same afternoon (v3 → v4)

The v3 guard called `firebase.auth()` to test whether the SDK was usable —
before `initializeApp`. The real compat SDK throws "No Firebase App
'[DEFAULT]' has been created" when you do that, so the guard caught its own
exception, concluded the SDK was missing, and locked every staff page behind
a Reload panel that could never succeed. Shipped to Ben's phone.

It passed every test because the mocked SDK returned an auth object whether
or not initializeApp had run. The mock was more forgiving than the thing it
mocked, so the suites were confirming a fiction.

v4: check the SDK is PRESENT without calling it, initialise, then check it
WORKS. All four suite mocks now throw before initializeApp exactly as the
real SDK does; the v3 file fails those suites outright.

Lesson: a mock that cannot fail the way the real dependency fails is not a
test, it is a rehearsal. Every guard added to auth.js must be exercised
against a mock that reproduces the real error, not a friendlier one.

### Rolled back (v5 = the original file)

v4 left Ben on a blank screen. Rather than attempt a third forward fix on a
live system, auth.js was restored byte-for-byte to the version from before
any of today's auth work and republished as ?v=5 on all seven pages.

Everything the auth work was trying to solve — the sign-in form flashing on
page changes, the silently dead Sign in button — is UNFIXED and back in the
backlog. The two suite checks written for it are parked with it.

Three attempts, three breaks, each one shipped on green tests. The tests were
green because the mock could not fail the way Firebase fails. Nothing should
be changed in auth.js again until there is a way to exercise it against real
Firebase, or at minimum a mock built from the SDK's actual error paths.

### The dead button, actually fixed (auth v6)

Root cause, confirmed by reproduction: when auth-compat does not arrive,
`firebase` still exists but `firebase.auth` does not. The wiring line threw,
which killed the rest of auth.js — but the 500ms timer had already been set,
so the sign-in form appeared anyway. Tapping Sign in then called the same
missing method and threw again, leaving the button disabled and silent.
This has been the behaviour since v1; nothing today caused it.

v6 changes two things and touches nothing else on the load path:
the wiring is wrapped so a throw cannot kill the file and can be re-run, and
the tap handler, if the sign-in method is missing, fetches the SDK scripts
and retries once — then either signs in or re-enables the button with a
message. Diffed against the live file to confirm initializeApp, the overlay
and the 500ms timer are byte-identical.

tests/auth_suite.py covers three worlds: SDK recovers on tap, SDK never
recovers, SDK healthy. Run against the previous file it fails 5 of 6, which
is the check the earlier attempts never had.
