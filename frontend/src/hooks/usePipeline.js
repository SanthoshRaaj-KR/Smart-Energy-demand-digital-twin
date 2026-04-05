'use client'
import { useState, useCallback, useEffect, useRef } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Pipeline stages
export const STAGES = {
  IDLE: 'idle',
  CHECKING_INTELLIGENCE: 'checking_intelligence',
  INTELLIGENCE_MISSING: 'intelligence_missing',
  GENERATING_INTELLIGENCE: 'generating_intelligence',
  LOADING_GRID: 'loading_grid',
  LOADING_SIMULATION: 'loading_simulation',
  READY: 'ready',
  ERROR: 'error',
}

// Stage metadata for XAI explanations
export const STAGE_META = {
  [STAGES.IDLE]: {
    label: 'Idle',
    description: 'Pipeline not started',
    icon: 'Circle',
    color: '#6b7280',
  },
  [STAGES.CHECKING_INTELLIGENCE]: {
    label: 'Checking Intelligence',
    description: 'Verifying if AI-generated regional intelligence data exists in cache',
    explanation: 'The system checks if we have recent AI analysis for each grid region (Bihar, UP, West Bengal, Karnataka). This intelligence includes demand forecasts, risk assessments, and event detection.',
    icon: 'Search',
    color: '#3b82f6',
  },
  [STAGES.INTELLIGENCE_MISSING]: {
    label: 'Intelligence Missing',
    description: 'No cached intelligence found - generation required',
    explanation: 'The AI intelligence cache is empty or stale. This could mean it\'s the first run, or the data is outdated. Generation involves real-time web scraping, weather API calls, and LLM analysis.',
    icon: 'AlertTriangle',
    color: '#f59e0b',
  },
  [STAGES.GENERATING_INTELLIGENCE]: {
    label: 'Generating Intelligence',
    description: 'Running AI agents to gather and analyze regional data',
    explanation: 'The SmartGridIntelligenceAgent is now active. It\'s scanning news sources, checking weather forecasts, analyzing economic indicators, and using LLM reasoning to synthesize grid multipliers for each region.',
    icon: 'Brain',
    color: '#8b5cf6',
  },
  [STAGES.LOADING_GRID]: {
    label: 'Loading Grid Status',
    description: 'Fetching current grid topology and applying intelligence multipliers',
    explanation: 'Loading the physical grid state (nodes, edges, power flows) and applying the AI-generated multipliers. This combines static grid physics with dynamic intelligence context.',
    icon: 'Network',
    color: '#06b6d4',
  },
  [STAGES.LOADING_SIMULATION]: {
    label: 'Loading Simulation Data',
    description: 'Checking for existing simulation results',
    explanation: 'Looking for previous dispatch simulation results. If found, they\'ll be displayed immediately. You can always run a fresh simulation from the War Room.',
    icon: 'Zap',
    color: '#10b981',
  },
  [STAGES.READY]: {
    label: 'Pipeline Ready',
    description: 'All data loaded and synchronized',
    explanation: 'The complete data pipeline is operational. Intelligence is cached, grid status is live, and you\'re ready to run simulations or analyze regional data.',
    icon: 'CheckCircle',
    color: '#22c55e',
  },
  [STAGES.ERROR]: {
    label: 'Pipeline Error',
    description: 'An error occurred during pipeline execution',
    explanation: 'Something went wrong. Check if the backend server is running on port 8000. You can retry the pipeline or check individual stages.',
    icon: 'XCircle',
    color: '#ef4444',
  },
}

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: 'no-store',
      ...options,
    })
    if (!res.ok) throw new Error(`API error: ${res.status}`)
    return await res.json()
  } catch (error) {
    throw error
  }
}

function isIntelligenceValid(data) {
  if (!data || typeof data !== 'object') return false
  const keys = Object.keys(data)
  if (keys.length === 0) return false
  
  // Check if at least one region has real data (not fallback)
  for (const key of keys) {
    const region = data[key]
    const gm = region?.grid_multipliers || {}
    // Fallback data has confidence = 0 and "Run /api/generate-intelligence" in reasoning
    if (gm.confidence > 0 && !String(gm.reasoning || '').includes('Run /api/generate-intelligence')) {
      return true
    }
  }
  return false
}

