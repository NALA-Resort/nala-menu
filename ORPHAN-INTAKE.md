# Unmatched pre-arrivals: the orphan intake

Decided by the owner, 23 Aug evening, at the end of the pre-arrival revision.
Report back rather than deciding alone on anything here that contradicts what
you find in the code.

## The problem this solves

A pre-arrival link whose booking id has no record in Firebase still opens,
greets from the link's cosmetic data, and saves answers under an id that
feeds nothing. The guest's effort is lost silently and the broken link (or
broken Zap run) is invisible until someone goes looking. The long link keeps
its cosmetics for exactly this moment: they are what make an orphan
identifiable to a human.

## The design

1. **The form stores the link's cosmetics when the record is missing.**
   Today n/s/a/d paint the greeting and are thrown away. When the boot's
   read of `/bookings/<id>/pms` comes back empty, the openedAt write also
   carries `link: { first, last, arrive, depart }` so the desk has a name
   and dates to show. When the record exists, nothing changes: cosmetics
   stay unstored, Firebase stays the truth.

2. **The front desk shows an unmatched row.** Same shape as a normal
   arrival row, but highlighted in the warn tone, separated from the day's
   list, and labelled as an error ("Unmatched pre-arrival" or the owner's
   words). It shows the stored link name and dates and whatever answers
   arrived. Placement: pinned visible regardless of the selected day until
   resolved, because an orphan with a mistyped date must not hide on the
   wrong day.

3. **Resolution is the Mews confirmation number.** The row contains one
   field asking for it (reception reads it from Mews; `pms.number` holds it
   for synced bookings - the check-in card already prints "Mews 1125" from
   this). On entry:
   - scan `/bookings/*/pms` for `number` matching the entry
   - **match found**: PATCH the orphan's prearrival answers into that
     booking, then delete the orphan node. The row disappears and the
     booking appears in arrivals as normal. Merge care: if the target
     already has prearrival answers, do not overwrite non-empty fields with
     empty ones; flag a genuine conflict to the operator rather than
     guessing.
   - **no match**: show an error on the row and leave everything standing.
     This is the Zap-never-ran case; entering a number cannot conjure the
     booking record. The row's error text should say the booking itself is
     missing and needs the sync re-run.

4. **Nothing writes toward Mews.** Bookings are born there and flow one
   way; this feature only re-homes answers already inside Firebase.

## Findings the builder needs (verified 23 Aug)

- `pms.number` exists (worker/mews-sync.js picks it) and is the only
  Mews-visible identifier a receptionist can transcribe.
- The scan for a matching number needs a read of all bookings' pms nodes;
  check the desk's existing reads before adding a new listener - it may
  already hold what is needed.
- Firebase rules: confirm the desk role may write another booking's
  prearrival and delete the orphan node. The rules cannot be read from the
  sandbox; check the console or test against the live database with a
  throwaway node first.
- Also outstanding from the same evening, same neighbourhood: confirm the
  rules accept the new approach keys ('few', 'once', 'unsure') as strings.
  One real send from a test link settles both questions in one visit.

## Suites

- pre_suite: the missing-record boot stores the link block; the present-
  record boot does not.
- fd_suite: the unmatched row renders from a fixture orphan; a matching
  number re-homes and clears it; a non-matching number errors and changes
  nothing; the merge refuses to blank a non-empty answer.

## Out of scope

No email, no Formspree: the owner chose the in-house queue after weighing a
third party holding dietaries. No changes to link structure: long links
stay, for the reason at the top.
