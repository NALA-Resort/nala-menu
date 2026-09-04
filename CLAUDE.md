# nala-menu

Dinner menu and reservation system for a 17-villa resort. Live and
guest-facing. Read `START-HERE.md` and `HANDOVER.md` for what the system is
and where it stands.

This file is how features get added here. Claude Code reads it automatically;
chat sessions are pointed at it from `START-HERE.md`. It is one file rather
than two because of rule 1 below, which the first draft of it broke.

---

## How features get added

Read this before adding anything. It is short on purpose.

The rule behind all of it: **a fact lives in one file.** When you are about to
type something that already exists elsewhere, make a table and read it twice
instead of typing it twice.

---

## Why this file exists

Adding one page (`invitations.html`, 24 Aug) cost **28 mechanical edits**
before any feature logic:

| Edit | Files | Cause |
|---|---|---|
| Nav link pasted in | 10 | the menu existed in 10 copies |
| `?v=` bumped | 14 | the version is hand-maintained |
| Menu list re-typed | 4 suites | the menu existed in 4 more copies |

None of that was the feature. It was fan-out from duplication. The cost is not
just typing — it is that every copy is a chance to miss one, and a missed
`?v=` serves stale JavaScript from the service worker to a waiter mid-service.

---

## The rules

### 1. One list, many readers

If two files need the same fact, one of them owns it and the other reads it.

Already done this way — follow these:

- `nala-shared.js` → `NAV` — the staff menu: every page's hamburger is
  generated from it by `buildNav`, and each entry carries the permission
  behind its link (`NAV_NEEDS` is derived from it). An entry with the wrong
  key is shown to everyone: until 22 Aug `publish.html` and `tag.html` were
  unlisted, so a housekeeper's menu offered to publish the dinner menu.
- `tests/nav_canon.json` — the menu's shape as the suites assert it. The
  `phone_cases.json` pattern: `NAV` is what the app draws, this is what the
  tests expect, and whichever side a change misses fails by name.
- `tests/phone_cases.json` — the phone rule's cases, read by both suites.
- `tests/form_dinner_cases.json` — the guest's pre-arrival dinner answer as
  every screen must read it (`formDinnerCell`, nala-shared.js). Added 4 Sep,
  after the Reservations board, the SMS page and the front desk each read
  their own subset of that one fact and told reception three different
  things about the same villa.
- `rules.json` — the database's permissions.

**Never** restate the menu in a suite. Four suites held their own copy of
the menu order until 26 Aug, which is why adding a page meant editing them
all; they read `nav_canon.json` now. A suite with its own copy can pass
while the app is wrong.

### 2. Adding a page is one entry in `NAV`, plus the `?v=` bumps

The 28-edit story below is over: the menu markup left the pages on 26 Aug,
when the hamburger was redesigned (submenus, non-caps) and generated in the
same stroke. A new page is one entry in `NAV`, the same line in
`tests/nav_canon.json`, and the `?v=` bumps — which are still hand-
maintained, see below.

Two things the generator gets right that you would get wrong pasting: each
page omits its own link, and the permission keys are `resSheet` and
`cleansBoard` — not the `resBoard`/`cleanBoard` you would guess.

### 3. Duplication that cannot be avoided gets a shared table

Some duplication is forced. `normalisePhone` exists in `nala-shared.js` *and*
in `worker/send-invites.js`, because a Worker cannot import from the site.

That is allowed **only** with a shared table both copies are tested against —
here, `tests/phone_cases.json`. Add cases to the table, not to the suites.
A case added there fails whichever copy has not learned it.

### 4. Long runs do not belong in front of a human

The sweep suite is combinatorial — every control × every role × every page —
so it takes minutes and always will. That is fine. Making someone watch it is
not.

- **While working:** `python3 tests/run.py --changed` plus the one new suite.
- **Before publishing:** the full run, once.

`run.py` has a `COVERS` map for exactly this. Use it. Running everything after
every small edit is what burns the session and hangs the tool.

### 5. Prove the test can fail

Before trusting a green tick, break the thing it tests and watch that test go
red. A test that passes against broken code is worse than no test, because it
is believed.

---

## The colour law

Ruled by the owner, 25 Aug, after red crept into a band that only meant
"nothing yet". One meaning per colour, everywhere, so a glance at any board
reads the same:

