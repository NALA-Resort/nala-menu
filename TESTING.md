# Tests only you can run

Everything in `tests/` runs in a sandbox with Firebase stubbed, no iOS fonts, no
real handset and no network to Mews, Zapier, Cloudflare or GitHub Pages. So a
green suite proves the logic and the layout and can say nothing about any of
the below.

That is not a caveat, it is the actual record: on 16 Aug the passcode screen
shipped with 30 passing tests and broke sign in on a real phone for two hours.

Ordered by what would hurt most if it were broken.

---

## 1. The pre-arrival round trip. NEW, never run on live data

The first time the guest form and the front desk have met outside a fixture.

1. Open **menu.nalaresort.com/debug.html** and find a booking id under today's
   or tomorrow's stays. Each villa entry carries one.
2. Open, with that id pasted in and any name and dates:
   `menu.nalaresort.com/prearrival.html?b=THE_ID&n=Test&s=Guest&a=2026-08-18&d=2026-08-22`
3. Answer all six questions and Send.
4. Open **front-desk.html** and browse to the date that booking arrives.

**Expect:** greeting by name, the nights counted, one question flagged at a time
if you try to send early, a thank you after Send. Then on Front Desk that villa
is green with a fork, and tapping it reads back exactly what you sent.

**If the row is not there at all** that is the lookahead, not the page. `/stays`
only holds what Mews has sent, roughly 84 hours ahead.

**If Send fails** check the browser console. A 401 means the rules moved.

## 2. GuestTouch merge tags

I chose the parameter names and cannot see your GuestTouch account.

Configure a test send with `?b=`, `n=`, `s=`, `a=`, `d=` and send it to your own
phone. **Expect** the link to open with your name filled in. **If GuestTouch
cannot produce a parameter with those names,** tell me what it does send and I
will read that instead. It is a one line change.

**Watch for `{{firstname}}` appearing as the guest's name.** That is an
unsubstituted tag, and it is why `debug.html` has a junk finder. On this page it
is display only, so it cannot reach the database, but it looks broken.

## 3. Sign in on a real handset

The suites stub the Firebase SDK completely, so this is untested by definition.

Sign out fully, close the tab, reopen **front-desk.html** and sign in with the
passcode. **Expect** the board, not a flash of the sign in pad first.

**If it hangs,** clear the browser's site data before any other theory. A wedged
stored session did this once and cost two hours.

## 4. Fonts, on iOS

Georgia, San Francisco and the iOS system fonts are not installed in the
sandbox, so every render I have shown you fell back to something else.

Open **font-test.html** on an iPhone. Then open **front-desk.html** and
**prearrival.html** on the same phone and check the numbers line up in the stats
row and the guest form's Raleway is loading rather than falling back.

## 5. Does the cancellation id match the reservation id

**Before anything else about cancellations.** The cancellation trigger in
Zapier has no `Mews Id` field, only `Id`. It has dashes, so it is a GUID, but
that is not enough: it only works if it is the SAME GUID as the reservation
trigger's `Mews Id`. If it identifies the cancellation event instead, nothing
links the two and every cancellation clears nothing.

Cancel a test booking. Compare the `Id` in the cancellation run against the
`Mews Id` from that same booking's reservation run.

**Same value:** nothing to do, it already works.
**Different:** cancellations cannot find their booking, and that needs solving
before the feed is worth switching on.

The Worker now reports `unknownCancellation: true` in its reply when a
cancellation matches no booking it has seen, so the Zap history will show this
without you comparing anything by hand.

## 6. Cancellation actually firing

Handled in the Worker and covered by 47 tests, but never observed arriving.

Cancel a test reservation in Mews and watch the Zap history. **Expect** the
Worker to be called and the villa to clear from `/stays`. **If nothing fires,**
the Zap's filter is dropping cancellations and that is the argument for the Mews
Connector API.

## 7. Does Mews send true UTC

The Worker takes the date part of Mews' `StartUtc`. The app uses the phone's
local clock. At UTC+8, any arrival after 4pm local would be recorded on the
night before.

Find a booking whose local check-in time you know and compare it to the
`StartUtc` in the Zap history. **If they differ by the timezone offset,** Mews
is sending true UTC and evening arrivals are on the wrong night. **If they
match,** Mews is sending local time in a field named Utc and there is nothing to
fix.

## 8. Printing

Never confirmed on a real phone: whether the repeating header actually repeats,
and whether the PDF path avoids the browser's own headers.

Print the Reservations Sheet from an iPhone, both via Print and via the PDF
button, on a two page day.

## 9. Push notifications

iOS only allows these for a site added to the Home Screen, so a browser tab
cannot test it.

Add the app to the Home Screen, enable notifications in the hamburger, and have
someone else mark a villa. **Expect** a lock screen buzz, and no notification
for your own tap.

## 10. Widths, on real devices

Measured at 390, 360 and 320 in a headless browser, which is not a phone.

Open **front-desk.html** and **prearrival.html** on the narrowest phone anyone at
the resort uses. **Expect** no sideways scrolling anywhere, including with a
summary open.

---

## What I check, so you do not have to

Every suite runs on every change: layout at three widths, every branch of the
logic, the failure paths, the role gates, and that each suite still fails when
the thing it protects is broken. 540 assertions across nine suites.

I also open every link on the site map and confirm no page in the repo is
missing from it, which is the check that stops that page rotting.
