'use client'
import { useState, useEffect } from 'react'
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine
} from 'recharts'
import { REGIONS } from '@/lib/gridMeta'
import { TrendingUp, AlertTriangle, Zap, Brain, Calendar, Shield, Target } from 'lucide-react'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  
  const dataPoint = payload[0]?.payload
  const confidence = dataPoint?.confidence
  
  return (
    <div className="glass-bright rounded-lg p-3 text-xs border border-cyan-500/20 min-w-[200px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-grid-textDim font-mono font-bold">{label}</span>
        {confidence !== undefined && (
          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
            confidence > 0.7 ? 'bg-green-500/20 text-green-400' :
            confidence > 0.4 ? 'bg-yellow-500/20 text-yellow-400' :
            'bg-red-500/20 text-red-400'
          }`}>
            {(confidence * 100).toFixed(0)}% conf
          </span>
        )}
      </div>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-grid-textDim">{p.name}</span>
          </div>
          <span className="font-bold text-white">{Math.round(p.value).toLocaleString()} MW</span>
        </div>
      ))}
      {dataPoint?.lower_bound && dataPoint?.upper_bound && (
        <div className="mt-2 pt-2 border-t border-grid-border/20 text-[10px] text-grid-textDim">
          Range: {Math.round(dataPoint.lower_bound).toLocaleString()} - {Math.round(dataPoint.upper_bound).toLocaleString()} MW
        </div>
      )}
    </div>
  )
}

function ZoneLegend() {
  return (
    <div className="flex items-center gap-4 text-xs">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded bg-gradient-to-r from-green-500/50 to-green-500/20" />
        <span className="text-grid-textDim">High Confidence (Days 1-7)</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded bg-gradient-to-r from-yellow-500/30 to-orange-500/10" />
        <span className="text-grid-textDim">Extended Forecast (Days 8-30)</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-3 h-1 border-t-2 border-dashed border-cyan-500/50" />
        <span className="text-grid-textDim">Uncertainty Band</span>
      </div>
    </div>
  )
}

function MethodologyCard({ methodology }) {
  if (!methodology) return null
  
  return (
    <div className="p-4 rounded-lg bg-gradient-to-br from-purple-500/10 to-cyan-500/10 border border-purple-500/20">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-400" />
        <span className="font-medium text-white text-sm">Forecast Methodology</span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="p-2 rounded bg-grid-bg/50">
          <div className="text-grid-textDim">High Confidence Zone</div>
          <div className="text-white font-mono">{methodology.high_confidence_days} days</div>
        </div>
        <div className="p-2 rounded bg-grid-bg/50">
          <div className="text-grid-textDim">Extended Zone</div>
          <div className="text-white font-mono">{methodology.extended_forecast_days} days</div>
        </div>
        <div className="p-2 rounded bg-grid-bg/50">
          <div className="text-grid-textDim">Confidence Decay</div>
          <div className="text-yellow-400 font-mono">{methodology.confidence_decay_rate}</div>
        </div>
        <div className="p-2 rounded bg-grid-bg/50">
          <div className="text-grid-textDim">Weather Model</div>
          <div className="text-cyan-400 font-mono text-[10px]">{methodology.weather_extrapolation?.slice(0, 25)}...</div>
        </div>
      </div>
    </div>
  )
}

export function Forecast30DayChart() {
  const [forecasts, setForecasts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState('BHR')

  useEffect(() => {
    async function fetchForecasts() {
      try {
        const res = await fetch(`${BASE_URL}/api/demand-forecast-30day`)
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin w-10 h-10 border-3 border-purple-500 border-t-transparent rounded-full mb-3" />
          <div className="text-grid-textDim text-sm">Loading 30-day forecast...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-red-400">
        <AlertTriangle className="w-10 h-10 mb-3" />
        <div className="text-sm mb-2">Failed to load 30-day forecast</div>
        <div className="text-xs text-grid-textDim">{error}</div>
      </div>
    )
  }

  if (!forecasts?.forecasts) {
    return <div className="text-grid-textDim text-sm py-8 text-center">No forecast data available</div>
  }

  const regionForecast = forecasts.forecasts[selectedRegion]
  if (!regionForecast) {
    return <div className="text-grid-textDim text-sm py-8 text-center">No data for {selectedRegion}</div>
  }

  // Transform data for chart
  const chartData = regionForecast.dates.map((date, idx) => ({
    date,
    day: `D${idx + 1}`,
    dayNum: idx + 1,
    predicted: regionForecast.predicted_mw[idx],
    adjusted: regionForecast.adjusted_mw[idx],
    confidence: regionForecast.confidence[idx],
    lower_bound: regionForecast.lower_bound[idx],
    upper_bound: regionForecast.upper_bound[idx],
    zone: idx < 7 ? 'high' : 'extended',
  }))

  const region = REGIONS.find(r => r.id === selectedRegion)

  return (
    <div className="glass-bright rounded-xl border border-purple-500/20 p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-gradient-to-br from-purple-500/20 to-orange-500/20">
            <Calendar className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-lg">30-Day Demand Forecast</h3>
            <p className="text-xs text-grid-textDim">Extended prediction with uncertainty quantification</p>
          </div>
        </div>
        
        {/* Region Selector */}
        <div className="flex gap-2">
          {REGIONS.map(r => (
            <button
              key={r.id}
              onClick={() => setSelectedRegion(r.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs transition-all ${
                selectedRegion === r.id
                  ? 'bg-gradient-to-r from-purple-500/30 to-cyan-500/30 text-white border border-purple-500/40'
                  : 'bg-grid-bg text-grid-textDim hover:bg-white/5'
              }`}
            >
              <span className="w-2 h-2 rounded-full" style={{ background: r.color }} />
              {r.id}
            </button>
          ))}
        </div>
      </div>

      {/* Zone Legend */}
      <div className="mb-4">
        <ZoneLegend />
      </div>

      {/* Main Chart */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, bottom: 10, left: 0 }}>
          <defs>
            {/* High confidence zone gradient */}
            <linearGradient id="highConfGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
            </linearGradient>
            {/* Extended zone gradient */}
            <linearGradient id="extendedGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.02} />
            </linearGradient>
            {/* Uncertainty band gradient */}
            <linearGradient id="uncertaintyGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={region?.color || '#06b6d4'} stopOpacity={0.15} />
              <stop offset="95%" stopColor={region?.color || '#06b6d4'} stopOpacity={0.02} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,61,0.6)" />
          
          {/* Reference line at day 7 boundary */}
          <ReferenceLine
            x="D7"
            stroke="#a855f7"
            strokeDasharray="5 5"
            strokeWidth={2}
            label={{
              value: 'Confidence Boundary',
              position: 'top',
              fill: '#a855f7',
              fontSize: 10,
            }}
          />

          <XAxis
            dataKey="day"
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
            interval={4}
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${(v / 1000).toFixed(1)}k`}
            width={50}
            label={{ value: 'MW', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }}
          />

          <Tooltip content={<CustomTooltip />} />

          {/* Uncertainty band (area between lower and upper bounds) */}
          <Area
            type="monotone"
            dataKey="upper_bound"
            stroke="none"
            fill="url(#uncertaintyGrad)"
            fillOpacity={1}
            name="Upper Bound"
            legendType="none"
          />
          <Area
            type="monotone"
            dataKey="lower_bound"
            stroke="none"
            fill="#0d1117"
            fillOpacity={1}
            name="Lower Bound"
            legendType="none"
          />

          {/* Intelligence-adjusted prediction line */}
          <Line
            type="monotone"
            dataKey="adjusted"
            name="Adjusted Forecast"
            stroke={region?.color || '#06b6d4'}
            strokeWidth={3}
            dot={(props) => {
              const { cx, cy, payload } = props
              const isHighConf = payload.dayNum <= 7
              return (
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHighConf ? 5 : 3}
                  fill={isHighConf ? '#22c55e' : '#f59e0b'}
                  stroke={region?.color || '#06b6d4'}
                  strokeWidth={2}
                />
              )
            }}
            activeDot={{ r: 7, strokeWidth: 0, fill: region?.color || '#06b6d4' }}
          />

          {/* Raw model prediction (dashed) */}
          <Line
            type="monotone"
            dataKey="predicted"
            name="Raw Model"
            stroke="#64748b"
            strokeWidth={1}
            strokeDasharray="4 4"
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Stats Summary */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-4 h-4 text-green-400" />
            <span className="text-xs text-grid-textDim">7-Day Avg Confidence</span>
          </div>
          <div className="text-xl font-bold text-green-400">
            {(regionForecast.confidence.slice(0, 7).reduce((a, b) => a + b, 0) / 7 * 100).toFixed(0)}%
          </div>
        </div>

        <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-center gap-2 mb-1">
            <Target className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-grid-textDim">30-Day Avg Confidence</span>
          </div>
          <div className="text-xl font-bold text-yellow-400">
            {(regionForecast.confidence.reduce((a, b) => a + b, 0) / 30 * 100).toFixed(0)}%
          </div>
        </div>

        <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-cyan-400" />
            <span className="text-xs text-grid-textDim">Peak Demand</span>
          </div>
          <div className="text-xl font-bold text-cyan-400">
            {Math.max(...regionForecast.adjusted_mw).toLocaleString()} MW
          </div>
        </div>

        <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-grid-textDim">Intelligence Multiplier</span>
          </div>
          <div className="text-xl font-bold text-purple-400">
            {regionForecast.intelligence?.multiplier?.toFixed(2) || '1.00'}x
          </div>
        </div>
      </div>

      {/* Methodology */}
      <div className="mt-6">
        <MethodologyCard methodology={forecasts.methodology} />
      </div>

      {/* Patent Claims */}
      {forecasts.patent_claims && (
        <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5" />
            <div>
              <div className="text-xs font-medium text-yellow-400 mb-1">Patent-Worthy Innovations</div>
              <ul className="text-[10px] text-yellow-200 space-y-0.5">
                {forecasts.patent_claims.map((claim, i) => (
                  <li key={i}>• {claim}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-grid-border/30 flex items-center justify-between text-[10px] text-grid-textDim font-mono">
        <span>Model: {forecasts.model}</span>
        <span>Region: {regionForecast.city || selectedRegion}</span>
        <span>Generated: {forecasts.generated_at}</span>
      </div>
    </div>
  )
}
