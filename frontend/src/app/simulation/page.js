'use client'
import { useMemo, useState } from 'react'
import { Zap, Network, BarChart2, MessageSquare } from 'lucide-react'
import { useSimulation, useGridStatus } from '@/hooks/useApi'
import { SimTerminal } from '@/components/grid/SimTerminal'
import { AgentChat } from '@/components/agents/AgentChat'
import { GridMap } from '@/components/grid/GridMap'
import { DispatchTable } from '@/components/grid/DispatchTable'
import { DispatcherRadar } from '@/components/grid/DispatcherRadar'
import { Card, SectionLabel, Badge } from '@/components/ui/Primitives'

const TABS = [
  { id: 'terminal', label: 'Terminal', icon: Zap },
  { id: 'agents', label: 'Agents', icon: MessageSquare },
  { id: 'grid', label: 'Grid View', icon: Network },
  { id: 'results', label: 'Dispatch', icon: BarChart2 },
]

export default function SimulationPage() {
  const { logs, results, running, done, runSimulation } = useSimulation()
  const { data: gridStatus } = useGridStatus()
  const [activeTab, setActiveTab] = useState('terminal')

  const edges = gridStatus?.edges || []
  const topCongested = useMemo(
    () => [...edges].sort((a, b) => Number(b.congestion || 0) - Number(a.congestion || 0)).slice(0, 5),
    [edges]
  )

  return (
    <div className="pt-14">
      <div className="relative border-b border-grid-border/50 overflow-hidden">
        <div className="absolute inset-0 grid-dots opacity-40" />
        <div className="max-w-7xl mx-auto px-6 py-10 relative z-10">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <div className="h-px w-6 bg-red-400" />
                <span className="text-[10px] uppercase tracking-[0.3em] text-red-400"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  Agentic Simulation
                </span>
              </div>
              <h1 className="text-4xl font-bold text-white mb-1"
                style={{ fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.05em' }}>
                THE WAR ROOM
              </h1>
              <p className="text-grid-textDim text-sm max-w-xl">
                Live backend simulation stream, agent negotiation logs, congestion view, and dispatch settlement.
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {running && (
                <Badge variant="red">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
                  SIMULATION RUNNING
                </Badge>
              )}
              {done && (
                <Badge variant="green">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                  SIMULATION COMPLETE
                </Badge>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex gap-1 mb-6 border-b border-grid-border/40 pb-0">
          {TABS.map(tab => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            const hasResults = tab.id === 'results' && results
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center gap-2 px-4 py-2.5 text-sm transition-all duration-150 border-b-2 -mb-px
                  ${active
                    ? 'border-cyan-400 text-cyan-400'
                    : 'border-transparent text-grid-textDim hover:text-white'
                  }
                `}
                style={{ fontFamily: 'Rajdhani, sans-serif', fontWeight: 600, letterSpacing: '0.05em' }}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
                {hasResults && <span className="w-1.5 h-1.5 rounded-full bg-green-400" />}
              </button>
            )
          })}
        </div>

        {activeTab === 'terminal' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Simulation Output Stream</SectionLabel>
              <span className="text-[10px] text-grid-textDim"
                style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                {logs.length} events
              </span>
            </div>
            <SimTerminal
              logs={logs}
              running={running}
              done={done}
              onRun={runSimulation}
            />
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Agent Negotiation Feed</SectionLabel>
              {!running && !done && (
                <button
                  onClick={() => { runSimulation(); setActiveTab('agents') }}
                  className="text-xs text-cyan-400 border border-cyan-500/20 px-3 py-1 rounded hover:bg-cyan-500/10 transition-colors"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}
                >
                  Run to see agents talk
                </button>
              )}
            </div>
            <Card>
              <AgentChat logs={logs} />
            </Card>
          </div>
        )}

        {activeTab === 'grid' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Live Grid Topology</SectionLabel>
              <Badge variant={running ? 'red' : 'cyan'}>
                {running ? 'ACTIVE TRADES' : 'STATIC VIEW'}
              </Badge>
            </div>
            <Card className="glow-cyan">
              <GridMap
                animated={running || done}
                className="h-96 md:h-[500px]"
                nodes={gridStatus?.nodes || []}
                edges={edges}
                dispatches={results?.dispatches || []}
              />
            </Card>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {topCongested.map((line, index) => {
                const congestion = Math.round(Number(line.congestion || 0) * 100)
                const flow = Number(line.flow_mw || 0).toFixed(0)
                const capacity = Number(line.capacity_mw || 5000).toFixed(0)
                const color = congestion > 80 ? '#ef4444' : congestion > 60 ? '#f59e0b' : '#22d3ee'
                
                return (
                  <div key={`${line.src}-${line.dst}-${index}`}
                    className="group relative overflow-hidden p-4 rounded-xl bg-black/40 border border-grid-border/30 hover:border-cyan-500/40 transition-all transition-shadow duration-300 hover:shadow-[0_4px_20px_rgba(34,211,238,0.15)]">
                    <div className="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-20 transition-opacity">
                       <Network className="w-10 h-10 text-cyan-400" />
                    </div>
                    
                    <div className="flex items-center gap-2 mb-3">
                       <span className="text-[10px] font-bold text-white px-2 py-0.5 bg-white/5 rounded border border-white/10 uppercase font-mono tracking-tighter">
                          {line.src} → {line.dst}
                       </span>
                       <Badge variant={congestion > 80 ? 'red' : 'cyan'}>
                          {congestion > 80 ? 'CRITICAL' : 'SAT_NORMAL'}
                       </Badge>
                    </div>

                    <div className="flex justify-between items-end mb-2">
                       <div className="flex flex-col">
                          <span className="text-[9px] text-grid-textDim uppercase font-mono">Net Transfer / Total Capacity</span>
                          <span className="text-sm font-bold text-grid-text" style={{ fontFamily: 'IBM Plex Mono' }}>
                            {flow} <span className="text-[10px] opacity-40">/</span> {capacity} <span className="text-[10px] opacity-40 italic">MW</span>
                          </span>
                       </div>
                       <span className="text-lg font-black tracking-tighter" style={{ color, fontFamily: 'Rajdhani, sans-serif' }}>
                          {congestion}%
                       </span>
                    </div>

                    <div className="h-1.5 rounded-full bg-white/5 border border-white/5 overflow-hidden p-0.25">
                       <div className="h-full rounded-full transition-all duration-1000 relative"
                         style={{
                           width: `${congestion}%`,
                           background: color,
                           boxShadow: `0 0 10px ${color}66`,
                         }}>
                         {congestion > 70 && <div className="absolute inset-0 bg-white/20 animate-pulse" />}
                       </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {activeTab === 'results' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Dispatch Orders and Settlement</SectionLabel>
            </div>
            
            {/* New Dispatcher Radar Visual */}
            <DispatcherRadar results={results} />

            <Card>
              <DispatchTable results={results} />
            </Card>
            {!results && !running && (
              <div className="text-center py-4">
                <button
                  onClick={() => { runSimulation() }}
                  className="text-sm text-cyan-400 border border-cyan-500/20 px-4 py-2 rounded-lg hover:bg-cyan-500/10 transition-colors"
                  style={{ fontFamily: 'Rajdhani, sans-serif', fontWeight: 600 }}
                >
                  Run Simulation to Generate Dispatch Orders
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
