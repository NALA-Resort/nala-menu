# Plan of attack

17 Aug. Everything open, in one order. Consolidates `MEWS-AUDIT.md`,
`GUEST-DATA.md`, `SCREENS.md`, `GAPS.md`, `MORNING-17-AUG.md` and the
`HANDOVER.md` backlog. Where any of those disagree with this, this is newer.

Marked **[you]** where it cannot be done from a chat, **[me]** where it can,
**[print]** where the parallel chat owns the file.

Ordering rule: nothing gets built on top of something about to be rewritten,
and nothing waits on an answer it does not need.

---

## Stage A. Six answers, all parallel, none blocking each other

Start these now because later stages wait on them, not because they are urgent
in themselves.

- **[you]** Can Zapier run an hourly schedule trigger that pings the Worker with
  an empty payload? Without it, silence cannot be told from a quiet week.
  Roughly 720 tasks a month, daylight only if that is too many
- **[you]** Does Mews send true UTC in the `Utc` fields, or local time? One
  evening check-in in the Zap history. Decides whether late arrivals are
  recorded on the wrong night
- **[you]** Type of stay: picklist or free text, and if picklist, what is on it.
  Blocks Stage E only
- **[you]** Do you still have the notification Worker source
- **[you]** Villa 3's missing phone in the Zap mapping. Fixing it lets me delete
  the risky half of `samePerson`
- **[you]** Clear stale test data in villas 3, 4 and 5, now that Mews feeds them

## Stage B. Foundations. No design decisions, no dependencies

- **[me]** ~~Write a suite for `index.html`~~ **DONE 17 Aug.**
  `tests/guest_suite.py`, 42 assertions. Every behaviour Stage D will change is
  labelled `STAGE D:` in its name, so a red test after the rewrite reads as
  "this changed on purpose" rather than "this broke". Verified by breaking the
  returning-guest read on purpose: four assertions fire
- **[you]** Move the notification Worker source into `worker/`. Send it and I
  will add tests and the deploy config, same as the Mews one
- **[you]** Rotate all four credentials: GitHub token, Firebase key, `sync`
  passcode, shared secret. Two GitHub tokens, `publish` and `chef`, so either
  can be revoked alone. Both current tokens have been in chat
- **[you]** Delete the leftover Firebase Auth logins for anyone removed on the
  Settings page. Frees their passcodes
- **[print]** Service Sheet header stats bleed about 12pt at 320pt width.
  Measured. Not a Galaxy problem, only the narrowest phones
- **[print]** The one em dash in `list.html`, backlog item 9

## Stage C. Front Desk Arrival

Unblocked, highest value, and it settles the questionnaire shape that Stage E
inherits. This is where building actually starts.

- **[me]** Mock at 390, check at 360, do not break at 320. Show you before it
  ships
- **[me]** Lists today's arrivals. Completed and not completed visible at a
  glance, since that is the receptionist's whole job on the screen
- **[me]** Opens a guest, completes the four questions, sets dining or not
- **[me]** Writes `/bookings/<id>/prearrival`. Edit not create: a guest who
  answered half sees their answers
- **[you]** One decision I need at the start: does "dining tonight" from this
  screen write to `manual` like every other staff action, or into `prearrival`
  with the questionnaire? I lean `manual`, because it is a staff override of
  tonight and the boards already understand that node

## Stage D. The rewrite. The biggest single piece

This is stage 4 from the original plan, and it is larger than that plan says.
It also closes the worst live security hole, which is the reason to do it here
rather than later.

- **[me]** Re-key `responses` from phone to booking id. **This is the security
  fix**: today anyone who knows a phone number can read and write that guest's
  booking, and phone numbers can be guessed in order. A booking id cannot
- **[me]** Change the read at `index.html:846` with it, which restores what a
  guest already answered tonight. The handover twice says this key is never
  read. It is
- **[me]** `index.html` and `welcome.html` take a booking id. Name and dates
  from the link are **display only**, never written
- **[me]** Stop writing `/roomguests` from both pages. Two writers, not one
- **[me]** Strip name, room, arrives and departs from the `responses` payload
  and the `/guests` profile. `/guests` keeps standing dietaries alone
- **[me]** Drop `roomguests` from the four boards, and with it
  `resolveRoomGuests`, `resolveRoomGuestsHK` and the date tolerance in
  `parseDepDate`
- **[me]** Delete `samePerson`, the phone normalisation and the name fallback.
  With booking ids the match is exact
- **[me]** Remove the merge-tag test panel and the `{{tag}}` junk finder, which
  have nothing left to find
- **[me]** Old style links keep working throughout, so URL parsing goes last

## Stage E. Guest pre-arrival questionnaire

- **UNBLOCKED 17 Aug.** Purpose of visit is a multi select and it is advisory
  only: it exists so that when a guest cannot be reached, staff can judge
  whether they are the type to eat out. It never drives logic. The picklist
  question that blocked this stage since before the audit is answered
- The 48 hour deadline on the live form is guest facing encouragement, not a
  rule. No cutoff, no lock, no expiry is to be built
- Pre-arrival asks about the ARRIVAL NIGHT only. The live form's per night
  planner for the whole stay is dropped: guests do not follow it even when they
  fill it in accurately, so it collects work rather than information
- Allergy conflict at the desk is a separate future job, see `SCREENS.md`
- **[me]** `prearrival.html`, guest tier, four questions, one screen, no scroll
- **[me]** Inherits the shape settled in Stage C
- **[me]** Works before Mews has the booking, which is the normal case at seven
  days out

## Stage F. Registration cards

- **[me]** `registration.html`, print tier, one card per arriving villa
- **[me]** Answers filled in or left blank for pen, editable with a save
- Prints what C and E collect, so it follows both

## Stage G. Hardening and the last of the sync

- **[you+me]** `.validate` rules bounding shape and size. There is not one in
  the database today. I cannot test rules here, no emulator, so this publishes
  live with you watching
- **[me]** Sync heartbeat and a stale marker on the boards. Needs the Stage A
  answer to be honest rather than noisy
- **[me]** Clear orphan `prearrival` nodes on the Worker's next event for that id
- **[me]** Timezone fix, if Stage A says there is one. May cost nothing
- **[you]** Widen the lookahead. Now a boards question only: it does **not**
  block pre-arrival, because the link carries the dates
- **[me]** Make vacant the default villa state, once the handful of pre-sync
  bookings are entered by hand
- **[me]** Write back to Mews reservation Notes. Last, as originally planned

---

## Not in the order, because they are standing rules

- Never commit the chef brief. The repo is public and GitHub auto-revokes a
  token pushed to it, which breaks the chef's publishing
- Confirm dinner and breakfast hours. Still provisional, still nobody's task
- A green suite is not proof. The suites stub Firebase entirely. Anything
  touching sign in, push or printing needs a real handset before it is believed

---

## What I would do first, if you want one thing

Stage B's `index.html` suite, then Stage C. The suite is unglamorous and gates
the largest piece of work in the plan, and Front Desk Arrival is the first
thing on this list that anyone at the resort will actually see.
