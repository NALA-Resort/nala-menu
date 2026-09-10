# The key-card encoder

How a villa's key cards get written, what runs where, and how to set it up.
The feature spans four places; each owns one thing:

| Piece | Where it runs | Owns |
|---|---|---|
| the queue, `/cardjobs/<date>/<villa>` | Firebase | the fact: which villas' cards are wanted, and where each stands |
| the key menu and run screen | front-desk.html | queuing, cancelling, watching. `cardCell` (nala-shared.js) is the only reader of a job's state, held to `tests/card_cases.json` |
| the Key cards step | dashboard.html | a door to Front Desk. It gathers, rule 7 |
| `tools/nala-encoder.ps1` | the front-desk PC | the encoder. The only thing that moves a job past `queued` |
| `/cardauth`, `/cardlocks` | the mews-sync Worker (`worker/cards.js`) | the TTLock secrets, which never reach the desk PC |

The flow at the desk: the key in the Front Desk date row → Encode all keys
(or one villa from its sheet, with a quantity) → hold each card to the E3 as
the run screen asks → envelope each villa's cards as it goes green. A card
dies at 1pm on the guest's departure day (`CARD_CHECKOUT_HOUR`,
nala-shared.js — one number, change it there or nowhere).

## Setting it up, once

Everything below is the owner's to do; none of it is in this repo's power.

**1. Cloudflare dashboard — five secrets on the `nala-mews-sync` Worker**,
exactly these names (worker/cards.js documents each):

    HELPER_KEY        any long random string you invent
    TT_CLIENT_ID      TTHotel Pro → Integration page
    TT_CLIENT_SECRET  same page, behind View
    TT_ACCOUNT        same page, the h_… account
    TT_PASSWORD       same page. Its md5 (32 hex) is also accepted,
                      so the plain text need not be stored anywhere

**2. Firebase — the encoder account.** Create a staff account the way the
sync account was made (HANDOVER.md job 3): six digits `@staff.nala`, and its
role set to `encoder` — the role `rules.json` lets touch `/cardjobs` and
nothing else. staff.html's role picker may not list `encoder`; setting the
role value directly in the console is fine, the rules read the string.

**3. The rules.** `rules.json` gained `/cardjobs`; paste the file into the
Firebase console as usual. Until this is done the feature fails politely:
every queue attempt is refused and the page says the job did not save.

**4. The desk PC.** Copy `tools/nala-encoder.ps1` into the encoder kit's
`dll\64` folder (the one holding `CardEncoder.dll`). The settings — Worker
URL, `HELPER_KEY`, the encoder account, the COM port — live in
`nala-config.ps1` beside it, so a fresh download of the helper needs no
editing (since 9 Sep; before that a CONFIG block at the top was hand-
filled on every update, and re-filling it is what every stale-helper bug
came down to). Run:

    powershell -ExecutionPolicy Bypass -File nala-encoder.ps1

It narrates one line per action and Ctrl+C stops it.

**Start it with the PC** (asked by the owner, 10 Sep: the window IS the
system - closed, jobs queue and nothing writes). Win+R, `shell:startup`,
Enter; in the folder that opens, New > Shortcut, location:

    powershell -ExecutionPolicy Bypass -WindowStyle Minimized -File "C:\...\dll\64\nala-encoder.ps1"

with the real path. It then starts minimized at every log on. Two edges:
it starts at LOG ON, not power-on - a PC sitting at the password screen
overnight runs no helper until the morning log in; and a crashed script
stays down until the next log on, visible as jobs stuck at queued. If
that ever recurs, the upgrade is a Task Scheduler job that restarts it.

## What the desk PC holds, and why that is fine

The PC keeps two credentials: `HELPER_KEY`, which opens only the Worker's
two read-only relays, and the encoder account, which the rules confine to
`/cardjobs`. The TTLock secrets stay in the Cloudflare dashboard;
`hotelInfo`, the credential every card write needs, arrives minted and
expires in about ten minutes. A stolen desk PC carries nothing durable.

## Card stock

A blank card must be initialised to the hotel once before it can be written
(error 106 is this). Cards already in circulation were initialised when
TTHotel issued them. New stock: initialise in the TTHotel client for now; an
init pass in the helper is a small follow-up if the desk wants it.

## The Keys page's half (added 9 Sep)

The helper also serves keys.html:

- **Serials on record.** Every card's number (CE_GetCardNo) is appended to
  the job's `nos` as it is written, so a held card can always be named.
- **The cancel session.** Keys' Cancel cards button writes `/cancelrun`
  `state:on`; the helper heartbeats `seen`, and every card held to the E3
  is read, matched against the serials on record, wiped (CE_ClearCard),
  reported under `/cancelrun/done`, and counted `back` on its job. Stop
  (or the page's offline verdict) sets `state:off`. Write jobs wait while
  a session runs: one encoder, one duty at a time.
- **Released when idle.** The COM port is held only while writing or
  cancelling, so TTLock's own program can use the E3 whenever the helper
  is quiet - no window juggling, no second encoder.
- **Issue more cards** continues from `written`: cards already in the
  guest's hands are never recut.

## When something goes wrong

- **Row holds amber "waiting for the desk PC"** — the helper is not
  running, or the PC is off. Jobs keep; start the helper.
- **Red "write failed" with a note** — the helper's own words, from the
  manual's error table. 106 means a foreign or uninitialised card; "re-plug
  the USB" means exactly that.
- **Everything refused after a rules paste** — check the `encoder` role
  spelling on the helper's staff account.

## Verified, and not

The queue, both boards, the Worker relays and the rules are suite-covered
(`cards`, `cardworker`, `frontdesk`, `dash`, `rules`). The helper and the
E3 cannot be exercised from the sandbox (HANDOVER.md: no egress, no
Windows, no encoder): `nala-encoder.ps1` ships reviewed but unrun, and its
first run at the desk is its test. TTLock's live field names for
`/cardlocks` are read tolerantly and confirmed on first live call —
worker/cards.js marks the spot.
