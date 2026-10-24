import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ExternalLink, Star, X } from 'lucide-react'
import { useCoin, useWatchToggle, useWatchlist } from '../hooks/useData'
import { tvUrl } from '../api/client'
import { px, usd } from '../lib'
import { Change, ErrorBox, Grade, Logo, Meta, Skeleton } from './ui'
export default function CoinModal({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const { data: c, isError, refetch } = useCoin(symbol); const { data: wl } = useWatchlist(); const tog = useWatchToggle()
  const [tab, setTab] = useState<'price' | 'volume' | 'rsi'>('price')
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onClose])
  const saved = !!wl?.some(w => w.symbol === symbol)
  const d = c?.candles.map(x => ({ ...x, label: new Date(x.t).toLocaleDateString([], { month: 'short', day: 'numeric' }) }))
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={`${symbol} analysis`} className="glass max-h-[92vh] w-full max-w-3xl overflow-y-auto bg-panel p-5" onClick={e => e.stopPropagation()}>
        {isError ? <ErrorBox onRetry={refetch} /> : !c ? <Skeleton className="h-96" /> : <>
          <div className="flex items-start gap-3">
            <Logo s={c} /><div className="min-w-0 flex-1"><h2 className="text-lg font-semibold">{c.name} <span className="text-slate-400">{c.symbol}</span></h2><div className="text-xs text-slate-400">Rank #{c.rank} · MC {usd(c.marketCap)} · <Meta s={c} /></div></div>
            <div className="text-right"><div className="num text-lg">${px(c.price)}</div><Change v={c.change24h} /></div>
            <button className="btn" aria-label="Close" onClick={onClose}><X size={16} /></button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2"><Grade g={c.grade} /><span className="num text-sm">Score {c.score}/100</span><span className="rounded border border-line px-2 text-xs">{c.status}</span></div>
          <div className="mt-4 grid grid-cols-3 gap-2 text-sm sm:grid-cols-6">
            {([['EMA50', px(c.ema50)], ['EMA200', px(c.ema200)], ['RSI', c.rsi.toFixed(1)], ['ADX', c.adx.toFixed(1)], ['Vol / avg', c.volumeRatio.toFixed(2) + 'x'], ['ATR', px(c.atr)]] as const).map(([k, v]) => <div key={k} className="rounded-lg border border-line p-2"><div className="text-xs text-slate-400">{k}</div><div className="num">{v}</div></div>)}
          </div>
          <div className="mt-3 rounded-lg border border-line p-3 text-sm"><div className="num">Entry {px(c.entryLow)}–{px(c.entryHigh)} · SL {px(c.stopLoss)} · TP {px(c.tp1)} / {px(c.tp2)} / {px(c.tp3)} · R:R {c.riskReward.toFixed(2)}</div></div>
          <div className="mt-4 flex gap-1" role="tablist">{(['price', 'volume', 'rsi'] as const).map(t => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`btn ${tab === t ? 'bg-white/10' : ''}`}>{t === 'price' ? 'Price + EMA' : t === 'volume' ? 'Volume' : 'RSI'}</button>)}</div>
          <div className="mt-2 h-64">
            <ResponsiveContainer>
              {tab === 'price' ? <ComposedChart data={d}><CartesianGrid stroke="#1f2a3a" /><XAxis dataKey="label" tick={{ fontSize: 10 }} /><YAxis domain={['auto', 'auto']} tick={{ fontSize: 10 }} width={50} /><Tooltip contentStyle={{ background: '#111823', border: '1px solid #1f2a3a' }} />
                <Line dataKey="c" stroke="#e2e8f0" dot={false} name="Close" /><Line dataKey="ema50" stroke="#2dd4a0" dot={false} name="EMA50" /><Line dataKey="ema200" stroke="#f2b84b" dot={false} name="EMA200" />
                <ReferenceLine y={c.entryHigh} stroke="#60a5fa" strokeDasharray="4 3" label={{ value: 'Entry', fontSize: 10, fill: '#60a5fa' }} /><ReferenceLine y={c.stopLoss} stroke="#f0616d" strokeDasharray="4 3" label={{ value: 'SL', fontSize: 10, fill: '#f0616d' }} />
                {[c.tp1, c.tp2, c.tp3].map((y, i) => <ReferenceLine key={i} y={y} stroke="#2dd4a0" strokeDasharray="4 3" label={{ value: `TP${i + 1}`, fontSize: 10, fill: '#2dd4a0' }} />)}</ComposedChart>
              : tab === 'volume' ? <BarChart data={d}><CartesianGrid stroke="#1f2a3a" /><XAxis dataKey="label" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} width={50} /><Tooltip contentStyle={{ background: '#111823', border: '1px solid #1f2a3a' }} /><Bar dataKey="v" fill="#4b6584" name="Volume" /></BarChart>
              : <ComposedChart data={d}><CartesianGrid stroke="#1f2a3a" /><XAxis dataKey="label" tick={{ fontSize: 10 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={50} /><Tooltip contentStyle={{ background: '#111823', border: '1px solid #1f2a3a' }} /><ReferenceLine y={30} stroke="#2dd4a0" strokeDasharray="3 3" /><ReferenceLine y={70} stroke="#f0616d" strokeDasharray="3 3" /><Line dataKey="rsi" stroke="#a78bfa" dot={false} name="RSI" /></ComposedChart>}
            </ResponsiveContainer>
          </div>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 text-sm">
            <div><h3 className="mb-1 font-semibold">Why this signal fired</h3><ul className="list-disc space-y-1 pl-5 text-slate-300">{c.explanation.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
            <div><h3 className="mb-1 font-semibold">What would invalidate it</h3><ul className="list-disc space-y-1 pl-5 text-slate-300">{c.invalidation.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
          </div>
          <div className="mt-3 text-xs text-slate-400">Score breakdown: {Object.entries(c.scoreBreakdown).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>
          <div className="mt-4 flex flex-wrap gap-2"><a className="btn" href={tvUrl(c.tradingViewSymbol)} target="_blank" rel="noreferrer"><ExternalLink size={14} className="mr-1 inline" />Open TradingView</a>
            <button className="btn" onClick={() => tog.mutate({ symbol, on: !saved })}><Star size={14} className={`mr-1 inline ${saved ? 'fill-amber text-amber' : ''}`} />{saved ? 'Remove from watchlist' : 'Add to watchlist'}</button></div>
          <p className="mt-3 text-xs text-slate-500">Not financial advice. Trading crypto carries a high risk of loss.</p>
        </>}
      </div>
    </div>
  )
}
