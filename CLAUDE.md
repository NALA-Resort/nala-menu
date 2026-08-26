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

- `nala-shared.js` → `NAV_NEEDS` — the permission behind each menu link.
  A page missing from it is shown to everyone: until 22 Aug `publish.html`
  and `tag.html` were absent, so a housekeeper's menu offered to publish the
  dinner menu.
- `tests/phone_cases.json` — the phone rule's cases, read by both suites.
- `rules.json` — the database's permissions.

**Never** restate the menu in a suite. Four suites currently hold their own
copy of the menu order, which is why adding a page means editing them all. A
suite with its own copy can pass while the app is wrong.

### 2. Adding a page costs 14 edits today, and shouldn't

As things stand: the link is pasted into every page's `navdrop`, the
permission goes in `NAV_NEEDS`, and four suites need the menu re-typed.
That is the current reality — follow it, and do not skip the suites.

It is also the largest known drag on feature work here. The fix is to
generate the dropdown from one array instead of filtering pasted markup, so
a page with no entry has no link. Not built. Worth doing next time someone
is in `nala-shared.js` anyway — not as a standalone job, since it touches
all fifteen pages of a live system.

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
| Amber | `--amber:#F6EAD5`, border `--amberb:#C29A55`, ink `#8A6A2F` | attention, in progress, chase this (front desk's confirm queue, a form opened but unfinished) | failure |
| Green tile | `rgba(122,160,130,.26)` / `.65`, ink `#5E7D67` | done, confirmed (the Reservations dining tile) | — |
| Green pill/tick | `--green:#E4EDE2`, `--greenb:#7E937A` | a positive state or a selection mark | — |
| Terracotta tile | `rgba(184,106,90,.16)` / `.45`, ink `#9E6455` | a **negative answer** — not dining, declined. A fact a guest gave us | a failure |
| Red | `--red:#A8321E` | **failure only**: a send that failed, a delivery that failed, an error. Text and pills, never a whole tile | pending, unknown, "nothing yet" |
| Grey dashed, sunk | `opacity:.62`, dashed `--rule` | nothing to do here (vacant villa, unsendable number) | — |

The Reservations green and terracotta tiles are a contract between boards:
suites assert them by computed colour, not class name. Change them in one
place and the suites will name every other.

---

## When you break these rules

Sometimes you should. Write down why, in the file, next to the thing. A
comment explaining a deliberate exception is worth more than a rule nobody
can find the reasoning for.

---

## Still fanned out — fix when you next touch it

- **`?v=` across 14 pages.** Should be one number rewritten by a pre-publish
  script. Until then it is hand-maintained and easy to miss.
- **The menu, in fifteen copies.** See rule 2. Two things a generator must
  get right that pasted markup does by hand: each page omits its own link,
  and the permission keys are `resSheet` and `cleansBoard` — not the
  `resBoard`/`cleanBoard` you would guess.

---

## Running tests

Do **not** run the full suite after every edit. It takes ~15 minutes and will
time out an interactive session.

```bash
python3 tests/run.py --changed     # while working
python3 tests/run.py <suite>       # the one suite you touched
python3 tests/run.py               # once, before publishing only
```

Known failures, pre-existing, not yours: `rules` ×2, `tally` ×1, `cleans` ×2.
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
