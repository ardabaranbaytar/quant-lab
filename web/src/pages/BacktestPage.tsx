import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ResultView } from '../components/ResultView'
import { TickerInput } from '../components/TickerInput'
import { Button, Card, ErrorBanner, Field, Spinner } from '../components/ui'
import { useI18n } from '../i18n/context'
import { api, type BacktestDetail, type ParamValue, type StrategyInfo } from '../lib/api'

const PRESETS: { id: 'spyTrend' | 'megaCap' | 'pairs' | 'sectorEtfs'; strategy: string; tickers: string[] }[] = [
  { id: 'spyTrend', strategy: 'ts_momentum', tickers: ['SPY'] },
  {
    id: 'megaCap',
    strategy: 'cross_sectional_momentum',
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'JPM', 'JNJ', 'XOM', 'PG', 'KO', 'PEP', 'WMT', 'UNH', 'HD'],
  },
  { id: 'pairs', strategy: 'pairs_trading', tickers: ['V', 'MA'] },
  { id: 'sectorEtfs', strategy: 'mean_reversion', tickers: ['XLK', 'XLF', 'XLE', 'XLV', 'XLI', 'XLP'] },
]

export function BacktestPage() {
  const { t, names } = useI18n()
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
  const [error, setError] = useState<Error | null>(null)
  const [result, setResult] = useState<BacktestDetail | null>(null)

  useEffect(() => {
    api
      .strategies()
      .then((list) => {
        setStrategies(list)
        setParams({ ...list.find((s) => s.name === strategy)?.params })
      })
      .catch(setError)
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
      setError(e as Error)
    } finally {
      setLoading(false)
    }
  }

  const tooFew = info ? tickers.length < info.min_tickers : tickers.length === 0

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        <Card title={t.backtest.configure}>
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => applyPreset(p)}
                  className="rounded-md border border-line px-2 py-1 text-xs text-ink-2 hover:bg-surface-2 hover:text-ink"
                >
                  {t.backtest.presets[p.id]}
                </button>
              ))}
            </div>

            <Field label={t.common.strategy} hint={info && names.strategyDescription(info.name, info.description)}>
              <select value={strategy} onChange={(e) => selectStrategy(e.target.value)}>
                {strategies.map((s) => (
                  <option key={s.name} value={s.name}>
                    {names.strategy(s.name)}
                  </option>
                ))}
              </select>
            </Field>

            <Field
              label={t.common.tickers}
              hint={info && info.min_tickers > 1 ? t.backtest.needsAtLeast(info.min_tickers) : undefined}
            >
              <TickerInput value={tickers} onChange={setTickers} />
            </Field>

            <div className="grid grid-cols-2 gap-3">
              <Field label={t.common.start}>
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label={t.common.end}>
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>

            {info && Object.keys(info.params).length > 0 && (
              <div className="space-y-3 border-t border-line pt-4">
                <div className="text-xs font-semibold text-ink-2">{t.backtest.parameters}</div>
                {Object.entries(info.params).map(([name, def]) => {
                  const isAsset = name.startsWith('asset_')
                  const value = params[name]
                  return (
                    <Field key={name} label={names.param(name)} hint={names.paramHint(name)}>
                      {isAsset ? (
                        <select
                          value={(value as string) ?? ''}
                          onChange={(e) => setParams({ ...params, [name]: e.target.value || null })}
                        >
                          <option value="">{t.backtest.auto}</option>
                          {tickers.map((t) => (
                            <option key={t}>{t}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="number"
                          step={typeof def === 'number' && !Number.isInteger(def) ? 0.05 : 1}
                          value={value === null || value === undefined ? '' : String(value)}
                          placeholder={def === null ? t.backtest.noValue : undefined}
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
              <Field label={t.backtest.costs}>
                <input type="number" min={0} value={costBps} onChange={(e) => setCostBps(Number(e.target.value))} />
              </Field>
              <Field label={t.backtest.riskFree}>
                <input type="number" min={0} step={0.5} value={rf} onChange={(e) => setRf(Number(e.target.value))} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-ink-2">
              <input type="checkbox" className="!w-auto" checked={benchmark} onChange={(e) => setBenchmark(e.target.checked)} />
              {t.backtest.compareSpy}
            </label>

            <Button className="w-full" onClick={run} disabled={loading || tooFew}>
              {loading ? t.backtest.running : t.backtest.run}
            </Button>
          </div>
        </Card>
      </aside>

      <section className="min-w-0 space-y-4">
        {error && <ErrorBanner error={error} />}
        {loading && !result && (
          <Card>
            <Spinner label={t.backtest.fetching} />
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
                <h1 className="text-xl font-semibold text-ink">{t.backtest.emptyTitle}</h1>
                <p className="mx-auto mt-2 max-w-md text-sm text-ink-2">{t.backtest.emptyText}</p>
              </div>
            </Card>
          )
        )}
      </section>
    </div>
  )
}
