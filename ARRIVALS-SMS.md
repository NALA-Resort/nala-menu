# Pre-arrival SMS (arrivals-sms.html)

Built overnight 24-25 Aug 2026 from the owner's brief: an almost-copy of
Invitations that looks FORWARD instead of at tonight. It finds bookings
arriving in the next 3, 7 or 14 days, sends each guest the pre-arrival form
by SMS through the same Worker and short-link scheme, and tracks who has been
sent the form, who opened it, and who finished it - so the desk can chase the
stragglers before they are standing at reception.

The mock the owner saw is `mock-arrivals-sms.html` beside this file.

## Division of labour with the Front Desk

**Front Desk owns the day of arrival.** This page owns the run-up. They read
the SAME cells, deliberately: `/bookings/<id>/prearrival` is the form's own
record, written by prearrival.html as the guest moves through it. Nothing on
this page invents state:

- `openedAt` - the guest opened their link
- any answer field present - they started (front-desk's GUEST_ANSWERS list,
  copied here, and "no" is an answer)
- `at` - they submitted: **form completed**
- what this page adds is only `/previnvites/<bookingId>` - the send record,
  the same shape as `/invites/<date>/<villa>` but keyed on the booking,
  because "has THIS guest been asked" outlives any one villa-night.

## Where the arrivals come from

`worker/mews-sync.js` already writes `/stays/<date>/<villa>` for every night
of every booking it hears about, however far ahead. An arrival on date d is
the stay at `/stays/<d>` whose own `arrive` IS d. The page walks the window's
dates, keeps those, and drops a booking id it has already seen (a villa move
lists one booking under two villas).

## The five bands (same visual contract as Invitations)

1. **To send** - white, pre-ticked. A failed send returns here with its
   reason. `stateOf` kind `ready`.
2. **Opened, not finished** - terracotta, the follow-up work this page
   exists for. Tickable, so a nudge is one tick plus the second-press
   confirm. Kind `open`.
3. **Waiting on the form** - grey, sent but silence. Kind `sent`.
4. **Form completed** - green, untickable: there is nothing to chase and no
   reason to message. Kind `done`. The form's stamps outrank the send's -
   however the link got to them, done is done.
5. **Cannot send** - dashed, sunk, no tick. Kind `nophone`.

## Sending

Same Worker (`worker/send-invites.js`), same URL, POST field `kind: "pre"`
with `bookings: [ids]` instead of `villas`. The Worker:

- skips the menu backstop (the form exists whether tonight's menu does)
- re-reads `/bookings/<id>/pms` itself: an edited browser can name a booking
  but not change whose phone or which link
- refuses a past arrival and anything over 45 days out
- normalises the phone by the same one table (`tests/phone_cases.json`)
- mints the same 6-character token; `/links/<token>` -> booking id, and the
  SMS carries `https://menu.nalaresort.com/prearrival.html?t=<token>` -
  52 characters, link last, so iPhones draw the preview card
- records to `/previnvites/<id>` with the caller's own auth

prearrival.html resolves `?t=` exactly as index.html does; the long `?b=`
links keep working.

## Templates

Its own set at `/presmstemplates`, edited on templates.html in a second
section beside the invitations set; marker `<form>`, moved-to-last on save
like `<menu>`. The page falls back to built-ins when the node is empty or
unreadable.

## Suites

The assertions live in `tests/inv_suite.py` (the SMS family suite) plus the
worker's `worker/invites-test.mjs`; sweep registered as `sweep:arrivals-sms`.
Bands, exclusions (in-house guest, double-listed booking, out-of-window
arrival), knob widening, the kind-pre POST shape, and the permission gate are
all pinned.

## Deploy checklist

Once `DEPLOY.md`'s one-time setup is done, publishing these files to `main`
deploys them by itself and this checklist is a green run in the repo's
Actions tab. Until then, by hand:

1. Paste `worker/send-invites.js` into the `nala-invites` Worker, Deploy.
2. Paste the whole `rules.json` into the Firebase console, Publish
   (adds `/previnvites` and `/presmstemplates`).

## Decisions taken alone (the owner was asleep; report, not re-litigate)

- **Name**: `arrivals-sms.html`, nav label "Pre-arrival SMS", placed after
  Invitations. "Arrivals" alone was taken by the registration print page.
- **Completed means `at`** (the guest submitted), not `confirmedAt`
  (reception verified): this page tracks the guest's side of the form.
- **Completed rows are untickable.** Invitations keeps answered villas
  tickable because a guest may want tonight's menu again; a finished form
  has no such second use. Failed sends and opened forms stay tickable.
- **The window knob is 3/7/14 days**, default 7, today included. The Worker
  independently accepts up to 45 days so a longer knob later is page-only.
- **One record per booking** (`/previnvites/<id>`), not per villa-night.
- **A booking with no villa yet sends anyway**; its token carries villa "0",
  which only the menu page's fallback would read and no board draws.
- **`<form>` is the marker**, and each template set normalises any marker
  typed into it to its own - a copied template cannot carry the wrong one.
