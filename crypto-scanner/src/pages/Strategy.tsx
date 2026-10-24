import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Play } from 'lucide-react'
import { api, api2 } from '../api/client'
import { Card, ErrorBox, Grade, Skeleton } from '../components/ui'
import { time } from '../lib'
import type { PerfRow } from '../types'
const inp = 'w-24 rounded-lg border border-line bg-panel px-2 py-1.5 text-sm'
const Rows = ({ title, rows }: { title: string; rows?: PerfRow[] }) => <div><h3 className="mb-1 text-xs text-slate-400">{title}</h3>{rows?.map(r => <div key={r.label} className="flex justify-between border-b border-line/60 py-1 text-sm"><span>{r.label}</span><span className="num text-slate-300">{r.total ? `${r.winRate}% win · ${r.directionAccuracy}% up · ${r.wins}W/${r.losses}L/${r.expired}E` : 'no resolved signals yet'}</span></div>)}</div>
export default function Strategy() {
  const info = useQuery({ queryKey: ['strategy'], queryFn: api2.strategy })
  const st = useQuery({ queryKey: ['scanStatus'], queryFn: api2.scanStatus, refetchInterval: q => (q.state.data?.running ? 1000 : 5000) })
  const perf = useQuery({ queryKey: ['perf'], queryFn: api.perf, refetchInterval: 15000 })
  const hist = useQuery({ queryKey: ['scans'], queryFn: api2.scans, refetchInterval: 15000 })
  const [p, setP] = useState({ adxMin: 20, minRR: 1.5, minScore: 55, topN: 150 })
  const run = useMutation({ mutationFn: () => api2.scan(p), onSuccess: () => st.refetch() })
  if (info.isError) return <ErrorBox onRetry={() => info.refetch()} />
  const s = st.data, last = s?.last, pct = s?.total ? Math.round((100 * s.done) / s.total) : 0
  return (
    <div className="space-y-4">
      <Card title={info.data?.name ?? 'Strategy'}>
        {!info.data ? <Skeleton /> : <div className="grid gap-4 md:grid-cols-2"><ul className="list-disc space-y-1 pl-5 text-sm text-slate-300">{info.data.rules.map(r => <li key={r}>{r}</li>)}</ul>
          <div className="text-sm"><div className="mb-1 text-xs text-slate-400">Score weights</div><div className="num">{Object.entries(info.data.weights).map(([k, v]) => `${k} ${v}`).join(' · ')}</div>
            <div className="mb-1 mt-3 text-xs text-slate-400">Grades</div><div className="num">{Object.entries(info.data.grades).map(([k, v]) => `${k} ${v}`).join(' · ')}</div></div></div>}
      </Card>
      <Card title="Scan with Trend Following">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          {([['topN', 'Coins to scan (max 250)'], ['adxMin', 'ADX min'], ['minRR', 'Min R:R'], ['minScore', 'Min score']] as const).map(([k, l]) => <label key={k} className="grid gap-1 text-xs text-slate-400">{l}<input type="number" className={inp} value={p[k]} onChange={e => setP({ ...p, [k]: +e.target.value })} /></label>)}
          <button className="btn flex items-center gap-1.5 bg-up/20 text-up" disabled={s?.running || run.isPending} onClick={() => run.mutate()}><Play size={14} />{s?.running ? 'Scanning…' : 'Scan now'}</button>
        </div>
        {run.isError && <p role="alert" className="mt-2 text-sm text-down">Could not start the scan. A scan may already be running.</p>}
        {s?.running && <div className="mt-3"><div className="h-2 overflow-hidden rounded bg-line"><div className="h-full bg-up transition-all" style={{ width: `${pct}%` }} /></div><div className="num mt-1 text-xs text-slate-400">{s.done} / {s.total} coins · {pct}%</div></div>}
        {last && <div className="mt-4"><div className="text-sm">Last scan {time(last.ts)}: <b>{last.coins}</b> coins ({Object.entries(last.byExchange).map(([k, v]) => `${k} ${v}`).join(' · ')}), <b>{last.signals}</b> signals, BTC {last.regime}</div>
          <ul className="mt-2 space-y-2">{last.top.map(t => <li key={t.symbol + t.timeframe} className="rounded-lg border border-line p-2 text-sm"><div className="flex items-center gap-2"><b>{t.symbol}</b><Grade g={t.grade} /><span className="num text-xs text-slate-400">{t.score} · {t.timeframe} · {t.exchange}</span></div><p className="mt-1 text-xs text-slate-300">{t.reason}</p></li>)}</ul></div>}
      </Card>
      <Card title="Were past signals accurate?">
        {!perf.data ? <Skeleton /> : <><div className="num text-sm">Win rate {perf.data.winRate}% · Avg R {perf.data.avgR} · Price higher after signal {perf.data.directionAccuracy}% · {perf.data.totalSignals} signals ({perf.data.open} still open)</div>
          <p className="mt-1 text-xs text-slate-500">{perf.data.source}</p>
          <div className="mt-3 grid gap-4 md:grid-cols-3"><Rows title="By grade" rows={perf.data.byGrade} /><Rows title="By timeframe" rows={perf.data.byTimeframe} /><Rows title="By exchange" rows={perf.data.byExchange} /></div>
          {!!perf.data.recent?.length && <div className="mt-4"><h3 className="mb-1 text-xs text-slate-400">Recent results</h3>{perf.data.recent.map((r, i) => <div key={i} className="border-b border-line/60 py-1 text-sm"><b>{r.symbol}</b> {r.timeframe} {r.exchange} · {r.grade} · <span className={r.status === 'TP hit' ? 'text-up' : r.status === 'Stopped' ? 'text-down' : 'text-amber'}>{r.status}</span> <span className="num">{r.fwdReturn}%</span></div>)}</div>}</>}
      </Card>
      <Card title="Scan history">
        {hist.data?.length ? hist.data.map(h => <div key={h.id} className="num flex justify-between border-b border-line/60 py-1 text-sm"><span>#{h.id} {time(h.ts)}</span><span>{h.coins} coins · {h.signals} signals · BTC {h.regime}</span></div>) : <span className="text-sm text-slate-400">No scans stored yet.</span>}
      </Card>
    </div>
  )
}
