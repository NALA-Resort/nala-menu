# Invitations: sending the menu link by SMS

Agreed with the owner by voice on 23 Aug. This file is the whole brief.

**Build all of it.** Two halves, and the order is page first because it is
useful the moment it exists: it is the only screen that shows who has not
answered about dinner.

- **The page**, `invitations.html`, which decides who to send to and records
  what was sent. Fully testable here, with the send stubbed.
- **The sender**, a Cloudflare Worker holding the ClickSend credential. Write
  it and publish it. You cannot test or deploy it: the sandbox reaches neither
  ClickSend nor Cloudflare, and the credential does not exist yet. Say so
  plainly when you hand it over rather than implying it has been run.

The owner sets up the ClickSend account and the Cloudflare secret. That is the
last step and it is his: see **Setup, which is not yours** below.

---

## Why this exists

Invitations go out through Guest Touch today, and its broadcast is all in-house
guests or nobody. The alternative is sending one at a time, which is slow at
five o'clock.

But speed is the smaller half. **Guest Touch is where the 22 Aug failure came
from**: the links went out with `{{bookingId}}` unmerged, so every confirmation
that evening was refused by the database while every guest was thanked for
nothing. A page that builds the link from the record it is looking at has no
merge field to fail, and no template engine between the booking and the URL.

That is the argument for this feature. Write it down where it can be read
later, because when somebody asks why the resort sends its own SMS, "it was
faster" is not the answer.

---

## What the page does

One screen. Everyone in-house tonight, in villa order.

### The four states a villa can be in

- **Ready** · in-house, no dinner answer tonight, has a phone number. **Ticked
  by default.** These are the whole point.
- **Answered** · already said yes or no. **Unticked, with the reason shown**:
  `Dining · 2 · answered 4:12pm` or `Not dining · set by reception`. Still
  tickable, because a guest who declined Monday may want to see Tuesday's menu.
- **Sent today** · already had one. **Unticked**, showing the time. Tickable,
  but sending a second identical message to the same guest is the thing that
  annoys, so it takes a second press. See Sending, below.
- **No number** · the booking carries no phone. **Not tickable**, greyed, with
  the reason on the row. It cannot be fixed here: the number comes from Mews.

A count at the foot, then one button: `Send to 6 guests`.

### Where the data comes from

One read of each. Everything needed is already stored.

- `fetchStays(todayKey())` gives `/stays/<date>/<villa>`, which carries `id`,
  `first`, `last`, **`phone`**, `adults` and `groupId` per villa. The phone
  number is already there; nothing new has to be synced.
- `/dinner/<date>` gives tonight's answers, with `status`, `pax`, `by` and `at`.
- `/invites/<date>` gives what has already been sent tonight. New node, see
  below.
- `fetchMenuAnywhere()` for whether a menu is published at all.

### Nothing sends before the menu is published

If no menu is published for today, the page **refuses** rather than warns:
the send button is disabled and the reason is on screen. A guest who taps the
link before the chef publishes gets a placeholder, and the message becomes a
lie about a menu that is not there.

Use the same test the guest page uses. Do not write a second opinion about what
"published today" means.

---

## The message

### Templates

A small set, chosen from a list, **editable before sending**. The owner asked
for editable; two constraints on that.

**The link is not editable.** It is appended by the page, not typed into the
box, and the box cannot contain one. A URL that a human can retype is a URL
that goes out wrong to fourteen guests at once, which is the failure this
feature exists to remove.

**Show the character count and the segment count** as it is edited. An SMS is
160 characters, and the link alone is about seventy, so most messages are two
segments. It matters less for cost than for the writer knowing what they are
doing.

Starting templates, in the resort's voice:

    Tonight's menu is ready. <link>
    Nala Resort

    Good afternoon. Tonight's menu, and a place to tell us if you will
    join us. <link>
    Nala Resort

    A reminder that we have not heard about dinner tonight. The menu, and
    the link to answer, is here. <link>
    Nala Resort

