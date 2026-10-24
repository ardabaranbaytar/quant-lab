import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LocaleProvider } from './i18n/LocaleProvider'
import { BacktestPage } from './pages/BacktestPage'
import { BotPage } from './pages/BotPage'
import { HistoryPage } from './pages/HistoryPage'
import { PairsPage } from './pages/PairsPage'
import { RunPage } from './pages/RunPage'

export default function App() {
  return (
    <LocaleProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<BacktestPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="runs/:id" element={<RunPage />} />
            <Route path="pairs" element={<PairsPage />} />
            <Route path="bots" element={<BotPage />} />
            <Route path="bots/:name" element={<BotPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </LocaleProvider>
  )
}
