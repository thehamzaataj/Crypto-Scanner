import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { STREAM_URL, USE_MOCK } from '../api/client'
// Realtime: the backend pushes an event whenever prices/RSI/scan data change; we refetch immediately (no page reload).
export function useLive() {
  const qc = useQueryClient()
  useEffect(() => {
    if (USE_MOCK) return
    const es = new EventSource(STREAM_URL); let last = 0
    es.onmessage = () => { const n = Date.now(); if (n - last > 2000) { last = n; qc.invalidateQueries() } }
    return () => es.close()
  }, [qc])
}
