# 23 Set aside filings whose orbit is not referred to the Earth

Status: ready-for-agent
Type: task
Size: S
Blocked by: none
Owns: visibility in `ific_guard/screening/rules.py` (`visible_from_finland`), `rule_stations.py` and `custom_rules.py` callers, their tests

## Why

README, "False positives": in 3074, six networks (LUNAR-R1 to R5, USASAT-MK1) have an orbit referred to the Moon, yet still get M4 and station cases as if they were Earth satellites. The pfd rule already sets them aside (`rule_pfd.py:777`, `notice.ref_body not in (None, EARTH_BODY)`). The other rules should agree.

## Do

1. Make `visible_from_finland` treat a non-GSO notice whose `ref_body` is set and isn't the Earth as not visible, with a reason that names the body. Use the same constant as the pfd rule.
2. Check `m4-no-space-to-earth`, `station-rx-overlap` and custom rules all go through it.
3. Update the README false-positive bullet with the new count.

## Acceptance

- On 3074 the six networks raise no M4 or station cases, and the README states the before and after case counts.
- A test covers a Moon-referred orbit and a missing `ref_body` (kept, as now).
- `uv run pytest` passes.
