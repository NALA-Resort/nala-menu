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
