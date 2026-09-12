# The key-card encoder

How a villa's key cards get written, what runs where, and how to set it up.
The feature spans four places; each owns one thing:

| Piece | Where it runs | Owns |
|---|---|---|
| the card table, `/cards/<no>` | Firebase | the fact: one row per card in the world, keyed by the card's own number. The register IS these rows |
| the cut request, `/cutrun` | Firebase | which villas' cards are wanted right now - short-lived, ends when the cutting ends, never stored with the cards |
| the Keys page and its run screen | keys.html + nala-cards.js | issuing, the register, lost/found/remove, the cancel session. `cardRows`/`cardState` (nala-shared.js) are the only readers, held to `tests/cardstate_cases.json` |
| the key in the date row | front-desk.html | ONE shortcut: cut all arrival keys. Nothing else - no drop, no card facts on its forms (ruled 11 Sep) |
| the Key cards step | dashboard.html | a door to Keys. It counts the table's rows, rule 7 |
| `tools/nala-encoder.ps1` | the front-desk PC | the encoder. The only thing that moves plastic - and each move is one thing done to the table |
| `/cardauth`, `/cardlocks` | the mews-sync Worker (`worker/cards.js`) | the TTLock secrets, which never reach the desk PC |

The flow at the desk: Issue keys on the Keys page (or the Front Desk key for
all arrivals) → hold each card to the E3 as the run screen asks → a ROW
APPEARS at `/cards/<no>` as each one is cut → envelope as it goes green. A
card dies at 1pm on the guest's departure day (`CARD_CHECKOUT_HOUR`,
nala-shared.js — one number, change it there or nowhere). Because the row
is keyed by the plastic's own number, a re-cut card sheds its old row in
the same act — TTHotel's own register behaviour, mirrored.

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
role set to `encoder` — the role `rules.json` confines to the card nodes.
staff.html's role picker may not list `encoder`; setting the role value
directly in the console is fine, the rules read the string.

**3. The rules.** `rules.json` holds `/cards` and `/cutrun` (11 Sep,
replacing the retired `/cardjobs`); paste the file into the Firebase
console as usual. Until this is done the writes sit under the catch-all
rule — loose but working — and validate nothing.

**4. The desk PC.** Copy `tools/nala-encoder.ps1` into the encoder kit's
`dll\64` folder (the one holding `CardEncoder.dll`). Download it from
MAIN and nowhere else:

    https://raw.githubusercontent.com/NALA-Resort/nala-menu/main/tools/nala-encoder.ps1

**Never from a branch.** The old branch
`claude/web-app-tt-hotel-lock-vko6td` still carries the pre-rebuild
tally helper: its copy watches `/cardjobs`, a node nothing writes any
more, so it LOOKS like it is working while every run on the phone dies
with the encoder-offline verdict — which is exactly how the desk lost a
morning on 12 Sep. Nothing merges to main from that branch either. The
downloaded file is the right one if its first logged line says
`watching the card table`; `watching /cardjobs` is the old helper,
wherever it came from.

The settings — Worker URL, `HELPER_KEY`, the encoder account, the COM
port — live in `nala-config.ps1` beside it, so a fresh download of the
helper needs no editing (since 9 Sep; before that a CONFIG block at the
top was hand-filled on every update, and re-filling it is what every
stale-helper bug came down to). Run:

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
the card nodes. The TTLock secrets stay in the Cloudflare dashboard;
`hotelInfo`, the credential every card write needs, arrives minted and
expires in about ten minutes. A stolen desk PC carries nothing durable.

## Card stock

A blank card must be initialised to the hotel once before it can be written
(error 106 is this). Cards already in circulation were initialised when
TTHotel issued them. New stock: initialise in the TTHotel client for now; an
init pass in the helper is a small follow-up if the desk wants it.

## The helper's two duties (rebuilt 11 Sep on the card table)

- **The cut run.** The desk writes `/cutrun` `state:on` with a queue -
  one entry per villa: guest, qty, cut, expiry. The helper heartbeats
  `seen`, works the queue in villa order, and for every card cut writes
  a ROW at `/cards/<no>` in the same breath (villa, guest, cut-at,
  expiry, by), bumps `queue/<villa>/cut`, and sets `state:done` when the
  queue is finished. Skip shrinks a villa's qty to its cut; Stop or a
  closed run sets `state:off` and the helper stands down mid-wait. A
  card whose number the encoder will not report still gets a row, under
  a `u`-prefixed key only the Keys page's Remove can retire.
- **The cancel session.** Keys' Cancel keys button writes `/cancelrun`
  `state:on`; the helper heartbeats `seen`, and every card held to the
  E3 is read, named by its own row at `/cards/<no>` - a direct read,
  never a scan - wiped (CE_ClearCard), and its ROW DELETED: the wipe
  and the removal are one act. A card with no row (foreign plastic, or
  one already cancelled) is wiped all the same and reported villa `?`;
  the page says "Unknown card", normal desk business. Stop (or the
  page's offline verdict) sets `state:off`. One encoder, one duty at a
  time.
- **Released when idle.** The COM port is held only while a run or a
  session needs it, so TTLock's own program can use the E3 whenever the
  helper is quiet - no window juggling, no second encoder.
- **Issue more cards** is simply another run: the rows the guest already
  holds stand as filled seats on the run screen, and nothing continues
  from a written count - there is no written count.

## When something goes wrong

- **The run holds "Waking up..." then reports the encoder offline** —
  the helper is not running, or the PC is off. The request dies with the
  verdict (a queue never lies in wait); start the helper, press again.
- **Red "write failed" with a note** — the helper's own words, from the
  manual's error table. 106 means a foreign or uninitialised card; "re-plug
  the USB" means exactly that.
- **Everything refused after a rules paste** — check the `encoder` role
  spelling on the helper's staff account.

## Verified, and not

The store, the pages, the Worker relays and the rules are suite-covered
(`cards`, `cardworker`, `keys`, `frontdesk`, `dash`, `rules`). The helper
and the E3 cannot be exercised from the sandbox (HANDOVER.md: no egress,
no Windows, no encoder), so each helper path's first run at the desk is
its test. The old tally-era helper had every path proven live by 10 Sep
(writing, lift-off waits, serial recording, the cancel session wiping a
real card); the 11 Sep rebuild reuses those proven encoder mechanics
verbatim but ITS OWN paths - the /cutrun watch, the row writes, the
row-keyed cancel, the re-cut shed - are live-unproven until their first
desk run. Watch the helper's own narration on that run; it says one line
per action. TTLock's live field names for `/cardlocks` are read
tolerantly and confirmed on first live call — worker/cards.js marks the
spot.
