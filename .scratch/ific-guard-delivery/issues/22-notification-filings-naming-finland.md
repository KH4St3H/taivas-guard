# 22 Screen notification-stage filings that name Finland

Status: resolved
Type: task
Size: S
Blocked by: none
Owns: `IN_SCOPE_REASONS` use in `ific_guard/screening/space.py`, `FinlandNamedRule` in `ific_guard/screening/rules.py`, their tests

## Why

Brief, section 06 D: "minimises material false positives and false negatives". The space reader keeps only `ntf_rsn` A (9.1/IA) and C (9.6) (`space.py:17`). So `fin-named-by-br` never sees notification-stage (`N`) filings, and the README lists three 3074 notices where the ITU names Finland that are missed: 125500060, 125500061 and 125500066. These are known false negatives in the accuracy issue.

## Do

1. Let `fin-named-by-br` see notification-stage notices whose coordination data names Finland. Keep the other rules on A and C unless there is a reason to widen them; say which in the commit.
2. A case from a notification-stage notice says so (its section and what that stage means for a response), and gets a comment deadline only if one applies. Don't invent a window.
3. Update the README "Things not evaluated" bullet.

## Acceptance

- On 3074, the three notices above raise cases, and no other rule's count changes.
- A test covers an `N` notice naming Finland, and an `N` notice that doesn't.
- `uv run pytest` passes.

## Answer ? 2026-11-07

Implemented in b606e99. The BR-names-Finland rule sees A/C/N coordination notices; technical rules retain their A/C notice view. Notification findings include source sections, explicit stage/response guidance, and no assumed deadline. Real 3074 finds all three requested notices and 11 BR cases total. Regression tests include named/unnamed notifications and missing provision data. Full final suite: 626 passed, zero skipped.
