# 25 Finding page drafts from the drafting service

Status: resolved
Owner: Claude, with arbaaz
Type: task
Size: M
Blocked by: none
Owns: the Draft letter panel in `frontend/src/pages/FindingDetail.tsx`, `frontend/src/lib/letter.ts`, the draft calls in `frontend/src/api/`

## Why

The brief's title is an "AI-assisted workflow", and step 9 asks to draft "relevant correspondence template for expert review". The backend has this: `GET /cases/{id}/draft` returns a deterministic draft with citations and retrieved regulation passages, and `?use_llm=true` rewrites it with Claude behind a guardrail (`ific_guard/llm/`). The UI ignores it and builds its own browser template, labelled "Filled from a fixed template, no AI yet". The demo therefore never shows the AI part or the citations.

Ticket 18 says a branch doing this, `agent/12-drafts-ui` at `1422f80`, exists only in the Codespace. Check for it first and reuse it if it can be found.

## Do

1. Load the draft from `GET /cases/{id}/draft`. Show the explanation, the letter, the citations and the review notes the service returns.
2. Add "Rewrite with AI" calling `?use_llm=true`, only when the service reports a model is configured. Label the result as AI-written and keep the template version one click away. Show the guardrail's verdict if it rejected something.
3. Keep browser-saved edits working, and keep the sample-mode fallback to `letter.ts`.
4. Remove "no AI yet" once the AI path is shown.

## Acceptance

- A case's draft in the UI matches the API response and lists its citations.
- With no API key, no AI button appears and nothing breaks.
- `npx vitest run` passes; screenshots of both states in the comments.

## Comments

2026-11-07, done:

- **Branch `agent/12-drafts-ui`:** not on the remote, so this is new work.
- **Service:** new `GET /drafting` returns `{"model": name}` when a credential is configured, else `{"model": null}`. It never returns the credential.
- **UI:** the Draft letter panel loads `GET /cases/{id}/draft` and shows its explanation, letter, "Sources the draft relies on" (every citation) and "For the reviewer, not part of the letter" (the review notes). "Rewrite with AI" appears only when `/drafting` names a model; the note under the panel says the call can cost money. An accepted rewrite is labelled "Written by AI (model), checked by the guardrail", with "Show the template version" / "Show the AI version". A rejected one keeps the template and lists the guardrail's verdict (kind, value, why). An unedited AI version can be saved ("Save this version") so it survives a reload without a second paid call.
- **Kept:** browser-saved edits load first and can be restored with "Back to your saved edit". Sample mode (`capabilities.drafts: false`), or a failed service call, falls back to `letter.ts`. "no AI yet" is gone.
- **Tests:** `frontend/src/api/drafts.test.ts` covers the mapping (citations, notes, letter), `use_llm` only when asked, the guardrail verdict, a 401 explained as AI being off, and no model meaning no button. `tests/test_llm.py` covers `/drafting`. `uv run pytest` and `npx vitest run` pass.
- **Screenshots** (`25-screenshots/`, case 5, CHINASAT-G-33.5E, `pfd-gso-app5`, 3074 export loaded into a local SQLite):
  - `25-no-model.png`: no credential, no AI button, the service's draft with citations and notes.
  - `25-model-unreachable.png`: a model configured but unreachable; template kept, reason shown.
  - `25-guardrail-rejected.png`: a rewrite adding "exceeds the limit by 42 dB and violates RR No. 22.5" rejected on five counts.
  - `25-ai-rewrite.png`: a clean rewrite shown as AI-written.
  The last two used a local stand-in for the Messages API, not a real model; a real run is ticket 26.
- **For ticket 32:** `docs/demo.md` step at line 77 can now show this in the UI instead of curl.
