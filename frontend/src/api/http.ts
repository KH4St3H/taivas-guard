// Talks to the IFIC Guard services through the /api proxy. Their shapes are defined in
// ific_guard/schemas.py and the Case.details contract in .scratch/ific-guard-delivery/map.md.
import { SEVERITY_ORDER } from '../lib/severity';
import type { Api, BandMatch, CeptCompliance, Coverage, Trends, NewRun, Run, CalculatedResult, CustomRule, CustomRuleRef, Domain, DomainFreshness, Finding, FunnelStage, IssueSummary, MonitorStatus, ReferenceSource, ReviewState, RuleDefinition, RuleSave, RuleSpec, RuleVersion, ScreenStatus, StationQuery, Severity, StationResult, SyncRun } from './types';

export interface ArtifactOut { id: number; domain: string; issue_no: number; published_on: string | null; source_url: string; sha256: string; size_bytes: number; fetched_at: string; screen_status: string; screened_at: string | null }
export interface SyncRunOut { id: number; trigger: string; started_at: string; finished_at: string | null; status: string; discovered: number; fetched: number; errors: string[] }
export interface CaseSummary { id: number; domain: string; rule_id: string; severity: string; title: string; adm: string | null; network: string | null; first_issue: number; last_issue: number; comment_deadline: string | null; review_status: string; m4_primary_services?: string[] }
export interface CaseOut extends CaseSummary { notice_ids: string[]; details: Record<string, unknown>; source_sha256: string; review_note: string | null; created_at: string; updated_at: string }
export interface UploadOut { artifact: ArtifactOut; new: boolean }
export interface StatusOut { running: boolean; schedule?: string | null; next_run_in_s?: number | null; domains: Record<string, { latest_issue: number | null; published_on: string | null; age_days: number | null; stale: boolean }> }

type Service = 'sync' | 'screening';
const LABEL: Record<Service, string> = { sync: 'sync', screening: 'screening' };

export class ApiError extends Error {
  constructor(message: string, readonly status: number | null) { super(message); }
}

/** Turns a failed response into something a reviewer can act on. */
export function errorMessage(service: Service, status: number, detail: string | null): string {
  if (status === 401 || status === 403) return 'Saving is switched off. Set IFIC_API_KEY for the frontend server to match the services, then restart it.';
  if (status === 409) return detail ?? 'That’s already running.';
  if (status === 404) return detail ?? 'That wasn’t found.';
  if (status >= 500) return `The ${LABEL[service]} service isn’t responding. Check that it’s running on its usual port.`;
  return detail ?? `The ${LABEL[service]} service rejected the request (${status}).`;
}

