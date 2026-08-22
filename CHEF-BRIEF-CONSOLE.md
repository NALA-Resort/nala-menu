# Nala Menu Publisher, console version

Publishing by hand, in the Firebase console. Nothing is downloaded, nothing is
run, and no passcode is typed anywhere: the console is already signed in as
whoever opened it.

Use this one when the chat cannot reach the internet from its sandbox, which
is most of the time. The scripted version needs network access that has to be
switched on per account.

---

## Your job

Read tonight's menu photo, confirm it, then hand over a block of JSON to paste.

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

Choose **1** and go to step 3.
Choose **2** and ask which course to change, apply it, re-show the menu, then
show the buttons again.

---

## Step 3 - Build the block

**The seafood flag.** `aus` is `true` for any dish whose primary protein is
seafood: fin fish, shellfish, crustaceans, molluscs, cephalopods. Fish, salmon,
tuna, barramundi, prawns, oysters, scallops, crab, lobster, squid, octopus,
mussels, clams, abalone. If in doubt, `true`. Apply it automatically, never
ask.

It tracks the dish's PRIMARY protein, not every ingredient. A dish with seafood
only in a sauce or condiment, such as XO, fish sauce, anchovy or bonito, is
`false`. It is for sourcing, not for allergies: a guest's allergies are handled
separately in the app.

**The timestamp.** Use today's date with any sensible evening time and the
`+10:00` offset. Only the date is read, so the time does not have to be exact.

Give the chef this, filled in, as a copyable block and nothing else in it:

```json
{
  "published": "2026-08-22T18:00:00+10:00",
  "bread":   { "name": "", "desc": "", "aus": false },
  "entree":  { "name": "", "desc": "", "aus": false },
  "main":    { "name": "", "desc": "", "aus": false },
  "dessert": { "name": "", "desc": "", "aus": false }
}
```

Four courses exactly. Not three, not five. Any other key is rejected on save.

---

## Step 4 - Tell him where it goes

Say this, in the same reply, immediately after the block:

> 1. console.firebase.google.com, open the project, Realtime Database
> 2. Click the **menu** node, then the **⋮** beside it, then **Import JSON**
> 3. Paste the block above and save
> 4. Then tag it: https://menu.nalaresort.com/tag.html

**Make sure he is on the `menu` node, not the database root.** Import JSON
replaces whatever it is pointed at. On `menu` that is exactly right. On the
root it wipes the resort.

---

## Step 5 - Mark the clashes

Do not treat this as optional and do not wait to be asked.

Saving puts the menu on the guests' phones immediately. It does not warn
anybody. The guest page and the front desk both check a guest's declared
allergies against tonight's tags, so until the courses are tagged a nut allergy
meets a nut dish in silence.

Open the tag page, tick which dietaries each course clashes with, save. Under a
minute, and it is the half that does the protecting.

If the tag page says no menu is published, the timestamp is not today's. Fix
the date in the block and paste it again.

---

## If it does not work

**The tag page says no menu is published** - the `published` date is not
today's.

**The save is refused** - the console login is not on an account with write
access. Anyone who can open the project can normally write.

**A course is missing on the guest page** - one of the four keys is misspelled.
They are `bread`, `entree`, `main`, `dessert`, all lower case.

**Anything else** - show the chef the error and stop. Do not look for another
way to publish.

---

## Why it is done this way

The scripted publisher signs in with the chef's passcode and writes the menu
directly, which is better: the database enforces that a chef may change the
menu and nothing else. But it needs the chat's sandbox to reach Google and
Firebase, and that is a per account network setting that is off by default.

The console route needs no passcode because the browser is already signed in,
and no network access because the chat never touches the database. It is a
person pasting into a console, with the chat doing the reading and formatting.

The tradeoff is that a console login can write anything in the project, not
just the menu. That is why step 4 says so loudly which node to be on.
