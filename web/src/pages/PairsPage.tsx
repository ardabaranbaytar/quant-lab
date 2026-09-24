import { useState } from 'react'
import { Link } from 'react-router-dom'
import { TickerInput } from '../components/TickerInput'
import { Button, Card, ErrorBanner, Field, Spinner } from '../components/ui'
import { api, type PairScanResult } from '../lib/api'
import { num } from '../lib/format'

const UNIVERSES: Record<string, string[]> = {
  Payments: ['V', 'MA', 'AXP', 'PYPL', 'FIS', 'GPN'],
  Banks: ['JPM', 'BAC', 'C', 'WFC', 'GS', 'MS'],
  Energy: ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'OXY'],
  Staples: ['KO', 'PEP', 'PG', 'CL', 'KMB', 'MDLZ'],
  Retail: ['WMT', 'TGT', 'COST', 'HD', 'LOW', 'DG'],
}

const SIGNIFICANCE = 0.05

export function PairsPage() {
  const [tickers, setTickers] = useState(UNIVERSES.Payments)
  const [start, setStart] = useState('2015-01-01')
  const [end, setEnd] = useState('2019-12-31')
  const [scan, setScan] = useState<PairScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runScan = async () => {
    setLoading(true)
    setError(null)
    try {
      setScan(await api.scanPairs(tickers, start, end))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const rows = scan?.pairs ?? null
  const nPairs = (tickers.length * (tickers.length - 1)) / 2
  const significant = rows?.filter((r) => r.coint_pvalue < SIGNIFICANCE).length ?? 0

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <Card title="Universe">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(UNIVERSES).map(([name, list]) => (
                <button
                  key={name}
                  onClick={() => setTickers(list)}
                  className="rounded-md border border-line px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
                >
                  {name}
                </button>
              ))}
            </div>
            <Field label="Tickers" hint={`${nPairs} pairs will be tested (max 40 tickers)`}>
              <TickerInput value={tickers} onChange={setTickers} max={40} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Start">
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label="End">
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>
            <Button className="w-full" onClick={runScan} disabled={loading || tickers.length < 2}>
              {loading ? 'Scanning…' : 'Scan pairs'}
            </Button>
          </div>
        </Card>
        <Card>
          <p className="text-xs leading-relaxed text-ink-2">
            <span className="font-semibold text-ink">Avoid look-ahead:</span> choose pairs on an in-sample window
            (default 2015–2019), then backtest them on later data. Picking pairs on the same period you trade
            them inflates results.
          </p>
        </Card>
      </aside>

      <section className="min-w-0 space-y-4">
        {error && <ErrorBanner message={error} />}
        {loading && (
          <Card>
            <Spinner label={`Running ${nPairs} Engle–Granger cointegration tests…`} />
          </Card>
        )}
        {scan && scan.skipped.length > 0 && !loading && (
          <div className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink-2">
            <span className="font-semibold text-ink">Skipped · </span>
            no price data for {scan.skipped.join(', ')}
          </div>
        )}
        {rows && !loading && (
          <Card
            title="Candidate pairs"
            action={
              <span className="text-xs text-muted">
                {significant} of {rows.length} cointegrated at {SIGNIFICANCE * 100}%
              </span>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="py-2 pr-4 font-medium">Pair</th>
                    <th className="py-2 pr-4 text-right font-medium">Coint. p-value</th>
                    <th className="py-2 pr-4 text-right font-medium">Return corr.</th>
                    <th className="py-2 pr-4 text-right font-medium">Hedge ratio</th>
                    <th className="py-2 pr-4 text-right font-medium">Half-life</th>
                    <th className="py-2 font-medium" />
                  </tr>
                </thead>
                <tbody className="tabular">
                  {rows.map((r) => {
                    const sig = r.coint_pvalue < SIGNIFICANCE
                    const next = new Date(end)
                    next.setDate(next.getDate() + 1)
                    const q = new URLSearchParams({
                      strategy: 'pairs_trading',
                      tickers: `${r.asset_a},${r.asset_b}`,
                      start: next.toISOString().slice(0, 10),
                      end: '2024-12-31',
                    })
                    return (
                      <tr key={r.pair} className="border-b border-line/50 last:border-0">
                        <td className="py-2 pr-4 font-medium text-ink">
                          {r.asset_a} / {r.asset_b}
                        </td>
                        <td className="py-2 pr-4 text-right">
                          <span className={sig ? 'text-good' : 'text-ink-2'}>
                            {sig && <span aria-hidden>✓ </span>}
                            {r.coint_pvalue < 0.0001 ? '<0.0001' : r.coint_pvalue.toFixed(4)}
                          </span>
                          {sig && <span className="sr-only"> (cointegrated)</span>}
                        </td>
                        <td className="py-2 pr-4 text-right text-ink-2">{num(r.correlation)}</td>
                        <td className="py-2 pr-4 text-right text-ink-2">{num(r.hedge_ratio, 3)}</td>
                        <td className="py-2 pr-4 text-right text-ink-2">
                          {r.half_life == null ? '∞' : `${r.half_life.toFixed(0)} d`}
                        </td>
                        <td className="py-2 text-right">
                          <Link to={`/?${q}`} className="whitespace-nowrap text-xs text-accent hover:underline">
                            Backtest out-of-sample →
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        {!rows && !loading && (
          <Card>
            <div className="py-16 text-center">
              <h1 className="text-xl font-semibold text-ink">Find cointegrated pairs</h1>
              <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">
                Tests every pair in the universe for a stable long-run relationship (Engle–Granger), and estimates
                how quickly the spread mean-reverts.
              </p>
            </div>
          </Card>
        )}
      </section>
    </div>
  )
}
