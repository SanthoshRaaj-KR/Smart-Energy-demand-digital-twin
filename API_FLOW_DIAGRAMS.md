# Smart Grid Simulation - API Flow Diagrams

This document provides detailed visual flowcharts for common API interactions and data flows.

---

## 1. Complete Application Startup Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    USER STARTS APPLICATION                   │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │   Terminal 1 │        │   Terminal 2 │
        │              │        │              │
        │  cd backend  │        │ cd frontend  │
        │  uvicorn ... │        │  npm run dev │
        └──────────────┘        └──────────────┘
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │   FastAPI    │        │   Next.js    │
        │  Port 8000   │◄───────│  Port 3000   │
        │              │  HTTP  │              │
        └──────────────┘        └──────────────┘
                │
                ▼
        ┌──────────────┐
        │    Engine    │
        │  - APrioriBrain
        │  - StochasticTrigger
        │  - UnifiedOrchestrator
        └──────────────┘
                │
                ▼
        ┌──────────────┐
        │   Outputs/   │
        │    Cache     │
        └──────────────┘
```

---

## 2. Home Page Load Sequence

```
User navigates to http://localhost:3000/
                │
                ▼
┌──────────────────────────────────────┐
│   Next.js renders app/page.js        │
│   - Mounts HomePage component        │
│   - Initializes usePipeline hook     │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│   usePipeline Hook Executes          │
│   (autoStart: true)                  │
└──────────────────────────────────────┘
                │
                ├─────────────────────────┐
                ▼                         ▼
    ┌────────────────────┐    ┌────────────────────┐
    │ GET /api/grid-     │    │ GET /api/v2/       │
    │ status             │    │ pipeline-bundle    │
    └────────────────────┘    └────────────────────┘
                │                         │
                ▼                         ▼
    ┌────────────────────┐    ┌────────────────────┐
    │ Returns:           │    │ Returns:           │
    │ - nodes[]          │    │ - intelligence     │
    │ - edges[]          │    │ - grid_status      │
    │ - battery SOC      │    │ - dialogue_log     │
    │                    │    │ - frequency_status │
    └────────────────────┘    └────────────────────┘
                │                         │
                └─────────┬───────────────┘
                          ▼
            ┌──────────────────────────┐
            │ React State Updated      │
            │ - nodes, edges           │
            │ - intelligence           │
            │ - stage, stageHistory    │
            └──────────────────────────┘
                          │
                          ▼
            ┌──────────────────────────┐
            │ UI Components Render     │
            │ - GridMap (animated)     │
            │ - LiveStatRow            │
            │ - RegionStatusRow        │
            │ - ForecastChart          │
            │ - PipelineStatusBar      │
            └──────────────────────────┘
```

---

## 3. Pipeline Page Execution Flow

```
User navigates to /pipeline
            │
            ▼
┌─────────────────────────────────┐
│  Render pipeline/page.js        │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Single API Call                │
│  GET /api/v2/pipeline-bundle    │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Backend Aggregates Data        │
│  from Multiple Sources:         │
│  - legacy_intelligence()        │
│  - legacy_grid_status()         │
│  - legacy_simulation_result()   │
│  - legacy_demand_forecast()     │
│  - get_dialogue_log()           │
│  - get_frequency_status()       │
│  - _get_cache_items()           │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Returns Bundle JSON            │
│  {                              │
│    status: "success",           │
│    data: {                      │
│      intelligence: {...},       │
│      grid_status: {...},        │
│      simulation_result: {...},  │
│      forecast: {...},           │
│      dialogue_log: {...},       │
│      frequency_status: {...},   │
│      intelligence_cache: {...}  │
│    }                            │
│  }                              │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Frontend Renders:              │
│  - Stage timeline               │
│  - Dialogue log (animated)      │
│  - Frequency monitor            │
│  - Intelligence cache explorer  │
└─────────────────────────────────┘
```

---

## 4. Simulation Execution Flow (Full Cycle)

```
User clicks "Run Simulation" button
            │
            ▼
