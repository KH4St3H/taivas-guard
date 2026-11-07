import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Domain, Finding, IssueSummary } from '../api/types';
import { Funnel } from '../components/Funnel';
import { CommentWindow, Hash, Loading, SeverityBadge, useLoad } from '../components/ui';
import { db, formatDate } from '../lib/format';

export function Overview() {
  const [params, setParams] = useSearchParams();
  const { data, error } = useLoad(async () => ({ issues: await api.listIssues(), monitor: await api.getMonitor() }), []);
  if (!data) return <Loading error={error} />;
  const { issues, monitor } = data;
  const latest = (d: Domain) => issues.filter((i) => i.domain === d).sort((a, b) => b.issue - a.issue)[0];
  const domain = (params.get('view') === 'terrestrial' ? 'terrestrial' : 'space') as Domain;
  const issue = latest(domain);
  const other = latest(domain === 'space' ? 'terrestrial' : 'space');
  const evaluation = issues.filter((i) => i.evaluationIssue);

  return (
    <>
      <section className="hero">
        <div className="hero-main">
          <p className="eyebrow">Latest ITU release</p>
          <h1>BR IFIC {issue.issue}</h1>
          <dl className="hero-facts">
            <div><dt>Released</dt><dd>{formatDate(issue.releasedOn)}</dd></div>
            <div><dt>Comment window</dt><dd><CommentWindow deadline={issue.commentDeadline} /></dd></div>
            <div><dt>Source file</dt><dd>{issue.file.zip} <Hash value={issue.file.zipSha256} /></dd></div>
          </dl>
          <dl className="hero-counts">
            {issue.counts.map((c) => <div key={c.label}><dt>{c.label}</dt><dd>{c.value.toLocaleString('en-GB')}</dd></div>)}
          </dl>
          {issue.commentDeadline && <p className="fine">Window calculated as release date plus four months. Confirm it against the date printed in each Special Section.</p>}
        </div>
        <aside className="monitor">
          <h2>ITU monitor</h2>
          <p className="monitor-state"><span className="dot dot-off" aria-hidden="true" /> {monitor.connected ? 'Running' : 'Not running yet'}</p>
          <dl className="plain">
            <div><dt>Latest release found</dt><dd>{monitor.latestKnownIssue}, {formatDate(monitor.latestKnownDate)}</dd></div>
            <div><dt>Checked</dt><dd>{formatDate(monitor.checkedOn)}, by hand</dd></div>
            <div><dt>Next release expected</dt><dd>{formatDate(monitor.nextExpectedOn)}</dd></div>
          </dl>
          <p className="fine">{monitor.note}</p>
          <Link className="btn btn-secondary" to="/analyze">Analyse a file now</Link>
        </aside>
      </section>

      <div className="tabs" role="tablist" aria-label="Choose results">
        {(['space', 'terrestrial'] as Domain[]).map((d) => (
          <button key={d} role="tab" type="button" aria-selected={domain === d} className={domain === d ? 'tab tab-on' : 'tab'} onClick={() => setParams(d === 'space' ? {} : { view: d })}>
            {d === 'space' ? 'Space' : 'Terrestrial'}
          </button>
        ))}
      </div>

      <IssueResults issue={issue} />

      <section className="panel">
        <h2>Issues named in the Traficom brief</h2>
        <p className="muted">These two issues are what the challenge evaluates.</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Issue</th><th>Type</th><th>Released</th><th className="num">Items</th><th aria-label="Link" /></tr></thead>
            <tbody>
              {evaluation.map((i) => (
                <tr key={i.id}>
                  <td className="nowrap">IFIC {i.issue}</td><td>{i.domain === 'space' ? 'Space' : 'Terrestrial'}</td><td className="nowrap">{formatDate(i.releasedOn)}</td><td className="num">{i.counts[0].value.toLocaleString('en-GB')}</td>
                  <td className="right nowrap"><Link to={`/findings?issue=${i.id}`}>View findings</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {other && <p className="fine">The latest {other.domain} results are also from IFIC {other.issue}; switch with the tabs above.</p>}
      </section>
    </>
  );
}

function IssueResults({ issue }: { issue: IssueSummary }) {
  const { data: findings, error } = useLoad(() => api.listFindings(issue.id), [issue.id]);
  const sev = issue.severityCounts;
  const isSpace = issue.domain === 'space';
  const pending = findings?.filter((f) => f.review.status === 'pending').length;
  return (
    <div role="tabpanel">
      <section className="stats" aria-label="Results summary">
        {isSpace ? (
          <>
            <Stat value={sev.high} label="High severity" to={`/findings?issue=${issue.id}&severity=high`} />
            <Stat value={sev.medium} label="Medium severity" to={`/findings?issue=${issue.id}&severity=medium`} />
            <Stat value={issue.brListedNetworks} label="Networks where ITU lists Finland" to={`/findings?issue=${issue.id}&kind=br_listed`} />
          </>
        ) : (
          <>
            <Stat value={issue.funnel[3].n} label="Foreign land-mobile stations within 100 km" to={`/findings?issue=${issue.id}`} />
            <Stat value={issue.funnel[2].n} label="Within 300 km" to={`/findings?issue=${issue.id}`} />
            <Stat value={sev.unscored} label="Listed here, waiting for a calculation" to={`/findings?issue=${issue.id}`} />
          </>
        )}
        <Stat value={pending ?? '–'} label="Waiting for expert review" to={`/findings?issue=${issue.id}&review=pending`} />
      </section>

      <div className="split">
        <section className="panel">
          <h2>How the issue narrowed down</h2>
          <Funnel stages={issue.funnel} />
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>Top findings</h2>
            <Link to={`/findings?issue=${issue.id}`}>All findings</Link>
          </div>
          {!findings ? <Loading error={error} /> : <TopFindings rows={findings.slice(0, 6)} />}
        </section>
      </div>

      <section className="panel callout">
        <h2>What this run didn’t check</h2>
        <ul>{issue.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>
    </div>
  );
}

function Stat({ value, label, to }: { value: number | string; label: string; to: string }) {
  return <Link className="stat" to={to}><span className="stat-value">{value}</span><span className="stat-label">{label}</span></Link>;
}

function TopFindings({ rows }: { rows: Finding[] }) {
  return (
    <ul className="top-list">
      {rows.map((f) => (
        <li key={f.id}>
          <Link to={`/findings/${f.id}`}>
            <span className="top-main"><strong>{f.title}</strong> <span className="muted">{f.adm} · {f.band}</span></span>
            <span className="top-meta">
              {f.marginDb !== null ? <span className="tnum">{db(f.marginDb)} dB</span> : f.terrestrial ? <span className="tnum">{f.terrestrial.borderKm} km</span> : <span className="muted">ITU-listed</span>}
              <SeverityBadge value={f.severity} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
