'use client'
import { useMemo } from 'react'
import { ShieldAlert, Clock, Zap } from 'lucide-react'
import { Card } from '@/components/ui/Primitives'

export function DispatcherRadar({ results }) {
  // Extract all radar issues from results
  const radarAlerts = useMemo(() => {
    if (!results || !results.dispatches) return []
    return results.dispatches
      .filter(d => d.radar_locked)
      .map(d => ({
        id: `${d.buyer_city_id}-${d.seller_city_id}`,
        buyer: d.buyer_city_id,
        seller: d.seller_city_id,
        alert: d.radar_alert || "DLR COLLAPSE",
      }))
  }, [results])

  const isLocked = radarAlerts.length > 0

  return (
    <Card className="relative overflow-hidden bg-gradient-to-br from-[#0a1219] to-[#050810] border-grid-border/40">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10">
            <Clock className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
              24-Hour Dispatch Timeline
            </h3>
            <p className="text-[10px] text-grid-textDim uppercase tracking-wider">
              Dynamic Line Rating Schedule
            </p>
          </div>
        </div>
        {isLocked && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/15 border border-red-500/40 rounded-lg">
            <ShieldAlert className="w-4 h-4 text-red-500 animate-pulse" />
            <span className="text-xs text-red-400 font-bold uppercase tracking-wider" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              Thermal Lock
            </span>
          </div>
        )}
      </div>

      {/* Enhanced 24-Hour Timeline */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-grid-textDim uppercase tracking-wider">Hour of Day</span>
          <div className="flex items-center gap-4 text-[9px] text-grid-textDim">
            {isLocked && (
              <>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded bg-green-500/30 border border-green-500/50" />
                  <span>Safe Window</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 rounded bg-red-500/30 border border-red-500/50" />
                  <span>Blocked</span>
                </div>
              </>
            )}
          </div>
        </div>
        <div className="relative h-20 w-full bg-black/40 rounded-lg border border-grid-border/30 flex overflow-hidden">
          {[...Array(24)].map((_, i) => {
            const hour = i;
            const isBlocked = isLocked && hour >= 12 && hour <= 16;
            const isMorningSafe = isLocked && hour >= 4 && hour <= 8;
            
            return (
              <div 
                key={i} 
                className={`flex-1 border-r border-grid-border/10 flex flex-col justify-between items-center py-2 relative transition-all duration-300
                  ${isBlocked ? 'bg-red-500/25' : ''}
                  ${isMorningSafe ? 'bg-green-500/15' : ''}
                `}
              >
                {/* Diagonal stripes for blocked hours */}
                {isBlocked && (
                  <div className="absolute inset-0 opacity-40" 
                    style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 5px, rgba(239, 68, 68, 0.6) 5px, rgba(239, 68, 68, 0.6) 10px)' }} 
                  />
                )}
                
                {/* Hour indicator bars */}
                <div className={`w-full flex-1 flex items-end justify-center ${isBlocked ? 'opacity-50' : ''}`}>
                  {i % 4 === 0 && (
                    <div className={`w-0.5 h-full ${isBlocked ? 'bg-red-500/60' : isMorningSafe ? 'bg-green-500/60' : 'bg-grid-border/40'}`} />
                  )}
                </div>
                
                {/* Hour label */}
                <span className={`text-[9px] font-bold relative z-10 ${isBlocked ? 'text-red-400' : isMorningSafe ? 'text-green-400' : 'text-grid-textDim'}`} 
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  {String(hour).padStart(2, '0')}
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Status Message */}
      {isLocked ? (
        <div className="p-4 bg-red-950/40 rounded-lg border border-red-900/50 relative">
           <div className="flex items-start gap-4">
              <div className="p-3 bg-red-600/20 rounded-lg shrink-0">
                 <ShieldAlert className="w-6 h-6 text-red-500" />
              </div>
              <div className="flex-1">
                 <div className="text-sm font-bold text-red-400 uppercase mb-2 tracking-wide">
                   ⚡ Thermal Capacity Alert
                 </div>
                 <div className="text-sm text-white/90 leading-relaxed mb-3 p-3 rounded-lg bg-red-600/10 border border-red-500/30">
                    High afternoon temperatures causing Dynamic Line Rating collapse. All power transfers automatically rescheduled to 04:00 - 08:00 morning window for grid safety.
                 </div>
                 <div className="text-[10px] text-grid-textDim/80 italic leading-relaxed">
                   System prevented thermal overload on {radarAlerts[0]?.seller || 'multi'}-{radarAlerts[0]?.buyer || 'state'} corridor by shifting dispatch timing.
                 </div>
              </div>
           </div>
        </div>
      ) : (
        <div className="p-4 bg-cyan-950/20 rounded-lg border border-cyan-900/30">
           <div className="flex items-center gap-3">
              <Zap className="w-5 h-5 text-cyan-400" />
              <div>
                <span className="text-sm text-white font-medium block mb-0.5">All Systems Operational</span>
                <span className="text-[10px] text-grid-textDim uppercase tracking-widest" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  DLR limits nominal • Full 24-hour dispatch available
                </span>
              </div>
           </div>
        </div>
      )}
    </Card>
  )
}
