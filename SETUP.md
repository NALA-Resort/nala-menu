# Mews sync - setup jobs

Companion to DESIGN.md. Everything here needs an account only Ben has.
Anything not listed is being done in the repo and needs nothing from you.

Five different pieces of software appear below, so each job names which one,
where it is, and who to be signed in as. If a job does not say Firebase, it is
not in Firebase.

## Do not do these

Listed first, because each one cost hours in a previous session.

- **Do not create the sync login in the Firebase console.** Job 3 is in the
  NALA app, on a page built for exactly this, and it creates the login and the
  staff record together. The console cannot create the record at all.
- **Do not create a Firebase service account.** An earlier draft of the plan
  called for one. It is not needed and would be worse: a service account
  bypasses the rules, a staff account is subject to them.
- **Do not enter any booking data by hand, anywhere.** If a booking is missing
  from a board, that is a bug in the sync, not a gap for you to fill. Tell me
  instead.
- **Do not paste the rules before job 3.** They grant a role that does not
  exist until the account does.

## Jobs 1 to 6 are done

The sync is live as of 16 Aug: a real booking reached Firebase and indexed
eight nights in villa 11. What follows is kept as the record of how it was
built. See DESIGN.md for what the live configuration actually is, which
differs from what these steps first said.

## Start now, nothing blocks these

### Job 1. Get the Mews access token

**Software:** Mews Operations, the PMS web app you run the property in.
**Signed in as:** a Mews user who can reach Marketplace.

1. Main menu, then **Marketplace**.
2. Search Zapier. Click **Explore**, then **Connect integration**.
3. Go to **My subscriptions**, find Zapier, click **Edit**.
4. Click the **access token** icon. Copy the token somewhere you can get at it.

Connect it to your demo property first if you want to practise. Mews recommends
that and it costs nothing.

This one is unavoidable and it is the front door. The alternative, registering
a webhook with Mews directly, is an email to their support and a wait, so it is
more friction now and better later.

### Job 2. Zapier account

**Software:** Zapier, at zapier.com.

Create an account if you do not have one, and add the Mews app to it using the
token from job 1. Stop there. The Zap itself needs the Worker URL, which does
not exist yet, and building it now means building it twice.

## After my commit, which has landed

### Job 3. Create the sync account

**Software: the NALA app itself.** Not Firebase, not Mews, not Zapier. This is
the Settings page you already use to manage staff.
**Signed in as:** admin.

https://menu.nalaresort.com/staff.html?v=16

Use that link rather than the menu. The `?v=` forces a fresh copy: the page
changed in this commit, and a phone holding the old one will not show the sync
option at all. Give GitHub Pages a minute after a publish before loading it.

1. Open the link, or the hamburger then **Settings**.
2. Tap **Add someone**.
3. Name: **NALA Sync**.
4. Role: **sync**. It is the fifth option, below housekeeping.
5. Tap **Create**, and **write down the six digit code**. It cannot be looked
   up later, by you or by anyone, and the Worker needs it.

That role can do nothing in the app: no boards, no marks, no menu, no
notifications, and it lands on no page. It exists only so the rules can name
it. It will appear at the bottom of the people list showing its code instead of
an address, which is normal for a passcode account.

### Job 4. Paste the rules

**Software:** Firebase console.
**Time:** about two minutes.

1. Go to **https://console.firebase.google.com**
2. Select the project **nala-menu**.
3. Left sidebar: **Build**, then **Realtime Database**.
4. Along the top of the database panel, click the **Rules** tab. You will see
   the current rules in an editor.
5. In another tab open
   **https://github.com/NALA-Resort/nala-menu/blob/main/rules.json**
   and click the **copy** icon at the top right of the file.
6. Back in Firebase: click into the editor, select all (Ctrl+A or Cmd+A) and
   paste over it. All of it. This is a complete replacement, not an addition.
7. Click **Publish**. It goes live instantly.

If it refuses to publish it will underline the line it dislikes. Send me the
message rather than editing it: the file is generated from the live copy and a
hand edit is how `extcancel` gets dropped.

## The Worker is written and published

Source: `worker/mews-sync.js`. Its suite is `worker/test.mjs`, 28 tests, run
with `node worker/test.mjs`.

### Job 5. Deploy the Worker

**Software:** Cloudflare dashboard.
**Time:** about ten minutes.

**Create it**

1. Go to **https://dash.cloudflare.com** and sign in.
2. Left sidebar: **Compute**, then **Workers & Pages**. (If your account still
   shows it at the top level, that is the same page.)
3. Click **Create**, then the **Workers** tab, then **Start with Hello World**.
   Do NOT choose Import a Git repository. You are pasting one file, not
   connecting this repo.
4. Name it **nala-mews-sync**. Click **Deploy**. It deploys the placeholder;
   that is expected.
5. Click **Edit code** (or **Continue to project**, then **Edit code**).
6. In the editor, select all of `worker.js` and delete it. Open
   **https://github.com/NALA-Resort/nala-menu/blob/main/worker/mews-sync.js**,
   click the **copy** icon, and paste the whole file in.
7. Click **Deploy** in the editor, then confirm.

**Add the four secrets**

8. Go back to the Worker, then **Settings**.
9. Find **Variables and Secrets** and click **Add**.
10. For each of the four: set **Type** to **Secret**, then the name and value:

| Variable name | Value |
|---|---|
| `SYNC_EMAIL` | the six digits from job 3, then `@staff.nala` |
| `SYNC_PASSWORD` | the same six digits on their own |
| `ZAP_SECRET` | a long random string you invent. Keep it, job 6 needs it |
| `FB_API_KEY` | `AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI` |

    Use **Add variable** between each one so all four go in together.
11. Click **Deploy** to apply them. Secrets do nothing until you do.

