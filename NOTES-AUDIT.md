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

Decided 19 Aug. Four notes, and no others. **Superseded on 20 Aug: five
names, and two renames. See "The five names" below. The data model here
still stands; the names and the arrival note do not.**

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

---

## The four notes, in plain words

Written 19 Aug after the shorthand in this document caused more confusion than
it saved. Three names are used below and nowhere else:

- **the night** is `/dinner/<date>/<villa>`. One record per villa per evening.
  It exists only once somebody answers for that date. Tomorrow is a different
  record and next week is another.
- **the reservation** is `/bookings/<id>/prearrival`. One record per booking.
  It lasts the whole stay and ends when the booking does.
- **the guest** is `/guests/<customerId>`. One record per person in Mews. It
  survives the booking ending, so it is still there next time they come.

### Where each of the four belongs

| Note | Belongs to | Why |
|---|---|---|
| Internal | the reservation | management's record of this stay |
| Guest note | the reservation | what they told us before this stay |
| **Dietary** | **the guest** | true of the person, not of an evening |
| Dinner note | **the night** | true of one evening only |

### The dinner note is the one that SHOULD expire

An example, and it is the reason the distinction matters. The menu goes out and
it is spicy meatballs. The guest has no allergy at all, but does not like heat,
so they ask for the spice on the side. That is true of tonight's dish. It must
not follow them to tomorrow, when the menu is something else, and it must not
be waiting for them next year as though it were a standing requirement.

A dietary is the opposite. There is no such thing as tonight's allergies being
different from the guest's allergies. There is **one list per person**. It is
shown to them for approval, they correct it if it is wrong, and it is the same
list on every screen and every night.

### What is actually wrong

Dietaries were stored beside the dinner note, on the night, so they inherited
its lifetime. Everything follows from that one mistake:

- three screens read dietaries from the night, so tomorrow shows none;
- the same list can disagree with itself between two dates;
- a returning guest starts empty, having told us already.

### The chain it should be

**guest → reservation → every screen.**

The sync seeds the reservation from the guest record. The guest approves or
corrects it on their pre-arrival form. Every screen reads that one list. The
night holds the dinner note and the dining answer, and no dietaries at all.

There is no case where the night should win. That was written down as a caution
on 19 Aug and it was wrong: it assumed an allergy could be true tonight and not
tomorrow, and no such thing exists.

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

---

## The five names

Decided 20 Aug, in conversation. This section supersedes the NAMES above, not
the data model: nothing moves, nothing changes lifetime. Two renames and one
promotion.

| Name on screen | Field | Belongs to | Guest may read it? |
|---|---|---|---|
| **Booking notes** | `prearrival.note` | the reservation | yes, they wrote it |
| **Arrival notes** | `prearrival.arriveNote` | the reservation, dead at check-in | yes, they wrote it |
| **Staff notes** | `/internal/<booking id>` | the reservation | **never** |
| **Dietary notes** | `dnote`, guest → reservation → night | the person | yes |
| **Dinner notes** | `dinner/<date>/<villa>/note` | one night | no |

- **Internal → Staff notes.** Same node. The old name said where
  it lived; the new one says who it is for, which is the thing a receptionist
  needs to know while typing. Decided 20 Aug: the note is the whole team's.
  EVERY staff login reads it and writes it, from the front desk and from the
  board's name dropdown alike, because the chef holding the phone at service
  is exactly who it is for. The rules fence one boundary only: staff against
  guest. A guest can never read it. (Rules change of 20 Aug needs its paste
  into the Firebase console before the wider read works live.)
- **Guest note → Booking notes.** "Guest notes" survived one morning: it reads
  as notes ABOUT the guest, and staff type into this field too. Booking notes
  is what it is: free text that lives the length of the booking.
- **Arrival notes, promoted.** The 19 Aug decision said arriveNote "is not one
  of the four" and only part of the arrival answer. Half right: it is arrival
  data with words attached, but it IS free text a guest writes, so it gets a
  name. It keeps its own field because it has a different lifetime to Booking
  notes: nobody needs "ferry lands 3pm" on day four.

