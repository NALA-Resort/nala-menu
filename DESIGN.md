# Design: who owns what, and why

17 Aug 2026. Merged from `GUEST-DATA.md`, `IDENTIFIERS.md` and `SCREENS.md`,
which overlapped. `HANDOVER.md` is the entry point; this is the detail behind
it.

---


---

## Two conversations, not one

These were fused in earlier drafts and it caused several wrong conclusions.
They have different purposes, different lifetimes and different homes.

**Pre-arrival.** Gathers data that sits against the guest for their whole stay:
type of stay, dietaries, arrival time, and dining on the arrival night. Happens
once, before or at check-in. Lives in `/bookings/<id>/prearrival`.

**The nightly dinner request.** Goes to in-house guests each day asking whether
they are dining that evening. Resets every night. Lives per date, where nightly
answers already live.

One is a profile. The other is tonight. Do not put them in the same node
because they look like the same question.

### The arrival night is answered by pre-arrival, not by a text

Most guests check in after 2pm, so the nightly request would arrive too late to
be useful. That is why the pre-arrival form asks about the arrival night
specifically, and why it describes what the menu will be like.

It is also why reception shows the guest the actual menu at the desk and
confirms the answer is still right. The guest answered days ago, against a
description. At the desk they see the real thing.

## The three villa states

- **Vacant.** No guest attached to the room.
- **Awaiting.** A guest is in house and has not answered tonight's request.
  Resets each night.
- **Confirmed.** A dining status is set for tonight.

**Confirmed includes not dining.** It is about an answer existing, not about
the answer being yes. Confirmed and dining are two different things and the
board has to keep them apart.

## The link icon is a delivery signal

It says the guest received the message and opened it. It stays whether or not
they answered, because that is the useful state: opened and unanswered means
chase gently, never opened means the phone is off or the number is wrong, so
reach out another way.

It is replaced the moment a dining status exists, because by then it says
nothing: a guest icon already means they answered, and a hotel icon already
means staff entered it. Verified 17 Aug that the tile and the villa sheet both
already behave this way. No change needed.

## Check-in at the desk

One screen, two starting states, same fields and same confirm. Not two flows.

**Form completed.** Reception sees the answers. Verifies the dietaries aloud,
verifies tonight's dining against the real menu, amends anything that changed,
presses confirm.

**Form not completed.** Reception fills it in with the guest, then confirms.

This is why the screen is edit rather than create, and why every arriving guest
ends the day confirmed.

---

## The principle

**A node has one writer. `responses` and `prearrival` hold only what a person
answered. Every fact about the booking is read from Mews, never copied.**

Two consequences that decide most of the questions below:

- The pre-arrival link may carry the guest's name and dates. Those are for
  **display only**. They are never written to the database.
- Mews is the authority not because the code defers to it, but because only the
  Worker writes the node it owns.

---

## Life of a booking

**Origin.** A reservation is made in Mews. Nothing else creates a booking.

**Sync.** Mews fires a Zap, the Worker writes `/bookings/<id>/pms` and one
`/stays/<date>/<villa>` row per night. Outside the sync window none of this has
happened and the app does not know the booking exists.

**The link.** GuestTouch sends the pre-arrival message, pulling from the
booking. It carries the booking id, first name, last name, arrival and
departure.

**The guest answers.** The page writes to `/bookings/<id>/prearrival`. It does
not require `pms` to exist: at seven days out it usually will not. The guest's
write contains their answers only. Not name, not villa, not dates.

**Display precedence on the guest page.** If `pms` exists, show from it, since
it is fresher than the link by definition. If not, show from the URL. Either
way the write is unaffected.

**The halves meet.** `prearrival` and `pms` are siblings under one booking id,
so they join with no lookup and no matching, whichever lands first. Mews
updates `pms` forever after and never touches `prearrival`. The guest can
revise `prearrival` and never touches `pms`.

**Booking flags, 26 Aug.** Short facts pinned under a guest's name - VIP,
Travel agent, Breakfast included. Three nodes, three owners, no exceptions
to the split above: `/flags` is the master list an admin edits on Flag
Settings (`flags.html`); `/bookflags/<booking id>` is the set the desk
ticked for one booking, admin-written, staff-readable; and `pms.rate` is the
Mews rate name the Worker carries, which by itself puts a Luxury Escapes
pill on a booking - that rate and no other, the owner's ruling. What a
booking wears resolves once, in `bookingFlagLabels` in `nala-shared.js`,
read by the desk and the Service Sheet alike.