| Colour | Tokens | Means | Never means |
|---|---|---|---|
| Cream row | transparent on `--cream:#F9F7F4`, border `--rule` | work to do (to send, unanswered) | — |
| True white | `#fff` | an editable surface: inputs, the message box, editor cards | a status |
| Light grey fill | `rgba(28,28,26,.045)`, border `--rule` | sent, waiting on the other side; unknown promises nothing | done |
| Amber | `--amber:#F6EAD5`, border `--amberb:#C29A55`, ink `#8A6A2F` | attention, in progress, chase this (front desk's confirm queue, a pre-arrival form **incomplete** — see the three states below) | failure |
| Green tile | `rgba(122,160,130,.26)` / `.65`, ink `#5E7D67` | done, confirmed (the Reservations dining tile) | — |
| Green pill/tick | `--green:#E4EDE2`, `--greenb:#7E937A` | a positive state or a selection mark | — |
| Terracotta tile | `rgba(184,106,90,.16)` / `.45`, ink `#9E6455` | a **negative answer** — not dining, declined. A fact a guest gave us | a failure |
| Red | `--red:#A8321E` | **failure only**, and the one exception below. A send that failed, a delivery that failed, an error. Text and pills, never a whole tile | pending, unknown, "nothing yet" |
| Grey dashed, sunk | `opacity:.62`, dashed `--rule` | nothing to do here (vacant villa, unsendable number) | — |

The Reservations green and terracotta tiles are a contract between boards:
suites assert them by computed colour, not class name. Change them in one
place and the suites will name every other.

### Red's one exception: an allergy

Ruled by the owner, 29 Aug, closing a question that had been re-opened
twice. An allergy wears red — the solid `.dpill-al` on Reservations, the
red words on the printed Reservations Sheet — and that is not a hole in the
law, it is the law's edge.

The rule red protects is that red must never mean *pending, unknown or
nothing yet*. An allergy is none of those. It is the one fact on a kitchen
screen that can hurt somebody, and the reader scanning for it is scanning
for danger, which is the reading red already carries. Nothing else in the
app competes for that: terracotta is a guest's negative answer, amber is
chase this. Neither says "stop".

So: **red may mean hazard, but only hazard about a person.** Not a busy
state, not a rejected form, not a colour picked because a thing is
important. If you are about to reach for red and the thing is not a failure
or an allergy, it is the wrong colour.

Two things this exception does NOT extend to, both settled already:

- **Selection never wears red.** Publish's dietary pills filled solid red
  until 27 Aug, when a page with a few on it became a wall of red and the
  one red *ring* that meant a confirmed guest's allergy vanished into it.
  Grey fill, red only as a ring. A hazard that has to compete with a
  selection for the same colour loses.
- **Dead CSS carrying a description of the app is not inert.** `tag.html`
  held orphaned red `.tick` rules under a comment calling this an open
  question, months after it was answered on the page that actually draws
  them. Removed 29 Aug. Delete the rule and the story with it.

### The pre-arrival form has three states, and the colour IS the state

Ruled by the owner, 28 Aug, superseding his own ruling of 26 Aug that the
Front Desk row tint read *completeness of the answers*. That ruling left two
systems describing one thing: a tint computed from the answers, and an `at`
stamp written by something else. Nothing reconciled them, so villa 17 could
read Form completed on Pre-arrival SMS and amber at the desk while holding
nothing at all, and no screen offered a way out.

| State | Row | Means |
|---|---|---|
| not started | grey, `todo-form` | nobody has answered anything |
| incomplete | amber, `part-form` | somebody has, and it has not been marked complete |
| completed | green, `done-form` | the guest pressed Send, or the desk marked it complete |

Three things follow, and they are the whole model:

- **Editing and saving change no state.** Reception adds what it hears across
  the day; that is not a claim the form is finished.
- **One control moves it**, the sheet's `Mark as completed`, available only
  once the mandatory answers are in — **dinner, dietary and massage**, and
  massage is not owed by a one night stay, whose guest form never asks it.
  The same control walks it back, in terracotta, and asks first.
- **Arriving is not finishing.** Check in is a *visual move of the tile* so
  reception can see who is here. It touches the form's state not at all, and
  it asks for nothing before it will move: a control that refuses is not a
  visual move. It is a toggle, so the way back from an accidental press is to
  press it again.

There is no third button. `Confirm arriving` is gone, and so is `confirmedAt`:
the field recorded that reception had been through the answers and **nothing
in the app ever read it** — `isConfirmed` was defined and never called. Once
the state moved to its own gated control, the only thing that button still did
was un-arrive a guest, under a name that said the opposite. Values already in
the database are left alone; nothing reads those either.

`formState` in `nala-shared.js` is the only thing that says which state a
booking is in, and both boards read it. Two readings of one state is how they
came to disagree. `prearrival.html` cannot read it — it is a guest page and
loads no staff code — so its half of the contract is
`tests/form_questions.json` and `tests/onenight_cases.json`, which both
suites answer to.

Buttons have a law of their own — **the button law, STYLEGUIDE.md** (ruled
26 Aug): one solid primary per surface, destructive actions wear terracotta
outline and always confirm before writing. Read it before adding any button.

---

### 6. Match the ceremony to the change

Rules 1 to 5 were written after a data model went wrong and after five tests
passed against broken code. They are aimed at facts and at state. Applied at
full weight to a label or a colour, they cost more than the change is worth.

Written 31 Aug, after moving one text span and adding one icon took half an
hour of the owner's time: eight serial runs of a 200 second suite, two rounds
of mockups, and a multiple choice question about a wording he had already
given. His words: "I have other apps being built at five times the speed of
this one."

The tier is set by **what the change can break**, not by how many lines it is.

| Change | What it needs |
|---|---|
| The data model, permissions, the colour law, anything two screens read | All of rules 1 to 5. A shared table, a mockup, a mutation proof each. |
| Layout, copy, an icon, a tint | Build it. One screenshot at 390. Tests for the behaviour, not for the pixels. One mutation proof for the batch, not one each. |
| A typo, a comment, a `?v=` bump | Change it. |

Three habits that make the difference, all learned the hard way:

- **Tests run in the background.** Never make somebody watch a suite. Start
  it, keep working, report once.
- **Mutations go in one run.** Mutate, run, restore, repeat, inside a single
  script. Five proofs is one job, not five.
- **Make the call.** A mockup is for when the shape is genuinely open. When
  the owner has already said what he wants, build that, and say afterwards
  what it cost. He was overruled twice on 31 Aug and was right both times.

And read the width rule as written, in STYLEGUIDE.md: **mock at 390, check
at 360, do not break at 320.** Breaking means a sideways bleed or a control
nobody can reach. A name clipping at 320 is not breaking. 320 is an iPhone
SE 1st generation, from 2016; nothing sold since is narrower than 375.

---

## When you break these rules

Sometimes you should. Write down why, in the file, next to the thing. A
comment explaining a deliberate exception is worth more than a rule nobody
can find the reasoning for.

---

## Still fanned out — fix when you next touch it

- **`?v=` across 14 pages.** Should be one number rewritten by a pre-publish
  script. Until then it is hand-maintained and easy to miss.
- **Destructive buttons predating the button law** (STYLEGUIDE.md). spa.html
  obeys it; every other page's cancels and deletes are still solid or quiet
  ink with no confirmation. Dress and confirm them when you next touch the
  page.

---

## Running tests

Do **not** run the full suite after every edit. It takes ~15 minutes and will
time out an interactive session.

```bash
python3 tests/run.py --changed     # while working
python3 tests/run.py <suite>       # the one suite you touched
python3 tests/run.py               # once, before publishing only
```

Known failures, pre-existing, not yours: `cleans` ×2, and `rules` ×2 where
`rules` can run. `tally` ×1 was on this list and has not failed for some
time; taken off 29 Aug, because a stale list of expected failures is how a
real one gets waved through.

Three suites report NO RESULT rather than failing in a container that lacks
their tools, and that is not a break either: `rules` and `coercion` need
node's firebase test module, `list` needs `pdftotext`.

Anything else is a real break.

## Publishing

`tools/publish.sh` pushes to `main` and GitHub Pages serves it to guests within
minutes. **There is no dry run and no staging.**

Never publish without being asked to, in that session, in as many words. A
green suite is not permission.

Every reply that ends a piece of work closes with this block, exactly, so the
answer to "is it live?" is never buried in prose (ruled by the owner, 26 Aug,
after it was):

    Published: yes / no
    Firebase rules change: yes / no
    Human requirements: what only the owner can do, or none
    Ready to publish? yes / no, and what blocks it if no

"Firebase rules change: yes" means rules.json moved and needs its paste into
the console - say whether the feature limps or fails without it.

## Secrets

Nothing secret goes in this repo — it is public. Worker credentials live in
the Cloudflare dashboard. Tokens pasted into a chat are burned; say so and add
them to the rotation list in `SECURITY.md`.
