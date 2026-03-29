'use client'
import { useState, useEffect, useMemo } from 'react'
import { REGIONS, REGION_BY_ID } from '@/lib/gridMeta'

function pct(val, max) {
  return (val / 100) * max
}

export function GridMap({ animated = false, highlight = null, className = '', nodes = [], edges = [] }) {
  const [flowOffset, setFlowOffset] = useState(0)
  const [pulseNodes, setPulseNodes] = useState([])

  const W = 500
  const H = 420

  useEffect(() => {
    if (!animated) return
    const id = setInterval(() => setFlowOffset(o => (o + 2) % 30), 60)
    return () => clearInterval(id)
  }, [animated])

  useEffect(() => {
    if (highlight) setPulseNodes([highlight])
  }, [highlight])

  const nodeById = useMemo(
    () => Object.fromEntries((nodes || []).map(node => [node.id, node])),
    [nodes]
  )

  const getNodePos = (id) => {
    const region = REGION_BY_ID[id]
    if (!region) return { x: W / 2, y: H / 2 }
    return { x: pct(region.x, W), y: pct(region.y, H) }
  }

  const getCongestionColor = (congestionPct) => {
    if (congestionPct > 80) return '#ef4444'
    if (congestionPct > 60) return '#f59e0b'
    return '#00d4ff'
  }

  const getSoCColor = (soc) => {
    if (soc > 0.6) return '#10b981'
    if (soc > 0.3) return '#f59e0b'
    return '#ef4444'
  }

  return (
    <div className={`relative ${className}`}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full h-full"
        style={{ filter: 'drop-shadow(0 0 30px rgba(0,212,255,0.06))' }}
      >
        <defs>
          <filter id="glow-cyan">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="glow-red">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="node-glow">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          <radialGradient id="bg-grad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(0,212,255,0.03)" />
            <stop offset="100%" stopColor="rgba(0,212,255,0)" />
          </radialGradient>
        </defs>

        <pattern id="dots" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.5" fill="rgba(0,212,255,0.06)" />
        </pattern>
        <rect width={W} height={H} fill="url(#dots)" />

        <ellipse cx={W * 0.52} cy={H * 0.5} rx={W * 0.32} ry={H * 0.44}
          fill="url(#bg-grad)" opacity="0.5" />

        {(edges || []).map((edge, i) => {
          const from = getNodePos(edge.src)
          const to = getNodePos(edge.dst)
          const congestionPct = Math.round((Number(edge.congestion || 0) * 100))
          const color = getCongestionColor(congestionPct)
          const isCongested = congestionPct > 80
          const midX = (from.x + to.x) / 2 + (i % 2 === 0 ? 15 : -15)
          const midY = (from.y + to.y) / 2 + (i % 2 === 0 ? -15 : 15)
          const d = `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`

          return (
            <g key={`${edge.src}-${edge.dst}-${i}`}>
              <path
                d={d}
                fill="none"
                stroke={color}
                strokeWidth={isCongested ? 6 : 3}
                opacity={0.08}
                filter={isCongested ? 'url(#glow-red)' : undefined}
              />
              <path
                d={d}
                fill="none"
                stroke={color}
                strokeWidth={isCongested ? 2.5 : 1.5}
                opacity={isCongested ? 0.9 : 0.6}
              />
              {animated && (
                <path
                  d={d}
                  fill="none"
                  stroke={color}
                  strokeWidth={2}
                  opacity={0.9}
                  strokeDasharray="6 8"
                  strokeDashoffset={-flowOffset}
                  style={{ filter: `drop-shadow(0 0 3px ${color})` }}
                />
              )}
              <text
                x={midX}
                y={midY - 4}
                fill={color}
                fontSize="9"
                textAnchor="middle"
                fontFamily="IBM Plex Mono"
                opacity={0.8}
              >
                {congestionPct}%
              </text>
              {isCongested && (
                <text
                  x={midX}
                  y={midY + 8}
                  fill="#ef4444"
                  fontSize="8"
                  textAnchor="middle"
                  fontFamily="IBM Plex Mono"
                  opacity={0.9}
                >
                  WARN
                </text>
              )}
            </g>
          )
        })}

        {REGIONS.map(region => {
          const pos = getNodePos(region.id)
          const status = nodeById[region.id]
          const soc = status?.battery?.soc ?? 0
          const deficit = status?.balance_mw ?? 0
          const socColor = getSoCColor(soc)
          const isDeficit = deficit < 0
          const isPulse = pulseNodes.includes(region.id)

          return (
            <g key={region.id} filter="url(#node-glow)">
              {(animated || isPulse) && (
                <circle
                  cx={pos.x} cy={pos.y} r="28"
                  fill="none"
                  stroke={region.color}
                  strokeWidth="1"
                  opacity="0.2"
                >
                  <animate
                    attributeName="r"
                    values="22;38;22"
                    dur="2.5s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.3;0;0.3"
                    dur="2.5s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              <circle
                cx={pos.x} cy={pos.y} r="22"
                fill="rgba(7,10,15,0.9)"
                stroke={region.color}
                strokeWidth="1.5"
                opacity="0.9"
              />

              <circle
                cx={pos.x} cy={pos.y} r="22"
                fill="none"
                stroke={socColor}
                strokeWidth="3"
                strokeDasharray={`${soc * 138.2} 138.2`}
                strokeDashoffset="-34.5"
                strokeLinecap="round"
                transform={`rotate(-90 ${pos.x} ${pos.y})`}
                opacity="0.7"
              />

              <text
                x={pos.x} y={pos.y - 4}
                fill={region.color}
                fontSize="10"
                fontWeight="700"
                textAnchor="middle"
                fontFamily="Rajdhani, sans-serif"
                letterSpacing="1"
              >
                {region.id}
              </text>

              <text
                x={pos.x} y={pos.y + 8}
                fill={isDeficit ? '#ef4444' : '#10b981'}
                fontSize="8"
                textAnchor="middle"
                fontFamily="IBM Plex Mono"
              >
                {isDeficit ? 'v' : '^'}{Math.abs(Math.round(deficit))}
              </text>

              <text
                x={pos.x} y={pos.y + 18}
                fill={socColor}
                fontSize="7"
                textAnchor="middle"
                fontFamily="IBM Plex Mono"
                opacity="0.8"
              >
                {Math.round(soc * 100)}%
              </text>

              <text
                x={pos.x} y={pos.y + 36}
                fill="rgba(148,163,184,0.7)"
                fontSize="8"
                textAnchor="middle"
                fontFamily="DM Sans, sans-serif"
              >
                {region.name}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
