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
