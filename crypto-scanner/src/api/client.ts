import axios from 'axios'
import { mock } from './mock'
import type { CoinDetail, ListParams, MarketStatus, Paginated, Performance, Signal } from '../types'
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL, timeout: 15000 })
const get = <T,>(url: string, params?: object) => http.get<T>(url, { params }).then(r => r.data)
export const api = {
  coins: (p: ListParams): Promise<Paginated<Signal>> => (USE_MOCK ? mock.coins(p) : get('/api/coins', p)),
  signals: (p: ListParams): Promise<Paginated<Signal>> => (USE_MOCK ? mock.signals(p) : get('/api/signals', p)),
  coin: (s: string): Promise<CoinDetail> => (USE_MOCK ? mock.coin(s) : get(`/api/coin/${encodeURIComponent(s)}`)),
  market: (): Promise<MarketStatus> => (USE_MOCK ? mock.market() : get('/api/market-status')),
  perf: (): Promise<Performance> => (USE_MOCK ? mock.perf() : get('/api/signals/performance')),
  watchlist: (): Promise<Signal[]> => (USE_MOCK ? mock.watchlist() : get('/api/watchlist')),
  addWatch: (symbol: string) => (USE_MOCK ? mock.add(symbol) : http.post('/api/watchlist', { symbol })),
  delWatch: (symbol: string) => (USE_MOCK ? mock.del(symbol) : http.delete(`/api/watchlist/${encodeURIComponent(symbol)}`)),
}
export const tvUrl = (tvSymbol: string) => `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`

const need = () => Promise.reject(new Error('This page needs the real backend: set VITE_USE_MOCK=false in .env'))
export const api2 = {
  heatmap: (p: object): Promise<import('../types').HeatResp> => (USE_MOCK ? need() : get('/api/rsi-heatmap', p)),
  strategy: (): Promise<import('../types').StrategyInfo> => (USE_MOCK ? need() : get('/api/strategy')),
  scan: (body: object) => (USE_MOCK ? need() : http.post('/api/scan', body).then(r => r.data)),
  scanStatus: (): Promise<import('../types').ScanStatus> => (USE_MOCK ? need() : get('/api/scan/status')),
  scans: (): Promise<import('../types').ScanRow[]> => (USE_MOCK ? need() : get('/api/scans')),
}
export const STREAM_URL = `${import.meta.env.VITE_API_BASE_URL}/api/stream`
