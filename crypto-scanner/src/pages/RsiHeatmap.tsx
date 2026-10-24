import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api2, tvUrl } from '../api/client'
import { Empty, ErrorBox, Skeleton } from '../components/ui'
import { TFS, rsiBg, rsiCls, px } from '../lib'
const sel = 'rounded-lg border border-line bg-panel px-2 py-1.5 text-sm'
export default function RsiHeatmap() {
  const [tf, setTf] = useState('4h'); const [lo, setLo] = useState(''); const [hi, setHi] = useState(''); const [ex, setEx] = useState(''); const [q, setQ] = useState(''); const [view, setView] = useState<'tiles' | 'matrix'>('tiles')
  const r = useQuery({ queryKey: ['heat', tf, lo, hi, ex, q], queryFn: () => api2.heatmap({ tf, rsiMin: lo === '' ? undefined : +lo, rsiMax: hi === '' ? undefined : +hi, exchange: ex || undefined, search: q || undefined }), refetchInterval: 10000, placeholderData: p => p })
  const items = [...(r.data?.items ?? [])].sort((a, b) => (b.rsi[tf] ?? -1) - (a.rsi[tf] ?? -1))
  return (
    <div className="space-y-4">
      <div className="glass flex flex-wrap items-center gap-2 p-3">
        <div className="flex gap-1" role="tablist">{TFS.map(t => <button key={t} role="tab" aria-selected={tf === t} onClick={() => setTf(t)} className={`btn ${tf === t ? 'bg-white/10' : ''}`}>{t}</button>)}</div>
        <span className="text-sm text-slate-400">RSI on {tf} between</span>
        <input aria-label="RSI min" type="number" min={0} max={100} placeholder="0" value={lo} onChange={e => setLo(e.target.value)} className={`${sel} w-20`} /><span>and</span>
        <input aria-label="RSI max" type="number" min={0} max={100} placeholder="100" value={hi} onChange={e => setHi(e.target.value)} className={`${sel} w-20`} />
        <select aria-label="Exchange" className={sel} value={ex} onChange={e => setEx(e.target.value)}><option value="">All exchanges</option>{['Binance', 'OKX', 'Bybit', 'KuCoin'].map(x => <option key={x}>{x}</option>)}</select>
        <input aria-label="Search" placeholder="Search coin" className={sel} onChange={e => setQ(e.target.value)} />
        <div className="ml-auto flex gap-1"><button className={`btn ${view === 'tiles' ? 'bg-white/10' : ''}`} onClick={() => setView('tiles')}>Heatmap</button><button className={`btn ${view === 'matrix' ? 'bg-white/10' : ''}`} onClick={() => setView('matrix')}>All timeframes</button></div>
      </div>
      {r.data && <div className="text-xs text-slate-400">{r.data.total} coins · {Object.entries(r.data.byExchange).map(([k, v]) => `${k} ${v}`).join(' · ')} · live RSI includes the forming candle · green below 30 (oversold), red above 70 (overbought)</div>}
      {r.isError ? <ErrorBox onRetry={() => r.refetch()} /> : r.isLoading ? <Skeleton className="h-96" /> : !items.length ? <Empty text="No coins match this RSI range" /> : view === 'tiles' ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">{items.map(h => (
          <a key={h.symbol} href={tvUrl(h.tradingViewSymbol)} target="_blank" rel="noreferrer" style={{ background: rsiBg(h.rsi[tf]) }} className="rounded-lg border border-white/10 p-2 text-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-up">
            <div className="text-sm font-semibold">{h.symbol}</div><div className="num text-lg">{h.rsi[tf] == null ? '–' : h.rsi[tf]!.toFixed(1)}</div><div className="text-[10px] text-slate-300">{h.exchange} · ${px(h.price)}</div></a>))}</div>
      ) : (
        <div className="glass overflow-x-auto"><table className="w-full text-sm"><thead className="text-xs text-slate-400"><tr><th className="p-2 text-left">Coin</th><th className="p-2 text-left">Exchange</th>{TFS.map(t => <th key={t} className="p-2">{t}</th>)}</tr></thead>
          <tbody>{items.map(h => <tr key={h.symbol} className="border-t border-line/50"><td className="p-2 font-semibold">{h.symbol}</td><td className="p-2 text-xs text-slate-400">{h.exchange}</td>{TFS.map(t => <td key={t} className={`num p-2 text-center ${rsiCls(h.rsi[t])}`}>{h.rsi[t] == null ? '–' : h.rsi[t]!.toFixed(1)}</td>)}</tr>)}</tbody></table></div>
      )}
    </div>
  )
}
