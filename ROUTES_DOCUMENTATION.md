# Smart Grid Simulation - Complete Routes Documentation

**Last Updated:** 2026-04-08

This document provides a comprehensive overview of all routes available in the Smart Grid Simulation application, including both backend API endpoints and frontend pages.

---

## 📑 Table of Contents

- [Backend API Routes](#backend-api-routes)
  - [Legacy Routes (routes.py)](#legacy-routes-routespy)
  - [V2 Routes (server.py)](#v2-routes-serverpy)
- [Frontend Pages](#frontend-pages)
- [Route Mapping](#route-mapping)
- [Quick Start](#quick-start)

---

## Backend API Routes

**Base URL:** `http://localhost:8000`

### Legacy Routes (routes.py)

#### Health & Status

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/api/health` | None | Health check - returns status and current date |
| `GET` | `/api/orchestration-status` | None | Returns current orchestration engine status (state, config, last_run_date) |

#### Intelligence & Analysis

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `POST` | `/api/generate-intelligence` | None | Runs the intelligence pipeline to generate new intelligence data for all regions |
| `GET` | `/api/intelligence` | None | Returns complete intelligence context from cache files |
| `GET` | `/api/intelligence/{region_id}/audit` | `region_id` (path) | Returns detailed phase-by-phase breakdown of intelligence generation for XAI visualization |
| `GET` | `/api/intelligence/{region_id}/signals` | `region_id` (path) | Returns extracted infrastructure signals for a region |

**Example:**
```bash
# Get intelligence for Delhi
GET /api/intelligence/DEL/audit
```

#### Grid Operations

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/api/grid-status` | None | Returns complete grid status with node generation/demand data, edges with flow/congestion, and battery SOC |
| `GET` | `/api/dispatch-log` | None | Returns the latest dispatch log from simulation results |

#### Simulation & Results

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `POST` | `/api/run-simulation` | None | Streams simulation output in real-time (text/plain streaming response) |
| `GET` | `/api/simulation-result` | None | Returns latest simulation result JSON (dispatches, summary, date) |
| `GET` | `/api/xai-audit-ledger` | `date_str` (optional)<br>`day_index` (optional) | Returns XAI daily audit ledger; optionally filtered by date and day_index |

**Example:**
```bash
# Get audit ledger for day 5
GET /api/xai-audit-ledger?day_index=5
```

#### Forecasting

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/api/demand-forecast` | None | Returns 7-day demand forecasts from LightGBM model with confidence and adjusted demand by region |
| `GET` | `/api/demand-forecast-30day` | None | Returns 30-day extended forecasts with confidence decay, uncertainty bands, and weather extrapolation |

#### Cost & Tracking

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/api/cost-savings` | None | Returns orchestration cost-savings rows and aggregate summary (total cost, savings %, etc.) |
| `GET` | `/api/cost-tracking` | None | Returns complete cost tracking data with daily breakdown and summary metrics |

---

### V2 Routes (server.py)

#### Health & Status

| Method | Endpoint | Parameters | Description |
|--------|----------|------------|-------------|
| `GET` | `/api/v2/health` | None | V2 service health check |

#### Intelligence & Cache

| Method | Endpoint | Query Parameters | Description |
|--------|----------|------------------|-------------|
| `GET` | `/api/v2/intelligence/{day_index}` | `start_date` (default: "2026-04-01")<br>`force_refresh` (default: false) | Generates daily intelligence report for a specific day index |
| `GET` | `/api/v2/intelligence-cache` | None | Returns all available daily intelligence cache summaries |
| `GET` | `/api/v2/intelligence-cache/{day_index}` | None | Returns full intelligence cache payload for a specific day |

**Example:**
```bash
# Get intelligence for day 10 with refresh
GET /api/v2/intelligence/10?start_date=2026-04-01&force_refresh=true

# Get all cache summaries
GET /api/v2/intelligence-cache
```

#### Grid Operations & Simulation

| Method | Endpoint | Query Parameters | Description |
|--------|----------|------------------|-------------|
| `POST` | `/api/v2/master-schedule` | `start_date` (default: "2026-04-01")<br>`days` (default: 30, range: 1-90) | Generates 30-day master schedule using APrioriBrain |
| `POST` | `/api/v2/simulate` | `start_date` (default: "2026-04-01")<br>`days` (default: 30, range: 1-90) | Runs unified simulator for specified date range |
| `GET` | `/api/v2/frequency-status` | None | Returns grid frequency status, Lifeboat trigger threshold, and frequency event log |

**Example:**
```bash
# Generate master schedule for 15 days
POST /api/v2/master-schedule?start_date=2026-04-01&days=15

# Run simulation
POST /api/v2/simulate?start_date=2026-04-01&days=30
```

#### Agentic Features

| Method | Endpoint | Query Parameters | Description |
|--------|----------|------------------|-------------|
| `GET` | `/api/v2/dialogue-log` | `limit` (default: 50, range: 1-500)<br>`day_index` (default: -1 for all) | Returns agentic negotiation dialogue log (3-turn JSON chats per trade) |

**Example:**
```bash
# Get last 100 dialogue entries for day 3
GET /api/v2/dialogue-log?limit=100&day_index=3
```

#### Integration

| Method | Endpoint | Query Parameters | Description |
|--------|----------|------------------|-------------|
| `GET` | `/api/v2/pipeline-bundle` | `limit` (default: 25, range: 1-200) | Single integration payload bundling legacy pipeline data with v2 dialogue/frequency outputs |

**Example:**
```bash
# Get complete pipeline bundle
GET /api/v2/pipeline-bundle?limit=50
```

---

## Frontend Pages

**Base URL:** `http://localhost:3000`

### Available Routes

| Route | Page Component | Description |
|-------|----------------|-------------|
| `/` | `app/page.js` | **Home Dashboard** - Live grid topology, real-time status, 7-day forecast, feature cards |
| `/costs` | `app/costs/page.js` | **Cost Analysis** - Orchestration cost tracking and savings analysis |
| `/forecast` | `app/forecast/page.js` | **Demand Forecasting** - 7-day and 30-day demand predictions with confidence intervals |
| `/intelligence` | `app/intelligence/page.js` | **Delta Intelligence** - LightGBM baseline + LLM delta anomaly detection |
| `/pipeline` | `app/pipeline/page.js` | **Stage-by-Stage Pipeline** - Complete 4-stage execution flow with dialogue logs and frequency monitoring |
| `/simulation` | `app/simulation/page.js` | **Waterfall + XAI** - Simulation results with XAI audit ledger |
| `/stages` | `app/stages/page.js` | **Stage Details** - Detailed breakdown of each processing stage |

### Frontend Route Structure

```
src/app/
├── page.js                    → /                (Home Dashboard)
├── costs/page.js              → /costs           (Cost Analysis)
├── forecast/page.js           → /forecast        (Demand Forecasting)
├── intelligence/page.js       → /intelligence    (Delta Intelligence)
├── pipeline/page.js           → /pipeline        (Pipeline View)
├── simulation/page.js         → /simulation      (Waterfall + XAI)
└── stages/page.js             → /stages          (Stage Details)
```

---

## Route Mapping

This section shows which frontend pages consume which backend API endpoints.

### Home Dashboard (`/`)

**APIs Used:**
- `GET /api/grid-status` - Live grid topology and node data
- `GET /api/intelligence` - Intelligence data for forecast calculations
- `GET /api/v2/pipeline-bundle` - Pipeline status bar

### Intelligence Page (`/intelligence`)

**APIs Used:**
- `GET /api/intelligence` - Complete intelligence context
- `GET /api/intelligence/{region_id}/audit` - XAI phase breakdown
- `GET /api/intelligence/{region_id}/signals` - Infrastructure signals

### Forecast Page (`/forecast`)

**APIs Used:**
- `GET /api/demand-forecast` - 7-day forecasts
- `GET /api/demand-forecast-30day` - 30-day extended forecasts

### Pipeline Page (`/pipeline`)

**APIs Used:**
- `GET /api/v2/pipeline-bundle` - Complete pipeline data
- `GET /api/v2/dialogue-log` - Agentic negotiation logs
- `GET /api/v2/frequency-status` - Grid frequency monitoring
- `GET /api/v2/intelligence-cache` - Daily intelligence cache

### Simulation Page (`/simulation`)

**APIs Used:**
- `GET /api/simulation-result` - Latest simulation results
- `GET /api/xai-audit-ledger` - XAI audit ledger
- `GET /api/dispatch-log` - Dispatch execution log

### Costs Page (`/costs`)

**APIs Used:**
- `GET /api/cost-savings` - Cost savings analysis
- `GET /api/cost-tracking` - Detailed cost tracking

---

## Quick Start

### Starting the Backend

```bash
cd backend
# Activate your virtual environment (conda or venv)
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

**Backend will be available at:** `http://localhost:8000`

**API Documentation:** `http://localhost:8000/docs` (Swagger UI)

### Starting the Frontend

```bash
cd frontend
npm install
npm run dev
```

**Frontend will be available at:** `http://localhost:3000`

---

## Route Summary Statistics

### Backend API Routes
- **Total Endpoints:** 24
  - Legacy Routes: 15
  - V2 Routes: 9
- **HTTP Methods:**
  - GET: 20 endpoints
  - POST: 4 endpoints

### Frontend Pages
- **Total Pages:** 7
- **All use Next.js App Router** (file-based routing)

---

## CORS Configuration

The backend is configured to accept requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

**Location:** `backend/routes.py` (lines 31-36)

---

## Notes

1. **Streaming Response:** The `/api/run-simulation` endpoint returns a streaming text response, not JSON.

2. **Cache Behavior:** 
   - Legacy `/api/intelligence` loads from cache only (never regenerates)
   - V2 `/api/v2/intelligence/{day_index}` can force refresh with `force_refresh=true`

3. **Path vs Query Parameters:**
   - Path parameters: `/api/intelligence/{region_id}/audit`
   - Query parameters: `/api/v2/simulate?days=30`

4. **Region IDs:** Valid region IDs for path parameters:
   - DEL (Delhi)
   - MUM (Mumbai)
   - BLR (Bangalore)
   - KOL (Kolkata)

5. **Date Format:** All dates use ISO format: `YYYY-MM-DD` (e.g., "2026-04-01")

---

## Testing Routes

### Using cURL

```bash
# Health check
curl http://localhost:8000/api/health

# Get grid status
curl http://localhost:8000/api/grid-status

# Generate master schedule
curl -X POST "http://localhost:8000/api/v2/master-schedule?days=15"

# Get dialogue log
curl "http://localhost:8000/api/v2/dialogue-log?limit=10&day_index=5"
```

### Using the Browser

Simply navigate to:
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

---

## Troubleshooting

### Backend Not Starting
1. Check if port 8000 is available
2. Ensure all dependencies are installed: `pip install -r requirements.txt`
3. Verify Python version compatibility

### Frontend Not Starting
1. Check if port 3000 is available
2. Run `npm install` to ensure all packages are installed
3. Verify Node.js version (requires Node 18+)

### CORS Errors
1. Ensure backend is running on port 8000
2. Ensure frontend is running on port 3000
3. Check browser console for detailed error messages

---

**For more information, see the main [README.md](./README.md)**