**In house.** Boards read `/stays` for who is where and the booking node for
what they said. Staff can override to dining, not dining or vacant. A vacant
contradicting Mews warns first and holds until Mews next changes that booking.

**Departure.** Mews holds the record, the app stops showing them.

**Cancellation.** Clears the nights. The Worker handles this and is tested for
it. Confirmed 17 Aug that the Zap can be made to fire cancellations, which
removes what was the largest open risk.

---

## The mixed state is normal, not an edge case

On any given check-in day some guests will have completed pre-arrival and some
will not. That is exactly today's paper process: an email goes out, some reply,
reception prints what came back, and the chef receives a mixture.

So the app's normal condition is a board where some bookings arrived through
the guest and some purely through the Mews window. No code should treat either
as exceptional.

---

## Front Desk Arrival

A new page. Closes the gap the paper process never could.

**Why.** Today only some guests return the form, and the chef gets a handful of
handwritten sheets to decipher. If reception completes the rest at check-in,
the chef's screen is complete and typed before the guest reaches their room.

**What it does.** Lists today's arrivals. Shows who has completed pre-arrival
and who has not, because that is the receptionist's whole job on this screen.
Opens a guest, completes the same questionnaire, and sets dining or not for
tonight.

**Where it writes.** `/bookings/<id>/prearrival`. The same node the guest
writes to, so there is one shape and one place regardless of who typed it.

**It is edit, not create.** A guest who answered half the form should have
those answers on screen, not a blank one.

**No provenance field.** Decided against recording whether reception or the
guest filled it in. The chef reads one thing and does not care who typed it.

**It is not a new output.** The Reservations screen is the chef's screen and
already exists. Front Desk Arrival is an input path into it.

**Which means confirming has to write to `/manual`, not only to
`prearrival`.** The chef's board reads `/manual` and `/responses`; it has never
read `/bookings`. Built on 17 Aug, and it was missing until then: reception
could type "dining, two guests, nut allergy" and Reservations would still show
that villa as awaiting. The path stopped one step short of the person it exists
to serve.

The record goes to the night the guest arrives, in the shape the board already
understands, so nothing changed on the board side. Both writes succeed or the
guest is put back: a confirmation the chef never sees is worse than one that
visibly failed.

The nightly dinner request never goes out for an arrival night, because guests
check in after 2pm, so this write is the only thing that will ever put an
arriving guest on that board.

---

## Manual bookings

Staff can add a reservation by hand. These are **dinner reservations and get no
booking id**, because they are not Mews bookings. `/bookings` stays purely
Mews, one authority and one shape.

This also covers the handful of reservations predating the sync. There is no
backfill problem: only a few bookings need adding by hand, every new booking
lands through Mews, and by the time the app is finished it will hold current
bookings without a migration.

---

## Corrections to MEWS-AUDIT.md

**The old guest-written URL path is not running.** The audit's central framing,
that every fact about a guest has two live sources, describes code rather than
production. `index.html` parses `p`, `r`, `n`, `a`, `d`, but no link has
carried a phone. It was an earlier plan. The section headed "The old mechanism
and the new one now both run" describes one running mechanism and one set of
unbuilt intentions.

**Finding 1 was not live.** If no response ever carried a date, the precedence
bug could not fire. The merge ordering is now explicit and matches the design,
which is worth having, but it is defensive rather than corrective and the audit
called it corrective. The error was stating an inference from reading code as
though it were a measurement of production.

**`samePerson` is scaffolding for a problem that may not exist.** The phone
normalisation reconciles `+61400000000` with `0400000000`, a mismatch that only
arises if a link supplies a phone. None does. The name fallback carries a real
risk of matching two different guests, and it is risk taken for no benefit.
Once records carry a booking id the match is exact and the function goes.

**The lookahead does not block stage 3.** The audit said the pre-arrival page
could not show a guest their own booking at seven days out. The link carries
the name and dates, so it can. Widening the window is a boards question only.

**The `prearrival` rules change is wrong and must not be pasted.** It required
`pms` to exist before anyone could write `prearrival`, which blocks precisely
the guest-first case this design depends on. Reverted, and `rules.json` is back
to the state that is live.

**No backfill is needed.** The audit listed a `Colliding` backfill of in-house
guests. Manual entry of a few bookings covers it.

---

