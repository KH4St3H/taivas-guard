import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Finding, ReviewStatus, Severity } from '../api/types';
import { CommentWindow, Loading, reviewLabel, ReviewBadge, SeverityBadge, useLoad } from '../components/ui';
import { exportFindings } from '../lib/export';
import { dateOr, db } from '../lib/format';

export function Findings() {
  const [params, setParams] = useSearchParams();
  const { data: issues, error } = useLoad(() => api.listIssues(), []);
  const newest = issues && [...issues].sort((a, b) => b.issue - a.issue || a.domain.localeCompare(b.domain))[0]?.id;
  const issueId = params.get('issue') ?? newest ?? '';
  const { data: rows, error: rowsError } = useLoad(() => (issueId ? api.listFindings(issueId) : Promise.resolve([])), [issueId]);
  const [exporting, setExporting] = useState<string | null>(null);

  const q = params.get('q') ?? '';
  const severity = params.get('severity') ?? '';
  const review = params.get('review') ?? '';
  const kind = params.get('kind') ?? '';
  const adm = params.get('adm') ?? '';
  const stations = params.get('stations') === '1';
  const m4 = params.get('m4') ?? '';

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };

  const filtered = useMemo(() => (rows ?? []).filter((f) =>
    (!severity || f.severity === severity) && (!review || f.review.status === review) && (!kind || f.kind === kind) && (!adm || f.adm === adm)
    && (!stations || (f.stationCount ?? 0) > 0) && (!m4 || f.m4PrimaryServices.includes(m4)) && (!q || `${f.title} ${f.summary ?? ''} ${f.adm} ${f.band ?? ''} ${f.sourceId}`.toLowerCase().includes(q.toLowerCase())),
  ), [rows, severity, review, kind, adm, stations, m4, q]);

  if (!issues) return <Loading error={error} />;
  const issue = issues.find((i) => i.id === issueId);
  const admins = [...new Set((rows ?? []).map((f) => f.adm))].sort();
  const m4Services = [...new Set((rows ?? []).flatMap((f) => f.m4PrimaryServices))].sort();
  const kinds = [...new Map((rows ?? []).map((f) => [f.kind, f.kindLabel])).entries()];
  const hasStations = (rows ?? []).some((f) => f.stationCount !== null);
  const filtersOn = q || severity || review || kind || adm || stations || m4;

  async function runExport(format: 'csv' | 'json') {
    setExporting(null);
    try {
      // List rows carry no details, so fetch each case before writing the file.
      const full = await Promise.all(filtered.map((f) => api.getFinding(f.id)));
      exportFindings(issueId, full.filter((f): f is Finding => !!f), format);
    } catch (e) {
      setExporting((e as Error).message);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Findings</h1>
          {issue && <p className="lead">{issue.domain === 'space' ? 'Space' : 'Terrestrial'} IFIC {issue.issue}, released {dateOr(issue.releasedOn, 'on a date not recorded')}. Ranked by severity, then nearest deadline.</p>}
        </div>
        <div className="actions">
          <button type="button" className="btn btn-secondary" disabled={!filtered.length} onClick={() => void runExport('csv')}>Export CSV</button>
          <button type="button" className="btn btn-secondary" disabled={!filtered.length} onClick={() => void runExport('json')}>Export JSON</button>
        </div>
      </div>
      {exporting && <p className="alert" role="alert">{exporting}</p>}

      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter findings">
        <label>Issue
          <select value={issueId} onChange={(e) => { setParams({ issue: e.target.value }, { replace: true }); }}>
            {issues.map((i) => <option key={i.id} value={i.id}>{i.issue} {i.domain === 'space' ? 'Space' : 'Terrestrial'}</option>)}
          </select>
        </label>
        <label>Search
          <input type="search" value={q} placeholder="Network, site, band or ID" onChange={(e) => set('q', e.target.value)} />
        </label>
        <label>Severity
          <select value={severity} onChange={(e) => set('severity', e.target.value)}>
            <option value="">All</option>
            {(['high', 'medium', 'low', 'unscored'] as Severity[]).map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
        </label>
        {kinds.length > 1 && (
          <label>Reason
            <select value={kind} onChange={(e) => set('kind', e.target.value)}>
              <option value="">All</option>
              {kinds.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </label>
        )}
        <label>Administration
          <select value={adm} onChange={(e) => set('adm', e.target.value)}>
            <option value="">All</option>
            {admins.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        {(m4Services.length > 0 || m4) && (
          <label>M4 primary service
            <select value={m4} onChange={(e) => set('m4', e.target.value)} title="A primary service in M4 on any of the bands involved">
              <option value="">All</option>
              {m4 && !m4Services.includes(m4) && <option value={m4}>{m4}</option>}
              {m4Services.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        )}
        <label>Review
          <select value={review} onChange={(e) => set('review', e.target.value)}>
            <option value="">All</option>
            {(['pending', ...api.capabilities.reviewStatuses.filter((s) => s !== 'pending')] as ReviewStatus[]).map((s) => <option key={s} value={s}>{reviewLabel(s)}</option>)}
          </select>
        </label>
        {hasStations && issue?.domain === 'space' && (
          <label className="check"><input type="checkbox" checked={stations} onChange={(e) => set('stations', e.target.checked ? '1' : '')} /> Overlaps a Finnish receiver</label>
        )}
      </form>

      {!rows ? <Loading error={rowsError} /> : (
        <>
          <p className="result-count" role="status">{filtered.length} of {rows.length} findings{sharedWindow(filtered) !== undefined && issue?.domain === 'space' && <> · {sharedWindow(filtered) ? <>all in one comment window: <CommentWindow deadline={sharedWindow(filtered)!} /></> : 'none opens a comment window'}</>}{filtersOn && <> · <button type="button" className="linkbtn" onClick={() => setParams({ issue: issueId }, { replace: true })}>Clear filters</button></>}</p>
          {issue?.screenStatus === 'no_rules' && <p className="notice notice-warn"><strong>No rules ran on this issue.</strong> Terrestrial screening doesn’t exist yet, so an empty list here does not mean there are no concerns.</p>}
          {issue?.screenStatus === 'pending' && <p className="notice" role="status"><strong>Screening is in progress,</strong> so this list may be incomplete.</p>}
          {issue?.screenStatus === 'failed' && <p className="alert" role="alert"><strong>Screening failed for this issue,</strong> so this list may be incomplete.</p>}
          {filtered.length === 0 ? (
            issue?.screenStatus !== 'no_rules' && <div className="empty panel"><h2>{filtersOn ? 'No findings match these filters' : 'No findings in this issue'}</h2></div>
          ) : rows.some((f) => f.terrestrial) ? <TerrTable rows={filtered} m4={m4} /> : <SpaceTable rows={filtered} m4={m4} />}
        </>
      )}
    </>
  );
}

/** The comment window every row shares, if they all share one: then it's said once, above the table. */
export const sharedWindow = (rows: Finding[]) => (rows.length > 1 && rows.every((f) => f.windowDeadline === rows[0].windowDeadline) ? rows[0].windowDeadline : undefined);

function SpaceTable({ rows, m4 }: { rows: Finding[]; m4: string }) {
  const hasBand = rows.some((f) => f.band);
  const hasMargin = rows.some((f) => f.marginDb !== null);
  const hasStations = rows.some((f) => f.stationCount !== null);
  const hasWindow = sharedWindow(rows) === undefined;
  const key = (f: Finding | undefined) => (f ? `${f.title}|${f.adm}` : '');
  return (
    <div className="table-wrap panel flush">
      <table className="rows">
        <thead><tr><th>Severity</th><th>Network</th>{hasBand && <th>Band</th>}<th>Reason</th>{hasMargin && <th className="num">Margin, dB</th>}{hasStations && <th className="num">Finnish receivers</th>}{hasWindow && <th>Comment window</th>}<th>Review</th></tr></thead>
        <tbody>
          {rows.map((f, i) => {
            const same = key(rows[i - 1]) === key(f);
            const continues = key(rows[i + 1]) === key(f);
            const href = `/findings/${f.id}${m4 ? `?m4=${encodeURIComponent(m4)}` : ''}`;
            return (
            <tr key={f.id} className={[same && 'same-network', continues && 'continues'].filter(Boolean).join(' ') || undefined}>
              <td><SeverityBadge value={f.severity} /></td>
              <td>{same
                ? <span className="continued"><span className="visually-hidden">{f.title}, same network as above</span></span>
                : <><Link to={href}><strong>{f.title}</strong></Link><span className="muted block">{f.adm}{f.orbit ? ` · ${f.orbit}` : ''}{f.sections.length ? ` · ${f.sections.join(', ')}` : ''}</span></>}</td>
              {hasBand && <td className="nowrap">{f.band ?? '–'}</td>}
              <td>{same ? <Link to={href}>{f.kindLabel}</Link> : f.kindLabel}</td>
              {hasMargin && <td className="num">{f.marginDb !== null ? db(f.marginDb) : '–'}</td>}
              {hasStations && <td className="num">{f.stationCount ?? '–'}</td>}
              {hasWindow && <td className="nowrap"><CommentWindow deadline={f.windowDeadline} /></td>}
              <td><ReviewBadge value={f.review.status} /></td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TerrTable({ rows, m4 }: { rows: Finding[]; m4: string }) {
  return (
    <div className="table-wrap panel flush">
      <table className="rows">
        <thead><tr><th>Severity</th><th>Site</th><th className="num">Frequency, MHz</th><th>Change</th><th className="num">To border, km</th><th className="num">Power, dBW</th><th>Review</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.id}>
              <td><SeverityBadge value={f.severity} /></td>
              <td><Link to={`/findings/${f.id}${m4 ? `?m4=${encodeURIComponent(m4)}` : ''}`}><strong>{f.title}</strong></Link><span className="muted block">{f.adm} · class {f.terrestrial?.stationClass}</span></td>
              <td className="num">{f.terrestrial?.fMhz}</td>
              <td>{f.terrestrial?.intent}</td>
              <td className="num">{f.terrestrial?.borderKm}</td>
              <td className="num">{f.terrestrial?.powerDbw ?? '–'}</td>
              <td><ReviewBadge value={f.review.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
