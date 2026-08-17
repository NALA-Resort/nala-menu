# Guest data: where it comes from and who owns it

Settled 17 Aug, in conversation, after the audit written the same night got
several things wrong. Where this and `MEWS-AUDIT.md` disagree, this is right.
The corrections to the audit are listed at the end.

Nothing here has been observed running. It is the design as agreed, and the
previous document's mistake was presenting exactly this kind of reasoning as
though it had been measured. Anything below marked as a fact about production
came from the user, not from the database.

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
