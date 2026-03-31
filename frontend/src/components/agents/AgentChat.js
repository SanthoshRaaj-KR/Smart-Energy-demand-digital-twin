'use client'
import React, { useState } from 'react'
import { Terminal as TerminalIcon, Info, Zap, ShieldAlert, Cpu, ChevronRight, ChevronDown, MessageSquare, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/Primitives'

const AGENT_DEFS = {
  BHR_AGENT: { name: 'Bihar', color: '#00d4ff', avatar: 'BH', icon: Cpu },
  UP_AGENT: { name: 'Uttar Pradesh', color: '#0066ff', avatar: 'UP', icon: Cpu },
  WB_AGENT: { name: 'West Bengal', color: '#8b5cf6', avatar: 'WB', icon: Cpu },
  KAR_AGENT: { name: 'Karnataka', color: '#10b981', avatar: 'KR', icon: Cpu },
  ROUTING: { name: 'Routing Engine', color: '#f59e0b', avatar: 'RT', icon: Zap },
  FUSION: { name: 'Syndicate AI', color: '#ef4444', avatar: 'FS', icon: ShieldAlert },
}

function parseLog(text) {
  if (typeof text !== 'string') return { action: text, reason: '', details: '' }
  const parts = text.split('|').map(p => p.trim())
  return {
    action: parts[0] || text,
    reason: parts[1] || '',
    details: parts[2] || ''
  }
}

export function AgentChat({ logs }) {
  const [filterAgent, setFilterAgent] = useState('ALL')

  const agentLogs = logs.filter(log => AGENT_DEFS[log.agent])
  const filteredLogs = filterAgent === 'ALL' 
    ? agentLogs 
    : agentLogs.filter(log => log.agent === filterAgent)

  if (agentLogs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-grid-border/20 rounded-xl bg-white/2">
        <MessageSquare className="w-12 h-12 text-grid-textDim mb-3 opacity-20" />
        <span className="text-sm text-white mb-1">No Agent Activity Yet</span>
        <span className="text-[10px] uppercase tracking-[0.2em] text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
           Run simulation to see agent negotiations
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex items-center gap-2 pb-3 border-b border-grid-border/30">
        <span className="text-[10px] text-grid-textDim uppercase tracking-wider mr-2">Filter:</span>
        <button
          onClick={() => setFilterAgent('ALL')}
          className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
            filterAgent === 'ALL'
              ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
              : 'bg-white/5 text-grid-textDim border border-grid-border/30 hover:bg-white/10'
          }`}
        >
          All ({agentLogs.length})
        </button>
        {Object.entries(AGENT_DEFS).map(([key, def]) => {
          const count = agentLogs.filter(log => log.agent === key).length
          if (count === 0) return null
          return (
            <button
              key={key}
              onClick={() => setFilterAgent(key)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                filterAgent === key
                  ? 'border-2'
                  : 'bg-white/5 border border-grid-border/30 hover:bg-white/10'
              }`}
              style={{
                backgroundColor: filterAgent === key ? `${def.color}20` : undefined,
                color: filterAgent === key ? def.color : '#94a3b8',
                borderColor: filterAgent === key ? `${def.color}60` : undefined,
              }}
            >
              {def.avatar} ({count})
            </button>
          )
        })}
      </div>

      {/* Agent Messages - Chat Style */}
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-2">
        {filteredLogs.length === 0 ? (
          <div className="text-center text-grid-textDim text-sm py-8">
            No messages from this agent
          </div>
        ) : (
          filteredLogs.map((log, i) => {
            const def = AGENT_DEFS[log.agent]
            if (!def) return null
            const Icon = def.icon
            const { action, reason, details } = parseLog(log.text)

            return (
              <div
                key={i}
                className="group relative"
                style={{ animation: `fade-in 0.3s ease-out ${i * 0.05}s both` }}
              >
                {/* Message Card */}
                <div className="flex gap-3">
                  {/* Agent Avatar */}
                  <div 
                    className="shrink-0 w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm border-2"
                    style={{
                      backgroundColor: `${def.color}15`,
                      borderColor: `${def.color}50`,
                      color: def.color,
                    }}
                  >
                    {def.avatar}
                  </div>

                  {/* Message Content */}
                  <div className="flex-1 min-w-0">
                    {/* Agent Name & Timestamp */}
                    <div className="flex items-center gap-2 mb-1.5">
                      <span 
                        className="font-bold text-sm"
                        style={{ color: def.color }}
                      >
                        {def.name}
                      </span>
                      <span className="text-[10px] text-grid-textDim">
                        Step {i + 1}
                      </span>
                    </div>

                    {/* Message Bubble */}
                    <div 
                      className="rounded-lg p-4 border-l-4"
                      style={{
                        backgroundColor: `${def.color}08`,
                        borderLeftColor: def.color,
                        borderRight: `1px solid ${def.color}20`,
                        borderTop: `1px solid ${def.color}20`,
                        borderBottom: `1px solid ${def.color}20`,
                      }}
                    >
                      {/* Main Action */}
                      <div className="flex items-start gap-2 mb-2">
                        <Icon className="w-4 h-4 mt-0.5 shrink-0" style={{ color: def.color }} />
                        <p className="text-sm text-white font-medium leading-relaxed">
                          {action}
                        </p>
                      </div>

                      {/* Reasoning */}
                      {reason && (
                        <div className="pl-6 mb-2 text-xs text-grid-text leading-relaxed italic border-l-2 border-grid-border/30 ml-1">
                          💡 {reason}
                        </div>
                      )}

                      {/* Details */}
                      {details && (
                        <div className="mt-3 pt-3 border-t border-grid-border/20">
                          <div className="text-[10px] text-grid-textDim uppercase tracking-wider mb-1.5">
                            Technical Details
                          </div>
                          <p className="text-xs text-grid-text/80 leading-relaxed font-mono">
                            {details}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Summary Footer */}
      <div className="pt-3 border-t border-grid-border/30 flex items-center justify-between text-xs">
        <span className="text-grid-textDim">
          Showing {filteredLogs.length} of {agentLogs.length} messages
        </span>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-green-400">Live Feed Active</span>
        </div>
      </div>
    </div>
  )
}
