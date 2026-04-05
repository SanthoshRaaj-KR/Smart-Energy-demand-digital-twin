'use client'
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Brain, TrendingUp, Zap, AlertTriangle, FileSearch, RefreshCw, ChevronDown, Calendar } from 'lucide-react'
import { NavBar } from '@/components/ui/NavBar'
import { DemandForecastChart } from '@/components/charts/DemandForecastChart'
import { Forecast30DayChart } from '@/components/charts/Forecast30DayChart'
import { XAIAuditPanel } from '@/components/agents/XAIAuditPanel'
import { REGIONS } from '@/lib/gridMeta'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function RegionSelector({ selectedRegion, onSelect }) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-grid-bg border border-cyan-500/30 hover:border-cyan-500/50 transition-colors"
      >
        <span className="w-3 h-3 rounded-full" style={{ 
          background: REGIONS.find(r => r.id === selectedRegion)?.color || '#888' 
        }} />
        <span className="text-white font-mono">
          {selectedRegion ? REGIONS.find(r => r.id === selectedRegion)?.name || selectedRegion : 'Select Region'}
        </span>
        <ChevronDown className={`w-4 h-4 text-grid-textDim transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-64 glass-bright rounded-lg border border-cyan-500/30 overflow-hidden z-50">
          {REGIONS.map(r => (
            <button
              key={r.id}
              onClick={() => { onSelect(r.id); setIsOpen(false) }}
              className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/10 transition-colors ${
                selectedRegion === r.id ? 'bg-cyan-500/20' : ''
              }`}
            >
              <span className="w-3 h-3 rounded-full" style={{ background: r.color }} />
              <div>
                <div className="text-white text-sm">{r.name}</div>
                <div className="text-xs text-grid-textDim">{r.id}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function SignalExplorer({ regionId }) {
  const [signals, setSignals] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!regionId) return

    async function fetchSignals() {
      setLoading(true)
      try {
        const res = await fetch(`${BASE_URL}/api/intelligence/${regionId}/signals`)
        if (res.ok) {
          setSignals(await res.json())
        }
      } catch (err) {
        console.error('Failed to fetch signals:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchSignals()
  }, [regionId])

  if (!regionId) {
    return (
      <div className="text-center py-8 text-grid-textDim">
        Select a region to view signals
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin w-6 h-6 border-2 border-green-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!signals) return null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-white">{signals.city} Signal Extraction</h3>
          <p className="text-xs text-grid-textDim">News → Infrastructure Mapping</p>
        </div>
        <span className="text-xs font-mono px-2 py-1 rounded bg-green-500/20 text-green-400">
          {signals.signal_count} signals
        </span>
      </div>

      {/* Input Headlines */}
      {signals.input_headlines?.length > 0 && (
        <div>
          <div className="text-xs text-grid-textDim mb-2 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
            Raw Headlines ({signals.input_headlines.length})
          </div>
          <div className="max-h-32 overflow-y-auto space-y-1">
            {signals.input_headlines.slice(0, 5).map((h, i) => (
              <div key={i} className="text-xs p-2 rounded bg-blue-500/10 text-blue-300 truncate">
                {h}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Extracted Signals */}
      {signals.signal_bullets?.length > 0 && (
        <div>
          <div className="text-xs text-grid-textDim mb-2 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400" />
            Extracted Signals
          </div>
          <div className="space-y-1">
            {signals.signal_bullets.map((sig, i) => (
              <div key={i} className="text-xs p-2 rounded bg-green-500/10 text-green-300">
                • {sig}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detected Events */}
      {signals.detected_events?.length > 0 && (
        <div>
          <div className="text-xs text-grid-textDim mb-2 flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-orange-400" />
            Detected Grid Events
          </div>
          <div className="grid grid-cols-2 gap-2">
            {signals.detected_events.map((evt, i) => (
              <div key={i} className="p-2 rounded bg-orange-500/10 border border-orange-500/20">
                <div className="text-xs font-medium text-orange-400">{evt.event_name || evt.event_type}</div>
                <div className="text-[10px] text-grid-textDim">{evt.grid_mechanism}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ForecastPage() {
  const [selectedRegion, setSelectedRegion] = useState('BHR')
  const [activeTab, setActiveTab] = useState('signals')

  return (
    <div className="min-h-screen bg-grid-bg">
      <NavBar />

      <main className="max-w-7xl mx-auto px-6 py-8 pt-20">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center gap-4 mb-2">
            <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-purple-500/30">
              <Brain className="w-8 h-8 text-purple-400" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-white">Intelligent Forecasting</h1>
              <p className="text-grid-textDim">
                LightGBM ML predictions + LLM knowledge extraction with full XAI traceability
              </p>
            </div>
          </div>
        </motion.div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Forecast Chart */}
          <div className="lg:col-span-2">
            <DemandForecastChart />
          </div>

          {/* Right Column - Region Selector & Tabs */}
          <div className="space-y-4">
            <div className="glass-bright rounded-xl border border-cyan-500/20 p-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-white">Region Deep Dive</h3>
                <RegionSelector selectedRegion={selectedRegion} onSelect={setSelectedRegion} />
              </div>

              {/* Tab Navigation */}
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => setActiveTab('signals')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    activeTab === 'signals'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-grid-bg text-grid-textDim hover:bg-white/5'
                  }`}
                >
                  <FileSearch className="w-4 h-4" />
                  Signals
                </button>
                <button
                  onClick={() => setActiveTab('xai')}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    activeTab === 'xai'
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'bg-grid-bg text-grid-textDim hover:bg-white/5'
                  }`}
                >
                  <Brain className="w-4 h-4" />
                  XAI Audit
                </button>
              </div>

              {/* Tab Content */}
              <div className="min-h-[400px]">
                {activeTab === 'signals' && <SignalExplorer regionId={selectedRegion} />}
                {activeTab === 'xai' && <XAIAuditPanel regionId={selectedRegion} />}
              </div>
            </div>
          </div>
        </div>

        {/* 30-Day Extended Forecast */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mt-8"
        >
          <Forecast30DayChart />
        </motion.div>

        {/* XAI Explanation Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mt-8 glass-bright rounded-xl border border-cyan-500/20 p-6"
        >
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 rounded-lg bg-gradient-to-br from-yellow-500/20 to-orange-500/20">
              <Zap className="w-5 h-5 text-yellow-400" />
            </div>
            <div>
              <h3 className="font-semibold text-white">How This System Works</h3>
              <p className="text-xs text-grid-textDim">Patent-pending multi-modal intelligence fusion</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20">
              <h4 className="font-medium text-blue-400 mb-2">1. Data Collection</h4>
              <p className="text-grid-textDim text-xs">
                Real-time weather (OpenWeatherMap 7-day), 11 RSS feeds (TOI, Hindu, ET, grid operators), 
                and GNews/NewsData APIs for regional news scraping.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-gradient-to-br from-purple-500/10 to-pink-500/10 border border-purple-500/20">
              <h4 className="font-medium text-purple-400 mb-2">2. LLM Intelligence Pipeline</h4>
              <p className="text-grid-textDim text-xs">
                7-phase analysis: City profiling → Event radar → Headline filtering → Signal extraction 
                → Impact narrative → Multiplier synthesis. Full chain-of-thought audit trail.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-gradient-to-br from-cyan-500/10 to-green-500/10 border border-cyan-500/20">
              <h4 className="font-medium text-cyan-400 mb-2">3. ML Forecasting</h4>
              <p className="text-grid-textDim text-xs">
                LightGBM autoregressive 7-day demand predictions with lag features, rolling statistics, 
                and climate inputs. Intelligence multipliers adjust baseline for real-world events.
              </p>
            </div>
          </div>

          <div className="mt-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5" />
              <div className="text-xs text-yellow-200">
                <strong>Patent Value:</strong> The fusion of LLM-based knowledge extraction with ML time-series 
                forecasting, where LLM outputs (multipliers) directly modulate ML predictions, creates a 
                unique hybrid intelligence system. The 7-phase audit trail provides unprecedented explainability 
                for critical infrastructure decisions.
              </div>
            </div>
          </div>
        </motion.div>
      </main>
    </div>
  )
}
