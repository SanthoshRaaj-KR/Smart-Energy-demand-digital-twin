'use client'
import { useState } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts'
import { REGIONS } from '@/lib/gridMeta'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-bright rounded-lg p-3 text-xs border border-cyan-500/20">
      <div className="text-grid-textDim mb-2 font-mono">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-grid-textDim">{p.name}:</span>
          <span className="font-bold text-white">{Math.round(p.value).toLocaleString()} MW</span>
        </div>
      ))}
    </div>
  )
}

export function ForecastChart({ forecastData = [] }) {
  const [activeRegions, setActiveRegions] = useState(new Set(REGIONS.map(r => r.id)))

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

  if (!forecastData.length) {
    return <div className="text-grid-textDim text-sm py-8 text-center">No forecast data available</div>
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        {REGIONS.map(r => (
          <button
            key={r.id}
            onClick={() => toggleRegion(r.id)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs transition-all duration-200 border ${
              activeRegions.has(r.id)
                ? 'border-transparent text-white'
                : 'border-grid-border/50 text-grid-textDim opacity-50'
            }`}
            style={{
              background: activeRegions.has(r.id) ? `${r.color}22` : 'transparent',
              borderColor: activeRegions.has(r.id) ? `${r.color}44` : undefined,
              fontFamily: 'IBM Plex Mono, monospace',
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: r.color }} />
            {r.id}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={forecastData} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <defs>
            {REGIONS.map(r => (
              <linearGradient key={r.id} id={`grad-${r.id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={r.color} stopOpacity={0.3} />
                <stop offset="95%" stopColor={r.color} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,45,61,0.6)" />
          <XAxis
            dataKey="day"
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'IBM Plex Mono' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${(v / 1000).toFixed(1)}k`}
            width={42}
          />
          <Tooltip content={<CustomTooltip />} />

          {REGIONS.map(r => activeRegions.has(r.id) && (
            <Area
              key={r.id}
              type="monotone"
              dataKey={r.id}
              name={r.name}
              stroke={r.color}
              strokeWidth={2}
              fill={`url(#grad-${r.id})`}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>

      <div className="flex items-center justify-between mt-2 text-[10px] text-grid-textDim"
        style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
        <span>7-day projection from live grid and intelligence deltas</span>
        <span>Units: MW</span>
      </div>
    </div>
  )
}