## Still open

- The write to `prearrival` is unauthenticated by necessity, since the guest
  cannot sign in. The practical guard is that a Mews reservation id is an
  unguessable GUID, so the exposure is garbage accumulation rather than data
  loss. A `.validate` bounding shape and size is worth adding. It cannot be
  tested here: there is no emulator in the sandbox, so any rules change is
  reasoned rather than verified and publishes straight to the live database.
- A `prearrival` written against a cancelled or mistyped booking id sits
  forever. Cheap to clear on the Worker's next event for that id.
- If GuestTouch fails to substitute a merge tag the guest sees `{{firstname}}`.
  Display only keeps it cosmetic rather than letting it reach the database,
  which is what the `debug.html` junk finder exists to catch.
- Name and dates in a URL is mild PII in an SMS and in browser history.
  Dropping the phone removed the sharp one.
- While `pms` is absent, nothing distinguishes a booking Mews has confirmed
  from one it has not yet seen. If reception ever needs to tell those apart,
  that is where to look.


---

## The id was wrong all along

Found 17 Aug, from two Zap runs for one booking: the `ID` field changed on
every event while `Mews Id` stayed the same. The Worker took `Id` first, so
**every event was filed as a brand new booking.**

That is the cause of all of it. One guest in three villas. A move never
clearing the villa it left. The duplicate finder reporting nothing, because the
three entries genuinely had three different ids. It was not the cancellation
feed, which is what I said twice.

**And no single field name is right.** Measured across three Zapier triggers:

| Trigger | Where the reservation GUID arrives |
|---|---|
| New reservation | `Id`, and there is no `MewsId` at all |
| Modification | `MewsId`. `Id` is Zapier's own 32 character key |
| Cancellation | `Id` |

So the first correction, "always use Mews Id", was also wrong: on a new
reservation that field does not exist.

The Worker takes **whichever value is a GUID**, because the shape is consistent
even when the name is not. Every Mews identifier has dashes; Zapier's key is 32
hex characters without. Anything that is not a GUID is refused with a message,
so a bad mapping fails loudly rather than quietly creating bookings.

The Zap should send both `Id` and `MewsId` and let the Worker choose.

Also in that list and worth mapping later: **Customer Id**, the guest across
all their stays, and **Group Id**, the party.

## One party can hold several villas

A family booking two villas is **two reservations under one group**. Each villa
gets its own reservation id, its own answers and its own registration card,
which is right: two villas need checking in twice.

What was missing is that nothing showed they were one party. Mews sends a
`groupId` and the Worker already stored it, just not where the boards could see
it. It is now on every night, and Front Desk Arrival says "with villa 8" on the
row so reception knows before they start.

**It cannot tell a two villa booking from a guest who was moved.** Both look
like one group across two villas with overlapping dates. Only a cancellation
separates them, which is why the cancellation feed matters more than any of
this. Seen live on 17 Aug: moving a booking in Mews created a NEW reservation
id, and the old one stayed on the board because its cancellation never arrived.

## The moved guest has three homes, not one

A guest moved between villas after Mews first sent the booking leaves a record
behind in the villa they left. It has happened in three places and each needed
its own fix:

- `/stays`, fixed in the Worker by clearing what is actually there rather than
  trusting a remembered villa
- `roomguests`, fixed in `overlayStays`, which drops any other villa holding
  the same person
- **the dinner cell**, fixed 17 Aug in `dinnerElsewhere`: a cell whose booking
  id the PMS places in a different villa is stale and is not read

The dinner cell one was introduced the same day the cell was, and found by
being asked about it rather than by any test. Anything new that stores a fact
against a villa needs the same question asked of it.

It drops the answer rather than moving it. Moving would guess that a booking
made for one villa still holds for another, and a villa change usually comes
with a change of party or plan. The empty villa on the board is telling
reception to ask again.

## The scheme

**The booking id is the only identifier for a guest. The date and the villa
identify a night and a place, not a person.**

Which gives three kinds of record, and each answers a different question:

**Per booking**, keyed by booking id, lasting the whole stay:
`/bookings/<id>/pms` from Mews, and `/bookings/<id>/prearrival` for what the
guest told us that has no date attached: dietaries, purpose, occasion, wellness,
arrival time. **No `dining` field.**

