# Where notes about a guest live

Written 19 Aug, from the rules and the code rather than from memory.

The question that prompted it: a dietary note is not a thing that should expire
overnight, and some of them do. This is every place free text about a guest is
stored, what it is for, and how long it lasts.

---

## The six places

| # | Where | Field | Written by | Lives for |
|---|---|---|---|---|
| 1 | `/bookings/<id>/prearrival` | `dnote` | guest form, front desk | the **booking** |
| 2 | `/bookings/<id>/prearrival` | `note` | guest form, front desk | the **booking** |
| 3 | `/bookings/<id>/prearrival` | `arriveNote` | guest form, front desk | the **booking** |
| 4 | `/dinner/<date>/<villa>` | `dnote` | front desk, reservations board | **one night** |
| 5 | `/dinner/<date>/<villa>` | `note` | front desk, reservations board | **one night** |
| 6 | `/manual/<date>/<key>` | `note` | reservations board, older writes | **one night** |

Nothing is stored under `/stays`, `/hk`, `/responses` or `/menutags`. `/hk` has
no free text at all: the Cleans board records marks and times, never sentences.

---

## What is actually wrong

**The same dietary note exists in two places with two different lifetimes.**

`prearrival.dnote` belongs to the booking and follows the guest across every
night of their stay. The dinner cell's `dnote` belongs to one night and is gone
at midnight with the rest of that date.

The front desk writes both, so a dietary recorded there survives. **The
reservations board writes only the night cell.** A dietary note typed there is
correct this evening and gone tomorrow, and nobody is told, because the guest
still has a booking and the board still looks right. That is the bug behind the
question.

The same is true of the general `note`, and it matters less: a note about
tonight's table genuinely is about tonight.

**Mews notes are discarded on purpose.** The sync sends `notes`, `notesType`
and `guestNotes` as null on every write, so whatever a receptionist typed into
Mews never reaches this app. That was a deliberate choice about scope, not an
oversight, but it means Mews and the app can hold different facts about the
same guest and neither shows the other's.

---

## The distinction worth naming

Not per night against per stay. **What the note is about.**

- **A dietary** is about the person. It is true next year. It should outlive
  the booking, not merely the night, and today it does not: a returning guest
  arrives with an empty record and is asked again.
- **A preference** is about the person for this stay. Quiet villa, late
  riser. True for the whole booking.
- **A service note** is about tonight. Table by the window, celebrating at
  dinner. It should expire, and it does.

Three lifetimes, and the app currently has two, with the dietary in the wrong
one on one of the two screens that writes it.

---

## What to do, in order

1. **Make the reservations board write the dietary to the booking**, as the
   desk already does. One line, no rules change, and it stops the loss that
   prompted this. Everything else can wait behind it.
2. **Give each note a type** rather than inferring it from where it sits:
   `dietary`, `preference`, `service`. Same field, an extra key, so a screen
   can show the dietaries a guest has had for years and the note somebody left
   about tonight, without either pretending to be the other.
3. **Decide whether a dietary should outlive the booking.** It should, and it
   needs somewhere to live that a booking id cannot reach: `customerId` is
   already collected on every booking for exactly this kind of thing, and
   nothing reads it yet.
4. **Decide about Mews notes.** Either read them, or write down that we do not,
   somewhere a receptionist will see. Silently holding a different set of facts
   to the PMS is the version that goes wrong.

Steps 3 and 4 are decisions, not code. Step 1 is a fix and should not wait for
them.
