# Mews sync - handover, 16 Aug 2026

Written at the end of the session that built the sync. Self-contained: it
repeats what it needs from MEWS-SYNC.md and SETUP.md so this file can be read
alone. Read STYLEGUIDE.md before touching anything visual.

---

## How to work with this user

These were said more than once during the session, and ignoring them cost the
most time.

- **One step, then wait.** Not a list. Not three things in a paragraph.
- **Name the software and the URL** for every task. Not "the dashboard".
- **Name the button** the step ends on.
- **Offer tappable options**, and always include a free-text "Other".
- **Never hand over manual work** the assistant could do.
- **Verify before asserting.** The session's worst moment was three reversals
  on whether Zap edits re-fire, because the test did not control for the
  polling window.

---

## What the sync is

Mews (PMS) knows who is arriving, when, in which villa. The app did not. The
sync closes that gap.

**Path: Mews -> Zapier -> Cloudflare Worker -> Firebase RTDB.**

A second Worker, separate from the existing push sender, so the push sender
continues to hold no database credential.

Booking data does **not** go in the repo. The repo is world readable, git
history is permanent, allergies are health data, and a commit per booking
would put a third writer on main.

### Data shape

```
/bookings/<mewsReservationId>/pms          Worker-written only
/bookings/<id>/prearrival, /dining         app-written
/stays/<date>/<villa> = { id, first, last, phone, arrive, depart, adults, updated }
```

`/stays` carries the **guest summary, not a pointer**. A pointer would cost one
request per villa and undo the work that took a poll from 19 requests to 4.

### The merge

`overlayStays()` lays the PMS over `roomguests` at the point that map is
resolved, on all four pages. Not inside `roomRecord()`, because tally.html
reads `roomguests` directly in eight places.

### Credentials

No service account. The Worker signs in as a **`sync` staff account** created
through the Settings page, and is therefore subject to the same rules as any
other account. Six-digit passcode, accepted given how narrow the role is.

---

## Live configuration

| Thing | Value |
|---|---|
| Worker | `https://nala-mews-sync.ben-681.workers.dev` |
| Worker name | `nala-mews-sync` |
| Database | `https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app` |
| Cloudflare secrets | `SYNC_EMAIL`, `SYNC_PASSWORD`, `ZAP_SECRET`, `FB_API_KEY` |
| Zapier plan | Paid. Webhooks by Zapier is premium, this was a real cost fork |
| Zaps | "Mews New Reservation to Webhooks", plus a duplicate for updates |

The shared secret and the Firebase web API key were both exchanged in the chat
that built this. **They should be rotated when convenient**, along with the
`sync` passcode, which was also pasted in chat.

### The Zap that works (new bookings)

Trigger: Mews -> Reservation Event.

- Time Filter: `Reservations starting (= arriving)` (ID: Start)
- State: empty
- Start Time Modifier: 0
- End Time Modifier: 60

