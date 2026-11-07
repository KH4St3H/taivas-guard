import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Finding, ReviewStatus, Severity } from '../api/types';
import { CommentWindow, Loading, reviewLabel, ReviewBadge, SeverityBadge, useLoad } from '../components/ui';
import { exportFindings } from '../lib/export';
import { db, formatDate } from '../lib/format';

const KIND: Record<Finding['kind'], string> = { pfd_screen: 'Above a limit', br_listed: 'ITU lists Finland', near_border: 'Near the border' };

export function Findings() {
  const [params, setParams] = useSearchParams();
  const { data: issues, error } = useLoad(() => api.listIssues(), []);
  const issueId = params.get('issue') ?? 'space-3083';
  const { data: rows, error: rowsError } = useLoad(() => api.listFindings(issueId), [issueId]);

  const q = params.get('q') ?? '';
  const severity = params.get('severity') ?? '';
  const review = params.get('review') ?? '';
  const kind = params.get('kind') ?? '';
  const adm = params.get('adm') ?? '';
  const stations = params.get('stations') === '1';

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };

  const filtered = useMemo(() => (rows ?? []).filter((f) =>
    (!severity || f.severity === severity) && (!review || f.review.status === review) && (!kind || f.kind === kind) && (!adm || f.adm === adm)
    && (!stations || f.stationCount > 0) && (!q || `${f.title} ${f.adm} ${f.band} ${f.sourceId}`.toLowerCase().includes(q.toLowerCase())),
  ), [rows, severity, review, kind, adm, stations, q]);

  if (!issues) return <Loading error={error} />;
  const issue = issues.find((i) => i.id === issueId);
  const admins = [...new Set((rows ?? []).map((f) => f.adm))].sort();
  const kinds = [...new Set((rows ?? []).map((f) => f.kind))];
  const filtersOn = q || severity || review || kind || adm || stations;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Findings</h1>
          {issue && <p className="lead">{issue.domain === 'space' ? 'Space' : 'Terrestrial'} IFIC {issue.issue}, released {formatDate(issue.releasedOn)}. Ranked by computed severity, then margin.</p>}
        </div>
        <div className="actions">
          <button type="button" className="btn btn-secondary" disabled={!filtered.length} onClick={() => exportFindings(issueId, filtered, 'csv')}>Export CSV</button>
          <button type="button" className="btn btn-secondary" disabled={!filtered.length} onClick={() => exportFindings(issueId, filtered, 'json')}>Export JSON</button>
        </div>
      </div>

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
              {kinds.map((k) => <option key={k} value={k}>{KIND[k]}</option>)}
            </select>
          </label>
        )}
        <label>Administration
          <select value={adm} onChange={(e) => set('adm', e.target.value)}>
            <option value="">All</option>
            {admins.map((a) => <option key={a}>{a}</option>)}
          </select>
        </label>
        <label>Review
          <select value={review} onChange={(e) => set('review', e.target.value)}>
            <option value="">All</option>
            {(['pending', 'accepted', 'rejected', 'needs_info'] as ReviewStatus[]).map((s) => <option key={s} value={s}>{reviewLabel(s)}</option>)}
          </select>
        </label>
        {issue?.domain === 'space' && (
          <label className="check"><input type="checkbox" checked={stations} onChange={(e) => set('stations', e.target.checked ? '1' : '')} /> Overlaps a Finnish receiver</label>
        )}
      </form>

      {!rows ? <Loading error={rowsError} /> : (
        <>
          <p className="result-count" role="status">{filtered.length} of {rows.length} findings{filtersOn && <> · <button type="button" className="linkbtn" onClick={() => setParams({ issue: issueId }, { replace: true })}>Clear filters</button></>}</p>
          {filtered.length === 0 ? (
            <div className="empty panel"><h2>No findings match these filters</h2></div>
          ) : issue?.domain === 'terrestrial' ? <TerrTable rows={filtered} /> : <SpaceTable rows={filtered} />}
        </>
      )}
    </>
  );
}

function SpaceTable({ rows }: { rows: Finding[] }) {
  return (
    <div className="table-wrap panel flush">
      <table className="rows">
        <thead><tr><th>Severity</th><th>Network</th><th>Band</th><th>Reason</th><th className="num">Margin, dB</th><th className="num">Finnish receivers</th><th>Comment window</th><th>Review</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.id}>
              <td><SeverityBadge value={f.severity} /></td>
              <td><Link to={`/findings/${f.id}`}><strong>{f.title}</strong></Link><span className="muted block">{f.adm} · {f.orbit} · {f.sections.join(', ') || f.provision}</span></td>
              <td className="nowrap">{f.band}</td>
              <td>{KIND[f.kind]}</td>
              <td className="num">{f.marginDb !== null ? db(f.marginDb) : '–'}</td>
              <td className="num">{f.stationCount}</td>
              <td className="nowrap"><CommentWindow deadline={f.windowDeadline} /></td>
              <td><ReviewBadge value={f.review.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TerrTable({ rows }: { rows: Finding[] }) {
  return (
    <div className="table-wrap panel flush">
      <table className="rows">
        <thead><tr><th>Severity</th><th>Site</th><th className="num">Frequency, MHz</th><th>Change</th><th className="num">To border, km</th><th className="num">Power, dBW</th><th>Review</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.id}>
              <td><SeverityBadge value={f.severity} /></td>
              <td><Link to={`/findings/${f.id}`}><strong>{f.title}</strong></Link><span className="muted block">{f.adm} · class {f.terrestrial?.stationClass}</span></td>
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
