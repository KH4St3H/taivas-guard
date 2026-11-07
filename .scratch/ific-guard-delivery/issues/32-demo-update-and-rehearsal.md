# 32 Update and rehearse the demo

Status: resolved
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

2026-11-07, rehearsed from an empty database at `5098f88` (Compose project `ificdemo`, Space and Terrestrial 3082 and 3083, no model key):

- Sync and first screening took 28 minutes, mostly the ITU download at about 1 MB a minute. The ITU dropped connections; sync retried, and the ops email "sync partial" recorded it. 405 cases.
- Steps 2, 2b and 2c matched the development numbers: J-BLUEBIRD-NGSO +36.7 dB, ARABSAT-12G-1E 9-20° and 26 stations, TOUTATIS 0 stations, SPACERAN -110.5 dB against -142 dB and not on Annex 2.
- Step 4 now uses the finding page's draft (ticket 25); without a key it shows the template and no "Rewrite with AI" button.
- Step 6 changed with two issues: Japan 12 against 1, Saudi Arabia 12 against 0, GSO 48 against 23, X, Ku and W bands; terrestrial flags Estonia, 70 against 19. Step 7's preview gives 31 cases, against 32 in development before tickets 22 and 23 landed; the difference wasn't traced.
- Screening both space issues again added no case, kept the accepted review and sent no email.
- Left for the presenter, written in the script: press Accept once by hand. The rehearsal saved the review through the UI's proxy API.
