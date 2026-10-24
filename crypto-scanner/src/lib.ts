export const usd = (n: number) => (n >= 1e9 ? `$${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`)
export const px = (n: number) => (n >= 100 ? n.toFixed(2) : n >= 1 ? n.toFixed(3) : n.toPrecision(3))
export const pct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
export const time = (iso: string) => new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
export const gradeCls = (g: string) => g === 'Strong Buy' ? 'bg-up/15 text-up border-up/40' : g === 'Buy' ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30' : g === 'Watch' ? 'bg-amber/10 text-amber border-amber/30' : 'bg-slate-500/10 text-slate-400 border-slate-500/30'
export const TFS = ['15m', '1h', '4h', '12h', '1d', '1w']
export const rsiCls = (v?: number | null) => v == null ? 'text-slate-600' : v < 30 ? 'bg-up/25 text-up' : v < 40 ? 'bg-up/10 text-emerald-300' : v <= 60 ? 'text-slate-300' : v < 70 ? 'bg-down/10 text-orange-300' : 'bg-down/25 text-down'
export const rsiBg = (v?: number | null) => v == null ? '#1f2a3a' : `hsl(${140 - 1.4 * Math.min(100, Math.max(0, v))} 55% 26%)`