┌─────────────────────────────────┐
│  POST /api/v2/simulate          │
│  ?start_date=2026-04-01         │
│  &days=30                       │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  UnifiedOrchestrator.run()      │
│  (backend/simulator.py)         │
└─────────────────────────────────┘
            │
            ├──────────────────────┐
            ▼                      ▼
    ┌──────────────┐      ┌──────────────┐
    │  Load Grid   │      │ Load Daily   │
    │  Config      │      │ Intelligence │
    └──────────────┘      └──────────────┘
            │                      │
            └──────────┬───────────┘
                       ▼
        ┌───────────────────────────┐
        │ For Each Day (0 to 29):   │
        └───────────────────────────┘
                       │
                       ▼
        ┌───────────────────────────┐
        │ Stage 3: Waterfall Routing│
        │                           │
        │ 1. Battery Resolution     │
        │    └─ Check SOC           │
        │    └─ Charge/Discharge    │
        │                           │
        │ 2. DR Auction             │
        │    └─ Demand Response     │
        │    └─ Agentic Negotiation │
        │                           │
        │ 3. BFS Transmission       │
        │    └─ Find shortest path  │
        │    └─ Check capacity      │
        │                           │
        │ 4. Fallback               │
        │    └─ Controlled deficit  │
        └───────────────────────────┘
                       │
                       ▼
        ┌───────────────────────────┐
        │ Stage 4: XAI Audit        │
        │                           │
        │ - Log decisions           │
        │ - Generate explanations   │
        │ - Memory warnings         │
        └───────────────────────────┘
                       │
                       ▼
        ┌───────────────────────────┐
        │ Save to outputs/          │
        │ - simulation_result.json  │
        │ - xai_daily_audit.json    │
        │ - dispatch_log.json       │
        └───────────────────────────┘
                       │
                       ▼
        ┌───────────────────────────┐
        │ Return Response           │
        │ {                         │
        │   status: "success",      │
        │   data: {                 │
        │     days_simulated: 30,   │
        │     summary: {...}        │
        │   }                       │
        │ }                         │
        └───────────────────────────┘
```

---

## 5. Intelligence Generation Flow

```
User triggers intelligence generation
            │
            ▼
┌─────────────────────────────────┐
│  POST /api/generate-intelligence│
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  SmartGridIntelligenceAgent     │
│  Orchestrator Initializes       │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  For Each Region (DEL, MUM,     │
│  BLR, KOL):                     │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Phase 1: News     │
    │ Gathering         │
    │ - Fetch headlines │
    │ - Filter relevant │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Phase 2: Signal   │
    │ Extraction        │
    │ - Map to grid     │
    │ - Extract impact  │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Phase 3: LLM      │
    │ Analysis          │
    │ - Generate deltas │
    │ - Confidence      │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Phase 4: Baseline │
    │ Integration       │
    │ - Merge LightGBM  │
    │ - Adjust forecast │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Phase 5: Cache    │
    │ - Save JSON       │
    │ - Update context  │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Save to:                       │
│  outputs/context_cache/         │
│  node_{region}_{date}.json      │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Return Response                │
│  {                              │
│    status: "success",           │
│    regions_processed: 4,        │
│    cache_updated: true          │
│  }                              │
└─────────────────────────────────┘
```

---

## 6. Forecast Calculation Flow

```
Frontend requests forecast
            │
            ▼
┌─────────────────────────────────┐
│  GET /api/demand-forecast       │
│  (7-day)                        │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Backend Loads:                 │
│  - LightGBM model               │
│  - Historical data              │
│  - Intelligence cache           │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ For Each Day      │
    │ (0 to 6):         │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ LightGBM Baseline │
    │ - Load features   │
    │ - Predict demand  │
    │ - Calculate conf  │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Apply Intelligence│
    │ Delta             │
    │ - Get multiplier  │
    │ - Adjust forecast │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Calculate Bands   │
    │ - Upper bound     │
    │ - Lower bound     │
    │ - Confidence int  │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Return Response                │
│  {                              │
│    DEL: [                       │
│      {                          │
│        day: 0,                  │
│        forecast_mw: 1200,       │
│        confidence: 0.85,        │
│        upper_bound: 1250,       │
│        lower_bound: 1150        │
│      }, ...                     │
│    ],                           │
│    MUM: [...],                  │
│    BLR: [...],                  │
│    KOL: [...]                   │
│  }                              │
└─────────────────────────────────┘
```

---

## 7. Agentic Dialogue Flow (Feature 1)

```
Simulation encounters deficit
            │
            ▼
