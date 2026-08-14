# NALA menu app — style guide

One rulebook, three tiers. Every page declares its tier on the body tag and
loads `nala-ui.css`, which owns all shared controls. Page CSS may only style
page content, never controls.

## Tiers

**tier-app** — the live tools: tally.html (res tally), cleaners.html (hc tally).
Job: fast operational reading. Cream/ink palette, big tap targets, colour used
only to encode state (green dining/done, amber breakfast, red attention,
dashed = unknown/awaiting).

**tier-print** — the sheets: list.html (res print), housekeeping.html (hc print).
Job: paper clarity. Black on white, minimum ink, no decoration, nothing
interactive appears in @media print. Red permitted only for "needs attention"
chips (prints grey, still legible).

**tier-guest** — index.html, welcome.html.
Job: brand. Styling matches nalaresort.com.au (palette/type to be lifted from
the real site — pending screenshots). Staff controls never appear here.

## Affordance — how you know what's tappable

- **Rectangle with border or solid fill = a button.** Nothing else may use
  that dress. Primary solid ink, secondary outlined.
- **Tinted rounded pill = status** (e.g. MENU NOT PUBLISHED). Never tappable.
- **Plain typography = information.** Stats are a bare number over a small
  label (`.stats`/`.stat`), never boxed. Attention turns the number red,
  not the frame.
- **Do not stack a fact under another fact.** Putting B on its own line
  beneath A says B is subordinate to A, which is usually a claim nobody
  checked, and it costs a row of white space. The table make-up sits on the
  same line as the table count because the make-up is the actual instruction
  to whoever sets the room; the count is only its checksum.
- Room tiles are the one exception: a bordered grid that is tappable on the
  app tier — the grid itself is the control surface.

## Header — one row on every staff page

`[Today] [‹] Wed 12th Aug [›] ............ [☰]`

- One `.daterow`, in flow, nothing floating or sticky. All controls the
  same 36px height.
- **Today is always present**, disabled (dimmed) when already viewing today.
- **Date format: Wd Dth Mon** (e.g. Wed 12th Aug). Short weekday, ordinal
  day, short month, no year on screen. Paper carries the full date in the
  printed stamp.
- The menu sits at the row's right end (`margin-left:auto`); dropdown opens
  beneath it. Gated on hc tally. hc tally shows date + menu only (locked
  to today).
- Page identity is not shown on screen; print sheets carry `.printkick`
  (NALA · page name) on paper only.
- `.stats` follows the row, unboxed as before.

Floating corner menus remain banned: a fixed element pinned over in-flow
content is guaranteed to collide with something at some width.

**One date format everywhere: Weekday D Mon YYYY** (e.g. Wednesday 12 Aug
2026), uppercased by CSS. No ordinals, no long months, no year-less dates.

## Controls — identical on every staff page

- **Nav menu**: three-bar button, fixed top right. Dropdown lists the other
  staff screens by their working names: Reservations (tally.html),
  Reservations Sheet (list.html), Cleans (cleaners.html), Clean sheet
  (housekeeping.html), always in that order — live board then its sheet,
  reservations before cleans. Labels never wrap; the dropdown widens to
  its longest label. On hc tally the menu exists but only renders for logins whose
  email does not start with "housekeeping".
- **Floating footer** (`.foot`): sticky at the bottom, holds the page's
  actions. Primary action solid, secondary outlined. App tier: cream with
  rule border. Print tier: white. Hidden when printing. The row sits hard
  against the bottom of the screen, so the first button's bottom-left and
  the last button's bottom-right carry an 8px radius (matching the nav
  button); every other corner in the row stays square.
- **Sign-in**: owned by auth.js on every staff page; guest pages never see it.

## Tokens (defined once in nala-ui.css)

