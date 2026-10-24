import { AlertTriangle, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Signal } from '../types'
import { gradeCls, pct } from '../lib'
export const Grade = ({ g }: { g: string }) => <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${gradeCls(g)}`}>{g}</span>
export const Change = ({ v }: { v: number }) => <span className={`num ${v >= 0 ? 'text-up' : 'text-down'}`}>{pct(v)}</span>
export const Skeleton = ({ className = 'h-24' }: { className?: string }) => <div className={`glass animate-pulse ${className}`} aria-busy />
export const Empty = ({ text }: { text: string }) => <div className="glass p-10 text-center text-slate-400">{text}</div>
export const ErrorBox = ({ onRetry }: { onRetry: () => void }) => (
  <div role="alert" className="glass flex items-center justify-between gap-3 border-down/40 p-4 text-sm"><span className="flex items-center gap-2"><AlertTriangle size={16} className="text-down" />Could not load data from the backend.</span><button className="btn" onClick={onRetry}><RefreshCw size={14} className="mr-1 inline" />Retry</button></div>
)
export const Card = ({ title, children }: { title?: string; children: ReactNode }) => <section className="glass p-4">{title && <h2 className="mb-3 text-sm font-semibold text-slate-300">{title}</h2>}{children}</section>
export const Meta = ({ s }: { s: Signal }) => <span className="text-xs text-slate-400">{s.timeframe} · closed {new Date(s.candleCloseTime).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · {s.exchange}</span>
export const Logo = ({ s }: { s: Signal }) => s.logo ? <img src={s.logo} alt="" className="h-7 w-7 rounded-full" /> : <span className="grid h-7 w-7 place-items-center rounded-full bg-line text-[10px] font-semibold">{s.symbol.slice(0, 3)}</span>
