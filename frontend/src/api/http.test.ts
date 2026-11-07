import { describe, expect, it } from 'vitest';
import { caseInIssue, errorMessage, mapBands, mapCase, mapSummary, rankFindings, summariseIssue, type ArtifactOut, type CaseOut, type CaseSummary } from './http';

const summary = (over: Partial<CaseSummary> = {}): CaseSummary => ({ id: 1, domain: 'space', rule_id: 'fin-named-by-br', severity: 'high', title: 'BR names Finland in SAT (USA)', adm: 'USA', network: 'SAT', first_issue: 3083, last_issue: 3083, comment_deadline: '2027-02-27', review_status: 'pending', ...over });
const full = (over: Partial<CaseOut> = {}): CaseOut => ({ ...summary(), notice_ids: ['11', '31'], details: {}, source_sha256: 'abc', review_note: null, created_at: '2026-11-07T00:00:00', updated_at: '2026-11-07T00:00:00', ...over });
const artifact = (over: Partial<ArtifactOut> = {}): ArtifactOut => ({ id: 7, domain: 'space', issue_no: 3083, published_on: '2026-10-27', source_url: 'https://www.itu.int/sns/ific10/ific3083.zip', sha256: 'abc', size_bytes: 1, fetched_at: '2026-11-07T00:00:00', screen_status: 'done', screened_at: null, ...over });

describe('mapCase', () => {
  it('reads a screening rule’s details, with no invented numbers', () => {
    const f = mapCase(full({ rule_id: 'm4-no-space-to-earth', details: { method: 'screening', assumptions: ['No pfd'], visibility: ['GSO at 10 deg'], sections: ['9.6'], bands: [{ low_mhz: 1400, high_mhz: 1427, m4_primary_services: 'RAS', finnish_use: 'Radio astronomy', passive: true, m4_table_pages: '90', group_ids: [1, 2] }] } }), 'space-3083', 'ific3083.zip');
    expect(f.result).toBeNull();
    expect(f.marginDb).toBeNull();
    expect(f.confidence).toBeNull();
    expect(f.band).toBe('1400–1427 MHz');
    expect(f.bands[0]).toMatchObject({ passive: true, groupCount: 2 });
    expect(f.assumptions).toEqual(['No pfd']);
    expect(f.file).toMatchObject({ zip: 'ific3083.zip', zipSha256: 'abc' });
  });
  it('reads the agreed calculated keys once a calculation exists', () => {
    const f = mapCase(full({ details: { method: 'pfd_gso', calc_inputs: { gain_dbi: 30 }, value_db: -120, limit_db: -130, margin_db: 10, mask_id: 'm1', citations: [{ doc: 'RR', clause: 'Table 21-4' }] } }), 'space-3083', 'x');
    expect(f.result).toMatchObject({ method: 'pfd_gso', valueDb: -120, limitDb: -130, marginDb: 10, maskId: 'm1' });
    expect(f.marginDb).toBe(10);
    expect(f.citations).toEqual(['RR, Table 21-4']);
  });
  it('keeps every notice in the family', () => {
    const f = mapCase(full(), 'space-3083', 'x');
    expect([f.sourceId, ...f.relatedSourceIds]).toEqual(['11', '31']);
  });
});

describe('mapBands', () => {
  it('tolerates a case with no bands', () => expect(mapBands({})).toEqual([]));
});

describe('mapSummary', () => {
  it('falls back to the case title when there’s no network, and passes the deadline through', () => {
    const f = mapSummary(summary({ network: null }), 'space-3083');
    expect(f.title).toBe('BR names Finland in SAT (USA)');
    expect(f.windowDeadline).toBe('2027-02-27');
    expect(f.review.status).toBe('pending');
  });
  it('doesn’t treat an unknown severity as a real one', () => expect(mapSummary(summary({ severity: 'odd' }), 'x').severity).toBe('unscored'));
});

describe('caseInIssue', () => {
  it('includes the issues a case spans, in its own domain only', () => {
    const c = summary({ first_issue: 3074, last_issue: 3083 });
    expect(caseInIssue(c, 'space', 3074)).toBe(true);
    expect(caseInIssue(c, 'space', 3083)).toBe(true);
    expect(caseInIssue(c, 'space', 3084)).toBe(false);
    expect(caseInIssue(c, 'terrestrial', 3083)).toBe(false);
  });
});

describe('summariseIssue', () => {
  it('counts only this issue’s cases, and uses the latest deadline', () => {
    const cases = [summary({ id: 1 }), summary({ id: 2, severity: 'medium', rule_id: 'm4-no-space-to-earth', comment_deadline: '2027-03-01' }), summary({ id: 3, first_issue: 3074, last_issue: 3074 })];
    const s = summariseIssue(artifact(), cases);
    expect(s.severityCounts).toMatchObject({ high: 1, medium: 1 });
    expect(s.brListedNetworks).toBe(1);
    expect(s.commentDeadline).toBe('2027-03-01');
    expect(s.file.zip).toBe('ific3083.zip');
    expect(s.funnel).toEqual([]);
  });
  it('flags the issues the brief evaluates', () => {
    expect(summariseIssue(artifact({ issue_no: 3074 }), []).evaluationIssue).toBe(true);
    expect(summariseIssue(artifact(), []).evaluationIssue).toBe(false);
  });
  it('says terrestrial has no rules rather than no concerns', () => {
    const s = summariseIssue(artifact({ domain: 'terrestrial', screen_status: 'no_rules' }), []);
    expect(s.screenStatus).toBe('no_rules');
    expect(s.limitations.join(' ')).toContain('does not mean there are no concerns');
  });
});

describe('rankFindings', () => {
  it('orders by severity, then the nearest deadline', () => {
    const rows = [summary({ id: 1, severity: 'medium', comment_deadline: '2027-01-01' }), summary({ id: 2, severity: 'high', comment_deadline: '2027-03-01' }), summary({ id: 3, severity: 'high', comment_deadline: '2027-02-01' })].map((c) => mapSummary(c, 'x'));
    expect(rankFindings(rows).map((f) => f.id)).toEqual(['3', '2', '1']);
  });
});

describe('errorMessage', () => {
  it('explains a missing key and a stopped service without technical detail', () => {
    expect(errorMessage('screening', 403, 'x')).toContain('IFIC_API_KEY');
    expect(errorMessage('screening', 401, null)).toContain('IFIC_API_KEY');
    expect(errorMessage('sync', 500, null)).toContain('sync service');
    expect(errorMessage('sync', 409, 'A sync is already running.')).toBe('A sync is already running.');
  });
});
