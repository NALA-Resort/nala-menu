# Pre-arrival form: the 23 Aug revision

Agreed with the owner by voice on 23 Aug, against a mockup he approved. This
file is the whole brief. If anything here contradicts an older note, this wins.

Everything is in `prearrival.html` and `tests/pre_suite.py`, except where a
section says otherwise. Two of them do, and between them they reach
`front-desk.html`, `registration.html`, `tally.html`, `list.html`, `stats.html`
and `rules.json`. Read all of it before starting: the
arrival control and the covers count reach into four other files, and building
the easy parts first will leave those two looking like small tidy-ups when they
are not.

---

## Decide these three first

**Do not start until the owner has answered.** Each has a recommendation. None
of them is a detail: two change what is stored, and stored shapes are read by
pages this brief does not touch.

### 1. What the arrival time is stored as

He wants a 30 minute scroller, same range as now. Today `arriveSlot` is one of
six keys and three places depend on that exact set:

- `front-desk.html`, `etaIndex()` and `etaLabel()`, which sort the arrivals
  board by a slot's POSITION in `ETA_SLOTS` and print its label.
- `front-desk.html`, reception's approved time, a whole hour 11 to 23. The
  database rule enforces that range and that it is a number.
- `registration.html`, which has its own `ETA_SLOTS` as a lookup object and
  prints the label on the card the guest signs. Its fallback is
  `ETA_SLOTS[slot] || slot`, so an unrecognised value prints RAW. Under
  minutes-from-midnight that puts `870` on a card handed to a guest. This one
  is easy to miss because it is a different file and a different shape from the
  other two.
- The cleans board ETA work, which maps each key to an hour.

Half hours break all three. Two ways:

- **Recommended: keep `arriveSlot` a string, store minutes from midnight.**
  `"870"` is 2:30pm. `"before2"` and `"after5"` stay exactly as they are, so
  nothing that already handles them changes. The rule already allows it:
  `arriveSlot` validates as a string of 60 characters or fewer, so **no rules
  change and nothing to paste into the console**. `etaIndex` becomes a numeric
  comparison with the two ends pinned to either end. Old records keep working
  because `"14"` parses to 14 and can be read as an hour when the value is
  under 24.
- Or: leave the six keys and let the scroller land on the nearest hour. Cheap,
  and it makes the scroller a lie, since it would show 2:30 and store 2:00.

Whichever is chosen, **reception's approved time must be able to say 2:30 too**,
or the desk cannot match what the guest asked for. That is a rules change:
`arriveApproved` is a number 11 to 23 today. Minutes from midnight is 660 to
1380. Needs a paste into the Firebase console, and the desk control needs half
hours added.

### 2. Where the cover count comes from once group size is gone

He wants the "how many of you" question removed. `pax` is read by
`tally.html`, `list.html`, `front-desk.html`, `registration.html`,
`stats.html` and `index.html`. It is what "16 covers" is counted from, what
prints in the Pax column of the FOH sheet, and what the kitchen shops against.

- **Recommended: fall back to the booking's adult count** from
  `/bookings/<id>/pms/adults`, which Mews sends. Write it into `pax` at the
  same moment the dinner answer is saved, so nothing downstream changes at all
  and no reader needs touching.

  **This form already has that number.** `paintGreeting` reads `pms.adults` to
  decide whether the companion question is shown, so there is no new fetch and
  no new failure mode: the value is in hand by the time any page draws. Guard
  the case where it is missing, since a booking with no adult count would
  otherwise write zero, and zero covers is a table nobody lays.
- Do NOT simply stop writing `pax`. Every one of those readers treats a missing
  pax as zero, and a table of zero is a table nobody lays.

Sanity check with the owner that Mews' adult count is reliable before relying
on it. If it is not, the question has to stay.

### 3. Does the treatments question stay

The mockup he approved has seven pages and no treatments question. He never
said to remove it and may not have noticed it was gone.

- Staying makes it eight pages, and it belongs after dining and before
  "Anything else".
- Going means removing `wellness`, `wellDay` and `wellTime` from the form and
  from anything that reads them.

**Recommended: ask.** Do not infer consent from the mockup.

---

## The page order

Seven pages, in this order, and the order is the point. Food was appearing at
three, four and six with an unrelated question between, which is what made it
feel like skipping backwards and forwards.

1. **Additional guests** - who is coming
2. **What brings you to Nala** - why, and it sets the tone
3. **What time do you expect to arrive** - getting here
4. **Where do you plan on eating during your stay** - the week
5. **Will you be dining with us on your first night** - tonight
6. **Dietaries** - what we need to know to cook for you
7. **Anything else** - open, and a warm close

Each move narrows: who, why, when, the week, tonight, how to cook for you.
Dietaries lands after the guest has said they are eating with you, which makes
it care rather than paperwork.

