# nala-menu

Dinner service tool for NALA Resort. Start with **PLAN.md** for what to build
next and in what order, then **STYLEGUIDE.md** before changing anything visual.
**HANDOVER.md** has the current state, but check PLAN.md first: several of its
gaps and backlog items are out of date as of 17 Aug.

Supporting documents: **GUEST-DATA.md** for who owns which data and why,
**SCREENS.md** for the screens still to build, **GAPS.md** for what the
architecture implies and the repo lacks, **MEWS-AUDIT.md** for the sync audit,
which carries a correction notice at the top.


`rules.json` is a copy of the live Realtime Database rules, kept here so a
change can be reviewed and diffed. It is NOT deployed from the repo: paste it
into the console (Realtime Database, Rules) and Publish. Keep it in step by
hand.
