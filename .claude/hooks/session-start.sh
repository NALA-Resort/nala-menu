#!/bin/bash
# Makes a fresh Claude Code on the web session ready to run the test suites
# (CLAUDE.md "Running tests") without the first ten minutes going on setup.
# Each step checks before it acts, so on a warm container it costs a second.
# The owner, 28 Sep: "What can we do to stop wasting sessions like that".
set -euo pipefail
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then exit 0; fi
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# 1. Playwright's Python package at the version whose Chromium the image
#    already ships (PLAYWRIGHT_BROWSERS_PATH, build 1194). Never run
#    `playwright install`: the browser is there, the download is not allowed.
if ! python3 -c "import importlib.metadata as m, sys; sys.exit(m.version('playwright') != '1.56.0')" 2>/dev/null; then
  pip install --quiet playwright==1.56.0
fi

# 2. The suites chdir to /home/claude/nala, where the repo lived in the
#    sandbox they were written in. A link, re-pointed if it is one already.
if [ -L /home/claude/nala ] || [ ! -e /home/claude/nala ]; then
  mkdir -p /home/claude
  ln -sfn "$ROOT" /home/claude/nala
fi

# 3. targaryen, which tests/rules_test.js evaluates rules.json with
#    (tests/package.json; node_modules is gitignored).
if [ ! -d "$ROOT/tests/node_modules/targaryen" ]; then
  (cd "$ROOT/tests" && npm install --silent --no-audit --no-fund)
fi
