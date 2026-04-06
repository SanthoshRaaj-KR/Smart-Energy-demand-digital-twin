'use client'
import { useMemo, useState, useEffect } from 'react'
import { Activity, Cpu, GitBranch, Zap, BarChart2, CloudLightning, ChevronRight, Workflow, ShieldCheck, Brain } from 'lucide-react'
import Link from 'next/link'
import { ForecastChart } from '@/components/charts/ForecastChart'
import { GridMap } from '@/components/grid/GridMap'
import { Card, SectionLabel, StatBlock, ProgressBar, Badge } from '@/components/ui/Primitives'
import { PipelineStatusBar } from '@/components/ui/PipelineExplainer'
import { usePipeline } from '@/hooks/usePipeline'
import { REGIONS } from '@/lib/gridMeta'

const FEATURE_CARDS = [
  {
    icon: Brain,
    color: '#00d4ff',
    title: 'Stage 1 + 2 Intelligence Gate',
    body: 'LightGBM prepares the baseline; LLM agents wake only when Delta anomalies break that baseline.',
  },
  {
    icon: GitBranch,
    color: '#0066ff',
    title: 'Stage 3 Waterfall Routing',
    body: 'Deficits are resolved in strict order: Battery, DR Auction, BFS Transmission, then controlled fallback.',
  },
  {
    icon: ShieldCheck,
    color: '#10b981',
    title: 'Stage 4 Self-Healing XAI',
    body: 'A human-readable 7-phase audit ledger explains daily decisions and memory warnings for next-day adaptation.',
  },
]

function buildForecastData(nodes = [], intelligence = null) {
  if (!nodes.length) return []

  const byId = Object.fromEntries(nodes.map(node => [node.id, node]))
  const start = new Date()

  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setDate(d.getDate() + i)

    const row = {
      day: d.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' }),
    }

    for (const region of REGIONS) {
      const node = byId[region.id]
      const base = Number(node?.adjusted_demand_mw || node?.demand_mw || 0)
      const intel = intelligence?.[region.id]?.grid_multipliers || {}
      const delta7d = Number(intel.seven_day_demand_forecast_mw_delta || 0)
      const value = base + (delta7d * (i / 6))
      row[region.id] = Number.isFinite(value) ? Math.max(0, value) : 0
    }

    return row
  })
}

function LiveStatRow({ nodes }) {
  const totalDemand = nodes.reduce((sum, node) => sum + Number(node.adjusted_demand_mw || node.demand_mw || 0), 0)
  const totalSupply = nodes.reduce((sum, node) => sum + Number(node.generation_mw || 0), 0)
  const netBalance = totalSupply - totalDemand

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[
        { label: 'Total Demand', value: (totalDemand / 1000).toFixed(1), unit: 'GW', color: 'text-amber-400' },
        { label: 'Total Supply', value: (totalSupply / 1000).toFixed(1), unit: 'GW', color: 'text-green-400' },
        { label: 'Net Balance', value: (netBalance > 0 ? '+' : '') + netBalance.toFixed(1), unit: 'MW', color: netBalance >= 0 ? 'text-cyan-400' : 'text-red-400' },
        { label: 'Active Regions', value: nodes.length, unit: 'nodes', color: 'text-purple-400' },
      ].map(stat => (
        <Card key={stat.label} className="py-4">
          <StatBlock {...stat} />
        </Card>
      ))}
    </div>
  )
}

function RegionStatusRow({ nodes }) {
  const byId = Object.fromEntries(nodes.map(node => [node.id, node]))

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {REGIONS.map(region => {
        const status = byId[region.id]
        const supply = Number(status?.generation_mw || 0)
        const demand = Number(status?.adjusted_demand_mw || status?.demand_mw || 0)
        const balance = Number(status?.balance_mw || 0)
        const soc = Number(status?.battery?.soc || 0)
        const socPct = Math.round(soc * 100)

        return (
          <Card key={region.id} className="p-4">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-bold tracking-widest"
                  style={{ fontFamily: 'Rajdhani, sans-serif', color: region.color }}>
                  {region.id}
                </div>
                <div className="text-[10px] text-grid-textDim">{region.name}</div>
              </div>
              <Badge variant={balance < 0 ? 'red' : 'green'}>
                {balance < 0 ? `v${Math.abs(balance).toFixed(1)}` : `^${balance.toFixed(1)}`} MW
              </Badge>
            </div>

            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-[10px] text-grid-textDim mb-1">
                  <span>Supply / Demand</span>
                  <span style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {supply.toFixed(1)} / {demand.toFixed(1)} MW
                  </span>
                </div>
                <ProgressBar
                  value={supply}
                  max={Math.max(supply, demand, 1)}
                  color={region.color}
                />
              </div>
              <div>
                <div className="flex justify-between text-[10px] text-grid-textDim mb-1">
                  <span>Battery SoC</span>
                  <span style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{socPct}%</span>
                </div>
                <ProgressBar
                  value={socPct}
                  max={100}
                  color={socPct > 60 ? '#10b981' : socPct > 30 ? '#f59e0b' : '#ef4444'}
                />
              </div>
            </div>
          </Card>
        )
      })}
    </div>
  )
}

