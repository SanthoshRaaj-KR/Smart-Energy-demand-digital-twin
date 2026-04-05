'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, Brain, Zap, GitBranch, Workflow } from 'lucide-react'

const NAV_ITEMS = [
  { href: '/',             label: 'Dashboard',    icon: Activity },
  { href: '/pipeline',     label: 'Pipeline',     icon: Workflow },
  { href: '/intelligence', label: 'Intelligence', icon: Brain },
  { href: '/simulation',   label: 'War Room',     icon: Zap },
]

export function NavBar() {
  const pathname = usePathname()

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-grid-border/60">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-7 h-7 relative flex items-center justify-center">
            <div className="absolute inset-0 rounded border border-cyan-400/60 rotate-45" />
            <GitBranch className="w-3.5 h-3.5 text-cyan-400 relative z-10" />
          </div>
          <div>
            <div className="font-display font-700 text-sm tracking-widest text-white leading-tight" style={{ fontFamily: 'Rajdhani, sans-serif', fontWeight: 700, letterSpacing: '0.12em' }}>
              INDIA GRID
            </div>
            <div className="text-[9px] text-grid-textDim tracking-[0.2em] uppercase leading-none" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
              Digital Twin v2.4
            </div>
          </div>
        </Link>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href
            return (
              <Link
                key={href}
                href={href}
                className={`
                  flex items-center gap-2 px-4 py-1.5 rounded text-sm transition-all duration-200
                  ${active
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                    : 'text-grid-textDim hover:text-white hover:bg-white/5'
                  }
                `}
                style={{ fontFamily: 'Rajdhani, sans-serif', fontWeight: 600, letterSpacing: '0.05em' }}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </Link>
            )
          })}
        </div>

        {/* Status indicator */}
        <div className="flex items-center gap-2 text-xs" style={{ fontFamily: 'IBM Plex Mono, monospace' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-grid-textDim">GRID LIVE</span>
        </div>
      </div>
    </nav>
  )
}
