/**
 * api.js — Data service layer
 *
 * Calls the FastAPI backend at /api/*.
 * The package.json proxy ("proxy": "http://localhost:8000") forwards
 * all /api/* requests from the React dev server to FastAPI automatically.
 *
 * If the backend is unreachable, each function falls back to mock data
 * so the UI remains usable for frontend-only development.
 */

// ── Fallback mock data ────────────────────────────────────────────────────────

const MOCK_GRID = {
  nodes: [
    { id: 'BHR', name: 'Bihar',        generation_mw: 9000,  demand_mw: 9850,  adjusted_demand_mw: 10238, balance_mw: -1238, battery: { soc: 0.50, charge: 250, capacity: 500  } },
    { id: 'UP',  name: 'NR UP',        generation_mw: 15000, demand_mw: 15750, adjusted_demand_mw: 15120, balance_mw: -120,  battery: { soc: 0.50, charge: 400, capacity: 800  } },
    { id: 'WB',  name: 'West Bengal',  generation_mw: 11000, demand_mw: 12650, adjusted_demand_mw: 13260, balance_mw: -2260, battery: { soc: 0.50, charge: 300, capacity: 600  } },
    { id: 'KAR', name: 'SR Karnataka', generation_mw: 14000, demand_mw: 12600, adjusted_demand_mw: 11970, balance_mw: 2030,  battery: { soc: 0.50, charge: 500, capacity: 1000 } },
  ],
  edges: [
    { src: 'BHR', dst: 'UP',  distance_km: 500,  flow_mw: 120,  capacity_mw: 3000, congestion: 0.04 },
    { src: 'BHR', dst: 'WB',  distance_km: 600,  flow_mw: 1100, capacity_mw: 2500, congestion: 0.44 },
    { src: 'BHR', dst: 'KAR', distance_km: 1800, flow_mw: 0,    capacity_mw: 2000, congestion: 0.00 },
    { src: 'UP',  dst: 'WB',  distance_km: 1000, flow_mw: 0,    capacity_mw: 3500, congestion: 0.00 },
    { src: 'UP',  dst: 'KAR', distance_km: 1600, flow_mw: 120,  capacity_mw: 3500, congestion: 0.03 },
    { src: 'WB',  dst: 'KAR', distance_km: 1700, flow_mw: 810,  capacity_mw: 3000, congestion: 0.27 },
  ],
};

