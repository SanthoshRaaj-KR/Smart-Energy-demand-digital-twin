import React from 'react';
import './Sidebar.css';

const NAV = [
  { id: 'grid',         icon: '⬡', label: 'Grid Status' },
  { id: 'intelligence', icon: '◈', label: 'Intelligence' },
  { id: 'dispatch',     icon: '⇄', label: 'Dispatch Log' },
  { id: 'simulation',   icon: '▷', label: 'Simulation' },
];

export default function Sidebar({ active, onSelect }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__brand-icon">⚡</div>
        <div>
          <div className="sidebar__brand-name">GridTwin</div>
          <div className="sidebar__brand-sub">India Digital Twin</div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map(({ id, icon, label }) => (
          <button
            key={id}
            className={`sidebar__item ${active === id ? 'sidebar__item--active' : ''}`}
            onClick={() => onSelect(id)}
          >
            <span className="sidebar__icon">{icon}</span>
            <span className="sidebar__label">{label}</span>
            {active === id && <span className="sidebar__indicator" />}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__status">
          <span className="sidebar__dot sidebar__dot--live" />
          <span>Live Context Active</span>
        </div>
        <div className="sidebar__version">v1.0 · 4 Regions</div>
      </div>
    </aside>
  );
}