Mews caps the interval near **100 hours** ("The interval must not exceed
100:00:00"), so the current lookahead is about 84 hours.

Start Time Modifier **accepts negatives** and shifts the window's start. That
is the untested route to a 7-day lookahead: Start 168 / End 216. Time Filter
also accepts a custom value.

### The Zap that catches changes

A duplicate with Time Filter `Updated`, Start -70, End 0. Confirmed to fire on
a room move.

### Field mapping

Found by looking at the picker, not from documentation.

| Worker expects | Zapier field |
|---|---|
| `Id` | ID |
| `FirstName` / `LastName` / `Phone` | **Companions 0** fields |
| `StartUtc` / `EndUtc` | Start Utc / End Utc |
| `ResourceName` | **Space Name** |
| `State` | State |
| `UpdateUtc` | Updated Utc (note the missing "d", the Worker accepts it) |

Also passed through: `BookingId` (from Number), `GroupId`, `AdultCount`,
`NotesText`, `NotesType`, `SpaceState`, `Companions0Notes`.

Companions is a numbered list, so a second guest is `Companions 1 First Name`.
Whether the picker offers `Companions` as a single item is unresolved.

---

## Settled facts about behaviour

- **New bookings arrive and work end to end.** Verified with villa 3, arriving
  17 Aug.
- **Edits do not re-fire on the Start Zap.** Confirmed with a test that
  controlled for the window: villa 3 is inside the window, an edit produced
  nothing, a new booking produced one event. This is why the Updated Zap
  exists.
- `/bookings` returning 401 to a plain read **is the rules working**. Read is
  granted on `$id`, not on the node. It is not a sign of missing data.

---

## Published today (all on main, HEAD `c233c54`)

In order:

1. `MEWS-SYNC.md` - the plan, later updated with live config and the overlay
   decision
2. `SETUP.md` - the user's task list, later rewritten click by click
3. The `sync` role - `ROLE_GRANTS` in nala-shared.js, a separate
   `ROLES_ASSIGN` in staff.html kept out of the notification matrix,
   `rules.json` naming `/bookings` and `/stays`, version bump to v16, six new
   tests, cl suite to 167
4. `worker/mews-sync.js` and `worker/test.mjs` - the test suite grew to 38
5. `worker/wrangler.jsonc` - name, main, compat date 2026-08-16
6. Stage 2 merge - `overlayStays`, `mewsRecord`, `fetchStays`, `isMewsOnly`,
   version bump to v17 then **v18**, cl suite to 176
7. `debug.html` extended - a fortnight `/stays` scan with a verdict, a read
   only "what the boards will show" merge preview for any date, a merge-tag
   junk finder and deleter, and a **clean slate** wipe (roomguests, responses,
   manual, hk, stays, guests, combined; config untouched; `/bookings` is not
   deletable from the app by design)
8. Fixes along the way - trimmed shared secret and self-explaining sign-in
   errors, accepted the Zap field spellings, link-opened no longer fires on
   PMS-only bookings (`isMewsOnly()`), debug preview no longer mislabels staff
   vacant villas
9. **Stale index fix** - one booking appeared as three Ben Davidsons in villas
   13, 14 and 15. Cause: clearing trusted `prev.villa`. Replaced with
   **clear by inspection**: for every date the booking could touch, read
   `/stays/<date>` and delete any entry claiming that reservation id which
   should not be there. Self-healing, tolerates the old bare-id shape, leaves
   other guests alone. Three tests added.

Suites at the last full run: tally 85, list 42, hk 22, cl 176, auth 30, worker
38.

---

## The precedence rule, as decided

Stated by the user: **"Mews data is always correct; it's the lack of data we
struggle with."**

- Mews **overwrites** name, dates, villa, guest count.
- Dinner data **survives**: dining or not, covers, notes, dietaries. Mews knows
  nothing about dinner, so overwriting these would only replace them with
  nothing.
- **Vacant Tonight on a villa Mews knows about: warn, then allow.** Reception
  can see the villa and Mews cannot, so it is not blocked.
- A staff vacant made after the warning **stands until Mews changes that
  booking**, and is then dropped.

The last point was stated earlier in the session and is what the in-progress
code implements. A closing question asking the user to confirm it explicitly
went unanswered, so treat it as decided but worth one confirmation.

---

## In progress, NOT published, NOT tested

This work was in the working tree when the session ended. It is reproduced in
full below because the sandbox does not survive. It was **not** published,
because the warning sheet has not been mocked up at 390pt and the styleguide
requires that first.

Still to do to finish it: run all five suites, add tests for the precedence
and the stale-vacant rule, mock up the warning sheet, bump `nala-shared.js` to
**v19** on all five pages, rebuild demos with `python3 tools/make-demo.py`,
one commit.

### worker/mews-sync.js, in the `/stays` summary (about line 261)

```js
        arrive: r.arrive, depart: r.depart, adults: r.adults,
        /* Carried into every night so the app can tell a staff decision made
           against THIS version of the booking from one made before Mews last
           changed it. Without it, a villa staff marked vacant either sticks
           forever or is undone on the next poll, and neither is what was
           asked for. */
        updated: r.updated || null
```

38 worker tests still green with this in.

### nala-shared.js, in `mewsRecord`

```js
  var out = { source:'mews', bookingId: stay.id, pmsUpdated: stay.updated || null };
```

### nala-shared.js, new functions above `roomRecord`

```js
/* The fields the PMS owns outright. Mews knows who is in a villa, when they
   arrive and leave and how many of them there are. It knows nothing about
   dinner, so dining, covers, notes and dietaries are never touched here: they
   would only be overwritten with nothing.                                   */
function pmsFields(known){
  if (!(known && known.bookingId)) return {};
  var out = {};
  ['name','departs','arrives','phone','adults'].forEach(function(k){
    if (known[k] !== undefined && known[k] !== null && known[k] !== '') out[k] = known[k];
  });
  return out;
}

/* A villa the PMS knows about can still be marked vacant by staff, after a
   warning, and that decision stands until Mews changes the booking. It is
   stamped with the PMS version it was made against: once Mews sends a newer
   one, the staff decision was about a different state of the world and is
   dropped rather than silently outliving the facts it was based on.        */
function vacantIsStale(m, known){
  return !!(m && m.status === 'vacant' && known && known.bookingId &&
            m.pmsUpdated !== known.pmsUpdated);
}
```

### nala-shared.js, inside `roomRecord`

```js
  var known = roomguests[String(n)] || {};
  if (vacantIsStale(m, known)) m = null;
  var pms = pmsFields(known);
  if (m && m.override) return Object.assign({}, known, best || {}, m, pms, { room:String(n) });
  if (best) return Object.assign({}, known, best, pms);
  if (m)    return Object.assign({}, known, m, pms, { room:String(n) });
```

### tally.html, `applyToSelected` (about line 918)

```js
    /* Same stamp as the single villa path. Without it a multi-select vacant
       would be dropped by the next render, since an unstamped vacant on a PMS
       villa reads as stale. */
    var kn = roomguests[String(n)] || {};
    if (status === 'vacant' && kn.bookingId) rec.pmsUpdated = kn.pmsUpdated || null;
```

### tally.html, the `oVac` handler (about line 1215)

```js
  /* Vacant contradicts the PMS rather than filling a gap in it, so it warns
     first on a villa Mews knows about. Allowed, not blocked: reception can see
     the villa and Mews cannot. The decision is stamped with the PMS version it
     was made against, so it stands until Mews changes the booking and then
     stops, rather than outliving the facts behind it. */
  document.getElementById('oVac').onclick = function(){
    var kn = roomguests[String(n)] || {};
    var rec = { status:'vacant', pax:0, room:String(n), source:'manual' };
    if (kn.bookingId) rec.pmsUpdated = kn.pmsUpdated || null;
    if (!kn.bookingId) return writeManual(rec);
    confirmSheet('Villa '+n,
      'Mews has a booking here'+(kn.name ? ' for '+kn.name : '')+
      (kn.departs ? ', departing '+kn.departs : '')+
      '. Marking it vacant contradicts the PMS. It will hold until Mews changes the booking.',
      'Mark vacant anyway',
      function(){ writeManual(rec); },
      function(){ openRoom(n, st); });
  };
```

---

## Open items, in the order they should be done

**Blocking, on the user:**

1. **Paste the current `worker/mews-sync.js` into Cloudflare.** The Git build
   is deploying something older, so the stale index fix is not live. Route:
   repo root -> `worker` folder -> `mews-sync.js` -> the "..." menu -> Copy,
   under Raw file content.
2. **Clear `/bookings` in the Firebase console.** It holds test guest PII and
   is deliberately not deletable from the app.

**Next on the sync:**

3. **Villa 3's phone did not come through** although it is present in Mews.
   Check the mapping in the working Zap, step 2, Configure.
4. **Widen the lookahead** with a negative Start Time Modifier. Untested.
5. **Backfill in-house guests** by switching Time Filter to `Colliding`
   temporarily, then reverting.
6. **Make vacant the default villa state.** The user's idea, and right, but it
   needs 4 and 5 first: at the moment an absent villa can mean three different
   things.

**Then the remaining stages:**

7. Finish and publish the precedence change above.
8. Stage 3, prearrival.html. **Blocked**: needs to know whether type of stay is
   a picklist or free text, and if a picklist, the actual list of stay types.
9. Stage 4, the guest page rewrite. This is where `responses` gets re-keyed to
   the booking id. CORRECTED 17 Aug: the key IS read, at index.html:846, to
   restore what the guest already answered tonight. Re-keying breaks that
   unless line 846 changes with it. Originally written as: only written at
   `index.html:823`.
10. Stage 5, registration cards.
11. Stage 6, write back to Mews reservation Notes.

**The questionnaire**, for stage 3, is four fields: type of stay, dining on the
arrival night, allergies and dietaries, estimated arrival time. GuestTouch
fires it one week out and that timing is configured in GuestTouch, so there is
no timing code on our side.

---

## The original brief

Reproduced so this file stands alone. Lightly cleaned of dictation slips:
"Zappia" and "Zaia" are Zapier throughout, and the note about storing in GitHub
is left as written, because the decision to store elsewhere is recorded in the
next section.

> Next feature I want to build is to update a current feature that might not be
> stable. The current feature is extracting guest data from the URL that is
> being sent via text message from GuestTouch data.
>
> The new proposal is that by using a Zapier connection to Mews PMS we can send
> data directly to GitHub when a new reservation action is triggered. This will
> build the upcoming guest database. From here we can send a triggered text
> message using GuestTouch with only the booking ID as the dynamic portion, and
> in that text message will be a link to a new page called "pre-arrival". The
> data from this pre-arrival questionnaire will be stored against the booking
> ID in GitHub. Data will also be sent back by Zapier to an appropriate field
> in Mews.
>
> The benefit of this flow is twofold. One is that we can capture an unlimited
> amount of data and store it for future reservations. Secondly it does not
> rely on guests clicking welcome messages in order to fulfil the data required
> in each room on the web app. In my experience the click through rate of a
> welcome message might not be as high as I hoped, and a reservation screen
> with missing guest data will become annoying.
>
> In order to not bloat the amount of data circling around, and the direction
> in which it flows, the Zapier integration will be the largest payload. From
> then on that payload will remain untouched and we will only ever add
> additional information relating to dinner reservations and allergies and
> things that we continue to build from time to time.
>
> The data could be broken up into two parts. 1. The first part is reservation
> data which will come from Zapier. It will contain the booking ID, first name,
> last name, phone number, check-in date and check-out date. 2. The second part
> would be things that we build in the web app that may get attached to the
> booking ID: things like allergies, dietary requirements, the date that guests
> will be dining, whether the guest has departed or not, or any additional
> things we decide to add as we develop the app.
>
> This next phase is to architect a plan of attack and a step-by-step process
> to building out the Zapier integration with Mews, and then tidying up the
> welcome letter and dinner reservations code so that it is not relying on all
> the existing data in the URL. It will just be relying on one unique piece of
> information, ideally the booking ID from Mews.
>
> In addition there will be a pre-arrival page that needs to be built that will
> contain questions about the type of stay they are looking for, whether or not
> they will be eating dinner on their arrival, if they have any allergies or
> dietary requirements and that sort of thing.
>
> So from a working flow, it goes like this:
> 1. Guest makes a booking.
> 2. Data is sent via Zapier to create a booking ID and guest profile.
> 3. A triggered correspondence is sent via GuestTouch a set number of days
>    before arrival, containing a link to the pre-arrival page with the booking
>    ID appended to the URL.
> 4. The guest fills out the pre-arrival questionnaire and any additional data
>    captured is added to their profile.
> 5. If the guest does not fill out their pre-arrival questionnaire, it can be
>    done on check-in at reception.
> 6. On the day of arrival we will be able to print out individually each
>    guest's registration form containing their details and the responses to
>    their questionnaire. This way we can attach their key cards to their
>    registration letter and confirm them on arrival.
> 7. Any guest that has not completed the pre-arrival form will have the
>    registration card printed also, but with the answers ready to be filled out
>    by pencil, or able to be edited on the computer in front of the guest and
>    saved.
>
> This plan needs to be read carefully and assessed from a logistics
> perspective, a code writing perspective and an integration perspective, to
> see if there are easier or better ways to do it using practices that already
> exist. Currently the only open API that I can find is via Zapier between Mews
> and GitHub, unless somebody has written one before.

---

## Assessment of the brief, and where the build differs

The brief was accepted almost entirely. Three changes, each with a reason.

**1. Booking data goes to Firebase, not GitHub.** This is the only structural
change and it matters. The repo is world readable and git history is
permanent, so a guest's name, phone and allergies would be public forever and
unremovable. Allergies are health data. A commit per booking would also put a
third writer on main, alongside the two chat sessions already working there.
Firebase RTDB is already in the app, already has rules and already holds the
operational data, so this is not new infrastructure. Everything else in the
brief is unchanged by it: the booking ID is still the key, the payload is still
written once and then only added to.

**2. Zapier does not write to Firebase directly.** It posts to a small
Cloudflare Worker, which signs in as a `sync` staff account and writes. Zapier
cannot hold a database credential safely, and the Worker is where the shaping
lives: one reservation becomes one `/bookings` record plus one `/stays` entry
per night, which is what makes a board render in four requests instead of
nineteen. It is also the only place that can clean up when a booking moves
villa or shortens.

**3. The payload is bigger than the brief's six fields.** Booking ID, first,
last, phone, arrival and departure are all there, plus villa, adult count,
booking state and the Mews updated timestamp. Villa is what lets the board show
the guest at all. The updated timestamp is what lets a staff decision be told
apart from a stale one.

**On the "only open API is Zapier" question.** Mews does publish a Connector
API, which would remove Zapier and its paid plan from the chain. It is not
worth doing now: it needs an enrolled integration and a server to receive
webhooks, and the Worker already is that server, so the swap later is a change
of what calls the Worker, not a rebuild. Revisit if Zapier's cost or its
polling window become a real constraint. The 100 hour window is already the
main limitation.

**On the logistics.** Steps 5 and 7 of the brief are the parts that make it
work in practice, because they mean a guest who ignores the message costs
reception a pencil rather than a rebuild of the record. Both are kept. The one
thing the brief does not say, and which the build assumes, is that Mews stays
authoritative for who is in a villa: reception can mark a villa vacant against
Mews, but that decision expires when Mews changes the booking.

---

## Every task, with status

**Stage 1, the pipeline. DONE.**

- Architecture decided and written up: MEWS-SYNC.md
- `sync` role, rules for `/bookings` and `/stays`, six tests
- Worker written, 38 tests
- Cloudflare deployed, four secrets set. CORRECTED 17 Aug: the Git integration
  was NEVER connected, which is why the stale index fix sat undeployed and was
  recorded as needing a manual paste. It is connected now, root directory
  `worker`, branch `main`, and the Worker deploys on every commit.
- Zapier paid plan, Mews Marketplace token, trigger Zap published
- Second Zap on `Updated` for changes
- Field mapping worked out
- Stale index bug found and fixed (published, not yet pasted into Cloudflare)

**Stage 2, the boards read the PMS. DONE.**

- `overlayStays`, `mewsRecord`, `fetchStays`, `isMewsOnly`
- All four pages, cl suite to 176
- Debug page: fortnight scan, merge preview, junk finder, clean slate

**Stage 2b, Mews versus staff precedence. WRITTEN, NOT PUBLISHED.**

Code is in this file. Needs suites, tests, a 390pt mockup of the warning
sheet, a v19 bump on five pages, demos rebuilt.

**Stage 3, prearrival.html. NOT STARTED. Blocked.**

- Decide type of stay: picklist or free text, and if a picklist, the list
- Four fields: type of stay, dining on arrival night, allergies and dietaries,
  estimated arrival time
- Page reads the booking ID from the URL and nothing else
- Writes to `/bookings/<id>/prearrival`
- Handle an unknown or expired booking ID gracefully
- Mock at 390pt before building
- GuestTouch: switch the template to a pre-arrival link carrying only the
  booking ID, firing one week out. Timing lives in GuestTouch, no code our side

**Stage 4, the guest page rewrite. NOT STARTED.**

This is the brief's main clean-up: stop reading guest data from the URL.

- index.html reads booking ID only, looks the guest up
- Re-key `responses` to the booking ID. CORRECTED 17 Aug: the key is read at
  `index.html:846` and must change with it. Stage 4 is also larger than this
  list: see the section on the two paths running at once in MEWS-AUDIT.md
- Retire the merge tag fields, and with them the `{{firstname}}` junk records
  that had to be cleaned out of `/roomguests` by hand
- Old style links must not break while any are still in flight

**Stage 5, registration cards. NOT STARTED.**

- One card per arriving guest, printed for the day
- Print tier rules apply: paper clarity, minimum ink, STYLEGUIDE.md
- Completed questionnaires print filled
- Uncompleted ones print with blank ruled answers for pencil
- Reception can fill the same form on screen and save, which covers brief
  step 5 and step 7 with one page rather than two

**Stage 6, write back to Mews. NOT STARTED.**

- A Zap the other way, into the reservation Notes field
- Decide what goes back: at minimum allergies and dietaries, since that is what
  a Mews user would look for
- Guard against a loop, since Notes changes can themselves trigger an Updated
  event

**Running alongside, on the sync itself:**

- Paste the current Worker into Cloudflare (blocking)
- Clear `/bookings` of test PII in the Firebase console (blocking)
- Fix the missing phone on villa 3
- Widen the lookahead with a negative Start Time Modifier
- Backfill in-house guests with Time Filter `Colliding`, then revert
- Then, and only then, make vacant the default villa state
- Rotate the shared secret, the Firebase key and the `sync` passcode

---

## What a fresh session needs

**No credentials are in this file, on purpose.** The repo is public, so the
shared secret, the Firebase web API key and the `sync` passcode are named here
but never written down. They are already stored where they are used, as
Cloudflare secrets, so the Worker keeps running without anyone re-entering
them.

The sandbox is wiped between sessions. To publish again, a new session needs
**one thing from the user: a GitHub token** with contents:write, saved to
`/home/claude/.ghtoken`. The publisher itself is now in the repo at
`tools/push.py`, so it does not have to be rewritten. Copy it to
`/home/claude/push.py`, edit `FILES` and `MSG`, run it.

Nothing else is needed. The clone is public, the Worker is deployed, the Zaps
are published and the rules are live.
