# Mews sync - setup jobs

Companion to MEWS-SYNC.md. Everything here needs an account only Ben has.
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

**Software:** Firebase console, console.firebase.google.com.
**Where exactly:** your project, then Realtime Database, then the **Rules** tab.

Only after job 3. Take the whole of `rules.json` from this repo and paste it
over what is there. It is a complete replacement built from the live copy, not
written from memory, so nothing existing is dropped.

Nothing breaks if this waits, because the new paths are currently covered by
the `$other` catch all and will function without it. It must land before any
real guest data does, because catch all means any signed in user can write it.

## After I hand you the Worker

### Job 5. Deploy the Worker

**Software:** Cloudflare dashboard, dash.cloudflare.com.
**Where exactly:** Workers and Pages, Create, then paste the source.

This is a second Worker, separate from the push sender you already run. Do not
add this to that one: it holds your VAPID key and no database credential, and
that is worth keeping true.

Four secrets to set, and I will name them exactly in the source: the sync
account's email and six digit code from job 3, and a shared secret you invent
for Zapier. Copy the deployed URL when it is done.

### Job 6. Build the Zap

**Software:** Zapier, from job 2.

Trigger: **Mews**, reservation event. Action: **Webhooks by Zapier**, POST, to
the Worker URL from job 5, carrying the shared secret. The field mapping will
be written out in the Worker source, so you are not guessing at names.

Test with one booking on the Mews demo property before pointing it at live.

## Later, at stage 3

### Job 7. GuestTouch message

**Software:** GuestTouch.

The triggered message, one week before arrival, with the booking id as the only
dynamic portion. Not needed until the pre-arrival page exists.

## What I am doing meanwhile

1. The `sync` role. Done, published.
2. `rules.json`. Done, published, waiting on job 4.
3. The Worker source. Next.
4. Stage 2, the `roomRecord()` merge, once data is landing.

Every one of those is a commit to this repo and needs nothing from you.
