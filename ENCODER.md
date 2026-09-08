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
dies at 11:00 on the guest's departure day (`CARD_CHECKOUT_HOUR`,
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
`dll\64` folder (the one holding `CardEncoder.dll`), fill in the CONFIG
block at the top — Worker URL, `HELPER_KEY`, the encoder account, the COM
port if known — and run:

    powershell -ExecutionPolicy Bypass -File nala-encoder.ps1

It narrates one line per action and Ctrl+C stops it. Once trusted, Task
Scheduler → run at log on, hidden, is the set-and-forget shape.

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
