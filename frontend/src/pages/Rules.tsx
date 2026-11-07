import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import type { CustomRule, IssueSummary, RuleDefinition, RuleOptions, RulePreview, RuleSave, RuleSpec, Tri } from '../api/types';
import { Loading, SeverityBadge, useLoad } from '../components/ui';
import { formatDateTime } from '../lib/format';

const SAVED_BY = 'ific-guard-saved-by';
const readSavedBy = () => { try { return localStorage.getItem(SAVED_BY) ?? ''; } catch { return ''; } };
const keepSavedBy = (name: string) => { try { localStorage.setItem(SAVED_BY, name); } catch { /* typed again next time */ } };

function LiveOnly() {
  return <div className="empty panel"><h2>Rules need the live services</h2><p>Sample mode has no screening service to store or run rules. Start the frontend with <code>npm run dev</code>.</p></div>;
}

function RescreenButton({ label = 'Screen all space issues again' }: { label?: string }) {
  const [state, setState] = useState<{ busy: boolean; done?: number[]; error?: string }>({ busy: false });
  async function go() {
    setState({ busy: true });
    try {
      setState({ busy: false, done: await api.rescreenSpace() });
    } catch (e) {
      setState({ busy: false, error: (e as Error).message });
    }
  }
  return (
    <>
      <button type="button" className="btn btn-secondary" disabled={state.busy} onClick={() => void go()}>{state.busy ? 'Queuing…' : label}</button>
      {state.done && <span className="muted" role="status">Queued {state.done.length ? `IFIC ${state.done.join(', ')}` : 'nothing: no space issues are stored'}. Cases update as each finishes.</span>}
      {state.error && <span className="alert" role="alert">{state.error}</span>}
    </>
  );
}