**Per night**, keyed by date and villa, one cell per villa per night:
the dinner answer, with `by` recording who set it and `at` when. Whether the
guest tapped it from a link, answered it in pre-arrival, or reception typed it
at the desk, it is the same cell. `roomRecord`'s precedence merge disappears,
because there is nothing left to merge.

**Per night, operational**, unchanged: `/hk/<date>/<villa>` and
`/combined/<date>/<gid>`. These are about the villa and the table, not the
guest.

`/guests/<phone>` keeps standing dietaries across separate stays and is the one
place a phone is still a sensible key, because it is the only thing that
outlives a booking. It stops holding a name, villa or dates.

**Every link carries `?b=<booking id>` and nothing that identifies the guest.**
Name and dates may ride along for display and are never written.

---

## Done 17 Aug

`guests`, `roomguests` and `responses` are the old scheme, keyed on a phone
number or written by a guest page. Nothing has written them since 17 Aug: the
dinner cell replaced `responses`, and Mews records who is in a villa through
`stays`. They are admin write only now, and kept readable so the boards can
fall back while old dates age out. Delete the nodes and their rules once no
date in the look-back window still uses them.

Note for anyone editing `rules.json`: Firebase rejects a plain string value
anywhere in it. Every key must be a rule such as `.read` or a node whose value
is an object. A comment key breaks the whole file, which is why this note lives
here instead.

- `welcome.html` takes a booking id and writes nothing at all. It was the last
  guest page reading a phone out of a link, and it wrote both `/guests` and
  `/roomguests` on every open. The merge-tag test panel went with it.
- `/guests`, `/roomguests` and `/responses` are no longer world writable. They
  are admin write only now, kept read-only so the boards can fall back while
  old dates age out.
- `/extcancel` removed from the rules entirely. It was world writable and
  nothing used it: those keys live inside `/manual`.
- **One world writable node remains, and it has to:**
  `/bookings/<id>/prearrival`, because a guest cannot sign in.
- Diagnostics can find and clear a booking left in two villas. It only offers
  to delete the villas Mews disagrees with, and lists the rest untouched rather
  than guessing.

## What this costs

- `index.html` and `welcome.html` take a booking id, and the reply panel stops
  depending on a phone being in the URL
- `responses` and `manual` collapse into one node, which removes `roomRecord`'s
  precedence rules, the `override` flag, and `samePerson`
- `prearrival.dining` goes, and the guest form writes the dinner cell for the
  arrival night directly
- The `/manual` bridge in Front Desk Arrival goes with it
- The enumerable hole closes as a side effect: a booking id is an unguessable
  GUID, a phone number is not
- `roomguests` retires, and with it `resolveRoomGuests`, `resolveRoomGuestsHK`
  and the date tolerance in `parseDepDate`

This is Stage D, and it is a rewrite of how the app identifies a guest rather
than the page edit the original plan described.

---

## The one thing that decides the shape

**Can a guest change their dinner answer after reception has confirmed it at
the desk?**

With one cell this is a real question rather than a precedence rule. Either the
cell carries a lock after confirmation, or it is last writer wins with `by`
recording who. It changes what gets built, so it is worth answering before I
start rather than after.


---

## Widths, measured

The app has **no width media queries at all**, only print and height ones, so
nothing had ever been checked below the 390pt iPhone the styleguide mocks at. I
measured the four boards at 390, 360 and 320.

| Page | 390 | 360 | 320 |
|---|---|---|---|
| Tonight's Numbers | ok | ok | ok |
| Cleans | ok | ok | ok |
| Service Sheet | scroller | scroller | scroller + **stat bleed** |
| Clean Sheet | scroller | scroller | scroller |

**360pt Galaxy needs no work.** Everything that fits an iPhone fits a Galaxy.
The layout is fluid rather than breakpointed, which turns out to be why.

"scroller" is not a fault. The two printable sheets put their wide table in
`.scroller { overflow-x:auto }` deliberately, because they are A4 sheets read
on a phone. The page itself does not bleed.

**One real finding. ~~At 320pt only.~~ Fixed 18 Aug, and it was not 320 only.**
The Service Sheet header stats pushed past the right edge, so the whole page
scrolled sideways. Re-measured 18 Aug with a full mixed house: the make-up
grows with the number of party sizes and was set never to wrap, so it ran to
397pt and bled at 390 and 360 as well. The original measurement used a tidy
house where the string is short, which is the lesson worth keeping: a width
check is only as wide as the fixture behind it.