Cream #F9F7F4 · Ink #1C1C1A · Mid #999990 · Rule #E0E0DA · Red #A8321E
UI font: Helvetica/Arial. Content serif (app tier only): Georgia.
Labels: 10-11px, uppercase, letterspaced .12-.15em.

**Type scale — pick from this list, never by eye: 8 · 11 · 15 · 20 · 27.**
Each step is about a third up from the last. Two things that form one
statement sit on adjacent steps; skipping steps is what makes one of them
shout. 27 is reserved for a single headline number.

**Never use em dashes.** Not in copy, not in titles, not in comments. A
hyphen in a sentence, a middot for a separator. This is a standing rule, not
a preference to be re-litigated.

**Name what a number counts.** "2×3" and "3×2" look like the same sum and
the reader has to already know which side is which. Write the make-up as
"3 twos · 1 three" — a wording that can be said out loud and cannot be
read backwards. Both dining pages state the make-up the same way, on one
line — sentence case, normal letter-spacing, `nowrap` — because a wrapped
statistic reads as two facts.

**Stay dates are one line: `Tue 11-Fri 14`.** Weekday and bare day number,
no ordinal, no "to", month omitted because we know it. A range that wraps
doubles the height of the row it sits in.

## Printed sheets — repeating header

Everything above the table repeats on every printed page: page name, date,
stats, and the manager strip where there is one. Browsers only reliably
repeat a table header group, so the block is cloned into a `.printhead` row
inside `<thead>` as soon as the sheet has data — NOT on `beforeprint`, which
iOS Safari does not reliably fire — and the on-screen original is hidden on
paper. The clone drops the nav menu, strips ids, and is marked `.printclone`
so tests and scripts can tell it from the original. Tables print with
`border-collapse:collapse`, which Safari requires before it will repeat a
header group at all.

## Wording

Guests stay in **villas**, not rooms. Every visible label says villa. The word
"room" survives only in code: database paths (`roomguests/<date>/<room>`),
variables, ids and CSS class names, where renaming it would orphan bookings
already stored. In a list where every line is a villa, the word is dropped
entirely and the number leads: **3 - Mark Whitfield**.

## Setting the job by hand

A manager can set a villa's job for the day from the Cleans board: **To be
cleaned** or **To be serviced**, or hand it back to the booking dates. It is
stored at `/hk/<date>/<villa>/kind`, beside the breakfast and done marks, so
it expires with the day.

The rule lives in `hkClassify()` in nala-shared.js, so the board and the
printed sheet agree by construction rather than by remembering to change two
places. A hand-set job beats whatever the dates imply.

Three options: **To be cleaned**, **To be serviced**, **Mark as vacant**.
Each goes through a confirm screen, the same two-step every other action on
this page uses. A vacant villa drops to 22% opacity and offers no cleaning
actions, only the job controls - it is not work, and must not compete with
the villas that are.

The revert button tells the truth about what it will do: **Use booking
dates** only when the dates actually decide a job, otherwise **Back to
unknown**. A villa the dates cannot place says Unknown, not "occupancy not
confirmed".

Management only. The controls reuse the same login check that hides the nav
menu from the housekeeping user - one gate, not two. Note this is a display
gate: the database rules still allow any signed-in user to write the field.

## Clean up

After a run of edits to a page, stop and read the whole block, not the lines
you changed. Every time this has been skipped the page has accumulated the
same four faults: two rules fighting each other for the same selector, a rule
whose subject no longer exists, a comment describing behaviour the code no
longer has, and a container quietly costing layout width. Patching around
those is what makes a page get worse with every edit. Fix them at the source
and re-measure; do not add a rule to counteract another rule.

## Wording

Guests stay in **villas**, not rooms. Every visible label says villa. The word
"room" survives only in code: database paths (`roomguests/<date>/<room>`),
variables, ids and CSS class names, where renaming it would orphan bookings
already stored. In a list where every line is a villa, the word is dropped
entirely and the number leads: **3 - Mark Whitfield**.

## Setting the job by hand

