# 32 Update and rehearse the demo

Status: claimed
Owner: Person C (Claude, with mehr)
Type: task
Size: S
Blocked by: 24, 25, 28, 29
Owns: `docs/demo.md`

## Why

Brief 07: "Demo of the solution". `docs/demo.md` was rehearsed before TX protection, and has none of: custom screening rules, the reach map, the paged station list, CEPT cases, the restyled UI. A demo that hits a stale screen costs more than a missing feature.

## Do

1. Add a short path through the new parts, anchored on one strong case: SPACERAN in 3083 (CEPT condition exceeded by 31.5 dB, not on the ECC/DEC/(25)02 Annex 2 list), or its 3074 equivalent after ticket 29.
2. Show one custom rule and its preview.
3. Rehearse once from a clean start, time it, and update "What the rehearsal did not cover".

## Comments

2026-11-07, script updated; rehearsal still open:

- `docs/demo.md` has new steps for the reach map (2b), the CEPT condition on SPACERAN (2c), Trends (6) and a screening rule with preview (7), and sets `IFIC_MIN_ISSUE=3082` so Trends has two issues to compare.
- The header and "What the rehearsal did not cover" say those steps aren't rehearsed, and that their numbers come from the development database.
- Still to do, by a person, once tickets 25, 28 and 29 are merged: switch step 4 to the finding page's draft, run the whole script from an empty database, time it, replace the development numbers with the fresh run's, and press Accept by hand.
