# What else is missing

17 Aug. Not pages, which are in `SCREENS.md`. This is everything else the
architecture implies and the repo does not have, plus the parts of
`HANDOVER.md`'s own gap list that the Mews work has quietly changed.

Measured items say so. The rest is reasoning, and the audit written last night
is a standing reminder of what happens when those two get mixed up.

---

## 1. The real security hole is `responses`, not `prearrival`. MEASURED

```
"responses": { "$date": { "$phone": { ".read": true, ".write": true } } }
```

Anyone who knows a phone number can read and write that guest's dinner
response. `HANDOVER.md` names this and calls the fix "signed links, which is a
project rather than a rules edit".

**That is no longer true, and nobody has noticed.** The Mews booking id is an
unguessable GUID and it now exists. Re-keying `responses` to it, which stage 4
already plans for other reasons, turns this from an enumerable hole into the
same bearer-token model `/bookings` already uses.

The difference in kind matters: phone numbers can be guessed in order, GUIDs
cannot. I spent last night worrying about the `prearrival` write, which is
GUID-protected, while the enumerable one sat next to it. Stage 4 should be
argued for on this basis, not on tidiness.

## 2. There is not one `.validate` rule in the database. MEASURED

Fourteen top level nodes, two of them world writable, and nothing anywhere
bounds a shape, a type or a size. A stranger can write a megabyte of anything
into `responses` or `prearrival` and the rules will accept it.

This is the missing half of every rules conversation so far, which has all been
about who may write rather than what may be written.

## 3. The notification Worker is not in this repo

`HANDOVER.md`: the push sender is a Cloudflare Worker, "not in this repo,
source is handed over separately". It holds the VAPID private key.

The Mews Worker now lives in `worker/`, has 47 tests and deploys on commit. The
push Worker has none of that. If that file is lost, a working part of the
product cannot be rebuilt from anything you own, and there is no test that
would catch a change breaking it.

Same treatment, same directory.

## 4. Five pages have no test suite, and one of them is the guest page. MEASURED

`index.html`, `welcome.html`, `debug.html`, `stats.html`, `menu-print.html`,
`tag.html`.

`HANDOVER.md` already flags `index.html`. It is now more urgent, not less:
stage 4 rewrites it, and rewriting an untested page is where the afternoon
goes. The suite should exist **before** that rewrite, describing today's
behaviour, so the rewrite has something to fail against.

## 5. Nothing tells anyone the sync has stopped

`debug.html` answers "is data arriving?" and it answers it only when a human
opens it and thinks to ask.

If the Zap stops firing, or the shared secret rotates and the Worker starts
refusing, the boards do not go red. They quietly show fewer bookings, which
looks exactly like a quiet week. The whole point of the sync is that nobody
maintains `roomguests` by hand any more, so nobody is watching the place where
the absence would show.

A single stored "last event received" timestamp, and a marker on the boards
once it passes some hours, is most of the value.

## 6. A late check-in may land on the wrong night. MEASURED, needs your answer

The Worker takes the date part of Mews' UTC timestamp. The app builds its dates
from the phone's local clock. The database is in `asia-southeast1`.

```
UTC+8, StartUtc 2026-09-10T16:00:00Z -> Worker writes night 2026-09-10
                                        locally it is already the 11th
```

Any arrival after 4pm local at UTC+8, or 5pm at UTC+7, records the night
before. Whether that is wrong depends on something I do not know: whether Mews
sends true UTC or local time in a field named Utc, which varies by property
configuration. If it is true UTC, evening arrivals are on the wrong night now.
If Mews sends local, it is correct and this note is noise.

Checkable in one look at the Zap history against a booking whose local check-in
time you know.

## 7. Where `HANDOVER.md`'s gap list is now out of date

- **"Mews PMS sync. Not started"** is backlog item 6, and it is substantially
  done.
- **"The role mechanism is a single email prefix check"** was replaced.
  `roleOf` reads `/staff` records now.
- **"Arrival detection is fragile"** was the reason for the whole project. The
  merge ordering published last night addresses it, though see `GUEST-DATA.md`
  on how live it ever was.
- **"Same phone, two villas"** was left open pending a booking id from
  GuestTouch. One arrived, from Mews, and the fix is now available.
- **"Clear stale test data in villas 3, 4 and 5"** is still open.

Left standing and worth re-reading: a green suite is not proof, the suites stub
Firebase, and anything touching sign in, push or printing needs a real device.

---

## Suggested order

1. `index.html` suite, describing what it does today. It gates stage 4 and it
   is the only untested guest facing page.
2. Re-key `responses` to the booking id. This is stage 4, and item 1 above is
   the argument for doing it sooner than planned.
3. `.validate` rules on the two open nodes. Untestable here, no emulator, so it
   goes in with you watching.
4. Sync heartbeat and a stale marker.
5. Move the push Worker into `worker/`.
6. Settle the timezone question, which may cost nothing.