**Type must be Secret, not Text.** A Text variable is readable back from the
dashboard by anyone with access to the account. A Secret is not.

**Never put `SYNC_EMAIL` or `SYNC_PASSWORD` in this repo.** It is public, and
that address contains the passcode.

`FB_API_KEY` is a secret for tidiness only. Firebase web API keys are public by
design and this one is already in `auth.js` here. The rules protect the data,
not the key.

**Check it**

12. Copy the Worker URL. It looks like
    `https://nala-mews-sync.<your-subdomain>.workers.dev`
13. Open it in a browser. You should see **405 POST only**. That is correct: it
    proves the code deployed and refuses a GET. If you see the Hello World text
    instead, step 7 did not take.
14. Send me the URL. I cannot reach it, but I can tell you whether it looks
    right.

### Job 6. Build the Zap

**Software:** Zapier.
**Time:** about fifteen minutes.

**The trigger**

1. Go to **https://zapier.com** and click **Create**, then **Zaps**.
2. Click the **Trigger** box. Search **Mews** and select it.
3. Event: **Reservation Event**. Continue.
4. Account: connect Mews using the access token from job 1. Continue.
5. Click **Test trigger**. Zapier pulls a recent reservation. If nothing comes
   back, make a test booking on the Mews demo property and try again. Continue.

**The action**

6. Click the **Action** box. Search **Webhooks by Zapier** and select it.
7. Event: **POST**. Continue.
8. Fill the fields:

   - **URL**: your Worker URL from job 5, with the secret on the end, so
     `https://nala-mews-sync.xxx.workers.dev/?secret=YOUR_ZAP_SECRET`
   - **Payload Type**: **JSON**
   - **Wrap Request In Array**: no
   - **Unflatten**: no

9. Under **Data**, add these nine rows. Left side is typed by you exactly as
   written. Right side you pick from the Mews trigger fields using the **+**
   button:

| Key (type this) | Value (pick from Mews) |
|---|---|
| `Id` | the reservation Id |
| `FirstName` | guest first name |
| `LastName` | guest last name |
| `Phone` | guest phone |
| `StartUtc` | start / arrival |
| `EndUtc` | end / departure |
| `ResourceName` | the villa or space name |
| `State` | reservation state |
| `UpdatedUtc` | last updated |

10. Click **Continue**, then **Test step**.

**A pass looks like this.** The response body says `"ok": true` with an `id`, a
`villa` and a `nights` count. A `401` means the secret does not match. A `400`
means `Id` did not map. A `500` means the Worker reached Firebase and Firebase
said no, which is usually job 4 not being done.

11. **Publish** the Zap.

**Map `UpdatedUtc`.** It is the one that looks like metadata and gets skipped.
Webhook delivery is not ordered, and it is the only way the Worker can tell a
late old event from a new one. Without it a cancellation arriving after a
rebooking wins, and the villa silently empties.

**Test on the demo property first.** Point it at live only once one booking has
gone through cleanly end to end.

## Later, at stage 3

### Job 7. GuestTouch message

**Software:** GuestTouch.

The triggered message, one week before arrival. The page exists now, so this is
buildable, and it is the last thing standing between a guest and answering
before they arrive.

**The link, with the Mews field names on the right:**

```
https://menu.nalaresort.com/prearrival.html?b={Id}&n={FirstName}&s={LastName}&a={StartUtc}&d={EndUtc}
```

| Parameter | Mews field | Required |
|---|---|---|
| `b` | `Id`, the reservation Id | yes |
| `n` | `FirstName` | no, display only |
| `s` | `LastName` | no, display only |
| `a` | `StartUtc` | no, display only |
| `d` | `EndUtc` | no, display only |

Filled in, it looks like this:

```
https://menu.nalaresort.com/prearrival.html?b=3f9c2a71-88d4-4e0b-9c1f-2b6d5e7a1c04&n=Sarah&s=Whitfield&a=2026-09-04&d=2026-09-08
```

**`b` is the only one that matters.** It must be the reservation GUID, the same
one the sync writes under. Not `CustomerId`, which is the person rather than the
stay, and not the reservation Number, which is the five digit thing staff read
out in Mews and is only unique per property. If `b` resolves to any of those the
page loads and looks perfectly normal, and the answers land under an id nothing
reads.

**Name and dates are never written back.** They are Mews' facts and a copy
stored here would be stale the moment the booking changed. They exist so the
guest sees their own name and stay. See the display precedence note in
`DESIGN.md`: if `pms` has arrived, the page shows from that instead, because it
is fresher than the link by definition.

`StartUtc` and `EndUtc` arrive as full timestamps. The page reads the first ten
characters, so either the timestamp or a plain `YYYY-MM-DD` works.

**The parameter names are mine, not a standard.** If GuestTouch cannot emit a
parameter called `b`, that is a one line change at the top of the script block
in `prearrival.html`, where the five are read. Change the page, not the link.

**A note on reading field names off a Zapier screen.** Zapier prettifies them
for display: it adds spaces and capitalises, so `AssignedSpaceId` shows as
"Assigned Space Id" and `Id` shows as "ID". The raw key underneath is unchanged,
and the true spelling cannot be read off that list. It does not matter for the
sync, because `readReservation()` accepts every spelling seen and picks the
reservation id by GUID shape rather than by name. It matters here only in that
GuestTouch has its own merge tag list and Zapier's labels say nothing about it.

## What I am doing meanwhile

1. The `sync` role. Done, published.
2. `rules.json`. Done, published, waiting on job 4.
3. The Worker source. Done, published, with a suite of 28.
4. Stage 2, the `roomRecord()` merge. Next, once data is landing.

Every one of those is a commit to this repo and needs nothing from you.