const MOCK_INTELLIGENCE = {
  BHR: {
    city: 'Bihar',
    grid_multipliers: { economic_demand_multiplier: 1.14, generation_capacity_multiplier: 0.96, temperature_anomaly: 2.8, demand_spike_risk: 'HIGH', supply_shortfall_risk: 'MEDIUM', pre_event_hoard: false, seven_day_demand_forecast_mw_delta: 980, confidence: 0.76, key_driver: 'Pre-monsoon heatwave building', reasoning: 'Bihar experiencing above-normal temperatures. Coal rake supply at 94% normal. NBPDCL grid stable but margin thin.' },
    detected_events: [],
    impact_narrative: `## 1. DEMAND OUTLOOK (next 7 days)
AC load is rising sharply as pre-monsoon heat builds across Bihar. Peak temperatures expected to reach 42°C by Day 3, adding an estimated +8–12% to residential cooling load (~780–980 MW above baseline). Industrial demand from sugar mills and fertiliser plants remains steady. No major behavioural shifts detected.

## 2. SUPPLY OUTLOOK (next 7 days)
NTPC Barh Stage-II (1320 MW) is running at 94% PLF. Kanti Thermal (610 MW) has one unit (220 MW) on planned maintenance until Day 4. NBPDCL is importing ~400 MW from the central pool via PGCIL. Coal stock at Barh: 11-day cover — comfortable.

## 3. LOGISTICS RISK
Coal rake supply from ECL Rajmahal mines is operating normally. No railway disruptions on the Jharkhand–Bihar corridor. Road freight to smaller captive plants unaffected.

## 4. RISK FLAGS (deviations >5% from normal baseline)
- Heat-driven demand spike: +8 to +12% above seasonal norm (+640 to +980 MW). Risk window: Days 2–5.
- Kanti Unit 2 maintenance: -220 MW generation until Day 4. Supply headroom narrows to ~6%.

## 5. PRE-EVENT HOARDING RECOMMENDATION
NO — Supply margin is thin but adequate at ~6%. No high-confidence demand-spiking events detected within 7 days. Recommend monitoring closely; activate if Kanti maintenance extends or temperatures exceed 44°C.`,
    extracted_signals: `[WEATHER] IMD issues heatwave advisory for Bihar — temperatures forecast 40–43°C over next 5 days, AC load could add 8–12% above seasonal norm.
[PLANT] Kanti Thermal Unit 2 (220 MW) on planned maintenance — expected back online Day 4. Reduces available generation headroom to ~6%.
[FUEL-SUPPLY] ECL Rajmahal coal rakes running at 94% normal dispatch rate — Barh STPS maintaining 11-day coal cover.`,
  },

  UP: {
    city: 'Lucknow',
    grid_multipliers: { economic_demand_multiplier: 1.08, generation_capacity_multiplier: 0.98, temperature_anomaly: 3.5, demand_spike_risk: 'MEDIUM', supply_shortfall_risk: 'LOW', pre_event_hoard: false, seven_day_demand_forecast_mw_delta: 2240, confidence: 0.82, key_driver: 'AC load surge from heatwave', reasoning: 'Lucknow peak heat index projected at 47°C. UPPCL generation adequate. No major events detected.' },
    detected_events: [{ event_name: 'Political rally – Lucknow Maidan', grid_mechanism: 'MASS_GATHERING', est_mw_impact: '+40 to +80 MW', days_away: 2, confidence: 'medium' }],
    impact_narrative: `## 1. DEMAND OUTLOOK (next 7 days)
Uttar Pradesh is entering peak summer load season. Heat index in Lucknow projected at 47°C on Day 2–3, historically the highest driver of residential AC demand across MVVNL and PVVNL zones. Estimated demand surge: +2,000–2,500 MW above baseline. A political rally at Lucknow Maidan (Day 2, ~80,000 attendees) will add ~40–80 MW for temporary floodlighting and sound infrastructure.

## 2. SUPPLY OUTLOOK (next 7 days)
UPPCL's own generation (Obra, Anpara, Harduaganj) running at ~98% PLF. Renewable contribution from solar parks (Bundelkhand corridor) remains high — clear sky forecast. Imports from NTPC central pool (~3,200 MW contracted) stable.

## 3. LOGISTICS RISK
No active logistics disruptions. Coal pipeline from NCL Singrauli mines operating normally with 14-day stock cover at Anpara.

## 4. RISK FLAGS
- Heat-index-driven residential load: +7–9% above norm (+1,960–2,520 MW). Window: Days 1–4.
- Rally temporary load: +40–80 MW, Day 2 evening only. Minor, well within grid headroom.

## 5. PRE-EVENT HOARDING RECOMMENDATION
NO — Generation headroom comfortable at ~8%. Rally impact is minor. Monitor heat index forecast; trigger pre-booking if sustained above 48°C.`,
    extracted_signals: `[WEATHER] IMD heatwave watch for Uttar Pradesh — heat index 45–47°C expected Days 2–4, driving AC load surge estimated at +7–9% above baseline.
[INDUSTRIAL] Textile mills in Kanpur running at full capacity — elevated industrial baseload contributing ~200 MW above seasonal norm.
[FUEL-SUPPLY] NCL Singrauli coal dispatch to Anpara STPS at 100% — 14-day coal cover maintained.`,
  },

  WB: {
    city: 'Kolkata',
    grid_multipliers: { economic_demand_multiplier: 1.18, generation_capacity_multiplier: 0.85, temperature_anomaly: 4.1, demand_spike_risk: 'CRITICAL', supply_shortfall_risk: 'HIGH', pre_event_hoard: true, seven_day_demand_forecast_mw_delta: 1120, confidence: 0.71, key_driver: 'DVC coal shortage + heat + IPL TV pickup', reasoning: 'DVC Mejia forced outage (2 units). Coal stock at 3-day cover. IPL knockout driving TV pickup.' },
    detected_events: [{ event_name: 'IPL Knockout Match broadcast', grid_mechanism: 'TV_PICKUP', est_mw_impact: '+200 to +350 MW', days_away: 1, confidence: 'high' }],
    impact_narrative: `## 1. DEMAND OUTLOOK (next 7 days)
Kolkata faces a compound demand shock. Heat index at 51°C (Day 1) is driving record AC loads — estimated +15–18% above seasonal norm (~1,350–1,620 MW). The IPL knockout match tomorrow evening (high confidence, city-wide TV pickup) will add a synchronised 200–350 MW residential spike between 19:30–23:00. This creates a worst-case peak of ~10,800 MW against a typical peak of 9,500 MW — a 14% overshoot.

## 2. SUPPLY OUTLOOK (next 7 days)
CRITICAL: DVC Mejia Thermal — Unit 3 (250 MW) tripped on forced outage Day 0; Unit 7 (500 MW) offline since Day -2 for emergency repairs. Total DVC generation down 750 MW. Coal stock at Mejia: 3-day cover only. CESC's Budge Budge plant (750 MW) running at full load. WBSEDCL relying on expensive short-term market purchases.

## 3. LOGISTICS RISK
Coal supply to Mejia from ECL Sonepur Bazari mines is disrupted — a derailment at Asansol yard has blocked the primary rake route. Alternative routing via Durgapur adds 18–24 hours of delay. At current consumption, stock will hit zero in 72 hours without emergency rake movement.

## 4. RISK FLAGS
- DVC generation shortfall: -750 MW (7.9% of peak). HIGH risk of load shedding Days 1–4.
- Coal logistics disruption: Asansol yard derailment — rake re-routing adds 18–24h delay. CRITICAL.
- IPL TV pickup tomorrow: +200–350 MW synchronised spike. Compound risk with supply shortfall.
- Combined worst-case shortfall on Day 1 evening: ~1,100 MW. Load shedding highly probable.

## 5. PRE-EVENT HOARDING RECOMMENDATION
YES — Pre-book 800–1,000 MW from NTPC central pool immediately. The compound risk of coal shortage + DVC forced outage + IPL demand spike exceeds current supply headroom by >10%. Failure to secure imports before tomorrow evening will force rotating load shedding across CESC and WBSEDCL zones.`,
    extracted_signals: `[PLANT] DVC Mejia Unit 3 (250 MW) forced outage — tripped on boiler tube failure. Timeline for return unknown.
[PLANT] DVC Mejia Unit 7 (500 MW) emergency maintenance — offline since Day -2. Grid headroom reduced by 750 MW total.
[FUEL-SUPPLY] ECL Sonepur Bazari coal rakes to Mejia blocked — Asansol yard derailment disrupting primary supply route. 3-day coal cover remaining.
[LOGISTICS] Asansol yard derailment — primary coal rake corridor to DVC Mejia blocked. Alternative Durgapur routing adds 18–24h delay.
[WEATHER] Heat index 51°C in Kolkata — record pre-monsoon reading driving +15–18% residential AC load surge.`,
  },

  KAR: {
    city: 'Bengaluru',
    grid_multipliers: { economic_demand_multiplier: 0.94, generation_capacity_multiplier: 1.06, temperature_anomaly: 0.8, demand_spike_risk: 'LOW', supply_shortfall_risk: 'LOW', pre_event_hoard: false, seven_day_demand_forecast_mw_delta: -640, confidence: 0.88, key_driver: 'Strong wind generation – surplus exporter', reasoning: 'Karnataka wind generation at 115% seasonal average. BESCOM grid balanced. Pleasant temperatures reducing AC load.' },
    detected_events: [],
    impact_narrative: `## 1. DEMAND OUTLOOK (next 7 days)
Bengaluru continues to benefit from its temperate highland climate. Temperatures remain 3–4°C below the national average, keeping AC demand suppressed. IT park demand is seasonally normal — no holiday or WFH orders detected. Overall demand forecast: -5 to -7% below seasonal norm, representing a net surplus position.

## 2. SUPPLY OUTLOOK (next 7 days)
Karnataka's generation fleet is in excellent health. Wind generation from the Chitradurga and Davangere corridors is running at 115% of seasonal average due to early onset of south-westerly flow. KPCL hydro generation from Sharavathi (1,035 MW) at 88% capacity — reservoir levels healthy. Solar parks (Pavagada, 2,050 MW) delivering full output under clear skies.

## 3. LOGISTICS RISK
No logistics risks. GESCOM and BESCOM grids stable. No coal dependency for base generation — Karnataka's mix is dominated by hydro, wind, and solar. Gas peakers on standby only.

## 4. RISK FLAGS
- No risk flags. System is in net surplus with ~2,000 MW exportable capacity.
- Wind forecast uncertainty: if westerlies weaken by Day 5, generation could dip 8–12%. Still within comfortable margins.

## 5. PRE-EVENT HOARDING RECOMMENDATION
NO — Karnataka is the system's natural exporter this week. BESCOM should maximise inter-state sales to deficit regions (WB, BHR) to recover cost. No pre-booking needed.`,
    extracted_signals: `[WEATHER] Clear sky and mild temperatures across Karnataka — solar irradiance at seasonal peak, Pavagada solar park at 100% output.
[GRID-EVENT] KPTCL 400kV Bengaluru–Hubli line maintenance completed ahead of schedule — full inter-state export capacity restored.
[POLICY] KERC approved additional 500 MW short-term sale to neighbouring states — Karnataka positioned as net exporter for 7-day window.`,
  },
};

