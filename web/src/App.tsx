import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LocaleProvider } from './i18n/LocaleProvider'
import { BacktestPage } from './pages/BacktestPage'
import { BotPage } from './pages/BotPage'
import { HistoryPage } from './pages/HistoryPage'
import { PairsPage } from './pages/PairsPage'
import { RunPage } from './pages/RunPage'

// The paper bot is the home page. Backtest links from before the move (`/?strategy=...&tickers=...`)
// are sent on to /backtest with their parameters.
function Home() {
  const { search } = useLocation()
  const params = new URLSearchParams(search)
  if (params.has('strategy') || params.has('tickers')) {
    return <Navigate to={`/backtest${search}`} replace />
  }
  return <BotPage />
}

export default function App() {
  return (
    <LocaleProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="backtest" element={<BacktestPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="runs/:id" element={<RunPage />} />
            <Route path="pairs" element={<PairsPage />} />
            <Route path="bots" element={<Navigate to="/" replace />} />
            <Route path="bots/:name" element={<BotPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LocaleProvider>
  )
}
