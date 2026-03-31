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
    <Card className="relative overflow-hidden bg-[#0a1219] border-grid-border/40">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-cyan-400" />
          <h3 className="text-sm font-bold text-white tracking-widest uppercase" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
            Intra-Day Dispatch Radar
          </h3>
        </div>
        {isLocked && (
          <div className="flex items-center gap-2 px-2 py-1 bg-red-500/10 border border-red-500/30 rounded">
            <ShieldAlert className="w-3 h-3 text-red-500 animate-pulse" />
            <span className="text-[10px] text-red-400 font-bold uppercase tracking-tighter" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              Corridor Lock Active
            </span>
          </div>
        )}
      </div>

      {/* 24-Hour Timeline Strip */}
      <div className="relative h-16 w-full bg-black/40 rounded border border-grid-border/20 flex mb-4">
        {[...Array(24)].map((_, i) => {
          const hour = i;
          const isBlocked = isLocked && hour >= 12 && hour <= 16;
          const isMorningSafe = isLocked && hour >= 4 && hour <= 8;
          
          return (
            <div 
              key={i} 
              className={`flex-1 border-r border-grid-border/10 flex flex-col justify-end items-center pb-1 relative
                ${isBlocked ? 'bg-red-500/20' : ''}
                ${isMorningSafe ? 'bg-green-500/10' : ''}
              `}
            >
              {isBlocked && (
                <div className="absolute inset-0 opacity-30" 
                  style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 5px, rgba(239, 68, 68, 0.5) 5px, rgba(239, 68, 68, 0.5) 10px)' }} 
                />
              )}
              <span className={`text-[8px] font-medium ${isBlocked ? 'text-red-400' : 'text-grid-textDim'}`} style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                {String(hour).padStart(2, '0')}
              </span>
              {i % 4 === 0 && (
                <div className="w-px h-2 bg-grid-border/40 absolute -top-1" />
              )}
            </div>
          )
        })}
      </div>

      {/* Large Pulsing Alert Overlay/Footer */}
      {isLocked ? (
        <div className="p-3 bg-red-950/30 rounded-lg border border-red-900/40 relative animate-pulse">
           <div className="flex items-start gap-3">
              <div className="p-2 bg-red-600/20 rounded-full">
                 <ShieldAlert className="w-5 h-5 text-red-500" />
              </div>
              <div className="flex-1">
                 <div className="text-xs font-bold text-red-400 uppercase mb-1 tracking-wider">Dispatcher System Warning</div>
                 <div className="text-sm text-white font-medium bg-red-600/10 p-2 rounded border border-red-500/20">
                    ⚠️ DISPATCHER ALERT: Afternoon DLR Collapse. ALL TRANSFERS FORCED TO 04:00 - 08:00 HRS.
                 </div>
                 <div className="mt-2 text-[10px] text-grid-textDim italic">
                   Visualizing why RL Double DQN shifted loads to morning window due to predicted {radarAlerts[0].seller}-{radarAlerts[0].buyer} thermal lockout.
                 </div>
              </div>
           </div>
        </div>
      ) : (
        <div className="p-3 bg-cyan-950/20 rounded-lg border border-cyan-900/20">
           <div className="flex items-center gap-3">
              <Zap className="w-4 h-4 text-cyan-400" />
              <span className="text-[11px] text-grid-textDim uppercase tracking-widest" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                All corridors nominal. DLR limits operational.
              </span>
           </div>
        </div>
      )}
    </Card>
  )
}
