'use client'
import { Brain, MessageSquare, AlertTriangle } from 'lucide-react'
import { useIntelligence } from '@/hooks/useApi'
import { RegionCard } from '@/components/agents/RegionCard'
import { Card, SectionLabel, Badge, Skeleton } from '@/components/ui/Primitives'
import { REGIONS } from '@/lib/gridMeta'

function getRegionData(data, id) {
  if (!data || typeof data !== 'object') return null
  return data[id] || null
}

function countRisks(regionData) {
  if (!regionData) return 0
  const gm = regionData.grid_multipliers || {}
  const flags = [
    ['HIGH', 'MEDIUM'].includes(String(gm.demand_spike_risk || '').toUpperCase()),
    ['HIGH', 'MEDIUM'].includes(String(gm.supply_shortfall_risk || '').toUpperCase()),
    Boolean(gm.pre_event_hoard),
  ]
  return flags.filter(Boolean).length
}

function globalSummary(data) {
  if (!data) return 'Intelligence feed is unavailable.'
  const pieces = REGIONS.map(region => {
    const item = data[region.id]
    if (!item) return null
    const gm = item.grid_multipliers || {}
    const delta = Number(gm.seven_day_demand_forecast_mw_delta || 0)
    const dir = delta >= 0 ? '+' : ''
    return `${region.id}: ${dir}${delta.toFixed(0)} MW, driver ${gm.key_driver || 'n/a'}`
  }).filter(Boolean)

  return pieces.join(' | ') || 'No intelligence summary available.'
}

export default function IntelligencePage() {
  const { data, loading } = useIntelligence()
  const summary = globalSummary(data)

  return (
    <div className="pt-14">
      <div className="relative border-b border-grid-border/50 overflow-hidden">
        <div className="absolute inset-0 grid-dots opacity-40" />
        <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-px w-6 bg-cyan-400" />
                <span className="text-[10px] uppercase tracking-[0.3em] text-cyan-400" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  LLM Agent Analysis
                </span>
              </div>
              <h1 className="text-4xl font-bold text-white mb-1" style={{ fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.05em' }}>
                INTELLIGENCE AGENTS
              </h1>
              <p className="text-grid-textDim text-sm max-w-xl">
                Vulnerabilities, causes, risk flags, and expected impact by region.
              </p>
            </div>
            <Badge variant="cyan"><Brain className="w-3 h-3" />AGENTS ONLINE</Badge>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <Card className="glow-cyan">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
              <MessageSquare className="w-4.5 h-4.5 text-cyan-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <SectionLabel>Grid-Wide Summary</SectionLabel>
                <Badge variant="cyan">FROM CACHE</Badge>
              </div>
              {loading ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              ) : (
                <p className="text-sm text-grid-text leading-relaxed">{summary}</p>
              )}
            </div>
          </div>
        </Card>

        {!loading && data && (
          <div className="flex flex-wrap gap-3">
            {REGIONS.map(region => {
              const count = countRisks(getRegionData(data, region.id))
              return (
                <div key={region.id} className="flex items-center gap-2 px-3 py-2 rounded-lg border" style={{
                  background: count > 0 ? 'rgba(245,158,11,0.05)' : 'rgba(16,185,129,0.05)',
                  borderColor: count > 0 ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.15)',
                }}>
                  <span className="text-xs font-bold" style={{ color: region.color, fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.1em' }}>{region.id}</span>
                  {count === 0 ? (
                    <span className="text-[10px] text-green-400" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>No active risks</span>
                  ) : (
                    <span className="text-[10px] text-amber-400 flex items-center gap-1" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                      <AlertTriangle className="w-3 h-3" />
                      {count} risk{count > 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {loading ? (
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <Card key={i}><Skeleton className="h-64 w-full" /></Card>
            ))}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4">
            {REGIONS.map(region => (
              <RegionCard key={region.id} regionId={region.id} data={getRegionData(data, region.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
