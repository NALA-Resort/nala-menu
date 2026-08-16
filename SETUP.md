# Mews sync - setup jobs

Companion to MEWS-SYNC.md. Everything here needs an account only Ben has.
Anything not listed is being done in the repo and needs nothing from you.

## Do not do these

Listed first, because each one cost hours in a previous session.

- **Do not create the sync login in the Firebase console.** The Settings page
  creates the login and the record together. Job 3 below is the whole of it.
- **Do not create a Firebase service account.** An earlier draft of the plan
  called for one. It is not needed and would be worse: a service account
  bypasses the rules, a staff account is subject to them.
- **Do not enter any booking data by hand, anywhere.** If a booking is missing
  from a board, that is a bug in the sync, not a gap for you to fill. Tell me
  instead.
- **Do not paste the rules yet.** They grant a role that does not exist until
  job 3 is done. Order matters here; see job 4.

## Start now, nothing blocks these

**Job 1. Mews access token.**
Mews Operations, main menu, Marketplace. Search Zapier, Explore, Connect
integration. Then My subscriptions, find Zapier, Edit, and the access token
icon. Copy the token somewhere you can get at it. Connect it to the demo
property first if you want to practise; Mews recommends that.

Unavoidable, and it is the front door. The alternative, registering a webhook
with Mews directly, is an email to their support and a wait, so it is more
friction now and better later.

**Job 2. Zapier account.**
If you do not have one, create it and add the Mews app using the token from
job 1. Do not build the Zap yet: it needs the Worker URL, which does not exist.

## After my first commit lands

I will tell you when. It adds a `sync` role to the app.

**Job 3. Create the sync account, on the Settings page, not in the console.**
Hamburger, Settings, add a person. Name it "NALA Sync" and give it the `sync`
role. Note the six digit code it produces; the Worker needs it.

That role can do nothing in the app: no boards, no marks, no menu, and it lands
on no page. It exists only so the rules can name it.

**Job 4. Paste the rules.**
Only after job 3. `rules.json` in the repo is the complete replacement, built
from the live copy rather than from memory. Copy the whole file, paste it over
what is in the console.

Nothing breaks if this waits, because the paths are currently covered by the
`$other` catch all and will function without it. It must land before any real
guest data does, because catch all means any signed in user can write it.

## After I hand you the Worker

**Job 5. Deploy the Worker.**
Cloudflare dashboard, create a Worker, paste the source, add four secrets:
the sync account's email and code from job 3, and a shared secret you invent
for Zapier. Copy the deployed URL.

**Job 6. Build the Zap.**
Trigger: Mews, reservation event. Action: Webhooks by Zapier, POST, to the
Worker URL from job 5, with the shared secret. Field mapping will be in the
Worker source so you are not guessing.

Test with one booking on the demo property before pointing it at the live one.

## Later, stage 3

**Job 7. GuestTouch.**
The triggered message, one week before arrival, booking id as the only dynamic
portion. Not needed until the pre-arrival page exists.

## What I am doing meanwhile

1. The `sync` role: `nala-shared.js`, `staff.html`, version bumps, suites.
2. `rules.json`, already drafted.
3. The Worker source.
4. Stage 2, the `roomRecord()` merge, once data is landing.

Every one of those is a commit to this repo and needs nothing from you.
