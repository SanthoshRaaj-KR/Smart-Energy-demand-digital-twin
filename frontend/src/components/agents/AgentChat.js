'use client'
import { useState } from 'react'
import { Terminal as TerminalIcon, Info, Zap, ShieldAlert, Cpu, ChevronRight, ChevronDown, ListFilter } from 'lucide-react'
import { Badge } from '@/components/ui/Primitives'

const AGENT_DEFS = {
  BHR_AGENT: { name: 'BIHAR', color: '#00d4ff', avatar: 'BH', icon: Cpu },
  UP_AGENT: { name: 'NR_UP', color: '#0066ff', avatar: 'UP', icon: Cpu },
  WB_AGENT: { name: 'W_BENGAL', color: '#8b5cf6', avatar: 'WB', icon: Cpu },
  KAR_AGENT: { name: 'KARNATAKA', color: '#10b981', avatar: 'KR', icon: Cpu },
  ROUTING: { name: 'ROUTING_AI', color: '#f59e0b', avatar: 'RT', icon: Zap },
  FUSION: { name: 'FUSION_AI', color: '#ef4444', avatar: 'FS', icon: Info },
}

function parseLog(text) {
  if (typeof text !== 'string') return { action: text, reason: '', details: '' }
  const parts = text.split('|').map(p => p.trim())
  return {
    action: parts[0] || '',
    reason: parts[1] || '',
    details: parts[2] || ''
  }
}

export function AgentChat({ logs }) {
  const [expandedRows, setExpandedRows] = useState({})
  
  const toggleRow = (idx) => {
    setExpandedRows(prev => ({ ...prev, [idx]: !prev[idx] }))
  }

  const agentLogs = logs.filter(log => AGENT_DEFS[log.agent])
  const visibleLogs = agentLogs.slice(-20)

  if (agentLogs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-grid-border/20 rounded-xl bg-white/2">
        <TerminalIcon className="w-8 h-8 text-grid-textDim mb-3 opacity-20" />
        <span className="text-[10px] uppercase tracking-[0.2em] text-grid-textDim" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
           Awaiting Agent Handshake...
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[450px] bg-black/40 rounded-xl border border-grid-border/30 overflow-hidden backdrop-blur-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-grid-border/30 bg-white/5 flex items-center justify-between">
         <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_#22c55e]" />
            <span className="text-[11px] font-bold uppercase tracking-widest text-white px-2 py-0.5 bg-white/5 rounded border border-white/10" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
              Strategic Negotiation Feed
            </span>
         </div>
         <div className="flex items-center gap-3">
            <span className="text-[9px] text-grid-textDim uppercase font-mono bg-black/40 px-2 py-1 rounded">R_T_TELEMETRY</span>
            <button className="flex items-center gap-1.5 px-2 py-1 rounded bg-cyan-500/10 border border-cyan-500/20 text-[9px] text-cyan-400 font-bold hover:bg-cyan-500/20 transition-all uppercase tracking-tighter" style={{ fontFamily: 'IBM Plex Mono' }}>
               <ListFilter className="w-3 h-3" /> System Audit
            </button>
         </div>
      </div>

      {/* Feed Area */}
      <div className="flex-1 overflow-y-auto p-0 scrollbar-thin scrollbar-thumb-grid-border/40">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-[#0a1219] z-10">
            <tr className="border-b border-grid-border/30">
              <th className="text-[9px] text-grid-textDim uppercase py-2 px-4 text-left font-mono w-10">#</th>
              <th className="text-[9px] text-grid-textDim uppercase py-2 px-2 text-left font-mono w-28">Source</th>
              <th className="text-[9px] text-grid-textDim uppercase py-2 px-3 text-left font-mono">Intent & Rationale</th>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody>
            {visibleLogs.map((log, i) => {
              const def = AGENT_DEFS[log.agent]
              if (!def) return null
              const Icon = def.icon
              const { action, reason, details } = parseLog(log.text)
              const isExpanded = expandedRows[i]

              return (
                <React.Fragment key={i}>
                  <tr 
                    className={`group hover:bg-white/5 transition-colors cursor-pointer border-b border-grid-border/10 ${isExpanded ? 'bg-white/5' : ''}`}
                    onClick={() => toggleRow(i)}
                    style={{ animation: 'fade-in 0.2s ease-out forwards' }}
                  >
                    <td className="py-2.5 px-4 text-[9px] text-grid-textDim font-mono opacity-50">{i + 1}</td>
                    <td className="py-2.5 px-2 align-top">
                      <div className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: def.color, boxShadow: `0 0 8px ${def.color}` }} />
                        <span 
                          className="text-[10px] font-bold tracking-tighter uppercase" 
                          style={{ color: def.color, fontFamily: 'IBM Plex Mono, monospace' }}
                        >
                          {def.name}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-2">
                           <Icon className="w-3.5 h-3.5 opacity-60 text-grid-text" />
                           <span className="text-[11px] font-bold text-white tracking-tight leading-none" style={{ fontFamily: 'Inter, sans-serif' }}>{action}</span>
                        </div>
                        {reason && (
                          <span className="text-[10px] text-grid-textDim pl-5 border-l border-grid-border/40 mt-1 italic leading-tight">
                            {reason}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 text-right">
                       {isExpanded ? <ChevronDown className="w-3 h-3 text-grid-textDim" /> : <ChevronRight className="w-3 h-3 text-grid-textDim/40 group-hover:text-grid-textDim" />}
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-black/60 border-b border-grid-border/20">
                      <td colSpan="4" className="p-4 pl-14">
                        <div className="rounded-lg border border-cyan-500/10 bg-cyan-500/5 p-3 space-y-3">
                           <div className="flex items-center justify-between">
                              <span className="text-[9px] uppercase font-bold text-cyan-400 font-mono tracking-widest">Protocol Tech-Specs</span>
                              <Badge variant="cyan">PHYSICAL_GROUNDING_OK</Badge>
                           </div>
                           <p className="text-[10px] leading-relaxed text-grid-text font-mono opacity-80">
                             {details || "No secondary telemetry packet associated with this broadcast."}
                           </p>
                           {log.agent !== 'ROUTING' && log.agent !== 'FUSION' && (
                             <div className="pt-2 border-t border-cyan-500/10">
                                <span className="text-[8px] text-grid-textDim uppercase font-mono">Agent Decision State: Resolved in 45ms</span>
                             </div>
                           )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Status Bar */}
      <div className="px-3 py-2 bg-black/60 border-t border-grid-border/30 flex justify-between items-center">
         <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
               <div className="w-1 h-1 bg-cyan-400" />
               <span className="text-[8px] text-cyan-400/70 font-mono uppercase">LLM_Audit_Active</span>
            </div>
            <div className="flex items-center gap-1.5">
               <div className="w-1 h-1 bg-amber-400" />
               <span className="text-[8px] text-amber-400/70 font-mono uppercase">Syndicate_Health: 100%</span>
            </div>
         </div>
         <span className="text-[8px] text-grid-textDim font-mono uppercase tracking-[0.2em]">
            Packets: {agentLogs.length}
         </span>
      </div>
    </div>
  )
}

// Add React to avoid ReferenceError for React.Fragment if not imported
import React from 'react'
