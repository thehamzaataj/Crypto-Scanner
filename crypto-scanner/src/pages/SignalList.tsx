import { useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useList } from '../hooks/useData'
import { useSettings } from '../hooks/useSettings'
import { Change, Empty, ErrorBox, Grade, Logo, Meta, Skeleton } from '../components/ui'
import CoinModal from '../components/CoinModal'
import { tvUrl } from '../api/client'
import { TFS, pct, px, rsiCls, usd } from '../lib'
import type { ListParams, Signal } from '../types'
const COLS = 'grid-cols-[34px_1.3fr_1fr_1fr_70px_170px_80px_2fr_50px_70px_64px]'
const sel = 'rounded-lg border border-line bg-panel px-2 py-1.5 text-sm'
const Chips = ({ s }: { s: Signal }) => <div className="grid grid-cols-3 gap-0.5">{TFS.map(t => <span key={t} className={`num rounded px-1 text-center text-[10px] ${rsiCls(s.rsiByTf?.[t])}`}>{t} {s.rsiByTf?.[t] == null ? '–' : s.rsiByTf[t]!.toFixed(0)}</span>)}</div>
export default function SignalList({ kind }: { kind: 'signals' | 'coins' }) {
  const { s } = useSettings()
  const [f, setF] = useState<ListParams>({ page: 1, limit: 50, sort: 'score', timeframe: kind === 'signals' ? s.timeframe : '', rsiTf: '4h' })
  const [open, setOpen] = useState<string | null>(null)
  const hasRsi = f.rsiMin !== undefined || f.rsiMax !== undefined
  const q = useList(kind, { ...f, rsiTf: hasRsi ? f.rsiTf : undefined, minVolume: f.minVolume ?? s.minVolume, minMarketCap: f.minMarketCap ?? s.minMarketCap })
  const set = (p: Partial<ListParams>) => setF(v => ({ ...v, page: 1, ...p }))
  const num = (v: string) => (v === '' ? undefined : +v)
  const items = q.data?.items ?? []; const ref = useRef<HTMLDivElement>(null)
  const v = useVirtualizer({ count: items.length, getScrollElement: () => ref.current, estimateSize: () => 84, overscan: 6 })
  const pages = Math.max(1, Math.ceil((q.data?.total ?? 0) / (f.limit ?? 50)))
  return (
    <div className="space-y-4">
      <div className="glass flex flex-wrap items-center gap-2 p-3">
        <input aria-label="Search coins" placeholder="Search coin" className={sel} onChange={e => set({ search: e.target.value })} />
        <select aria-label="Grade" className={sel} onChange={e => set({ signal: e.target.value })}><option value="">All grades</option>{['Strong Buy', 'Buy', 'Watch', 'Neutral'].map(g => <option key={g}>{g}</option>)}</select>
        <select aria-label="Market cap" className={sel} onChange={e => set({ minMarketCap: e.target.value ? +e.target.value : undefined })}><option value="">Market cap &gt; $10M</option><option value="1e8">&gt; $100M</option><option value="1e9">&gt; $1B</option></select>
        <select aria-label="Volume" className={sel} onChange={e => set({ minVolume: e.target.value ? +e.target.value : undefined })}><option value="">Volume &gt; $1M</option><option value="1e8">High liquidity (&gt; $100M)</option></select>
        <select aria-label="Exchange" className={sel} onChange={e => set({ exchange: e.target.value })}><option value="">All exchanges</option>{['Binance', 'OKX', 'Bybit', 'KuCoin'].map(x => <option key={x}>{x}</option>)}</select>
        <select aria-label="Signal timeframe" className={sel} value={f.timeframe} onChange={e => set({ timeframe: e.target.value })}><option value="">Signal TF: all</option><option>4H</option><option>1D</option></select>
        <span className="flex items-center gap-1 text-sm text-slate-400">RSI on
          <select aria-label="RSI timeframe" className={sel} value={f.rsiTf} onChange={e => set({ rsiTf: e.target.value })}>{TFS.map(t => <option key={t}>{t}</option>)}</select>
          <input aria-label="RSI min" type="number" min={0} max={100} placeholder="min" className={`${sel} w-16`} onChange={e => set({ rsiMin: num(e.target.value) })} />–
          <input aria-label="RSI max" type="number" min={0} max={100} placeholder="max" className={`${sel} w-16`} onChange={e => set({ rsiMax: num(e.target.value) })} /></span>
      </div>
      {q.isError ? <ErrorBox onRetry={() => q.refetch()} /> : q.isLoading ? <div className="space-y-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-14" />)}</div> : !items.length ? <Empty text={kind === 'signals' ? 'No trading signals found' : 'No coins found'} /> : <>
        <div className="hidden overflow-x-auto md:block"><div className="glass min-w-[1250px]">
          <div className={`grid ${COLS} gap-2 border-b border-line px-3 py-2 text-xs text-slate-400`}>{['#', 'Coin', 'Price / 24h', 'Mkt cap / 24h vol', 'Trend', 'RSI by timeframe', 'Score', 'Entry / SL / TP', 'R:R', 'Exchange', 'Action'].map(h => <div key={h}>{h}</div>)}</div>
          <div ref={ref} className="h-[600px] overflow-y-auto"><div style={{ height: v.getTotalSize(), position: 'relative' }}>
            {v.getVirtualItems().map(r => { const c = items[r.index]; return (
              <div key={c.symbol + c.timeframe} style={{ position: 'absolute', top: 0, transform: `translateY(${r.start}px)`, height: r.size, width: '100%' }} className="border-b border-line/50 px-3 py-1 hover:bg-white/5">
                <div className={`grid ${COLS} items-center gap-2 text-sm`}>
                  <div className="num text-slate-400">{c.rank}</div>
                  <button className="flex items-center gap-2 text-left" onClick={() => setOpen(c.symbol)}><Logo s={c} /><span><b>{c.symbol}</b><div className="text-xs text-slate-400">{c.name}</div></span></button>
                  <div className="num">${px(c.price)}<div><Change v={c.change24h} /></div></div><div className="num text-xs">{usd(c.marketCap)}<div>{usd(c.volume24h)}</div></div>
                  <div className={c.trend === 'Bullish' ? 'text-up' : c.trend === 'Bearish' ? 'text-down' : 'text-amber'}>{c.trend}</div><Chips s={c} />
                  <div><Grade g={c.grade} /><div className="num text-xs">{c.score}</div></div>
                  <div className="num text-xs">{px(c.entryLow)}–{px(c.entryHigh)} / {px(c.stopLoss)} / {px(c.tp1)}, {px(c.tp2)}, {px(c.tp3)}<div><Meta s={c} /></div></div>
                  <div className="num">{c.riskReward.toFixed(1)}</div><div className="text-xs">{c.exchange}</div>
                  <a className="btn text-center" href={tvUrl(c.tradingViewSymbol)} target="_blank" rel="noreferrer">Chart</a>
                </div>
                <p className="mt-1 truncate text-xs text-slate-400" title={c.reason}>{c.reason}</p>
              </div>) })}
          </div></div></div></div>
        <div className="space-y-2 md:hidden">{items.map((c: Signal) => (
          <div key={c.symbol + c.timeframe} className="glass p-3"><button className="flex w-full items-center gap-2 text-left" onClick={() => setOpen(c.symbol)}><Logo s={c} /><b>{c.symbol}</b><span className="text-xs text-slate-400">{c.exchange}</span><span className="ml-auto"><Grade g={c.grade} /></span></button>
            <div className="num mt-2 flex justify-between text-sm"><span>${px(c.price)}</span><span>{pct(c.change24h)}</span><span>Score {c.score}</span><span>R:R {c.riskReward.toFixed(1)}</span></div>
            <div className="mt-2"><Chips s={c} /></div>
            <div className="num mt-2 text-xs text-slate-300">Entry {px(c.entryLow)}–{px(c.entryHigh)} · SL {px(c.stopLoss)} · TP1 {px(c.tp1)}</div><p className="mt-1 text-xs text-slate-400">{c.reason}</p><div className="mt-1"><Meta s={c} /></div></div>))}</div>
        <div className="flex items-center justify-between text-sm"><span className="text-slate-400">{q.data?.total} results</span>
          <div className="flex items-center gap-2"><button className="btn" disabled={f.page! <= 1} onClick={() => setF(v => ({ ...v, page: v.page! - 1 }))}>Previous</button><span className="num">{f.page} / {pages}</span><button className="btn" disabled={f.page! >= pages} onClick={() => setF(v => ({ ...v, page: v.page! + 1 }))}>Next</button></div></div>
      </>}
      {open && <CoinModal symbol={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
