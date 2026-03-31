'use client'
import { useMemo, useState } from 'react'
import { AlertTriangle, Route, Factory, CalendarClock, Zap, Thermometer, Battery, ArrowDownRight, ShieldCheck, Brain } from 'lucide-react'
import { Card, SectionLabel, Badge, RiskFlag } from '@/components/ui/Primitives'
import { REGION_BY_ID } from '@/lib/gridMeta'

const SEVERITY_VARIANT = { HIGH: 'red', MEDIUM: 'amber', MED: 'amber', LOW: 'cyan', INFO: 'info', UNKNOWN: 'default' }

function normalizeRiskLevel(level) {
  return String(level || 'UNKNOWN').toUpperCase()
}

function normalizeEvents(events = []) {
  return events.map((event, index) => {
    if (typeof event === 'string') {
      return { label: event, severity: 'INFO' }
    }

    return {
      label: event.event_name || event.label || event.title || event.event || `Event ${index + 1}`,
      severity: normalizeRiskLevel(event.severity || event.confidence || event.risk || 'INFO'),
    }
  })
}

function clean(text = '') {
  if (!text) return ''
  return String(text).replace(/\s+/g, ' ').trim()
}

function compact(items = []) {
  return items.map(clean).filter(Boolean)
}

function short(text = '', max = 96) {
  const t = clean(text)
  if (!t) return ''
  return t.length > max ? `${t.slice(0, max).trim()}...` : t
}

