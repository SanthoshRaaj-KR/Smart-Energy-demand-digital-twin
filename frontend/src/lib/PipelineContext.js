'use client'
import { createContext, useContext, useMemo } from 'react'
import { usePipeline, STAGES, STAGE_META } from '@/hooks/usePipeline'

const PipelineContext = createContext(null)

export function PipelineProvider({ children, autoStart = true }) {
  const pipeline = usePipeline({ autoStart })
  
  const value = useMemo(() => ({
    ...pipeline,
    STAGES,
    STAGE_META,
  }), [pipeline])
  
  return (
    <PipelineContext.Provider value={value}>
      {children}
    </PipelineContext.Provider>
  )
}

export function usePipelineContext() {
  const context = useContext(PipelineContext)
  if (!context) {
    throw new Error('usePipelineContext must be used within a PipelineProvider')
  }
  return context
}

// Re-export for convenience
export { STAGES, STAGE_META }
