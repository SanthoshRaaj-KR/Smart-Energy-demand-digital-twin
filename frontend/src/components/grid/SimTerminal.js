'use client'
import { useEffect, useRef, useState } from 'react'
import { Terminal, Play, RotateCcw } from 'lucide-react'

const AGENT_COLORS = {
  SYSTEM:    { color: '#94a3b8', label: 'SYS',    bg: 'rgba(148,163,184,0.1)' },
  BHR_AGENT: { color: '#00d4ff', label: 'BHR',    bg: 'rgba(0,212,255,0.08)' },
  UP_AGENT:  { color: '#0066ff', label: 'UP',     bg: 'rgba(0,102,255,0.08)' },
  WB_AGENT:  { color: '#8b5cf6', label: 'WB',     bg: 'rgba(139,92,246,0.08)' },
  KAR_AGENT: { color: '#10b981', label: 'KAR',    bg: 'rgba(16,185,129,0.08)' },
  ROUTING:   { color: '#f59e0b', label: 'ROUTE',  bg: 'rgba(245,158,11,0.08)' },
  FUSION:    { color: '#ef4444', label: 'FUSION', bg: 'rgba(239,68,68,0.08)' },
  STREAM:    { color: '#94a3b8', label: 'LIVE',   bg: 'rgba(148,163,184,0.08)' },
}

export function SimTerminal({ logs, running, done, onRun, disabled = false }) {
  const bottomRef = useRef(null)
  const [showCursor, setShowCursor] = useState(true)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    const id = setInterval(() => setShowCursor(v => !v), 500)
    return () => clearInterval(id)
  }, [])

  const isEmpty = logs.length === 0
  const isDisabled = disabled || running

  return (
    <div className="glass rounded-xl overflow-hidden border border-grid-border/80">
      {/* Terminal header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-grid-border/50 bg-black/30">
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
            <div className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
          </div>
          <div className="flex items-center gap-2 text-xs text-grid-textDim"
            style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
            <Terminal className="w-3 h-3" />
            india-grid-twin/simulation.log
          </div>
        </div>
        <div className="flex items-center gap-2">
          {running && (
            <div className="flex items-center gap-1.5 text-xs text-green-400"
              style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              RUNNING
            </div>
          )}
          {done && (
            <div className="flex items-center gap-1.5 text-xs text-cyan-400"
              style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              COMPLETE
            </div>
          )}
          <button
            onClick={onRun}
            disabled={isDisabled}
            className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-all duration-200 ${
              isDisabled
                ? 'bg-grid-border/50 text-grid-muted cursor-not-allowed'
                : 'bg-cyan-500/15 text-cyan-400 hover:bg-cyan-500/25 border border-cyan-500/20'
            }`}
            style={{ fontFamily: 'IBM Plex Mono, monospace' }}
            title={disabled ? 'Pipeline not ready - generate intelligence first' : ''}
          >
            {done ? <RotateCcw className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            {running ? 'Running...' : disabled ? 'Pipeline Required' : done ? 'Re-run' : 'Run Sim'}
          </button>
        </div>
      </div>

      {/* Terminal body */}
      <div
        className="h-96 overflow-y-auto p-4 space-y-0.5 font-mono text-xs"
        style={{ background: 'rgba(3,5,8,0.95)', fontFamily: 'IBM Plex Mono, monospace' }}
      >
        {isEmpty && !running && (
          <div className="flex flex-col items-center gap-3 text-grid-textDim/50 py-12 justify-center">
            <Terminal className="w-8 h-8" />
            <span className="text-sm">Click "Run Sim" to start the agentic simulation</span>
            <span className="text-[10px] text-grid-textDim/30">Live logs will stream here</span>
          </div>
        )}

        {/* Logs with improved spacing */}
        {logs.map((log, i) => {
          const agentDef = AGENT_COLORS[log.agent] || AGENT_COLORS.STREAM
          const isLast = i === logs.length - 1
          const isDone = log.text?.includes('SIMULATION COMPLETE')
          const isPhaseHeader = log.text?.includes('PHASE') || log.text?.includes('=====')

          return (
            <div
              key={i}
              className={`flex items-start gap-2.5 py-1.5 px-3 rounded ${isPhaseHeader ? 'mt-2' : ''}`}
              style={{
                background: isDone 
                  ? 'rgba(16,185,129,0.1)' 
                  : isPhaseHeader 
                  ? 'rgba(0,212,255,0.05)' 
                  : agentDef.bg,
                borderLeft: `2px solid ${agentDef.color}40`,
                animation: isLast ? 'count-up 0.2s ease-out' : 'none',
              }}
            >
              {/* Agent badge - improved visibility */}
              <span
                className="text-[9px] px-2 py-1 rounded shrink-0 mt-0.5 font-bold tracking-wider"
                style={{
                  background: `${agentDef.color}20`,
                  color: agentDef.color,
                  border: `1px solid ${agentDef.color}40`,
                  minWidth: '50px',
                  textAlign: 'center'
                }}
              >
                {agentDef.label}
              </span>

              {/* Text with better contrast */}
              <span
                className={`leading-relaxed flex-1 ${
                  isDone
                    ? 'text-green-400 font-bold'
                    : isPhaseHeader
                    ? 'text-cyan-300 font-semibold'
                    : log.agent === 'SYSTEM'
                    ? 'text-grid-textDim'
                    : 'text-grid-text'
                }`}
              >
                {log.text}
              </span>
            </div>
          )
        })}

        {/* Cursor */}
        {running && (
          <div className="flex items-center gap-1.5 text-cyan-400 px-3 pt-2">
            <span className="text-sm">$</span>
            <span className={`inline-block w-2 h-4 bg-cyan-400 ${showCursor ? 'opacity-100' : 'opacity-0'}`} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
