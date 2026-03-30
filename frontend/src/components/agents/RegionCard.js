'use client'
import { useEffect, useMemo, useState } from 'react'
import { Thermometer, Droplets, AlertTriangle, ShieldAlert, Lightbulb } from 'lucide-react'
import { Card, SectionLabel, Badge, RiskFlag, Gauge, Divider } from '@/components/ui/Primitives'
import { REGION_BY_ID } from '@/lib/gridMeta'

const SEVERITY_VARIANT = { HIGH: 'red', MEDIUM: 'amber', MED: 'amber', LOW: 'cyan', INFO: 'info', UNKNOWN: 'default' }

function normalizeRiskLevel(level) {
  return String(level || 'UNKNOWN').toUpperCase()
}

function normalizeEvents(events = []) {
  return events.map((event, index) => {
    if (typeof event === 'string') {
      return { label: event, severity: 'INFO', timestamp: `E${index + 1}` }
    }

    return {
      label: event.event_name || event.label || event.title || event.event || 'Event',
      severity: normalizeRiskLevel(event.severity || event.confidence || event.risk || 'INFO'),
      timestamp: event.dates || event.timestamp || event.time || event.date || `E${index + 1}`,
      impact: event.est_mw_impact || null,
    }
  })
}

function firstLine(text = '') {
  if (!text) return ''
  return String(text).replace(/\s+/g, ' ').trim()
}

export function myData(rows = [], selectedDate = '') {
  if (!Array.isArray(rows) || !selectedDate) return null
  return rows.find(row => String(row?.date || '') === String(selectedDate)) || null
}

function shortNumber(value) {
  const n = Number(value || 0)
  return Number.isFinite(n) ? n.toFixed(2) : '0.00'
}

