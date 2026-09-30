# Chat: the guests' messages, and the tasks they become

Agreed with the owner in chat on 29 Sep 2026. This file is the brief, the
record of what was decided, and the setup, which is his.

**Called Chat since 30 Sep** (the owner: "I would like this module to be
called Chat from now on and in menus and all references"). Until then it
was Guest Contact, and its files keep that name, so links and the stored
Settings switch keep working: `guest-contact.html`, the Worker
`nala-contact` (`worker/guest-contact.js`), this file, and the
`/permissions/open/guest-contact` switch. The owner's own setup steps, to
print and tick off, are the doc *Chat: your setup steps*.

**Published 29 Sep as the admin's alone, with a demo at
`guest-contact.html?demo`** (made-up guests, no sign-in). Nothing here
reaches a guest until the steps under *Going live* are done, in order.

---

## The brief, in his words

> "This would be a completely new module, let's call it Chat. It
> would be able to operate just like Guest Touch, whereby guests are
> filtered by upcoming, in-house and past, based on their booking dates.
> This makes it easy for us to send the guest a message and for them to
> reply to us. Currently we send pre-arrival forms via our web application
> and the reply is caught by Guest Touch. The reply should be caught by our
> application. This would save us from having an additional application."

> "WhatsApp is a major upgrade that I'd be willing to invest time to
> accomplish."

> "This chat service is predominantly a task request. [Guests] ask for some
> drinks by the pool or an umbrella to their room. So I would like that
> message to be able to be tagged or marked as done or marked as no task
> required."

> "I wanna be able to get this module up and running and tested without it
> actually sending messages to the guests because we will be using it on a
> live application."

---

## What was decided

**Supplier: Twilio**, because ClickSend has no WhatsApp. One Australian
mobile number carries both SMS and WhatsApp. Twilio's plain Messaging API,
not its Conversations API, and not a fork of `twilio-conversations-demo-react`.
Conversations would keep a second copy of every thread at Twilio, behind its
own logins, with one open conversation allowed per guest number; the demo is
a separate React app with a build step, a generic chat with no bookings, and
it keeps staff passwords in plain text. The thread lives in Firebase beside
the booking, where every board already reads.

**The everyday texts stay on ClickSend until the end** (the owner, 29 Sep):
Invitations, Pre-arrival, Spa reminders and external invitations keep going
out through ClickSend from the Guest Touch mobile while this is built and
tested. See *The switch-over* for how they move.

**Every guest message is sorted** - No task, or Task and the team that does
it - and a task is open until someone presses Done. Two requests in one
message are a task each. A reply closes nothing.

**Each team closes its own tasks, on its own login** (the owner's answer).
Which teams a login does is set per person in Settings, General. The six
teams to start: Bar, Kitchen, Housekeeping, Maintenance, Spa, Front desk -
renamed, added to or removed on that page's Teams tab. A removed team is
retired rather than deleted, so its tasks keep its name, and it can only
go once nothing of it is open.

**WhatsApp only for a guest who asks for it** (the owner: "The reason we
would choose to use WhatsApp is if it's an international number and they
have requested that we contact them on WhatsApp"). Staff switch it on in
the guest's conversation; the switch records who and when, because the
request is the consent Meta requires. A guest who writes to us on WhatsApp
is answered there. Everyone else gets SMS.

**Who may read and answer:** admin, manager and waiter logins - the same
permission as the SMS pages, `editBookings`.

**Decided by the build, overrule any:** Upcoming looks 30 days ahead and
Past 30 days back, and search reaches every conversation; staff send text
only, guests' photos come through; Done never messages the guest; a guest
who texts STOP is shown as opted out and nothing is sent to them.

---

## How it works

**Chat** (`guest-contact.html`, top of the menu after Front Desk).
Every guest by booking, on three tabs by their dates. Each row is the colour
of where the conversation stands (`contactRowState`, the colour law):

| Row | Colour | Means |
|---|---|---|
| New | white, with a count | a message nobody has sorted yet |
| Task open | amber | sorted, and a team's task still open |
| Sent, no reply | the waiting grey | only we have written |
| All done | done green | everything they sent is sorted, nothing open |
| No messages | sunk, dashed | nothing either way, or no mobile on the booking |

A number on no booking - a caller about dinner, a guest from months ago -
still lands on In-house, its number in place of a name.

Tap a guest for the conversation, drawn as the iPhone draws one (the owner,
30 Sep, with a screenshot of his Messages): the guest's words on the
iPhone's grey, ours on its blue, the time centred over each stretch of
talk. Under each of the guest's messages: **No task** or **Task**, then
the team. A task shows amber with **Done** until someone closes it, then
green with who did.

**Every message both ways is in it** (the owner, 30 Sep: "every outgoing
and incoming message including dinner invitations and pre-arrival form"):

- Everything typed here, both ways, and every approved WhatsApp message.
- Every text the SMS pages sent this number: the pre-arrival form and its
  reminder, each night's dinner invitation, spa reminders, and for a
  number on no booking, an outside guest's dinner invitation. Each says
  under it what it was, who sent it and whether it arrived.
- A text sent again, the pre-arrival reminder most often, keeps the one
  it replaced: `send-invites.js` carries it under `earlier` on the page's
  own record, five at most, so neither drops out of the conversation.
  It needs that Worker's paste and the rules paste, in either order: until
  both, a text sent again replaces the first, as it always has.
- Every message a guest sends to the Twilio number, SMS or WhatsApp. Until
  the everyday texts move to Twilio (`SMS_VIA`, below), a guest who
  answers a text ClickSend sent is answering ClickSend's number, and that
  reply is not here; after it, it is.

**The box says which way a message goes before it goes:**

- *Sends by SMS* - the guest's number, free text.
- *Sends on WhatsApp, free text until 3:14pm tomorrow* - the guest wrote on
  WhatsApp in the last 24 hours.
- *Past 24 hours* - WhatsApp only carries wording Meta approved. Choose
  *A quick question* or, for a guest still to arrive, *Your arrival*; their
  reply opens free text again. Or **SMS instead**.
- *This guest texted STOP* - nothing can be sent until they text START.

**Tasks** (`tasks.html`, beside it in the menu). Each login sees the open
tasks of its teams, in the guest's own words, and presses Done. The desk
sees every team. The menu entry counts what is open.

A task carries what the team needs to do it (the owner, 29 Sep: "can we
get some drinks by the pool? This becomes a task with no other
information attached"):

- **The conversation since the request**: every message after it until
  Done - the desk's "what would you like?" and the guest's "two G&Ts and a
  lemonade" - and the guest's photos. Only that stretch: a team's login
  reads no other part of a guest's conversation.
- **The desk's note**: typed under *Task* when the task is made, or with
  *Note* on the open task afterwards, for what the conversation does not
  say - *charge to villa 9*, *bring the ladder*.

**Who may reply is a switch per role** (the owner, 30 Sep: "a toggle in
settings for a role being able to respond to messages"): *Reply to guests*,
Settings, General, Roles. It ships on for the admin, the manager and the
waiter - the desk, as before it was a switch - and off for the chef and
housekeeping.

- A role switched on that does tasks gets **Reply** on each open card,
  beside Done: a box that says which way it goes (WhatsApp, SMS, or past
  WhatsApp's 24 hours so SMS), and Send. It goes to that task's guest and
  nobody else, and only until Done. The approved WhatsApp wording stays
  the desk's.
- Switched off, a login reads - its tasks, or at the desk the whole
  conversation - and cannot send. Chat says so where the box
  was.
- The admin and the manager always may. The masseuse is not on the grid,
  so never may: an outside contractor's reach is a rules decision.

The Worker decides, not the page: `mayDo`, the twin of the page's `can()`,
held to `tests/contact_cases.json` "grants"; a team's reply names its task,
and the Worker checks the login is on that task's team, the task is open,
and sends to the task's guest.

**The Dashboard** has a Guest messages card beside Arrivals, today only: how
many guests have a message to sort and how many tasks are open, and a door
to Chat. It reads both counts from the readers the two pages use.

**If a guest has no WhatsApp**, WhatsApp says so a few seconds after a send
(Twilio error 63024 or 63003). The Worker sends the same words by SMS and
remembers the number as SMS only, until the guest writes on WhatsApp.

---

## The data

One fact to a place (CLAUDE.md, rule 1):

| Node | Holds | Written by |
|---|---|---|
| `/contact/<number>` | one guest's thread: last message, which way they wrote, WhatsApp consent, opted out | the Worker; the consent switch by the desk |
| `/contactmsgs/<number>/<id>` | each message in and out, with its Twilio status | the Worker; how it was sorted by the desk |
| `/contactnew/<number>/<id>` | a guest message nobody has sorted | the Worker adds, the desk removes by sorting |
| `/tasks/<team>/<id>` | a task, open then done, and the desk's note (`note`, `noteBy`, `noteAt`) | the desk makes it and writes its note; the team or the desk closes it |
| `/contactsettings/teams/<team>` | a team's name, whether it is retired, and who does its tasks (`members/<login>`) | the admin, in Settings |

`<number>` is the guest's number without its plus, e.g. `61412345678`.

The rules let the Worker's own login (role `contact`) write messages and
nothing else, so no browser can claim a message went that did not; let the
desk sort messages, make tasks and record consent, in its own name; and let
a team's login see its own team's tasks and close one, in its own name, and
nothing more.

Shared readers, both copies held to `tests/contact_cases.json`: `waWindow`,
`contactChannel` and `contactTemplateText` live in `nala-shared.js` and again
in `worker/guest-contact.js`.

---

## Setup, which is the owner's

In this order. Steps 1 to 3 wait on Twilio and Meta, so start them first.

1. **Twilio account and number.** Create the account and upgrade it from
   trial. Submit the Australian regulatory bundle (legal business name and
   ABN/ACN, the ASIC company extract, proof of address), then buy a +614
   mobile number that can send and receive SMS. Up to three business days,
   sometimes longer.
2. **WhatsApp sender.** A Meta business portfolio, then WhatsApp Self
   Sign-up in the Twilio console on that same number, with the display name
   Nala Resort and the logo. Business verification is optional at this size.
3. **The two approved messages**, in the Twilio console's Content Template
   Builder, category Utility, each with a sample value per variable. Note
   each one's Content SID (it starts HX).
   - **A quick question**: `Hi {{1}}, it's Nala Resort with a quick question
     about your stay. Could you reply to this message when you have a moment?`
     Sample for {{1}}: James.
   - **Your arrival**: `Hi {{1}}, we look forward to welcoming you to Nala
     Resort on {{2}}. If there is anything we can prepare before you arrive,
     just reply to this message.` Samples: James, Saturday 3 October.

   The words must stay exactly these: the app previews and records its own
   copy (`CONTACT_TEMPLATES`, held to `tests/contact_cases.json`).
4. **The Worker's login.** Settings, General, Add someone: name *Guest
   Contact Worker*, role `contact`, a six digit passcode. Its address is the
   six digits then `@staff.nala`, as the sync account's is.
5. **The rules.** Paste `rules.json` into Firebase console, Realtime
   Database, Rules, Publish. Without it the Worker's writes and the desk's
   sorting are refused: the feature fails, it does not limp.
6. **The Worker.** Cloudflare dashboard, Workers, create `nala-contact`,
   paste `worker/guest-contact.js`, and set these secrets:
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` - from the Twilio console
   - `TWILIO_FROM` - the number, `+614XXXXXXXX`
   - `TWILIO_WA_FROM` - the same number, once WhatsApp is approved; leave it
     unset until then and everything goes by SMS
   - `TPL_QUESTION_SID`, `TPL_ARRIVAL_SID` - the two Content SIDs
   - `CONTACT_EMAIL`, `CONTACT_PASSWORD` - step 4's login
   - `FB_API_KEY` - `AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI`
   - `TEST_NUMBERS` - your own phones, separated by commas. **While this is
     set, nothing goes to any other number.** The page says Test mode.
7. **Point Twilio at the Worker.** In the Twilio console, on the number (and
   on the WhatsApp sender), set *A message comes in* to Webhook, HTTP POST,
   `https://nala-contact.ben-681.workers.dev/twilio/in`. Receipts need no
   setting: each message carries its own.
8. **Teams.** Settings, General, Teams: rename, add or remove teams until
   they are the resort's. Then each person, on the Staff tab: switch on the
   teams whose tasks they do.
9. **Publish** the pages, when asked in as many words. It can come before
   Twilio, straight after the rules (step 5): Chat and Tasks
   arrive as the admin's alone - their menu entries, the pages and the
   Dashboard card - for every other login, manager and masseuse included.
   Try them with the real bookings: every guest on the three tabs, the
   Teams tab, Tasks. Until the Worker and Twilio exist no message comes
   in and none can go, and the page says so at the top.
10. **Open to the staff** when you are ready: Settings, General, Teams, the
    *Open to the staff* switch. From then on each login sees them as its
    permissions say; off takes them back to you alone. No publish needed.
    Nothing can reach a guest while `TEST_NUMBERS` is set, whoever sees the
    pages - that is the Worker's job, not the menu's.

## The demo, before Twilio

`guest-contact.html?demo` (29 Sep): the same two pages with made-up guests,
and no sign-in. A bar at the top offers:

- **A guest writes** - pick a guest, WhatsApp or SMS, and what they say; it
  arrives New, as a real one would.
- **Look as** - Reception sees everything; Ray, Marco and Freya are team
  logins (Maintenance, Kitchen, Spa) and land on Tasks.
- **Start again** puts the made-up guests back; **Leave demo** ends it.

Everything else is the real page: sorting, tasks, Done, replies and their
receipts, WhatsApp's 24 hours (James, arriving in four days, is past them).
Nothing reaches the live app or a guest: the database is a copy held in the
browser tab, and the messenger is played there too (`contact-demo.js`,
held to `tests/contact_demo_suite.py`, which watches the network).

The made-up guests have what a real stay has: each one's pre-arrival text,
each night's dinner invitation, and for Sarah the pre-arrival reminder, a
spa reminder and her answer to last night's invitation.

**The demo moves with the module** (the owner, 30 Sep: "Keep update the
demo as we go"): a change the owner can see is in the demo in the same
commit, and `contact_demo_suite.py` checks it there.

The demo needs the pages published to be opened on a phone; without
`?demo` the pages are the real ones, the admin's alone until opened.

## Testing on the live app

Only the test phones can be messaged. From them:

- Text the number: the message appears under In-house, as a number on no
  booking, New. Sort it: No task, then a Task for a team; check the team's
  login sees it on Tasks and closes it.
- Make a test booking in Mews with one test phone on it: it appears on the
  right tab, by name, and a first message to it goes.
- WhatsApp the number from a phone that has WhatsApp: the box offers
  WhatsApp free text for 24 hours. From a phone without WhatsApp, switch
  WhatsApp on and send *A quick question*: it should arrive by SMS instead.
- Send a photo on WhatsApp: it shows in the conversation. Try one by
  picture message (MMS) too, but it may not arrive: Twilio's Australian
  MMS launch (June 2025) was for sending, with receiving still to come.
  That is Twilio's limit, not a fault here; WhatsApp photos are the sure way.
- Text STOP, then START.

## Going live, and the switch-over

1. **Remove `TEST_NUMBERS`** in Cloudflare. Chat can now message
   guests; the everyday texts are still ClickSend's.
2. **Alerts.** Staff phones buzz once the push Worker (`nala-push`) knows two
   events, and `BUZZ` is set to `1` on `nala-contact`. The push Worker lives
   only in Cloudflare, so its code has to come into this repo first. The
   change it needs:
   - `guestMessage` - to the roles ticked for it in Settings, Notifications
     (admin, manager and waiter by default); text *Villa 7 - new message*;
     opens `url` from the payload.
   - `guestTask` - to the logins in `/contactsettings/teams/<team>/members`,
     `team` from the payload; text *Villa 7 - Maintenance task*; opens
     `/tasks.html`.
   - `guestMessage` is sent by `nala-contact` itself, signed in as the
     `contact` login, with no `actor`: the push Worker has to accept that
     login as a sender.
   Until `BUZZ` is set nothing is sent to it, and the menu counts still work.
3. **ClickSend sends from the Twilio number.** Verify the Twilio number as an
   *own number* in ClickSend (its code arrives in Chat as a message;
   if ClickSend sends it from a name rather than a number, Chat has
   no thread to put it in, so read it in the Twilio console under Monitor,
   Logs, Messaging), then set `CLICKSEND_FROM` on `nala-invites` to it. The
   everyday texts still go through ClickSend, but replies land in Guest
   Contact. The SMS pages do not check Chat's STOP list meanwhile:
   the owner, 29 Sep, "not required, it will be a short transition". A
   guest who texts STOP in that window shows as Opted out in Chat.
4. **Guest Touch** can go once guests texted from its number have checked
   out: their replies still go there until then.
5. **The everyday texts move to Twilio.** Built, behind a switch (29 Sep).
   Paste `worker/send-invites.js` into `nala-invites` - safe at any time:
   until the switch is set it sends through ClickSend exactly as now. Add
   `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and `TWILIO_FROM` beside its
   ClickSend secrets, the same three `nala-contact` holds. Then set
   `SMS_VIA` to `twilio`: every text - tonight's menu, the pre-arrival form,
   spa reminders, external guests' invitations - goes from the Twilio
   number, and delivery is checked at Twilio. Texts already sent through
   ClickSend are still checked at ClickSend. Deleting `SMS_VIA` moves the
   texts straight back. After this, the pre-arrival form, menu and spa
   texts can go on WhatsApp too, each as an approved template of its own.

---

## Not built yet

- Staff sending photos.

## Tests

- `worker/contact-test.mjs` (run.py `contactworker`): Twilio's signature,
  checked against Twilio's own published example; inbound SMS, WhatsApp and
  photos; STOP and START; who may send; the 24 hours; the approved messages;
  the test list; a first message only to a number on a booking; receipts in
  and out of order; the SMS fallback, once; photos only from Twilio; a
  team's reply, only with the switch, only to its open task's guest.
- `tests/contact_suite.py` (`contact`): both pages at the fixture's 3:20pm,
  in two zones, against the same table; and the team list as all three
  pages offer it, Settings' Teams tab included.
- `tests/rules_test.js`: every write the Worker, the desk and a team make,
  and what each may not.
- `tests/dash_suite.py` (`dash`): the Dashboard's Guest messages card.
- `worker/invites-test.mjs` (`invworker`): the everyday texts through Twilio
  once `SMS_VIA` is set, and through ClickSend until then.
- The sweep, paper and colour suites read both pages.

Nothing here has touched Twilio, Meta or Cloudflare: the sandbox reaches
none of them. The first real message is the real test.