function PreviewRow({ icon: Icon, label, items }) {
  const shown = items.slice(0, 2)
  return (
    <div className="rounded-lg border border-grid-border/50 bg-white/5 p-2.5">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="w-3.5 h-3.5 text-cyan-300" />
        <div className="text-[10px] uppercase tracking-[0.1em] text-cyan-300" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{label}</div>
      </div>
      {shown.length ? (
        <div className="space-y-1">
          {shown.map((item, i) => (
            <div key={`${label}-${i}`} className="text-xs text-grid-textDim leading-relaxed">{item}</div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-grid-textDim">No data</div>
      )}
    </div>
  )
}

function FullList({ title, items, showAll, setShowAll }) {
  const visible = showAll ? items : items.slice(0, 2)
  return (
    <div className="rounded-lg border border-grid-border/50 bg-white/5 p-2.5">
      <div className="text-[10px] uppercase tracking-[0.1em] text-cyan-300 mb-1.5" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{title}</div>
      {visible.length ? (
        <div className="space-y-1">
          {visible.map((item, idx) => (
            <div key={`${title}-${idx}`} className="text-xs text-grid-textDim leading-relaxed">{item}</div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-grid-textDim">No data</div>
      )}
      {items.length > 2 && (
        <button
          type="button"
          onClick={() => setShowAll(!showAll)}
          className="mt-2 text-[10px] uppercase tracking-[0.1em] text-cyan-300 hover:text-cyan-200"
          style={{ fontFamily: 'IBM Plex Mono, monospace' }}
        >
          {showAll ? 'Show top 2' : `Show all (${items.length})`}
        </button>
      )}
    </div>
  )
}

function TemperatureTrend({ points = [] }) {
  if (!points.length) {
    return <div className="text-xs text-grid-textDim">No temperature forecast data.</div>
  }

  const maxVal = Math.max(...points.map(p => Number(p.max)))
  const minVal = Math.min(...points.map(p => Number(p.min)))
  const range = Math.max(1, maxVal - minVal)

  return (
    <div className="space-y-2">
      {points.slice(0, 7).map((p, idx) => {
        const maxWidth = `${((Number(p.max) - minVal) / range) * 100}%`
        const minWidth = `${((Number(p.min) - minVal) / range) * 100}%`
        return (
          <div key={`${p.date}-${idx}`}>
            <div className="flex items-center justify-between text-[10px] text-grid-textDim mb-1" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              <span>{p.label}</span>
              <span>{Number(p.min).toFixed(1)}C - {Number(p.max).toFixed(1)}C</span>
            </div>
            <div className="h-1.5 rounded bg-[#0f1a27] border border-cyan-500/20 overflow-hidden">
              <div className="h-full bg-cyan-500/35 relative" style={{ width: maxWidth }}>
                <div className="absolute top-0 bottom-0 bg-amber-400/60" style={{ width: minWidth }} />
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export function RegionCard({ regionId, data }) {
  const region = REGION_BY_ID[regionId]
  if (!region || !data) return null

  const multipliers = data?.grid_multipliers || {}
  const intel = data?.city_intelligence || {}
  const weather = data?.weather || {}
  const events = normalizeEvents(data?.detected_events || [])

  const demandRiskLevel = normalizeRiskLevel(multipliers.demand_spike_risk)
  const supplyRiskLevel = normalizeRiskLevel(multipliers.supply_shortfall_risk)
  const demandRiskActive = demandRiskLevel === 'HIGH' || demandRiskLevel === 'MEDIUM'
  const supplyRiskActive = supplyRiskLevel === 'HIGH' || supplyRiskLevel === 'MEDIUM'
  const hoardActive = Boolean(multipliers.pre_event_hoard)
  const hasRisk = demandRiskActive || supplyRiskActive || hoardActive

  const demandDrivers = compact(intel.demand_drivers || [])
  const seasonalFactors = compact(intel.seasonal_demand_factors || [])
  const vulnerabilities = compact(intel.key_vulnerabilities || [])
  const fuelRoutes = compact(intel.fuel_supply_routes || [])
  const fuelSources = compact(intel.primary_fuel_sources || [])

  const hoardDay = multipliers.hoard_day || 0
  const isHoarding = hoardActive || hoardDay > 0

  const [pinDetails, setPinDetails] = useState(false)
  const [allDrivers, setAllDrivers] = useState(false)
  const [allSeasonal, setAllSeasonal] = useState(false)
  const [allVuln, setAllVuln] = useState(false)
  const [allRoutes, setAllRoutes] = useState(false)
  const [allFuel, setAllFuel] = useState(false)
  const [showTempTrend, setShowTempTrend] = useState(false)

  const topEvents = useMemo(() => events.slice(0, 2), [events])
  const delta = Number(multipliers.seven_day_demand_forecast_mw_delta || 0)
  const tempPoints = useMemo(() => {
    const rows = Array.isArray(weather?.forecast_days) ? weather.forecast_days : []
    return rows
      .map((r, i) => ({
        date: String(r?.date || i),
        label: r?.date ? String(r.date).slice(5) : `D${i + 1}`,
        max: Number(r?.max_c ?? weather?.current_temp_c ?? 0),
        min: Number(r?.min_c ?? weather?.current_temp_c ?? 0),
      }))
      .filter(r => Number.isFinite(r.max) && Number.isFinite(r.min))
  }, [weather])

  return (
    <>
      <Card className="relative overflow-visible min-h-[350px] transition-all duration-300">
        <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-xl" style={{ background: `linear-gradient(90deg, ${region.color}, transparent)` }} />

        <div className="flex items-start justify-between mb-3">
          <div>
            <div className="text-xl font-bold tracking-[0.08em]" style={{ fontFamily: 'Rajdhani, sans-serif', color: region.color }}>{regionId}</div>
            <div className="text-xs text-grid-textDim">{region.fullName}</div>
          </div>
          <Badge variant={hasRisk ? 'amber' : 'green'}>{hasRisk ? 'RISK WATCH' : 'STABLE'}</Badge>
        </div>

        {/* 7-Day Horizon Cells */}
        <div className="mb-4">
          <div className="text-[10px] uppercase tracking-[0.15em] text-grid-textDim mb-2 flex justify-between items-center" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
             <span>7-Day Security Horizon</span>
             {isHoarding && <span className="text-amber-400 flex items-center gap-1"><ShieldCheck className="w-3 h-3"/> SELF-PRESERVATION ACTIVE</span>}
          </div>
          <div className="flex gap-1.5 h-8">
            {[...Array(7)].map((_, i) => {
              const isTargetDay = (i + 1) === hoardDay;
              const isToday = i === 0;
              return (
                <div 
                  key={i} 
                  className={`flex-1 rounded-sm border transition-all duration-500 flex items-center justify-center text-[10px] font-bold
                    ${isTargetDay ? 'bg-red-500/20 border-red-500 animate-pulse scale-105 shadow-[0_0_10px_rgba(239,68,68,0.5)]' : 
                      isToday ? 'bg-cyan-500/10 border-cyan-500/50 text-cyan-400' : 'bg-white/5 border-grid-border/30 text-grid-textDim'}
                  `}
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}
                >
                  D{i+1}
                </div>
              )
            })}
          </div>
        </div>

        {/* Hoarding Animation & Storage Vault */}
        {isHoarding && (
          <div className="relative mb-4 h-12 flex items-center justify-between px-2 bg-amber-500/5 rounded-lg border border-amber-500/20 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-amber-500/5 to-transparent animate-shimmer" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase text-amber-500 font-bold" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>Surplus Lock</span>
              <span className="text-[11px] text-white font-medium">Hoarding for Day {hoardDay}</span>
            </div>
            
            <div className="flex items-center gap-2">
              <div className="flex items-center text-amber-400">
                 <ArrowDownRight className="w-4 h-4 animate-bounce" />
              </div>
              <div className="w-10 h-10 rounded-full border-2 border-amber-500 flex items-center justify-center bg-amber-500/20 shadow-[0_0_15px_rgba(245,158,11,0.3)]">
                  <Battery className="w-5 h-5 text-amber-400" />
              </div>
            </div>
            <div className="absolute top-0 right-0 p-1">
               <span className="text-[8px] text-amber-500 animate-pulse">VAULTING...</span>
            </div>
          </div>
        )}

        {/* Virtual Battery / Spin-Up Gauge */}
        <div className="mb-4 space-y-1.5">
          <div className="flex justify-between items-center text-[10px] uppercase tracking-wider text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            <span>Pumped Hydro Reservoir / Spin-Up</span>
            <span className={isHoarding ? 'text-amber-400' : 'text-cyan-400'}>
              {isHoarding ? 'RAMPING' : 'STABLE'} ({(data?.summary?.[regionId]?.battery_soc * 100 || 62).toFixed(1)}%)
            </span>
          </div>
          <div className="h-3 rounded-full bg-black/40 border border-grid-border/30 overflow-hidden p-0.5">
             <div 
               className={`h-full rounded-full transition-all duration-1000 relative ${isHoarding ? 'bg-amber-500 animate-pulse shadow-[0_0_10px_rgba(245,158,11,0.5)]' : 'bg-cyan-500/60'}`}
               style={{ width: `${(data?.summary?.[regionId]?.battery_soc * 100 || 62)}%` }}
             >
               {isHoarding && <div className="absolute inset-0 bg-white/20 animate-pulse" />}
             </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="rounded-lg border border-grid-border/50 bg-white/5 p-2.5">
            <div className="text-[10px] text-grid-textDim uppercase tracking-[0.08em]" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>7D Demand Delta</div>
            <div className={`text-sm font-semibold mt-1 ${delta >= 0 ? 'text-amber-300' : 'text-green-300'}`} style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              {delta >= 0 ? '+' : ''}{delta.toFixed(0)} MW
            </div>
          </div>
          <div className="rounded-lg border border-grid-border/50 bg-white/5 p-2.5">
            <div className="text-[10px] text-grid-textDim uppercase tracking-[0.08em]" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>Key Driver</div>
            <div className="text-sm text-white mt-1">{short(multipliers.key_driver || 'N/A', 46)}</div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap mb-4">
          <RiskFlag label={`Demand ${demandRiskLevel}`} active={demandRiskActive} />
          <RiskFlag label={`Supply ${supplyRiskLevel}`} active={supplyRiskActive} />
          <RiskFlag label="Hoarding" active={hoardActive} />
        </div>

        <div className="mt-auto pt-4 border-t border-grid-border/20">
          <button
            type="button"
            onClick={() => setPinDetails(true)}
            className="w-full py-2 flex items-center justify-center gap-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 hover:bg-cyan-500/20 transition-all font-bold tracking-widest text-[10px] uppercase"
            style={{ fontFamily: 'Rajdhani, sans-serif' }}
          >
            <Route className="w-3.5 h-3.5" />
            View Full Strategy Intel
          </button>
        </div>
      </Card>

      {/* BLOOM OUT Modal Overlay */}
      {pinDetails && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
           {/* Backdrop */}
           <div className="absolute inset-0 bg-black/90 backdrop-blur-md animate-fade-in" onClick={() => setPinDetails(false)} />
           
           {/* Modal Body */}
           <div className="relative w-full max-w-4xl max-h-[90vh] bg-[#07101a] border border-cyan-400/40 rounded-2xl shadow-[0_0_100px_rgba(0,212,255,0.2)] overflow-hidden flex flex-col scale-1 animation-bloom">
              {/* Header */}
              <div className="p-6 border-b border-grid-border/30 flex items-start justify-between bg-white/2">
                 <div>
                    <h2 className="text-3xl font-bold tracking-[0.1em]" style={{ color: region.color, fontFamily: 'Rajdhani, sans-serif' }}>{regionId} Strategic Audit</h2>
                    <p className="text-grid-textDim text-sm font-mono mt-1 uppercase tracking-tighter">Regional Intelligence Analysis Packet // 7-Day Window</p>
                 </div>
                 <button onClick={() => setPinDetails(false)} className="p-2 text-grid-textDim hover:text-white transition-colors">
                    <span className="text-sm font-mono">[ CLOSE_AUDIT ]</span>
                 </button>
              </div>

              {/* Scrollable Intel Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                 {/* Narrative Section */}
                 <div className="p-5 rounded-xl border border-cyan-500/20 bg-cyan-500/5">
                    <div className="flex items-center gap-2 mb-3">
                       <Brain className="w-5 h-5 text-cyan-400" />
                       <SectionLabel>LLM Situational Narrative</SectionLabel>
                    </div>
                    <p className="text-sm text-grid-text leading-relaxed font-medium italic">
                       "{multipliers.reasoning || data?.impact_narrative || data?.extracted_signals || 'No detailed reasoning provided by the Agentic layer.'}"
                    </p>
                 </div>

                 {/* Grid Intel Rows */}
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-4">
                       <FullList title="Demand Drivers" items={demandDrivers} showAll={allDrivers} setShowAll={setAllDrivers} />
                       <FullList title="Seasonal Demand Factors" items={seasonalFactors} showAll={allSeasonal} setShowAll={setAllSeasonal} />
                       <div className="rounded-lg border border-cyan-500/25 bg-[#0a1826] p-4">
                          <div className="flex items-center justify-between mb-4">
                             <span className="text-[10px] uppercase tracking-[0.15em] text-cyan-300 font-bold" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>Temperature Trend Analysis</span>
                             <Thermometer className="w-4 h-4 text-cyan-300" />
                          </div>
                          <TemperatureTrend points={tempPoints} />
                       </div>
                    </div>
                    <div className="space-y-4">
                       <FullList title="Key Vulnerabilities" items={vulnerabilities} showAll={allVuln} setShowAll={setAllVuln} />
                       <FullList title="Fuel Supply Routes" items={fuelRoutes} showAll={allRoutes} setShowAll={setAllRoutes} />
                       <FullList title="Primary Fuel Sources" items={fuelSources} showAll={allFuel} setShowAll={setAllFuel} />
                       <div className="rounded-lg border border-grid-border/50 bg-white/5 p-4">
                         <div className="text-[10px] uppercase tracking-[0.1em] text-cyan-300 mb-3" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>Top Intelligence Events</div>
                         {events.length ? events.map((ev, idx) => (
                           <div key={`${ev.label}-${idx}`} className="flex items-center justify-between gap-3 py-2 border-b border-grid-border/10 last:border-0">
                             <div className="text-xs text-grid-text font-medium">{ev.label}</div>
                             <Badge variant={SEVERITY_VARIANT[ev.severity] || 'default'}>{ev.severity}</Badge>
                           </div>
                         )) : <div className="text-xs text-grid-textDim">No events recorded</div>}
                       </div>
                    </div>
                 </div>
              </div>

              {/* Status Footer */}
              <div className="p-4 bg-black/60 border-t border-grid-border/30 flex justify-between items-center px-8">
                 <div className="flex gap-4">
                    <div className="flex items-center gap-2">
                       <div className="w-2 h-2 rounded-full bg-cyan-400" />
                       <span className="text-[10px] text-cyan-400/80 font-mono">ENCRYPTED_STREAM_ACTV</span>
                    </div>
                    <div className="flex items-center gap-2">
                       <div className="w-2 h-2 rounded-full bg-amber-400" />
                       <span className="text-[10px] text-amber-400/80 font-mono">AGENT_AUTH_DONE</span>
                    </div>
                 </div>
                 <span className="text-[10px] text-grid-textDim font-mono">VERIFIED_DATA_PACKET // REVISION_4.0</span>
              </div>
           </div>
        </div>
      )}
    </>
  )
}

