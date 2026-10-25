import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useSettings } from './useSettings'
import type { ListParams } from '../types'
const useOpts = () => { const { s } = useSettings(); return { refetchInterval: Math.max(s.refreshSec, 15) * 1000, staleTime: 15000, placeholderData: keepPreviousData } }
export const useMarket = () => useQuery({ queryKey: ['market'], queryFn: api.market, ...useOpts() })
export const usePerf = () => useQuery({ queryKey: ['perf'], queryFn: api.perf, ...useOpts() })
export const useList = (kind: 'signals' | 'coins', p: ListParams) => useQuery({ queryKey: [kind, p], queryFn: () => api[kind](p), ...useOpts() })
export const useCoin = (sym: string | null) => useQuery({ queryKey: ['coin', sym], queryFn: () => api.coin(sym!), enabled: !!sym })
export const useWatchlist = () => useQuery({ queryKey: ['watchlist'], queryFn: api.watchlist, ...useOpts() })
export const useWatchToggle = () => { const qc = useQueryClient(); return useMutation({ mutationFn: async ({ symbol, on }: { symbol: string; on: boolean }) => { await (on ? api.addWatch(symbol) : api.delWatch(symbol)) }, onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist'] }) }) }