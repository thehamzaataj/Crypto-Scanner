import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { SettingsProvider } from './hooks/useSettings'
import './index.css'
const qc = new QueryClient({ defaultOptions: { queries: { retry: 2 } } })
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={qc}><SettingsProvider><BrowserRouter><App /></BrowserRouter></SettingsProvider></QueryClientProvider></React.StrictMode>)
