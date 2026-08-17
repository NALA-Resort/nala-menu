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

## 5. The new database rules need pasting into the console

`rules.json` in the repo now has a validate rule on every node, and nothing in
it is real until you paste it into the Firebase console and press Publish. The
steps are the ones already written down in `SETUP.md`, the section on the
database rules: open the file on GitHub, copy button, select all in the Rules
editor, paste over the lot, Publish. It is a complete replacement, not an
addition. Say the word if you would rather have it as a block in chat.

Before you paste: this refuses twenty six shapes the database accepts today,
and refuses nothing the app actually writes. Both halves of that were tested
rather than reasoned about. The thing to watch for afterwards is any page
reporting that a save was not allowed, which would mean a field somebody writes
was missed.

## 6. Housekeeping can set a villa's job, and ROLES.md says they cannot

The rule meant to stop them has never worked. The new file stops them.

**Question for you:** is ROLES.md right? If housekeeping should be able to mark
a villa as a clean or a service themselves, say so and the rule comes out
before you paste. Nothing else in the file depends on it.

## 7. Still yours from before, unchanged

None of these moved today, and none of them can move without you.

1. Cancellations still do not fire from Zapier.
2. GuestTouch links need `?b=<booking id>`.
3. Four credentials to rotate, now five: the token issued on 18 Aug has been in
   chat too. Issue `nala-menu publish` and `nala-menu chef` separately.
4. Leftover Firebase Auth logins to delete.
5. Whether Mews sends true UTC.
6. Dinner and breakfast hours.
7. The placeholder line on the pre-arrival form.

## 8. For the print chat, not for you

`menu-print.html` now has a suite and passes it, so nothing is owed there. The
three nav entries it owes in `list.html` and `housekeeping.html`, the 320pt
header bleed on the Service Sheet and the one em dash in `list.html` are all
still outstanding.
