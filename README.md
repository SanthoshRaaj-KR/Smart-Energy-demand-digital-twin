# Smart Grid Simulation - India Grid Digital Twin

A phase-by-phase Smart Grid digital twin: forecast baseline, detect deltas, route deficits, and learn from failures with explainable ledgers.

## 📚 Documentation

- **[Complete Routes Documentation](./ROUTES_DOCUMENTATION.md)** - Detailed API endpoints and frontend pages
- **[Routes Architecture Diagram](./ROUTES_DIAGRAM.md)** - Visual route mapping and data flow

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ with conda or venv
- Node.js 18+
- Git

### Installation Steps

```bash
git clone https://github.com/SanthoshRaaj-KR/Smart-Energy-demand-digital-twin
cd Smart-Energy-demand-digital-twin
```

### Terminal 1: Backend (FastAPI)

```bash
cd backend
# Activate your virtual environment using conda or python venv
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

**Backend will be available at:** `http://localhost:8000`

**API Documentation:** `http://localhost:8000/docs`

### Terminal 2: Frontend (Next.js)

```bash
cd frontend 
npm install
npm run dev
```

**Frontend will be available at:** `http://localhost:3000`

---

## 📋 Available Routes

### Frontend Pages

| Route | Description |
|-------|-------------|
| `/` | Home Dashboard - Live grid topology & status |
| `/intelligence` | Delta Intelligence - LightGBM + LLM anomaly detection |
| `/forecast` | Demand Forecasting - 7-day and 30-day predictions |
| `/pipeline` | Stage-by-Stage Pipeline - Complete 4-stage flow |
| `/simulation` | Waterfall + XAI - Simulation results with audit ledger |
| `/costs` | Cost Analysis - Orchestration cost tracking |
| `/stages` | Stage Details - Detailed breakdown of each stage |

### Backend API Endpoints

**Total: 24 endpoints** (15 legacy + 9 v2)

See [ROUTES_DOCUMENTATION.md](./ROUTES_DOCUMENTATION.md) for complete API reference.

---

## 🏗️ Architecture Overview

```
Frontend (Next.js)     Backend (FastAPI)     Engine Layer
─────────────────      ────────────────      ────────────
Port 3000       ──→    Port 8000      ──→    engine.py
                                              intelligence.py
                                              simulator.py
```

**Data Flow:**
1. Frontend requests data via HTTP
2. Backend routes handle requests
3. Engine layer processes logic
4. Results cached in `outputs/`
5. JSON response to frontend

See [ROUTES_DIAGRAM.md](./ROUTES_DIAGRAM.md) for detailed architecture diagrams.

---

## ✨ Key Features

### Stage 1 + 2: Intelligence Gate
- LightGBM prepares baseline
- LLM agents wake on Delta anomalies

### Stage 3: Waterfall Routing
- Deficits resolved in strict order
- Battery → DR Auction → BFS Transmission → Fallback

### Stage 4: Self-Healing XAI
- 7-phase audit ledger
- Human-readable explanations
- Memory warnings for next-day adaptation

---

## 🧪 Testing the Setup

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "date": "2026-04-08"
}
```

### 2. Access Frontend

Open browser: `http://localhost:3000`

### 3. View API Documentation

Open browser: `http://localhost:8000/docs`

---

## 📦 Project Structure

```
Smart_Grid_Simulation/
├── backend/
│   ├── server.py              # V2 API routes
│   ├── routes.py              # Legacy API routes  
│   ├── engine.py              # APrioriBrain
│   ├── intelligence.py        # StochasticTrigger
│   ├── simulator.py           # UnifiedOrchestrator
│   ├── config/                # Configuration files
│   ├── outputs/               # Generated data & cache
│   └── requirements.txt       # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js pages (routes)
│   │   ├── components/        # React components
│   │   ├── hooks/             # Custom React hooks
│   │   └── lib/               # Utilities
│   ├── package.json           # Node dependencies
│   └── next.config.js         # Next.js config
│
├── ROUTES_DOCUMENTATION.md    # Complete routes reference
├── ROUTES_DIAGRAM.md          # Architecture diagrams
└── README.md                  # This file
```

---

## 🔧 Troubleshooting

### Backend Won't Start

**Issue:** Port 8000 already in use

**Solution:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Frontend Won't Start

**Issue:** Port 3000 already in use

**Solution:**
```bash
# Run on different port
npm run dev -- -p 3001
```

### CORS Errors

**Check:**
1. Backend running on port 8000
2. Frontend running on port 3000
3. No proxy/firewall blocking requests

---

## 📖 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Complete API Routes](./ROUTES_DOCUMENTATION.md)
- [Architecture Diagrams](./ROUTES_DIAGRAM.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'Add my feature'`
4. Push to branch: `git push origin feature/my-feature`
5. Open a Pull Request

---

## 📄 License

[Add your license here]

---

## 👥 Authors

[Add author information here]
