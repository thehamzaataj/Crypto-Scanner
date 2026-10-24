import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import SignalList from './pages/SignalList'
import RsiHeatmap from './pages/RsiHeatmap'
import Strategy from './pages/Strategy'
import Watchlist from './pages/Watchlist'
import SettingsPage from './pages/SettingsPage'
export default function App() {
  return <Routes><Route element={<Layout />}><Route index element={<Dashboard />} /><Route path="signals" element={<SignalList kind="signals" />} /><Route path="coins" element={<SignalList kind="coins" />} /><Route path="rsi" element={<RsiHeatmap />} /><Route path="strategy" element={<Strategy />} /><Route path="watchlist" element={<Watchlist />} /><Route path="settings" element={<SettingsPage />} /></Route></Routes>
}
