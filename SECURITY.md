# Security jobs, click by click

Written 18 Aug 2026, for Ben. Everything here is done by you, in a browser.
None of it can be done from the app or from a chat.

**Do them in this order.** Jobs 1 to 3 protect the database. Job 4 protects
documentation and costs money. Stopping after job 3 is a good night's work.

**Before you start, have these open in tabs:**

- github.com
- console.firebase.google.com
- console.cloud.google.com
- dash.cloudflare.com
- zapier.com

**One warning that applies throughout.** Two of these rotations stop the Mews
sync between one console and the next. Bookings stop arriving in that gap and
do not backfill. Do not start one and get distracted.

**A note on the words on screen.** These consoles rename their buttons every
few months. If something is not where I say, look for the same word nearby
rather than striking out for a different screen, and tell me so I can correct
this file.

**Names you will need, spelled exactly:**

| Thing | Value |
|---|---|
| GitHub organisation | `NALA-Resort` |
| GitHub repository | `nala-menu` |
| Cloudflare Worker | `nala-mews-sync` |
| Worker secret, sync address | `SYNC_EMAIL` |
| Worker secret, sync passcode | `SYNC_PASSWORD` |
| Worker secret, shared secret | `ZAP_SECRET` |
| Worker secret, Firebase key | `FB_API_KEY` |
| Zapier header the secret travels in | `x-nala-secret` |

---

# JOB 1. Rotate the credentials

## 1a. The two GitHub tokens

**Time:** ten minutes. **Breaks:** any chat holding an old token, until you
paste the new one when it asks.

There are two on purpose. `nala-menu publish` is what an assistant chat uses to
publish code. `nala-menu chef` is what the chef's chat uses to publish the
nightly menu. Separate, so either can be killed without stopping the other.

**Make the new ones first, revoke the old ones after.** The other way round
leaves the chef unable to publish a menu in between.

1. Go to **github.com**. Sign in if it asks.
2. Click your **profile picture**, top right corner.
3. In the menu that drops down, click **Settings**.
4. You are now in account settings. Look at the **left sidebar** and scroll it
   all the way to the bottom.
5. Click **Developer settings**. It is the last item.
6. In the new left sidebar, click **Personal access tokens**. It expands.
7. Click **Fine-grained tokens** underneath it.
8. Your existing tokens are listed. Leave them alone for now.
9. Click **Generate new token**, top right.
10. **Token name:** type `nala-menu publish 2`
11. **Description:** leave it empty.
12. **Resource owner:** click the dropdown and choose **NALA-Resort**. If the
    only option is your own username, the token will not reach the repo. Stop
    and tell me.
13. **Expiration:** click the dropdown, choose **90 days**.
14. Scroll to **Repository access**. Click the radio button **Only select
    repositories**.
15. A **Select repositories** dropdown appears. Click it, type `nala-menu`,
    and click it in the list.
16. Scroll down to **Permissions**. Click **Repository permissions** to expand
    it if it is not already open.
17. It is a long alphabetical list. Scroll down to **Contents**.
18. At the right of the **Contents** row is a dropdown reading **No access**.
    Click it, choose **Read and write**.
19. Leave every other permission alone. **Metadata** will set itself to Read
    only. That is normal and required.
20. Scroll to the bottom. Click **Generate token**.
21. A green box appears with the token, starting `github_pat_`. Click the
    **copy icon** beside it.
22. **Paste it somewhere safe now.** GitHub will never show it again.
23. Repeat steps 9 to 22 for the second token. The only difference is step 10:
    type `nala-menu chef 2`.
24. Go back to the **Fine-grained tokens** list.
25. Click the name of the **old** `nala-menu publish` token.
26. Scroll to the bottom, click the red **Revoke** button, confirm.
27. Repeat 25 and 26 for the old `nala-menu chef` token.
28. The list should now show only the two names ending in `2`.

**Test it:** next time a chat asks for a token, paste the new one. If it is
rejected, come back and check step 12 and step 18. Those are the two that go
wrong.

---

## 1b. The `sync` passcode

**Time:** ten minutes. **Breaks:** the Mews sync, from step 9 until step 18.
Reservations do not reach the app in that window and do not backfill afterwards.

1. Go to **console.firebase.google.com**.
2. Click the **nala-menu** project tile.
3. In the **left sidebar**, click **Build** to expand it.
4. Click **Authentication**.
5. Along the top of the main panel are tabs. Click **Users**.
6. Find the machine account. It is the address ending `@staff.nala`, with six
   digits in front of the @.
7. **Write that address down exactly**, digits included. You need it twice
   below, and it must not change.
8. Think of a new six digit code. Not a birthday, not 123456. Write it down.
9. Hover over that user's row. Three vertical dots appear at the far right.
   Click them.
10. If you see **Reset password**, it emails a link, which is no use for a
    machine account. Use this instead:
    - Click the three dots again, click **Delete account**, confirm.
    - Click **Add user** at the top of the Users list.
    - **Email:** the address from step 7, character for character.
    - **Password:** your new six digit code.
    - Click **Add user**.
11. The address must be identical to before. The app looks up the role by that
    address, so a changed address means the Worker has no permissions and
    every write is refused.