**So the standard becomes: mock at 390, check at 360, and do not break at 320.**
Front Desk Arrival is the first screen built to that from the start.

---

## Built 17 Aug: Pages, the site map

`pages.html`, admin only, in the hamburger. Every page in the app as a live
link, grouped by tier, with a note on what each is for and which need a link or
a sign in.

Its suite does the thing the page exists for: it opens every link it lists and
confirms the file is served, and it checks the reverse too, that no page exists
in the repo which the map fails to mention. A hand written map rots the first
time somebody ships a page and forgets it, and a map that lies is worse than
none, because it is what you check when you are already unsure.

`list.html` and `housekeeping.html` still need Pages and Front Desk Arrival
added to their nav dropdowns.

## To build

### 1. Pre-arrival questionnaire, guest. BUILT 17 Aug

`prearrival.html?b=<id>&n=<first>&s=<last>&a=<arrive>&d=<depart>`

Guest tier, no sign in. Four questions, chosen because they fit one phone
screen without scrolling and completion rate is the whole point: type of stay,
dining on the arrival night, allergies and dietary requirements, estimated
arrival time. Arrival time is the only one that feeds the Cleans board rather
than the kitchen, since it says which villa has to be ready first.

Writes to `/bookings/<id>/prearrival`. Never writes name, villa or dates: those
come from the link for display and from Mews for truth. Works before Mews has
the booking, which is the normal case at seven days out.

**Every question on the form is mandatory.** So a submitted form always
carries a dining answer, and "form done but the dinner question unanswered"
cannot happen. That state was designed for and then removed once the rule was
known.

**Which makes no form a tentative yes, not an unknown.** The kitchen cooks for
it: oversupplying is the cheap mistake and undersupplying is not, and reception
settles it at check-in either way. So on Front Desk Arrival every guest carries
a fork icon, and grey means assumed dining and still to be pinned down rather
than ignore this one. The kitchen's planning number is dining plus not sure;
only not dining is genuinely off the list. The three are still counted
separately because how firm a number is matters as much as the number.

**Answers are written on submission only, never as the guest types.** A
half-written record is indistinguishable from a considered one, so "Form done"
would come to mean "some fields exist" and reception would stop trusting it.
Incomplete guests are finished at the desk anyway, so a partial record adds a
state without adding an action. If losing a long form to a dropped connection
turns out to matter, save a draft on the guest's own phone rather than writing
partial records to the database: it costs nothing and creates no status.

**But the page MUST stamp an opened time when the guest lands on it**, separate
from submitting. Without it there is no way to tell a message that never
arrived from one that arrived and was ignored, and those need different
chasing: a wrong number needs another channel, an ignored message needs a
nudge. This mirrors what the dinner flow already has and the pre-arrival flow
does not.

Worth being precise, because it has been confused once already: the link icon
on Tonight's Numbers belongs to the NIGHTLY dinner message and is written when
a guest opens `index.html`. It says nothing about pre-arrival. The two sends
are separate and need separate signals.

**Estimated arrival is a picklist, not free text.** Six slots in the order
reception works through them: Before 2pm, Approx 2pm, 3pm, 4pm, 5pm, After 5pm.
The two open ended ones carry a compulsory note, because "before 2pm" with no
time is the answer that causes the problem it is warning about.

Stored as the slot key, so the arrivals list orders exactly. Free text was
tried first and it reads "late morning" and "after 5pm" correctly often enough
to be trusted and wrongly often enough to matter, which is the worst
combination.

Built as six required questions plus two optional ones. Purpose of visit is
the multi select, and it is advisory only. Special occasion and "anything else"
are NOT required: the live form does not star them, and forcing free text is
the fastest way to lose a completion.

**One thing still to write:** the help line under the first night question. The
guest is answering before that night's menu exists, so something has to stand
in for it. There is a marked placeholder in the page.

Resist a fifth question without deciding which of the four it replaces.

### 2. Front Desk Arrival, reception

New, specified in conversation on 17 Aug.

Lists today's arrivals and shows at a glance who has completed pre-arrival and
who has not, because that is the receptionist's whole job on this screen.
Opens a guest, completes the same four questions, and sets dining or not for
tonight.

Writes to the same `prearrival` node the guest writes to, so there is one shape
and one place whoever typed it. It is edit rather than create: a guest who
answered half the form should see those answers, not a blank one. No record of
who filled it in.

