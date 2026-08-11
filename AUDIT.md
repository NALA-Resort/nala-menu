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
