# Deploys, without the pasting

Written 25 Aug 2026, for Ben. The setup below is one-time, in a browser,
about twenty minutes. After it, two standing pastes disappear for good:

- `rules.json` into the Firebase console (SETUP.md job 4)
- `worker/mews-sync.js` and `worker/send-invites.js` into the Cloudflare
  dashboard (SETUP.md job 5, and the ARRIVALS-SMS.md checklist)

**How it works.** A push to `main` that touches `rules.json` or anything in
`worker/` runs a GitHub Action (the two files in `.github/workflows/`).
The Action runs on GitHub's machines, which reach Firebase and Cloudflare.
The sandbox a chat session works in never could and still cannot; the
session's job now ends at the push, which is the thing it was always able
to do. The Worker suites run first and gate the deploy: a red suite means
nothing ships.

**Where the credentials live.** In GitHub Actions secrets, on the
repository. They are write-only: once saved, nobody can read them back out
of GitHub, and they never appear in this repo. Workflows in forks of this
repo do not receive them.

**Until the three secrets below exist, these runs fail red** in the repo's
Actions tab on every rules or Worker push. That is deliberate. A deploy
that quietly skipped and showed green would read as "the change is live"
when it is not, which is the same trap as a failed read counting as an
empty one. While red, the old paste procedures still work and are still
the way.

**What this does not cover.** The notification Worker is not in this repo
and still changes by dashboard paste. The chef's console fallback
(`CHEF-BRIEF-CONSOLE.md`) is data, not code, and is unchanged. GitHub
Pages already deploys the site itself and nothing about that changes.

---

## The three secrets, spelled exactly

| GitHub secret name | What it holds |
|---|---|
| `CLOUDFLARE_API_TOKEN` | a token allowed to edit your Workers |
| `CLOUDFLARE_ACCOUNT_ID` | your Cloudflare account id · an address rather than a secret, kept here so it lives beside the token |
| `FIREBASE_SERVICE_ACCOUNT` | a Google service account key that may publish database rules |

---

## Job 1. The Cloudflare token

**Software:** Cloudflare dashboard. **Time:** five minutes.

1. Go to **dash.cloudflare.com** and sign in.
2. Click the **profile icon**, top right, then **My Profile**.
3. Left sidebar: **API Tokens**.
4. Click **Create Token**.
5. Find the template **Edit Cloudflare Workers** and click **Use template**.
6. Under **Account Resources**, pick your account. Leave the rest of the
   template as it is.
7. Click **Continue to summary**, then **Create Token**.
8. **Copy it somewhere safe now.** Cloudflare never shows it again.
9. While you are here, get the account id: go to **Compute**, then
   **Workers & Pages**. The **Account ID** is in the right-hand column of
   the overview page, with a copy icon. Copy that too.

## Job 2. The Firebase deploy account

**Software:** Google Cloud console. **Time:** five minutes.

SETUP.md says "do not create a Firebase service account", and that rule
stands where it was made: the **sync** must sign in as a staff account so
the rules apply to it. This account is a different thing. It never touches
data and no running code holds it; it exists only so GitHub can publish the
rules file, and it lives only in the GitHub secret. That is the exception,
written down next to the thing, per CLAUDE.md.

1. Go to **console.cloud.google.com**.
2. Top left, click the **project picker** and choose **nala-menu**.
3. Hamburger menu, top left: **IAM & Admin**, then **Service Accounts**.
4. Click **Create service account**.
5. Name: `github-rules-deploy`. Click **Create and continue**.
6. Under **Grant this service account access**, click the role dropdown,
   search **Firebase Realtime Database Admin**, select it. Click
   **Continue**, then **Done**.
7. In the list, click the account you just made.
8. Click the **Keys** tab, then **Add key**, then **Create new key**.
9. Key type **JSON**, click **Create**. A `.json` file downloads. That
   file's contents are the secret.

## Job 3. Put the three into GitHub

**Software:** GitHub. **Time:** five minutes.

1. Go to **github.com/NALA-Resort/nala-menu**.
2. Click **Settings**, in the row of tabs across the top of the repository.
3. Left sidebar: **Secrets and variables**, then **Actions**.
4. Click **New repository secret**. Three times, one per row of the table
   above. Names character for character; the usual warning about trailing
   spaces applies.
5. For `FIREBASE_SERVICE_ACCOUNT`, open the downloaded `.json` in a text
   editor, select **all** of it, and paste the whole thing as the value.
6. **Delete the downloaded `.json` file** once the secret is saved. It is
   a credential sitting in your Downloads folder.

## Job 4. Prove it

1. Back on the repository page, click the **Actions** tab.
2. Left sidebar: **Deploy Cloudflare Workers**. Click **Run workflow**,
   keep branch `main`, run it. Do the same for **Deploy Firebase rules**.
3. Both should go green in about a minute. A red run names the step that
   failed; the two that go wrong are a mistyped secret name and a partial
   paste of the `.json`.
4. Check Cloudflare believed it: **dash.cloudflare.com**, **Workers &
   Pages**, **nala-mews-sync**, the **Deployments** (or **Versions**) tab.
   The newest entry should be from just now, uploaded via API rather than
   the dashboard editor. Same for **nala-invites**.
5. Check Firebase believed it: **console.firebase.google.com**,
   **nala-menu**, **Build**, **Realtime Database**, **Rules** tab. The
   editor should show the repo's `rules.json`, and the rules history
   (clock icon) an entry from just now.
6. The Workers still answer: open each Worker URL in a browser and expect
   **405 POST only**, exactly as when they were pasted.

## Job 5. One deployer, not two

The sync Worker may still have the repo connected under Cloudflare's own
build feature, from before this existed. Two deployers racing on every
commit is confusion waiting to happen, so once you have seen job 4 green:

1. **dash.cloudflare.com**, **Workers & Pages**, **nala-mews-sync**,
   **Settings**, then **Build** or **Builds**.
2. If a GitHub connection to `NALA-Resort/nala-menu` is listed, disconnect
   it. If there is none, there is nothing to do.

This also retires SECURITY.md job 4 steps 21 to 24: after going private,
the check is a green **Deploy Cloudflare Workers** run in the Actions tab,
not a Builds connection.

---

## Rotating these later

Both rotate with no window where the site or the sync breaks: the worst
case is a deploy failing red until the new value is in, and job 4 re-runs
it.

- **The Cloudflare token:** dash.cloudflare.com, profile icon, **My
  Profile**, **API Tokens**, three dots on the token's row, **Roll**. Put
  the new value into the GitHub secret (job 3), which overwrites the old.
- **The service account key:** job 2 steps 7 to 9 to make a new key, job 3
  to save it, then back on the **Keys** tab delete the old key.
- The account id is not a secret and never needs rotating.

If either value is ever pasted into a chat, it is burned like any other
credential: rotate it and say so, per SECURITY.md.

---

## For the session doing the pushing

Nothing here changes how you work. Publish with `tools/publish.sh` as
always; the deploy hangs off the push to `main`. Three things worth
knowing:

- **The Actions tab is the deploy record.** A red run there means the
  change is NOT live, however green the local suites were. Say so rather
  than reporting the push as a deploy.
- You cannot see the Actions tab from the sandbox any more than you can
  see Firebase. The owner can, and the run also emails him on failure,
  which is GitHub's default.
- A rules or Worker change on `main` goes live within about a minute of
  the push. There is no dry run and no staging here either, so the rule
  about publishing only when asked carries exactly the same weight it has
  for pages.
