"""Publish tonight's menu, as the chef.

Fetched and run by the menu chat. It lives here rather than inside the chef's
brief because a long code block pasted between people gets truncated, and a
truncated Python file fails with a syntax error that looks nothing like its
cause. That happened on 21 Aug: the URL line was cut in half, and the report
was "it says it failed".

Signing in rather than carrying a token. A GitHub token cannot be narrowed to
one file - the smallest scope that can write menu.json is Contents write, which
is every file in the repository, including the pages and the Worker. So a token
in a document that gets forwarded can change the whole live site. A Firebase
login can be narrowed: the rules let a chef and an admin write /menu and
nothing else, and it expires in an hour.

Usage, from the chat:

    publish(email, password, {
      "bread":   ("Housemade focaccia", "smoked paprika butter", False),
      "entree":  ("Poblano pepper", "braised beef, smoked cheddar", False),
      "main":    ("Yellowtail kingfish", "corn, saffron, tomato", True),
      "dessert": ("Tres leches", "passionfruit, coconut", False),
    })
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

AEST = timezone(timedelta(hours=10))
DB = "https://nala-menu-default-rtdb.asia-southeast1.firebasedatabase.app"
API_KEY = "AIzaSyA0zAzL-zfPivrIRhY_ip8BABjuYVMlzqI"
SIGNIN = ("https://identitytoolkit.googleapis.com/v1/"
          "accounts:signInWithPassword?key=" + API_KEY)

COURSES = ("bread", "entree", "main", "dessert")


def _post(url, payload, token=None):
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers, method="PUT"
                                 if token else "POST")
    return json.loads(urllib.request.urlopen(req).read())


def sign_in(email, password):
    """A staff login, good for about an hour. The password is never stored."""
    try:
        out = _post(SIGNIN, {"email": email, "password": password,
                             "returnSecureToken": True})
        return out["idToken"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        raise SystemExit(
            "Could not sign in. Check the email and password.\n"
            "This is a staff login for the app, not a GitHub account.\n\n"
            + detail)


def publish(email, password, courses):
    """Write the menu, then read it back and show what is live."""
    for c in COURSES:
        if c not in courses:
            raise SystemExit("Missing course: " + c)

    menu = {"published": datetime.now(AEST).isoformat()}
    for c in COURSES:
        name, desc, aus = courses[c]
        menu[c] = {"name": str(name).strip(),
                   "desc": str(desc).strip(),
                   "aus": bool(aus)}

    token = sign_in(email, password)

    url = DB + "/menu.json?auth=" + token
    req = urllib.request.Request(url, data=json.dumps(menu).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="PUT")
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        if e.code in (401, 403):
            raise SystemExit(
                "Signed in, but this login is not allowed to publish menus.\n"
                "Ask the manager to set the role to chef in Settings.\n\n"
                + detail)
        raise SystemExit("The menu was not saved.\n\n" + detail)

    # Read it back rather than trust the write. A publish that half worked and
    # a publish that worked look identical from here otherwise, and the chef
    # has no way to tell until a guest asks.
    live = json.loads(urllib.request.urlopen(DB + "/menu.json").read())
    if not live or not live.get("published"):
        raise SystemExit("The menu did not save. Nothing is live.")

    print("Published " + live["published"][:16].replace("T", " ") + "\n")
    for c in COURSES:
        d = live.get(c) or {}
        flag = "  [seafood]" if d.get("aus") else ""
        print(c.title().ljust(8) + " " + str(d.get("name", "")) + flag)
        if d.get("desc"):
            print("         " + d["desc"])
    print("\nIt is on the guests' phones now.")
    return live
