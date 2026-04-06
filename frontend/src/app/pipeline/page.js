'use client'
import { useState, useEffect } from 'react'
import { 
  Workflow, Brain, RefreshCw, CheckCircle, XCircle, 
  AlertTriangle, Play, Pause, RotateCcw, ChevronRight,
  Activity, Zap, Clock, TrendingUp, Shield
} from 'lucide-react'
import Link from 'next/link'
import { usePipeline, STAGES, STAGE_META } from '@/hooks/usePipeline'
import { PipelineExplainer, PipelineFlow, PipelineStatusBar } from '@/components/ui/PipelineExplainer'
import { Card, SectionLabel, Badge, StatBlock, ProgressBar } from '@/components/ui/Primitives'
import { REGIONS } from '@/lib/gridMeta'

function DataQualityGauge({ label, value, max = 100, threshold = 70 }) {
  const pct = Math.round((value / max) * 100)
  const color = pct >= threshold ? '#22c55e' : pct >= 50 ? '#f59e0b' : '#ef4444'
  
  return (
    <div className="p-4 rounded-xl bg-black/40 border border-grid-border/30">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-grid-textDim uppercase tracking-wider">{label}</span>
        <span className="text-lg font-bold" style={{ color, fontFamily: 'Rajdhani, sans-serif' }}>
          {pct}%
        </span>
      </div>
      <ProgressBar value={pct} max={100} color={color} height={6} />
    </div>
  )
}

