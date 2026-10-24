import { useState } from 'react'
import { Link } from 'react-router-dom'
import { TickerInput } from '../components/TickerInput'
import { Button, Card, ErrorBanner, Field, Spinner } from '../components/ui'
import { useI18n } from '../i18n/context'
import { api, type PairScanResult } from '../lib/api'

const UNIVERSES = {
  payments: ['V', 'MA', 'AXP', 'PYPL', 'FIS', 'GPN'],
  banks: ['JPM', 'BAC', 'C', 'WFC', 'GS', 'MS'],
  energy: ['XOM', 'CVX', 'COP', 'EOG', 'SLB', 'OXY'],
  staples: ['KO', 'PEP', 'PG', 'CL', 'KMB', 'MDLZ'],
  retail: ['WMT', 'TGT', 'COST', 'HD', 'LOW', 'DG'],
}

const SIGNIFICANCE = 0.05

export function PairsPage() {
  const { t, f } = useI18n()
  const [tickers, setTickers] = useState(UNIVERSES.payments)
  const [start, setStart] = useState('2015-01-01')
  const [end, setEnd] = useState('2019-12-31')
  const [scan, setScan] = useState<PairScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const runScan = async () => {
    setLoading(true)
    setError(null)
    try {
      setScan(await api.scanPairs(tickers, start, end))
    } catch (e) {
      setError(e as Error)
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
        <Card title={t.pairs.universe}>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(UNIVERSES) as (keyof typeof UNIVERSES)[]).map((id) => (
                <button
                  key={id}
                  onClick={() => setTickers(UNIVERSES[id])}
                  className="rounded-md border border-line px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
                >
                  {t.pairs.universes[id]}
                </button>
              ))}
            </div>
            <Field label={t.common.tickers} hint={t.pairs.pairsToTest(nPairs, 40)}>
              <TickerInput value={tickers} onChange={setTickers} max={40} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={t.common.start}>
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label={t.common.end}>
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>
            <Button className="w-full" onClick={runScan} disabled={loading || tickers.length < 2}>
              {loading ? t.pairs.scanning : t.pairs.scan}
            </Button>
          </div>
        </Card>
        <Card>
          <p className="text-xs leading-relaxed text-ink-2">
            <span className="font-semibold text-ink">{t.pairs.lookAheadTitle}</span> {t.pairs.lookAheadText}
          </p>
        </Card>
      </aside>

      <section className="min-w-0 space-y-4">
        {error && <ErrorBanner error={error} />}
        {loading && (
          <Card>
            <Spinner label={t.pairs.running(nPairs)} />
          </Card>
        )}
        {scan && scan.skipped.length > 0 && !loading && (
          <div className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-ink-2">
            <span className="font-semibold text-ink">{t.pairs.skipped}</span>
            {t.pairs.noPriceData(scan.skipped.join(', '))}
          </div>
        )}
        {rows && !loading && (
          <Card
            title={t.pairs.candidates}
            action={
              <span className="text-xs text-muted">
                {t.pairs.cointegratedCount(significant, rows.length, f.pct(SIGNIFICANCE, 0))}
              </span>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="py-2 pr-4 font-medium">{t.common.pair}</th>
                    <th className="py-2 pr-4 text-right font-medium">{t.pairs.cointP}</th>
                    <th className="py-2 pr-4 text-right font-medium">{t.pairs.returnCorr}</th>
                    <th className="py-2 pr-4 text-right font-medium">{t.pairs.hedgeRatio}</th>
                    <th className="py-2 pr-4 text-right font-medium">{t.pairs.halfLife}</th>
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
                            {r.coint_pvalue < 0.0001 ? `<${f.num(0.0001, 4)}` : f.num(r.coint_pvalue, 4)}
                          </span>
                          {sig && <span className="sr-only"> {t.pairs.cointegrated}</span>}
                        </td>
                        <td className="py-2 pr-4 text-right text-ink-2">{f.num(r.correlation)}</td>
                        <td className="py-2 pr-4 text-right text-ink-2">{f.num(r.hedge_ratio, 3)}</td>
                        <td className="py-2 pr-4 text-right text-ink-2">
                          {r.half_life == null ? '∞' : t.pairs.days(f.num(r.half_life, 0))}
                        </td>
                        <td className="py-2 text-right">
                          <Link to={`/?${q}`} className="whitespace-nowrap text-xs text-accent hover:underline">
                            {t.pairs.backtestOos}
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
              <h1 className="text-xl font-semibold text-ink">{t.pairs.emptyTitle}</h1>
              <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">{t.pairs.emptyText}</p>
            </div>
          </Card>
        )}
      </section>
    </div>
  )
}