The resort's name is on every one of them. Australian rules require a
commercial sender to identify itself, and the guest should know who is texting
before they open a link.

### The link

Built by the page, fresh, at send time:

    https://menu.nalaresort.com/?b=<booking id>&r=<villa>

Both values come off tonight's stay record.

**Both parameters, not one.** The owner asked whether the villa alone would do,
since generating the link at send time already traps a room move. It does trap
the move, and that is worth having, but the booking id is doing a second job:
**it is the secret.** With `?r=12` alone, anybody can walk `?r=1` through
`?r=17` and set or overwrite the dinner answer for every villa in the resort.
There is a note in `index.html` recording that the previous scheme was
abandoned for exactly this, being keyed on a phone number and so guessable in
order. A villa number is worse: guessable in order, and there are seventeen of
them.

The booking id also carries the dietaries, which are written to
`/bookings/<id>/prearrival` so they follow the guest across nights. Without it
there is nowhere to put them.

**Build the URL in ONE function**, so it can be swapped later without touching
the guest page. A Mews id is a 36 character GUID and it is what makes these
messages two segments. The eventual fix is a short unguessable token per
booking, six or seven characters, resolving to the id. Not now: it needs a
lookup table and a resolver. But build so that later is a small change.

---

## Sending

### Where the credential lives

**Not in the browser, and not in this repo.** Same rule as the GitHub token and
the manager's mobile: the repo is public until `SECURITY.md` job 4.

The page calls a Cloudflare Worker, passing the caller's Firebase ID token. The
Worker verifies the token, checks the role, and only then talks to ClickSend
with a credential held as a dashboard secret.

**This pattern already exists here.** `notifyPush()` in `nala-shared.js` posts
`{ idToken, event, villa, user }` to `nala-push.ben-681.workers.dev`, and that
Worker verifies the token before acting. Read it before writing a new one:
either extend it or copy its verification exactly. Do not invent a third way of
proving who is calling.

### What the Worker must do

1. Verify the Firebase ID token. Reject anything unsigned, expired, or from
   another project.
2. Check the role may send. See Permissions below.
3. **Re-read the villa's stay and dinner cell server-side** and rebuild the
   link itself. The page proposes; the Worker decides. A browser can be edited,
   and a browser that can name any phone number and any message body is a
   browser that can send anything to anyone on the resort's sender ID.
4. Send, one message per villa.
5. Write the result to `/invites/<date>/<villa>` whether it succeeded or not.
6. Return per-villa results, so the page can show which failed.

### The record

`/invites/<date>/<villa>`, a new node. **No rules change needed**: `invites` is
not named in `rules.json`, so it falls to the `$other` catch-all, which grants
read and write to any signed-in user. Same as `/demo`.

    sentAt      ISO time
    to          the number as sent
    template    which one was used
    body        what actually went, after any edit
    status      sent | failed
    providerId  ClickSend's message id
    error       when it failed, verbatim
    by          the staff email that pressed send

`body` is stored because the templates are editable. Without it there is no way
to answer "what did we actually say to that guest", which is the question that
gets asked when a guest is confused.

### Sending twice

A villa already sent to tonight is unticked. Ticking it and pressing send is
allowed, but the button must say what it is about to do:
`Send to 6 guests, 1 of them again`, and that press confirms.

This is the same shape as Remove on the publish page and for the same reason:
the destructive-or-annoying action is a stride from the ordinary one on a phone
at service time.

### Failures

Per villa, not per batch. Four of six succeeding is the normal case for a bad
number, and it must be visible which two did not, on the row, with the reason.
A batch that reports "failed" as a whole tells nobody who to chase.

---

## Permissions

`editBookings`. It is reception's job and the manager's. Checked rather than
assumed: **admin and waiter** hold it, chef and housekeeping do not. There is no
`staff` role in `ROLE_GRANTS`, whatever older notes may say.

Add `invitations.html` to `NAV_NEEDS` in `nala-shared.js` at the same time as
the page, or it appears in every login's menu. That has happened twice.

