import { afterEach, describe, expect, it, vi } from 'vitest';
import { httpApi, mapDraft, type DraftOut } from './http';
import { mockApi } from './mock';

const out = (over: Partial<DraftOut> = {}): DraftOut => ({
  source: 'template', model: null, fallback_reason: null, violations: [], method: 'screening', possible_concern_only: true,
  explanation: 'Why it was raised.', subject: 'Possible concern', letter: 'DRAFT FOR EXPERT REVIEW. NOT SENT.',
  citations: [{ doc: 'RR', clause: 'Art. 9, No. 9.52', page_or_url: 'rr-9.52' }, { doc: 'RR', clause: 'Table 21-4', printed_page: 165 }, { doc: 'M4', clause: 'Frequency Allocation Table' }],
  review_notes: ['Check the deadline.'], ...over,
});

const respond = (status: number, body: unknown) => vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));

afterEach(() => vi.unstubAllGlobals());

describe('drafts from the drafting service', () => {
  it('keeps the service’s letter, explanation, review notes and every citation', () => {
    const d = mapDraft(out());
    expect(d).toMatchObject({ source: 'template', letter: 'DRAFT FOR EXPERT REVIEW. NOT SENT.', explanation: 'Why it was raised.', reviewNotes: ['Check the deadline.'] });
    expect(d.citations).toEqual([
      { doc: 'RR', clause: 'Art. 9, No. 9.52', page: 'rr-9.52' },
      { doc: 'RR', clause: 'Table 21-4', page: 'p. 165' },
      { doc: 'M4', clause: 'Frequency Allocation Table', page: null },
    ]);
  });

  it('asks for the template by default and the model only when told to', async () => {
    const fetch = respond(200, out());
    vi.stubGlobal('fetch', fetch);
    await httpApi.getDraft('7');
    await httpApi.getDraft('7', true);
    expect(fetch.mock.calls.map((c) => String((c as unknown[])[0]))).toEqual(['/api/screening/cases/7/draft', '/api/screening/cases/7/draft?use_llm=true']);
  });

  it('carries the guardrail’s verdict when it rejects a rewrite', async () => {
    vi.stubGlobal('fetch', respond(200, out({ model: 'claude-x', fallback_reason: 'the model’s text failed the guardrail', violations: [{ kind: 'number', value: '42', why: 'Not in the case.' }] })));
    const d = await httpApi.getDraft('7', true);
    expect(d.source).toBe('template');
    expect(d.fallbackReason).toContain('guardrail');
    expect(d.violations).toEqual([{ kind: 'number', value: '42', why: 'Not in the case.' }]);
  });

  it('explains a refused rewrite in terms of the AI, not saving', async () => {
    vi.stubGlobal('fetch', respond(401, { detail: 'Missing or invalid X-API-Key.' }));
    await expect(httpApi.getDraft('7', true)).rejects.toThrow('Rewriting with AI is switched off');
  });

  it('reports no model when none is configured, so no AI button appears', async () => {
    vi.stubGlobal('fetch', respond(200, { model: null }));
    expect(await httpApi.draftingModel()).toBeNull();
    expect(await mockApi.draftingModel()).toBeNull();
    expect(mockApi.capabilities.drafts).toBe(false);
  });
});
