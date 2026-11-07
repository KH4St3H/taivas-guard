import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type { Coverage } from '../api/types';
import { useLoad } from './ui';

// Colours: one blue sequential ramp for magnitude, blue <-> red with a grey midpoint for the margin, and
// one orange for stations. Validated with the dataviz palette script against both app surfaces.
const BLUE = ['#cde2fb', '#b7d3f6', '#9ec5f4', '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6', '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b'];
const DIVERGING = {
  light: { low: '#2a78d6', mid: '#f0efec', high: '#e34948' },
  dark: { low: '#3987e5', mid: '#383835', high: '#e66767' },
};

type Theme = 'light' | 'dark';
type Layer = 'angle' | 'minutes' | 'pfd' | 'margin';
type CellRow = Coverage['cells'][number];

function useTheme(): Theme {
  const read = (): Theme => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    const watch = new MutationObserver(() => setTheme(read()));
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => watch.disconnect();
  }, []);
  return theme;
}

const hex = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const mix = (a: string, b: string, t: number) => `rgb(${hex(a).map((v, i) => Math.round(v + (hex(b)[i] - v) * t)).join(',')})`;

/** Low values recede into the surface: light steps first on a light page, dark steps first on a dark one. */
function sequential(t: number, theme: Theme): string {
  const ramp = theme === 'light' ? BLUE : [...BLUE].reverse();
  const x = Math.max(0, Math.min(1, t)) * (ramp.length - 1);
  const i = Math.min(ramp.length - 2, Math.floor(x));
  return mix(ramp[i], ramp[i + 1], x - i);
}

function diverging(value: number, span: number, theme: Theme): string {
  const p = DIVERGING[theme];
  const t = Math.max(-1, Math.min(1, value / span));
  return t < 0 ? mix(p.mid, p.low, -t) : mix(p.mid, p.high, t);
}

const LAYERS: Record<Layer, { label: string; unit: string; value: (c: CellRow) => number | null }> = {
  angle: { label: 'Angle above the horizon', unit: '°', value: (c) => c.angleDeg },
  minutes: { label: 'Minutes in view per day', unit: ' min', value: (c) => c.minutes },
  pfd: { label: 'Worst-case pfd', unit: ' dB', value: (c) => c.pfdDb },
  margin: { label: 'Margin to the RR limit', unit: ' dB', value: (c) => c.marginDb },
};

