# Mews sync - audit and new brief

> **SUPERSEDED IN PART, 17 Aug.** Several findings here were reasoned from
> reading code and stated as though measured in production. `GUEST-DATA.md`
> carries the settled design and lists every correction. Where the two
> disagree, that one is right. In short: the old guest-written URL path is not
> running, finding 1 could not fire, `samePerson` solves a problem that may not
> exist, the lookahead does not block stage 3, and the `prearrival` rules
> change must not be pasted.

Written 16 Aug 2026, in the session after the one that built it. Audits the
brief, the plan (MEWS-SYNC.md) and the code as it stands on main at `139971c`.

Everything below marked **measured** was run, not reasoned about. The probe
loaded the real `nala-shared.js` and put a moved guest and a shortened stay
through `resolveRoomGuests`, `overlayStays`, `roomRecord` and `hkClassify`.

---

## Verdict

The pipeline is sound. Stage 1 is genuinely done and the Worker is the best
written thing in the project: 38 tests, real edge cases, comments that say why.

Stage 2 is where it comes apart. The plan wrote down the precedence rule,
argued for it, and then the build put the merge somewhere that quietly
reverses it. The result is that **the failure this whole project exists to fix
is still live**, and it is now harder to see because everyone believes it is
fixed.

Three findings are serious enough to change the order of work. The rest are
listed so they are not rediscovered one at a time.

---

## Finding 1. The guest still beats Mews on the departure date. MEASURED

MEWS-SYNC.md line 126 names `depart` as one of two fields that genuinely
collide, and rules on it in plain words:

> Mews wins over `roomguests` and over the guest's own answer. Staff override
> still wins over Mews.

The build does the first half and not the second.

`overlayStays()` lays the PMS over `roomguests`, which is correct, and its
comment justifies sitting below `responses` like this:

> a response carries a name and a dinner answer but never a departure date

**That premise is false.** `index.html` line 821 puts `arrives` and `departs`
into every response payload. So `roomRecord()` applies the response over the
overlay and the guest's date wins.

This is a bridge, not the design. The new link carries a booking id and
nothing else, `?b=<reservation-guid>`, so the guest page reads name, villa,
dates and phone from `/bookings/<id>/pms`, which is Mews. There is no second
copy of anything, and precedence stops being a question rather than being
answered.

**The principle, which belongs here rather than in a chat: `responses` holds
only what the guest told us. Every fact about the booking is read live from
`/bookings/<id>`, never copied into a response.** Dinner status, covers,
dietaries and notes are the guest's and are stored. Name, villa, arrival and
departure are Mews' and are looked up. Nothing that is looked up can go stale.

The merge ordering below still has to be fixed, because links carrying merge
tags are live today and the bug is measurable today, and old style links must
keep working while any are in flight. But it is scaffolding to be removed at
stage 4, not a permanent rule to maintain.

Measured, on a stay Mews shortened from the 25th to the 22nd:

```
after overlayStays, villa 5 departs = 2026-08-22   (Mews, correct)
after roomRecord,   villa 5 departs = 2026-08-25   (the guest's old URL)

hkClassify on the 22nd, with the response  -> svc     (service, wrong)
hkClassify on the 22nd, without it         -> clean   (correct)
```

The villa is not presented for cleaning on the day it is vacated. This is
"arrival detection is fragile" from the known gaps list, unchanged, and it now
only bites guests who **did** open their link, which is the harder half to
notice because those villas look complete.

It is not a deep design problem. The overlay is in the right place; the fields
Mews owns simply have to be reapplied above `responses`, which is what the
unpublished `pmsFields()` in the handover already does. That function exists
and is correct. It is sitting in the handover unpublished, and it was written
for the vacant-stale rule rather than for this, so nobody connected it to the
precedence bug.

## Finding 2. A moved guest appears in two villas again. MEASURED

The stale index bug cost an evening and produced three Ben Davidsons. The
Worker fix is good and self healing. It fixes `/stays`.

Nothing fixes `roomguests`. It is resolved over a fortnight of history and an
entry is only dropped once its own `departs` has passed, so the old villa keeps
the guest until they were due to leave.

Measured, guest opens their link in villa 5 on the 18th, Mews then moves them
to villa 9:

```
villas showing a guest: [ '5', '9' ]
villa 5 name: Jane Doe   villa 9 name: Jane Doe
```

Same guest, two villas, on every board. Identical symptom to the bug that was
just fixed, one layer up, and no suite covers it. `responses` does the same
thing independently: the response carries `room` from the URL and
`roomRecord()` matches on it, so the guest sticks to the old villa there too.