const MOCK_DISPATCH = [
  { type: 'SYNDICATE',  buyer_city_id: 'WB',  syndicate_sellers: ['KAR', 'UP'], transfer_mw: 1850, cleared_price_mw: 8.42,  buyer_bid: 15.00, breakdown_log: '1200 MW from KAR @ ₹3.00 | 650 MW from UP @ ₹3.00' },
  { type: 'STANDARD',   buyer_city_id: 'BHR', seller_city_id: 'KAR', transfer_mw: 830,  cleared_price_mw: 11.15, seller_ask: 3.00, path_cost: 8.00, carbon_tax: 0.15, buyer_bid: 5.00,  path_description: 'KAR → BHR @hour 06:00', llm_safety_status: 'APPROVED', dlr_applied: false, effective_capacity: 2000 },
  { type: 'STANDARD',   buyer_city_id: 'UP',  seller_city_id: 'KAR', transfer_mw: 120,  cleared_price_mw: 10.50, seller_ask: 3.00, path_cost: 7.35, carbon_tax: 0.15, buyer_bid: 5.00,  path_description: 'KAR → UP @hour 06:00',  llm_safety_status: 'APPROVED', dlr_applied: true,  effective_capacity: 3290 },
  { type: 'NEGOTIATED', buyer_city_id: 'BHR', seller_city_id: 'WB',  transfer_mw: 400,  cleared_price_mw: 6.20,  seller_ask: 3.00, path_cost: 3.05, carbon_tax: 0.45, buyer_bid: 5.00,  path_description: 'WB → BHR @hour 07:00',  llm_safety_status: 'APPROVED', dlr_applied: false, effective_capacity: 2500 },
];

