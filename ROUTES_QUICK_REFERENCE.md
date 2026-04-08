# Quick Routes Reference Card

**Last Updated:** 2026-04-08

---

## 🎯 Frontend Pages (localhost:3000)

| URL | Page | Key Features |
|-----|------|--------------|
| `/` | Home Dashboard | Grid topology, live status, 7-day forecast |
| `/intelligence` | Delta Intelligence | LightGBM baseline, LLM deltas, XAI audit |
| `/forecast` | Demand Forecasting | 7-day & 30-day forecasts with confidence |
| `/pipeline` | Pipeline View | 4-stage flow, dialogue log, frequency monitor |
| `/simulation` | Waterfall + XAI | Simulation results, audit ledger |
| `/costs` | Cost Analysis | Cost tracking, savings analysis |
| `/stages` | Stage Details | Detailed stage explanations |

---

## 🔌 Backend API Endpoints (localhost:8000)

### Most Commonly Used

```bash
# Health Check
GET /api/health
GET /api/v2/health

# Get Grid Data
GET /api/grid-status                          # Live grid topology & node data

# Intelligence
GET /api/intelligence                         # All intelligence data
GET /api/v2/intelligence/{day_index}          # Daily intelligence for specific day

# Simulation
POST /api/v2/simulate?days=30                 # Run simulation
GET /api/simulation-result                    # Get results

# Forecasting
GET /api/demand-forecast                      # 7-day forecast
GET /api/demand-forecast-30day                # 30-day forecast

# Pipeline Integration
GET /api/v2/pipeline-bundle                   # Everything in one call
```

---

## 🔥 Quick cURL Commands

### Generate & Run

```bash
# Generate master schedule
curl -X POST "http://localhost:8000/api/v2/master-schedule?start_date=2026-04-01&days=30"

# Run simulation
curl -X POST "http://localhost:8000/api/v2/simulate?start_date=2026-04-01&days=30"

# Generate intelligence
curl -X POST "http://localhost:8000/api/generate-intelligence"
```

### Fetch Data

```bash
# Grid status
curl http://localhost:8000/api/grid-status

# Intelligence
curl http://localhost:8000/api/intelligence

# Dialogue log for day 5
curl "http://localhost:8000/api/v2/dialogue-log?day_index=5&limit=10"

# Frequency status
curl http://localhost:8000/api/v2/frequency-status

# Pipeline bundle
curl http://localhost:8000/api/v2/pipeline-bundle
```

### Regional Data

```bash
# Intelligence audit for Delhi
curl http://localhost:8000/api/intelligence/DEL/audit

# Infrastructure signals for Mumbai
curl http://localhost:8000/api/intelligence/MUM/signals
```

---

## 🗺️ Route Mapping Cheat Sheet

| Frontend Page | Backend APIs Used |
|---------------|-------------------|
| `/` (Home) | `/api/grid-status`, `/api/intelligence`, `/api/v2/pipeline-bundle` |
| `/intelligence` | `/api/intelligence`, `/api/intelligence/{id}/audit`, `/api/intelligence/{id}/signals` |
| `/forecast` | `/api/demand-forecast`, `/api/demand-forecast-30day` |
| `/pipeline` | `/api/v2/pipeline-bundle`, `/api/v2/dialogue-log`, `/api/v2/frequency-status` |
| `/simulation` | `/api/simulation-result`, `/api/xai-audit-ledger`, `/api/dispatch-log` |
| `/costs` | `/api/cost-savings`, `/api/cost-tracking` |

---

## 📊 Response Format Examples

### Grid Status

```json
{
  "nodes": [
    {"id": "DEL", "demand_mw": 1200, "generation_mw": 1150, "balance_mw": -50}
  ],
  "edges": [
    {"from": "DEL", "to": "MUM", "flow_mw": 100, "capacity_mw": 500}
  ]
}
```

### Intelligence

```json
{
  "DEL": {
    "grid_multipliers": {
      "demand_multiplier": 1.05,
      "seven_day_demand_forecast_mw_delta": 50.2
    }
  }
}
```

### Pipeline Bundle

```json
{
  "status": "success",
  "data": {
    "intelligence": {...},
    "grid_status": {...},
    "simulation_result": {...},
    "forecast": {...},
    "dialogue_log": {...},
    "frequency_status": {...}
  }
}
```

---

## 🔑 Valid Region IDs

```
DEL  →  Delhi
MUM  →  Mumbai
BLR  →  Bangalore
KOL  →  Kolkata
```

---

## ⚙️ Query Parameters Quick Guide

### `/api/v2/master-schedule`

```bash
?start_date=2026-04-01    # ISO date format
&days=30                  # Range: 1-90
```

### `/api/v2/intelligence/{day_index}`

```bash
/{day_index}              # Path param: 0, 1, 2, ...
?start_date=2026-04-01    # ISO date format
&force_refresh=true       # Boolean: true/false
```

### `/api/v2/simulate`

```bash
?start_date=2026-04-01    # ISO date format
&days=30                  # Range: 1-90
```

### `/api/v2/dialogue-log`

```bash
?limit=50                 # Range: 1-500
&day_index=5              # -1 for all days
```

### `/api/xai-audit-ledger`

```bash
?date_str=2026-04-05      # ISO date format (optional)
&day_index=5              # Integer (optional)
```

---

## 🚀 Startup Commands

### Backend

```bash
cd backend
uvicorn server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

---

## 📍 Important URLs

```
Frontend:       http://localhost:3000
Backend API:    http://localhost:8000
Swagger Docs:   http://localhost:8000/docs
Redoc Docs:     http://localhost:8000/redoc
```

---

## 🐛 Debug Helpers

### Check if services are running

```bash
# Windows
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Linux/Mac
lsof -i :3000
lsof -i :8000
```

### Test backend connectivity

```bash
curl http://localhost:8000/api/health
```

### View backend logs

Check the terminal where `uvicorn` is running

### View frontend logs

1. Open browser console (F12)
2. Go to Network tab
3. Monitor API calls

---

## 💡 Pro Tips

1. **Use Pipeline Bundle:** Instead of calling multiple APIs, use `/api/v2/pipeline-bundle` for frontend integration

2. **Cache Intelligence:** Intelligence data is cached. Use `force_refresh=true` if you need fresh data

3. **Streaming Simulation:** `/api/run-simulation` returns streaming text, not JSON

4. **Region-Specific Data:** Use `/api/intelligence/{region_id}/audit` for XAI breakdowns

5. **Interactive Docs:** Visit `http://localhost:8000/docs` to test APIs directly in browser

---

## 📚 Full Documentation

For complete details, see:
- [ROUTES_DOCUMENTATION.md](./ROUTES_DOCUMENTATION.md) - Complete route reference
- [ROUTES_DIAGRAM.md](./ROUTES_DIAGRAM.md) - Architecture diagrams
- [README.md](./README.md) - Project overview

---

**Print this page for quick reference while developing!**
