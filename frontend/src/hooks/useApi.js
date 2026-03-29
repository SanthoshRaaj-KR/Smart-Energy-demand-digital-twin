'use client'
import { useState, useEffect, useCallback } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: 'no-store',
      ...options,
    })
    if (!res.ok) throw new Error('API error')
    return await res.json()
  } catch {
    return null
  }
}

export function useIntelligence() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/intelligence').then(d => {
      setData(d)
      setLoading(false)
    })
  }, [])

  return { data, loading }
}

export function useGridStatus() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/grid-status').then(d => {
      setData(d)
      setLoading(false)
    })
  }, [])

  return { data, loading }
}

export function useSimulation() {
  const [logs, setLogs] = useState([])
  const [results, setResults] = useState(null)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    apiFetch('/api/simulation-result').then(d => {
      if (d?.dispatches) {
        setResults(d)
        setDone(true)
      }
    })
  }, [])

  const inferAgent = (text) => {
    const line = text.toUpperCase()
    if (line.includes('FUSION')) return 'FUSION'
    if (line.includes('ROUTING') || line.includes('PATH')) return 'ROUTING'
    if (line.includes('BHR') || line.includes('BIHAR')) return 'BHR_AGENT'
    if (line.includes('UP')) return 'UP_AGENT'
    if (line.includes('WB') || line.includes('BENGAL')) return 'WB_AGENT'
    if (line.includes('KAR') || line.includes('KARNATAKA')) return 'KAR_AGENT'
    return 'SYSTEM'
  }

  const runSimulation = useCallback(async () => {
    setLogs([])
    setResults(null)
    setRunning(true)
    setDone(false)

    try {
      const res = await fetch(`${API_BASE}/api/run-simulation`, {
        method: 'POST',
        signal: AbortSignal.timeout(600000),
      })
      if (!res.ok || !res.body) throw new Error()

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done: streamDone, value } = await reader.read()
        if (streamDone) break
        buffer += decoder.decode(value)
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const text = line.trim()
          if (text) {
            setLogs(prev => [...prev, { text, agent: inferAgent(text) }])
          }
        }
      }

      if (buffer.trim()) {
        const text = buffer.trim()
        setLogs(prev => [...prev, { text, agent: inferAgent(text) }])
      }
    } catch {}

    const res = await apiFetch('/api/simulation-result')
    setResults(res)
    setRunning(false)
    setDone(true)
  }, [])

  return { logs, results, running, done, runSimulation }
}
