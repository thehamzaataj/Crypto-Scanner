import { useState } from 'react'
import { useWatchlist, useWatchToggle } from '../hooks/useData'
import { Change, Empty, ErrorBox, Grade, Logo, Meta, Skeleton } from '../components/ui'
import CoinModal from '../components/CoinModal'
import { px } from '../lib'
export default function Watchlist() {
  const q = useWatchlist(), t = useWatchToggle(); const [open, setOpen] = useState<string | null>(null)
  if (q.isError) return <ErrorBox onRetry={() => q.refetch()} />
  if (q.isLoading) return <Skeleton className="h-40" />
  if (!q.data?.length) return <Empty text="Your watchlist is empty. Open a coin and choose Add to watchlist." />
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{q.data.map(s => (
    <div key={s.symbol} className="glass p-4"><button className="flex w-full items-center gap-2" onClick={() => setOpen(s.symbol)}><Logo s={s} /><b>{s.symbol}</b><span className="ml-auto"><Grade g={s.grade} /></span></button>
      <div className="num mt-2 flex justify-between"><span>${px(s.price)}</span><Change v={s.change24h} /></div><div className="mt-1 text-sm">Status: {s.status} · Score {s.score}</div><div className="mt-1"><Meta s={s} /></div>
      <button className="btn mt-3" onClick={() => t.mutate({ symbol: s.symbol, on: false })}>Remove</button></div>))}
    {open && <CoinModal symbol={open} onClose={() => setOpen(null)} />}</div>
}
