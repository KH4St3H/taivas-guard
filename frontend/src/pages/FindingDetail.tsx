import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Finding, ReviewStatus, StationPage, StationResult } from '../api/types';
import { CommentWindow, ConfidenceText, Hash, Loading, ReviewBadge, SeverityBadge, useLoad } from '../components/ui';
import { admName } from '../lib/adm';
import { exportText } from '../lib/export';
import { db, formatDateTime, m4Services, refBandwidth, signed } from '../lib/format';
import { draftLetter } from '../lib/letter';
import { pfdSteps } from '../lib/pfd';

export function FindingDetail() {
  const { id = '' } = useParams();
  const { data, error, loading } = useLoad(() => api.getFinding(id), [id]);
  const [finding, setFinding] = useState<Finding | null>(null);
  useEffect(() => {
    setFinding(data ?? null);
  }, [data]);

  if (loading && !finding) return <Loading />;
  if (error) return <Loading error={error} />;
  if (!finding) return <div className="empty"><h1>Finding not found</h1><Link to="/findings">Back to findings</Link></div>;
  const f = finding;
  const issues = f.firstIssue === f.lastIssue ? `IFIC ${f.lastIssue}` : `IFIC ${f.firstIssue}–${f.lastIssue}`;
  const unconfirmed = !f.calc && !f.result && !f.terrestrial;

  return (
    <>
      <p className="crumb"><Link to={`/findings?issue=${f.issueId}`}>Findings, IFIC {f.issue}</Link> / {f.title}</p>
      <div className="page-head">
        <div>
          <h1>{f.title}</h1>
          <p className="lead">{admName(f.adm)}{f.orbit ? ` · ${f.orbit}` : ''}{f.band ? ` · ${f.band}` : ''}{f.sections.length ? ` · ${f.sections.join(', ')}` : ''} · {issues}</p>
        </div>
        <ReviewBadge value={f.review.status} />
      </div>

      <div className="detail">
        <div className="detail-main">
          <section className="panel">
            <h2>Why it was flagged</h2>
            <dl className={f.confidence ? 'assess' : 'assess assess-one'}>
              <div><dt>Severity</dt><dd><SeverityBadge value={f.severity} /><ul>{f.severityReasons.map((r) => <li key={r}>{r}</li>)}</ul></dd></div>
              {f.confidence && <div><dt>Confidence</dt><dd><strong><ConfidenceText value={f.confidence} /></strong><ul>{f.confidenceReasons.map((r) => <li key={r}>{r}</li>)}</ul></dd></div>}
            </dl>
            {f.basis && <p className="muted">{f.basis}</p>}
            {f.coordProvisions.length > 0 && <p>Provisions: <strong>{f.coordProvisions.join(', ')}</strong>. ITU’s list is for information only (RR No. 9.36.1), so an expert still decides.</p>}
            {f.visibility.length > 0 && <p className="muted">Visibility: {f.visibility.join('; ')}</p>}
            {unconfirmed && <p className="notice notice-warn"><strong>Possible concern.</strong> No calculation backs this case, so it doesn’t show that any limit is exceeded.</p>}
            <p className="fine">{f.customRule ? <>Severity is set by the rule an expert wrote, under <Link to="/rules">Screening rules</Link>.</> : <>Severity follows fixed rules listed under <Link to="/reference">Rules and data</Link>.</>} No AI was involved in this assessment.</p>
          </section>

          {f.customRule && <CustomRulePanel f={f} />}
          {f.bands.length > 0 && <BandsPanel f={f} />}
          {(f.stationResults?.length ?? 0) > 0 ? <StationResultsPanel f={f} /> : f.stationIds.length > 0 && <StationIdsPanel f={f} />}
          {f.calc && <Calculation f={f} />}
          {f.result && <ResultPanel f={f} />}
          {f.terrestrial && <TerrestrialPanel f={f} />}

          {f.assumptions.length > 0 && (
            <section className="panel">
              <h2>Assumptions</h2>
              <ul>{f.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
            </section>
          )}

          {f.stations.length > 0 && (
            <section className="panel">
              <h2>Finnish receivers in this band</h2>
              <p className="muted">Showing {f.stations.length} of {f.stationCount} from Traficom’s synthetic list. Overlap covers the group’s whole frequency range, and doesn’t yet consider location or antenna direction.</p>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Station</th><th className="num">Receive, MHz</th><th>Licence class</th><th className="num">Lat</th><th className="num">Lon</th></tr></thead>
                  <tbody>{f.stations.map((s) => <tr key={`${s.id}-${s.rxMhz}`}><td className="tnum">{s.id}</td><td className="num">{s.rxMhz}</td><td>{s.licence ?? 'Not stated'}</td><td className="num">{s.lat.toFixed(3)}</td><td className="num">{s.lon.toFixed(3)}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}

          <Letter f={f} onChange={setFinding} />
        </div>

        <aside className="detail-side">
          <Review f={f} onChange={setFinding} />
          <section className="panel">
            <h2>Comment window</h2>
            <p><CommentWindow deadline={f.windowDeadline} /></p>
            <p className="fine">{f.windowDeadline ? 'An estimate: publication date plus four months. Confirm it against the Special Section.' : f.domain === 'terrestrial' ? 'Not determined for terrestrial notices yet.' : 'No window was identified for this case.'}</p>
            {f.sections.includes('API/A') && <p className="fine">RR No. 9.3 names interference to satellite networks, not terrestrial stations. Check how Traficom would raise a terrestrial concern on an API/A filing.</p>}
          </section>
          <section className="panel">
            <h2>Evidence</h2>
            <dl className="plain stacked">
              <div><dt>Source file</dt><dd className="wrap">{f.file.zip}</dd></div>
              <div><dt>SHA-256</dt><dd><Hash value={f.file.zipSha256} /></dd></div>
              <div><dt>Notice ID</dt><dd className="tnum">{f.sourceId}{f.relatedSourceIds.length > 0 && <span className="muted block">Also: {f.relatedSourceIds.join(', ')}</span>}</dd></div>
              {f.updatedAt && <div><dt>Last updated</dt><dd>{formatDateTime(/[zZ]$/.test(f.updatedAt) ? f.updatedAt : `${f.updatedAt}Z`)}</dd></div>}
            </dl>
            {f.evidence.length > 0 && (
              <>
                <h3>Source rows</h3>
                <ul className="evidence">{f.evidence.map((e) => <li key={e.table + e.key}><code>{e.table}</code> <span className="wrap">{e.key}</span></li>)}</ul>
              </>
            )}
            {f.citations.length > 0 && (
              <>
                <h3>Citations</h3>
                <ul className="evidence">{f.citations.map((c) => <li key={c}>{c}</li>)}</ul>
              </>
            )}
          </section>
          {f.review.history.length > 0 && (
            <section className="panel">
              <h2>Review history</h2>
              <ul className="history">{f.review.history.map((h, i) => <li key={`${h.at}-${i}`}><strong>{h.action}</strong><span className="muted block">{formatDateTime(h.at)}</span>{h.note && <span className="block">{h.note}</span>}</li>)}</ul>
              <p className="fine">Saved in this browser only while in sample mode.</p>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}

const SHOW_IDS = 30;

/** Station IDs arrive as number@Rrow, or number@SsheetRrow beyond the first sheet of Traficom's register. */
const stationLabel = (id: string) => id.replace(/@S(\d+)R(\d+)$/, ' (sheet $1, row $2)').replace(/@R(\d+)$/, ' (row $1)');
const classSummary = (classes: Record<string, number>) => Object.entries(classes).map(([name, n]) => `${name}: ${n}`).join(', ');

const SHOW_BANDS = 12;
const SHOW_ASSIGNMENTS = 12;

function CustomRulePanel({ f }: { f: Finding }) {
  const r = f.customRule!;
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? r.matchedAssignments : r.matchedAssignments.slice(0, SHOW_ASSIGNMENTS);
  return (
    <section className="panel">
      <h2>Rule that raised it</h2>
      <p><Link to={`/rules/${r.id}`}><strong>{r.name}</strong></Link>, version {r.version}. Written by an expert, not taken from a regulation. It matched because:</p>
      <ul className="conditions">{r.conditions.map((c) => <li key={c}>{c}.</li>)}</ul>
      <h3>Matched assignments</h3>
      <div className="table-wrap">
        <table>
          <thead><tr><th className="num">Group</th><th className="num">From, MHz</th><th className="num">To, MHz</th><th>Satellite</th></tr></thead>
          <tbody>{shown.map((a, i) => <tr key={`${a.groupId}-${a.fMinMhz}-${i}`}><td className="num">{a.groupId}</td><td className="num">{a.fMinMhz}</td><td className="num">{a.fMaxMhz}</td><td>{a.direction === 'receive' ? 'Receives' : 'Transmits'}</td></tr>)}</tbody>
        </table>
      </div>
      {r.matchedAssignments.length > SHOW_ASSIGNMENTS && <button type="button" className="linkbtn show-all" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer' : `Show all ${r.matchedAssignments.length}`}</button>}
      {r.matchedCount > r.matchedAssignments.length && <p className="fine">{r.matchedCount} assignments matched; the case keeps the first {r.matchedAssignments.length}.</p>}
    </section>
  );
}

function BandsPanel({ f }: { f: Finding }) {
  const stationRule = f.kind === 'station-rx-overlap';
  const [showAll, setShowAll] = useState(false);
  // Same `m4` parameter as the Findings list, so a filtered list opens its cases already filtered.
  const [params, setParams] = useSearchParams();
  const m4 = params.get('m4') ?? '';
  const services = [...new Set(f.bands.flatMap((b) => m4Services(b.primaryServices)))].sort();
  const matching = m4 && services.includes(m4) ? f.bands.filter((b) => m4Services(b.primaryServices).includes(m4)) : f.bands;
  const bands = showAll ? matching : matching.slice(0, SHOW_BANDS);
  const setM4 = (value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set('m4', value); else next.delete('m4');
    setParams(next, { replace: true });
  };
  return (
    <section className="panel">
      <h2>Bands involved</h2>
      <p className="muted">{f.customRule ? 'Bands of the Finnish table (M4) where the matched frequencies fall.' : stationRule ? 'Bands where this filing transmits on an RX or TX frequency of a station in Traficom’s list, with what M4 allocates there. Results at each station are in the next panel.' : 'Bands where this filing transmits and M4 has no space-to-Earth allocation.'}</p>
      {services.length > 1 && (
        <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter bands">
          <label>M4 primary service
            <select value={services.includes(m4) ? m4 : ''} onChange={(e) => setM4(e.target.value)}>
              <option value="">All</option>
              {services.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          {matching !== f.bands && <p className="result-count" role="status">{matching.length} of {f.bands.length} bands · <button type="button" className="linkbtn" onClick={() => setM4('')}>Show all bands</button></p>}
        </form>
      )}
      <div className="table-wrap">
        <table>
          {stationRule ? (
            <>
              <thead><tr><th>Band, MHz</th><th className="num">Stations</th><th>Licence classes</th><th>M4 primary services</th><th>M4 space-to-Earth</th><th className="num">Groups</th></tr></thead>
              <tbody>
                {bands.map((b) => (
                  <tr key={`${b.lowMhz}-${b.highMhz}`}>
                    <td className="nowrap tnum">{b.lowMhz}–{b.highMhz}{b.passive && <span className="badge sev-high passive">Passive</span>}</td><td className="num">{b.stationCount}</td><td>{classSummary(b.classes) || '–'}</td>
                    <td>{b.primaryServices || '–'}</td><td>{b.m4SpaceToEarth ?? '–'}</td><td className="num">{b.groupCount}</td>
                  </tr>
                ))}
              </tbody>
            </>
          ) : (
            <>
              <thead><tr><th>Band, MHz</th><th>Finnish use</th><th>M4 primary services</th><th>M4 table page</th><th className="num">Groups</th></tr></thead>
              <tbody>
                {bands.map((b) => (
                  <tr key={`${b.lowMhz}-${b.highMhz}`}>
                    <td className="nowrap tnum">{b.lowMhz}–{b.highMhz}{b.passive && <span className="badge sev-high passive">Passive</span>}</td>
                    <td>{b.finnishUse || '–'}</td><td>{b.primaryServices || '–'}</td><td>{b.pages || '–'}</td><td className="num">{b.groupCount}</td>
                  </tr>
                ))}
              </tbody>
            </>
          )}
        </table>
      </div>
      {matching.length > SHOW_BANDS && <button type="button" className="linkbtn show-all" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer' : `Show all ${matching.length} bands`}</button>}
    </section>
  );
}

function StationIdsPanel({ f }: { f: Finding }) {
  const shown = f.stationIds.slice(0, SHOW_IDS);
  const total = f.stationCount ?? f.stationIds.length;
  return (
    <section className="panel">
      <h2>Finnish stations affected</h2>
      <p className="muted">{total} in Traficom’s synthetic list{classSummary(f.stationClasses) ? ` (${classSummary(f.stationClasses)})` : ''}.{total > shown.length ? ` Showing ${shown.length}.` : ''}</p>
      <ul className="id-list">{shown.map((id) => <li key={id}><code>{stationLabel(id)}</code></li>)}</ul>
      <AllStations f={f} />
    </section>
  );
}

const PAGE = 100;

/** The full list, recomputed by the service on request: a case keeps only its worst stations. */
function AllStations({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState<{ offset: number; status: string; licence: string }>({ offset: 0, status: '', licence: '' });
  const [state, setState] = useState<{ loading: boolean; page?: StationPage; error?: string }>({ loading: false });
  useEffect(() => {
    if (!open) return;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    api.listCaseStations(f.id, { ...query, limit: PAGE }).then(
      (page) => live && setState({ loading: false, page }),
      (e: Error) => live && setState({ loading: false, error: e.message }),
    );
    return () => { live = false; };
  }, [open, query, f.id]);
  if (!api.capabilities.stationLists) return null;
  const csv = api.caseStationsCsvUrl(f.id, { status: query.status, licence: query.licence });
  const total = f.stationCount ?? 0;
  if (!open) {
    return (
      <div className="actions">
        <button type="button" className="btn btn-secondary" onClick={() => setOpen(true)}>Browse all {total.toLocaleString('en-GB')} stations</button>
        {csv && <a className="btn btn-secondary" href={csv} download>Download all as CSV</a>}
        <span className="fine">Recomputed from the issue file when asked. On a large register the first request can take minutes.</span>
      </div>
    );
  }
  const page = state.page;
  const set = (change: Partial<typeof query>) => setQuery({ ...query, offset: 0, ...change });
  return (
    <div className="all-stations">
      <h3>All stations</h3>
      {page && (
        <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter stations">
          <label>Result
            <select value={query.status} onChange={(e) => set({ status: e.target.value })}>
              <option value="">All</option>
              {Object.entries(page.counts.status).map(([s, n]) => <option key={s} value={s}>{STATUS_TEXT[s] ?? s} ({n.toLocaleString('en-GB')})</option>)}
            </select>
          </label>
          <label>Licence class
            <select value={query.licence} onChange={(e) => set({ licence: e.target.value })}>
              <option value="">All</option>
              {Object.entries(page.counts.licence).map(([s, n]) => <option key={s} value={s}>{s} ({n.toLocaleString('en-GB')})</option>)}
            </select>
          </label>
          {csv && <a className="btn btn-secondary" href={csv} download>Download {query.status || query.licence ? 'these' : 'all'} as CSV</a>}
        </form>
      )}
      {state.loading && <p className="muted" role="status">{page ? 'Loading…' : 'Recomputing the station list from the issue file. On a large register this can take minutes.'}</p>}
      {state.error && <p className="alert" role="alert">{state.error}</p>}
      {page && page.datasetChanged && <p className="notice notice-warn">The station register has changed since this case was screened, so this list is from the current register and may not match the case.</p>}
      {page && (
        <>
          <StationTable rows={page.rows} />
          <div className="actions">
            <span className="result-count" role="status">{page.matching === 0 ? 'No stations match' : `${(page.offset + 1).toLocaleString('en-GB')}–${Math.min(page.offset + PAGE, page.matching).toLocaleString('en-GB')} of ${page.matching.toLocaleString('en-GB')}`}{page.notVisible > 0 ? ` · ${page.notVisible.toLocaleString('en-GB')} more below the satellite’s horizon` : ''}</span>
            <button type="button" className="btn btn-secondary" disabled={state.loading || page.offset === 0} onClick={() => setQuery({ ...query, offset: Math.max(0, page.offset - PAGE) })}>Previous</button>
            <button type="button" className="btn btn-secondary" disabled={state.loading || page.offset + PAGE >= page.matching} onClick={() => setQuery({ ...query, offset: page.offset + PAGE })}>Next</button>
          </div>
        </>
      )}
    </div>
  );
}

function StationTable({ rows }: { rows: StationResult[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Station</th><th>Side</th><th>Result</th><th className="num">Value, dB</th><th className="num">Limit, dB</th><th className="num">Margin, dB</th><th className="num">Angle</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="tnum">{stationLabel(r.id)}{r.licence && <span className="muted block">{r.licence}</span>}</td>
              <td>{r.sides.join(', ').toUpperCase() || '–'}{r.atSiteOnly && <span className="muted block">At the site, not the receiver</span>}</td>
              <td>{STATUS_TEXT[r.status] ?? r.status}{r.locationFlagged && <span className="muted block">Location flagged in the sheet</span>}</td>
              <td className="num">{dbOr(r.valueDb)}</td><td className="num">{dbOr(r.limitDb)}</td><td className="num"><strong>{r.marginDb === null ? '–' : db(r.marginDb)}</strong></td>
              <td className="num">{r.angleDeg === null ? '–' : `${r.angleDeg.toFixed(1)}°`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const STATUS_TEXT: Record<string, string> = {
  exceeds: 'Above the limit', exceeds_flagged: 'Above, but input or location flagged', within_3db: 'Within 3 dB below',
  bound_above: 'Only the filing’s upper bound is near or above', no_calculation: 'Not calculated', below: 'Below the limit',
  bound_below: 'Filing’s upper bound below', not_visible: 'Below this station’s horizon', calculated: 'Calculated',
};
const SHOW_STATIONS = 30;
const dbOr = (v: number | null) => (v === null ? '–' : signed(v));

function StationResultsPanel({ f }: { f: Finding }) {
  const results = f.stationResults ?? [];
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? results : results.slice(0, SHOW_STATIONS);
  const atSite = results.some((r) => r.atSiteOnly);
  const total = f.stationCount ?? results.length;
  const counts = f.stationStatusCounts ? Object.entries(f.stationStatusCounts).filter(([s]) => s !== 'not_visible').map(([s, n]) => `${STATUS_TEXT[s] ?? s} ${n.toLocaleString('en-GB')}`).join(', ') : '';
  return (
    <section className="panel">
      <h2>Finnish stations affected</h2>
      <p className="muted">{total.toLocaleString('en-GB')} in Traficom’s synthetic list{classSummary(f.stationClasses) ? ` (${classSummary(f.stationClasses)})` : ''}{total > results.length ? `. This case keeps the worst ${results.length}` : ', worst first'}{counts ? `. By result: ${counts}` : ''}. A value is calculated at the station’s coordinates under worst-case assumptions. An upper bound applies to the filing, so it is never shown as a value at a station.</p>
      <StationTable rows={shown} />
      {atSite && <p className="fine">For a TX match, the station’s coordinates are not where that band is received, so its margin is at the site, not at the receiver.</p>}
      {results.length > SHOW_STATIONS && <button type="button" className="linkbtn show-all" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show fewer' : `Show the worst ${results.length}`}</button>}
      <AllStations f={f} />
    </section>
  );
}

function ResultPanel({ f }: { f: Finding }) {
  const r = f.result!;
  return (
    <section className="panel">
      <h2>Calculation</h2>
      <dl className="plain">
        <div><dt>Method</dt><dd>{r.method}</dd></div>
        {Object.entries(r.inputs).filter(([k]) => k !== 'group').map(([k, v]) => <div key={k}><dt>{k}</dt><dd className="wrap">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>)}
        {r.valueDb !== null && <div><dt>Calculated value</dt><dd>{signed(r.valueDb)} dB</dd></div>}
        {r.limitDb !== null && <div><dt>Limit</dt><dd>{signed(r.limitDb)} dB{r.maskId ? ` (${r.maskId})` : ''}</dd></div>}
        {r.marginDb !== null && <div><dt>Margin</dt><dd><strong>{db(r.marginDb)} dB</strong></dd></div>}
        {r.worstPoint && <div><dt>Worst point</dt><dd className="wrap">{Object.entries(r.worstPoint).map(([k, v]) => `${k} ${String(v)}`).join(', ')}</dd></div>}
      </dl>
    </section>
  );
}

function Calculation({ f }: { f: Finding }) {
  const c = f.calc!;
  const s = pfdSteps(c);
  const over = c.marginDb > 0;
  return (
    <section className="panel">
      <h2>Calculation</h2>
      <p className="formula">pfd = power in {refBandwidth(c.refBandwidthHz)} + antenna gain − 10·log₁₀(4π·d²)</p>
      <div className="table-wrap">
        <table className="calc">
          <tbody>
            <tr><th scope="row">Power density <span className="muted">emiss.pwr_ds_max</span></th><td className="num">{signed(c.powerDensityDbwHz)} dBW/Hz</td></tr>
            <tr><th scope="row">Power in {refBandwidth(c.refBandwidthHz)}{s.cappedByPeak && <span className="muted block">Capped at the filed peak power of {signed(c.peakPowerDbw!)} dBW, as the signal is narrower</span>}</th><td className="num">{signed(s.power)} dBW</td></tr>
            <tr><th scope="row">Antenna gain, beam {c.beam} <span className="muted">s_beam.gain, peak</span></th><td className="num">{db(c.gainDbi)} dB</td></tr>
            <tr><th scope="row">Spreading over {c.distanceKm.toLocaleString('en-GB')} km</th><td className="num">−{s.spreading.toFixed(1)} dB</td></tr>
            <tr className="calc-total"><th scope="row">Power flux density</th><td className="num">{signed(c.pfd)} dB(W/m²)</td></tr>
            <tr><th scope="row">Limit at {c.angleDeg}° arrival angle <span className="muted block">{f.citations[0]}</span></th><td className="num">{signed(c.limit)} dB(W/m²)</td></tr>
            <tr className="calc-total"><th scope="row">{over ? 'Above the limit by' : 'Below the limit by'}</th><td className="num">{Math.abs(c.marginDb).toFixed(1)} dB</td></tr>
          </tbody>
        </table>
      </div>
      <dl className="inline-counts">
        <div><dt>Frequency</dt><dd>{c.fMinMhz}–{c.fMaxMhz} MHz</dd></div>
        <div><dt>Emission</dt><dd>{c.emission}</dd></div>
        {c.altitudeKm !== null && <div><dt>Altitude used</dt><dd>{c.altitudeKm.toLocaleString('en-GB')} km</dd></div>}
        {c.inclinationDeg !== null && <div><dt>Inclination</dt><dd>{c.inclinationDeg.toFixed(1)}°</dd></div>}
        {c.lat !== null && <div><dt>Worst point</dt><dd>{c.lat}°N, {c.lon}°E</dd></div>}
      </dl>
    </section>
  );
}

function TerrestrialPanel({ f }: { f: Finding }) {
  const t = f.terrestrial!;
  const type: Record<string, string> = { E: 'E (as notified)', I: 'I (as notified)', V: 'V (as notified)' };
  return (
    <section className="panel">
      <h2>Station</h2>
      <dl className="plain">
        <div><dt>Frequency</dt><dd>{t.fMhz} MHz{t.bandwidthKhz ? `, ${t.bandwidthKhz} kHz` : ''}</dd></div>
        <div><dt>Change in this issue</dt><dd>{t.intent}</dd></div>
        <div><dt>Station class</dt><dd>{t.stationClass}</dd></div>
        <div><dt>Location</dt><dd>{t.lat.toFixed(3)}°N, {t.lon.toFixed(3)}°E</dd></div>
        <div><dt>Distance to Finland</dt><dd>About {t.borderKm} km (rough border)</dd></div>
        <div><dt>Notified power</dt><dd>{t.powerDbw === null ? 'Not available' : `${t.powerDbw} dBW, type ${t.powerType ? type[t.powerType] ?? t.powerType : 'unknown'}`}</dd></div>
        <div><dt>Antenna height</dt><dd>{t.heightM === null ? 'Not available' : `${t.heightM} m`}</dd></div>
      </dl>
      <p className="notice notice-warn"><strong>Not calculated yet.</strong> The P.1546 field strength hasn’t been run, so there’s nothing to compare with a coordination threshold.</p>
    </section>
  );
}

function Letter({ f, onChange }: { f: Finding; onChange: (f: Finding) => void }) {
  const template = draftLetter(f);
  const [text, setText] = useState(f.review.letter ?? template);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setText(f.review.letter ?? template);
  }, [f.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = text !== (f.review.letter ?? template);

  async function save() {
    setError(null);
    try {
      onChange(await api.updateReview(f.id, { letter: text }));
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Draft letter</h2>
        <span className="muted">Filled from a fixed template, no AI yet</span>
      </div>
      <label className="visually-hidden" htmlFor="letter">Draft letter text</label>
      <textarea id="letter" className="letter" rows={18} value={text} onChange={(e) => { setText(e.target.value); setSaved(false); }} />
      <div className="actions">
        <button type="button" className="btn btn-secondary" disabled={!dirty} onClick={() => void save()}>Save edits</button>
        <button type="button" className="btn btn-secondary" onClick={() => exportText(`draft-${f.sourceId || f.id}.txt`, text)}>Download</button>
        {saved && <span className="muted" role="status">Saved</span>}
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <p className="fine">{api.capabilities.letterStorage === 'browser' ? 'Edits are saved in this browser only. ' : ''}IFIC Guard never sends letters. An expert reviews each one and sends it through Traficom’s own channel.</p>
    </section>
  );
}

const ACTION: Record<ReviewStatus, string> = { accepted: 'Accept', needs_info: 'Needs info', rejected: 'Reject', pending: 'Back to review' };

function Review({ f, onChange }: { f: Finding; onChange: (f: Finding) => void }) {
  const [note, setNote] = useState(f.review.note);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(status: ReviewStatus) {
    setBusy(true);
    setError(null);
    try {
      onChange(await api.updateReview(f.id, { status, note }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const statuses = api.capabilities.reviewStatuses.filter((s) => s !== 'pending' || f.review.status !== 'pending');
  return (
    <section className="panel">
      <h2>Your review</h2>
      <label className="field-label" htmlFor="note">Note <span className="muted">(recommended for a rejection)</span></label>
      <textarea id="note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why did you decide this?" />
      <div className="review-actions">
        {statuses.map((s) => (
          <button key={s} type="button" disabled={busy} className={s === 'accepted' ? 'btn btn-primary' : 'btn btn-secondary'} aria-pressed={f.review.status === s} onClick={() => void decide(s)}>{ACTION[s]}</button>
        ))}
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <p className="fine">Accepting means this is worth acting on. It sends nothing.{api.mode === 'live' ? ' If the filing changes in a later issue, the case returns to review.' : ''}</p>
    </section>
  );
}
