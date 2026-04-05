'use client'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronDown, ChevronRight, CheckCircle2, AlertTriangle, Brain, 
  Newspaper, Cloud, Filter, Cpu, FileText, Gauge, Zap
} from 'lucide-react'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const PHASE_ICONS = {
  phase_1_data_fetch: Cloud,
  phase_2_city_intel: Brain,
  phase_3_event_radar: Zap,
  phase_4_headline_filter: Filter,
  phase_5_signal_extraction: Cpu,
  phase_6_impact_narrative: FileText,
  phase_7_multiplier_synthesis: Gauge,
}

const PHASE_COLORS = {
  phase_1_data_fetch: 'cyan',
  phase_2_city_intel: 'purple',
  phase_3_event_radar: 'orange',
  phase_4_headline_filter: 'blue',
  phase_5_signal_extraction: 'green',
  phase_6_impact_narrative: 'pink',
  phase_7_multiplier_synthesis: 'yellow',
}

function PhaseCard({ phaseKey, phase, isExpanded, onToggle }) {
  const Icon = PHASE_ICONS[phaseKey] || Brain
  const color = PHASE_COLORS[phaseKey] || 'cyan'
  const isCompleted = phase.status === 'completed'

  return (
    <div className={`border rounded-lg overflow-hidden transition-all duration-200 ${
      isCompleted ? `border-${color}-500/30 bg-${color}-500/5` : 'border-grid-border/30 bg-grid-bg/50'
    }`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-${color}-500/20`}>
            <Icon className={`w-4 h-4 text-${color}-400`} />
          </div>
          <div>
            <div className="font-medium text-white text-sm">{phase.name}</div>
            <div className="text-xs text-grid-textDim">{phase.description}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isCompleted ? (
            <CheckCircle2 className="w-4 h-4 text-green-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
          )}
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-grid-textDim" />
          ) : (
            <ChevronRight className="w-4 h-4 text-grid-textDim" />
          )}
        </div>
      </button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-2 border-t border-grid-border/20">
              <PhaseContent phaseKey={phaseKey} phase={phase} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function PhaseContent({ phaseKey, phase }) {
  switch (phaseKey) {
    case 'phase_1_data_fetch':
      return (
        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div className="p-2 rounded bg-grid-bg/50">
              <div className="text-grid-textDim">Headlines Collected</div>
              <div className="text-lg font-bold text-white">{phase.raw_headline_count}</div>
            </div>
            <div className="p-2 rounded bg-grid-bg/50">
              <div className="text-grid-textDim">Grid Events</div>
              <div className="text-lg font-bold text-white">
                {phase.phase_1_grid_events?.length || 0}
              </div>
            </div>
          </div>

          <div className="p-2 rounded bg-grid-bg/50">
            <div className="text-grid-textDim mb-2">Weather Snapshot</div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <span className="text-grid-textDim">Temp:</span>
                <span className="ml-1 text-white">{phase.weather_snapshot?.current_temp_c}°C</span>
              </div>
              <div>
                <span className="text-grid-textDim">Max:</span>
                <span className="ml-1 text-white">{phase.weather_snapshot?.week_max_c}°C</span>
              </div>
              <div>
                <span className="text-grid-textDim">Rain:</span>
                <span className="ml-1 text-white">{phase.weather_snapshot?.week_total_rain_mm}mm</span>
              </div>
            </div>
          </div>

          {phase.raw_headline_samples?.length > 0 && (
            <div>
              <div className="text-grid-textDim mb-1">Sample Headlines:</div>
              <ul className="space-y-1">
                {phase.raw_headline_samples.slice(0, 3).map((h, i) => (
                  <li key={i} className="p-1.5 rounded bg-grid-bg/30 text-grid-textDim truncate">
                    • {h}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )

    case 'phase_2_city_intel':
      return (
        <div className="space-y-3 text-xs">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-grid-textDim">LLM Confidence:</span>
            <div className="flex-1 h-2 bg-grid-bg/50 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-cyan-500"
                style={{ width: `${(phase.llm_confidence || 0) * 100}%` }}
              />
            </div>
            <span className="text-white font-mono">{((phase.llm_confidence || 0) * 100).toFixed(0)}%</span>
          </div>

          {phase.key_vulnerabilities?.length > 0 && (
            <div>
              <div className="text-grid-textDim mb-1">Key Vulnerabilities:</div>
              <div className="flex flex-wrap gap-1">
                {phase.key_vulnerabilities.map((v, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-red-500/20 text-red-400 text-[10px]">
                    {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          {phase.primary_fuel_sources?.length > 0 && (
            <div>
              <div className="text-grid-textDim mb-1">Fuel Sources:</div>
              <div className="flex flex-wrap gap-1">
                {phase.primary_fuel_sources.map((f, i) => (
                  <span key={i} className="px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 text-[10px]">
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )

    case 'phase_3_event_radar':
      return (
        <div className="space-y-2 text-xs">
          <div className="text-grid-textDim mb-2">
            Detected {phase.event_count} grid-relevant events:
          </div>
          {phase.events?.length > 0 ? (
            <div className="space-y-2">
              {phase.events.map((evt, i) => (
                <div key={i} className="p-2 rounded bg-grid-bg/50 border border-orange-500/20">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-orange-400">{evt.event_name || evt.event_type}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/20 text-orange-300">
                      {evt.severity || evt.confidence}
                    </span>
                  </div>
                  {evt.grid_mechanism && (
                    <div className="text-grid-textDim">Mechanism: {evt.grid_mechanism}</div>
                  )}
                  {evt.est_mw_impact && (
                    <div className="text-cyan-400">Impact: {evt.est_mw_impact} MW</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-grid-textDim italic">No significant events detected</div>
          )}
        </div>
      )

    case 'phase_4_headline_filter':
      return (
        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div className="p-2 rounded bg-grid-bg/50">
              <div className="text-grid-textDim">Input Headlines</div>
              <div className="text-lg font-bold text-white">{phase.input_count}</div>
            </div>
            <div className="p-2 rounded bg-grid-bg/50">
              <div className="text-grid-textDim">After Filtering</div>
              <div className="text-lg font-bold text-green-400">{phase.output_count}</div>
            </div>
          </div>
          <div className="text-grid-textDim">
            Removed {phase.input_count - phase.output_count} noise headlines (sports, gossip, irrelevant politics)
          </div>
        </div>
      )

    case 'phase_5_signal_extraction':
      return (
        <div className="space-y-2 text-xs">
          <div className="text-grid-textDim mb-2">Extracted Infrastructure Signals:</div>
          {phase.extracted_signals ? (
            <div className="p-3 rounded bg-grid-bg/50 font-mono text-green-400 whitespace-pre-wrap max-h-40 overflow-y-auto">
              {phase.extracted_signals}
            </div>
          ) : (
            <div className="text-grid-textDim italic">No infrastructure signals extracted</div>
          )}
        </div>
      )

    case 'phase_6_impact_narrative':
      return (
        <div className="space-y-2 text-xs">
          <div className="text-grid-textDim mb-2">LLM Chain-of-Thought Analysis:</div>
          {phase.narrative ? (
            <div className="p-3 rounded bg-grid-bg/50 text-grid-textDim whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
              {phase.narrative}
            </div>
          ) : (
            <div className="text-grid-textDim italic">No narrative generated</div>
          )}
        </div>
      )

    case 'phase_7_multiplier_synthesis':
      const m = phase.final_multipliers || {}
      return (
        <div className="space-y-3 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <MultiplierCard label="Economic Demand" value={m.economic_demand_multiplier} unit="x" />
            <MultiplierCard label="Generation Capacity" value={m.generation_capacity_multiplier} unit="x" />
            <MultiplierCard label="Temp Anomaly" value={m.temperature_anomaly} unit="°C" />
            <MultiplierCard label="7-Day Delta" value={m.seven_day_demand_forecast_mw_delta} unit="MW" />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <RiskBadge label="Demand Spike" risk={m.demand_spike_risk} />
            <RiskBadge label="Supply Shortfall" risk={m.supply_shortfall_risk} />
          </div>

          <div className="p-2 rounded bg-grid-bg/50">
            <div className="text-grid-textDim mb-1">Key Driver:</div>
            <div className="text-white">{m.key_driver || 'Baseline'}</div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-grid-textDim">Confidence:</span>
            <div className="flex-1 h-2 bg-grid-bg/50 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-yellow-500 to-green-500"
                style={{ width: `${(m.confidence || 0) * 100}%` }}
              />
            </div>
            <span className="text-white font-mono">{((m.confidence || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>
      )

    default:
      return <div className="text-grid-textDim text-xs">No details available</div>
  }
}

function MultiplierCard({ label, value, unit }) {
  const isNeutral = value === 1.0 || value === 0
  return (
    <div className="p-2 rounded bg-grid-bg/50 border border-grid-border/20">
      <div className="text-[10px] text-grid-textDim">{label}</div>
      <div className={`text-sm font-bold font-mono ${isNeutral ? 'text-white' : 'text-cyan-400'}`}>
        {typeof value === 'number' ? value.toFixed(2) : value}{unit}
      </div>
    </div>
  )
}

function RiskBadge({ label, risk }) {
  const colors = {
    LOW: 'bg-green-500/20 text-green-400 border-green-500/30',
    MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    HIGH: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    CRITICAL: 'bg-red-500/20 text-red-400 border-red-500/30',
    UNKNOWN: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  }
  return (
    <div className={`p-2 rounded border ${colors[risk] || colors.UNKNOWN}`}>
      <div className="text-[10px] opacity-70">{label}</div>
      <div className="text-sm font-bold">{risk || 'UNKNOWN'}</div>
    </div>
  )
}

export function XAIAuditPanel({ regionId }) {
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedPhases, setExpandedPhases] = useState(new Set(['phase_7_multiplier_synthesis']))

  useEffect(() => {
    if (!regionId) return

    async function fetchAudit() {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${BASE_URL}/api/intelligence/${regionId}/audit`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setAudit(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchAudit()
  }, [regionId])

  const togglePhase = (phaseKey) => {
    setExpandedPhases(prev => {
      const next = new Set(prev)
      if (next.has(phaseKey)) {
        next.delete(phaseKey)
      } else {
        next.add(phaseKey)
      }
      return next
    })
  }

  if (!regionId) {
    return (
      <div className="text-center py-8 text-grid-textDim">
        Select a region to view XAI audit
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-red-400">
        <AlertTriangle className="w-6 h-6 mb-2" />
        <div className="text-sm">Failed to load audit: {error}</div>
      </div>
    )
  }

  if (!audit?.phases) {
    return <div className="text-center py-8 text-grid-textDim">No audit data available</div>
  }

  const phaseOrder = [
    'phase_1_data_fetch',
    'phase_2_city_intel',
    'phase_3_event_radar',
    'phase_4_headline_filter',
    'phase_5_signal_extraction',
    'phase_6_impact_narrative',
    'phase_7_multiplier_synthesis',
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-white">{audit.city} Intelligence Audit</h3>
          <p className="text-xs text-grid-textDim">7-phase XAI decision chain</p>
        </div>
        <span className="text-xs text-grid-textDim font-mono">{audit.generated_at}</span>
      </div>

      <div className="space-y-2">
        {phaseOrder.map(phaseKey => {
          const phase = audit.phases[phaseKey]
          if (!phase) return null
          return (
            <PhaseCard
              key={phaseKey}
              phaseKey={phaseKey}
              phase={phase}
              isExpanded={expandedPhases.has(phaseKey)}
              onToggle={() => togglePhase(phaseKey)}
            />
          )
        })}
      </div>
    </div>
  )
}