The fix belongs in `overlayStays`, which is the one place that can see both
sides: a booking id present in `/stays` at one villa should clear that same
booking id out of every other villa in the merged map.

**How the two sides are matched is scaffolding, for the same reason as the
dates.** A `roomguests` record holds a phone a guest's URL supplied, so Mews'
`+61400000000` has to be reconciled with a link's `0400000000`, which is done
on the last nine digits. Once every record carries a booking id the match is
exact and the whole heuristic goes.

It has a sharp edge worth naming. Phone matching is sound. Name matching, which
covers the case where Mews sends no phone at all, is a guess: two different
real guests sharing a name, one guest written and one from Mews, and the wrong
villa's record is deleted. Rare and silent, which is the bad combination. It
exists only because villa 3's Zap mapping drops the phone, so one workaround is
propping up another, and fixing that mapping removes the need for the name
half. Only guest written entries are ever dropped, so a villa the PMS itself
claims is never at risk.

## Finding 3. Internal Mews notes are readable by anyone holding the booking id

The rules grant `bookings/$id/.read: true`, unconditionally. That is
deliberate and correct on its own: the guest cannot sign in, so the pre-arrival
page needs it, and a GUID in an SMS is a reasonable bearer token. MEWS-SYNC.md
argues this well.

What the plan did not anticipate is what the Worker actually stores there.
Lines 246 and 247 write `notes`, `notesType` and `guestNotes` into
`/bookings/<id>/pms`. Those are `NotesText` and `Companions0Notes` from Mews:
free text written by reception, about the guest, for staff. Nobody writing a
note in Mews expects the guest to read it.

So the pre-arrival SMS carries a link that exposes whatever the front desk last
typed about that guest. One forwarded message is enough.

`spaceState` is in the same bucket and is stored while being explicitly never
used, which is the weakest version of the trade: no benefit, some exposure.

Two ways out, and the choice is the user's. Either stop carrying the note
fields, which loses the stage 6 write back's most useful context, or move them
to `/bookings/<id>/staff` and give that node `auth != null`. The second is
better and costs one rules line and one Worker line.

---

## Where the build differs from the plan, in full

| Plan said | Build does | Verdict |
|---|---|---|
| Merge inside `roomRecord`, Mews below `responses` | `overlayStays` at the roomguests layer | Better. Reason given in the code is right: tally.html reads roomguests directly in eight places |
| Mews wins on `depart` over the guest's answer | The guest's answer wins | **Wrong, finding 1** |
| Mews wins on `villa` for a moved guest | Wins in `/stays`, loses in `roomguests` and `responses` | **Wrong, finding 2** |
| Firebase service account for the Worker | A `sync` staff account with a six digit passcode | Better. Same rules as everyone else, no key that grants everything |
| Booking data to Firebase, not GitHub | Done | Right, and the reasoning holds |
| Six fields in the payload | Eleven, plus notes | Mostly right, but see finding 3 |

The three departures the previous session wrote up were all sound. These two
were not written up because nobody noticed them.

---

## Fresh eyes: things neither the brief nor the plan raises

**The adult count is stored and never read anywhere.** `mewsRecord` sets
`adults`, and `grep` finds no page that reads it. Mews knows the party size,
the app has it in memory, and the board still shows nothing for a villa whose
guest has not clicked. The brief's complaint was a reservation screen with
missing guest data. Covers is the field it is most missing.

**The 84 hour lookahead and the 7 day SMS do not meet.** Recorded in
MEWS-SYNC.md as the main open problem, but the consequence for stage 3 is not
recorded anywhere: the pre-arrival page cannot show a guest their own name and
dates, because at 7 days out the booking is not in Firebase yet. Widening the
lookahead is listed as sync item 4 and stage 3 is listed as blocked only on the
picklist question. It is blocked on both.

**Anyone can write to `/bookings/<anything>/prearrival`, unauthenticated.**
The rule is `".write": true` with no validation and no requirement that the
booking exist. A stranger can create nodes under invented ids indefinitely. The
guest page has to be able to write without signing in, so this cannot simply be
closed, but requiring that `pms` already exists under that id would remove the
invented-id half of it in one rules clause.

**Nothing validates the villa name.** `ResourceName` becomes a `/stays` key
verbatim. If a Mews space is ever named "Villa 3" rather than "3", or a new
space is added, the entry is written to a key no board looks at and the guest
is silently invisible. There are 17 villas and `ROOMS = 17` is already in
`nala-shared.js`. The Worker should reject or flag anything outside it rather
than writing quietly.

**Cancellation has never been observed arriving.** It is handled correctly in
the Worker and tested there, but the Zap that would deliver it filters on
reservations *starting* within a window. A cancelled reservation may drop out
of that filter and never fire at all, in which case the handling has nothing
feeding it and a cancelled guest keeps their villa and prints a registration
card. The room move was tested. This was not, and it is the more expensive one
to get wrong.

