# Identifiers: what is in use, and what it should be

17 Aug. Written after four rounds of asking a question the repo could have
answered. This is the answer, from the code, not from memory.

---

## The problem, stated once

**Four different things identify a guest, depending on which file you are in.**

| Identifier | Where it is used |
|---|---|
| Phone number | `responses`, `guests` |
| Villa number | `manual`, `roomguests`, `hk`, `stays` |
| Booking id | `bookings`, and the guest's pre-arrival link |
| Date | the partition key on all of the above |

None of them is wrong on its own. The problem is that a booking is identified
one way in one file and another way in the next, so nothing joins without a
lookup, and every join is a place two records can disagree.

---

## Every URL parameter in the app, measured

| Page | Reads | Meaning |
|---|---|---|
| `index.html` | `p` `r` `n` `a` `d` | phone, villa, name, arrive, depart |
| `welcome.html` | `p` `r` `n` `a` `d` `t` | the same, plus a test flag |
| `prearrival.html` | `b` `n` `s` `a` `d` | **booking id**, first, last, arrive, depart |
| every staff page | `date` | the day being viewed, from the shared header |

**Two schemes, and they do not overlap.** `prearrival.html` is the only page
built after the booking id existed. The other two predate it and expect a phone.

Consequence, from `index.html:833`: **no phone in the link means no reply panel
at all.** The guest sees the menu and cannot answer. So the nightly dinner path
requires a parameter the new scheme does not send.

---

## Every database path, and what keys it

| Path | Keyed by | Written by |
|---|---|---|
| `/responses/<date>/<phone>` | **phone** | `index.html` |
| `/guests/<phone>` | **phone** | `index.html`, `welcome.html` |
| `/roomguests/<date>/<villa>` | villa | `index.html`, `welcome.html` |
| `/manual/<date>/room-<villa>` | villa | `tally.html`, `cleaners.html`, `front-desk.html` |
| `/hk/<date>/<villa>` | villa | `cleaners.html` |
| `/combined/<date>/<gid>` | group id | `tally.html` |
| `/stays/<date>/<villa>` | villa | the Worker |
| `/bookings/<id>/pms` | **booking id** | the Worker |
| `/bookings/<id>/prearrival` | **booking id** | `prearrival.html`, `front-desk.html` |

---

## One dinner answer, three cells

For one villa on one night, the answer to "are you eating with us" can live in:

1. `/responses/<date>/<phone>` when the guest replies to the nightly link
2. `/manual/<date>/room-<villa>` when staff enter it
3. `/bookings/<id>/prearrival.dining` when the guest answers pre-arrival

One and two are inherited, and `roomRecord` exists to merge them by precedence.
**Three is new, added on 16 and 17 Aug, and it was a mistake.** It should never
have been a separate field: a dinner reservation is a dinner reservation
whoever set it.

The `/manual` write added to Front Desk Arrival on 17 Aug bridges one and three.
It works and it is the wrong shape. Under the correct model there is nothing to
bridge.

---

## Built 17 Aug

The dinner cell exists at `/dinner/<date>/<villa>`. Every board reads it,
reception writes it at the desk, and the guest page writes it from a link
carrying `?b=<booking id>`.

`index.html` no longer reads or writes anything keyed on a phone. It does not
write `/roomguests` either: Mews records who is in a villa now, through
`/stays`, and it does that for guests who never open their link.

A cell set by staff cannot be changed by a guest. That is enforced twice, in
the page and in the rules, because a hidden button is not a rule.

Still to retire, once no live data depends on them: the `/responses` and
`/manual` fallback in `roomRecord`, `roomguests`, and `samePerson`. Both old
nodes partition by date, so they empty themselves as the days pass.

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
