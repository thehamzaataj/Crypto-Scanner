import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Settings } from '../types'
export const DEFAULTS: Settings = { minVolume: 1e6, minMarketCap: 1e7, rsiMin: 40, rsiMax: 55, adxMin: 20, minRR: 1.5, timeframe: '4H', refreshSec: 30, theme: 'dark' }
const Ctx = createContext<{ s: Settings; set: (p: Partial<Settings>) => void }>({ s: DEFAULTS, set: () => {} })
export const SettingsProvider = ({ children }: { children: ReactNode }) => {
  const [s, setS] = useState<Settings>(() => { try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem('settings') || '{}') } } catch { return DEFAULTS } })
  useEffect(() => { localStorage.setItem('settings', JSON.stringify(s)); document.documentElement.classList.toggle('dark', s.theme === 'dark') }, [s])
  return <Ctx.Provider value={{ s, set: p => setS(v => ({ ...v, ...p })) }}>{children}</Ctx.Provider>
}
export const useSettings = () => useContext(Ctx)
