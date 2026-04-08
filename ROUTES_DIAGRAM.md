# Smart Grid Simulation - Routes Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js)                               │
│                        Port: 3000                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTP Requests
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                │
│                        Port: 8000                                        │
│                                                                          │
│  ┌────────────────────┐              ┌──────────────────────┐          │
│  │   Legacy Routes    │              │     V2 Routes        │          │
│  │   (routes.py)      │              │   (server.py)        │          │
│  └────────────────────┘              └──────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Frontend Routes → Backend API Mapping

### 1. Home Dashboard (`/`)

```
┌──────────────────────┐
│   Home Dashboard     │
│   (app/page.js)      │
└──────────────────────┘
          │
          ├─→ GET /api/grid-status              (Live grid topology)
          ├─→ GET /api/intelligence             (Forecast calculations)
          └─→ GET /api/v2/pipeline-bundle       (Pipeline status bar)
```

**Features:**
- Live Grid Topology Map
- Real-time Grid Status (4 stat cards)
- Regional Status (4 region cards)
- 7-Day Demand Forecast Chart
- Feature Capability Cards

---

### 2. Intelligence Page (`/intelligence`)

```
┌──────────────────────┐
│  Delta Intelligence  │
│ (intelligence/page)  │
└──────────────────────┘
          │
          ├─→ GET /api/intelligence                     (Intelligence context)
          ├─→ GET /api/intelligence/{region_id}/audit   (XAI phase breakdown)
          └─→ GET /api/intelligence/{region_id}/signals (Infrastructure signals)
```

**Features:**
- LightGBM Baseline Display
- LLM Delta Anomaly Detection
- Regional Intelligence Breakdown
- Phase-by-Phase XAI Audit

---

### 3. Forecast Page (`/forecast`)

```
┌──────────────────────┐
│  Demand Forecasting  │
│   (forecast/page)    │
└──────────────────────┘
          │
          ├─→ GET /api/demand-forecast          (7-day forecasts)
          └─→ GET /api/demand-forecast-30day    (30-day forecasts)
```

**Features:**
- 7-Day Regional Forecasts
- 30-Day Extended Projections
- Confidence Intervals
- Uncertainty Bands
- Weather Extrapolation

---

### 4. Pipeline Page (`/pipeline`)

```
┌──────────────────────┐
│  Stage-by-Stage      │
│  Pipeline View       │
│  (pipeline/page)     │
└──────────────────────┘
          │
          ├─→ GET /api/v2/pipeline-bundle           (Complete bundle)
          ├─→ GET /api/v2/dialogue-log              (Agentic negotiations)
          ├─→ GET /api/v2/frequency-status          (Grid frequency)
          └─→ GET /api/v2/intelligence-cache        (Daily cache)
```

**Features:**
- 4-Stage Pipeline Visualization
- Agentic Dialogue Log (animated)
- Grid Frequency Monitoring
- Intelligence Cache Explorer
- Legacy Pipeline Integration

---

### 5. Simulation Page (`/simulation`)

```
┌──────────────────────┐
│  Waterfall + XAI     │
│  (simulation/page)   │
└──────────────────────┘
          │
          ├─→ GET /api/simulation-result       (Simulation results)
          ├─→ GET /api/xai-audit-ledger        (XAI audit)
          └─→ GET /api/dispatch-log            (Dispatch log)
```

**Features:**
- Waterfall Routing Results
- XAI Audit Ledger
- Dispatch Execution Log
- Self-Healing Analysis

---

### 6. Costs Page (`/costs`)

```
┌──────────────────────┐
│   Cost Analysis      │
│    (costs/page)      │
└──────────────────────┘
          │
          ├─→ GET /api/cost-savings        (Cost savings)
          └─→ GET /api/cost-tracking       (Cost breakdown)
```

**Features:**
- Orchestration Cost Tracking
- Daily Cost Breakdown
- Savings Analysis
- Aggregate Metrics

---

### 7. Stages Page (`/stages`)

```
┌──────────────────────┐
│   Stage Details      │
│   (stages/page)      │
└──────────────────────┘
          │
          └─→ (Custom stage breakdown visualization)
```

**Features:**
- Detailed Stage Explanations
- Stage 1: Planner
- Stage 2: Delta Intelligence
- Stage 3: Waterfall Routing
- Stage 4: Memory & XAI

---

## Backend API Routes Hierarchy

### Legacy API (`routes.py`)

```
/api
├── health                             [GET]   Health check
├── orchestration-status               [GET]   Engine status
│
├── intelligence                       [GET]   Intelligence context
├── generate-intelligence              [POST]  Generate intelligence
├── intelligence/{region_id}
│   ├── audit                          [GET]   XAI phase breakdown
│   └── signals                        [GET]   Infrastructure signals
│
├── grid-status                        [GET]   Grid topology + data
├── dispatch-log                       [GET]   Dispatch log
│
├── run-simulation                     [POST]  Stream simulation
├── simulation-result                  [GET]   Simulation JSON
├── xai-audit-ledger                   [GET]   XAI ledger
│
├── demand-forecast                    [GET]   7-day forecast
├── demand-forecast-30day              [GET]   30-day forecast
│
├── cost-savings                       [GET]   Cost savings
└── cost-tracking                      [GET]   Cost tracking
```

### V2 API (`server.py`)

