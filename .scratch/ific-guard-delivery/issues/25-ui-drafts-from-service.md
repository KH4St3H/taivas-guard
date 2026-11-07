# 25 Finding page drafts from the drafting service

Status: ready-for-agent
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