**The Worker makes one subrequest per night per event.** A 14 night stay is
about 30 outbound calls, and `nights()` caps at 120. Cloudflare limits
subrequests per request, and the limit differs by plan. Worth checking which
plan the Worker is on before a long stay or the `Colliding` backfill is run,
because the failure mode is a 500 and a Zapier retry loop.

**Small ones.** `staleVilla` at line 197 is assigned and never used, left over
from the rewrite. The reply's `cleared` count reports the previous booking's
night count rather than what was actually deleted, so it now overstates. The
late event guard compares timestamps as strings, which is fine while every
event comes from one Zap field and wrong the moment two formats mix.

---

## The old mechanism and the new one now both run

This is the part neither document treats as a single thing. The sync did not
replace the guest-written path, it was laid alongside it, and every fact about
a guest now has two sources. Findings 1 and 2 are not two bugs. They are two
places where the older source happens to be winning.

**Five URL parameters, all now supplied by Mews.** `index.html:553` and
`welcome.html:208` read the same five: `p` phone, `r` room, `n` name, `a`
arrives, `d` departs. Every one has a PMS equivalent in `/bookings/<id>/pms`
and `/stays`. The booking id is the only thing a link still needs to carry.

**Three nodes, each part duplicate and part not.** The distinction matters,
because the instinct will be to delete a node and the correct move is to strip
fields out of one.

| Node | Written by | Duplicated by the PMS | Genuinely its own |
|---|---|---|---|
| `/roomguests/<date>/<room>` | index.html:840, welcome.html:281 | all of it | nothing |
| `/guests/<phone>` | index.html:828, welcome.html:280 | name, room, arrives, departs | `diets`, the standing dietaries that carry across stays |
| `/responses/<date>/<phone>` | index.html:823 | name, room, phone, arrives, departs | status, pax, diets, note, dnote, flag, premenu, nodiet |

Note that `/roomguests` and `/guests` each have **two** writers, not one. Any
cleanup that only touches `index.html` leaves `welcome.html` writing the old
shape.

**Code that exists solely to cope with the old path.** It is more than the
writes.

- `parseDepDate()` in `nala-shared.js` accepts `dd/mm/yyyy`, ISO, or anything
  the `Date` constructor will take. That tolerance exists because the date
  arrives as a GuestTouch merge tag in a format nobody controls. Mews always
  sends `dkey` format.
- `resolveRoomGuests()` and `resolveRoomGuestsHK()` scan a fortnight of history
  and then expire rows by comparing each guest's own `departs` to today. Both
  the scan and the expiry exist because `roomguests` is written whenever a
  guest happens to click and has no authoritative end. `/stays` is authored one
  row per night and needs neither. This is also where finding 2 comes from: the
  expiry cannot drop a guest who moved villa, only one whose date has passed.
- The `{{tag}}` junk finder in `debug.html` exists because unsubstituted merge
  tags land in the database as real guest names and dates. `debug.html:282`
  names the exact shape: a guest called `{{firstname}} {{lastname}}` departing
  on `{{check-out_date}}`. That failure mode does not exist on the PMS path.
- The merge-tag test panel in `welcome.html`, already backlog item 3.

**What has to be true before any of it can go.** `roomguests` is currently the
only source for a guest who is already in house, or who booked outside the 84
hour window. Until the lookahead is widened and the backfill has run, deleting
the old path deletes the guests. That is the real reason items 8 and 11 in the
brief below come before the cleanup, and it is a stronger reason than the one
recorded in MEWS-SYNC.md, which frames retiring `roomguests` as a later nicety
rather than as the thing that resolves a live contradiction.

**Sizing.** The handover describes stage 4 as `index.html` reading a booking id
and `responses` being re-keyed. That is about a third of it. The rest is the
list above, and doing the writes without the readers leaves two occupancy
indexes disagreeing, which is the failure that looks plausible.



---

## Corrections to the handover

Three statements in HANDOVER-MEWS.md are wrong and all three are load bearing.

**"Cloudflare deployed, four secrets set, Git integration connected."** The Git
integration was never connected. Confirmed from the dashboard on 16 Aug: the
Build section offers GitHub and GitLab connect buttons with no repository, no
branch and no build history beneath them. This is the whole reason the stale
index fix is not live, and it is why that was recorded as needing a manual
paste rather than as a setup nobody finished. `wrangler.jsonc` was written and
committed for a build that did not exist.