12. Now go to **dash.cloudflare.com**.
13. Left sidebar, click **Compute**, then **Workers & Pages**. On older
    dashboards it is a single **Workers & Pages** item.
14. Click **nala-mews-sync** in the list.
15. Click the **Settings** tab.
16. Find the **Variables and Secrets** section.
17. Find the row named `SYNC_PASSWORD`. Click **Edit** beside it, type the new
    six digit code, click **Save**. It will say Deploying for a moment.
18. Check the row named `SYNC_EMAIL` matches the address from step 7. Edit it
    if not.

**Test it:** in Mews, change something small on any booking so an event fires.
Open `menu.nalaresort.com/debug.html`, sign in as yourself, and look at today's
stays. If the booking is there and current, it worked. If nothing arrives, the
two passcodes do not match.

---

## 1c. The shared secret

**Time:** ten minutes. **Breaks:** every reservation event, from step 6 until
step 12.

This is the value Zapier sends so the Worker knows a request is really from you
and not from anyone who found the Worker's address.

1. Invent a new one. Long and random, thirty characters or more. A password
   manager will generate it. Not a word, not a date.
2. Write it down. You are about to paste it into two places and they must match
   exactly.
3. Go to **dash.cloudflare.com**.
4. **Compute**, then **Workers & Pages**, then **nala-mews-sync**.
5. **Settings** tab, **Variables and Secrets** section.
6. Find the row `ZAP_SECRET`. Click **Edit**, paste the new value, **Save**.
7. **Watch for a trailing space.** Copying from a password manager very often
   carries one, it is invisible, and it makes two identical looking values
   compare unequal. Select the field contents and check the highlight stops
   right at the last character.
8. Go to **zapier.com**.
9. Open the Zap that sends reservations to the Worker. It has a **Mews**
   trigger and a **Webhooks by Zapier** action.
10. Click the **Webhooks by Zapier** action step to open it.
11. Click **Configure**. Scroll to the **Headers** section.
12. Find the header named `x-nala-secret`. Replace its value with the new
    secret. Same warning about trailing spaces.
13. Click **Continue**, then **Test step**.
14. **A pass reads `"ok": true`.** A **401** means the two values do not match,
    so one did not save, or one has a space on the end.
15. Click **Publish** to put the Zap back on.

---

## 1d. The Firebase web API key

**Read this before deciding.** This key is public by design. It is in `auth.js`
in the repository, and in every browser that has ever loaded the app. It
identifies the project; it does not authorise anything. The database rules are
what protect the data.

**My advice: do not rotate it. Restrict it instead, which is job 3.** Rotating
means the app is broken between the moment you make the new key and the moment
I publish it into the code, and it buys nothing.

If you want it rotated anyway, tell me and we will do it together at a quiet
hour, in this order: you make the key, you send it to me, I publish, you delete
the old key. Not before.

---

# JOB 2. Delete the leftover logins

**Time:** five minutes. **Breaks:** nothing.

Removing somebody on the app's Settings screen removes their access. It does
not delete their Firebase login, which still exists and still holds a working
passcode.

1. Open **menu.nalaresort.com/staff.html**. Sign in.
2. Look at the **People** list. Note every name and the six digit code beside
   it. That is the list of who should exist.
3. Go to **console.firebase.google.com**.
4. Click the **nala-menu** project.
5. Left sidebar, **Build**, then **Authentication**, then the **Users** tab.
6. Compare the two lists.
7. For anybody in Firebase who is **not** in the app's People list: hover the
   row, click the **three dots** at the right, click **Delete account**,
   confirm.
8. **Do not delete** your own login, or the `@staff.nala` sync account.

**Why bother:** it is tidiness rather than a hole, since a login with no record
in the app grants nothing. But it frees the six digit passcode. A code
belonging to a deleted person cannot be given to a new one until this is done.

---

# JOB 3. Lock the Firebase key to your own site

**Time:** ten minutes. **Breaks:** the live site for guests, if you mistype a
domain. Which is why step 18 is not optional.

This is the job people skip and it is the best ten minutes here. The key is
public. Restricting it means a copy of your app on somebody else's domain
cannot use your database with it.

## 3a. Restrict by website

1. Go to **console.cloud.google.com**.
2. At the **top left**, beside the Google Cloud logo, is a **project picker**.
   Click it.
3. Choose **nala-menu**. If it is not listed, click **All** in that dialog.
4. Click the **hamburger menu**, top left, the three horizontal lines.
5. Click **APIs and services**. A submenu appears.
6. Click **Credentials**.
7. Under the heading **API keys** there is a row, most likely called **Browser
   key (auto created by Firebase)**.
8. Click its **name** to open it. Not the copy icon beside it.
9. Scroll to **Application restrictions**.
10. Click the radio button for **Websites**.
11. A **Website restrictions** box appears with an **Add** button. Click
    **Add**.
12. Type `menu.nalaresort.com/*` and click **Done**.
13. Click **Add** again, type `nalaresort.com/*`, click **Done**.
14. Click **Add** again, type `*.nalaresort.com/*`, click **Done**.
15. Leave **API restrictions** below exactly as it is. Restricting by API as
    well is a second way to break it for no extra protection.
