# Invitations: status bands

Approved by the owner from mock-ups, 23 Aug late evening. Written by the
session that does NOT hold invitations.html, so this brief deliberately
confines itself to presentation the mock-ups introduced and names what it
must not touch. The mock the owner approved is invite-status.html, committed
beside this file; open it in a browser to see every state at once.

Report back rather than deciding alone on anything here that contradicts
what you find in the code, which may have moved since this was written.

## What this is

The board's rows regrouped and coloured so the sender reads status at a
glance instead of reading every line. Seventeen tiles on a full morning;
the screen's job is confidence: all white gone from the top means everyone
has been asked, the grey middle drains as replies land, green and terra are
the kitchen's answer taking shape.

## The four bands, in order (the Cleans principle: work first, done sinks)

1. **To send** - kind 'ready'. White tiles, pre-ticked, top of the board.
   A failed send belongs HERE, not in a separate error band: the sender's
   question is "who still needs a message" and a failure answers yes. Its
   reason stays in the status line, as stateOf already writes it.
2. **Waiting on a reply** - kind 'sent'. Light neutral grey:
   background rgba(28,28,26,.045), border the standard --rule, status line
   in --mid. Unknown promises nothing, so it is NOT green. Solid border and
   full opacity keep it apart from band 4.
3. **Answered** - kind 'answered'. The Reservations tiles exactly, so the
   two boards speak one language. Dining: background --green-t
   rgba(122,160,130,.26), border --green-b rgba(122,160,130,.65), line in
   --green #5E7D67. Not dining: background --terra-t rgba(184,106,90,.16),
   border --terra-b rgba(184,106,90,.45), line in --terra #9E6455. Within
   the band, villa order as now; dining and not-dining stay interleaved.
4. **Cannot send** - kind 'nophone'. Grey, dashed border, opacity .62,
   tick hidden, sunk to the bottom: the same nothing-to-do voice as the
   Reservations board's vacant villas.

Each band carries a small uppercase header with its count ("TO SEND - 4"),
so nobody counts tiles. A band with nothing in it shows no header.

## Scope fence - why this brief is narrow

This page is actively owned by another session; two of its commits landed
mid-evening while this was being drafted. Everything below is theirs and
this work must not restate or restyle it:

- stateOf() and its kinds, lines and tickable/ticked flags: consume as-is.
  The bands are a GROUPING of kinds, not new state. If a new kind has
  appeared since 23 Aug, report it and propose its band; do not invent one.
- The tick, the send flow, the second-press confirm, the counts strip, the
  phone rules, the Worker: untouched.
- Existing row markup: extend with band classes and group headers; do not
  rebuild the row.
- If render() already sorts or groups by the time this is built, merge the
  band order into it rather than adding a second sort.

Bump ?v= if nala-shared.js is touched; this design should not need to.

## Suites

fd-style assertions in the invitations suite (whatever its name is by
then): the four bands render in order from a fixture covering every kind;
a failed send appears in band 1 with its reason; band headers carry counts
and absent bands show none; the answered tiles carry the reservation
tints; the cannot-send tick is hidden. Colour assertions by computed
style, not class name, because the tints are the contract with the other
board.
