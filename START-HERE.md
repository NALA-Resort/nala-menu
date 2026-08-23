# Start a new chat with this

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

## If the fetch fails

The sandbox reaches `raw.githubusercontent.com` on its default allowlist, and
nothing else about this project. If it is refused, the network settings have
changed and the handover cannot be reached that way; clone instead:

    git clone https://github.com/NALA-Resort/nala-menu.git /home/claude/nala

Then read `HANDOVER.md` in the clone.