function IntelligenceSummaryCard({ intelligence }) {
  if (!intelligence) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8">
          <div className="text-center">
            <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
            <p className="text-sm text-grid-textDim">No intelligence data loaded</p>
          </div>
        </div>
      </Card>
    )
  }
  
  const regions = Object.values(intelligence)
  const avgConfidence = regions.reduce((sum, r) => 
    sum + (r.grid_multipliers?.confidence || 0), 0) / regions.length
  const highRiskCount = regions.filter(r => 
    ['HIGH', 'MEDIUM'].includes(r.grid_multipliers?.demand_spike_risk)).length
  const eventsCount = regions.reduce((sum, r) => 
    sum + (r.detected_events?.length || 0), 0)
  
  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-5 h-5 text-purple-400" />
        <h3 className="font-bold text-white" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
          Intelligence Summary
        </h3>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
          <div className="text-[10px] text-purple-300 uppercase tracking-wider mb-1">Regions</div>
          <div className="text-2xl font-bold text-purple-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {regions.length}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
          <div className="text-[10px] text-cyan-300 uppercase tracking-wider mb-1">Avg Confidence</div>
          <div className="text-2xl font-bold text-cyan-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {(avgConfidence * 100).toFixed(0)}%
          </div>
        </div>
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <div className="text-[10px] text-amber-300 uppercase tracking-wider mb-1">Risk Alerts</div>
          <div className="text-2xl font-bold text-amber-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {highRiskCount}
          </div>
        </div>
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
          <div className="text-[10px] text-green-300 uppercase tracking-wider mb-1">Events</div>
          <div className="text-2xl font-bold text-green-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {eventsCount}
          </div>
        </div>
      </div>
      
      <div className="space-y-2">
        {REGIONS.map(region => {
          const data = intelligence[region.id]
          const gm = data?.grid_multipliers || {}
          const conf = Math.round((gm.confidence || 0) * 100)
          const risk = gm.demand_spike_risk || 'UNKNOWN'
          
          return (
            <div 
              key={region.id}
              className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-grid-border/20"
            >
              <div className="flex items-center gap-3">
                <span 
                  className="w-2 h-2 rounded-full"
                  style={{ background: region.color }}
                />
                <span className="text-sm font-bold" style={{ color: region.color, fontFamily: 'Rajdhani, sans-serif' }}>
                  {region.id}
                </span>
                <span className="text-xs text-grid-textDim">{region.name}</span>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={
                  risk === 'HIGH' ? 'red' : 
                  risk === 'MEDIUM' ? 'amber' : 'green'
                }>
                  {risk}
                </Badge>
                <span 
                  className="text-xs px-2 py-0.5 rounded bg-white/5"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}
                >
                  {conf}% conf
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function GridStatusCard({ gridStatus }) {
  if (!gridStatus) {
    return (
      <Card>
        <div className="flex items-center justify-center py-8">
          <div className="text-center">
            <Activity className="w-12 h-12 text-grid-textDim mx-auto mb-3 opacity-30" />
            <p className="text-sm text-grid-textDim">Grid status not loaded</p>
          </div>
        </div>
      </Card>
    )
  }
  
  const nodes = gridStatus.nodes || []
  const edges = gridStatus.edges || []
  const totalGen = nodes.reduce((sum, n) => sum + (n.generation_mw || 0), 0)
  const totalDem = nodes.reduce((sum, n) => sum + (n.adjusted_demand_mw || n.demand_mw || 0), 0)
  const avgCongestion = edges.length 
    ? edges.reduce((sum, e) => sum + (e.congestion || 0), 0) / edges.length 
    : 0
  
  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-cyan-400" />
        <h3 className="font-bold text-white" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
          Grid Status
        </h3>
        <Badge variant="cyan">LIVE</Badge>
      </div>
      
      <div className="grid grid-cols-3 gap-3">
        <div className="p-3 rounded-lg bg-green-500/10 border border-green-500/20">
          <div className="text-[10px] text-green-300 uppercase tracking-wider mb-1">Generation</div>
          <div className="text-xl font-bold text-green-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {(totalGen / 1000).toFixed(1)} <span className="text-xs">GW</span>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
          <div className="text-[10px] text-amber-300 uppercase tracking-wider mb-1">Demand</div>
          <div className="text-xl font-bold text-amber-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {(totalDem / 1000).toFixed(1)} <span className="text-xs">GW</span>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
          <div className="text-[10px] text-cyan-300 uppercase tracking-wider mb-1">Congestion</div>
          <div className="text-xl font-bold text-cyan-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            {(avgCongestion * 100).toFixed(0)}%
          </div>
        </div>
      </div>
      
      <div className="mt-4 p-3 rounded-lg bg-white/5 border border-grid-border/20">
        <div className="flex justify-between text-xs mb-2">
          <span className="text-grid-textDim">Supply/Demand Balance</span>
          <span className={totalGen >= totalDem ? 'text-green-400' : 'text-red-400'}>
            {totalGen >= totalDem ? '+' : ''}{(totalGen - totalDem).toFixed(0)} MW
          </span>
        </div>
        <ProgressBar 
          value={totalGen} 
          max={Math.max(totalGen, totalDem)} 
          color={totalGen >= totalDem ? '#22c55e' : '#ef4444'}
          height={8}
        />
      </div>
    </Card>
  )
}

function StageHistoryTimeline({ history }) {
  if (!history.length) {
    return (
      <div className="text-center py-6 text-grid-textDim text-sm">
        No pipeline activity yet. Start the pipeline to see history.
      </div>
    )
  }
  
  return (
    <div className="space-y-2">
      {history.map((entry, idx) => {
        const meta = STAGE_META[entry.stage]
        const isError = entry.status === 'error'
        const isComplete = entry.status === 'completed'
        
        return (
          <div 
            key={idx}
            className="flex items-start gap-3 p-3 rounded-lg bg-white/5 border border-grid-border/20"
          >
            <div 
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{ 
                background: isError ? '#ef444420' : isComplete ? '#22c55e20' : '#3b82f620',
                border: `1px solid ${isError ? '#ef444440' : isComplete ? '#22c55e40' : '#3b82f640'}`,
              }}
            >
              {isError ? (
                <XCircle className="w-4 h-4 text-red-400" />
              ) : isComplete ? (
                <CheckCircle className="w-4 h-4 text-green-400" />
              ) : (
                <Clock className="w-4 h-4 text-blue-400" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">{meta?.label || entry.stage}</span>
                <Badge variant={isError ? 'red' : isComplete ? 'green' : 'cyan'}>
                  {entry.status}
                </Badge>
              </div>
              <div className="text-[10px] text-grid-textDim mt-1" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                {new Date(entry.timestamp).toLocaleTimeString()}
                {entry.details && Object.keys(entry.details).length > 0 && (
                  <span className="ml-2">
                    {Object.entries(entry.details).map(([k, v]) => `${k}: ${v}`).join(' | ')}
                  </span>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function PipelinePage() {
  const pipeline = usePipeline({ autoStart: true })
  const [showHistory, setShowHistory] = useState(false)
  
  const {
    stage,
    stageMeta,
    error,
    intelligence,
    gridStatus,
    simulation,
    stageHistory,
    isLoading,
    isReady,
    needsGeneration,
    hasIntelligence,
    runPipeline,
    generateIntelligence,
    forceRegenerate,
  } = pipeline

  return (
    <div className="pt-14">
      {/* Hero Header */}
      <div className="relative border-b border-grid-border/50 overflow-hidden">
        <div className="absolute inset-0 grid-dots opacity-40" />
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse at 50% 0%, ${stageMeta?.color}15, transparent 70%)`,
          }}
        />
        
        <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-px w-6 bg-cyan-400" />
                <span 
                  className="text-[10px] uppercase tracking-[0.3em] text-cyan-400"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}
                >
                  XAI Command Center
                </span>
              </div>
              <h1 
                className="text-4xl font-bold text-white mb-1"
                style={{ fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.05em' }}
              >
                DATA PIPELINE
              </h1>
              <p className="text-grid-textDim text-sm max-w-xl">
                Human-readable 4-stage grid workflow: A Priori Planner, Intelligence Delta Trigger, Strict Waterfall Routing, and Self-Healing Memory.
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              {isLoading && (
                <Badge variant="cyan">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                  PROCESSING
                </Badge>
              )}
              {isReady && (
                <Badge variant="green">
                  <CheckCircle className="w-3 h-3" />
                  READY
                </Badge>
              )}
              {needsGeneration && (
                <Badge variant="amber">
                  <AlertTriangle className="w-3 h-3" />
                  ACTION REQUIRED
                </Badge>
              )}
            </div>
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Quick Actions */}
        <div className="flex flex-wrap gap-3 mb-8">
          <button
            onClick={() => runPipeline()}
            disabled={isLoading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ 
              background: 'rgba(34,211,238,0.15)', 
              color: '#22d3ee', 
              border: '1px solid rgba(34,211,238,0.3)',
              fontFamily: 'Rajdhani, sans-serif',
            }}
          >
            <Play className="w-4 h-4" />
            {isLoading ? 'Running...' : 'Run Pipeline'}
          </button>
          
          <button
            onClick={() => forceRegenerate()}
            disabled={isLoading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ 
              background: 'rgba(139,92,246,0.15)', 
              color: '#a78bfa', 
              border: '1px solid rgba(139,92,246,0.3)',
              fontFamily: 'Rajdhani, sans-serif',
            }}
          >
            <Brain className="w-4 h-4" />
            Force Regenerate
          </button>
          
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
            style={{ 
              background: showHistory ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.05)', 
              color: '#fff', 
              border: '1px solid rgba(255,255,255,0.2)',
              fontFamily: 'Rajdhani, sans-serif',
            }}
          >
            <Clock className="w-4 h-4" />
            {showHistory ? 'Hide History' : 'Show History'}
          </button>
          
          {isReady && (
            <>
              <Link
                href="/intelligence"
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
                style={{ 
                  background: 'rgba(16,185,129,0.15)', 
                  color: '#10b981', 
                  border: '1px solid rgba(16,185,129,0.3)',
                  fontFamily: 'Rajdhani, sans-serif',
                }}
              >
                <Brain className="w-4 h-4" />
                View Intelligence
                <ChevronRight className="w-3 h-3" />
              </Link>
              
              <Link
                href="/simulation"
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
                style={{ 
                  background: 'rgba(239,68,68,0.15)', 
                  color: '#ef4444', 
                  border: '1px solid rgba(239,68,68,0.3)',
                  fontFamily: 'Rajdhani, sans-serif',
                }}
              >
                <Zap className="w-4 h-4" />
                War Room
                <ChevronRight className="w-3 h-3" />
              </Link>
            </>
          )}
        </div>
        
        {/* Pipeline Status */}
        <div className="grid lg:grid-cols-2 gap-6 mb-8">
          <PipelineExplainer
            stage={stage}
            stageHistory={stageHistory}
            error={error}
            onRetry={runPipeline}
            onGenerate={generateIntelligence}
            showDetails={true}
          />
          
          <div className="space-y-6">
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <Shield className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-white" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                  Data Quality Metrics
                </h3>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <DataQualityGauge 
                  label="Intelligence Coverage" 
                  value={hasIntelligence ? 100 : 0} 
                />
                <DataQualityGauge 
                  label="Grid Data Freshness" 
                  value={gridStatus ? 95 : 0} 
                />
                <DataQualityGauge 
                  label="API Connectivity" 
                  value={error ? 0 : 100} 
                />
                <DataQualityGauge 
                  label="Simulation Ready" 
                  value={isReady ? 100 : isLoading ? 50 : 0} 
                />
              </div>
            </Card>
            
            {showHistory && (
              <Card>
                <SectionLabel>Pipeline History</SectionLabel>
                <div className="mt-3">
                  <StageHistoryTimeline history={stageHistory} />
                </div>
              </Card>
            )}
          </div>
        </div>
        
        {/* Data Summaries */}
        <div className="grid lg:grid-cols-2 gap-6">
          <IntelligenceSummaryCard intelligence={intelligence} />
          <GridStatusCard gridStatus={gridStatus} />
        </div>
        
        {/* XAI Explanation Panel */}
        <div className="mt-8">
          <Card className="glow-cyan">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
                <TrendingUp className="w-6 h-6 text-cyan-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white mb-2" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                  End-to-End Stage Narrative
                </h3>
                <div className="text-sm text-grid-text leading-relaxed space-y-3">
                  <p>
                    <strong className="text-cyan-400">Stage 1 - A Priori Planner:</strong> LightGBM generates baseline demand/supply expectations for all states and decides if LLM agents should stay asleep.
                  </p>
                  <p>
                    <strong className="text-purple-400">Stage 2 - Intelligence Extraction:</strong> The Intelligence agent detects anomalies and computes Delta. If Delta is zero, the day remains baseline-only.
                  </p>
                  <p>
                    <strong className="text-green-400">Stage 3 - Strict Waterfall Orchestrator:</strong> Deficits are resolved in non-negotiable order: battery first, DR auction second, transmission third, controlled fallback last.
                  </p>
                  <p>
                    <strong className="text-amber-400">Stage 4 - Self-Healing Memory + XAI:</strong> The system writes a daily audit ledger and short-term memory warning so tomorrow's routing avoids repeated bottlenecks.
                  </p>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