16. Click **Save**, at the bottom.
17. **Wait five minutes.** Google says up to five; it is usually two.

**Test it, and do not skip this:**

18. Open a **private browsing window**.
19. Go to `menu.nalaresort.com`.
20. The guest menu should load exactly as before.
21. **If it does not:** go back to step 9, choose **None** under Application
    restrictions, click Save, and the site recovers within minutes. Then tell
    me and we will check the entries together.

## 3b. Prune the authorised domains

1. Back to **console.firebase.google.com**, the **nala-menu** project.
2. Left sidebar, **Build**, then **Authentication**.
3. Click the **Settings** tab, across the top of the main panel.
4. Click **Authorised domains**.
5. Delete anything that is not one of these:
   - `menu.nalaresort.com`
   - `localhost`
   - something ending `.firebaseapp.com`
   - something ending `.web.app`
6. To delete: three dots at the right of the row, then **Delete**.

**Leave `localhost` alone.** It is how the test suites sign in. Removing it
turns every suite red for a reason nobody would guess at.

---

# JOB 4. Make the repository private

**Optional. Costs money. Do it last, or not at all.**

What it does: hides the documentation, the rules file and the tests from
strangers. What it does not do: hide the app. Every page is HTML served to a
browser, so anyone visiting the site reads the code whatever this setting says.

`NALA-Resort` is a personal account, so this needs the **Pro** plan. An
earlier version of this file said Team, which is the plan for organisations
and costs more; the profile page's contribution graph is how you can tell it
is a personal account. Check the current price on GitHub's pricing page first.

1. Go to **github.com**. Click your **profile picture**, top right corner.
2. In the menu that drops down, click **Settings**.
3. Left sidebar, **Billing and licensing**, then **Plans and usage**. On
   older layouts it reads **Billing and plans**.
4. Find the **Pro** plan and click **Upgrade**. Follow the payment steps.
5. Go to **github.com/NALA-Resort/nala-menu**.
6. Click **Settings**, in the row of tabs across the top of the repository.
7. Stay on **General** and scroll all the way to the bottom.
8. Find the red bordered box titled **Danger Zone**.
9. Click **Change visibility**.
10. Click **Make private**.
11. It asks you to type the repository name to confirm. Type
    `NALA-Resort/nala-menu`.
12. Click the confirm button.
13. Still in **Settings**, click **Pages** in the left sidebar.
14. Check **Source** still reads **Deploy from a branch**, branch **main**,
    folder **/ (root)**.
15. Check **Custom domain** still reads `menu.nalaresort.com`.
16. If **Enforce HTTPS** has unticked itself, tick it again. It may be greyed
    out for a few minutes while a certificate is issued.

**Test it:**

17. Open a **private browsing window**.
18. Go to `menu.nalaresort.com`. Give it five minutes before worrying.
19. If the guest menu loads, it worked.
20. **If it does not**, go back to step 7 and set the repository Public again.
    Nothing is lost by doing that.

**One more, or the sync stops silently:**

21. Go to **dash.cloudflare.com**, **Compute**, **Workers & Pages**,
    **nala-mews-sync**.
22. Click **Settings**, then **Build** or **Builds** depending on the dashboard
    version.
23. Check the GitHub connection still lists `NALA-Resort/nala-menu`. A private
    repository needs the Cloudflare GitHub App granted access to it explicitly,
    and going private can drop that.
24. If it shows an error or a disconnected repository, click through to GitHub
    and grant access to `nala-menu` again.

**Test it:** make any commit and watch the Worker redeploy. If it does not,
step 23 is why.

**One more thing this changes:** `START-HERE.md` tells a fresh chat to fetch
`HANDOVER.md` from `raw.githubusercontent.com`, and that address stops
working once the repository is private. A new chat will need the repo cloned
with a token instead — the clone line is already in `START-HERE.md` under
"If the fetch fails". Tell me once you have gone private and I will update
both files so the next session is not sent down the dead path.

---

# What none of this fixes

Worth knowing. These are design decisions with reasons rather than oversights,
and no setting above changes them.

- **The app's code is readable by anyone**, private repository or not, because
  it is served to browsers. That is why nothing secret may ever live in it, and
  why the notification signing key lives in the Worker instead.
- **`/bookings/<id>` is readable by anyone holding a booking id.** Deliberate:
  it is how a guest opens a pre-arrival link without signing in. It is why the
  sync stopped storing reception's notes about a guest, and why nothing else
  private may go on that node.
- **`/dinner/<date>` is readable outright**, because the guest menu page reads
  it before anybody has signed in.

All three are written up in `DESIGN.md`.

---

# The short version, for the fridge

1. New GitHub tokens, then revoke the old two.
2. New sync passcode in Firebase, the same passcode into Cloudflare.
3. New shared secret into Cloudflare, the same secret into Zapier, test the Zap.
4. Delete Firebase logins that are not in the app's People list.
5. Restrict the Firebase key to `nalaresort.com`, then test in a private window.
6. Repository private, only if you have bought Pro, then test in a private
   window.
