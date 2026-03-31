'use client'
import { ArrowRight, CheckCircle, Zap, Leaf, FileText } from 'lucide-react'
import { REGIONS } from '@/lib/gridMeta'
import { Badge } from '@/components/ui/Primitives'

const regionColor = (id) => REGIONS.find(r => r.id === id)?.color || '#94a3b8'

function normalizeDispatches(results) {
  if (!results) return []
  const raw = Array.isArray(results) ? results : (results.dispatches || [])
  return raw.map((trade, index) => {
    const isSyndicate = trade.type === 'SYNDICATE'
    const seller = trade.seller_city_id || trade.seller || (trade.syndicate_sellers?.[0]?.seller_city_id || 'MULTI')
    const buyer = trade.buyer_city_id || trade.buyer || 'UNKNOWN'
    const quantity = Number(trade.transfer_mw || trade.quantity_mw || 0)
    const price = Number(trade.cleared_price_mw || trade.price_kwh || 0)
    const value = Number(trade.total_value || (quantity * price) || 0)
    const carbonTax = Number(trade.carbon_tax || 0)
    const path = (trade.path || [])
    const pathDescription = trade.path_description || trade.breakdown_log || (path.length ? path.join(' -> ') : null)

    return {
      id: trade.id || `TX-${index + 1}`,
      type: trade.type || 'STANDARD',
      seller,
      buyer,
      quantity,
      price,
      value,
      carbonTax,
      status: trade.status || trade.llm_safety_status || 'CLEARED',
      path,
      pathDescription,
      isSyndicate,
    }
  })
}

