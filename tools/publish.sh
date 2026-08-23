#!/bin/bash
# The one way to publish. Run from anywhere in the repo:
#
#     bash tools/publish.sh "<commit message>" <file> [<file>...]
#
# It rewrites FILES and MSG in tools/push.py, runs it, then resets hard to the
# new origin/main. Two guards, both from real losses: it refuses if main moved
# since this clone last published, and it refuses if a modified file is not in
# the publish, because the reset at the end would discard it.
#
# Kept in the repo because the sandbox it used to live in is wiped between
# sessions, and a fresh session that cannot publish is a fresh session that
# starts by rebuilding this from memory.
set -e
cd "$(dirname "$0")/.."
MSG="$1"; shift
MARK="${NALA_LASTPUSH:-$HOME/.lastpush}"
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
p = 'tools/push.py'; s = open(p).read()
# The replacement is a function, not a string. re.sub reads backslashes in a
# replacement string, so a multi line message put a real newline into the
# source and push.py stopped parsing. It failed loudly, but it failed after
# rewriting the file, which left push.py broken for the next run too.
s, n1 = re.subn(r'^FILES=.*$', lambda m: 'FILES=' + json.dumps(files), s, flags=re.M)
s, n2 = re.subn(r'^MSG=.*$', lambda m: 'MSG=' + json.dumps(msg), s, flags=re.M)
if n1 != 1 or n2 != 1:
    sys.exit('push.py does not have exactly one FILES and one MSG line, refusing to write')
open(p, 'w').write(s)
import py_compile; py_compile.compile(p, doraise=True)
EOF
python3 "$(dirname "$0")/push.py"
git fetch -q origin main:refs/remotes/origin/main
git rev-parse refs/remotes/origin/main > $MARK
git reset -q --hard refs/remotes/origin/main
echo "PUBLISHED $(git log --oneline -1)"