**The trade-off, already weighed and accepted.** Pages save as they are left, so
the order is also the order in which answers are captured. Arrival and dietaries
are the two that matter operationally and this arc puts them third and sixth,
where the old order had them second and fourth. The owner chose the gentler
arc: the real risk was never a guest stopping at page four, it was a guest never
opening the form.

The companion question is still hidden for a single booking and for a party
whose second name Mews already carries, so the count is not always seven. It is
settled before the first page draws, as it is now.

---

## Copy

Changed lines only. Everything not listed stays as it is.

**Page 1.** Heading: `Who is coming with you?` becomes **`Additional guests?`**

**Page 5, first night.** Heading: `Will you dine with us on your first night?`
becomes **`Will you be dining with us on your first night?`**

The help line loses "one sitting" and gives the times instead:
**`Dining is from 6:00 to 6:30.`**

The two answers become **`Yes please`** and **`Not on the first night`**.

**Page 2, what brings you.** Read more becomes:
**`It changes the type of experience that you might be seeking, and we want to
make sure everyone is looked after.`**

**Page 4, eating.** Heading: `How do you plan to eat during your stay?` becomes
**`Where do you plan on eating during your stay?`**

Read more becomes: **`Our restaurant creates menus and meals for the number of
guests onsite. Knowing how often you plan on eating with us means less waste,
and a better experience on the nights that you do.`**

---

## Read more

The help text is in a `<details>` today, and its summary sits tight against the
options below it, so it reads as one of the answers.

- A plain button labelled **Read more**, becoming **Read less** when open.
- It belongs to the text ABOVE it. Margin above it, and clear space below the
  block before the answers start. Not attached to the buttons underneath.
- The revealed text is indented under a light left rule, so it reads as an
  aside rather than as more of the question.
- **Closed on every page, every time.** This is what keeps the constraints out
  of the guest's way: the invitation is on the page and the limit is one tap
  behind it. Do not make any of them open by default.

---

## Every page fits a phone

- The Back and Next buttons are **sticky at the foot**, outside the scrolling
  area, not at the end of the content.
- Every page fits a 390 x 780 screen **with its Read more open**. The mockup
  does; check each page rather than assuming.
- The step count sits above the buttons and inside the fixed footer.

---

## Removals

**Group size.** The "how many of you" chips go from the dining page. See
decision 2: `pax` must still be written, from the booking.

**Change an answer.** The button on the thank-you screen goes, and with it the
path back into a submitted form.

Understand what this costs before doing it, because it reverses a deliberate
decision with a comment explaining itself: plans change, and a form that refuses
to reopen sends the guest to the phone. Reception can still edit every answer at
the desk, so nothing is lost operationally, and the owner has accepted the
trade. **Leave the comment, rewritten to say what was decided and why**, rather
than deleting the reasoning with the button.

---

## What must keep working

Do not lose these while moving pages around. Each was built for a reason and
each has tests.

- **A page saves as it is left**, and `at` is written by the final send alone.
  The desk reads `at` to tell a form in progress from a finished one, and shows
  three states. Moving the pages must not change when `at` is written.
- **Everything an answer opens up stays on the page where the answer is given.**
  A guest must never say yes on one page and meet the cost of yes on the next.
  Dining yes no longer opens the pax chips, but the arrival note and the
  treatment days still open in place if those questions survive.
- **A returning guest resumes at the first page they have not answered**, and
  a guest who already sent it sees the thank-you.
- **`Other` with an empty note is refused.** It tells the kitchen there is an
  allergy and nothing about what it is, which is worse than silence because it
  looks answered.
- **Nothing about identity or dates is ever written back.** The link carries
  name and dates for display only; Mews owns them.

---

## Tests

`tests/pre_suite.py` is 114 assertions and most will need their page indices
moved. Do not delete an assertion to make it pass: if the behaviour it names is
still wanted, move it; if it is not, replace it with one that says what is
wanted now and why it changed, in place.

New assertions needed:

- The order of the seven pages, as a list, so a later reshuffle is deliberate.
- Every page fits 390 x 780 with its Read more open.
- Read more is closed on load, on every page.
- The nav is fixed to the foot and does not scroll with the content.
- The arrival control produces the value decided in 1, at both ends of the
  track and at a half hour in the middle.
- `pax` is still written, and equals the booking's adult count.
- The thank-you screen offers no way back in.

And check the two suites that read what this form writes: `fd_suite` for the
three form states and the arrivals ordering, `list_suite` for the printed
dietaries.

---

## House rules

`git fetch` before pushing. Publish with
`bash tools/publish.sh "<message>" <file> [<file>...]`, which ends in a hard
reset, so a modified file not passed is discarded. Run `python3 tests/run.py`
before publishing, not the suites one at a time.

**Bump `?v=` on any shared file you touch.** Not needed for this brief unless
`nala-shared.js` changes, but four changes went unbumped to 23 Aug and browsers
ran old copies for days.

Reasoning goes in the commit message, not in a comment above the change.

Report back rather than deciding alone on: anything in the three decisions
above, and anything in this brief that contradicts what you find in the code.
