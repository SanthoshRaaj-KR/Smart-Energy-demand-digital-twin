import React, { useEffect, useMemo, useState } from 'react';
import {
  fetchDispatchLog,
  fetchGridStatus,
  fetchHealth,
  fetchIntelligence,
  fetchSimulationResult,
  runIntelligence,
  runSimulation,
} from '../api';
import { Badge, Button, Card, SectionHeader } from './Primitives';
import './EndpointRunner.css';

function nowLabel() {
  return new Date().toLocaleTimeString();
}

export default function EndpointRunner() {
  const [busy, setBusy] = useState({});
  const [snapshots, setSnapshots] = useState({});
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastResponse, setLastResponse] = useState(null);
  const [streamLog, setStreamLog] = useState([]);
  const [error, setError] = useState('');
  const [lastPollAt, setLastPollAt] = useState('');

  const anyBusy = useMemo(() => Object.values(busy).some(Boolean), [busy]);

  const setBusyState = (key, value) => {
    setBusy((prev) => ({ ...prev, [key]: value }));
  };

  const runRead = async (key, label, fn) => {
    setBusyState(key, true);
    setError('');
    try {
      const data = await fn();
      setSnapshots((prev) => ({ ...prev, [key]: data }));
      setLastResponse({ label, data, at: nowLabel() });
      return data;
    } catch (err) {
      setError(`${label} failed: ${err.message || err}`);
      throw err;
    } finally {
      setBusyState(key, false);
    }
  };

  const refreshAll = async () => {
    setBusyState('refreshAll', true);
    try {
      const [health, grid, intelligence, dispatches, simulationResult] = await Promise.all([
        fetchHealth(),
        fetchGridStatus(),
        fetchIntelligence(),
        fetchDispatchLog(),
        fetchSimulationResult(),
      ]);
      setSnapshots({ health, grid, intelligence, dispatches, simulationResult });
      setLastPollAt(nowLabel());
    } catch (err) {
      setError(`Live poll failed: ${err.message || err}`);
    } finally {
      setBusyState('refreshAll', false);
    }
  };

  const runGenerateIntelligence = async () => {
    setBusyState('generateIntelligence', true);
    setError('');
    try {
      const data = await runIntelligence();
      setLastResponse({ label: 'POST /api/generate-intelligence', data, at: nowLabel() });
      await refreshAll();
    } catch (err) {
      setError(`POST /api/generate-intelligence failed: ${err.message || err}`);
    } finally {
      setBusyState('generateIntelligence', false);
    }
  };

  const runSimulationEndpoint = async () => {
    setBusyState('runSimulation', true);
    setError('');
    setStreamLog([]);
    try {
      await runSimulation((line) => {
        setStreamLog((prev) => {
          const next = [...prev, line];
          return next.length > 400 ? next.slice(next.length - 400) : next;
        });
      });
      const latest = await fetchSimulationResult();
      setSnapshots((prev) => ({ ...prev, simulationResult: latest }));
      setLastResponse({ label: 'POST /api/run-simulation', data: latest, at: nowLabel() });
      await refreshAll();
    } catch (err) {
      setError(`POST /api/run-simulation failed: ${err.message || err}`);
    } finally {
      setBusyState('runSimulation', false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const id = setInterval(() => {
      if (!anyBusy) refreshAll();
    }, 10000);
    return () => clearInterval(id);
  }, [autoRefresh, anyBusy]);

  const healthStatus = snapshots.health?.status || 'unknown';
  const nodeCount = snapshots.grid?.nodes?.length || 0;
  const cityCount = snapshots.intelligence ? Object.keys(snapshots.intelligence).length : 0;
  const dispatchCount = snapshots.dispatches?.length || 0;
  const simDate = snapshots.simulationResult?.date || 'n/a';

  return (
    <Card className="endpoint-runner">
      <SectionHeader
        title="Realtime API Control"
        subtitle={lastPollAt ? `Last sync ${lastPollAt}` : 'Syncing route snapshots'}
        right={
          <div className="endpoint-runner__right">
            <Badge label={autoRefresh ? 'AUTO 10S' : 'MANUAL'} variant={autoRefresh ? 'green' : 'neutral'} />
            <Button variant="secondary" disabled={anyBusy} onClick={() => setAutoRefresh((v) => !v)}>
              {autoRefresh ? 'Pause Polling' : 'Resume Polling'}
            </Button>
          </div>
        }
      />

      <div className="endpoint-runner__strip">
        <Badge label={`/api/health: ${healthStatus}`} variant={healthStatus === 'ok' ? 'green' : 'amber'} />
        <Badge label={`/api/grid-status: ${nodeCount} nodes`} variant="blue" />
        <Badge label={`/api/intelligence: ${cityCount} cities`} variant="neutral" />
        <Badge label={`/api/dispatch-log: ${dispatchCount} records`} variant="amber" />
        <Badge label={`/api/simulation-result: ${simDate}`} variant="neutral" />
      </div>

      <div className="endpoint-runner__actions">
        <Button disabled={anyBusy} onClick={() => runRead('health', 'GET /api/health', fetchHealth)}>
          GET /api/health
        </Button>
        <Button disabled={anyBusy} onClick={() => runRead('grid', 'GET /api/grid-status', fetchGridStatus)}>
          GET /api/grid-status
        </Button>
        <Button disabled={anyBusy} onClick={() => runRead('intelligence', 'GET /api/intelligence', fetchIntelligence)}>
          GET /api/intelligence
        </Button>
        <Button disabled={anyBusy} onClick={() => runRead('dispatches', 'GET /api/dispatch-log', fetchDispatchLog)}>
          GET /api/dispatch-log
        </Button>
        <Button disabled={anyBusy} onClick={() => runRead('simulationResult', 'GET /api/simulation-result', fetchSimulationResult)}>
          GET /api/simulation-result
        </Button>
        <Button variant="primary" disabled={anyBusy} onClick={runGenerateIntelligence}>
          POST /api/generate-intelligence
        </Button>
        <Button variant="primary" disabled={anyBusy} onClick={runSimulationEndpoint}>
          POST /api/run-simulation
        </Button>
        <Button variant="secondary" disabled={anyBusy} onClick={refreshAll}>
          Refresh All
        </Button>
      </div>

      {error && <div className="endpoint-runner__error mono">{error}</div>}

      {streamLog.length > 0 && (
        <div className="endpoint-runner__terminal">
          {streamLog.map((line, idx) => (
            <div key={`${idx}-${line.slice(0, 12)}`} className="endpoint-runner__line mono">
              <span className="dim">{String(idx + 1).padStart(3, '0')}</span>
              <span>{line}</span>
            </div>
          ))}
        </div>
      )}

      {lastResponse && (
        <div className="endpoint-runner__json-wrap">
          <div className="endpoint-runner__label mono">
            {lastResponse.label} @ {lastResponse.at}
          </div>
          <pre className="endpoint-runner__json">{JSON.stringify(lastResponse.data, null, 2)}</pre>
        </div>
      )}
    </Card>
  );
}
