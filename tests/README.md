# Verification suites

Playwright suites with a fully mocked Firebase (auth SDK stubbed, every
database route intercepted, writes captured and inspected).

## Run them all at once

    python3 tests/run.py              # everything except the demo check
    python3 tests/run.py --changed    # only what covers your modified files
    python3 tests/run.py tally index  # by name
    python3 tests/run.py --demos      # include the demo drift check

The suites are independent: each owns its port, its browser and its stubbed
database. Nothing was making them serial except the habit of typing them out
one after another, which is what made them feel like a reason to skip them.

Every suite has a timeout, and one that stops is reported as `TIMEOUT` with a
name on it. Before that existed, a hang and slow progress looked identical from
outside, because every suite holds its output until the end.

The demo drift check is not in the default run. See the bottom of this file.

## Or one at a time

Run from the repo root with a local copy of the site:

    python3 tests/tally_suite.py     # 87  - Reservations
    python3 tests/list_suite.py      # 42  - Reservations Sheet (incl. Safari-fraction regression)
    python3 tests/hk_suite.py        # 22  - Clean Sheet
    python3 tests/cl_suite.py        # 193 - Cleans (incl. roles, Settings and the menu gate)
    python3 tests/auth_suite.py      # 30  - passcode sign-in and the email fallback
    python3 tests/index_suite.py     # 40  - the guest menu page
    python3 tests/fd_suite.py        # 123 - Front Desk Arrival
    python3 tests/pre_suite.py       # 46  - the guest pre-arrival form
    python3 tests/reg_suite.py       # 25  - registration cards
    python3 tests/pages_suite.py     # 10  - the site map, and every link on it
    python3 tests/stats_suite.py     # 38  - Statistics, incl. where the numbers come from
    python3 tests/tag_suite.py       # 45  - Menu Dietaries, incl. the destructive save
    python3 tests/debug_suite.py     # 44  - Diagnostics, incl. Clean Slate and the deletes
    python3 tests/print_suite.py     # 34  - Printable Menu, asserted on the PDF not the DOM
    python3 tests/welcome_suite.py   # 23  - the welcome page

The Mews sync Worker has its own, in node rather than Playwright because it
never runs in a browser:

    node worker/test.mjs             # 62  - Mews sync Worker

So do the database rules, which run on Google's servers and cannot be reached
by opening a page. targaryen evaluates them exactly as the database does:

    npm install targaryen            # once
    node tests/rules_test.js         # 68  - who may write what, and what shape

Two halves, and the first matters more. Before asking whether a bad write is
refused it asks whether every real write the app makes is still allowed: a
validate rule that is too strict does not look like security, it looks like
reception being unable to seat a guest. Every body in it was copied from the
code that sends it. `RULES_FILE=/path/to/rules.json node tests/rules_test.js`
points the same suite at another copy, which is how these were diffed against
the deployed ones.

    node tests/matrix_probe.js       # 8   - can a matrix in Settings be a real permission

Not a suite for anything that is built. It is a working prototype of the
permission matrix asked for on 18 Aug, kept because the answer was not obvious
and the first answer given was wrong. A matrix stored in the database CAN
enforce a permission, because the rules already read the database to find a
role, so ticking a box changes what is allowed with no paste. The probe pins
the shape that makes it safe: the manager is allowed regardless, a missing
matrix falls back to manager only, and nobody can tick their own box.

Counts drift. If yours do not match, the suite moved and this line did not:
trust the suite.

`print_suite.py` is the odd one. menu-print.html draws its menu with jsPDF, so
the page's own HTML is a staging area and reading the DOM would tell you
nothing about the sheet that comes out of the printer. The suite replaces jsPDF
with a stub that records every draw call and asserts against those, then checks
the screen and the paper agree. That last comparison is the one that did not
exist when the Service Sheet went blind to a whole node for two commits with
every suite passing.

They assert rendered outcomes, not markup: computed colours, fixed-footer
geometry, tap-target sizes, menu interaction, write bodies, and
order-independence of seating vs reservations. wk_harness.py loads res
tally in WebKitGTK (Safari's engine) at 390pt and prints layout geometry.

## Offline demo sheets

**Rebuilt on request, not on every change.** They are built from the real
pages, so any change to a sheet leaves them behind, and `demo_suite` fails the
moment that happens. That is the check doing its job, and it is still the wrong
thing to hold a publish on: the demos are shown to somebody who is not going to
sign in, and nobody looks at one during service.

So `demo_suite` is out of the default run, and `tests/run.py` instead ends with
a line saying how many have drifted. The drift is reported every run and never
blocks one. When somebody asks for a demo, rebuild and publish the four files
with whatever else is going out.

    python3 tools/make-demo.py

Rebuilds demo-tally.html, demo-reservations.html, demo-cleans.html and
demo-clean.html: standalone copies of all four staff pages with the CSS and shared JS inlined, Firebase and auth
removed, and fetch() replaced by a fixed busy-night dataset. No network at
all, so they open on a phone with no signal, and no tap can write anything.
A red band marks them on screen; it is hidden when printing.

Re-run after changing either sheet - the demos do not track changes.

## sweep_suite.py

Presses every control on every page, as every role, and asks whether anything
happened. Not what each control does, which the page suites cover, but that no
control is dead. Goes two levels deep, so it reaches the buttons that only
exist once a sheet is open. Also checks every page at 390, 360 and 320 for
sideways scroll.

Slow. Run a slice: `python3 tests/sweep_suite.py cleaners admin`.

## demo_suite.py

The four demo sheets are built by `tools/make-demo.py` and nothing rebuilds
them, so every change to a real sheet leaves them further behind, silently.
This rebuilds them in a scratch copy and fails if the committed files differ.

When it fails: `python3 tools/make-demo.py`, then publish the four demo files.

It also opens each demo in a browser and asserts it asks the network for
nothing, even after its buttons are pressed. That is checked by watching the
requests, not by searching the text: the database address does appear in each
file and is harmless, because fetch is replaced before anything uses it.

## coercion_test.js

Asks whether what the Worker sends is what the rules will accept. Two files
nobody edits together: rules.json is pasted into the Firebase console by hand,
the Worker deploys from the repo, and nothing connects them.

The failure this exists to stop is not a plain outage. The database refuses the
WHOLE write when one field fails validation, and the error is "Permission
denied", which reads like a credentials fault and sends the reader to the wrong
place. That happened on 18 Aug.

It reads the coercion helpers out of the Worker rather than copying them, so it
cannot pass against code that no longer ships.

    node tests/coercion_test.js
