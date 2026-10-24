# Global Crypto Trend Scanner (frontend)

React + Vite + TypeScript, Tailwind, TanStack Query/Virtual, Recharts, Lucide. The frontend only consumes your REST API and never calculates indicators.

## Setup
```
npm install
cp .env .env.local   # set VITE_API_BASE_URL and VITE_USE_MOCK
npm run dev
```
`VITE_USE_MOCK=true` serves generated data from `src/api/mock.ts` and shows a **DEMO DATA** badge. Set it to `false` for real mode, which never uses mock values.

## Backend contract
All list endpoints return `{ items, total, page, limit }`.
- `GET /api/coins?page&limit&search&signal&minMarketCap&minVolume&exchange&sort&timeframe&confirmedOnly`
- `GET /api/signals` same params. Items follow `Signal` in `src/types.ts` (symbol, name, logo, exchange, pair, tradingViewSymbol, price, change24h, marketCap, volume24h, rank, timeframe, score, grade, rsi, ema50, ema200, adx, atr, volumeRatio, entryLow, entryHigh, stopLoss, tp1-3, riskReward, status, candleCloseTime, explanation[], trend)
- `GET /api/coin/{symbol}` returns `CoinDetail`: Signal + `candles[{t,o,h,l,c,v,ema50,ema200,rsi}]`, `scoreBreakdown`, `invalidation[]`
- `GET /api/market-status` returns `MarketStatus`
- `GET /api/signals/performance` returns `Performance`
- `GET /api/watchlist` returns `Signal[]`; `POST /api/watchlist {symbol}`; `DELETE /api/watchlist/{symbol}`

The backend must compute signals on closed candles only, apply the universe filter, hide R:R below 1.5, downgrade altcoin signals when BTC is below its 1D EMA200, and score 0-100 (Trend 30, Pullback 20, RSI 15, Volume 15, ADX 10, Regime 10; Strong Buy 85+, Buy 70-84, Watch 55-69). TradingView links use the backend's `tradingViewSymbol` only.

## Status badge rules
Connected: last fetch under 60s old. Delayed: 60-120s. Offline: request failing. A "Stale data" banner shows after 2 minutes or on error.