export default function HomePage() {
  const [mounted, setMounted] = useState(false)
  
  // Use unified pipeline instead of separate hooks
  const {
    stage,
    stageHistory,
    intelligence,
    gridStatus,
    isReady,
    isLoading,
  } = usePipeline({ autoStart: true })

  useEffect(() => setMounted(true), [])

  const nodes = gridStatus?.nodes || []
  const edges = gridStatus?.edges || []
  const forecastData = useMemo(() => buildForecastData(nodes, intelligence), [nodes, intelligence])

  return (
    <div className="pt-14">
      <section className="relative min-h-[85vh] flex flex-col items-center justify-center overflow-hidden grid-dots">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full opacity-5"
            style={{ background: 'radial-gradient(circle, #00d4ff, transparent)', filter: 'blur(60px)' }} />
          <div className="absolute bottom-1/4 right-1/4 w-80 h-80 rounded-full opacity-4"
            style={{ background: 'radial-gradient(circle, #10b981, transparent)', filter: 'blur(60px)' }} />
        </div>

        <div className="max-w-7xl mx-auto px-6 w-full">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="h-px w-8 bg-cyan-400" />
                <span className="text-[10px] uppercase tracking-[0.3em] text-cyan-400"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  Digital Twin Infrastructure
                </span>
              </div>

              <h1 className="mb-6 leading-none"
                style={{ fontFamily: 'Rajdhani, sans-serif', fontWeight: 700 }}>
                <span className="block text-5xl lg:text-7xl text-white tracking-tight">INDIA GRID</span>
                <span className="block text-4xl lg:text-6xl tracking-tight"
                  style={{ background: 'linear-gradient(90deg, #00d4ff, #0066ff)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  DIGITAL TWIN
                </span>
              </h1>

              <p className="text-grid-textDim text-base leading-relaxed mb-8 max-w-lg">
                A phase-by-phase Smart Grid digital twin: forecast baseline, detect deltas, route deficits, and learn from failures with explainable ledgers.
              </p>

              <div className="flex flex-wrap gap-3">
                <Link href="/pipeline"
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
                  style={{ background: 'rgba(139,92,246,0.1)', color: '#a78bfa', border: '1px solid rgba(139,92,246,0.2)', fontFamily: 'Rajdhani, sans-serif', fontWeight: 600, letterSpacing: '0.05em' }}>
                  <Workflow className="w-4 h-4" />
                  Stage-by-Stage Pipeline
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
                <Link href="/intelligence"
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
                  style={{ background: 'rgba(0,212,255,0.1)', color: '#00d4ff', border: '1px solid rgba(0,212,255,0.2)', fontFamily: 'Rajdhani, sans-serif', fontWeight: 600, letterSpacing: '0.05em' }}>
                  <Activity className="w-4 h-4" />
                  Delta Intelligence
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
                <Link href="/simulation"
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
                  style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)', fontFamily: 'Rajdhani, sans-serif', fontWeight: 600, letterSpacing: '0.05em' }}>
                  <Zap className="w-4 h-4" />
                  Waterfall + XAI
                  <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div className="flex flex-wrap gap-2 mt-6">
                {['Stage 1 Planner', 'Stage 2 Delta', 'Stage 3 Waterfall', 'Stage 4 Memory', 'XAI Ledger'].map(tag => (
                  <span key={tag} className="text-[9px] px-2 py-0.5 rounded border border-grid-border/60 text-grid-textDim"
                    style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {tag}
                  </span>
                ))}
              </div>
            </div>

            <div className="relative">
              <div className="glass rounded-2xl p-4 glow-cyan">
                <div className="flex items-center justify-between mb-3">
                  <SectionLabel>Live Grid Topology</SectionLabel>
                  <div className="flex items-center gap-1.5 text-[10px] text-green-400"
                    style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                    LIVE
                  </div>
                </div>
                {mounted && <GridMap animated className="h-64 lg:h-80" nodes={nodes} edges={edges} />}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-8">
        {/* Pipeline Status Bar */}
        <Link href="/pipeline" className="block mb-6">
          <PipelineStatusBar 
            stage={stage} 
            stageHistory={stageHistory}
            onExpand={() => {}}
          />
        </Link>
        
        <div className="flex items-center gap-3 mb-4">
          <SectionLabel>Real-Time Grid Status</SectionLabel>
          <div className="flex-1 h-px bg-grid-border/30" />
          <span className="text-[10px] text-grid-textDim"
            style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            Updated: {new Date().toLocaleTimeString('en-IN')} IST
          </span>
        </div>
        <LiveStatRow nodes={nodes} />
        <div className="mt-3">
          <RegionStatusRow nodes={nodes} />
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-6">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-lg font-bold text-white"
                style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                7-Day Demand Forecast
              </div>
              <div className="text-xs text-grid-textDim">Derived from live demand and intelligence deltas</div>
            </div>
            <Badge variant="cyan">
              <BarChart2 className="w-3 h-3" />
              LIVE FORECAST
            </Badge>
          </div>
          <ForecastChart forecastData={forecastData} />
        </Card>
      </section>

      <section className="max-w-7xl mx-auto px-6 py-8">
        <div className="text-center mb-8">
          <div className="text-[10px] uppercase tracking-[0.3em] text-cyan-400 mb-2"
            style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            Capabilities
          </div>
          <h2 className="text-3xl font-bold text-white"
            style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            What This System Does
          </h2>
        </div>
        <div className="grid md:grid-cols-3 gap-4">
          {FEATURE_CARDS.map((card, i) => {
            const Icon = card.icon
            return (
              <Card key={i} className="group hover:scale-[1.02] transition-transform duration-200">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
                  style={{ background: `${card.color}15`, border: `1px solid ${card.color}25` }}>
                  <Icon className="w-5 h-5" style={{ color: card.color }} />
                </div>
                <h3 className="text-lg font-bold text-white mb-2"
                  style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                  {card.title}
                </h3>
                <p className="text-sm text-grid-textDim leading-relaxed">{card.body}</p>
              </Card>
            )
          })}
        </div>
      </section>

      <div className="h-12" />
    </div>
  )
}
