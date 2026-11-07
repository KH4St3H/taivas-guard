# 27 Letters name the kind of criterion

Status: ready-for-agent
Type: task
Size: S
Blocked by: none
Owns: wording in `ific_guard/llm/template.py`, `frontend/src/lib/letter.ts`, their tests

## Why

README, "Assumptions an expert should check": "Draft letters say 'limit' for every comparison, including Appendix 5 triggers and T/R 25-08 thresholds." Each case already knows which it is: the mask `kind` (`pfd_art21`, `pfd_app5`, `pfd_cept`) or the terrestrial criterion basis. Calling a coordination trigger a limit overstates the case in a letter to another administration (brief 06 E).

## Do

1. Map each kind to its term: Article 21 limit; Appendix 5 coordination threshold; CEPT condition (name the ECC document); T/R 25-08 indicative threshold. Use it in the explanation, the letter and the reference block.
2. For "exceeds", say "exceeds the coordination threshold" or "is above the indicative threshold" as appropriate, never "breaks a limit" for anything but Article 21.
3. Remove the README bullet.

## Acceptance

- A test per kind checks the term in the explanation and the letter.
- `uv run pytest` and `npx vitest run` pass.