```
/api/v2
├── health                             [GET]   V2 health check
│
├── master-schedule                    [POST]  Generate schedule
├── simulate                           [POST]  Run simulation
│
├── intelligence/{day_index}           [GET]   Daily intelligence
├── intelligence-cache                 [GET]   All cache summaries
├── intelligence-cache/{day_index}     [GET]   Specific day cache
│
├── dialogue-log                       [GET]   Agentic negotiations
├── frequency-status                   [GET]   Grid frequency
└── pipeline-bundle                    [GET]   Complete integration
```

---

## Data Flow Diagram

### Complete Request Flow

```
┌─────────────┐         ┌─────────────┐         ┌──────────────┐
│   Browser   │  HTTP   │   Next.js   │  API    │   FastAPI    │
│             │ ──────→ │  Frontend   │ ──────→ │   Backend    │
│  localhost  │         │  (Port 3000)│         │  (Port 8000) │
│   :3000     │         │             │         │              │
└─────────────┘         └─────────────┘         └──────────────┘
      ↑                       │                         │
      │                       │                         ↓
      │                       │                  ┌──────────────┐
      │                       │                  │  Engine.py   │
      │                       │                  │Intelligence.│
      │                       │                  │Simulator.py │
      │                       │                  └──────────────┘
      │                       │                         │
      │                       │                         ↓
      │                       │                  ┌──────────────┐
      │                       ↓                  │   Outputs/   │
      └───────────── JSON Response ────────────  │   Cache      │
                                                 └──────────────┘
```

### Stage Pipeline Flow

```
Stage 1: Planner
    ↓
[APrioriBrain]
    ↓
master_schedule.json
    ↓
Stage 2: Delta Intelligence
    ↓
[StochasticTrigger]
    ↓
intelligence_cache/day_*.json
    ↓
Stage 3: Waterfall Routing
    ↓
[UnifiedOrchestrator]
    ├─→ Battery Resolution
    ├─→ DR Auction
    ├─→ BFS Transmission
    └─→ Fallback
    ↓
Stage 4: Memory & XAI
    ↓
[XAI Audit Ledger]
    ↓
xai_daily_audit.json
```

---

## API Response Examples

### Grid Status Response

```json
{
  "nodes": [
    {
      "id": "DEL",
      "name": "Delhi",
      "demand_mw": 1200.5,
      "generation_mw": 1150.0,
      "balance_mw": -50.5,
      "battery": {
        "soc": 0.75,
        "capacity_mwh": 500
      }
    }
  ],
  "edges": [
    {
      "from": "DEL",
      "to": "MUM",
      "flow_mw": 100.0,
      "capacity_mw": 500.0,
      "congestion": false
    }
  ]
}
```

### Intelligence Response

```json
{
  "DEL": {
    "grid_multipliers": {
      "demand_multiplier": 1.05,
      "seven_day_demand_forecast_mw_delta": 50.2
    },
    "news_signals": [
      {
        "headline": "Heatwave Alert",
        "impact": "High",
        "confidence": 0.85
      }
    ]
  }
}
```

### Dialogue Log Response

```json
{
  "status": "success",
  "total_entries": 3,
  "entries": [
    {
      "day_index": 5,
      "turn": 1,
      "agent": "Prosumer",
      "message": "Requesting 50MW from grid",
      "timestamp": "2026-04-06T10:30:00"
    }
  ]
}
```

---

## WebSocket Support (Future)

Currently, all communication is HTTP-based. For real-time updates, the frontend uses:
- Polling with `usePipeline` hook
- Auto-refresh intervals

**Potential Future Enhancement:**
```
WebSocket Endpoint: ws://localhost:8000/ws
├── /ws/grid-status          (Real-time grid updates)
├── /ws/dialogue             (Live dialogue stream)
└── /ws/frequency            (Frequency monitoring)
```

---

## Route Protection & Authentication

**Current State:** No authentication required (development mode)

**Production Recommendations:**
- Add JWT authentication for API routes
- Implement rate limiting
- Add request validation middleware
- Enable HTTPS

---

## Performance Optimization

### Caching Strategy

```
Frontend (Next.js):
├── Static Generation (SSG) for /stages
├── Client-side caching with React hooks
└── SWR/React Query for API requests

Backend (FastAPI):
├── File-based caching (outputs/intelligence_cache/)
├── In-memory caching for frequently accessed data
└── Lazy loading for large datasets
```

### Response Streaming

The `/api/run-simulation` endpoint uses Server-Sent Events (SSE) for real-time streaming:

```python
@app.post("/api/run-simulation")
async def run_simulation():
    return StreamingResponse(
        simulate_generator(),
        media_type="text/plain"
    )
```

---

## Testing Routes

### Backend (FastAPI Swagger)

Navigate to: `http://localhost:8000/docs`

Interactive API documentation with:
- Try-it-out functionality
- Request/response schemas
- Example payloads

### Frontend (Browser Dev Tools)

1. Open browser console
2. Go to Network tab
3. Navigate to any page
4. View API calls in real-time

### Automated Testing

```bash
# Backend tests (if available)
cd backend
pytest

# Frontend tests (if available)
cd frontend
npm test
```

---

## Troubleshooting Routes

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| CORS Error | Frontend/Backend port mismatch | Verify ports 3000 (frontend) and 8000 (backend) |
| 404 Not Found | Route doesn't exist | Check ROUTES_DOCUMENTATION.md |
| 500 Server Error | Backend crash | Check backend terminal logs |
| Empty Response | Cache not populated | Run `POST /api/generate-intelligence` first |

---

**For complete route details, see [ROUTES_DOCUMENTATION.md](./ROUTES_DOCUMENTATION.md)**
