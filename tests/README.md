# Verification suites

Playwright suites with a fully mocked Firebase (auth SDK stubbed, every
database route intercepted, writes captured and inspected). Run from the
repo root with a local copy of the site:

    python3 tests/tally_suite.py     # 69 - res tally
    python3 tests/list_suite.py      # 29 — res print (incl. Safari-fraction regression)
    python3 tests/hk_suite.py        # 21 - HC print
    python3 tests/cl_suite.py        # 55 - HC tally (incl. management menu gate)
    python3 tests/auth_suite.py      # 6  — sign-in when the Firebase SDK does not load

They assert rendered outcomes, not markup: computed colours, fixed-footer
geometry, tap-target sizes, menu interaction, write bodies, and
order-independence of seating vs reservations. wk_harness.py loads res
tally in WebKitGTK (Safari's engine) at 390pt and prints layout geometry.

## Offline demo sheets

    python3 tools/make-demo.py

Rebuilds demo-tally.html, demo-reservations.html, demo-cleans.html and
demo-clean.html: standalone copies of all four staff pages with the CSS and shared JS inlined, Firebase and auth
removed, and fetch() replaced by a fixed busy-night dataset. No network at
all, so they open on a phone with no signal, and no tap can write anything.
A red band marks them on screen; it is hidden when printing.

Re-run after changing either sheet — the demos do not track changes.
