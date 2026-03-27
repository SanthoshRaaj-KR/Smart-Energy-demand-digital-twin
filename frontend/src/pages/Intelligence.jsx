import React, { useEffect, useState } from 'react';
import { fetchIntelligence } from '../api';
import { Card, SectionHeader, Stat, Skeleton, RiskBadge, Badge, Meter } from '../components/Primitives';
import './Intelligence.css';

const CITY_COLORS = { BHR: '#3d9eff', UP: '#00e5a0', WB: '#ff4560', KAR: '#ffb020' };

function EventChip({ event }) {
  const mechColors = {
    TV_PICKUP: 'blue', HEAVY_INFRA: 'amber', ROUTINE_DISRUPTION: 'neutral', MASS_GATHERING: 'amber'
  };
  return (
    <div className="event-chip">
      <div className="event-chip__row">
        <Badge label={event.grid_mechanism} variant={mechColors[event.grid_mechanism] || 'neutral'} />
        <Badge label={`${event.days_away}d away`} variant="neutral" />
        <Badge label={event.confidence} variant={event.confidence === 'high' ? 'green' : event.confidence === 'medium' ? 'amber' : 'neutral'} />
      </div>
      <div className="event-chip__name">{event.event_name}</div>
      <div className="event-chip__impact">{event.est_mw_impact}</div>
    </div>
  );
}

function MultiplierGauge({ label, value, min, max, neutral = 1.0, unit = '' }) {
  const pct = Math.min(Math.max((value - min) / (max - min), 0), 1);
  const neutralPct = Math.min(Math.max((neutral - min) / (max - min), 0), 1);
  const above = value > neutral;

  return (
    <div className="mult-gauge">
      <div className="mult-gauge__label">{label}</div>
      <div className="mult-gauge__track">
        <div className="mult-gauge__fill" style={{ width: `${pct * 100}%`, background: above ? 'var(--amber)' : 'var(--blue)' }} />
        <div className="mult-gauge__neutral" style={{ left: `${neutralPct * 100}%` }} />
      </div>
      <div className="mult-gauge__value mono" style={{ color: above ? 'var(--amber)' : 'var(--blue)' }}>
        {value > 0 && value !== neutral && (above ? '+' : '')}
        {typeof value === 'number' && unit === '°C' ? value.toFixed(1) : value.toFixed(2)}
        {unit && <span className="dim"> {unit}</span>}
      </div>
    </div>
  );
}

/* Parses the extracted_signals bullet string into individual lines */
function SignalList({ raw }) {
  if (!raw || raw === 'NO GRID-RELEVANT SIGNALS DETECTED.') {
    return <div className="signal-empty">No grid-relevant signals detected.</div>;
  }
  const lines = raw
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.length > 0);

  return (
    <div className="signal-list">
      {lines.map((line, i) => {
        // Extract [TYPE] tag
        const match = line.match(/^\[([A-Z\-]+)\]\s*(.*)/);
        const tag  = match ? match[1] : null;
        const body = match ? match[2] : line;
        const tagColors = {
          'WEATHER': 'blue', 'FUEL-SUPPLY': 'red', 'PLANT': 'red',
          'INDUSTRIAL': 'amber', 'LOGISTICS': 'amber', 'HYDRO': 'blue',
          'GRID-EVENT': 'red', 'POLICY': 'neutral',
        };
        return (
          <div key={i} className="signal-line">
            {tag && <Badge label={tag} variant={tagColors[tag] || 'neutral'} />}
            <span className="signal-body">{body}</span>
          </div>
        );
      })}
    </div>
  );
}

