# NALA menu app - style guide

One rulebook, three tiers. Every page declares its tier on the body tag and
loads `nala-ui.css`, which owns all shared controls. Page CSS may only style
page content, never controls.

## Mock up before you build

**Every visual change is rendered and shown before it is published.** No
exceptions, and no "this one is too small to bother".

The evidence is one day's commit log. Changes that were mocked first went in
as a single commit each and stayed. Changes published first and iterated on
the phone took four and five commits and twice ended in a revert. The cost of
a mockup is a minute; the cost of skipping it was hours.

What a mockup means here:

- Render it at the real width, 390pt for a phone screen, A4 or A5 for a sheet
- Show the worst case as well as the ordinary one - the longest name, five
  dietaries, a booking that carries a note AND a comment
- Show the states side by side when a change alters one of them, so the
  before is visible rather than remembered
- Measure what the change was supposed to fix and quote the number, not an
  impression

If the target is subjective - "make it clearer", "more pronounced" - turn it
into something measurable BEFORE writing code, or say plainly that it cannot
be, and offer options instead of guessing. A guess at a subjective target is
what leads to changing things nobody asked about in order to make the guess
work.

Publish only once the mockup is approved. Then it is one commit.

## Tiers

**tier-app** - the live tools: tally.html (res tally), cleaners.html (hc tally).
Job: fast operational reading. Cream/ink palette, big tap targets, colour used
only to encode state (green dining/done/ready, amber ageing, red attention,
dashed = unknown/awaiting).

**tier-print** - the sheets: list.html (res print), housekeeping.html (hc print).
Job: paper clarity. Black on white, minimum ink, no decoration, nothing
interactive appears in @media print. Red permitted only for "needs attention"
chips (prints grey, still legible).

**tier-guest** - index.html, welcome.html.
Job: brand. Styling matches nalaresort.com.au (palette/type to be lifted from
the real site - pending screenshots). Staff controls never appear here.

## Affordance - how you know what's tappable

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
  app tier - the grid itself is the control surface.

## Header - one row on every staff page

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

## Controls - identical on every staff page

- **Nav menu**: three-bar button, fixed top right. Dropdown lists the other
  staff screens by their working names: Reservations (tally.html),
  Reservations Sheet (list.html), Cleans (cleaners.html), Clean sheet
  (housekeeping.html), always in that order - live board then its sheet,
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

**Type scale - pick from this list, never by eye: 8 · 11 · 15 · 20 · 27.**
Each step is about a third up from the last. Two things that form one
statement sit on adjacent steps; skipping steps is what makes one of them
shout. 27 is reserved for a single headline number.

**Never use em dashes.** Not in copy, not in titles, not in comments. A
hyphen in a sentence, a middot for a separator. This is a standing rule, not
a preference to be re-litigated.

**Name what a number counts.** "2×3" and "3×2" look like the same sum and
the reader has to already know which side is which. Write the make-up as
"3 twos · 1 three" - a wording that can be said out loud and cannot be
read backwards. Both dining pages state the make-up the same way, on one
line - sentence case, normal letter-spacing, `nowrap` - because a wrapped
statistic reads as two facts.

**Stay dates are one line: `Tue 11-Fri 14`.** Weekday and bare day number,
no ordinal, no "to", month omitted because we know it. A range that wraps
doubles the height of the row it sits in.

## Printed sheets - repeating header

Everything above the table repeats on every printed page: page name, date,
stats, and the manager strip where there is one. Browsers only reliably
repeat a table header group, so the block is cloned into a `.printhead` row
inside `<thead>` as soon as the sheet has data - NOT on `beforeprint`, which
iOS Safari does not reliably fire - and the on-screen original is hidden on
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
stored at `/hk/<date>/<villa>/kind`, beside the availability and done marks, so
it expires with the day.

The rule lives in `hkClassify()` in nala-shared.js, so the board and the
printed sheet agree by construction rather than by remembering to change two
places. A hand-set job beats whatever the dates imply.

Three options: **To be cleaned**, **To be serviced**, **Mark as empty**.
Each goes through a confirm screen, the same two-step every other action on
this page uses. An empty villa drops to 22% opacity and offers no cleaning
actions, only the job controls - it is not work, and must not compete with
the villas that are.

A villa whose job is unknown carries ONE label, the pill reading Unknown, and
nothing beneath it - two labels for one state says nothing twice. The pill is
dashed grey, not red: unknown is a gap in what we know, not something wrong.
Red stays reserved for alarm. Its sheet offers only the job controls, all
three of them, because nothing can be completed on a villa nobody has decided
about yet. Decide first, then it becomes work.

The revert button tells the truth about what it will do: **Use booking
dates** only when the dates actually decide a job, otherwise **Back to
unknown**. A villa the dates cannot place says Unknown, not "occupancy not
confirmed".

Management only. The controls reuse the same login check that hides the nav
menu from the housekeeping user - one gate, not two. Note this is a display
gate: the database rules still allow any signed-in user to write the field.

## Colour on the Cleans board

Colour means one thing: **this villa is ready to work on now**, and which
colour says which job.

- **White** - a job is set but the villa is not ready yet
- **Blue** - ready to clean, the guest has departed
- **Green** - ready to service, someone has noticed the villa is free
- **Light grey with a green tick** - finished. It loses its colour entirely:
  it is no longer work and must stop competing for attention
- **Very pale** - empty, not a job at all
- **Orange** - deliberately unused, held for a warning state

Order down the board, top left is highest priority: services, then cleans,
then finished work, then unknown, then empty. Finished work sinks below
outstanding work but stays above the villas nobody has decided about.

