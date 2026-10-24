// DEMO DATA ONLY. Used when VITE_USE_MOCK=true; real mode never calls this module.
import type { CoinDetail, ListParams, MarketStatus, Paginated, Performance, Signal } from '../types'
let s = 7; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647
const names = 'BTC Bitcoin,ETH Ethereum,SOL Solana,BNB BNB,XRP XRP,ADA Cardano,AVAX Avalanche,LINK Chainlink,DOT Polkadot,NEAR Near,ATOM Cosmos,INJ Injective,SUI Sui,APT Aptos,ARB Arbitrum,OP Optimism,LTC Litecoin,UNI Uniswap,AAVE Aave,FIL Filecoin,TIA Celestia,SEI Sei,RUNE THORChain,MKR Maker,GRT Graph,IMX Immutable,ALGO Algorand,XLM Stellar,HBAR Hedera,ETC Ethereum-Classic'.split(',')
const ex = ['Binance', 'OKX', 'Bybit', 'KuCoin']
const grade = (n: number) => (n >= 85 ? 'Strong Buy' : n >= 70 ? 'Buy' : n >= 55 ? 'Watch' : 'Neutral') as Signal['grade']
const now = Date.now()
const coins: Signal[] = names.map((row, i) => {
  const [symbol, ...rest] = row.split(' '); const price = 0.5 + rnd() * (i < 3 ? 60000 : 200)
  const atr = price * (0.015 + rnd() * 0.03), score = Math.round(35 + rnd() * 62), e = ex[i % 4]
  const entry = price * 0.995, sl = entry - 1.5 * atr, risk = entry - sl
  const trend = score >= 55 ? 'Bullish' : rnd() > 0.5 ? 'Neutral' : 'Bearish'
  return { symbol, name: rest.join(' '), logo: '', exchange: e, pair: symbol + '/USDT', tradingViewSymbol: `${e.toUpperCase()}:${symbol}USDT`,
    price, change24h: (rnd() - 0.4) * 12, marketCap: (1e7 + rnd() * 1e11) | 0, volume24h: (1e6 + rnd() * 5e9) | 0, rank: i + 1,
    timeframe: i % 3 ? '4H' : '1D', score, grade: grade(score), rsi: 40 + rnd() * 15, ema50: price * 0.99, ema200: price * 0.9, adx: 18 + rnd() * 22, atr,
    volumeRatio: 0.8 + rnd() * 1.6, entryLow: entry * 0.998, entryHigh: entry * 1.003, stopLoss: sl, tp1: entry + risk * 1.5, tp2: entry + risk * 2.5, tp3: entry + risk * 4,
    riskReward: 1.5 + rnd() * 2.5, status: (['New', 'Active', 'Active', 'TP hit', 'Stopped', 'Expired'] as const)[i % 6],
    candleCloseTime: new Date(now - (i % 8) * 4 * 3600e3 - 600e3).toISOString(), trend,
    explanation: ['Price is above the 1D and 4H EMA200, with EMA50 above EMA200 (uptrend).', 'Price pulled back into the EMA50 zone and RSI turned up from the 40s.', 'A bullish candle closed on more than 1.2x average volume.'] }
})
const filter = (p: ListParams, only: boolean) => {
  let r = coins.filter(c => (!only || (c.score >= 55 && c.riskReward >= 1.5)) && (!p.search || (c.symbol + c.name).toLowerCase().includes(p.search.toLowerCase())) &&
    (!p.signal || c.grade === p.signal) && (!p.exchange || c.exchange === p.exchange) && (!p.timeframe || c.timeframe === p.timeframe) &&
    c.marketCap >= (p.minMarketCap ?? 0) && c.volume24h >= (p.minVolume ?? 0))
  r = [...r].sort((a, b) => (p.sort === 'marketCap' ? b.marketCap - a.marketCap : b.score - a.score))
  const page = p.page ?? 1, limit = p.limit ?? 50
  return { items: r.slice((page - 1) * limit, page * limit), total: r.length, page, limit } as Paginated<Signal>
}
const wait = <T,>(v: T) => new Promise<T>(r => setTimeout(() => r(v), 250))
let watch = ['SOL', 'LINK']
export const mock = {
  coins: (p: ListParams) => wait(filter(p, false)), signals: (p: ListParams) => wait(filter(p, true)),
  market: () => wait<MarketStatus>({ btcRegime: 'Bullish', totalScanned: coins.length, activeSignals: coins.filter(c => c.score >= 55).length, strongTrendCount: coins.filter(c => c.trend === 'Bullish').length, lastScanTime: new Date().toISOString() }),
  perf: () => wait<Performance>({ winRate: 54.2, avgR: 0.62, totalSignals: 418, source: 'DEMO backtest + live', byGrade: [{ label: 'Strong Buy', winRate: 61, avgR: 0.9, total: 70 }, { label: 'Buy', winRate: 55, avgR: 0.6, total: 190 }, { label: 'Watch', winRate: 47, avgR: 0.3, total: 158 }], byTimeframe: [{ label: '4H', winRate: 52, avgR: 0.55, total: 300 }, { label: '1D', winRate: 58, avgR: 0.75, total: 118 }] }),
  coin: (symbol: string) => {
    const c = coins.find(x => x.symbol === symbol) ?? coins[0]; let p = c.price * 0.8
    const candles = Array.from({ length: 80 }, (_, i) => { const o = p; p = Math.max(0.01, p * (1 + (rnd() - 0.42) * 0.03)); return { t: new Date(now - (80 - i) * 4 * 3600e3).toISOString(), o, h: Math.max(o, p) * 1.005, l: Math.min(o, p) * 0.995, c: p, v: 100 + rnd() * 900, ema50: p * 0.97, ema200: p * 0.9, rsi: 35 + rnd() * 35 } })
    return wait<CoinDetail>({ ...c, candles, scoreBreakdown: { Trend: 27, 'Pullback quality': 15, RSI: 11, Volume: 12, 'Momentum/ADX': 7, 'Market regime': 10 }, invalidation: ['A candle closes below the stop loss.', 'Price closes below EMA200 on the signal timeframe.', 'BTC loses its 1D EMA200.'] })
  },
  watchlist: () => wait(watch.map(w => coins.find(c => c.symbol === w)!).filter(Boolean)),
  add: (sym: string) => { if (!watch.includes(sym)) watch.push(sym); return wait(true) }, del: (sym: string) => { watch = watch.filter(w => w !== sym); return wait(true) },
}
