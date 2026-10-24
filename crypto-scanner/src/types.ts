export type Grade = 'Strong Buy' | 'Buy' | 'Watch' | 'Neutral'
export type SignalStatus = 'New' | 'Active' | 'TP hit' | 'Stopped' | 'Expired' | 'No signal'
export type Trend = 'Bullish' | 'Neutral' | 'Bearish'
export type Timeframe = '4H' | '1D'
export interface Signal {
  symbol: string; name: string; logo: string; exchange: string; pair: string; tradingViewSymbol: string
  price: number; change24h: number; marketCap: number; volume24h: number; rank: number; timeframe: Timeframe
  score: number; grade: Grade; rsi: number; ema50: number; ema200: number; adx: number; atr: number; volumeRatio: number
  entryLow: number; entryHigh: number; stopLoss: number; tp1: number; tp2: number; tp3: number; riskReward: number
  status: SignalStatus; candleCloseTime: string; explanation: string[]; trend: Trend; reason?: string; rsiByTf?: Record<string, number | null>
}
export interface Paginated<T> { items: T[]; total: number; page: number; limit: number }
export interface ListParams { page?: number; limit?: number; search?: string; signal?: string; minMarketCap?: number; minVolume?: number; exchange?: string; sort?: string; timeframe?: string; confirmedOnly?: boolean; rsiTf?: string; rsiMin?: number; rsiMax?: number }
export interface MarketStatus { btcRegime: Trend; totalScanned: number; activeSignals: number; strongTrendCount: number; lastScanTime: string }
export interface PerfRow { label: string; winRate: number; avgR: number; total: number; wins?: number; losses?: number; expired?: number; directionAccuracy?: number }
export interface Performance { winRate: number; avgR: number; totalSignals: number; byGrade: PerfRow[]; byTimeframe: PerfRow[]; source: string; byExchange?: PerfRow[]; directionAccuracy?: number; open?: number; recent?: { symbol: string; exchange: string; timeframe: string; grade: string; status: string; fwdReturn: number; reason: string }[] }
export interface Candle { t: string; o: number; h: number; l: number; c: number; v: number; ema50: number; ema200: number; rsi: number }
export interface CoinDetail extends Signal { candles: Candle[]; scoreBreakdown: Record<string, number>; invalidation: string[] }
export interface Settings { minVolume: number; minMarketCap: number; rsiMin: number; rsiMax: number; adxMin: number; minRR: number; timeframe: Timeframe; refreshSec: number; theme: 'dark' | 'light' }

export interface Heat { symbol: string; name: string; logo: string; exchange: string; tradingViewSymbol: string; price: number; change24h: number; marketCap: number; volume24h: number; rank: number; rsi: Record<string, number | null> }
export interface HeatResp { items: Heat[]; total: number; tf: string; byExchange: Record<string, number> }
export interface StrategyInfo { name: string; params: Record<string, number>; weights: Record<string, number>; grades: Record<string, string>; rules: string[] }
export interface ScanLast { id: number; ts: string; coins: number; signals: number; byExchange: Record<string, number>; regime: string; top: { symbol: string; exchange: string; timeframe: string; grade: string; score: number; reason: string }[] }
export interface ScanStatus { running: boolean; done: number; total: number; last: ScanLast | null }
export interface ScanRow { id: number; ts: string; regime: string; coins: number; signals: number; byExchange: Record<string, number> }
