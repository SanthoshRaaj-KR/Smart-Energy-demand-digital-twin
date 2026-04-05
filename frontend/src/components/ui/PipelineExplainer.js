'use client'
import { useState } from 'react'
import { 
  Circle, Search, AlertTriangle, Brain, Network, Zap, 
  CheckCircle, XCircle, ChevronDown, ChevronUp, RefreshCw,
  ArrowRight, Lightbulb, Clock
} from 'lucide-react'
import { STAGES, STAGE_META } from '@/hooks/usePipeline'
import { Card, Badge, SectionLabel } from '@/components/ui/Primitives'

const ICON_MAP = {
  Circle,
  Search,
  AlertTriangle,
  Brain,
  Network,
  Zap,
  CheckCircle,
  XCircle,
}

function getStageIcon(stageMeta) {
  const IconComponent = ICON_MAP[stageMeta?.icon] || Circle
  return IconComponent
}

function getStageOrder(stage) {
  const order = [
    STAGES.IDLE,
    STAGES.CHECKING_INTELLIGENCE,
    STAGES.INTELLIGENCE_MISSING,
    STAGES.GENERATING_INTELLIGENCE,
    STAGES.LOADING_GRID,
    STAGES.LOADING_SIMULATION,
    STAGES.READY,
  ]
  const idx = order.indexOf(stage)
  return idx >= 0 ? idx : -1
}

