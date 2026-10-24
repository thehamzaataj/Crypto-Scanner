import { NavLink, Outlet } from 'react-router-dom'
import { Activity, LayoutDashboard, List, Settings as Cog, Star, Radar, Flame, Target } from 'lucide-react'
import { useMarket } from '../hooks/useData'
import { USE_MOCK } from '../api/client'
import { useLive } from '../hooks/useLive'
const nav = [['/', 'Dashboard', LayoutDashboard], ['/signals', 'Trade Signals', Activity], ['/coins', 'All Coins', List], ['/rsi', 'RSI Heatmap', Flame], ['/strategy', 'Strategy & Scan', Target], ['/watchlist', 'Watchlist', Star], ['/settings', 'Settings', Cog]] as const
export default function Layout() {
  useLive()
  const { data, isError, dataUpdatedAt, isFetching } = useMarket()
  const age = data ? Date.now() - dataUpdatedAt : 0
  const status = isError ? 'Offline' : age > 60000 ? 'Delayed' : data ? 'Connected' : 'Connecting'
  const dot = status === 'Connected' ? 'bg-up' : status === 'Delayed' ? 'bg-amber' : 'bg-down'
  const stale = isError || age > 120000
  const regime = data?.btcRegime
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-line bg-ink/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <div className="flex items-center gap-2 font-semibold"><Radar size={18} className="text-up" />Trend Scanner</div>
          {USE_MOCK && <span className="rounded bg-amber/15 px-2 py-0.5 text-xs font-semibold text-amber">DEMO DATA</span>}
          <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-slate-400">
            {regime && <span>BTC 1D: <b className={regime === 'Bullish' ? 'text-up' : regime === 'Bearish' ? 'text-down' : 'text-amber'}>{regime}</b></span>}
            <span>Updated {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '–'}{isFetching && ' …'}</span>
            <span className="flex items-center gap-1.5"><i className={`h-2 w-2 rounded-full ${dot} ${status === 'Connected' ? 'live' : ''}`} />{status}</span>
          </div>
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 overflow-x-auto px-3 pb-2" aria-label="Main">
          {nav.map(([to, label, Icon]) => <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-up ${isActive ? 'bg-white/10 text-white' : 'text-slate-400 hover:text-white'}`}><Icon size={15} />{label}</NavLink>)}
        </nav>
      </header>
      {stale && <div role="status" className="bg-amber/15 px-4 py-2 text-center text-sm text-amber">Stale data: the last successful update was more than 2 minutes ago. Do not trade on these values.</div>}
      {regime === 'Bearish' && <div className="bg-down/10 px-4 py-2 text-center text-sm text-down">BTC is below its 1D EMA200. Altcoin Buy signals are downgraded or hidden.</div>}
      <main className="mx-auto max-w-7xl px-4 py-6"><Outlet /></main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-500">Not financial advice. Signals are computed on closed candles. Past results do not predict future performance.</footer>
    </div>
  )
}
