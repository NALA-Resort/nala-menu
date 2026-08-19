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

---

## The model to build towards

Decided 19 Aug. Four notes, and no others.

| # | Note | Comes from | Belongs to | Who may read it | Who may edit it |
|---|---|---|---|---|---|
| 1 | **Internal** | Mews, then edited here | the reservation | management only | management only |
| 2 | **Guest note** | the pre-arrival form | the reservation | staff and the guest | the guest, and the desk |
| 3 | **Dietary** | anywhere it is asked | the **person** | staff and the guest | anyone who may edit a guest |
| 4 | **Dinner note** | tonight's service | **one night** | staff | anyone editing tonight |

Rules that fall out of it:

- A dinner note is only ever offered where a dietary note is also offered, so
  nobody types an allergy into the wrong box for want of finding the right one.
- A dietary outlives the booking. A guest who comes back is not asked again.
- An internal note is never shown to a guest, on any screen, in any state.

### What each one needs

**1. Internal notes: not built, and the obvious place is wrong.**
`/bookings/<id>` has `".read": true`. Anything under it is readable by anybody
holding a pre-arrival link, which is the whole point of that node: the guest
form reads it without signing in. An internal note stored there would be one
URL away from the guest it is about.

So it needs its own node outside `/bookings`, readable only by staff. That is a
rules change and cannot be avoided by putting it somewhere convenient.

It also needs the sync to stop deleting it. `notes`, `notesType` and
`guestNotes` are sent as null on every write, so any edit would be wiped by the
next Mews event for that booking. The sync should write the Mews note ONCE, on
first sight, and never overwrite an edited one: otherwise a manager's
correction survives until the guest changes their booking.

**2. Guest note: built.** `prearrival.note`, written by both forms, lives with
the booking. Nothing to do.

**3. Dietary: built in the wrong place, twice.** It is on the booking
(`prearrival.dnote`) and on the night (`dinner/<date>/<villa>/dnote`), and the
reservations board writes only the night, so a dietary typed there is gone at
midnight. Belonging to the PERSON needs a third home: `customerId` is already
collected on every booking for exactly this and nothing reads it yet.

Two steps, and the first is worth doing on its own: make every screen write the
dietary to the booking, then move it to the customer.

**4. Dinner note: built.** `dinner/<date>/<villa>/note`, expires with the date.

### What has to go

- `manual/<date>/<key>/note` is a second dinner note from before the one cell
  existed. Same lifetime, same purpose, one of them is enough.
- `prearrival.arriveNote` is not one of the four. It is part of the answer to
  when are you arriving rather than a note about the guest, and it should keep
  living beside `arriveSlot` rather than being counted here.

---

## Where it got to, 19 Aug

**1. Internal notes: built.** Live at `/internal/<booking id>`, a node outside
`/bookings` because that one is world readable. Rules restrict both reading and
writing to admin and staff; the sync may seed but a waiter cannot see one at
all, which is asserted rather than assumed. The Mews note is read for the first
time and written ONCE, on first sight, into its own `fromMews` field, so a
manager's rewrite survives the next event for that booking and the original is
still there underneath. Editable on the front desk sheet, management only, and
saved separately from the guest's answers: management's private record failing
must not roll back the service's.

**2. Guest note: was already right.** No change.

**3. Dietary: done.** It now lives in three places on purpose, and the
distinction between them is the whole point:

- the **night** (`dinner/<date>/<villa>/dnote`) is what tonight's service
  reads, and expires with the date;
- the **booking** (`prearrival.dnote`) is what every screen reads and edits;
- the **person** (`guests/<customerId>`) is what outlasts the booking.

Every screen that edits a dietary now mirrors it to the person, and the sync
seeds a newly seen booking from what the person already told us, so a returning
guest is not asked twice. Seeded only when the booking has no answers of its
own, or last year's answer would overwrite what somebody just said.

The mirror is quiet and separate from the save everywhere it appears: a guest
record failing to write must never cost the evening its answers.

**4. Dinner note: was already right.** No change.

**Still to remove:** `manual/<date>/<key>/note`, the second dinner note from
before the single cell. Nothing writes it now except older records, so it can
go once those have aged out with their dates.

---

## Decided against: a dietary per person

Asked 19 Aug, and answered no on the same day. Attaching dietaries to each
guest separately would mean the companion needs their own record, keyed on
their own Mews id, and every screen would have to ask which of them a dietary
belongs to before it could store one.

It is not worth it. A dietary stays with one of the two guests in practice, and
a short note saying whose it is answers the question in the time it takes to
type four words. The dietary note field already holds exactly that, and the
front desk sheet has carried "the daughter, severe" as its example since it was
written.

If this is ever revisited, the thing that changed will be that somebody needed
to filter or count by person, not that the note was unclear.

---

## Where notes and dietaries are DISPLAYED

Added 19 Aug after a report that dietaries vanished on tomorrow's board. The
storage audit above was not enough: what a screen SHOWS depends on which of the
three copies it reads, and they do not agree.

| Screen | Dietaries read from | Falls back to the booking? |
|---|---|---|
| Reservations board, tile and comment sheet | the night's dinner cell | **no** |
| Reservations board, Edit details | the night's dinner cell | **no** |
| Front desk sheet | the cell **if it exists**, else the booking | yes |
| Reservation sheet (print) | the night's dinner cell | **no** |
| Registration card | the booking | n/a |
| Guest pre-arrival form | the booking | n/a |

**That is the bug.** The dinner cell exists only for a night somebody has
answered. On tomorrow's board there is no cell, so the reservations board and
the printed sheet show no dietaries at all, and Edit details opens with the
allergy chips blank. The front desk is the only screen that already falls back,
which is why it looked right there and nowhere else.

A dietary is not a fact about a night. Reading it from the night is the mistake,
and it is repeated on three screens.

### What it should be

One rule, everywhere: **the booking is the source, the cell is an override for
tonight only.** Read the cell if it has dietaries, otherwise the booking, which
is exactly what the front desk already does and what the other three do not.

The guest's own form should prefill from the booking too, which is seeded from
`/guests/<customerId>` by the sync, so a returning guest opens their dining
request with their allergy already ticked.

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
