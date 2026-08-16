# Mews sync and pre-arrival - design

Agreed 16 Aug. Not built yet. Backlog item 6.

Replaces the current mechanism, in which a guest's name, villa and dates reach
the app only when that guest opens a welcome link. Click through is not high
enough to rely on, and a reservations board with missing guest data is worse
than useless: it looks like the villa is empty.

## The decision that shapes everything else

**Booking data goes to Firebase RTDB, not to this repo.**

The original proposal was Zapier to GitHub. Three reasons it changed:

1. **This repo is public.** Names, phone numbers, arrival dates and allergies
   in it are world readable, indexed, and permanent, because git history keeps
   them after a delete. Allergies are health data. Backlog item 2 already says
   a token committed here is auto revoked by GitHub; nothing rescues a guest's
   name the same way.
2. **The database already exists.** `responses`, `roomguests`, `/hk` and
   `/staff` all live in RTDB. A second store means two sources of truth and a
   join across them on every render.
3. **A commit per booking is a third writer to main.** Commits land on top of
   whatever main is at that moment, with no merge and no warning. An automated
   committer firing on every reservation change makes that routine.

GitHub is a filesystem with an audit log. This needs a database.

## The path

```
Mews  ->  Zapier  ->  Cloudflare Worker  ->  RTDB
```

Zapier holds a URL and a shared secret, nothing that can read the guest list.
The Worker holds the credential.

**A second Worker, not a route on the push sender.** That sender was built to
hold the VAPID key and no database credential, so compromising it cannot reach
the data. Adding a Firebase service account to it would throw that away. One
extra deploy is the cheaper side of the trade.

**Nothing on our side schedules anything.** GuestTouch owns the send timing, so
there is no cron, no scheduled Worker and no date arithmetic here. The Worker
only ever reacts to Zapier.

**Why not Zapier straight to RTDB.** Zapier would need either a legacy
database secret, which is deprecated and grants everything, or service account
JWT signing, which Zapier cannot do without a code step. Either way a third
party ends up holding a key to the whole database.

**Why not the Mews Connector API directly, yet.** It is the better end state:
Mews supports registering a webhook endpoint with a shared secret token, which
would remove Zapier entirely and cost nothing per event. It needs a support
request to register the endpoint, and the webhook carries the event and entity
id only, so the Worker must call back for detail. Zapier's Mews app already has
a reservation trigger covering new booking, check in and check out, so it is
the faster way to prove the shape. Because the Worker is in the middle, moving
to a native webhook later changes the front half only.

## Data shape

```
/bookings/<mewsReservationId>
  pms/                      written by the Worker only, never by the app
    first, last, phone
    arrive, depart          YYYY-MM-DD, dkey() format
    villa
    state                   confirmed | cancelled
    updated                 from Mews, for stale write rejection
  prearrival/               the questionnaire answers
  dining/                   per date: covers, dietaries, notes, departed

/stays/<date>/<villa>  =  <mewsReservationId>
```

**Two nodes under one id** so the rules enforce the split rather than everyone
remembering it. The app can never write `pms`; the Worker never writes
anything else. That is what makes "the Zapier payload is written once and then
left alone" true rather than a convention.

**`/stays` is not optional.** Keyed by reservation id alone, "who is here
tonight" means downloading every booking ever made, on every board, every
twenty seconds. The boards were taken from nineteen requests to four
deliberately, and that is the difference between about 9GB and 1.9GB a month
across five phones. `/stays` is one line per villa night; a fortnight is about
240 tiny entries, and every existing query is already a date and a villa.

**Dates use `dkey()` format** from nala-shared.js line 10, so `/bookings` joins
to `/hk/<date>` and `roomguests` with no conversion anywhere.

## How it reaches the boards

`roomRecord()` already merges in layers, each filling only what the one below
left empty:

```
Object.assign({}, known, best || {}, m)
     known = roomguests    best = the guest's responses entry    m = staff override
```

Mews does not compete with any of these. It replaces the bottom layer:

```
Object.assign({}, known, mews, best || {}, m)
```

- **Mews owns** name, phone, arrive, depart, villa. Stable for the whole
  reservation.
- **`responses` keeps** dining intent, dietaries, covers, notes, the `at`
  timestamp. Additive, per night.
- **`manual` keeps** the staff override, still beating everything.

Existing bookings keep working from `roomguests`; new ones get Mews layered
over it. There is no cut over day and no backfill, because the fallback is
already how the function works.

**Two fields genuinely collide and are called here rather than left to chance:**