Within **services**, the villa noticed free longest ago leads - the guest is
the most likely to walk back in. The mark is **Possibly available**, stamped
with a time, and its elapsed timer turns amber at 15 minutes and red at 20:
an observation from half an hour ago is not worth acting on.

One mark, not two. Breakfast was only ever a way of saying "the villa is free
right now", so it says that instead, and it works whatever the hour.

**Services only.** A clean is decided by whether the guest has departed, not
by whether someone glanced in, so the option is not offered there. A mark
already set stays visible and clearable whatever the villa's job becomes -
otherwise a stale one would be stranded.

Within **cleans**, in order: a departed villa with a guest arriving today,
then any departed villa, then the rest. Two departed villas waiting to be
cleaned sort numerically - once the guest has gone there is no reason to
prefer one over the other, so they may as well be next to each other.

## Pre-arrival

A villa nobody is checking out of, but someone is checking into: it was
cleaned yesterday or last week, or its state is unknown, and it needs a look
before the guest walks in.

Only an **unknown** or **empty** villa can be set to it. Never a service -
that guest is staying on, so nobody is arriving.

It takes no colour. Colour means "something changed, go now", and a
pre-arrival is ready from the start because nobody has to leave first. The
pill reads PRE-ARRIVAL with "Arriving today" beneath, and PRE-ARRIVED with
the green tick once done, on the same grey as other finished work.

It is not a clean and not a service, so it carries its own count, shown only
when there are any - folding it into Cleans would misreport the morning's
workload. It sorts after the cleans and before finished work, and it prints
on the sheet.

Its sheet is short, because a pre-arrival is one job with one outcome: do it
or decide it was never one.

- Outstanding: **Mark as pre-arrived**, Back to unknown, Close
- Done: **Undo done**, Back to unknown, Close

No availability, no departure, no push, and no switching it to a clean or a
service. Nobody is in the villa yet, and nobody is leaving it.

## Pushing a clean to tomorrow

On a busy morning a clean can be deferred. **Push villa** appears only on a
clean with no arrival that day - a villa someone checks into tonight cannot
wait. It writes `pushed` to `/hk/<date>/<villa>`.

A pushed villa reads like finished work, grey and out of the way, but the
word is **Pushed** in purple: deferred, not done. For the rest of today it
sorts BELOW the finished villas - it is not today's work at all - while
staying above the undecided and empty ones. The board also reads
yesterday's marks, so a villa pushed yesterday and never finished arrives
today as a clean that is already departed - the guest left, the work did not
happen - and sorts at priority 2 with the other departed cleans.

**Undo push** brings it back to today.

**Empty, not vacant.** The word is empty everywhere a person reads it, on the
board and on the printed sheet. Only management can set it - though the
display gate is only as good as the logins, and while the housekeeping user
does not exist everyone signs in as management and sees everything.

## Multi-select on the Cleans board

The footer carries Refresh on the left and Select multiple on the right. In
select mode the button reads **Cancel** while nothing is picked and
**Options** once something is, so one button covers the whole flow.

Only villas whose job is **unknown** can be picked: the point is to decide
several at once, and anything already decided has nothing to decide. Villas
that cannot take part dim rather than disappear, so the grid keeps its shape.

The options are the same sheet an unknown villa shows on its own, applied to
every villa picked, and the board leaves select mode once the decision is
made.

## Tense on the Cleans board

A villa reads **Clean** or **Service** while the work is outstanding and
**Cleaned** or **Serviced** once it is done. The completion button names the
job it completes - "Mark as cleaned", "Mark as serviced", with a tick - not a
generic "done". Staff should never have to remember which kind of job they
are finishing.

The board derives each villa's job on every render rather than freezing it at
load, so setting one takes effect on the tile immediately and the villa
re-sorts into its block. Anything that requires a refresh to show is a bug.

## Clean up

After a run of edits to a page, stop and read the whole block, not the lines
you changed. Every time this has been skipped the page has accumulated the
same four faults: two rules fighting each other for the same selector, a rule
whose subject no longer exists, a comment describing behaviour the code no
longer has, and a container quietly costing layout width. Patching around
those is what makes a page get worse with every edit. Fix them at the source
and re-measure; do not add a rule to counteract another rule.

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
  then empty**, villa order within each block. Services are attempted while
  the guest is out, before the departure cleans open up.
- **The printed clean sheet carries jobs only** - services and cleans - then
  three blank write-in rows for anything penned on. Unknown and empty villas
  are not printed; the "To verify" count says how many to check. Rows are
  sized so that even a full house - all 17 rooms a job, plus the write-ins -
  stays within one A5 page. Do not loosen row padding without re-running the
  fit checks in tests/hk_suite.py.

## Seating (combined tables)

- The controls say **Seat together** and **Seat separately** - grouping rooms
  onto one table. It never merges bookings.
- Grouping affects table counts and adjacency display only. Per-room
  reservations are independent of it and must survive any order of
  operations; every `/manual` write preserves a room's reservation details
  (name, phone, diets, notes, and a dining pax) via `withExtras`.

## Rules of change

- **Shared files are versioned at their references.** Any edit to nala-ui.css
  or nala-shared.js bumps the `?v=` on every page that links it, in the same
  commit. The HTML no-cache metas do not protect shared assets - GitHub Pages
  caches them for 10 minutes and in-app browsers hold them longer. Mutating a
  shared file under a frozen version is how a phone ends up rendering one
  generation's HTML with another generation's stylesheet.

1. Control styling changes happen in nala-ui.css only, one commit, all pages.
2. New staff pages start by linking nala-ui.css and declaring a tier.
3. Anything guest-visible waits for the brand pass before restyling.
