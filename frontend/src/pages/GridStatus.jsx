import React, { useEffect, useState } from 'react';
import { fetchGridStatus, runIntelligence } from '../api';
import { Card, SectionHeader, Stat, Skeleton, Meter, Badge, Button } from '../components/Primitives';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import './GridStatus.css';

function NodeCard({ node }) {
  const surplus = node.balance_mw > 0;
  const soc = node.battery ? node.battery.soc : null;

  const socColor =
    soc === null ? null :
    soc > 0.7 ? 'var(--green)' :
    soc > 0.35 ? 'var(--amber)' :
    'var(--red)';

  return (
    <Card className="node-card">
      <div className="node-card__header">
        <div className="node-card__id mono">{node.id}</div>
        <div className="node-card__name">{node.name}</div>
        <Badge
          label={surplus ? `+${node.balance_mw.toFixed(0)} MW` : `${node.balance_mw.toFixed(0)} MW`}
          variant={surplus ? 'green' : 'red'}
        />
      </div>

      <div className="node-card__stats">
        <Stat label="Generation" value={node.generation_mw.toLocaleString()} unit="MW" />
        <Stat label="Demand (adj)" value={node.adjusted_demand_mw.toFixed(0)} unit="MW" />
        <Stat
          label="Balance"
          value={`${surplus ? '+' : ''}${node.balance_mw.toFixed(0)}`}
          unit="MW"
          color={surplus ? 'var(--green)' : 'var(--red)'}
        />
      </div>

      {soc !== null && (
        <div className="node-card__battery">
          <div className="node-card__batt-row">
            <span className="node-card__batt-label">Battery SoC</span>
            <span className="node-card__batt-val mono" style={{ color: socColor }}>
              {(soc * 100).toFixed(0)}%
            </span>
          </div>
          <Meter value={soc} max={1} color={socColor} />
          <div className="node-card__batt-mwh mono">
            {node.battery.charge.toFixed(0)} / {node.battery.capacity} MWh
          </div>
        </div>
      )}
    </Card>
  );
}

function EdgeTable({ edges }) {
  return (
    <div className="edge-table">
      <table>
        <thead>
          <tr>
            <th>Corridor</th>
            <th>Distance</th>
            <th>Flow</th>
            <th>Capacity</th>
            <th>Congestion</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((e) => {
            const cong = e.congestion;
            const congColor = cong > 0.7 ? 'var(--red)' : cong > 0.4 ? 'var(--amber)' : 'var(--green)';
            return (
              <tr key={`${e.src}-${e.dst}`}>
                <td className="mono">{e.src} → {e.dst}</td>
                <td className="mono dim">{e.distance_km} km</td>
                <td className="mono">{e.flow_mw.toLocaleString()} MW</td>
                <td className="mono dim">{e.capacity_mw.toLocaleString()} MW</td>
                <td>
                  <div className="edge-cong">
                    <Meter value={cong} max={1} color={congColor} />
                    <span className="mono" style={{ color: congColor }}>{(cong * 100).toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function BalanceChart({ nodes }) {
  const data = nodes.map((n) => ({ name: n.id, balance: n.balance_mw }));
  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} barSize={28}>
        <XAxis dataKey="name" tick={{ fill: 'var(--text-dim)', fontSize: 11, fontFamily: 'IBM Plex Mono' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: 'var(--text-dim)', fontSize: 10, fontFamily: 'IBM Plex Mono' }} axisLine={false} tickLine={false} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 2, fontFamily: 'IBM Plex Mono', fontSize: 11 }}
          labelStyle={{ color: 'var(--text-hi)' }}
          itemStyle={{ color: 'var(--text)' }}
          formatter={(v) => [`${v.toFixed(0)} MW`, 'Balance']}
        />
        <Bar dataKey="balance" radius={[2, 2, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.balance >= 0 ? 'var(--green)' : 'var(--red)'} fillOpacity={0.8} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function GridStatus() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState('');

  const loadGridStatus = async () => {
    setError('');
    try {
      const d = await fetchGridStatus();
      setData(d);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(`Grid status fetch failed: ${err.message || err}`);
    } finally {
      setLoading(false);
      setBusy(false);
    }
  };

  useEffect(() => {
    loadGridStatus();
    const id = setInterval(loadGridStatus, 12000);
    return () => clearInterval(id);
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="page__header">
          <div className="page__title">Grid Status</div>
        </div>
        <div className="node-grid">
          {[0,1,2,3].map((i) => <Card key={i}><div style={{padding:16}}><Skeleton h={120} /></div></Card>)}
        </div>
      </div>
    );
  }

  const totalGen = data.nodes.reduce((s, n) => s + n.generation_mw, 0);
  const totalDem = data.nodes.reduce((s, n) => s + n.adjusted_demand_mw, 0);

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <div className="page__title">Grid Status</div>
          <div className="page__sub">Real-time node balances, battery SoC &amp; transmission congestion</div>
          {lastUpdated && <div className="page__sub">Last updated: {lastUpdated}</div>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              loadGridStatus();
            }}
          >
            Refresh /api/grid-status
          </Button>
          <Button
            variant="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await runIntelligence();
                await loadGridStatus();
              } catch (err) {
                setError(`Generate intelligence failed: ${err.message || err}`);
                setBusy(false);
              }
            }}
          >
            Run /api/generate-intelligence
          </Button>
        </div>
      </div>
      {error && <Card style={{ marginBottom: 12, padding: 12, color: 'var(--red)', fontSize: 12 }}>{error}</Card>}

      {/* Summary strip */}
      <div className="summary-strip">
        <Stat label="Total Generation" value={totalGen.toLocaleString()} unit="MW" />
        <Stat label="Total Demand (adj)" value={totalDem.toFixed(0)} unit="MW" />
        <Stat
          label="System Balance"
          value={`${totalGen - totalDem > 0 ? '+' : ''}${(totalGen - totalDem).toFixed(0)}`}
          unit="MW"
          color={totalGen >= totalDem ? 'var(--green)' : 'var(--red)'}
        />
        <Stat label="Active Nodes" value={data.nodes.length} />
      </div>

      {/* Balance chart */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader title="Node Balance (MW)" subtitle="Generation minus adjusted demand" />
        <div style={{ padding: '16px 8px 8px' }}>
          <BalanceChart nodes={data.nodes} />
        </div>
      </Card>

      {/* Node cards */}
      <div className="node-grid">
        {data.nodes.map((n) => <NodeCard key={n.id} node={n} />)}
      </div>

      {/* Edge table */}
      <Card style={{ marginTop: 16 }}>
        <SectionHeader title="Transmission Corridors" subtitle={`${data.edges.length} edges`} />
        <EdgeTable edges={data.edges} />
      </Card>
    </div>
  );
}
