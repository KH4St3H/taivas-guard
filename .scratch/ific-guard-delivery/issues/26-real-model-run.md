# 26 Run the drafting path with a real model

Status: ready-for-human
Type: task
Size: S
Blocked by: 25
Owns: `outputs/llm-check.md`

## Why

README, "Data and operations": "Not tested: … the language-model path with a real model". It's the one AI component in the workflow, and the brief judges outputs that are "understandable, reviewable" (06 C) with citations (06 E). A human is needed because it uses an API key and costs money.

## Do

1. Set `ANTHROPIC_API_KEY` and `IFIC_LLM_MODEL` (see `.env.example`), then draft with `use_llm=true` for one case of each rule on 3074: `fin-named-by-br`, `m4-no-space-to-earth`, `station-rx-overlap`, a pfd case, a CEPT case and a terrestrial case.
2. Record in `outputs/llm-check.md`: model id, date, cost if shown, and for each case whether the guardrail passed, and any number, citation or claim the rewrite changed or added.
3. File a ticket for anything the guardrail let through that it shouldn't.

## Acceptance

- `outputs/llm-check.md` exists with six cases, and the README no longer lists the path as untested.

## Comments

2026-11-07, ready for someone with a key. Ticket 25 (the blocker) is done on the same branch, `agent/25-26-drafting`.

**What's ready:**

- `tools/llm_check.py` does steps 1 and 2. It drafts one case of each kind from the exports with the configured model and writes `outputs/llm-check.md`. Each section has the guardrail verdict and any violations, the numbers and citations the rewrite added or dropped, and both texts. It refuses to run without a key. The exports now cover all six kinds: 3074 has a CEPT case (`pfd-ngso-cept`, CSN-SSO), and 3076 has the terrestrial one.
- The request in `ific_guard/llm/model.py` was checked against the current API reference: `claude-opus-5-5`, the `server-side-fallback-2026-07-01` beta with `fallbacks: "default"`, and `output_config` with `effort` and a JSON schema. Six drafts at $4/$20 per million tokens should cost well under a dollar.
- **The guardrail now passes the template's own facts.** Before this, it rejected the template's text on four of the six kinds (station levels, derived counts, quoted M4 restrictions, hedged wording), so a faithful rewrite would always have fallen back. A test now requires every exported case's template to pass. A dry run against a local stand-in for the API (not a real model) gave 6 of 6 passing for faithful rewrites and 0 of 6 for rewrites with an invented number, citation and "violates" claim.

**To do (needs `ANTHROPIC_API_KEY`):**

1. Run it:

       ANTHROPIC_API_KEY=... uv run python tools/llm_check.py outputs/ific_3074/cases.json outputs/ific_3076/cases.json

   `IFIC_LLM_MODEL` is optional; the default is `claude-opus-5-5`.
2. In `outputs/llm-check.md`, fill in the cost from the Anthropic Console, and under "Claims changed" note any claim each rewrite strengthened or added (read the two texts side by side).
3. File a ticket for anything the guardrail let through that it shouldn't have.
4. Remove "the language-model path with a real model" from the README's "Not tested" line (`README.md`, Data and operations).

To see it in the UI as well: put `ANTHROPIC_API_KEY` in `.env` (and `IFIC_API_KEY`, which the AI rewrite also needs), run `docker compose up`, then open a finding. "Rewrite with AI" appears under the draft letter.