Settled 17 Aug: the arrival night's dining answer comes from pre-arrival, not
from the nightly text, because guests check in after 2pm and the text would
arrive too late. Reception shows the guest the real menu at the desk and
confirms the answer still holds. Every arriving guest ends the day confirmed,
and confirmed includes not dining. See `GUEST-DATA.md`.

This is an input path into the Reservations screen, which is the chef's screen
and already exists. It is not a new output.

**Confirming and checking in are two buttons and two fields.** Confirm verifies
the answers and leaves the guest under Arriving. Confirm and check in does the
same and moves them to Arrived. They are not one event: reception can verify on
the phone the day before and the guest turns up hours later, so the sections
follow arrival rather than confirmation.

`checkedInAt` is only ever set, never cleared. A guest who has arrived has
arrived, and editing their answers afterwards must not un-arrive them.

FUTURE: check in is where the Mews reservation moves to Checked in, through the
Connector API. Nothing writes back to Mews yet, so until that exists the app is
the only record that a guest has arrived. The hook is marked in
`front-desk.html`.

Closes the gap the paper process never could: today only some guests return the
form and the chef gets handwritten sheets.

### 2b. Allergy conflict at the desk. BUILT 17 Aug

The mechanic that already exists: the chef publishes a menu and tags which
dietaries each dish conflicts with, per day, at `/menutags/<date>`. When a
guest opts in for dinner and selects one of those dietaries, the guest page
flags it, tells them the menu contains it, and requires a note before the reply
will save. That is live today in `index.html` and covered by `index_suite.py`.

**Pre-arrival cannot do this, and that is the gap.** The form is filled days
ahead, when the menu for the arrival night does not exist yet. A guest can
declare a nut allergy and opt in for dinner on their arrival night and nothing
can be checked, because there is nothing to check against.

**On the day of check-in the menu IS live.** So Front Desk Arrival should
compute the conflict between the guest's declared allergies and that day's
published tags, and show it to the receptionist. It is the same comparison,
run at the one moment when both halves finally exist. The receptionist raises
it with the guest standing in front of them, which is a better conversation
than a warning on a phone days earlier.

How it was resolved, since the plan called for moving `menuConflicts()` out of
`index.html` into `nala-shared.js` and that turned out to be wrong:

`index.html` does not load `nala-shared.js` and must not. It is guest tier, and
a shared function would drag staff code onto a guest page. So Front Desk
Arrival compares the guest's dietaries against `/menutags/<date>` directly,
which is the same node the guest page's tags come from. Two comparisons, one
source of truth. Change what a conflict means and both have to change, which is
what keeps them honest.

The desk version names the course rather than the dish, because it does not
read `menu.json`. Reception is holding the menu, so "tonight's main contains
Nut allergy" is enough to start the conversation.

It warns and does not block. The guest page requires a note before saving;
reception is talking to the guest and can settle it out loud.

### 3. Registration cards, print. BUILT 17 Aug

`registration.html`, `tests/reg_suite.py`, 22 assertions. One card per arriving
villa, one page each.

An unanswered question prints as a **rule to write on**, not as blank space.
The card is the working document at the desk, so a gap has to be writable. A
guest who sent nothing gets eight rules and their name and stay still printed,
because Mews knows those.

It carries the menu conflict too, and here it earns its place twice over: the
card goes to the kitchen, and the kitchen is who acts on it.

Not built: editing on the card itself with a save. Front Desk Arrival already
edits and confirms, so a second editor for the same data would be two ways to
change one thing. Worth deciding rather than assuming: if reception works from
paper and types it up later, that is a different design from confirming at the
screen.

### 4. Write back to Mews

Not a screen. Selected answers appended to the reservation Notes through Update
reservation, so front desk staff working in Mews see dietaries without opening
the app. Free text, so nothing can query it, which is accepted. The app stays
the source of truth.

---

## Not a screen, but queued ahead of some of these

The guest page rewrite, stage 4. `index.html` and `welcome.html` take a booking
id, `responses` re-keys to it, and the URL parsing goes. Its real size is in
`MEWS-AUDIT.md` under the two paths section, and it is larger than the one line
the handover gives it.

---

## Order

Front Desk Arrival before the guest questionnaire, on the grounds that it is
unblocked and the questionnaire is not. Both use the same four questions and
write the same node, so building reception first settles the shape and the
guest page inherits it. If the picklist answer arrives first, that reverses.

Registration cards after both, since they print what those two collect.

Write back last, as planned.
