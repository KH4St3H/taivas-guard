import { Link } from 'react-router-dom';
import { api } from '../api';
import { Hash, Loading, RunStatusBadge, triggerLabel, useLoad } from '../components/ui';
import { formatDateTime } from '../lib/format';

export function Runs() {
  const { data: runs, error } = useLoad(() => api.listRuns(), []);
  if (!runs) return <Loading error={error} />;
  const scheduled = runs.filter((r) => r.trigger === 'scheduled').length;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Runs</h1>
          <p className="lead">Every time a file has gone through the system, on a schedule or on demand.</p>
        </div>
        <Link className="btn btn-primary" to="/analyze">Analyse a file</Link>
      </div>
      {scheduled === 0 && <p className="notice">No scheduled runs yet, because the ITU monitor isn’t running. Once it is, each new release will appear here automatically.</p>}
      <div className="table-wrap panel flush">
        <table>
          <thead><tr><th>Started</th><th>Trigger</th><th>File</th><th>Issue</th><th>Status</th><th>SHA-256</th><th aria-label="Link" /></tr></thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td className="nowrap">{formatDateTime(r.startedAt)}</td>
                <td>{triggerLabel(r.trigger)}</td>
                <td>{r.fileName}<span className="muted block">{r.domain === 'space' ? 'Space' : 'Terrestrial'}</span></td>
                <td className="tnum">{r.issue ?? '–'}</td>
                <td><RunStatusBadge value={r.status} /></td>
                <td><Hash value={r.sha256} /></td>
                <td className="right nowrap">{r.issueId ? <Link to={`/findings?issue=${r.issueId}`}>Findings</Link> : <Link to={`/runs/${r.id}`}>Details</Link>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