### The two rules every screen must follow

Decided 20 Aug after "booking comment one, booking comment two" had to be
typed into live fields to find out where they surface. That must never be the
method again.

1. **Every input that takes a note carries its name as a visible label.** A
   placeholder is not a label: it vanishes the moment the box has text in it,
   which is precisely when someone needs to know what the text is. The board's
   three editors are the standing offenders.
2. **Every place a note is displayed carries a heading saying which note it
   is.** No orphan quotes. A bare "Notes" heading is half an answer; the
   heading is one of the five names.

And a working rule for conversation, same date: "notes" or "comments" without
one of the five names in front of it gets a clarifying question, not a guess.
"Comments" has meant the dinner note on the board and the general note in the
bubble, which is exactly how the ambiguity started.

### Where guest free text may travel

Decided 20 Aug. Free text typed by a guest on the pre-arrival form stays on
the pre-arrival form and the front desk, with **one exception: the dietary
note**, which must reach the kitchen because Other means read the note.

- **Booking notes** come OFF the reservations board row and the printed
  list's comment column. The chef does not need the guest's private context
  on a dinner row. They remain readable from the board through the bubble and
  the snapshot panel, under their own heading.
- **Arrival notes** appear on the arrivals views only, beside the time.
- **Dietary notes** travel exactly as dietaries do: person, reservation,
  every screen.

### The bubble

One bubble per row, as today, because the column's width is already balanced
around it. The colour carries the meaning, worst state wins:

| Colour | Means | Contains |
|---|---|---|
| none | nothing to read | — |
| **grey** | context, not kitchen | Booking notes |
| **amber** | kitchen content, complete | dietaries, Dietary notes, Dinner notes |
| **red** | alarm, act before cooking | Other with no note written, a menu conflict with tonight's dishes |

Red stays what it is everywhere else in the app: something is wrong. A normal
allergy, properly recorded, is amber. The popover it opens keeps its sections,
each under one of the five names, and carried-over DIETARIES leave the
"Previous dining notes" section: a dietary is person-level now, so showing it
as "not confirmed for tonight" contradicts the row above it. Notes from
another night keep the warning; the dietaries move up into the current list.

### What this costs, screen by screen

The audit behind this, 20 Aug. What exists today against the two rules:

| Screen | Field | Today | Needed |
|---|---|---|---|
| Pre-arrival | `note` | under "Anything else?", unnamed | titled Booking notes |
| Pre-arrival | `etaNote` | placeholder only | titled, Arrival notes |
| Pre-arrival | `dietNote` | placeholder only | titled, Dietary notes |
| Front desk sheet | `fNote` | labelled Guest notes (unpublished) | relabel Booking notes |
| Front desk sheet | `fEtaNote` | under "Arriving", unnamed | titled Arrival notes |
| Front desk sheet | `fInternal` | labelled Staff notes (unpublished) | done |
| Front desk summary | `note` | heading "Notes" | heading Booking notes |
| Board, three editors | `xNote`, `xDnote` | placeholder only | visible labels above both |
| Board, booking row | dinner note | bare quote, no label | comes off the row (bubble instead) |
| Board, booking row | booking note | printed on row | comes off the row (bubble instead) |
| Board, snapshot panel | `note` | heading "Note" | heading Booking notes |
| Board, bubble | previous section | mixes old dinner + dietary notes | split under their names, dietaries out |
| Printed list | column head | "Dietaries & comments" | "Dietaries & dinner notes" |
| Registration card | `note` | heading "Notes" | heading Booking notes |

Housekeeping's "Manager notes" and "Housekeeper notes" are handwriting lines
on a printed sheet, never stored, and are left alone.

### Order of work

1. Labels and headings, all fourteen rows above. Boring, low risk, no
   behaviour change.
2. Booking note off the board row and the printed list, into the bubble under
   its own heading. Small, with tests.
3. Bubble colours. The fiddly one: "what is kitchen content" gets computed in
   ONE place and tested first, because three screens will want the answer.
