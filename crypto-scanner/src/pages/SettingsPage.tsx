import { useSettings, DEFAULTS } from '../hooks/useSettings'
import { Card } from '../components/ui'
import type { Settings } from '../types'
const num = ['minVolume', 'minMarketCap', 'rsiMin', 'rsiMax', 'adxMin', 'minRR', 'refreshSec'] as const
const label: Record<string, string> = { minVolume: 'Min 24h volume ($)', minMarketCap: 'Min market cap ($)', rsiMin: 'RSI min', rsiMax: 'RSI max', adxMin: 'ADX min (20–25)', minRR: 'Min R:R', refreshSec: 'Refresh interval (seconds)' }
export default function SettingsPage() {
  const { s, set } = useSettings()
  return <Card title="Settings"><div className="grid max-w-xl gap-3">
    {num.map(k => <label key={k} className="grid grid-cols-2 items-center gap-2 text-sm">{label[k]}<input type="number" className="rounded-lg border border-line bg-panel px-2 py-1.5" value={s[k]} min={k === 'refreshSec' ? 10 : 0} onChange={e => set({ [k]: +e.target.value } as Partial<Settings>)} /></label>)}
    <label className="grid grid-cols-2 items-center gap-2 text-sm">Default timeframe<select className="rounded-lg border border-line bg-panel px-2 py-1.5" value={s.timeframe} onChange={e => set({ timeframe: e.target.value as Settings['timeframe'] })}><option>4H</option><option>1D</option></select></label>
    <label className="grid grid-cols-2 items-center gap-2 text-sm">Theme<select className="rounded-lg border border-line bg-panel px-2 py-1.5" value={s.theme} onChange={e => set({ theme: e.target.value as Settings['theme'] })}><option value="dark">Dark</option><option value="light">Light</option></select></label>
    <button className="btn w-fit" onClick={() => set(DEFAULTS)}>Reset to defaults</button>
    <p className="text-xs text-slate-500">Volume and market cap filters apply to list queries. The backend computes all indicators; thresholds such as RSI and ADX are shown for reference and sent to the backend if it supports them.</p></div></Card>
}