export function DispatchTable({ results }) {
  const rows = normalizeDispatches(results)
  const xaiLogs = results?.xai_log || []

  if (!rows.length) {
    return (
      <div className="text-center text-grid-textDim text-sm py-8">
        Run simulation to see dispatch results
      </div>
    )
  }

  const totalValue = rows.reduce((sum, row) => sum + row.value, 0)
  const totalTax = rows.reduce((sum, row) => sum + row.carbonTax, 0)
  const totalMW = rows.reduce((sum, row) => sum + row.quantity, 0)

  return (
    <div>
      {/* Enhanced Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { 
            label: 'Trades Cleared', 
            value: rows.length, 
            color: 'text-cyan-400',
            bgColor: 'bg-cyan-500/10',
            borderColor: 'border-cyan-500/30',
            icon: <CheckCircle className="w-4 h-4" />
          },
          { 
            label: 'Total Power', 
            value: `${totalMW.toFixed(0)} MW`, 
            color: 'text-yellow-400',
            bgColor: 'bg-yellow-500/10',
            borderColor: 'border-yellow-500/30',
            icon: <Zap className="w-4 h-4" />
          },
          { 
            label: 'Market Value', 
            value: `₹${(totalValue / 1000).toFixed(1)}k`, 
            color: 'text-green-400',
            bgColor: 'bg-green-500/10',
            borderColor: 'border-green-500/30'
          },
          { 
            label: 'Carbon Tax', 
            value: `₹${(totalTax / 1000).toFixed(1)}k`, 
            color: 'text-emerald-400',
            bgColor: 'bg-emerald-500/10',
            borderColor: 'border-emerald-500/30',
            icon: <Leaf className="w-4 h-4" />
          },
        ].map(stat => (
          <div key={stat.label} className={`p-4 rounded-lg ${stat.bgColor} border ${stat.borderColor}`}>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] text-grid-textDim uppercase tracking-widest"
                style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                {stat.label}
              </div>
              {stat.icon && <div className={stat.color}>{stat.icon}</div>}
            </div>
            <div className={`text-2xl font-bold ${stat.color}`}
              style={{ fontFamily: 'Rajdhani, sans-serif' }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* Simplified Trade Cards */}
      <div className="space-y-3 mb-8">
        {rows.map((trade, i) => (
          <div
            key={trade.id}
            className="group relative overflow-hidden rounded-xl border bg-gradient-to-br from-white/[0.02] to-transparent hover:from-white/[0.05] transition-all duration-300"
            style={{
              borderColor: trade.isSyndicate ? '#ef444460' : '#00d4ff60',
              animation: `count-up 0.3s ease-out ${i * 0.1}s both`,
            }}
          >
            {/* Colored accent bar */}
            <div 
              className="absolute left-0 top-0 bottom-0 w-1" 
              style={{ background: trade.isSyndicate ? '#ef4444' : '#00d4ff' }}
            />

            <div className="p-5 pl-6">
              {/* Header Row */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <Badge variant={trade.isSyndicate ? 'red' : 'cyan'}>
                    {trade.type}
                  </Badge>
                  <span className="text-[11px] text-grid-textDim/60"
                    style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {trade.id}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-green-400 text-xs">
                  <CheckCircle className="w-3.5 h-3.5" />
                  <span style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{trade.status}</span>
                </div>
              </div>

              {/* Trade Flow - Larger and Clearer */}
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1">
                  <div className="text-[9px] text-grid-textDim mb-1 uppercase tracking-wider">From</div>
                  <div
                    className="px-3 py-2 rounded-lg text-sm font-bold text-center"
                    style={{
                      background: `${regionColor(trade.seller)}20`,
                      color: regionColor(trade.seller),
                      fontFamily: 'Rajdhani, sans-serif',
                      letterSpacing: '0.1em',
                      border: `1px solid ${regionColor(trade.seller)}40`
                    }}
                  >
                    {trade.seller}
                  </div>
                </div>

                <div className="flex flex-col items-center gap-1 px-3">
                  <ArrowRight className="w-5 h-5 text-cyan-400" />
                  <div className="text-[10px] text-cyan-400 font-bold">
                    {trade.quantity.toFixed(0)} MW
                  </div>
                </div>

                <div className="flex-1">
                  <div className="text-[9px] text-grid-textDim mb-1 uppercase tracking-wider">To</div>
                  <div
                    className="px-3 py-2 rounded-lg text-sm font-bold text-center"
                    style={{
                      background: `${regionColor(trade.buyer)}20`,
                      color: regionColor(trade.buyer),
                      fontFamily: 'Rajdhani, sans-serif',
                      letterSpacing: '0.1em',
                      border: `1px solid ${regionColor(trade.buyer)}40`
                    }}
                  >
                    {trade.buyer}
                  </div>
                </div>
              </div>

              {/* Route Path if exists */}
              {trade.pathDescription && (
                <div className="mb-4 p-3 rounded-lg bg-black/40 border border-grid-border/20">
                  <div className="text-[9px] text-grid-textDim uppercase tracking-wider mb-1">Network Route</div>
                  <div className="text-xs text-white/80" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {trade.pathDescription}
                  </div>
                </div>
              )}

              {/* Financial Details - Horizontal Layout */}
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-2.5 rounded-lg bg-white/5 border border-white/10">
                  <div className="text-[9px] text-grid-textDim uppercase mb-1">Price</div>
                  <div className="text-sm font-bold text-white" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                    ₹{trade.price.toFixed(2)}<span className="text-[10px] opacity-50">/MW</span>
                  </div>
                </div>
                <div className="text-center p-2.5 rounded-lg bg-green-500/10 border border-green-500/20">
                  <div className="text-[9px] text-grid-textDim uppercase mb-1">Total Value</div>
                  <div className="text-sm font-bold text-green-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                    ₹{(trade.value / 1000).toFixed(1)}k
                  </div>
                </div>
                <div className="text-center p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <div className="text-[9px] text-grid-textDim uppercase mb-1">Carbon Tax</div>
                  <div className="text-sm font-bold text-emerald-400" style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                    ₹{(trade.carbonTax / 1000).toFixed(1)}k
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* XAI Narratives Section - Enhanced */}
      {xaiLogs.length > 0 && (
        <div className="mt-8 border-t border-grid-border/40 pt-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="p-2 rounded-lg bg-purple-500/10">
              <FileText className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white" style={{ fontFamily: 'Rajdhani, sans-serif', letterSpacing: '0.05em' }}>
                AI OPERATOR INSIGHTS
              </h3>
              <p className="text-[10px] text-grid-textDim uppercase tracking-wider">
                Human-readable simulation explanations
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {xaiLogs.map((log, i) => {
              const isAlert = log.includes('[LLM ALERT]')
              const cleanLog = log.replace('[LLM]', '').replace('[LLM ALERT]', '').trim()
              return (
                <div key={i} className={`p-5 rounded-lg border shadow-lg ${isAlert ? 'bg-red-950/30 border-red-500/40' : 'bg-purple-950/20 border-purple-500/30'}`}>
                  {isAlert && (
                    <div className="flex items-center gap-2 text-red-400 mb-3 text-xs font-bold" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                      CRITICAL SYSTEM ALERT
                    </div>
                  )}
                  <p className="text-sm leading-relaxed text-white/90" style={{ fontFamily: 'Inter, sans-serif', lineHeight: '1.7' }}>
                    {cleanLog}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