- **`depart`.** `hkClassify()` line 231 reads `rec.departs` to decide clean
  versus service, and today that comes from a guest written record. This is the
  root of "arrival detection is fragile". Mews wins over `roomguests` and over
  the guest's own answer. Staff override still wins over Mews.
- **`villa`,** for a guest who gets moved after booking. Mews wins.

## Bookings change

The proposal triggers on a new reservation. Reservations are also moved,
extended, shortened and cancelled, and Mews fires update events for all of it.
An insert only Zap leaves a moved guest in two villas and prints a registration
card for a cancelled one. The Zap upserts on the id; `state` and `updated`
exist for that.

A cancelled booking clears its `/stays` entries. It does not delete
`/bookings/<id>`, so the record of what was asked for survives.

## Build order

**Stage 1 - data lands, nothing on screen changes.**
Worker route, Zap, rules, `/bookings` and `/stays` written. The boards ignore
both. Real bookings can be watched against what the board already shows, at no
risk to a live service.

**Stage 2 - the boards read it.**
One insertion into `roomRecord()`, plus the departure precedence. Touches
nala-shared.js and therefore a version bump everywhere. Suites updated.

**Stage 3 - the pre-arrival page.**
`prearrival.html?b=<id>`. Guest tier. Mock up first. Four questions:

1. Type of stay
2. Dining on the arrival night
3. Allergies and dietary requirements
4. Estimated arrival time

Four because it fits one phone screen without scrolling, and completion rate is
the entire point of the page. Arrival time is the only one that feeds the
Cleans board rather than the kitchen: it says which villa has to be ready
first. Resist adding a fifth without deciding which of these it replaces.

**Stage 4 - the guest page rewrite.**
`index.html` and `welcome.html` take a booking id instead of a URL carrying
guest data. `responses` becomes keyed by booking id at the same moment, because
that is the only identifier the page has left. This is where the two villas one
phone bug dies, as a side effect rather than a task.

**Stage 5 - registration cards.**
`registration.html`, print tier, one card per arriving villa, questionnaire
answers filled in or left blank for pen. Editable at reception with a save.

**Stage 6 - write back to Mews.**
Selected answers appended to the **reservation Notes**, through Update
reservation. Free text, so nothing can query it; that is accepted. The app
stays the source of truth and this exists only so front desk staff working in
Mews see dietaries without opening the app.

No echo risk: `pms` is Worker written and holds only the six named fields, so a
note written into Mews cannot arrive back as booking data.

## Security notes

**A reservation id is a GUID, so it is a better secret than a phone number.**
The open item "anyone who knows a guest's phone number can write that guest's
booking" stops being true at stage 4, without needing signed links.

**The pre-arrival page is still unauthenticated by design,** because a guest
cannot sign in. Anyone holding a booking id can read and write that booking.
That is acceptable for a GUID that only ever travels in an SMS to the guest; it
would not be acceptable for a short code.

**`/bookings` must be named explicitly in the rules.** The `$other` catch all
grants any signed in user read and write on paths not named, which is what lets
new fields work without a rules change. Guest PII is exactly the thing that has
to be named, as `kind` now is.

## Required console actions

These cannot be done from here and are listed so they are not discovered one at
a time.

1. **Mews Marketplace:** connect the Zapier integration, copy the access token.
2. **Firebase:** create a service account for the Worker. The previous handover
   said there was no service account and one was not warranted; that reasoning
   held while every write came from a signed in phone. A machine writer changes
   it. The alternative is a legacy database secret, which is deprecated and
   grants everything, so it is not the answer.
3. **Firebase rules:** paste the `/bookings` and `/stays` rules. Written into
   `rules.json` for review first, starting from the live copy, never from
   memory: `extcancel` exists only in the rules.
4. **GuestTouch:** the triggered message, **one week** before arrival, with the
   booking id as the only dynamic portion. The timing lives here and nowhere
   else, so changing it later is a GuestTouch setting, not a deploy.

## Open questions

- Whether **type of stay** is a picklist or free text. A picklist can be
  counted and printed as a chip; free text cannot. Needs the actual list of
  stay types before stage 3 is mocked.

## What this does not do

**It does not replace `roomguests`.** That comes later, once `/stays` has been
trusted for a while. It is worth doing: `roomguests` is fourteen of the
nineteen requests a board used to make, and it is written by a guest opening a
link, which is the fragility this whole project exists to remove.

**It does not put any guest data in this repo.** Not the plan, not a fixture,
not a demo file. The demos use fixed invented data and must keep doing so.