export function usePipeline(options = {}) {
  const { autoStart = false, skipGeneration = false } = options
  
  const [stage, setStage] = useState(STAGES.IDLE)
  const [error, setError] = useState(null)
  const [intelligence, setIntelligence] = useState(null)
  const [gridStatus, setGridStatus] = useState(null)
  const [simulation, setSimulation] = useState(null)
  const [stageHistory, setStageHistory] = useState([])
  const [generationLogs, setGenerationLogs] = useState([])
  
  const abortRef = useRef(null)
  
  const addToHistory = useCallback((stageName, status = 'completed', details = null) => {
    setStageHistory(prev => [...prev, {
      stage: stageName,
      status,
      timestamp: new Date().toISOString(),
      details,
    }])
  }, [])
  
  const runPipeline = useCallback(async (forceRegenerate = false) => {
    // Reset state
    setError(null)
    setStageHistory([])
    setGenerationLogs([])
    
    // Abort any existing operation
    if (abortRef.current) {
      abortRef.current.abort()
    }
    abortRef.current = new AbortController()
    
    try {
      // Stage 1: Check Intelligence
      setStage(STAGES.CHECKING_INTELLIGENCE)
      addToHistory(STAGES.CHECKING_INTELLIGENCE, 'running')
      
      const existingIntel = await apiFetch('/api/intelligence')
      const hasValidIntel = isIntelligenceValid(existingIntel) && !forceRegenerate
      
      addToHistory(STAGES.CHECKING_INTELLIGENCE, 'completed', {
        found: hasValidIntel,
        regions: existingIntel ? Object.keys(existingIntel).length : 0,
      })
      
      // Stage 2: Generate if needed
      if (!hasValidIntel) {
        setStage(STAGES.INTELLIGENCE_MISSING)
        addToHistory(STAGES.INTELLIGENCE_MISSING, 'flagged')
        
        if (!skipGeneration) {
          setStage(STAGES.GENERATING_INTELLIGENCE)
          addToHistory(STAGES.GENERATING_INTELLIGENCE, 'running')
          
          // Run intelligence generation
          const genResult = await apiFetch('/api/generate-intelligence', {
            method: 'POST',
            signal: abortRef.current.signal,
          })
          
          addToHistory(STAGES.GENERATING_INTELLIGENCE, 'completed', {
            nodes: genResult?.nodes_generated?.length || 0,
          })
          
          // Reload intelligence after generation
          const freshIntel = await apiFetch('/api/intelligence')
          setIntelligence(freshIntel)
        } else {
          // Use fallback intelligence
          setIntelligence(existingIntel)
        }
      } else {
        setIntelligence(existingIntel)
      }
      
      // Stage 3: Load Grid Status
      setStage(STAGES.LOADING_GRID)
      addToHistory(STAGES.LOADING_GRID, 'running')
      
      const grid = await apiFetch('/api/grid-status')
      setGridStatus(grid)
      
      addToHistory(STAGES.LOADING_GRID, 'completed', {
        nodes: grid?.nodes?.length || 0,
        edges: grid?.edges?.length || 0,
      })
      
      // Stage 4: Load Simulation Results
      setStage(STAGES.LOADING_SIMULATION)
      addToHistory(STAGES.LOADING_SIMULATION, 'running')
      
      const simResult = await apiFetch('/api/simulation-result')
      setSimulation(simResult?.dispatches ? simResult : null)
      
      addToHistory(STAGES.LOADING_SIMULATION, 'completed', {
        hasResults: Boolean(simResult?.dispatches),
        dispatches: simResult?.dispatches?.length || 0,
      })
      
      // Complete
      setStage(STAGES.READY)
      addToHistory(STAGES.READY, 'completed')
      
    } catch (err) {
      if (err.name === 'AbortError') return
      
      setError(err.message || 'Pipeline failed')
      setStage(STAGES.ERROR)
      addToHistory(STAGES.ERROR, 'error', { message: err.message })
    }
  }, [addToHistory, skipGeneration])
  
  const retryStage = useCallback(async (targetStage) => {
    // Simplified retry - just restart pipeline
    await runPipeline()
  }, [runPipeline])
  
  const generateIntelligence = useCallback(async () => {
    if (stage === STAGES.GENERATING_INTELLIGENCE) return
    
    setStage(STAGES.GENERATING_INTELLIGENCE)
    setGenerationLogs([])
    addToHistory(STAGES.GENERATING_INTELLIGENCE, 'running')
    
    try {
      const result = await apiFetch('/api/generate-intelligence', {
        method: 'POST',
      })
      
      addToHistory(STAGES.GENERATING_INTELLIGENCE, 'completed', {
        nodes: result?.nodes_generated?.length || 0,
      })
      
      // Refresh intelligence data
      const freshIntel = await apiFetch('/api/intelligence')
      setIntelligence(freshIntel)
      
      // Continue pipeline
      await runPipeline()
      
    } catch (err) {
      setError(err.message || 'Intelligence generation failed')
      setStage(STAGES.ERROR)
      addToHistory(STAGES.ERROR, 'error', { message: err.message })
    }
  }, [stage, addToHistory, runPipeline])
  
  // Auto-start if configured
  useEffect(() => {
    if (autoStart && stage === STAGES.IDLE) {
      runPipeline()
    }
  }, [autoStart, stage, runPipeline])
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort()
      }
    }
  }, [])
  
  return {
    // Current state
    stage,
    stageMeta: STAGE_META[stage],
    error,
    
    // Data
    intelligence,
    gridStatus,
    simulation,
    
    // History & logs
    stageHistory,
    generationLogs,
    
    // Computed
    isLoading: [
      STAGES.CHECKING_INTELLIGENCE,
      STAGES.GENERATING_INTELLIGENCE,
      STAGES.LOADING_GRID,
      STAGES.LOADING_SIMULATION,
    ].includes(stage),
    isReady: stage === STAGES.READY,
    needsGeneration: stage === STAGES.INTELLIGENCE_MISSING,
    hasIntelligence: isIntelligenceValid(intelligence),
    
    // Actions
    runPipeline,
    retryStage,
    generateIntelligence,
    forceRegenerate: () => runPipeline(true),
  }
}

export default usePipeline
