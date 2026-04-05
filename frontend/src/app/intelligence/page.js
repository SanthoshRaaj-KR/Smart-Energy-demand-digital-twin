'use client'
import { useState } from 'react'
import { Brain, Radar, AlertTriangle, RefreshCw, CheckCircle, Play } from 'lucide-react'
import { usePipeline, STAGES } from '@/hooks/usePipeline'
import { PipelineStatusBar } from '@/components/ui/PipelineExplainer'
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

function topSummary(data) {
  if (!data) return 'Intelligence feed unavailable.'
  const rows = REGIONS.map(region => {
    const item = data[region.id]
    if (!item) return null
    const gm = item.grid_multipliers || {}
    const delta = Number(gm.seven_day_demand_forecast_mw_delta || 0)
    return {
      id: region.id,
      delta,
      driver: gm.key_driver || 'n/a',
      risks: countRisks(item),
      color: region.color,
    }
  }).filter(Boolean)

  const highest = [...rows].sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta)).slice(0, 2)
  if (!highest.length) return 'No intelligence summary available.'

  return highest.map(r => `${r.id}: ${r.delta >= 0 ? '+' : ''}${r.delta.toFixed(0)} MW | ${r.driver}`).join('  |  ')
}

function PipelineAlert({ stage, onGenerate, onRetry }) {
  const needsGeneration = stage === STAGES.INTELLIGENCE_MISSING
  const isGenerating = stage === STAGES.GENERATING_INTELLIGENCE
  const isError = stage === STAGES.ERROR
  
  if (!needsGeneration && !isGenerating && !isError) return null
  
  return (
    <Card className={`mb-6 ${needsGeneration ? 'border-amber-500/30' : isError ? 'border-red-500/30' : 'border-purple-500/30'}`}>
      <div className="flex items-start gap-4">
        <div className={`
          w-10 h-10 rounded-lg flex items-center justify-center shrink-0
          ${needsGeneration ? 'bg-amber-500/10' : isError ? 'bg-red-500/10' : 'bg-purple-500/10'}
        `}>
          {needsGeneration && <AlertTriangle className="w-5 h-5 text-amber-400" />}
          {isGenerating && <Brain className="w-5 h-5 text-purple-400 animate-pulse" />}
          {isError && <AlertTriangle className="w-5 h-5 text-red-400" />}
        </div>
        <div className="flex-1">
          <h3 className="font-bold text-white mb-1" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {needsGeneration && 'Intelligence Data Required'}
            {isGenerating && 'Generating Intelligence...'}
            {isError && 'Pipeline Error'}
          </h3>
          <p className="text-sm text-grid-textDim mb-3">
            {needsGeneration && 'No cached intelligence found. Generate fresh AI analysis for all regions to see accurate data.'}
            {isGenerating && 'The AI agent is analyzing news, weather, and market data for each region. This may take a minute.'}
            {isError && 'Failed to load intelligence data. Check if the backend server is running.'}
          </p>
          <div className="flex gap-2">
            {needsGeneration && (
              <button
                onClick={onGenerate}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                style={{ 
                  background: 'rgba(139,92,246,0.15)', 
                  color: '#a78bfa', 
                  border: '1px solid rgba(139,92,246,0.3)',
                  fontFamily: 'Rajdhani, sans-serif',
                }}
              >
                <Brain className="w-4 h-4" />
                Generate Intelligence Now
              </button>
            )}
            {isError && (
              <button
                onClick={onRetry}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all hover:scale-105"
                style={{ 
                  background: 'rgba(34,211,238,0.15)', 
                  color: '#22d3ee', 
                  border: '1px solid rgba(34,211,238,0.3)',
                  fontFamily: 'Rajdhani, sans-serif',
                }}
              >
                <RefreshCw className="w-4 h-4" />
                Retry Pipeline
              </button>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}

export default function IntelligencePage() {
  const { 
    stage, 
    stageHistory, 
    intelligence: data, 
    isLoading, 
    isReady,
    needsGeneration,
    hasIntelligence,
    runPipeline,
    generateIntelligence,
  } = usePipeline({ autoStart: true })
  
  const [showPipelineDetails, setShowPipelineDetails] = useState(false)
  const loading = isLoading && !hasIntelligence
  const summary = topSummary(data)

  return (
    <div className="pt-14">
      <div className="relative border-b border-grid-border/50 overflow-hidden">
        <div className="absolute inset-0 grid-dots opacity-40" />
        <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-px w-6 bg-cyan-400" />
                <span className="text-[10px] uppercase tracking-[0.3em] text-cyan-400" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  Intelligence Command Deck
                </span>
              </div>
              <h1 className="text-4xl font-bold text-white mb-1" style={{ fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.05em' }}>
                REGIONAL INTELLIGENCE
              </h1>
              <p className="text-grid-textDim text-sm max-w-2xl">
                Clean regional cards with demand drivers, seasonal demand factors, key vulnerabilities, fuel supply routes, and primary fuel sources.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={isReady ? 'green' : loading ? 'cyan' : 'amber'}>
                {isReady ? <CheckCircle className="w-3 h-3" /> : <Brain className="w-3 h-3" />}
                {isReady ? 'PIPELINE READY' : loading ? 'LOADING' : 'NEEDS DATA'}
              </Badge>
              {isReady && (
                <button
                  onClick={() => generateIntelligence()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs transition-all hover:scale-105"
                  style={{ 
                    background: 'rgba(139,92,246,0.15)', 
                    color: '#a78bfa', 
                    border: '1px solid rgba(139,92,246,0.2)',
                    fontFamily: 'IBM Plex Mono, monospace',
                  }}
                >
                  <RefreshCw className="w-3 h-3" />
                  Refresh
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Pipeline Status Bar */}
        <PipelineStatusBar 
          stage={stage} 
          stageHistory={stageHistory}
          onExpand={() => setShowPipelineDetails(!showPipelineDetails)}
        />
        
        {/* Pipeline Alert for missing data */}
        <PipelineAlert 
          stage={stage} 
          onGenerate={generateIntelligence}
          onRetry={runPipeline}
        />
        
        <Card className="glow-cyan">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
              <Radar className="w-4.5 h-4.5 text-cyan-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <SectionLabel>Priority Snapshot</SectionLabel>
                <Badge variant={hasIntelligence ? 'cyan' : 'amber'}>
                  {hasIntelligence ? 'LIVE CACHE' : 'FALLBACK DATA'}
                </Badge>
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
                  background: count > 0 ? 'rgba(245,158,11,0.07)' : 'rgba(16,185,129,0.07)',
                  borderColor: count > 0 ? 'rgba(245,158,11,0.25)' : 'rgba(16,185,129,0.2)',
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
          <div className="grid md:grid-cols-2 gap-6 items-start">
            {[1, 2, 3, 4].map(i => (
              <Card key={i}><Skeleton className="h-[360px] w-full" /></Card>
            ))}
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-6 items-start">
            {REGIONS.map(region => (
              <RegionCard key={region.id} regionId={region.id} data={getRegionData(data, region.id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