export function Rules() {
  const { data: rules, error } = useLoad(() => api.listRules(), []);
  if (!api.capabilities.customRules) return <><div className="page-head"><h1>Screening rules</h1></div><LiveOnly /></>;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Screening rules</h1>
          <p className="lead">Rules written by experts run beside the built-in ones on every space issue. Each save is a new version, and each case names the version that raised it.</p>
        </div>
        <div className="actions"><Link className="btn btn-primary" to="/rules/new">New rule</Link></div>
      </div>
      {!rules ? <Loading error={error} /> : rules.length === 0 ? (
        <div className="empty panel"><h2>No rules written yet</h2><p>The built-in rules are listed under <Link to="/reference">Rules and data</Link>.</p></div>
      ) : (
        <div className="table-wrap panel flush">
          <table className="rows">
            <thead><tr><th>Rule</th><th>Severity</th><th>Status</th><th className="num">Version</th><th className="num">Cases now</th><th>Updated</th></tr></thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id}>
                  <td><Link to={`/rules/${r.id}`}><strong>{r.name}</strong></Link><span className="muted block">{r.conditions.join(' · ')}</span></td>
                  <td><SeverityBadge value={r.severity} /></td>
                  <td>{r.enabled ? 'On' : <span className="muted">Off</span>}</td>
                  <td className="num">{r.version}</td>
                  <td className="num">{r.caseCount > 0 ? <Link to={`/findings?kind=${r.ruleId}`}>{r.caseCount}</Link> : 0}</td>
                  <td className="nowrap">{formatDateTime(r.updatedAt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <section className="panel subtle">
        <h2>Applying changes</h2>
        <p className="muted">A saved rule changes cases only when issues are screened again. Screening runs the built-in rules too and can take a few minutes per issue. A case whose content changes goes back to pending review.</p>
        <div className="actions"><RescreenButton /></div>
      </section>
    </>
  );
}

interface Draft {
  name: string; description: string; severity: RuleSpec['severity']; titleTemplate: string; enabled: boolean; savedBy: string; note: string;
  orbit: RuleDefinition['orbit']; visible: boolean; admIn: string; admNotIn: string; provisionIn: string; direction: RuleDefinition['direction'];
  ranges: { low: string; high: string }[]; m4: RuleDefinition['m4'];
}

const BLANK: Draft = {
  name: '', description: '', severity: 'medium', titleTemplate: '{network} ({adm}) matches {rule}', enabled: true, savedBy: '', note: '',
  orbit: 'any', visible: true, admIn: '', admNotIn: '', provisionIn: '', direction: 'transmit', ranges: [],
  m4: { spaceToEarth: 'any', earthToSpace: 'any', terrestrialPrimary: 'any', passive: 'any', primaryServicesAny: [] },
};

const draftOf = (r: CustomRule): Draft => ({
  name: r.name, description: r.description, severity: r.severity, titleTemplate: r.titleTemplate, enabled: r.enabled, savedBy: '', note: '',
  orbit: r.definition.orbit, visible: r.definition.visibleFromFinland, admIn: r.definition.admIn.join(', '), admNotIn: r.definition.admNotIn.join(', '),
  provisionIn: r.definition.provisionIn.join(', '), direction: r.definition.direction,
  ranges: r.definition.frequencyRanges.map((x) => ({ low: String(x.lowMhz), high: String(x.highMhz) })), m4: r.definition.m4,
});

const list = (text: string) => text.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);

function specOf(d: Draft): RuleSpec {
  return {
    name: d.name, description: d.description, severity: d.severity, titleTemplate: d.titleTemplate,
    definition: {
      orbit: d.orbit, visibleFromFinland: d.visible, admIn: list(d.admIn).map((a) => a.toUpperCase()), admNotIn: list(d.admNotIn).map((a) => a.toUpperCase()),
      provisionIn: list(d.provisionIn), direction: d.direction,
      frequencyRanges: d.ranges.filter((r) => r.low !== '' || r.high !== '').map((r) => ({ lowMhz: Number(r.low), highMhz: Number(r.high) })), m4: d.m4,
    },
  };
}

function TriSelect({ label, value, onChange, yes, no }: { label: string; value: Tri; onChange: (v: Tri) => void; yes: string; no: string }) {
  return (
    <div className="field">
      <label>{label}
        <select value={value} onChange={(e) => onChange(e.target.value as Tri)}>
          <option value="any">Doesn’t matter</option><option value="yes">{yes}</option><option value="no">{no}</option>
        </select>
      </label>
    </div>
  );
}

function ServicePicker({ all, chosen, onChange }: { all: string[]; chosen: string[]; onChange: (v: string[]) => void }) {
  const [q, setQ] = useState('');
  const shown = all.filter((s) => chosen.includes(s) || s.toLowerCase().includes(q.toLowerCase()));
  const toggle = (s: string) => onChange(chosen.includes(s) ? chosen.filter((x) => x !== s) : [...chosen, s].sort());
  return (
    <div className="field">
      <span className="field-label">M4 primary service is one of</span>
      <input type="search" value={q} placeholder="Find a service" onChange={(e) => setQ(e.target.value)} aria-label="Find an M4 service" />
      <div className="pick-list" role="group" aria-label="M4 primary services">
        {shown.map((s) => <label key={s} className="check"><input type="checkbox" checked={chosen.includes(s)} onChange={() => toggle(s)} /> {s}</label>)}
        {shown.length === 0 && <p className="muted">No service matches.</p>}
      </div>
      <p className="field-hint">{chosen.length ? `${chosen.length} chosen: ${chosen.join(', ')}` : 'None chosen, so any service counts.'}</p>
    </div>
  );
}

function Preview({ spec, issues }: { spec: RuleSpec; issues: IssueSummary[] }) {
  const space = issues.filter((i) => i.domain === 'space' && i.artifactId !== null).sort((a, b) => b.issue - a.issue);
  const [artifactId, setArtifactId] = useState<number | null>(space[0]?.artifactId ?? null);
  const [state, setState] = useState<{ busy: boolean; result?: RulePreview; error?: string }>({ busy: false });
  async function run() {
    if (artifactId === null) return;
    setState({ busy: true });
    try {
      setState({ busy: false, result: await api.previewRule(spec, artifactId) });
    } catch (e) {
      setState({ busy: false, error: (e as Error).message });
    }
  }
  const r = state.result;
  return (
    <section className="panel">
      <h2>Preview</h2>
      <p className="muted">Runs this draft on a stored issue. Nothing is saved and no cases are opened. The first preview of an issue reads the whole file, so it can take a minute.</p>
      {space.length === 0 ? <p className="muted">No space issue is stored yet.</p> : (
        <div className="filters">
          <label>Issue
            <select value={artifactId ?? ''} onChange={(e) => setArtifactId(Number(e.target.value))}>
              {space.map((i) => <option key={i.id} value={i.artifactId!}>IFIC {i.issue} Space</option>)}
            </select>
          </label>
          <button type="button" className="btn btn-secondary" disabled={state.busy || !spec.name.trim()} onClick={() => void run()}>{state.busy ? 'Running…' : 'Preview'}</button>
        </div>
      )}
      {!spec.name.trim() && <p className="field-hint">Name the rule to preview it.</p>}
      {state.error && <p className="alert" role="alert">{state.error}</p>}
      {r && (
        <>
          <p role="status"><strong>{r.total === 0 ? 'Would raise no cases' : `Would raise ${r.total} case${r.total === 1 ? '' : 's'}`}</strong> in IFIC {r.issueNo}{r.total > 0 && <> · {Object.entries(r.byAdm).slice(0, 8).map(([a, n]) => `${a} ${n}`).join(', ')}{Object.keys(r.byAdm).length > 8 ? ', …' : ''}</>}</p>
          {r.hits.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>Severity</th><th>Title</th><th className="num">M4 bands</th><th className="num">Assignments</th></tr></thead>
                <tbody>{r.hits.map((h) => <tr key={h.noticeIds.join('-')}><td><SeverityBadge value={h.severity} /></td><td>{h.title}</td><td className="num">{h.bands}</td><td className="num">{h.assignments}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {r.total > r.hits.length && <p className="fine">Showing the first {r.hits.length}.</p>}
        </>
      )}
    </section>
  );
}

export function RuleEditor() {
  const { id } = useParams();
  const ruleId = id === undefined || id === 'new' ? undefined : Number(id);
  const navigate = useNavigate();
  const { data, error } = useLoad(async () => {
    const [rule, options, issues] = await Promise.all([ruleId === undefined ? Promise.resolve(null) : api.getRule(ruleId), api.ruleOptions(), api.listIssues()]);
    return { rule, options, issues };
  }, [ruleId]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [current, setCurrent] = useState<CustomRule | null>(null);
  const [saving, setSaving] = useState<{ busy: boolean; error?: string; saved?: CustomRule; changed?: boolean }>({ busy: false });

  useEffect(() => {
    if (!data) return;
    setCurrent(data.rule);
    setDraft({ ...(data.rule ? draftOf(data.rule) : BLANK), savedBy: readSavedBy() });
  }, [data]);
  const spec = useMemo(() => (draft ? specOf(draft) : null), [draft]);

  if (!api.capabilities.customRules) return <><div className="page-head"><h1>Screening rule</h1></div><LiveOnly /></>;
  if (!data || !draft || !spec) return <Loading error={error} />;
  if (ruleId !== undefined && !data.rule) return <div className="empty"><h1>Rule not found</h1><Link to="/rules">Back to rules</Link></div>;
  const rule = current;
  const options: RuleOptions = data.options;
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft({ ...draft, [key]: value });
  const setM4 = <K extends keyof Draft['m4']>(key: K, value: Draft['m4'][K]) => setDraft({ ...draft, m4: { ...draft.m4, [key]: value } });
  const setRange = (i: number, side: 'low' | 'high', value: string) => set('ranges', draft.ranges.map((r, j) => (j === i ? { ...r, [side]: value } : r)));

  async function save() {
    if (!draft || !spec) return;
    setSaving({ busy: true });
    try {
      const body: RuleSave = { ...spec, enabled: draft.enabled, savedBy: draft.savedBy.trim(), note: draft.note.trim() };
      const saved = await api.saveRule(body, rule?.id);
      keepSavedBy(body.savedBy);
      setSaving({ busy: false, saved, changed: !rule || saved.version !== rule.version });
      setCurrent(saved);
      setDraft({ ...draftOf(saved), savedBy: body.savedBy });
      if (!rule) navigate(`/rules/${saved.id}`, { replace: true });
    } catch (e) {
      setSaving({ busy: false, error: (e as Error).message });
    }
  }

  return (
    <>
      <p className="crumb"><Link to="/rules">Screening rules</Link> / {rule ? rule.name : 'New rule'}</p>
      <div className="page-head">
        <div>
          <h1>{rule ? rule.name : 'New rule'}</h1>
          <p className="lead">{rule ? `Version ${rule.version} · ${rule.enabled ? 'on' : 'off'} · ${rule.caseCount} case${rule.caseCount === 1 ? '' : 's'} now` : 'Every condition must hold for a filing to be raised.'}</p>
        </div>
      </div>

      <form className="detail" onSubmit={(e) => { e.preventDefault(); void save(); }}>
        <div className="detail-main">
          <section className="panel">
            <h2>About the rule</h2>
            <div className="field"><label>Name<input value={draft.name} onChange={(e) => set('name', e.target.value)} required maxLength={120} /></label></div>
            <div className="field" style={{ marginTop: 12 }}><label>Why it matters<textarea rows={2} value={draft.description} onChange={(e) => set('description', e.target.value)} placeholder="Shown to reviewers on the Rules page" /></label></div>
            <div className="form-row">
              <div className="field"><label>Severity of its cases
                <select value={draft.severity} onChange={(e) => set('severity', e.target.value as Draft['severity'])}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
              </label></div>
              <div className="field"><label>Case title<input value={draft.titleTemplate} onChange={(e) => set('titleTemplate', e.target.value)} required maxLength={300} /></label>
                <p className="field-hint">Fields: {Object.entries(options.titleFields).map(([k, v]) => `{${k}} ${v}`).join(', ')}.</p>
              </div>
            </div>
            <label className="check" style={{ marginTop: 12 }}><input type="checkbox" checked={draft.enabled} onChange={(e) => set('enabled', e.target.checked)} /> On: run this rule when issues are screened</label>
          </section>

          <section className="panel">
            <h2>Which filings</h2>
            <div className="form-row">
              <div className="field"><label>Orbit
                <select value={draft.orbit} onChange={(e) => set('orbit', e.target.value as Draft['orbit'])}><option value="any">Any satellite</option><option value="gso">GSO only</option><option value="ngso">Non-GSO only</option></select>
              </label></div>
              <div className="field"><label>Provisions<input value={draft.provisionIn} onChange={(e) => set('provisionIn', e.target.value)} placeholder="Any, or e.g. 9.6, 9.1A" /></label></div>
              <div className="field"><label>Notified by<input value={draft.admIn} onChange={(e) => set('admIn', e.target.value)} placeholder="Any, or e.g. RUS, CHN" /></label></div>
              <div className="field"><label>Not notified by<input value={draft.admNotIn} onChange={(e) => set('admNotIn', e.target.value)} placeholder="e.g. FIN" /></label></div>
            </div>
            <label className="check" style={{ marginTop: 12 }}><input type="checkbox" checked={draft.visible} onChange={(e) => set('visible', e.target.checked)} /> Only satellites whose orbit can be seen from Finland</label>
          </section>

          <section className="panel">
            <h2>Which frequencies</h2>
            <div className="form-row">
              <div className="field"><label>The satellite
                <select value={draft.direction} onChange={(e) => set('direction', e.target.value as Draft['direction'])}><option value="transmit">Transmits (space-to-Earth)</option><option value="receive">Receives (Earth-to-space)</option><option value="either">Transmits or receives</option></select>
              </label></div>
            </div>
            <p className="field-label" style={{ marginTop: 14 }}>Within these ranges, MHz</p>
            {draft.ranges.length === 0 && <p className="field-hint">Any frequency.</p>}
            {draft.ranges.map((r, i) => (
              <div key={i} className="range-row">
                <input type="number" min={0} step="any" value={r.low} onChange={(e) => setRange(i, 'low', e.target.value)} aria-label={`Range ${i + 1} from, MHz`} placeholder="From" required />
                <span aria-hidden="true">–</span>
                <input type="number" min={0} step="any" value={r.high} onChange={(e) => setRange(i, 'high', e.target.value)} aria-label={`Range ${i + 1} to, MHz`} placeholder="To" required />
                <button type="button" className="linkbtn" onClick={() => set('ranges', draft.ranges.filter((_, j) => j !== i))}>Remove</button>
              </div>
            ))}
            <button type="button" className="btn btn-secondary" style={{ marginTop: 8 }} onClick={() => set('ranges', [...draft.ranges, { low: '', high: '' }])}>Add a range</button>
          </section>

          <section className="panel">
            <h2>What M4 says there</h2>
            <p className="muted">The frequency must fall in an M4 row that meets all of these. Leave them open to match any row; the case still lists the M4 bands it falls in.</p>
            <div className="form-row">
              <TriSelect label="Space-to-Earth allocation" value={draft.m4.spaceToEarth} onChange={(v) => setM4('spaceToEarth', v)} yes="Allocated" no="Not allocated" />
              <TriSelect label="Earth-to-space allocation" value={draft.m4.earthToSpace} onChange={(v) => setM4('earthToSpace', v)} yes="Allocated" no="Not allocated" />
              <TriSelect label="Primary terrestrial use" value={draft.m4.terrestrialPrimary} onChange={(v) => setM4('terrestrialPrimary', v)} yes="Yes" no="No" />
              <TriSelect label="Passive or radio astronomy" value={draft.m4.passive} onChange={(v) => setM4('passive', v)} yes="Yes" no="No" />
            </div>
            <div style={{ marginTop: 14 }}><ServicePicker all={options.m4PrimaryServices} chosen={draft.m4.primaryServicesAny} onChange={(v) => setM4('primaryServicesAny', v)} /></div>
          </section>

          <Preview spec={spec} issues={data.issues} />

          {rule && rule.versions.length > 0 && (
            <section className="panel">
              <h2>History</h2>
              <div className="table-wrap">
                <table>
                  <thead><tr><th className="num">Version</th><th>Saved</th><th>By</th><th>Severity</th><th>Note</th></tr></thead>
                  <tbody>{rule.versions.map((v) => <tr key={v.version}><td className="num">{v.version}</td><td className="nowrap">{formatDateTime(v.savedAt)}</td><td>{v.savedBy || '–'}</td><td><SeverityBadge value={v.severity} />{!v.enabled && <span className="muted"> off</span>}</td><td>{v.note || '–'}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}
        </div>

        <aside className="detail-side">
          <section className="panel">
            <h2>{rule ? 'Save a new version' : 'Save'}</h2>
            <div className="field"><label>Your name<input value={draft.savedBy} onChange={(e) => set('savedBy', e.target.value)} placeholder="Recorded with this version" /></label></div>
            <div className="field" style={{ marginTop: 12 }}><label>What changed<textarea rows={2} value={draft.note} onChange={(e) => set('note', e.target.value)} /></label></div>
            <div className="actions"><button type="submit" className="btn btn-primary" disabled={saving.busy}>{saving.busy ? 'Saving…' : 'Save'}</button></div>
            {saving.error && <p className="alert" role="alert">{saving.error}</p>}
            {saving.saved && (
              <div className="notice" role="status" style={{ marginTop: 12 }}>
                <p>{saving.changed ? `Saved as version ${saving.saved.version}.` : 'Nothing changed, so no new version was saved.'} Cases change when issues are screened again.</p>
                <div className="actions"><RescreenButton label="Screen space issues again" /></div>
              </div>
            )}
          </section>
        </aside>
      </form>
    </>
  );
}
