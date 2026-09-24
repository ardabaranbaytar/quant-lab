import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ResultView } from '../components/ResultView'
import { TickerInput } from '../components/TickerInput'
import { Button, Card, ErrorBanner, Field, Spinner } from '../components/ui'
import { api, type BacktestDetail, type ParamValue, type StrategyInfo } from '../lib/api'
import { humanize } from '../lib/format'

const PRESETS: { label: string; strategy: string; tickers: string[]; params?: Record<string, ParamValue> }[] = [
  { label: 'SPY trend', strategy: 'ts_momentum', tickers: ['SPY'] },
  {
    label: 'Mega-cap momentum',
    strategy: 'cross_sectional_momentum',
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'JPM', 'JNJ', 'XOM', 'PG', 'KO', 'PEP', 'WMT', 'UNH', 'HD'],
  },
  { label: 'V / MA pairs', strategy: 'pairs_trading', tickers: ['V', 'MA'] },
  { label: 'Sector ETFs mean-rev', strategy: 'mean_reversion', tickers: ['XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLP'] },
]

const PARAM_HINTS: Record<string, string> = {
  lookback: 'Trading days of past return used for the signal',
  top_n: 'Number of winners held each month',
  skip_days: 'Most recent days excluded (12-1 momentum uses ~21)',
  window: 'Moving-average length in days',
  threshold: 'Distance below the SMA that triggers a buy (0.05 = 5%)',
  hedge_window: 'Days of history for the rolling hedge ratio',
  z_window: 'Days used to normalise the spread',
  entry_z: 'Open a trade when |z| exceeds this',
  exit_z: 'Close when z crosses back through this',
  stop_z: 'Optional stop-loss on |z| (blank = none)',
}

export function BacktestPage() {
  const [search] = useSearchParams()
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [strategy, setStrategy] = useState(search.get('strategy') ?? 'cross_sectional_momentum')
  const [tickers, setTickers] = useState<string[]>(
    search.get('tickers')?.split(',').filter(Boolean) ?? PRESETS[1].tickers,
  )
  const [start, setStart] = useState(search.get('start') ?? '2015-01-01')
  const [end, setEnd] = useState(search.get('end') ?? '2024-12-31')
  const [params, setParams] = useState<Record<string, ParamValue>>({})
  const [costBps, setCostBps] = useState(10)
  const [rf, setRf] = useState(0)
  const [benchmark, setBenchmark] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestDetail | null>(null)

  useEffect(() => {
    api
      .strategies()
      .then((list) => {
        setStrategies(list)
        setParams({ ...list.find((s) => s.name === strategy)?.params })
      })
      .catch((e: Error) => setError(e.message))
    // Load once; the initial strategy comes from the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const info = strategies.find((s) => s.name === strategy)

  // Switching strategy resets its parameters to the defaults.
  const selectStrategy = (name: string) => {
    setStrategy(name)
    setParams({ ...strategies.find((s) => s.name === name)?.params })
  }

  const applyPreset = (p: (typeof PRESETS)[number]) => {
    selectStrategy(p.strategy)
    setTickers(p.tickers)
  }

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      // Blank fields fall back to the server-side defaults.
      const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== null && v !== ''))
      setResult(
        await api.runBacktest({
          strategy,
          tickers,
          start,
          end,
          params: clean,
          cost_rate: costBps / 1e4,
          risk_free_rate: rf / 100,
          benchmark: benchmark ? 'SPY' : null,
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const tooFew = info ? tickers.length < info.min_tickers : tickers.length === 0

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <Card title="Configure">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  className="rounded-md border border-line px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
                >
                  {p.label}
                </button>
              ))}
            </div>

            <Field label="Strategy" hint={info?.description}>
              <select value={strategy} onChange={(e) => selectStrategy(e.target.value)}>
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>
                    {humanize(s.name)}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Tickers" hint={info && info.min_tickers > 1 ? `Needs at least ${info.min_tickers}` : undefined}>
              <TickerInput value={tickers} onChange={setTickers} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Start">
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label="End">
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>

            {info && Object.keys(info.params).length > 0 && (
              <div className="space-y-3 border-t border-line pt-4">
                <div className="text-xs font-semibold text-ink-2">Parameters</div>
                {Object.entries(info.params).map(([name, def]) => {
                  const isAsset = name.startsWith('asset_')
                  const value = params[name]
                  return (
                    <Field key={name} label={humanize(name)} hint={isAsset ? 'Defaults to ticker order' : PARAM_HINTS[name]}>
                      {isAsset ? (
                        <select
                          value={(value as string) ?? ''}
                          onChange={(e) => setParams({ ...params, [name]: e.target.value || null })}
                        >
                          <option value="">Auto</option>
                          {tickers.map((t) => (
                            <option key={t}>{t}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="number"
                          step={typeof def === 'number' && !Number.isInteger(def) ? 0.05 : 1}
                          value={value === null || value === undefined ? '' : String(value)}
                          placeholder={def === null ? 'none' : undefined}
                          onChange={(e) =>
                            setParams({ ...params, [name]: e.target.value === '' ? null : Number(e.target.value) })
                          }
                        />
                      )}
                    </Field>
                  )
                })}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 border-t border-line pt-4">
              <Field label="Costs (bps)">
                <input type="number" min={0} value={costBps} onChange={(e) => setCostBps(Number(e.target.value))} />
              </Field>
              <Field label="Risk-free (%)">
                <input type="number" min={0} step={0.5} value={rf} onChange={(e) => setRf(Number(e.target.value))} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-ink-2">
              <input type="checkbox" className="!w-auto" checked={benchmark} onChange={(e) => setBenchmark(e.target.checked)} />
              Compare with SPY
            </label>

            <Button className="w-full" onClick={run} disabled={loading || tooFew}>
              {loading ? 'Running…' : 'Run backtest'}
            </Button>
          </div>
        </Card>
      </aside>

      <section className="min-w-0 space-y-4">
        {error && <ErrorBanner message={error} />}
        {loading && !result && (
          <Card>
            <Spinner label="Fetching prices and running the backtest…" />
          </Card>
        )}
        {result ? (
          <div className={loading ? 'opacity-50 transition' : 'transition'}>
            <ResultView run={result} />
          </div>
        ) : (
          !loading && (
            <Card>
              <div className="py-16 text-center">
                <h1 className="text-xl font-semibold text-ink">Backtest a strategy</h1>
                <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">
                  Pick a preset or configure a strategy on the left. Prices are cached in MySQL, signals use only
                  information available at each close, and costs are charged on actual turnover.
                </p>
              </div>
            </Card>
          )
        )}
      </section>
    </div>
  )
}
