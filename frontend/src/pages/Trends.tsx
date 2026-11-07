import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import type { Domain, TrendFlag, Trends as TrendData } from '../api/types';
import { Loading, useLoad } from '../components/ui';
import { admName } from '../lib/adm';

const SPACE_TABLES: { key: string; title: string; adm?: boolean }[] = [
  { key: 'by_adm', title: 'Notices by administration', adm: true },
  { key: 'by_band', title: 'Notices by downlink band' },
  { key: 'by_orbit', title: 'Notices by orbit' },
  { key: 'by_reason', title: 'Notices by stage' },
];
const TERR_TABLES: { key: string; title: string; adm?: boolean }[] = [
  { key: 'screened_by_adm', title: 'Land-mobile notices within the distance screen, by administration', adm: true },
  { key: 'by_adm', title: 'All land-mobile notices, by administration', adm: true },
  { key: 'screened_by_band', title: 'Screened notices by frequency band' },
  { key: 'screened_by_class', title: 'Screened notices by station class' },
  { key: 'screened_by_bandwidth', title: 'Screened notices by bandwidth' },
];
const SHOW_ROWS = 10;

export function Trends() {
  const [params, setParams] = useSearchParams();
  const domain: Domain = params.get('domain') === 'terrestrial' ? 'terrestrial' : 'space';
  const { data, error } = useLoad(() => (api.capabilities.trends ? api.getTrends(domain) : Promise.resolve(null)), [domain]);
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Trends</h1>
          <p className="lead">What changes from one stored issue to the next. Counts are descriptive and make no predictions; a flag only says a count jumped.</p>
        </div>
        <div className="tabs" role="tablist" aria-label="Choose domain">
          {(['space', 'terrestrial'] as Domain[]).map((d) => (
            <button key={d} role="tab" type="button" aria-selected={domain === d} className={domain === d ? 'tab tab-on' : 'tab'} onClick={() => setParams(d === 'space' ? {} : { domain: d })}>
              {d === 'space' ? 'Space' : 'Terrestrial'}
            </button>
          ))}
        </div>
      </div>
      {!api.capabilities.trends ? <div className="empty panel"><h2>Trends need the live services</h2><p>Sample mode has no stored issues to compare.</p></div>
        : !data ? <Loading error={error} /> : <TrendBody t={data} />}
    </>
  );
}

function flagText(f: TrendFlag, adm: boolean) {
  return `${adm ? admName(f.name) : f.name}: ${f.count} in IFIC ${f.issue}, against ${f.earlierAverage} on average before`;
}

function TrendBody({ t }: { t: TrendData }) {
  const tables = t.domain === 'space' ? SPACE_TABLES : TERR_TABLES;
  const latest = t.issues[t.issues.length - 1];
  const gaps = t.issues.some((n, i) => i > 0 && n - t.issues[i - 1] > 1);
  const flags = tables.flatMap((tb) => (t.flags[tb.key] ?? []).map((f) => ({ ...f, table: tb })));
  const findings = (adm: string) => `/findings?issue=${t.domain}-${latest}&adm=${encodeURIComponent(adm)}`;

  if (t.issues.length === 0) return <div className="empty panel"><h2>No screened {t.domain} issue is stored yet</h2></div>;
  return (
    <>
      <p className="muted">
        Comparing IFIC {t.issues.join(', ')}{gaps ? '. Only issues stored here are shown, so some issue numbers are skipped.' : '.'}
        {t.issues.length < 2 && ' Trends need at least two stored issues, so these are one issue’s counts.'}
      </p>
      {t.problems.length > 0 && <p className="alert" role="alert">Left out: {t.problems.join('; ')}</p>}

      <section className="panel">
        <h2>Worth a look in IFIC {latest}</h2>
        {t.issues.length < 2 ? <p className="muted">Nothing to compare yet: a flag needs at least two stored issues.</p> : flags.length === 0 ? <p className="muted">No count jumped.</p> : (
          <ul className="trend-flags">
            {flags.map((f) => (
              <li key={`${f.table.key}-${f.name}`}>
                <span className="trend-up" aria-hidden="true">▲</span> {flagText(f, !!f.table.adm)}
                <span className="muted"> · {f.table.title.toLowerCase()}</span>
                {f.table.adm && <> · <Link to={findings(f.name)}>findings</Link></>}
              </li>
            ))}
          </ul>
        )}
        <p className="fine">{t.rule}</p>
      </section>

      {t.totals && (
        <section className="panel">
          <h2>Notices screened</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>IFIC</th>{t.issues.map((i) => <th key={i} className="num">{i}</th>)}</tr></thead>
              <tbody>
                <tr><td>Notices in scope</td>{t.issues.map((i) => <td key={i} className="num">{t.totals![i]?.filings ?? '–'}</td>)}</tr>
                <tr><td>Visible from Finland</td>{t.issues.map((i) => <td key={i} className="num">{t.totals![i]?.visibleFromFinland ?? '–'}</td>)}</tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {t.largestNgso && (t.largestNgso[latest]?.length ?? 0) > 0 && (
        <section className="panel">
          <h2>Largest non-GSO systems filed in IFIC {latest}</h2>
          <p className="muted">Planned satellites, summed over the notified orbital planes. What is planned, not launched.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Network</th><th>Administration</th><th>Stage</th><th className="num">Satellites</th></tr></thead>
              <tbody>{t.largestNgso[latest].map((s) => (
                <tr key={s.ntcId}>
                  <td><Link to={`/findings?issue=space-${latest}&q=${encodeURIComponent(s.network ?? String(s.ntcId))}`}>{s.network ?? s.ntcId}</Link></td>
                  <td>{s.adm ? admName(s.adm) : '–'}</td><td>{s.reason ?? '–'}</td><td className="num">{s.satellites.toLocaleString('en-GB')}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      {tables.map((tb) => <CountTable key={tb.key} t={t} title={tb.title} dim={tb.key} adm={!!tb.adm} />)}

      <section className="panel subtle">
        <h2>How these are counted</h2>
        <ul className="muted">{t.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      </section>
    </>
  );
}

function CountTable({ t, title, dim, adm }: { t: TrendData; title: string; dim: string; adm: boolean }) {
  const [all, setAll] = useState(false);
  const series = t.series[dim] ?? {};
  const latest = t.issues[t.issues.length - 1];
  const flagged = new Set((t.flags[dim] ?? []).map((f) => f.name));
  const rows = Object.entries(series).sort(([a, x], [b, y]) => (y[latest] ?? 0) - (x[latest] ?? 0) || a.localeCompare(b));
  if (rows.length === 0) return null;
  const shown = all ? rows : rows.slice(0, SHOW_ROWS);
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>{adm ? 'Administration' : 'Category'}</th>{t.issues.map((i) => <th key={i} className="num">{i}</th>)}</tr></thead>
          <tbody>
            {shown.map(([name, counts]) => (
              <tr key={name}>
                <td>{adm ? admName(name) : name}</td>
                {t.issues.map((i) => {
                  const up = i === latest && flagged.has(name);
                  return <td key={i} className="num">{up && <span className="trend-up" title="Jumped against the earlier issues">▲ </span>}<span className={up ? 'trend-value-up' : undefined}>{counts[i] ?? 0}</span></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > SHOW_ROWS && <button type="button" className="linkbtn show-all" onClick={() => setAll(!all)}>{all ? 'Show fewer' : `Show all ${rows.length}`}</button>}
    </section>
  );
}
