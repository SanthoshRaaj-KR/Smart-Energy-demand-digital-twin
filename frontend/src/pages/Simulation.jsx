import React, { useState } from 'react';
import { runSimulation, runIntelligence } from '../api';
import { Card, SectionHeader, Button, Badge } from '../components/Primitives';
import EndpointRunner from '../components/EndpointRunner';
import './Simulation.css';

const PIPELINE_PHASES = [
  { label: 'DataFetcher',          desc: 'Weather + news + RSS — no LLM',          icon: '⬇' },
  { label: 'CityIntelAgent',       desc: 'City profile — cache-first',              icon: '◈' },
  { label: 'EventRadarAgent',      desc: 'Mass event + broadcast detection',        icon: '◎' },
  { label: 'FilterAgent',          desc: 'Noise kill — quality gate',               icon: '⌖' },
  { label: 'SignalExtractorAgent', desc: 'Infrastructure supply-chain signals',     icon: '⊡' },
  { label: 'ImpactNarratorAgent',  desc: 'Expert narrative — chain-of-thought',     icon: '✎' },
  { label: 'MultiplierSynthAgent', desc: 'Numeric JSON multipliers — terminal',     icon: '⊞' },
];

const MARKET_PHASES = [
  { label: 'StateAgent (per city)', desc: 'net_mw + battery SoC + LLM context → BUY/SELL order', icon: '◐' },
  { label: 'SyndicateBroker',       desc: 'Pool sellers to fulfill large buyer orders',            icon: '◑' },
  { label: 'RoutingAgent',          desc: 'DLR + carbon tariff + LLM safety → DispatchRecords',   icon: '⇄' },
  { label: 'BatteryPhase',          desc: 'Absorb surplus / cover residual deficit',               icon: '⊟' },
];

function lineColor(line) {
  if (line.includes('SYNDICATE'))  return 'var(--blue)';
  if (line.includes('DISPATCH') || line.includes('NEGOTIATED')) return 'var(--green)';
  if (line.includes('PANIC'))      return 'var(--red)';
  if (line.includes('DONE') || line.includes('complete')) return 'var(--amber)';
  if (line.includes('ERROR') || line.includes('WARN'))    return 'var(--red)';
  return 'var(--text-dim)';
}

