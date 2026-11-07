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
