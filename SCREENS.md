# Screens still to build

17 Aug. Companion to `GUEST-DATA.md`, which carries the data design. This is
the build queue.

---

## Widths, measured

The app has **no width media queries at all**, only print and height ones, so
nothing had ever been checked below the 390pt iPhone the styleguide mocks at. I
measured the four boards at 390, 360 and 320.

| Page | 390 | 360 | 320 |
|---|---|---|---|
| Tonight's Numbers | ok | ok | ok |
| Cleans | ok | ok | ok |
| Service Sheet | scroller | scroller | scroller + **stat bleed** |
| Clean Sheet | scroller | scroller | scroller |

**360pt Galaxy needs no work.** Everything that fits an iPhone fits a Galaxy.
The layout is fluid rather than breakpointed, which turns out to be why.

"scroller" is not a fault. The two printable sheets put their wide table in
`.scroller { overflow-x:auto }` deliberately, because they are A4 sheets read
on a phone. The page itself does not bleed.

**One real finding, at 320pt only.** The Service Sheet header stats push about
12pt past the right edge, so the whole page scrolls sideways. 320pt is the
narrowest phone still in use, older and budget Android. Worth fixing, not
urgent, and not a Galaxy problem.

**So the standard becomes: mock at 390, check at 360, and do not break at 320.**
Front Desk Arrival is the first screen built to that from the start.

---

## To build

### 1. Pre-arrival questionnaire, guest

`prearrival.html?b=<id>&n=<first>&s=<last>&a=<arrive>&d=<depart>`

Guest tier, no sign in. Four questions, chosen because they fit one phone
screen without scrolling and completion rate is the whole point: type of stay,
dining on the arrival night, allergies and dietary requirements, estimated
arrival time. Arrival time is the only one that feeds the Cleans board rather
than the kitchen, since it says which villa has to be ready first.

Writes to `/bookings/<id>/prearrival`. Never writes name, villa or dates: those
come from the link for display and from Mews for truth. Works before Mews has
the booking, which is the normal case at seven days out.

**Every question on the form is mandatory.** So a submitted form always
carries a dining answer, and "form done but the dinner question unanswered"
cannot happen. That state was designed for and then removed once the rule was
known.

**Which makes no form a tentative yes, not an unknown.** The kitchen cooks for
it: oversupplying is the cheap mistake and undersupplying is not, and reception
settles it at check-in either way. So on Front Desk Arrival every guest carries
a fork icon, and grey means assumed dining and still to be pinned down rather
than ignore this one. The kitchen's planning number is dining plus not sure;
only not dining is genuinely off the list. The three are still counted
separately because how firm a number is matters as much as the number.

**Answers are written on submission only, never as the guest types.** A
half-written record is indistinguishable from a considered one, so "Form done"
would come to mean "some fields exist" and reception would stop trusting it.
Incomplete guests are finished at the desk anyway, so a partial record adds a
state without adding an action. If losing a long form to a dropped connection
turns out to matter, save a draft on the guest's own phone rather than writing
partial records to the database: it costs nothing and creates no status.

**But the page MUST stamp an opened time when the guest lands on it**, separate
from submitting. Without it there is no way to tell a message that never
arrived from one that arrived and was ignored, and those need different
chasing: a wrong number needs another channel, an ignored message needs a
nudge. This mirrors what the dinner flow already has and the pre-arrival flow
does not.

Worth being precise, because it has been confused once already: the link icon
on Tonight's Numbers belongs to the NIGHTLY dinner message and is written when
a guest opens `index.html`. It says nothing about pre-arrival. The two sends
are separate and need separate signals.

**Estimated arrival is a picklist, not free text.** Six slots in the order
reception works through them: Before 2pm, Approx 2pm, 3pm, 4pm, 5pm, After 5pm.
The two open ended ones carry a compulsory note, because "before 2pm" with no
time is the answer that causes the problem it is warning about.