It belongs in the hamburger's first group, with the screens you work on.

---

## The provider

**ClickSend**, and the reason is specific rather than commercial.

The owner wants replies to land in Guest Touch, on the mobile number Guest Touch
already uses. **Twilio cannot do that.** It sends from a number Twilio owns, or
from an alphanumeric sender ID like NALA which cannot be replied to at all.
Neither puts a reply in Guest Touch.

ClickSend supports an **own number**: a mobile you already hold, verified once,
and replies go directly to that handset rather than into ClickSend's dashboard.
That is exactly the model wanted. Sinch MessageMedia has the same feature and is
the fallback if ClickSend is unsuitable.

It also suits the architecture: a single authenticated POST, no SDK, which is
what a Worker wants.

Three things that are true of the own-number path and need to be known:

- **Verification expires after twelve months** and sending stops. Diarise it.
  A silent stop at five o'clock is the worst version of this.
- **Replies arrive on that handset at all hours**, which is presumably already
  true of that number.
- **Opt-outs are manual** on an own number. There is no automatic keyword
  handling, so if a guest replies STOP, somebody has to act on it.

Do not build a NALA alphanumeric sender as a fallback without checking the
rules again: ClickSend flags upcoming ACMA changes to alpha tag regulation in
Australia.

---

## Testing

The page is testable here in full, with the Worker call stubbed. The Worker is
not: the sandbox reaches neither ClickSend nor Cloudflare.

Assert at least:

- A villa with no dinner answer is ticked; one that has answered is not, and
  its reason is on the row.
- A villa with no phone number cannot be ticked at all.
- A villa already sent to tonight is unticked and shows the time.
- With no menu published, the send button is disabled and the page says why.
- The link built for a villa carries that villa's booking id AND its villa
  number, and comes from the stay record rather than from anything typed.
- The message body cannot be made to contain a second URL by editing.
- Every send writes an `/invites/<date>/<villa>` record, including failures.
- A partial failure names which villas failed.
- A role without `editBookings` never sees the page or its link.

**Do not test the Worker by calling it**, and do not test it by sending
yourself a message once a credential exists. There is no dry run. A live token
and a live sender ID is how a commit called `test` reached main on 23 Aug.

---

## Setup, which is not yours

The Worker needs a ClickSend account and an API credential, and neither exists.
Both are the owner's to create, in a browser, and none of it can be done from
here. Write the Worker to read its credential from the environment and leave it
at that.

What he has to do, in order, so the Worker can name what it expects:

1. Create a ClickSend account with the resort's real business details. An
   Australian street address is required and a PO box is refused: ACMA rules,
   enforced at registration.
2. Register the Guest Touch mobile as an **own number** and verify it. A code
   is sent to that handset, so whoever holds the phone has to be present.
3. Generate an API username and key.
4. Set them as Cloudflare Worker secrets in the dashboard, never in this repo.
   `wrangler.jsonc` has no vars block on purpose and must not gain one:
   declaring vars there overwrites what is deployed, and dashboard secrets
   survive a deploy untouched.

Name the two environment variables in your Worker and say what you called them,
so his last step is unambiguous.

## Not in this brief

- Short link tokens. Named above, deliberately later.
- Anything that reads replies. Replies go to Guest Touch and stay there. This
  app never sees them and should not pretend to.
- Scheduling or automatic sending. Somebody presses the button.

---

## House rules

`git fetch` before pushing. Publish with
`bash tools/publish.sh "<message>" <file> [<file>...]`, which ends in a hard
reset, so a modified file not passed is discarded. Run `python3 tests/run.py`
before publishing.

**Bump `?v=` on `nala-shared.js`** if you touch it, which adding to `NAV_NEEDS`
means you will. Four changes went unbumped to 23 Aug and browsers ran old copies
for days.

Reasoning goes in the commit message.

If something here contradicts the code, the code wins and this file is wrong:
fix the file in the same commit.
