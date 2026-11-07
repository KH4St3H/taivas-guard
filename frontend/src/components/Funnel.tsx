import { useState } from 'react';
import type { FunnelStage } from '../api/types';

/** Horizontal bars for one ordered series. Each row's hover and focus text gives its share of the previous stage. */
export function Funnel({ stages }: { stages: FunnelStage[] }) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(...stages.map((s) => s.n), 1);
  return (
    <ol className="funnel">
      {stages.map((s, i) => {
        const prev = i > 0 ? stages[i - 1].n : null;
        const share = prev ? Math.round((s.n / prev) * 100) : null;
        const open = active === s.key;
        return (
          <li
            key={s.key}
            className="funnel-row"
            tabIndex={0}
            onMouseEnter={() => setActive(s.key)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(s.key)}
            onBlur={() => setActive(null)}
            aria-label={`${s.label}: ${s.n.toLocaleString('en-GB')}${share !== null ? `, ${share}% of the previous stage` : ''}`}
          >
            <div className="funnel-text">
              <span className="funnel-label">{s.label}</span>
              <span className="funnel-value">{s.n.toLocaleString('en-GB')}</span>
            </div>
            <div className="funnel-track">
              <div className="funnel-bar" style={{ width: `${Math.max((s.n / max) * 100, s.n > 0 ? 0.8 : 0)}%` }} />
            </div>
            {open && share !== null && <div className="funnel-tip" role="tooltip">{share}% of the previous stage</div>}
          </li>
        );
      })}
    </ol>
  );
}
