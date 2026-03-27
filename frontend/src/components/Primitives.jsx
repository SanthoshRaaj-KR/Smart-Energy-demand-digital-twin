import React from 'react';
import './Primitives.css';

/* ── Badge ── */
export function Badge({ label, variant = 'neutral' }) {
  return <span className={`badge badge--${variant}`}>{label}</span>;
}

export function RiskBadge({ risk }) {
  const map = { LOW: 'green', MEDIUM: 'amber', HIGH: 'red', CRITICAL: 'red', UNKNOWN: 'neutral' };
  const icons = { LOW: '●', MEDIUM: '●', HIGH: '●', CRITICAL: '⬥', UNKNOWN: '○' };
  return (
    <span className={`badge badge--${map[risk] || 'neutral'}`}>
      {icons[risk] || '○'} {risk}
    </span>
  );
}

/* ── Card ── */
export function Card({ children, className = '' }) {
  return <div className={`card ${className}`}>{children}</div>;
}

/* ── Section header ── */
export function SectionHeader({ title, subtitle, right }) {
  return (
    <div className="section-header">
      <div>
        <div className="section-header__title">{title}</div>
        {subtitle && <div className="section-header__sub">{subtitle}</div>}
      </div>
      {right && <div className="section-header__right">{right}</div>}
    </div>
  );
}

/* ── Stat cell ── */
export function Stat({ label, value, unit, color }) {
  return (
    <div className="stat">
      <div className="stat__label">{label}</div>
      <div className="stat__value mono" style={color ? { color } : {}}>
        {value}{unit && <span className="stat__unit"> {unit}</span>}
      </div>
    </div>
  );
}

/* ── Loading skeleton ── */
export function Skeleton({ h = 20, w = '100%' }) {
  return <div className="skeleton" style={{ height: h, width: w }} />;
}

/* ── Meter bar ── */
export function Meter({ value, max = 1, color }) {
  const pct = Math.min(Math.max(value / max, 0), 1) * 100;
  return (
    <div className="meter">
      <div
        className="meter__fill"
        style={{ width: `${pct}%`, background: color || 'var(--blue)' }}
      />
    </div>
  );
}

/* ── Button ── */
export function Button({ children, onClick, loading, variant = 'default', disabled }) {
  return (
    <button
      className={`btn btn--${variant}`}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading ? <span className="spinner" /> : null}
      {children}
    </button>
  );
}
