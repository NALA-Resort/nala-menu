# NALA menu app: start here

Paste this at the start of a new chat. It contains no credentials. It tells you
what to ask for, how to work, and where everything is.

---

## First message: ask for the token, then set up

**Ask for a GitHub token before doing anything else**, not at the moment of the
first push. Fine grained, repository `NALA-Resort/nala-menu`, permission
Contents: Read and write. Save it to `/home/claude/.ghtoken` and verify it with
a write test before relying on it.

Then, without being asked:

```bash
git clone https://github.com/NALA-Resort/nala-menu.git /home/claude/nala
ln -sfn /home/claude/nala /home/claude/repo    # some suites expect this path
```

The suites expect the working copy at `/home/claude/nala`.

**Then read `HANDOVER.md` in the repo.** It is the only document you have to
read and it points at the rest. Do not ask the user to re-explain what is in it.

---

## The two scripts, which the sandbox does not keep

Recreate both. `push.py` can add and update but **cannot delete**; a deletion
that looks published and is not has cost hours.

### /home/claude/push.py

```python
# Publishes one commit to main. Put a GitHub token with contents:write on the
# repo at /home/claude/.ghtoken first (no newline needed, it is stripped).
import json,base64,urllib.request,os
TOKEN=open('/home/claude/.ghtoken').read().strip()
REPO="NALA-Resort/nala-menu"; API="https://api.github.com/repos/"+REPO
# Edit these two, then run: python3 /home/claude/push.py
FILES=["README.md"]
MSG="Say what changed and why, in the imperative, no em dashes"
def call(path,data=None,method=None):
    req=urllib.request.Request(path if path.startswith("http") else API+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization":"token "+TOKEN,"Accept":"application/vnd.github+json",
                 "Content-Type":"application/json","User-Agent":"nala-assistant"},
        method=method or ("POST" if data is not None else "GET"))
    return json.load(urllib.request.urlopen(req))
ref=call("/git/ref/heads/main"); base=ref["object"]["sha"]
basecommit=call("/git/commits/"+base)
tree=[]
for f in FILES:
    blob=call("/git/blobs",{"content":base64.b64encode(open(f,'rb').read()).decode(),"encoding":"base64"})
    tree.append({"path":f,"mode":"100644","type":"blob","sha":blob["sha"]})
    print("blob",f,blob["sha"][:8])
nt=call("/git/trees",{"base_tree":basecommit["tree"]["sha"],"tree":tree})
nc=call("/git/commits",{"message":MSG,"tree":nt["sha"],"parents":[base]})
upd=call("/git/refs/heads/main",{"sha":nc["sha"]},method="PATCH")
print("COMMIT",nc["sha"],"->",upd["object"]["sha"])
```

`tools/rm.py` in the repo does deletions. Copy it to `/home/claude/rm.py`.

### /home/claude/publish.sh

Refuses if `main` moved since your last push, rather than silently pushing over
it. This was written when a second chat published here too. That arrangement
ended on 18 Aug and this chat owns every file, but the guard is kept: it costs
nothing and it catches a push made from a stale clone.

```bash
#!/bin/bash
set -e
cd /home/claude/nala
MSG="$1"; shift
MARK=/home/claude/.lastpush
git fetch -q origin main:refs/remotes/origin/main
REMOTE=$(git rev-parse refs/remotes/origin/main)
if [ -f "$MARK" ] && [ "$(cat $MARK)" != "$REMOTE" ]; then
  echo "STOP: someone else has published."
  git log --oneline $(cat $MARK)..$REMOTE
  exit 1
fi
# This script ends in git reset --hard, which throws away any modified file it
# did not publish. A failed push followed by a successful one silently deleted
# a session's work that way. Refuse rather than discard.
LEFT=$(git diff --name-only)
for f in "$@"; do LEFT=$(echo "$LEFT" | grep -vx -- "$f" || true); done
if [ -n "$(echo "$LEFT" | tr -d '[:space:]')" ]; then
  echo "STOP: these files are modified but not in this publish, and the reset would discard them:"
  echo "$LEFT"
  echo "Add them to the command, or git checkout them first."
  exit 1
fi
python3 - "$MSG" "$@" <<'EOF'
import re, sys, json
msg, files = sys.argv[1], sys.argv[2:]
p = '/home/claude/push.py'; s = open(p).read()
# Functions, not strings. re.sub reads backslashes in a replacement string, so
# a multi line commit message wrote a real newline into push.py and broke it
# for that run and every run after.
s, n1 = re.subn(r'^FILES=.*$', lambda m: 'FILES=' + json.dumps(files), s, flags=re.M)
s, n2 = re.subn(r'^MSG=.*$', lambda m: 'MSG=' + json.dumps(msg), s, flags=re.M)
if n1 != 1 or n2 != 1:
    sys.exit('push.py does not have exactly one FILES and one MSG line, refusing to write')
open(p, 'w').write(s)
import py_compile; py_compile.compile(p, doraise=True)
EOF
python3 /home/claude/push.py
git fetch -q origin main:refs/remotes/origin/main
git rev-parse refs/remotes/origin/main > $MARK
git reset -q --hard refs/remotes/origin/main
echo "PUBLISHED $(git log --oneline -1)"
```