Stored as the slot key, so the arrivals list orders exactly. Free text was
tried first and it reads "late morning" and "after 5pm" correctly often enough
to be trusted and wrongly often enough to matter, which is the worst
combination.

**Blocked on one answer:** is type of stay a picklist, and if so what is on it.

Resist a fifth question without deciding which of the four it replaces.

### 2. Front Desk Arrival, reception

New, specified in conversation on 17 Aug.

Lists today's arrivals and shows at a glance who has completed pre-arrival and
who has not, because that is the receptionist's whole job on this screen.
Opens a guest, completes the same four questions, and sets dining or not for
tonight.

Writes to the same `prearrival` node the guest writes to, so there is one shape
and one place whoever typed it. It is edit rather than create: a guest who
answered half the form should see those answers, not a blank one. No record of
who filled it in.

Settled 17 Aug: the arrival night's dining answer comes from pre-arrival, not
from the nightly text, because guests check in after 2pm and the text would
arrive too late. Reception shows the guest the real menu at the desk and
confirms the answer still holds. Every arriving guest ends the day confirmed,
and confirmed includes not dining. See `GUEST-DATA.md`.

This is an input path into the Reservations screen, which is the chef's screen
and already exists. It is not a new output.

Closes the gap the paper process never could: today only some guests return the
form and the chef gets handwritten sheets.

### 2b. Allergy conflict at the desk. BUILT 17 Aug

The mechanic that already exists: the chef publishes a menu and tags which
dietaries each dish conflicts with, per day, at `/menutags/<date>`. When a
guest opts in for dinner and selects one of those dietaries, the guest page
flags it, tells them the menu contains it, and requires a note before the reply
will save. That is live today in `index.html` and covered by `index_suite.py`.

**Pre-arrival cannot do this, and that is the gap.** The form is filled days
ahead, when the menu for the arrival night does not exist yet. A guest can
declare a nut allergy and opt in for dinner on their arrival night and nothing
can be checked, because there is nothing to check against.

**On the day of check-in the menu IS live.** So Front Desk Arrival should
compute the conflict between the guest's declared allergies and that day's
published tags, and show it to the receptionist. It is the same comparison,
run at the one moment when both halves finally exist. The receptionist raises
it with the guest standing in front of them, which is a better conversation
than a warning on a phone days earlier.

How it was resolved, since the plan called for moving `menuConflicts()` out of
`index.html` into `nala-shared.js` and that turned out to be wrong:

`index.html` does not load `nala-shared.js` and must not. It is guest tier, and
a shared function would drag staff code onto a guest page. So Front Desk
Arrival compares the guest's dietaries against `/menutags/<date>` directly,
which is the same node the guest page's tags come from. Two comparisons, one
source of truth. Change what a conflict means and both have to change, which is
what keeps them honest.

The desk version names the course rather than the dish, because it does not
read `menu.json`. Reception is holding the menu, so "tonight's main contains
Nut allergy" is enough to start the conversation.

It warns and does not block. The guest page requires a note before saving;
reception is talking to the guest and can settle it out loud.

### 3. Registration cards, print

`registration.html`. One card per arriving villa, questionnaire answers filled
in or left blank for pen. Editable at reception with a save.

### 4. Write back to Mews

Not a screen. Selected answers appended to the reservation Notes through Update
reservation, so front desk staff working in Mews see dietaries without opening
the app. Free text, so nothing can query it, which is accepted. The app stays
the source of truth.

---

## Not a screen, but queued ahead of some of these

The guest page rewrite, stage 4. `index.html` and `welcome.html` take a booking
id, `responses` re-keys to it, and the URL parsing goes. Its real size is in
`MEWS-AUDIT.md` under the two paths section, and it is larger than the one line
the handover gives it.

---

## Order

Front Desk Arrival before the guest questionnaire, on the grounds that it is
unblocked and the questionnaire is not. Both use the same four questions and
write the same node, so building reception first settles the shape and the
guest page inherits it. If the picklist answer arrives first, that reverses.

Registration cards after both, since they print what those two collect.

Write back last, as planned.
