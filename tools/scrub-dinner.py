#!/usr/bin/env python3
"""One-time scrub of identity off the world-readable /dinner cells.

Tightening the rules stops NEW writes from putting a guest's name, phone or
raw booking id on the public /dinner node. It does nothing to the cells
already there - every past and present night still carries whatever was
written before the fix. This walks them and rewrites each one clean:

  - a raw `bookingId` becomes its fingerprint `bkey` (which correlates but
    opens nothing - see bookingKey in nala-shared.js),
  - `name` and `phone` are lifted OFF the cell; when present they are moved to
    the staff-only /manual/<date>/room-<villa> node so a walk-in's name is not
    simply lost,
  - the same is done inside any preserved `guest` sub-object.

It reads /dinner with no auth (that node is public - that is the whole
problem) but WRITES need an admin login, so it wants an admin id token. Get
one from a browser signed in to the app as admin: open the console and run
    copy(window.__idToken)
then paste it in. The token is short-lived and is never stored here.

    python3 tools/scrub-dinner.py                 # dry run: report only
    python3 tools/scrub-dinner.py --apply         # actually rewrite

Token via NALA_TOKEN=... env or the --token flag. DB defaults to the one in
nala-shared.js; override with NALA_DB=... .

Run order for the whole fix: publish the pages, run this with --apply, then
paste the tightened rules.json into the Firebase console. The readers tolerate
both old and new shapes throughout, so nothing breaks mid-way; pasting the
rules last only means the database refuses identity once everything is clean.

The booking fingerprint is reimplemented here in Python and self-checked
against tests/bookingkey_cases.json before anything runs: if the port has
drifted from the JS by one bit, the script aborts rather than write tokens the
boards would not recognise.
"""
import json, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

DEFAULT_DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app"


# ── the booking fingerprint, ported from bookingKey in nala-shared.js ──────
#  cyrb53. Every step is masked to a 32-bit unsigned word so Python's
#  arbitrary-precision ints match JavaScript's Math.imul and >>> exactly.
def _imul(a, b):
    return (a * b) & 0xFFFFFFFF


def booking_key(idv):
    s = "" if idv is None else str(idv)
    if not s:
        return ""
    h1 = 0xDEADBEEF
    h2 = 0x41C6CE57
    for ch in s:
        c = ord(ch)
        h1 = _imul(h1 ^ c, 2654435761)
        h2 = _imul(h2 ^ c, 1597334677)
    h1 = _imul(h1 ^ (h1 >> 16), 2246822507)
    h1 = (h1 ^ _imul(h2 ^ (h2 >> 13), 3266489909)) & 0xFFFFFFFF
    h2 = _imul(h2 ^ (h2 >> 16), 2246822507)
    h2 = (h2 ^ _imul(h1 ^ (h1 >> 13), 3266489909)) & 0xFFFFFFFF
    n = 4294967296 * (2097151 & h2) + h1
    return _base36(n)


def _base36(n):
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


def self_check():
    cases = json.load(open("tests/bookingkey_cases.json"))["cases"]
    bad = [(c[0], booking_key(c[0]), c[1]) for c in cases if booking_key(c[0]) != c[1]]
    if bad:
        for got in bad:
            print("  %s -> %s, shared table says %s" % got, file=sys.stderr)
        sys.exit("ABORT: the Python fingerprint has drifted from the JS. Fix "
                 "booking_key here before running - the boards would not "
                 "recognise the tokens this would write.")


# ── the cell's public shape, mirroring sanitiseDinnerCell in nala-shared.js ─
FORBIDDEN = ("name", "phone", "bookingId", "bkey", "guest")


def sanitise(cell):
    if not isinstance(cell, dict):
        return cell, {}
    out, ident = {}, {}
    for k, v in cell.items():
        if k in ("name", "phone"):
            if isinstance(v, str) and v.strip():
                ident[k] = v
            continue
        if k in ("bookingId", "bkey", "guest"):
            continue
        out[k] = v
    bk = cell.get("bkey") or (booking_key(cell["bookingId"]) if cell.get("bookingId") else "")
    if bk:
        out["bkey"] = bk
    if isinstance(cell.get("guest"), dict):
        gout, _ = sanitise(cell["guest"])   # a guest sub-object's own identity is dropped, not relocated
        out["guest"] = gout
    return out, ident


def changed(before, after):
    return json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True)


# ── database helpers ───────────────────────────────────────────────────────
def get_json(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read().decode() or "null")


def put_json(url, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, method="PUT",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        r.read()


def main():
    apply = "--apply" in sys.argv
    token = os.environ.get("NALA_TOKEN", "")
    if "--token" in sys.argv:
        token = sys.argv[sys.argv.index("--token") + 1]
    db = os.environ.get("NALA_DB", DEFAULT_DB).rstrip("/")

    self_check()
    print("fingerprint self-check: ok")

    if apply and not token:
        sys.exit("--apply needs an admin id token (NALA_TOKEN=... or --token). "
                 "In the app console: copy(window.__idToken)")

    auth = ("?auth=" + token) if token else ""
    all_dinner = get_json(db + "/dinner.json") or {}

    cells = 0
    scrubbed = 0
    relocated = 0
    for date, villas in sorted(all_dinner.items()):
        if not isinstance(villas, dict):
            continue
        for villa, cell in sorted(villas.items()):
            cells += 1
            clean, ident = sanitise(cell)
            if not changed(cell, clean) and not ident:
                continue
            scrubbed += 1
            leaked = [k for k in ("name", "phone", "bookingId") if k in cell]
            gl = []
            if isinstance(cell.get("guest"), dict):
                gl = [("guest." + k) for k in ("name", "phone", "bookingId")
                      if k in cell["guest"]]
            print("%s villa %s: removes %s" % (date, villa,
                  ", ".join(leaked + gl) or "(nothing at top level)"))
            if ident:
                print("            -> name/phone moved to /manual/%s/room-%s" % (date, villa))
            if apply:
                put_json(db + "/dinner/%s/%s.json%s" % (date, villa, auth), clean)
                if ident:
                    put_json(db + "/manual/%s/room-%s.json%s" % (date, villa, auth), ident)
                    relocated += 1

    print("\n%d cells seen, %d needed scrubbing%s." % (
        cells, scrubbed, "" if apply else " (dry run - nothing written)"))
    if apply:
        print("%d walk-in identities relocated to /manual." % relocated)
    elif scrubbed:
        print("Re-run with --apply (and an admin token) to rewrite them.")


if __name__ == "__main__":
    main()
