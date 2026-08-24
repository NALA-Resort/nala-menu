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

- `nala-shared.js` → `NAV` — the menu. Adding a page is one line.
- `tests/phone_cases.json` — the phone rule's cases, read by both suites.
- `rules.json` — the database's permissions.

**Never** restate the menu in a suite. Read `NAV`. A suite with its own copy is
a suite that passes while the app is wrong.

### 2. A page is one line

Adding a page means: create the file, add one entry to `NAV`, done. If you
find yourself editing ten files, stop — you are working around this rule
rather than using it.

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

## When you break these rules

Sometimes you should. Write down why, in the file, next to the thing. A
comment explaining a deliberate exception is worth more than a rule nobody
can find the reasoning for.

---

## Still fanned out — fix when you next touch it

- **`?v=` across 14 pages.** Should be one number rewritten by a pre-publish
  script. Until then it is hand-maintained and easy to miss.
- **The nav refactor itself.** `NAV` exists, but pages still carrying pasted
  markup need converting to `renderNav(role)` as they are touched. Do not do
  all fifteen at once for its own sake; do each as you are in the file anyway.

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

## Secrets

Nothing secret goes in this repo — it is public. Worker credentials live in
the Cloudflare dashboard. Tokens pasted into a chat are burned; say so and add
them to the rotation list in `SECURITY.md`.