const fmt = (v: number | null, unit: string, digits = 1) => (v === null ? '–' : `${v.toFixed(digits)}${unit}`);
const signedFmt = (v: number | null) => (v === null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)} dB`);
const refBw = (hz?: number) => (!hz ? '' : hz >= 1e6 ? `${hz / 1e6} MHz` : `${hz / 1e3} kHz`);

export function FindingMap({ findingId }: { findingId: string }) {
  const { data, error, loading } = useLoad(() => api.getCoverage(findingId), [findingId]);
  if (!api.capabilities.coverage) return null;
  return (
    <section className="panel">
      <h2>Reach over Finland</h2>
      {loading && <p className="muted" role="status">Working out where this satellite can reach. The first map for an issue reads the whole file, so it can take a few seconds.</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      {data && <MapBody c={data} />}
    </section>
  );
}

function MapBody({ c }: { c: Coverage }) {
  const theme = useTheme();
  const available = (Object.keys(LAYERS) as Layer[]).filter((l) => c.cells.some((cell) => LAYERS[l].value(cell) !== null));
  const [layer, setLayer] = useState<Layer>(available[0] ?? 'angle');
  const [showStations, setShowStations] = useState(c.stations.total > 0);
  const [hover, setHover] = useState<{ cell: CellRow; x: number; y: number } | null>(null);

  const geo = useMemo(() => {
    const lons = c.boundary.flat().map((p) => p[0]);
    const lats = c.boundary.flat().map((p) => p[1]);
    const [lonMin, lonMax, latMin, latMax] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
    const k = Math.cos(((latMin + latMax) / 2) * Math.PI / 180); // keeps distances roughly true at mid-latitude
    const scale = 40; // svg units per degree of latitude
    const x = (lon: number) => (lon - lonMin) * k * scale;
    const y = (lat: number) => (latMax - lat) * scale;
    const path = c.boundary.map((ring) => `M${ring.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('L')}Z`).join('');
    return { x, y, path, width: x(lonMax), height: y(latMin), cw: c.cell.lonStep * k * scale, ch: c.cell.latStep * scale };
  }, [c]);

  const spec = LAYERS[layer];
  const values = c.cells.map(spec.value).filter((v): v is number => v !== null);
  const [lo, hi] = values.length ? [Math.min(...values), Math.max(...values)] : [0, 1];
  const span = Math.max(Math.abs(lo), Math.abs(hi), 0.1);
  const colour = (v: number) => (layer === 'margin' ? diverging(v, span, theme) : sequential(hi > lo ? (v - lo) / (hi - lo) : 0.5, theme));
  const pointsOrBins = c.stations.points ?? [];
  const bins = c.stations.bins ?? [];
  const maxBin = Math.max(1, ...bins.map((b) => b.count));
  const noReach = c.mapped && c.cells.some((cell) => cell.angleDeg === null);
  const clipId = `fi-${c.issueNo}-${layer}`;

  return (
    <>
      <p className="muted">
        {c.satellites.join(', ') || 'This satellite'}{c.gsoLonDeg !== null ? ` at ${c.gsoLonDeg}° in the geostationary orbit` : c.orbit === 'ngso' ? ', non-geostationary' : ''}.
        {' '}There’s no beam footprint in the filing, so this shows where it can reach, not where its beam points.
      </p>
      {!c.mapped && <p className="notice notice-warn">{c.notes[0] ?? 'Its position couldn’t be worked out from the filing, so reach can’t be mapped.'}</p>}

      {c.mapped && (
        <div className="map-controls" role="group" aria-label="Map layer">
          {available.map((l) => <button key={l} type="button" className="btn btn-secondary" aria-pressed={layer === l} onClick={() => setLayer(l)}>{LAYERS[l].label}</button>)}
          {c.stations.total > 0 && <label className="check"><input type="checkbox" checked={showStations} onChange={(e) => setShowStations(e.target.checked)} /> Listed stations ({c.stations.total.toLocaleString('en-GB')})</label>}
        </div>
      )}

      <div className="map-layout">
        <div className="map-frame" onMouseLeave={() => setHover(null)}>
          <svg viewBox={`-4 -4 ${geo.width + 8} ${geo.height + 8}`} role="img" aria-label={`Map of Finland: ${spec.label.toLowerCase()}, from ${fmt(lo, spec.unit)} to ${fmt(hi, spec.unit)}`}>
            <defs>
              <clipPath id={clipId}><path d={geo.path} /></clipPath>
              <pattern id={`${clipId}-hatch`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" className="map-hatch" />
              </pattern>
            </defs>
            <path d={geo.path} className="map-land" />
            {c.mapped && (
              <g clipPath={`url(#${clipId})`}>
                {c.cells.map((cell, i) => {
                  const v = spec.value(cell);
                  const fill = v !== null ? colour(v) : cell.angleDeg === null ? `url(#${clipId}-hatch)` : 'none';
                  return (
                    <rect key={i} x={geo.x(cell.lon) - geo.cw / 2} y={geo.y(cell.lat) - geo.ch / 2} width={geo.cw + 0.8} height={geo.ch + 0.8} fill={fill} shapeRendering="crispEdges"
                      onMouseEnter={() => setHover({ cell, x: geo.x(cell.lon) / (geo.width + 8), y: geo.y(cell.lat) / (geo.height + 8) })} />
                  );
                })}
              </g>
            )}
            <path d={geo.path} className="map-border" />
            {showStations && pointsOrBins.map((s) => <circle key={s.id} cx={geo.x(s.lon)} cy={geo.y(s.lat)} r="3.2" className="map-station"><title>{`${s.id}${s.licence ? `, ${s.licence}` : ''}`}</title></circle>)}
            {showStations && bins.map((b) => <circle key={`${b.lat},${b.lon}`} cx={geo.x(b.lon)} cy={geo.y(b.lat)} r={2.5 + 6 * Math.sqrt(b.count / maxBin)} className="map-station"><title>{`${b.count.toLocaleString('en-GB')} stations`}</title></circle>)}
            {hover && <rect x={geo.x(hover.cell.lon) - geo.cw / 2} y={geo.y(hover.cell.lat) - geo.ch / 2} width={geo.cw} height={geo.ch} className="map-hover" />}
          </svg>
          {hover && (
            <div className="map-tip" style={{ left: `${hover.x * 100}%`, top: `${hover.y * 100}%` }} role="status">
              <strong>{hover.cell.lat.toFixed(2)}° N, {hover.cell.lon.toFixed(2)}° E</strong>
              {hover.cell.angleDeg === null ? <span>Never above the horizon</span> : <>
                <span>Angle {fmt(hover.cell.angleDeg, '°')}</span>
                {hover.cell.minutes !== null && <span>In view {hover.cell.minutes} min a day</span>}
                {hover.cell.pfdDb !== null && <span>pfd {fmt(hover.cell.pfdDb, ` dB(W/m²/${refBw(c.pfd.refBwHz)})`)}</span>}
                {hover.cell.marginDb !== null && <span>Margin {signedFmt(hover.cell.marginDb)}</span>}
              </>}
            </div>
          )}
        </div>

        <div className="map-side">
          {c.mapped && values.length > 0 && (
            <div className="map-legend">
              <p className="field-label">{spec.label}{layer === 'pfd' ? `, dB(W/m²) in ${refBw(c.pfd.refBwHz)}` : ''}</p>
              <div className="map-ramp" style={{ background: `linear-gradient(to right, ${[0, 0.25, 0.5, 0.75, 1].map((t) => colour(lo + (hi - lo) * t)).join(',')})` }} />
              <div className="map-ramp-ticks"><span>{layer === 'margin' ? signedFmt(lo) : fmt(lo, spec.unit)}</span>{layer === 'margin' && lo < 0 && hi > 0 && <span>0 dB</span>}<span>{layer === 'margin' ? signedFmt(hi) : fmt(hi, spec.unit)}</span></div>
              {layer === 'margin' && <p className="fine">Above 0 dB, the worst-case pfd is over the {c.pfd.maskId} limit at that angle.</p>}
              {noReach && <p className="map-key"><span className="map-swatch map-swatch-hatch" /> Never above the horizon</p>}
              {showStations && c.stations.total > 0 && <p className="map-key"><span className="map-swatch map-swatch-station" /> {bins.length ? 'Listed stations, sized by count per cell' : 'Listed station in these bands'}</p>}
            </div>
          )}
          <Summary c={c} />
        </div>
      </div>

      {c.mapped && c.notes.length > 0 && <ul className="fine">{c.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      <details className="map-details">
        <summary>How this map is made</summary>
        <ul>{c.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
        {c.pfd.available ? (
          <p>pfd uses group {c.pfd.groupId} ({c.pfd.fLowMhz}–{c.pfd.fHighMhz} MHz): {c.pfd.powerInRefBwDbw} dBW in {refBw(c.pfd.refBwHz)} and {c.pfd.gainDbi} dBi, the strongest transmission in this case’s bands.{c.pfd.maskId ? ` Margin is against ${c.pfd.maskId}.` : ' No single RR limit covers it, so no margin is shown.'}</p>
        ) : <p>No pfd layer: {c.pfd.reason}</p>}
      </details>
    </>
  );
}

function Summary({ c }: { c: Coverage }) {
  if (!c.mapped) {
    return c.stations.total > 0 ? <StationClasses c={c} /> : null;
  }
  const reached = c.cells.filter((x) => x.angleDeg !== null);
  const pct = Math.round((100 * reached.length) / Math.max(1, c.cells.length));
  const stat = (pick: (x: CellRow) => number | null) => {
    const v = c.cells.map(pick).filter((n): n is number => n !== null);
    return v.length ? [Math.min(...v), Math.max(...v)] as const : null;
  };
  const rows: [string, readonly [number, number] | null, (v: number) => string][] = [
    ['Angle', stat((x) => x.angleDeg), (v) => `${v.toFixed(1)}°`],
    ['Minutes in view', stat((x) => x.minutes), (v) => `${v}`],
    [`pfd, dB in ${refBw(c.pfd.refBwHz)}`, stat((x) => x.pfdDb), (v) => v.toFixed(1)],
    ['Margin, dB', stat((x) => x.marginDb), (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}`],
  ];
  const over = c.cells.filter((x) => (x.marginDb ?? -1) > 0).length;
  return (
    <>
      <p><strong>{pct === 100 ? 'All of Finland' : `${pct}% of Finland`}</strong> is in view{c.orbit === 'ngso' ? ' at some point in the day flown' : ''}.{over > 0 ? ` The worst-case pfd is over the limit in ${Math.round((100 * over) / c.cells.length)}% of it.` : ''}</p>
      <table className="map-table">
        <thead><tr><th>Across Finland</th><th className="num">Lowest</th><th className="num">Highest</th></tr></thead>
        <tbody>{rows.filter(([, s]) => s).map(([name, s, f]) => <tr key={name}><td>{name}</td><td className="num">{f(s![0])}</td><td className="num">{f(s![1])}</td></tr>)}</tbody>
      </table>
      {c.stations.total > 0 && <StationClasses c={c} />}
    </>
  );
}

function StationClasses({ c }: { c: Coverage }) {
  return (
    <p className="fine">
      {c.stations.total.toLocaleString('en-GB')} listed station{c.stations.total === 1 ? '' : 's'} in these bands: {Object.entries(c.stations.byClass).map(([k, n]) => `${k} ${n.toLocaleString('en-GB')}`).join(', ')}
      {c.stations.withoutLocation > 0 ? `; ${c.stations.withoutLocation} without coordinates, not drawn` : ''}.
    </p>
  );
}
