import { describe, expect, it } from 'vitest';
import { draftLetter } from '../lib/letter';
import { formatDuration } from '../lib/format';
import { caseInIssue, definitionIn, definitionOf, errorMessage, fileName, mapBands, mapCase, mapSummary, rankFindings, ruleLabel, runFromArtifact, summariseIssue, type ArtifactOut, type CaseOut, type CaseSummary } from './http';

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
  it('reads Finnish restrictions and RR footnotes naming Finland', () => {
    const [b] = mapBands({ bands: [{ low_mhz: 430, high_mhz: 432, m4_restrictions: ['Restrictions on use (RR 5.113).'], m4_national_use: ['Military use'], m4_rr_footnotes: ['5.113'], rr_footnotes_naming_finland: [{ footnote: '5.275', kind: 'Additional allocation', pdf_page: 104 }] }] });
    expect(b.restrictions).toEqual(['Restrictions on use (RR 5.113).']);
    expect(b.nationalUse).toEqual(['Military use']);
    expect(b.rrFootnotesNamingFinland).toEqual([{ footnote: '5.275', kind: 'Additional allocation', pdfPage: 104 }]);
  });
});

describe('mapSummary', () => {
  it('falls back to the case title when there’s no network, and passes the deadline through', () => {
    const f = mapSummary(summary({ network: null }), 'space-3083');
    expect(f.title).toBe('BR names Finland in SAT (USA)');
    expect(f.windowDeadline).toBe('2027-02-27');
    expect(f.review.status).toBe('pending');
  });
  it('carries M4 primary services on list rows, and none when the service omits them', () => {
    expect(mapSummary({ ...summary(), m4_primary_services: ['FIXED', 'MOBILE'] }, 'x').m4PrimaryServices).toEqual(['FIXED', 'MOBILE']);
    expect(mapSummary(summary(), 'x').m4PrimaryServices).toEqual([]);
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

  it('states the terrestrial limits once terrestrial rules have run', () => {
    const s = summariseIssue(artifact({ domain: 'terrestrial', screen_status: 'done' }), []);
    expect(s.limitations.join(' ')).toContain('extended above 470 MHz');
    expect(s.limitations.join(' ')).not.toContain('no rules');
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

describe('station overlap cases', () => {
  const details = { method: 'screening', station_ids: ['600529@R215', '601452@R224'], classes: { 'no class': 2 }, sections: ['9.6'], assumptions: ['61 of 873 stations have no RX frequency and were skipped'], bands: [{ low_mhz: 18875, high_mhz: 19067.5, classes: { 'no class': 2 }, station_ids: ['600529@R215', '601452@R224'], group_ids: [1] }] };
  const f = mapCase(full({ rule_id: 'station-rx-overlap', severity: 'medium', details }), 'space-3083', 'ific3083.zip');

  it('reads stations from the case, overall and per band', () => {
    expect(f.kindLabel).toBe('On a Finnish station’s frequency');
    expect(f.stationCount).toBe(2);
    expect(f.stationIds).toEqual(['600529@R215', '601452@R224']);
    expect(f.stationClasses).toEqual({ 'no class': 2 });
    expect(f.bands[0].stationIds).toHaveLength(2);
  });
  it('drafts a letter about receivers, not about allocations or exceeded limits', () => {
    const letter = draftLetter(f);
    expect(letter).toContain('overlap frequencies used by Finnish stations');
    expect(letter).toContain('possible concern only');
    expect(letter).toContain('18875–19067.5 MHz');
    expect(letter).not.toContain('no space-to-Earth allocation');
    expect(letter).not.toMatch(/exceed/i);
  });
});

describe('station cases with pfd evidence', () => {
  const details = {
    method: 'pfd_gso', value_db: -111.2, limit_db: -113.2, margin_db: 2.0, station_ids: ['624714@R352', '1000@R100'],
    bands: [{ low_mhz: 18415, high_mhz: 18525, station_ids: ['624714@R352'], group_ids: [1], m4_space_to_earth: 'allocated', m4_primary_services: 'FIXED' }],
    stations_overlapping: [
      { station_id: '624714@R352', status: 'exceeds', value_db: -111.2, limit_db: -113.2, margin_db: 2.0, angle_deg: 8.55, matched_bands: [{ side: 'tx' }], field_location: 'station site, not the receiver' },
      { station_id: '1000@R100', status: 'bound_above', matched_bands: [{ side: 'rx' }], filing_upper_bound: { margin_db: 4.1 } },
    ],
  };
  const f = mapCase(full({ rule_id: 'station-rx-overlap', severity: 'high', details }), 'space-3074', 'ific3074.zip');

  it('maps each station’s result, and never turns a filing bound into a station value', () => {
    const [tx, bound] = f.stationResults ?? [];
    expect(tx).toMatchObject({ id: '624714@R352', sides: ['tx'], status: 'exceeds', marginDb: 2.0, atSiteOnly: true });
    expect(bound).toMatchObject({ status: 'bound_above', marginDb: null, valueDb: null, filingBoundDb: 4.1, atSiteOnly: false });
    expect(f.bands[0].m4SpaceToEarth).toBe('allocated');
  });
  it('drafts a letter quoting only values calculated at stations', () => {
    const letter = draftLetter(f);
    expect(letter).toContain('Station 624714@R352 (TX)');
    expect(letter).toContain('at the site, which is not where this band is received');
    expect(letter).toContain("space-to-Earth in Finland's frequency table: allocated");
    expect(letter).not.toContain('Station 1000@R100');
    expect(letter).toContain('1 more station, listed in the case');
  });
});

describe('screening-only letters', () => {
  it('never claim a limit was exceeded', () => {
    const allocation = mapCase(full({ rule_id: 'm4-no-space-to-earth', details: { bands: [{ low_mhz: 1400, high_mhz: 1427, finnish_use: 'Radio astronomy' }] } }), 'x', 'y');
    const named = mapCase(full({ details: { provisions: ['9.14'] } }), 'x', 'y');
    for (const f of [allocation, named]) expect(draftLetter(f)).not.toMatch(/exceed/i);
    expect(draftLetter(allocation)).toContain('no space-to-Earth allocation');
    expect(draftLetter(named)).toContain('9.14');
  });
});

describe('file names', () => {
  it('reads each kind of source', () => {
    expect(fileName('https://www.itu.int/sns/ific10/ific3083.zip')).toBe('ific3083.zip');
    expect(fileName('import:ific3074.zip')).toBe('ific3074.zip');
    expect(fileName('upload:brific3076.mdb')).toBe('brific3076.mdb');
  });
});

describe('runFromArtifact', () => {
  it('follows screening status, and marks no rules as not a clean result', () => {
    expect(runFromArtifact(artifact({ screen_status: 'pending' })).status).toBe('running');
    expect(runFromArtifact(artifact({ screen_status: 'failed' })).status).toBe('failed');
    const done = runFromArtifact(artifact({ screen_status: 'done' }));
    expect(done).toMatchObject({ status: 'succeeded', id: 'issue-7', issueId: 'space-3083', fileName: 'ific3083.zip' });
    expect(runFromArtifact(artifact({ domain: 'terrestrial', screen_status: 'no_rules' })).message).toContain('does not mean there are no concerns');
    expect(runFromArtifact(artifact(), 'Already stored. ').message).toContain('Already stored.');
  });
});

describe('labels and durations', () => {
  it('leaves an unknown rule readable', () => expect(ruleLabel('new-rule')).toBe('new-rule'));
  it('formats the next check', () => {
    expect(formatDuration(20)).toBe('under a minute');
    expect(formatDuration(600)).toBe('10 min');
    expect(formatDuration(5 * 3600 + 720)).toBe('5 h 12 min');
    expect(formatDuration(7200)).toBe('2 h');
    expect(formatDuration(5 * 86400)).toBe('5 days');
  });
});

describe('rules written by experts', () => {
  it('round-trips a rule definition between the service and the UI', () => {
    const wire = { orbit: 'gso' as const, visible_from_finland: false, adm_in: ['RUS'], adm_not_in: [], provision_in: ['9.6'], direction: 'receive' as const,
      frequency_ranges: [{ low_mhz: 5925, high_mhz: 6425 }], m4: { space_to_earth: 'any' as const, earth_to_space: 'yes' as const, terrestrial_primary: 'no' as const, passive: 'any' as const, primary_services_any: ['FIXED'] } };
    const ui = definitionOf(wire);
    expect(ui.frequencyRanges).toEqual([{ lowMhz: 5925, highMhz: 6425 }]);
    expect(ui.m4.earthToSpace).toBe('yes');
    expect(definitionIn(ui)).toEqual(wire);
  });

  it('labels and explains a case from a custom rule', () => {
    expect(ruleLabel('custom-42')).toBe('Custom rule 42');
    const f = mapCase(full({ rule_id: 'custom-3', details: {
      custom_rule: { id: 3, name: 'Uplinks', version: 2 }, conditions: ['The satellite receives'],
      matched_assignments: [{ group_id: 9, freq_min_mhz: 14100, freq_max_mhz: 14200, direction: 'receive' }], matched_assignment_count: 140,
    } }), 'space-3083', 'x');
    expect(f.customRule).toEqual({ id: 3, name: 'Uplinks', version: 2, conditions: ['The satellite receives'], matchedAssignments: [{ groupId: 9, fMinMhz: 14100, fMaxMhz: 14200, direction: 'receive' }], matchedCount: 140 });
    expect(mapCase(full(), 'x', 'y').customRule).toBeNull();
  });
});

describe('large station lists', () => {
  it('counts stations from the stored total, not the sample the case keeps', () => {
    const f = mapCase(full({ rule_id: 'station-rx-overlap', details: {
      station_count: 2_400_000, stations_listed: 1, station_ids: ['1@R13'], station_status_counts: { below: 2_400_000 },
      stations_overlapping: [{ station_id: '1@R13', status: 'below', matched_bands: [{ side: 'rx' }] }],
      bands: [{ low_mhz: 1, high_mhz: 2, station_count: 2_400_000, station_ids: ['1@R13'] }],
    } }), 'space-3083', 'x');
    expect([f.stationCount, f.stationsListed, f.stationResults?.length, f.bands[0].stationCount]).toEqual([2_400_000, 1, 1, 2_400_000]);
  });

  it('falls back to the id list on cases saved before the cap', () => {
    const f = mapCase(full({ details: { station_ids: ['1@R13', '2@R14'], bands: [{ low_mhz: 1, high_mhz: 2, station_ids: ['1@R13'] }] } }), 'x', 'y');
    expect([f.stationCount, f.bands[0].stationCount]).toEqual([2, 1]);
  });
});