export default function Simulation() {
  const [running, setRunning]   = useState(false);
  const [done, setDone]         = useState(false);
  const [log, setLog]           = useState([]);

  const handleRun = async () => {
    setRunning(true);
    setDone(false);
    setLog([]);

    await runSimulation((line) => {
      setLog((prev) => [...prev, line]);
    });

    setRunning(false);
    setDone(true);
  };

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <div className="page__title">Simulation</div>
          <div className="page__sub">Run the India Grid Digital Twin pipeline end-to-end</div>
        </div>
      </div>

      <div className="sim-layout">
        {/* Left column - Workflow Controls */}
        <div className="sim-left" style={{ maxWidth: 600 }}>


          {/* Workflow Steps */}
          <div style={{ marginBottom: 12 }}>
            <SectionHeader title="Workflow" subtitle="3-step pipeline" />
          </div>

          {/* Step 1: Generate Intelligence */}
          <Card style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <Badge label="STEP 1" variant="blue" />
              <span style={{ marginLeft: 8, fontSize: '0.95rem', fontWeight: 500 }}>Generate Intelligence</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: 12 }}>
              Run the 7-phase LLM pipeline to analyze grid state, detect events, and compute risk multipliers.
            </div>
            <Button
              variant="primary"
              onClick={async () => {
                setRunning(true);
                setLog(['[STEP 1] Starting intelligence pipeline...']);
                try {
                  const result = await runIntelligence();
                  setLog((prev) => [...prev, `✓ Intelligence generated: ${result.nodes_generated || 0} nodes`]);
                  setLog((prev) => [...prev, `✓ Date: ${result.date}`]);
                  setLog((prev) => [...prev, '']);
                  setLog((prev) => [...prev, '→ STEP 1 COMPLETE. Proceed to Step 2 (Generate Intelligence) or Step 3 (Simulate).']);
                } catch (err) {
                  setLog((prev) => [...prev, `✗ Error: ${err.message || err}`]);
                } finally {
                  setRunning(false);
                }
              }}
              disabled={running}
              style={{ width: '100%' }}
            >
              {running ? '⟳ Generating...' : '► Generate Intelligence'}
            </Button>
          </Card>

          {/* Step 2: Optionally Fetch Intelligence Details */}
          <Card style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <Badge label="STEP 2" variant="blue" />
              <span style={{ marginLeft: 8, fontSize: '0.95rem', fontWeight: 500 }}>Review Intelligence (Optional)</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: 12 }}>
              After generating intelligence, view details in the "Intelligence" page (risk flags, events, weather, narratives).
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button variant="secondary" disabled style={{ flex: 1 }}>
                → See Grid Status Page
              </Button>
              <Button variant="secondary" disabled style={{ flex: 1 }}>
                → See Intelligence Page
              </Button>
            </div>
          </Card>

          {/* Step 3: Run Simulation */}
          <Card style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <Badge label="STEP 3" variant="blue" />
              <span style={{ marginLeft: 8, fontSize: '0.95rem', fontWeight: 500 }}>Run Simulation</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginBottom: 12 }}>
              Execute market clearing: pool BUY/SELL orders, route power with DLR + carbon tariff, and generate dispatch log.
            </div>
            <Button
              variant="primary"
              onClick={handleRun}
              loading={running}
              disabled={running}
              style={{ width: '100%' }}
            >
              {running ? '⟳ Running simulation...' : '► Run Simulation'}
            </Button>
            {done && (
              <div className="sim-result" style={{ marginTop: 12 }}>
                <Badge label="COMPLETE" variant="green" />
                <span className="sim-result-msg" style={{ marginLeft: 8 }}>
                  View Dispatch Log &amp; Grid Status for results.
                </span>
              </div>
            )}
          </Card>

          {/* Terminal */}
          {log.length > 0 && (
            <Card style={{ marginTop: 12 }}>
              <SectionHeader title="Output Log" subtitle={`${log.length} lines`} />
              <div className="sim-terminal">
                {log.map((line, i) => (
                  <div key={i} className="sim-line mono" style={{ color: lineColor(line) }}>
                    <span className="sim-line__idx dim">{String(i + 1).padStart(2, '0')}</span>
                    {line}
                  </div>
                ))}
                {running && <div className="sim-cursor" />}
              </div>
            </Card>
          )}

          <EndpointRunner />
        </div>

        {/* Right column - Architecture Reference */}
        <div className="sim-right" style={{ minWidth: 350 }}>
          <div style={{ marginBottom: 12 }}>
            <SectionHeader title="Reference Docs" subtitle="Architecture & pipeline details" />
          </div>

          <Card style={{ marginBottom: 12 }}>
            <SectionHeader title="Intelligence Pipeline" subtitle="7-phase LLM agent chain" />
            <div className="pipeline">
              {PIPELINE_PHASES.map((p, i) => (
                <div key={p.label} className="pipeline-step">
                  <div className="pipeline-step__left">
                    <div className="pipeline-step__num">{p.icon}</div>
                    {i < PIPELINE_PHASES.length - 1 && <div className="pipeline-step__line" />}
                  </div>
                  <div className="pipeline-step__body">
                    <div className="pipeline-step__label">{p.label}</div>
                    <div className="pipeline-step__desc">{p.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeader title="Market Clearing" subtitle="Per simulation day" />
            <div className="pipeline">
              {MARKET_PHASES.map((p, i) => (
                <div key={p.label} className="pipeline-step">
                  <div className="pipeline-step__left">
                    <div className="pipeline-step__num">{p.icon}</div>
                    {i < MARKET_PHASES.length - 1 && <div className="pipeline-step__line" />}
                  </div>
                  <div className="pipeline-step__body">
                    <div className="pipeline-step__label">{p.label}</div>
                    <div className="pipeline-step__desc">{p.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