A manager can set a villa's job for the day from the Cleans board: **To be
cleaned** or **To be serviced**, or hand it back to the booking dates. It is
stored at `/hk/<date>/<villa>/kind`, beside the breakfast and done marks, so
it expires with the day.

The rule lives in `hkClassify()` in nala-shared.js, so the board and the
printed sheet agree by construction rather than by remembering to change two
places. A hand-set job beats whatever the dates imply.

Three options: **To be cleaned**, **To be serviced**, **Mark as vacant**.
Each goes through a confirm screen, the same two-step every other action on
this page uses. A vacant villa drops to 22% opacity and offers no cleaning
actions, only the job controls - it is not work, and must not compete with
the villas that are.

The revert button tells the truth about what it will do: **Use booking
dates** only when the dates actually decide a job, otherwise **Back to
unknown**. A villa the dates cannot place says Unknown, not "occupancy not
confirmed".

Management only. The controls reuse the same login check that hides the nav
menu from the housekeeping user - one gate, not two. Note this is a display
gate: the database rules still allow any signed-in user to write the field.

## Clean up

Every piece of work ends with a clean-up pass over the whole block that was
touched, not just the lines that were edited. Look for:

- **rules that fight each other** - two selectors setting the same property,
  usually one original and one added later
- **dead rules** - styling for markup that no longer exists
- **comments that describe behaviour the code no longer has**
- **containers that cost layout width** - padding or borders on a wrapper make
  everything inside narrower, which shows up later as mysterious compression
  in one place and not another
- **shorthand doing more than intended** - `gap` sets both axes, `padding` sets
  all four sides

Patching around these is what turns a readable file into an unreadable one
over a handful of edits. The clean-up is part of the job, not an extra.

## Dietaries

Shown as pills, on the reservations board and the printed sheet. An allergy is
a solid red pill with the word "allergy" dropped from the label, since the fill
already says it; a preference is a tinted red pill at full label. Pills lay out
horizontally and wrap.

On the printed sheet, dietaries and comments share ONE column at their combined
width, pills on the first line and the comment beneath. Split across two narrow
columns a busy guest stacked three deep and left the row half empty.

## Housekeeping badges and order

- **Service** is a faint outline pill, **Clean** a solid ink pill, **Verify** a
  dashed red pill. The three must separate at arm's length without reading
  the word, on the board and on paper.
- **Order on both housekeeping pages: services, then cleans, then verify,
  then vacant**, room order within each block. Services are attempted during
  breakfast, before the departure cleans open up.
- **The printed clean sheet carries jobs only** — services and cleans — then
  three blank write-in rows for anything penned on. Verify and vacant rooms
  are not printed; the "To verify" count says how many to check. Rows are
  sized so that even a full house — all 17 rooms a job, plus the write-ins —
  stays within one A5 page. Do not loosen row padding without re-running the
  fit checks in tests/hk_suite.py.

## Seating (combined tables)

- The controls say **Seat together** and **Seat separately** — grouping rooms
  onto one table. It never merges bookings.
- Grouping affects table counts and adjacency display only. Per-room
  reservations are independent of it and must survive any order of
  operations; every `/manual` write preserves a room's reservation details
  (name, phone, diets, notes, and a dining pax) via `withExtras`.

## Rules of change

- **Shared files are versioned at their references.** Any edit to nala-ui.css
  or nala-shared.js bumps the `?v=` on every page that links it, in the same
  commit. The HTML no-cache metas do not protect shared assets — GitHub Pages
  caches them for 10 minutes and in-app browsers hold them longer. Mutating a
  shared file under a frozen version is how a phone ends up rendering one
  generation's HTML with another generation's stylesheet.

1. Control styling changes happen in nala-ui.css only, one commit, all pages.
2. New staff pages start by linking nala-ui.css and declaring a tier.
3. Anything guest-visible waits for the brand pass before restyling.
