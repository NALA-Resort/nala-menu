# Security jobs, click by click

Written 18 Aug 2026, for Ben, to be done in one sitting.

Everything here is done by you, in a browser. None of it can be done from the
app or from a chat. Do them in this order: the first three protect the database
and the last one protects the documentation, and if you run out of time it is
far better to have done 1 to 3 than to have done 4.

Rough timings: job 1 about twenty minutes, job 2 five, job 3 ten, job 4 fifteen.

**A warning that applies to all of it.** Changing a credential breaks whatever
was using the old one, immediately. Each job below says what will break and how
to put it back. Do not do these while a service is running.

---

## Job 1. Rotate the five credentials

All five have been pasted into a chat window at some point, which means they
should be treated as known to somebody else. None of them are in the repository.

### 1a. The two GitHub tokens

There are two on purpose, so either can be revoked without stopping the other.
`nala-menu publish` is the one an assistant chat uses to publish code.
`nala-menu chef` is the one the chef's chat uses to publish the nightly menu.

1. Go to **github.com**, click your avatar, top right.
2. **Settings**, then scroll the left sidebar to the bottom, **Developer
   settings**.
3. **Personal access tokens**, then **Fine-grained tokens**.
4. You should see the existing tokens listed. For each one, click its name,
   then **Revoke** at the bottom. Do not do this until you have read step 5, as
   the chef cannot publish a menu between revoking and reissuing.
5. Click **Generate new token**.
   - **Token name:** `nala-menu publish`
   - **Expiration:** 90 days
   - **Resource owner:** `NALA-Resort`
   - **Repository access:** Only select repositories, then pick `nala-menu`
   - **Permissions:** expand **Repository permissions**, find **Contents**, set
     it to **Read and write**. Leave everything else alone.
6. **Generate token**. Copy it now. GitHub will never show it again.
7. Repeat from step 5 for the second token, named `nala-menu chef`, identical
   settings.

**What breaks:** any chat holding the old token. Paste the new one when a chat
asks for it, and never into a message you have not been asked for.

### 1b. The Firebase web API key

This one is public by design and appears in `auth.js` in the repository. It
identifies the project rather than authorising anything, so rotating it is
optional. **Restricting it, in job 3, is the thing worth doing.** If you would
rather rotate it anyway:

1. Go to **console.cloud.google.com**, and pick the Nala project, top left.
2. Left sidebar, **APIs and services**, then **Credentials**.
3. Under **API keys** you will see the browser key. Create a new one with
   **Create credentials**, **API key**, then delete the old one.
4. The new key has to be pasted into `auth.js`, which is a code change. Send it
   to me and I will publish it. **The app is broken between those two moments**,
   so do this one last, or not at all.

### 1c. The `sync` passcode

This is the login the Mews sync Worker uses to write to the database.

1. **console.firebase.google.com**, pick the Nala project.
2. Left sidebar, **Build**, **Authentication**, **Users** tab.
3. Find the user whose address ends `@staff.nala` and whose role is `sync`. It
   is the one with a six digit number in front of the @.
4. Click the three dots at the right of that row, **Reset password**, and set a
   new six digit code. Write it down.
5. The Worker holds the old one in its environment. Go to **Cloudflare**, your
   Worker, **Settings**, **Variables and Secrets**, and update it there.

**What breaks:** the Mews sync, between step 4 and step 5. Bookings stop
arriving until you finish. It catches up on the next event per booking, it does
not backfill, so do not leave it broken overnight.

### 1d. The shared secret

The value the Zap sends so the Worker knows the request is really from you.

1. Think of a new one. Long and random. A password manager will generate it.
2. **Cloudflare**, your Worker, **Settings**, **Variables and Secrets**, update
   the secret there first.
3. **Zapier**, open the Zap, the webhook action step, and update the same value
   in the header or body where it is sent.
4. **Test step** in Zapier. A pass says `"ok": true`. A **401** means the two
   values do not match, so one of them did not save.

