# Button audit - 27 Aug

Prompted by the owner: saves give no feedback, everything reads black, and
every page seems to dress its buttons its own way. This file is the survey -
what exists today, page by page - and the proposal sits rendered in
`mock-buttons.html`. Nothing changes until that mock is approved; on
approval the standard's wording moves into STYLEGUIDE.md (the button law's
home) and this file keeps only the survey.

## The headline

- Roughly **25 to 30 visually distinct button dresses** across 21 live
  pages: 5 shared rules in nala-ui.css plus about 46 page-local ones.
- **Six surfaces save with zero feedback** - no disable, no label change,
  no colour, nothing between tap and network return.
- **No shared feedback helper exists.** nala-shared.js has ~100 functions
  and not one UI feedback primitive. Seven pages each own a private
  error bar; five pages each hand-wrote their own save feedback.
- tally.html:1576 says "api() already showed the toast". There is no toast.

## Where saves are silent

All of these write to Firebase and change nothing on the button:

| Page | Buttons |
|---|---|
| front-desk.html | Save, Confirm and check in, and the summary's Confirm arriving / Confirm & check in |
| tally.html | Save details / Update guests / Save changes, Dining, Not dining, Cancel booking, Vacant, Restore, Revert, and all six bulk-select actions |
| cleaners.html | every sheet write - about 40 buttons: Mark as cleaned, departed, push, breakfast stamps, take-over - plus the strip/linen toggles |
| spa.html | Book, Confirm, Suggest, Approve, Ask the masseuse, Guest told, Decline, Cancel booking |
| staff.html | every permission and notify tick, the master toggle, the three spa price inputs |
| index.html | the guest's Confirm - nothing shows between tap and the panel change, and a second tap writes twice |

Most of these are optimistic writes with rollback on failure - good data
discipline that has been quietly doing feedback's job, which is why the
silence went unnoticed until now.

## Where feedback already exists (all page-local, none shared)

1. **templates.html `.save`** - the complete lifecycle and the best on the
   site. Rests disabled reading "Saved"; an edit re-arms it to "Save";
   click disables it through "Saving"; failure re-arms with a warning line.
2. **arrivals-sms.html / invitations.html `#sendBtn`** - live count in the
   label, red armed confirm press, disabled "Sending", rows repaint sent.
   The whole handler is pasted identically into both pages.
3. **flags.html / tag.html `#saveBtn`** - disable, then a "Saved" chip and
   the save bar slides away. Also pasted wholesale between the two pages.
4. **publish.html `#pubBtn`** - disable, "Publishing" status, then the done
   panel. `#rmBtn` two-press arm with a 4s disarm.
5. **prearrival.html** - disable plus "Sending", clean revert on failure.
6. **tally.html `#gdIntSave`** - the lone disable-and-"Saving" in an
   otherwise silent page.

The two-press arm (publish's remove, templates' delete, the send buttons)
is already the house pattern for destructive and bulk sends and stays.

## The dress divergence, per page

Shared (nala-ui.css): `.btn` / `.btn.solid` (square, system font,
11px/.14em), `.tier-print .btn` / `.ghost`, `.navbtn`, `.dnav`, `.navgrp`.
The shared `.btn` has **no :active rule**: the only pressed state in the
shared CSS belongs to the date arrows.

| Page | Local dresses | Notes |
|---|---|---|
| tally.html | `.opt` +`.solid/.out/.vac/.quiet`, `.selbtn` ×5, `.gd-int-save`, `.bub`, `.pax`, `.chip`, `.seg` | `.opt.solid` is solid green at rest - green claims "done" before the press (colour law). Two anchors act as buttons |
| front-desk.html | `.opt` +`.solid/.quiet`, `.sum-btns .go/.wide`, `.seg`, `.pax`, `.chip`, `.pen` | its `.opt` is a drifted near-twin of tally's (different radius, size, text colour). The primary Save wears `.opt.quiet` - the secondary's dress |
| cleaners.html | `.pbtn` +`.solid/.ghost/.warn`, `.ttog` | 6px radius, 12px/.1em, `font-family:inherit`; one disabled state done with an inline style |
| spa.html | `.cbtn` +`.solid/.quiet/.danger`, `.chip`, `.allbtn` | the one page on the new button law; four bare `<button class="stat">` filters wear no button dress at all |
| staff.html | re-declares `.btn` over the shared one, `.tick`, `.warn`, `.ghost`, `.master`, `.bin` | the override adds 8px radius and a cream fill back |
| templates.html | `.save`, `.del` / `.del.arm`, `.add` | |
| flags.html | `.savebtn`, `.addbtn`, `.mtog` / `.mdel`, private `.navbtn` copy | hard-coded Helvetica; no nala-ui.css on this page |
| tag.html | the same four, byte for byte | pasted from flags.html |
| publish.html | `.pubbtn`, `.rmbtn` / `.arm`, `.sfbtn`, `.tick`, `.addbtn`, private `.navbtn` copy | no nala-ui.css |
| arrivals-sms.html | `.btn.arm`, bare `<button>` day segments | otherwise shared |
| invitations.html | `.btn.arm` again | pasted from arrivals-sms |
| index.html | `.r-btn` +`.primary/.danger/.quiet`, `.pax`, `.chip` | guest brand: Raleway, brown, 10px radius. Its own on purpose |
| welcome.html | private `.btn` +`.primary` | guest brand |
| prearrival.html | `.send`, `.back`, `.more`, `.opt` / `.on` | guest brand, 10px radius |
| stats.html | private `.btn` copy | Helvetica 10px against the shared 11px system font |
| menu-print.html | private `.btn` / `.ghost` copy | Raleway - a third font on a third `.btn` |
| past-menus.html | `.err .btn` partial override | adds 8px radius and different padding |
| list / housekeeping / registration | none | the clean ones: shared dress only, with a comment saying so |
| pages.html | none | link rows, not buttons |

Radius across all of it: 0 · 5 · 6 · 7 · 8 · 10 · 16 to 20 (pills) · 50%.
Fonts: the system token, hard-coded Helvetica (flags, tag, publish, stats),
Raleway (index, menu-print), plus `inherit` leaking Georgia on app pages.

## The proposal (rendered in mock-buttons.html)

The button law's three dresses stay as ruled. New, defined once:

- **Press:** every `.btn` gets an `:active` state - quiet fills rule-grey,
  solid deepens, terracotta tints.
- **Saving:** disabled, label "Saving", the waiting grey of the colour law.
- **Saved:** the green pill green - done's colour, only ever after the
  write. Editors that stay open rest at a disabled "Saved" until the next
  edit re-arms (the templates pattern); sheets that close on success flash
  it 400ms first.
- **Failure:** the button returns to rest and a red line appears under it.
  Red text, never a red tile.
- **One helper in nala-shared.js** - `saveFeedback(btn, promise)` - replaces
  the five hand-written copies and gives the six silent surfaces something
  to call.

Open questions the mock puts to the owner: square or 8px radius; whether
tally's colour-previewing choice buttons (green Dining, terracotta Not
dining) keep their colours; how far the resting "Saved" label travels.

Rollout as pages are touched, per the standing rule for the destructive
dress: the CSS and helper land in one commit with every `?v=` bumped, then
each page adopts as it is next opened. staff, stats, menu-print, past-menus
and welcome drop their private `.btn` copies when their turn comes.
