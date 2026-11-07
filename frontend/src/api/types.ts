// The contract between this UI and the backend. Units are in field names,
// matching schema.sql. See frontend/README.md for the HTTP endpoints.

export type Domain = 'space' | 'terrestrial';
export type Severity = 'high' | 'medium' | 'low' | 'unscored';
export type Confidence = 'medium' | 'low' | 'not_calculated';
export type ReviewStatus = 'pending' | 'accepted' | 'rejected' | 'needs_info';
export type FindingKind = 'pfd_screen' | 'br_listed' | 'near_border';
export type RunTrigger = 'scheduled' | 'on_demand' | 'sample';
export type RunStatus = 'running' | 'succeeded' | 'failed' | 'simulated';

export interface SourceFile {
  zip: string;
  zipSha256: string;
  mdb: string;
  mdbSha256: string;
}

export interface FunnelStage {
  key: string;
  label: string;
  n: number;
}

export interface IssueSummary {
  id: string; // e.g. "space-3083"
  domain: Domain;
  issue: number;
  releasedOn: string;
  commentDeadline: string | null;
  file: SourceFile;
  evaluationIssue: boolean; // named in the Traficom brief
  counts: { label: string; value: number }[];
  funnel: FunnelStage[];
  severityCounts: Record<Severity, number>;
  brListedNetworks: number;
  limitations: string[];
}

export interface PfdCalculation {
  groupId: number;
  beam: string;
  fMinMhz: number;
  fMaxMhz: number;
  emission: string;
  gainDbi: number;
  powerDensityDbwHz: number;
  peakPowerDbw: number | null;
  refBandwidthHz: number;
  distanceKm: number;
  angleDeg: number;
  pfd: number;
  limit: number;
  marginDb: number;
  altitudeKm: number | null;
  inclinationDeg: number | null;
  lat: number | null;
  lon: number | null;
}

export interface StationRef {
  id: number;
  rxMhz: number;
  licence: string | null;
  lat: number;
  lon: number;
}

export interface TerrestrialDetail {
  terrakey: number;
  stationClass: string;
  fMhz: number;
  bandwidthKhz: number | null;
  intent: string;
  noticeType: string;
  site: string;
  lat: number;
  lon: number;
  borderKm: number;
  powerDbw: number | null;
  powerType: string | null;
  gainDbi: number | null;
  heightM: number | null;
}

export interface Finding {
  id: string;
  issueId: string;
  domain: Domain;
  issue: number;
  kind: FindingKind;
  title: string;
  adm: string;
  orbit: string | null;
  band: string;
  sourceId: number;
  relatedSourceIds: number[];
  provision: string | null;
  sections: string[];
  coordProvisions: string[];
  severity: Severity;
  severityReasons: string[];
  confidence: Confidence;
  confidenceReasons: string[];
  marginDb: number | null;
  stationCount: number;
  stations: StationRef[];
  calc: PfdCalculation | null;
  terrestrial: TerrestrialDetail | null;
  windowDeadline: string | null;
  assumptions: string[];
  citations: string[];
  evidence: { table: string; key: string }[];
  file: SourceFile;
  review: ReviewState;
}

export interface ReviewEvent {
  at: string;
  action: string;
  note: string;
}

export interface ReviewState {
  status: ReviewStatus;
  note: string;
  letter: string | null;
  history: ReviewEvent[];
}

export interface Run {
  id: string;
  trigger: RunTrigger;
  domain: Domain;
  issue: number | null;
  fileName: string;
  sha256: string;
  sizeBytes: number | null;
  startedAt: string;
  status: RunStatus;
  stageIndex: number;
  issueId: string | null;
  message: string;
}

export interface MonitorStatus {
  connected: boolean;
  latestKnownIssue: number;
  latestKnownDate: string;
  checkedOn: string;
  nextExpectedOn: string;
  note: string;
}

export interface ReferenceSource {
  name: string;
  version: string;
  detail: string;
  url: string | null;
  status: 'loaded' | 'partial' | 'planned';
}

export interface LimitRow {
  citation: string;
  refBandwidth: string;
  rule: string;
}

export interface NewRun {
  file: File;
  sha256: string;
  domain: Domain;
  issue: number | null;
}

/** Anything implementing this can drive the UI: the mock now, HTTP later. */
export interface Api {
  mode: 'sample' | 'live';
  listIssues(): Promise<IssueSummary[]>;
  getMonitor(): Promise<MonitorStatus>;
  listFindings(issueId: string): Promise<Finding[]>;
  getFinding(id: string): Promise<Finding | null>;
  updateReview(id: string, change: { status?: ReviewStatus; note?: string; letter?: string }): Promise<Finding>;
  listRuns(): Promise<Run[]>;
  getRun(id: string): Promise<Run | null>;
  findIssueByHash(sha256: string): Promise<IssueSummary | null>;
  createRun(input: NewRun): Promise<Run>;
  listReferenceSources(): Promise<ReferenceSource[]>;
  listLimits(): Promise<LimitRow[]>;
}

export const PIPELINE_STAGES = [
  'Upload and fingerprint file',
  'Read database tables',
  'Normalise to shared schema',
  'Filter for Finnish relevance',
  'Run calculations',
  'Rank findings',
  'Prepare drafts for review',
] as const;
