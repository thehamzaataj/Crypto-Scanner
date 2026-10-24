import { useMarket, useList, usePerf } from '../hooks/useData'
import { tvUrl } from '../api/client'
import { Card, Change, Empty, ErrorBox, Grade, Logo, Meta, Skeleton } from '../components/ui'
import { px } from '../lib'
export default function Dashboard() {
  const m = useMarket(), p = usePerf(), l = useList('signals', { limit: 30, sort: 'score' })
  const items = l.data?.items ?? []
  const stats = [['Coins Scanned', m.data?.totalScanned], ['Active Signals', m.data?.activeSignals], ['Strong Trend Coins', m.data?.strongTrendCount], ['Market Status', m.data ? `BTC ${m.data.btcRegime}` : undefined]]
  return (
    <div className="space-y-6">
      {(m.isError || l.isError) && <ErrorBox onRetry={() => { m.refetch(); l.refetch(); p.refetch() }} />}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{stats.map(([k, v]) => v === undefined ? <Skeleton key={k as string} /> : <Card key={k as string}><div className="text-xs text-slate-400">{k}</div><div className="num mt-1 text-2xl">{v}</div></Card>)}</div>
      <section><h2 className="mb-3 font-semibold">Top trending coins</h2>
        {l.isLoading ? <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[...Array(6)].map((_, i) => <Skeleton key={i} />)}</div> : !items.length ? <Empty text="No trading signals found" /> :
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{items.slice(0, 6).map(s => (
            <a key={s.symbol} href={tvUrl(s.tradingViewSymbol)} target="_blank" rel="noreferrer" className="glass block p-4 transition hover:border-up/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-up">
              <div className="flex items-center gap-2"><Logo s={s} /><b>{s.symbol}</b><span className="ml-auto"><Grade g={s.grade} /></span></div>
              <div className="mt-2 flex items-baseline justify-between"><span className="num text-lg">${px(s.price)}</span><Change v={s.change24h} /></div>
              <div className="num mt-1 text-xs text-slate-300">Score {s.score} · RSI {s.rsi.toFixed(0)} · Vol {s.volumeRatio.toFixed(1)}x · EMA50 {s.price > s.ema50 ? '>' : '<'} price</div>
              <div className="mt-1"><Meta s={s} /></div>
            </a>))}</div>}
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Signal performance">
          {p.isLoading ? <Skeleton /> : !p.data ? <span className="text-slate-400">No data</span> : <>
            <div className="num text-sm">Win rate {p.data.winRate}% · Avg R {p.data.avgR} · {p.data.totalSignals} signals</div>
            <div className="mt-3 space-y-1 text-sm">{[...p.data.byGrade, ...p.data.byTimeframe].map(r => <div key={r.label} className="flex justify-between border-b border-line/60 py-1"><span>{r.label}</span><span className="num text-slate-300">{r.winRate}% win · {r.avgR}R · n={r.total}</span></div>)}</div>
            <p className="mt-2 text-xs text-slate-500">Source: {p.data.source}. Past results do not predict future outcomes.</p></>}
        </Card>
        <Card title="Recent signals">
          {l.isLoading ? <Skeleton /> : !items.length ? <span className="text-slate-400">No trading signals found</span> :
            <ul className="space-y-2">{[...items].sort((a, b) => +new Date(b.candleCloseTime) - +new Date(a.candleCloseTime)).slice(0, 6).map(s => <li key={s.symbol} className="flex items-center justify-between gap-2 text-sm"><span className="flex items-center gap-2"><b>{s.symbol}</b><Grade g={s.grade} /></span><span className="text-right"><Meta s={s} /> <span className="ml-1 rounded border border-line px-1.5 text-xs">{s.status}</span></span></li>)}</ul>}
        </Card>
      </div>
    </div>
  )
}