**What breaks:** every reservation event, between steps 2 and 3. Same warning as
above.

---

## Job 2. Delete the leftover Firebase logins

Removing somebody in Settings removes their access. It does not delete their
login, which still exists and still holds a passcode nobody is watching.

1. **console.firebase.google.com**, the Nala project.
2. **Build**, **Authentication**, **Users**.
3. Compare that list against the People list in the app's Settings screen.
4. Anybody in Firebase who is **not** in the app's Settings should be deleted:
   three dots at the right of the row, **Delete account**.
5. Leave alone: your own login, and the `sync` account.

**Why it matters:** the app decides what a login may do by looking it up in
`/staff`. A login with no record grants nothing, so this is tidiness rather than
a hole. But it also frees the six digit passcode for reuse, and a code that
belongs to a deleted person cannot be issued to a new one until you do this.

---

## Job 3. Lock the Firebase key to your own site

This is the one people skip and it is the most useful ten minutes here. The key
is public. Restricting it means a copy of your app, hosted on somebody else's
domain, cannot use it.

### 3a. Restrict the key by referrer

1. **console.cloud.google.com**, pick the Nala project.
2. **APIs and services**, **Credentials**.
3. Click the name of the browser API key.
4. Under **Application restrictions**, choose **Websites**.
5. Click **Add**, and add each of these on its own line:
   - `menu.nalaresort.com/*`
   - `nalaresort.com/*`
   - `*.nalaresort.com/*`
6. **Save**. It can take a few minutes to take effect.
7. **Test it.** Open `menu.nalaresort.com` in a private window and load the
   guest menu. If it fails, come back and check the entries for a typo, since a
   wrong entry here breaks the live site for guests.

### 3b. Prune the authorised domains

1. **console.firebase.google.com**, **Build**, **Authentication**.
2. **Settings** tab, then **Authorised domains**.
3. Delete anything that is not `menu.nalaresort.com`, `localhost`, or the two
   `firebaseapp.com` and `web.app` entries Firebase adds itself.

**Leave `localhost`.** It is how the test suites sign in, and removing it turns
every suite red for a reason nobody will guess.

---

## Job 4. Make the repository private

**Optional, and it costs money.** It hides the documentation, the rules file
and the tests. It does not hide the app: every page is HTML served to a browser,
so anyone visiting the site can read the code whatever this setting says.

`NALA-Resort` is an organisation, so this needs the **Team** plan. Check the
current price before committing.

1. **github.com/NALA-Resort**, **Settings**, **Billing and plans**, upgrade to
   Team.
2. Go to the `nala-menu` repository, **Settings**, scroll to the very bottom,
   **Danger Zone**, **Change repository visibility**, **Make private**.
3. Still in **Settings**, click **Pages** in the left sidebar. Confirm the
   source is still **main** and the custom domain still reads
   `menu.nalaresort.com`. Re-tick **Enforce HTTPS** if it has cleared.
4. **Test it.** Open `menu.nalaresort.com` in a private window. If the guest
   menu loads, it worked. Give it five minutes before worrying.
5. **Cloudflare**, your Worker, and check its Git connection. A private
   repository needs the GitHub App to be granted access to it explicitly. If the
   Worker stops deploying when you commit, this is why.

**If Pages stops serving,** set the repository back to public in the same place.
Nothing is lost by doing so.

---

## What this does not fix

- **The app's code is readable by anyone**, private repository or not. It is
  served to browsers. Nothing secret may ever live in it, which is why the
  notification signing key lives in the Worker and not here.
- **`/bookings/<id>` is readable by anyone holding a booking id.** Deliberate:
  it is how a guest opens a pre-arrival link without signing in. It is why the
  sync no longer stores reception's notes about a guest, and why nothing else
  private may be put on that node.
- **`/dinner/<date>` is readable outright**, because the guest menu page reads
  it before anybody signs in.

Both of those are design decisions with reasons, written up in `DESIGN.md`. They
are worth knowing about rather than worth changing.
