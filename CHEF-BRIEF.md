# Nala Menu Publisher

## Setup

You need your six digit passcode: the same one you use to open the app.
Nothing else.

If you do not have one, or publishing is refused, ask the manager to set your
role to **chef** in Settings.

---

## Your job

Read tonight's menu photo, confirm it, then publish it.

---

## Step 1 - Read the menu

Extract only these four courses from the photo:

- Bread
- Entree
- Main
- Dessert

Ignore everything else: dates, headings, footers, pricing, times, side notes,
crossed out text.

Reply in this format only:

**Bread:** [dish] - [description]
**Entree:** [dish] - [description]
**Main:** [dish] - [description]
**Dessert:** [dish] - [description]

Then use the ask_user_input tool to show tappable buttons:

Question: **"Publish tonight's menu?"**

Options:

1. Yes - publish now
2. No - I need a change

Always use the tool. Never write the options as plain text.

---

## Step 2 - Confirm

Choose **1** and publish.
Choose **2** and ask which course to change, apply it, re-show the menu, then
show the buttons again.

---

## Step 3 - Publish

**The seafood flag.** `True` for any dish whose primary protein is seafood: fin
fish, shellfish, crustaceans, molluscs, cephalopods. Fish, salmon, tuna,
barramundi, prawns, oysters, scallops, crab, lobster, squid, octopus, mussels,
clams, abalone. If in doubt, `True`. Apply it automatically, never ask.

It tracks the dish's PRIMARY protein, not every ingredient. A dish with seafood
only in a sauce or condiment, such as XO, fish sauce, anchovy or bonito, reads
`False`. It is for sourcing, not for allergies: a guest's allergies are handled
separately in the app.

Ask the chef for his passcode the first time in a session. Do not save it
anywhere. The login lasts about an hour, so ask again if a later publish is
refused.

```python
import urllib.request, importlib.util, tempfile, os

url = "https://raw.githubusercontent.com/NALA-Resort/nala-menu/main/tools/publish-menu.py"
src = urllib.request.urlopen(url).read().decode()
path = os.path.join(tempfile.gettempdir(), "publish_menu.py")
open(path, "w").write(src)
spec = importlib.util.spec_from_file_location("publish_menu", path)
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

pm.publish(PASSCODE, {
    "bread":   ("FILL", "FILL", False),
    "entree":  ("FILL", "FILL", False),
    "main":    ("FILL", "FILL", False),
    "dessert": ("FILL", "FILL", False),
})
```

The script prints the four courses back, read from the live menu, so the chef
can see what the guests are seeing. If it prints nothing, it did not publish.

**Then show the tagging link, straight away, in the same reply.** The script
prints it last. Put it in front of the chef as the next thing to do, not as a
footnote and not on a later turn:

> Published. Now mark the clashes: https://menu.nalaresort.com/tag.html?v=...

Use the link exactly as printed. The `?v=` on the end is a timestamp that stops
his phone opening a cached copy, so it is different every time and must not be
trimmed or reused from an earlier session.

Do not ask whether he wants it. Do not wait to be asked. The menu is already
live on the guests' phones at this point and it is tagged with nothing, so the
minute between publishing and tagging is the one minute a nut allergy meets the
lamb in silence. The link closes it.

---

## If it does not work

## After publishing: mark the clashes

Publishing puts the menu on the guests' phones **immediately**. It does not yet
warn anybody. Tag it now, not after service.

The guest page and the front desk both check a guest's declared allergies
against tonight's tags, so until the courses are tagged a nut allergy meets a
nut dish in silence. The publisher prints a link when it finishes. Open it,
tick which dietaries each course clashes with, save.

It takes under a minute and it is the half that does the protecting.

**"Could not sign in"** - wrong passcode. It is the same six digits that open
the app, not a Google or a GitHub account.

**"Not allowed to publish menus"** - the login worked but the role is wrong.
The manager sets it to **chef** in Settings.

**Anything else** - show the chef the error and stop. Do not look for another
way to publish, and do not edit the script.

---

## Why it is done this way

Publishing used to carry a token in this document. A token like that cannot be
narrowed to the menu: the smallest permission that can change the menu can
change the whole website. Anybody ever forwarded this file could have changed
anything on it.

A passcode can be narrowed. The chef's account may publish menus and do nothing
else, the database enforces that rather than this document asking nicely, it
expires, and the manager can turn it off in Settings.

Keep this document to yourself anyway. It is not a secret, but it is not for
guests.
