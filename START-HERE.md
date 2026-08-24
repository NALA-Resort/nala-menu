# Start a new chat with this

**Before adding anything, read `CLAUDE.md`.** It is the convention for how
features get added here: a fact lives in one file, and adding a page is one
line in `NAV` rather than markup pasted into ten. Claude Code reads it
automatically; a chat session needs pointing at it, which is what this line
is for.

Paste this line, and nothing else:

> Fetch https://raw.githubusercontent.com/NALA-Resort/nala-menu/main/HANDOVER.md
> and follow it.

That is the whole thing, and it never changes. The handover moves; this does
not, which is the point. Anything that has to be edited whenever the project
changes is a thing that will one day be out of date at exactly the moment
somebody is relying on it.

---

## Why this file is nine lines and used to be three hundred

It carried setup instructions, the two scripts, how to work, where everything
is. All of that is in `HANDOVER.md`, so the two drifted: on 23 Aug I wrote a
"Starting from nothing" section into the handover, complete with the clone
line and the token path, without noticing this file had said the same things
for a week. Two documents describing one setup is how a session ends up
following the older one.

`HANDOVER.md` is the only document that has to be read, and it says so. This
one exists solely because a fresh chat has no way to know that sentence exists.

## If what you fetch looks out of date

`raw.githubusercontent.com` caches for about five minutes, so a handover updated
moments ago can come back as the previous version. It is not wrong, only late.
Add a cache buster, or clone and read the file there, which is never stale:

    curl -s "https://raw.githubusercontent.com/NALA-Resort/nala-menu/main/HANDOVER.md?x=$(date +%s)"

The same trap in a different coat is the `?v=` on this site's shared scripts,
which cost the owner days of retesting against old code. The handover has that
under Standing cautions.

## If the fetch fails

The sandbox reaches `raw.githubusercontent.com` on its default allowlist, and
nothing else about this project. If it is refused, the network settings have
changed and the handover cannot be reached that way; clone instead:

    git clone https://github.com/NALA-Resort/nala-menu.git /home/claude/nala

Then read `HANDOVER.md` in the clone.
