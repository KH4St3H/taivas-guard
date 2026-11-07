import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { api } from '../api';

const NAV = [
  { to: '/', label: 'Latest issue', end: true },
  { to: '/findings', label: 'Findings' },
  { to: '/runs', label: 'Runs' },
  { to: '/reference', label: 'Rules and data' },
];

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0); // Newer browsers return a Promise here, which must not reach React as a cleanup.
  }, [pathname]);
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">IFIC Guard</NavLink>
          <nav aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}>{n.label}</NavLink>
            ))}
          </nav>
          <NavLink to="/analyze" className="btn btn-primary btn-sm topbar-cta">Analyse a file</NavLink>
        </div>
      </header>
      {api.mode === 'sample' && (
        <div className="sample-banner" role="note">
          <strong>Sample mode.</strong> Results come from a one-off screen of real ITU files, not the finished pipeline. They’re prompts for review, not regulatory findings.
        </div>
      )}
      <main id="main" className="page"><Outlet /></main>
    </>
  );
}
