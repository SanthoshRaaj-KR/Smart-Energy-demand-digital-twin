import React, { useState } from 'react';
import { runSimulation } from '../api';
import { Card, SectionHeader, Button, Badge } from '../components/Primitives';
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

const CONFIG = [
  { key: 'simulation_days',          label: 'Simulation Days',           value: '1',    type: 'number' },
  { key: 'green_mode',               label: 'Green Mode (Carbon Tariff)',value: 'true', type: 'bool'   },
  { key: 'seed',                     label: 'Random Seed',               value: '42',   type: 'number' },
  { key: 'lgb_inference',            label: 'LightGBM Inference',        value: 'true', type: 'bool'   },
  { key: 'llm_approval_probability', label: 'LLM Safety Approval %',     value: '90',   type: 'number' },
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
        {/* ── Left column ── */}
        <div className="sim-left">

          {/* Config */}
          <Card style={{ marginBottom: 12 }}>
            <SectionHeader title="Configuration" subtitle="run_simulation.py parameters" />
            <div className="config-table">
              {CONFIG.map((c) => (
                <div key={c.key} className="config-row">
                  <span className="config-key mono">{c.key}</span>
                  <span className={`config-val mono ${c.type === 'bool' ? (c.value === 'true' ? 'val-green' : 'val-dim') : 'val-blue'}`}>
                    {c.value}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* Run button + status */}
          <div className="sim-run">
            <Button variant="primary" onClick={handleRun} loading={running} disabled={running}>
              {running ? 'Running simulation...' : '▷  Run Simulation'}
            </Button>
            {done && (
              <div className="sim-result">
                <Badge label="COMPLETE" variant="green" />
                <span className="sim-result-msg">
                  Refresh Grid Status &amp; Dispatch Log pages to see updated data.
                </span>
              </div>
            )}
          </div>

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
        </div>

        {/* ── Right column — reference ── */}
        <div className="sim-right">
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