// ── Generic fetch with fallback ───────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function fetchGridStatus() {
  try {
    return await apiFetch('/api/grid-status');
  } catch {
    console.warn('[api] /api/grid-status unreachable — using mock data');
    return MOCK_GRID;
  }
}

export async function fetchIntelligence() {
  try {
    return await apiFetch('/api/intelligence');
  } catch {
    console.warn('[api] /api/intelligence unreachable — using mock data');
    return MOCK_INTELLIGENCE;
  }
}

export async function fetchDispatchLog() {
  try {
    const data = await apiFetch('/api/dispatch-log');
    if (Array.isArray(data) && data.length > 0) return data;
    console.warn('[api] /api/dispatch-log returned empty — using mock data');
    return MOCK_DISPATCH;
  } catch {
    console.warn('[api] /api/dispatch-log unreachable — using mock data');
    return MOCK_DISPATCH;
  }
}

export async function runIntelligence() {
  try {
    return await apiFetch('/api/generate-intelligence', { method: 'POST' });
  } catch (err) {
    console.warn('[api] /api/generate-intelligence failed', err);
    throw err;
  }
}

export async function fetchHealth() {
  try {
    return await apiFetch('/api/health');
  } catch {
    console.warn('[api] /api/health unreachable - returning fallback');
    return { status: 'offline', date: new Date().toISOString().slice(0, 10) };
  }
}

export async function fetchSimulationResult() {
  try {
    return await apiFetch('/api/simulation-result');
  } catch (err) {
    console.warn('[api] /api/simulation-result failed', err);
    throw err;
  }
}

/**
 * Run the simulation and stream stdout lines back.
 * onLine(str) is called for each line received.
 * Returns a promise that resolves when the stream ends.
 */
export async function runSimulation(onLine) {
  try {
    const res = await fetch('/api/run-simulation', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // last partial line stays in buffer
      for (const line of lines) {
        if (line.trim()) onLine(line);
      }
    }
    if (buffer.trim()) onLine(buffer);
    return { status: 'ok' };

  } catch (err) {
    console.warn('[api] /api/run-simulation unreachable — simulating locally');
    // Fake streaming for demo
    const fakeLines = [
      'Initialising GridEnvironment (seed=42)...',
      'Loading LightGBM artefacts...',
      'Loading live context cache...',
      'HourlyFusionAgent: applying daily multipliers...',
      'StateAgent [BHR]: BUY 1238 MW @ ₹5.00',
      'StateAgent [UP]:  BUY 120 MW @ ₹5.00',
      'StateAgent [WB]:  BUY 2260 MW @ ₹15.00 (PANIC)',
      'StateAgent [KAR]: SELL 2030 MW @ ₹3.00',
      'RoutingAgent: market open — 3 BUY, 1 SELL',
      '[SYNDICATE] 1850 MW Syndicate(KAR, UP) → WB @ ₹8.42/MW ✓',
      '[DISPATCH]  830 MW KAR → BHR @ ₹11.15/MW ✓',
      '[DISPATCH]  120 MW KAR → UP  @ ₹10.50/MW (DLR active) ✓',
      '[NEGOTIATED] 400 MW WB → BHR @ ₹6.20/MW ✓',
      'BatteryPhase complete.',
      '[DONE] Simulation exited with code 0',
    ];
    for (const line of fakeLines) {
      await new Promise((r) => setTimeout(r, 200 + Math.random() * 150));
      onLine(line);
    }
    return { status: 'ok' };
  }
}
