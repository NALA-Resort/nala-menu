"""The error trap.

A suite goes green when the things it asked about were true. It says nothing
about the things it did not ask about, and a page that throws an uncaught error
on the way to a correct answer still gives the correct answer. So a suite can
pass over a page that is quietly broken, and the first person to find out is
whoever is holding the phone.

This closes that. Import it and every browser page the suite opens is watched
for uncaught errors and unhandled promise rejections. At the end of the run it
prints what it caught, and exits non-zero if it caught anything, so a suite
cannot go green over a page that threw.

One line per suite:

    import errortrap

Nothing else. It patches the browser at import and reports at exit.

Some suites break things on purpose: a refused write, a failed sign in, a
malformed record. Those pages are supposed to complain. Tell the trap so, and
it stays quiet about that one message:

    errortrap.expect("Permission denied")

Match is a plain substring on the error text. Keep them specific: a broad
pattern silences the bug you have not met yet.
"""
import atexit
import os
import sys

CAUGHT = []          # (page url, message)
EXPECTED = []        # substrings that are somebody's deliberate test
_installed = False


def expect(fragment):
    """Silence one error message the suite causes on purpose."""
    EXPECTED.append(fragment)


def _is_expected(msg):
    return any(f in msg for f in EXPECTED)


def _watch(page):
    def on_error(exc):
        msg = str(exc).split("\n")[0][:200]
        CAUGHT.append((getattr(page, "url", "?"), msg))

    def on_console(m):
        if m.type == "error":
            txt = (m.text or "")[:200]
            # A failed fetch logs a console error of its own; the suites stub
            # plenty of those deliberately, and reporting them here would bury
            # the real thing under noise.
            if "Failed to load resource" in txt:
                return
            CAUGHT.append((getattr(page, "url", "?"), txt))

    page.on("pageerror", on_error)
    page.on("console", on_console)
    return page


def install():
    global _installed
    if _installed:
        return
    try:
        from playwright.sync_api import Browser, BrowserContext
    except Exception:
        return

    for cls in (Browser, BrowserContext):
        orig = getattr(cls, "new_page", None)
        if orig is None:
            continue

        def make(orig):
            def new_page(self, *a, **k):
                return _watch(orig(self, *a, **k))
            return new_page

        setattr(cls, "new_page", make(orig))
    _installed = True


def report():
    real = [(u, m) for (u, m) in CAUGHT if not _is_expected(m)]
    if not real:
        if CAUGHT:
            print("\nerror trap: %d expected error(s), none unexplained"
                  % len(CAUGHT))
        else:
            print("\nerror trap: no page threw")
        return
    print("\nerror trap: %d uncaught error(s)" % len(real))
    seen = set()
    for url, msg in real:
        page = url.split("/")[-1].split("?")[0] or url
        key = (page, msg)
        if key in seen:
            continue
        seen.add(key)
        print("  %s: %s" % (page, msg))
    # A suite that threw has not passed, whatever its own assertions decided.
    # sys.exit inside an atexit handler only prints "Exception ignored", so the
    # exit status has to be set the blunt way.
    sys.stdout.flush()
    os._exit(1)


# The notification Worker is on a domain this sandbox is not allowed to reach,
# so every page that tries to register for push logs a CORS refusal. That is
# the sandbox's network, not the app, and it would otherwise redden every
# suite. What it does NOT tell us is whether the live Worker sends the headers
# the real site needs. Nothing here can answer that; it is a check for a
# person, and it is in TESTING.md.
expect("nala-push.ben-681.workers.dev")

install()
atexit.register(report)
