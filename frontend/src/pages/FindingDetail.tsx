import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';
import type { Finding, ReviewStatus } from '../api/types';
import { CommentWindow, ConfidenceText, Hash, Loading, ReviewBadge, SeverityBadge, useLoad } from '../components/ui';
import { admName } from '../lib/adm';
import { exportText } from '../lib/export';
import { db, formatDateTime, refBandwidth, signed } from '../lib/format';
import { draftLetter } from '../lib/letter';
import { pfdSteps } from '../lib/pfd';

export function FindingDetail() {
  const { id = '' } = useParams();
  const { data, error, loading } = useLoad(() => api.getFinding(id), [id]);
  const [finding, setFinding] = useState<Finding | null>(null);
  useEffect(() => setFinding(data ?? null), [data]);

  if (loading && !finding) return <Loading />;
  if (error) return <Loading error={error} />;
  if (!finding) return <div className="empty"><h1>Finding not found</h1><Link to="/findings">Back to findings</Link></div>;
  const f = finding;

  return (
    <>
      <p className="crumb"><Link to={`/findings?issue=${f.issueId}`}>Findings, IFIC {f.issue}</Link> / {f.title}</p>
      <div className="page-head">
        <div>
          <h1>{f.title}</h1>
          <p className="lead">{admName(f.adm)}{f.orbit ? ` · ${f.orbit}` : ''} · {f.band}{f.sections.length ? ` · ${f.sections.join(', ')}` : ''}</p>
        </div>
        <ReviewBadge value={f.review.status} />
      </div>

      <div className="detail">
        <div className="detail-main">
          <section className="panel">
            <h2>Why it was flagged</h2>
            <dl className="assess">
              <div><dt>Severity</dt><dd><SeverityBadge value={f.severity} /><ul>{f.severityReasons.map((r) => <li key={r}>{r}</li>)}</ul></dd></div>
              <div><dt>Confidence</dt><dd><strong><ConfidenceText value={f.confidence} /></strong><ul>{f.confidenceReasons.map((r) => <li key={r}>{r}</li>)}</ul></dd></div>
            </dl>
            <p className="fine">Severity follows fixed rules listed under <Link to="/reference">Rules and data</Link>. No AI was involved in this assessment.</p>
          </section>

          {f.calc && <Calculation f={f} />}
          {f.terrestrial && <TerrestrialPanel f={f} />}

          <section className="panel">
            <h2>Assumptions</h2>
            <ul>{f.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          </section>

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
            <p className="fine">{f.windowDeadline ? 'Release date plus four months. Confirm it against the Special Section.' : f.domain === 'terrestrial' ? 'Not determined for terrestrial notices yet.' : 'This issue carries a status update or a notification, so no new window was identified.'}</p>
            {f.sections.includes('API/A') && <p className="fine">RR No. 9.3 names interference to satellite networks, not terrestrial stations. Check how Traficom would raise a terrestrial concern on an API/A filing.</p>}
          </section>
          <section className="panel">
            <h2>Evidence</h2>
            <dl className="plain stacked">
              <div><dt>Source file</dt><dd className="wrap">{f.file.mdb}</dd></div>
              <div><dt>SHA-256</dt><dd><Hash value={f.file.mdbSha256} /></dd></div>
              <div><dt>Notice ID</dt><dd className="tnum">{f.sourceId}{f.relatedSourceIds.length > 0 && <span className="muted block">Paired record: {f.relatedSourceIds.join(', ')}</span>}</dd></div>
            </dl>
            <h3>Source rows</h3>
            <ul className="evidence">{f.evidence.map((e) => <li key={e.table + e.key}><code>{e.table}</code> <span className="wrap">{e.key}</span></li>)}</ul>
            <h3>Citations</h3>
            <ul className="evidence">{f.citations.map((c) => <li key={c}>{c}</li>)}</ul>
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
  useEffect(() => setText(f.review.letter ?? template), [f.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const dirty = text !== (f.review.letter ?? template);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Draft letter</h2>
        <span className="muted">Filled from a fixed template, no AI yet</span>
      </div>
      <label className="visually-hidden" htmlFor="letter">Draft letter text</label>
      <textarea id="letter" className="letter" rows={18} value={text} onChange={(e) => { setText(e.target.value); setSaved(false); }} />
      <div className="actions">
        <button type="button" className="btn btn-secondary" disabled={!dirty} onClick={async () => { onChange(await api.updateReview(f.id, { letter: text })); setSaved(true); }}>Save edits</button>
        <button type="button" className="btn btn-secondary" onClick={() => exportText(`draft-${f.sourceId}.txt`, text)}>Download</button>
        {saved && <span className="muted" role="status">Saved</span>}
      </div>
      <p className="fine">IFIC Guard never sends letters. An expert reviews each one and sends it through Traficom’s own channel.</p>
    </section>
  );
}

function Review({ f, onChange }: { f: Finding; onChange: (f: Finding) => void }) {
  const [note, setNote] = useState(f.review.note);
  const decide = async (status: ReviewStatus) => onChange(await api.updateReview(f.id, { status, note }));
  return (
    <section className="panel">
      <h2>Your review</h2>
      <label className="field-label" htmlFor="note">Note <span className="muted">(recommended for a rejection)</span></label>
      <textarea id="note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why did you decide this?" />
      <div className="review-actions">
        <button type="button" className="btn btn-primary" aria-pressed={f.review.status === 'accepted'} onClick={() => void decide('accepted')}>Accept</button>
        <button type="button" className="btn btn-secondary" aria-pressed={f.review.status === 'needs_info'} onClick={() => void decide('needs_info')}>Needs info</button>
        <button type="button" className="btn btn-secondary" aria-pressed={f.review.status === 'rejected'} onClick={() => void decide('rejected')}>Reject</button>
      </div>
      <p className="fine">Accepting means this is worth acting on. It sends nothing.</p>
    </section>
  );
}
