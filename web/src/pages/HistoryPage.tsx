import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { PerformanceCharts, type Series } from '../components/PerformanceCharts'
import { Button, Card, ErrorBanner, Spinner } from '../components/ui'
import { useI18n } from '../i18n/context'
import { ApiError, api, type BacktestDetail, type BacktestSummary } from '../lib/api'
import { loadAdminKey, saveAdminKey } from '../lib/admin'

const MAX_COMPARE = 4

export function HistoryPage() {
  const { t, f, names } = useI18n()
  const [runs, setRuns] = useState<BacktestSummary[] | null>(null)
  const [error, setError] = useState<Error | null>(null)
  // run id -> colour slot. A run keeps its slot while selected, so toggling
  // another run never repaints it.
  const [slots, setSlots] = useState<Map<number, number>>(new Map())
  const [details, setDetails] = useState<Map<number, BacktestDetail>>(new Map())

  // Deleting is for the owner: the server only offers it when it has a key, and only the right key works.
  const [adminEnabled, setAdminEnabled] = useState(false)
  const [adminKey, setAdminKey] = useState<string | null>(null) // set once the server has accepted it
  const [keyFormOpen, setKeyFormOpen] = useState(false)
  const [draftKey, setDraftKey] = useState('')
  const [confirmAll, setConfirmAll] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<Error | null>(null)

  useEffect(() => {
    api.backtests().then(setRuns).catch(setError)
    const saved = loadAdminKey()
    api
      .adminSession(saved)
      .then((session) => {
        setAdminEnabled(session.enabled)
        if (session.authorized) setAdminKey(saved)
        else if (saved) saveAdminKey(null)
      })
      .catch(() => {
        /* the list works without admin; nothing to show */
      })
  }, [])

  const toggle = async (id: number) => {
    const next = new Map(slots)
    if (next.has(id)) {
      next.delete(id)
      setSlots(next)
      return
    }
    if (next.size >= MAX_COMPARE) return
    const used = new Set(next.values())
    const slot = [1, 2, 3, 4].find((s) => !used.has(s))!
    next.set(id, slot)
    setSlots(next)
    if (!details.has(id)) {
      try {
        const d = await api.backtest(id)
        setDetails((prev) => new Map(prev).set(id, d))
      } catch (e) {
        setError(e as Error)
      }
    }
  }

  const unlock = async (e: FormEvent) => {
    e.preventDefault()
    const key = draftKey.trim()
    if (!key) return
    setNotice(null)
    setActionError(null)
    try {
      const session = await api.adminSession(key)
      if (!session.authorized) {
        setNotice(t.history.admin.wrongKey)
        return
      }
      saveAdminKey(key)
      setAdminKey(key)
      setKeyFormOpen(false)
      setDraftKey('')
    } catch (err) {
      setActionError(err as Error)
    }
  }

  const signOut = () => {
    saveAdminKey(null)
    setAdminKey(null)
    setConfirmAll(false)
  }

  const remove = async (target: { ids: number[] } | { delete_all: true }) => {
    if (!adminKey) return
    setNotice(null)
    setActionError(null)
    try {
      await api.deleteBacktests(adminKey, target)
      const without = <V,>(m: Map<number, V>) => {
        const next = new Map(m)
        for (const id of 'ids' in target ? target.ids : [...m.keys()]) next.delete(id)
        return next
      }
      setSlots(without)
      setDetails(without)
      setRuns(await api.backtests()) // refill the list: older runs may now fit
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        signOut()
        setNotice(t.history.admin.rejected)
      } else {
        setActionError(err as Error)
      }
    }
  }

  const series: Series[] = useMemo(
    () =>
      [...slots]
        .filter(([id]) => details.has(id))
        .map(([id, slot]) => {
          const d = details.get(id)!
          return { key: `run${id}`, label: `#${id} ${names.strategy(d.strategy)}`, slot, points: d.points }
        }),
    [slots, details, names],
  )

  if (error) return <ErrorBanner error={error} />
  if (!runs) return <Spinner />

  const admin = t.history.admin

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-ink">{t.history.title}</h1>
          <p className="text-sm text-ink-2">{t.history.subtitle(MAX_COMPARE)}</p>
        </div>

        {adminEnabled && (
          <div className="flex flex-wrap items-center gap-2">
            {adminKey ? (
              confirmAll ? (
                <>
                  <span className="text-sm text-ink-2">{admin.confirmAll}</span>
                  <Button
                    variant="danger"
                    onClick={() => {
                      setConfirmAll(false)
                      void remove({ delete_all: true })
                    }}
                  >
                    {admin.confirmYes}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmAll(false)}>
                    {admin.cancel}
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="ghost" onClick={() => setConfirmAll(true)} disabled={runs.length === 0}>
                    {admin.deleteAll}
                  </Button>
                  <Button variant="ghost" onClick={signOut}>
                    {admin.signOut}
                  </Button>
                </>
              )
            ) : keyFormOpen ? (
              <form onSubmit={unlock} className="flex flex-wrap items-center gap-2">
                <input
                  type="password"
                  autoComplete="off"
                  autoFocus
                  aria-label={admin.keyLabel}
                  placeholder={admin.keyLabel}
                  value={draftKey}
                  onChange={(e) => setDraftKey(e.target.value)}
                  className="!w-56"
                />
                <Button type="submit" disabled={!draftKey.trim()}>
                  {admin.unlock}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setKeyFormOpen(false)
                    setNotice(null)
                  }}
                >
                  {admin.cancel}
                </Button>
              </form>
            ) : (
              <Button variant="ghost" onClick={() => setKeyFormOpen(true)}>
                {admin.open}
              </Button>
            )}
          </div>
        )}
      </div>

      {notice && (
        <div role="alert" className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-ink">
          {notice}
        </div>
      )}
      {actionError && <ErrorBanner error={actionError} />}

      {series.length > 0 && <PerformanceCharts series={series} title={t.charts.comparison} />}

      <Card>
        {runs.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted">
            {t.history.noRuns}
            <Link to="/" className="text-accent hover:underline">{t.history.firstRun}</Link>
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="w-8 py-2" />
                  <th className="py-2 pr-4 font-medium">{t.history.run}</th>
                  <th className="py-2 pr-4 font-medium">{t.common.strategy}</th>
                  <th className="py-2 pr-4 font-medium">{t.common.tickers}</th>
                  <th className="py-2 pr-4 font-medium">{t.history.period}</th>
                  <th className="py-2 pr-4 text-right font-medium">{t.history.return}</th>
                  <th className="py-2 pr-4 text-right font-medium">{t.history.sharpe}</th>
                  <th className="py-2 text-right font-medium">{t.history.maxDd}</th>
                  {adminKey && <th className="w-16 py-2" />}
                </tr>
              </thead>
              <tbody className="tabular">
                {runs.map((r) => {
                  const slot = slots.get(r.id)
                  const disabled = !slot && slots.size >= MAX_COMPARE
                  return (
                    <tr key={r.id} className="border-b border-line/50 last:border-0 hover:bg-surface-2/50">
                      <td className="py-2">
                        <label className="flex items-center gap-1.5">
                          <input
                            type="checkbox"
                            className="!w-auto"
                            checked={!!slot}
                            disabled={disabled}
                            onChange={() => toggle(r.id)}
                            aria-label={t.history.compareRun(r.id)}
                          />
                          {slot && <span className="h-0.5 w-3 rounded" style={{ background: `var(--series-${slot})` }} />}
                        </label>
                      </td>
                      <td className="py-2 pr-4">
                        <Link to={`/runs/${r.id}`} className="text-accent hover:underline">#{r.id}</Link>
                      </td>
                      <td className="py-2 pr-4 text-ink">{names.strategy(r.strategy)}</td>
                      <td className="max-w-48 truncate py-2 pr-4 text-ink-2" title={r.tickers.join(', ')}>
                        {r.tickers.join(', ')}
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-ink-2">
                        {r.start_date.slice(0, 4)}–{r.end_date.slice(0, 4)}
                      </td>
                      <td className={`py-2 pr-4 text-right ${(r.metrics.total_return ?? 0) < 0 ? 'text-critical' : 'text-ink'}`}>
                        {f.pct(r.metrics.total_return)}
                      </td>
                      <td className="py-2 pr-4 text-right text-ink">{f.num(r.metrics.sharpe)}</td>
                      <td className="py-2 text-right text-ink-2">{f.pct(r.metrics.max_drawdown)}</td>
                      {adminKey && (
                        <td className="py-2 pl-3 text-right">
                          <button
                            type="button"
                            onClick={() => remove({ ids: [r.id] })}
                            aria-label={admin.deleteRun(r.id)}
                            className="text-xs text-muted hover:text-critical"
                          >
                            {admin.delete}
                          </button>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
