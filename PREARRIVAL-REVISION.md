# Pre-arrival form: the 23 Aug revision

Agreed with the owner by voice on 23 Aug, against a mockup he approved. This
file is the whole brief. If anything here contradicts an older note, this wins.

Most of it is `prearrival.html` and `tests/pre_suite.py`. Two parts are not:
the arrival control also lives in `front-desk.html` and `registration.html`,
and the covers number is read by `tally.html`, `list.html`, `stats.html` and
`registration.html`.

**No rules change and nothing to paste into the Firebase console.** That was
true of an earlier draft and is not true of this one: the longer key list still
validates as a string, and a half hour approved by reception is a number
between 11 and 23, which `arriveApproved` already allows as `14.5`.

Read all of it before starting. Building the easy parts first leaves the
arrival control and the covers number looking like small tidy-ups when they are
not.

---

## The three questions, answered 23 Aug

The owner answered all three. They are written here rather than deleted,
because each changes something outside this form.

### 1. The arrival time: more slot keys, not a new shape

**Keep the list of keys and lengthen it.** This is his call and it is the safer
one: `etaIndex()` orders arrivals by a key's POSITION in the list, so a longer
list in the same order needs no new sorting logic, and every existing record
stays valid because its key is still in the list.

    before2 · 14 · 1430 · 15 · 1530 · 16 · 1630 · 17 · after5

Nine, where there were six. `14` still means 2pm, so nothing already stored has
to be migrated or read twice.

**Four files hold a copy of this list and all four must change together.**

- `prearrival.html`, `ETA_SLOTS`, the guest's own control.
- `front-desk.html`, `ETA_SLOTS`, used by `etaIndex()` to sort the arrivals
  board and by `etaLabel()` to print it.
- `registration.html`, a lookup OBJECT rather than an array, printing the label
  on the card a guest signs. Its fallback is `ETA_SLOTS[slot] || slot`, so a
  key it does not know prints raw: miss this file and `1430` appears on a
  registration card. It is easy to miss because it is a different shape from
  the other two.
- The cleans board ETA work, wherever it maps a key to an hour.

**Reception must be able to approve a half hour too**, or the desk cannot agree
to what the guest asked for. `arriveApproved` is a number and the rule accepts
anything from 11 to 23, so **14.5 is already legal and there is no rules change
and nothing to paste into the console**. `paintApproved()` in `front-desk.html`
loops whole hours today; it needs half steps and a label that reads `2:30pm`.

**Before 2pm and After 5pm still demand a note.** A compulsory field appears
beneath the control when either end is chosen, and the page will not advance
without it. This already works and must survive the change to a scroller: it is
the whole reason those two answers are useful rather than vague.

### 2. Group size: the guest is not asked, and pax is optional

The question goes. **Mews knows the adult count**, and this form already reads
it: `paintGreeting` uses `pms.adults` to decide whether to show the companion
question, so the number is in hand before any page draws.

The owner is **not confident the count is actually being sent** through Zapier,
so `pax` is optional rather than assumed:

- Write `pax` from `pms.adults` when it is there.
- When it is not, write nothing rather than zero. Every reader treats a missing
  `pax` as no covers, and zero covers is a table nobody lays, but a wrong number
  is worse than an absent one: reception fills it at the desk, where they
  already can, and an absent number is visibly absent.
- **Do not add a guest-facing fallback question.** The owner removed it
  deliberately.

Worth confirming against a live Zap run whether `AdultCount` arrives. The Worker
picks it under `AdultCount` or `adults`. If it never arrives, this needs
revisiting and the answer is a desk job, not a guest one.

### 3. The treatments question stays

It stays, and so does every other question. The mockup was approving the design
and the flow, not the question set: the treatments page was missing from it and
the owner had not agreed to that.

**Eight pages, not seven.** Treatments sits after dietaries and before Anything
else, so the run of care questions stays together: what you cannot eat, then
what we can arrange for you.

Group size is the one question that does go, and only because he asked for it
by name.

## The page order

Eight pages, in this order, and the order is the point. Food was appearing at
three, four and six with an unrelated question between, which is what made it
feel like skipping backwards and forwards.

1. **Additional guests** - who is coming
2. **What brings you to Nala** - why, and it sets the tone
3. **What time do you expect to arrive** - getting here
4. **Where do you plan on eating during your stay** - the week
5. **Will you be dining with us on your first night** - tonight
6. **Dietaries** - what we need to know to cook for you
7. **A massage or treatment** - what else we can arrange
8. **Anything else** - open, and a warm close

Each move narrows: who, why, when, the week, tonight, how to cook for you,
what else we can arrange. Dietaries lands after the guest has said they are
eating with you, which makes it care rather than paperwork, and treatments
follows it so the two care questions sit together.

**The trade-off, already weighed and accepted.** Pages save as they are left, so
the order is also the order in which answers are captured. Arrival and dietaries
are the two that matter operationally and this arc puts them third and sixth,
where the old order had them second and fourth. The owner chose the gentler
arc: the real risk was never a guest stopping at page four, it was a guest never
opening the form.

The companion question is still hidden for a single booking and for a party
whose second name Mews already carries, so the count is not always eight. It is
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
question 2 above: `pax` is still written, from the booking's adult count when
Mews sends one, and left absent rather than zero when it does not.

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

- The order of the eight pages, as a list, so a later reshuffle is deliberate.
- The nine arrival keys, as a list and in order, in all four files that hold a
  copy. A test that reads one file's copy proves nothing about the other three,
  and `registration.html` prints an unknown key raw onto a card a guest signs.
- Choosing either end of the arrival track demands a note, and the page does
  not advance without one.
- Every page fits 390 x 780 with its Read more open.
- Read more is closed on load, on every page.
- The nav is fixed to the foot and does not scroll with the content.
- The arrival control produces the right key at both ends of the track and at
  a half hour in the middle.
- `pax` equals the booking's adult count when Mews sends one, and is absent,
  not zero, when it does not.
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

Report back rather than deciding alone on anything in this brief that
contradicts what you find in the code. The three questions at the top are
answered and are not open again.

One thing to raise rather than solve: if a live Zap run shows the adult count
is not arriving from Mews, say so instead of inventing a source for the covers
number.