Seed the marker after the first fetch: `git rev-parse refs/remotes/origin/main
> /home/claude/.lastpush`.

---

## Other things to ask for, when they matter

Never assume any of these are set up. Ask, and say why you need it.

- **Firebase rules**: `rules.json` in the repo is a copy, not a deployment.
  Any change to it must be pasted into the console by the user and Published.
  Give them the whole file in a code block, not a diff.
- **Firebase console access** for anything the app cannot do itself.
- **Zapier and Mews**: unreachable from the sandbox entirely.
- **`api.cloudflare.com` is not on the sandbox allowlist.** The Worker deploys
  from GitHub on commit, so this is usually not needed.
- **Nothing outside the allowlist can be fetched**, including the resort's own
  website. Ask the user to paste the content instead.

---

## How this person works

**Replies must be short.** They have said plainly that a thousand words after a
build does not get read. Give what changed for the person using it, anything
needed from them, and what is next. No commit hashes, no test counts, no file
names unless they are the point.

**Decide things yourself.** If a question can be answered with reasoning, answer
it, note the decision, and move on. Do not stall waiting for permission.

**Ask in plain language, not the multiple choice widget.** It truncates long
questions and short ones say nothing. Number the questions and let them reply
with numbers.

**They are the designer, not the author.** Explain in terms of what the guest or
the receptionist sees, not in terms of nodes and functions.

**They test on real data for days.** Expect bug reports from live use, and
expect them to be right. Several times this session the user's instinct was
correct and the assistant's reading of the code was wrong.

---

## Working rules that were learned the hard way

**Verify before asserting.** Reading code tells you what it can do, not what it
does. Do not describe production behaviour you have not observed. This caused a
whole audit to be partly wrong.

**Edits that can fail silently will.** Python's `str.replace` does nothing when
the text does not match and reports nothing. Three separate bugs came from it:
a function called but never defined, twice, and a duplicated fixture key that
silently overrode the first. Use edits that error on no match, and check each
one landed.

**Run every suite before publishing.** Fifteen page suites in `tests/`, plus
`worker/test.mjs`, `tests/rules_test.js` and `tests/matrix_probe.js`, about 1085
assertions. `/home/claude/runall.sh` runs the lot, but the whole run exceeds the
sandbox command timeout, so run them in batches of three or four. The printed
sheet went blind to a whole node for two commits with everything green, because
nothing tested screen and paper agreeing.

The two node suites need `npm install targaryen` in the repo root once.

**A failed read is not an empty node.** Clean Slate reported zero records for
four nodes it could not read, said it had succeeded, and deleted nothing.

**Mock up before anything visual.** 390pt, check 360, do not break at 320.
`STYLEGUIDE.md` first, every time.

**Never em dashes**, anywhere, including code comments.

**Do not edit `list.html`, `menu-print.html` or `housekeeping.html`.** A second
chat owns them.

**Check the sandbox before saying it is gone.** After a context compaction this
chat twice told the user the working copy and the repo were unreachable and
suggested starting over. Both were intact the whole time. A `view` tool call
failing, or a `web_fetch` being refused, says nothing about the files: read them
with bash or code execution instead.

---

## Where things stand

The Mews sync, Front Desk Arrival, the guest pre-arrival form, registration
cards and the single dinner record are all built and live. `HANDOVER.md` has the
current open list; the short version is:

**Waiting on the user:** the four security jobs in `SECURITY.md`, which is
credential rotation, deleting leftover logins, locking the Firebase key to the
site, and optionally making the repo private; cancellations do not fire from
Zapier; GuestTouch links need `?b=<booking id>`; dinner and breakfast hours; the
placeholder line on the pre-arrival form.

The 18 Aug rules were pasted into the Firebase console and published that
evening, so `rules.json` and the live rules match. Any further change to that
file is another paste.

**Waiting on a developer:** nothing reports the sync stopping, which needs a
Zapier schedule trigger; the notification Worker exists only on the user's
machine and it is not known whether it handles the `menu` event; write back to
Mews is unbuilt and needs Connector API credentials; the demo sheets do not
rebuild themselves.

`TESTING.md` section 0 lists the smoke tests for everything that changed on
18 Aug, and sections 1 onward the checks a sandbox cannot run. **None of them
have been done, and nothing built on 18 Aug has ever been touched by a human on
a real device.** Everything you inherit is code that passes its own tests and
has not otherwise been used. Treat a bug report as true until you have proved
otherwise.

---

## One thing to say at the start

Tell the user what you have set up and what you need, in a few lines, then ask
for the token. Do not open with a plan, a summary of the repo, or a list of
everything you have read.
