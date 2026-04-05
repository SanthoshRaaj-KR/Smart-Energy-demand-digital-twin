'use client'
import { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine
} from 'recharts'
import { REGIONS } from '@/lib/gridMeta'
import { TrendingUp, AlertTriangle, Zap, Brain } from 'lucide-react'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-bright rounded-lg p-3 text-xs border border-cyan-500/20 min-w-[180px]">
      <div className="text-grid-textDim mb-2 font-mono font-bold">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-grid-textDim">{p.name}</span>
          </div>
          <span className="font-bold text-white">{Math.round(p.value).toLocaleString()} MW</span>
        </div>
      ))}
    </div>
  )
}

function ConfidenceBadge({ confidence }) {
  const level = confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low'
  const colors = {
    high: 'bg-green-500/20 text-green-400 border-green-500/30',
    medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    low: 'bg-red-500/20 text-red-400 border-red-500/30',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono border ${colors[level]}`}>
      {(confidence * 100).toFixed(0)}% conf
    </span>
  )
}

export function DemandForecastChart() {
  const [forecasts, setForecasts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeRegions, setActiveRegions] = useState(new Set(REGIONS.map(r => r.id)))
  const [showAdjusted, setShowAdjusted] = useState(true)

  useEffect(() => {
    async function fetchForecasts() {
      try {
        const res = await fetch(`${BASE_URL}/api/demand-forecast`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setForecasts(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    fetchForecasts()
  }, [])

  const toggleRegion = (id) => {
    setActiveRegions(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        if (next.size > 1) next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-red-400">
        <AlertTriangle className="w-8 h-8 mb-2" />
        <div className="text-sm">Failed to load forecasts: {error}</div>
      </div>
    )
  }

  if (!forecasts?.forecasts) {
    return <div className="text-grid-textDim text-sm py-8 text-center">No forecast data available</div>
  }

  // Transform data for chart
  const chartData = []
  const firstRegion = Object.keys(forecasts.forecasts)[0]
  const dates = forecasts.forecasts[firstRegion]?.dates || []

  dates.forEach((date, idx) => {
    const row = { date, day: `Day ${idx + 1}` }
    Object.keys(forecasts.forecasts).forEach(regionId => {
      const fc = forecasts.forecasts[regionId]
      const key = showAdjusted ? 'adjusted_mw' : 'predicted_mw'
      row[regionId] = fc[key]?.[idx] || 0
    })
    chartData.push(row)
  })

  return (
    <div className="glass-bright rounded-xl border border-cyan-500/20 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-cyan-500/20">
            <Brain className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white">LightGBM 7-Day Demand Forecast</h3>
            <p className="text-xs text-grid-textDim">Autoregressive predictions with intelligence multipliers</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAdjusted(!showAdjusted)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all ${
              showAdjusted
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                : 'bg-grid-bg text-grid-textDim border border-grid-border/50'
            }`}
          >
            {showAdjusted ? 'Intelligence-Adjusted' : 'Raw Model Output'}
          </button>
        </div>
      </div>

      {/* Region toggles with confidence badges */}
      <div className="flex flex-wrap gap-2 mb-4">
        {REGIONS.map(r => {
          const fc = forecasts.forecasts[r.id]
          return (
            <button
              key={r.id}
              onClick={() => toggleRegion(r.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all duration-200 border ${
                activeRegions.has(r.id)
                  ? 'border-transparent text-white'
                  : 'border-grid-border/50 text-grid-textDim opacity-50'
              }`}
              style={{
                background: activeRegions.has(r.id) ? `${r.color}22` : 'transparent',
                borderColor: activeRegions.has(r.id) ? `${r.color}44` : undefined,
              }}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: r.color }} />
              <span className="font-mono">{r.id}</span>
              {fc && <ConfidenceBadge confidence={fc.confidence || 0.5} />}
            </button>
          )
        })}
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 30, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,61,0.6)" />
          <XAxis
            dataKey="day"
            tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${(v / 1000).toFixed(1)}k`}
            width={50}
            label={{ value: 'MW', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }}
          />
          <Tooltip content={<CustomTooltip />} />

          {REGIONS.map(r => activeRegions.has(r.id) && (
            <Line
              key={r.id}
              type="monotone"
              dataKey={r.id}
              name={forecasts.forecasts[r.id]?.city || r.name}
              stroke={r.color}
              strokeWidth={2}
              dot={{ r: 4, strokeWidth: 2, fill: '#0d1117' }}
              activeDot={{ r: 6, strokeWidth: 0, fill: r.color }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Intelligence drivers summary */}
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(forecasts.forecasts).map(([regionId, fc]) => {
          const region = REGIONS.find(r => r.id === regionId)
          if (!activeRegions.has(regionId)) return null
          return (
            <div
              key={regionId}
              className="p-3 rounded-lg border"
              style={{
                background: `${region?.color}11`,
                borderColor: `${region?.color}33`,
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="w-2 h-2 rounded-full" style={{ background: region?.color }} />
                <span className="text-xs font-mono text-white">{fc.city}</span>
              </div>
              <div className="text-[10px] text-grid-textDim">
                EDM: {fc.economic_demand_multiplier?.toFixed(2)}x
              </div>
              <div className="text-[10px] text-cyan-400 truncate">
                {fc.key_driver || 'Baseline conditions'}
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-grid-border/30 text-[10px] text-grid-textDim font-mono">
        <span>Model: {forecasts.model}</span>
        <span>Generated: {forecasts.generated_at}</span>
        <span>Features: {forecasts.feature_inputs?.join(', ')}</span>
      </div>
    </div>
  )
}
