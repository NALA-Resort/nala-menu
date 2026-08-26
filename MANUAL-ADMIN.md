# Nala app: the manager's sheet

One page. What each screen is for, and why it behaves the way it does.

Sign in with your email and passcode. Your role comes from a record in the
app, never from your address, so changing who you are is a Settings change and
not an email change.

---

## The five screens you own

| Screen | What it answers |
|---|---|
| **Reservations** | Who is eating tonight, and how many |
| **Reservations Sheet** | The same thing on paper, for the kitchen and the floor |
| **Front Desk Arrival** | Who is arriving, what they told us before they came |
| **Cleans** | Which villas need work today and which are done |
| **Settings** | Who has a login, and who gets told what |

Plus **Statistics**, **Diagnostics** and the **site map**, which are yours
alone.

---

## Reservations: read the tiles, not the list

Every villa is a tile, and its colour is a claim about the world:

- **Vacant** - nobody is booked into that villa tonight. Nothing to chase.
- **Awaiting** - somebody is in it and has not said yes or no to dinner.
- **In** - dining, with the party size on the tile.
- **Out** - not dining tonight.

The distinction between vacant and awaiting is the whole design. "Awaiting"
is a list of people to ask. If empty villas counted as awaiting, the figure
would read seventeen on a quiet night and you could not act on it.

**A villa that has a guest in it but reads vacant is a fault, not a state.**
It means the booking never reached the app. Tell whoever is building it, with
the villa and the date.

**The speech bubble** carries dietaries and notes. It has two headings, and
they are not decoration:

- *Tonight's dining notes* - given for tonight.
- *Previous dining notes* - given on an earlier night of the same stay, with a
  line saying not to cook to it without asking.

A guest's dietary is an answer to one night's invitation. Treating Monday's
answer as Tuesday's is how a wrong dietary reaches a plate.

**A staff answer outranks a guest answer.** Once you or reception set a
villa, the guest's own link cannot overwrite it. That is deliberate: reception
has usually just spoken to them.

---

## Front Desk Arrival

One card per arriving villa. Green with a fork means they told us they are
dining. Tapping reads back exactly what they sent on the pre-arrival form.

Confirming and checking in are two separate facts. A guest who has arrived has
arrived, and editing their answers afterwards does not un-arrive them.

---

## Cleans

Each villa carries a job for the day: **clean** (they leave today),
**service** (they are staying on), **pre-arrival**, or **vacant**.

The app works the job out from the dates. You can override it by hand, and
your choice beats what the dates imply, because you know things Mews does not.
**Only you can set the job.** Housekeeping marks their own work; a waiter can
say a villa looks free and can mark a departure. Neither can set the job.

The timer beside an available villa is the only place on that board where
colour means time rather than state:

- **green** under ten minutes - turned around fast
- **ink** from ten
- **amber** from fifteen
- **red** from twenty - the guest is coming back

---

## Settings

Three things live here.

**Logins.** Add a person, give them a role, and they get exactly the screens
that role allows. Removing someone here removes their access immediately; the
Firebase login itself still needs deleting separately, which frees the
passcode for reuse.

**What each role may do.** A grid of jobs against the three roles below you.
Every box starts where the app shipped it, and a box you change is marked
*changed* so you can see at a glance what you have fiddled with. You are not a
column, because you always have everything, and a column of ticks nobody may
untick teaches people the ticks do nothing.

There is no box for Settings itself. Giving somebody the power to hand
permissions out is not a permission, it is a second manager, and that is done
by changing their role in the list above, where you can see it.

**One of the seven is real, the other six are polite.** "Change what a villa
needs" is enforced by the database: untick it and that person cannot set a job
even if they find another way in. The other six hide the button. That stops an
honest mistake, which is what it is for, and it is not a lock. If somebody
must genuinely be unable to do a thing, change their role.

**Notifications.** A grid of events against roles. Tick who gets told what,
and set quiet hours. "Menu published" is on for you and nobody else: the chef
already knows, they just published it.

Beside Settings in the same menu group sits **Flags**: the short facts you can
pin under a guest's name - VIP, Travel agent, Breakfast included, whatever you
define there. You tick them per booking on the Front Desk sheet (only you: a
flag is a statement about the booking's standing) and they print under the
guest's name on the FOH Sheet, where the whole floor reads them. One flag is
automatic and is not on the list: a booking whose Mews rate is Luxury Escapes
wears that pill by itself. Hide takes a flag off the desk's chips without
unticking anyone; Delete, offered once a flag is hidden, removes it from the
list for good. Either way a booking already ticked keeps its pill until
somebody unticks it, so nothing a person recorded is silently dropped.

---

## Diagnostics: the screen to be careful with

Yours alone, and it can delete live data. Every destructive tool works the
same way: it lists what it would remove, and a second button removes only what
was listed. Read the list.

- **Clean slate** wipes the operational data. A node it cannot read says so
  and is skipped, rather than counting as empty. That distinction once made a
  wipe report success and delete nothing.
- **Merge tag junk** finds records where a mail merge failed and the guest is
  called `{{firstname}}`.
- **Two villas, one booking** offers only the villa Mews disagrees with, and
  offers nothing at all when Mews cannot settle it. Deleting the wrong one is
  worse than leaving both, because both is at least visible.
- **Orphan pre-arrival answers** finds guest answers whose booking Mews has
  cancelled or never had. A stay that is merely in the past is never listed:
  those are the words of a guest who came.
- **What the boards will show** runs the real merge for any date, read only.
  It is the fastest way to tell three things apart that look identical on a
  tile: the PMS knows them, a guest opened their link, or nobody knows
  anything.

---

## The two things that are not in the app

**The menu** is published by the chef pushing a file, not by writing to the
app. That is why the app only notices a new menu when a board is open.

**Mews is the authority on who is where.** The app never argues with it. If a
guest is moved, their answer is dropped rather than carried to the new villa,
because a booking made for one villa does not necessarily hold for another.
The empty villa on the board is telling reception to ask again.