**"The key is only written today, at `index.html:823`, never read."** It is
read, at `index.html:846`, to restore what the guest already answered tonight.
Stage 4's re-key is described as low risk on the strength of that claim. It is
not: re-keying `responses` to the booking id breaks the guest's own returning
view unless line 846 changes with it.

**"Roles stage two is effectively done."** Unrelated to this feature, but
`staff.html` cannot delete a Firebase Auth login, so a passcode cannot be
reused. That is backlog item 8 and it is still open, not done.

---

## The new brief

Ordered so that nothing is built on top of something that is wrong. Stages 3
to 6 are unchanged in intent and are not restated; the plan describes them well.

### Before anything else, two things already on the list

1. **Connect Workers Builds to the repo.** This replaces the manual paste: the
   build deploys `c233c54`, which is the stale index fix, and every future
   Worker change ships in the same `push.py` commit as everything else. Root
   directory `worker`, branch `main`, no build command.
2. Clear `/bookings` of test PII in the Firebase console.

### Then, correctness. This is the new work

3. **Make Mews win the fields it owns.** Reapply `pmsFields()` above
   `responses` inside `roomRecord`. The function is already written in the
   handover. Tests: a shortened stay classifies as a clean on the new departure
   date even when the guest's response says otherwise, and dining, covers,
   notes and dietaries are untouched by it.

   Then stop copying dates into `responses` and `/guests` at all, at
   `index.html` lines 821 and 826. Once Mews owns the dates, a second copy
   written by the guest page can only ever be a stale rival. This half can wait
   for stage 4 if it is easier to do there, but the ordering fix above cannot.
4. **Clear a moved guest out of the old villa.** In `overlayStays`, a booking
   id seen at one villa removes that id from every other villa in the merged
   map, covering both the `roomguests` carry forward and the stale `responses`
   room. Test: a guest moved from 5 to 9 appears once.
5. **Take the note fields out of the public node.** Move `notes`, `notesType`,
   `guestNotes` and `spaceState` to `/bookings/<id>/staff`, rules
   `auth != null`. One Worker change, one rules change, both small.
6. **Publish the precedence and stale-vacant work** that is already written.
   It needs the 390pt mockup of the warning sheet, tests, a v19 bump on five
   pages and rebuilt demos. Doing it after 3 and 4 means one version bump
   rather than three.

Items 3, 4 and 6 all touch `nala-shared.js`, so they should be one commit and
one bump.

### Then, the sync itself

7. Fix villa 3's missing phone in the Zap mapping.
8. Widen the lookahead with a negative Start Time Modifier. **This now blocks
   stage 3**, not just item 6 on the old list.
9. Prove a cancellation reaches the Worker. Cancel a real test booking in Mews
   and watch the Zap history. If it does not fire, that is the argument for the
   Mews Connector API, and it should be made then rather than deferred again.
10. Validate the villa against the 17 in `ROOMS` before writing `/stays`.
11. Backfill in-house guests with Time Filter `Colliding`, then revert.
12. Only then make vacant the default villa state.
13. Rotate the shared secret, the Firebase key, the `sync` passcode and the
    GitHub token.

### Then, and only then, stage 3 onward

Stage 3 needs two answers before it can be mocked, not one:

- Is type of stay a picklist, and if so what is the list
- Is item 8 done, so the page can show the guest their own booking

Show the adult count on the boards as part of stage 3 or earlier. It is a small
change and it is the brief's actual complaint.

**Stage 4 is bigger than the handover says**, and should be rewritten as the
retirement of the old path rather than as a page edit. In order:

- `index.html` and `welcome.html` both take a booking id only. Two pages, not
  one
- Stop writing `/roomguests` from either page
- Strip name, room, arrives and departs out of the `/responses` payload and out
  of the `/guests` profile, leaving `/guests` holding standing dietaries alone
- Re-key `responses` to the booking id, and change the read at
  `index.html:846` with it
- Drop `roomguests` from the four boards, and with it `resolveRoomGuests`,
  `resolveRoomGuestsHK` and the tolerance in `parseDepDate`
- Replace `samePerson` with an exact booking id match, and delete the phone
  normalisation and the name fallback with it. Both exist only to reconcile
  records that will by then carry the same key
- Remove the merge-tag test panel and the `{{tag}}` junk finder, which have
  nothing left to find
- Old style links keep working throughout, so the URL parsing is the last thing
  to go, not the first

---

## What this audit did not check

The five Playwright suites were not run; the sandbox has no browsers installed
this session. The Zapier configuration, the Cloudflare deployment and the live
Firebase rules were all read from the documents in this repo, not from the
consoles, and the documents themselves say the consoles are the source of
truth. Anything above that depends on live configuration is marked as needing a
check rather than stated as fact.