┌─────────────────────────────────┐
│  Prosumer Agent Activated       │
│  (Needs 50MW)                   │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Turn 1: Request   │
    │                   │
    │ "I need 50MW      │
    │  from grid due to │
    │  heatwave spike"  │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Syndicate Agent Responds       │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Turn 2: Offer     │
    │                   │
    │ "Available at     │
    │  ₹5.2/kWh from    │
    │  neighboring grid"│
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Orchestrator Agent Decides     │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Turn 3: Decision  │
    │                   │
    │ "Approved. Trans- │
    │  fer via DEL→MUM  │
    │  line (80% cap)"  │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Log to dialogue_log            │
│  {                              │
│    day_index: 5,                │
│    turns: [                     │
│      {agent: "Prosumer", ...},  │
│      {agent: "Syndicate", ...}, │
│      {agent: "Orchestrator",...}│
│    ],                           │
│    outcome: "approved",         │
│    power_mw: 50                 │
│  }                              │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Frontend Displays (animated)   │
│  - Turn 1 (500ms pause)         │
│  - Turn 2 (500ms pause)         │
│  - Turn 3 (final)               │
└─────────────────────────────────┘
```

---

## 8. Frequency Monitoring Flow (Feature 3)

```
Grid frequency deviation detected
            │
            ▼
┌─────────────────────────────────┐
│  FrequencyMonitor               │
│  (in simulator.py)              │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Check Frequency   │
    │ Current: 49.2 Hz  │
    │ Nominal: 50.0 Hz  │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Compare Threshold │
    │ Lifeboat: 49.5 Hz │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ TRIGGER ALERT!    │
    │ 49.2 < 49.5       │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Log Event                      │
│  {                              │
│    timestamp: "10:30:00",       │
│    frequency_hz: 49.2,          │
│    threshold_hz: 49.5,          │
│    status: "critical",          │
│    action: "lifeboat_engaged"   │
│  }                              │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  GET /api/v2/frequency-status   │
│  Returns:                       │
│  {                              │
│    summary: {                   │
│      current_hz: 49.2,          │
│      threshold_hz: 49.5,        │
│      status: "critical"         │
│    },                           │
│    event_log: [...]             │
│  }                              │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Frontend Displays              │
│  - Frequency gauge (red)        │
│  - Event timeline               │
│  - Alert badge                  │
└─────────────────────────────────┘
```

---

## 9. Error Handling Flow

```
User requests data
            │
            ▼
┌─────────────────────────────────┐
│  GET /api/intelligence          │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Check Cache       │
    │ Exists?           │
    └───────────────────┘
            │
      ┌─────┴─────┐
      ▼           ▼
   YES           NO
      │           │
      │           ▼
      │    ┌──────────────┐
      │    │ Return Empty │
      │    │ Default Data │
      │    │ (Graceful)   │
      │    └──────────────┘
      │           │
      └───────┬───┘
              ▼
    ┌───────────────────┐
    │ Return Response   │
    │ status: 200       │
    └───────────────────┘

    ──────────────────

User triggers action with error
            │
            ▼
┌─────────────────────────────────┐
│  POST /api/v2/simulate          │
│  ?days=200  (exceeds max!)      │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Validation Fails  │
    │ days > 90         │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Return 422        │
    │ Unprocessable     │
    │ Entity            │
    │                   │
    │ {                 │
    │   detail: [       │
    │     {             │
    │       msg: "value"│
    │       type: "..."│
    │     }             │
    │   ]               │
    │ }                 │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Frontend Displays Error        │
│  - Toast notification           │
│  - Error message                │
│  - Suggested fix                │
└─────────────────────────────────┘
```

---

## 10. Cache Invalidation Flow

```
Intelligence data is stale
            │
            ▼
┌─────────────────────────────────┐
│  GET /api/v2/intelligence/5     │
│  ?force_refresh=true            │
└─────────────────────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ Check Cache       │
    │ day_005.json      │
    └───────────────────┘
            │
            ▼
    ┌───────────────────┐
    │ force_refresh?    │
    │ YES               │
    └───────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Delete Cached File             │
│  outputs/intelligence_cache/    │
│  day_005.json                   │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Regenerate Intelligence        │
│  - StochasticTrigger.generate() │
│  - Save new cache               │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│  Return Fresh Data              │
│  {                              │
│    status: "success",           │
│    data: {...},                 │
│    cached_at: "2026-04-08..."   │
│  }                              │
└─────────────────────────────────┘
```

---

**For complete route details, see [ROUTES_DOCUMENTATION.md](./ROUTES_DOCUMENTATION.md)**
