'use client'
import { ArrowRight, CheckCircle, Zap, Leaf } from 'lucide-react'
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

  if (!rows.length) {
    return (
      <div className="text-center text-grid-textDim text-sm py-8">
        Run simulation to see dispatch results
      </div>
    )
  }

  const totalValue = rows.reduce((sum, row) => sum + row.value, 0)
  const totalTax = rows.reduce((sum, row) => sum + row.carbonTax, 0)

  return (
    <div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[
          { label: 'Total Trades', value: rows.length, color: 'text-cyan-400' },
          { label: 'Total Value', value: `Rs ${(totalValue / 1000).toFixed(1)}k`, color: 'text-green-400' },
          { label: 'Carbon Tax', value: `Rs ${(totalTax / 1000).toFixed(1)}k`, color: 'text-emerald-400' },
        ].map(stat => (
          <div key={stat.label} className="p-3 rounded-lg bg-white/3 border border-grid-border/50 text-center">
            <div className={`text-xl font-bold ${stat.color}`}
              style={{ fontFamily: 'Rajdhani, sans-serif' }}>
              {stat.value}
            </div>
            <div className="text-[10px] text-grid-textDim uppercase tracking-wider mt-0.5"
              style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3">
        {rows.map((trade, i) => (
          <div
            key={trade.id}
            className="p-4 rounded-xl border border-grid-border/60 bg-white/2"
            style={{
              borderLeft: `3px solid ${trade.isSyndicate ? '#ef4444' : '#00d4ff'}`,
              animation: `count-up 0.3s ease-out ${i * 0.1}s both`,
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Badge variant={trade.isSyndicate ? 'red' : 'cyan'}>
                  {trade.type}
                </Badge>
                <span className="text-[10px] text-grid-textDim"
                  style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                  {trade.id}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-green-400 text-xs">
                <CheckCircle className="w-3 h-3" />
                <span style={{ fontFamily: 'IBM Plex Mono, monospace' }}>{trade.status}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <div
                className="px-2 py-1 rounded text-xs font-bold"
                style={{
                  background: `${regionColor(trade.seller)}15`,
                  color: regionColor(trade.seller),
                  fontFamily: 'Rajdhani, sans-serif',
                  letterSpacing: '0.1em',
                }}
              >
                {trade.seller}
              </div>
              <ArrowRight className="w-3 h-3 text-grid-textDim" />
              <div
                className="px-2 py-1 rounded text-xs font-bold"
                style={{
                  background: `${regionColor(trade.buyer)}15`,
                  color: regionColor(trade.buyer),
                  fontFamily: 'Rajdhani, sans-serif',
                  letterSpacing: '0.1em',
                }}
              >
                {trade.buyer}
              </div>
            </div>

            {trade.pathDescription && (
              <div className="text-xs text-grid-textDim mb-3" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                Path: {trade.pathDescription}
              </div>
            )}

            <div className="grid grid-cols-4 gap-2 text-center">
              {[
                { label: 'Quantity', value: `${trade.quantity.toFixed(1)} MW`, icon: <Zap className="w-3 h-3" />, color: 'text-cyan-400' },
                { label: 'Price', value: `Rs ${trade.price.toFixed(2)}/MW`, color: 'text-white' },
                { label: 'Value', value: `Rs ${(trade.value / 1000).toFixed(1)}k`, color: 'text-green-400' },
                { label: 'Carbon Tax', value: `Rs ${(trade.carbonTax / 1000).toFixed(1)}k`, icon: <Leaf className="w-3 h-3" />, color: 'text-emerald-400' },
              ].map(stat => (
                <div key={stat.label} className="p-2 rounded bg-white/3">
                  <div className={`text-sm font-bold flex items-center justify-center gap-1 ${stat.color}`}
                    style={{ fontFamily: 'Rajdhani, sans-serif' }}>
                    {stat.icon}
                    {stat.value}
                  </div>
                  <div className="text-[9px] text-grid-textDim mt-0.5 uppercase tracking-wider"
                    style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
                    {stat.label}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
