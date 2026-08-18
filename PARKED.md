# Parked

Things that stopped for want of an answer, rather than for want of work.
Written 18 Aug. Each one says what was decided in the meantime, so nothing is
sitting still waiting: the decision holds until it is overruled.

---

## 1. Statistics counts a vacant villa as nobody, not as a no

Reception marks empty villas vacant most days. The old page counted every
record in the node as a reply, so a half full week read as half the guests
declining dinner, and every menu looked worse than it was.

**Decided:** a villa marked vacant is not counted at all, in either direction.
Take-up is now the share of guests who actually answered.

**Needs you only if** you want vacant nights shown somewhere as occupancy. That
is a different chart, not this one.

## 2. How far back Statistics should look

120 days, unchanged, because that is what it was. The page now reads three
whole nodes in three requests instead of two requests a day for 120 days, so a
longer window costs almost nothing.

**Question for you:** is a season the right frame, or do you want it since the
resort opened? Say a number of days or say "everything".

## 3. Dish groups

The groups are Beef, Lamb, Pork, Chicken, Duck, Fish, Shellfish, Vegetarian
and Other. They are matched from the dish name, animal first and cut second,
which is what stopped lamb rump counting as beef.

**Question for you:** anything the chef cooks that lands in Other and should
not. Send a few dish names and they go in the list.

## 4. The dietary list can now refuse to save

Menu Dietaries saves by writing the whole list at once. If the list cannot be
read when the page opens, the page now says so and refuses to save, rather than
quietly offering to replace the chef's dietaries with the eight built-in ones.

**Watch for:** the chef reporting that Save is greyed out. That means a sign in
problem, not a lost list, and reloading after signing in fixes it.

## 5. The new database rules: published 18 Aug

Done. The live rules and the repo copy match.

What is left is the smoke test in `TESTING.md` section 0, six taps, worst
first. The suite proved the rules against write bodies taken from the code, so
the only thing it cannot rule out is a page writing a field that is not visible
in the code that appears to send it. A write refused by a rule does not
announce itself: the change simply is not there on the next refresh.

Before you paste: this refuses twenty six shapes the database accepts today,
and refuses nothing the app actually writes. Both halves of that were tested
rather than reasoned about. The thing to watch for afterwards is any page
reporting that a save was not allowed, which would mean a field somebody writes
was missed.

## 6. Housekeeping setting a villa's job: answered 18 Aug

ROLES.md was right. Setting the job is the manager's, and the rule that was
supposed to enforce that had never worked. It works in the new file, and the
suite now pins that a waiter and the chef cannot do it either. Nothing more is
needed here, it just has to be pasted with the rest.

## 7. Where the service hours should appear

Answered 18 Aug: dinner 6:00 to 6:30, breakfast 8:00 to 9:30. They are written
down now, but nothing shows them: no page in the app has ever stated a service
time, so putting them on one is a design change rather than filling a blank.

**Proposed, needs a yes from you before it is built.** Dinner goes on the
welcome page, under the menu button, where a guest reading it has just arrived
and is deciding about tonight. Breakfast goes on the pre-arrival form beside
the dining question, since that is the only place a guest is asked about a
meal before they get here. Neither appears on a staff board: reception knows
the hours and the space is worth more to a villa number.

Anything visual gets a mock first, at 390pt, checked at 360, unbroken at 320.

## 8. Still yours from before, unchanged

None of these moved today, and none of them can move without you.

1. Cancellations still do not fire from Zapier.
2. GuestTouch links need `?b=<booking id>`.
3. Four credentials to rotate, now five: the token issued on 18 Aug has been in
   chat too. Issue `nala-menu publish` and `nala-menu chef` separately.
4. Leftover Firebase Auth logins to delete.
5. ~~Whether Mews sends true UTC.~~ Answered: it does, and the Worker now
   converts. See `TESTING.md` section 7.
6. ~~Dinner and breakfast hours.~~ Answered, see above.
7. **The wording of the dining description on the pre-arrival form.** Standing
   in and live. Only the 6:00 to 6:30 seating is a real fact; the rest is mine
   and should be yours. `prearrival.html`, id `dineHelp`.

## 9. Left over from the print work

These were another chat's to do while it owned the print pages. That
arrangement ended on 18 Aug and they are now this chat's, still undone:
the three nav entries in `list.html` and `housekeeping.html`, the 320pt header
bleed on the Service Sheet, the one em dash in `list.html`, and the missing
role gate on `menu-print.html`. `menu-print.html` otherwise has a suite and
passes it.