async function call<T>(service: Service, path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/${service}${path}`, init);
  } catch {
    throw new ApiError(`The ${LABEL[service]} service can’t be reached.`, null);
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
      // FastAPI lists validation errors; show their messages, without pydantic's "Value error," prefix.
      else if (Array.isArray(body.detail)) detail = (body.detail as { msg?: string }[]).map((e) => String(e.msg ?? '').replace(/^Value error, /, '')).filter(Boolean).join(' ') || null;
    } catch { /* an empty proxy error has no body */ }
    throw new ApiError(errorMessage(service, res.status, detail), res.status);
  }
  return (await res.json()) as T;
}

const RULE_LABELS: Record<string, string> = {
  'fin-named-by-br': 'ITU names Finland',
  'm4-no-space-to-earth': 'No space-to-Earth allocation in Finland',
  'station-rx-overlap': 'On a Finnish station’s frequency',
  'pfd-gso-art21': 'pfd against RR Article 21 (GSO)',
  'pfd-ngso-art21': 'pfd against RR Article 21 (non-GSO)',
  'pfd-gso-app5': 'pfd against RR Appendix 5 (GSO)',
  'pfd-ngso-app5': 'pfd against RR Appendix 5 (non-GSO)',
  'pfd-gso-cept': 'pfd against a CEPT condition (GSO)',
  'pfd-ngso-cept': 'pfd against a CEPT condition (non-GSO)',
};
export const ruleLabel = (id: string) => RULE_LABELS[id] ?? (id.startsWith('custom-') ? `Custom rule ${id.slice(7)}` : id);

// Rules experts write are named in the service; load the names once so lists can label their cases.
let ruleNames: Promise<void> | null = null;
const loadRuleNames = () => (ruleNames ??= call<RuleOut[]>('screening', '/rules')
  .then((rows) => { for (const r of rows) RULE_LABELS[r.rule_id] = r.name; })
  .catch(() => { ruleNames = null; })); // an older service has no rules endpoint; ids are shown instead

interface DefinitionOut {
  orbit: RuleDefinition['orbit']; visible_from_finland: boolean; adm_in: string[]; adm_not_in: string[]; provision_in: string[];
  direction: RuleDefinition['direction']; frequency_ranges: { low_mhz: number; high_mhz: number }[];
  m4: { space_to_earth: RuleDefinition['m4']['spaceToEarth']; earth_to_space: RuleDefinition['m4']['earthToSpace']; terrestrial_primary: RuleDefinition['m4']['terrestrialPrimary']; passive: RuleDefinition['m4']['passive']; primary_services_any: string[] };
}
interface SpecOut { name: string; description: string; severity: RuleSpec['severity']; title_template: string; definition: DefinitionOut }
interface RuleVersionOut extends SpecOut { version: number; enabled: boolean; saved_by: string; note: string; saved_at: string }
export interface RuleOut extends SpecOut { id: number; rule_id: string; enabled: boolean; version: number; conditions: string[]; case_count: number; updated_at: string; versions: RuleVersionOut[] }
interface PreviewOut { issue_no: number; total: number; by_adm: Record<string, number>; hits: { network: string | null; adm: string | null; title: string; severity: string; notice_ids: number[]; bands: number; assignments: number }[] }

export const definitionOf = (d: DefinitionOut): RuleDefinition => ({
  orbit: d.orbit, visibleFromFinland: d.visible_from_finland, admIn: d.adm_in, admNotIn: d.adm_not_in, provisionIn: d.provision_in, direction: d.direction,
  frequencyRanges: d.frequency_ranges.map((r) => ({ lowMhz: r.low_mhz, highMhz: r.high_mhz })),
  m4: { spaceToEarth: d.m4.space_to_earth, earthToSpace: d.m4.earth_to_space, terrestrialPrimary: d.m4.terrestrial_primary, passive: d.m4.passive, primaryServicesAny: d.m4.primary_services_any },
});
export const definitionIn = (d: RuleDefinition): DefinitionOut => ({
  orbit: d.orbit, visible_from_finland: d.visibleFromFinland, adm_in: d.admIn, adm_not_in: d.admNotIn, provision_in: d.provisionIn, direction: d.direction,
  frequency_ranges: d.frequencyRanges.map((r) => ({ low_mhz: r.lowMhz, high_mhz: r.highMhz })),
  m4: { space_to_earth: d.m4.spaceToEarth, earth_to_space: d.m4.earthToSpace, terrestrial_primary: d.m4.terrestrialPrimary, passive: d.m4.passive, primary_services_any: d.m4.primaryServicesAny },
});
const specOf = (r: SpecOut): RuleSpec => ({ name: r.name, description: r.description, severity: r.severity, titleTemplate: r.title_template, definition: definitionOf(r.definition) });
const specIn = (r: RuleSpec): SpecOut => ({ name: r.name, description: r.description, severity: r.severity, title_template: r.titleTemplate, definition: definitionIn(r.definition) });
const versionOf = (v: RuleVersionOut): RuleVersion => ({ ...specOf(v), version: v.version, enabled: v.enabled, savedBy: v.saved_by, note: v.note, savedAt: utc(v.saved_at) });
export const ruleOf = (r: RuleOut): CustomRule => {
  RULE_LABELS[r.rule_id] = r.name;
  return { ...specOf(r), id: r.id, ruleId: r.rule_id, enabled: r.enabled, version: r.version, conditions: r.conditions, caseCount: r.case_count, updatedAt: utc(r.updated_at), versions: r.versions.map(versionOf) };
};

const stationParams = (q: StationQuery) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== '') p.set(k, String(v));
  return p.toString();
};

function mapCompliance(d: Record<string, unknown>): CeptCompliance | null {
  const c = d.cept_compliance_list as Record<string, unknown> | undefined;
  if (!c || typeof c.listed !== 'boolean') return null;
  return { doc: String(c.doc), clause: String(c.clause), page: Number(c.printed_page), listed: c.listed, systems: (c.systems as { adm: string; network: string; commitment: string }[]) ?? [] };
}

function mapCustomRule(d: Record<string, unknown>): CustomRuleRef | null {
  const rule = d.custom_rule as { id?: number; name?: string; version?: number } | undefined;
  if (!rule || typeof rule.id !== 'number') return null;
  const assignments = Array.isArray(d.matched_assignments) ? (d.matched_assignments as Record<string, unknown>[]) : [];
  return {
    id: rule.id, name: String(rule.name ?? ''), version: Number(rule.version ?? 0), conditions: strings(d.conditions),
    matchedAssignments: assignments.map((a) => ({ groupId: Number(a.group_id), fMinMhz: Number(a.freq_min_mhz), fMaxMhz: Number(a.freq_max_mhz), direction: String(a.direction) })),
    matchedCount: typeof d.matched_assignment_count === 'number' ? d.matched_assignment_count : assignments.length,
  };
}

const EVALUATED = new Set(['space-3074', 'terrestrial-3076']);
const issueKey = (domain: string, issue: number) => `${domain}-${issue}`;
const asSeverity = (s: string): Severity => (s === 'high' || s === 'medium' || s === 'low' ? s : 'unscored');
const strings = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : []);
const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
// Downloads store a URL; imports and uploads store import:name or upload:name.
export const fileName = (source: string) => source.replace(/^(import|upload):/, '').split('/').pop() ?? source;
const fileOf = (name: string, sha: string) => ({ zip: name, zipSha256: sha, mdb: '', mdbSha256: '' });

const LETTERS = 'ific-guard-letters-v1';
function readLetters(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(LETTERS) ?? '{}') as Record<string, string>; } catch { return {}; }
}
function saveLetter(id: string, text: string) {
  try { localStorage.setItem(LETTERS, JSON.stringify({ ...readLetters(), [id]: text })); } catch { /* the edit lasts until the page closes */ }
}

function reviewOf(status: string, note: string | null, id: string): ReviewState {
  return { status: status === 'accepted' || status === 'rejected' ? status : 'pending', note: note ?? '', letter: readLetters()[id] ?? null, history: [] };
}

const bandLabel = (b: BandMatch) => `${b.lowMhz}–${b.highMhz} MHz`;

export function mapBands(details: Record<string, unknown>): BandMatch[] {
  if (!Array.isArray(details.bands)) return [];
  return (details.bands as Record<string, unknown>[]).map((b) => ({
    lowMhz: Number(b.low_mhz), highMhz: Number(b.high_mhz), primaryServices: String(b.m4_primary_services ?? ''), finnishUse: String(b.finnish_use ?? ''),
    passive: b.passive === true, pages: String(b.m4_table_pages ?? ''), groupCount: Array.isArray(b.group_ids) ? b.group_ids.length : 0,
    stationIds: strings(b.station_ids), stationCount: typeof b.station_count === 'number' ? b.station_count : strings(b.station_ids).length, classes: (b.classes as Record<string, number>) ?? {},
    m4SpaceToEarth: typeof b.m4_space_to_earth === 'string' ? b.m4_space_to_earth : null,
    restrictions: strings(b.m4_restrictions), nationalUse: strings(b.m4_national_use), rrFootnotesCited: strings(b.m4_rr_footnotes),
    rrFootnotesNamingFinland: Array.isArray(b.rr_footnotes_naming_finland)
      ? (b.rr_footnotes_naming_finland as Record<string, unknown>[]).map((f) => ({ footnote: String(f.footnote), kind: String(f.kind ?? ''), pdfPage: Number(f.pdf_page) }))
      : [],
  }));
}

/** Per-station evidence from `stations_overlapping`, worst first as the service orders it. */
export function mapStationResults(details: Record<string, unknown>): StationResult[] {
  return Array.isArray(details.stations_overlapping) ? mapStationRecords(details.stations_overlapping as Record<string, unknown>[]) : [];
}

export function mapStationRecords(records: Record<string, unknown>[]): StationResult[] {
  return records.map((r) => ({
    id: String(r.station_id), licence: typeof r.licence_class === 'string' ? r.licence_class : null,
    sides: Array.isArray(r.matched_bands) ? [...new Set((r.matched_bands as Record<string, unknown>[]).map((b) => String(b.side)))].sort() : [],
    status: typeof r.status === 'string' ? r.status : 'calculated', valueDb: num(r.value_db), limitDb: num(r.limit_db), marginDb: num(r.margin_db),
    angleDeg: num(r.angle_deg), atSiteOnly: typeof r.field_location === 'string', locationFlagged: r.location_flagged === true,
    filingBoundDb: num((r.filing_upper_bound as Record<string, unknown> | undefined)?.margin_db),
  }));
}

function mapResult(d: Record<string, unknown>): CalculatedResult | null {
  if (typeof d.method !== 'string' || d.method === 'screening') return null;
  return {
    method: d.method, inputs: (d.calc_inputs as Record<string, unknown>) ?? {}, valueDb: num(d.value_db), limitDb: num(d.limit_db), marginDb: num(d.margin_db),
    maskId: typeof d.mask_id === 'string' ? d.mask_id : null, worstPoint: (d.worst_point as Record<string, unknown>) ?? null,
  };
}

function mapCitations(d: Record<string, unknown>): string[] {
  if (!Array.isArray(d.citations)) return [];
  return (d.citations as Record<string, unknown>[]).map((c) => [c.doc, c.clause, c.page_or_url].filter(Boolean).join(', '));
}

function base(c: CaseSummary, issueId: string) {
  const id = String(c.id);
  return {
    id, issueId, domain: c.domain as Domain, issue: c.last_issue, firstIssue: c.first_issue, lastIssue: c.last_issue, kind: c.rule_id, kindLabel: ruleLabel(c.rule_id),
    title: c.network ?? c.title, summary: c.title, adm: c.adm ?? 'Unknown', orbit: null, provision: null, severity: asSeverity(c.severity), windowDeadline: c.comment_deadline,
    m4PrimaryServices: c.m4_primary_services ?? [],
    confidence: null, confidenceReasons: [], stations: [], stationIds: [], stationClasses: {}, calc: null, terrestrial: null,
  };
}

/** List rows carry no details, so anything from `details` stays empty until the case is opened. */
export function mapSummary(c: CaseSummary, issueId: string): Finding {
  return {
    ...base(c, issueId), band: null, sourceId: '', relatedSourceIds: [], sections: [], coordProvisions: [], severityReasons: [], marginDb: null, stationCount: null, bands: [], visibility: [], basis: null, result: null, assumptions: [], citations: [], evidence: [],
    file: fileOf('', ''), updatedAt: null, review: reviewOf(c.review_status, null, String(c.id)),
  };
}

export function mapCase(c: CaseOut, issueId: string, sourceName: string): Finding {
  const d = c.details ?? {};
  const bands = mapBands(d);
  const result = mapResult(d);
  const provisions = strings(d.provisions);
  const [first, ...rest] = c.notice_ids;
  return {
    ...base(c, issueId),
    band: bands.length === 1 ? bandLabel(bands[0]) : bands.length > 1 ? `${bands.length} bands` : null,
    sourceId: first ?? '', relatedSourceIds: rest, sections: strings(d.sections), coordProvisions: provisions,
    severityReasons: [c.title], marginDb: result?.marginDb ?? null, stationCount: typeof d.station_count === 'number' ? d.station_count : Array.isArray(d.station_ids) ? d.station_ids.length : null,
    stationsListed: typeof d.stations_listed === 'number' ? d.stations_listed : undefined,
    stationStatusCounts: (d.station_status_counts as Record<string, number> | undefined) ?? undefined,
    stationIds: strings(d.station_ids), stationClasses: (d.classes as Record<string, number>) ?? {}, stationResults: mapStationResults(d),
    bands, customRule: mapCustomRule(d), ceptCompliance: mapCompliance(d), visibility: strings(d.visibility), basis: typeof d.basis === 'string' ? d.basis : null, result, assumptions: strings(d.assumptions), citations: mapCitations(d),
    evidence: [
      { table: 'notice', key: `ntc_id in ${c.notice_ids.join(', ')}` },
      ...(Array.isArray(d.group_ids) ? [{ table: 'grp', key: `${d.group_ids.length} group(s) named in the coordination data` }] : []),
      ...provisions.map((p) => ({ table: 'provn', key: `adm = 'FIN', provision ${p}` })),
    ],
    file: fileOf(sourceName, c.source_sha256), updatedAt: c.updated_at, review: reviewOf(c.review_status, c.review_note, String(c.id)),
  };
}

export function rankFindings(rows: Finding[]): Finding[] {
  return [...rows].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || (a.windowDeadline ?? '9').localeCompare(b.windowDeadline ?? '9') || a.title.localeCompare(b.title));
}

/** A case stays open across issues, so it belongs to every stored issue in its first-to-last range. */
export const caseInIssue = (c: CaseSummary, domain: string, issue: number) => c.domain === domain && c.first_issue <= issue && issue <= c.last_issue;

const GAPS: Record<Domain, string[]> = {
  space: ['No beam coverage check: maximum notified gain is applied towards Finland, as Traficom said to assume, so the M4 rule over-flags by design', 'Only Space database version 10 is supported; Finnish operating satellites are not yet protected', 'AP30, AP30A and AP30B aren’t screened', 'Station results come from the pfd calculation at each station; a band with no limit mask stays uncalculated, and antenna direction isn’t used'],
  terrestrial: ['Land-mobile notices from the configured neighbours only, within an approximate 300 km screen', 'P.1546 without terrain; the 400-470 MHz T/R 25-08 threshold is extended above 470 MHz on Traficom’s instruction; Russian-border applicability is provisional', 'Notices that could not be calculated are listed for expert review; they are not clear results'],
};

// An artifact screened before terrestrial rules existed keeps this status until it is screened again.
const NO_RULES_GAPS = ['No rules ran on this stored file', 'This does not mean there are no concerns'];

export function summariseIssue(a: ArtifactOut, cases: CaseSummary[]): IssueSummary {
  const domain = a.domain as Domain;
  const mine = cases.filter((c) => caseInIssue(c, a.domain, a.issue_no));
  const severityCounts: Record<Severity, number> = { high: 0, medium: 0, low: 0, unscored: 0 };
  const rules = new Map<string, number>();
  for (const c of mine) {
    severityCounts[asSeverity(c.severity)]++;
    rules.set(c.rule_id, (rules.get(c.rule_id) ?? 0) + 1);
  }
  const ruleCounts: FunnelStage[] = [...rules.entries()].sort((x, y) => y[1] - x[1]).map(([key, n]) => ({ key, label: ruleLabel(key), n }));
  const deadlines = mine.map((c) => c.comment_deadline).filter((d): d is string => !!d).sort();
  const id = issueKey(a.domain, a.issue_no);
  return {
    id, artifactId: a.id, domain, issue: a.issue_no, releasedOn: a.published_on, screenStatus: a.screen_status as ScreenStatus, screenedAt: a.screened_at,
    commentDeadline: deadlines[deadlines.length - 1] ?? null, file: fileOf(fileName(a.source_url), a.sha256), sourceUrl: a.source_url, evaluationIssue: EVALUATED.has(id),
    counts: [{ label: 'Cases', value: mine.length }, ...ruleCounts.map((r) => ({ label: r.label, value: r.n }))], funnel: [], ruleCounts, severityCounts,
    brListedNetworks: rules.get('fin-named-by-br') ?? 0, limitations: a.screen_status === 'no_rules' ? NO_RULES_GAPS : GAPS[domain] ?? [],
  };
}

const allCases = () => call<CaseSummary[]>('screening', '/cases?limit=1000');
const newestPerIssue = (rows: ArtifactOut[]) => { // the API lists newest first; a republished issue keeps only its latest revision
  const seen = new Set<string>();
  return rows.filter((a) => { const k = issueKey(a.domain, a.issue_no); if (seen.has(k)) return false; seen.add(k); return true; });
};
const artifacts = async () => newestPerIssue(await call<ArtifactOut[]>('sync', '/issues?limit=500'));

export const toSyncRun = (r: SyncRunOut): SyncRun => ({ id: r.id, trigger: r.trigger === 'schedule' ? 'Scheduled' : r.trigger === 'manual' ? 'Manual' : r.trigger, startedAt: r.started_at, finishedAt: r.finished_at, status: r.status, discovered: r.discovered, fetched: r.fetched, errors: r.errors });
// The API returns naive UTC timestamps; mark them so the browser doesn't read them as local time.
const utc = (t: string) => (/[zZ]|[+-]\d\d:\d\d$/.test(t) ? t : `${t}Z`);

// Sends the file with progress, which fetch can't report.
function uploadFile(input: NewRun, onProgress?: (fraction: number) => void): Promise<UploadOut> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', input.file);
    form.append('domain', input.domain);
    if (input.issue) form.append('issue_no', String(input.issue));
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/sync/issues/upload');
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    xhr.onerror = () => reject(new ApiError('The sync service can’t be reached.', null));
    xhr.onload = () => {
      let body: { detail?: unknown } | null = null;
      try { body = JSON.parse(xhr.responseText) as { detail?: unknown }; } catch { /* an empty proxy error has no body */ }
      if (xhr.status >= 200 && xhr.status < 300 && body) resolve(body as unknown as UploadOut);
      else reject(new ApiError(errorMessage('sync', xhr.status, typeof body?.detail === 'string' ? body.detail : null), xhr.status));
    };
    xhr.send(form);
  });
}

export function runFromArtifact(a: ArtifactOut, message = ''): Run {
  const status = a.screen_status === 'failed' ? 'failed' : a.screen_status === 'pending' ? 'running' : 'succeeded';
  const done = a.screen_status === 'no_rules' ? 'No screening rules ran on this stored file. Re-screen it with the current service. This does not mean there are no concerns.' : 'Screening finished.';
  return {
    id: `issue-${a.id}`, trigger: 'on_demand', domain: a.domain as Domain, issue: a.issue_no, fileName: fileName(a.source_url), sha256: a.sha256, sizeBytes: a.size_bytes, startedAt: utc(a.fetched_at),
    status, stageIndex: status === 'running' ? 1 : status === 'failed' ? 1 : 3, issueId: issueKey(a.domain, a.issue_no),
    message: status === 'failed' ? 'Screening failed. Check the screening service’s log, then try screening it again.' : `${message}${done}`,
  };
}

const SOURCES: ReferenceSource[] = [
  { name: 'Regulation M4 allocation table', version: 'Traficom API snapshot, 7 Nov 2026', detail: 'National allocation bands in data/national/m4_bands.csv, with sub-band directions, Finnish restrictions, reserved use and cited RR footnotes. Used by M4 and station screening; restrictions are displayed without changing severity.', url: 'https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko', status: 'loaded' },
  { name: 'ITU coordination data', version: 'Each IFIC: provn and tr_provn', detail: 'Finds API/A, CR/C and notification-stage filings naming Finland. Notification cases have no assumed response deadline; AP30-family screening remains unsupported.', url: null, status: 'loaded' },
  { name: 'Traficom frequencies of interest', version: 'v05112026 (synthetic)', detail: 'Protects both RX and TX bands. PFD is evaluated at station coordinates where inputs and masks permit; lists are paged. TX-site fields do not represent the location of a remote receiver.', url: null, status: 'loaded' },
  { name: 'Finnish earth stations and RR footnotes naming Finland', version: 'M4 API snapshot; RR 2024', detail: 'Protects the receiving bands of the named Sodankyla site, currently without coordinates. Shows 16 extracted Finland-related RR footnotes with source pages; their text needs expert verification.', url: 'https://www.itu.int/pub/r-reg-rr', status: 'partial' },
  { name: 'ITU Radio Regulations PFD criteria', version: '2024 edition', detail: 'GSO and non-GSO rules evaluate sourced Article 21 limits and Appendix 5 coordination triggers. Non-GSO upper bounds are distinguished from sampled exceedances; unsupported masks and missing inputs remain review items.', url: 'https://www.itu.int/pub/r-reg-rr', status: 'partial' },
  { name: 'ECC Decision (25)02', version: '27 June 2025; Finland implementation planned 31 Jan 2027', detail: 'Checks the sourced -142 dB(W/(m2.4kHz)) condition in 862-870 MHz and the Decision’s list of compliant systems. This is a CEPT condition, not an RR limit. Unwanted emissions outside the band cannot be evaluated from these filings.', url: 'https://docdb.cept.org/download/4784', status: 'partial' },
  { name: 'ECC T/R 25-08 and ITU-R P.1546', version: 'June 2025; P.1546-6', detail: 'Land-mobile field strengths at the Finnish boundary use P.1546 without terrain. Annex 1 indicative thresholds are extended above 470 MHz on Traficom’s instruction. Russian-border applicability remains provisional; missing antenna heights stay uncalculated.', url: 'https://docdb.cept.org/document/909', status: 'partial' },
  { name: 'Natural Earth boundary and land mask', version: '1:50m reference data', detail: 'Approximate Finnish boundary/coast evaluation points and land/sea path classification; lakes count as land. The distance screen is an engineering approximation.', url: 'https://www.naturalearthdata.com/', status: 'loaded' },
];

export const httpApi: Api = {
  mode: 'live',
  capabilities: { upload: true, checkItuNow: true, rescreen: true, reviewStatuses: ['accepted', 'rejected', 'pending'], letterStorage: 'browser', customRules: true, stationLists: true, coverage: true, trends: true },
  severityNote: 'Deterministic rules set severity; the 3 dB watch band and ranking weights are project choices. Calculated exceedances use worst-case assumptions. Expert review is required; severity does not establish interference or a regulatory breach.',
  listSeverityRules: async () => [
    { severity: 'High', rule: 'BR names Finland; passive-band M4 concerns; unflagged calculated PFD exceedances, including at stations; or a terrestrial indicative-threshold exceedance with score at least 50, subject to the caps below.' },
    { severity: 'Medium', rule: 'M4 allocation concerns; PFD within the project watch band, upper-bound concerns, missing calculations or flagged inputs. Station severity follows its strongest evidence. Terrestrial results use medium for missing criteria, sensitivities or special interests, and cap flagged or notifier-declared FIN-coordinated exceedances at medium.' },
    { severity: 'Low', rule: 'Calculated PFD more than 3 dB below its criterion, a sufficiently low upper bound, or no visible station; terrestrial results below the indicative threshold without sensitivity, FIN coordination or special-interest reasons for medium. These are not compliance findings.' },
  ],
  listIssues: async () => {
    const [rows, cases] = await Promise.all([artifacts(), allCases(), loadRuleNames()]);
    return rows.map((a) => summariseIssue(a, cases));
  },
  getMonitor: async (): Promise<MonitorStatus> => {
    const [status, runs] = await Promise.all([call<StatusOut>('sync', '/status'), call<SyncRunOut[]>('sync', '/runs?limit=1')]);
    const last = runs[0];
    const domains: DomainFreshness[] = Object.entries(status.domains).map(([domain, d]) => ({ domain: domain as Domain, latestIssue: d.latest_issue, publishedOn: d.published_on, ageDays: d.age_days, stale: d.stale }));
    return { active: true, running: status.running, domains, lastCheck: last ? { at: utc(last.started_at), label: last.trigger === 'schedule' ? 'Scheduled' : 'Manual', status: last.status, errors: last.errors } : null, schedule: status.schedule ?? null, nextCheckInS: status.next_run_in_s ?? null, nextExpectedOn: null, note: null };
  },
  listFindings: async (issueId) => {
    const i = issueId.lastIndexOf('-');
    const domain = issueId.slice(0, i);
    const issue = Number(issueId.slice(i + 1));
    const [cases] = await Promise.all([allCases(), loadRuleNames()]);
    return rankFindings(cases.filter((c) => caseInIssue(c, domain, issue)).map((c) => mapSummary(c, issueId)));
  },
  getFinding: async (id) => {
    let c: CaseOut;
    try {
      [c] = await Promise.all([call<CaseOut>('screening', `/cases/${encodeURIComponent(id)}`), loadRuleNames()]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
    const match = (await call<ArtifactOut[]>('sync', '/issues?limit=500')).find((a) => a.sha256 === c.source_sha256);
    return mapCase(c, issueKey(c.domain, c.last_issue), match ? fileName(match.source_url) : 'Source file');
  },
  updateReview: async (id, change) => {
    if (change.letter !== undefined) saveLetter(id, change.letter); // no letter field in the API yet
    if (change.status) {
      await call<CaseOut>('screening', `/cases/${encodeURIComponent(id)}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ review_status: change.status, review_note: change.note || null }),
      });
    }
    const f = await httpApi.getFinding(id);
    if (!f) throw new ApiError('That case no longer exists.', 404);
    return f;
  },
  listRuns: async () => [],
  getRun: async (id) => {
    const artifactId = Number(id.replace(/^issue-/, ''));
    const row = (await call<ArtifactOut[]>('sync', '/issues?limit=500')).find((a) => a.id === artifactId);
    return row ? runFromArtifact(row) : null;
  },
  listSyncRuns: async () => (await call<SyncRunOut[]>('sync', '/runs?limit=50')).map((r) => ({ ...toSyncRun(r), startedAt: utc(r.started_at), finishedAt: r.finished_at ? utc(r.finished_at) : null })),
  findIssueByHash: async (sha) => (await httpApi.listIssues()).find((i) => i.file.zipSha256 === sha) ?? null,
  createRun: async (input, onProgress) => {
    const { artifact, new: isNew } = await uploadFile(input, onProgress);
    return runFromArtifact(artifact, isNew ? '' : 'This exact file was already stored, so nothing new was added. ');
  },
  checkItuNow: async () => { await call('sync', '/sync', { method: 'POST' }); },
  rescreen: async (issue) => { await call('screening', `/issues/${issue.artifactId}/screen`, { method: 'POST' }); },
  listRules: async () => (await call<RuleOut[]>('screening', '/rules')).map(ruleOf),
  getRule: async (id) => {
    try {
      return ruleOf(await call<RuleOut>('screening', `/rules/${id}`));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
  ruleOptions: async () => {
    const o = await call<{ m4_primary_services: string[]; title_fields: Record<string, string> }>('screening', '/rules/options');
    return { m4PrimaryServices: o.m4_primary_services, titleFields: o.title_fields };
  },
  saveRule: async (rule: RuleSave, id?: number) => {
    const body = JSON.stringify({ ...specIn(rule), enabled: rule.enabled, saved_by: rule.savedBy, note: rule.note });
    const out = await call<RuleOut>('screening', id === undefined ? '/rules' : `/rules/${id}`, { method: id === undefined ? 'POST' : 'PUT', headers: { 'Content-Type': 'application/json' }, body });
    return ruleOf(out);
  },
  previewRule: async (spec, artifactId) => {
    const out = await call<PreviewOut>('screening', '/rules/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ spec: specIn(spec), artifact_id: artifactId }) });
    return { issueNo: out.issue_no, total: out.total, byAdm: out.by_adm, hits: out.hits.map((h) => ({ network: h.network, adm: h.adm, title: h.title, severity: asSeverity(h.severity), noticeIds: h.notice_ids, bands: h.bands, assignments: h.assignments })) };
  },
  listCaseStations: async (id, q) => {
    const out = await call<{ total: number; matching: number; offset: number; rows: Record<string, unknown>[]; counts: { status: Record<string, number>; licence: Record<string, number> }; not_visible: number; issue_no: number; dataset_changed: boolean }>(
      'screening', `/cases/${encodeURIComponent(id)}/stations?${stationParams(q)}`);
    return { total: out.total, matching: out.matching, offset: out.offset, rows: mapStationRecords(out.rows), counts: out.counts, notVisible: out.not_visible, issueNo: out.issue_no, datasetChanged: out.dataset_changed };
  },
  caseStationsCsvUrl: (id, q) => `/api/screening/cases/${encodeURIComponent(id)}/stations.csv?${stationParams({ ...q, offset: undefined, limit: undefined })}`,
  getTrends: async (domain) => {
    type Out = { domain: Domain; issues: number[]; series: Trends['series']; rule: string; problems: string[]; assumptions: string[];
      flags: Record<string, { name: string; issue: number; count: number; earlier_average: number }[]>;
      totals?: Record<string, { filings: number; visible_from_finland: number }>;
      largest_ngso?: Record<string, { ntc_id: number; network: string | null; adm: string | null; satellites: number; reason: string | null }[]> };
    const o = await call<Out>('screening', `/trends?domain=${domain}`);
    const byIssue = <A, B>(m: Record<string, A> | undefined, f: (a: A) => B) => (m ? Object.fromEntries(Object.entries(m).map(([k, v]) => [Number(k), f(v)])) : undefined);
    return {
      domain: o.domain, issues: o.issues, rule: o.rule, problems: o.problems, assumptions: o.assumptions,
      series: Object.fromEntries(Object.entries(o.series).map(([dim, cats]) => [dim, Object.fromEntries(Object.entries(cats).map(([c, v]) => [c, byIssue(v, (n) => n)!]))])),
      flags: Object.fromEntries(Object.entries(o.flags).map(([dim, fs]) => [dim, fs.map((f) => ({ name: f.name, issue: f.issue, count: f.count, earlierAverage: f.earlier_average }))])),
      totals: byIssue(o.totals, (t) => ({ filings: t.filings, visibleFromFinland: t.visible_from_finland })),
      largestNgso: byIssue(o.largest_ngso, (list) => list.map((x) => ({ ntcId: x.ntc_id, network: x.network, adm: x.adm, satellites: x.satellites, reason: x.reason }))),
    };
  },
  getCoverage: async (id) => {
    type Out = { issue_no: number; mapped: boolean; boundary: number[][][]; cell: { lat_step: number; lon_step: number }; orbit: Coverage['orbit']; gso_lon_deg: number | null; satellites: string[];
      cells: { lat: number; lon: number; angle_deg: number | null; minutes: number | null; pfd_db: number | null; margin_db: number | null }[];
      pfd: { available: boolean; reason?: string; ref_bw_hz?: number; group_id?: number; f_low_mhz?: number; f_high_mhz?: number; power_in_ref_bw_dbw?: number; gain_dbi?: number; mask_id?: string | null };
      stations: { total: number; segments?: { low_mhz: number; high_mhz: number }[]; without_location: number; by_class: Record<string, number>; points?: { id: string; lat: number; lon: number; licence: string | null }[]; bins?: { lat: number; lon: number; count: number }[] };
      notes: string[]; assumptions: string[] };
    const o = await call<Out>('screening', `/cases/${encodeURIComponent(id)}/coverage`);
    return {
      issueNo: o.issue_no, mapped: o.mapped, boundary: o.boundary, cell: { latStep: o.cell.lat_step, lonStep: o.cell.lon_step }, orbit: o.orbit, gsoLonDeg: o.gso_lon_deg, satellites: o.satellites,
      cells: o.cells.map((c) => ({ lat: c.lat, lon: c.lon, angleDeg: c.angle_deg, minutes: c.minutes, pfdDb: c.pfd_db, marginDb: c.margin_db })),
      pfd: { available: o.pfd.available, reason: o.pfd.reason, refBwHz: o.pfd.ref_bw_hz, groupId: o.pfd.group_id, fLowMhz: o.pfd.f_low_mhz, fHighMhz: o.pfd.f_high_mhz, powerInRefBwDbw: o.pfd.power_in_ref_bw_dbw, gainDbi: o.pfd.gain_dbi, maskId: o.pfd.mask_id },
      stations: { total: o.stations.total, segments: o.stations.segments?.map((g) => ({ lowMhz: g.low_mhz, highMhz: g.high_mhz })), withoutLocation: o.stations.without_location, byClass: o.stations.by_class, points: o.stations.points, bins: o.stations.bins },
      notes: o.notes, assumptions: o.assumptions,
    };
  },
  rescreenSpace: async () => (await call<{ issues: number[] }>('screening', '/rules/rescreen', { method: 'POST' })).issues,
  listReferenceSources: async () => SOURCES,
  listLimits: async () => [],
};
