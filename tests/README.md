# Verification suites

Playwright suites with a fully mocked Firebase (auth SDK stubbed, every
database route intercepted, writes captured and inspected). Run from the
repo root with a local copy of the site:

    python3 tests/tally_suite.py     # 60 checks — res tally
    python3 tests/list_suite.py      # 22 — res print (incl. Safari-fraction regression)
    python3 tests/hk_suite.py        # 17 — HC print
    python3 tests/cl_suite.py        # 22 — HC tally (incl. management menu gate)

They assert rendered outcomes, not markup: computed colours, fixed-footer
geometry, tap-target sizes, menu interaction, write bodies, and
order-independence of seating vs reservations. wk_harness.py loads res
tally in WebKitGTK (Safari's engine) at 390pt and prints layout geometry.
