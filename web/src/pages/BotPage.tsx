import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Badge } from '../components/bot/Badge'
import { ConfigCard } from '../components/bot/ConfigCard'
import { EquityCard } from '../components/bot/EquityCard'
import { EventsCard } from '../components/bot/EventsCard'
import { FillsCard } from '../components/bot/FillsCard'
import { OpenBookCard } from '../components/bot/OpenBookCard'
import { StatusPanel } from '../components/bot/StatusPanel'
import { Button, Card, ErrorBanner, Spinner } from '../components/ui'
import {
  api,
  type BotEquityPoint,
  type BotEvent,
  type BotFill,
  type BotStatus,
  type BotSummary,
} from '../lib/api'
import { longDate } from '../lib/format'

interface BotData {
  status: BotStatus
  equity: BotEquityPoint[]
  fills: BotFill[]
  events: BotEvent[]
}

/** Calendar days without a new bar before the bot counts as stale (covers long weekends). */
const STALE_AFTER_DAYS = 4

function staleness(lastDate: string | null, now = new Date()) {
  if (!lastDate) return null
  const days = Math.floor((now.getTime() - new Date(lastDate + 'T00:00:00').getTime()) / 86_400_000)
  return days > STALE_AFTER_DAYS ? days : null
}

async function fetchBot(bot: string): Promise<BotData> {
  const [status, equity, fills, events] = await Promise.all([
    api.bot(bot),
    api.botEquity(bot),
    api.botFills(bot),
    api.botEvents(bot),
  ])
  return { status, equity, fills, events }
}

function EmptyState() {
  return (
    <Card>
      <div className="mx-auto max-w-xl space-y-3 py-8 text-center">
        <h2 className="font-semibold text-ink">No paper bot yet</h2>
        <p className="text-sm text-ink-2">
          Bots are stepped by a scheduled job, not from the browser. Start one from the backend folder; it trades the
          point-in-time S&amp;P 500 from the last completed close:
        </p>
        <pre className="overflow-x-auto rounded-lg bg-surface-2 px-4 py-3 text-left text-xs text-ink">
          python -m quantlab.bot run --name sp500-pairs
        </pre>
        <p className="text-xs text-muted">Re-run it after each US close (it skips days already processed).</p>
      </div>
    </Card>
  )
}

export function BotPage() {
  const { name } = useParams()
  const navigate = useNavigate()
  const [bots, setBots] = useState<BotSummary[] | null>(null)
  const [data, setData] = useState<BotData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selected = name ?? bots?.[0]?.name

  useEffect(() => {
    api.bots().then(setBots).catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!selected) return
    let cancelled = false // a slow response for a previous bot must not overwrite this one
    fetchBot(selected)
      .then((d) => !cancelled && (setData(d), setError(null)))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [selected])

  const refresh = async () => {
    if (!selected) return
    setLoading(true)
    try {
      setData(await fetchBot(selected))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  if (error && !data) return <ErrorBanner message={error} />
  if (!bots) return <Spinner />
  if (bots.length === 0) return <EmptyState />

  const stale = data && staleness(data.status.last_date)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-semibold text-ink">
            Paper-trading bot
            {data && (
              <Badge tone={stale ? 'warning' : 'good'}>{stale ? `stale · ${stale} days` : 'up to date'}</Badge>
            )}
          </h1>
          <p className="text-sm text-ink-2">
            Multi-pair stat-arb run forward one close at a time against a simulated broker. Paper money only.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {bots.length > 1 && (
            <select
              aria-label="Bot"
              value={selected}
              onChange={(e) => navigate(`/bots/${encodeURIComponent(e.target.value)}`)}
            >
              {bots.map((b) => (
                <option key={b.name} value={b.name}>{b.name}</option>
              ))}
            </select>
          )}
          <Button variant="ghost" onClick={refresh} disabled={loading}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {stale && data?.status.last_date && (
        <div className="rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-ink">
          No new close since {longDate(data.status.last_date)}. Is the daily job running?
        </div>
      )}

      {!data ? (
        <Spinner />
      ) : (
        <>
          <StatusPanel status={data.status} equity={data.equity} events={data.events} />
          <EquityCard points={data.equity} capital={data.status.config.capital} />
          <div className="grid gap-5 lg:grid-cols-2">
            <OpenBookCard status={data.status} />
            <ConfigCard config={data.status.config} />
          </div>
          <EventsCard events={data.events} />
          <FillsCard fills={data.fills} />
        </>
      )}
    </div>
  )
}
