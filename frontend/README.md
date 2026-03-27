# Grid Twin UI

React frontend for the **India Grid Digital Twin** simulation.

## Directory Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Primitives.jsx      # Shared UI: Badge, Card, Stat, Meter, Button, Skeleton
│   │   ├── Primitives.css
│   │   ├── Sidebar.jsx         # Left nav
│   │   └── Sidebar.css
│   ├── pages/
│   │   ├── GridStatus.jsx      # Node balances, battery SoC, edge congestion
│   │   ├── GridStatus.css
│   │   ├── Intelligence.jsx    # LLM multipliers, risk levels, detected events
│   │   ├── Intelligence.css
│   │   ├── DispatchLog.jsx     # Dispatch records (standard, syndicate, negotiated)
│   │   ├── DispatchLog.css
│   │   ├── Simulation.jsx      # Run simulation, terminal log, pipeline reference
│   │   └── Simulation.css
│   ├── api.js                  # Data service layer (mock → replace with real fetch)
│   ├── App.jsx
│   ├── App.css
│   ├── index.js
│   └── index.css
├── package.json
└── README.md
```

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Grid Status | `grid` | Node gen/demand/balance, battery SoC, edge congestion |
| Intelligence | `intelligence` | LLM multipliers (EDM, GCM, temp anomaly), risk badges, detected events |
| Dispatch Log | `dispatch` | All dispatch records — standard, syndicate, negotiated. Click to expand details |
| Simulation | `simulation` | Run pipeline, animated terminal log, pipeline phase reference |

## Setup

```bash
cd frontend
npm install
npm start
```

Opens at `http://localhost:3000`.

## Connecting to the Backend

All data calls are in `src/api.js`. Each function currently returns mock data.

To wire up the real backend, replace each function with a `fetch` call. Example:

```js
// Before (mock)
export async function fetchGridStatus() {
  await delay(400);
  return { nodes: [...], edges: [...] };
}

// After (real backend)
export async function fetchGridStatus() {
  const res = await fetch('/api/grid-status');
  return res.json();
}
```

The `"proxy": "http://localhost:8000"` in `package.json` forwards `/api/*`
requests to your Python backend in dev mode.

### Suggested API endpoints

| Function | Endpoint | Source |
|----------|----------|--------|
| `fetchGridStatus()` | `GET /api/grid-status` | `grid_physics.GridEnvironment` |
| `fetchIntelligence()` | `GET /api/intelligence` | `outputs/context_cache/node_*.json` |
| `fetchDispatchLog()` | `GET /api/dispatch-log` | `RoutingAgent.clear_market()` result |
| `runSimulation()` | `POST /api/run-simulation` | Triggers `run_simulation.py` |
