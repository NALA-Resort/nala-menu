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

## Controls — identical on every staff page

- **Nav menu**: three-bar button, fixed top right. Dropdown lists the other
  staff screens by their working names: Res tally, Res print, HC print,
  HC tally. On hc tally the menu exists but only renders for logins whose
  email does not start with "housekeeping".
- **Floating footer** (`.foot`): sticky at the bottom, holds the page's
  actions. Primary action solid, secondary outlined. App tier: cream with
  rule border. Print tier: white. Hidden when printing.
- **Date navigation**: ‹ › + Today/date, top of page, never inside the footer.
- **Sign-in**: owned by auth.js on every staff page; guest pages never see it.

## Tokens (defined once in nala-ui.css)

Cream #F9F7F4 · Ink #1C1C1A · Mid #999990 · Rule #E0E0DA · Red #A8321E
UI font: Helvetica/Arial. Content serif (app tier only): Georgia.
Labels: 10-11px, uppercase, letterspaced .12-.15em.

## Rules of change

1. Control styling changes happen in nala-ui.css only, one commit, all pages.
2. New staff pages start by linking nala-ui.css and declaring a tier.
3. Anything guest-visible waits for the brand pass before restyling.
