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
  staff screens by their working names: Res tally, Res print, HC print,
  HC tally. On hc tally the menu exists but only renders for logins whose
  email does not start with "housekeeping".
- **Floating footer** (`.foot`): sticky at the bottom, holds the page's
  actions. Primary action solid, secondary outlined. App tier: cream with
  rule border. Print tier: white. Hidden when printing.
- **Sign-in**: owned by auth.js on every staff page; guest pages never see it.

## Tokens (defined once in nala-ui.css)

Cream #F9F7F4 · Ink #1C1C1A · Mid #999990 · Rule #E0E0DA · Red #A8321E
UI font: Helvetica/Arial. Content serif (app tier only): Georgia.
Labels: 10-11px, uppercase, letterspaced .12-.15em.

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
