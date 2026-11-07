# 02 Ask Traficom the open questions

Status: ready-for-human
Type: research
Size: S
Blocked by: none

## Why

Several tickets rest on assumptions only Traficom can settle. Agents should not contact anyone; a person asks, then records the answers here.

## When and where

Discord is the preferred channel: `traficomsinceai2026`. From the brief, on Saturday 7 Nov:

- Q&A stand: 9:00-12:00 and 14:30-18:00
- Space IFIC specialists: 10-11 and 17-18
- Terrestrial IFIC specialists: 11-12 and 16-17

## Questions

**Submission (affects 03, 10, 14)**
1. The brief says "separate file(s) to be provided" for 3074 and 3076. Do you provide a template, or do we choose the format and fields?

**Space scope (03, 04, 07)**
2. Which bands and services do you watch most?
3. Do you want cases where Finland is already listed by the BR, cases the BR missed, or both?
4. Criterion D scores both false positives and false negatives. How much over-flagging is acceptable in worst-case screening?
5. Is a 4-month comment window right for every in-scope section, including API/A?

**Terrestrial (08, 09, 10)**
6. Which T/R 25-08 trigger values and time percentage do you use with Russia, Sweden, Estonia, Norway and Denmark?
7. Terrestrial 3075, 3076 and 3083 hold station notices from only Russia and Estonia among those five. For Sweden, Norway and Denmark, does coordination data (`fxm_coord`) matter instead?

**Station spreadsheet (05, 07)**
8. Is the power column ERP or EIRP? 67 no-class rows run from 133 MW to 9.4 GW and fit `10^(d/10) / 1.64` exactly. Should they be read as dBm?
9. What does `E` in `Radiation power (ITU)` mean?
10. What do class `MVV` and the blank class mean?
11. What receive gain should we assume where none is given? Only 85 of 873 rows have one.
12. Should stations with no RX frequency be protected at their TX frequency?

**Calibration**
13. Can you share recent items you actually commented on?

## Answered by the team

- The submission deadline does not constrain the plan.
- Neighbours in scope: Russia, Sweden, Estonia, Norway, Denmark.
- Issues 3074 and 3076 are downloaded from ITU by cron, or uploaded as an `.mdb` or a `.zip` containing one.

## Answer

(Record Traficom's answers here, with who answered and when.)