/* Full impact narrative rendered section by section */
function NarrativePanel({ text }) {
  if (!text) return <div className="narrative-empty">No narrative available. Run the intelligence pipeline first.</div>;

  // Split on markdown ## headers
  const sections = text.split(/^## /m).filter(Boolean);

  if (sections.length <= 1) {
    // No headers — just render as plain text
    return <div className="narrative-plain">{text}</div>;
  }

  return (
    <div className="narrative-sections">
      {sections.map((section, i) => {
        const nl = section.indexOf('\n');
        const heading = nl > -1 ? section.slice(0, nl).trim() : section.trim();
        const body    = nl > -1 ? section.slice(nl + 1).trim() : '';
        return (
          <div key={i} className="narrative-section">
            <div className="narrative-heading">{heading}</div>
            <div className="narrative-body">{body}</div>
          </div>
        );
      })}
    </div>
  );
}

function NodeIntelCard({ nodeId, data }) {
  const gm     = data.grid_multipliers || {};
  const accent = CITY_COLORS[nodeId] || 'var(--blue)';
  const [tab, setTab] = useState('overview'); // 'overview' | 'narrative' | 'signals'

  const hasNarrative = !!data.impact_narrative;
  const hasSignals   = !!data.extracted_signals && data.extracted_signals !== 'NO GRID-RELEVANT SIGNALS DETECTED.';

  return (
    <Card className="intel-card">
      {/* Header */}
      <div className="intel-card__header" style={{ borderLeft: `3px solid ${accent}` }}>
        <div className="intel-card__id mono" style={{ color: accent }}>{nodeId}</div>
        <div className="intel-card__city">{data.city}</div>
        <div className="intel-card__badges">
          <RiskBadge risk={gm.demand_spike_risk} />
          {gm.pre_event_hoard && <Badge label="HOARD" variant="red" />}
        </div>
      </div>

      {/* Tab bar */}
      <div className="intel-tabs">
        {['overview', 'narrative', 'signals'].map((t) => (
          <button
            key={t}
            className={`intel-tab ${tab === t ? 'intel-tab--active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'overview'  ? 'Overview'  : null}
            {t === 'narrative' ? <>Narrative {hasNarrative && <span className="tab-dot tab-dot--green" />}</> : null}
            {t === 'signals'   ? <>Signals   {hasSignals   && <span className="tab-dot tab-dot--amber" />}</> : null}
          </button>
        ))}
      </div>

      {/* ── Tab: Overview ── */}
      {tab === 'overview' && (
        <div className="intel-card__body">
          <div className="intel-card__section">
            <div className="intel-section-title">Grid Multipliers</div>
            <MultiplierGauge label="Demand (EDM)"    value={gm.economic_demand_multiplier     || 1} min={0.55} max={1.5}  />
            <MultiplierGauge label="Generation (GCM)" value={gm.generation_capacity_multiplier || 1} min={0.55} max={1.12} />
            <MultiplierGauge label="Temp Anomaly"    value={gm.temperature_anomaly            || 0} min={-10}  max={14} neutral={0} unit="°C" />
          </div>

          <div className="intel-card__stats">
            <Stat label="Supply Risk"  value={<RiskBadge risk={gm.supply_shortfall_risk} />} />
            <Stat label="7-Day ΔMW"
              value={`${(gm.seven_day_demand_forecast_mw_delta || 0) > 0 ? '+' : ''}${gm.seven_day_demand_forecast_mw_delta || 0}`}
              unit="MW"
              color={(gm.seven_day_demand_forecast_mw_delta || 0) > 0 ? 'var(--amber)' : 'var(--blue)'} />
            <Stat label="Confidence"   value={((gm.confidence || 0) * 100).toFixed(0)} unit="%" />
          </div>

          <div className="intel-card__section">
            <div className="intel-section-title">Key Driver</div>
            <div className="intel-card__driver">{gm.key_driver || '—'}</div>
            <div className="intel-card__reasoning">{gm.reasoning || '—'}</div>
          </div>

          <div className="intel-card__conf">
            <Meter
              value={gm.confidence || 0} max={1}
              color={(gm.confidence || 0) > 0.75 ? 'var(--green)' : (gm.confidence || 0) > 0.5 ? 'var(--amber)' : 'var(--red)'}
            />
          </div>

          {data.detected_events && data.detected_events.length > 0 && (
            <div className="intel-card__section">
              <div className="intel-section-title">Detected Events ({data.detected_events.length})</div>
              {data.detected_events.map((ev, i) => <EventChip key={i} event={ev} />)}
            </div>
          )}
        </div>
      )}

      {/* ── Tab: Narrative (ImpactNarratorAgent full output) ── */}
      {tab === 'narrative' && (
        <div className="intel-card__body">
          <div className="intel-card__section narrative-tab">
            <div className="intel-section-title" style={{ marginBottom: 8 }}>
              ImpactNarratorAgent — 7-Day Demand/Supply Analysis
            </div>
            <NarrativePanel text={data.impact_narrative} />
          </div>
        </div>
      )}

      {/* ── Tab: Signals (SignalExtractorAgent output) ── */}
      {tab === 'signals' && (
        <div className="intel-card__body">
          <div className="intel-card__section signals-tab">
            <div className="intel-section-title" style={{ marginBottom: 8 }}>
              SignalExtractorAgent — Grid-Relevant Signals
            </div>
            <SignalList raw={data.extracted_signals} />
          </div>
        </div>
      )}
    </Card>
  );
}

export default function Intelligence() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchIntelligence().then((d) => { setData(d); setLoading(false); });
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="page__header"><div className="page__title">Intelligence</div></div>
        <div className="intel-grid">
          {[0,1,2,3].map((i) => <Card key={i}><div style={{ padding: 16 }}><Skeleton h={300} /></div></Card>)}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <div className="page__title">Intelligence</div>
          <div className="page__sub">
            LLM multipliers · Impact narrative · Extracted grid signals · Detected events
          </div>
        </div>
      </div>
      <div className="intel-grid">
        {Object.entries(data).map(([nodeId, nodeData]) => (
          <NodeIntelCard key={nodeId} nodeId={nodeId} data={nodeData} />
        ))}
      </div>
    </div>
  );
}