export function RegionCard({ regionId, data }) {
  const region = REGION_BY_ID[regionId]
  const hasData = Boolean(data && region)

  const multipliers = data?.grid_multipliers || {}
  const weather = data?.weather || {}
  const cityIntel = data?.city_intelligence || {}
  const phaseTrace = data?.phase_trace || {}
  const events = normalizeEvents(data?.detected_events || [])
  const forecastDays = Array.isArray(weather.forecast_days) ? weather.forecast_days : []
  const availableDates = forecastDays.map(d => String(d.date || '')).filter(Boolean)
  const [selectedDate, setSelectedDate] = useState(availableDates[0] || '')
  useEffect(() => {
    if (!availableDates.length) {
      setSelectedDate('')
      return
    }
    if (!availableDates.includes(selectedDate)) {
      setSelectedDate(availableDates[0])
    }
  }, [availableDates, selectedDate])
  const selectedForecast = useMemo(
    () => myData(forecastDays, selectedDate),
    [forecastDays, selectedDate]
  )

  const demandRiskLevel = normalizeRiskLevel(multipliers.demand_spike_risk)
  const supplyRiskLevel = normalizeRiskLevel(multipliers.supply_shortfall_risk)
  const demandRiskActive = demandRiskLevel === 'HIGH' || demandRiskLevel === 'MEDIUM'
  const supplyRiskActive = supplyRiskLevel === 'HIGH' || supplyRiskLevel === 'MEDIUM'
  const hoardActive = Boolean(multipliers.pre_event_hoard)

  const hasAnyRisk = demandRiskActive || supplyRiskActive || hoardActive
  const currentTemp = Number(weather.current_temp_c || 0)
  const humidity = Number(weather.current_humidity_pct || 0)
  const condition = weather.current_condition || 'No weather feed'
  const vulnerabilities = Array.isArray(cityIntel.key_vulnerabilities) ? cityIntel.key_vulnerabilities.slice(0, 3) : []
  const phase7 = phaseTrace.phase_7 || {}
  const beforeMultiplier = phase7.before_multiplier || {
    economic_demand_multiplier: 1.0,
    generation_capacity_multiplier: 1.0,
    temperature_anomaly: 0.0,
  }
  const afterMultiplier = phase7.after_multiplier || multipliers
  const pathSignals = phase7.path_dependency_signals || phaseTrace.phase_2 || {}
  const pathRoutes = [
    ...(Array.isArray(pathSignals.fuel_supply_routes) ? pathSignals.fuel_supply_routes : []),
    ...(Array.isArray(pathSignals.neighboring_exchange) ? pathSignals.neighboring_exchange : []),
  ].slice(0, 4)
  const phaseRows = [
    {
      title: 'Phase 1 Data Fetch',
      summary: `${phaseTrace.phase_1?.raw_headline_count ?? 0} raw headlines, weather feed ${condition}`,
    },
    {
      title: 'Phase 2 City Profile',
      summary: `${(phaseTrace.phase_2?.key_vulnerabilities || []).length || vulnerabilities.length} vulnerabilities mapped`,
    },
    {
      title: 'Phase 3 Event Radar',
      summary: `${phaseTrace.phase_3?.event_count ?? events.length} events detected`,
    },
    {
      title: 'Phase 4 Filtering',
      summary: `${phaseTrace.phase_4?.input_count ?? 0} -> ${phaseTrace.phase_4?.output_count ?? 0} headlines retained`,
    },
    {
      title: 'Phase 5 Signal Extractor',
      summary: firstLine(phaseTrace.phase_5?.summary || data?.extracted_signals || 'No signal summary'),
    },
    {
      title: 'Phase 6 Impact Narrative',
      summary: firstLine(phaseTrace.phase_6?.narrative || data?.impact_narrative || 'No narrative'),
    },
    {
      title: 'Phase 7 Multiplier Output',
      summary: `EDM ${shortNumber(afterMultiplier.economic_demand_multiplier)} | GCM ${shortNumber(afterMultiplier.generation_capacity_multiplier)} | Delta ${Number(afterMultiplier.seven_day_demand_forecast_mw_delta || 0) >= 0 ? '+' : ''}${Number(afterMultiplier.seven_day_demand_forecast_mw_delta || 0).toFixed(0)} MW`,
    },
  ]

  if (!hasData) return null

  return (
    <Card className={`relative ${hasAnyRisk ? 'glow-amber' : ''}`}>
      <div
        className="absolute top-0 left-0 right-0 h-0.5 rounded-t-xl"
        style={{ background: `linear-gradient(90deg, ${region.color}, transparent)` }}
      />

      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-xl font-bold tracking-wider" style={{ fontFamily: 'Rajdhani, sans-serif', color: region.color }}>
            {regionId}
          </div>
          <div className="text-xs text-grid-textDim">{region.fullName}</div>
        </div>
        <Badge variant={hasAnyRisk ? 'amber' : 'green'}>{hasAnyRisk ? 'VULNERABLE' : 'STABLE'}</Badge>
      </div>

      <div className="flex items-center justify-between mb-4 p-2.5 rounded-lg bg-white/3">
        <div className="flex items-center gap-1.5 text-sm">
          <Thermometer className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-white font-medium">{currentTemp.toFixed(1)}C</span>
        </div>
        <div className="flex items-center gap-1.5 text-sm">
          <Droplets className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-grid-textDim">{Math.round(humidity)}%</span>
        </div>
        <div className="text-[10px] text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{condition}</div>
      </div>

      <SectionLabel>Impact Drivers</SectionLabel>
      <div className="text-xs text-grid-text mb-3 leading-relaxed">
        {firstLine(multipliers.reasoning) || firstLine(data.impact_narrative) || 'No reasoning available'}
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="p-2 rounded bg-white/3 border border-grid-border/50">
          <div className="text-[10px] text-grid-textDim">7d Demand Delta</div>
          <div className="text-sm text-cyan-400 font-bold" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            {Number(multipliers.seven_day_demand_forecast_mw_delta || 0) >= 0 ? '+' : ''}{Number(multipliers.seven_day_demand_forecast_mw_delta || 0).toFixed(0)} MW
          </div>
        </div>
        <div className="p-2 rounded bg-white/3 border border-grid-border/50">
          <div className="text-[10px] text-grid-textDim">Key Driver</div>
          <div className="text-sm text-white font-medium">{multipliers.key_driver || 'N/A'}</div>
        </div>
      </div>

      <Divider className="mb-4" />

      <SectionLabel>Intelligence Multipliers</SectionLabel>
      <div className="flex justify-around py-2 mb-4">
        <Gauge value={Number(multipliers.economic_demand_multiplier || 1)} label="EDM" color={region.color} />
        <div className="w-px bg-grid-border/50 self-stretch" />
        <Gauge value={Number(multipliers.generation_capacity_multiplier || 1)} label="GCM" color={region.color} />
      </div>

      <Divider className="mb-3" />

      <SectionLabel>Risk Assessment</SectionLabel>
      <div className="flex flex-col gap-1.5 mb-4">
        <RiskFlag label={`Demand Spike (${demandRiskLevel})`} active={demandRiskActive} />
        <RiskFlag label={`Supply Shortfall (${supplyRiskLevel})`} active={supplyRiskActive} />
        <RiskFlag label="Pre-Event Hoarding" active={hoardActive} />
      </div>

      <SectionLabel>Key Vulnerabilities</SectionLabel>
      <div className="flex flex-col gap-2 mb-4">
        {vulnerabilities.length ? vulnerabilities.map((item, i) => (
          <div key={i} className="text-xs text-grid-textDim p-2 rounded bg-white/3 border border-grid-border/40 flex gap-2">
            <ShieldAlert className="w-3.5 h-3.5 mt-0.5 text-amber-400 shrink-0" />
            <span>{item}</span>
          </div>
        )) : (
          <div className="text-xs text-grid-textDim">No vulnerability insights in cache</div>
        )}
      </div>

      <SectionLabel>Detected Events</SectionLabel>
      <div className="flex flex-col gap-2 mb-4">
        {events.length ? events.slice(0, 2).map((event, i) => (
          <div key={i} className="flex items-start gap-2 p-2 rounded-lg bg-white/3">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 text-amber-400" />
            <div className="flex-1 min-w-0">
              <div className="text-xs text-white font-medium truncate">{event.label}</div>
              <div className="text-[10px] text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{event.timestamp}</div>
              {event.impact && <div className="text-[10px] text-cyan-300 mt-0.5">Impact: {event.impact}</div>}
            </div>
            <Badge variant={SEVERITY_VARIANT[event.severity] || 'default'}>{event.severity}</Badge>
          </div>
        )) : (
          <div className="text-xs text-grid-textDim">No events reported</div>
        )}
      </div>

      <SectionLabel>Extracted Signal</SectionLabel>
      <div className="text-xs text-grid-textDim p-2 rounded bg-white/3 border border-grid-border/40 flex gap-2 leading-relaxed">
        <Lightbulb className="w-3.5 h-3.5 mt-0.5 text-cyan-400 shrink-0" />
        <span>{firstLine(data.extracted_signals) || 'No extracted signal'}</span>
      </div>

      <Divider className="my-4" />

      <SectionLabel>Date Detail (myData)</SectionLabel>
      {availableDates.length ? (
        <div className="space-y-2 mb-4">
          <div className="flex flex-wrap gap-1.5">
            {availableDates.map(d => (
              <button
                key={d}
                type="button"
                onClick={() => setSelectedDate(d)}
                className={`px-2 py-1 text-[10px] rounded border transition ${
                  d === selectedDate
                    ? 'border-cyan-400/40 text-cyan-300 bg-cyan-500/10'
                    : 'border-grid-border/40 text-grid-textDim bg-white/3 hover:border-cyan-400/20'
                }`}
                style={{ fontFamily: 'IBM Plex Mono, monospace' }}
              >
                {d}
              </button>
            ))}
          </div>
          <div className="text-xs text-grid-textDim p-2 rounded bg-white/3 border border-grid-border/40">
            {selectedForecast ? (
              <span>
                {selectedDate}: max {selectedForecast.max_c}C, min {selectedForecast.min_c}C, humidity {selectedForecast.avg_humidity_pct}%, rain {selectedForecast.total_rain_mm} mm, condition {selectedForecast.dominant_condition}
              </span>
            ) : (
              <span>No forecast details for selected date.</span>
            )}
          </div>
        </div>
      ) : (
        <div className="text-xs text-grid-textDim mb-4">No per-date forecast entries in cache.</div>
      )}

      <SectionLabel>Before vs After Multiplier</SectionLabel>
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="p-2 rounded bg-white/3 border border-grid-border/40">
          <div className="text-[10px] text-grid-textDim mb-1">Before (Baseline)</div>
          <div className="text-[11px] text-grid-text leading-5" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            EDM: {shortNumber(beforeMultiplier.economic_demand_multiplier)}<br />
            GCM: {shortNumber(beforeMultiplier.generation_capacity_multiplier)}<br />
            Temp: {shortNumber(beforeMultiplier.temperature_anomaly)}C
          </div>
        </div>
        <div className="p-2 rounded bg-white/3 border border-grid-border/40">
          <div className="text-[10px] text-grid-textDim mb-1">After (Phase 7)</div>
          <div className="text-[11px] text-grid-text leading-5" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            EDM: {shortNumber(afterMultiplier.economic_demand_multiplier)}<br />
            GCM: {shortNumber(afterMultiplier.generation_capacity_multiplier)}<br />
            Temp: {shortNumber(afterMultiplier.temperature_anomaly)}C
          </div>
        </div>
      </div>

      <SectionLabel>Path Dependencies</SectionLabel>
      <div className="flex flex-col gap-2 mb-4">
        {pathRoutes.length ? pathRoutes.map((pathItem, idx) => (
          <div key={idx} className="text-xs text-grid-textDim p-2 rounded bg-white/3 border border-grid-border/40">
            {pathItem}
          </div>
        )) : (
          <div className="text-xs text-grid-textDim p-2 rounded bg-white/3 border border-grid-border/40">
            No route/path dependency signals found.
          </div>
        )}
      </div>

      <SectionLabel>Phase-by-Phase Trace</SectionLabel>
      <div className="flex flex-col gap-2">
        {phaseRows.map((phase, idx) => (
          <div key={idx} className="p-2 rounded bg-white/3 border border-grid-border/40">
            <div className="text-[10px] uppercase tracking-[0.08em] text-cyan-300" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              {phase.title}
            </div>
            <div className="text-xs text-grid-textDim mt-1 leading-relaxed">{phase.summary}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}