// Individual stage indicator
export function StageIndicator({ stage, currentStage, details = null, showExplanation = false }) {
  const [expanded, setExpanded] = useState(false)
  const meta = STAGE_META[stage]
  const Icon = getStageIcon(meta)
  
  const isActive = currentStage === stage
  const isPast = getStageOrder(currentStage) > getStageOrder(stage)
  const isFuture = getStageOrder(currentStage) < getStageOrder(stage)
  const isError = stage === STAGES.ERROR
  
  let statusColor = meta.color
  let statusText = 'Pending'
  let bgOpacity = '05'
  
  if (isActive) {
    statusText = 'Running'
    bgOpacity = '15'
  } else if (isPast) {
    statusText = 'Complete'
    statusColor = '#22c55e'
  } else if (isFuture) {
    statusText = 'Waiting'
    statusColor = '#6b7280'
  }
  
  if (isError) {
    statusText = 'Error'
    statusColor = '#ef4444'
  }

  return (
    <div 
      className={`
        relative rounded-xl border transition-all duration-300
        ${isActive ? 'ring-2 ring-offset-2 ring-offset-[#0a1628]' : ''}
        ${isFuture ? 'opacity-50' : ''}
      `}
      style={{ 
        borderColor: `${statusColor}40`,
        background: `${statusColor}${bgOpacity}`,
        ringColor: isActive ? statusColor : 'transparent',
      }}
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div 
            className={`
              w-10 h-10 rounded-lg flex items-center justify-center shrink-0
              ${isActive ? 'animate-pulse' : ''}
            `}
            style={{ 
              background: `${statusColor}20`,
              border: `1px solid ${statusColor}40`,
            }}
          >
            <Icon className="w-5 h-5" style={{ color: statusColor }} />
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span 
                className="font-bold text-sm tracking-wide"
                style={{ fontFamily: 'Rajdhani, sans-serif', color: statusColor }}
              >
                {meta.label}
              </span>
              <Badge variant={
                isActive ? 'cyan' : isPast ? 'green' : isError ? 'red' : 'default'
              }>
                {statusText}
              </Badge>
            </div>
            
            <p className="text-xs text-grid-textDim leading-relaxed">
              {meta.description}
            </p>
            
            {details && isPast && (
              <div className="mt-2 flex flex-wrap gap-2">
                {Object.entries(details).map(([key, val]) => (
                  <span 
                    key={key}
                    className="text-[10px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-grid-textDim"
                    style={{ fontFamily: 'IBM Plex Mono, monospace' }}
                  >
                    {key}: {String(val)}
                  </span>
                ))}
              </div>
            )}
          </div>
          
          {showExplanation && meta.explanation && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1.5 rounded-lg hover:bg-white/5 transition-colors"
            >
              {expanded ? (
                <ChevronUp className="w-4 h-4 text-grid-textDim" />
              ) : (
                <ChevronDown className="w-4 h-4 text-grid-textDim" />
              )}
            </button>
          )}
        </div>
        
        {expanded && meta.explanation && (
          <div className="mt-4 p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/20">
            <div className="flex items-start gap-2">
              <Lightbulb className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-[10px] uppercase tracking-wider text-cyan-400 mb-1"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  XAI Explanation
                </div>
                <p className="text-xs text-grid-text leading-relaxed">
                  {meta.explanation}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
      
      {isActive && (
        <div 
          className="absolute bottom-0 left-0 right-0 h-0.5 overflow-hidden rounded-b-xl"
          style={{ background: `${statusColor}30` }}
        >
          <div 
            className="h-full w-1/3 animate-[progress_1.5s_ease-in-out_infinite]"
            style={{ background: statusColor }}
          />
        </div>
      )}
    </div>
  )
}

// Pipeline flow visualization
export function PipelineFlow({ currentStage, stageHistory = [], compact = false }) {
  const mainStages = [
    STAGES.CHECKING_INTELLIGENCE,
    STAGES.LOADING_GRID,
    STAGES.LOADING_SIMULATION,
    STAGES.READY,
  ]
  
  const historyMap = {}
  stageHistory.forEach(h => {
    historyMap[h.stage] = h
  })
  
  if (compact) {
    return (
      <div className="flex items-center gap-2">
        {mainStages.map((stage, idx) => {
          const meta = STAGE_META[stage]
          const Icon = getStageIcon(meta)
          const isActive = currentStage === stage
          const isPast = historyMap[stage]?.status === 'completed'
          
          return (
            <div key={stage} className="flex items-center gap-2">
              <div 
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center
                  ${isActive ? 'animate-pulse' : ''}
                `}
                style={{
                  background: isPast ? '#22c55e20' : isActive ? `${meta.color}20` : '#1e2d3d',
                  border: `1px solid ${isPast ? '#22c55e40' : isActive ? `${meta.color}40` : '#2a3f55'}`,
                }}
                title={meta.label}
              >
                <Icon 
                  className="w-4 h-4" 
                  style={{ color: isPast ? '#22c55e' : isActive ? meta.color : '#6b7280' }}
                />
              </div>
              {idx < mainStages.length - 1 && (
                <ArrowRight className="w-3 h-3 text-grid-border" />
              )}
            </div>
          )
        })}
      </div>
    )
  }
  
  return (
    <div className="space-y-3">
      {mainStages.map((stage) => (
        <StageIndicator 
          key={stage}
          stage={stage}
          currentStage={currentStage}
          details={historyMap[stage]?.details}
          showExplanation
        />
      ))}
    </div>
  )
}

// Full pipeline explainer component
export function PipelineExplainer({ 
  stage, 
  stageHistory = [], 
  error = null,
  onRetry,
  onGenerate,
  showDetails = true 
}) {
  const meta = STAGE_META[stage]
  const Icon = getStageIcon(meta)
  const isGenerating = stage === STAGES.GENERATING_INTELLIGENCE
  const needsGeneration = stage === STAGES.INTELLIGENCE_MISSING
  const isError = stage === STAGES.ERROR
  const isReady = stage === STAGES.READY
  
  return (
    <Card className="relative overflow-visible">
      {(isGenerating || needsGeneration) && (
        <div 
          className="absolute -inset-px rounded-xl pointer-events-none"
          style={{
            background: `linear-gradient(135deg, ${meta.color}15, transparent)`,
            boxShadow: `0 0 40px ${meta.color}10`,
          }}
        />
      )}
      
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div 
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ 
                background: `${meta.color}15`,
                border: `1px solid ${meta.color}30`,
              }}
            >
              <Icon className="w-4 h-4" style={{ color: meta.color }} />
            </div>
            <div>
              <h3 className="font-bold text-white tracking-wide" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                Data Pipeline
              </h3>
              <div className="flex items-center gap-1.5">
                <span 
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ 
                    background: meta.color,
                    animation: isGenerating ? 'pulse 1.5s infinite' : 'none',
                  }}
                />
                <span 
                  className="text-[10px] uppercase tracking-wider"
                  style={{ fontFamily: 'IBM Plex Mono, monospace', color: meta.color }}
                >
                  {meta.label}
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <Badge variant={
          isReady ? 'green' : isError ? 'red' : needsGeneration ? 'amber' : isGenerating ? 'purple' : 'cyan'
        }>
          {isReady ? <CheckCircle className="w-3 h-3" /> : 
           isError ? <XCircle className="w-3 h-3" /> : 
           <Clock className="w-3 h-3" />}
          {meta.label}
        </Badge>
      </div>
      
      <div className="p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/20 mb-4">
        <p className="text-sm text-grid-text leading-relaxed">
          {meta.explanation || meta.description}
        </p>
      </div>
      
      {isError && error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 mb-4">
          <div className="flex items-start gap-2">
            <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-sm text-red-400 font-medium mb-1">Error Details</div>
              <p className="text-xs text-red-300/80">{error}</p>
            </div>
          </div>
        </div>
      )}
      
      {(needsGeneration || isError) && (
        <div className="flex gap-2 mb-4">
          {needsGeneration && onGenerate && (
            <button
              onClick={onGenerate}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
              style={{ 
                background: 'rgba(139,92,246,0.15)', 
                color: '#a78bfa', 
                border: '1px solid rgba(139,92,246,0.3)',
                fontFamily: 'Rajdhani, sans-serif',
              }}
            >
              <Brain className="w-4 h-4" />
              Generate Intelligence
            </button>
          )}
          {isError && onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 hover:scale-105"
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
      )}
      
      {showDetails && (
        <>
          <SectionLabel>Pipeline Stages</SectionLabel>
          <div className="mt-2">
            <PipelineFlow currentStage={stage} stageHistory={stageHistory} />
          </div>
        </>
      )}
    </Card>
  )
}

// Compact status bar for embedding in other pages
export function PipelineStatusBar({ stage, stageHistory = [], onExpand, className = '' }) {
  const meta = STAGE_META[stage]
  const Icon = getStageIcon(meta)
  const isReady = stage === STAGES.READY
  const isError = stage === STAGES.ERROR
  const isLoading = [
    STAGES.CHECKING_INTELLIGENCE,
    STAGES.GENERATING_INTELLIGENCE,
    STAGES.LOADING_GRID,
    STAGES.LOADING_SIMULATION,
  ].includes(stage)
  
  return (
    <div 
      className={`
        flex items-center justify-between px-4 py-2 rounded-lg border cursor-pointer
        hover:border-cyan-500/30 transition-all ${className}
      `}
      style={{
        background: `${meta.color}08`,
        borderColor: `${meta.color}20`,
      }}
      onClick={onExpand}
    >
      <div className="flex items-center gap-3">
        <div 
          className={`w-6 h-6 rounded flex items-center justify-center ${isLoading ? 'animate-pulse' : ''}`}
          style={{ background: `${meta.color}20` }}
        >
          <Icon className="w-3.5 h-3.5" style={{ color: meta.color }} />
        </div>
        <div>
          <div className="text-xs font-medium text-white" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            Pipeline: {meta.label}
          </div>
          <div className="text-[10px] text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            {isReady ? 'All systems operational' : 
             isError ? 'Click to view error details' :
             isLoading ? 'Processing...' : meta.description}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <PipelineFlow currentStage={stage} stageHistory={stageHistory} compact />
        <Badge variant={isReady ? 'green' : isError ? 'red' : 'cyan'}>
          {isReady ? 'READY' : isError ? 'ERROR' : 'ACTIVE'}
        </Badge>
      </div>
    </div>
  )
}

export default PipelineExplainer
